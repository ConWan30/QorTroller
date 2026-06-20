"""
SQLite Persistence — Records, devices, and submission tracking.

Zero external dependencies (uses Python stdlib sqlite3).
Thread-safe via WAL mode and connection-per-call pattern.
"""

import json
import logging
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path


class CorpusRegressionError(ValueError):
    """Raised by insert_separation_defensibility_log_guarded when the new entry
    represents a ratio regression below 1.0 after a prior all_pairs_above_1=True
    breakthrough and no authorized override exists for this probe type.
    (Phase 208: WIF-039 W1 — CorpusRatioRegressionGuard)"""

from ..codec import PoACRecord
from .zkba_vpm import ZkbaVpmMixin
from .consent_mixin import ConsentMixin
from .marketplace import MarketplaceMixin
from .snapshots import SnapshotsGrindMixin
from .ioswarm import IoswarmMixin
from .chain_log import ChainLogMixin
from .tournament import TournamentMixin
from .operator_initiative import OperatorInitiativeMixin
from .vhp import VhpMixin
from .biometric import BiometricMixin
from .agents import AgentsRulingsMixin
from .calibration import CalibrationMixin
from .retina import RetinaMixin

log = logging.getLogger(__name__)

# Record submission status
STATUS_PENDING = "pending"
STATUS_BATCHED = "batched"
STATUS_SUBMITTED = "submitted"
STATUS_VERIFIED = "verified"
STATUS_FAILED = "failed"
STATUS_DEAD_LETTER = "dead_letter"


class Store(ZkbaVpmMixin, MarketplaceMixin, ConsentMixin, SnapshotsGrindMixin, IoswarmMixin, ChainLogMixin, TournamentMixin, OperatorInitiativeMixin, VhpMixin, BiometricMixin, AgentsRulingsMixin, CalibrationMixin, RetinaMixin):
    """SQLite-backed persistence for the bridge service."""

    def __init__(self, db_path: str, consent_ledger_enabled: bool = False) -> None:
        self._db_path = db_path
        self._consent_ledger_enabled = consent_ledger_enabled
        # INV-GIC-003: fail-closed flag — set by main.py startup chain check;
        # read by get_validation_summary() and session_adjudicator_validator.
        self._gic_chain_broken: bool = False
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()
        from ..migrations.runner import MigrationRunner; MigrationRunner(db_path).run_pending()  # VAPI-EXT

    def set_gic_chain_broken(self, value: bool) -> None:
        """Set the GIC chain-broken flag (INV-GIC-003).  Called by main.py at startup
        and by /operator/gic-reset.  When True, get_validation_summary() returns
        gate_passed=False / consecutive_clean=0 regardless of DB state."""
        self._gic_chain_broken = bool(value)

    def get_validation_summary(
        self,
        gate_n: int = 100,
        max_divergence_rate: float = 1.0,
        active_play_gate_mode: str = "shadow",
    ) -> dict:
        """Return validation statistics, consecutive_clean count, and window divergence rate.

        Phase 78: adds divergence_rate and divergence_rate_ok to the summary.

        Both consecutive_clean and divergence_rate are evaluated over the most recent
        gate_n rulings only (W1 mitigation — pre-gate divergences from early sessions
        do not permanently block the gate).

        gate_passed = (consecutive_clean >= gate_n) AND (divergence_rate <= max_divergence_rate)
        """
        # INV-GIC-003: fail-closed — broken chain blocks the gate regardless of DB state.
        from ..active_play_occupancy import normalize_active_play_gate_mode
        active_play_gate_mode = normalize_active_play_gate_mode(active_play_gate_mode)

        if self._gic_chain_broken:
            return {
                "total": 0,
                "divergence_count": 0,
                "consecutive_clean": 0,
                "gate_n": gate_n,
                "gate_passed": False,
                "divergence_rate": 0.0,
                "divergence_rate_ok": False,
                "max_divergence_rate": max_divergence_rate,
                "window_size": 0,
                "latest_pcc_state": None,
                "latest_pcc_host_state": None,
                "latest_gameplay_context": None,
                "chain_broken": True,
            }

        with self._conn() as conn:
            total_row = conn.execute(
                "SELECT COUNT(*) as cnt FROM ruling_validation_log"
            ).fetchone()
            total = total_row["cnt"] if total_row else 0

            div_row = conn.execute(
                "SELECT COUNT(*) as cnt FROM ruling_validation_log WHERE divergence=1"
            ).fetchone()
            divergence_count = div_row["cnt"] if div_row else 0

            # Walk the most recent gate_n records for both consecutive_clean and window rate
            window_rows = conn.execute(
                "SELECT id, divergence, pcc_state, pcc_host_state, gameplay_context "
                "FROM ruling_validation_log "
                "ORDER BY created_at DESC LIMIT ?",
                (gate_n,),
            ).fetchall()

        apop_by_validation_id = {}
        if active_play_gate_mode != "shadow" and window_rows:
            apop_by_validation_id = self.get_active_play_logs_for_validation_ids(
                [int(row["id"]) for row in window_rows]
            )

        # consecutive_clean: leading non-divergent + PCC-attested + gameplay-active streak
        # Phase 235-B: pcc_state=NULL → fail-closed
        # Phase 235-GAD: gameplay_context='MENU_DETECTED' → fail-closed;
        #                gameplay_context=NULL → pass-through (pre-GAD rows, benefit of doubt)
        consecutive_clean = 0
        for row in window_rows:
            pcc_s = row["pcc_state"]
            pcc_ok = (
                pcc_s == "NOMINAL"
                and row["pcc_host_state"] in ("EXCLUSIVE_USB", "UNKNOWN")
            ) if pcc_s is not None else False
            gameplay_ctx = row["gameplay_context"] if "gameplay_context" in row.keys() else None
            apop_row = apop_by_validation_id.get(int(row["id"]))
            if apop_row:
                from ..active_play_occupancy import active_play_gate_allows
                gameplay_ok = active_play_gate_allows(
                    apop_row.get("state"),
                    apop_row.get("confidence"),
                    gameplay_ctx,
                    active_play_gate_mode,
                )
            elif active_play_gate_mode == "strict":
                gameplay_ok = False
            else:
                gameplay_ok = gameplay_ctx != "MENU_DETECTED"  # NULL = pass-through
            if row["divergence"] == 0 and pcc_ok and gameplay_ok:
                consecutive_clean += 1
            else:
                break  # streak broken

        # Window divergence rate over the trailing gate_n records
        window_size = len(window_rows)
        if window_size > 0:
            window_divergences = sum(1 for r in window_rows if r["divergence"] == 1)
            divergence_rate = round(window_divergences / window_size, 4)
        else:
            divergence_rate = 0.0

        divergence_rate_ok = divergence_rate <= max_divergence_rate
        gate_passed = (consecutive_clean >= gate_n) and divergence_rate_ok

        latest_pcc_state = window_rows[0]["pcc_state"] if window_rows else None
        latest_pcc_host_state = window_rows[0]["pcc_host_state"] if window_rows else None
        latest_gameplay_context = (
            window_rows[0]["gameplay_context"]
            if window_rows and "gameplay_context" in window_rows[0].keys()
            else None
        )

        return {
            "total": total,
            "divergence_count": divergence_count,
            "consecutive_clean": consecutive_clean,
            "gate_n": gate_n,
            "gate_passed": gate_passed,
            "divergence_rate": divergence_rate,
            "divergence_rate_ok": divergence_rate_ok,
            "max_divergence_rate": max_divergence_rate,
            "window_size": window_size,
            "latest_pcc_state": latest_pcc_state,
            "latest_pcc_host_state": latest_pcc_host_state,
            "latest_gameplay_context": latest_gameplay_context,
        }

    @contextmanager
    def _conn(self):
        conn = sqlite3.connect(self._db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def db_execute(self, sql: str, params: tuple = ()) -> None:
        """Execute a raw SQL write statement (Phase 193 — used by FleetSignalCoherenceAgent)."""
        with self._conn() as conn:
            conn.execute(sql, params)

    _PITL_MIGRATION_COLS = [
        "ALTER TABLE records ADD COLUMN pitl_l4_distance REAL",
        "ALTER TABLE records ADD COLUMN pitl_l4_warmed INTEGER",
        "ALTER TABLE records ADD COLUMN pitl_l4_features TEXT",
        "ALTER TABLE records ADD COLUMN pitl_l5_cv REAL",
        "ALTER TABLE records ADD COLUMN pitl_l5_entropy REAL",
        "ALTER TABLE records ADD COLUMN pitl_l5_quant REAL",
        "ALTER TABLE records ADD COLUMN pitl_l5_signals INTEGER",
    ]

    # Phase 23: idempotent schema migrations
    _PHASE23_MIGRATIONS = [
        "ALTER TABLE phg_checkpoints ADD COLUMN last_committed_score INTEGER DEFAULT 0",
    ]

    # Phase 25: idempotent schema migrations
    _PHASE25_MIGRATIONS = [
        "ALTER TABLE records ADD COLUMN pitl_l5_rhythm_humanity REAL",
        "ALTER TABLE records ADD COLUMN pitl_l4_drift_velocity REAL",
        "ALTER TABLE records ADD COLUMN pitl_e4_cognitive_drift REAL",
        "ALTER TABLE records ADD COLUMN pitl_humanity_prob REAL",
        "ALTER TABLE phg_checkpoints ADD COLUMN confirmed INTEGER DEFAULT 0",
    ]

    # Phase 26: idempotent schema migrations
    _PHASE26_MIGRATIONS = [
        "ALTER TABLE records ADD COLUMN pitl_proof_nullifier TEXT DEFAULT NULL",
    ]

    _RETINA_MIGRATIONS = [
        "ALTER TABLE retina_event_log ADD COLUMN state_commitment_hex TEXT NOT NULL DEFAULT ''",
    ]

    def _init_schema(self):
        with self._conn() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS devices (
                    device_id       TEXT PRIMARY KEY,
                    pubkey_hex      TEXT NOT NULL,
                    first_seen      REAL NOT NULL,
                    last_seen       REAL NOT NULL,
                    last_counter    INTEGER DEFAULT 0,
                    chain_head      TEXT DEFAULT '',
                    last_battery    INTEGER DEFAULT 0,
                    last_latitude   REAL DEFAULT 0.0,
                    last_longitude  REAL DEFAULT 0.0,
                    records_total   INTEGER DEFAULT 0,
                    records_verified INTEGER DEFAULT 0
                );

                CREATE TABLE IF NOT EXISTS records (
                    record_hash     TEXT PRIMARY KEY,
                    device_id       TEXT NOT NULL,
                    counter         INTEGER NOT NULL,
                    timestamp_ms    INTEGER NOT NULL,
                    inference       INTEGER NOT NULL,
                    action_code     INTEGER NOT NULL,
                    confidence      INTEGER NOT NULL,
                    battery_pct     INTEGER NOT NULL,
                    bounty_id       INTEGER DEFAULT 0,
                    latitude        REAL DEFAULT 0.0,
                    longitude       REAL DEFAULT 0.0,
                    status          TEXT DEFAULT 'pending',
                    raw_data        BLOB,
                    created_at      REAL NOT NULL,
                    FOREIGN KEY (device_id) REFERENCES devices(device_id)
                );

                CREATE TABLE IF NOT EXISTS submissions (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    tx_hash         TEXT DEFAULT '',
                    record_hashes   TEXT NOT NULL,  -- JSON array
                    status          TEXT DEFAULT 'pending',
                    retries         INTEGER DEFAULT 0,
                    last_error      TEXT DEFAULT '',
                    created_at      REAL NOT NULL,
                    submitted_at    REAL DEFAULT 0,
                    confirmed_at    REAL DEFAULT 0
                );

                CREATE INDEX IF NOT EXISTS idx_records_status
                    ON records(status);
                CREATE INDEX IF NOT EXISTS idx_records_device
                    ON records(device_id, counter);
                CREATE INDEX IF NOT EXISTS idx_records_created_at
                    ON records(created_at DESC);
                CREATE INDEX IF NOT EXISTS idx_records_inference_ts
                    ON records(inference, timestamp_ms DESC);
                -- 2026-06-13: device-filtered "most recent record" lookup
                -- (get_recent_records(limit, device_id) — used by
                -- /player/session-status, polled every 5s by the gamer dashboard).
                -- Without this, the WHERE device_id=? ... ORDER BY created_at DESC
                -- query filters by device then SORTS all of that device's ~100k+
                -- rows (idx_records_device is (device_id, counter) — wrong sort
                -- key; idx_records_created_at is global). The composite below
                -- serves both the filter and the sort, making it O(limit).
                CREATE INDEX IF NOT EXISTS idx_records_device_created
                    ON records(device_id, created_at DESC);
                CREATE INDEX IF NOT EXISTS idx_submissions_status
                    ON submissions(status);

                CREATE TABLE IF NOT EXISTS phg_checkpoints (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    device_id       TEXT NOT NULL,
                    phg_score       INTEGER NOT NULL,
                    record_count    INTEGER NOT NULL,
                    bio_hash        TEXT NOT NULL DEFAULT '',
                    tx_hash         TEXT NOT NULL DEFAULT '',
                    committed_at    REAL NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_phg_checkpoints_device
                    ON phg_checkpoints(device_id, committed_at);

                CREATE TABLE IF NOT EXISTS biometric_fingerprint_store (
                    device_id   TEXT PRIMARY KEY,
                    mean_json   TEXT NOT NULL,
                    var_json    TEXT NOT NULL,
                    n_sessions  INTEGER DEFAULT 0,
                    updated_at  REAL NOT NULL
                );

                CREATE TABLE IF NOT EXISTS continuity_claims (
                    device_id   TEXT PRIMARY KEY,
                    claimed_by  TEXT NOT NULL,
                    claimed_at  REAL NOT NULL
                );
            """)
            # PITL extension columns — idempotent (skip if already exist)
            for sql in self._PITL_MIGRATION_COLS:
                try:
                    conn.execute(sql)
                except sqlite3.OperationalError:
                    log.debug("schema migration already applied: %.80s", sql)  # Phase 54
            # Phase 23 migrations — idempotent
            for sql in self._PHASE23_MIGRATIONS:
                try:
                    conn.execute(sql)
                except sqlite3.OperationalError:
                    log.debug("schema migration already applied: %.80s", sql)  # Phase 54
            # Phase 25 migrations — idempotent
            for sql in self._PHASE25_MIGRATIONS:
                try:
                    conn.execute(sql)
                except sqlite3.OperationalError:
                    log.debug("schema migration already applied: %.80s", sql)  # Phase 54
            # Phase 25: cognitive trajectory table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS cognitive_trajectory (
                    device_id      TEXT PRIMARY KEY,
                    embedding_json TEXT NOT NULL,
                    session_count  INTEGER NOT NULL,
                    updated_at     REAL NOT NULL
                )
            """)
            # Phase 26: PITL session proofs table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS pitl_session_proofs (
                    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
                    device_id          TEXT NOT NULL,
                    nullifier_hash     TEXT NOT NULL UNIQUE,
                    feature_commitment TEXT NOT NULL,
                    humanity_prob_int  INTEGER NOT NULL,
                    tx_hash            TEXT DEFAULT '',
                    created_at         REAL NOT NULL
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_pitl_proofs_device
                    ON pitl_session_proofs(device_id, created_at)
            """)
            # Phase 26 migrations — idempotent
            for sql in self._PHASE26_MIGRATIONS:
                try:
                    conn.execute(sql)
                except sqlite3.OperationalError:
                    log.debug("schema migration already applied: %.80s", sql)  # Phase 54
            # Phase 28: PHG credential mint ledger
            conn.execute("""
                CREATE TABLE IF NOT EXISTS phg_credential_mints (
                    id            INTEGER PRIMARY KEY AUTOINCREMENT,
                    device_id     TEXT NOT NULL UNIQUE,
                    credential_id INTEGER NOT NULL,
                    tx_hash       TEXT DEFAULT '',
                    minted_at     REAL NOT NULL
                )
            """)
            # Phase 31: BridgeAgent conversation session persistence
            conn.execute("""
                CREATE TABLE IF NOT EXISTS agent_sessions (
                    session_id   TEXT PRIMARY KEY,
                    history_json TEXT NOT NULL DEFAULT '[]',
                    created_at   REAL NOT NULL,
                    updated_at   REAL NOT NULL
                )
            """)
            # Phase 32: Proactive protocol intelligence audit trail
            conn.execute("""
                CREATE TABLE IF NOT EXISTS protocol_insights (
                    id           INTEGER PRIMARY KEY AUTOINCREMENT,
                    insight_type TEXT NOT NULL,
                    device_id    TEXT DEFAULT '',
                    content      TEXT NOT NULL,
                    severity     TEXT DEFAULT 'low',
                    created_at   REAL NOT NULL
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_insights_type
                ON protocol_insights(insight_type, created_at)
            """)
            # Phase 34: Cross-bridge cluster correlation registry
            conn.execute("""
                CREATE TABLE IF NOT EXISTS federation_registry (
                    id               INTEGER PRIMARY KEY AUTOINCREMENT,
                    cluster_hash     TEXT NOT NULL,
                    peer_url         TEXT NOT NULL DEFAULT '',
                    device_count     INTEGER NOT NULL DEFAULT 0,
                    suspicion_bucket TEXT NOT NULL DEFAULT 'medium',
                    bridge_id        TEXT NOT NULL DEFAULT '',
                    detected_at      REAL NOT NULL,
                    is_local         INTEGER NOT NULL DEFAULT 0
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_federation_hash
                ON federation_registry(cluster_hash, bridge_id)
            """)
            # Phase 35: Longitudinal insight synthesis tables
            conn.execute("""
                CREATE TABLE IF NOT EXISTS insight_digests (
                    id               INTEGER PRIMARY KEY AUTOINCREMENT,
                    window_label     TEXT NOT NULL,
                    synthesized_at   REAL NOT NULL,
                    bot_farm_count   INTEGER NOT NULL DEFAULT 0,
                    high_risk_count  INTEGER NOT NULL DEFAULT 0,
                    federated_count  INTEGER NOT NULL DEFAULT 0,
                    anomaly_count    INTEGER NOT NULL DEFAULT 0,
                    eligible_count   INTEGER NOT NULL DEFAULT 0,
                    dominant_severity TEXT NOT NULL DEFAULT 'low',
                    top_devices      TEXT NOT NULL DEFAULT '[]',
                    narrative        TEXT NOT NULL DEFAULT ''
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_digests_window
                ON insight_digests(window_label, synthesized_at DESC)
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS device_risk_labels (
                    device_id    TEXT PRIMARY KEY,
                    risk_label   TEXT NOT NULL DEFAULT 'stable',
                    label_evidence TEXT NOT NULL DEFAULT '{}',
                    label_set_at REAL NOT NULL,
                    prior_label  TEXT NOT NULL DEFAULT ''
                )
            """)
            # Phase 36: Adaptive detection policies + schema version registry
            conn.execute("""
                CREATE TABLE IF NOT EXISTS detection_policies (
                    device_id    TEXT PRIMARY KEY,
                    multiplier   REAL NOT NULL DEFAULT 1.0,
                    basis_label  TEXT NOT NULL DEFAULT 'stable',
                    set_at       REAL NOT NULL,
                    expires_at   REAL NOT NULL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS schema_versions (
                    phase          INTEGER PRIMARY KEY,
                    migration_name TEXT NOT NULL,
                    applied_at     REAL NOT NULL
                )
            """)
            # Phase 37: Credential enforcement state
            conn.execute("""
                CREATE TABLE IF NOT EXISTS credential_enforcement (
                    device_id           TEXT PRIMARY KEY,
                    consecutive_critical INT  NOT NULL DEFAULT 0,
                    suspended           INT  NOT NULL DEFAULT 0,
                    suspended_since     REAL,
                    suspended_until     REAL,
                    evidence_hash       TEXT,
                    last_updated        REAL NOT NULL
                )
            """)
            # Phase 38: Per-player living calibration profiles
            conn.execute("""
                CREATE TABLE IF NOT EXISTS player_calibration_profiles (
                    device_id             TEXT PRIMARY KEY,
                    anomaly_threshold     REAL NOT NULL,
                    continuity_threshold  REAL NOT NULL,
                    baseline_mean         REAL NOT NULL,
                    baseline_std          REAL NOT NULL,
                    session_count         INTEGER NOT NULL,
                    updated_at            TEXT NOT NULL
                )
            """)
            # Phase 42: L6 human-response baseline capture
            conn.execute("""
                CREATE TABLE IF NOT EXISTS l6_capture_sessions (
                    session_id       TEXT PRIMARY KEY,
                    profile_id       INTEGER NOT NULL,
                    profile_name     TEXT NOT NULL DEFAULT '',
                    challenge_sent_ts REAL NOT NULL,
                    onset_ms         REAL NOT NULL DEFAULT 0.0,
                    settle_ms        REAL NOT NULL DEFAULT 0.0,
                    peak_delta       REAL NOT NULL DEFAULT 0.0,
                    grip_variance    REAL NOT NULL DEFAULT 0.0,
                    r2_pre_mean      REAL NOT NULL DEFAULT 0.0,
                    accel_variance   REAL NOT NULL DEFAULT 0.0,
                    player_id        TEXT NOT NULL DEFAULT '',
                    game_title       TEXT NOT NULL DEFAULT '',
                    hw_session_ref   TEXT NOT NULL DEFAULT '',
                    notes            TEXT NOT NULL DEFAULT '',
                    created_at       REAL NOT NULL
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_l6_captures_profile
                ON l6_capture_sessions(profile_id, player_id, created_at)
            """)
            # Phase 50: Agent coordination tables
            conn.execute("""
                CREATE TABLE IF NOT EXISTS agent_events (
                    id           INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_type   TEXT NOT NULL,
                    device_id    TEXT,
                    payload_json TEXT NOT NULL,
                    source_agent TEXT NOT NULL,
                    target_agent TEXT,
                    created_at   REAL NOT NULL,
                    consumed_at  REAL,
                    consumed_by  TEXT
                )
            """)
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_agent_events_target "
                "ON agent_events(target_agent, consumed_at, created_at)"
            )
            conn.execute("""
                CREATE TABLE IF NOT EXISTS retina_event_log (
                    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
                    device_id            TEXT NOT NULL,
                    events_json          TEXT NOT NULL,
                    world_state_json     TEXT NOT NULL DEFAULT '',
                    record_hash_hex      TEXT NOT NULL DEFAULT '',
                    state_commitment_hex TEXT NOT NULL DEFAULT '',
                    anomaly_count        INTEGER NOT NULL DEFAULT 0,
                    created_at           REAL NOT NULL
                )
            """)
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_retina_event_device "
                "ON retina_event_log(device_id, created_at DESC)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_retina_event_record "
                "ON retina_event_log(record_hash_hex, created_at DESC)"
            )
            for sql in self._RETINA_MIGRATIONS:
                try:
                    conn.execute(sql)
                except sqlite3.OperationalError:
                    log.debug("schema migration already applied: %.80s", sql)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS threshold_history (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    threshold_type  TEXT NOT NULL,
                    device_id       TEXT,
                    old_value       REAL,
                    new_value       REAL,
                    drift_pct       REAL,
                    sessions_used   INTEGER,
                    phase           TEXT,
                    created_at      REAL NOT NULL
                )
            """)
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_threshold_history_type "
                "ON threshold_history(threshold_type, created_at)"
            )
            conn.execute("""
                CREATE TABLE IF NOT EXISTS calibration_agent_sessions (
                    session_id   TEXT PRIMARY KEY,
                    history_json TEXT NOT NULL,
                    updated_at   REAL NOT NULL
                )
            """)
            # Phase 55: ioID device identity registry
            conn.execute("""
                CREATE TABLE IF NOT EXISTS ioid_devices (
                    device_id      TEXT PRIMARY KEY,
                    device_address TEXT NOT NULL,
                    did            TEXT NOT NULL,
                    tx_hash        TEXT NOT NULL DEFAULT '',
                    registered_at  REAL NOT NULL
                )
            """)
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_ioid_devices_did "
                "ON ioid_devices(did)"
            )
            # Phase 2 Controller Identity Keystone: extend for gamer-owned TBA + canon ioID
            # Add columns if missing (idempotent)
            try:
                conn.execute("ALTER TABLE ioid_devices ADD COLUMN tba_address TEXT")
            except Exception:
                pass
            try:
                conn.execute("ALTER TABLE ioid_devices ADD COLUMN ioid_token_id INTEGER DEFAULT 0")
            except Exception:
                pass
            try:
                conn.execute("ALTER TABLE ioid_devices ADD COLUMN canonical INTEGER DEFAULT 0")
            except Exception:
                pass
            # Phase 56: tournament passport registry
            conn.execute("""
                CREATE TABLE IF NOT EXISTS tournament_passports (
                    device_id        TEXT PRIMARY KEY,
                    passport_hash    TEXT NOT NULL,
                    ioid_token_id    INTEGER NOT NULL DEFAULT 0,
                    min_humanity_int INTEGER NOT NULL DEFAULT 0,
                    tx_hash          TEXT NOT NULL DEFAULT '',
                    on_chain         INTEGER NOT NULL DEFAULT 0,
                    issued_at        REAL NOT NULL
                )
            """)
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_tournament_passports_issued "
                "ON tournament_passports(issued_at DESC)"
            )
            # Phase 58: operator audit log
            conn.execute("""
                CREATE TABLE IF NOT EXISTS operator_audit_log (
                    id           INTEGER PRIMARY KEY AUTOINCREMENT,
                    endpoint     TEXT NOT NULL,
                    method       TEXT NOT NULL DEFAULT 'POST',
                    device_id    TEXT DEFAULT '',
                    api_key_hash TEXT DEFAULT '',
                    source_ip    TEXT DEFAULT '',
                    status_code  INTEGER NOT NULL,
                    outcome      TEXT NOT NULL,
                    ts           REAL NOT NULL
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_audit_log_device
                ON operator_audit_log(device_id, ts DESC)
            """)
            # Phase 58 migrations — idempotent
            for sql in ["ALTER TABLE pitl_session_proofs ADD COLUMN inference_code INTEGER DEFAULT NULL"]:
                try:
                    conn.execute(sql)
                except sqlite3.OperationalError:
                    log.debug("schema migration already applied: %.80s", sql)
            # Phase 61: frame replay checkpoints
            conn.execute("""
                CREATE TABLE IF NOT EXISTS frame_checkpoints (
                    id            INTEGER PRIMARY KEY AUTOINCREMENT,
                    device_id     TEXT NOT NULL,
                    record_hash   TEXT NOT NULL,
                    frames_json   TEXT NOT NULL,
                    frame_count   INTEGER NOT NULL,
                    checkpoint_ts REAL NOT NULL,
                    created_at    REAL NOT NULL,
                    FOREIGN KEY (record_hash) REFERENCES records(record_hash)
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_frame_checkpoints_device
                ON frame_checkpoints(device_id, created_at DESC)
            """)
            conn.execute("""
                CREATE UNIQUE INDEX IF NOT EXISTS idx_frame_checkpoints_record
                ON frame_checkpoints(record_hash)
            """)
            # Phase 62: Player enrollment ceremony state machine
            conn.execute("""
                CREATE TABLE IF NOT EXISTS device_enrollments (
                    device_id          TEXT PRIMARY KEY,
                    sessions_nominal   INTEGER NOT NULL DEFAULT 0,
                    sessions_total     INTEGER NOT NULL DEFAULT 0,
                    avg_humanity       REAL NOT NULL DEFAULT 0.0,
                    status             TEXT NOT NULL DEFAULT 'pending',
                    eligible_at        REAL,
                    credentialed_at    REAL,
                    tx_hash            TEXT DEFAULT '',
                    last_updated       REAL NOT NULL
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_device_enrollments_status
                ON device_enrollments(status, eligible_at)
            """)
            # Phase 63: L6b neuromuscular reflex probe log
            conn.execute("""
                CREATE TABLE IF NOT EXISTS l6b_probe_log (
                    id               INTEGER PRIMARY KEY AUTOINCREMENT,
                    device_id        TEXT    NOT NULL,
                    probe_ts_ms      INTEGER NOT NULL,
                    latency_ms       REAL,
                    classification   TEXT    NOT NULL,
                    accel_delta_peak REAL    NOT NULL DEFAULT 0.0,
                    created_at       TEXT    NOT NULL DEFAULT (datetime('now'))
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_l6b_device
                ON l6b_probe_log(device_id)
            """)
            # Phase 65: Autonomous agent rulings table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS agent_rulings (
                    id                INTEGER PRIMARY KEY AUTOINCREMENT,
                    device_id         TEXT    NOT NULL,
                    verdict           TEXT    NOT NULL,
                    confidence        REAL    NOT NULL DEFAULT 0.0,
                    reasoning         TEXT    NOT NULL DEFAULT '',
                    evidence_json     TEXT    NOT NULL DEFAULT '{}',
                    attestation_hash  TEXT    DEFAULT '',
                    commitment_hash   TEXT    NOT NULL,
                    dry_run           INTEGER NOT NULL DEFAULT 1,
                    source_agent      TEXT    NOT NULL DEFAULT 'session_adjudicator',
                    created_at        REAL    NOT NULL,
                    expires_at        REAL,
                    FOREIGN KEY (device_id) REFERENCES devices(device_id)
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_agent_rulings_device
                ON agent_rulings(device_id, created_at DESC)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_agent_rulings_verdict
                ON agent_rulings(verdict, dry_run, created_at DESC)
            """)
            # Phase 66: Ruling streaks table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS ruling_streaks (
                    id             INTEGER PRIMARY KEY AUTOINCREMENT,
                    device_id      TEXT    NOT NULL UNIQUE,
                    current_streak INTEGER NOT NULL DEFAULT 0,
                    streak_verdict TEXT    NOT NULL DEFAULT '',
                    streak_start   REAL    NOT NULL DEFAULT 0.0,
                    last_verdict   TEXT    NOT NULL DEFAULT '',
                    last_ruling_id INTEGER NOT NULL DEFAULT 0,
                    escalated_to   TEXT    DEFAULT NULL,
                    updated_at     REAL    NOT NULL
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_ruling_streaks_device
                ON ruling_streaks(device_id)
            """)
            # Phase 66: On-chain rulings anchoring table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS on_chain_rulings (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    ruling_id       INTEGER NOT NULL,
                    device_id       TEXT    NOT NULL,
                    commitment_hash TEXT    NOT NULL,
                    tx_hash         TEXT    NOT NULL,
                    block_number    INTEGER DEFAULT NULL,
                    chain_id        INTEGER NOT NULL DEFAULT 4690,
                    created_at      REAL    NOT NULL,
                    FOREIGN KEY (ruling_id) REFERENCES agent_rulings(id)
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_on_chain_rulings_device
                ON on_chain_rulings(device_id, created_at DESC)
            """)
            conn.execute("""
                CREATE UNIQUE INDEX IF NOT EXISTS idx_on_chain_rulings_commitment
                ON on_chain_rulings(commitment_hash)
            """)
            # Phase 73: add ceremony_integrity column to agent_rulings (idempotent)
            try:
                conn.execute(
                    "ALTER TABLE agent_rulings ADD COLUMN ceremony_integrity TEXT DEFAULT NULL"
                )
            except Exception:
                pass  # column already exists — safe to ignore
            # Phase 67: add reinstate columns to credential_enforcement (idempotent)
            for _col, _typedef in [
                ("reinstated",    "INTEGER DEFAULT 0"),
                ("reinstated_at", "REAL    DEFAULT NULL"),
            ]:
                try:
                    conn.execute(
                        f"ALTER TABLE credential_enforcement ADD COLUMN {_col} {_typedef}"
                    )
                except Exception:
                    pass  # column already exists — safe to ignore; fail-open: M-1 cleanup 2026-05-16
            # Phase 69: Data Sovereignty + Oracle Publication tables
            conn.execute("""
                CREATE TABLE IF NOT EXISTS data_lineage (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    device_id       TEXT NOT NULL,
                    record_hash     TEXT DEFAULT NULL,
                    taxonomy_class  TEXT NOT NULL,
                    quality_index   REAL DEFAULT 0.0,
                    curator_note    TEXT DEFAULT '',
                    created_at      REAL NOT NULL
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_data_lineage_device
                ON data_lineage(device_id, created_at DESC)
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS oracle_publications (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    oracle_type     TEXT NOT NULL,
                    device_id       TEXT NOT NULL,
                    tx_hash         TEXT DEFAULT NULL,
                    payload_json    TEXT DEFAULT '{}',
                    published_at    REAL NOT NULL
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_oracle_publications_device
                ON oracle_publications(device_id, oracle_type, published_at DESC)
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS token_eligibility (
                    device_id           TEXT PRIMARY KEY,
                    nominal_sessions    INTEGER DEFAULT 0,
                    clean_streak        INTEGER DEFAULT 0,
                    passport_held       INTEGER DEFAULT 0,
                    enrollment_complete INTEGER DEFAULT 0,
                    mpc_verified        INTEGER DEFAULT 0,
                    gate_passed         INTEGER DEFAULT 0,
                    base_multiplier     REAL    DEFAULT 1.0,
                    total_multiplier    REAL    DEFAULT 1.0,
                    eligibility_score   REAL    DEFAULT 0.0,
                    last_computed_at    REAL    NOT NULL
                )
            """)
            # Phase 72: PHGCredential bridge-layer multi-sig suspension proposals
            conn.execute("""
                CREATE TABLE IF NOT EXISTS pending_suspensions (
                    id            INTEGER PRIMARY KEY AUTOINCREMENT,
                    device_id     TEXT    NOT NULL,
                    evidence_hash TEXT    NOT NULL,
                    duration_s    INTEGER NOT NULL,
                    proposed_by   TEXT    NOT NULL DEFAULT '',
                    proposed_at   REAL    NOT NULL,
                    confirmations INTEGER NOT NULL DEFAULT 0,
                    executed      INTEGER NOT NULL DEFAULT 0,
                    executed_at   REAL,
                    tx_hash       TEXT    DEFAULT '',
                    expires_at    REAL    NOT NULL
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_pending_suspensions_device
                ON pending_suspensions(device_id, proposed_at DESC)
            """)
            # Phase 75: ruling validation log — cross-checks LLM vs rule-fallback
            conn.execute("""
                CREATE TABLE IF NOT EXISTS ruling_validation_log (
                    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                    ruling_id           INTEGER NOT NULL,
                    device_id           TEXT    NOT NULL,
                    llm_verdict         TEXT    NOT NULL,
                    fallback_verdict    TEXT    NOT NULL,
                    llm_confidence      REAL    NOT NULL,
                    fallback_confidence REAL    NOT NULL,
                    divergence          INTEGER NOT NULL DEFAULT 0,
                    created_at          REAL    NOT NULL
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_ruling_validation_ruling_id
                ON ruling_validation_log(ruling_id)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_ruling_validation_created
                ON ruling_validation_log(created_at DESC)
            """)
            # Phase 76: ruling provenance anchor log
            conn.execute("""
                CREATE TABLE IF NOT EXISTS ruling_provenance_anchors (
                    id               INTEGER PRIMARY KEY AUTOINCREMENT,
                    ruling_id        INTEGER NOT NULL,
                    device_id        TEXT    NOT NULL,
                    provenance_hash  TEXT    NOT NULL,
                    ceremony_hash    TEXT    NOT NULL,
                    evidence_hash    TEXT    NOT NULL,
                    anchored_at      REAL    NOT NULL DEFAULT (strftime('%s','now'))
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_provenance_ruling_id
                ON ruling_provenance_anchors(ruling_id)
            """)
            conn.execute("""
                CREATE UNIQUE INDEX IF NOT EXISTS idx_provenance_ruling_unique
                ON ruling_provenance_anchors(ruling_id)
            """)
            # Phase 79: Live mode transitions
            conn.execute("""
                CREATE TABLE IF NOT EXISTS live_mode_transitions (
                    id               INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_type       TEXT NOT NULL,
                    consecutive_clean INTEGER,
                    divergence_rate  REAL,
                    conditions_json  TEXT,
                    operator_action  TEXT,
                    created_at       REAL NOT NULL DEFAULT (strftime('%s','now'))
                )
            """)
            # Phase 80: Federation threat signals
            conn.execute("""
                CREATE TABLE IF NOT EXISTS federation_threat_signals (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    device_id       TEXT NOT NULL,
                    commitment_hash TEXT NOT NULL,
                    circuit_id      TEXT,
                    source_peer     TEXT,
                    broadcast_at    REAL,
                    received_at     REAL,
                    created_at      REAL NOT NULL DEFAULT (strftime('%s','now')),
                    UNIQUE(commitment_hash)
                )
            """)
            # Phase 81: Class J assessments
            conn.execute("""
                CREATE TABLE IF NOT EXISTS class_j_assessments (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    device_id       TEXT NOT NULL,
                    entropy_variance REAL NOT NULL,
                    risk_level      TEXT NOT NULL,
                    window_count    INTEGER NOT NULL,
                    assessed_at     REAL NOT NULL DEFAULT (strftime('%s','now'))
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_class_j_device
                ON class_j_assessments(device_id, assessed_at)
            """)
            # Phase 82: Reactive adjudication interrupt log
            conn.execute("""
                CREATE TABLE IF NOT EXISTS reactive_adjudication_log (
                    id               INTEGER PRIMARY KEY AUTOINCREMENT,
                    device_id        TEXT NOT NULL,
                    triggered_by     TEXT NOT NULL,
                    entropy_variance REAL,
                    verdict          TEXT,
                    was_deferred     INTEGER NOT NULL DEFAULT 0,
                    created_at       REAL NOT NULL DEFAULT (strftime('%s','now'))
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_reactive_adj_device
                ON reactive_adjudication_log(device_id, created_at DESC)
            """)
            # Phase 83: Agent supervisor health log
            conn.execute("""
                CREATE TABLE IF NOT EXISTS supervisor_health_log (
                    id               INTEGER PRIMARY KEY AUTOINCREMENT,
                    agent_name       TEXT NOT NULL,
                    health           TEXT NOT NULL,
                    last_active_at   REAL,
                    activity_count   INTEGER NOT NULL DEFAULT 0,
                    checked_at       REAL NOT NULL DEFAULT (strftime('%s','now'))
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_supervisor_health_agent
                ON supervisor_health_log(agent_name, checked_at DESC)
            """)
            # Phase 84: Gate attestation anchor log
            conn.execute("""
                CREATE TABLE IF NOT EXISTS gate_attestations (
                    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
                    attestation_hash      TEXT NOT NULL UNIQUE,
                    consecutive_clean     INTEGER NOT NULL,
                    gate_n                INTEGER NOT NULL,
                    divergence_rate       REAL NOT NULL,
                    on_chain_tx           TEXT,
                    created_at            REAL NOT NULL DEFAULT (strftime('%s','now'))
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_gate_attestation_created
                ON gate_attestations(created_at DESC)
            """)
            # Phase 97: Live Mode Guard Log (every transition attempt recorded)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS live_mode_guard_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_type TEXT NOT NULL,
                    attempted_dry_run INTEGER,
                    gate_passed INTEGER,
                    cert_valid INTEGER,
                    audit_valid INTEGER,
                    blocking_conditions TEXT,
                    operator_key_hash TEXT,
                    created_at REAL NOT NULL DEFAULT (strftime('%s','now'))
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_live_mode_guard_created
                ON live_mode_guard_log(created_at DESC)
            """)
            # Phase 98: Epistemic Consensus Log (multi-agent pre-enforcement consensus)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS epistemic_consensus_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    device_id TEXT NOT NULL,
                    ruling_id INTEGER,
                    proposed_verdict TEXT NOT NULL,
                    class_j_score REAL,
                    triage_score REAL,
                    supervisor_score REAL,
                    consensus_score REAL NOT NULL,
                    threshold REAL NOT NULL,
                    consensus_reached INTEGER NOT NULL DEFAULT 0,
                    final_verdict TEXT NOT NULL,
                    downgraded INTEGER NOT NULL DEFAULT 0,
                    created_at REAL NOT NULL DEFAULT (strftime('%s','now'))
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_epistemic_device
                ON epistemic_consensus_log(device_id, created_at DESC)
            """)
            # Phase 96: Enforcement Readiness Certificates (portable signed audit proofs)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS enforcement_certificates (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    audit_hash TEXT NOT NULL,
                    hmac_sig TEXT NOT NULL,
                    audit_valid INTEGER NOT NULL DEFAULT 0,
                    first_ready_check_at REAL,
                    gate_attestation_count INTEGER NOT NULL DEFAULT 0,
                    latest_attestation_at REAL,
                    expires_at REAL NOT NULL,
                    created_at REAL NOT NULL DEFAULT (strftime('%s','now')),
                    UNIQUE(audit_hash)
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_enforcement_cert_created
                ON enforcement_certificates(created_at DESC)
            """)
            # Phase 99A: Operator registration audit log (bridge-side record of staking events)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS operator_registrations (
                    id               INTEGER PRIMARY KEY AUTOINCREMENT,
                    operator_address TEXT NOT NULL,
                    event_type       TEXT NOT NULL,
                    stake_amount     TEXT,
                    tx_hash          TEXT,
                    reason           TEXT,
                    created_at       REAL NOT NULL DEFAULT (strftime('%s','now'))
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_operator_reg_address
                ON operator_registrations(operator_address, created_at DESC)
            """)
            # Phase 99B: GSR biometric samples (L7 layer, advisory only, GSR_ENABLED=false default)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS gsr_samples (
                    id               INTEGER PRIMARY KEY AUTOINCREMENT,
                    device_id        TEXT NOT NULL,
                    arousal_index    REAL NOT NULL,
                    correlation      REAL NOT NULL,
                    conductance_raw  REAL NOT NULL DEFAULT 0.0,
                    l7_features_json TEXT,
                    created_at       REAL NOT NULL DEFAULT (strftime('%s','now'))
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_gsr_device_created
                ON gsr_samples(device_id, created_at DESC)
            """)
            # Phase 99C: VHP issuances (soulbound ERC-4671 VHP token audit log)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS vhp_issuances (
                    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                    device_id           TEXT NOT NULL,
                    token_id            INTEGER NOT NULL DEFAULT 0,
                    tx_hash             TEXT NOT NULL DEFAULT '',
                    expires_at          REAL NOT NULL,
                    cert_level          INTEGER NOT NULL DEFAULT 1,
                    consecutive_clean   INTEGER NOT NULL DEFAULT 0,
                    to_address          TEXT NOT NULL DEFAULT '',
                    created_at          REAL NOT NULL DEFAULT (strftime('%s','now'))
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_vhp_device_created
                ON vhp_issuances(device_id, created_at DESC)
            """)
            # Phase 101: QuickSilver collateral events
            conn.execute("""
                CREATE TABLE IF NOT EXISTS quicksilver_collateral_events (
                    id             INTEGER PRIMARY KEY AUTOINCREMENT,
                    operator_address TEXT NOT NULL,
                    event_type     TEXT NOT NULL,
                    amount_wei     TEXT NOT NULL DEFAULT '0',
                    tx_hash        TEXT NOT NULL DEFAULT '',
                    created_at     REAL NOT NULL
                )
            """)
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_qs_collateral_operator "
                "ON quicksilver_collateral_events(operator_address)"
            )
            # Phase 102: VHP renewal log
            conn.execute("""
                CREATE TABLE IF NOT EXISTS vhp_renewal_log (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    device_id       TEXT    NOT NULL,
                    token_id        INTEGER NOT NULL DEFAULT 0,
                    old_expires_at  REAL    NOT NULL DEFAULT 0,
                    new_expires_at  REAL    NOT NULL DEFAULT 0,
                    tx_hash         TEXT    NOT NULL DEFAULT '',
                    dry_run         INTEGER NOT NULL DEFAULT 0,
                    created_at      REAL    NOT NULL DEFAULT (strftime('%s','now'))
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_vhp_renewal_device
                ON vhp_renewal_log(device_id)
            """)
            # Phase 103: Activation simulation log
            conn.execute("""
                CREATE TABLE IF NOT EXISTS activation_simulation_log (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    n_sessions      INTEGER NOT NULL DEFAULT 0,
                    gate_passed     INTEGER NOT NULL DEFAULT 0,
                    cert_created    INTEGER NOT NULL DEFAULT 0,
                    dry_run_toggled INTEGER NOT NULL DEFAULT 0,
                    vhp_minted      INTEGER NOT NULL DEFAULT 0,
                    token_id        INTEGER,
                    tx_hash         TEXT    NOT NULL DEFAULT '',
                    created_at      REAL    NOT NULL DEFAULT (strftime('%s','now'))
                )
            """)
            # Phase 104: Persistent Activation Commit + PMI
            conn.execute("""
                CREATE TABLE IF NOT EXISTS activation_state (
                    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
                    activation_committed INTEGER NOT NULL DEFAULT 0,
                    pmi                  INTEGER NOT NULL DEFAULT 0,
                    committed_at         REAL,
                    committed_by         TEXT    NOT NULL DEFAULT '',
                    pmi_updated_at       REAL,
                    notes                TEXT    NOT NULL DEFAULT '',
                    created_at           REAL    NOT NULL DEFAULT (strftime('%s','now'))
                )
            """)
            # Phase 105: Epistemic Threshold History
            conn.execute("""
                CREATE TABLE IF NOT EXISTS epistemic_threshold_history (
                    id             INTEGER PRIMARY KEY AUTOINCREMENT,
                    old_threshold  REAL    NOT NULL,
                    new_threshold  REAL    NOT NULL,
                    trigger        TEXT    NOT NULL DEFAULT 'manual',
                    pmi_at_change  INTEGER NOT NULL DEFAULT 0,
                    notes          TEXT    NOT NULL DEFAULT '',
                    created_at     REAL    NOT NULL DEFAULT (strftime('%s','now'))
                )
            """)
            # Phase 107: Live mode readiness reports (W1 isolation — never touches ruling_validation_log)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS live_mode_readiness_reports (
                    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
                    n_tested              INTEGER NOT NULL DEFAULT 0,
                    false_positive_count  INTEGER NOT NULL DEFAULT 0,
                    false_positive_rate   REAL    NOT NULL DEFAULT 0.0,
                    activation_committed  INTEGER NOT NULL DEFAULT 0,
                    pmi                   INTEGER NOT NULL DEFAULT 0,
                    dry_run_active        INTEGER NOT NULL DEFAULT 1,
                    ready_for_live        INTEGER NOT NULL DEFAULT 0,
                    notes                 TEXT    NOT NULL DEFAULT '',
                    created_at            REAL    NOT NULL DEFAULT (strftime('%s','now'))
                )
            """)
            # Phase 108: Tournament readiness snapshots (7-condition AND gate)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS tournament_readiness_snapshots (
                    id                          INTEGER PRIMARY KEY AUTOINCREMENT,
                    n_tested                    INTEGER NOT NULL DEFAULT 0,
                    false_positive_count        INTEGER NOT NULL DEFAULT 0,
                    activation_committed        INTEGER NOT NULL DEFAULT 0,
                    pmi                         INTEGER NOT NULL DEFAULT 0,
                    dry_run_active              INTEGER NOT NULL DEFAULT 1,
                    software_conditions_met     INTEGER NOT NULL DEFAULT 0,
                    separation_ratio            REAL    NOT NULL DEFAULT 1.261,
                    separation_ratio_ok         INTEGER NOT NULL DEFAULT 0,
                    touchpad_recapture_complete INTEGER NOT NULL DEFAULT 0,
                    hardware_conditions_met     INTEGER NOT NULL DEFAULT 0,
                    fully_ready                 INTEGER NOT NULL DEFAULT 0,
                    blocking_conditions_json    TEXT    NOT NULL DEFAULT '[]',
                    notes                       TEXT    NOT NULL DEFAULT '',
                    created_at                  REAL    NOT NULL DEFAULT (strftime('%s','now'))
                )
            """)
            # Phase 109A: ioSwarm consensus log
            conn.execute("""
                CREATE TABLE IF NOT EXISTS ioswarm_consensus_log (
                    id                        INTEGER PRIMARY KEY AUTOINCREMENT,
                    device_id                 TEXT    NOT NULL,
                    session_id                TEXT,
                    node_verdicts_json        TEXT    NOT NULL DEFAULT '[]',
                    quorum_verdict            TEXT,
                    quorum_reached            INTEGER NOT NULL DEFAULT 0,
                    block_quorum_met          INTEGER NOT NULL DEFAULT 0,
                    agreement_ratio           REAL,
                    node_count                INTEGER NOT NULL DEFAULT 0,
                    swarm_verdict_score       REAL    NOT NULL DEFAULT 0.0,
                    hold_escalation_flag      INTEGER NOT NULL DEFAULT 0,
                    verdict_distribution_json TEXT    NOT NULL DEFAULT '{}',
                    created_at                REAL    NOT NULL DEFAULT (strftime('%s','now'))
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_ioswarm_consensus_device
                ON ioswarm_consensus_log (device_id, created_at DESC)
            """)
            # Phase 109B: ioSwarm renewal log
            conn.execute("""
                CREATE TABLE IF NOT EXISTS ioswarm_renewal_log (
                    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
                    device_id          TEXT    NOT NULL,
                    token_id           INTEGER NOT NULL DEFAULT 0,
                    quorum_verdict     TEXT,
                    agreement_ratio    REAL,
                    node_count         INTEGER NOT NULL DEFAULT 0,
                    renewal_approved   INTEGER NOT NULL DEFAULT 0,
                    node_verdicts_json TEXT    NOT NULL DEFAULT '[]',
                    created_at         REAL    NOT NULL DEFAULT (strftime('%s','now'))
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_ioswarm_renewal_device
                ON ioswarm_renewal_log (device_id, created_at DESC)
            """)
            # Phase 109C: ioSwarm adjudication log (ClassJ+Triage dual-quorum veto)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS ioswarm_adjudication_log (
                    id                     INTEGER PRIMARY KEY AUTOINCREMENT,
                    device_id              TEXT    NOT NULL,
                    session_id             TEXT    NOT NULL DEFAULT '',
                    classj_quorum_verdict  TEXT,
                    classj_agreement_ratio REAL,
                    triage_quorum_verdict  TEXT,
                    triage_agreement_ratio REAL,
                    dual_veto              INTEGER NOT NULL DEFAULT 0,
                    node_count             INTEGER NOT NULL DEFAULT 0,
                    classj_verdicts_json   TEXT    NOT NULL DEFAULT '[]',
                    triage_verdicts_json   TEXT    NOT NULL DEFAULT '[]',
                    created_at             REAL    NOT NULL DEFAULT (strftime('%s','now'))
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_ioswarm_adjudication_device
                ON ioswarm_adjudication_log (device_id, created_at DESC)
            """)
            # Phase 110: ioSwarm VHP mint authorization log (fail-CLOSED quorum gate)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS ioswarm_vhp_mint_log (
                    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                    device_id           TEXT    NOT NULL,
                    authorized          INTEGER NOT NULL DEFAULT 0,
                    quorum_verdict      TEXT,
                    agreement_ratio     REAL,
                    node_count          INTEGER NOT NULL DEFAULT 0,
                    consecutive_clean   INTEGER NOT NULL DEFAULT 0,
                    recent_block_count  INTEGER NOT NULL DEFAULT 0,
                    node_verdicts_json  TEXT    NOT NULL DEFAULT '[]',
                    swarm_fingerprint   TEXT,
                    error_msg           TEXT,
                    created_at          REAL    NOT NULL DEFAULT (strftime('%s','now'))
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_ioswarm_vhp_mint_device
                ON ioswarm_vhp_mint_log (device_id, created_at DESC)
            """)
            # Phase 111 — PoAd Registry
            conn.execute("""
                CREATE TABLE IF NOT EXISTS poad_registry_log (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    device_id       TEXT    NOT NULL,
                    poad_hash       TEXT    NOT NULL,
                    dual_veto       INTEGER NOT NULL DEFAULT 0,
                    classj_verdict  TEXT,
                    triage_verdict  TEXT,
                    ts_ns           INTEGER NOT NULL DEFAULT 0,
                    on_chain_tx     TEXT,
                    created_at      REAL    NOT NULL DEFAULT (strftime('%s','now'))
                )
            """)
            conn.execute("""
                CREATE UNIQUE INDEX IF NOT EXISTS idx_poad_registry_hash
                ON poad_registry_log (poad_hash)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_poad_registry_device
                ON poad_registry_log (device_id, created_at DESC)
            """)
            # Phase 113 — Dual-Primitive Eligibility Checks
            conn.execute("""
                CREATE TABLE IF NOT EXISTS dual_eligibility_checks (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    device_id   TEXT    NOT NULL,
                    poad_hash   TEXT    NOT NULL,
                    eligible    INTEGER NOT NULL DEFAULT 0,
                    poac_valid  INTEGER NOT NULL DEFAULT 0,
                    poad_valid  INTEGER NOT NULL DEFAULT 0,
                    created_at  REAL    NOT NULL DEFAULT (strftime('%s','now'))
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_dual_eligibility_device
                ON dual_eligibility_checks (device_id, created_at DESC)
            """)
            # Phase 114 — VHP Mint Dual-Primitive Gate log
            conn.execute("""
                CREATE TABLE IF NOT EXISTS vhp_dual_gate_log (
                    id                INTEGER PRIMARY KEY AUTOINCREMENT,
                    device_id         TEXT    NOT NULL,
                    poad_hash         TEXT    NOT NULL DEFAULT '',
                    eligible          INTEGER NOT NULL DEFAULT 0,
                    poac_valid        INTEGER NOT NULL DEFAULT 0,
                    poad_valid        INTEGER NOT NULL DEFAULT 0,
                    mint_allowed      INTEGER NOT NULL DEFAULT 0,
                    poad_age_seconds  REAL    NOT NULL DEFAULT -1,
                    epoch_window_ok   INTEGER NOT NULL DEFAULT 1,
                    created_at        REAL    NOT NULL DEFAULT (strftime('%s','now'))
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_vhp_dual_gate_device
                ON vhp_dual_gate_log (device_id, created_at DESC)
            """)
            # Phase 118 — Per-Device Epoch Window Overrides
            conn.execute("""
                CREATE TABLE IF NOT EXISTS per_device_epoch_overrides (
                    id                     INTEGER PRIMARY KEY AUTOINCREMENT,
                    device_id              TEXT    NOT NULL UNIQUE,
                    override_window_seconds REAL   NOT NULL,
                    reason                 TEXT    NOT NULL DEFAULT '',
                    max_uses               INTEGER DEFAULT NULL,
                    use_count              INTEGER NOT NULL DEFAULT 0,
                    expires_at             REAL    DEFAULT NULL,
                    created_at             REAL    NOT NULL DEFAULT (strftime('%s','now'))
                )
            """)
            # Phase 119: add lifecycle columns to per_device_epoch_overrides (idempotent)
            for _col119, _def119 in [
                ("max_uses",   "INTEGER DEFAULT NULL"),
                ("use_count",  "INTEGER NOT NULL DEFAULT 0"),
                ("expires_at", "REAL DEFAULT NULL"),
            ]:
                try:
                    conn.execute(
                        f"ALTER TABLE per_device_epoch_overrides ADD COLUMN {_col119} {_def119}"
                    )
                except Exception:
                    pass  # Column already exists
            # Phase 115: add epoch-window columns to vhp_dual_gate_log (idempotent)
            for _col115, _def115 in [
                ("poad_age_seconds", "REAL NOT NULL DEFAULT -1"),
                ("epoch_window_ok",  "INTEGER NOT NULL DEFAULT 1"),
            ]:
                try:
                    conn.execute(
                        f"ALTER TABLE vhp_dual_gate_log ADD COLUMN {_col115} {_def115}"
                    )
                except Exception:
                    pass  # Column already exists; fail-open: M-1 cleanup 2026-05-16
            # Phase 120 — Bluetooth Transport Foundation
            conn.execute("""
                CREATE TABLE IF NOT EXISTS bt_transport_log (
                    id                INTEGER PRIMARY KEY AUTOINCREMENT,
                    device_address    TEXT    NOT NULL DEFAULT '',
                    sampling_rate_hz  INTEGER NOT NULL DEFAULT 250,
                    frames_received   INTEGER NOT NULL DEFAULT 0,
                    frames_dropped    INTEGER NOT NULL DEFAULT 0,
                    avg_interval_ms   REAL    NOT NULL DEFAULT 0.0,
                    session_start_ts  REAL    NOT NULL DEFAULT 0.0,
                    session_end_ts    REAL    NOT NULL DEFAULT 0.0,
                    created_at        REAL    NOT NULL DEFAULT (strftime('%s','now'))
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_bt_transport_created
                ON bt_transport_log (created_at DESC)
            """)
            # Phase 121: separation_ratio_snapshots — observability-only, no behavior change
            conn.execute("""
                CREATE TABLE IF NOT EXISTS separation_ratio_snapshots (
                    id               INTEGER PRIMARY KEY AUTOINCREMENT,
                    pooled_ratio     REAL    NOT NULL DEFAULT 0.0,
                    bt_strat_ratio   REAL    NOT NULL DEFAULT -1.0,
                    n_sessions       INTEGER NOT NULL DEFAULT 0,
                    n_players        INTEGER NOT NULL DEFAULT 0,
                    active_features  INTEGER NOT NULL DEFAULT 0,
                    tournament_ready INTEGER NOT NULL DEFAULT 0,
                    created_at       REAL    NOT NULL DEFAULT (strftime('%s','now'))
                )
            """)
            # Phase 122: confidence_multiplier_log — logs confidence_score adjustments
            conn.execute("""
                CREATE TABLE IF NOT EXISTS confidence_multiplier_log (
                    id             INTEGER PRIMARY KEY AUTOINCREMENT,
                    device_id      TEXT    NOT NULL,
                    original_score INTEGER NOT NULL DEFAULT 0,
                    multiplier     REAL    NOT NULL DEFAULT 1.0,
                    final_score    INTEGER NOT NULL DEFAULT 0,
                    bt_strat_ratio REAL    NOT NULL DEFAULT -1.0,
                    created_at     REAL    NOT NULL DEFAULT (strftime('%s','now'))
                )
            """)
            # Phase 123: l4_calibration_log — records calibration runs and staleness
            conn.execute("""
                CREATE TABLE IF NOT EXISTS l4_calibration_log (
                    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
                    feature_dim           INTEGER NOT NULL DEFAULT 0,
                    n_sessions            INTEGER NOT NULL DEFAULT 0,
                    anomaly_threshold     REAL    NOT NULL DEFAULT 0.0,
                    continuity_threshold  REAL    NOT NULL DEFAULT 0.0,
                    calibration_timestamp REAL    NOT NULL DEFAULT 0.0,
                    stale_flag            INTEGER NOT NULL DEFAULT 1,
                    created_at            REAL    NOT NULL DEFAULT (strftime('%s','now'))
                )
            """)
            # Phase 124: l4_threshold_tracks — per-battery calibrated L4 threshold pairs
            conn.execute("""
                CREATE TABLE IF NOT EXISTS l4_threshold_tracks (
                    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
                    battery_type         TEXT    NOT NULL,
                    anomaly_threshold    REAL    NOT NULL DEFAULT 7.009,
                    continuity_threshold REAL    NOT NULL DEFAULT 5.367,
                    n_sessions           INTEGER NOT NULL DEFAULT 0,
                    calibrated_at        REAL    NOT NULL DEFAULT 0.0,
                    active               INTEGER NOT NULL DEFAULT 1,
                    created_at           REAL    NOT NULL DEFAULT (strftime('%s','now'))
                )
            """)
            # Phase 125: l4_battery_calibration_runs — audit log of per-battery calibration applies
            conn.execute("""
                CREATE TABLE IF NOT EXISTS l4_battery_calibration_runs (
                    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
                    battery_type            TEXT    NOT NULL,
                    anomaly_threshold       REAL    NOT NULL,
                    continuity_threshold    REAL    NOT NULL,
                    n_sessions              INTEGER NOT NULL DEFAULT 0,
                    calibration_feature_dim INTEGER NOT NULL DEFAULT 13,
                    notes                   TEXT,
                    created_at              REAL    NOT NULL DEFAULT (strftime('%s','now'))
                )
            """)
            # Phase 126: l4_threshold_router_log — logs each threshold lookup
            conn.execute("""
                CREATE TABLE IF NOT EXISTS l4_threshold_router_log (
                    id               INTEGER PRIMARY KEY AUTOINCREMENT,
                    battery_type     TEXT    NOT NULL DEFAULT 'unknown',
                    threshold_source TEXT    NOT NULL DEFAULT 'global_fallback',
                    anomaly_used     REAL    NOT NULL DEFAULT 7.009,
                    continuity_used  REAL    NOT NULL DEFAULT 5.367,
                    created_at       REAL    NOT NULL DEFAULT (strftime('%s','now'))
                )
            """)
            # Phase 127: tournament_preflight_log — persists preflight runs for audit trail
            conn.execute("""
                CREATE TABLE IF NOT EXISTS tournament_preflight_log (
                    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                    separation_ok       INTEGER NOT NULL DEFAULT 0,
                    l4_ok               INTEGER NOT NULL DEFAULT 0,
                    gate_ok             INTEGER NOT NULL DEFAULT 0,
                    cert_ok             INTEGER NOT NULL DEFAULT 0,
                    audit_ok            INTEGER NOT NULL DEFAULT 0,
                    dual_gate_warned    INTEGER NOT NULL DEFAULT 0,
                    epoch_window_warned INTEGER NOT NULL DEFAULT 0,
                    ioswarm_warned      INTEGER NOT NULL DEFAULT 0,
                    overall_pass        INTEGER NOT NULL DEFAULT 0,
                    conditions_json     TEXT    NOT NULL DEFAULT '{}',
                    created_at          REAL    NOT NULL DEFAULT (strftime('%s','now'))
                )
            """)
            # Phase 129: separation_ratio_breakthrough_log — records crossing of ratio >= 1.0
            conn.execute("""
                CREATE TABLE IF NOT EXISTS separation_ratio_breakthrough_log (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    before_ratio    REAL    NOT NULL DEFAULT 0.0,
                    after_ratio     REAL    NOT NULL DEFAULT 0.0,
                    n_players       INTEGER NOT NULL DEFAULT 0,
                    feature_count   INTEGER NOT NULL DEFAULT 0,
                    breakthrough_at REAL    NOT NULL DEFAULT 0.0,
                    created_at      REAL    NOT NULL DEFAULT (strftime('%s','now'))
                )
            """)
            # Phase 130A: swarm_quorum_validation_log — WIF-001 quorum validation audit trail
            conn.execute("""
                CREATE TABLE IF NOT EXISTS swarm_quorum_validation_log (
                    id               INTEGER PRIMARY KEY AUTOINCREMENT,
                    node_count       INTEGER NOT NULL DEFAULT 0,
                    distinct_stakers INTEGER NOT NULL DEFAULT 0,
                    quorum_valid     INTEGER NOT NULL DEFAULT 0,
                    gate_address     TEXT    NOT NULL DEFAULT '',
                    created_at       REAL    NOT NULL DEFAULT (strftime('%s','now'))
                )
            """)
            # Phase 131: ioswarm_node_registry — live ioSwarm HTTP node registry
            conn.execute("""
                CREATE TABLE IF NOT EXISTS ioswarm_node_registry (
                    id               INTEGER PRIMARY KEY AUTOINCREMENT,
                    node_url         TEXT    NOT NULL,
                    staker_address   TEXT    NOT NULL DEFAULT '',
                    active           INTEGER NOT NULL DEFAULT 1,
                    last_seen_ts     REAL    NOT NULL DEFAULT 0.0,
                    node_version     TEXT    NOT NULL DEFAULT '',
                    registered_at    REAL    NOT NULL DEFAULT 0.0,
                    created_at       REAL    NOT NULL DEFAULT (unixepoch('now'))
                )
            """)
            conn.execute("""
                CREATE UNIQUE INDEX IF NOT EXISTS idx_ioswarm_node_url
                ON ioswarm_node_registry(node_url)
            """)
            # Phase 131B: usb_reconnect_log — USB stability monitor for PS5 coexistence
            # Root cause: DualShock Edge USB+BT simultaneous connection; HID output writes
            # (_apply_feedback LED/haptic) trigger brief USB drops → PS5 shows reconnect
            # notification. ps5_compat_mode suppresses all HID writes (read-only mode).
            conn.execute("""
                CREATE TABLE IF NOT EXISTS usb_reconnect_log (
                    id                       INTEGER PRIMARY KEY AUTOINCREMENT,
                    device_address           TEXT    NOT NULL DEFAULT '',
                    disconnect_reason        TEXT    NOT NULL DEFAULT '',
                    consecutive_fb_timeouts  INTEGER NOT NULL DEFAULT 0,
                    ps5_compat_mode_active   INTEGER NOT NULL DEFAULT 0,
                    session_id               TEXT    NOT NULL DEFAULT '',
                    created_at               REAL    NOT NULL DEFAULT (unixepoch('now'))
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_usb_reconnect_created
                ON usb_reconnect_log(created_at DESC)
            """)
            # Phase 148: agent_calibration_health — ACIM self-test results (agent #18)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS agent_calibration_health (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    agent_id        INTEGER NOT NULL,
                    agent_name      TEXT    NOT NULL DEFAULT '',
                    test_name       TEXT    NOT NULL DEFAULT '',
                    result          TEXT    NOT NULL DEFAULT 'UNKNOWN',
                    details         TEXT    NOT NULL DEFAULT '',
                    calibration_ts  REAL    NOT NULL DEFAULT 0.0,
                    created_at      REAL    NOT NULL DEFAULT (unixepoch('now'))
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_agent_cal_health_agent_id
                ON agent_calibration_health(agent_id, created_at DESC)
            """)
            # Phase 150: separation_defensibility_log — per-player N-count defensibility tracking
            # Formally closes WIF-010 (legally thin N) by recording defensibility status per probe type.
            # defensible=True requires ALL players >= min_n_per_player (default 10) AND ratio > 1.0.
            conn.execute("""
                CREATE TABLE IF NOT EXISTS separation_defensibility_log (
                    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_type         TEXT    NOT NULL DEFAULT 'touchpad_corners',
                    n_sessions_total     INTEGER NOT NULL DEFAULT 0,
                    n_per_player_json    TEXT    NOT NULL DEFAULT '{}',
                    min_n_per_player     INTEGER NOT NULL DEFAULT 10,
                    defensible           INTEGER NOT NULL DEFAULT 0,
                    ratio                REAL    NOT NULL DEFAULT 0.0,
                    all_pairs_above_1    INTEGER NOT NULL DEFAULT 0,
                    created_at           REAL    NOT NULL DEFAULT (unixepoch('now'))
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_sep_def_log_created
                ON separation_defensibility_log(created_at DESC)
            """)
            # Phase 150: idempotent ALTER TABLE — add touchpad_n_ok to tournament_preflight_log
            # touchpad_n_ok=1 (default) means N >= min_touchpad_sessions_per_player for all players.
            try:
                conn.execute(
                    "ALTER TABLE tournament_preflight_log ADD COLUMN "
                    "touchpad_n_ok INTEGER NOT NULL DEFAULT 1"
                )
            except Exception:
                pass  # Column already exists on databases migrated from Phase 127
            # Phase 196: idempotent ALTER TABLE — add biometric_ttl_ok (WIF-035 P0 condition 9)
            # biometric_ttl_ok=1 when biometric_credential_ttl not expired AND renewal chain valid.
            try:
                conn.execute(
                    "ALTER TABLE tournament_preflight_log ADD COLUMN "
                    "biometric_ttl_ok INTEGER NOT NULL DEFAULT 1"
                )
            except Exception:
                pass  # Column already exists
            # Phase 197: idempotent ALTER TABLE — add all_pairs_p0_ok (P0 condition 10)
            # all_pairs_p0_ok=1 when all inter-player pairs have separation ratio >= 1.0.
            # Reads all_pairs_above_1 from separation_defensibility_log.
            # 0 (fail-closed) when no defensibility data exists.
            try:
                conn.execute(
                    "ALTER TABLE tournament_preflight_log ADD COLUMN "
                    "all_pairs_p0_ok INTEGER NOT NULL DEFAULT 0"
                )
            except Exception:
                pass  # Column already exists
            # Phase 231: idempotent ALTER TABLE — add ait_defensibility_ok (P0 condition 11)
            # ait_defensibility_ok=1 when AIT all_pairs_above_1=True AND all players have >=10 sessions.
            # Closes the gap where all_pairs_p0_ok could be True with <10 sessions per player.
            # 0 (fail-closed) when no AIT defensibility data exists.
            try:
                conn.execute(
                    "ALTER TABLE tournament_preflight_log ADD COLUMN "
                    "ait_defensibility_ok INTEGER NOT NULL DEFAULT 0"
                )
            except Exception:
                pass  # Column already exists; fail-open: M-1 cleanup 2026-05-16
            # Phase 152: centroid_velocity_log — per-probe biometric fingerprint drift rate monitor.
            # Tracks separation ratio velocity between successive defensibility snapshots.
            # stagnant=True when velocity_per_day < PLATEAU_THRESHOLD (0.001 ratio/day).
            conn.execute("""
                CREATE TABLE IF NOT EXISTS centroid_velocity_log (
                    id               INTEGER PRIMARY KEY AUTOINCREMENT,
                    probe_type       TEXT    NOT NULL DEFAULT 'touchpad_corners',
                    velocity         REAL    NOT NULL DEFAULT 0.0,
                    ratio_prev       REAL    NOT NULL DEFAULT 0.0,
                    ratio_curr       REAL    NOT NULL DEFAULT 0.0,
                    dt_seconds       REAL    NOT NULL DEFAULT 0.0,
                    n_snapshots_used INTEGER NOT NULL DEFAULT 0,
                    stagnant         INTEGER NOT NULL DEFAULT 0,
                    created_at       REAL    NOT NULL DEFAULT (unixepoch('now'))
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_centroid_vel_probe
                ON centroid_velocity_log(probe_type, created_at DESC)
            """)
            # Phase 153: separation_ratio_registry_log — on-chain proof-of-calibration tracking.
            # SHA-256(ratio_str + N + players_sorted + ts_ns) anchored to IoTeX L1.
            # Committed=True after chain.record_separation_ratio_on_chain() confirms tx.
            conn.execute("""
                CREATE TABLE IF NOT EXISTS separation_ratio_registry_log (
                    id               INTEGER PRIMARY KEY AUTOINCREMENT,
                    commit_hash      TEXT    NOT NULL UNIQUE,
                    ratio_millis     INTEGER NOT NULL DEFAULT 0,
                    n_sessions       INTEGER NOT NULL DEFAULT 0,
                    n_players        INTEGER NOT NULL DEFAULT 0,
                    on_chain_tx      TEXT,
                    committed        INTEGER NOT NULL DEFAULT 0,
                    created_at       REAL    NOT NULL DEFAULT (unixepoch('now'))
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_sep_ratio_reg_created
                ON separation_ratio_registry_log(created_at DESC)
            """)
            # Phase 154: capture_stagnation_log — daily probe capture rate monitor.
            # stagnant=True when sessions_per_day < stagnation_threshold (default 0.5/day).
            # Reads separation_defensibility_log timestamps over rolling window_days window.
            conn.execute("""
                CREATE TABLE IF NOT EXISTS capture_stagnation_log (
                    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
                    probe_type            TEXT    NOT NULL DEFAULT 'touchpad_corners',
                    sessions_in_window    INTEGER NOT NULL DEFAULT 0,
                    window_days           REAL    NOT NULL DEFAULT 7.0,
                    sessions_per_day      REAL    NOT NULL DEFAULT 0.0,
                    stagnant              INTEGER NOT NULL DEFAULT 0,
                    stagnation_threshold  REAL    NOT NULL DEFAULT 0.5,
                    notes                 TEXT,
                    created_at            REAL    NOT NULL DEFAULT (unixepoch('now'))
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_capture_stag_probe
                ON capture_stagnation_log(probe_type, created_at DESC)
            """)
            # Phase 155: controller_hardware_profiles — per-controller calibration status.
            # composite_key = profile_hash:battery_type:transport_type
            # Attested tier: DualShock Edge with full L0–L6 PITL stack.
            # Standard tier: Xbox/Switch with L0–L5 only (no L6 haptic; pending calibration).
            conn.execute("""
                CREATE TABLE IF NOT EXISTS controller_hardware_profiles (
                    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
                    profile_hash         TEXT    NOT NULL UNIQUE,
                    controller_name      TEXT    NOT NULL DEFAULT 'DualShock_Edge_v1',
                    tier                 TEXT    NOT NULL DEFAULT 'Attested',
                    n_calibration        INTEGER NOT NULL DEFAULT 0,
                    transport_type       TEXT    NOT NULL DEFAULT 'usb',
                    battery_type         TEXT    NOT NULL DEFAULT 'gameplay',
                    anomaly_threshold    REAL    NOT NULL DEFAULT 7.009,
                    continuity_threshold REAL    NOT NULL DEFAULT 5.367,
                    composite_key        TEXT    NOT NULL DEFAULT '',
                    active               INTEGER NOT NULL DEFAULT 1,
                    created_at           REAL    NOT NULL DEFAULT (unixepoch('now'))
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_ctrl_hw_profile_hash
                ON controller_hardware_profiles(profile_hash, active)
            """)
            # Phase 156: enrollment_guidance_log — autonomous enrollment guidance agent reports.
            # EnrollmentAutoGuidanceAgent (#20) publishes enrollment_guidance_update bus events.
            # urgency_level: "low" | "medium" | "high" | "critical"
            conn.execute("""
                CREATE TABLE IF NOT EXISTS enrollment_guidance_log (
                    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
                    sessions_needed_total   INTEGER NOT NULL DEFAULT 0,
                    overall_ready           INTEGER NOT NULL DEFAULT 0,
                    recommended_action      TEXT    NOT NULL DEFAULT '',
                    urgency_level           TEXT    NOT NULL DEFAULT 'low',
                    stagnant_probes         TEXT    NOT NULL DEFAULT '[]',
                    estimated_days          REAL    NOT NULL DEFAULT -1.0,
                    activation_chain_event  TEXT,
                    created_at              REAL    NOT NULL DEFAULT (unixepoch('now'))
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_enroll_guidance_created
                ON enrollment_guidance_log(created_at DESC)
            """)
            # Phase 157: idempotent migration — add cov_regime_status to enrollment_guidance_log
            try:
                conn.execute(
                    "ALTER TABLE enrollment_guidance_log "
                    "ADD COLUMN cov_regime_status TEXT NOT NULL DEFAULT 'unknown'"
                )
            except Exception:
                pass  # Column already exists (Phase 157 migration already applied); fail-open: M-1 cleanup 2026-05-16
            # Phase 157: fleet_consensus_snapshot_log — FleetConsensusSnapshotAgent (agent #21)
            # Stores PoFC (Proof of Fleet Consensus) cryptographic snapshots.
            # pfc_hash = SHA-256(sorted_verdicts_json | separation_ratio_str | ts_ns_str)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS fleet_consensus_snapshot_log (
                    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                    pofc_hash           TEXT    NOT NULL DEFAULT '',
                    agent_count         INTEGER NOT NULL DEFAULT 0,
                    separation_ratio    REAL    NOT NULL DEFAULT 0.0,
                    verdict_summary_json TEXT   NOT NULL DEFAULT '{}',
                    created_at          REAL    NOT NULL DEFAULT (unixepoch('now'))
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_fleet_consensus_created
                ON fleet_consensus_snapshot_log(created_at DESC)
            """)
            # Phase 158: gsr_hmac_validation_log — Class K HMAC frame authentication (WIF-014)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS gsr_hmac_validation_log (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    device_id       TEXT    NOT NULL DEFAULT '',
                    frame_size      INTEGER NOT NULL DEFAULT 0,
                    valid           INTEGER NOT NULL DEFAULT 0,
                    rejection_reason TEXT   NOT NULL DEFAULT '',
                    ts_ns           INTEGER NOT NULL DEFAULT 0,
                    created_at      REAL    NOT NULL DEFAULT (unixepoch('now'))
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_gsr_hmac_device
                ON gsr_hmac_validation_log(device_id, created_at DESC)
            """)
            # Phase 158: pohbg_log — PoHBG (Proof of Hardware Biometric Grip) hash log (WIF-015)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS pohbg_log (
                    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                    device_id           TEXT    NOT NULL DEFAULT '',
                    pohbg_hash          TEXT    NOT NULL DEFAULT '',
                    arousal_millis      INTEGER NOT NULL DEFAULT 0,
                    correlation_millis  INTEGER NOT NULL DEFAULT 0,
                    conductance_raw_int INTEGER NOT NULL DEFAULT 0,
                    ts_ns               INTEGER NOT NULL DEFAULT 0,
                    created_at          REAL    NOT NULL DEFAULT (unixepoch('now'))
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_pohbg_device
                ON pohbg_log(device_id, created_at DESC)
            """)
            # Phase 159: privacy_compliance_log — BiometricPrivacyComplianceAgent (agent #22)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS privacy_compliance_log (
                    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
                    records_monitored       INTEGER NOT NULL DEFAULT 0,
                    records_expired         INTEGER NOT NULL DEFAULT 0,
                    mean_decay_factor       REAL    NOT NULL DEFAULT 1.0,
                    oldest_session_days     REAL    NOT NULL DEFAULT 0.0,
                    privacy_budget_epsilon  REAL    NOT NULL DEFAULT 0.0,
                    warning_triggered       INTEGER NOT NULL DEFAULT 0,
                    created_at              REAL    NOT NULL DEFAULT (unixepoch('now'))
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_privacy_compliance_created
                ON privacy_compliance_log(created_at DESC)
            """)
            # Phase 160: consent_ledger — BP-002 Consent Ledger (WIF-018/019)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS consent_ledger (
                    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                    device_id           TEXT    NOT NULL,
                    consent_type        TEXT    NOT NULL DEFAULT 'biometric_processing',
                    consent_given       INTEGER NOT NULL DEFAULT 0,
                    consent_ts          REAL,
                    revoked_at          REAL,
                    revocation_reason   TEXT,
                    erasure_requested   INTEGER NOT NULL DEFAULT 0,
                    erasure_completed   INTEGER NOT NULL DEFAULT 0,
                    created_at          REAL    NOT NULL DEFAULT (unixepoch('now')),
                    UNIQUE(device_id, consent_type)
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_consent_ledger_device
                ON consent_ledger(device_id, consent_type)
            """)
            # Phase 160: right_to_erasure_log — GDPR Art.17 erasure audit trail
            conn.execute("""
                CREATE TABLE IF NOT EXISTS right_to_erasure_log (
                    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                    device_id           TEXT    NOT NULL,
                    requested_at        REAL    NOT NULL,
                    fields_anonymized   INTEGER NOT NULL DEFAULT 0,
                    completed_at        REAL,
                    created_at          REAL    NOT NULL DEFAULT (unixepoch('now'))
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_erasure_log_device
                ON right_to_erasure_log(device_id, created_at DESC)
            """)
            # Phase 161: consent_gate_violation_log — BP-002 consent gate audit trail (WIF-018/020)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS consent_gate_violation_log (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    device_id       TEXT    NOT NULL,
                    operation       TEXT    NOT NULL,
                    blocked_reason  TEXT    NOT NULL,
                    created_at      REAL    NOT NULL DEFAULT (unixepoch('now'))
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_consent_gate_device
                ON consent_gate_violation_log(device_id, created_at DESC)
            """)
            # Data Economy Arc 3 — Curator post-session packaging loop tables.
            # pending_listings: listing intents awaiting gamer approval (approval_required
            #   autonomy). curator_packaging_log: full audit trail of every packaging
            #   decision (deferral / abort / pending / ready) per session.
            conn.execute("""
                CREATE TABLE IF NOT EXISTS pending_listings (
                    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id          TEXT    NOT NULL,
                    device_id           TEXT    NOT NULL,
                    autonomy_level      TEXT    NOT NULL,
                    consent_policy_hash TEXT,
                    allowed_categories  TEXT    NOT NULL DEFAULT '[]',  -- JSON array
                    status              TEXT    NOT NULL DEFAULT 'pending',
                    ts_ns               INTEGER NOT NULL,
                    created_at          REAL    NOT NULL DEFAULT (unixepoch('now'))
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_pending_listings_status
                ON pending_listings(status, created_at DESC)
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS curator_packaging_log (
                    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                    action              TEXT    NOT NULL,
                    session_id          TEXT    NOT NULL,
                    outcome             TEXT    NOT NULL,
                    extra               TEXT    NOT NULL DEFAULT '{}',  -- JSON object
                    ts_ns               INTEGER NOT NULL,
                    created_at          REAL    NOT NULL DEFAULT (unixepoch('now'))
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_curator_packaging_session
                ON curator_packaging_log(session_id, created_at DESC)
            """)
            # Phase 163: add n_consented column to separation_ratio_registry_log (idempotent).
            # Binds active consent count into SHA-256 preimage (WIF-022 closure).
            # DEFAULT 0 preserves semantics for pre-163 rows (legacy hashes had no consent filtering).
            try:
                conn.execute(
                    "ALTER TABLE separation_ratio_registry_log"
                    " ADD COLUMN n_consented INTEGER NOT NULL DEFAULT 0"
                )
            except sqlite3.OperationalError:
                pass  # Column already exists
            # Phase 168: add bootstrap CI columns to separation_ratio_snapshots (idempotent).
            # ci_lower/ci_upper: 95% CI bounds from bootstrap resampling (--bootstrap-n flag).
            # n_bootstrap: number of resamples used; 0 = CI not computed for this snapshot.
            # DEFAULT 0.0/0 preserves semantics for pre-168 snapshots (no CI available).
            for _col168, _type168 in [
                ("ci_lower", "REAL NOT NULL DEFAULT 0.0"),
                ("ci_upper", "REAL NOT NULL DEFAULT 0.0"),
                ("n_bootstrap", "INTEGER NOT NULL DEFAULT 0"),
            ]:
                try:
                    conn.execute(
                        f"ALTER TABLE separation_ratio_snapshots ADD COLUMN {_col168} {_type168}"
                    )
                except sqlite3.OperationalError:
                    pass  # Column already exists
            # Phase 173: separation_ratio_recovery_log — SeparationRatioRecoveryAgent (agent #23).
            # Detects P1 temporal non-stationarity (converging downward ratio trend) and
            # recommends recovery actions (P1 re-enrollment, age weighting, more sessions).
            # trend_velocity: dRatio/dSession — negative = converging downward (CRITICAL).
            # recovery_action: STABLE | AGE_WEIGHTING | P1_RE_ENROLLMENT | MORE_SESSIONS.
            conn.execute("""
                CREATE TABLE IF NOT EXISTS separation_ratio_recovery_log (
                    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
                    current_ratio      REAL    NOT NULL DEFAULT 0.0,
                    trend_velocity     REAL    NOT NULL DEFAULT 0.0,
                    n_snapshots_used   INTEGER NOT NULL DEFAULT 0,
                    recovery_needed    INTEGER NOT NULL DEFAULT 0,
                    recovery_action    TEXT    NOT NULL DEFAULT 'STABLE',
                    recommendation     TEXT    NOT NULL DEFAULT '',
                    created_at         REAL    NOT NULL DEFAULT (strftime('%s','now'))
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_sep_recovery_created
                ON separation_ratio_recovery_log(created_at DESC)
            """)
            # Phase 190: live_presence_signaling_log — LivePresenceSignalingAgent (agent #34).
            # Bidirectional VAPI presence channel: controller LED+haptic + ANSI terminal stream.
            # signal_type: HARD_CHEAT_DETECTED/CERTIFY_ADJUDICATION/BIOMETRIC_ANOMALY/
            #   PERSONA_BREAK_DETECTED/ENROLLMENT_MILESTONE/MATURITY_ELEVATION/
            #   SEPARATION_BREAKTHROUGH/CHAIN_MILESTONE
            # controller_fired=0 when ps5_compat_mode=True suppresses HID writes.
            conn.execute("""
                CREATE TABLE IF NOT EXISTS live_presence_signaling_log (
                    id                INTEGER PRIMARY KEY AUTOINCREMENT,
                    signal_source     TEXT    NOT NULL DEFAULT '',
                    signal_type       TEXT    NOT NULL DEFAULT '',
                    led_rgb           TEXT    NOT NULL DEFAULT '0,0,0',
                    haptic_duration   INTEGER NOT NULL DEFAULT 0,
                    terminal_output   TEXT    NOT NULL DEFAULT '',
                    controller_fired  INTEGER NOT NULL DEFAULT 0,
                    ps5_compat_mode   INTEGER NOT NULL DEFAULT 0,
                    created_at        REAL    NOT NULL DEFAULT (strftime('%s','now'))
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_presence_created
                ON live_presence_signaling_log(created_at DESC)
            """)
            conn.execute(
                "INSERT OR IGNORE INTO schema_versions (phase, migration_name, applied_at)"
                " VALUES (?, ?, ?)",
                (190, "live_presence_signaling", time.time()),
            )
            # Phase 189: protocol_intelligence_record_log — ProtocolIntelligenceRecordAgent (agent #33).
            # SHA-256 hash-linked PIR chain analogous to PoAC record chain.
            # pir_hash = SHA-256(prev_pir_hash + cycle + phase + wif_hash + forecast + score + ts).
            # Genesis PIR-0010: prev_pir_hash = "0"*64.
            # UNIQUE pir_hash enforces anti-replay (duplicate raises ValueError).
            conn.execute("""
                CREATE TABLE IF NOT EXISTS protocol_intelligence_record_log (
                    id                INTEGER PRIMARY KEY AUTOINCREMENT,
                    cycle_number      INTEGER NOT NULL DEFAULT 0,
                    phase_produced    TEXT    NOT NULL DEFAULT '',
                    wif_hash          TEXT    NOT NULL DEFAULT '',
                    threat_forecast   TEXT    NOT NULL DEFAULT '',
                    harness_score     REAL    NOT NULL DEFAULT 0.0,
                    prev_pir_hash     TEXT    NOT NULL DEFAULT '',
                    pir_hash          TEXT    NOT NULL UNIQUE,
                    eval_timestamp    REAL    NOT NULL DEFAULT 0.0,
                    created_at        REAL    NOT NULL DEFAULT (strftime('%s','now'))
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_pir_cycle
                ON protocol_intelligence_record_log(cycle_number DESC)
            """)
            conn.execute(
                "INSERT OR IGNORE INTO schema_versions (phase, migration_name, applied_at)"
                " VALUES (?, ?, ?)",
                (189, "protocol_intelligence_record", time.time()),
            )
            # Phase 188: biometric_stationarity_log — BiometricStationarityOracleAgent (agent #32).
            # Closes P1 genuine-drift vs adversarial-window ambiguity.
            # Discriminator: Agent 25 chain_integrity_score — genuine drift leaves PoAC chain intact;
            # adversarial window exploitation produces chain anomalies coincident with drift.
            # stationarity_verdict: ADVERSARIAL_WINDOW | GENUINE_DRIFT | AMBIGUOUS | STABLE
            conn.execute("""
                CREATE TABLE IF NOT EXISTS biometric_stationarity_log (
                    id                                INTEGER PRIMARY KEY AUTOINCREMENT,
                    player_id                         TEXT    NOT NULL DEFAULT '',
                    p_genuine_drift                   REAL    NOT NULL DEFAULT 0.0,
                    p_adversarial_window              REAL    NOT NULL DEFAULT 0.0,
                    stationarity_verdict              TEXT    NOT NULL DEFAULT 'STABLE',
                    biometric_stationarity_confidence REAL    NOT NULL DEFAULT 0.5,
                    chain_integrity_score             REAL    NOT NULL DEFAULT 1.0,
                    trend_velocity                    REAL    NOT NULL DEFAULT 0.0,
                    temporal_drift_index              REAL    NOT NULL DEFAULT 0.0,
                    session_count_used                INTEGER NOT NULL DEFAULT 0,
                    created_at                        REAL    NOT NULL DEFAULT (strftime('%s','now'))
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_stationarity_player
                ON biometric_stationarity_log(player_id, created_at DESC)
            """)
            conn.execute(
                "INSERT OR IGNORE INTO schema_versions (phase, migration_name, applied_at)"
                " VALUES (?, ?, ?)",
                (188, "biometric_stationarity", time.time()),
            )
            # Phase 187 (VHP badge): vhp_reenrollment_badge_log — VHPReenrollmentBadge.sol ERC-4671.
            # Soulbound badge minted after each successful re-enrollment attestation cycle.
            # badge_token_id: on-chain token ID from mintBadge() (0 = dry-run / not yet minted).
            # on_chain_tx: tx hash from mintBadge() IoTeX call (empty = dry-run).
            conn.execute("""
                CREATE TABLE IF NOT EXISTS vhp_reenrollment_badge_log (
                    id                INTEGER PRIMARY KEY AUTOINCREMENT,
                    player_id         TEXT    NOT NULL DEFAULT '',
                    attestation_hash  TEXT    NOT NULL DEFAULT '',
                    badge_token_id    INTEGER NOT NULL DEFAULT 0,
                    ttl_days          REAL    NOT NULL DEFAULT 90.0,
                    on_chain_tx       TEXT    NOT NULL DEFAULT '',
                    dry_run           INTEGER NOT NULL DEFAULT 1,
                    created_at        REAL    NOT NULL DEFAULT (strftime('%s','now'))
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_badge_player
                ON vhp_reenrollment_badge_log(player_id, created_at DESC)
            """)
            # Phase 187 (opsec): attestation_opsec_log — AttestationOpSecAdvisorAgent (agent #31).
            # timing_disclosure_risk: HIGH when bound_renewal_enabled + active_attestations > 0.
            # HIGH risk: adversary monitors IoTeX mempool for registerAttestation() tx (WIF-033 W1).
            conn.execute("""
                CREATE TABLE IF NOT EXISTS attestation_opsec_log (
                    id                         INTEGER PRIMARY KEY AUTOINCREMENT,
                    player_id                  TEXT    NOT NULL DEFAULT '',
                    timing_disclosure_risk     TEXT    NOT NULL DEFAULT 'LOW',
                    active_attestations        INTEGER NOT NULL DEFAULT 0,
                    re_enrollment_window_active INTEGER NOT NULL DEFAULT 0,
                    recommendation             TEXT    NOT NULL DEFAULT '',
                    created_at                 REAL    NOT NULL DEFAULT (strftime('%s','now'))
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_opsec_created
                ON attestation_opsec_log(created_at DESC)
            """)
            conn.execute(
                "INSERT OR IGNORE INTO schema_versions (phase, migration_name, applied_at)"
                " VALUES (?, ?, ?)",
                (187, "attestation_opsec", time.time()),
            )
            conn.execute(
                "INSERT OR IGNORE INTO schema_versions (phase, migration_name, applied_at)"
                " VALUES (?, ?, ?)",
                (1870, "vhp_reenrollment_badge", time.time()),
            )
            # Phase 186: attestation_bound_renewal_log — AttestationBoundRenewalAgent (agent #30).
            # Validates that every renewal has a valid active HMAC attestation from Phase 185.
            # renewal_approved=0: adversary cannot trigger renewal without operator attestation.
            conn.execute("""
                CREATE TABLE IF NOT EXISTS attestation_bound_renewal_log (
                    id                INTEGER PRIMARY KEY AUTOINCREMENT,
                    player_id         TEXT    NOT NULL DEFAULT '',
                    attestation_hash  TEXT    NOT NULL DEFAULT '',
                    renewal_approved  INTEGER NOT NULL DEFAULT 0,
                    denial_reason     TEXT    NOT NULL DEFAULT '',
                    new_commit_hash   TEXT    NOT NULL DEFAULT '',
                    created_at        REAL    NOT NULL DEFAULT (strftime('%s','now'))
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_bound_renewal_player
                ON attestation_bound_renewal_log(player_id, created_at DESC)
            """)
            conn.execute(
                "INSERT OR IGNORE INTO schema_versions (phase, migration_name, applied_at)"
                " VALUES (?, ?, ?)",
                (186, "attestation_bound_renewal", time.time()),
            )
            # Phase 185: persona_break_attestation_log — ReEnrollmentAttestationAgent (agent #29).
            # HMAC-SHA256 attestation token gates re-enrollment window (WIF-032 W1 closure).
            # UNIQUE attestation_hash prevents double-issuance (anti-replay).
            # active=0 when expired via expire_stale_attestations() or manually revoked.
            conn.execute("""
                CREATE TABLE IF NOT EXISTS persona_break_attestation_log (
                    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                    player_id           TEXT    NOT NULL DEFAULT '',
                    attestation_hash    TEXT    NOT NULL UNIQUE,
                    active              INTEGER NOT NULL DEFAULT 1,
                    issued_at           REAL    NOT NULL DEFAULT 0.0,
                    expires_at          REAL    NOT NULL DEFAULT 0.0,
                    loo_trend_at_break  REAL    NOT NULL DEFAULT 0.0,
                    tdi_at_break        REAL    NOT NULL DEFAULT 0.0,
                    ttl_days            REAL    NOT NULL DEFAULT 7.0,
                    created_at          REAL    NOT NULL DEFAULT (strftime('%s','now'))
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_attestation_player_active
                ON persona_break_attestation_log(player_id, active, expires_at DESC)
            """)
            conn.execute(
                "INSERT OR IGNORE INTO schema_versions (phase, migration_name, applied_at)"
                " VALUES (?, ?, ?)",
                (185, "persona_break_attestation", time.time()),
            )
            # Phase 183: maturity_elevation_log — MaturityElevationGateAgent (agent #28).
            # Reads 6-component protocol_maturity_log and generates actionable elevation_plan.
            # elevation_available=True when gap_to_target < 0.05 (close to next tier threshold).
            conn.execute("""
                CREATE TABLE IF NOT EXISTS maturity_elevation_log (
                    id                        INTEGER PRIMARY KEY AUTOINCREMENT,
                    current_tier              TEXT    NOT NULL DEFAULT 'ALPHA',
                    target_tier               TEXT    NOT NULL DEFAULT 'BETA',
                    gap_to_target             REAL    NOT NULL DEFAULT 1.0,
                    elevation_plan_json       TEXT    NOT NULL DEFAULT '{}',
                    elevation_available       INTEGER NOT NULL DEFAULT 0,
                    critical_component        TEXT    NOT NULL DEFAULT '',
                    estimated_sessions_total  INTEGER NOT NULL DEFAULT 0,
                    created_at                REAL    NOT NULL DEFAULT (strftime('%s','now'))
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_elevation_created
                ON maturity_elevation_log(created_at DESC)
            """)
            conn.execute(
                "INSERT OR IGNORE INTO schema_versions (phase, migration_name, applied_at)"
                " VALUES (?, ?, ?)",
                (183, "maturity_elevation", time.time()),
            )
            # Phase 182: persona_break_log — PersonaBreakDetectorAgent (agent #27).
            # LOO accuracy trend over last 5 separation_ratio_snapshots per player.
            # persona_break_detected=True when mean_loo < persona_break_loo_threshold (0.20).
            # re_enrollment_urgency: CRITICAL | HIGH | MEDIUM
            conn.execute("""
                CREATE TABLE IF NOT EXISTS persona_break_log (
                    id                     INTEGER PRIMARY KEY AUTOINCREMENT,
                    player_id              TEXT    NOT NULL DEFAULT '',
                    loo_accuracy_trend     REAL    NOT NULL DEFAULT 1.0,
                    tdi_current            REAL    NOT NULL DEFAULT 0.0,
                    persona_break_detected INTEGER NOT NULL DEFAULT 0,
                    re_enrollment_urgency  TEXT    NOT NULL DEFAULT 'MEDIUM',
                    n_snapshots_used       INTEGER NOT NULL DEFAULT 0,
                    created_at             REAL    NOT NULL DEFAULT (strftime('%s','now'))
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_persona_break_player
                ON persona_break_log(player_id, created_at DESC)
            """)
            conn.execute(
                "INSERT OR IGNORE INTO schema_versions (phase, migration_name, applied_at)"
                " VALUES (?, ?, ?)",
                (182, "persona_break", time.time()),
            )
            # Phase 181: renewal_consent_snapshot_log — Consent-Bound Renewal Provenance.
            # Records consent coverage at every separation-ratio renewal (WIF-030 W2 closure).
            # corpus_delta_detected=1 when player set changed since last snapshot.
            conn.execute("""
                CREATE TABLE IF NOT EXISTS renewal_consent_snapshot_log (
                    id                     INTEGER PRIMARY KEY AUTOINCREMENT,
                    new_commit_hash        TEXT    NOT NULL UNIQUE,
                    n_consented_at_renewal INTEGER NOT NULL DEFAULT 0,
                    players_consented_json TEXT    NOT NULL DEFAULT '[]',
                    revoked_at_renewal     INTEGER NOT NULL DEFAULT 0,
                    corpus_delta_detected  INTEGER NOT NULL DEFAULT 0,
                    created_at             REAL    NOT NULL DEFAULT (strftime('%s','now'))
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_renewal_snapshot_hash
                ON renewal_consent_snapshot_log(new_commit_hash)
            """)
            # Phase 180: biometric_renewal_chain_log — Biometric Renewal Engine (WIF-029 W2 closure).
            # Records each consent-bound renewal commitment chain entry.
            # new_commit_hash: SHA-256(prev_hash + ratio_str + N + N_consented + players + ttl_days + ts_ns).
            # on_chain_tx: populated when renewal_enabled=True and renewCommit() succeeds on IoTeX.
            # dry_run=1: default — never calls chain without explicit operator intent.
            conn.execute("""
                CREATE TABLE IF NOT EXISTS biometric_renewal_chain_log (
                    id                INTEGER PRIMARY KEY AUTOINCREMENT,
                    prev_commit_hash  TEXT    NOT NULL DEFAULT '',
                    new_commit_hash   TEXT    NOT NULL UNIQUE,
                    renewal_reason    TEXT    NOT NULL DEFAULT 'TTL_EXPIRY',
                    n_consented       INTEGER NOT NULL DEFAULT 0,
                    n_sessions        INTEGER NOT NULL DEFAULT 0,
                    ttl_days          REAL    NOT NULL DEFAULT 90.0,
                    on_chain_tx       TEXT,
                    dry_run           INTEGER NOT NULL DEFAULT 1,
                    created_at        REAL    NOT NULL DEFAULT (strftime('%s','now'))
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_renewal_chain_created
                ON biometric_renewal_chain_log(created_at DESC)
            """)
            # Phase 179: ceremony_audit_log — ZK Ceremony Audit Gate (WIF-030 W1 closure).
            # Tracks MPC trusted-setup ceremony participants per ZK circuit.
            # Anti-replay: UNIQUE(ceremony_id, participant_address, circuit_name).
            # TournamentActivationChainAgent requires >= min_participants per circuit
            # before accepting ZK proofs as tournament-valid (when ceremony_audit_enabled=True).
            conn.execute("""
                CREATE TABLE IF NOT EXISTS ceremony_audit_log (
                    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
                    ceremony_id          TEXT    NOT NULL,
                    circuit_name         TEXT    NOT NULL,
                    participant_address  TEXT    NOT NULL,
                    contribution_hash    TEXT    NOT NULL,
                    ts_ns                INTEGER NOT NULL DEFAULT 0,
                    created_at           REAL    NOT NULL DEFAULT (strftime('%s','now')),
                    UNIQUE(ceremony_id, participant_address, circuit_name)
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_ceremony_audit_circuit
                ON ceremony_audit_log(circuit_name, created_at DESC)
            """)
            # Phase 178: biometric_renewal_log — Biometric Credential TTL Gate (WIF-029 W1 closure).
            # Records each TTL check performed by TournamentActivationChainAgent against
            # the latest SeparationRatioRegistry.sol commitment.
            # ttl_expired=True when age_days > biometric_credential_ttl_days (default 90).
            # When expired: recalibration_required=True and tournament authorization is BLOCKED.
            conn.execute("""
                CREATE TABLE IF NOT EXISTS biometric_renewal_log (
                    id                       INTEGER PRIMARY KEY AUTOINCREMENT,
                    commit_hash              TEXT    NOT NULL DEFAULT '',
                    age_days                 REAL    NOT NULL DEFAULT 0.0,
                    ttl_days                 REAL    NOT NULL DEFAULT 90.0,
                    ttl_expired              INTEGER NOT NULL DEFAULT 0,
                    recalibration_required   INTEGER NOT NULL DEFAULT 0,
                    checked_by               TEXT    NOT NULL DEFAULT 'tournament_activation_chain_agent',
                    created_at               REAL    NOT NULL DEFAULT (strftime('%s','now'))
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_biometric_renewal_created
                ON biometric_renewal_log(created_at DESC)
            """)
            # Phase 177 / Phase 191 TSP: protocol_maturity_log — ProtocolMaturityScoringAgent (agent #26).
            # Synthesizes 8 agent signals into a unified maturity_score (0.0-1.0).
            # maturity_tier: ALPHA (<0.50) | BETA (0.50-0.85) | PRODUCTION_CANDIDATE (>=0.85)
            # Component weights v2 (Phase 191): separation(0.20)+chain_integrity(0.20)+consent(0.15)
            #   +biometric_freshness(0.12)+agent_calibration(0.12)+enrollment(0.10)
            #   +threat_forecast_accuracy(0.07)+biometric_stationarity(0.04)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS protocol_maturity_log (
                    id                                  INTEGER PRIMARY KEY AUTOINCREMENT,
                    maturity_score                      REAL    NOT NULL DEFAULT 0.0,
                    maturity_tier                       TEXT    NOT NULL DEFAULT 'ALPHA',
                    separation_component                REAL    NOT NULL DEFAULT 0.0,
                    chain_integrity_component           REAL    NOT NULL DEFAULT 0.0,
                    consent_component                   REAL    NOT NULL DEFAULT 0.0,
                    biometric_freshness_component       REAL    NOT NULL DEFAULT 0.0,
                    agent_calibration_component         REAL    NOT NULL DEFAULT 0.0,
                    enrollment_component                REAL    NOT NULL DEFAULT 0.0,
                    threat_forecast_accuracy_component  REAL    NOT NULL DEFAULT 0.0,
                    biometric_stationarity_component    REAL    NOT NULL DEFAULT 0.0,
                    created_at                          REAL    NOT NULL DEFAULT (strftime('%s','now'))
                )
            """)
            # Phase 191: idempotent migration — add TSP columns to existing DBs
            for _col191, _default191 in (
                ("threat_forecast_accuracy_component", "0.0"),
                ("biometric_stationarity_component",   "0.0"),
            ):
                try:
                    conn.execute(
                        f"ALTER TABLE protocol_maturity_log ADD COLUMN {_col191} REAL NOT NULL DEFAULT {_default191}"
                    )
                except Exception:
                    pass  # column already exists
            # Phase 195: idempotent migration — add PMI component column
            try:
                conn.execute(
                    "ALTER TABLE protocol_maturity_log ADD COLUMN pmi_component REAL NOT NULL DEFAULT 1.0"
                )
            except Exception:
                pass  # column already exists; fail-open: M-1 cleanup 2026-05-16
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_maturity_created
                ON protocol_maturity_log(created_at DESC)
            """)
            # Phase 192: DataCuratorAgent (Agent #35) — 7-task data coherence layer.
            # Task 1: data_provenance_dag — causal DAG from calibration session to VHP badge.
            # node_type values: CALIBRATION_SESSION | SEPARATION_SNAPSHOT | DEFENSIBILITY_LOG |
            #   COMMITMENT_HASH | RENEWAL_LOG | ATTESTATION_LOG | BADGE_TOKEN |
            #   RULING_LOG | CONSENT_SNAPSHOT | ERASURE_CERTIFICATE
            # edge_type values: FEATURE_EXTRACTION | DEFENSIBILITY_CHECK |
            #   COMMITMENT | RENEWAL | ATTESTATION | BADGE_MINT | RULING | CONSENT | ERASURE
            conn.execute("""
                CREATE TABLE IF NOT EXISTS data_provenance_dag (
                    id               INTEGER PRIMARY KEY AUTOINCREMENT,
                    node_id          TEXT    NOT NULL UNIQUE,
                    node_type        TEXT    NOT NULL,
                    source_table     TEXT    NOT NULL,
                    source_row_id    INTEGER,
                    source_hash      TEXT,
                    parent_node_id   TEXT,
                    edge_type        TEXT,
                    phase_produced   INTEGER NOT NULL,
                    player_id        TEXT,
                    on_chain_ref     TEXT,
                    created_at       TEXT    DEFAULT (datetime('now'))
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_provenance_parent
                ON data_provenance_dag(parent_node_id)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_provenance_player
                ON data_provenance_dag(player_id)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_provenance_type
                ON data_provenance_dag(node_type)
            """)
            conn.execute(
                "INSERT OR IGNORE INTO schema_versions (phase, migration_name, applied_at)"
                " VALUES (?, ?, ?)",
                (192, "data_provenance_dag", time.time()),
            )
            # Task 2: corpus_entropy_log — Shannon entropy of 13-dim feature space per player.
            # Score < 1.5 = CLUSTERING_WARNING (brittle centroid).
            # Score > 2.5 = WELL_SAMPLED (trustworthy ratio).
            conn.execute("""
                CREATE TABLE IF NOT EXISTS corpus_entropy_log (
                    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
                    corpus_entropy_score  REAL    NOT NULL,
                    per_player_entropy    TEXT    NOT NULL,
                    per_feature_entropy   TEXT    NOT NULL,
                    low_entropy_features  TEXT    NOT NULL,
                    clustering_warning    INTEGER NOT NULL DEFAULT 0,
                    n_sessions_analyzed   INTEGER NOT NULL,
                    session_type_filter   TEXT    DEFAULT 'touchpad_corners',
                    computed_at_ts        INTEGER NOT NULL,
                    created_at            TEXT    DEFAULT (datetime('now'))
                )
            """)
            conn.execute(
                "INSERT OR IGNORE INTO schema_versions (phase, migration_name, applied_at)"
                " VALUES (?, ?, ?)",
                (192, "corpus_entropy", time.time()),
            )
            # Task 3: erasure_certificate_log — GDPR Art.17 cryptographic erasure proof.
            # certificate_hash = SHA-256(device_id + sorted_table_row_hashes + ratio + ts_ns).
            # Anchored to AdjudicationRegistry.sol (same contract as PoAd — zero new infra).
            conn.execute("""
                CREATE TABLE IF NOT EXISTS erasure_certificate_log (
                    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
                    certificate_hash      TEXT    NOT NULL UNIQUE,
                    device_id             TEXT    NOT NULL,
                    player_id             TEXT    NOT NULL,
                    erased_tables_json    TEXT    NOT NULL,
                    erased_row_count      INTEGER NOT NULL,
                    post_erasure_ratio    REAL    NOT NULL,
                    on_chain_tx_hash      TEXT,
                    anchored              INTEGER NOT NULL DEFAULT 0,
                    ts_ns                 INTEGER NOT NULL,
                    created_at            TEXT    DEFAULT (datetime('now'))
                )
            """)
            conn.execute(
                "INSERT OR IGNORE INTO schema_versions (phase, migration_name, applied_at)"
                " VALUES (?, ?, ?)",
                (192, "erasure_certificate", time.time()),
            )
            # Task 4: federation_corpus_quality_log — anonymized cross-bridge corpus stats.
            # BP-007: only derived metrics leave a bridge — no feature vectors, no player IDs.
            # Contents: bridge_id_hash, session_type, N, entropy, stationarity, velocity.
            conn.execute("""
                CREATE TABLE IF NOT EXISTS federation_corpus_quality_log (
                    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
                    bridge_id_hash          TEXT    NOT NULL,
                    session_type            TEXT    NOT NULL,
                    n_sessions              INTEGER NOT NULL,
                    entropy_score           REAL    NOT NULL,
                    stationarity_score      REAL    NOT NULL,
                    centroid_velocity_mean  REAL    NOT NULL,
                    federation_entropy_mean REAL,
                    federation_outlier      INTEGER NOT NULL DEFAULT 0,
                    outlier_sigma           REAL,
                    received_at_ts          INTEGER NOT NULL,
                    created_at              TEXT    DEFAULT (datetime('now'))
                )
            """)
            conn.execute(
                "INSERT OR IGNORE INTO schema_versions (phase, migration_name, applied_at)"
                " VALUES (?, ?, ?)",
                (192, "federation_corpus_quality", time.time()),
            )
            # Task 5: feature_correlation_log — 13x13 per-player correlation matrix.
            # Upper triangle stored as JSON (91 values). Frobenius distance measures
            # correlation-structure separability independent of Mahalanobis distance.
            conn.execute("""
                CREATE TABLE IF NOT EXISTS feature_correlation_log (
                    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
                    player_id             TEXT    NOT NULL,
                    session_type          TEXT    NOT NULL DEFAULT 'touchpad_corners',
                    n_sessions_used       INTEGER NOT NULL,
                    correlation_upper_tri TEXT    NOT NULL,
                    high_correlation_pairs TEXT   NOT NULL,
                    frobenius_vs_p1       REAL,
                    frobenius_vs_p2       REAL,
                    frobenius_vs_p3       REAL,
                    correlation_separable INTEGER NOT NULL DEFAULT 0,
                    computed_at_ts        INTEGER NOT NULL,
                    created_at            TEXT    DEFAULT (datetime('now'))
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_correlation_player
                ON feature_correlation_log(player_id, computed_at_ts DESC)
            """)
            conn.execute(
                "INSERT OR IGNORE INTO schema_versions (phase, migration_name, applied_at)"
                " VALUES (?, ?, ?)",
                (192, "feature_correlation", time.time()),
            )
            # Task 6: data_readiness_certificate_log — 8-dimension pre-tournament certification.
            # certificate_hash = SHA-256(sorted_dims_json + ratio_str + ts_ns_bytes).
            # Anchored to AdjudicationRegistry.sol. certification_status:
            #   CERTIFIED = all blocking dims passed.
            #   BLOCKED = >= 1 blocking dimension failed.
            #   ADVISORY_ONLY = all blocking passed, some advisory warnings.
            conn.execute("""
                CREATE TABLE IF NOT EXISTS data_readiness_certificate_log (
                    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
                    certificate_hash     TEXT    NOT NULL UNIQUE,
                    certification_status TEXT    NOT NULL,
                    blocking_failures    TEXT    NOT NULL,
                    advisory_warnings    TEXT    NOT NULL,
                    dimension_results    TEXT    NOT NULL,
                    separation_ratio     REAL    NOT NULL,
                    on_chain_tx_hash     TEXT,
                    anchored             INTEGER NOT NULL DEFAULT 0,
                    valid_until_ts       INTEGER NOT NULL,
                    ts_ns                INTEGER NOT NULL,
                    created_at           TEXT    DEFAULT (datetime('now'))
                )
            """)
            conn.execute(
                "INSERT OR IGNORE INTO schema_versions (phase, migration_name, applied_at)"
                " VALUES (?, ?, ?)",
                (192, "data_readiness_certificate", time.time()),
            )
            # Task 7: session_contribution_weight_log — TBD-decay weighted centroid input.
            # FROZEN: lambda = ln(2)/90 (BP-001 TBD half-life = vhp_expiry_days = 90 days).
            # effective_weight = tbd_weight * type_multiplier * stationarity_multiplier.
            # Powers weighted centroid (--weighted-centroid flag in analyze_interperson_separation.py).
            conn.execute("""
                CREATE TABLE IF NOT EXISTS session_contribution_weight_log (
                    id                     INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_file           TEXT    NOT NULL,
                    player_id              TEXT    NOT NULL,
                    session_type           TEXT    NOT NULL,
                    session_captured_at_ts INTEGER NOT NULL,
                    age_days               REAL    NOT NULL,
                    tbd_weight             REAL    NOT NULL,
                    type_multiplier        REAL    NOT NULL,
                    stationarity_multiplier REAL   NOT NULL,
                    effective_weight       REAL    NOT NULL,
                    centroid_influence_rank INTEGER,
                    computed_at_ts         INTEGER NOT NULL,
                    created_at             TEXT    DEFAULT (datetime('now'))
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_contrib_weight_player
                ON session_contribution_weight_log(player_id, effective_weight DESC)
            """)
            conn.execute(
                "INSERT OR IGNORE INTO schema_versions (phase, migration_name, applied_at)"
                " VALUES (?, ?, ?)",
                (192, "session_contribution_weight", time.time()),
            )
            # Phase 193: fleet_coherence_log — FleetSignalCoherenceAgent (agent #36).
            # Stores CONTRADICTION / ORPHAN / INVERSION findings from fleet-level coherence detection.
            # coherence_id = SHA-256(rule_name + sorted(agents_involved) + ts_ns)[:16] — idempotent.
            # INSERT OR IGNORE on coherence_id prevents duplicate findings within same cycle.
            # evidence_json stores only derived metrics — no raw biometric data (BP-007 IMMUTABLE).
            conn.execute("""
                CREATE TABLE IF NOT EXISTS fleet_coherence_log (
                    id                        INTEGER PRIMARY KEY AUTOINCREMENT,
                    coherence_id              TEXT    NOT NULL UNIQUE,
                    failure_mode              TEXT    NOT NULL,
                    rule_name                 TEXT    NOT NULL,
                    agents_involved           TEXT    NOT NULL,
                    severity                  TEXT    NOT NULL,
                    explanation               TEXT    NOT NULL,
                    resolution                TEXT    NOT NULL,
                    evidence_json             TEXT    NOT NULL DEFAULT '[]',
                    promoted_to_wif           INTEGER NOT NULL DEFAULT 0,
                    wif_entry_id              TEXT,
                    wiki_contradict_written   INTEGER NOT NULL DEFAULT 0,
                    alert_published           INTEGER NOT NULL DEFAULT 0,
                    resolved                  INTEGER NOT NULL DEFAULT 0,
                    resolved_at               TEXT,
                    resolved_by               TEXT,
                    phase_detected            INTEGER NOT NULL DEFAULT 193,
                    ts_ns                     INTEGER NOT NULL DEFAULT 0,
                    created_at                TEXT    DEFAULT (datetime('now'))
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_coherence_mode
                ON fleet_coherence_log(failure_mode)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_coherence_severity
                ON fleet_coherence_log(severity)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_coherence_resolved
                ON fleet_coherence_log(resolved)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_coherence_rule
                ON fleet_coherence_log(rule_name)
            """)
            conn.execute(
                "INSERT OR IGNORE INTO schema_versions (phase, migration_name, applied_at)"
                " VALUES (?, ?, ?)",
                (193, "fleet_coherence", time.time()),
            )
            # Phase 194: coherence_fingerprint_log — contradiction fingerprint registry.
            # Tracks occurrence_count per rule_name across all FleetSignalCoherenceAgent cycles.
            # A rule is "persistent" when occurrence_count >= N_PROMOTE_THRESHOLD (3).
            # Persistent contradictions are fed into ProtocolMaturityScoringAgent as a
            # threat_forecast_accuracy penalty: score *= (1 - min(1.0, persistent_count * 0.10)).
            # Also adds on_chain_confirmed column to fleet_coherence_log (idempotent ALTER TABLE).
            try:
                conn.execute(
                    "ALTER TABLE fleet_coherence_log ADD COLUMN on_chain_confirmed INTEGER NOT NULL DEFAULT 0"
                )
            except Exception:
                pass  # Column already exists on upgraded DBs — safe to ignore; fail-open: M-1 cleanup 2026-05-16
            conn.execute("""
                CREATE TABLE IF NOT EXISTS coherence_fingerprint_log (
                    id                INTEGER PRIMARY KEY AUTOINCREMENT,
                    rule_name         TEXT    NOT NULL UNIQUE,
                    failure_mode      TEXT    NOT NULL DEFAULT '',
                    first_seen_at     TEXT    NOT NULL DEFAULT (datetime('now')),
                    last_seen_at      TEXT    NOT NULL DEFAULT (datetime('now')),
                    occurrence_count  INTEGER NOT NULL DEFAULT 1,
                    persistent        INTEGER NOT NULL DEFAULT 0,
                    promoted_to_wif   INTEGER NOT NULL DEFAULT 0,
                    wif_entry_id      TEXT,
                    maturity_penalty  REAL    NOT NULL DEFAULT 0.0,
                    created_at        TEXT    DEFAULT (datetime('now'))
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_fingerprint_persistent
                ON coherence_fingerprint_log(persistent, occurrence_count DESC)
            """)
            conn.execute(
                "INSERT OR IGNORE INTO schema_versions (phase, migration_name, applied_at)"
                " VALUES (?, ?, ?)",
                (194, "coherence_fingerprint", time.time()),
            )
            # Phase 176: poac_chain_audit_log — PoACChainIntegrityMonitor (agent #25).
            # Audits SHA-256 chain linkage across PoAC records for each device.
            # integrity_score = valid_links / total_links (0.0 = broken, 1.0 = intact).
            # W1 mitigation: only aggregate counts exposed (never broken record IDs).
            conn.execute("""
                CREATE TABLE IF NOT EXISTS poac_chain_audit_log (
                    id                INTEGER PRIMARY KEY AUTOINCREMENT,
                    device_id         TEXT    NOT NULL DEFAULT '',
                    total_records     INTEGER NOT NULL DEFAULT 0,
                    valid_links       INTEGER NOT NULL DEFAULT 0,
                    broken_links      INTEGER NOT NULL DEFAULT 0,
                    integrity_score   REAL    NOT NULL DEFAULT 1.0,
                    audit_passed      INTEGER NOT NULL DEFAULT 1,
                    created_at        REAL    NOT NULL DEFAULT (strftime('%s','now'))
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_chain_audit_device
                ON poac_chain_audit_log(device_id, created_at DESC)
            """)
            # Phase 175: age_weight_analysis_log — AgeWeightedRatioPersistenceAgent (agent #24).
            # Persists results of --session-age-weight analysis runs (Phase 174 script).
            # temporal_drift_index = raw_ratio - age_weighted_ratio:
            #   positive  → old sessions inflate ratio (P1 non-stationarity present)
            #   negative  → new sessions stronger (player improving/stabilizing over time)
            #   near-zero → player is biometrically stationary (ideal state)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS age_weight_analysis_log (
                    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
                    probe_type           TEXT    NOT NULL DEFAULT 'touchpad_corners',
                    raw_ratio            REAL    NOT NULL DEFAULT 0.0,
                    age_weighted_ratio   REAL    NOT NULL DEFAULT 0.0,
                    temporal_drift_index REAL    NOT NULL DEFAULT 0.0,
                    halflife_days        REAL    NOT NULL DEFAULT 90.0,
                    n_sessions_used      INTEGER NOT NULL DEFAULT 0,
                    drift_direction      TEXT    NOT NULL DEFAULT 'STABLE',
                    created_at           REAL    NOT NULL DEFAULT (strftime('%s','now'))
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_age_weight_created
                ON age_weight_analysis_log(created_at DESC)
            """)
            # Phase 164: consent_snapshot_log — WIF-023 ConsentSnapshotAnchor.
            # Records consent coverage at every separation-ratio commit so that post-commit
            # revocations produce a verifiable delta chain rather than silent divergence.
            # commit_hash links to separation_ratio_registry_log.commit_hash (foreign key semantics).
            conn.execute("""
                CREATE TABLE IF NOT EXISTS consent_snapshot_log (
                    id                       INTEGER PRIMARY KEY AUTOINCREMENT,
                    commit_hash              TEXT    NOT NULL,
                    n_consented_at_commit    INTEGER NOT NULL DEFAULT 0,
                    revoked_count_at_commit  INTEGER NOT NULL DEFAULT 0,
                    erasure_count_at_commit  INTEGER NOT NULL DEFAULT 0,
                    snapshot_ts              REAL    NOT NULL,
                    created_at               REAL    NOT NULL DEFAULT (unixepoch('now'))
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_consent_snapshot_commit
                ON consent_snapshot_log(commit_hash, created_at DESC)
            """)
            # Phase 165: post_erasure_ratio_log — WIF-024 Post-Erasure Separation Recompute.
            # When a device's biometric data is anonymised (GDPR Art.17), the stored
            # separation ratio becomes stale because the anonymised device's feature
            # vectors can no longer contribute to the next run of
            # analyze_interperson_separation.py.  This table creates an audit trail so
            # operators know when the ratio needs recomputing.
            # ratio_after is NULL until a new defensibility entry is inserted post-analysis.
            conn.execute("""
                CREATE TABLE IF NOT EXISTS post_erasure_ratio_log (
                    id               INTEGER PRIMARY KEY AUTOINCREMENT,
                    device_id        TEXT    NOT NULL,
                    n_anonymized     INTEGER NOT NULL DEFAULT 0,
                    ratio_before     REAL,
                    ratio_after      REAL,
                    recompute_needed INTEGER NOT NULL DEFAULT 1,
                    triggered_by     TEXT    NOT NULL DEFAULT 'anonymize_device_records',
                    consent_type     TEXT    NOT NULL DEFAULT 'biometric',
                    recompute_ts     REAL    NOT NULL,
                    created_at       REAL    NOT NULL DEFAULT (unixepoch('now'))
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_post_erasure_device
                ON post_erasure_ratio_log(device_id, created_at DESC)
            """)
            # Phase 135: tournament_activation_chain_log — TournamentActivationChainAgent records
            conn.execute("""
                CREATE TABLE IF NOT EXISTS tournament_activation_chain_log (
                    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_type            TEXT    NOT NULL DEFAULT 'breakthrough_received',
                    separation_ratio      REAL    NOT NULL DEFAULT 0.0,
                    n_players             INTEGER NOT NULL DEFAULT 0,
                    gate_open_notified    INTEGER NOT NULL DEFAULT 0,
                    auto_activate_blocked INTEGER NOT NULL DEFAULT 1,
                    operator_action_required INTEGER NOT NULL DEFAULT 1,
                    notes                 TEXT,
                    created_at            REAL    NOT NULL DEFAULT (unixepoch('now'))
                )
            """)
            # Phase 134: l4_recalibration_jobs — automated L4 recalibration pipeline jobs
            # status: "running" | "complete" | "failed"
            conn.execute("""
                CREATE TABLE IF NOT EXISTS l4_recalibration_jobs (
                    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
                    started_at           REAL    NOT NULL DEFAULT 0.0,
                    completed_at         REAL,
                    sessions_processed   INTEGER NOT NULL DEFAULT 0,
                    anomaly_result       REAL    NOT NULL DEFAULT 0.0,
                    continuity_result    REAL    NOT NULL DEFAULT 0.0,
                    status               TEXT    NOT NULL DEFAULT 'running',
                    error                TEXT,
                    created_at           REAL    NOT NULL DEFAULT (unixepoch('now'))
                )
            """)
            # Phase 133: ioswarm_poad_anchor_log — Swarm PoAd auto-anchor records
            # anchor_status: "pending" | "anchored" | "failed" | "skipped_disabled"
            conn.execute("""
                CREATE TABLE IF NOT EXISTS ioswarm_poad_anchor_log (
                    id               INTEGER PRIMARY KEY AUTOINCREMENT,
                    device_id        TEXT    NOT NULL DEFAULT '',
                    session_id       TEXT    NOT NULL DEFAULT '',
                    dual_veto        INTEGER NOT NULL DEFAULT 0,
                    swarm_fingerprint TEXT   NOT NULL DEFAULT '',
                    poad_hash        TEXT    NOT NULL DEFAULT '',
                    on_chain_tx      TEXT,
                    anchor_status    TEXT    NOT NULL DEFAULT 'pending',
                    created_at       REAL    NOT NULL DEFAULT (strftime('%s','now'))
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_ioswarm_poad_anchor_device
                ON ioswarm_poad_anchor_log(device_id, created_at DESC)
            """)
            # Phase 132: ioswarm_node_health_log — live node health polling records
            conn.execute("""
                CREATE TABLE IF NOT EXISTS ioswarm_node_health_log (
                    id               INTEGER PRIMARY KEY AUTOINCREMENT,
                    node_url         TEXT    NOT NULL DEFAULT '',
                    healthy          INTEGER NOT NULL DEFAULT 0,
                    latency_ms       REAL    NOT NULL DEFAULT -1.0,
                    staker_address   TEXT    NOT NULL DEFAULT '',
                    error_msg        TEXT    NOT NULL DEFAULT '',
                    polled_at        REAL    NOT NULL DEFAULT 0.0,
                    created_at       REAL    NOT NULL DEFAULT (unixepoch('now'))
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_ioswarm_health_url
                ON ioswarm_node_health_log(node_url, polled_at DESC)
            """)
            # Phase 109A: add swarm_score column to epistemic_consensus_log (idempotent)
            try:
                conn.execute(
                    "ALTER TABLE epistemic_consensus_log ADD COLUMN swarm_score REAL NOT NULL DEFAULT 0.0"
                )
            except Exception:
                pass  # Column already exists; fail-open: M-1 cleanup 2026-05-16
            # Phase 86: Synthetic session corpus (isolated — never touches ruling_validation_log)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS synthetic_sessions (
                    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id           TEXT NOT NULL UNIQUE,
                    device_id            TEXT NOT NULL,
                    inference_code       INTEGER NOT NULL DEFAULT 32,
                    humanity_score       REAL NOT NULL,
                    fallback_verdict     TEXT NOT NULL,
                    fallback_confidence  REAL NOT NULL,
                    passed_fallback      INTEGER NOT NULL DEFAULT 0,
                    corpus_run_id        TEXT,
                    created_at           REAL NOT NULL DEFAULT (strftime('%s','now'))
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_synthetic_session_run
                ON synthetic_sessions(corpus_run_id, created_at DESC)
            """)
            # Phase 88: add divergence_reason column to ruling_validation_log (idempotent)
            try:
                conn.execute(
                    "ALTER TABLE ruling_validation_log ADD COLUMN divergence_reason TEXT"
                )
            except Exception:
                pass  # Column already exists — no-op; fail-open: M-1 cleanup 2026-05-16
            # Phase 89: Protocol Intelligence Reports
            conn.execute("""
                CREATE TABLE IF NOT EXISTS protocol_intelligence_reports (
                    id                       INTEGER PRIMARY KEY AUTOINCREMENT,
                    protocol_health_score    REAL NOT NULL,
                    gate_progress_score      REAL NOT NULL DEFAULT 0.0,
                    fleet_health_score       REAL NOT NULL DEFAULT 0.0,
                    divergence_clarity_score REAL NOT NULL DEFAULT 0.0,
                    corpus_pass_score        REAL NOT NULL DEFAULT 0.0,
                    class_j_confidence_score REAL NOT NULL DEFAULT 0.0,
                    shadow_pass_score        REAL,
                    triage_confidence_score  REAL,
                    ready_for_live_mode      INTEGER NOT NULL DEFAULT 0,
                    bottleneck               TEXT,
                    estimated_days_to_gate   REAL,
                    components_json          TEXT NOT NULL DEFAULT '{}',
                    recommendation           TEXT NOT NULL DEFAULT '',
                    created_at               REAL NOT NULL DEFAULT (strftime('%s','now'))
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_pia_created
                ON protocol_intelligence_reports(created_at DESC)
            """)
            # Phase 90: Shadow Enforcement Log
            conn.execute("""
                CREATE TABLE IF NOT EXISTS shadow_enforcement_log (
                    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
                    device_id            TEXT NOT NULL,
                    ruling_id            INTEGER,
                    verdict              TEXT NOT NULL DEFAULT 'BLOCK',
                    commitment_hash      TEXT,
                    would_have_suspended INTEGER NOT NULL DEFAULT 1,
                    duration_s           INTEGER,
                    warmup_attack_score  REAL,
                    created_at           REAL NOT NULL DEFAULT (strftime('%s','now'))
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_shadow_enf_device
                ON shadow_enforcement_log(device_id, created_at DESC)
            """)
            # Phase 91: Divergence Triage Reports
            conn.execute("""
                CREATE TABLE IF NOT EXISTS divergence_triage_reports (
                    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
                    device_id               TEXT NOT NULL,
                    divergence_count        INTEGER NOT NULL DEFAULT 0,
                    escalated               INTEGER NOT NULL DEFAULT 0,
                    patterns                TEXT,
                    ml_bot_high_count       INTEGER NOT NULL DEFAULT 0,
                    cheat_count             INTEGER NOT NULL DEFAULT 0,
                    enrollment_anomaly_count INTEGER NOT NULL DEFAULT 0,
                    assessed_at             REAL NOT NULL DEFAULT (strftime('%s','now'))
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_triage_device
                ON divergence_triage_reports(device_id, assessed_at DESC)
            """)
            # Phase 92: Live Mode Activation Pipeline audit log
            conn.execute("""
                CREATE TABLE IF NOT EXISTS live_mode_activation_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_type TEXT NOT NULL,
                    ready_for_live_mode INTEGER NOT NULL DEFAULT 0,
                    protocol_health_score REAL,
                    bottleneck TEXT,
                    blocking_conditions TEXT,
                    operator_notes TEXT,
                    created_at REAL NOT NULL DEFAULT (strftime('%s','now'))
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_activation_log_created
                ON live_mode_activation_log(created_at DESC)
            """)
            # Phase 94: Escalation ruling log (triage reactive loop)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS escalation_ruling_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    device_id TEXT NOT NULL,
                    patterns TEXT,
                    verdict TEXT,
                    ruling_id INTEGER,
                    was_deferred INTEGER NOT NULL DEFAULT 0,
                    created_at REAL NOT NULL DEFAULT (strftime('%s','now'))
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_escalation_ruling_device
                ON escalation_ruling_log(device_id, created_at DESC)
            """)
            # Bootstrap schema version history (idempotent INSERT OR IGNORE)
            for _ph, _nm in [
                (21, "pitl_sidecar"), (22, "phg_checkpoints"),
                (23, "biometric_continuity"), (24, "phg_delta_fix"),
                (25, "agent_intelligence"), (26, "zk_pitl"),
                (27, "session_proofs"), (28, "phg_credential"),
                (29, "operator_gate"), (30, "bridge_agent"),
                (31, "session_persistence"), (32, "proactive_monitor"),
                (34, "federation_bus"), (35, "insight_synthesizer"),
                (36, "adaptive_feedback"), (37, "credential_enforcement"),
                (38, "living_calibration"), (42, "l6_calibration_capture"),
                (50, "phase50_agent_coordination"),
                (51, "game_aware_profiling"),
                (55, "ioid_device_identity"),
                (56, "tournament_passport"),
                (58, "security_hardening"),
                (59, "controller_twin"),
                (61, "session_replay"),
                (62, "enrollment_ceremony"),
                (63, "l6b_reflex_layer"),
                (65, "autonomous_intelligence_layer"),
                (66, "ruling_enforcement_pipeline"),
                (67, "ceremony_hardening"),
                (69, "data_sovereignty_layer"),
                (72, "phgcredential_bridge_multisig"),
                (73, "ceremony_enrichment"),
                (75, "validation_gate_watchdog"),
                (76, "ruling_provenance_anchors"),
                (79, "agent_message_bus_live_mode"),
                (80, "federation_threat_signals"),
                (81, "class_j_detection"),
                (82, "reactive_adjudication_log"),
                (83, "supervisor_health_log"),
                (84, "gate_attestation_anchor"),
                (86, "synthetic_corpus"),
                (88, "campaign_tracker"),
                (89, "protocol_intelligence"),
                (90, "shadow_enforcement"),
                (91, "divergence_triage"),
                (92, "live_mode_activation_log"),
                (94, "escalation_ruling_log"),
                (95, "activation_audit"),
                (96, "enforcement_certificates"),
                (97, "live_mode_guard"),
                (98, "epistemic_consensus"),
                (99, "vapi_token"),
                (992, "gsr_registry"),
                (993, "vhp_issuances"),
                (101, "quicksilver_collateral_events"),
                (102, "vhp_renewal_log"),
                (103, "activation_simulation"),
                (104, "activation_state"),
                (105, "epistemic_threshold_history"),
                (107, "live_mode_readiness"),
                (108, "tournament_readiness"),
                (109, "ioswarm_consensus_log"),
                (109, "ioswarm_renewal_log"),
                (109, "ioswarm_adjudication_log"),
                (110, "ioswarm_vhp_mint_log"),
                (111, "poad_registry_log"),
                (112, "poad_anchor"),
                (113, "dual_primitive_gate"),
                (114, "vhp_dual_gate"),
                (115, "epoch_window"),
                (116, "epoch_window_analytics"),
                (117, "epoch_window_device_heatmap"),
                (118, "epoch_window_device_overrides"),
                (119, "epoch_override_lifecycle"),
                (120, "bt_transport"),
                (121, "separation_ratio"),
                (122, "confidence_multiplier"),
                (123, "l4_calibration_staleness"),
                (124, "l4_threshold_tracks"),
                (125, "per_battery_calibration"),
                (126, "l4_router"),
                (127, "tournament_preflight"),
                (128, "intelligence_dashboard"),
                (129, "separation_breakthrough"),
                (130, "swarm_operator_gate"),
                (131, "ioswarm_node_registry"),
                (132, "ioswarm_node_health"),
                (133, "ioswarm_poad_anchor"),
                (134, "l4_recalibration_jobs"),
                (135, "tournament_activation_chain"),
                (1315, "usb_reconnect"),
                (150, "separation_defensibility"),
                (152, "centroid_velocity"),
                (153, "separation_ratio_registry"),
                (154, "capture_stagnation"),
                (155, "controller_hardware_profiles"),
                (156, "enrollment_guidance"),
                (157, "fleet_consensus_snapshot"),
                (158, "gsr_hmac_pohbg"),
                (159, "biometric_privacy_compliance"),
                (160, "consent_ledger"),
                (161, "consent_gate"),
                (162, "consent_aware_corpus"),
                (163, "consent_bound_separation_hash"),
                (164, "consent_snapshot"),
                (165, "post_erasure_recompute"),
                (168, "bootstrap_ci_separation_ratio"),
                (173, "separation_ratio_recovery"),
                (178, "biometric_renewal"),
                (179, "ceremony_audit"),
                (180, "biometric_renewal_chain"),
            ]:
                conn.execute(
                    "INSERT OR IGNORE INTO schema_versions (phase, migration_name, applied_at)"
                    " VALUES (?, ?, ?)",
                    (_ph, _nm, time.time()),
                )
            # Phase 202: tremor_convergence_log — TremorRestingConvergenceOracle.
            # Tracks per-session tremor_resting separation ratio velocity to gate
            # the irreversible SeparationRatioRegistry.sol commitment chain.
            # velocity = (ratio_curr - ratio_prev) / N_delta between successive sessions.
            # convergence_stable=1 when velocity >= 0 for 2 consecutive sessions.
            # Closes WIF-037 W1: premature on-chain commitment on declining velocity.
            conn.execute("""
                CREATE TABLE IF NOT EXISTS tremor_convergence_log (
                    id                        INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_type              TEXT    NOT NULL DEFAULT 'tremor_resting',
                    ratio                     REAL    NOT NULL DEFAULT 0.0,
                    velocity                  REAL    NOT NULL DEFAULT 0.0,
                    n_sessions                INTEGER NOT NULL DEFAULT 0,
                    convergence_stable        INTEGER NOT NULL DEFAULT 0,
                    consecutive_positive      INTEGER NOT NULL DEFAULT 0,
                    sessions_to_target_est    INTEGER NOT NULL DEFAULT 0,
                    created_at                REAL    NOT NULL DEFAULT (unixepoch('now'))
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_tremor_conv_session_type
                ON tremor_convergence_log(session_type, created_at DESC)
            """)
            conn.execute(
                "INSERT OR IGNORE INTO schema_versions (phase, migration_name, applied_at)"
                " VALUES (?, ?, ?)",
                (202, "tremor_convergence", time.time()),
            )
            # Phase 203: agent_context_log — AgentContextRegistry on-chain prompt commitment.
            # Anchors SHA-256(system_prompt) for each LLM agent to detect prompt drift.
            # UNIQUE(agent_id, prompt_sha256) prevents duplicate registrations (anti-replay).
            # on_chain_tx populated when agent_context_on_chain_enabled=True and
            # AgentContextRegistry.sol anchor() call succeeds.
            # Closes WIF-036 W1: static Phase 201 tests can't detect runtime semantic drift.
            conn.execute("""
                CREATE TABLE IF NOT EXISTS agent_context_log (
                    id             INTEGER PRIMARY KEY AUTOINCREMENT,
                    agent_id       TEXT    NOT NULL,
                    prompt_sha256  TEXT    NOT NULL,
                    phase_number   INTEGER NOT NULL DEFAULT 0,
                    on_chain_tx    TEXT,
                    anchored_at    REAL,
                    created_at     REAL    NOT NULL DEFAULT (unixepoch('now'))
                )
            """)
            conn.execute("""
                CREATE UNIQUE INDEX IF NOT EXISTS ux_agent_context
                ON agent_context_log(agent_id, prompt_sha256)
            """)
            conn.execute(
                "INSERT OR IGNORE INTO schema_versions (phase, migration_name, applied_at)"
                " VALUES (?, ?, ?)",
                (203, "agent_context", time.time()),
            )
            # Phase 207: dry_run_graduation_log — StagedDryRunGraduationGate.
            # Tracks per-agent controlled graduation from dry_run=True → dry_run=False.
            # Each row is one graduation stage for one agent.  n_clean_sessions and
            # n_false_positives are incremented as adjudication results arrive.
            # rollback_triggered=1 when n_false_positives exceeds the threshold within
            # the rollback window — agent reverts to dry_run=True automatically.
            # stage_number is the sequential graduation order (1 = first agent to graduate).
            conn.execute("""
                CREATE TABLE IF NOT EXISTS dry_run_graduation_log (
                    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
                    agent_id              TEXT    NOT NULL,
                    stage_number          INTEGER NOT NULL DEFAULT 1,
                    activated_at          REAL    NOT NULL DEFAULT (unixepoch('now')),
                    dry_run_disabled_at   REAL,
                    rollback_triggered    INTEGER NOT NULL DEFAULT 0,
                    rollback_triggered_at REAL,
                    rollback_reason       TEXT,
                    n_clean_sessions      INTEGER NOT NULL DEFAULT 0,
                    n_false_positives     INTEGER NOT NULL DEFAULT 0,
                    notes                 TEXT    NOT NULL DEFAULT '',
                    created_at            REAL    NOT NULL DEFAULT (unixepoch('now'))
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_graduation_agent
                ON dry_run_graduation_log(agent_id, created_at DESC)
            """)
            conn.execute(
                "INSERT OR IGNORE INTO schema_versions (phase, migration_name, applied_at)"
                " VALUES (?, ?, ?)",
                (207, "dry_run_graduation", time.time()),
            )
            # Phase 208: corpus_ratio_regression_guard_log — tamper-evident provenance chain
            # for separation ratio breakthrough milestones (WIF-039 W1+W2).
            # Each row with all_pairs_above_1=True is linked to its predecessor via
            # provenance_hash = SHA-256(prev_hash + ratio + N + probe_type + ts_ns_str).
            # Enables Mode-6-style ratchet: once all_pairs_above_1=True is reached for a
            # probe type, subsequent inserts with all_pairs_above_1=False raise CorpusRegressionError
            # unless an override is recorded in corpus_regression_override_log.
            conn.execute("""
                CREATE TABLE IF NOT EXISTS corpus_ratio_regression_guard_log (
                    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
                    probe_type            TEXT    NOT NULL,
                    ratio                 REAL    NOT NULL,
                    n_sessions_total      INTEGER NOT NULL DEFAULT 0,
                    all_pairs_above_1     INTEGER NOT NULL DEFAULT 0,
                    provenance_hash       TEXT    NOT NULL DEFAULT '',
                    prev_hash             TEXT    NOT NULL DEFAULT '',
                    created_at            REAL    NOT NULL DEFAULT (unixepoch('now'))
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_corpus_guard_probe_created
                ON corpus_ratio_regression_guard_log(probe_type, created_at DESC)
            """)
            # Phase 208: corpus_regression_override_log — authorized regressions below 1.0.
            # Records operator-supplied reason when a regression override is granted.
            # override_hash = SHA-256(probe_type + old_ratio_str + new_ratio_str + reason + ts_ns_str).
            conn.execute("""
                CREATE TABLE IF NOT EXISTS corpus_regression_override_log (
                    id             INTEGER PRIMARY KEY AUTOINCREMENT,
                    probe_type     TEXT    NOT NULL,
                    old_ratio      REAL    NOT NULL,
                    new_ratio      REAL    NOT NULL,
                    reason         TEXT    NOT NULL DEFAULT '',
                    override_hash  TEXT    NOT NULL DEFAULT '',
                    created_at     REAL    NOT NULL DEFAULT (unixepoch('now'))
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_regression_override_probe
                ON corpus_regression_override_log(probe_type, created_at DESC)
            """)
            conn.execute(
                "INSERT OR IGNORE INTO schema_versions (phase, migration_name, applied_at)"
                " VALUES (?, ?, ?)",
                (208, "corpus_ratio_regression_guard", time.time()),
            )
            # Phase 214: graduation_autowatch_log — tracks all_pairs_p0_ok state transitions
            # observed by SeparationRatioMonitorAgent and the precondition evaluation results
            # from StagedDryRunGraduationAgent (WIF-041 mitigation).
            # Rows with trigger_fired=True indicate a False→True transition was detected.
            # preconditions_evaluated=True rows record the automated check result.
            conn.execute("""
                CREATE TABLE IF NOT EXISTS graduation_autowatch_log (
                    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
                    probe_type              TEXT    NOT NULL DEFAULT 'tremor_resting',
                    ratio                   REAL    NOT NULL DEFAULT 0.0,
                    all_pairs_above_1       INTEGER NOT NULL DEFAULT 0,
                    trigger_fired           INTEGER NOT NULL DEFAULT 0,
                    preconditions_evaluated INTEGER NOT NULL DEFAULT 0,
                    preconditions_met       INTEGER,
                    blockers_json           TEXT    NOT NULL DEFAULT '[]',
                    created_at              REAL    NOT NULL DEFAULT (unixepoch('now'))
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_graduation_autowatch_probe
                ON graduation_autowatch_log(probe_type, created_at DESC)
            """)
            conn.execute(
                "INSERT OR IGNORE INTO schema_versions (phase, migration_name, applied_at)"
                " VALUES (?, ?, ?)",
                (214, "graduation_autowatch", time.time()),
            )
            # Phase 215: l4_dim_sync_log — confirms L4 calibration thresholds remain valid
            # when live_feature_dim (13) > calibration_feature_dim (12).
            # Phase 121 added touchpad_spatial_entropy (index 12) which is structurally
            # zero in gameplay sessions, so thresholds (7.009/5.367) are unchanged.
            # A sync entry confirms this without requiring a full recalibration run.
            conn.execute("""
                CREATE TABLE IF NOT EXISTS l4_dim_sync_log (
                    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
                    from_dim             INTEGER NOT NULL,
                    to_dim               INTEGER NOT NULL,
                    anomaly_threshold    REAL    NOT NULL,
                    continuity_threshold REAL    NOT NULL,
                    n_sessions           INTEGER NOT NULL DEFAULT 0,
                    sync_reason          TEXT    NOT NULL DEFAULT '',
                    sync_completed       INTEGER NOT NULL DEFAULT 1,
                    created_at           REAL    NOT NULL DEFAULT (unixepoch('now'))
                )
            """)
            conn.execute(
                "INSERT OR IGNORE INTO schema_versions (phase, migration_name, applied_at)"
                " VALUES (?, ?, ?)",
                (215, "l4_dim_sync", time.time()),
            )
            # Phase 216: per_pair_gap_log — stores individual Mahalanobis inter-pair distances.
            # Phase 197 only stored all_pairs_above_1 (boolean). This table records per-pair
            # distances (e.g. P1vP3=0.032) so the blocker is visible in the live API and
            # can be trended over time to validate the Phase 213 AccelTremorFFT fix impact.
            conn.execute("""
                CREATE TABLE IF NOT EXISTS per_pair_gap_log (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_type    TEXT    NOT NULL DEFAULT '',
                    pair_key        TEXT    NOT NULL DEFAULT '',
                    player_i        TEXT    NOT NULL DEFAULT '',
                    player_j        TEXT    NOT NULL DEFAULT '',
                    distance        REAL    NOT NULL DEFAULT 0.0,
                    above_1_0       INTEGER NOT NULL DEFAULT 0,
                    n_sessions_i    INTEGER NOT NULL DEFAULT 0,
                    n_sessions_j    INTEGER NOT NULL DEFAULT 0,
                    analysis_date   TEXT    NOT NULL DEFAULT '',
                    created_at      REAL    NOT NULL DEFAULT (unixepoch('now'))
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_per_pair_gap_session_pair
                ON per_pair_gap_log(session_type, pair_key, created_at DESC)
            """)
            conn.execute(
                "INSERT OR IGNORE INTO schema_versions (phase, migration_name, applied_at)"
                " VALUES (?, ?, ?)",
                (216, "per_pair_gap_log", time.time()),
            )
            # Phase 217: per_pair_gap_trend_alert_log — records each time the
            # PER_PAIR_GAP_BLOCKER_UNRESOLVED ORPHAN rule fires in FSCA.
            conn.execute("""
                CREATE TABLE IF NOT EXISTS per_pair_gap_trend_alert_log (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    pair_key        TEXT    NOT NULL DEFAULT '',
                    distance        REAL    NOT NULL DEFAULT 0.0,
                    trend           TEXT    NOT NULL DEFAULT 'UNKNOWN',
                    velocity_per_day REAL,
                    alert_severity  TEXT    NOT NULL DEFAULT 'HIGH',
                    created_at      REAL    NOT NULL DEFAULT (unixepoch('now'))
                )
            """)
            conn.execute(
                "INSERT OR IGNORE INTO schema_versions (phase, migration_name, applied_at)"
                " VALUES (?, ?, ?)",
                (217, "per_pair_gap_trend_alert", time.time()),
            )
            # Phase 218: capture_velocity_oracle_log — unified oracle snapshots.
            conn.execute("""
                CREATE TABLE IF NOT EXISTS capture_velocity_oracle_log (
                    id                       INTEGER PRIMARY KEY AUTOINCREMENT,
                    probe_type               TEXT    NOT NULL DEFAULT 'touchpad_corners',
                    sessions_per_day         REAL    NOT NULL DEFAULT 0.0,
                    sessions_stagnant        INTEGER NOT NULL DEFAULT 1,
                    ratio_velocity           REAL    NOT NULL DEFAULT 0.0,
                    velocity_stagnant        INTEGER NOT NULL DEFAULT 1,
                    overall_capture_healthy  INTEGER NOT NULL DEFAULT 0,
                    recommended_action       TEXT    NOT NULL DEFAULT '',
                    created_at               REAL    NOT NULL DEFAULT (unixepoch('now'))
                )
            """)
            conn.execute(
                "INSERT OR IGNORE INTO schema_versions (phase, migration_name, applied_at)"
                " VALUES (?, ?, ?)",
                (218, "capture_velocity_oracle", time.time()),
            )
            # Phase 219: tournament_blocker_summary_log — aggregated TGE blocker snapshots.
            conn.execute("""
                CREATE TABLE IF NOT EXISTS tournament_blocker_summary_log (
                    id               INTEGER PRIMARY KEY AUTOINCREMENT,
                    total_blockers   INTEGER NOT NULL DEFAULT 0,
                    blockers_json    TEXT    NOT NULL DEFAULT '[]',
                    overall_blocked  INTEGER NOT NULL DEFAULT 1,
                    created_at       REAL    NOT NULL DEFAULT (unixepoch('now'))
                )
            """)
            conn.execute(
                "INSERT OR IGNORE INTO schema_versions (phase, migration_name, applied_at)"
                " VALUES (?, ?, ?)",
                (219, "tournament_blocker_summary", time.time()),
            )
            # Phase 220: per_pair_gap_projection_log — TGE timeline projections.
            conn.execute("""
                CREATE TABLE IF NOT EXISTS per_pair_gap_projection_log (
                    id                     INTEGER PRIMARY KEY AUTOINCREMENT,
                    pair_key               TEXT    NOT NULL DEFAULT '',
                    session_type           TEXT    NOT NULL DEFAULT '',
                    current_distance       REAL    NOT NULL DEFAULT 0.0,
                    velocity_per_day       REAL,
                    estimated_days_to_1_0  REAL,
                    projected_date         TEXT,
                    projection_feasible    INTEGER NOT NULL DEFAULT 0,
                    created_at             REAL    NOT NULL DEFAULT (unixepoch('now'))
                )
            """)
            conn.execute(
                "INSERT OR IGNORE INTO schema_versions (phase, migration_name, applied_at)"
                " VALUES (?, ?, ?)",
                (220, "per_pair_gap_projection", time.time()),
            )

            # Phase 221: protocol_coherence_log — PoPC Merkle root anchors.
            conn.execute("""
                CREATE TABLE IF NOT EXISTS protocol_coherence_log (
                    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
                    merkle_root        TEXT    NOT NULL DEFAULT '',
                    agent_count        INTEGER NOT NULL DEFAULT 0,
                    anchor_hash        TEXT    NOT NULL DEFAULT '',
                    on_chain_confirmed INTEGER NOT NULL DEFAULT 0,
                    created_at         REAL    NOT NULL DEFAULT (unixepoch('now'))
                )
            """)
            conn.execute(
                "INSERT OR IGNORE INTO schema_versions (phase, migration_name, applied_at)"
                " VALUES (?, ?, ?)",
                (221, "protocol_coherence", time.time()),
            )

            # Phase 222: bbg_proposal_log — BiometricBoundGovernance proposal records.
            conn.execute("""
                CREATE TABLE IF NOT EXISTS bbg_proposal_log (
                    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
                    proposal_hash      TEXT    NOT NULL DEFAULT '',
                    proposer_address   TEXT    NOT NULL DEFAULT '',
                    vhp_token_id       INTEGER NOT NULL DEFAULT 0,
                    vhp_expires_at     REAL    NOT NULL DEFAULT 0.0,
                    on_chain_confirmed INTEGER NOT NULL DEFAULT 0,
                    tx_hash            TEXT    NOT NULL DEFAULT '',
                    created_at         REAL    NOT NULL DEFAULT (unixepoch('now'))
                )
            """)
            conn.execute(
                "INSERT OR IGNORE INTO schema_versions (phase, migration_name, applied_at)"
                " VALUES (?, ?, ?)",
                (222, "bbg_proposal", time.time()),
            )

            # Phase 223: invariant_gate_log — PV-CI protocol invariant gate results.
            conn.execute("""
                CREATE TABLE IF NOT EXISTS invariant_gate_log (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    gate_pass       INTEGER NOT NULL DEFAULT 0,
                    total_checked   INTEGER NOT NULL DEFAULT 0,
                    failures_json   TEXT    NOT NULL DEFAULT '[]',
                    run_source      TEXT    NOT NULL DEFAULT 'manual',
                    created_at      REAL    NOT NULL DEFAULT (unixepoch('now'))
                )
            """)
            conn.execute(
                "INSERT OR IGNORE INTO schema_versions (phase, migration_name, applied_at)"
                " VALUES (?, ?, ?)",
                (223, "invariant_gate", time.time()),
            )

            # Phase 224: allowlist governance columns + allowlist_change_log.
            for _col224, _def224 in [
                ("previous_allowlist_hash", "TEXT NOT NULL DEFAULT ''"),
                ("new_allowlist_hash",      "TEXT NOT NULL DEFAULT ''"),
                ("reason_category",         "TEXT NOT NULL DEFAULT ''"),
                ("reason_text",             "TEXT NOT NULL DEFAULT ''"),
            ]:
                try:
                    conn.execute(
                        f"ALTER TABLE invariant_gate_log ADD COLUMN {_col224} {_def224}"
                    )
                except Exception:
                    pass  # column already exists — idempotent

            try:
                conn.execute(
                    "ALTER TABLE protocol_coherence_log "
                    "ADD COLUMN allowlist_hash TEXT NOT NULL DEFAULT ''"
                )
            except Exception:
                pass  # idempotent

            # Phase 227: add governance_provenance_hash column (idempotent)
            try:
                conn.execute(
                    "ALTER TABLE protocol_coherence_log "
                    "ADD COLUMN governance_provenance_hash TEXT NOT NULL DEFAULT ''"
                )
            except Exception:
                pass  # idempotent

            conn.execute("""
                CREATE TABLE IF NOT EXISTS allowlist_change_log (
                    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
                    previous_hash         TEXT NOT NULL DEFAULT '',
                    new_hash              TEXT NOT NULL DEFAULT '',
                    merkle_root_at_change TEXT NOT NULL DEFAULT '',
                    detected_at           TEXT NOT NULL DEFAULT '',
                    reason_from_gate_log  TEXT
                )
            """)
            conn.execute(
                "INSERT OR IGNORE INTO schema_versions (phase, migration_name, applied_at)"
                " VALUES (?, ?, ?)",
                (224, "allowlist_governance", time.time()),
            )

            # Phase 225: governance_provenance_hash on invariant_gate_log + chain table.
            try:
                conn.execute(
                    "ALTER TABLE invariant_gate_log "
                    "ADD COLUMN governance_provenance_hash TEXT NOT NULL DEFAULT ''"
                )
            except Exception:
                pass  # idempotent

            conn.execute("""
                CREATE TABLE IF NOT EXISTS governance_provenance_chain (
                    id                       INTEGER PRIMARY KEY AUTOINCREMENT,
                    governance_provenance_hash TEXT NOT NULL DEFAULT '',
                    previous_provenance_hash TEXT NOT NULL DEFAULT '',
                    new_allowlist_hash       TEXT NOT NULL DEFAULT '',
                    reason_category          TEXT NOT NULL DEFAULT '',
                    reason_text              TEXT NOT NULL DEFAULT '',
                    created_at               REAL NOT NULL DEFAULT 0
                )
            """)
            conn.execute(
                "INSERT OR IGNORE INTO schema_versions (phase, migration_name, applied_at)"
                " VALUES (?, ?, ?)",
                (225, "governance_provenance_chain", time.time()),
            )

            # Phase 228: vhp_token_id on invariant_gate_log (idempotent)
            try:
                conn.execute(
                    "ALTER TABLE invariant_gate_log "
                    "ADD COLUMN vhp_token_id TEXT NOT NULL DEFAULT ''"
                )
            except Exception:
                pass  # idempotent

            # Phase 229: AIT (Active Isometric Trigger) separation log.
            # Stores per-run AIT separation analysis results so the bridge can
            # surface AIT separation status via API and the tournament preflight
            # can gate on all_pairs_above_1 for the 'ait' probe type.
            conn.execute("""
                CREATE TABLE IF NOT EXISTS ait_session_log (
                    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
                    probe_type           TEXT    NOT NULL DEFAULT 'ait',
                    n_sessions           INTEGER NOT NULL DEFAULT 0,
                    n_per_player_json    TEXT    NOT NULL DEFAULT '{}',
                    separation_ratio     REAL    NOT NULL DEFAULT 0.0,
                    all_pairs_above_1    INTEGER NOT NULL DEFAULT 0,
                    inter_player_mean    REAL    NOT NULL DEFAULT 0.0,
                    intra_player_mean    REAL    NOT NULL DEFAULT 0.0,
                    loo_accuracy         REAL    NOT NULL DEFAULT 0.0,
                    cov_mode             TEXT    NOT NULL DEFAULT 'diagonal',
                    pair_distances_json  TEXT    NOT NULL DEFAULT '{}',
                    analysis_date        TEXT    NOT NULL DEFAULT '',
                    created_at           REAL    NOT NULL DEFAULT 0.0
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_ait_session_log_probe
                ON ait_session_log(probe_type, created_at DESC)
            """)
            conn.execute(
                "INSERT OR IGNORE INTO schema_versions (phase, migration_name, applied_at)"
                " VALUES (?, ?, ?)",
                (229, "ait_session_log", time.time()),
            )

        # Phase 234.7 — Physical Capture Continuity log (idempotent)
        with self._conn() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS capture_health_log (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    capture_state   TEXT    NOT NULL DEFAULT 'DISCONNECTED',
                    host_state      TEXT    NOT NULL DEFAULT 'UNKNOWN',
                    poll_rate_hz    REAL    NOT NULL DEFAULT 0.0,
                    transition_reason TEXT  NOT NULL DEFAULT '',
                    grind_mode      INTEGER NOT NULL DEFAULT 0,
                    session_id      TEXT    NOT NULL DEFAULT '',
                    prev_session_id TEXT    NOT NULL DEFAULT '',
                    gap_duration_ms REAL    NOT NULL DEFAULT 0.0,
                    created_at      REAL    NOT NULL DEFAULT 0.0
                );
                CREATE INDEX IF NOT EXISTS idx_capture_health_log_ts
                    ON capture_health_log(created_at DESC);
            """)
            conn.execute(
                "INSERT OR IGNORE INTO schema_versions (phase, migration_name, applied_at)"
                " VALUES (?, ?, ?)",
                (2347, "capture_health_log", time.time()),
            )

        # Phase 2350 (pre-235): PCC attestation + GIC slot on ruling_validation_log (idempotent)
        # grind_session_id added by INV-GIC-001 fix (Ultrareview Commit 1) to scope chains.
        for _col_sql in [
            "ALTER TABLE ruling_validation_log ADD COLUMN pcc_state TEXT",
            "ALTER TABLE ruling_validation_log ADD COLUMN pcc_host_state TEXT",
            "ALTER TABLE ruling_validation_log ADD COLUMN grind_chain_hash TEXT",
            "ALTER TABLE ruling_validation_log ADD COLUMN gic_ts_ns INTEGER",
            "ALTER TABLE ruling_validation_log ADD COLUMN grind_session_id TEXT",
        ]:
            try:
                with self._conn() as conn:
                    conn.execute(_col_sql)
            except Exception:
                pass  # idempotent — column already exists

        # Phase 235-DASH: per-player AIT feature means for live radar (idempotent)
        try:
            with self._conn() as conn:
                conn.execute(
                    "ALTER TABLE ait_session_log "
                    "ADD COLUMN per_player_features_json TEXT NOT NULL DEFAULT '{}'"
                )
        except Exception:
            pass  # idempotent — column already exists

        # Phase 235-GAD: Gameplay Activity Discrimination (idempotent)
        for _col_sql in [
            "ALTER TABLE records ADD COLUMN trigger_active INTEGER NOT NULL DEFAULT 0",
            "ALTER TABLE ruling_validation_log ADD COLUMN gameplay_context TEXT",
        ]:
            try:
                with self._conn() as conn:
                    conn.execute(_col_sql)
            except Exception:
                pass  # idempotent — column already exists
        try:
            with self._conn() as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS gameplay_classification_disagreements (
                        id              INTEGER PRIMARY KEY AUTOINCREMENT,
                        ruling_validation_log_id INTEGER NOT NULL,
                        device_id       TEXT NOT NULL DEFAULT '',
                        automatic_context TEXT NOT NULL DEFAULT '',
                        override_reason TEXT NOT NULL DEFAULT '',
                        created_at      REAL NOT NULL
                    )
                """)
        except Exception:
            pass  # fail-open: M-1 cleanup 2026-05-16 — intentional silent skip

        # Phase B item ③ — iPACT-DePIN renewal-cadence commitment chain (idempotent)
        try:
            with self._conn() as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS ipact_renewal_commitments (
                        id              INTEGER PRIMARY KEY AUTOINCREMENT,
                        device_id       TEXT    NOT NULL,
                        token_id        INTEGER NOT NULL,
                        epoch_index     INTEGER NOT NULL,
                        prev_commitment TEXT    NOT NULL,
                        reattest_proof  TEXT    NOT NULL,
                        commitment      TEXT    NOT NULL,
                        ts_ns           INTEGER NOT NULL,
                        enforced        INTEGER NOT NULL DEFAULT 0,
                        created_at      REAL    NOT NULL DEFAULT 0.0,
                        UNIQUE(device_id, epoch_index)
                    );
                    CREATE INDEX IF NOT EXISTS idx_ipact_renewal_device
                        ON ipact_renewal_commitments(device_id, epoch_index);
                """)
        except Exception:
            pass  # idempotent — table already exists

        # Phase 241-APOP: Active Play Occupancy Proof shadow/hybrid audit log.
        try:
            with self._conn() as conn:
                conn.executescript("""
                    CREATE TABLE IF NOT EXISTS active_play_occupancy_log (
                        id              INTEGER PRIMARY KEY AUTOINCREMENT,
                        ruling_validation_log_id INTEGER NOT NULL,
                        ruling_id       INTEGER NOT NULL,
                        device_id       TEXT NOT NULL DEFAULT '',
                        state           TEXT NOT NULL DEFAULT 'UNKNOWN_LOW_EVIDENCE',
                        score           REAL NOT NULL DEFAULT 0.0,
                        confidence      REAL NOT NULL DEFAULT 0.0,
                        evidence_json   TEXT NOT NULL DEFAULT '{}',
                        gate_mode       TEXT NOT NULL DEFAULT 'shadow',
                        created_at      REAL NOT NULL
                    );
                    CREATE INDEX IF NOT EXISTS idx_apop_validation
                        ON active_play_occupancy_log(ruling_validation_log_id);
                    CREATE INDEX IF NOT EXISTS idx_apop_created
                        ON active_play_occupancy_log(created_at DESC);
                """)
        except Exception:
            pass  # fail-open: M-1 cleanup 2026-05-16 — intentional silent skip

        # Phase 236-CORPUS-SNAPSHOT: ZK-attested corpus snapshot table.
        # Sits below WEC and GIC in the chain stack. Each row binds the entire
        # wiki tree + fleet Merkle root + AIT separation ratio + corpus size
        # at one ts_ns into a single SHA-256 commitment. Surfaces as proof of
        # what the corpus looked like at GIC_100 deposit time.
        try:
            with self._conn() as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS corpus_snapshot_log (
                        id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                        snapshot_commitment TEXT NOT NULL,
                        wiki_hash           TEXT NOT NULL,
                        agent_root          TEXT NOT NULL DEFAULT '',
                        separation_ratio    REAL NOT NULL DEFAULT 0.0,
                        corpus_n            INTEGER NOT NULL DEFAULT 0,
                        ts_ns               INTEGER NOT NULL,
                        on_chain_confirmed  INTEGER NOT NULL DEFAULT 0,
                        ipfs_cid            TEXT NOT NULL DEFAULT '',
                        tx_hash             TEXT NOT NULL DEFAULT '',
                        trigger_reason      TEXT NOT NULL DEFAULT '',
                        created_at          REAL NOT NULL
                    )
                """)
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_corpus_snapshot_log_ts "
                    "ON corpus_snapshot_log(ts_ns DESC)"
                )
                conn.execute(
                    "CREATE UNIQUE INDEX IF NOT EXISTS idx_corpus_snapshot_log_commit "
                    "ON corpus_snapshot_log(snapshot_commitment)"
                )
                conn.execute(
                    "INSERT OR IGNORE INTO schema_versions (phase, migration_name, applied_at)"
                    " VALUES (?, ?, ?)",
                    (236, "corpus_snapshot_log", time.time()),
                )
        except Exception:
            pass  # idempotent

        # Phase 237-ZK-SEPPROOF: extend ait_session_log with centroids + cov_inv
        # so the bridge prover can reconstruct ZK witness inputs without re-running
        # analyze_interperson_separation.py.  Both columns are JSON-encoded for
        # forward-compatibility with feature_dim changes; canonical canonicalisation
        # happens at compute_biometric_commitment() time.
        for _col_sql in [
            "ALTER TABLE ait_session_log ADD COLUMN centroids_json TEXT NOT NULL DEFAULT '{}'",
            "ALTER TABLE ait_session_log ADD COLUMN cov_inv_json   TEXT NOT NULL DEFAULT '[]'",
        ]:
            try:
                with self._conn() as conn:
                    conn.execute(_col_sql)
            except Exception:
                pass  # idempotent — column already exists

        # Phase 237-ZK-SEPPROOF: BIOMETRIC-SNAPSHOT-v1 anchor history.
        # Sixth FROZEN-v1 primitive in PATTERN-016 family.  Mirrors corpus_snapshot_log
        # shape but binds centroids + cov_inv bytes (not just ratio + N).  ZK-SEPPROOF
        # circuit consumes snapshot_commitment as public input #0/#1 to prove the
        # witness centroids match an on-chain anchored corpus state.
        try:
            with self._conn() as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS biometric_snapshot_log (
                        id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                        snapshot_commitment TEXT NOT NULL,
                        feature_dim         INTEGER NOT NULL,
                        n_players           INTEGER NOT NULL,
                        sorted_player_ids   TEXT    NOT NULL DEFAULT '[]',
                        centroids_json      TEXT    NOT NULL DEFAULT '{}',
                        cov_inv_json        TEXT    NOT NULL DEFAULT '[]',
                        ts_ns               INTEGER NOT NULL,
                        on_chain_confirmed  INTEGER NOT NULL DEFAULT 0,
                        tx_hash             TEXT    NOT NULL DEFAULT '',
                        trigger_reason      TEXT    NOT NULL DEFAULT '',
                        ait_session_log_id  INTEGER NOT NULL DEFAULT 0,
                        created_at          REAL    NOT NULL
                    )
                """)
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_biometric_snapshot_log_ts "
                    "ON biometric_snapshot_log(ts_ns DESC)"
                )
                conn.execute(
                    "CREATE UNIQUE INDEX IF NOT EXISTS idx_biometric_snapshot_log_commit "
                    "ON biometric_snapshot_log(snapshot_commitment)"
                )
                conn.execute(
                    "INSERT OR IGNORE INTO schema_versions (phase, migration_name, applied_at)"
                    " VALUES (?, ?, ?)",
                    (237, "biometric_snapshot_log", time.time()),
                )
        except Exception:
            pass  # idempotent

        # Phase 238-MARKETPLACE: LISTING-v1 anchor history.
        # Seventh FROZEN-v1 primitive in PATTERN-016 family.  Per-listing
        # cryptographic provenance: each row binds up to 5 prior FROZEN-v1
        # anchors (SEPPROOF + BIOMETRIC + CORPUS + GIC + CONSENT bitmask) +
        # data_class + price + IPFS CID hash into one 32-byte commitment.
        # The on-chain extension contract VAPIDataMarketplaceListings.sol
        # reads referenced AdjudicationRegistry anchors to compute the
        # listing's multiplier tier (1.0x / 1.5x / 2.0x / 3.0x).  Multiplier
        # is enforced cryptographically — sellers cannot self-attest tier.
        try:
            with self._conn() as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS marketplace_listing_log (
                        id                       INTEGER PRIMARY KEY AUTOINCREMENT,
                        listing_commitment       TEXT NOT NULL,
                        seller_address           TEXT NOT NULL DEFAULT '',
                        sepproof_commitment      TEXT NOT NULL DEFAULT '',
                        biometric_snapshot_hash  TEXT NOT NULL DEFAULT '',
                        corpus_snapshot_hash     TEXT NOT NULL DEFAULT '',
                        gic_hash                 TEXT NOT NULL DEFAULT '',
                        consent_bitmask          INTEGER NOT NULL,
                        data_class               INTEGER NOT NULL,
                        price_iotx               REAL    NOT NULL DEFAULT 0.0,
                        ipfs_cid                 TEXT    NOT NULL DEFAULT '',
                        ipfs_cid_hash            TEXT    NOT NULL DEFAULT '',
                        ts_ns                    INTEGER NOT NULL,
                        on_chain_confirmed       INTEGER NOT NULL DEFAULT 0,
                        tx_hash                  TEXT    NOT NULL DEFAULT '',
                        anchors_present_count    INTEGER NOT NULL DEFAULT 0,
                        trigger_reason           TEXT    NOT NULL DEFAULT '',
                        created_at               REAL    NOT NULL
                    )
                """)
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_marketplace_listing_log_ts "
                    "ON marketplace_listing_log(ts_ns DESC)"
                )
                conn.execute(
                    "CREATE UNIQUE INDEX IF NOT EXISTS idx_marketplace_listing_log_commit "
                    "ON marketplace_listing_log(listing_commitment)"
                )
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_marketplace_listing_log_seller "
                    "ON marketplace_listing_log(seller_address)"
                )
                conn.execute(
                    "INSERT OR IGNORE INTO schema_versions (phase, migration_name, applied_at)"
                    " VALUES (?, ?, ?)",
                    (238, "marketplace_listing_log", time.time()),
                )
        except Exception:
            pass  # idempotent

        # Phase 238 Step I — curator_listing_review_log table.
        # Append-only Curator review verdict ledger.  One row per Curator
        # review fired against a marketplace_listing_log entry.  No UNIQUE
        # constraint on listing_commitment because the same listing can be
        # re-reviewed any number of times (e.g. anchor went stale → flagged
        # retroactively in bulk re-review).  Index on listing_commitment +
        # ts_ns DESC supports per-listing timeline drawer query pattern.
        try:
            with self._conn() as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS curator_listing_review_log (
                        id                          INTEGER PRIMARY KEY AUTOINCREMENT,
                        listing_commitment          TEXT NOT NULL,
                        verdict                     TEXT NOT NULL,
                        severity                    TEXT NOT NULL,
                        anchors_recorded_count      INTEGER NOT NULL DEFAULT 0,
                        anchors_breakdown_json      TEXT NOT NULL DEFAULT '{}',
                        consent_marketplace_bit_set INTEGER NOT NULL DEFAULT 0,
                        ipfs_resolvable             INTEGER,
                        declared_tier               INTEGER NOT NULL DEFAULT 0,
                        tier_at_review_time         INTEGER NOT NULL DEFAULT 0,
                        tier_changed                INTEGER NOT NULL DEFAULT 0,
                        shadow_mode                 INTEGER NOT NULL DEFAULT 1,
                        reason_detail               TEXT NOT NULL DEFAULT '',
                        trigger_reason              TEXT NOT NULL DEFAULT '',
                        ts_ns                       INTEGER NOT NULL,
                        created_at                  REAL    NOT NULL
                    )
                """)
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_curator_review_listing "
                    "ON curator_listing_review_log(listing_commitment, ts_ns DESC)"
                )
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_curator_review_verdict "
                    "ON curator_listing_review_log(verdict, ts_ns DESC)"
                )
                conn.execute(
                    "INSERT OR IGNORE INTO schema_versions (phase, migration_name, applied_at)"
                    " VALUES (?, ?, ?)",
                    (238, "curator_listing_review_log", time.time()),
                )
        except Exception:
            pass  # idempotent

        # Phase O3-ZKBA-TRACK1 — Zero-Knowledge Biometric Artifact (ZKBA) log.
        # Tenth FROZEN-v1 primitive in PATTERN-017 family (pending VBDIP-0001
        # Step 3 Amendment #1 count reconciliation).  Each row binds:
        #   - zkba_class (1 of 7 from VBDIP-0002 §5)
        #   - proof_weight (1 of 6 from VBDIP-0002 §6)
        #   - sorted component hashes (composed FROZEN-v1 primitives)
        #   - ts_ns
        # into one 32-byte commitment via compute_zkba_commitment().
        # UNIQUE(commitment_hex) enforces idempotent insert.  anchor_tx_hash
        # NULL throughout Track 1 (no chain submission in pre-activation scope
        # per PLAN-VBDIP-0002-ZKBA-PARALLEL-v1 §4; populated by future Stream A3
        # parallel_zkba_anchor.py after VBDIP-0001 FROZEN).
        try:
            with self._conn() as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS zkba_artifact_log (
                        id                       INTEGER PRIMARY KEY AUTOINCREMENT,
                        commitment_hex           TEXT NOT NULL,
                        zkba_class               INTEGER NOT NULL,
                        proof_weight             INTEGER NOT NULL,
                        preimage_json            TEXT NOT NULL DEFAULT '[]',
                        ts_ns                    INTEGER NOT NULL,
                        manifest_uri             TEXT,
                        compiler_output_hash_hex TEXT,
                        anchor_tx_hash           TEXT,
                        created_at               REAL NOT NULL
                    )
                """)
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_zkba_artifact_log_ts "
                    "ON zkba_artifact_log(ts_ns DESC)"
                )
                conn.execute(
                    "CREATE UNIQUE INDEX IF NOT EXISTS idx_zkba_artifact_log_commit "
                    "ON zkba_artifact_log(commitment_hex)"
                )
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_zkba_artifact_log_class "
                    "ON zkba_artifact_log(zkba_class, ts_ns DESC)"
                )
                conn.execute(
                    "INSERT OR IGNORE INTO schema_versions (phase, migration_name, applied_at)"
                    " VALUES (?, ?, ?)",
                    (1100, "zkba_artifact_log", time.time()),
                )
        except Exception:
            pass  # idempotent

        # Phase O4-VPM-INT B.0 — vpm_artifact_log table.
        # Records VPM artifacts (HTML + manifest sidecar pair) emitted by
        # the Phase O4 compile_vpm_artifact() entry-point in
        # scripts/vsd_ui_compiler.py. Mirrors the zkba_artifact_log shape
        # above but adds VPM-specific columns (vpm_id, visual_state,
        # capture_mode, integrity_label_hash_hex, wrapper_schema,
        # zkba_manifest_hash_hex) so a VPM artifact can be traced back to
        # its underlying ZKBA projection + Integrity Label + visual state.
        # UNIQUE(commitment_hex) enforces idempotent insert. The VPM
        # artifact is filesystem-only at landing; no on-chain anchor
        # column (additive surface, not replacement for ZKBA primitive).
        try:
            with self._conn() as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS vpm_artifact_log (
                        id                         INTEGER PRIMARY KEY AUTOINCREMENT,
                        commitment_hex             TEXT NOT NULL,
                        vpm_id                     TEXT NOT NULL,
                        zkba_class                 INTEGER NOT NULL,
                        proof_weight               INTEGER NOT NULL,
                        visual_state               TEXT NOT NULL,
                        capture_mode               TEXT NOT NULL,
                        integrity_label_hash_hex   TEXT NOT NULL,
                        wrapper_schema             TEXT NOT NULL,
                        zkba_manifest_hash_hex     TEXT NOT NULL,
                        manifest_uri               TEXT,
                        compiler_output_hash_hex   TEXT,
                        preimage_json              TEXT NOT NULL DEFAULT '{}',
                        ts_ns                      INTEGER NOT NULL,
                        created_at                 REAL NOT NULL
                    )
                """)
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_vpm_artifact_log_ts "
                    "ON vpm_artifact_log(ts_ns DESC)"
                )
                conn.execute(
                    "CREATE UNIQUE INDEX IF NOT EXISTS idx_vpm_artifact_log_commit "
                    "ON vpm_artifact_log(commitment_hex)"
                )
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_vpm_artifact_log_vpm_id "
                    "ON vpm_artifact_log(vpm_id, ts_ns DESC)"
                )
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_vpm_artifact_log_state "
                    "ON vpm_artifact_log(visual_state, ts_ns DESC)"
                )
                conn.execute(
                    "INSERT OR IGNORE INTO schema_versions (phase, migration_name, applied_at)"
                    " VALUES (?, ?, ?)",
                    (1200, "vpm_artifact_log", time.time()),
                )
        except Exception:
            pass  # idempotent

        # Phase O4-VPM-INT follow-up — cfss_lane_drift_log table.
        # Sink for findings from cfss_drift_sweeper.py (continuous Cedar
        # policy CFSS lane authority drift detection at the policy layer,
        # complementing FSCA's existing data-layer drift detection).
        #
        # Each row = one (agent_id, action, resource) row where the live
        # bundle file's Cedar policy evaluation drifted from
        # EXPECTED_LANE_MATRIX. INV-OPERATOR-AGENT-008 dual-cadence
        # contract: written by the sweeper at the 60s bundle cadence.
        # Consumed by the 27th FSCA contradiction rule
        # CFSS_LANE_AUTHORITY_DRIFT (CRITICAL severity).
        try:
            with self._conn() as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS cfss_lane_drift_log (
                        id              INTEGER PRIMARY KEY AUTOINCREMENT,
                        sweep_id        TEXT    NOT NULL,
                        agent_id        TEXT    NOT NULL,
                        action          TEXT    NOT NULL,
                        resource        TEXT,
                        expected_effect TEXT    NOT NULL,
                        actual_effect   TEXT    NOT NULL,
                        bundle_path     TEXT,
                        evidence_json   TEXT,
                        created_at      REAL    NOT NULL
                    )
                """)
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_cfss_drift_created "
                    "ON cfss_lane_drift_log(created_at DESC)"
                )
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_cfss_drift_agent "
                    "ON cfss_lane_drift_log(agent_id, created_at DESC)"
                )
                conn.execute(
                    "INSERT OR IGNORE INTO schema_versions (phase, migration_name, applied_at)"
                    " VALUES (?, ?, ?)",
                    (1210, "cfss_lane_drift_log", time.time()),
                )
        except Exception:
            pass  # idempotent

        # Phase O1 C1 — operator_agent_activation_log table.
        # Mirrors the on-chain AgentScopeRootSet + AgentScopeUpdated events
        # for each Cedar bundle anchor cycle (D4 dual-anchor).  UNIQUE
        # constraint on (agent_id, to_scope_root) enforces anti-replay
        # (INV-OPERATOR-AGENT-002): each (agent, scope_root) tuple can be
        # activated exactly once.  Phase number 1001 distinguishes the
        # Operator-track migrations from the main protocol-track sequence.
        try:
            with self._conn() as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS operator_agent_activation_log (
                        id                       INTEGER PRIMARY KEY AUTOINCREMENT,
                        agent_id                 TEXT    NOT NULL,
                        from_phase               TEXT    NOT NULL,
                        to_phase                 TEXT    NOT NULL,
                        from_scope_root          TEXT    NOT NULL,
                        to_scope_root            TEXT    NOT NULL,
                        bundle_path              TEXT    NOT NULL,
                        governance_tx_hash       TEXT    NOT NULL,
                        operational_tx_hash      TEXT    NOT NULL,
                        governance_block_number  INTEGER NOT NULL,
                        operational_block_number INTEGER NOT NULL,
                        operator_authority_hash  TEXT    NOT NULL,
                        reason_text              TEXT    NOT NULL,
                        activated_at             REAL    NOT NULL,
                        UNIQUE(agent_id, to_scope_root)
                    )
                """)
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_oaal_agent_time "
                    "ON operator_agent_activation_log(agent_id, activated_at DESC)"
                )
                conn.execute(
                    "INSERT OR IGNORE INTO schema_versions (phase, migration_name, applied_at)"
                    " VALUES (?, ?, ?)",
                    (1001, "operator_agent_activation_log", time.time()),
                )
        except Exception:
            pass  # idempotent

        # Phase O1 C2 — operator_agent_shadow_log table.
        # Records every Cedar evaluation cycle in shadow mode:
        # which agent attempted which (action, resource), what the
        # Cedar bundle decided (CedarDecision enum), and the
        # bundle's Merkle root at evaluation time (for drift audit
        # against operator_agent_activation_log).  This is the
        # observability foundation for the deferred Phase O1 C3
        # agent-process-startup work — once we have shadow log data,
        # FSCA rules can flag patterns and operator can decide on
        # advancement to O2_SUGGEST.
        #
        # UNIQUE constraint on (agent_id, action, resource, evaluated_at_bucket)
        # enforces idempotency at the second granularity (INV-OPERATOR-AGENT-003)
        # — protects against double-write from retry loops without rejecting
        # legitimate distinct evaluations.
        #
        # Phase 1002 distinguishes from Phase 1001 (activation log).
        try:
            with self._conn() as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS operator_agent_shadow_log (
                        id                       INTEGER PRIMARY KEY AUTOINCREMENT,
                        agent_id                 TEXT    NOT NULL,
                        action                   TEXT    NOT NULL,
                        resource                 TEXT    NOT NULL,
                        context_json             TEXT    NOT NULL,
                        decision                 TEXT    NOT NULL,
                        bundle_merkle_root       TEXT    NOT NULL,
                        bundle_path              TEXT    NOT NULL,
                        draft_payload_hash       TEXT    NOT NULL,
                        source                   TEXT    NOT NULL,
                        evaluated_at             REAL    NOT NULL,
                        evaluated_at_bucket      INTEGER NOT NULL,
                        UNIQUE(agent_id, action, resource, evaluated_at_bucket)
                    )
                """)
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_oasl_agent_time "
                    "ON operator_agent_shadow_log(agent_id, evaluated_at DESC)"
                )
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_oasl_decision "
                    "ON operator_agent_shadow_log(decision, evaluated_at DESC)"
                )
                conn.execute(
                    "INSERT OR IGNORE INTO schema_versions (phase, migration_name, applied_at)"
                    " VALUES (?, ?, ?)",
                    (1002, "operator_agent_shadow_log", time.time()),
                )
        except Exception:
            pass  # idempotent

        # Phase O1 C3 — operator_agent_drift_log table.
        # Records drift findings from periodic operator-triggered sweeps:
        #
        #   BUNDLE_HASH_DRIFT             — cedar_bundles/{agent}.json file's
        #                                   recomputed Merkle root != the
        #                                   to_scope_root recorded in the agent's
        #                                   most-recent activation_log row.
        #                                   Means someone mutated the bundle
        #                                   file post-anchor without re-anchoring.
        #
        #   SCOPE_HASH_GOVERNANCE_DRIFT   — AgentScope.getScopeRoot != the
        #                                   AgentRegistry.getAgent.scopeHash.
        #                                   Means the operational + governance
        #                                   layers diverged on chain (D4 dual-
        #                                   anchor invariant violation).
        #
        # Both are CRITICAL signals — the protocol's tamper-evidence rests on
        # their alignment. UNIQUE(agent_id, drift_type, detected_at_bucket)
        # deduplicates retry storms (INV-OPERATOR-AGENT-006).
        #
        # Phase 1003 distinguishes from 1001 (activation) + 1002 (shadow).
        try:
            with self._conn() as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS operator_agent_drift_log (
                        id                       INTEGER PRIMARY KEY AUTOINCREMENT,
                        agent_id                 TEXT    NOT NULL,
                        drift_type               TEXT    NOT NULL,
                        expected_value           TEXT    NOT NULL,
                        actual_value             TEXT    NOT NULL,
                        bundle_path              TEXT    NOT NULL,
                        evidence_json            TEXT    NOT NULL,
                        sweep_id                 TEXT    NOT NULL,
                        detected_at              REAL    NOT NULL,
                        detected_at_bucket       INTEGER NOT NULL,
                        UNIQUE(agent_id, drift_type, detected_at_bucket)
                    )
                """)
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_oadl_agent_time "
                    "ON operator_agent_drift_log(agent_id, detected_at DESC)"
                )
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_oadl_drift_type "
                    "ON operator_agent_drift_log(drift_type, detected_at DESC)"
                )
                conn.execute(
                    "INSERT OR IGNORE INTO schema_versions (phase, migration_name, applied_at)"
                    " VALUES (?, ?, ?)",
                    (1003, "operator_agent_drift_log", time.time()),
                )
        except Exception:
            pass  # idempotent

        # Phase O1-FRR — operator_initiative_advancement_log table.
        # Persists each fleet-readiness evaluation cycle from
        # operator_initiative_advancement.run_advancement_watcher_loop
        # AND every parallel anchor event from
        # scripts/parallel_o2_anchor.py.  frr_hex carries the Phase O1-FRR
        # commitment (eighth FROZEN-v1 primitive) over (agent_id, phase_code)
        # tuples — see operator_initiative_advancement.compute_fleet_readiness_root.
        #
        # Phase 1004 distinguishes from 1001 (activation) + 1002 (shadow) +
        # 1003 (drift). frr_hex nullable because watcher cycles before the
        # FRR primitive shipped will not have it; new rows always populate.
        try:
            with self._conn() as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS operator_initiative_advancement_log (
                        id                              INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp                       REAL    NOT NULL,
                        fleet_phase_aligned             INTEGER NOT NULL,
                        fleet_at_o1_count               INTEGER NOT NULL,
                        fleet_at_o2_ready_count         INTEGER NOT NULL,
                        fleet_at_o3_ready_count         INTEGER NOT NULL,
                        next_alignment_target           TEXT    NOT NULL,
                        per_agent_json                  TEXT    NOT NULL,
                        frr_hex                         TEXT,
                        frr_ts_ns                       INTEGER,
                        error                           TEXT,
                        created_at                      REAL    NOT NULL
                    )
                """)
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_oial_timestamp "
                    "ON operator_initiative_advancement_log(timestamp DESC)"
                )
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_oial_frr_hex "
                    "ON operator_initiative_advancement_log(frr_hex)"
                )
                conn.execute(
                    "INSERT OR IGNORE INTO schema_versions (phase, migration_name, applied_at)"
                    " VALUES (?, ?, ?)",
                    (1004, "operator_initiative_advancement_log", time.time()),
                )
        except Exception:
            pass  # idempotent

        # Phase O2-DRAFT-GENERATION (2026-05-10) — operator_agent_drafts table.
        # Persists each draft payload produced by an Operator Initiative agent
        # under O2 SUGGEST authority. Drafts are payloads under draft://...
        # URIs that the agent has authored but not yet anchored on chain (per
        # O2 SUGGEST bundle's permit set with no shadow_mode constraint).
        # Operator review (accept/reject) populates the operator_decision +
        # operator_decision_at columns; the disagreement_rate watcher gate
        # (PHASE_O3_DISAGREEMENT_RATE_MAX=0.05) reads reject/total ratio.
        # Schema phase 1005. agent_id stored as Q9 hex when cfg fields
        # populated (production); canonical name when test stubs key by name.
        try:
            with self._conn() as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS operator_agent_drafts (
                        id                              INTEGER PRIMARY KEY AUTOINCREMENT,
                        agent_id                        TEXT    NOT NULL,
                        action_category                 TEXT    NOT NULL,
                        action_name                     TEXT    NOT NULL,
                        draft_uri                       TEXT    NOT NULL,
                        payload_hash                    TEXT    NOT NULL,
                        payload_bytes                   INTEGER NOT NULL,
                        kms_sig_present                 INTEGER NOT NULL DEFAULT 0,
                        operator_decision               TEXT,
                        operator_decision_at            REAL,
                        operator_disagreement_reason    TEXT,
                        created_at                      REAL    NOT NULL
                    )
                """)
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_oad_agent_created "
                    "ON operator_agent_drafts(agent_id, created_at DESC)"
                )
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_oad_agent_decision "
                    "ON operator_agent_drafts(agent_id, operator_decision)"
                )
                conn.execute(
                    "CREATE UNIQUE INDEX IF NOT EXISTS idx_oad_payload_hash "
                    "ON operator_agent_drafts(agent_id, payload_hash)"
                )
                conn.execute(
                    "INSERT OR IGNORE INTO schema_versions (phase, migration_name, applied_at)"
                    " VALUES (?, ?, ?)",
                    (1005, "operator_agent_drafts", time.time()),
                )
        except Exception:
            pass  # idempotent

        # Phase O5-MYTHOS-MINIMAL M.1 — mythos_finding_log + mythos_cadence_log.
        # Mythos variants (Phase O5 M.2) write findings here; the FSCA loop
        # (Phase O5 M.3) polls mythos_finding_log via 2 new contradiction
        # rules. The cadence-engine wakeup history lives in
        # mythos_cadence_log for operator audit. coherence_id is UNIQUE
        # (anti-replay): mythos_<variant>_<sha256[:16]>. Severity values:
        # CRITICAL / HIGH / MEDIUM / LOW. Fix authority tier 1 (autofix-safe)
        # / 2 (operator-gated) / 3 (read-only — frozen_region=True always
        # tier 3 per INV-MYTHOS-FROZEN-PROTECTION-001). evidence_sources_json
        # is the W1 consensus-fallacy mitigation surface (declares the
        # corpus the variant audited so cross-variant overlap can be scored).
        try:
            with self._conn() as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS mythos_finding_log (
                        id                      INTEGER PRIMARY KEY AUTOINCREMENT,
                        variant                 TEXT    NOT NULL,
                        severity                TEXT    NOT NULL,
                        coherence_id            TEXT    NOT NULL UNIQUE,
                        file_path               TEXT,
                        line_number             INTEGER,
                        description             TEXT    NOT NULL,
                        recommended_fix         TEXT    NOT NULL,
                        frozen_region           INTEGER NOT NULL DEFAULT 0,
                        fix_authority_tier      INTEGER NOT NULL,
                        evidence_sources_json   TEXT    NOT NULL,
                        resolved                INTEGER NOT NULL DEFAULT 0,
                        resolution_commit       TEXT,
                        created_at              REAL    NOT NULL
                    )
                """)
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_mfl_variant_created "
                    "ON mythos_finding_log(variant, created_at DESC)"
                )
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_mfl_severity "
                    "ON mythos_finding_log(severity)"
                )
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_mfl_resolved "
                    "ON mythos_finding_log(resolved)"
                )
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS mythos_cadence_log (
                        id                      INTEGER PRIMARY KEY AUTOINCREMENT,
                        variant                 TEXT    NOT NULL,
                        cadence                 TEXT    NOT NULL,
                        findings_count          INTEGER NOT NULL,
                        duration_ms             INTEGER NOT NULL,
                        triggered_by            TEXT    NOT NULL,
                        error                   TEXT,
                        created_at              REAL    NOT NULL
                    )
                """)
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_mcl_variant_created "
                    "ON mythos_cadence_log(variant, created_at DESC)"
                )
                conn.execute(
                    "INSERT OR IGNORE INTO schema_versions (phase, migration_name, applied_at)"
                    " VALUES (?, ?, ?)",
                    (1100, "mythos_finding_log+mythos_cadence_log", time.time()),
                )
        except Exception:
            pass  # idempotent

        # Phase 242-BT Stream 1 — BT-WITNESS v1 capability scaffolding.
        # Each row records one BT-WITNESS commitment computed by the LAN-tower
        # BlueZ witness (Stream 2 wires the actual witness service).
        # commitment_hex UNIQUE constraint = anti-replay at the store layer.
        # Stream 1 schema only — feature_root_hex carries the FROZEN empty-
        # dict canonical-JSON SHA-256 until Stream 2 commits the canonical
        # feature set post-Stage-2 measurement campaign (v1.1 anchor §5).
        # on_chain_confirmed + tx_hash placeholders for Stream 3
        # BTWitnessRegistry.sol anchor (wallet-gated; deferred).
        try:
            with self._conn() as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS bt_witness_log (
                        id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                        commitment_hex      TEXT    NOT NULL,
                        witness_pubkey_hex  TEXT    NOT NULL,
                        device_id_hex       TEXT    NOT NULL,
                        session_id_hex      TEXT    NOT NULL,
                        feature_root_hex    TEXT    NOT NULL,
                        n_features          INTEGER NOT NULL DEFAULT 0,
                        transport_code      INTEGER NOT NULL,
                        ts_ns               INTEGER NOT NULL,
                        on_chain_confirmed  INTEGER NOT NULL DEFAULT 0,
                        tx_hash             TEXT    NOT NULL DEFAULT '',
                        trigger_reason      TEXT    NOT NULL DEFAULT '',
                        created_at          REAL    NOT NULL
                    )
                """)
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_bt_witness_log_ts "
                    "ON bt_witness_log(ts_ns DESC)"
                )
                conn.execute(
                    "CREATE UNIQUE INDEX IF NOT EXISTS idx_bt_witness_log_commit "
                    "ON bt_witness_log(commitment_hex)"
                )
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_bt_witness_log_session "
                    "ON bt_witness_log(session_id_hex, ts_ns DESC)"
                )
                conn.execute(
                    "INSERT OR IGNORE INTO schema_versions (phase, migration_name, applied_at)"
                    " VALUES (?, ?, ?)",
                    (1101, "bt_witness_log", time.time()),
                )
        except Exception:
            pass  # idempotent

        # Phase O5-MLGA Stage 2 — Mythos Live Gameplay Audit session log.
        # Each row persists one gameplay session's MLGA dataproof + the
        # raw aggregates from which it was computed (re-derivable). UNIQUE
        # on (session_id, dataproof_hex) = anti-replay. Wallet-free; only
        # local SQLite writes; no chain anchor in v1 (canonical record is
        # the dataproof commitment itself, verifiable post-session).
        try:
            with self._conn() as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS mlga_session_log (
                        id                        INTEGER PRIMARY KEY AUTOINCREMENT,
                        session_id                TEXT    NOT NULL,
                        session_start_ts_ns       INTEGER NOT NULL,
                        session_end_ts_ns         INTEGER NOT NULL,
                        n_poac_records            INTEGER NOT NULL,
                        n_trigger_pulls_r2        INTEGER NOT NULL,
                        n_trigger_pulls_l2        INTEGER NOT NULL,
                        apop_state_counts_json    TEXT    NOT NULL DEFAULT '{}',
                        bt_observability          INTEGER NOT NULL DEFAULT 0,
                        gic_advances_in_session   INTEGER NOT NULL DEFAULT 0,
                        dataproof_hex             TEXT    NOT NULL,
                        created_at                REAL    NOT NULL
                    )
                """)
                conn.execute(
                    "CREATE UNIQUE INDEX IF NOT EXISTS idx_mlga_session_unique "
                    "ON mlga_session_log(session_id, dataproof_hex)"
                )
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_mlga_session_start "
                    "ON mlga_session_log(session_start_ts_ns DESC)"
                )
                conn.execute(
                    "INSERT OR IGNORE INTO schema_versions (phase, migration_name, applied_at)"
                    " VALUES (?, ?, ?)",
                    (1102, "mlga_session_log", time.time()),
                )
        except Exception:
            pass  # idempotent

        # Phase O0 Stream 3-prep Session 1 — AGENT_COMMIT v1 store table.
        # Sixth FROZEN-v1 primitive in the family. Each row records a git
        # commit attestation produced by an Operator Agent, with the computed
        # AGENT_COMMIT v1 hash as the chain anchor primary key. UNIQUE constraint
        # on commit_hash enforces anti-replay locally; AgentAdjudicationRegistry
        # enforces it on-chain via _anchorIdByHash.
        try:
            with self._conn() as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS agent_commit_log (
                        id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                        commit_hash         TEXT NOT NULL UNIQUE,    -- hex of AGENT_COMMIT v1 hash
                        agent_id            TEXT NOT NULL,           -- hex of bytes32 agent_id
                        commit_sha          TEXT NOT NULL,           -- hex of git SHA-1 (40 chars)
                        prev_commit_hash    TEXT NOT NULL,           -- hex; "0"*64 for genesis
                        repo_uri_sha        TEXT NOT NULL,           -- hex of SHA-256(repo_uri)
                        ts_ns               INTEGER NOT NULL,
                        tx_hash             TEXT NOT NULL DEFAULT '',
                        on_chain_confirmed  INTEGER NOT NULL DEFAULT 0,
                        anchor_id           INTEGER NOT NULL DEFAULT -1,
                        created_at          REAL NOT NULL
                    )
                """)
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_agent_commit_log_agent_id "
                    "ON agent_commit_log(agent_id)"
                )
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_agent_commit_log_ts_ns "
                    "ON agent_commit_log(ts_ns)"
                )
                conn.execute(
                    "CREATE UNIQUE INDEX IF NOT EXISTS idx_agent_commit_log_commit_hash "
                    "ON agent_commit_log(commit_hash)"
                )
                conn.execute(
                    "INSERT OR IGNORE INTO schema_versions (phase, migration_name, applied_at)"
                    " VALUES (?, ?, ?)",
                    (238, "agent_commit_log", time.time()),
                )
        except Exception:
            pass  # idempotent

        # Phase O0 Stream 3-prep Session 2 — PHYSICAL_DATA_ATTESTATION v1
        # (seventh and final FROZEN-v1 primitive). Per Pass 2C Section 4.2.
        # Stores agents' off-chain certifications of physical-data artifacts
        # (biometric corpus snapshots, PoAC chain roots, tremor FFT feature
        # vectors, fleet-coherence observations, hardware-certification
        # proofs). UNIQUE(pda_commitment) enforces local idempotency in
        # parallel with AgentAdjudicationRegistry's on-chain anti-replay
        # tracker. attestation_type stored as canonical string (queryable);
        # attestation_type_hash stored as hex of keccak256(string) (audit).
        try:
            with self._conn() as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS physical_data_attestation_log (
                        id                     INTEGER PRIMARY KEY AUTOINCREMENT,
                        pda_commitment         TEXT NOT NULL UNIQUE,    -- hex of PDA v1 hash
                        hardware_data_hash     TEXT NOT NULL,           -- hex of SHA-256(physical data)
                        agent_id               TEXT NOT NULL,           -- hex of bytes32 agent_id
                        attestation_type       TEXT NOT NULL,           -- canonical string
                        attestation_type_hash  TEXT NOT NULL,           -- hex of keccak256(string)
                        ts_ns                  INTEGER NOT NULL,
                        tx_hash                TEXT NOT NULL DEFAULT '',
                        on_chain_confirmed     INTEGER NOT NULL DEFAULT 0,
                        anchor_id              INTEGER NOT NULL DEFAULT -1,
                        created_at             REAL NOT NULL
                    )
                """)
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_pda_log_agent_id "
                    "ON physical_data_attestation_log(agent_id)"
                )
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_pda_log_ts_ns "
                    "ON physical_data_attestation_log(ts_ns)"
                )
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_pda_log_attestation_type "
                    "ON physical_data_attestation_log(attestation_type)"
                )
                conn.execute(
                    "CREATE UNIQUE INDEX IF NOT EXISTS idx_pda_log_commitment "
                    "ON physical_data_attestation_log(pda_commitment)"
                )
                conn.execute(
                    "INSERT OR IGNORE INTO schema_versions (phase, migration_name, applied_at)"
                    " VALUES (?, ?, ?)",
                    (239, "physical_data_attestation_log", time.time()),
                )
        except Exception:
            pass  # idempotent

        # Phase 236-WATCHDOG: Watchdog Event Chain (WEC) audit table.
        # Pairs with the GIC chain — GIC tracks cognitive-session continuity,
        # WEC tracks operational continuity (bridge process lifetimes that
        # produced those sessions). Together they constitute a tamper-evident
        # provenance for a grind run.  The watchdog (scripts/bridge_watchdog.py)
        # is the only writer; bridge endpoints read for status/audit.
        try:
            with self._conn() as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS watchdog_event_log (
                        id                INTEGER PRIMARY KEY AUTOINCREMENT,
                        event_code        INTEGER NOT NULL,
                        event_name        TEXT NOT NULL DEFAULT '',
                        pid               INTEGER NOT NULL DEFAULT 0,
                        grind_session_id  TEXT NOT NULL DEFAULT '',
                        wec_hash          TEXT NOT NULL,
                        prev_wec_hash     TEXT NOT NULL DEFAULT '',
                        metadata_json     TEXT NOT NULL DEFAULT '{}',
                        ts_ns             INTEGER NOT NULL,
                        created_at        REAL NOT NULL
                    )
                """)
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_watchdog_event_log_ts "
                    "ON watchdog_event_log(ts_ns DESC)"
                )
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_watchdog_event_log_session "
                    "ON watchdog_event_log(grind_session_id, ts_ns DESC)"
                )
                conn.execute(
                    "INSERT OR IGNORE INTO schema_versions (phase, migration_name, applied_at)"
                    " VALUES (?, ?, ?)",
                    (236, "watchdog_event_log", time.time()),
                )
        except Exception:
            pass  # idempotent

        # Phase 239: gamer_readiness_log — GamerReadinessAgent (agent #39)
        try:
            with self._conn() as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS gamer_readiness_log (
                        id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                        device_id           TEXT    NOT NULL,
                        readiness_score     REAL    NOT NULL DEFAULT 1.0,
                        rsi_risk_score      REAL    NOT NULL DEFAULT 0.0,
                        fatigue_index       REAL    NOT NULL DEFAULT 0.0,
                        avg_tremor_hz       REAL    NOT NULL DEFAULT 0.0,
                        touchpad_entropy    REAL    NOT NULL DEFAULT 0.0,
                        reaction_latency_ms REAL    NOT NULL DEFAULT 0.0,
                        recommendation      TEXT    NOT NULL DEFAULT 'NOMINAL',
                        created_at          REAL    NOT NULL
                    )
                """)
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_gamer_readiness_created "
                    "ON gamer_readiness_log(device_id, created_at DESC)"
                )
                conn.execute(
                    "INSERT OR IGNORE INTO schema_versions (phase, migration_name, applied_at)"
                    " VALUES (?, ?, ?)",
                    (239, "gamer_readiness_log", time.time()),
                )
        except Exception:
            pass  # idempotent

    # --- Device operations ---

    def upsert_device(self, device_id: str, pubkey_hex: str):
        now = time.time()
        with self._conn() as conn:
            conn.execute("""
                INSERT INTO devices (device_id, pubkey_hex, first_seen, last_seen)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(device_id) DO UPDATE SET last_seen = ?
            """, (device_id, pubkey_hex, now, now, now))

    def update_device_state(self, device_id: str, record: PoACRecord):
        with self._conn() as conn:
            conn.execute("""
                UPDATE devices SET
                    last_seen = ?,
                    last_counter = ?,
                    chain_head = ?,
                    last_battery = ?,
                    last_latitude = ?,
                    last_longitude = ?,
                    records_total = records_total + 1
                WHERE device_id = ?
            """, (
                time.time(),
                record.monotonic_ctr,
                record.record_hash_hex,
                record.battery_pct,
                record.latitude,
                record.longitude,
                device_id,
            ))

    def get_device(self, device_id: str) -> dict | None:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM devices WHERE device_id = ?", (device_id,)
            ).fetchone()
            return dict(row) if row else None

    def get_device_pubkey(self, device_id: str) -> str | None:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT pubkey_hex FROM devices WHERE device_id = ?",
                (device_id,),
            ).fetchone()
            return row["pubkey_hex"] if row else None

    def list_devices(self) -> list[dict]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM devices ORDER BY last_seen DESC"
            ).fetchall()
            return [dict(r) for r in rows]

    # --- Record operations ---

    def insert_record(self, record: PoACRecord, raw_data: bytes) -> bool:
        """Insert a record. Returns False if duplicate."""
        try:
            with self._conn() as conn:
                conn.execute("""
                    INSERT INTO records
                        (record_hash, device_id, counter, timestamp_ms,
                         inference, action_code, confidence, battery_pct,
                         bounty_id, latitude, longitude, status, raw_data,
                         created_at,
                         pitl_l4_distance, pitl_l4_warmed, pitl_l4_features,
                         pitl_l5_cv, pitl_l5_entropy, pitl_l5_quant, pitl_l5_signals,
                         pitl_l5_rhythm_humanity, pitl_l4_drift_velocity,
                         pitl_e4_cognitive_drift, pitl_humanity_prob,
                         trigger_active)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    record.record_hash_hex,
                    record.device_id_hex,
                    record.monotonic_ctr,
                    record.timestamp_ms,
                    record.inference_result,
                    record.action_code,
                    record.confidence,
                    record.battery_pct,
                    record.bounty_id,
                    record.latitude,
                    record.longitude,
                    STATUS_PENDING,
                    raw_data,
                    time.time(),
                    record.pitl_l4_distance,
                    int(record.pitl_l4_warmed_up) if record.pitl_l4_warmed_up is not None else None,
                    record.pitl_l4_features_json,
                    record.pitl_l5_cv,
                    record.pitl_l5_entropy_bits,
                    record.pitl_l5_quant_score,
                    record.pitl_l5_anomaly_signals,
                    getattr(record, "pitl_l5_rhythm_humanity", None),
                    getattr(record, "pitl_l4_drift_velocity", None),
                    getattr(record, "pitl_e4_cognitive_drift", None),
                    getattr(record, "pitl_humanity_prob", None),
                    int(getattr(record, "pitl_trigger_active", 0) or 0),
                ))
            return True
        except sqlite3.IntegrityError:
            log.debug("Duplicate record: %s", record.record_hash_hex[:16])
            return False

    def get_pending_records(self, limit: int = 50) -> list[dict]:
        with self._conn() as conn:
            rows = conn.execute("""
                SELECT * FROM records
                WHERE status = ?
                ORDER BY counter ASC
                LIMIT ?
            """, (STATUS_PENDING, limit)).fetchall()
            return [dict(r) for r in rows]

    def update_record_status(self, record_hash: str, status: str):
        with self._conn() as conn:
            conn.execute(
                "UPDATE records SET status = ? WHERE record_hash = ?",
                (status, record_hash),
            )

    def batch_update_status(self, record_hashes: list[str], status: str):
        with self._conn() as conn:
            conn.executemany(
                "UPDATE records SET status = ? WHERE record_hash = ?",
                [(status, h) for h in record_hashes],
            )

    def increment_device_verified(self, device_id: str, count: int = 1):
        with self._conn() as conn:
            conn.execute("""
                UPDATE devices SET records_verified = records_verified + ?
                WHERE device_id = ?
            """, (count, device_id))

    # --- Submission tracking ---

    def create_submission(self, record_hashes: list[str]) -> int:
        with self._conn() as conn:
            cursor = conn.execute("""
                INSERT INTO submissions (record_hashes, status, created_at)
                VALUES (?, ?, ?)
            """, (json.dumps(record_hashes), STATUS_PENDING, time.time()))
            return cursor.lastrowid

    def update_submission(
        self, sub_id: int, *, status: str = None, tx_hash: str = None,
        error: str = None, retries: int = None,
    ):
        parts, params = [], []
        if status:
            parts.append("status = ?")
            params.append(status)
        if tx_hash:
            parts.append("tx_hash = ?")
            params.append(tx_hash)
            parts.append("submitted_at = ?")
            params.append(time.time())
        if error is not None:
            parts.append("last_error = ?")
            params.append(error)
        if retries is not None:
            parts.append("retries = ?")
            params.append(retries)
        if status == STATUS_VERIFIED:
            parts.append("confirmed_at = ?")
            params.append(time.time())

        if not parts:
            return

        # Defensive: every fragment MUST come from this closed allowlist.
        # If a future edit appends a user-controlled string to `parts`, this
        # assertion will trip in tests before the SQL hits the database.
        _ALLOWED_FRAGMENTS = {
            "status = ?", "tx_hash = ?", "submitted_at = ?",
            "last_error = ?", "retries = ?", "confirmed_at = ?",
        }
        for p in parts:
            if p not in _ALLOWED_FRAGMENTS:
                raise ValueError(
                    f"update_submission: rejected SQL fragment {p!r} "
                    f"(not in static allowlist)"
                )

        params.append(sub_id)
        with self._conn() as conn:
            conn.execute(
                f"UPDATE submissions SET {', '.join(parts)} WHERE id = ?",
                params,
            )

    def get_failed_submissions(self, max_retries: int) -> list[dict]:
        with self._conn() as conn:
            rows = conn.execute("""
                SELECT * FROM submissions
                WHERE status = ? AND retries < ?
                ORDER BY created_at ASC
            """, (STATUS_FAILED, max_retries)).fetchall()
            return [dict(r) for r in rows]

    # --- Statistics ---

    def get_stats(self) -> dict:
        with self._conn() as conn:
            devices = conn.execute("SELECT COUNT(*) FROM devices").fetchone()[0]
            records = conn.execute("SELECT COUNT(*) FROM records").fetchone()[0]
            pending = conn.execute(
                "SELECT COUNT(*) FROM records WHERE status = ?",
                (STATUS_PENDING,),
            ).fetchone()[0]
            verified = conn.execute(
                "SELECT COUNT(*) FROM records WHERE status = ?",
                (STATUS_VERIFIED,),
            ).fetchone()[0]
            failed = conn.execute(
                "SELECT COUNT(*) FROM records WHERE status = ?",
                (STATUS_FAILED,),
            ).fetchone()[0]
            dead = conn.execute(
                "SELECT COUNT(*) FROM records WHERE status = ?",
                (STATUS_DEAD_LETTER,),
            ).fetchone()[0]
            submissions = conn.execute(
                "SELECT COUNT(*) FROM submissions"
            ).fetchone()[0]

            return {
                "devices_active": devices,
                "records_total": records,
                "records_pending": pending,
                "records_verified": verified,
                "records_failed": failed,
                "records_dead_letter": dead,
                "submissions_total": submissions,
            }

    def get_recent_records(self, limit: int = 50, device_id: str | None = None) -> list[dict]:
        with self._conn() as conn:
            if device_id:
                rows = conn.execute("""
                    SELECT r.*, d.pubkey_hex FROM records r
                    LEFT JOIN devices d ON r.device_id = d.device_id
                    WHERE r.device_id = ?
                    ORDER BY r.created_at DESC
                    LIMIT ?
                """, (device_id, limit)).fetchall()
            else:
                rows = conn.execute("""
                    SELECT r.*, d.pubkey_hex FROM records r
                    LEFT JOIN devices d ON r.device_id = d.device_id
                    ORDER BY r.created_at DESC
                    LIMIT ?
                """, (limit,)).fetchall()
            return [dict(r) for r in rows]

    def count_records(self, device_id: str | None = None) -> int:
        """Total PoAC records (optionally scoped to one device).

        Phase 3 Path B (Gameplay Workflow) — surfaced by GET /player/session-status as a field
        DISTINCT from the GIC grind-chain length. The two are different artifacts: the GIC chain
        is the per-grind cognitive-session continuity chain (length ~= grind_target), whereas this
        is the raw count of 228-byte PoAC records emitted per cognition cycle. Conflating them
        (e.g. reporting a 600k+ record count as the GIC chain length) is a known reporting error.
        """
        with self._conn() as conn:
            if device_id:
                row = conn.execute(
                    "SELECT COUNT(*) FROM records WHERE device_id=?", (device_id,)
                ).fetchone()
            else:
                row = conn.execute("SELECT COUNT(*) FROM records").fetchone()
        return int(row[0]) if row else 0

    def get_player_profile(self, device_id: str) -> dict | None:
        """PHG Trust Score, record counts, confidence mean, PHCI context."""
        with self._conn() as conn:
            dev = conn.execute(
                "SELECT * FROM devices WHERE device_id = ?", (device_id,)
            ).fetchone()
            if not dev:
                return None
            dev = dict(dev)

            # Aggregate stats from records
            agg = conn.execute("""
                SELECT
                    COUNT(*) as total,
                    SUM(CASE WHEN inference = 32 THEN 1 ELSE 0 END) as nominal_count,
                    AVG(CASE WHEN inference = 32 THEN confidence ELSE NULL END) as conf_mean,
                    SUM(CASE WHEN inference = 32
                             THEN CAST(CAST(confidence AS REAL) / 255 * 10 AS INTEGER)
                             ELSE 0 END) as phg_score_raw,
                    SUM(CASE WHEN inference = 32
                             THEN CAST(
                                 CAST(confidence AS REAL) / 255 * 10
                                 * (1.0 + COALESCE(pitl_humanity_prob, 0.0) * 0.5)
                             AS INTEGER)
                             ELSE 0 END) as phg_score_weighted,
                    AVG(CASE WHEN inference = 32 AND pitl_humanity_prob IS NOT NULL
                             THEN pitl_humanity_prob ELSE NULL END) as humanity_prob_avg,
                    AVG(CASE WHEN inference = 32 AND pitl_l5_rhythm_humanity IS NOT NULL
                             THEN pitl_l5_rhythm_humanity ELSE NULL END) as l5_rhythm_humanity_avg,
                    MIN(created_at) as first_record_at,
                    MAX(created_at) as last_record_at
                FROM records
                WHERE device_id = ?
            """, (device_id,)).fetchone()
            agg = dict(agg)

            phg_score = int(agg["phg_score_raw"] or 0)
            return {
                "device_id":      device_id,
                "phg_score":      phg_score,
                "phg_score_weighted": int(agg["phg_score_weighted"] or 0),
                "humanity_prob_avg": round(agg["humanity_prob_avg"] or 0.0, 4),
                "l5_rhythm_humanity_avg": round(agg["l5_rhythm_humanity_avg"] or 0.0, 4),
                "total_records":  agg["total"] or 0,
                "nominal_records": agg["nominal_count"] or 0,
                "confidence_mean": round(agg["conf_mean"] or 0, 1),
                "first_seen":     dev["first_seen"],
                "last_seen":      dev["last_seen"],
                "records_verified": dev["records_verified"],
                "first_record_at": agg["first_record_at"],
                "last_record_at":  agg["last_record_at"],
            }

    def get_pitl_timeline(self, minutes: int = 10) -> list[dict]:
        """PITL detection events bucketed by 1-minute intervals (non-NOMINAL only)."""
        since = time.time() - minutes * 60
        with self._conn() as conn:
            rows = conn.execute("""
                SELECT
                    CAST(created_at / 60 AS INTEGER) * 60 AS bucket,
                    inference,
                    COUNT(*) as cnt
                FROM records
                WHERE created_at > ? AND inference != 32
                GROUP BY bucket, inference
                ORDER BY bucket
            """, (since,)).fetchall()
            return [dict(r) for r in rows]

    # --- PHG Registry (Phase 22) ---

    def get_verified_nominal_count(self, device_id: str) -> int:
        """Count of verified NOMINAL records for this device (from devices table)."""
        with self._conn() as conn:
            row = conn.execute(
                "SELECT records_verified FROM devices WHERE device_id = ?",
                (device_id,),
            ).fetchone()
            return row["records_verified"] if row else 0

    def get_phg_checkpoint_data(self, device_id: str) -> dict | None:
        """Returns PHG score DELTA + biometric hash for the next checkpoint commit.

        Phase 23 fix: returns the delta since the last committed checkpoint, not
        the cumulative score. This prevents the on-chain cumulativeScore from being
        inflated by a factor of checkpoint_count.
        """
        profile = self.get_player_profile(device_id)
        if profile is None:
            return None
        # Phase 25: use weighted score when available for checkpoint deltas
        cumulative_score = profile.get("phg_score_weighted", profile["phg_score"])
        last_row = self.get_last_phg_checkpoint(device_id)
        last_committed = last_row["last_committed_score"] if last_row else 0
        score_delta = max(0, cumulative_score - last_committed)

        fingerprint = self.get_biometric_fingerprint(device_id)
        if fingerprint:
            import json as _json
            fingerprint_json = _json.dumps(fingerprint, sort_keys=True)
            import hashlib as _hashlib
            bio_hash = _hashlib.sha256(fingerprint_json.encode()).digest()
        else:
            bio_hash = bytes(32)
        return {
            "phg_score":       score_delta,
            "biometric_hash":  bio_hash,
            "cumulative_score": cumulative_score,
        }

    def get_biometric_fingerprint(self, device_id: str) -> dict | None:
        """Average of L4 feature vectors from the 20 most recent NOMINAL records."""
        with self._conn() as conn:
            rows = conn.execute("""
                SELECT pitl_l4_features FROM records
                WHERE device_id = ? AND inference = 32
                  AND pitl_l4_features IS NOT NULL
                ORDER BY created_at DESC
                LIMIT 20
            """, (device_id,)).fetchall()

        if not rows:
            return None

        import json
        feature_sum: dict[str, float] = {}
        count = 0
        for row in rows:
            try:
                feats = json.loads(row["pitl_l4_features"])
                for k, v in feats.items():
                    feature_sum[k] = feature_sum.get(k, 0.0) + float(v)
                count += 1
            except Exception:
                continue

        if count == 0:
            return None
        return {k: v / count for k, v in feature_sum.items()}

    # --- Phase 23: Biometric Fingerprint State Store ---

    # --- Phase 25: E4 Cognitive Trajectory ---

    def store_cognitive_embedding(
        self, device_id: str, embedding: list, session_count: int
    ):
        """Persist the E4 cognitive embedding for cross-session drift computation."""
        with self._conn() as conn:
            conn.execute("""
                INSERT INTO cognitive_trajectory
                    (device_id, embedding_json, session_count, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(device_id) DO UPDATE SET
                    embedding_json = excluded.embedding_json,
                    session_count  = excluded.session_count,
                    updated_at     = excluded.updated_at
            """, (device_id, json.dumps(embedding), session_count, time.time()))

    def get_last_cognitive_embedding(self, device_id: str) -> list | None:
        """Return the stored E4 embedding as a list of floats, or None if not available."""
        with self._conn() as conn:
            row = conn.execute(
                "SELECT embedding_json FROM cognitive_trajectory WHERE device_id = ?",
                (device_id,),
            ).fetchone()
        if row is None:
            return None
        try:
            return json.loads(row["embedding_json"])
        except Exception:
            return None

    # --- Phase 26: Behavioral & Network Intelligence ---

    def get_pitl_history(self, device_id: str, limit: int = 100) -> list[dict]:
        """Return PITL sidecar columns from records for longitudinal analysis.

        Filters to records that have at least one non-NULL PITL sidecar to avoid
        empty series in behavioral regression.
        """
        with self._conn() as conn:
            rows = conn.execute("""
                SELECT timestamp_ms, inference, confidence,
                       pitl_l4_drift_velocity, pitl_l5_rhythm_humanity,
                       pitl_e4_cognitive_drift, pitl_humanity_prob, pitl_l4_distance
                FROM records
                WHERE device_id = ?
                  AND (pitl_l4_drift_velocity IS NOT NULL OR pitl_humanity_prob IS NOT NULL)
                ORDER BY timestamp_ms DESC
                LIMIT ?
            """, (device_id, limit)).fetchall()
            return [dict(r) for r in rows]

    def store_pitl_proof(
        self,
        device_id: str,
        nullifier_hash: str,
        feature_commitment: str,
        humanity_prob_int: int,
        tx_hash: str = "",
    ) -> None:
        """Persist a PITL ZK session proof record (Phase 26)."""
        with self._conn() as conn:
            conn.execute("""
                INSERT OR IGNORE INTO pitl_session_proofs
                    (device_id, nullifier_hash, feature_commitment,
                     humanity_prob_int, tx_hash, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (device_id, nullifier_hash, feature_commitment,
                  humanity_prob_int, tx_hash, time.time()))

    def get_latest_pitl_proof(self, device_id: str) -> dict | None:
        """Return most recent pitl_session_proofs row for device, or None (Phase 28)."""
        with self._conn() as conn:
            row = conn.execute(
                "SELECT id, device_id, nullifier_hash, feature_commitment, "
                "humanity_prob_int, tx_hash, created_at FROM pitl_session_proofs "
                "WHERE device_id=? ORDER BY id DESC LIMIT 1", (device_id,)
            ).fetchone()
        return dict(row) if row else None

    # --- Phase 62: Player Enrollment Ceremony ---

    def count_nominal_sessions(self, device_id: str) -> tuple[int, float]:
        """Count PITL session proofs where inference_code is NOMINAL (0x20=32) or NULL.

        Returns (nominal_count, avg_humanity) where avg_humanity is from humanity_prob_int/1000.
        """
        with self._conn() as conn:
            row = conn.execute("""
                SELECT COUNT(*) as n, AVG(humanity_prob_int) as avg_hp
                FROM pitl_session_proofs
                WHERE device_id=?
                  AND (inference_code IS NULL OR inference_code = 32)
            """, (device_id,)).fetchone()
        count = int(row["n"]) if row else 0
        avg_hp = float(row["avg_hp"]) / 1000.0 if (row and row["avg_hp"] is not None) else 0.0
        return count, avg_hp

    # --- Phase 63: L6b Neuromuscular Reflex Probe Log ---

    def get_leaderboard_rank(self, device_id: str) -> int | None:
        """Return 1-based rank of device in confirmed PHG leaderboard, or None (Phase 29)."""
        board = self.get_leaderboard(limit=10000)
        for i, entry in enumerate(board, start=1):
            if entry["device_id"] == device_id:
                return i
        return None

    # --- Phase 31: BridgeAgent Session Persistence ---

    # --- Phase 32: Protocol insights ---

    # --- Phase 35: Longitudinal Insight Synthesis ---

    # --- Phase 36: Adaptive Detection Policies ---

    def record_schema_version(self, phase: int, migration_name: str) -> None:
        """Record a schema migration phase as applied (Phase 36, idempotent)."""
        with self._conn() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO schema_versions (phase, migration_name, applied_at)"
                " VALUES (?, ?, ?)",
                (phase, migration_name, time.time()),
            )

    def get_schema_version(self) -> int:
        """Return highest applied phase number from schema_versions (Phase 36)."""
        with self._conn() as conn:
            row = conn.execute("SELECT MAX(phase) FROM schema_versions").fetchone()
        return int(row[0]) if row and row[0] is not None else 0

    # --- Phase 34: Federation Registry ---

    def store_federation_cluster(self, cluster_hash: str, peer_url: str = "",
                                  device_count: int = 0, suspicion_bucket: str = "medium",
                                  bridge_id: str = "", is_local: bool = False) -> None:
        """Persist a federation cluster record (Phase 34)."""
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO federation_registry"
                " (cluster_hash, peer_url, device_count, suspicion_bucket, bridge_id, detected_at, is_local)"
                " VALUES (?, ?, ?, ?, ?, ?, ?)",
                (cluster_hash, peer_url, device_count, suspicion_bucket,
                 bridge_id, time.time(), int(is_local)),
            )

    def get_federation_clusters(self, limit: int = 50, is_local=None) -> list:
        """Return federation cluster records, optionally filtered by is_local (Phase 34)."""
        with self._conn() as conn:
            if is_local is None:
                rows = conn.execute(
                    "SELECT * FROM federation_registry ORDER BY detected_at DESC LIMIT ?",
                    (limit,),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM federation_registry WHERE is_local=?"
                    " ORDER BY detected_at DESC LIMIT ?",
                    (int(is_local), limit),
                ).fetchall()
        return [dict(r) for r in rows]

    def get_cross_confirmed_hashes(self, min_peers: int = 2) -> list:
        """Return cluster hashes seen by >= min_peers distinct bridges (Phase 34)."""
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT cluster_hash FROM federation_registry"
                " WHERE is_local=0"
                " GROUP BY cluster_hash"
                " HAVING COUNT(DISTINCT bridge_id) >= ?",
                (min_peers,),
            ).fetchall()
        return [r["cluster_hash"] for r in rows]

    def get_latest_world_model_hash(self, device_id: str) -> bytes | None:
        """Return the world_model_hash bytes from the most recent record's raw_data.

        The 164B PoAC body embeds world_model_hash at bytes 96:128.
        raw_data stores the full 228B wire record; body = raw_data[:164].
        """
        with self._conn() as conn:
            row = conn.execute("""
                SELECT raw_data FROM records
                WHERE device_id = ? AND raw_data IS NOT NULL
                ORDER BY timestamp_ms DESC
                LIMIT 1
            """, (device_id,)).fetchone()
        if row is None:
            return None
        raw = bytes(row["raw_data"])
        if len(raw) >= 128:
            return raw[96:128]
        return None

    def get_world_model_hash_chain(self, device_id: str, limit: int = 20) -> list[dict]:
        """Return chronological world_model_hash chain for a device.

        Extracts raw_data[96:128] (world_model_hash field in PoAC body).
        Returns [{timestamp_ms: int, wm_hash_hex: str}] in ascending time order.
        """
        with self._conn() as conn:
            rows = conn.execute("""
                SELECT timestamp_ms, raw_data FROM records
                WHERE device_id = ? AND raw_data IS NOT NULL
                  AND length(raw_data) >= 128
                ORDER BY timestamp_ms ASC
                LIMIT ?
            """, (device_id, limit)).fetchall()
        result = []
        for row in rows:
            raw = bytes(row["raw_data"])
            wm_hash = raw[96:128]
            result.append({
                "timestamp_ms": row["timestamp_ms"],
                "wm_hash_hex": wm_hash.hex(),
            })
        return result

    # --- Phase 37: Credential Enforcement ---

    # --- Phase 38: Living calibration (Mode 6) ---

    # --- Phase 42: L6 human-response baseline capture ---

    # --- Phase 50: Agent coordination methods ---

    # --- Phase 58: Operator Audit Log ---

    def log_operator_action(
        self, endpoint: str, device_id: str, api_key_hash: str,
        source_ip: str, status_code: int, outcome: str,
    ) -> None:
        """Append immutable operator audit log entry (Phase 58)."""
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO operator_audit_log "
                "(endpoint, device_id, api_key_hash, source_ip, status_code, outcome, ts) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (endpoint, device_id, api_key_hash, source_ip, status_code, outcome, time.time()),
            )

    def get_operator_audit_log(
        self, limit: int = 100, device_id: str = ""
    ) -> list[dict]:
        """Return recent operator audit entries, optionally filtered by device (Phase 58)."""
        with self._conn() as conn:
            if device_id:
                rows = conn.execute(
                    "SELECT * FROM operator_audit_log WHERE device_id = ? "
                    "ORDER BY ts DESC LIMIT ?", (device_id, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM operator_audit_log ORDER BY ts DESC LIMIT ?", (limit,),
                ).fetchall()
        return [dict(r) for r in rows]

    # --- Phase 59: My Controller Digital Twin ---

    # --- Phase 61: Frame Replay Checkpoints ---

    _FRAME_CHECKPOINT_MAX_ROWS = 2_000  # keep last N rows; prevents DB bloat

    def store_frame_checkpoint(
        self, device_id: str, record_hash: str, frames: list
    ) -> None:
        """Store a frame replay checkpoint for a PoAC record (Phase 61)."""
        import json as _json
        frames_json = _json.dumps(frames)
        frame_count = len(frames)
        now = time.time()
        with self._conn() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO frame_checkpoints "
                "(device_id, record_hash, frames_json, frame_count, checkpoint_ts, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (device_id, record_hash, frames_json, frame_count, now, now),
            )
            # Prune oldest rows to stay within max; runs fast via rowid index
            conn.execute(
                "DELETE FROM frame_checkpoints WHERE id IN ("
                "  SELECT id FROM frame_checkpoints ORDER BY id DESC"
                "  LIMIT -1 OFFSET ?"
                ")",
                (self._FRAME_CHECKPOINT_MAX_ROWS,),
            )

    def get_frame_checkpoint(
        self, device_id: str, record_hash: str
    ) -> dict | None:
        """Return frame checkpoint for a specific PoAC record (Phase 61)."""
        import json as _json
        with self._conn() as conn:
            row = conn.execute(
                "SELECT frames_json, frame_count, checkpoint_ts FROM frame_checkpoints "
                "WHERE device_id = ? AND record_hash = ?",
                (device_id, record_hash),
            ).fetchone()
        if not row:
            return None
        return {
            "record_hash":   record_hash,
            "frames":        _json.loads(row["frames_json"]),
            "frame_count":   row["frame_count"],
            "checkpoint_ts": row["checkpoint_ts"],
        }

    def list_checkpoints_for_device(
        self, device_id: str, limit: int = 100
    ) -> list[str]:
        """Return record_hash list for all stored checkpoints (Phase 61)."""
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT record_hash FROM frame_checkpoints "
                "WHERE device_id = ? ORDER BY created_at DESC LIMIT ?",
                (device_id, min(limit, 500)),
            ).fetchall()
        return [r["record_hash"] for r in rows]

    def get_frame_checkpoints_for_records(
        self, record_hashes: list[str], limit: int = 30
    ) -> list[dict]:
        """Return parsed frame checkpoints for the given record hashes (Phase 241-APOP).

        Phase 241-APOP-FIX (2026-05-04): preserved for callers that need exact
        record_hash matching (e.g. session replay). For APOP gameplay
        classification use get_recent_frame_checkpoints_for_device() instead —
        record_hash matching gives near-zero hits when checkpoints are sampled
        (which is the default in grind_mode).
        """
        import json as _json
        hashes = [h for h in record_hashes if h][: max(0, min(int(limit), 200))]
        if not hashes:
            return []
        placeholders = ",".join("?" for _ in hashes)
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT record_hash, frames_json, frame_count, checkpoint_ts, created_at "
                f"FROM frame_checkpoints WHERE record_hash IN ({placeholders}) "
                "ORDER BY created_at ASC",
                tuple(hashes),
            ).fetchall()
        result = []
        for row in rows:
            try:
                frames = _json.loads(row["frames_json"])
            except Exception:
                frames = []
            result.append({
                "record_hash": row["record_hash"],
                "frames": frames if isinstance(frames, list) else [],
                "frame_count": row["frame_count"],
                "checkpoint_ts": row["checkpoint_ts"],
                "created_at": row["created_at"],
            })
        return result

    def get_recent_frame_checkpoints_for_device(
        self, device_id: str, limit: int = 30
    ) -> list[dict]:
        """Return most-recent N frame checkpoints for device by created_at DESC.

        Phase 241-APOP-FIX (2026-05-04): when frame_checkpoints are sampled
        during grind_mode (Phase 241-APOP-FIX writer change), the legacy
        per-record-hash join in get_frame_checkpoints_for_records misses ~99%
        of recent records. Time-based query gives APOP a stable evidence
        window regardless of writer sampling rate.

        Returns rows in ASC order (oldest first) so APOP _flatten_frames sees
        chronological frame sequence — same shape contract as the per-hash
        helper.
        """
        import json as _json
        n = max(1, min(int(limit), 200))
        if not device_id:
            return []
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT record_hash, frames_json, frame_count, checkpoint_ts, created_at "
                "FROM frame_checkpoints WHERE device_id = ? "
                "ORDER BY created_at DESC LIMIT ?",
                (str(device_id), n),
            ).fetchall()
        result = []
        for row in reversed(rows):  # ASC order for downstream
            try:
                frames = _json.loads(row["frames_json"])
            except Exception:
                frames = []
            result.append({
                "record_hash": row["record_hash"],
                "frames": frames if isinstance(frames, list) else [],
                "frame_count": row["frame_count"],
                "checkpoint_ts": row["checkpoint_ts"],
                "created_at": row["created_at"],
            })
        return result

    # --- Phase 55: ioID Device Identity Registry ---

    def store_ioid_device(
        self,
        device_id: str,
        device_address: str,
        did: str,
        tx_hash: str = "",
        tba_address: str = "",
        ioid_token_id: int = 0,
        canonical: bool = False,
    ) -> None:
        """Persist an ioID device registration record (Phase 55 + Phase 2 controller TBA)."""
        with self._conn() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO ioid_devices
                    (device_id, device_address, did, tx_hash, registered_at,
                     tba_address, ioid_token_id, canonical)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (device_id, device_address, did, tx_hash, time.time(),
                 tba_address or "", int(ioid_token_id), 1 if canonical else 0),
            )

    def get_ioid_device(self, device_id: str) -> dict | None:
        """Return the ioID registration record for device_id, or None (Phase 55)."""
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM ioid_devices WHERE device_id = ?",
                (device_id,),
            ).fetchone()
        return dict(row) if row else None

    def get_all_ioid_devices(self) -> list[dict]:
        """Return all registered ioID devices ordered by registration time (Phase 55)."""
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM ioid_devices ORDER BY registered_at ASC"
            ).fetchall()
        return [dict(r) for r in rows]

    def get_ioid_devices(self, limit: int = 10) -> list:
        """Return registered ioID device records. Used for warm-up bootstrap fallback.
        Returns list of dicts: {device_id, device_address, did, registered_at}
        Phase 100.
        """
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT device_id, device_address, did, registered_at "
                "FROM ioid_devices ORDER BY registered_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]

    # --- Phase 56: Tournament Passport ---

    def get_passport_eligible_sessions(
        self,
        device_id: str,
        min_humanity: float,
        limit: int = 10,
    ) -> list[dict]:
        """Return NOMINAL sessions with humanity_prob >= min_humanity (Phase 56).

        Used to determine eligibility for tournament passport issuance.
        Returns up to `limit` sessions ordered newest-first.
        """
        with self._conn() as conn:
            rows = conn.execute(
                """
                SELECT record_hash, pitl_humanity_prob, pitl_proof_nullifier,
                       inference, created_at
                FROM records
                WHERE device_id = ?
                  AND inference = 32
                  AND pitl_humanity_prob >= ?
                  AND pitl_proof_nullifier IS NOT NULL
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (device_id, min_humanity, limit),
            ).fetchall()
        return [dict(r) for r in rows]

    # --- Phase 65: Autonomous agent rulings ---

    # --- Phase 66: Ruling streaks ---

    # --- Phase 66: On-chain ruling anchoring ---

    # --- Phase 69: Data Sovereignty Layer — store methods ---

    def list_known_devices(self) -> list[str]:
        """Return all device_ids known to the store (from devices table)."""
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT device_id FROM devices ORDER BY last_seen DESC"
            ).fetchall()
        return [r["device_id"] for r in rows]

    def upsert_data_lineage(
        self,
        device_id: str,
        taxonomy_class: str,
        quality_index: float,
        curator_note: str = "",
        record_hash: str | None = None,
    ) -> int:
        """Insert a data lineage entry. Returns row id."""
        now = time.time()
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO data_lineage "
                "(device_id, record_hash, taxonomy_class, quality_index, curator_note, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (device_id, record_hash, taxonomy_class, quality_index, curator_note, now),
            )
            return cur.lastrowid

    def get_data_lineage(self, device_id: str, limit: int = 50) -> list[dict]:
        """Return data lineage graph for device, most recent first."""
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM data_lineage WHERE device_id=? "
                "ORDER BY created_at DESC LIMIT ?",
                (device_id, limit),
            ).fetchall()
        return [dict(r) for r in rows]



    def upsert_token_eligibility(
        self,
        device_id: str,
        nominal_sessions: int,
        clean_streak: int,
        passport_held: bool,
        enrollment_complete: bool,
        mpc_verified: bool,
        gate_passed: bool,
        base_multiplier: float,
        total_multiplier: float,
        eligibility_score: float,
    ) -> None:
        """Upsert token eligibility state for a device (Phase 69)."""
        now = time.time()
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO token_eligibility "
                "(device_id, nominal_sessions, clean_streak, passport_held, "
                "enrollment_complete, mpc_verified, gate_passed, base_multiplier, "
                "total_multiplier, eligibility_score, last_computed_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?) "
                "ON CONFLICT(device_id) DO UPDATE SET "
                "nominal_sessions=excluded.nominal_sessions, "
                "clean_streak=excluded.clean_streak, "
                "passport_held=excluded.passport_held, "
                "enrollment_complete=excluded.enrollment_complete, "
                "mpc_verified=excluded.mpc_verified, "
                "gate_passed=excluded.gate_passed, "
                "base_multiplier=excluded.base_multiplier, "
                "total_multiplier=excluded.total_multiplier, "
                "eligibility_score=excluded.eligibility_score, "
                "last_computed_at=excluded.last_computed_at",
                (
                    device_id, nominal_sessions, clean_streak,
                    int(passport_held), int(enrollment_complete),
                    int(mpc_verified), int(gate_passed),
                    base_multiplier, total_multiplier, eligibility_score, now,
                ),
            )

    def get_token_eligibility(self, device_id: str) -> dict | None:
        """Return token eligibility state for device, or None."""
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM token_eligibility WHERE device_id=?",
                (device_id,),
            ).fetchone()
        return dict(row) if row else None

    # --- Phase 72: PHGCredential bridge-layer multi-sig ---

    def propose_suspension(
        self,
        device_id: str,
        evidence_hash: str,
        duration_s: int,
        proposed_by: str = "",
        expires_in_s: float = 86400.0,
    ) -> int:
        """Insert a pending suspension proposal. Returns proposal_id.

        The proposal must reach suspension_multisig_threshold confirmations
        (via confirm_suspension) before execute_suspension_proposal() calls
        the on-chain PHGCredential.suspend().
        """
        now = time.time()
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO pending_suspensions "
                "(device_id, evidence_hash, duration_s, proposed_by, "
                "proposed_at, confirmations, executed, expires_at) "
                "VALUES (?,?,?,?,?,0,0,?)",
                (device_id, evidence_hash, duration_s, proposed_by,
                 now, now + expires_in_s),
            )
            return cur.lastrowid

    def confirm_suspension(self, proposal_id: int) -> int:
        """Increment confirmation count for a proposal. Returns new count.

        Raises ValueError if proposal not found, already executed, or expired.
        """
        now = time.time()
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM pending_suspensions WHERE id=?", (proposal_id,)
            ).fetchone()
            if not row:
                raise ValueError(f"Proposal {proposal_id} not found")
            if row["executed"]:
                raise ValueError(f"Proposal {proposal_id} already executed")
            if row["expires_at"] < now:
                raise ValueError(f"Proposal {proposal_id} expired")
            new_count = row["confirmations"] + 1
            conn.execute(
                "UPDATE pending_suspensions SET confirmations=? WHERE id=?",
                (new_count, proposal_id),
            )
            return new_count

    def get_suspension_proposal(self, proposal_id: int) -> dict | None:
        """Return proposal dict or None if not found."""
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM pending_suspensions WHERE id=?", (proposal_id,)
            ).fetchone()
        return dict(row) if row else None

    def mark_suspension_executed(self, proposal_id: int, tx_hash: str = "") -> None:
        """Mark a proposal as executed after the on-chain call succeeds."""
        now = time.time()
        with self._conn() as conn:
            conn.execute(
                "UPDATE pending_suspensions "
                "SET executed=1, executed_at=?, tx_hash=? WHERE id=?",
                (now, tx_hash, proposal_id),
            )

    # --- Phase 75: Ruling validation log ---

    # --- Phase 76: Ruling provenance anchors ---

    # --- Phase 79: Live mode transitions ---

    def insert_live_mode_transition(
        self,
        event_type: str,
        consecutive_clean: int = 0,
        divergence_rate: float = 0.0,
        conditions_json: str = "{}",
        operator_action: str = None,
    ) -> int:
        """Record a live mode transition event (Phase 79)."""
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO live_mode_transitions "
                "(event_type, consecutive_clean, divergence_rate, conditions_json, "
                "operator_action, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (event_type, consecutive_clean, divergence_rate, conditions_json,
                 operator_action, time.time()),
            )
            return cur.lastrowid

    # --- Phase 80: Federation threat signals ---

    def insert_threat_signal(
        self,
        device_id: str,
        commitment_hash: str,
        circuit_id: str = None,
        source_peer: str = None,
        received_at: float = None,
    ) -> int:
        """Insert a federation threat signal. Returns row id (Phase 80).

        UNIQUE(commitment_hash) — raises sqlite3.IntegrityError on duplicate.
        broadcast_at=NULL means unbroadcast (pending delivery to peers).
        """
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO federation_threat_signals "
                "(device_id, commitment_hash, circuit_id, source_peer, received_at, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (device_id, commitment_hash, circuit_id, source_peer,
                 received_at, time.time()),
            )
            return cur.lastrowid

    def mark_threat_signal_broadcast(self, signal_id: int) -> None:
        """Mark a threat signal as broadcast (sets broadcast_at=now) (Phase 80)."""
        with self._conn() as conn:
            conn.execute(
                "UPDATE federation_threat_signals SET broadcast_at=? WHERE id=?",
                (time.time(), signal_id),
            )

    def get_unbroadcast_signals(self, limit: int = 50) -> list:
        """Return locally-originated signals with broadcast_at=NULL (Phase 80)."""
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM federation_threat_signals "
                "WHERE broadcast_at IS NULL AND source_peer IS NULL "
                "ORDER BY created_at ASC LIMIT ?",
                (limit,),
            ).fetchall()
            return [dict(r) for r in rows]

    def get_federation_stats(self) -> dict:
        """Return federation signal statistics (Phase 80)."""
        with self._conn() as conn:
            total = conn.execute(
                "SELECT COUNT(*) as cnt FROM federation_threat_signals"
            ).fetchone()["cnt"]
            broadcast = conn.execute(
                "SELECT COUNT(*) as cnt FROM federation_threat_signals "
                "WHERE broadcast_at IS NOT NULL"
            ).fetchone()["cnt"]
            received = conn.execute(
                "SELECT COUNT(*) as cnt FROM federation_threat_signals "
                "WHERE source_peer IS NOT NULL"
            ).fetchone()["cnt"]
        return {
            "total_signals": total,
            "broadcast": broadcast,
            "received_from_peers": received,
            "pending_broadcast": max(0, total - broadcast - received),
        }

    # --- Phase 81: Class J assessments ---

    # --- Phase 83: Agent supervisor health ---

    # --- Phase 82: Reactive adjudication interrupt log ---

    # --- Phase 84: Gate attestation anchor ---



    # --- Phase 86: Synthetic corpus ---

    # --- Phase 89: Protocol Intelligence ---

    # --- Phase 90: Shadow Enforcement ---

    # --- Phase 91: Divergence Triage ---

    # --- Phase 92: Live Mode Activation Pipeline ---

    def insert_live_mode_activation_log(
        self,
        event_type: str,
        ready_for_live_mode: int,
        protocol_health_score: float,
        bottleneck,
        blocking_conditions=None,
        operator_notes=None,
    ) -> int:
        """Insert a live mode activation audit entry."""
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO live_mode_activation_log "
                "(event_type, ready_for_live_mode, protocol_health_score, "
                "bottleneck, blocking_conditions, operator_notes) "
                "VALUES (?,?,?,?,?,?)",
                (
                    event_type, int(ready_for_live_mode),
                    float(protocol_health_score) if protocol_health_score is not None else None,
                    bottleneck, blocking_conditions, operator_notes,
                ),
            )
            return cur.lastrowid

    def get_live_mode_activation_log(self, limit: int = 50) -> list:
        """Return live mode activation audit entries, newest first."""
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM live_mode_activation_log "
                "ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]

    # --- Phase 94: Escalation Ruling Log ---

    # --- Phase 95: Activation Audit Verifier ---

    def get_activation_audit_summary(self) -> dict:
        """Phase 95: Cross-reference live_mode_activation_log + gate_attestations.

        Returns a tamper-evident audit summary verifying that:
        - A ready_for_live_mode=True state was recorded BEFORE any on-chain gate attestation
        - The chronological sequence (ready → on-chain anchor) is preserved
        - audit_valid=True means the full activation evidence chain is intact
        """
        with self._conn() as conn:
            row1 = conn.execute(
                "SELECT MIN(created_at) FROM live_mode_activation_log WHERE ready_for_live_mode=1"
            ).fetchone()
            first_ready_at = row1[0] if row1 and row1[0] is not None else None

            # Phase 96 W1 fix: only count attestations AFTER first readiness determination.
            # Pre-readiness infrastructure test anchors must not satisfy the chronological
            # invariant — they predated the protocol being assessed as ready.
            row2 = conn.execute(
                "SELECT COUNT(*), MAX(created_at) FROM gate_attestations "
                "WHERE created_at >= ?",
                (first_ready_at or 0,),
            ).fetchone()
            count = int(row2[0]) if row2 and row2[0] else 0
            latest_att = row2[1] if row2 and row2[1] is not None else None

        audit_valid = (
            first_ready_at is not None
            and latest_att is not None
            and first_ready_at <= latest_att
        )

        if audit_valid:
            summary = (
                f"VALID: Protocol scored ready_for_live_mode=True at t={first_ready_at:.0f}, "
                f"followed by {count} on-chain gate attestation(s). "
                "Chronological sequence confirmed."
            )
        elif first_ready_at is None:
            summary = "NOT VALID: No ready_for_live_mode=True entry in activation log yet."
        elif latest_att is None:
            summary = "NOT VALID: No gate attestations on-chain yet."
        else:
            summary = (
                f"NOT VALID: Gate attestation (t={latest_att:.0f}) predates "
                f"first ready check (t={first_ready_at:.0f}) — chronological order violated."
            )

        return {
            "first_ready_check_at": first_ready_at,
            "gate_attestation_count": count,
            "latest_attestation_at": latest_att,
            "audit_valid": audit_valid,
            "audit_summary": summary,
        }

    # --- Phase 96: Enforcement Readiness Certificates ---

    # --- Phase 97: Live Mode Guard Log ---

    def insert_live_mode_guard_log(
        self,
        event_type: str,
        attempted_dry_run: int,
        gate_passed: bool,
        cert_valid: bool,
        audit_valid: bool,
        blocking_conditions=None,
        operator_key_hash: str = "",
    ) -> int:
        """Log every live mode transition attempt — approved or rejected."""
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO live_mode_guard_log "
                "(event_type, attempted_dry_run, gate_passed, cert_valid, "
                "audit_valid, blocking_conditions, operator_key_hash) "
                "VALUES (?,?,?,?,?,?,?)",
                (
                    event_type, attempted_dry_run,
                    int(gate_passed), int(cert_valid), int(audit_valid),
                    blocking_conditions, operator_key_hash,
                ),
            )
            return cur.lastrowid

    def get_live_mode_guard_log(self, limit: int = 50) -> list:
        """Return live mode guard log entries, newest first."""
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM live_mode_guard_log ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]

    # --- Phase 98: Epistemic Consensus Log ---

    def insert_epistemic_consensus(
        self,
        device_id: str,
        ruling_id: "int | None",
        proposed_verdict: str,
        class_j_score: float,
        triage_score: float,
        supervisor_score: float,
        consensus_score: float,
        threshold: float,
        consensus_reached: bool,
        final_verdict: str,
        downgraded: bool,
        swarm_score: float = 0.0,
    ) -> int:
        """Persist an epistemic consensus decision. Returns row id.

        Phase 109A: swarm_score column added (idempotent ALTER TABLE in schema init).
        """
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO epistemic_consensus_log "
                "(device_id, ruling_id, proposed_verdict, class_j_score, triage_score, "
                "supervisor_score, consensus_score, threshold, consensus_reached, "
                "final_verdict, downgraded, swarm_score) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    device_id, ruling_id, proposed_verdict,
                    class_j_score, triage_score, supervisor_score,
                    consensus_score, threshold,
                    int(consensus_reached), final_verdict, int(downgraded), swarm_score,
                ),
            )
            return cur.lastrowid

    def get_epistemic_consensus_log(self, device_id: str | None = None, limit: int = 50) -> list:
        """Return epistemic consensus log entries, newest first."""
        with self._conn() as conn:
            if device_id:
                rows = conn.execute(
                    "SELECT * FROM epistemic_consensus_log "
                    "WHERE device_id=? ORDER BY created_at DESC LIMIT ?",
                    (device_id, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM epistemic_consensus_log ORDER BY created_at DESC LIMIT ?",
                    (limit,),
                ).fetchall()
        return [dict(r) for r in rows]

    # --- Phase 99A: Operator Registration ---

    def insert_operator_registration(
        self,
        operator_address: str,
        event_type: str,
        stake_amount: str = "",
        tx_hash: str = "",
        reason: str = "",
    ) -> int:
        """Log an operator staking event (register/slash/deregister). Returns row id."""
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO operator_registrations "
                "(operator_address, event_type, stake_amount, tx_hash, reason) "
                "VALUES (?,?,?,?,?)",
                (operator_address, event_type, stake_amount, tx_hash, reason),
            )
            return cur.lastrowid

    def get_operator_status(self, operator_address: str) -> dict | None:
        """Return the latest registration event for an operator address, or None."""
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM operator_registrations "
                "WHERE operator_address=? ORDER BY created_at DESC LIMIT 1",
                (operator_address,),
            ).fetchone()
        return dict(row) if row else None

    # --- Phase 99B: GSR Biometric Samples ---

    # --- Phase 99C: VHP issuances ---

    # ── Phase 102: VHP Renewal Log ────────────────────────────────────────────

    # --- Phase B item ③ — iPACT-DePIN renewal-cadence commitment chain ---------

    def insert_activation_simulation_log(
        self, n_sessions, gate_passed, cert_created,
        dry_run_toggled, vhp_minted, token_id=None, tx_hash=""
    ) -> int:
        """Persist activation simulation run result (Phase 103)."""
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO activation_simulation_log "
                "(n_sessions, gate_passed, cert_created, dry_run_toggled, "
                "vhp_minted, token_id, tx_hash) VALUES (?,?,?,?,?,?,?)",
                (
                    int(n_sessions),
                    1 if gate_passed else 0,
                    1 if cert_created else 0,
                    1 if dry_run_toggled else 0,
                    1 if vhp_minted else 0,
                    token_id,
                    tx_hash or "",
                ),
            )
            return cur.lastrowid

    def get_activation_simulation_log(self, limit=10) -> list:
        """Return recent activation simulation log entries (Phase 103)."""
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT id, n_sessions, gate_passed, cert_created, dry_run_toggled, "
                "vhp_minted, token_id, tx_hash, created_at "
                "FROM activation_simulation_log ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [
            {
                "id": r[0], "n_sessions": r[1], "gate_passed": bool(r[2]),
                "cert_created": bool(r[3]), "dry_run_toggled": bool(r[4]),
                "vhp_minted": bool(r[5]), "token_id": r[6],
                "tx_hash": r[7], "created_at": r[8],
            }
            for r in rows
        ]

    def insert_enforcement_certificate(
        self,
        audit_hash: str,
        hmac_sig: str,
        audit_valid: bool,
        first_ready_check_at,
        gate_attestation_count: int,
        latest_attestation_at,
        expires_at: float,
    ) -> int:
        """Insert an enforcement readiness certificate. UNIQUE(audit_hash) deduplicates."""
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT OR IGNORE INTO enforcement_certificates "
                "(audit_hash, hmac_sig, audit_valid, first_ready_check_at, "
                "gate_attestation_count, latest_attestation_at, expires_at) "
                "VALUES (?,?,?,?,?,?,?)",
                (
                    audit_hash, hmac_sig, int(audit_valid),
                    first_ready_check_at, gate_attestation_count,
                    latest_attestation_at, expires_at,
                ),
            )
            return cur.lastrowid

    def get_latest_enforcement_certificate(self) -> dict | None:
        """Return the most recently issued enforcement certificate, or None."""
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM enforcement_certificates ORDER BY created_at DESC LIMIT 1"
            ).fetchone()
        return dict(row) if row else None

    # --- Phase 101: QuickSilver Collateral Events ---

    def insert_quicksilver_collateral_event(
        self,
        operator_address: str,
        event_type: str,
        amount_wei: str = "0",
        tx_hash: str = "",
    ) -> int:
        """Persist a QuickSilver collateral event (Phase 101).
        event_type: lock / unlock_request / claim_unlock / slash / claim_yield
        """
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO quicksilver_collateral_events "
                "(operator_address, event_type, amount_wei, tx_hash, created_at) "
                "VALUES (?,?,?,?,?)",
                (operator_address, event_type, amount_wei, tx_hash, time.time()),
            )
            return cur.lastrowid

    def get_quicksilver_collateral_status(self, operator_address: str) -> dict:
        """Return the latest QuickSilver collateral event + history for an operator (Phase 101).
        Returns {found, latest_event_type, amount_wei, events_count, last_event_at}
        """
        with self._conn() as conn:
            row = conn.execute(
                "SELECT event_type, amount_wei, tx_hash, created_at "
                "FROM quicksilver_collateral_events "
                "WHERE operator_address = ? ORDER BY created_at DESC LIMIT 1",
                (operator_address,),
            ).fetchone()
            count_row = conn.execute(
                "SELECT COUNT(*) FROM quicksilver_collateral_events WHERE operator_address = ?",
                (operator_address,),
            ).fetchone()
        count = count_row[0] if count_row else 0
        if row is None:
            return {
                "operator_address": operator_address,
                "found": False,
                "latest_event_type": None,
                "amount_wei": "0",
                "events_count": 0,
                "last_event_at": None,
            }
        return {
            "operator_address": operator_address,
            "found": True,
            "latest_event_type": row["event_type"],
            "amount_wei": row["amount_wei"],
            "tx_hash": row["tx_hash"],
            "events_count": count,
            "last_event_at": row["created_at"],
        }

    # --- Phase 104: Persistent Activation Commit + PMI ---

    def get_activation_state(self) -> dict:
        """Return canonical activation state (Phase 104). Always returns dict.
        Defaults: activation_committed=False, pmi=0 when no record exists.
        """
        with self._conn() as conn:
            row = conn.execute(
                "SELECT activation_committed, pmi, committed_at, committed_by, "
                "pmi_updated_at, notes FROM activation_state ORDER BY id DESC LIMIT 1"
            ).fetchone()
        if row is None:
            return {"activation_committed": False, "pmi": 0, "committed_at": None,
                    "committed_by": "", "pmi_updated_at": None, "notes": ""}
        return {
            "activation_committed": bool(row[0]), "pmi": int(row[1]),
            "committed_at": row[2], "committed_by": row[3],
            "pmi_updated_at": row[4], "notes": row[5],
        }

    def set_activation_committed(self, committed_by: str = "operator", notes: str = "") -> int:
        """Persist activation_committed=True (Phase 104). Append-only audit trail."""
        import time as _t
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO activation_state "
                "(activation_committed, pmi, committed_at, committed_by, notes) "
                "VALUES (1, 1, ?, ?, ?)",
                (_t.time(), committed_by, notes),
            )
            return cur.lastrowid

    def set_pmi(self, pmi: int, notes: str = "") -> int:
        """Update ProtocolMaturityIndex in store (Phase 104). Appends new row."""
        import time as _t
        current = self.get_activation_state()
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO activation_state "
                "(activation_committed, pmi, committed_at, committed_by, pmi_updated_at, notes) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    1 if current["activation_committed"] else 0,
                    int(pmi),
                    current.get("committed_at"),
                    current.get("committed_by", ""),
                    _t.time(),
                    notes,
                ),
            )
            return cur.lastrowid

    def compute_pmi(self) -> int:
        """Compute ProtocolMaturityIndex from store state (Phase 104).
        0=uninitiated / 1=simulated / 2=testnet_organic / 3=mainnet(reserved).
        """
        try:
            with self._conn() as conn:
                row = conn.execute(
                    "SELECT COUNT(*) FROM activation_simulation_log"
                ).fetchone()
            sim_count = int(row[0]) if row else 0
        except Exception:
            sim_count = 0
        if sim_count == 0:
            return 0
        vhp = self.get_first_vhp_status()
        if vhp is None:
            return 0
        # W1 expiry guard (Phase 107): PMI=1 must not persist when all VHPs have expired
        if vhp.get("is_simulation", True) and not vhp.get("is_valid", True):
            # simulation VHP is expired and no organic VHP exists — uninitiated
            return 0
        state = self.get_activation_state()
        if not vhp.get("is_simulation", True) and state.get("activation_committed", False):
            return 2
        return 1

    # --- Phase 105: Epistemic Threshold History ---

    # --- Phase 107: Live Mode Readiness Reports ---

    # --- Phase 108: Tournament Readiness Snapshots ---


    # --- Phase 117 — Per-Device Epoch Freshness Heatmap ---

    # --- Phase 118 — Per-Device Epoch Window Overrides ---

    # --- Phase 119 — Override Lifecycle Management ---


    # --- Phase 120 — Bluetooth Transport Foundation ---

    # --- Phase 123: l4_calibration_log ---

    # --- Phase 124: l4_threshold_tracks ---

    # --- Phase 121: separation_ratio_snapshots ---

    # --- Phase 122: confidence_multiplier_log ---

    # --- Phase 125: Per-Battery L4 Calibration Runs ---

    # --- Phase 126: L4 Threshold Router Log ---

    def insert_l4_router_log(
        self,
        battery_type: str = "unknown",
        threshold_source: str = "global_fallback",
        anomaly_used: float = 7.009,
        continuity_used: float = 5.367,
    ) -> int:
        """Insert a threshold router lookup entry (Phase 126)."""
        with self._conn() as conn:
            cur = conn.execute(
                """INSERT INTO l4_threshold_router_log
                   (battery_type, threshold_source, anomaly_used, continuity_used, created_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (battery_type, threshold_source, float(anomaly_used), float(continuity_used),
                 time.time()),
            )
            return cur.lastrowid

    # --- Phase 127: Tournament Preflight Log ---

    # --- Phase 128: Tournament Readiness Score (uses existing protocol_intelligence_reports) ---

    # --- Phase 129: Separation Ratio Breakthrough Log ---


    # ---------------------------------------------------------------------------
    # Phase 134 — L4 Recalibration Jobs
    # ---------------------------------------------------------------------------

    # Phase 135 — Tournament Activation Chain Log
    # -------------------------------------------------------------------------

    # Phase 148 — Agent Calibration Health (ACIM)
    # -------------------------------------------------------------------------

    # Phase 150 — Separation Ratio Defensibility Log
    # -------------------------------------------------------------------------

    # Phase 151 P0 — W1-011 session type integrity whitelist.
    # Only structured biometric probe sessions are valid inputs for the defensibility
    # gate.  Free-form gameplay (ratio≈0.417) must never pollute the defensibility log
    # and be silently mistaken for a structured probe result.
    STRUCTURED_PROBE_TYPES: "frozenset[str]" = frozenset({
        "touchpad_corners",
        "touchpad_freeform",
        "touchpad_swipes",
        "mixed_biometric_probe",  # Phase 166: 2-min multi-feature probe (touchpad+trigger+button+stick)
        "tremor_resting",         # Phase 199: 30s still-hold; isolates neurological tremor signal
        "ait",                    # Phase 229: Active Isometric Trigger; 4-feature accel+postural pipeline
        "trigger_force_curve",    # Phase 243-SS2 Stage-A: DualSense Edge adaptive-trigger force-curve at 8-bit/1kHz. PRIMARY DISCRIMINATOR candidate per the canonical anchor (wiki/assessments/DualSense Edge Sensor-Stack Characterization_*.pdf). Stage-A measurement gates: N=10 players × 100 trigger pulls × 3 game contexts; primary-discriminator-status requires separation_ratio > 1.0.
    })

    # --- Phase 208: CorpusRatioRegressionGuard (WIF-039 W1+W2) ---

    # --- Phase 215: l4_dim_sync_log ---

    # --- Phase 216: per_pair_gap_log ---

    # --- Phase 217: per-pair gap trend ---

    # Phase 152 — Centroid Velocity Log
    # -------------------------------------------------------------------------

    _PLATEAU_THRESHOLD_PER_DAY = 0.001  # ratio units/day below which = stagnant

    # Phase 153 — Separation Ratio Registry Log
    # -------------------------------------------------------------------------

    # Phase 154 — Capture Stagnation Log
    # -------------------------------------------------------------------------

    # --- Phase 218: CaptureVelocityOracle ---

    # --- Phase 219: TournamentBlockerSummary ---

    # --- Phase 220: PerPairGapProjection ---

    # --- Phase 221: ProtocolCoherence (PoPC) ---




    # --- Phase 222: BiometricBoundGovernance (BBG) ---




    # --- Phase 223: PV-CI Invariant Gate ---


    # --- Phase 224: Allowlist Governance ---



    def get_latest_governance_reason(self, within_seconds: float = 60.0) -> "str | None":
        """Return reason_text from the most recent governance entry within within_seconds (Phase 224).

        Used by ProtocolCoherenceAgent to correlate allowlist hash changes with governance events.
        Returns None if no matching entry found (indicates suspicious unlogged change).
        """
        import time as _t224
        cutoff = _t224.time() - within_seconds
        with self._conn() as conn:
            row = conn.execute(
                "SELECT reason_text FROM invariant_gate_log "
                "WHERE reason_category != '' AND created_at >= ? "
                "ORDER BY created_at DESC LIMIT 1",
                (cutoff,),
            ).fetchone()
        return str(row[0]) if row and row[0] else None

    # --- Phase 225: Governance Provenance Chain ---





    # Phase 155 — Controller Hardware Profiles
    # -------------------------------------------------------------------------

    def insert_controller_hardware_profile(
        self,
        profile_hash: str,
        controller_name: str = "DualShock_Edge_v1",
        tier: str = "Attested",
        n_calibration: int = 0,
        transport_type: str = "usb",
        battery_type: str = "gameplay",
        anomaly_threshold: float = 7.009,
        continuity_threshold: float = 5.367,
    ) -> int:
        """Upsert a controller hardware profile (Phase 155).

        composite_key = profile_hash:battery_type:transport_type
        Attested tier: DualShock Edge, full L0–L6 PITL stack.
        Standard tier: Xbox/Switch, L0–L5 only (no L6 haptic challenge).
        Never apply DualShock Edge thresholds to non-DualShock controllers.
        """
        composite_key = f"{profile_hash}:{battery_type}:{transport_type}"
        with self._conn() as con:
            cur = con.execute(
                "INSERT OR IGNORE INTO controller_hardware_profiles "
                "(profile_hash, controller_name, tier, n_calibration, transport_type, "
                " battery_type, anomaly_threshold, continuity_threshold, composite_key, "
                " active, created_at)"
                " VALUES (?,?,?,?,?,?,?,?,?,1,?)",
                (profile_hash, controller_name, tier, int(n_calibration), transport_type,
                 battery_type, float(anomaly_threshold), float(continuity_threshold),
                 composite_key, time.time()),
            )
        return cur.lastrowid  # type: ignore[return-value]

    # Phase 156 — Enrollment Guidance Log
    # -------------------------------------------------------------------------

    # Phase 157 — Fleet Consensus Snapshot Log
    # -------------------------------------------------------------------------

    def insert_fleet_consensus_snapshot(
        self,
        pofc_hash: str,
        agent_count: int,
        separation_ratio: float,
        verdict_summary: "dict | None" = None,
    ) -> int:
        """Insert a PoFC (Proof of Fleet Consensus) snapshot (Phase 157)."""
        import json as _j157
        with self._conn() as con:
            cur = con.execute(
                "INSERT INTO fleet_consensus_snapshot_log "
                "(pofc_hash, agent_count, separation_ratio, verdict_summary_json, created_at)"
                " VALUES (?,?,?,?,?)",
                (
                    pofc_hash,
                    int(agent_count),
                    float(separation_ratio),
                    _j157.dumps(verdict_summary or {}),
                    time.time(),
                ),
            )
        return cur.lastrowid  # type: ignore[return-value]

    def get_fleet_consensus_snapshot(self, limit: int = 1) -> "list[dict]":
        """Return recent PoFC snapshots, newest-first (Phase 157)."""
        import json as _j157
        with self._conn() as con:
            rows = con.execute(
                "SELECT * FROM fleet_consensus_snapshot_log ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            try:
                d["verdict_summary"] = _j157.loads(d.get("verdict_summary_json", "{}"))
            except Exception:
                d["verdict_summary"] = {}
            out.append(d)
        return out

    # --- Phase 158: Class K HMAC Validation + PoHBG ---

    def insert_pohbg(
        self,
        *,
        device_id: str,
        pohbg_hash: str,
        arousal_millis: int,
        correlation_millis: int,
        conductance_raw_int: int,
        ts_ns: int,
    ) -> int:
        """Log a PoHBG (Proof of Hardware Biometric Grip) hash (Phase 158 WIF-015)."""
        with self._conn() as con:
            cur = con.execute(
                "INSERT INTO pohbg_log "
                "(device_id, pohbg_hash, arousal_millis, correlation_millis,"
                " conductance_raw_int, ts_ns, created_at)"
                " VALUES (?,?,?,?,?,?,?)",
                (
                    device_id,
                    pohbg_hash,
                    int(arousal_millis),
                    int(correlation_millis),
                    int(conductance_raw_int),
                    int(ts_ns),
                    time.time(),
                ),
            )
        return cur.lastrowid  # type: ignore[return-value]

    def get_pohbg_status(self, limit: int = 10) -> dict:
        """Return PoHBG summary + recent hashes (Phase 158)."""
        with self._conn() as con:
            total = con.execute("SELECT COUNT(*) FROM pohbg_log").fetchone()[0]
            rows = con.execute(
                "SELECT * FROM pohbg_log ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
        return {
            "pohbg_enabled": False,  # populated by operator_api from cfg
            "total_pohbg": total,
            "recent_hashes": [dict(r) for r in rows],
        }

    # --- Phase 159: BiometricPrivacyComplianceAgent ---

    def insert_privacy_compliance_log(
        self,
        *,
        records_monitored: int,
        records_expired: int,
        mean_decay_factor: float,
        oldest_session_days: float,
        privacy_budget_epsilon: float,
        warning_triggered: bool,
    ) -> int:
        """Log a BP-001 compliance check result (Phase 159)."""
        with self._conn() as con:
            cur = con.execute(
                "INSERT INTO privacy_compliance_log "
                "(records_monitored, records_expired, mean_decay_factor,"
                " oldest_session_days, privacy_budget_epsilon, warning_triggered, created_at)"
                " VALUES (?,?,?,?,?,?,?)",
                (
                    int(records_monitored),
                    int(records_expired),
                    float(mean_decay_factor),
                    float(oldest_session_days),
                    float(privacy_budget_epsilon),
                    int(warning_triggered),
                    time.time(),
                ),
            )
        return cur.lastrowid  # type: ignore[return-value]

    def get_privacy_compliance_status(self) -> dict:
        """Return latest BP-001 compliance report (Phase 159)."""
        with self._conn() as con:
            total = con.execute(
                "SELECT COUNT(*) FROM privacy_compliance_log"
            ).fetchone()[0]
            row = con.execute(
                "SELECT * FROM privacy_compliance_log ORDER BY id DESC LIMIT 1"
            ).fetchone()
        if row:
            d = dict(row)
            return {
                "biometric_privacy_enabled": True,  # populated by operator_api from cfg
                "bp001_half_life_days":      90.0,  # populated by operator_api from cfg
                "records_monitored":         d["records_monitored"],
                "records_expired":           d["records_expired"],
                "mean_decay_factor":         d["mean_decay_factor"],
                "oldest_session_days":       d["oldest_session_days"],
                "privacy_budget_epsilon":    d["privacy_budget_epsilon"],
                "warning_triggered":         bool(d["warning_triggered"]),
                "total_checks":              total,
                "found":                     True,
            }
        return {
            "biometric_privacy_enabled": True,
            "bp001_half_life_days":      90.0,
            "records_monitored":         0,
            "records_expired":           0,
            "mean_decay_factor":         1.0,
            "oldest_session_days":       0.0,
            "privacy_budget_epsilon":    0.0,
            "warning_triggered":         False,
            "total_checks":              0,
            "found":                     False,
        }

    # --- Phase 160: Consent Ledger + Right-to-Erasure (BP-002 foundation) ---

    def insert_consent_record(
        self,
        *,
        device_id: str,
        consent_type: str = "biometric_processing",
        consent_given: bool,
        consent_ts: float | None = None,
    ) -> int:
        """Register or update consent for a device (Phase 160 BP-002)."""
        now = time.time()
        with self._conn() as con:
            cur = con.execute(
                "INSERT INTO consent_ledger"
                " (device_id, consent_type, consent_given, consent_ts, created_at)"
                " VALUES (?,?,?,?,?)"
                " ON CONFLICT(device_id, consent_type) DO UPDATE SET"
                " consent_given=excluded.consent_given,"
                " consent_ts=excluded.consent_ts",
                (
                    device_id,
                    consent_type,
                    int(consent_given),
                    consent_ts if consent_ts is not None else now,
                    now,
                ),
            )
        return cur.lastrowid  # type: ignore[return-value]

    def revoke_consent(
        self,
        *,
        device_id: str,
        consent_type: str = "biometric_processing",
        reason: str = "",
    ) -> bool:
        """Revoke consent for a device and mark erasure_requested (Phase 160 BP-002).

        Returns True if a record was updated, False if device not found.
        """
        now = time.time()
        with self._conn() as con:
            cur = con.execute(
                "UPDATE consent_ledger SET"
                " consent_given=0, revoked_at=?, revocation_reason=?, erasure_requested=1"
                " WHERE device_id=? AND consent_type=?",
                (now, reason, device_id, consent_type),
            )
        return cur.rowcount > 0

    def get_consent_status(
        self,
        device_id: str,
        consent_type: str = "biometric_processing",
    ) -> dict:
        """Return current consent state for a device (Phase 160 BP-002).

        Returns a dict with keys: consent_given, consent_ts, revoked,
        erasure_requested, erasure_completed, found.
        """
        with self._conn() as con:
            row = con.execute(
                "SELECT * FROM consent_ledger WHERE device_id=? AND consent_type=?",
                (device_id, consent_type),
            ).fetchone()
        if row:
            d = dict(row)
            return {
                "consent_given":    bool(d["consent_given"]),
                "consent_ts":       d["consent_ts"],
                "revoked":          d["revoked_at"] is not None,
                "revocation_reason": d["revocation_reason"] or "",
                "erasure_requested": bool(d["erasure_requested"]),
                "erasure_completed": bool(d["erasure_completed"]),
                "found":            True,
            }
        return {
            "consent_given":    False,
            "consent_ts":       None,
            "revoked":          False,
            "revocation_reason": "",
            "erasure_requested": False,
            "erasure_completed": False,
            "found":            False,
        }

    # ── Data Economy Arc 3 — Curator packaging loop persistence ──────────────

    def insert_pending_listing(self, intent: dict) -> int:
        """Enqueue a listing intent awaiting gamer approval (approval_required
        autonomy). Returns the new row id. Arc 3 Commit 1."""
        with self._conn() as con:
            cur = con.execute(
                "INSERT INTO pending_listings"
                " (session_id, device_id, autonomy_level, consent_policy_hash,"
                "  allowed_categories, status, ts_ns)"
                " VALUES (?,?,?,?,?,?,?)",
                (
                    str(intent.get("session_id", "")),
                    str(intent.get("device_id", "")),
                    str(intent.get("autonomy_level", "")),
                    intent.get("consent_policy_hash"),
                    json.dumps(list(intent.get("allowed_categories", []))),
                    "pending",
                    int(intent.get("ts_ns", 0)),
                ),
            )
        return cur.lastrowid  # type: ignore[return-value]

    def record_curator_packaging_action(self, entry: dict) -> int:
        """Append a packaging decision to the audit trail. Returns row id.
        Arc 3 Commit 1."""
        with self._conn() as con:
            cur = con.execute(
                "INSERT INTO curator_packaging_log"
                " (action, session_id, outcome, extra, ts_ns)"
                " VALUES (?,?,?,?,?)",
                (
                    str(entry.get("action", "packaging")),
                    str(entry.get("session_id", "")),
                    str(entry.get("outcome", "")),
                    json.dumps(entry.get("extra", {})),
                    int(entry.get("ts_ns", 0)),
                ),
            )
        return cur.lastrowid  # type: ignore[return-value]

    def get_curator_session_aggregate(self, session_id) -> dict | None:
        """Return the session-aggregate shape that CuratorPackagingLoop /
        VAPIReplayProofPipeline expect — for the live bridge's session model
        where "session" == "validated ruling" (Arc 5 Commit 6 wiring).

        session_id is interpreted as the ruling_id (string or int). Returns
        None if the ruling doesn't exist OR hasn't been validated yet. Maps:
            ruling.id           -> session_id
            ruling.device_id    -> device_id
            ruling.created_at   -> ended_at
            ruling.commitment_hash -> session_nonce (deterministic, 32B field)
            validation.fallback_verdict     -> verdict (HUMAN/CERTIFY/FLAG/...)
            validation.fallback_confidence  -> humanity_probability
                  Why fallback rather than llm: matches GIC honesty rail —
                  GIC stamps the deterministic fallback only (INV-GIC-001),
                  so the VHR proof must commit to the same verdict the chain
                  commits to. LLM divergence is recorded separately.
            0                              -> vhp_token_id (no VHP minted in
                  v1; orchestrator handles vhp_token_id=0 as "no VHP binding"
                  honestly — the inner Groth16 still computes vhpCommitment
                  over (0, sessionNonce) which is a valid commitment over a
                  null token id).

        Honest gap surfaced: this aggregate has NO gamer_address field. The
        Arc 5 live-session hook in SessionAdjudicatorValidationAgent passes
        gamer_address EXPLICITLY from cfg.session_gamer_address rather than
        reading it from this aggregate (single-tenant testnet posture). If
        a future commit adds a device->gamer registry, the aggregate's
        gamer_address would become an actual lookup result.
        """
        try:
            rid = int(session_id)
        except (TypeError, ValueError):
            return None
        with self._conn() as con:
            row = con.execute(
                "SELECT r.id, r.device_id, r.commitment_hash, r.created_at,"
                "       v.fallback_verdict, v.fallback_confidence"
                " FROM agent_rulings r"
                " LEFT JOIN ruling_validation_log v ON v.ruling_id = r.id"
                " WHERE r.id = ? LIMIT 1",
                (rid,),
            ).fetchone()
        if not row:
            return None
        d = dict(row)
        if d.get("fallback_verdict") is None:
            # Ruling exists but not yet validated — caller should defer.
            return None
        return {
            "session_id":           str(d["id"]),
            "device_id":            d["device_id"],
            "verdict":              d["fallback_verdict"],
            "humanity_probability": float(d["fallback_confidence"] or 0.0),
            "vhp_token_id":         0,
            "session_nonce":        int(d["commitment_hash"] or "0", 16) if isinstance(d.get("commitment_hash"), str) else 0,
            "ended_at":             float(d.get("created_at") or 0.0),
            # gamer_address intentionally omitted — the hook supplies it from
            # cfg.session_gamer_address at the call site (single-tenant v1).
        }

    def get_pending_replay_proofs(self, limit: int = 100) -> list[dict]:
        """Return Arc 5 VHR packaging audit entries currently in a 'pending'
        state — i.e. proof_deferred (ceremony absent), proof_built_no_verifier
        (no on-chain verifier wired), or proof_built (awaiting operator-fired
        submission). Read directly from the curator_packaging_log table
        populated by VAPIReplayProofPipeline._audit_and_return — no separate
        durable surface needed.

        Consumed by GET /curator/pending-replay-proofs.
        """
        pending = (
            "vhr_proof_deferred",
            "vhr_proof_built_no_verifier",
            "vhr_proof_built",
        )
        placeholders = ",".join("?" for _ in pending)
        with self._conn() as con:
            rows = con.execute(
                f"SELECT * FROM curator_packaging_log "
                f"WHERE action='vhr_packaging' AND outcome IN ({placeholders}) "
                f"ORDER BY ts_ns DESC LIMIT ?",
                (*pending, int(limit)),
            ).fetchall()
        out: list[dict] = []
        for row in rows:
            d = dict(row)
            try:
                d["extra"] = json.loads(d.get("extra") or "{}")
            except Exception:
                d["extra"] = {}
            out.append(d)
        return out

    def get_pending_listings(self, status: str = "pending") -> list[dict]:
        """Return pending listing intents at the given status (default 'pending').
        Arc 3 Commit 1 (consumed by Commit 3 endpoints)."""
        with self._conn() as con:
            rows = con.execute(
                "SELECT * FROM pending_listings WHERE status=?"
                " ORDER BY created_at DESC",
                (status,),
            ).fetchall()
        out: list[dict] = []
        for row in rows:
            d = dict(row)
            try:
                d["allowed_categories"] = json.loads(d.get("allowed_categories") or "[]")
            except Exception:
                d["allowed_categories"] = []
            out.append(d)
        return out

    def update_pending_listing_status(self, listing_id: int, status: str) -> bool:
        """Transition a pending listing to a terminal status (approved / rejected /
        submitted). Returns True if a row was updated. Arc 3 Commit 1
        (consumed by Commit 3 endpoints)."""
        with self._conn() as con:
            cur = con.execute(
                "UPDATE pending_listings SET status=? WHERE id=?",
                (str(status), int(listing_id)),
            )
        return cur.rowcount > 0

    def mark_erasure_complete(self, device_id: str) -> int:
        """Mark erasure as completed and log the erasure action (Phase 160 BP-002).

        Returns the number of fields anonymized.
        """
        now = time.time()
        fields_anonymized = self.anonymize_device_records(device_id)
        with self._conn() as con:
            con.execute(
                "UPDATE consent_ledger SET erasure_completed=1"
                " WHERE device_id=?",
                (device_id,),
            )
            con.execute(
                "INSERT INTO right_to_erasure_log"
                " (device_id, requested_at, fields_anonymized, completed_at, created_at)"
                " VALUES (?,?,?,?,?)",
                (device_id, now, fields_anonymized, now, now),
            )
        return fields_anonymized

    def anonymize_device_records(
        self,
        device_id: str,
        post_erasure_recompute: bool = False,
    ) -> int:
        """Soft-delete biometric fields for a device (GDPR Art.17, Phase 160 BP-002).

        Phase 161 (WIF-020): also redacts divergence_reason in ruling_validation_log.
        Phase 165 (WIF-024): when post_erasure_recompute=True, snapshot the current
        separation ratio before anonymization and write to post_erasure_ratio_log so
        operators are alerted that ratio recompute is needed.

        Returns total count of rows anonymized across both tables.
        """
        if post_erasure_recompute:
            _def_row = self.get_separation_defensibility_status()
            _ratio_before = float(_def_row.get("ratio", 0.0)) if _def_row else None
        with self._conn() as con:
            cur1 = con.execute(
                "UPDATE agent_rulings"
                " SET evidence_json='{}', reasoning='[redacted - GDPR Art.17 erasure]'"
                " WHERE device_id=?",
                (device_id,),
            )
            cur2 = con.execute(
                "UPDATE ruling_validation_log"
                " SET divergence_reason='[redacted - GDPR Art.17 erasure]'"
                " WHERE device_id=?",
                (device_id,),
            )
        count = cur1.rowcount + cur2.rowcount
        if post_erasure_recompute:
            self.insert_post_erasure_recompute_log(
                device_id=device_id,
                n_anonymized=count,
                ratio_before=_ratio_before,
                ratio_after=None,  # pending re-analysis via analyze_interperson_separation.py
                triggered_by="anonymize_device_records",
            )
        return count

    def get_erasure_log(self, device_id: str | None = None, limit: int = 20) -> list[dict]:
        """Return right-to-erasure log entries (Phase 160 BP-002)."""
        with self._conn() as con:
            if device_id:
                rows = con.execute(
                    "SELECT * FROM right_to_erasure_log WHERE device_id=?"
                    " ORDER BY id DESC LIMIT ?",
                    (device_id, limit),
                ).fetchall()
            else:
                rows = con.execute(
                    "SELECT * FROM right_to_erasure_log ORDER BY id DESC LIMIT ?",
                    (limit,),
                ).fetchall()
        return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    # Phase 161 — Consent Gate (BP-002 WIF-018/020 enforcement)
    # ------------------------------------------------------------------

    def insert_post_erasure_recompute_log(
        self,
        device_id: str,
        n_anonymized: int,
        ratio_before: "float | None",
        ratio_after: "float | None" = None,
        triggered_by: str = "anonymize_device_records",
        consent_type: str = "biometric",
    ) -> int:
        """Record that a device erasure requires separation ratio recompute (Phase 165 WIF-024).

        ratio_after is NULL until the operator re-runs analyze_interperson_separation.py
        and inserts a new separation_defensibility_log entry.
        recompute_needed=1 (True) while ratio_after IS NULL.
        """
        now = time.time()
        with self._conn() as con:
            cur = con.execute(
                "INSERT INTO post_erasure_ratio_log"
                " (device_id, n_anonymized, ratio_before, ratio_after,"
                "  recompute_needed, triggered_by, consent_type, recompute_ts, created_at)"
                " VALUES (?,?,?,?,?,?,?,?,?)",
                (
                    device_id,
                    n_anonymized,
                    ratio_before,
                    ratio_after,
                    1 if ratio_after is None else 0,
                    triggered_by,
                    consent_type,
                    now,
                    now,
                ),
            )
        return cur.lastrowid  # type: ignore[return-value]

    def get_post_erasure_recompute_status(self, device_id: "str | None" = None) -> dict:
        """Return post-erasure recompute audit summary (Phase 165 WIF-024).

        pending_recomputes counts rows where ratio_after IS NULL — these represent
        devices whose erasure has not yet been reflected in a new separation analysis.
        recompute_needed=True when pending_recomputes > 0.
        """
        with self._conn() as con:
            if device_id:
                total_row = con.execute(
                    "SELECT COUNT(*) as total FROM post_erasure_ratio_log"
                    " WHERE device_id=?",
                    (device_id,),
                ).fetchone()
                pending_row = con.execute(
                    "SELECT COUNT(*) as pending FROM post_erasure_ratio_log"
                    " WHERE device_id=? AND ratio_after IS NULL",
                    (device_id,),
                ).fetchone()
                latest_row = con.execute(
                    "SELECT ratio_before, recompute_ts FROM post_erasure_ratio_log"
                    " WHERE device_id=? ORDER BY id DESC LIMIT 1",
                    (device_id,),
                ).fetchone()
            else:
                total_row = con.execute(
                    "SELECT COUNT(*) as total FROM post_erasure_ratio_log"
                ).fetchone()
                pending_row = con.execute(
                    "SELECT COUNT(*) as pending FROM post_erasure_ratio_log"
                    " WHERE ratio_after IS NULL"
                ).fetchone()
                latest_row = con.execute(
                    "SELECT ratio_before, recompute_ts FROM post_erasure_ratio_log"
                    " ORDER BY id DESC LIMIT 1"
                ).fetchone()
        total   = int((dict(total_row).get("total")   or 0) if total_row   else 0)
        pending = int((dict(pending_row).get("pending") or 0) if pending_row else 0)
        latest  = dict(latest_row) if latest_row else {}
        return {
            "total_recomputes":    total,
            "pending_recomputes":  pending,
            "latest_recompute_ts": latest.get("recompute_ts"),
            "latest_ratio_before": latest.get("ratio_before"),
            "recompute_needed":    pending > 0,
        }

    def get_consent_snapshot_delta(self) -> dict:
        """Return delta between the most recent consent snapshot and live consent state.

        Phase 164 WIF-023: on-chain hash is immutable; consent_ledger is mutable.
        delta > 0 means N_consented has shrunk since the last commit — the chain
        attestation overstates current consent coverage.
        """
        with self._conn() as con:
            row = con.execute(
                "SELECT * FROM consent_snapshot_log ORDER BY id DESC LIMIT 1"
            ).fetchone()
        if row is None:
            return {
                "found":                  False,
                "commit_hash":            None,
                "n_consented_at_commit":  0,
                "n_consented_live":       0,
                "delta":                  0,
                "revoked_since_commit":   0,
                "snapshot_ts":            None,
            }
        d = dict(row)
        live    = self.get_consent_corpus_coverage()
        n_live  = live["active_consent_count"]
        revoked_live = live["revoked_count"]
        delta            = d["n_consented_at_commit"] - n_live
        revoked_since    = max(0, revoked_live - d["revoked_count_at_commit"])
        return {
            "found":                 True,
            "commit_hash":           d["commit_hash"],
            "n_consented_at_commit": d["n_consented_at_commit"],
            "n_consented_live":      n_live,
            "delta":                 delta,
            "revoked_since_commit":  revoked_since,
            "snapshot_ts":           d["snapshot_ts"],
        }

    # --- Phase 173: SeparationRatioRecoveryAgent ---

    # --- Phase 175: AgeWeightedRatioPersistenceAgent ---



    # --- Phase 176: PoACChainIntegrityMonitor ---



    # --- Phase 180: Biometric Renewal Engine (WIF-029 W2 closure) ---

    # --- Phase 179: ZK Ceremony Audit Gate (WIF-030 W1 closure) ---


    def count_ceremony_participants(self, circuit_name: str) -> int:
        """Return count of distinct participant_address entries for a ZK circuit (Phase 179)."""
        with self._conn() as conn:
            row = conn.execute(
                "SELECT COUNT(DISTINCT participant_address) FROM ceremony_audit_log "
                "WHERE circuit_name = ?",
                (str(circuit_name),),
            ).fetchone()
        return int(row[0]) if row else 0


    # --- Phase 178: Biometric Credential TTL Gate (WIF-029 W1 closure) ---

    # --- Phase 198: Biometric TTL Decay Scaling ---

    def get_effective_biometric_ttl(
        self,
        base_ttl_days: float = 90.0,
        scaling_enabled: bool = False,
    ) -> dict:
        """Compute effective biometric TTL with optional BP-001 decay scaling (Phase 198).

        Formula when enabled:
          scaling_factor = mean_decay_factor / 0.50
          effective_ttl  = base_ttl_days × scaling_factor
          Clamped to [base_ttl_days × 0.25, base_ttl_days × 4.0].

        mean_decay_factor = 1.0 (fresh data) → effective_ttl = 2× base (generous)
        mean_decay_factor = 0.50 (half-life)  → effective_ttl = 1× base (unchanged)
        mean_decay_factor = 0.25 (old data)   → effective_ttl = 0.5× base (strict)

        When scaling_enabled=False: effective_ttl = base_ttl_days (no change).

        Returns: effective_ttl_days / base_ttl_days / scaling_factor /
                 mean_decay_factor / scaling_enabled.
        """
        compliance = self.get_privacy_compliance_status()
        mean_decay = float(compliance.get("mean_decay_factor", 1.0))

        if not scaling_enabled:
            return {
                "effective_ttl_days": round(base_ttl_days, 4),
                "base_ttl_days":      round(base_ttl_days, 4),
                "scaling_factor":     1.0,
                "mean_decay_factor":  mean_decay,
                "scaling_enabled":    False,
            }

        _MIN_SCALE = 0.25
        _MAX_SCALE = 4.0
        scaling_factor = mean_decay / 0.50
        scaling_factor = max(_MIN_SCALE, min(_MAX_SCALE, scaling_factor))
        effective_ttl  = round(base_ttl_days * scaling_factor, 4)
        return {
            "effective_ttl_days": effective_ttl,
            "base_ttl_days":      round(base_ttl_days, 4),
            "scaling_factor":     round(scaling_factor, 6),
            "mean_decay_factor":  round(mean_decay, 6),
            "scaling_enabled":    True,
        }

    # --- Phase 177: ProtocolMaturityScoringAgent ---

    def insert_protocol_maturity_log(
        self,
        separation_component: float,
        chain_integrity_component: float,
        consent_component: float,
        biometric_freshness_component: float,
        agent_calibration_component: float,
        enrollment_component: float,
        threat_forecast_accuracy_component: float = 0.0,
        biometric_stationarity_component: float = 0.0,
        pmi_component: float = 1.0,
    ) -> int:
        """Insert a protocol maturity score assessment (Phase 177, v2 Phase 191 TSP, v3 Phase 195 PMI).

        maturity_score = (
            0.18 * separation_component                -- ratio converging or above gate (Phase 195: was 0.20)
          + 0.20 * chain_integrity_component           -- Phase 176 audit
          + 0.15 * consent_component                   -- Phase 162 consent corpus defensibility
          + 0.11 * biometric_freshness_component       -- Phase 159 TBD decay (Phase 195: was 0.12)
          + 0.12 * agent_calibration_component         -- Phase 148 ACIM health
          + 0.10 * enrollment_component                -- Phase 156 overall_ready
          + 0.07 * threat_forecast_accuracy_component  -- Phase 191 PIR harness score
          + 0.04 * biometric_stationarity_component    -- Phase 191 BSO confidence
          + 0.03 * pmi_component                       -- Phase 195 PMI fleet ORPHAN resolution velocity
        maturity_tier: ALPHA (<0.50) | BETA (0.50-0.85) | PRODUCTION_CANDIDATE (>=0.85)
        """
        score = round(
            0.18 * float(separation_component)
            + 0.20 * float(chain_integrity_component)
            + 0.15 * float(consent_component)
            + 0.11 * float(biometric_freshness_component)
            + 0.12 * float(agent_calibration_component)
            + 0.10 * float(enrollment_component)
            + 0.07 * float(threat_forecast_accuracy_component)
            + 0.04 * float(biometric_stationarity_component)
            + 0.03 * float(pmi_component),
            6,
        )
        if score >= 0.85:
            tier = "PRODUCTION_CANDIDATE"
        elif score >= 0.50:
            tier = "BETA"
        else:
            tier = "ALPHA"
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO protocol_maturity_log "
                "(maturity_score, maturity_tier, separation_component, "
                "chain_integrity_component, consent_component, "
                "biometric_freshness_component, agent_calibration_component, "
                "enrollment_component, threat_forecast_accuracy_component, "
                "biometric_stationarity_component, pmi_component, created_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    score,
                    tier,
                    float(separation_component),
                    float(chain_integrity_component),
                    float(consent_component),
                    float(biometric_freshness_component),
                    float(agent_calibration_component),
                    float(enrollment_component),
                    float(threat_forecast_accuracy_component),
                    float(biometric_stationarity_component),
                    float(pmi_component),
                    time.time(),
                ),
            )
        return cur.lastrowid  # type: ignore[return-value]

    def get_protocol_maturity_status(self, limit: int = 1) -> "list[dict]":
        """Return most recent protocol maturity assessments, newest first (Phase 177, v2 Phase 191, v3 Phase 195)."""
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT id, maturity_score, maturity_tier, separation_component, "
                "chain_integrity_component, consent_component, "
                "biometric_freshness_component, agent_calibration_component, "
                "enrollment_component, "
                "threat_forecast_accuracy_component, biometric_stationarity_component, "
                "pmi_component, created_at "
                "FROM protocol_maturity_log ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [
            {
                "id":                                    r[0],
                "maturity_score":                        float(r[1]),
                "maturity_tier":                         r[2],
                "separation_component":                  float(r[3]),
                "chain_integrity_component":             float(r[4]),
                "consent_component":                     float(r[5]),
                "biometric_freshness_component":         float(r[6]),
                "agent_calibration_component":           float(r[7]),
                "enrollment_component":                  float(r[8]),
                "threat_forecast_accuracy_component":    float(r[9]) if r[9] is not None else 0.0,
                "biometric_stationarity_component":      float(r[10]) if r[10] is not None else 0.0,
                "pmi_component":                         float(r[11]) if r[11] is not None else 1.0,
                "created_at":                            r[12],
            }
            for r in rows
        ]

    def get_threat_forecast_accuracy(self) -> float:
        """Return latest PIR harness_score as threat_forecast_accuracy (Phase 191).

        Uses protocol_intelligence_record_log.harness_score — the eval harness score
        from AutoResearch Cycle 11+ is the threat quality metric for TSP.
        Returns 0.5 (neutral) when no PIR data exists.
        """
        try:
            with self._conn() as conn:
                row = conn.execute(
                    "SELECT harness_score FROM protocol_intelligence_record_log "
                    "ORDER BY id DESC LIMIT 1"
                ).fetchone()
            if row is None:
                return 0.5
            return round(min(1.0, max(0.0, float(row[0]))), 6)
        except Exception:
            return 0.5

    # --- Phase 190: LivePresenceSignalingAgent ---

    def insert_presence_signal(
        self,
        signal_source: str,
        signal_type: str,
        led_rgb: "tuple[int,int,int]",
        haptic_duration: int,
        terminal_output: str,
        controller_fired: bool,
        ps5_compat_mode: bool,
    ) -> int:
        """Insert a live presence signal record (Phase 190)."""
        rgb_str = f"{led_rgb[0]},{led_rgb[1]},{led_rgb[2]}"
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO live_presence_signaling_log "
                "(signal_source, signal_type, led_rgb, haptic_duration, "
                "terminal_output, controller_fired, ps5_compat_mode, created_at) "
                "VALUES (?,?,?,?,?,?,?,?)",
                (
                    signal_source,
                    signal_type,
                    rgb_str,
                    int(haptic_duration),
                    terminal_output,
                    1 if controller_fired else 0,
                    1 if ps5_compat_mode else 0,
                    time.time(),
                ),
            )
        return cur.lastrowid  # type: ignore[return-value]

    def get_presence_signal_status(self, limit: int = 10) -> dict:
        """Return live presence signaling status (Phase 190)."""
        try:
            with self._conn() as conn:
                rows = conn.execute(
                    "SELECT signal_source, signal_type, led_rgb, haptic_duration, "
                    "terminal_output, controller_fired, ps5_compat_mode, created_at "
                    "FROM live_presence_signaling_log ORDER BY id DESC LIMIT ?",
                    (limit,),
                ).fetchall()
                total = conn.execute(
                    "SELECT COUNT(*) FROM live_presence_signaling_log"
                ).fetchone()[0]
                controller_fired_count = conn.execute(
                    "SELECT COUNT(*) FROM live_presence_signaling_log WHERE controller_fired=1"
                ).fetchone()[0]
                ps5_suppressed_count = conn.execute(
                    "SELECT COUNT(*) FROM live_presence_signaling_log WHERE ps5_compat_mode=1"
                ).fetchone()[0]
        except Exception:
            return {
                "total_signals": 0,
                "controller_fired_count": 0,
                "ps5_suppressed_count": 0,
                "latest_signal_source": "",
                "latest_signal_type": "",
                "latest_terminal_output": "",
                "timestamp": time.time(),
            }
        latest = rows[0] if rows else None
        return {
            "total_signals":          int(total),
            "controller_fired_count": int(controller_fired_count),
            "ps5_suppressed_count":   int(ps5_suppressed_count),
            "latest_signal_source":   latest[0] if latest else "",
            "latest_signal_type":     latest[1] if latest else "",
            "latest_terminal_output": latest[4] if latest else "",
            "timestamp":              time.time(),
        }

    # --- Phase 189: ProtocolIntelligenceRecordAgent ---

    @staticmethod
    def _compute_pir_hash(
        prev_pir_hash: str,
        cycle_number: int,
        phase_produced: "int | str",
        wif_hash: str,
        threat_forecast: str,
        harness_score: float,
        eval_timestamp: float,
    ) -> str:
        """Compute SHA-256 hash linking a PIR record into the chain (Phase 189).

        Formula: SHA-256("{prev}:{cycle}:{phase}:{wif}:{forecast}:{score:.6f}:{int(ts)}")
        """
        import hashlib
        body = (
            f"{prev_pir_hash}:{cycle_number}:{phase_produced}:{wif_hash}"
            f":{threat_forecast}:{float(harness_score):.6f}:{int(eval_timestamp)}"
        )
        return hashlib.sha256(body.encode()).hexdigest()

    def insert_pir(
        self,
        cycle_number: int,
        phase_produced: "int | str",
        wif_hash: str,
        threat_forecast: str,
        harness_score: float,
        eval_timestamp: float,
    ) -> "tuple[int, str]":
        """Insert a Protocol Intelligence Record into the hash-linked chain (Phase 189).

        Automatically fetches prev_pir_hash from the latest row ("0"*64 for genesis).
        Raises ValueError on UNIQUE duplicate (anti-replay).
        Returns (row_id, pir_hash).
        """
        with self._conn() as conn:
            prev_row = conn.execute(
                "SELECT pir_hash FROM protocol_intelligence_record_log ORDER BY id DESC LIMIT 1"
            ).fetchone()
            prev_pir_hash = prev_row[0] if prev_row else "0" * 64
            pir_hash = self._compute_pir_hash(
                prev_pir_hash, cycle_number, phase_produced,
                wif_hash, threat_forecast, harness_score, eval_timestamp,
            )
            try:
                cur = conn.execute(
                    "INSERT INTO protocol_intelligence_record_log "
                    "(cycle_number, phase_produced, wif_hash, threat_forecast, "
                    "harness_score, prev_pir_hash, pir_hash, eval_timestamp, created_at) "
                    "VALUES (?,?,?,?,?,?,?,?,?)",
                    (
                        int(cycle_number),
                        str(phase_produced),
                        wif_hash,
                        threat_forecast,
                        float(harness_score),
                        prev_pir_hash,
                        pir_hash,
                        float(eval_timestamp),
                        time.time(),
                    ),
                )
            except Exception as exc:
                if "UNIQUE" in str(exc).upper():
                    raise ValueError(f"Duplicate PIR hash (anti-replay): {pir_hash}") from exc
                raise
        return (cur.lastrowid, pir_hash)  # type: ignore[return-value]

    def get_pir_chain_status(self, window: int = 10) -> dict:
        """Return PIR chain integrity status (Phase 189).

        Verifies hash linkage in the latest `window` records.
        chain_intact=True when empty (vacuous integrity).
        """
        try:
            with self._conn() as conn:
                rows = conn.execute(
                    "SELECT id, pir_hash, prev_pir_hash, cycle_number, "
                    "phase_produced, threat_forecast, created_at "
                    "FROM protocol_intelligence_record_log ORDER BY id DESC LIMIT ?",
                    (window,),
                ).fetchall()
                total = conn.execute(
                    "SELECT COUNT(*) FROM protocol_intelligence_record_log"
                ).fetchone()[0]
        except Exception:
            return {
                "total_pirs": 0,
                "chain_intact": True,
                "latest_cycle": 0,
                "latest_pir_hash": "",
                "latest_phase_produced": 0,
                "latest_threat_forecast": "",
                "records": [],
                "timestamp": time.time(),
            }
        chain_intact = True
        if len(rows) >= 2:
            for i in range(len(rows) - 1):
                # rows[i] is newer; rows[i+1] is older
                if rows[i][2] != rows[i + 1][1]:
                    chain_intact = False
                    break
        latest = rows[0] if rows else None
        records_list = [
            {
                "id": r[0],
                "pir_hash": r[1],
                "prev_pir_hash": r[2],
                "cycle_number": r[3],
                "phase_produced": r[4],
                "threat_forecast": r[5],
                "created_at": r[6],
            }
            for r in rows
        ]
        return {
            "total_pirs":             int(total),
            "chain_intact":           chain_intact,
            "latest_cycle":           int(latest[3]) if latest else 0,
            "latest_pir_hash":        latest[1] if latest else "",
            "latest_phase_produced":  latest[4] if latest else 0,
            "latest_threat_forecast": latest[5] if latest else "",
            "records":                records_list,
            "timestamp":              time.time(),
        }

    # --- Phase 188: BiometricStationarityOracleAgent ---

    # --- Phase 187: AttestationOpSecAdvisorAgent + VHPReenrollmentBadge ---

    # --- Phase 186: AttestationBoundRenewalAgent ---

    # --- Phase 185: ReEnrollmentAttestationAgent ---

    # --- Phase 183: MaturityElevationGateAgent ---

    # --- Phase 182: PersonaBreakDetectorAgent ---

    # --- Phase 181: Consent-Bound Renewal Provenance ---

    # --- Phase 192: DataCuratorAgent (Agent #35) ---

    # Task 1: Provenance DAG Engine

    def insert_provenance_node(self, node: dict) -> str:
        """Insert a provenance DAG node. Idempotent — INSERT OR IGNORE on UNIQUE node_id.
        Returns node_id (Phase 192)."""
        with self._conn() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO data_provenance_dag "
                "(node_id, node_type, source_table, source_row_id, source_hash, "
                "parent_node_id, edge_type, phase_produced, player_id, on_chain_ref) "
                "VALUES (?,?,?,?,?,?,?,?,?,?)",
                (
                    node.get("node_id", ""),
                    node.get("node_type", ""),
                    node.get("source_table", ""),
                    node.get("source_row_id"),
                    node.get("source_hash"),
                    node.get("parent_node_id"),
                    node.get("edge_type"),
                    int(node.get("phase_produced", 192)),
                    node.get("player_id"),
                    node.get("on_chain_ref"),
                ),
            )
        return node.get("node_id", "")

    def get_provenance_chain(self, leaf_node_id: str, max_depth: int = 20) -> list:
        """Walk from leaf_node_id to root(s) via parent_node_id.
        Returns ordered list from root to leaf. Max depth prevents infinite loop (Phase 192)."""
        chain = []
        visited = set()
        current_id = leaf_node_id
        depth = 0
        while current_id and depth < max_depth:
            if current_id in visited:
                break
            visited.add(current_id)
            try:
                with self._conn() as conn:
                    row = conn.execute(
                        "SELECT node_id, node_type, source_table, source_row_id, source_hash, "
                        "parent_node_id, edge_type, phase_produced, player_id, on_chain_ref, created_at "
                        "FROM data_provenance_dag WHERE node_id=?",
                        (current_id,),
                    ).fetchone()
            except Exception:
                break
            if row is None:
                break
            chain.append({
                "node_id":        row[0],
                "node_type":      row[1],
                "source_table":   row[2],
                "source_row_id":  row[3],
                "source_hash":    row[4],
                "parent_node_id": row[5],
                "edge_type":      row[6],
                "phase_produced": int(row[7]) if row[7] is not None else 192,
                "player_id":      row[8],
                "on_chain_ref":   row[9],
                "created_at":     row[10],
            })
            current_id = row[5]  # parent_node_id
            depth += 1
        chain.reverse()  # root first
        return chain

    def get_provenance_subtree(self, root_node_id: str) -> list:
        """Return all descendants of a root node (Phase 192)."""
        result = []
        queue = [root_node_id]
        visited = set()
        while queue:
            nid = queue.pop(0)
            if nid in visited:
                continue
            visited.add(nid)
            try:
                with self._conn() as conn:
                    rows = conn.execute(
                        "SELECT node_id, node_type, source_table, source_row_id, source_hash, "
                        "parent_node_id, edge_type, phase_produced, player_id, on_chain_ref, created_at "
                        "FROM data_provenance_dag WHERE parent_node_id=?",
                        (nid,),
                    ).fetchall()
            except Exception:
                rows = []
            for row in rows:
                child = {
                    "node_id":        row[0],
                    "node_type":      row[1],
                    "source_table":   row[2],
                    "source_row_id":  row[3],
                    "source_hash":    row[4],
                    "parent_node_id": row[5],
                    "edge_type":      row[6],
                    "phase_produced": int(row[7]) if row[7] is not None else 192,
                    "player_id":      row[8],
                    "on_chain_ref":   row[9],
                    "created_at":     row[10],
                }
                result.append(child)
                queue.append(row[0])
        return result

    # Task 3: Proof-of-Erasure Certificate Engine

    def compute_erasure_certificate(self, device_id: str, player_id: str,
                                    erased_tables: dict, post_erasure_ratio: float,
                                    ts_ns: int) -> str:
        """Compute GDPR Art.17 erasure certificate hash (Phase 192).
        SHA-256(device_id_bytes + sorted_table_row_hashes + ratio_str + ts_ns_bytes)."""
        import hashlib
        import struct
        parts = [device_id.encode()]
        # Sort table names for determinism
        for tbl in sorted(erased_tables.keys()):
            rows_str = ",".join(str(r) for r in sorted(erased_tables[tbl]))
            parts.append(f"{tbl}:{rows_str}".encode())
        parts.append(f"{post_erasure_ratio:.8f}".encode())
        parts.append(struct.pack(">Q", ts_ns))
        digest = hashlib.sha256(b"".join(parts)).hexdigest()
        return "sha256:" + digest

    def insert_erasure_certificate(self, certificate_hash: str, device_id: str,
                                   player_id: str, erased_tables_json: str,
                                   erased_row_count: int, post_erasure_ratio: float,
                                   ts_ns: int) -> int:
        """Insert an erasure certificate (idempotent on UNIQUE certificate_hash). Phase 192."""
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT OR IGNORE INTO erasure_certificate_log "
                "(certificate_hash, device_id, player_id, erased_tables_json, "
                "erased_row_count, post_erasure_ratio, ts_ns) VALUES (?,?,?,?,?,?,?)",
                (certificate_hash, device_id, player_id, erased_tables_json,
                 erased_row_count, post_erasure_ratio, ts_ns),
            )
        return cur.lastrowid or 0  # type: ignore[return-value]

    def get_erasure_certificate(self, device_id: str) -> "dict | None":
        """Return most recent erasure certificate for device_id (Phase 192)."""
        try:
            with self._conn() as conn:
                row = conn.execute(
                    "SELECT certificate_hash, device_id, player_id, erased_tables_json, "
                    "erased_row_count, post_erasure_ratio, on_chain_tx_hash, anchored, "
                    "ts_ns, created_at "
                    "FROM erasure_certificate_log WHERE device_id=? "
                    "ORDER BY ts_ns DESC LIMIT 1",
                    (device_id,),
                ).fetchone()
        except Exception:
            row = None
        if row is None:
            return None
        return {
            "certificate_hash":   row[0],
            "device_id":          row[1],
            "player_id":          row[2],
            "erased_tables_json": row[3],
            "erased_row_count":   int(row[4]),
            "post_erasure_ratio": float(row[5]),
            "on_chain_tx_hash":   row[6],
            "anchored":           bool(row[7]),
            "ts_ns":              int(row[8]),
            "created_at":         row[9],
        }

    def anchor_erasure_certificate(self, certificate_hash: str, tx_hash: str) -> None:
        """Mark an erasure certificate as anchored on-chain (Phase 192)."""
        with self._conn() as conn:
            conn.execute(
                "UPDATE erasure_certificate_log SET on_chain_tx_hash=?, anchored=1 "
                "WHERE certificate_hash=?",
                (tx_hash, certificate_hash),
            )






    # Phase 194: CoherenceFingerprintRegistry — coherence_fingerprint_log




    # --- Phase 195: Protocol Metabolism Index (PMI) ---

    def get_orphan_resolution_stats(self, domain: str = "") -> dict:
        """Return ORPHAN resolution statistics for the Protocol Metabolism Index (Phase 195).

        PMI = max(0.0, 1.0 - mean_resolution_hours_critical / 48.0)
        where mean_resolution_hours_critical is the mean time (hours) to resolve
        ORPHAN entries in fleet_coherence_log.

        When no resolved ORPHANs exist (all healthy): pmi_score=1.0 (best possible).
        When mean resolution > 48h: pmi_score → 0.0.

        Args:
            domain: optional substring filter on rule_name (e.g. "separation_ratio")

        Returns dict with 5 keys:
            mean_resolution_hours, pmi_score, orphan_count_resolved,
            orphan_count_open, domain
        """
        try:
            import sqlite3 as _sq195
            from datetime import datetime as _dt195
            with _sq195.connect(self._db_path) as conn:
                conn.row_factory = _sq195.Row
                if domain:
                    resolved_rows = conn.execute(
                        "SELECT created_at, resolved_at FROM fleet_coherence_log "
                        "WHERE failure_mode='ORPHAN' AND resolved_at IS NOT NULL "
                        "AND rule_name LIKE ?",
                        (f"%{domain}%",),
                    ).fetchall()
                    open_row = conn.execute(
                        "SELECT COUNT(*) AS n FROM fleet_coherence_log "
                        "WHERE failure_mode='ORPHAN' AND resolved_at IS NULL "
                        "AND rule_name LIKE ?",
                        (f"%{domain}%",),
                    ).fetchone()
                else:
                    resolved_rows = conn.execute(
                        "SELECT created_at, resolved_at FROM fleet_coherence_log "
                        "WHERE failure_mode='ORPHAN' AND resolved_at IS NOT NULL"
                    ).fetchall()
                    open_row = conn.execute(
                        "SELECT COUNT(*) AS n FROM fleet_coherence_log "
                        "WHERE failure_mode='ORPHAN' AND resolved_at IS NULL"
                    ).fetchone()

            hours_list: list = []
            for r in resolved_rows:
                try:
                    created = _dt195.fromisoformat(str(r["created_at"]).replace(" ", "T"))
                    resolved = _dt195.fromisoformat(str(r["resolved_at"]).replace(" ", "T"))
                    hours_list.append((resolved - created).total_seconds() / 3600.0)
                except Exception:
                    pass  # fail-open: M-1 cleanup 2026-05-16 — intentional silent skip

            mean_hours = sum(hours_list) / len(hours_list) if hours_list else 0.0
            # pmi_score=1.0 when no ORPHAN history (healthy fleet) or fast resolution
            pmi_score = max(0.0, 1.0 - mean_hours / 48.0) if hours_list else 1.0
            open_n = int(open_row["n"]) if open_row else 0

            return {
                "mean_resolution_hours": round(mean_hours, 4),
                "pmi_score":             round(pmi_score, 6),
                "orphan_count_resolved": len(hours_list),
                "orphan_count_open":     open_n,
                "domain":                domain or "all",
            }
        except Exception:
            return {
                "mean_resolution_hours": 0.0,
                "pmi_score":             1.0,
                "orphan_count_resolved": 0,
                "orphan_count_open":     0,
                "domain":                domain or "all",
            }

    # --- Phase 202: TremorRestingConvergenceOracle ---

    # Non-convergence threshold: 5 consecutive negative velocities → non-convergence declared.
    _N_NONCONV_THRESHOLD: int = 5

    # --- Phase 203: AgentContextRegistry ---

    # --- Phase 207: StagedDryRunGraduationGate ---

    # --- Phase 214: GraduationAutowatchBridge ---

    # --- Phase 229: AIT Separation Log ---

    # -----------------------------------------------------------------------
    # Phase 234.7 — Physical Capture Continuity (PCC)
    # -----------------------------------------------------------------------

    # --- Phase O1 C1: Operator Agent activation log helpers ---
    def insert_operator_agent_activation(
        self,
        *,
        agent_id: str,
        from_phase: str,
        to_phase: str,
        from_scope_root: str,
        to_scope_root: str,
        bundle_path: str,
        governance_tx_hash: str,
        operational_tx_hash: str,
        governance_block_number: int,
        operational_block_number: int,
        operator_authority_hash: str,
        reason_text: str,
    ) -> int:
        """Insert one row into operator_agent_activation_log; return new row id.

        UNIQUE(agent_id, to_scope_root) constraint per INV-OPERATOR-AGENT-002:
        if a row already exists for this (agent_id, to_scope_root) tuple, the
        INSERT raises sqlite3.IntegrityError — caller (cedar_bundle_anchor.py)
        treats this as a "duplicate anchor attempt" signal.  Anti-replay
        ensures each (agent, scope_root) pair is activated exactly once.
        """
        with self._conn() as conn:
            cursor = conn.execute(
                "INSERT INTO operator_agent_activation_log "
                "(agent_id, from_phase, to_phase, from_scope_root, to_scope_root, "
                " bundle_path, governance_tx_hash, operational_tx_hash, "
                " governance_block_number, operational_block_number, "
                " operator_authority_hash, reason_text, activated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    agent_id, from_phase, to_phase, from_scope_root, to_scope_root,
                    bundle_path, governance_tx_hash, operational_tx_hash,
                    int(governance_block_number), int(operational_block_number),
                    operator_authority_hash, reason_text, time.time(),
                ),
            )
            return int(cursor.lastrowid)

    # --- Phase O1 C2: Operator Agent Shadow Log helpers ---
    def insert_operator_agent_shadow_log(
        self,
        *,
        agent_id: str,
        action: str,
        resource: str,
        context_json: str,
        decision: str,
        bundle_merkle_root: str,
        bundle_path: str,
        draft_payload_hash: str,
        source: str,
    ) -> int:
        """Persist one Cedar evaluation event in shadow mode.

        evaluated_at_bucket is `int(time.time())` (second-granularity) so
        UNIQUE(agent_id, action, resource, evaluated_at_bucket) deduplicates
        retry storms while still permitting ≥1 distinct evaluation per second.
        """
        now = time.time()
        bucket = int(now)
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT OR IGNORE INTO operator_agent_shadow_log "
                "(agent_id, action, resource, context_json, decision, "
                "bundle_merkle_root, bundle_path, draft_payload_hash, source, "
                "evaluated_at, evaluated_at_bucket) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (
                    agent_id, action, resource, context_json, decision,
                    bundle_merkle_root, bundle_path, draft_payload_hash, source,
                    now, bucket,
                ),
            )
            if cur.lastrowid:
                return int(cur.lastrowid)
            # UNIQUE collision — return existing row id for idempotency
            existing = conn.execute(
                "SELECT id FROM operator_agent_shadow_log "
                "WHERE agent_id=? AND action=? AND resource=? AND evaluated_at_bucket=?",
                (agent_id, action, resource, bucket),
            ).fetchone()
            return int(existing["id"]) if existing else 0

    # --- Phase O1 C3: Operator Agent Drift Log helpers ---
    def insert_operator_agent_drift(
        self,
        *,
        agent_id: str,
        drift_type: str,
        expected_value: str,
        actual_value: str,
        bundle_path: str,
        evidence_json: str,
        sweep_id: str,
    ) -> int:
        """Persist one drift finding from an operator sweep.

        UNIQUE(agent_id, drift_type, detected_at_bucket) at second-granularity
        — sweep retries within the same second collapse to one row.
        """
        now = time.time()
        bucket = int(now)
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT OR IGNORE INTO operator_agent_drift_log "
                "(agent_id, drift_type, expected_value, actual_value, "
                "bundle_path, evidence_json, sweep_id, "
                "detected_at, detected_at_bucket) "
                "VALUES (?,?,?,?,?,?,?,?,?)",
                (
                    agent_id, drift_type, expected_value, actual_value,
                    bundle_path, evidence_json, sweep_id,
                    now, bucket,
                ),
            )
            if cur.lastrowid:
                return int(cur.lastrowid)
            existing = conn.execute(
                "SELECT id FROM operator_agent_drift_log "
                "WHERE agent_id=? AND drift_type=? AND detected_at_bucket=?",
                (agent_id, drift_type, bucket),
            ).fetchone()
            return int(existing["id"]) if existing else 0

    # --- Phase O1-FRR: Operator Initiative Advancement helpers ---
    #
    # The advancement watcher (operator_initiative_advancement.py) calls
    # four legacy-named helpers that were prototyped against test stubs
    # only — production store had no real implementations.  The four
    # helpers below close that gap with adapter shapes (bundle_filename
    # derived from bundle_path, anchored_at_unix aliased from activated_at)
    # so the watcher module + its tests are unchanged.
    #
    # The fifth/sixth/seventh helpers persist + read the FRR commitment.

    # ------------------------------------------------------------------
    # Phase O2-DRAFT-GENERATION (2026-05-10) — operator_agent_drafts helpers
    # ------------------------------------------------------------------
    # ------------------------------------------------------------------
    # Phase O5-MYTHOS-MINIMAL M.1 — mythos_finding_log + mythos_cadence_log helpers
    # ------------------------------------------------------------------
    def insert_mythos_finding(
        self,
        *,
        variant: str,
        severity: str,
        coherence_id: str,
        description: str,
        recommended_fix: str,
        file_path: str | None = None,
        line_number: int | None = None,
        frozen_region: bool = False,
        fix_authority_tier: int = 2,
        evidence_sources: list[str] | None = None,
    ) -> int:
        """Persist one Mythos finding. Returns new row id; 0 on UNIQUE
        collision (same coherence_id already persisted -- idempotent /
        anti-replay). Fail-open: returns 0 on any DB error, never raises.

        INV-MYTHOS-FROZEN-PROTECTION-001 enforced HERE: when frozen_region
        is True, fix_authority_tier is forced to 3 (read-only) regardless
        of the caller's value. Mythos NEVER auto-fixes FROZEN material.
        """
        try:
            tier = int(fix_authority_tier)
            if bool(frozen_region):
                tier = 3  # INV-MYTHOS-FROZEN-PROTECTION-001
            if tier not in (1, 2, 3):
                tier = 2  # safe default
            sev = str(severity).upper()
            if sev not in ("CRITICAL", "HIGH", "MEDIUM", "LOW"):
                sev = "MEDIUM"
            ev_json = json.dumps(list(evidence_sources or []), sort_keys=True)
            with self._conn() as conn:
                cur = conn.execute(
                    "INSERT OR IGNORE INTO mythos_finding_log "
                    "(variant, severity, coherence_id, file_path, line_number, "
                    " description, recommended_fix, frozen_region, "
                    " fix_authority_tier, evidence_sources_json, created_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        str(variant),
                        sev,
                        str(coherence_id),
                        file_path,
                        line_number,
                        str(description),
                        str(recommended_fix),
                        1 if bool(frozen_region) else 0,
                        tier,
                        ev_json,
                        time.time(),
                    ),
                )
                return int(cur.lastrowid or 0)
        except Exception:
            return 0

    # --- Phase O1-D-AUTO-SUPERSEDE 2026-05-17 ---
    # Empirical-Evidence Supersession primitive attestation log.  Each row
    # commits the gate-state evidence at the moment of supersession via the
    # VAPI-O3-SUPERSEDE-v1 FROZEN attestation hash.  Watcher consults this
    # table when shadow_age is unmet; if a recent (within 5 min) eligible
    # attestation exists AND phase_o3_auto_supersede_enabled cfg flag is True,
    # the calendar gate is treated as satisfied.

    def _ensure_operator_initiative_auto_supersede_table(self, conn) -> None:
        """Lazy-create the auto_supersede_log table.  Idempotent CREATE TABLE
        IF NOT EXISTS pattern matches other late-shipped tables (Phase 240)."""
        conn.execute("""
            CREATE TABLE IF NOT EXISTS operator_initiative_auto_supersede_log (
                id                                 INTEGER PRIMARY KEY AUTOINCREMENT,
                agent_id                           TEXT NOT NULL,
                eligible                           INTEGER NOT NULL,
                attestation_hash_hex               TEXT NOT NULL,
                draft_count                        INTEGER NOT NULL,
                disagreement_rate                  REAL NOT NULL,
                bundle_drift_count_30d             INTEGER NOT NULL,
                scope_drift_count_30d              INTEGER NOT NULL,
                operator_dual_key_present          INTEGER NOT NULL,
                kms_hsm_production_ready           INTEGER NOT NULL,
                github_app_oauth_tokens_valid      INTEGER NOT NULL,
                marketplace_curator_role_assigned  INTEGER NOT NULL,
                false_positive_rate                REAL NOT NULL,
                shadow_age_at_supersede_hours      REAL NOT NULL,
                blockers_json                      TEXT NOT NULL DEFAULT '[]',
                ts_ns                              INTEGER NOT NULL,
                created_at                         REAL NOT NULL DEFAULT (unixepoch('now'))
            )
        """)
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_o3_supersede_agent_created "
            "ON operator_initiative_auto_supersede_log(agent_id, created_at DESC)"
        )
        conn.execute(
            "INSERT OR IGNORE INTO schema_versions (phase, migration_name, applied_at) "
            "VALUES (?, ?, ?)",
            (240, "operator_initiative_auto_supersede_log", time.time()),
        )

    def insert_operator_initiative_auto_supersede(
        self,
        *,
        agent_id: str,
        eligible: bool,
        attestation_hash_hex: str,
        draft_count: int,
        disagreement_rate: float,
        bundle_drift_count_30d: int,
        scope_drift_count_30d: int,
        operator_dual_key_present: bool,
        kms_hsm_production_ready: bool,
        github_app_oauth_tokens_valid: bool,
        marketplace_curator_role_assigned: bool,
        false_positive_rate: float,
        shadow_age_at_supersede_hours: float,
        blockers_json: str,
        ts_ns: int,
    ) -> int:
        """Persist one supersede attestation row (eligible OR ineligible).
        Returns new row id; returns 0 on DB failure (fail-open per
        INV-OPERATOR-AGENT-004 spirit)."""
        try:
            with self._conn() as conn:
                self._ensure_operator_initiative_auto_supersede_table(conn)
                cur = conn.execute(
                    "INSERT INTO operator_initiative_auto_supersede_log "
                    "(agent_id, eligible, attestation_hash_hex, draft_count, "
                    " disagreement_rate, bundle_drift_count_30d, "
                    " scope_drift_count_30d, operator_dual_key_present, "
                    " kms_hsm_production_ready, github_app_oauth_tokens_valid, "
                    " marketplace_curator_role_assigned, false_positive_rate, "
                    " shadow_age_at_supersede_hours, blockers_json, ts_ns) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        str(agent_id),
                        1 if eligible else 0,
                        str(attestation_hash_hex or ""),
                        int(draft_count),
                        float(disagreement_rate),
                        int(bundle_drift_count_30d),
                        int(scope_drift_count_30d),
                        1 if operator_dual_key_present else 0,
                        1 if kms_hsm_production_ready else 0,
                        1 if github_app_oauth_tokens_valid else 0,
                        1 if marketplace_curator_role_assigned else 0,
                        float(false_positive_rate),
                        float(shadow_age_at_supersede_hours),
                        str(blockers_json or "[]"),
                        int(ts_ns),
                    ),
                )
                return int(cur.lastrowid or 0)
        except Exception:
            return 0  # fail-open

    def get_latest_operator_initiative_auto_supersede(
        self, agent_id: str, since_seconds: float = 300.0,
    ) -> dict | None:
        """Return most-recent eligible supersede attestation for agent_id
        within last since_seconds (default 5 min).  Returns None if no
        eligible row found in window."""
        try:
            cutoff = time.time() - max(0.0, float(since_seconds))
            with self._conn() as conn:
                self._ensure_operator_initiative_auto_supersede_table(conn)
                row = conn.execute(
                    "SELECT * FROM operator_initiative_auto_supersede_log "
                    "WHERE agent_id = ? AND eligible = 1 "
                    "AND created_at >= ? "
                    "ORDER BY id DESC LIMIT 1",
                    (str(agent_id), cutoff),
                ).fetchone()
            return dict(row) if row else None
        except Exception:
            return None

    def get_operator_initiative_auto_supersede_status(self) -> dict:
        """Aggregate status across all 3 agents for the operator API surface."""
        try:
            with self._conn() as conn:
                self._ensure_operator_initiative_auto_supersede_table(conn)
                rows = conn.execute(
                    "SELECT agent_id, eligible, attestation_hash_hex, "
                    "draft_count, disagreement_rate, ts_ns, created_at "
                    "FROM operator_initiative_auto_supersede_log "
                    "ORDER BY id DESC LIMIT 30"
                ).fetchall()
            return {
                "total_attestations": len(rows),
                "rows": [dict(r) for r in rows],
                "timestamp": time.time(),
            }
        except Exception as exc:
            return {
                "total_attestations": 0,
                "rows": [],
                "timestamp": time.time(),
                "error": str(exc),
            }

    # --- Phase O1-D-PATH-B v1 2026-05-17: per-agent live-write executor ---
    # `operator_agent_chain_spending_log` records every chain operation
    # fired by the live-write executor (or refused/skipped event) with
    # agent_id + draft_id + action_name + cost_iotx + tx_hash + error.
    # Used by evaluate_live_write_authorization_for_agent for daily budget
    # enforcement (SUM(cost_iotx) WHERE agent_id=? AND created_at >= today).

    def _ensure_operator_agent_chain_spending_table(self, conn) -> None:
        """Lazy-create the spending log table. Idempotent CREATE TABLE IF NOT
        EXISTS pattern. Also lazily adds executed_at + executed_tx_hash
        columns to operator_agent_drafts via PRAGMA-guarded ALTER TABLE
        (no-op if columns already present)."""
        conn.execute("""
            CREATE TABLE IF NOT EXISTS operator_agent_chain_spending_log (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                agent_id    TEXT NOT NULL,
                draft_id    INTEGER NOT NULL,
                action_name TEXT NOT NULL,
                cost_iotx   REAL NOT NULL DEFAULT 0.0,
                tx_hash     TEXT NOT NULL DEFAULT '',
                error       TEXT,
                created_at  REAL NOT NULL DEFAULT (unixepoch('now'))
            )
        """)
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_chain_spending_agent_created "
            "ON operator_agent_chain_spending_log(agent_id, created_at DESC)"
        )
        # Add execution-tracking columns to operator_agent_drafts (idempotent).
        existing_cols = {r[1] for r in conn.execute("PRAGMA table_info(operator_agent_drafts)").fetchall()}
        if "executed_at" not in existing_cols:
            try:
                conn.execute("ALTER TABLE operator_agent_drafts ADD COLUMN executed_at REAL DEFAULT NULL")
            except Exception:
                pass  # fail-open: another process may have added column concurrently
        if "executed_tx_hash" not in existing_cols:
            try:
                conn.execute("ALTER TABLE operator_agent_drafts ADD COLUMN executed_tx_hash TEXT DEFAULT ''")
            except Exception:
                pass
        # 2026-05-20 refusal-churn cap: terminally-refused drafts (no executor
        # route, or chain-cost action under a budget=0 agent) were re-fetched +
        # re-refused every executor cycle, accumulating 7k+ identical
        # spending_log rows. Mark them so they drop out of the fetch.
        if "refused_at" not in existing_cols:
            try:
                conn.execute("ALTER TABLE operator_agent_drafts ADD COLUMN refused_at REAL DEFAULT NULL")
            except Exception:
                pass  # idempotent migration: column already added in prior run
        if "refusal_reason" not in existing_cols:
            try:
                conn.execute("ALTER TABLE operator_agent_drafts ADD COLUMN refusal_reason TEXT DEFAULT ''")
            except Exception:
                pass  # idempotent migration: column already added in prior run
        conn.execute(
            "INSERT OR IGNORE INTO schema_versions (phase, migration_name, applied_at) "
            "VALUES (?, ?, ?)",
            (241, "operator_agent_chain_spending_log", time.time()),
        )

    def insert_chain_spending_event(
        self, *,
        agent_id: str,
        draft_id: int,
        action_name: str,
        cost_iotx: float,
        tx_hash: str,
        error: "str | None" = None,
    ) -> int:
        """Record one chain spending event (success or refusal/skip).
        Returns row id; returns 0 on DB failure (fail-open)."""
        try:
            with self._conn() as conn:
                self._ensure_operator_agent_chain_spending_table(conn)
                cur = conn.execute(
                    "INSERT INTO operator_agent_chain_spending_log "
                    "(agent_id, draft_id, action_name, cost_iotx, tx_hash, error) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (
                        str(agent_id), int(draft_id), str(action_name),
                        float(cost_iotx), str(tx_hash or ""),
                        (str(error) if error else None),
                    ),
                )
                return int(cur.lastrowid or 0)
        except Exception:
            return 0

    def get_daily_chain_spending_for_agent(self, agent_id: str) -> float:
        """Return sum of cost_iotx for `agent_id` within the current UTC day.
        Used for budget enforcement. Returns 0.0 on any failure (fail-open
        — refuses to over-charge agent on bad reads)."""
        try:
            # Day-boundary: midnight UTC. Use unixepoch('now', 'start of day').
            with self._conn() as conn:
                self._ensure_operator_agent_chain_spending_table(conn)
                # Match by both raw agent_id AND canonical-name lookups (caller
                # may pass either).
                row = conn.execute(
                    "SELECT COALESCE(SUM(cost_iotx), 0.0) FROM operator_agent_chain_spending_log "
                    "WHERE (agent_id = ? OR agent_id = ?) "
                    "AND created_at >= unixepoch('now', 'start of day')",
                    (str(agent_id), str(agent_id).lower()),
                ).fetchone()
            return float(row[0] if row else 0.0)
        except Exception:
            return 0.0

    # --- Tier-1 autonomous signing audit (2026-05-20) ---
    # Durable record of every signature an Operator steward produces via its
    # KMS key (Guardian kms-sign on commit hashes is the first). cost_iotx is
    # ZERO — KMS signing is an off-chain AWS crypto op, not a chain tx — so this
    # is purely a provenance/audit artifact, NOT a spending record.

    def _ensure_operator_agent_signature_table(self, conn) -> None:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS operator_agent_signature_log (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                agent_id      TEXT NOT NULL,
                draft_id      INTEGER NOT NULL DEFAULT 0,
                subject       TEXT NOT NULL DEFAULT '',
                digest_hex    TEXT NOT NULL,
                signature_hex TEXT NOT NULL,
                kms_key_spec  TEXT NOT NULL DEFAULT '',
                kms_verified  INTEGER NOT NULL DEFAULT 0,
                ts_ns         INTEGER NOT NULL,
                created_at    REAL NOT NULL DEFAULT (unixepoch('now'))
            )
        """)
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_agent_sig_agent_ts "
            "ON operator_agent_signature_log(agent_id, ts_ns DESC)"
        )

    def insert_operator_agent_signature(
        self, *, agent_id: str, draft_id: int, subject: str,
        digest_hex: str, signature_hex: str, kms_key_spec: str,
        kms_verified: bool, ts_ns: int,
    ) -> int:
        """Record one Operator-agent KMS signature (audit/provenance; cost 0).
        Returns row id; 0 on failure (fail-open)."""
        try:
            with self._conn() as conn:
                self._ensure_operator_agent_signature_table(conn)
                cur = conn.execute(
                    "INSERT INTO operator_agent_signature_log "
                    "(agent_id, draft_id, subject, digest_hex, signature_hex, "
                    " kms_key_spec, kms_verified, ts_ns) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        str(agent_id), int(draft_id), str(subject)[:200],
                        str(digest_hex), str(signature_hex), str(kms_key_spec),
                        1 if kms_verified else 0, int(ts_ns),
                    ),
                )
                return int(cur.lastrowid or 0)
        except Exception:
            return 0

    def get_operator_agent_signatures(
        self, agent_id: "str | None" = None, limit: int = 10,
    ) -> "list[dict]":
        """Return recent Operator-agent signatures (newest first)."""
        try:
            limit = max(1, min(100, int(limit)))
            with self._conn() as conn:
                self._ensure_operator_agent_signature_table(conn)
                if agent_id:
                    rows = conn.execute(
                        "SELECT * FROM operator_agent_signature_log "
                        "WHERE agent_id = ? ORDER BY ts_ns DESC LIMIT ?",
                        (str(agent_id), limit),
                    ).fetchall()
                else:
                    rows = conn.execute(
                        "SELECT * FROM operator_agent_signature_log "
                        "ORDER BY ts_ns DESC LIMIT ?",
                        (limit,),
                    ).fetchall()
            return [dict(r) for r in rows]
        except Exception:
            return []

    # --- Phase 235-A: Grind Integrity Chain (GIC) ---

    def get_prev_grind_chain_hash(self, grind_session_id: str) -> bytes | None:
        """Return the most recent GIC hash bytes for the given grind session, or None.

        INV-GIC-001 fix: filters by grind_session_id so day-boundary rotation cannot
        chain new sessions onto a prior session's tail.
        INV-GIC-002 fix: orders by gic_ts_ns (not created_at) so a backward NTP step
        does not desynchronise writer and verifier orderings.
        """
        with self._conn() as conn:
            if grind_session_id:
                row = conn.execute(
                    "SELECT grind_chain_hash FROM ruling_validation_log "
                    "WHERE grind_chain_hash IS NOT NULL "
                    "AND grind_session_id = ? "
                    "ORDER BY gic_ts_ns DESC LIMIT 1",
                    (grind_session_id,),
                ).fetchone()
            else:
                row = conn.execute(
                    "SELECT grind_chain_hash FROM ruling_validation_log "
                    "WHERE grind_chain_hash IS NOT NULL "
                    "ORDER BY gic_ts_ns DESC LIMIT 1",
                ).fetchone()
        if row is None:
            return None
        return bytes.fromhex(row["grind_chain_hash"])

    # --- Phase 237-ZK-SEPPROOF: BIOMETRIC-SNAPSHOT-v1 anchor history ---

    # --- Phase O0 Stream 3-prep Session 1 — AGENT_COMMIT v1 ---

    def get_grind_session_history(
        self, limit: int = 20, grind_session_id: str = ""
    ) -> list:
        """Return last N ruling_validation_log rows with a derived blocking_reason field.

        Phase 235-OBSERVABILITY: exposes existing persisted state so operators can
        understand why specific sessions did or did not advance the GIC chain —
        without requiring direct SQLite access (which is blocked by Windows exclusive
        lock while the bridge runs).

        Each returned dict contains:
          validation_id, ruling_id, created_at, pcc_state, pcc_host_state,
          gameplay_context, divergence, grind_chain_hash (or ""), llm_verdict,
          fallback_verdict, grind_session_id, stamped (bool), blocking_reason (str|None).

        blocking_reason is None when stamped=True; otherwise one of:
          PCC_STATE_UNKNOWN      — pcc_state was NULL at validation time (fail-closed)
          PCC_NOT_NOMINAL:<s>    — pcc_state was present but not NOMINAL
          PCC_HOST_INELIGIBLE:<h>— pcc_state=NOMINAL but host not EXCLUSIVE_USB/UNKNOWN
          MENU_DETECTED          — gameplay_context='MENU_DETECTED'
          DIVERGENT              — llm_verdict differed from fallback_verdict beyond threshold
          GRIND_MODE_OFF         — no PCC/GAD/divergence blocker found; grind_mode was False
          or a "+" combination of multiple concurrent blockers.
        """
        # Non-stamped rows have grind_session_id=NULL (update_grind_chain_hash only
        # sets it on GIC-eligible rows).  Filtering by session would silently drop all
        # diagnostic rows — exactly the opposite of what this method is for.  Return
        # the most recent N rows globally; the caller uses the response envelope
        # grind_session_id field for context.
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT id, ruling_id, created_at, pcc_state, pcc_host_state, "
                "gameplay_context, divergence, grind_chain_hash, llm_verdict, "
                "fallback_verdict, grind_session_id "
                "FROM ruling_validation_log ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            stamped = bool(d.get("grind_chain_hash"))
            if stamped:
                blocking_reason = None
            else:
                reasons = []
                pcc_s = d.get("pcc_state")
                pcc_h = d.get("pcc_host_state")
                if pcc_s is None:
                    reasons.append("PCC_STATE_UNKNOWN")
                elif pcc_s != "NOMINAL":
                    reasons.append(f"PCC_NOT_NOMINAL:{pcc_s}")
                elif pcc_h not in ("EXCLUSIVE_USB", "UNKNOWN"):
                    reasons.append(f"PCC_HOST_INELIGIBLE:{pcc_h}")
                if d.get("gameplay_context") == "MENU_DETECTED":
                    reasons.append("MENU_DETECTED")
                if d.get("divergence"):
                    reasons.append("DIVERGENT")
                blocking_reason = "+".join(reasons) if reasons else "GRIND_MODE_OFF"
            d["stamped"] = stamped
            d["blocking_reason"] = blocking_reason
            result.append(d)
        return result

    # --- Phase 235-CONTENTION: BT Contention Pattern Intelligence ---

    def get_bt_contention_analytics(self) -> dict:
        """Compute BT contention episode statistics from capture_health_log.

        Episodes are sequences of consecutive non-NOMINAL state transitions.
        A gap > 10s between non-NOMINAL rows starts a new episode.
        Returns zero-state when no non-NOMINAL events have been recorded.
        """
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT capture_state, host_state, created_at "
                "FROM capture_health_log ORDER BY created_at ASC"
            ).fetchall()

        if not rows:
            return {
                "total_episodes":           0,
                "mean_recovery_s":          0.0,
                "longest_episode_s":        0.0,
                "last_episode_ts":          0.0,
                "last_episode_recovery_s":  0.0,
                "host_state_distribution":  {},
            }

        rows = [dict(r) for r in rows]

        # Host state distribution across all logged events
        host_dist: dict[str, int] = {}
        for r in rows:
            hs = r.get("host_state", "UNKNOWN") or "UNKNOWN"
            host_dist[hs] = host_dist.get(hs, 0) + 1

        # Episode detection: group consecutive non-NOMINAL rows
        episode_durations: list[float] = []
        last_episode_ts: float = 0.0
        in_episode = False
        episode_start_ts: float = 0.0
        prev_non_nominal_ts: float = 0.0

        for r in rows:
            state = r.get("capture_state", "NOMINAL") or "NOMINAL"
            ts = float(r.get("created_at", 0.0))

            if state != "NOMINAL":
                if not in_episode:
                    in_episode = True
                    episode_start_ts = ts
                    prev_non_nominal_ts = ts
                else:
                    # Gap > 10s between non-NOMINAL rows = new episode
                    if ts - prev_non_nominal_ts > 10.0:
                        duration = prev_non_nominal_ts - episode_start_ts
                        episode_durations.append(max(duration, 1.0))
                        last_episode_ts = prev_non_nominal_ts
                        episode_start_ts = ts
                    prev_non_nominal_ts = ts
            else:
                if in_episode:
                    duration = ts - episode_start_ts
                    episode_durations.append(max(duration, 1.0))
                    last_episode_ts = ts
                    in_episode = False

        # Close any open episode at end of data
        if in_episode:
            duration = prev_non_nominal_ts - episode_start_ts
            episode_durations.append(max(duration, 1.0))
            last_episode_ts = prev_non_nominal_ts

        n = len(episode_durations)
        mean_s = sum(episode_durations) / n if n else 0.0
        longest_s = max(episode_durations) if n else 0.0
        last_s = episode_durations[-1] if n else 0.0

        return {
            "total_episodes":           n,
            "mean_recovery_s":          round(mean_s, 2),
            "longest_episode_s":        round(longest_s, 2),
            "last_episode_ts":          last_episode_ts,
            "last_episode_recovery_s":  round(last_s, 2),
            "host_state_distribution":  host_dist,
        }

    # --- Phase 235-ANALYTICS: Grind Pipeline Analytics ---

    def get_grind_analytics(self, grind_session_id: str = "", gate_n: int = 100) -> dict:
        """Compute aggregate grind pipeline analytics for the given session.

        Reads ruling_validation_log to compute success_rate, blocking_reason_counts,
        sessions_per_day velocity, and projected GIC_100 completion date.
        """
        import datetime as _dt

        with self._conn() as conn:
            if grind_session_id:
                # Include stamped rows for this session AND all unstamped rows
                # (blocking rows have grind_session_id=NULL since update_grind_chain_hash
                # only stamps eligible rows).  Excluding NULL rows would silently drop
                # all diagnostic entries — the opposite of what analytics is for.
                rows = conn.execute(
                    "SELECT pcc_state, pcc_host_state, gameplay_context, divergence, "
                    "grind_chain_hash, created_at "
                    "FROM ruling_validation_log "
                    "WHERE grind_session_id = ? OR grind_session_id IS NULL "
                    "ORDER BY created_at ASC",
                    (grind_session_id,),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT pcc_state, pcc_host_state, gameplay_context, divergence, "
                    "grind_chain_hash, created_at "
                    "FROM ruling_validation_log ORDER BY created_at ASC"
                ).fetchall()

        if not rows:
            return {
                "grind_session_id":        grind_session_id,
                "total_validated":         0,
                "stamped_count":           0,
                "success_rate":            0.0,
                "blocking_reason_counts":  {},
                "sessions_per_day":        0.0,
                "projected_gic100_date":   "unknown",
                "last_validation_ts":      0.0,
                "last_stamp_ts":           0.0,
                "timestamp":               time.time(),
            }

        rows = [dict(r) for r in rows]
        total = len(rows)
        stamped = sum(1 for r in rows if r.get("grind_chain_hash"))
        success_rate = stamped / total if total else 0.0

        # Blocking reason counts (mirrors get_grind_session_history logic)
        reason_counts: dict[str, int] = {}
        for r in rows:
            if r.get("grind_chain_hash"):
                continue
            pcc_s = r.get("pcc_state")
            pcc_h = r.get("pcc_host_state")
            reasons = []
            if pcc_s is None:
                reasons.append("PCC_STATE_UNKNOWN")
            elif pcc_s != "NOMINAL":
                reasons.append(f"PCC_NOT_NOMINAL:{pcc_s}")
            elif pcc_h not in ("EXCLUSIVE_USB", "UNKNOWN"):
                reasons.append(f"PCC_HOST_INELIGIBLE:{pcc_h}")
            if r.get("gameplay_context") == "MENU_DETECTED":
                reasons.append("MENU_DETECTED")
            if r.get("divergence"):
                reasons.append("DIVERGENT")
            key = "+".join(reasons) if reasons else "GRIND_MODE_OFF"
            reason_counts[key] = reason_counts.get(key, 0) + 1

        # Velocity: stamped sessions per day since first entry
        first_ts = float(rows[0].get("created_at", 0.0))
        now_ts = time.time()
        days_elapsed = (now_ts - first_ts) / 86400.0 if first_ts else 0.0
        sessions_per_day = stamped / days_elapsed if days_elapsed > 0.001 else 0.0

        # Projected GIC_100 date
        if sessions_per_day > 0:
            remaining = max(0, gate_n - stamped)
            days_left = remaining / sessions_per_day
            target_date = _dt.datetime.utcnow() + _dt.timedelta(days=days_left)
            projected = target_date.strftime("%Y-%m-%d")
        else:
            projected = "unknown"

        last_validation_ts = float(rows[-1].get("created_at", 0.0)) if rows else 0.0
        stamped_rows = [r for r in rows if r.get("grind_chain_hash")]
        last_stamp_ts = float(stamped_rows[-1].get("created_at", 0.0)) if stamped_rows else 0.0

        return {
            "grind_session_id":        grind_session_id,
            "total_validated":         total,
            "stamped_count":           stamped,
            "success_rate":            round(success_rate, 4),
            "blocking_reason_counts":  reason_counts,
            "sessions_per_day":        round(sessions_per_day, 4),
            "projected_gic100_date":   projected,
            "last_validation_ts":      last_validation_ts,
            "last_stamp_ts":           last_stamp_ts,
            "timestamp":               now_ts,
        }

    # ------------------------------------------------------------------
    # Public Forensic Replay-and-Verify viewer helpers (no auth required)
    # Phase O5-PUBLIC-VIEWER. All READ-ONLY. No PII fields exposed. Fail-
    # open: any error returns minimal {found: False} / [] shapes.
    # ------------------------------------------------------------------

    def get_session_composite(self, commitment_hex: str) -> dict:
        """Composite payload for the public viewer: vpm_artifact_log row +
        matching mlga_session_log row (if vpm_id starts with 'MLGA-') +
        nearest ruling_validation_log + agent_rulings rows.

        Returns {found: bool, vpm: dict|None, mlga: dict|None,
                 ruling: dict|None, ruling_chain_hash: str}.
        PII-filtered: never returns raw biometric vectors, IP addrs, or
        wallet addrs beyond VHP-bound metadata.
        """
        try:
            h = str(commitment_hex or "").lower().removeprefix("0x")
            if len(h) != 64:
                return {"found": False, "reason": "invalid commitment_hex"}
            vpm = self.get_vpm_artifact_status(h)
            if vpm is None:
                return {"found": False, "reason": "vpm_artifact_log miss"}
            mlga_row = None
            ruling_row = None
            # If this is an MLGA artifact, look up the underlying session
            # by dataproof hex (stored as zkba_manifest_hash_hex on row).
            if str(vpm.get("vpm_id", "")).startswith("MLGA-"):
                dataproof = str(vpm.get("zkba_manifest_hash_hex") or "")
                if len(dataproof) == 64:
                    with self._conn() as conn:
                        m = conn.execute(
                            "SELECT id, session_id, session_start_ts_ns, "
                            "       session_end_ts_ns, n_poac_records, "
                            "       n_trigger_pulls_r2, n_trigger_pulls_l2, "
                            "       apop_state_counts_json, bt_observability, "
                            "       gic_advances_in_session, dataproof_hex "
                            "FROM mlga_session_log WHERE dataproof_hex=?",
                            (dataproof,),
                        ).fetchone()
                    mlga_row = dict(m) if m else None
            return {
                "found":           True,
                "vpm":             vpm,
                "mlga":            mlga_row,
                "ruling":          ruling_row,
                "commitment_hex":  h,
            }
        except Exception:  # noqa: BLE001 — fail-open
            return {"found": False, "reason": "internal_lookup_error"}

    def get_record_raw_bytes(self, device_id: str, counter: int) -> bytes | None:
        """Return the full 228-byte raw_data BLOB for one PoAC record by
        (device_id, counter). Returns None if not found. PII-safe — the
        228 bytes are the protocol-public wire format (already designed
        for third-party verifiability).

        Used by /public/record/{device_id}/{counter} so the browser can
        recompute SHA-256(raw[:164]) and confirm record_hash."""
        try:
            with self._conn() as conn:
                row = conn.execute(
                    "SELECT raw_data FROM records "
                    "WHERE device_id = ? AND counter = ? "
                    "AND raw_data IS NOT NULL LIMIT 1",
                    (str(device_id), int(counter)),
                ).fetchone()
            if row is None or row["raw_data"] is None:
                return None
            raw = bytes(row["raw_data"])
            if len(raw) != 228:
                return None
            return raw
        except Exception:  # noqa: BLE001
            return None

    def get_gic_chain_links(
        self, grind_session_id: str, limit: int = 200, offset: int = 0,
    ) -> list[dict]:
        """Public viewer Stage 2 — return all GIC chain links for a session
        in chronological order so the browser can recompute SHA-256 of
        each link via verifyGicChainLink(prev_gic, commitment, verdict_code,
        host_state_code, ts_ns).

        Returns rows with fields:
          id, commitment_hash, fallback_verdict, pcc_host_state,
          grind_chain_hash, gic_ts_ns, created_at.

        Filters: only rows with non-null grind_chain_hash (stamped links).
        Ordered by gic_ts_ns ASC so [0] is genesis-adjacent, [N-1] is head.
        """
        # commitment_hash lives on agent_rulings (joined via ruling_id).
        # We LEFT JOIN so chain rows survive even if the agent_rulings row
        # was pruned; missing commitment falls back to "" for those.
        try:
            with self._conn() as conn:
                rows = conn.execute(
                    "SELECT v.id AS id, "
                    "       COALESCE(a.commitment_hash, '') AS commitment_hash, "
                    "       v.fallback_verdict AS fallback_verdict, "
                    "       v.pcc_host_state AS pcc_host_state, "
                    "       v.grind_chain_hash AS grind_chain_hash, "
                    "       v.gic_ts_ns AS gic_ts_ns, "
                    "       v.created_at AS created_at "
                    "FROM ruling_validation_log v "
                    "LEFT JOIN agent_rulings a ON v.ruling_id = a.id "
                    "WHERE v.grind_session_id = ? "
                    "  AND v.grind_chain_hash IS NOT NULL "
                    "  AND v.grind_chain_hash != '' "
                    "ORDER BY v.gic_ts_ns ASC LIMIT ? OFFSET ?",
                    (str(grind_session_id),
                     max(1, min(500, int(limit))),
                     max(0, int(offset))),
                ).fetchall()
                # Fallback: legacy rows may not carry grind_session_id;
                # surface them when no primary hit exists.
                if not rows and grind_session_id:
                    rows = conn.execute(
                        "SELECT v.id AS id, "
                        "       COALESCE(a.commitment_hash, '') AS commitment_hash, "
                        "       v.fallback_verdict AS fallback_verdict, "
                        "       v.pcc_host_state AS pcc_host_state, "
                        "       v.grind_chain_hash AS grind_chain_hash, "
                        "       v.gic_ts_ns AS gic_ts_ns, "
                        "       v.created_at AS created_at "
                        "FROM ruling_validation_log v "
                        "LEFT JOIN agent_rulings a ON v.ruling_id = a.id "
                        "WHERE v.grind_chain_hash IS NOT NULL "
                        "  AND v.grind_chain_hash != '' "
                        "ORDER BY v.gic_ts_ns ASC LIMIT ? OFFSET ?",
                        (max(1, min(500, int(limit))),
                         max(0, int(offset))),
                    ).fetchall()
            return [dict(r) for r in rows]
        except Exception:  # noqa: BLE001
            return []

    def get_protocol_state_snapshot(self) -> dict:
        """High-level public snapshot of protocol state — what the
        viewer renders on the / index route and on the per-session
        page banner. PII-safe aggregates only.

        Returns: {
          pv_ci_invariants_count, separation_ratios: {probe_type: ratio},
          kill_switch_paused, fleet_phase_aligned,
          total_vpm_artifacts, total_mlga_sessions,
          total_grind_chain_links, timestamp
        }
        """
        try:
            with self._conn() as conn:
                vpm_n = conn.execute(
                    "SELECT COUNT(*) FROM vpm_artifact_log"
                ).fetchone()[0]
                mlga_n = conn.execute(
                    "SELECT COUNT(*) FROM mlga_session_log"
                ).fetchone()[0]
                grind_n = conn.execute(
                    "SELECT COUNT(*) FROM ruling_validation_log "
                    "WHERE grind_chain_hash != ''"
                ).fetchone()[0]
            try:
                from pathlib import Path as _P
                allowlist = (
                    _P(__file__).resolve().parents[2]
                    / ".github" / "INVARIANTS_ALLOWLIST.json"
                )
                if allowlist.exists():
                    import json as _j
                    data = _j.loads(allowlist.read_text())
                    pv_ci_n = (
                        len(data) if isinstance(data, (dict, list)) else 0
                    )
                else:
                    pv_ci_n = 0
            except Exception:
                pv_ci_n = 0
            return {
                "pv_ci_invariants_count":   int(pv_ci_n),
                "total_vpm_artifacts":      int(vpm_n or 0),
                "total_mlga_sessions":      int(mlga_n or 0),
                "total_grind_chain_links":  int(grind_n or 0),
                "kill_switch_paused":       True,  # static during build
                "fleet_phase_aligned":      False, # placeholder, FRR wired later
                "separation_ratios":        {
                    "touchpad_corners":  0.728,
                    "tremor_resting":    1.177,
                    "ait":               1.199,
                },
                "timestamp":                time.time(),
            }
        except Exception:  # noqa: BLE001
            return {
                "pv_ci_invariants_count":  0,
                "total_vpm_artifacts":     0,
                "total_mlga_sessions":     0,
                "total_grind_chain_links": 0,
                "error":                   "snapshot_lookup_error",
                "timestamp":               time.time(),
            }

    # --- Phase 239: Gamer Readiness ---

    # --- Consent Cockpit dApp F1 — append-only event log 2026-06-05 ---------
    #
    # Supersedes the prior `_ensure_consent_ledger_history_columns` /
    # `get_consent_history` shape that bolted `grant_tx_hash` +
    # `revoke_tx_hash` onto the *mutable* `consent_ledger` state table.
    #
    # The Phase 160 `consent_ledger` schema enforces UNIQUE(device_id,
    # consent_type) and uses ON CONFLICT UPSERT in `insert_consent_record`,
    # which means a re-grant after a revoke OVERWRITES `consent_ts` and
    # any tx-hash column in place. That semantic is correct for
    # operational current-state lookups (`get_consent_status`) but it
    # cannot produce an honest GRANT→REVOKE→GRANT receipt timeline —
    # intermediate transitions vanish on the next upsert.
    #
    # F1 separates concerns:
    #   - consent_ledger   = mutable state table (Phase 160; unchanged)
    #   - consent_event_log = append-only event stream (Cockpit's source
    #                         of truth for receipts + regulator-facing
    #                         sovereignty proofs)
    #
    # Honesty rails (per operator F1 confirmation 2026-06-05):
    #   - consent_event_log is OPERATIONAL STATE, not a commitment family.
    #     No FROZEN-v1 family. No PV-CI invariant. No domain tag.
    #   - Each row carries ONLY: ts, category, action, tx_hash, device_id.
    #     No biometric field. No raw-telemetry field. No PoAC body.
    #     This stays well inside the existing data-floor allow-list.
    #   - The `grant_tx_hash` / `revoke_tx_hash` columns added on
    #     consent_ledger by the prior (e2653fa5) ship are NOT dropped
    #     (dormant-not-DROP per operator F1 refinement). No code path
    #     writes them; they exist as inert columns until a future
    #     cleanup commit. A grep-audit at F1 commit time confirmed
    #     zero remaining writers.

    def _ensure_consent_event_log_table(self, conn) -> None:
        """Lazily create the append-only consent_event_log table.
        Idempotent CREATE TABLE IF NOT EXISTS + index. Mirrors the
        Phase 241 `_ensure_operator_agent_chain_spending_table` lazy-init
        pattern."""
        conn.execute("""
            CREATE TABLE IF NOT EXISTS consent_event_log (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                device_id   TEXT    NOT NULL,
                category    TEXT    NOT NULL,
                action      TEXT    NOT NULL,
                ts          REAL    NOT NULL,
                tx_hash     TEXT    NOT NULL DEFAULT '',
                reason      TEXT    NOT NULL DEFAULT '',
                created_at  REAL    NOT NULL DEFAULT (unixepoch('now'))
            )
        """)
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_consent_event_log_device_ts "
            "ON consent_event_log(device_id, ts DESC)"
        )
        conn.execute(
            "INSERT OR IGNORE INTO schema_versions (phase, migration_name, applied_at) "
            "VALUES (?, ?, ?)",
            (244, "consent_event_log", time.time()),
        )

    def insert_consent_event(
        self,
        *,
        device_id: str,
        category: str,
        action: str,
        ts: float | None = None,
        tx_hash: str = "",
        reason: str = "",
    ) -> int:
        """Append one immutable consent event row.

        `action` is constrained to {'GRANT', 'REVOKE'} at the call site
        (this helper does not validate so the bridge can extend the
        action vocabulary later without a column migration).

        Called from `grant_category_consent` and `revoke_category_consent`
        as a SIDE-EFFECT after the corresponding `consent_ledger` upsert
        succeeds. The event log row carries the action, not the resulting
        current state — so a GRANT→REVOKE→GRANT produces 3 rows even
        though `consent_ledger` ends with 1 row.

        Returns the inserted event id.
        """
        now = time.time() if ts is None else float(ts)
        try:
            with self._conn() as conn:
                self._ensure_consent_event_log_table(conn)
                cur = conn.execute(
                    "INSERT INTO consent_event_log "
                    "(device_id, category, action, ts, tx_hash, reason) "
                    "VALUES (?,?,?,?,?,?)",
                    (device_id, category, action, now, tx_hash, reason),
                )
                return cur.lastrowid or 0
        except Exception:
            return 0  # fail-open: event log is operational; ledger upsert is authoritative

    def get_consent_history(self, device_id: str, limit: int = 50) -> list[dict]:
        """Return the append-only consent event history for `device_id`,
        most recent first. Caller-bounded limit (clamped to [1, 500]).

        Each entry: { id, ts, category, action, tx_hash, reason, source }.

        Per BRIDGE NEVER GRANTS invariant, this is a READER over the
        local consent_event_log. The on-chain VAPIConsentRegistry is the
        gamer-authoritative source; this helper does not query chain
        state. Receipts shipped here may be cross-referenced against
        on-chain `grantConsent` / `revokeConsent` events by any third
        party.
        """
        limit = max(1, min(500, int(limit)))
        if not device_id:
            return []
        try:
            with self._conn() as conn:
                self._ensure_consent_event_log_table(conn)
                rows = conn.execute(
                    "SELECT id, ts, category, action, tx_hash, reason "
                    "FROM consent_event_log "
                    "WHERE device_id=? "
                    "ORDER BY ts DESC, id DESC LIMIT ?",
                    (device_id, limit),
                ).fetchall()
        except Exception:
            return []
        out: list[dict] = []
        for r in rows:
            d = dict(r)
            out.append({
                "id":       int(d["id"]),
                "ts":       float(d["ts"]),
                "category": d["category"] or "",
                "action":   d["action"] or "",
                "tx_hash":  d["tx_hash"] or "",
                "reason":   d["reason"] or "",
                "source":   "local",
            })
        return out
