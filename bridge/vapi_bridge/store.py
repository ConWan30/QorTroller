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

from .codec import PoACRecord

log = logging.getLogger(__name__)

# Record submission status
STATUS_PENDING = "pending"
STATUS_BATCHED = "batched"
STATUS_SUBMITTED = "submitted"
STATUS_VERIFIED = "verified"
STATUS_FAILED = "failed"
STATUS_DEAD_LETTER = "dead_letter"


class Store:
    """SQLite-backed persistence for the bridge service."""

    def __init__(self, db_path: str, consent_ledger_enabled: bool = False) -> None:
        self._db_path = db_path
        self._consent_ledger_enabled = consent_ledger_enabled
        # INV-GIC-003: fail-closed flag — set by main.py startup chain check;
        # read by get_validation_summary() and session_adjudicator_validator.
        self._gic_chain_broken: bool = False
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()
        from .migrations.runner import MigrationRunner; MigrationRunner(db_path).run_pending()  # VAPI-EXT

    def set_gic_chain_broken(self, value: bool) -> None:
        """Set the GIC chain-broken flag (INV-GIC-003).  Called by main.py at startup
        and by /operator/gic-reset.  When True, get_validation_summary() returns
        gate_passed=False / consecutive_clean=0 regardless of DB state."""
        self._gic_chain_broken = bool(value)

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
                    pass  # column already exists — safe to ignore
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
                    pass  # Column already exists
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
                pass  # Column already exists
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
                pass  # Column already exists (Phase 157 migration already applied)
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
                pass  # column already exists
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
                pass  # Column already exists on upgraded DBs — safe to ignore
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
                pass  # Column already exists
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
                pass  # Column already exists — no-op
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
            pass

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
            pass

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

    def get_last_phg_checkpoint(self, device_id: str) -> dict | None:
        """Return the most recently *confirmed* PHG checkpoint for a device, or None.

        Phase 25: filters to confirmed=1 only so unconfirmed checkpoints are never
        used as the cumulative-score delta baseline.
        """
        with self._conn() as conn:
            row = conn.execute("""
                SELECT * FROM phg_checkpoints
                WHERE device_id = ? AND confirmed = 1
                ORDER BY id DESC
                LIMIT 1
            """, (device_id,)).fetchone()
            return dict(row) if row else None

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

    def store_phg_checkpoint(
        self,
        device_id: str,
        phg_score: int,
        record_count: int,
        bio_hash_hex: str,
        tx_hash: str,
        cumulative_score: int = 0,
        confirmed: bool = False,
    ):
        """Persist a committed PHG checkpoint for dashboard display.

        cumulative_score is the true cumulative PHG score at the time of commit.
        It is written to last_committed_score so that future delta calculations
        read the correct cumulative baseline (not the previous delta).
        confirmed=True when the transaction receipt status==1 was observed.
        """
        with self._conn() as conn:
            conn.execute("""
                INSERT OR IGNORE INTO phg_checkpoints
                    (device_id, phg_score, record_count, bio_hash, tx_hash, committed_at,
                     last_committed_score, confirmed)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (device_id, phg_score, record_count, bio_hash_hex, tx_hash, time.time(),
                  cumulative_score, int(confirmed)))

    def get_phg_checkpoints(self, device_id: str, limit: int = 20) -> list[dict]:
        """Return the most recent PHG checkpoints for a device."""
        with self._conn() as conn:
            rows = conn.execute("""
                SELECT * FROM phg_checkpoints
                WHERE device_id = ?
                ORDER BY committed_at DESC
                LIMIT ?
            """, (device_id, limit)).fetchall()
            return [dict(r) for r in rows]

    def mark_checkpoint_confirmed(self, tx_hash: str) -> None:
        """Mark a PHG checkpoint as confirmed by on-chain event (Phase 25)."""
        with self._conn() as conn:
            conn.execute(
                "UPDATE phg_checkpoints SET confirmed = 1 WHERE tx_hash = ?",
                (tx_hash,),
            )

    def get_unconfirmed_checkpoints(self, age_s: float = 300.0) -> list[dict]:
        """Return PHG checkpoints that are older than age_s seconds and still unconfirmed (Phase 25)."""
        cutoff = time.time() - age_s
        with self._conn() as conn:
            rows = conn.execute("""
                SELECT * FROM phg_checkpoints
                WHERE confirmed = 0 AND committed_at < ?
                ORDER BY committed_at ASC
            """, (cutoff,)).fetchall()
            return [dict(r) for r in rows]

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

    def store_fingerprint_state(
        self,
        device_id: str,
        mean_dict: dict,
        var_dict: dict,
        n_sessions: int,
    ):
        """Persist the classifier's mean and variance arrays for cross-session distance computation."""
        with self._conn() as conn:
            conn.execute("""
                INSERT INTO biometric_fingerprint_store
                    (device_id, mean_json, var_json, n_sessions, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(device_id) DO UPDATE SET
                    mean_json  = excluded.mean_json,
                    var_json   = excluded.var_json,
                    n_sessions = excluded.n_sessions,
                    updated_at = excluded.updated_at
            """, (
                device_id,
                json.dumps(mean_dict, sort_keys=True),
                json.dumps(var_dict, sort_keys=True),
                n_sessions,
                time.time(),
            ))

    def get_fingerprint_variance(self, device_id: str):
        """Return the stored variance vector as a numpy array, or None if not available.

        Returns numpy ndarray of shape (7,) in FEATURE_KEYS canonical order, or None.
        """
        with self._conn() as conn:
            row = conn.execute(
                "SELECT var_json FROM biometric_fingerprint_store WHERE device_id = ?",
                (device_id,),
            ).fetchone()
        if row is None:
            return None
        try:
            import numpy as np
            from .continuity_prover import FEATURE_KEYS
            var_dict = json.loads(row["var_json"])
            # Return values in canonical FEATURE_KEYS order so the vector aligns with
            # the distance computation in ContinuityProver.compute_distance().
            return np.array([var_dict.get(k, 0.0) for k in FEATURE_KEYS], dtype=np.float64)
        except Exception:
            return None

    def mark_device_claimed(self, device_id: str, claimed_by: str):
        """Record that a device has been used in a continuity claim (anti-replay)."""
        with self._conn() as conn:
            conn.execute("""
                INSERT OR IGNORE INTO continuity_claims (device_id, claimed_by, claimed_at)
                VALUES (?, ?, ?)
            """, (device_id, claimed_by, time.time()))

    def is_device_claimed(self, device_id: str) -> bool:
        """Return True if this device has already been used in a continuity claim."""
        with self._conn() as conn:
            row = conn.execute(
                "SELECT 1 FROM continuity_claims WHERE device_id = ?", (device_id,)
            ).fetchone()
            return row is not None

    def get_continuity_chain(self, device_id: str) -> list[dict]:
        """Return all continuity claim records involving this device (as source or destination).

        Each entry: {device_id, claimed_by, claimed_at, direction}
        direction = "source" if this device was the old device; "destination" if the new one.
        """
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM continuity_claims WHERE device_id = ? OR claimed_by = ?",
                (device_id, device_id),
            ).fetchall()
            result = []
            for row in rows:
                entry = dict(row)
                entry["direction"] = "source" if entry["claimed_by"] != device_id else "destination"
                result.append(entry)
            return result

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

    def get_all_fingerprinted_devices(self) -> list[str]:
        """Return device IDs that have a stored biometric fingerprint."""
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT device_id FROM biometric_fingerprint_store"
            ).fetchall()
            return [r["device_id"] for r in rows]

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

    def store_credential_mint(
        self, device_id: str, credential_id: int, tx_hash: str
    ) -> None:
        """Record a successfully minted PHGCredential. INSERT OR IGNORE (idempotent)."""
        with self._conn() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO phg_credential_mints "
                "(device_id, credential_id, tx_hash, minted_at) VALUES (?,?,?,?)",
                (device_id, credential_id, tx_hash, time.time()),
            )

    def get_credential_mint(self, device_id: str) -> dict | None:
        """Return credential mint record for device, or None if not minted (Phase 28)."""
        with self._conn() as conn:
            row = conn.execute(
                "SELECT device_id, credential_id, tx_hash, minted_at "
                "FROM phg_credential_mints WHERE device_id=?", (device_id,)
            ).fetchone()
        return dict(row) if row else None

    # --- Phase 62: Player Enrollment Ceremony ---

    def upsert_enrollment(
        self,
        device_id: str,
        sessions_nominal: int,
        sessions_total: int,
        avg_humanity: float,
        status: str,
        tx_hash: str = "",
    ) -> None:
        """Insert or update enrollment progress for a device. Idempotent."""
        now = time.time()
        with self._conn() as conn:
            conn.execute("""
                INSERT INTO device_enrollments
                    (device_id, sessions_nominal, sessions_total, avg_humanity,
                     status, tx_hash, last_updated)
                VALUES (?,?,?,?,?,?,?)
                ON CONFLICT(device_id) DO UPDATE SET
                    sessions_nominal=excluded.sessions_nominal,
                    sessions_total=excluded.sessions_total,
                    avg_humanity=excluded.avg_humanity,
                    status=excluded.status,
                    tx_hash=excluded.tx_hash,
                    eligible_at=CASE WHEN excluded.status='eligible' AND status!='eligible'
                                     THEN ? ELSE eligible_at END,
                    credentialed_at=CASE WHEN excluded.status='credentialed'
                                         THEN ? ELSE credentialed_at END,
                    last_updated=?
            """, (device_id, sessions_nominal, sessions_total, avg_humanity,
                  status, tx_hash, now, now, now, now))

    def get_enrollment(self, device_id: str) -> dict | None:
        """Return enrollment row for device, or None if no row exists."""
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM device_enrollments WHERE device_id=?", (device_id,)
            ).fetchone()
        return dict(row) if row else None

    def get_eligible_unenrolled(self) -> list[dict]:
        """Devices that are eligible but not yet credentialed."""
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM device_enrollments WHERE status='eligible' "
                "ORDER BY eligible_at"
            ).fetchall()
        return [dict(r) for r in rows]

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

    def insert_l6b_probe(
        self,
        device_id: str,
        probe_ts_ms: int,
        latency_ms: float,
        classification: str,
        accel_delta_peak: float,
    ) -> None:
        """Persist one L6b reflex probe result (Phase 63).

        latency_ms=-1.0 indicates NO_RESPONSE (stored as NULL in DB).
        Never raises — caller wraps in try/except.
        """
        _lat = None if latency_ms < 0 else latency_ms
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO l6b_probe_log "
                "(device_id, probe_ts_ms, latency_ms, classification, accel_delta_peak) "
                "VALUES (?, ?, ?, ?, ?)",
                (device_id, probe_ts_ms, _lat, classification, accel_delta_peak),
            )

    def get_l6b_baseline(self, device_id: str) -> dict:
        """Return L6b reflex baseline statistics for a device (Phase 63).

        Returns dict with:
          device_id, probe_count, mean_latency_ms, std_latency_ms,
          classification_distribution (dict[str, int]),
          bot_events (int — count of BOT-classified probes)
        """
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT latency_ms, classification FROM l6b_probe_log WHERE device_id=?",
                (device_id,),
            ).fetchall()
        if not rows:
            return {
                "device_id": device_id,
                "probe_count": 0,
                "mean_latency_ms": None,
                "std_latency_ms": None,
                "classification_distribution": {},
                "bot_events": 0,
            }
        latencies = [float(r["latency_ms"]) for r in rows if r["latency_ms"] is not None]
        dist: dict[str, int] = {}
        for r in rows:
            c = r["classification"]
            dist[c] = dist.get(c, 0) + 1
        mean_lat = sum(latencies) / len(latencies) if latencies else None
        if latencies and len(latencies) > 1:
            var = sum((x - mean_lat) ** 2 for x in latencies) / len(latencies)
            std_lat = var ** 0.5
        else:
            std_lat = None
        return {
            "device_id": device_id,
            "probe_count": len(rows),
            "mean_latency_ms": round(mean_lat, 2) if mean_lat is not None else None,
            "std_latency_ms": round(std_lat, 2) if std_lat is not None else None,
            "classification_distribution": dist,
            "bot_events": dist.get("BOT", 0),
        }

    def get_leaderboard(self, limit: int = 20) -> list[dict]:
        """Return top devices by confirmed cumulative PHG score (Phase 28)."""
        with self._conn() as conn:
            rows = conn.execute("""
                SELECT device_id, MAX(last_committed_score) AS cumulative_score,
                       MAX(record_count) AS record_count
                FROM phg_checkpoints WHERE confirmed = 1
                GROUP BY device_id
                ORDER BY cumulative_score DESC
                LIMIT ?
            """, (limit,)).fetchall()
        return [dict(r) for r in rows]

    def get_leaderboard_rank(self, device_id: str) -> int | None:
        """Return 1-based rank of device in confirmed PHG leaderboard, or None (Phase 29)."""
        board = self.get_leaderboard(limit=10000)
        for i, entry in enumerate(board, start=1):
            if entry["device_id"] == device_id:
                return i
        return None

    # --- Phase 31: BridgeAgent Session Persistence ---

    def store_agent_session(self, session_id: str, history: list[dict]) -> None:
        """Persist BridgeAgent conversation history (Phase 31)."""
        now = time.time()
        with self._conn() as conn:
            conn.execute("""
                INSERT INTO agent_sessions (session_id, history_json, created_at, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(session_id) DO UPDATE SET
                    history_json = excluded.history_json,
                    updated_at   = excluded.updated_at
            """, (session_id, json.dumps(history, default=str), now, now))

    def get_agent_session(self, session_id: str) -> list[dict]:
        """Load BridgeAgent conversation history (Phase 31). Returns [] if not found."""
        with self._conn() as conn:
            row = conn.execute(
                "SELECT history_json FROM agent_sessions WHERE session_id = ?",
                (session_id,),
            ).fetchone()
        if row is None:
            return []
        try:
            return json.loads(row["history_json"])
        except Exception:
            return []

    def delete_agent_session(self, session_id: str) -> None:
        """Remove an agent session from persistent store (Phase 31)."""
        with self._conn() as conn:
            conn.execute(
                "DELETE FROM agent_sessions WHERE session_id = ?", (session_id,)
            )

    # --- Phase 32: Protocol insights ---

    def store_protocol_insight(self, insight_type: str, content: str,
                                device_id: str = "", severity: str = "low") -> None:
        """Persist a proactive alert or anomaly reaction (Phase 32)."""
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO protocol_insights"
                " (insight_type, device_id, content, severity, created_at)"
                " VALUES (?, ?, ?, ?, ?)",
                (insight_type, device_id, content, severity, time.time()),
            )

    def get_recent_insights(self, limit: int = 20) -> list:
        """Return most recent protocol insights DESC by created_at (Phase 32)."""
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT id, insight_type, device_id, content, severity, created_at"
                " FROM protocol_insights ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]

    def prune_old_agent_sessions(self, age_days: float = 30.0) -> int:
        """Delete agent sessions older than age_days. Returns rows deleted (Phase 32)."""
        cutoff = time.time() - age_days * 86400
        with self._conn() as conn:
            cur = conn.execute(
                "DELETE FROM agent_sessions WHERE updated_at < ?", (cutoff,)
            )
        return cur.rowcount

    def prune_old_insights(self, age_days: float = 30.0) -> int:
        """Delete protocol_insights older than age_days. Returns rows deleted (Phase 32)."""
        cutoff = time.time() - age_days * 86400
        with self._conn() as conn:
            cur = conn.execute(
                "DELETE FROM protocol_insights WHERE created_at < ?", (cutoff,)
            )
        return cur.rowcount

    # --- Phase 35: Longitudinal Insight Synthesis ---

    def get_insights_since(self, since: float) -> list:
        """Return all protocol_insights rows created after `since` epoch (Phase 35)."""
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM protocol_insights WHERE created_at >= ? ORDER BY created_at ASC",
                (since,),
            ).fetchall()
        return [dict(r) for r in rows]

    def store_insight_digest(self, window_label: str, bot_farm_count: int,
                              high_risk_count: int, federated_count: int,
                              anomaly_count: int, eligible_count: int,
                              dominant_severity: str, top_devices: list,
                              narrative: str) -> None:
        """Persist a longitudinal insight digest for a time window (Phase 35)."""
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO insight_digests"
                " (window_label, synthesized_at, bot_farm_count, high_risk_count,"
                "  federated_count, anomaly_count, eligible_count, dominant_severity,"
                "  top_devices, narrative)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (window_label, time.time(), bot_farm_count, high_risk_count,
                 federated_count, anomaly_count, eligible_count, dominant_severity,
                 json.dumps(top_devices[:5]), narrative),
            )

    def get_latest_digest(self, window_label: str) -> dict | None:
        """Return most recent insight digest for the given window_label (Phase 35)."""
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM insight_digests WHERE window_label=?"
                " ORDER BY synthesized_at DESC LIMIT 1",
                (window_label,),
            ).fetchone()
        if not row:
            return None
        d = dict(row)
        d["top_devices"] = json.loads(d.get("top_devices", "[]"))
        return d

    def get_all_latest_digests(self) -> list:
        """Return most recent digest for each window_label (Phase 35)."""
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM insight_digests GROUP BY window_label"
                " HAVING synthesized_at = MAX(synthesized_at)"
                " ORDER BY synthesized_at DESC",
            ).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            d["top_devices"] = json.loads(d.get("top_devices", "[]"))
            result.append(d)
        return result

    def set_device_risk_label(self, device_id: str, risk_label: str,
                               label_evidence: dict, prior_label: str = "") -> None:
        """Upsert a per-device risk trajectory label (Phase 35)."""
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO device_risk_labels"
                " (device_id, risk_label, label_evidence, label_set_at, prior_label)"
                " VALUES (?, ?, ?, ?, ?)"
                " ON CONFLICT(device_id) DO UPDATE SET"
                "   risk_label=excluded.risk_label,"
                "   label_evidence=excluded.label_evidence,"
                "   label_set_at=excluded.label_set_at,"
                "   prior_label=excluded.prior_label",
                (device_id, risk_label, json.dumps(label_evidence), time.time(), prior_label),
            )

    def get_device_risk_label(self, device_id: str) -> dict | None:
        """Return the risk trajectory label for a device (Phase 35)."""
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM device_risk_labels WHERE device_id=?", (device_id,)
            ).fetchone()
        if not row:
            return None
        d = dict(row)
        d["label_evidence"] = json.loads(d.get("label_evidence", "{}"))
        return d

    def get_devices_by_risk_label(self, risk_label: str) -> list:
        """Return all devices with the specified risk_label (Phase 35)."""
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM device_risk_labels WHERE risk_label=?"
                " ORDER BY label_set_at DESC",
                (risk_label,),
            ).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            d["label_evidence"] = json.loads(d.get("label_evidence", "{}"))
            result.append(d)
        return result

    def prune_old_digests(self, age_days: float = 90.0) -> int:
        """Delete insight_digests older than age_days. Returns rows deleted (Phase 35)."""
        cutoff = time.time() - age_days * 86400
        with self._conn() as conn:
            cur = conn.execute(
                "DELETE FROM insight_digests WHERE synthesized_at < ?", (cutoff,)
            )
        return cur.rowcount

    # --- Phase 36: Adaptive Detection Policies ---

    def store_detection_policy(self, device_id: str, multiplier: float,
                                basis_label: str, expires_at: float) -> None:
        """Upsert an adaptive PITL threshold multiplier for a device (Phase 36)."""
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO detection_policies"
                " (device_id, multiplier, basis_label, set_at, expires_at)"
                " VALUES (?, ?, ?, ?, ?)"
                " ON CONFLICT(device_id) DO UPDATE SET"
                "   multiplier=excluded.multiplier, basis_label=excluded.basis_label,"
                "   set_at=excluded.set_at, expires_at=excluded.expires_at",
                (device_id, multiplier, basis_label, time.time(), expires_at),
            )

    def get_detection_policy(self, device_id: str) -> dict | None:
        """Return active detection policy for device, or None if none/expired (Phase 36)."""
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM detection_policies WHERE device_id=? AND expires_at > ?",
                (device_id, time.time()),
            ).fetchone()
        return dict(row) if row else None

    def get_all_active_policies(self) -> list:
        """Return all non-expired detection policies ordered by set_at DESC (Phase 36)."""
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM detection_policies WHERE expires_at > ?"
                " ORDER BY set_at DESC",
                (time.time(),),
            ).fetchall()
        return [dict(r) for r in rows]

    def clear_detection_policy(self, device_id: str) -> None:
        """Remove detection policy for a device (Phase 36)."""
        with self._conn() as conn:
            conn.execute(
                "DELETE FROM detection_policies WHERE device_id=?", (device_id,)
            )

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

    def get_credential_enforcement(self, device_id: str) -> dict | None:
        """Return credential enforcement row for a device, or None (Phase 37)."""
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM credential_enforcement WHERE device_id=?", (device_id,)
            ).fetchone()
        return dict(row) if row else None

    def increment_consecutive_critical(self, device_id: str) -> int:
        """Increment consecutive_critical counter for a device; return new count (Phase 37)."""
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO credential_enforcement (device_id, consecutive_critical, last_updated)"
                " VALUES (?, 1, ?)"
                " ON CONFLICT(device_id) DO UPDATE SET"
                "   consecutive_critical = consecutive_critical + 1,"
                "   last_updated = excluded.last_updated",
                (device_id, time.time()),
            )
            row = conn.execute(
                "SELECT consecutive_critical FROM credential_enforcement WHERE device_id=?",
                (device_id,),
            ).fetchone()
        return int(row[0]) if row else 1

    def reset_consecutive_critical(self, device_id: str) -> None:
        """Reset consecutive_critical to 0 for a device (Phase 37)."""
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO credential_enforcement (device_id, consecutive_critical, last_updated)"
                " VALUES (?, 0, ?)"
                " ON CONFLICT(device_id) DO UPDATE SET"
                "   consecutive_critical = 0, last_updated = excluded.last_updated",
                (device_id, time.time()),
            )

    def store_credential_suspension(self, device_id: str,
                                     evidence_hash: str, until: float) -> None:
        """Record a credential suspension in the DB (Phase 37)."""
        now = time.time()
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO credential_enforcement"
                " (device_id, consecutive_critical, suspended, suspended_since,"
                "  suspended_until, evidence_hash, last_updated)"
                " VALUES (?, 0, 1, ?, ?, ?, ?)"
                " ON CONFLICT(device_id) DO UPDATE SET"
                "   suspended=1, suspended_since=excluded.suspended_since,"
                "   suspended_until=excluded.suspended_until,"
                "   evidence_hash=excluded.evidence_hash,"
                "   last_updated=excluded.last_updated",
                (device_id, now, until, evidence_hash, now),
            )

    def is_credential_suspended(self, device_id: str) -> bool:
        """Return True if device has an active credential suspension (Phase 37)."""
        with self._conn() as conn:
            row = conn.execute(
                "SELECT suspended FROM credential_enforcement WHERE device_id=?",
                (device_id,),
            ).fetchone()
        return bool(row[0]) if row else False

    def clear_credential_suspension(self, device_id: str) -> None:
        """Clear suspension state for a device (Phase 37)."""
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO credential_enforcement"
                " (device_id, consecutive_critical, suspended, last_updated)"
                " VALUES (?, 0, 0, ?)"
                " ON CONFLICT(device_id) DO UPDATE SET"
                "   suspended=0, suspended_since=NULL, suspended_until=NULL,"
                "   evidence_hash=NULL, last_updated=excluded.last_updated",
                (device_id, time.time()),
            )

    def get_all_suspended_credentials(self) -> list:
        """Return all currently suspended credential enforcement rows (Phase 37)."""
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM credential_enforcement WHERE suspended=1"
                " ORDER BY suspended_since DESC"
            ).fetchall()
        return [dict(r) for r in rows]

    def get_expired_suspensions(self) -> list[dict]:
        """Return suspended rows whose suspension window has elapsed (Phase 67).

        Used by RulingEnforcementAgent._check_expired_suspensions() to auto-reinstate.
        Only returns rows where suspended=1, suspended_until < now(), reinstated is falsy.
        """
        now = time.time()
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM credential_enforcement"
                " WHERE suspended=1 AND suspended_until IS NOT NULL AND suspended_until < ?"
                " AND (reinstated IS NULL OR reinstated=0)",
                (now,),
            ).fetchall()
        return [dict(r) for r in rows]

    def mark_suspension_reinstated(self, device_id: str) -> None:
        """Mark a device's credential suspension as reinstated (Phase 67)."""
        with self._conn() as conn:
            conn.execute(
                "UPDATE credential_enforcement SET reinstated=1, reinstated_at=? WHERE device_id=?",
                (time.time(), device_id),
            )

    # --- Phase 38: Living calibration (Mode 6) ---

    def get_nominal_records_for_calibration(self, limit: int = 200) -> list[dict]:
        """Fetch warmed NOMINAL records for living calibration (Phase 38).

        Only includes records where inference=32 (NOMINAL) and the L4 classifier
        had warmed up (pitl_l4_warmed=1), ensuring threshold quality.
        Returns newest-first so exponential decay weights index 0 = most recent.
        """
        with self._conn() as conn:
            rows = conn.execute(
                """
                SELECT device_id, pitl_l4_distance, pitl_l5_cv,
                       pitl_humanity_prob, timestamp_ms
                FROM records
                WHERE inference = 32
                  AND pitl_l4_distance IS NOT NULL
                  AND pitl_l4_warmed = 1
                ORDER BY timestamp_ms DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]

    def upsert_player_calibration_profile(
        self,
        device_id: str,
        anomaly_threshold: float,
        continuity_threshold: float,
        baseline_mean: float,
        baseline_std: float,
        session_count: int,
    ) -> None:
        """Insert or replace a per-player calibration profile (Phase 38)."""
        import datetime as _dt
        updated_at = _dt.datetime.now(_dt.timezone.utc).isoformat().replace("+00:00", "Z")
        with self._conn() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO player_calibration_profiles
                    (device_id, anomaly_threshold, continuity_threshold,
                     baseline_mean, baseline_std, session_count, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (device_id, anomaly_threshold, continuity_threshold,
                 baseline_mean, baseline_std, session_count, updated_at),
            )

    def get_player_calibration_profile(self, device_id: str) -> dict | None:
        """Return the per-player calibration profile for a device, or None (Phase 38)."""
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM player_calibration_profiles WHERE device_id = ?",
                (device_id,),
            ).fetchone()
        return dict(row) if row else None

    def get_all_player_calibration_profiles(self) -> list[dict]:
        """Return all per-player calibration profiles (Phase 38)."""
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM player_calibration_profiles ORDER BY updated_at DESC"
            ).fetchall()
        return [dict(r) for r in rows]

    # --- Phase 42: L6 human-response baseline capture ---

    def store_l6_capture(
        self,
        session_id: str,
        profile_id: int,
        profile_name: str,
        challenge_sent_ts: float,
        onset_ms: float,
        settle_ms: float,
        peak_delta: float,
        grip_variance: float,
        r2_pre_mean: float,
        accel_variance: float,
        player_id: str = "",
        game_title: str = "",
        hw_session_ref: str = "",
        notes: str = "",
    ) -> None:
        """Insert one L6 challenge-response record into l6_capture_sessions (Phase 42)."""
        with self._conn() as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO l6_capture_sessions
                    (session_id, profile_id, profile_name, challenge_sent_ts,
                     onset_ms, settle_ms, peak_delta, grip_variance,
                     r2_pre_mean, accel_variance,
                     player_id, game_title, hw_session_ref, notes, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session_id, profile_id, profile_name, challenge_sent_ts,
                    onset_ms, settle_ms, peak_delta, grip_variance,
                    r2_pre_mean, accel_variance,
                    player_id, game_title, hw_session_ref, notes, time.time(),
                ),
            )

    def query_l6_captures(
        self,
        player_id: str = "",
        profile_id: int | None = None,
        limit: int = 0,
    ) -> list[dict]:
        """Return l6_capture_sessions rows, optionally filtered (Phase 42).

        Args:
            player_id:  Filter to this player ('' = all players).
            profile_id: Filter to this profile_id (None = all profiles).
            limit:      Max rows to return (0 = no limit).
        """
        clauses, params = [], []
        if player_id:
            clauses.append("player_id = ?")
            params.append(player_id)
        if profile_id is not None:
            clauses.append("profile_id = ?")
            params.append(profile_id)
        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        limit_clause = f"LIMIT {int(limit)}" if limit > 0 else ""
        sql = f"SELECT * FROM l6_capture_sessions {where} ORDER BY created_at ASC {limit_clause}"
        with self._conn() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]

    def count_l6_captures_by_profile(self, player_id: str = "") -> dict[int, int]:
        """Return {profile_id: count} for captured L6 sessions (Phase 42)."""
        params = []
        where = ""
        if player_id:
            where = "WHERE player_id = ?"
            params.append(player_id)
        sql = f"SELECT profile_id, COUNT(*) as n FROM l6_capture_sessions {where} GROUP BY profile_id"
        with self._conn() as conn:
            rows = conn.execute(sql, params).fetchall()
        return {r["profile_id"]: r["n"] for r in rows}

    # --- Phase 50: Agent coordination methods ---

    def write_agent_event(
        self,
        event_type: str,
        payload: str,
        source: str,
        device_id: str = None,
        target: str = None,
    ) -> int:
        """Insert an agent coordination event (Phase 50). Returns the new event id."""
        now = time.time()
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO agent_events "
                "(event_type, device_id, payload_json, source_agent, target_agent, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (event_type, device_id, payload, source, target, now),
            )
            return cur.lastrowid

    def read_unconsumed_events(self, target_agent: str, limit: int = 50) -> list:
        """Return unconsumed agent events for target_agent (Phase 50)."""
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM agent_events "
                "WHERE target_agent = ? AND consumed_at IS NULL "
                "ORDER BY created_at ASC LIMIT ?",
                (target_agent, limit),
            ).fetchall()
        return [dict(r) for r in rows]

    def mark_event_consumed(self, event_id: int, consumed_by: str) -> None:
        """Mark an agent event as consumed (Phase 50)."""
        with self._conn() as conn:
            conn.execute(
                "UPDATE agent_events SET consumed_at = ?, consumed_by = ? WHERE id = ?",
                (time.time(), consumed_by, event_id),
            )

    def get_last_sbd_fire_ts(self) -> float | None:
        """Return wall-clock created_at of the most recent SBD ruling_request, or None.

        Phase 235-OBSERVABILITY: used by SessionBoundaryDetectorAgent on startup to
        recover last_fire_at so the 300s throttle survives bridge restart.
        """
        with self._conn() as conn:
            row = conn.execute(
                "SELECT created_at FROM agent_events "
                "WHERE event_type='ruling_request' "
                "AND source_agent='session_boundary_detector_agent' "
                "ORDER BY created_at DESC LIMIT 1"
            ).fetchone()
        return float(row["created_at"]) if row else None

    def write_threshold_history(
        self,
        threshold_type: str,
        old_value: float,
        new_value: float,
        drift_pct: float,
        sessions_used: int,
        phase: str,
        device_id: str = None,
    ) -> None:
        """Record a threshold change in history (Phase 50)."""
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO threshold_history "
                "(threshold_type, device_id, old_value, new_value, drift_pct, "
                "sessions_used, phase, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (threshold_type, device_id, old_value, new_value, drift_pct,
                 sessions_used, phase, time.time()),
            )

    def get_threshold_history(self, limit: int = 20) -> list:
        """Return recent threshold history entries desc by created_at (Phase 50)."""
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM threshold_history ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]

    def get_last_global_recalibration_time(self) -> float:
        """Return epoch of last global agent-triggered recalibration, or 0.0 (Phase 50)."""
        with self._conn() as conn:
            row = conn.execute(
                "SELECT MAX(created_at) as ts FROM threshold_history "
                "WHERE threshold_type LIKE 'global%' "
                "AND phase IN ('manual', 'agent_triggered')",
            ).fetchone()
        ts = row["ts"] if (row is not None and row["ts"] is not None) else None
        return float(ts) if ts is not None else 0.0

    def count_records_since_last_calibration(self, device_id: str) -> int:
        """Count records for device_id since last threshold_history entry (Phase 50)."""
        with self._conn() as conn:
            row = conn.execute(
                "SELECT MAX(created_at) as ts FROM threshold_history WHERE device_id = ?",
                (device_id,),
            ).fetchone()
            last_ts = float(row["ts"]) if (row is not None and row["ts"] is not None) else 0.0
            result = conn.execute(
                "SELECT COUNT(*) as n FROM records WHERE device_id = ? AND created_at > ?",
                (device_id, last_ts),
            ).fetchone()
        return int(result["n"]) if result is not None else 0

    def store_calib_agent_session(self, session_id: str, history: list) -> None:
        """Persist CalibrationIntelligenceAgent conversation history (Phase 50)."""
        now = time.time()
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO calibration_agent_sessions (session_id, history_json, updated_at) "
                "VALUES (?, ?, ?) "
                "ON CONFLICT(session_id) DO UPDATE SET "
                "history_json = excluded.history_json, updated_at = excluded.updated_at",
                (session_id, json.dumps(history, default=str), now),
            )

    def load_calib_agent_session(self, session_id: str) -> list:
        """Load CalibrationIntelligenceAgent conversation history (Phase 50)."""
        with self._conn() as conn:
            row = conn.execute(
                "SELECT history_json FROM calibration_agent_sessions WHERE session_id = ?",
                (session_id,),
            ).fetchone()
        if row is None:
            return []
        try:
            return json.loads(row["history_json"])
        except Exception:
            return []

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

    def get_controller_twin_snapshot(self, device_id: str) -> dict:
        """Aggregate all data for the My Controller 3D page (Phase 59)."""
        device   = self.get_device(device_id) or {}
        profile  = self.get_player_calibration_profile(device_id) or {}
        ioid     = self.get_ioid_device(device_id) or {}
        passport = self.get_tournament_passport(device_id) or {}
        audit_log = self.get_operator_audit_log(limit=10, device_id=device_id[:16])
        # Query biometric_fingerprint_store directly (Phase 59)
        with self._conn() as conn:
            _fp_row = conn.execute(
                "SELECT * FROM biometric_fingerprint_store WHERE device_id = ?",
                (device_id,),
            ).fetchone()
            biofp = dict(_fp_row) if _fp_row else {}
            recent = conn.execute(
                "SELECT record_hash, inference, pitl_l4_distance, pitl_humanity_prob, "
                "pitl_l4_features, created_at FROM records "
                "WHERE device_id = ? ORDER BY created_at DESC LIMIT 20",
                (device_id,),
            ).fetchall()
            insight_rows = conn.execute(
                "SELECT content, severity, insight_type, created_at "
                "FROM protocol_insights WHERE device_id = ? "
                "ORDER BY created_at DESC LIMIT 5",
                (device_id,),
            ).fetchall()
        dists = [r["pitl_l4_distance"] for r in recent if r["pitl_l4_distance"] is not None]
        trend = "UNKNOWN"
        if len(dists) >= 4:
            mid = len(dists) // 2
            first_h  = sum(dists[mid:]) / max(len(dists) - mid, 1)
            second_h = sum(dists[:mid]) / mid
            trend = ("DEGRADING" if first_h > second_h * 1.1
                     else "IMPROVING" if first_h < second_h * 0.9 else "STABLE")
        return {
            "device":    dict(device) if device else {},
            "calibration": {
                "anomaly_threshold":    profile.get("anomaly_threshold"),
                "continuity_threshold": profile.get("continuity_threshold"),
                "baseline_mean":        profile.get("baseline_mean"),
                "baseline_std":         profile.get("baseline_std"),
                "session_count":        profile.get("session_count", 0),
            },
            "biometric_fingerprint": {
                "mean_json":  biofp.get("mean_json"),
                "var_json":   biofp.get("var_json"),
                "n_sessions": biofp.get("n_sessions", 0),
            },
            "ioid":     {"registered": bool(ioid), "did": ioid.get("did"), "tx_hash": ioid.get("tx_hash")},
            "passport": {
                "issued": bool(passport),
                "passport_hash": passport.get("passport_hash"),
                "min_humanity_int": passport.get("min_humanity_int"),
                "on_chain": bool(passport.get("on_chain")),
                "issued_at": passport.get("issued_at"),
            },
            "audit_log": audit_log,
            "anomaly_trend": trend,
            "recent_records": [dict(r) for r in recent],
            "insights": [dict(r) for r in insight_rows],
        }

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
    ) -> None:
        """Persist an ioID device registration record (Phase 55)."""
        with self._conn() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO ioid_devices
                    (device_id, device_address, did, tx_hash, registered_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (device_id, device_address, did, tx_hash, time.time()),
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

    def store_tournament_passport(
        self,
        device_id: str,
        passport_hash: str,
        ioid_token_id: int,
        min_humanity_int: int,
        tx_hash: str = "",
        on_chain: bool = False,
    ) -> None:
        """Persist a tournament passport record (Phase 56)."""
        with self._conn() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO tournament_passports
                    (device_id, passport_hash, ioid_token_id, min_humanity_int,
                     tx_hash, on_chain, issued_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    device_id, passport_hash, ioid_token_id, min_humanity_int,
                    tx_hash, 1 if on_chain else 0, time.time(),
                ),
            )

    def get_tournament_passport(self, device_id: str) -> dict | None:
        """Return tournament passport for device_id, or None (Phase 56)."""
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM tournament_passports WHERE device_id = ?",
                (device_id,),
            ).fetchone()
        return dict(row) if row else None

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

    def insert_agent_ruling(
        self,
        device_id: str,
        verdict: str,
        confidence: float,
        reasoning: str,
        evidence_json: str,
        commitment_hash: str,
        attestation_hash: str = "",
        dry_run: bool = True,
        source_agent: str = "session_adjudicator",
        expires_at: float | None = None,
        ceremony_integrity: str | None = None,
    ) -> int:
        """Insert autonomous agent ruling. Returns ruling id.

        Phase 73: optional ceremony_integrity — JSON string from
        VAPIZKProof.verify_ceremony_integrity() stored alongside the ruling for
        cryptographic provenance tracing.
        """
        now = time.time()
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO agent_rulings "
                "(device_id, verdict, confidence, reasoning, evidence_json, "
                "attestation_hash, commitment_hash, dry_run, source_agent, "
                "created_at, expires_at, ceremony_integrity) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (device_id, verdict, confidence, reasoning, evidence_json,
                 attestation_hash, commitment_hash, int(dry_run), source_agent,
                 now, expires_at, ceremony_integrity),
            )
            return cur.lastrowid

    def get_agent_rulings(
        self,
        device_id: str,
        limit: int = 20,
        verdict_filter: str | None = None,
    ) -> list[dict]:
        """Return rulings for device, most recent first. Optional verdict filter."""
        with self._conn() as conn:
            if verdict_filter:
                rows = conn.execute(
                    "SELECT * FROM agent_rulings WHERE device_id=? AND verdict=? "
                    "ORDER BY created_at DESC LIMIT ?",
                    (device_id, verdict_filter, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM agent_rulings WHERE device_id=? "
                    "ORDER BY created_at DESC LIMIT ?",
                    (device_id, limit),
                ).fetchall()
        return [dict(r) for r in rows]

    def get_agent_ruling_by_id(self, ruling_id: int) -> dict | None:
        """Return single ruling by id, or None."""
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM agent_rulings WHERE id=?", (ruling_id,)
            ).fetchone()
        return dict(row) if row else None

    # --- Phase 66: Ruling streaks ---

    def upsert_ruling_streak(self, device_id: str, verdict: str, ruling_id: int) -> dict:
        """Update streak counter. Resets on verdict change. Returns current streak dict."""
        now = time.time()
        with self._conn() as conn:
            existing = conn.execute(
                "SELECT * FROM ruling_streaks WHERE device_id=?", (device_id,)
            ).fetchone()
            if existing and existing["streak_verdict"] == verdict:
                new_count = existing["current_streak"] + 1
                conn.execute(
                    "UPDATE ruling_streaks SET current_streak=?, last_verdict=?, "
                    "last_ruling_id=?, updated_at=? WHERE device_id=?",
                    (new_count, verdict, ruling_id, now, device_id),
                )
            else:
                conn.execute(
                    "INSERT INTO ruling_streaks (device_id, current_streak, streak_verdict, "
                    "streak_start, last_verdict, last_ruling_id, updated_at) VALUES (?,?,?,?,?,?,?) "
                    "ON CONFLICT(device_id) DO UPDATE SET current_streak=excluded.current_streak, "
                    "streak_verdict=excluded.streak_verdict, streak_start=excluded.streak_start, "
                    "last_verdict=excluded.last_verdict, last_ruling_id=excluded.last_ruling_id, "
                    "updated_at=excluded.updated_at",
                    (device_id, 1, verdict, now, verdict, ruling_id, now),
                )
        return self.get_ruling_streak(device_id)

    def get_ruling_streak(self, device_id: str) -> dict | None:
        """Return current streak for device, or None if no streak recorded."""
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM ruling_streaks WHERE device_id=?", (device_id,)
            ).fetchone()
        return dict(row) if row else None

    def set_streak_escalation(self, device_id: str, escalated_to: str) -> None:
        """Mark that a streak was auto-escalated to a higher verdict."""
        with self._conn() as conn:
            conn.execute(
                "UPDATE ruling_streaks SET escalated_to=?, updated_at=? WHERE device_id=?",
                (escalated_to, time.time(), device_id),
            )

    # --- Phase 66: On-chain ruling anchoring ---

    def insert_on_chain_ruling(
        self,
        ruling_id: int,
        device_id: str,
        commitment_hash: str,
        tx_hash: str,
        block_number: int | None = None,
        chain_id: int = 4690,
    ) -> int:
        """Insert on-chain commitment record. Returns row id."""
        now = time.time()
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO on_chain_rulings "
                "(ruling_id, device_id, commitment_hash, tx_hash, block_number, chain_id, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (ruling_id, device_id, commitment_hash, tx_hash, block_number, chain_id, now),
            )
            return cur.lastrowid

    def get_on_chain_rulings(self, device_id: str, limit: int = 10) -> list[dict]:
        """Return on-chain ruling records for device, most recent first."""
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM on_chain_rulings WHERE device_id=? "
                "ORDER BY created_at DESC LIMIT ?",
                (device_id, limit),
            ).fetchall()
        return [dict(r) for r in rows]

    def get_on_chain_ruling_by_commitment(self, commitment_hash: str) -> dict | None:
        """Return on-chain ruling by commitment_hash, or None if not found."""
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM on_chain_rulings WHERE commitment_hash=?",
                (commitment_hash,),
            ).fetchone()
        return dict(row) if row else None

    # --- Phase 69: Data Sovereignty Layer — store methods ---

    def list_known_devices(self) -> list[str]:
        """Return all device_ids known to the store (from devices table)."""
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT device_id FROM devices ORDER BY last_seen DESC"
            ).fetchall()
        return [r["device_id"] for r in rows]

    def get_device_suspension(self, device_id: str) -> dict | None:
        """Return active suspension state for device from credential_enforcement, or None."""
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM credential_enforcement WHERE device_id=? "
                "AND suspended=1 AND (reinstated IS NULL OR reinstated=0) "
                "ORDER BY last_updated DESC LIMIT 1",
                (device_id,),
            ).fetchone()
        return dict(row) if row else None

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

    def insert_oracle_publication(
        self,
        oracle_type: str,
        device_id: str,
        tx_hash: str | None,
        payload_json: str,
    ) -> int:
        """Log an oracle publication event. Returns row id."""
        now = time.time()
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO oracle_publications "
                "(oracle_type, device_id, tx_hash, payload_json, published_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (oracle_type, device_id, tx_hash, payload_json, now),
            )
            return cur.lastrowid

    def get_oracle_publications(
        self, oracle_type: str | None = None, limit: int = 50
    ) -> list[dict]:
        """Return oracle publication log, optionally filtered by oracle_type."""
        with self._conn() as conn:
            if oracle_type:
                rows = conn.execute(
                    "SELECT * FROM oracle_publications WHERE oracle_type=? "
                    "ORDER BY published_at DESC LIMIT ?",
                    (oracle_type, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM oracle_publications "
                    "ORDER BY published_at DESC LIMIT ?",
                    (limit,),
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

    def get_unvalidated_rulings(self, limit: int = 50) -> list[dict]:
        """Phase 235-BRIDGE-WEDGE-FIX: agent_rulings rows with no matching
        ruling_validation_log row.  Extracted from session_adjudicator_validator
        so the entire connection-open / fetch / close lifecycle runs inside a
        single asyncio.to_thread() worker thread instead of straddling the
        event loop."""
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT ar.* FROM agent_rulings ar "
                "LEFT JOIN ruling_validation_log rvl ON ar.id = rvl.ruling_id "
                "WHERE rvl.id IS NULL "
                "ORDER BY ar.created_at ASC LIMIT ?",
                (limit,),
            ).fetchall()
            return [dict(r) for r in rows]

    def insert_validation_record(
        self,
        ruling_id: int,
        device_id: str,
        llm_verdict: str,
        fallback_verdict: str,
        llm_confidence: float,
        fallback_confidence: float,
        divergence: int,
        divergence_reason: str | None = None,
        pcc_state: str | None = None,
        pcc_host_state: str | None = None,
        gameplay_context: str | None = None,
    ) -> int:
        """Insert a validation comparison record. Returns row id.

        divergence_reason (Phase 88): JSON string of non-nominal evidence fields that
        may explain why LLM and _rule_fallback disagreed. None for non-diverging records.

        pcc_state / pcc_host_state (Phase 235-B): capture health at adjudication time.
        NULL = fail-closed (session does not count toward consecutive_clean in grind mode).

        gameplay_context (Phase 235-GAD): 'ACTIVE_GAMEPLAY' | 'MENU_DETECTED' | None.
        NULL = unknown (pass-through). 'MENU_DETECTED' = confirmed non-gameplay (blocked).
        """
        if self._consent_ledger_enabled:
            self._check_consent_gate(device_id, "insert_validation_record")
        now = time.time()
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO ruling_validation_log "
                "(ruling_id, device_id, llm_verdict, fallback_verdict, "
                "llm_confidence, fallback_confidence, divergence, divergence_reason, "
                "pcc_state, pcc_host_state, gameplay_context, created_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (ruling_id, device_id, llm_verdict, fallback_verdict,
                 llm_confidence, fallback_confidence, divergence, divergence_reason,
                 pcc_state, pcc_host_state, gameplay_context, now),
            )
            return cur.lastrowid

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
        from .active_play_occupancy import normalize_active_play_gate_mode
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
                from .active_play_occupancy import active_play_gate_allows
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

    def override_gameplay_context(
        self, row_id: int, reason: str, device_id: str = ""
    ) -> None:
        """Phase 235-GAD — Operator override: set gameplay_context='ACTIVE_GAMEPLAY'.

        Logs to gameplay_classification_disagreements for post-hoc analysis.
        Use when automatic MENU_DETECTED classification was incorrect (e.g., analog
        stick fault caused false classification during competitive match).
        """
        with self._conn() as conn:
            conn.execute(
                "SELECT gameplay_context FROM ruling_validation_log WHERE id = ?",
                (row_id,),
            )
            old_ctx_row = conn.execute(
                "SELECT gameplay_context FROM ruling_validation_log WHERE id = ?",
                (row_id,),
            ).fetchone()
            old_ctx = old_ctx_row["gameplay_context"] if old_ctx_row else None
        with self._conn() as conn:
            conn.execute(
                "UPDATE ruling_validation_log SET gameplay_context = 'ACTIVE_GAMEPLAY' WHERE id = ?",
                (row_id,),
            )
            conn.execute(
                "INSERT INTO gameplay_classification_disagreements "
                "(ruling_validation_log_id, device_id, automatic_context, override_reason, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (row_id, device_id, old_ctx or "", reason, time.time()),
            )

    def insert_active_play_occupancy_log(
        self,
        ruling_validation_log_id: int,
        ruling_id: int,
        device_id: str,
        state: str,
        score: float,
        confidence: float,
        evidence_json: str,
        gate_mode: str,
    ) -> int:
        """Persist Phase 241-APOP classifier output for a validation row."""
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO active_play_occupancy_log "
                "(ruling_validation_log_id, ruling_id, device_id, state, score, "
                "confidence, evidence_json, gate_mode, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    int(ruling_validation_log_id),
                    int(ruling_id),
                    device_id or "",
                    state,
                    float(score),
                    float(confidence),
                    evidence_json or "{}",
                    gate_mode or "shadow",
                    time.time(),
                ),
            )
            return cur.lastrowid or 0

    def get_active_play_logs_for_validation_ids(
        self, validation_ids: list[int]
    ) -> dict[int, dict]:
        """Return latest APOP log per ruling_validation_log id."""
        ids = [int(v) for v in validation_ids if v is not None]
        if not ids:
            return {}
        placeholders = ",".join("?" for _ in ids)
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM active_play_occupancy_log "
                f"WHERE ruling_validation_log_id IN ({placeholders}) "
                "ORDER BY created_at DESC",
                tuple(ids),
            ).fetchall()
        result: dict[int, dict] = {}
        for row in rows:
            d = dict(row)
            key = int(d["ruling_validation_log_id"])
            if key not in result:
                result[key] = d
        return result

    def get_latest_active_play_occupancy_status(
        self,
        enabled: bool = True,
        gate_mode: str = "shadow",
        latest_gameplay_context: str | None = None,
    ) -> dict:
        """Return latest Phase 241-APOP status for the operator API."""
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM active_play_occupancy_log ORDER BY created_at DESC LIMIT 1"
            ).fetchone()
            total = conn.execute(
                "SELECT COUNT(*) FROM active_play_occupancy_log"
            ).fetchone()[0]
        if row is None:
            return {
                "active_play_occupancy_enabled": bool(enabled),
                "gate_mode": gate_mode,
                "total_logs": int(total),
                "latest_state": None,
                "latest_score": 0.0,
                "latest_confidence": 0.0,
                "latest_evidence": {},
                "latest_gameplay_context": latest_gameplay_context,
                "timestamp": time.time(),
            }
        d = dict(row)
        try:
            evidence = json.loads(d.get("evidence_json") or "{}")
        except Exception:
            evidence = {}
        return {
            "active_play_occupancy_enabled": bool(enabled),
            "gate_mode": gate_mode,
            "total_logs": int(total),
            "latest_state": d.get("state"),
            "latest_score": float(d.get("score", 0.0) or 0.0),
            "latest_confidence": float(d.get("confidence", 0.0) or 0.0),
            "latest_evidence": evidence if isinstance(evidence, dict) else {},
            "latest_gameplay_context": latest_gameplay_context,
            "latest_ruling_validation_log_id": d.get("ruling_validation_log_id"),
            "latest_ruling_id": d.get("ruling_id"),
            "latest_device_id": d.get("device_id", ""),
            "last_run_ts": d.get("created_at"),
            "timestamp": time.time(),
        }

    def get_validation_gate_status(
        self, gate_n: int = 100, max_divergence_rate: float = 1.0
    ) -> dict:
        """Return validation gate status with recommended operator action (Phase 78)."""
        summary = self.get_validation_summary(gate_n, max_divergence_rate)
        if summary["gate_passed"]:
            action = "Gate passed — safe to set AGENT_DRY_RUN=false via POST /agent/config"
        elif not summary["divergence_rate_ok"]:
            action = (
                f"Divergence rate {summary['divergence_rate']:.1%} exceeds max "
                f"{max_divergence_rate:.1%} — review recent divergences before enabling enforcement"
            )
        elif summary["divergence_count"] > 0:
            action = (
                f"Divergences detected ({summary['divergence_count']}) — "
                "review validation_divergence events before enabling enforcement"
            )
        else:
            remaining = gate_n - summary["consecutive_clean"]
            action = (
                f"{remaining} more clean ruling(s) needed before enforcement is safe"
            )
        summary["recommended_action"] = action
        return summary

    def get_campaign_status(
        self, gate_n: int = 100, max_divergence_rate: float = 1.0
    ) -> dict:
        """Return adjudication campaign progress toward dry_run=False activation (Phase 88).

        Reads from ruling_validation_log to compute:
          - consecutive_clean / gate_n progress (atomically from get_validation_summary)
          - verdict_breakdown (CERTIFY/FLAG/HOLD/BLOCK counts from LLM verdicts)
          - divergence_breakdown (divergence_reason → count for diverged rows)
          - recent_sessions (last 10 validation log rows, newest-first)
          - estimated_sessions_to_gate (probabilistic: remaining / (1 - divergence_rate))
          - campaign_note (human-readable operator narrative)

        W1 invariant: consecutive_clean and gate_passed computed atomically via
        get_validation_summary() — never cached or stale.
        """
        import math as _math

        summary = self.get_validation_summary(gate_n, max_divergence_rate)
        consecutive_clean = summary["consecutive_clean"]
        session_count = summary["total"]
        divergence_count = summary["divergence_count"]
        divergence_rate = summary["divergence_rate"]
        gate_passed = summary["gate_passed"]

        progress_pct = round(
            min(100.0, consecutive_clean / gate_n * 100.0), 1
        ) if gate_n > 0 else 0.0

        remaining = max(0, gate_n - consecutive_clean)
        if remaining == 0:
            estimated_sessions_to_gate = 0
        elif (1.0 - divergence_rate) > 0.01:
            estimated_sessions_to_gate = int(
                _math.ceil(remaining / (1.0 - divergence_rate))
            )
        else:
            estimated_sessions_to_gate = 9999  # divergence_rate near 1.0 — gating indefinitely

        with self._conn() as conn:
            vb_rows = conn.execute(
                "SELECT llm_verdict, COUNT(*) as cnt FROM ruling_validation_log "
                "GROUP BY llm_verdict"
            ).fetchall()
            verdict_breakdown = {r["llm_verdict"]: r["cnt"] for r in vb_rows}

            div_rows = conn.execute(
                "SELECT divergence_reason, COUNT(*) as cnt FROM ruling_validation_log "
                "WHERE divergence=1 AND divergence_reason IS NOT NULL "
                "GROUP BY divergence_reason"
            ).fetchall()
            divergence_breakdown = {r["divergence_reason"]: r["cnt"] for r in div_rows}

            recent_rows = conn.execute(
                "SELECT ruling_id, device_id, llm_verdict, fallback_verdict, "
                "divergence, divergence_reason, created_at "
                "FROM ruling_validation_log ORDER BY created_at DESC LIMIT 10"
            ).fetchall()
            recent_sessions = [dict(r) for r in recent_rows]

            last_row = conn.execute(
                "SELECT MAX(created_at) as last_at FROM ruling_validation_log"
            ).fetchone()
            last_session_at = (
                float(last_row["last_at"])
                if last_row and last_row["last_at"] else None
            )

        if gate_passed:
            note = (
                f"Gate PASSED — {consecutive_clean}/{gate_n} consecutive clean rulings. "
                "Safe to set AGENT_DRY_RUN=false via POST /agent/config."
            )
        elif session_count == 0:
            note = (
                "No real sessions validated yet — start the bridge with controller "
                "connected and play NCAA CFB 26 to begin accumulating clean rulings."
            )
        else:
            note = (
                f"Campaign in progress: {consecutive_clean}/{gate_n} consecutive clean "
                f"(~{estimated_sessions_to_gate} more sessions at current divergence "
                f"rate {divergence_rate:.1%})."
            )

        return {
            "consecutive_clean": consecutive_clean,
            "gate_n": gate_n,
            "progress_pct": progress_pct,
            "session_count": session_count,
            "divergence_count": divergence_count,
            "divergence_rate": divergence_rate,
            "gate_passed": gate_passed,
            "estimated_sessions_to_gate": estimated_sessions_to_gate,
            "verdict_breakdown": verdict_breakdown,
            "divergence_breakdown": divergence_breakdown,
            "recent_sessions": recent_sessions,
            "last_session_at": last_session_at,
            "campaign_note": note,
        }

    # --- Phase 76: Ruling provenance anchors ---

    def insert_provenance_anchor(
        self,
        ruling_id: int,
        device_id: str,
        provenance_hash: str,
        ceremony_hash: str,
        evidence_hash: str,
    ) -> int:
        """Insert a provenance anchor record. Returns row id.

        Uses INSERT OR IGNORE so duplicate anchors for the same ruling_id are silently
        ignored (the unique index on ruling_id enforces idempotency).
        """
        now = time.time()
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT OR IGNORE INTO ruling_provenance_anchors "
                "(ruling_id, device_id, provenance_hash, ceremony_hash, evidence_hash, anchored_at) "
                "VALUES (?,?,?,?,?,?)",
                (ruling_id, device_id, provenance_hash, ceremony_hash, evidence_hash, now),
            )
            return cur.lastrowid or 0

    def get_provenance_anchor(self, ruling_id: int) -> dict | None:
        """Return the provenance anchor record for ruling_id, or None if not yet anchored."""
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM ruling_provenance_anchors WHERE ruling_id=?",
                (ruling_id,),
            ).fetchone()
        return dict(row) if row else None

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

    def count_operator_overrides(self, within_n: int = 100) -> int:
        """Count manual operator overrides in the most recent within_n rulings window (Phase 79).

        An override is a 'ruling_override' event in agent_events.
        """
        with self._conn() as conn:
            row = conn.execute(
                "SELECT COUNT(*) as cnt FROM agent_events "
                "WHERE event_type='ruling_override' "
                "AND created_at > COALESCE(("
                "  SELECT MIN(created_at) FROM ("
                "    SELECT created_at FROM agent_rulings ORDER BY created_at DESC LIMIT ?"
                "  )"
                "), 0)",
                (within_n,),
            ).fetchone()
            return int(row["cnt"]) if row else 0

    def count_ceremony_key_rotations(self, within_hours: float = 24.0) -> int:
        """Count ceremony_key_rotated events within the last within_hours hours (Phase 79)."""
        cutoff = time.time() - within_hours * 3600
        with self._conn() as conn:
            row = conn.execute(
                "SELECT COUNT(*) as cnt FROM agent_events "
                "WHERE event_type='ceremony_key_rotated' AND created_at > ?",
                (cutoff,),
            ).fetchone()
            return int(row["cnt"]) if row else 0

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

    def insert_class_j_assessment(
        self,
        device_id: str,
        entropy_variance: float,
        risk_level: str,
        window_count: int,
    ) -> int:
        """Insert a Class J ML-bot risk assessment (Phase 81). Returns row id."""
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO class_j_assessments "
                "(device_id, entropy_variance, risk_level, window_count, assessed_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (device_id, entropy_variance, risk_level, window_count, time.time()),
            )
            return cur.lastrowid

    def get_class_j_assessment(self, device_id: str) -> dict | None:
        """Return most recent Class J assessment for device_id (Phase 81)."""
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM class_j_assessments WHERE device_id=? "
                "ORDER BY assessed_at DESC LIMIT 1",
                (device_id,),
            ).fetchone()
            return dict(row) if row else None

    # --- Phase 83: Agent supervisor health ---

    def get_agent_activity(
        self,
        table: str,
        ts_col: str,
        filter_sql: str | None = None,
        device_col: str | None = None,
    ) -> dict:
        """Return last-activity metrics for an agent's table (Phase 83).

        Returns last_active_at, activity_count, and distinct_devices.
        W1 mitigation: distinct_devices distinguishes genuine agent activity from
        a zombie writing to a single device in a tight loop.
        """
        where = f"WHERE {filter_sql}" if filter_sql else ""
        with self._conn() as conn:
            row = conn.execute(
                f"SELECT MAX({ts_col}), COUNT(*) FROM {table} {where}"
            ).fetchone()
            last_active_at = row[0] if row else None
            activity_count = int(row[1]) if row else 0

            distinct = None
            if device_col:
                d_row = conn.execute(
                    f"SELECT COUNT(DISTINCT {device_col}) FROM {table} {where}"
                ).fetchone()
                distinct = int(d_row[0]) if d_row else 0

        return {
            "last_active_at": last_active_at,
            "activity_count": activity_count,
            "distinct_devices": distinct,
        }

    def insert_supervisor_health_log(
        self,
        agent_name: str,
        health: str,
        last_active_at: float | None,
        activity_count: int = 0,
    ) -> int:
        """Persist an agent health check result (Phase 83). Returns row id."""
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO supervisor_health_log "
                "(agent_name, health, last_active_at, activity_count, checked_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (agent_name, health, last_active_at, activity_count, time.time()),
            )
            return cur.lastrowid

    def get_latest_supervisor_health(self) -> list[dict]:
        """Return the most recent health check row per agent (Phase 83)."""
        with self._conn() as conn:
            rows = conn.execute(
                """
                SELECT s.*
                FROM supervisor_health_log s
                INNER JOIN (
                    SELECT agent_name, MAX(checked_at) AS max_checked
                    FROM supervisor_health_log
                    GROUP BY agent_name
                ) latest ON s.agent_name = latest.agent_name
                          AND s.checked_at = latest.max_checked
                ORDER BY s.agent_name
                """
            ).fetchall()
            return [dict(r) for r in rows]

    # --- Phase 82: Reactive adjudication interrupt log ---

    def insert_reactive_adjudication_log(
        self,
        device_id: str,
        triggered_by: str,
        entropy_variance: float | None,
        verdict: str | None,
        was_deferred: bool = False,
    ) -> int:
        """Log a reactive adjudication interrupt attempt (Phase 82). Returns row id."""
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO reactive_adjudication_log "
                "(device_id, triggered_by, entropy_variance, verdict, was_deferred, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (device_id, triggered_by, entropy_variance, verdict,
                 1 if was_deferred else 0, time.time()),
            )
            return cur.lastrowid

    def get_reactive_adjudication_log(
        self, device_id: str | None = None, limit: int = 20
    ) -> list[dict]:
        """Return recent reactive adjudication log entries (Phase 82).

        If device_id is provided, filters to that device only.
        Returns newest-first, at most limit rows.
        """
        with self._conn() as conn:
            if device_id:
                rows = conn.execute(
                    "SELECT * FROM reactive_adjudication_log "
                    "WHERE device_id=? ORDER BY created_at DESC LIMIT ?",
                    (device_id, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM reactive_adjudication_log "
                    "ORDER BY created_at DESC LIMIT ?",
                    (limit,),
                ).fetchall()
            return [dict(r) for r in rows]

    # --- Phase 84: Gate attestation anchor ---

    def insert_gate_attestation(
        self,
        attestation_hash: str,
        consecutive_clean: int,
        gate_n: int,
        divergence_rate: float,
        on_chain_tx: str | None = None,
    ) -> int:
        """Persist a gate attestation hash (Phase 84). Returns row id.

        INSERT OR IGNORE — idempotent; same attestation_hash is a no-op (no exception).
        """
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT OR IGNORE INTO gate_attestations "
                "(attestation_hash, consecutive_clean, gate_n, divergence_rate, "
                " on_chain_tx, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (
                    attestation_hash,
                    consecutive_clean,
                    gate_n,
                    divergence_rate,
                    on_chain_tx,
                    time.time(),
                ),
            )
            return cur.lastrowid

    def get_gate_attestations(self, limit: int = 10) -> list[dict]:
        """Return the most recent gate attestation records (Phase 84), newest-first."""
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM gate_attestations ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
            return [dict(r) for r in rows]

    # --- Phase 86: Synthetic corpus ---

    def insert_synthetic_session(
        self,
        session_id: str,
        device_id: str,
        inference_code: int,
        humanity_score: float,
        fallback_verdict: str,
        fallback_confidence: float,
        passed_fallback: int,
        corpus_run_id: str | None = None,
    ) -> int:
        """Insert synthetic session result. INSERT OR IGNORE (idempotent by session_id)."""
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT OR IGNORE INTO synthetic_sessions "
                "(session_id, device_id, inference_code, humanity_score, "
                " fallback_verdict, fallback_confidence, passed_fallback, corpus_run_id) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (session_id, device_id, inference_code, humanity_score,
                 fallback_verdict, fallback_confidence, passed_fallback, corpus_run_id),
            )
            conn.commit()
            return cur.lastrowid or 0

    def get_corpus_status(self) -> dict:
        """Return synthetic corpus aggregate statistics (Phase 86)."""
        with self._conn() as conn:
            row = conn.execute(
                "SELECT COUNT(*) as total, "
                "SUM(passed_fallback) as passed, "
                "COUNT(DISTINCT corpus_run_id) as run_count, "
                "MAX(created_at) as last_run_at "
                "FROM synthetic_sessions"
            ).fetchone()
        if not row or not row["total"]:
            return {
                "total": 0, "passed": 0, "failed": 0,
                "run_count": 0, "last_run_at": None,
                "isolation_note": (
                    "Synthetic sessions do NOT count toward production gate "
                    "consecutive_clean (Phase 86 W1 isolation invariant)."
                ),
            }
        total = int(row["total"] or 0)
        passed = int(row["passed"] or 0)
        return {
            "total": total,
            "passed": passed,
            "failed": total - passed,
            "run_count": int(row["run_count"] or 0),
            "last_run_at": row["last_run_at"],
            "isolation_note": (
                "Synthetic sessions do NOT count toward production gate "
                "consecutive_clean (Phase 86 W1 isolation invariant)."
            ),
        }
    # --- Phase 89: Protocol Intelligence ---

    def insert_protocol_intelligence_report(self, report: dict) -> int:
        """Insert a protocol intelligence report. Returns row id."""
        components = report.get("components", {})
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO protocol_intelligence_reports "
                "(protocol_health_score, gate_progress_score, fleet_health_score, "
                "divergence_clarity_score, corpus_pass_score, class_j_confidence_score, "
                "shadow_pass_score, triage_confidence_score, ready_for_live_mode, "
                "bottleneck, estimated_days_to_gate, components_json, recommendation, created_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    float(report.get("protocol_health_score", 0.0)),
                    float(components.get("gate_progress", 0.0)) / 35.0
                    if components.get("gate_progress") is not None else 0.0,
                    float(components.get("fleet_health", 0.0)) / 25.0
                    if components.get("fleet_health") is not None else 0.0,
                    float(components.get("divergence_clarity", 0.0)) / 20.0
                    if components.get("divergence_clarity") is not None else 0.0,
                    float(components.get("corpus_pass", 0.0)) / 10.0
                    if components.get("corpus_pass") is not None else 0.0,
                    float(components.get("class_j_confidence", 0.0)) / 10.0
                    if components.get("class_j_confidence") is not None else 0.0,
                    float(components["shadow_pass"]) / 5.0 if "shadow_pass" in components else None,
                    float(components["triage_confidence"]) / 5.0
                    if "triage_confidence" in components else None,
                    int(bool(report.get("ready_for_live_mode", False))),
                    report.get("bottleneck"),
                    report.get("estimated_days_to_gate"),
                    report.get("components_json", "{}"),
                    report.get("recommendation", ""),
                    float(report.get("created_at", time.time())),
                ),
            )
            return cur.lastrowid

    def get_latest_protocol_intelligence_report(self) -> dict | None:
        """Return the most recent protocol intelligence report, or None."""
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM protocol_intelligence_reports "
                "ORDER BY created_at DESC LIMIT 1"
            ).fetchone()
        if not row:
            return None
        result = dict(row)
        try:
            result["components"] = json.loads(result.get("components_json") or "{}")
        except (json.JSONDecodeError, TypeError):
            result["components"] = {}
        return result

    # --- Phase 90: Shadow Enforcement ---

    def insert_shadow_enforcement_log(
        self,
        device_id: str,
        ruling_id,
        commitment_hash,
        would_have_suspended: int,
        duration_s=None,
        warmup_attack_score=None,
    ) -> int:
        """Log a shadow enforcement event (BLOCK in shadow mode)."""
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO shadow_enforcement_log "
                "(device_id, ruling_id, verdict, commitment_hash, "
                "would_have_suspended, duration_s, warmup_attack_score) "
                "VALUES (?,?,?,?,?,?,?)",
                (
                    device_id, ruling_id, "BLOCK", commitment_hash,
                    int(would_have_suspended), duration_s, warmup_attack_score,
                ),
            )
            return cur.lastrowid

    def get_shadow_enforcement_log(self, device_id=None, limit: int = 50) -> list:
        """Return recent shadow enforcement log entries."""
        with self._conn() as conn:
            if device_id:
                rows = conn.execute(
                    "SELECT * FROM shadow_enforcement_log WHERE device_id=? "
                    "ORDER BY created_at DESC LIMIT ?",
                    (device_id, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM shadow_enforcement_log "
                    "ORDER BY created_at DESC LIMIT ?",
                    (limit,),
                ).fetchall()
        return [dict(r) for r in rows]

    def get_shadow_enforcement_stats(self) -> dict:
        """Return aggregate shadow enforcement statistics."""
        with self._conn() as conn:
            row = conn.execute(
                "SELECT COUNT(*) as total, "
                "SUM(CASE WHEN would_have_suspended=0 THEN 1 ELSE 0 END) as passed, "
                "SUM(would_have_suspended) as would_have_suspended "
                "FROM shadow_enforcement_log"
            ).fetchone()
        total = int(row["total"] or 0)
        passed = int(row["passed"] or 0)
        suspended = int(row["would_have_suspended"] or 0)
        return {
            "total": total,
            "passed": passed,
            "would_have_suspended": suspended,
            "pass_rate": round(passed / total, 4) if total > 0 else None,
        }

    # --- Phase 91: Divergence Triage ---

    def insert_divergence_triage_report(
        self,
        device_id: str,
        divergence_count: int,
        escalated: int,
        patterns,
        ml_bot_high_count: int,
        cheat_count: int,
        enrollment_anomaly_count: int,
    ) -> int:
        """Insert triage report for device."""
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO divergence_triage_reports "
                "(device_id, divergence_count, escalated, patterns, "
                "ml_bot_high_count, cheat_count, enrollment_anomaly_count) "
                "VALUES (?,?,?,?,?,?,?)",
                (
                    device_id, int(divergence_count), int(escalated), patterns,
                    int(ml_bot_high_count), int(cheat_count), int(enrollment_anomaly_count),
                ),
            )
            return cur.lastrowid

    def get_divergence_triage_report(self, limit: int = 50) -> list:
        """Return most recent triage entry per device, escalated first."""
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT t.* FROM divergence_triage_reports t "
                "INNER JOIN (SELECT device_id, MAX(assessed_at) as latest "
                "FROM divergence_triage_reports GROUP BY device_id) latest "
                "ON t.device_id=latest.device_id AND t.assessed_at=latest.latest "
                "ORDER BY t.escalated DESC, t.assessed_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]

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

    def insert_escalation_ruling_log(
        self,
        device_id: str,
        patterns,
        verdict,
        ruling_id,
        was_deferred: bool,
    ) -> int:
        """Insert an escalation ruling log entry."""
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO escalation_ruling_log "
                "(device_id, patterns, verdict, ruling_id, was_deferred) "
                "VALUES (?,?,?,?,?)",
                (device_id, patterns, verdict, ruling_id, int(was_deferred)),
            )
            return cur.lastrowid

    def get_escalation_ruling_log(self, device_id=None, limit: int = 50) -> list:
        """Return escalation ruling log entries."""
        with self._conn() as conn:
            if device_id:
                rows = conn.execute(
                    "SELECT * FROM escalation_ruling_log WHERE device_id=? "
                    "ORDER BY created_at DESC LIMIT ?",
                    (device_id, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM escalation_ruling_log "
                    "ORDER BY created_at DESC LIMIT ?",
                    (limit,),
                ).fetchall()
        return [dict(r) for r in rows]

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

    def insert_gsr_sample(
        self,
        device_id: str,
        arousal_index: float,
        correlation: float,
        conductance_raw: float = 0.0,
        l7_features_json: str = "",
    ) -> int:
        """Persist a GSR biometric sample. Returns row id."""
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO gsr_samples "
                "(device_id, arousal_index, correlation, conductance_raw, l7_features_json) "
                "VALUES (?,?,?,?,?)",
                (device_id, arousal_index, correlation, conductance_raw, l7_features_json),
            )
            return cur.lastrowid

    def get_gsr_samples(self, device_id: str, limit: int = 50) -> list:
        """Return GSR samples for a device, newest first."""
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM gsr_samples WHERE device_id=? ORDER BY created_at DESC LIMIT ?",
                (device_id, limit),
            ).fetchall()
        return [dict(r) for r in rows]

    # --- Phase 99C: VHP issuances ---

    def insert_vhp_issuance(
        self,
        device_id: str,
        token_id: int = 0,
        tx_hash: str = "",
        expires_at: float = 0.0,
        cert_level: int = 1,
        consecutive_clean: int = 0,
        to_address: str = "",
    ) -> int:
        """Persist a VHP token issuance record. Returns row id."""
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO vhp_issuances "
                "(device_id, token_id, tx_hash, expires_at, cert_level, consecutive_clean, to_address) "
                "VALUES (?,?,?,?,?,?,?)",
                (device_id, token_id, tx_hash, expires_at, cert_level, consecutive_clean, to_address),
            )
            return cur.lastrowid

    def get_vhp_status(self, device_id: str) -> dict | None:
        """Return the latest VHP issuance for a device, or None if none found."""
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM vhp_issuances WHERE device_id=? ORDER BY created_at DESC LIMIT 1",
                (device_id,),
            ).fetchone()
        return dict(row) if row else None

    # ── Phase 102: VHP Renewal Log ────────────────────────────────────────────

    def insert_vhp_renewal(
        self,
        device_id: str,
        token_id: int,
        old_expires_at: float,
        new_expires_at: float,
        tx_hash: str = "",
        dry_run: bool = False,
    ) -> int:
        """Persist a VHP renewal record (Phase 102)."""
        with self._conn() as conn:
            cur = conn.execute(
                """INSERT INTO vhp_renewal_log
                   (device_id, token_id, old_expires_at, new_expires_at,
                    tx_hash, dry_run)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (device_id, token_id, old_expires_at, new_expires_at,
                 tx_hash, int(dry_run)),
            )
            return cur.lastrowid

    def get_vhp_renewal_log(
        self, device_id: str | None = None, limit: int = 20
    ) -> list[dict]:
        """Return renewal log entries, optionally filtered by device_id (Phase 102)."""
        with self._conn() as conn:
            if device_id:
                rows = conn.execute(
                    """SELECT id, device_id, token_id, old_expires_at,
                              new_expires_at, tx_hash, dry_run, created_at
                       FROM vhp_renewal_log
                       WHERE device_id = ?
                       ORDER BY created_at DESC LIMIT ?""",
                    (device_id, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    """SELECT id, device_id, token_id, old_expires_at,
                              new_expires_at, tx_hash, dry_run, created_at
                       FROM vhp_renewal_log
                       ORDER BY created_at DESC LIMIT ?""",
                    (limit,),
                ).fetchall()
            return [
                {
                    "id": r[0], "device_id": r[1], "token_id": r[2],
                    "old_expires_at": r[3], "new_expires_at": r[4],
                    "tx_hash": r[5], "dry_run": bool(r[6]), "created_at": r[7],
                }
                for r in rows
            ]

    def get_expiring_vhps(self, cutoff_ts: float) -> list[dict]:
        """Return vhp_issuances where now < expires_at < cutoff_ts (Phase 102)."""
        now = __import__("time").time()
        with self._conn() as conn:
            rows = conn.execute(
                """SELECT device_id, token_id, expires_at
                   FROM vhp_issuances
                   WHERE expires_at > ? AND expires_at < ?
                   ORDER BY expires_at ASC""",
                (now, cutoff_ts),
            ).fetchall()
            return [
                {"device_id": r[0], "token_id": r[1], "expires_at": r[2]}
                for r in rows
            ]

    def get_total_vhp_count(self) -> int:
        """Return COUNT(*) of all vhp_issuances records (Phase 102)."""
        with self._conn() as conn:
            row = conn.execute("SELECT COUNT(*) FROM vhp_issuances").fetchone()
            return int(row[0]) if row else 0

    def get_first_vhp_status(self) -> dict | None:
        """Return earliest VHP issuance record + is_valid + is_simulation flags (Phase 103).
        is_simulation=True when tx_hash starts with 'sim_'.
        Returns None when no VHP has ever been issued.
        """
        import time as _t
        with self._conn() as conn:
            row = conn.execute(
                "SELECT device_id, token_id, tx_hash, expires_at, cert_level, "
                "consecutive_clean, to_address, created_at "
                "FROM vhp_issuances ORDER BY created_at ASC LIMIT 1"
            ).fetchone()
        if row is None:
            return None
        tx_hash = row[2] or ""
        expires_at = row[3] or 0.0
        return {
            "device_id": row[0],
            "token_id": row[1],
            "tx_hash": tx_hash,
            "expires_at": expires_at,
            "cert_level": row[4],
            "consecutive_clean": row[5],
            "to_address": row[6] or "",
            "created_at": row[7],
            "is_valid": expires_at > _t.time(),
            "is_simulation": tx_hash.startswith("sim_"),
        }

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

    def insert_epistemic_threshold_change(
        self, old_threshold: float, new_threshold: float,
        trigger: str = "manual", pmi_at_change: int = 0, notes: str = ""
    ) -> int:
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO epistemic_threshold_history "
                "(old_threshold, new_threshold, trigger, pmi_at_change, notes) VALUES (?,?,?,?,?)",
                (old_threshold, new_threshold, trigger, int(pmi_at_change), notes),
            )
            return cur.lastrowid

    def get_epistemic_threshold_history(self, limit: int = 20) -> list:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT id, old_threshold, new_threshold, trigger, pmi_at_change, notes, created_at "
                "FROM epistemic_threshold_history ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
        return [{"id": r[0], "old_threshold": r[1], "new_threshold": r[2],
                  "trigger": r[3], "pmi_at_change": r[4], "notes": r[5], "created_at": r[6]}
                for r in rows]

    # --- Phase 107: Live Mode Readiness Reports ---

    def insert_readiness_report(
        self, n_tested: int, false_positive_count: int, false_positive_rate: float,
        activation_committed: int, pmi: int, dry_run_active: int,
        ready_for_live: int, notes: str = ""
    ) -> int:
        """Persist live mode readiness validation result (Phase 107)."""
        import time as _t
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO live_mode_readiness_reports "
                "(n_tested, false_positive_count, false_positive_rate, activation_committed, "
                "pmi, dry_run_active, ready_for_live, notes, created_at) "
                "VALUES (?,?,?,?,?,?,?,?,?)",
                (n_tested, false_positive_count, false_positive_rate,
                 activation_committed, pmi, dry_run_active, ready_for_live, notes, _t.time()),
            )
            return cur.lastrowid

    def get_latest_readiness_report(self) -> "dict | None":
        """Return the most recent live mode readiness report (Phase 107). None if none exist."""
        with self._conn() as conn:
            row = conn.execute(
                "SELECT id, n_tested, false_positive_count, false_positive_rate, "
                "activation_committed, pmi, dry_run_active, ready_for_live, notes, created_at "
                "FROM live_mode_readiness_reports ORDER BY created_at DESC LIMIT 1"
            ).fetchone()
        if row is None:
            return None
        return {
            "id": row[0], "n_tested": row[1], "false_positive_count": row[2],
            "false_positive_rate": row[3], "activation_committed": bool(row[4]),
            "pmi": row[5], "dry_run_active": bool(row[6]), "ready_for_live": bool(row[7]),
            "notes": row[8], "created_at": row[9],
        }

    # --- Phase 108: Tournament Readiness Snapshots ---

    def insert_tournament_readiness_snapshot(
        self, n_tested: int, false_positive_count: int,
        activation_committed: int, pmi: int, dry_run_active: int,
        software_conditions_met: int, separation_ratio: float,
        separation_ratio_ok: int, touchpad_recapture_complete: int,
        hardware_conditions_met: int, fully_ready: int,
        blocking_conditions_json: str = "[]", notes: str = ""
    ) -> int:
        """Persist tournament readiness snapshot (Phase 108)."""
        import time as _t
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO tournament_readiness_snapshots "
                "(n_tested, false_positive_count, activation_committed, pmi, dry_run_active, "
                "software_conditions_met, separation_ratio, separation_ratio_ok, "
                "touchpad_recapture_complete, hardware_conditions_met, fully_ready, "
                "blocking_conditions_json, notes, created_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (n_tested, false_positive_count, activation_committed, pmi, dry_run_active,
                 software_conditions_met, separation_ratio, separation_ratio_ok,
                 touchpad_recapture_complete, hardware_conditions_met, fully_ready,
                 blocking_conditions_json, notes, _t.time()),
            )
            return cur.lastrowid

    def get_latest_tournament_readiness_snapshot(self) -> "dict | None":
        """Return most recent tournament readiness snapshot (Phase 108). None if none exist."""
        with self._conn() as conn:
            row = conn.execute(
                "SELECT id, n_tested, false_positive_count, activation_committed, pmi, "
                "dry_run_active, software_conditions_met, separation_ratio, "
                "separation_ratio_ok, touchpad_recapture_complete, hardware_conditions_met, "
                "fully_ready, blocking_conditions_json, notes, created_at "
                "FROM tournament_readiness_snapshots ORDER BY created_at DESC LIMIT 1"
            ).fetchone()
        if row is None:
            return None
        import json as _j
        return {
            "id": row[0], "n_tested": row[1], "false_positive_count": row[2],
            "activation_committed": bool(row[3]), "pmi": row[4],
            "dry_run_active": bool(row[5]), "software_conditions_met": row[6],
            "separation_ratio": row[7], "separation_ratio_ok": bool(row[8]),
            "touchpad_recapture_complete": bool(row[9]),
            "hardware_conditions_met": row[10], "fully_ready": bool(row[11]),
            "blocking_conditions": _j.loads(row[12]), "notes": row[13],
            "created_at": row[14],
        }

    # --- Phase 109A: ioSwarm consensus log ---

    def insert_ioswarm_consensus(
        self,
        device_id: str,
        node_verdicts_json: str,
        quorum_verdict: str,
        quorum_reached: bool,
        block_quorum_met: bool,
        agreement_ratio: float,
        node_count: int,
        swarm_verdict_score: float,
        hold_escalation_flag: bool,
        verdict_distribution_json: str = "{}",
        session_id: "str | None" = None,
    ) -> int:
        """Insert an ioSwarm consensus result. Returns new row id."""
        import time as _t
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO ioswarm_consensus_log "
                "(device_id, session_id, node_verdicts_json, quorum_verdict, quorum_reached, "
                "block_quorum_met, agreement_ratio, node_count, swarm_verdict_score, "
                "hold_escalation_flag, verdict_distribution_json, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    device_id, session_id, node_verdicts_json, quorum_verdict,
                    int(quorum_reached), int(block_quorum_met), agreement_ratio, node_count,
                    swarm_verdict_score, int(hold_escalation_flag),
                    verdict_distribution_json, _t.time(),
                ),
            )
            return cur.lastrowid

    def get_ioswarm_consensus_log(
        self,
        device_id: "str | None" = None,
        limit: int = 20,
    ) -> "list[dict]":
        """Return ioSwarm consensus log entries, newest first. Optional device_id filter."""
        import json as _j
        with self._conn() as conn:
            if device_id is not None:
                rows = conn.execute(
                    "SELECT id, device_id, session_id, node_verdicts_json, quorum_verdict, "
                    "quorum_reached, block_quorum_met, agreement_ratio, node_count, "
                    "swarm_verdict_score, hold_escalation_flag, verdict_distribution_json, "
                    "created_at FROM ioswarm_consensus_log "
                    "WHERE device_id = ? ORDER BY created_at DESC LIMIT ?",
                    (device_id, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT id, device_id, session_id, node_verdicts_json, quorum_verdict, "
                    "quorum_reached, block_quorum_met, agreement_ratio, node_count, "
                    "swarm_verdict_score, hold_escalation_flag, verdict_distribution_json, "
                    "created_at FROM ioswarm_consensus_log "
                    "ORDER BY created_at DESC LIMIT ?",
                    (limit,),
                ).fetchall()
        result = []
        for row in rows:
            result.append({
                "id": row[0], "device_id": row[1], "session_id": row[2],
                "node_verdicts": _j.loads(row[3]),
                "quorum_verdict": row[4],
                "quorum_reached": bool(row[5]), "block_quorum_met": bool(row[6]),
                "agreement_ratio": row[7], "node_count": row[8],
                "swarm_verdict_score": row[9],
                "hold_escalation_flag": bool(row[10]),
                "verdict_distribution": _j.loads(row[11]),
                "created_at": row[12],
            })
        return result

    # --- Phase 109B: ioSwarm renewal log ---

    def insert_ioswarm_renewal(
        self,
        device_id: str,
        token_id: int,
        quorum_verdict: "str | None",
        agreement_ratio: float,
        node_count: int,
        renewal_approved: int,
        node_verdicts_json: str = "[]",
    ) -> int:
        """Insert ioSwarm renewal evaluation record. Returns new row id."""
        import time as _t
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO ioswarm_renewal_log "
                "(device_id, token_id, quorum_verdict, agreement_ratio, node_count, "
                "renewal_approved, node_verdicts_json, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    device_id,
                    token_id,
                    quorum_verdict,
                    agreement_ratio,
                    node_count,
                    renewal_approved,
                    node_verdicts_json,
                    _t.time(),
                ),
            )
            return cur.lastrowid

    def get_ioswarm_renewal_log(
        self,
        device_id: "str | None" = None,
        limit: int = 20,
    ) -> "list[dict]":
        """Return ioSwarm renewal log entries, newest first. Optional device_id filter."""
        import json as _j
        with self._conn() as conn:
            if device_id is not None:
                rows = conn.execute(
                    "SELECT id, device_id, token_id, quorum_verdict, agreement_ratio, "
                    "node_count, renewal_approved, node_verdicts_json, created_at "
                    "FROM ioswarm_renewal_log "
                    "WHERE device_id = ? ORDER BY created_at DESC LIMIT ?",
                    (device_id, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT id, device_id, token_id, quorum_verdict, agreement_ratio, "
                    "node_count, renewal_approved, node_verdicts_json, created_at "
                    "FROM ioswarm_renewal_log "
                    "ORDER BY created_at DESC LIMIT ?",
                    (limit,),
                ).fetchall()
        result = []
        for row in rows:
            result.append({
                "id": row[0],
                "device_id": row[1],
                "token_id": row[2],
                "quorum_verdict": row[3],
                "agreement_ratio": row[4],
                "node_count": row[5],
                "renewal_approved": bool(row[6]),
                "node_verdicts": _j.loads(row[7]),
                "created_at": row[8],
            })
        return result

    # --- Phase 109C: ioSwarm Adjudication Log ---

    def insert_ioswarm_adjudication(
        self,
        device_id: str,
        session_id: str,
        classj_quorum_verdict: "str | None",
        classj_agreement_ratio: float,
        triage_quorum_verdict: "str | None",
        triage_agreement_ratio: float,
        dual_veto: bool,
        node_count: int,
        classj_verdicts_json: str = "[]",
        triage_verdicts_json: str = "[]",
    ) -> int:
        """Insert an ioSwarm adjudication record and return the new row ID."""
        import time as _t
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO ioswarm_adjudication_log "
                "(device_id, session_id, classj_quorum_verdict, classj_agreement_ratio, "
                "triage_quorum_verdict, triage_agreement_ratio, dual_veto, node_count, "
                "classj_verdicts_json, triage_verdicts_json, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    device_id,
                    session_id or "",
                    classj_quorum_verdict,
                    classj_agreement_ratio,
                    triage_quorum_verdict,
                    triage_agreement_ratio,
                    int(bool(dual_veto)),
                    node_count,
                    classj_verdicts_json,
                    triage_verdicts_json,
                    _t.time(),
                ),
            )
            return cur.lastrowid

    def get_ioswarm_adjudication_log(
        self,
        device_id: "str | None" = None,
        limit: int = 20,
    ) -> "list[dict]":
        """Return recent ioSwarm adjudication log entries."""
        import json as _j
        with self._conn() as conn:
            if device_id:
                rows = conn.execute(
                    "SELECT id, device_id, session_id, classj_quorum_verdict, "
                    "classj_agreement_ratio, triage_quorum_verdict, triage_agreement_ratio, "
                    "dual_veto, node_count, classj_verdicts_json, triage_verdicts_json, created_at "
                    "FROM ioswarm_adjudication_log "
                    "WHERE device_id = ? ORDER BY created_at DESC LIMIT ?",
                    (device_id, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT id, device_id, session_id, classj_quorum_verdict, "
                    "classj_agreement_ratio, triage_quorum_verdict, triage_agreement_ratio, "
                    "dual_veto, node_count, classj_verdicts_json, triage_verdicts_json, created_at "
                    "FROM ioswarm_adjudication_log "
                    "ORDER BY created_at DESC LIMIT ?",
                    (limit,),
                ).fetchall()
        result = []
        for row in rows:
            result.append({
                "id": row[0],
                "device_id": row[1],
                "session_id": row[2],
                "classj_quorum_verdict": row[3],
                "classj_agreement_ratio": row[4],
                "triage_quorum_verdict": row[5],
                "triage_agreement_ratio": row[6],
                "dual_veto": bool(row[7]),
                "node_count": row[8],
                "classj_verdicts": _j.loads(row[9]),
                "triage_verdicts": _j.loads(row[10]),
                "created_at": row[11],
            })
        return result

    # --- Phase 110: ioSwarm VHP Mint Authorization Log ---

    def insert_ioswarm_vhp_mint(
        self,
        device_id: str,
        authorized: bool,
        quorum_verdict: str,
        agreement_ratio: float,
        node_count: int,
        consecutive_clean: int,
        recent_block_count: int,
        node_verdicts_json: str = "[]",
        swarm_fingerprint: "str | None" = None,
        error_msg: "str | None" = None,
    ) -> int:
        import time as _t
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO ioswarm_vhp_mint_log "
                "(device_id, authorized, quorum_verdict, agreement_ratio, node_count, "
                "consecutive_clean, recent_block_count, node_verdicts_json, swarm_fingerprint, "
                "error_msg, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    device_id,
                    int(authorized),
                    quorum_verdict,
                    float(agreement_ratio),
                    int(node_count),
                    int(consecutive_clean),
                    int(recent_block_count),
                    node_verdicts_json,
                    swarm_fingerprint,
                    error_msg,
                    _t.time(),
                ),
            )
            return cur.lastrowid

    def get_ioswarm_vhp_mint_log(
        self,
        device_id: "str | None" = None,
        limit: int = 20,
    ) -> list[dict]:
        with self._conn() as conn:
            if device_id:
                rows = conn.execute(
                    "SELECT id, device_id, authorized, quorum_verdict, agreement_ratio, "
                    "node_count, consecutive_clean, recent_block_count, node_verdicts_json, "
                    "swarm_fingerprint, error_msg, created_at "
                    "FROM ioswarm_vhp_mint_log "
                    "WHERE device_id = ? ORDER BY created_at DESC LIMIT ?",
                    (device_id, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT id, device_id, authorized, quorum_verdict, agreement_ratio, "
                    "node_count, consecutive_clean, recent_block_count, node_verdicts_json, "
                    "swarm_fingerprint, error_msg, created_at "
                    "FROM ioswarm_vhp_mint_log "
                    "ORDER BY created_at DESC LIMIT ?",
                    (limit,),
                ).fetchall()
        result = []
        for row in rows:
            result.append({
                "id":                  row[0],
                "device_id":           row[1],
                "authorized":          bool(row[2]),
                "quorum_verdict":      row[3],
                "agreement_ratio":     row[4],
                "node_count":          row[5],
                "consecutive_clean":   row[6],
                "recent_block_count":  row[7],
                "node_verdicts":       json.loads(row[8]),
                "swarm_fingerprint":   row[9],
                "error_msg":           row[10],
                "created_at":          row[11],
            })
        return result

    # --- Phase 111: PoAd Registry ---

    def insert_poad_registry(
        self,
        device_id: str,
        poad_hash: str,
        dual_veto: bool,
        classj_verdict: "str | None",
        triage_verdict: "str | None",
        ts_ns: int,
        on_chain_tx: "str | None" = None,
    ) -> int:
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT OR IGNORE INTO poad_registry_log "
                "(device_id, poad_hash, dual_veto, classj_verdict, triage_verdict, ts_ns, on_chain_tx) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (device_id, poad_hash, int(dual_veto), classj_verdict, triage_verdict,
                 ts_ns, on_chain_tx),
            )
            return cur.lastrowid

    def get_poad_registry_log(
        self,
        device_id: "str | None" = None,
        limit: int = 20,
    ) -> "list[dict]":
        with self._conn() as conn:
            if device_id:
                rows = conn.execute(
                    "SELECT id, device_id, poad_hash, dual_veto, classj_verdict, "
                    "triage_verdict, ts_ns, on_chain_tx, created_at "
                    "FROM poad_registry_log WHERE device_id = ? "
                    "ORDER BY created_at DESC LIMIT ?",
                    (device_id, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT id, device_id, poad_hash, dual_veto, classj_verdict, "
                    "triage_verdict, ts_ns, on_chain_tx, created_at "
                    "FROM poad_registry_log ORDER BY created_at DESC LIMIT ?",
                    (limit,),
                ).fetchall()
        result = []
        for row in rows:
            result.append({
                "id":              row[0],
                "device_id":       row[1],
                "poad_hash":       row[2],
                "dual_veto":       bool(row[3]),
                "classj_verdict":  row[4],
                "triage_verdict":  row[5],
                "ts_ns":           row[6],
                "on_chain_tx":     row[7],
                "created_at":      row[8],
            })
        return result

    def update_poad_on_chain_tx(self, poad_hash: str, on_chain_tx: str) -> None:
        with self._conn() as conn:
            conn.execute(
                "UPDATE poad_registry_log SET on_chain_tx = ? WHERE poad_hash = ?",
                (on_chain_tx, poad_hash),
            )

    def get_unanchored_poad_entries(self, limit: int = 10) -> "list[dict]":
        """Return poad_registry_log rows with on_chain_tx IS NULL, oldest first."""
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT id, device_id, poad_hash, dual_veto, classj_verdict, "
                "triage_verdict, ts_ns FROM poad_registry_log "
                "WHERE on_chain_tx IS NULL ORDER BY created_at ASC LIMIT ?",
                (limit,),
            ).fetchall()
        return [
            {"id": r[0], "device_id": r[1], "poad_hash": r[2], "dual_veto": bool(r[3]),
             "classj_verdict": r[4], "triage_verdict": r[5], "ts_ns": r[6]}
            for r in rows
        ]

    # --- Phase 113: Dual-Primitive Gate ---

    def insert_dual_eligibility_check(
        self,
        device_id: str,
        poad_hash: str,
        eligible: bool,
        poac_valid: bool,
        poad_valid: bool,
    ) -> int:
        """Insert a dual-primitive eligibility check result (Phase 113)."""
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO dual_eligibility_checks "
                "(device_id, poad_hash, eligible, poac_valid, poad_valid) "
                "VALUES (?, ?, ?, ?, ?)",
                (device_id, poad_hash, int(eligible), int(poac_valid), int(poad_valid)),
            )
            return cur.lastrowid

    def get_dual_eligibility_history(self, device_id: "str | None" = None, limit: int = 100) -> "list[dict]":
        """Return dual_eligibility_checks rows, newest first. Optionally filter by device_id."""
        with self._conn() as conn:
            if device_id:
                rows = conn.execute(
                    "SELECT id, device_id, poad_hash, eligible, poac_valid, poad_valid, created_at "
                    "FROM dual_eligibility_checks WHERE device_id = ? "
                    "ORDER BY id DESC LIMIT ?",
                    (device_id, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT id, device_id, poad_hash, eligible, poac_valid, poad_valid, created_at "
                    "FROM dual_eligibility_checks ORDER BY id DESC LIMIT ?",
                    (limit,),
                ).fetchall()
        return [
            {"id": r[0], "device_id": r[1], "poad_hash": r[2],
             "eligible": bool(r[3]), "poac_valid": bool(r[4]), "poad_valid": bool(r[5]),
             "created_at": r[6]}
            for r in rows
        ]

    # --- Phase 116 — Epoch-Window Analytics ---

    def get_epoch_window_analytics(self, limit: int = 1000) -> dict:
        """Return analytics over poad_age_seconds from vhp_dual_gate_log.

        Returns: dict with total_gate5_checks, staleness_blocked_count, checked_count
        (rows with poad_age_seconds >= 0), p50/p95/p99 age in seconds, max_age_seconds,
        recommended_window_seconds (2× p95 or 86400 if <10 samples).
        """
        with self._conn() as conn:
            total = conn.execute(
                "SELECT COUNT(*) FROM vhp_dual_gate_log LIMIT ?", (limit,)
            ).fetchone()[0]
            blocked = conn.execute(
                "SELECT COUNT(*) FROM vhp_dual_gate_log WHERE epoch_window_ok = 0"
            ).fetchone()[0]
            rows = conn.execute(
                "SELECT poad_age_seconds FROM vhp_dual_gate_log "
                "WHERE poad_age_seconds >= 0 ORDER BY poad_age_seconds ASC LIMIT ?",
                (limit,),
            ).fetchall()
        ages = [r[0] for r in rows]
        n = len(ages)

        def _pct(lst, p):
            if not lst:
                return -1.0
            idx = int(len(lst) * p / 100.0)
            idx = min(idx, len(lst) - 1)
            return lst[idx]

        p50  = _pct(ages, 50)
        p95  = _pct(ages, 95)
        p99  = _pct(ages, 99)
        maxv = max(ages) if ages else -1.0
        # Recommend 2× p95, floored at 3600s (1h), capped at 604800s (7d)
        # Falls back to 86400 if fewer than 10 samples
        if n >= 10 and p95 > 0:
            rec = max(3600.0, min(604800.0, p95 * 2.0))
        else:
            rec = 86400.0
        return {
            "total_gate5_checks":      total,
            "staleness_blocked_count": blocked,
            "checked_count":           n,
            "p50_age_seconds":         p50,
            "p95_age_seconds":         p95,
            "p99_age_seconds":         p99,
            "max_age_seconds":         maxv,
            "recommended_window_seconds": rec,
        }

    # --- Phase 117 — Per-Device Epoch Freshness Heatmap ---

    def get_epoch_window_analytics_by_device(
        self, limit_per_device: int = 100, top_n: int = 20
    ) -> "list[dict]":
        """Return per-device epoch freshness analytics sorted by p95 DESC (worst first).

        Each entry: device_id, check_count, blocked_count, p50_age_seconds,
        p95_age_seconds, last_check_ts.
        Only devices with at least 1 checked entry (poad_age_seconds >= 0) are included.
        """
        with self._conn() as conn:
            device_rows = conn.execute(
                "SELECT DISTINCT device_id FROM vhp_dual_gate_log "
                "WHERE poad_age_seconds >= 0"
            ).fetchall()

        def _pct(lst, p):
            if not lst:
                return -1.0
            idx = min(int(len(lst) * p / 100.0), len(lst) - 1)
            return lst[idx]

        results = []
        for dr in device_rows:
            dev = dr[0]
            with self._conn() as conn:
                age_rows = conn.execute(
                    "SELECT poad_age_seconds, created_at FROM vhp_dual_gate_log "
                    "WHERE device_id = ? AND poad_age_seconds >= 0 "
                    "ORDER BY poad_age_seconds ASC LIMIT ?",
                    (dev, limit_per_device),
                ).fetchall()
                blocked = conn.execute(
                    "SELECT COUNT(*) FROM vhp_dual_gate_log "
                    "WHERE device_id = ? AND epoch_window_ok = 0",
                    (dev,),
                ).fetchone()[0]
                last_ts = conn.execute(
                    "SELECT MAX(created_at) FROM vhp_dual_gate_log WHERE device_id = ?",
                    (dev,),
                ).fetchone()[0]
            ages = [r[0] for r in age_rows]
            results.append({
                "device_id":       dev,
                "check_count":     len(ages),
                "blocked_count":   blocked,
                "p50_age_seconds": _pct(ages, 50),
                "p95_age_seconds": _pct(ages, 95),
                "last_check_ts":   last_ts or 0.0,
            })

        # Sort by p95 DESC — worst offenders first
        results.sort(key=lambda x: x["p95_age_seconds"], reverse=True)
        return results[:top_n]

    # --- Phase 118 — Per-Device Epoch Window Overrides ---

    def insert_device_epoch_override(
        self,
        device_id: str,
        window_seconds: float,
        reason: str = "",
        max_uses: "int | None" = None,
        expires_at: "float | None" = None,
    ) -> int:
        """Upsert a per-device epoch window override (Phase 118/119).

        INSERT OR REPLACE so subsequent calls update the override for the same device_id.
        Phase 119: max_uses (auto-expire after N successful Gate-5 checks) and
        expires_at (absolute time-based expiry) are optional; None = infinite/never.
        Returns the rowid of the inserted/replaced row.
        """
        import time as _t118
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT OR REPLACE INTO per_device_epoch_overrides "
                "(device_id, override_window_seconds, reason, max_uses, use_count, expires_at, created_at) "
                "VALUES (?, ?, ?, ?, 0, ?, ?)",
                (device_id, float(window_seconds), reason, max_uses, expires_at, _t118.time()),
            )
            return cur.lastrowid

    def get_device_epoch_override(self, device_id: str) -> "float | None":
        """Return per-device epoch override window in seconds, or None if not set (Phase 118).

        Phase 119: also returns None if the override has expired (expires_at exceeded).
        Expired overrides are deleted on read.
        """
        import time as _t119g
        with self._conn() as conn:
            row = conn.execute(
                "SELECT override_window_seconds, expires_at FROM per_device_epoch_overrides "
                "WHERE device_id = ?",
                (device_id,),
            ).fetchone()
            if row is None:
                return None
            window, expires_at = row
            # Phase 119: check time-based expiry
            if expires_at is not None and _t119g.time() > expires_at:
                conn.execute(
                    "DELETE FROM per_device_epoch_overrides WHERE device_id = ?",
                    (device_id,),
                )
                return None
        return float(window)

    def get_all_device_epoch_overrides(self) -> "list[dict]":
        """Return all per-device epoch window overrides (Phase 118)."""
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT device_id, override_window_seconds, reason, created_at "
                "FROM per_device_epoch_overrides ORDER BY created_at DESC"
            ).fetchall()
        return [
            {
                "device_id": r[0],
                "override_window_seconds": r[1],
                "reason": r[2],
                "created_at": r[3],
            }
            for r in rows
        ]

    # --- Phase 119 — Override Lifecycle Management ---

    def delete_device_epoch_override(self, device_id: str) -> bool:
        """Revoke a per-device epoch window override (Phase 119).

        Returns True if a row was deleted, False if no override was set for device_id.
        """
        with self._conn() as conn:
            cur = conn.execute(
                "DELETE FROM per_device_epoch_overrides WHERE device_id = ?",
                (device_id,),
            )
            return cur.rowcount > 0

    def increment_override_use_count(self, device_id: str) -> bool:
        """Increment use_count for a per-device override after a successful Gate-5 pass.

        Phase 119 W2: auto-graduation — when use_count reaches max_uses, the override
        self-deletes, restoring standard fleet policy for that device.
        Also checks time-based expiry (expires_at).

        Returns True if the override was consumed/expired and deleted, False otherwise.
        Non-blocking: returns False on any error (Gate-5 must not fail on this call).
        """
        import time as _t119i
        try:
            with self._conn() as conn:
                row = conn.execute(
                    "SELECT use_count, max_uses, expires_at "
                    "FROM per_device_epoch_overrides WHERE device_id = ?",
                    (device_id,),
                ).fetchone()
                if row is None:
                    return False
                use_count, max_uses, expires_at = row
                # Time-based expiry check
                if expires_at is not None and _t119i.time() > expires_at:
                    conn.execute(
                        "DELETE FROM per_device_epoch_overrides WHERE device_id = ?",
                        (device_id,),
                    )
                    return True
                # Increment use_count
                new_count = use_count + 1
                # max_uses check (None = infinite)
                if max_uses is not None and new_count >= max_uses:
                    conn.execute(
                        "DELETE FROM per_device_epoch_overrides WHERE device_id = ?",
                        (device_id,),
                    )
                    return True
                conn.execute(
                    "UPDATE per_device_epoch_overrides SET use_count = ? WHERE device_id = ?",
                    (new_count, device_id),
                )
                return False
        except Exception:
            return False

    def get_override_lifecycle_status(self) -> "list[dict]":
        """Return all overrides with full lifecycle fields (Phase 119).

        Includes max_uses, use_count, expires_at so operators can audit
        which overrides are ephemeral vs permanent.
        """
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT device_id, override_window_seconds, reason, "
                "max_uses, use_count, expires_at, created_at "
                "FROM per_device_epoch_overrides ORDER BY created_at DESC"
            ).fetchall()
        return [
            {
                "device_id":              r[0],
                "override_window_seconds": r[1],
                "reason":                 r[2],
                "max_uses":               r[3],
                "use_count":              r[4],
                "expires_at":             r[5],
                "created_at":             r[6],
            }
            for r in rows
        ]

    # --- Phase 114 — VHP Mint Dual-Primitive Gate ---

    def get_latest_poad_hash_for_device(self, device_id: str) -> "str | None":
        """Return the most recent poad_hash from poad_registry_log for device_id, or None."""
        with self._conn() as conn:
            row = conn.execute(
                "SELECT poad_hash FROM poad_registry_log "
                "WHERE device_id = ? ORDER BY id DESC LIMIT 1",
                (device_id,),
            ).fetchone()
        return row[0] if row else None

    def get_poad_ts_ns_for_device(self, device_id: str) -> "int | None":
        """Return ts_ns of the most recent poad_registry_log entry for device_id, or None."""
        with self._conn() as conn:
            row = conn.execute(
                "SELECT ts_ns FROM poad_registry_log "
                "WHERE device_id = ? ORDER BY id DESC LIMIT 1",
                (device_id,),
            ).fetchone()
        return int(row[0]) if row and row[0] is not None else None

    def insert_vhp_dual_gate_log(
        self,
        device_id: str,
        poad_hash: str,
        eligible: bool,
        poac_valid: bool,
        poad_valid: bool,
        mint_allowed: bool,
        poad_age_seconds: float = -1.0,
        epoch_window_ok: bool = True,
    ) -> int:
        import time as _t
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO vhp_dual_gate_log "
                "(device_id, poad_hash, eligible, poac_valid, poad_valid, mint_allowed, "
                "poad_age_seconds, epoch_window_ok, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (device_id, poad_hash, int(eligible), int(poac_valid),
                 int(poad_valid), int(mint_allowed),
                 float(poad_age_seconds), int(epoch_window_ok), _t.time()),
            )
            return cur.lastrowid

    def get_vhp_dual_gate_log(
        self, device_id: "str | None" = None, limit: int = 20
    ) -> "list[dict]":
        """Return vhp_dual_gate_log rows, newest first. Optionally filter by device_id."""
        with self._conn() as conn:
            if device_id:
                rows = conn.execute(
                    "SELECT id, device_id, poad_hash, eligible, poac_valid, poad_valid, "
                    "mint_allowed, poad_age_seconds, epoch_window_ok, created_at "
                    "FROM vhp_dual_gate_log "
                    "WHERE device_id = ? ORDER BY id DESC LIMIT ?",
                    (device_id, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT id, device_id, poad_hash, eligible, poac_valid, poad_valid, "
                    "mint_allowed, poad_age_seconds, epoch_window_ok, created_at "
                    "FROM vhp_dual_gate_log "
                    "ORDER BY id DESC LIMIT ?",
                    (limit,),
                ).fetchall()
        return [
            {"id": r[0], "device_id": r[1], "poad_hash": r[2],
             "eligible": bool(r[3]), "poac_valid": bool(r[4]),
             "poad_valid": bool(r[5]), "mint_allowed": bool(r[6]),
             "poad_age_seconds": r[7], "epoch_window_ok": bool(r[8]),
             "created_at": r[9]}
            for r in rows
        ]

    # --- Phase 120 — Bluetooth Transport Foundation ---

    def insert_bt_transport_log(
        self,
        device_address: str,
        sampling_rate_hz: int,
        frames_received: int,
        frames_dropped: int,
        avg_interval_ms: float,
        session_start_ts: float,
        session_end_ts: float,
    ) -> int:
        """Insert a BT transport session log entry (Phase 120). Returns row id."""
        import time as _t120
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO bt_transport_log "
                "(device_address, sampling_rate_hz, frames_received, frames_dropped, "
                "avg_interval_ms, session_start_ts, session_end_ts, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (device_address, sampling_rate_hz, frames_received, frames_dropped,
                 avg_interval_ms, session_start_ts, session_end_ts, _t120.time()),
            )
            return cur.lastrowid

    def get_bt_transport_status(self, limit: int = 10) -> "list[dict]":
        """Return most recent BT transport session logs, newest first (Phase 120)."""
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT id, device_address, sampling_rate_hz, frames_received, "
                "frames_dropped, avg_interval_ms, session_start_ts, session_end_ts, created_at "
                "FROM bt_transport_log ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [
            {
                "id":               r[0],
                "device_address":   r[1],
                "sampling_rate_hz": r[2],
                "frames_received":  r[3],
                "frames_dropped":   r[4],
                "avg_interval_ms":  r[5],
                "session_start_ts": r[6],
                "session_end_ts":   r[7],
                "created_at":       r[8],
            }
            for r in rows
        ]

    # --- Phase 123: l4_calibration_log ---

    def insert_l4_calibration_log(
        self,
        feature_dim: int,
        n_sessions: int,
        anomaly_threshold: float,
        continuity_threshold: float,
        calibration_timestamp: float,
        stale_flag: bool,
    ) -> int:
        """Record a threshold calibration run or staleness snapshot (Phase 123)."""
        import time as _t123
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO l4_calibration_log "
                "(feature_dim, n_sessions, anomaly_threshold, continuity_threshold, "
                "calibration_timestamp, stale_flag, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (feature_dim, n_sessions, float(anomaly_threshold),
                 float(continuity_threshold), float(calibration_timestamp),
                 int(stale_flag), _t123.time()),
            )
            return cur.lastrowid

    def get_l4_calibration_log(self, limit: int = 10) -> "list[dict]":
        """Return recent L4 calibration log entries, newest first (Phase 123)."""
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT id, feature_dim, n_sessions, anomaly_threshold, "
                "continuity_threshold, calibration_timestamp, stale_flag, created_at "
                "FROM l4_calibration_log ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [
            {
                "id":                    r[0],
                "feature_dim":           r[1],
                "n_sessions":            r[2],
                "anomaly_threshold":     r[3],
                "continuity_threshold":  r[4],
                "calibration_timestamp": r[5],
                "stale_flag":            bool(r[6]),
                "created_at":            r[7],
            }
            for r in rows
        ]

    # --- Phase 124: l4_threshold_tracks ---

    def insert_l4_threshold_track(
        self,
        battery_type: str,
        anomaly_threshold: float,
        continuity_threshold: float,
        n_sessions: int,
        calibrated_at: float,
        active: bool = True,
    ) -> int:
        """Insert a per-battery L4 threshold track (Phase 124).

        Bounds enforced: anomaly [5.0, 15.0]; continuity [3.0, 10.0].
        Raises ValueError on out-of-bounds to prevent threshold pollution (W1).
        """
        if not (5.0 <= anomaly_threshold <= 15.0):
            raise ValueError(
                f"anomaly_threshold {anomaly_threshold} out of range [5.0, 15.0]"
            )
        if not (3.0 <= continuity_threshold <= 10.0):
            raise ValueError(
                f"continuity_threshold {continuity_threshold} out of range [3.0, 10.0]"
            )
        import time as _t124
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO l4_threshold_tracks "
                "(battery_type, anomaly_threshold, continuity_threshold, n_sessions, "
                "calibrated_at, active, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (battery_type, float(anomaly_threshold), float(continuity_threshold),
                 int(n_sessions), float(calibrated_at), int(active), _t124.time()),
            )
            return cur.lastrowid

    def get_l4_threshold_tracks(
        self, battery_type: "str | None" = None, active_only: bool = False
    ) -> "list[dict]":
        """Return L4 threshold tracks, newest first (Phase 124)."""
        conditions = []
        params: list = []
        if battery_type is not None:
            conditions.append("battery_type = ?")
            params.append(battery_type)
        if active_only:
            conditions.append("active = 1")
        where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
        with self._conn() as conn:
            rows = conn.execute(
                f"SELECT id, battery_type, anomaly_threshold, continuity_threshold, "
                f"n_sessions, calibrated_at, active, created_at "
                f"FROM l4_threshold_tracks {where} ORDER BY id DESC",
                params,
            ).fetchall()
        return [
            {
                "id":                   r[0],
                "battery_type":         r[1],
                "anomaly_threshold":    r[2],
                "continuity_threshold": r[3],
                "n_sessions":           r[4],
                "calibrated_at":        r[5],
                "active":               bool(r[6]),
                "created_at":           r[7],
            }
            for r in rows
        ]

    # --- Phase 121: separation_ratio_snapshots ---

    def insert_separation_ratio_snapshot(
        self,
        pooled_ratio: float,
        bt_strat_ratio: float,
        n_sessions: int,
        n_players: int,
        active_features: int,
        tournament_ready: bool,
        ci_lower: float = 0.0,
        ci_upper: float = 0.0,
        n_bootstrap: int = 0,
    ) -> int:
        """Insert a separation ratio snapshot (Phase 121).
        Phase 168: ci_lower/ci_upper/n_bootstrap from bootstrap resampling (optional).
        """
        import time as _t121
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO separation_ratio_snapshots "
                "(pooled_ratio, bt_strat_ratio, n_sessions, n_players, active_features, "
                "tournament_ready, ci_lower, ci_upper, n_bootstrap, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (pooled_ratio, bt_strat_ratio, n_sessions, n_players, active_features,
                 int(tournament_ready), ci_lower, ci_upper, n_bootstrap, _t121.time()),
            )
            return cur.lastrowid

    def get_separation_ratio_status(self, limit: int = 1) -> "list[dict]":
        """Return most recent separation ratio snapshots, newest first (Phase 121/168)."""
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT id, pooled_ratio, bt_strat_ratio, n_sessions, n_players, "
                "active_features, tournament_ready, "
                "COALESCE(ci_lower, 0.0) as ci_lower, "
                "COALESCE(ci_upper, 0.0) as ci_upper, "
                "COALESCE(n_bootstrap, 0) as n_bootstrap, "
                "created_at "
                "FROM separation_ratio_snapshots ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [
            {
                "id":               r[0],
                "pooled_ratio":     r[1],
                "bt_strat_ratio":   r[2],
                "n_sessions":       r[3],
                "n_players":        r[4],
                "active_features":  r[5],
                "tournament_ready": bool(r[6]),
                "ci_lower":         float(r[7]),
                "ci_upper":         float(r[8]),
                "n_bootstrap":      int(r[9]),
                "created_at":       r[10],
            }
            for r in rows
        ]

    # --- Phase 122: confidence_multiplier_log ---

    def insert_confidence_multiplier_log(
        self,
        device_id: str,
        original_score: int,
        multiplier: float,
        final_score: int,
        bt_strat_ratio: float,
    ) -> int:
        """Log a confidence_score multiplier application (Phase 122). Non-blocking callers."""
        import time as _t122
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO confidence_multiplier_log "
                "(device_id, original_score, multiplier, final_score, bt_strat_ratio, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (device_id, original_score, float(multiplier), final_score,
                 float(bt_strat_ratio), _t122.time()),
            )
            return cur.lastrowid

    def get_confidence_multiplier_log(
        self,
        device_id: "str | None" = None,
        limit: int = 10,
    ) -> "list[dict]":
        """Return recent confidence multiplier log entries, newest first (Phase 122)."""
        with self._conn() as conn:
            if device_id is not None:
                rows = conn.execute(
                    "SELECT id, device_id, original_score, multiplier, final_score, "
                    "bt_strat_ratio, created_at FROM confidence_multiplier_log "
                    "WHERE device_id=? ORDER BY id DESC LIMIT ?",
                    (device_id, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT id, device_id, original_score, multiplier, final_score, "
                    "bt_strat_ratio, created_at FROM confidence_multiplier_log "
                    "ORDER BY id DESC LIMIT ?",
                    (limit,),
                ).fetchall()
        return [
            {
                "id":             r[0],
                "device_id":      r[1],
                "original_score": r[2],
                "multiplier":     r[3],
                "final_score":    r[4],
                "bt_strat_ratio": r[5],
                "created_at":     r[6],
            }
            for r in rows
        ]

    # --- Phase 125: Per-Battery L4 Calibration Runs ---

    def insert_l4_battery_calibration_run(
        self,
        battery_type: str,
        anomaly_threshold: float,
        continuity_threshold: float,
        n_sessions: int,
        calibration_feature_dim: int = 13,
        notes: "str | None" = None,
    ) -> int:
        """Insert a per-battery L4 calibration run audit record (Phase 125).

        Records each apply operation for traceability.
        Returns the new row id.
        """
        with self._conn() as conn:
            cur = conn.execute(
                """INSERT INTO l4_battery_calibration_runs
                   (battery_type, anomaly_threshold, continuity_threshold,
                    n_sessions, calibration_feature_dim, notes, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    battery_type,
                    float(anomaly_threshold),
                    float(continuity_threshold),
                    int(n_sessions),
                    int(calibration_feature_dim),
                    notes,
                    time.time(),
                ),
            )
            return cur.lastrowid

    def get_l4_battery_calibration_runs(self, limit: int = 10) -> "list[dict]":
        """Return recent per-battery L4 calibration run records, newest first (Phase 125)."""
        with self._conn() as conn:
            rows = conn.execute(
                """SELECT id, battery_type, anomaly_threshold, continuity_threshold,
                          n_sessions, calibration_feature_dim, notes, created_at
                   FROM l4_battery_calibration_runs
                   ORDER BY id DESC
                   LIMIT ?""",
                (limit,),
            ).fetchall()
        return [
            {
                "id":                      r[0],
                "battery_type":            r[1],
                "anomaly_threshold":       r[2],
                "continuity_threshold":    r[3],
                "n_sessions":              r[4],
                "calibration_feature_dim": r[5],
                "notes":                   r[6],
                "created_at":              r[7],
            }
            for r in rows
        ]

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

    def get_l4_router_log(self, limit: int = 50) -> "list[dict]":
        """Return recent L4 threshold router lookup entries, newest first (Phase 126)."""
        with self._conn() as conn:
            rows = conn.execute(
                """SELECT id, battery_type, threshold_source, anomaly_used,
                          continuity_used, created_at
                   FROM l4_threshold_router_log
                   ORDER BY id DESC
                   LIMIT ?""",
                (limit,),
            ).fetchall()
        return [
            {
                "id":               r[0],
                "battery_type":     r[1],
                "threshold_source": r[2],
                "anomaly_used":     r[3],
                "continuity_used":  r[4],
                "created_at":       r[5],
            }
            for r in rows
        ]

    # --- Phase 127: Tournament Preflight Log ---

    def insert_tournament_preflight_log(
        self,
        separation_ok: bool,
        l4_ok: bool,
        gate_ok: bool,
        cert_ok: bool,
        audit_ok: bool,
        dual_gate_warned: bool = False,
        epoch_window_warned: bool = False,
        ioswarm_warned: bool = False,
        overall_pass: bool = False,
        conditions_json: str = "{}",
        biometric_ttl_ok: bool = True,
        all_pairs_p0_ok: bool = False,
        ait_defensibility_ok: bool = False,
    ) -> int:
        """Insert a tournament preflight run record (Phase 127; Phase 196 biometric_ttl_ok; Phase 197 all_pairs_p0_ok; Phase 231 ait_defensibility_ok).

        Returns the new row id.
        """
        with self._conn() as conn:
            cur = conn.execute(
                """INSERT INTO tournament_preflight_log
                   (separation_ok, l4_ok, gate_ok, cert_ok, audit_ok,
                    dual_gate_warned, epoch_window_warned, ioswarm_warned,
                    overall_pass, conditions_json, biometric_ttl_ok, all_pairs_p0_ok,
                    ait_defensibility_ok, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    int(separation_ok), int(l4_ok), int(gate_ok),
                    int(cert_ok), int(audit_ok),
                    int(dual_gate_warned), int(epoch_window_warned), int(ioswarm_warned),
                    int(overall_pass), conditions_json,
                    int(biometric_ttl_ok), int(all_pairs_p0_ok),
                    int(ait_defensibility_ok),
                    time.time(),
                ),
            )
            return cur.lastrowid

    def get_tournament_preflight_status(self, limit: int = 5) -> "list[dict]":
        """Return recent tournament preflight run records, newest first (Phase 127; Phase 196; Phase 197; Phase 231)."""
        with self._conn() as conn:
            rows = conn.execute(
                """SELECT id, separation_ok, l4_ok, gate_ok, cert_ok, audit_ok,
                          dual_gate_warned, epoch_window_warned, ioswarm_warned,
                          overall_pass, conditions_json, biometric_ttl_ok, all_pairs_p0_ok,
                          ait_defensibility_ok, created_at
                   FROM tournament_preflight_log
                   ORDER BY id DESC
                   LIMIT ?""",
                (limit,),
            ).fetchall()
        return [
            {
                "id":                    r[0],
                "separation_ok":         bool(r[1]),
                "l4_ok":                 bool(r[2]),
                "gate_ok":               bool(r[3]),
                "cert_ok":               bool(r[4]),
                "audit_ok":              bool(r[5]),
                "dual_gate_warned":      bool(r[6]),
                "epoch_window_warned":   bool(r[7]),
                "ioswarm_warned":        bool(r[8]),
                "overall_pass":          bool(r[9]),
                "conditions_json":       r[10],
                "biometric_ttl_ok":       bool(r[11]) if r[11] is not None else True,
                "all_pairs_p0_ok":        bool(r[12]) if r[12] is not None else False,
                "ait_defensibility_ok":   bool(r[13]) if r[13] is not None else False,
                "created_at":             r[14],
            }
            for r in rows
        ]

    # --- Phase 128: Tournament Readiness Score (uses existing protocol_intelligence_reports) ---

    def insert_readiness_score(
        self,
        score: float,
        breakdown_json: str,
        conditions_met: int,
    ) -> int:
        """Insert a tournament readiness score into protocol_intelligence_reports (Phase 128).

        Stores: score in protocol_health_score, breakdown in components_json,
        conditions_met count in recommendation, ready_for_live_mode=score>=0.90.
        Returns row id.
        """
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO protocol_intelligence_reports "
                "(protocol_health_score, components_json, recommendation, "
                "ready_for_live_mode, created_at) "
                "VALUES (?,?,?,?,?)",
                (
                    float(score),
                    breakdown_json,
                    str(conditions_met),
                    int(score >= 0.90),
                    time.time(),
                ),
            )
            return cur.lastrowid

    def get_readiness_scores(self, limit: int = 10) -> "list[dict]":
        """Return recent tournament readiness score reports, newest first (Phase 128)."""
        import json as _json
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT id, protocol_health_score AS score, components_json, "
                "recommendation AS conditions_met_str, ready_for_live_mode, created_at "
                "FROM protocol_intelligence_reports "
                "ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        result = []
        for row in rows:
            d = dict(row)
            try:
                d["breakdown"] = _json.loads(d.get("components_json") or "{}")
            except (ValueError, TypeError):
                d["breakdown"] = {}
            try:
                d["conditions_met"] = int(d.get("conditions_met_str") or "0")
            except (ValueError, TypeError):
                d["conditions_met"] = 0
            result.append(d)
        return result

    # --- Phase 129: Separation Ratio Breakthrough Log ---

    def insert_separation_ratio_breakthrough(
        self,
        before_ratio: float,
        after_ratio: float,
        n_players: int,
        feature_count: int,
    ) -> int:
        """Insert a separation ratio breakthrough event (Phase 129)."""
        now = time.time()
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO separation_ratio_breakthrough_log "
                "(before_ratio, after_ratio, n_players, feature_count, breakthrough_at, created_at) "
                "VALUES (?,?,?,?,?,?)",
                (float(before_ratio), float(after_ratio), int(n_players),
                 int(feature_count), now, now),
            )
            return cur.lastrowid

    def get_separation_ratio_breakthrough(self, limit: int = 5) -> "list[dict]":
        """Return recent breakthrough log entries, newest first (Phase 129)."""
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT id, before_ratio, after_ratio, n_players, feature_count, "
                "breakthrough_at, created_at "
                "FROM separation_ratio_breakthrough_log "
                "ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]

    # --- Phase 130A: VAPISwarmOperatorGate validation log ---

    def insert_swarm_quorum_validation(
        self,
        node_count: int,
        distinct_stakers: int,
        quorum_valid: bool,
        gate_address: str = "",
    ) -> int:
        """Insert a swarm quorum validation result (Phase 130A)."""
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO swarm_quorum_validation_log "
                "(node_count, distinct_stakers, quorum_valid, gate_address, created_at) "
                "VALUES (?,?,?,?,?)",
                (int(node_count), int(distinct_stakers),
                 1 if quorum_valid else 0, str(gate_address), time.time()),
            )
            return cur.lastrowid

    def get_swarm_quorum_validation_log(self, limit: int = 10) -> "list[dict]":
        """Return recent swarm quorum validation entries, newest first (Phase 130A)."""
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT id, node_count, distinct_stakers, quorum_valid, gate_address, created_at "
                "FROM swarm_quorum_validation_log "
                "ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]

    def insert_ioswarm_node_registry(self, node_url: str, staker_address: str = "", active: bool = True, node_version: str = "") -> int:
        """Phase 131: Register an ioSwarm live node URL."""
        with self._conn() as con:
            cur = con.execute(
                "INSERT OR IGNORE INTO ioswarm_node_registry "
                "(node_url, staker_address, active, node_version, registered_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (node_url, staker_address, int(active), node_version, __import__("time").time()),
            )
            return cur.lastrowid or 0

    def get_ioswarm_node_registry(self, active_only: bool = False) -> list:
        """Phase 131: Return registered ioSwarm node entries."""
        query = "SELECT * FROM ioswarm_node_registry"
        if active_only:
            query += " WHERE active=1"
        query += " ORDER BY registered_at ASC"
        with self._conn() as con:
            rows = con.execute(query).fetchall()
        return [dict(r) for r in rows]

    def update_ioswarm_node_last_seen(self, node_url: str, ts: float, staker_address: str = "") -> None:
        """Phase 131: Update last_seen_ts for a registered ioSwarm node."""
        with self._conn() as con:
            if staker_address:
                con.execute(
                    "UPDATE ioswarm_node_registry SET last_seen_ts=?, staker_address=? WHERE node_url=?",
                    (ts, staker_address, node_url),
                )
            else:
                con.execute(
                    "UPDATE ioswarm_node_registry SET last_seen_ts=? WHERE node_url=?",
                    (ts, node_url),
                )

    # ------------------------------------------------------------------
    # Phase 132: IoSwarm Node Health Log
    # ------------------------------------------------------------------

    def insert_ioswarm_node_health(
        self,
        node_url: str,
        healthy: bool,
        latency_ms: float,
        staker_address: str = "",
        error_msg: str = "",
    ) -> int:
        """Phase 132: Record a health poll result for a live ioSwarm node."""
        polled_at = time.time()
        with self._conn() as con:
            cur = con.execute(
                "INSERT INTO ioswarm_node_health_log "
                "(node_url, healthy, latency_ms, staker_address, error_msg, polled_at, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (node_url, int(healthy), latency_ms, staker_address, error_msg, polled_at, polled_at),
            )
            return cur.lastrowid

    def get_ioswarm_node_health(self, node_url: str | None = None, limit: int = 50) -> list:
        """Phase 132: Retrieve recent health poll records, optionally filtered by node_url."""
        with self._conn() as con:
            if node_url:
                rows = con.execute(
                    "SELECT * FROM ioswarm_node_health_log WHERE node_url=? "
                    "ORDER BY polled_at DESC LIMIT ?",
                    (node_url, limit),
                ).fetchall()
            else:
                rows = con.execute(
                    "SELECT * FROM ioswarm_node_health_log ORDER BY polled_at DESC LIMIT ?",
                    (limit,),
                ).fetchall()
        return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    # Phase 133: IoSwarm PoAd Auto-Anchor
    # ------------------------------------------------------------------

    def insert_ioswarm_poad_anchor(
        self,
        device_id: str,
        session_id: str = "",
        dual_veto: bool = False,
        swarm_fingerprint: str = "",
        poad_hash: str = "",
        on_chain_tx: str | None = None,
        anchor_status: str = "pending",
    ) -> int:
        """Phase 133: Insert a PoAd auto-anchor record."""
        with self._conn() as conn:
            cur = conn.execute(
                """INSERT INTO ioswarm_poad_anchor_log
                   (device_id, session_id, dual_veto, swarm_fingerprint,
                    poad_hash, on_chain_tx, anchor_status, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (device_id, session_id, int(dual_veto), swarm_fingerprint,
                 poad_hash, on_chain_tx, anchor_status, time.time()),
            )
            return cur.lastrowid

    def update_ioswarm_poad_anchor_tx(
        self,
        anchor_id: int,
        on_chain_tx: str,
        anchor_status: str,
    ) -> None:
        """Phase 133: Update an anchor record's tx hash and status."""
        with self._conn() as conn:
            conn.execute(
                "UPDATE ioswarm_poad_anchor_log SET on_chain_tx=?, anchor_status=? WHERE id=?",
                (on_chain_tx, anchor_status, anchor_id),
            )

    def get_ioswarm_poad_anchor_log(self, limit: int = 50) -> list:
        """Phase 133: Retrieve recent PoAd anchor records, newest first."""
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM ioswarm_poad_anchor_log ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    # Phase 131B: USB Stability Monitor — PS5 coexistence logging
    # ------------------------------------------------------------------

    def insert_usb_reconnect_log(
        self,
        device_address: str = "",
        disconnect_reason: str = "",
        consecutive_fb_timeouts: int = 0,
        ps5_compat_mode_active: bool = False,
        session_id: str = "",
    ) -> int:
        """Phase 131B: Log a USB disconnect/instability event from the HID feedback path.

        Called when _consecutive_fb_timeouts exceeds the auto-log threshold, indicating
        the HID output write path (LED/haptic) is causing USB instability — the root cause
        of the PS5 reconnect notification. VAPI-exclusive: only VAPI writes HID output
        to a DualShock Edge while simultaneously maintaining a live biometric PoAC stream.
        """
        import time as _t
        with self._conn() as con:
            cur = con.execute(
                "INSERT INTO usb_reconnect_log "
                "(device_address, disconnect_reason, consecutive_fb_timeouts, "
                "ps5_compat_mode_active, session_id, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    device_address,
                    disconnect_reason,
                    consecutive_fb_timeouts,
                    int(ps5_compat_mode_active),
                    session_id,
                    _t.time(),
                ),
            )
            return cur.lastrowid or 0

    def get_usb_stability_status(self, limit: int = 50) -> dict:
        """Phase 131B: Return USB stability summary for /agent/usb-stability-status.

        Returns disconnect_count, last_disconnect_ts, and recent log entries. Used by
        the operator to diagnose PS5 coexistence issues and decide whether to enable
        ps5_compat_mode (suppresses all HID output writes, eliminating USB drops at
        the cost of no LED/haptic feedback during gameplay).
        """
        with self._conn() as con:
            rows = con.execute(
                "SELECT * FROM usb_reconnect_log ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        entries = [dict(r) for r in rows]
        last_ts = entries[0]["created_at"] if entries else 0.0
        return {
            "disconnect_count": len(entries),
            "last_disconnect_ts": last_ts,
            "entries": entries,
        }

    # ---------------------------------------------------------------------------
    # Phase 134 — L4 Recalibration Jobs
    # ---------------------------------------------------------------------------

    def insert_l4_recalibration_job(self, started_at: float) -> int:
        """Insert a new recalibration job with status='running'. Returns row id."""
        with self._conn() as con:
            cur = con.execute(
                "INSERT INTO l4_recalibration_jobs (started_at, status, created_at)"
                " VALUES (?, 'running', ?)",
                (started_at, time.time()),
            )
            return cur.lastrowid

    def update_l4_recalibration_job(
        self,
        job_id: int,
        status: str,
        sessions_processed: int,
        anomaly_result: float,
        continuity_result: float,
        completed_at: float,
        error: str | None = None,
    ) -> None:
        """Update a recalibration job record (Phase 134)."""
        with self._conn() as con:
            con.execute(
                "UPDATE l4_recalibration_jobs"
                " SET status=?, sessions_processed=?, anomaly_result=?,"
                "     continuity_result=?, completed_at=?, error=?"
                " WHERE id=?",
                (status, sessions_processed, anomaly_result,
                 continuity_result, completed_at, error, job_id),
            )

    def get_l4_recalibration_jobs(self, limit: int = 10) -> list:
        """Return the most recent L4 recalibration jobs ordered by id DESC (Phase 134)."""
        with self._conn() as con:
            rows = con.execute(
                "SELECT * FROM l4_recalibration_jobs ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]

    # Phase 135 — Tournament Activation Chain Log
    # -------------------------------------------------------------------------

    def insert_tournament_activation_chain(
        self,
        event_type: str,
        separation_ratio: float,
        n_players: int,
        gate_open_notified: bool = False,
        notes: str | None = None,
    ) -> int:
        """Insert a tournament activation chain event (Phase 135)."""
        with self._conn() as con:
            cur = con.execute(
                "INSERT INTO tournament_activation_chain_log "
                "(event_type, separation_ratio, n_players, gate_open_notified, "
                " auto_activate_blocked, operator_action_required, notes, created_at)"
                " VALUES (?,?,?,?,1,1,?,?)",
                (event_type, separation_ratio, n_players,
                 1 if gate_open_notified else 0,
                 notes, time.time()),
            )
        return cur.lastrowid  # type: ignore[return-value]

    def get_tournament_activation_chain(self, limit: int = 10) -> list:
        """Return tournament activation chain log entries ordered by id DESC (Phase 135)."""
        with self._conn() as con:
            rows = con.execute(
                "SELECT * FROM tournament_activation_chain_log ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]

    # Phase 148 — Agent Calibration Health (ACIM)
    # -------------------------------------------------------------------------

    def insert_agent_calibration_health(
        self,
        agent_id: int,
        agent_name: str,
        test_name: str,
        result: str,
        details: str = "",
    ) -> int:
        """Insert an agent self-test result (Phase 148)."""
        with self._conn() as con:
            cur = con.execute(
                "INSERT INTO agent_calibration_health "
                "(agent_id, agent_name, test_name, result, details, calibration_ts, created_at)"
                " VALUES (?,?,?,?,?,?,?)",
                (agent_id, agent_name, test_name, result, details,
                 time.time(), time.time()),
            )
        return cur.lastrowid  # type: ignore[return-value]

    def get_agent_calibration_health(self, limit: int = 32, agent_id: int | None = None) -> list:
        """Return agent calibration health rows ordered by id DESC (Phase 148)."""
        with self._conn() as con:
            if agent_id is not None:
                rows = con.execute(
                    "SELECT * FROM agent_calibration_health WHERE agent_id=? ORDER BY id DESC LIMIT ?",
                    (agent_id, limit),
                ).fetchall()
            else:
                rows = con.execute(
                    "SELECT * FROM agent_calibration_health ORDER BY id DESC LIMIT ?",
                    (limit,),
                ).fetchall()
        return [dict(r) for r in rows]

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

    def insert_separation_defensibility_log(
        self,
        session_type: str,
        n_sessions_total: int,
        n_per_player: dict,
        min_n_per_player: int,
        defensible: bool,
        ratio: float,
        all_pairs_above_1: bool,
    ) -> int:
        """Insert a separation defensibility report (Phase 150/151).

        defensible=True requires ALL players >= min_n_per_player AND ratio > 1.0.
        Closes WIF-010 formally by tracking per-player N vs target.

        Phase 151 P0 — W1-011: session_type must be in STRUCTURED_PROBE_TYPES.
        Raises ValueError on invalid session_type to prevent free-form corpus
        contamination of the defensibility gate.
        """
        if session_type not in self.STRUCTURED_PROBE_TYPES:
            raise ValueError(
                f"Invalid session_type {session_type!r} for defensibility log. "
                f"Must be one of {sorted(self.STRUCTURED_PROBE_TYPES)}. "
                "Free-form gameplay sessions must not enter the defensibility gate "
                "(W1-011: session type mixing integrity)."
            )
        import json as _json150
        with self._conn() as con:
            cur = con.execute(
                "INSERT INTO separation_defensibility_log "
                "(session_type, n_sessions_total, n_per_player_json, min_n_per_player, "
                " defensible, ratio, all_pairs_above_1, created_at)"
                " VALUES (?,?,?,?,?,?,?,?)",
                (
                    session_type,
                    n_sessions_total,
                    _json150.dumps(n_per_player),
                    min_n_per_player,
                    1 if defensible else 0,
                    float(ratio),
                    1 if all_pairs_above_1 else 0,
                    time.time(),
                ),
            )
        return cur.lastrowid  # type: ignore[return-value]

    # --- Phase 208: CorpusRatioRegressionGuard (WIF-039 W1+W2) ---

    def insert_separation_defensibility_log_guarded(
        self,
        session_type: str,
        n_sessions_total: int,
        n_per_player: dict,
        min_n_per_player: int,
        defensible: bool,
        ratio: float,
        all_pairs_above_1: bool,
        guard_enabled: bool = False,
    ) -> int:
        """Guarded variant of insert_separation_defensibility_log (Phase 208 — WIF-039 W1).

        When guard_enabled=True (CORPUS_RATIO_REGRESSION_GUARD_ENABLED=true):
          - If all_pairs_above_1=True: insert a breakthrough milestone in
            corpus_ratio_regression_guard_log with a tamper-evident provenance chain.
          - If all_pairs_above_1=False AND a prior breakthrough exists for this probe type
            (any prior separation_defensibility_log row had all_pairs_above_1=True):
            raises CorpusRegressionError UNLESS an override exists in
            corpus_regression_override_log for this probe type.
          - This is the Mode-6 ratchet for separation ratio: once all_pairs_above_1
            is reached, it cannot silently regress without an explicit override record.

        When guard_enabled=False (default): behaves identically to
        insert_separation_defensibility_log — no regression check is performed.

        The Ratio Provenance Chain links consecutive guard log entries via:
          provenance_hash = SHA-256(prev_hash + str(ratio) + str(n) + probe_type + str(ts_ns))
        This gives operators an auditable lineage of every milestone.
        """
        import hashlib as _hl208
        # Always insert the main defensibility log entry (guard only adds a side effect)
        row_id = self.insert_separation_defensibility_log(
            session_type=session_type,
            n_sessions_total=n_sessions_total,
            n_per_player=n_per_player,
            min_n_per_player=min_n_per_player,
            defensible=defensible,
            ratio=ratio,
            all_pairs_above_1=all_pairs_above_1,
        )

        if not guard_enabled:
            return row_id

        with self._conn() as con:
            # Check whether a prior breakthrough exists for this probe type
            breakthrough_row = con.execute(
                "SELECT id FROM separation_defensibility_log "
                "WHERE session_type=? AND all_pairs_above_1=1 ORDER BY id ASC LIMIT 1",
                (session_type,),
            ).fetchone()
            prior_breakthrough = breakthrough_row is not None

            if not all_pairs_above_1 and prior_breakthrough:
                # Regression detected — check for an authorized override
                override_row = con.execute(
                    "SELECT id FROM corpus_regression_override_log "
                    "WHERE probe_type=? ORDER BY id DESC LIMIT 1",
                    (session_type,),
                ).fetchone()
                if override_row is None:
                    raise CorpusRegressionError(
                        f"Corpus ratio regression blocked for probe_type={session_type!r}: "
                        f"all_pairs_above_1 was previously True but new entry has "
                        f"all_pairs_above_1=False (ratio={ratio:.3f}). "
                        "Call insert_corpus_regression_override() with a reason before inserting. "
                        "(Phase 208: WIF-039 W1 — CorpusRatioRegressionGuard)"
                    )

            # Record milestone in provenance chain when all_pairs_above_1=True
            if all_pairs_above_1:
                last_guard = con.execute(
                    "SELECT provenance_hash FROM corpus_ratio_regression_guard_log "
                    "WHERE probe_type=? ORDER BY id DESC LIMIT 1",
                    (session_type,),
                ).fetchone()
                prev_hash = last_guard["provenance_hash"] if last_guard else ""
                ts_ns = int(time.time() * 1e9)
                prov_input = f"{prev_hash}{ratio}{n_sessions_total}{session_type}{ts_ns}"
                prov_hash = _hl208.sha256(prov_input.encode()).hexdigest()
                con.execute(
                    "INSERT INTO corpus_ratio_regression_guard_log "
                    "(probe_type, ratio, n_sessions_total, all_pairs_above_1, "
                    " provenance_hash, prev_hash, created_at) VALUES (?,?,?,?,?,?,?)",
                    (
                        session_type,
                        float(ratio),
                        n_sessions_total,
                        1,
                        prov_hash,
                        prev_hash,
                        time.time(),
                    ),
                )

        return row_id

    def insert_corpus_regression_override(
        self,
        probe_type: str,
        old_ratio: float,
        new_ratio: float,
        reason: str,
    ) -> int:
        """Record an authorized corpus ratio regression override (Phase 208 — WIF-039 W2).

        Allows insert_separation_defensibility_log_guarded to proceed with
        all_pairs_above_1=False after a prior breakthrough, provided this
        override record exists.

        override_hash = SHA-256(probe_type + str(old_ratio) + str(new_ratio) + reason + str(ts_ns))
        """
        import hashlib as _hl208o
        ts_ns = int(time.time() * 1e9)
        ov_input = f"{probe_type}{old_ratio}{new_ratio}{reason}{ts_ns}"
        ov_hash = _hl208o.sha256(ov_input.encode()).hexdigest()
        with self._conn() as con:
            cur = con.execute(
                "INSERT INTO corpus_regression_override_log "
                "(probe_type, old_ratio, new_ratio, reason, override_hash, created_at) "
                "VALUES (?,?,?,?,?,?)",
                (probe_type, float(old_ratio), float(new_ratio), reason, ov_hash, time.time()),
            )
        return cur.lastrowid  # type: ignore[return-value]

    def get_corpus_regression_guard_status(
        self, probe_type: str | None = None
    ) -> dict:
        """Return corpus ratio regression guard summary (Phase 208).

        Returns 7 keys:
          guard_active / breakthrough_ratio / breakthrough_n /
          provenance_hash / override_count / probe_type / timestamp
        """
        import time as _t208
        with self._conn() as con:
            if probe_type:
                guard_row = con.execute(
                    "SELECT ratio, n_sessions_total, provenance_hash, created_at "
                    "FROM corpus_ratio_regression_guard_log "
                    "WHERE probe_type=? ORDER BY id DESC LIMIT 1",
                    (probe_type,),
                ).fetchone()
                override_count = con.execute(
                    "SELECT COUNT(*) AS cnt FROM corpus_regression_override_log "
                    "WHERE probe_type=?",
                    (probe_type,),
                ).fetchone()["cnt"]
            else:
                guard_row = con.execute(
                    "SELECT ratio, n_sessions_total, provenance_hash, created_at "
                    "FROM corpus_ratio_regression_guard_log ORDER BY id DESC LIMIT 1"
                ).fetchone()
                override_count = con.execute(
                    "SELECT COUNT(*) AS cnt FROM corpus_regression_override_log"
                ).fetchone()["cnt"]

        guard_active = guard_row is not None
        return {
            "guard_active":      guard_active,
            "breakthrough_ratio": float(guard_row["ratio"]) if guard_row else None,
            "breakthrough_n":    int(guard_row["n_sessions_total"]) if guard_row else None,
            "provenance_hash":   guard_row["provenance_hash"] if guard_row else None,
            "override_count":    int(override_count),
            "probe_type":        probe_type,
            "timestamp":         _t208.time(),
        }

    # --- Phase 215: l4_dim_sync_log ---

    def insert_l4_dim_sync(
        self,
        from_dim: int,
        to_dim: int,
        anomaly_threshold: float,
        continuity_threshold: float,
        n_sessions: int = 0,
        sync_reason: str = "",
    ) -> int:
        """Record an L4 dimension sync confirmation (Phase 215).

        Called when live_feature_dim != calibration_feature_dim but the added feature is
        structurally zero in gameplay sessions (touchpad_spatial_entropy, index 12),
        confirming thresholds remain valid without a full recalibration run.

        Returns the new row id.
        """
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO l4_dim_sync_log "
                "(from_dim, to_dim, anomaly_threshold, continuity_threshold, n_sessions, "
                "sync_reason, sync_completed, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (int(from_dim), int(to_dim), float(anomaly_threshold),
                 float(continuity_threshold), int(n_sessions), sync_reason, 1, time.time()),
            )
            return cur.lastrowid  # type: ignore[return-value]

    def get_l4_dim_sync_status(self) -> dict:
        """Return the latest L4 dimension sync status (Phase 215).

        Returns 6 keys:
          sync_completed / from_dim / to_dim / anomaly_threshold / continuity_threshold / timestamp
        """
        import time as _t215
        with self._conn() as conn:
            row = conn.execute(
                "SELECT from_dim, to_dim, anomaly_threshold, continuity_threshold, "
                "sync_completed, created_at FROM l4_dim_sync_log ORDER BY id DESC LIMIT 1"
            ).fetchone()
        if row is None:
            return {
                "sync_completed":        False,
                "from_dim":              None,
                "to_dim":                None,
                "anomaly_threshold":     None,
                "continuity_threshold":  None,
                "timestamp":             _t215.time(),
            }
        return {
            "sync_completed":        bool(row["sync_completed"]),
            "from_dim":              int(row["from_dim"]),
            "to_dim":                int(row["to_dim"]),
            "anomaly_threshold":     float(row["anomaly_threshold"]),
            "continuity_threshold":  float(row["continuity_threshold"]),
            "timestamp":             _t215.time(),
        }

    # --- Phase 216: per_pair_gap_log ---

    def insert_per_pair_gap(
        self,
        session_type: str,
        pair_key: str,
        player_i: str,
        player_j: str,
        distance: float,
        above_1_0: bool,
        n_sessions_i: int = 0,
        n_sessions_j: int = 0,
        analysis_date: str = "",
    ) -> int:
        """Insert a per-pair Mahalanobis distance record (Phase 216)."""
        import time as _t216
        if not analysis_date:
            import datetime as _dt216
            analysis_date = _dt216.date.today().isoformat()
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO per_pair_gap_log "
                "(session_type, pair_key, player_i, player_j, distance, above_1_0, "
                "n_sessions_i, n_sessions_j, analysis_date, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    session_type, pair_key, player_i, player_j,
                    float(distance), int(bool(above_1_0)),
                    int(n_sessions_i), int(n_sessions_j),
                    analysis_date, _t216.time(),
                ),
            )
            return cur.lastrowid  # type: ignore[return-value]

    def get_per_pair_gap_status(self, session_type: str | None = None) -> dict:
        """Return per-pair gap distances for the most recent analysis run (Phase 216).

        Returns dict with keys:
          all_pairs_above_1 / pairs / session_type / pair_count / timestamp
        """
        import time as _t216
        with self._conn() as conn:
            if session_type:
                rows = conn.execute(
                    "SELECT pair_key, player_i, player_j, distance, above_1_0, "
                    "n_sessions_i, n_sessions_j, analysis_date FROM per_pair_gap_log "
                    "WHERE session_type=? ORDER BY created_at DESC LIMIT 50",
                    (session_type,),
                ).fetchall()
            else:
                # Return rows from the most recent analysis_date across all session types
                latest = conn.execute(
                    "SELECT analysis_date FROM per_pair_gap_log ORDER BY created_at DESC LIMIT 1"
                ).fetchone()
                if latest is None:
                    return {
                        "all_pairs_above_1": False,
                        "pairs": [],
                        "session_type": None,
                        "pair_count": 0,
                        "timestamp": _t216.time(),
                    }
                rows = conn.execute(
                    "SELECT pair_key, player_i, player_j, distance, above_1_0, "
                    "n_sessions_i, n_sessions_j, analysis_date FROM per_pair_gap_log "
                    "WHERE analysis_date=? ORDER BY distance ASC",
                    (latest["analysis_date"],),
                ).fetchall()

        if not rows:
            return {
                "all_pairs_above_1": False,
                "pairs": [],
                "session_type": session_type,
                "pair_count": 0,
                "timestamp": _t216.time(),
            }

        pairs = [
            {
                "pair_key": r["pair_key"],
                "player_i": r["player_i"],
                "player_j": r["player_j"],
                "distance": float(r["distance"]),
                "above_1_0": bool(r["above_1_0"]),
                "n_sessions_i": int(r["n_sessions_i"]),
                "n_sessions_j": int(r["n_sessions_j"]),
            }
            for r in rows
        ]
        all_above = all(p["above_1_0"] for p in pairs)
        return {
            "all_pairs_above_1": all_above,
            "pairs": pairs,
            "session_type": rows[0]["analysis_date"],
            "pair_count": len(pairs),
            "timestamp": _t216.time(),
        }

    # --- Phase 217: per-pair gap trend ---

    def get_per_pair_gap_trend(
        self,
        pair_key: str,
        session_type: str | None = None,
        n_runs: int = 5,
    ) -> dict:
        """Compute velocity (distance delta per day) for a specific pair over the last N analysis runs.

        Returns dict with keys (Phase 217):
          pair_key / session_type / distances / analysis_dates / velocity_per_day /
          trend / n_runs / timestamp
        """
        import time as _t217
        n_runs = max(2, min(20, int(n_runs)))
        with self._conn() as conn:
            if session_type:
                rows = conn.execute(
                    "SELECT distance, analysis_date, above_1_0, created_at "
                    "FROM per_pair_gap_log "
                    "WHERE pair_key=? AND session_type=? "
                    "ORDER BY created_at DESC LIMIT ?",
                    (pair_key, session_type, n_runs),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT distance, analysis_date, above_1_0, created_at "
                    "FROM per_pair_gap_log "
                    "WHERE pair_key=? "
                    "ORDER BY created_at DESC LIMIT ?",
                    (pair_key, n_runs),
                ).fetchall()

        if not rows:
            return {
                "pair_key":         pair_key,
                "session_type":     session_type,
                "distances":        [],
                "analysis_dates":   [],
                "velocity_per_day": None,
                "trend":            "UNKNOWN",
                "n_runs":           0,
                "timestamp":        _t217.time(),
            }

        distances   = [float(r["distance"])      for r in rows]
        dates       = [r["analysis_date"]         for r in rows]
        created_ats = [float(r["created_at"])     for r in rows]

        # Velocity = (latest - oldest) / elapsed_days  (positive = improving = farther apart)
        if len(distances) >= 2:
            dt_days = (created_ats[0] - created_ats[-1]) / 86400.0
            if dt_days > 0:
                vel = (distances[0] - distances[-1]) / dt_days
            else:
                vel = 0.0
            if vel > 0.01:
                trend = "IMPROVING"
            elif vel < -0.01:
                trend = "WORSENING"
            else:
                trend = "STABLE"
        else:
            vel = None
            trend = "UNKNOWN"

        return {
            "pair_key":         pair_key,
            "session_type":     session_type,
            "distances":        distances,
            "analysis_dates":   dates,
            "velocity_per_day": vel,
            "trend":            trend,
            "n_runs":           len(distances),
            "timestamp":        _t217.time(),
        }

    def get_separation_defensibility_status(
        self, session_type: str | None = None
    ) -> "dict | None":
        """Return the latest defensibility report, optionally filtered by session_type (Phase 150)."""
        import json as _json150
        with self._conn() as con:
            if session_type:
                row = con.execute(
                    "SELECT * FROM separation_defensibility_log "
                    "WHERE session_type=? ORDER BY id DESC LIMIT 1",
                    (session_type,),
                ).fetchone()
            else:
                row = con.execute(
                    "SELECT * FROM separation_defensibility_log ORDER BY id DESC LIMIT 1"
                ).fetchone()
        if row is None:
            return None
        d = dict(row)
        try:
            d["n_per_player"] = _json150.loads(d.pop("n_per_player_json", "{}"))
        except Exception:
            d["n_per_player"] = {}
        return d

    def get_enrollment_capture_guidance(
        self, min_n: int = 10
    ) -> dict:
        """Return per-player capture guidance for each structured probe type (Phase 151 P1).

        For each probe type in STRUCTURED_PROBE_TYPES, reads the latest defensibility
        log entry and computes how many more sessions each player needs to reach min_n.

        Returns a guidance dict with:
          - min_n_per_player: the target
          - probe_types: list of structured probe types
          - guidance: per-probe-type breakdown with n_per_player, gap, all_players_ready
          - sessions_needed_total: total capture sessions across all probes/players
          - overall_ready: True when all probe types have all players >= min_n AND ratio >= min_separation_ratio
        """
        import json as _j151
        guidance = {}
        sessions_needed_total = 0
        overall_ready = True
        # Phase 166: configurable gate — retrieve from store attribute if set, else default 0.70
        _min_sep = float(getattr(self, "_min_separation_ratio", 0.70))

        for probe in sorted(self.STRUCTURED_PROBE_TYPES):
            row = self.get_separation_defensibility_status(session_type=probe)
            if row is None:
                guidance[probe] = {
                    "found":             False,
                    "current_ratio":     0.0,
                    "n_per_player":      {},
                    "gap":               {},
                    "all_players_ready": False,
                }
                overall_ready = False
                continue

            n_per_player = row.get("n_per_player", {})
            gap = {
                player: max(0, min_n - count)
                for player, count in n_per_player.items()
            }
            all_players_ready = all(count >= min_n for count in n_per_player.values()) \
                and bool(n_per_player)
            probe_ratio_ok = float(row.get("ratio", 0.0)) >= _min_sep
            probe_entry_ready = all_players_ready and probe_ratio_ok

            sessions_needed_total += sum(gap.values())
            if not probe_entry_ready:
                overall_ready = False

            guidance[probe] = {
                "found":             True,
                "current_ratio":     float(row.get("ratio", 0.0)),
                "n_per_player":      n_per_player,
                "gap":               gap,
                "all_players_ready": probe_entry_ready,
            }

        return {
            "min_n_per_player":       min_n,
            "min_separation_ratio":   _min_sep,
            "probe_types":            sorted(self.STRUCTURED_PROBE_TYPES),
            "guidance":               guidance,
            "sessions_needed_total":  sessions_needed_total,
            "overall_ready":          overall_ready,
        }

    # Phase 152 — Centroid Velocity Log
    # -------------------------------------------------------------------------

    _PLATEAU_THRESHOLD_PER_DAY = 0.001  # ratio units/day below which = stagnant

    def insert_centroid_velocity_log(
        self,
        probe_type: str,
        velocity: float,
        ratio_prev: float,
        ratio_curr: float,
        dt_seconds: float,
        n_snapshots_used: int,
        stagnant: bool,
    ) -> int:
        """Insert a centroid velocity record (Phase 152)."""
        with self._conn() as con:
            cur = con.execute(
                "INSERT INTO centroid_velocity_log "
                "(probe_type, velocity, ratio_prev, ratio_curr, dt_seconds, "
                " n_snapshots_used, stagnant, created_at)"
                " VALUES (?,?,?,?,?,?,?,?)",
                (probe_type, float(velocity), float(ratio_prev), float(ratio_curr),
                 float(dt_seconds), int(n_snapshots_used),
                 1 if stagnant else 0, time.time()),
            )
        return cur.lastrowid  # type: ignore[return-value]

    def get_centroid_velocity_status(
        self, probe_type: str = "touchpad_corners"
    ) -> "dict | None":
        """Return the latest centroid velocity record for a probe type (Phase 152)."""
        with self._conn() as con:
            row = con.execute(
                "SELECT * FROM centroid_velocity_log WHERE probe_type=? ORDER BY id DESC LIMIT 1",
                (probe_type,),
            ).fetchone()
        return dict(row) if row else None

    def compute_centroid_velocity(
        self, probe_type: str = "touchpad_corners"
    ) -> dict:
        """Compute centroid velocity from last 2 defensibility snapshots (Phase 152).

        velocity = |ratio_curr - ratio_prev| / dt_seconds (ratio units per second).
        stagnant = True when velocity_per_day < _PLATEAU_THRESHOLD_PER_DAY (0.001/day).
        Returns velocity dict; never raises.
        """
        with self._conn() as con:
            rows = con.execute(
                "SELECT ratio, created_at FROM separation_defensibility_log "
                "WHERE session_type=? ORDER BY id DESC LIMIT 2",
                (probe_type,),
            ).fetchall()
        if len(rows) < 2:
            return {
                "velocity": 0.0, "ratio_prev": 0.0, "ratio_curr": 0.0,
                "dt_seconds": 0.0, "n_snapshots_used": len(rows), "stagnant": True,
            }
        ratio_curr = float(rows[0]["ratio"])
        ratio_prev = float(rows[1]["ratio"])
        dt = max(1.0, float(rows[0]["created_at"]) - float(rows[1]["created_at"]))
        velocity = abs(ratio_curr - ratio_prev) / dt
        stagnant = (velocity * 86400) < self._PLATEAU_THRESHOLD_PER_DAY
        return {
            "velocity": velocity,
            "ratio_prev": ratio_prev,
            "ratio_curr": ratio_curr,
            "dt_seconds": dt,
            "n_snapshots_used": 2,
            "stagnant": stagnant,
        }

    # Phase 153 — Separation Ratio Registry Log
    # -------------------------------------------------------------------------

    def insert_separation_ratio_registry_log(
        self,
        commit_hash: str,
        ratio_millis: int,
        n_sessions: int,
        n_players: int,
        on_chain_tx: "str | None" = None,
        committed: bool = False,
        n_consented: int = 0,
    ) -> int:
        """Insert a separation ratio registry commitment record (Phase 153).
        Phase 163: n_consented binds active consent count into hash preimage (WIF-022).
        """
        with self._conn() as con:
            cur = con.execute(
                "INSERT OR IGNORE INTO separation_ratio_registry_log "
                "(commit_hash, ratio_millis, n_sessions, n_players, "
                " on_chain_tx, committed, n_consented, created_at)"
                " VALUES (?,?,?,?,?,?,?,?)",
                (commit_hash, int(ratio_millis), int(n_sessions), int(n_players),
                 on_chain_tx, 1 if committed else 0, int(n_consented), time.time()),
            )
        return cur.lastrowid  # type: ignore[return-value]

    def get_separation_ratio_registry_status(self) -> "dict | None":
        """Return the latest separation ratio registry entry (Phase 153/163)."""
        with self._conn() as con:
            row = con.execute(
                "SELECT * FROM separation_ratio_registry_log ORDER BY id DESC LIMIT 1"
            ).fetchone()
        return dict(row) if row else None

    def update_separation_ratio_registry_committed(
        self, commit_hash: str, on_chain_tx: str
    ) -> None:
        """Mark a separation ratio registry entry as committed on-chain (Phase 163)."""
        with self._conn() as con:
            con.execute(
                "UPDATE separation_ratio_registry_log"
                " SET committed=1, on_chain_tx=? WHERE commit_hash=?",
                (on_chain_tx, commit_hash),
            )

    def compute_separation_ratio_commit_hash(
        self,
        ratio: float,
        n_sessions: int,
        players_sorted: str,
        ts_ns: int,
    ) -> "tuple[str, int]":
        """Compute (commit_hash, n_consented) for Phase 163 WIF-022.

        Hash formula: SHA-256('{ratio:.6f}:{n_sessions}:{n_consented}:{players_sorted}:{ts_ns}')
        Reads n_consented atomically from consent_corpus_coverage at call time.
        Returns (commit_hash_hex, n_consented).
        """
        import hashlib as _hl163
        cov = self.get_consent_corpus_coverage()
        n_consented = cov["active_consent_count"]
        preimage = (
            f"{ratio:.6f}:{n_sessions}:{n_consented}:{players_sorted}:{ts_ns}"
        ).encode()
        commit_hash = _hl163.sha256(preimage).hexdigest()
        return commit_hash, n_consented

    # Phase 154 — Capture Stagnation Log
    # -------------------------------------------------------------------------

    def insert_capture_stagnation_log(
        self,
        probe_type: str,
        sessions_in_window: int,
        window_days: float,
        sessions_per_day: float,
        stagnant: bool,
        stagnation_threshold: float = 0.5,
        notes: "str | None" = None,
    ) -> int:
        """Insert a capture stagnation check result (Phase 154)."""
        with self._conn() as con:
            cur = con.execute(
                "INSERT INTO capture_stagnation_log "
                "(probe_type, sessions_in_window, window_days, sessions_per_day, "
                " stagnant, stagnation_threshold, notes, created_at)"
                " VALUES (?,?,?,?,?,?,?,?)",
                (probe_type, int(sessions_in_window), float(window_days),
                 float(sessions_per_day), 1 if stagnant else 0,
                 float(stagnation_threshold), notes, time.time()),
            )
        return cur.lastrowid  # type: ignore[return-value]

    def get_capture_stagnation_status(
        self, probe_type: str = "touchpad_corners"
    ) -> "dict | None":
        """Return the latest capture stagnation check for a probe type (Phase 154)."""
        with self._conn() as con:
            row = con.execute(
                "SELECT * FROM capture_stagnation_log WHERE probe_type=? ORDER BY id DESC LIMIT 1",
                (probe_type,),
            ).fetchone()
        return dict(row) if row else None

    def compute_capture_stagnation(
        self, probe_type: str = "touchpad_corners",
        window_days: float = 7.0, threshold: float = 0.5
    ) -> dict:
        """Compute capture stagnation for a probe type over window_days (Phase 154).

        Counts separation_defensibility_log entries in the last window_days.
        stagnant=True when sessions_per_day < threshold (default 0.5/day = 1 every 2 days).
        """
        cutoff = time.time() - window_days * 86400
        with self._conn() as con:
            count_row = con.execute(
                "SELECT COUNT(*) AS cnt FROM separation_defensibility_log "
                "WHERE session_type=? AND created_at >= ?",
                (probe_type, cutoff),
            ).fetchone()
        count = int(count_row["cnt"]) if count_row else 0
        spd = count / window_days if window_days > 0 else 0.0
        return {
            "probe_type": probe_type,
            "sessions_in_window": count,
            "window_days": window_days,
            "sessions_per_day": spd,
            "stagnant": spd < threshold,
            "stagnation_threshold": threshold,
        }

    # --- Phase 218: CaptureVelocityOracle ---

    def get_capture_velocity_oracle_status(
        self,
        probe_type: str = "touchpad_corners",
        window_days: float = 7.0,
        stagnation_threshold: float = 0.5,
    ) -> dict:
        """Synthesize capture stagnation + centroid velocity into a unified oracle (Phase 218).

        Returns dict with keys:
          probe_type / sessions_per_day / sessions_stagnant / ratio_velocity /
          velocity_stagnant / overall_capture_healthy / recommended_action / timestamp
        """
        import time as _t218
        # --- capture stagnation (Phase 154) ---
        stag_row = self.get_capture_stagnation_status(probe_type)
        if stag_row:
            spd = float(stag_row.get("sessions_per_day", 0.0))
            sessions_stagnant = bool(stag_row.get("stagnant", True))
        else:
            # compute live if no log entry
            live = self.compute_capture_stagnation(
                probe_type=probe_type,
                window_days=window_days,
                threshold=stagnation_threshold,
            )
            spd = float(live["sessions_per_day"])
            sessions_stagnant = bool(live["stagnant"])

        # --- centroid velocity (Phase 152) ---
        vel_row = self.get_centroid_velocity_status(probe_type)
        if vel_row:
            ratio_vel = float(vel_row.get("velocity", 0.0))
            velocity_stagnant = bool(vel_row.get("stagnant", True))
        else:
            ratio_vel = 0.0
            velocity_stagnant = True

        overall_healthy = not sessions_stagnant and not velocity_stagnant

        # --- recommended action ---
        if overall_healthy:
            action = "CONTINUE_CURRENT_PROTOCOL"
        elif sessions_stagnant and velocity_stagnant:
            action = "URGENT_CAPTURE_SESSIONS_AND_REANALYZE"
        elif sessions_stagnant:
            action = "CAPTURE_MORE_SESSIONS"
        else:
            action = "RERUN_SEPARATION_ANALYSIS"

        return {
            "probe_type":            probe_type,
            "sessions_per_day":      spd,
            "sessions_stagnant":     sessions_stagnant,
            "ratio_velocity":        ratio_vel,
            "velocity_stagnant":     velocity_stagnant,
            "overall_capture_healthy": overall_healthy,
            "recommended_action":    action,
            "timestamp":             _t218.time(),
        }

    # --- Phase 219: TournamentBlockerSummary ---

    def get_tournament_blocker_summary(self) -> dict:
        """Aggregate all active TGE blockers across preflight, per-pair gaps, and capture velocity (Phase 219).

        Returns dict with keys:
          total_blockers / blockers / overall_blocked /
          preflight_pass / capture_healthy / all_pairs_above_1 / timestamp
        """
        import time as _t219
        blockers = []

        # --- Tournament preflight P0 failures ---
        try:
            preflight_rows = self.get_tournament_preflight_status(limit=1)
            if preflight_rows:
                pf = preflight_rows[0]
                preflight_pass = bool(pf.get("overall_pass", False))
                if not pf.get("separation_ok", True):
                    blockers.append({
                        "source": "tournament_preflight",
                        "key":    "separation_ok",
                        "detail": "Separation ratio below threshold (ratio < min_separation_ratio)",
                        "severity": "P0",
                    })
                if not pf.get("l4_ok", True):
                    blockers.append({
                        "source": "tournament_preflight",
                        "key":    "l4_ok",
                        "detail": "L4 threshold staleness or calibration gap",
                        "severity": "P0",
                    })
                if not pf.get("all_pairs_p0_ok", True):
                    blockers.append({
                        "source": "tournament_preflight",
                        "key":    "all_pairs_p0_ok",
                        "detail": "Not all per-pair Mahalanobis distances above 1.0",
                        "severity": "P0",
                    })
                if not pf.get("biometric_ttl_ok", True):
                    blockers.append({
                        "source": "tournament_preflight",
                        "key":    "biometric_ttl_ok",
                        "detail": "Biometric credential TTL expired or no renewal chain",
                        "severity": "P0",
                    })
            else:
                preflight_pass = False
                blockers.append({
                    "source": "tournament_preflight",
                    "key":    "no_preflight_run",
                    "detail": "Tournament preflight has never been executed",
                    "severity": "P0",
                })
        except Exception:
            preflight_pass = False

        # --- Per-pair gap blockers ---
        try:
            gap_status = self.get_per_pair_gap_status()
            all_pairs_above_1 = bool(gap_status.get("all_pairs_above_1", False))
            if not all_pairs_above_1:
                for bp in gap_status.get("pairs", []):
                    if not bp.get("above_1_0", True):
                        blockers.append({
                            "source":  "per_pair_gap",
                            "key":     bp.get("pair_key", "UNKNOWN"),
                            "detail":  f"Distance={bp.get('distance', 0.0):.4f} < 1.0 (tournament gate requires all pairs ≥ 1.0)",
                            "severity": "P0",
                        })
        except Exception:
            all_pairs_above_1 = False

        # --- Capture velocity oracle ---
        try:
            cvo = self.get_capture_velocity_oracle_status()
            capture_healthy = bool(cvo.get("overall_capture_healthy", False))
            if not capture_healthy:
                blockers.append({
                    "source":  "capture_velocity",
                    "key":     "overall_capture_healthy",
                    "detail":  f"Recommended: {cvo.get('recommended_action', 'UNKNOWN')}; "
                               f"sessions/day={cvo.get('sessions_per_day', 0.0):.2f}",
                    "severity": "P1",
                })
        except Exception:
            capture_healthy = False

        return {
            "total_blockers":   len(blockers),
            "blockers":         blockers,
            "overall_blocked":  len(blockers) > 0,
            "preflight_pass":   preflight_pass,
            "capture_healthy":  capture_healthy,
            "all_pairs_above_1": all_pairs_above_1,
            "timestamp":        _t219.time(),
        }

    # --- Phase 220: PerPairGapProjection ---

    def get_per_pair_gap_projection(
        self,
        session_type: str | None = None,
        n_runs: int = 5,
    ) -> dict:
        """Project how many days until each blocker pair reaches distance=1.0 (Phase 220).

        Uses get_per_pair_gap_trend() to compute velocity for each known pair,
        then estimates days_to_1_0 = (1.0 - current_distance) / velocity_per_day.
        Returns None for WORSENING/STABLE pairs (infeasible without hardware change).

        Returns dict with keys:
          projections / any_feasible / max_days_to_1_0 / projected_tge_date /
          session_type / timestamp
        """
        import time as _t220
        import datetime as _dt220

        # Get current gap status; deduplicate by pair_key keeping most recent entry
        gap_status = self.get_per_pair_gap_status(session_type=session_type)
        _all_pairs = gap_status.get("pairs", [])
        # get_per_pair_gap_status may return multiple entries per pair_key when
        # filtered by session_type; keep only the first (most recent, sorted DESC).
        _seen: set = set()
        pairs = []
        for _p in _all_pairs:
            _pk = _p.get("pair_key", "")
            if _pk not in _seen:
                _seen.add(_pk)
                pairs.append(_p)

        projections = []
        max_days: float | None = None

        for p in pairs:
            pk = p.get("pair_key", "")
            current_dist = float(p.get("distance", 0.0))
            above = bool(p.get("above_1_0", False))

            if above:
                # Already resolved
                projections.append({
                    "pair_key":              pk,
                    "current_distance":      current_dist,
                    "velocity_per_day":      None,
                    "estimated_days_to_1_0": 0,
                    "projected_date":        _dt220.date.today().isoformat(),
                    "projection_feasible":   True,
                    "status":                "RESOLVED",
                })
                continue

            # Get trend velocity
            trend = self.get_per_pair_gap_trend(
                pair_key=pk,
                session_type=session_type,
                n_runs=n_runs,
            )
            vel = trend.get("velocity_per_day")

            if vel is not None and vel > 0.001:
                # IMPROVING — project forward
                days_needed = (1.0 - current_dist) / vel
                proj_date = (_dt220.date.today() +
                             _dt220.timedelta(days=days_needed)).isoformat()
                feasible = True
                if max_days is None or days_needed > max_days:
                    max_days = days_needed
            else:
                days_needed = None
                proj_date = None
                feasible = False

            projections.append({
                "pair_key":              pk,
                "current_distance":      current_dist,
                "velocity_per_day":      vel,
                "estimated_days_to_1_0": days_needed,
                "projected_date":        proj_date,
                "projection_feasible":   feasible,
                "status":                trend.get("trend", "UNKNOWN"),
            })

        # projected TGE date = today + max_days across all blocker pairs
        if max_days is not None:
            tge_date = (_dt220.date.today() +
                        _dt220.timedelta(days=max_days)).isoformat()
        else:
            tge_date = None

        any_feasible = any(p.get("projection_feasible") for p in projections
                          if p.get("status") != "RESOLVED")

        return {
            "projections":       projections,
            "any_feasible":      any_feasible,
            "max_days_to_1_0":   max_days,
            "projected_tge_date": tge_date,
            "session_type":      session_type,
            "timestamp":         _t220.time(),
        }

    # --- Phase 221: ProtocolCoherence (PoPC) ---

    def insert_protocol_coherence_log(
        self,
        merkle_root: str,
        agent_count: int,
        anchor_hash: str = "",
        on_chain_confirmed: bool = False,
        allowlist_hash: str = "",
        governance_provenance_hash: str = "",
    ) -> int:
        """Insert a PoPC Merkle root anchor record (Phase 221/224/227).

        Args:
            merkle_root:               Hex string of the Merkle root (64 chars).
            agent_count:               Number of agents included in the Merkle tree.
            anchor_hash:               On-chain tx hash if anchored; empty if local only.
            on_chain_confirmed:        True when the tx was confirmed on IoTeX testnet.
            allowlist_hash:            SHA-256 of INVARIANTS_ALLOWLIST.json at anchor time (Phase 224).
            governance_provenance_hash: Latest governance provenance hash anchored on-chain (Phase 227).

        Returns:
            Row id of the inserted record.
        """
        now = time.time()
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO protocol_coherence_log "
                "(merkle_root, agent_count, anchor_hash, on_chain_confirmed, created_at, "
                "allowlist_hash, governance_provenance_hash) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    str(merkle_root),
                    int(agent_count),
                    str(anchor_hash),
                    1 if on_chain_confirmed else 0,
                    now,
                    str(allowlist_hash),
                    str(governance_provenance_hash),
                ),
            )
            return cur.lastrowid or 0

    def get_protocol_coherence_status(self) -> dict:
        """Return the most recent PoPC anchor status (Phase 221/227).

        Returns dict with keys:
            total_anchors / latest_merkle_root / agent_count /
            on_chain_confirmed / last_anchor_ts / governance_provenance_hash / timestamp
        """
        import time as _t221
        with self._conn() as conn:
            total = (conn.execute(
                "SELECT COUNT(*) FROM protocol_coherence_log"
            ).fetchone() or (0,))[0]
            row = conn.execute(
                "SELECT merkle_root, agent_count, on_chain_confirmed, created_at, "
                "COALESCE(governance_provenance_hash, '') "
                "FROM protocol_coherence_log ORDER BY created_at DESC LIMIT 1"
            ).fetchone()
        if row:
            return {
                "total_anchors":              int(total),
                "latest_merkle_root":         str(row[0]),
                "agent_count":                int(row[1]),
                "on_chain_confirmed":         bool(row[2]),
                "last_anchor_ts":             float(row[3]),
                "governance_provenance_hash": str(row[4]),
                "timestamp":                  _t221.time(),
            }
        return {
            "total_anchors":              0,
            "latest_merkle_root":         None,
            "agent_count":                0,
            "on_chain_confirmed":         False,
            "last_anchor_ts":             None,
            "governance_provenance_hash": "",
            "timestamp":                  _t221.time(),
        }

    def get_protocol_coherence_history(self, limit: int = 10) -> list:
        """Return the most recent PoPC anchor records (Phase 221).

        Returns list of dicts with keys:
            id / merkle_root / agent_count / on_chain_confirmed / created_at
        """
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT id, merkle_root, agent_count, on_chain_confirmed, created_at "
                "FROM protocol_coherence_log ORDER BY created_at DESC LIMIT ?",
                (int(limit),),
            ).fetchall()
        return [
            {
                "id":                int(r[0]),
                "merkle_root":       str(r[1]),
                "agent_count":       int(r[2]),
                "on_chain_confirmed": bool(r[3]),
                "created_at":        float(r[4]),
            }
            for r in rows
        ]

    # --- Phase 222: BiometricBoundGovernance (BBG) ---

    def insert_bbg_proposal_log(
        self,
        proposal_hash: str,
        proposer_address: str = "",
        vhp_token_id: int = 0,
        vhp_expires_at: float = 0.0,
        on_chain_confirmed: bool = False,
        tx_hash: str = "",
    ) -> int:
        """Insert a BBG governance proposal record (Phase 222).

        Returns:
            Row id of the inserted record.
        """
        now = time.time()
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO bbg_proposal_log "
                "(proposal_hash, proposer_address, vhp_token_id, vhp_expires_at, "
                "on_chain_confirmed, tx_hash, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    str(proposal_hash),
                    str(proposer_address),
                    int(vhp_token_id),
                    float(vhp_expires_at),
                    1 if on_chain_confirmed else 0,
                    str(tx_hash),
                    now,
                ),
            )
            return cur.lastrowid or 0

    def get_bbg_status(self) -> dict:
        """Return the BBG proposal status (Phase 222).

        Returns dict with keys:
            total_proposals / latest_proposal_hash / latest_proposer /
            on_chain_confirmed / last_proposal_ts / timestamp
        """
        import time as _t222
        with self._conn() as conn:
            total = (conn.execute(
                "SELECT COUNT(*) FROM bbg_proposal_log"
            ).fetchone() or (0,))[0]
            row = conn.execute(
                "SELECT proposal_hash, proposer_address, on_chain_confirmed, created_at "
                "FROM bbg_proposal_log ORDER BY created_at DESC LIMIT 1"
            ).fetchone()
        if row:
            return {
                "total_proposals":     int(total),
                "latest_proposal_hash": str(row[0]),
                "latest_proposer":     str(row[1]),
                "on_chain_confirmed":  bool(row[2]),
                "last_proposal_ts":    float(row[3]),
                "timestamp":           _t222.time(),
            }
        return {
            "total_proposals":     0,
            "latest_proposal_hash": None,
            "latest_proposer":     None,
            "on_chain_confirmed":  False,
            "last_proposal_ts":    None,
            "timestamp":           _t222.time(),
        }

    def get_bbg_proposal_history(self, limit: int = 10) -> list:
        """Return the most recent BBG proposal records (Phase 222).

        Returns list of dicts with keys:
            id / proposal_hash / proposer_address / vhp_token_id /
            on_chain_confirmed / created_at
        """
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT id, proposal_hash, proposer_address, vhp_token_id, "
                "on_chain_confirmed, created_at "
                "FROM bbg_proposal_log ORDER BY created_at DESC LIMIT ?",
                (int(limit),),
            ).fetchall()
        return [
            {
                "id":               int(r[0]),
                "proposal_hash":    str(r[1]),
                "proposer_address": str(r[2]),
                "vhp_token_id":     int(r[3]),
                "on_chain_confirmed": bool(r[4]),
                "created_at":       float(r[5]),
            }
            for r in rows
        ]

    # --- Phase 223: PV-CI Invariant Gate ---

    def insert_invariant_gate_log(
        self,
        gate_pass: bool,
        total_checked: int,
        failures_json: str = "[]",
        run_source: str = "manual",
        previous_allowlist_hash: str = "",
        new_allowlist_hash: str = "",
        reason_category: str = "",
        reason_text: str = "",
        vhp_token_id: str = "",
    ) -> int:
        """Record a PV-CI invariant gate run result (Phase 223/224/228).

        Args:
            gate_pass:               True if all invariants passed.
            total_checked:           Number of invariants evaluated.
            failures_json:           JSON-encoded list of failure description strings.
            run_source:              'manual', 'ci', 'api', or 'governance:<cat>:<text>'.
            previous_allowlist_hash: SHA-256 of allowlist before --generate (Phase 224).
            new_allowlist_hash:      SHA-256 of allowlist after --generate (Phase 224).
            reason_category:         Governance category (refactor/bugfix/...) (Phase 224).
            reason_text:             Human-readable governance rationale (Phase 224).
            vhp_token_id:            VHP token ID supplied for invariant_change events (Phase 228).
        Returns:
            row id of the inserted record.
        """
        import time as _t223
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO invariant_gate_log "
                "(gate_pass, total_checked, failures_json, run_source, created_at, "
                "previous_allowlist_hash, new_allowlist_hash, reason_category, reason_text, "
                "vhp_token_id) "
                "VALUES (?,?,?,?,?,?,?,?,?,?)",
                (
                    int(bool(gate_pass)),
                    int(total_checked),
                    failures_json,
                    run_source,
                    _t223.time(),
                    str(previous_allowlist_hash),
                    str(new_allowlist_hash),
                    str(reason_category),
                    str(reason_text),
                    str(vhp_token_id),
                ),
            )
            return int(cur.lastrowid)

    # --- Phase 224: Allowlist Governance ---

    def insert_allowlist_change_log(
        self,
        previous_hash: str,
        new_hash: str,
        merkle_root_at_change: str = "",
        reason_from_gate_log: "str | None" = None,
    ) -> int:
        """Record a detected allowlist hash change (Phase 224).

        Called by ProtocolCoherenceAgent when allowlist_hash changes between anchor cycles.
        reason_from_gate_log is fetched from the most recent invariant_gate_log entry
        within 60 seconds; NULL if no matching governance event was found (suspicious).

        Returns:
            Row id of the inserted record.
        """
        import time as _t224
        detected_at = str(_t224.time())
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO allowlist_change_log "
                "(previous_hash, new_hash, merkle_root_at_change, detected_at, reason_from_gate_log) "
                "VALUES (?, ?, ?, ?, ?)",
                (
                    str(previous_hash),
                    str(new_hash),
                    str(merkle_root_at_change),
                    detected_at,
                    reason_from_gate_log,
                ),
            )
            return cur.lastrowid or 0

    def get_allowlist_change_status(self) -> dict:
        """Return allowlist change log summary (Phase 224).

        Returns dict with keys:
            total_changes / suspicious_count / latest_previous_hash /
            latest_new_hash / latest_detected_at / timestamp
        """
        import time as _t224
        with self._conn() as conn:
            total = (conn.execute(
                "SELECT COUNT(*) FROM allowlist_change_log"
            ).fetchone() or (0,))[0]
            suspicious = (conn.execute(
                "SELECT COUNT(*) FROM allowlist_change_log WHERE reason_from_gate_log IS NULL"
            ).fetchone() or (0,))[0]
            row = conn.execute(
                "SELECT previous_hash, new_hash, detected_at, reason_from_gate_log "
                "FROM allowlist_change_log ORDER BY id DESC LIMIT 1"
            ).fetchone()
        if row:
            return {
                "total_changes":       int(total),
                "suspicious_count":    int(suspicious),
                "latest_previous_hash": str(row[0]),
                "latest_new_hash":     str(row[1]),
                "latest_detected_at":  str(row[2]),
                "timestamp":           _t224.time(),
            }
        return {
            "total_changes":       0,
            "suspicious_count":    0,
            "latest_previous_hash": None,
            "latest_new_hash":     None,
            "latest_detected_at":  None,
            "timestamp":           _t224.time(),
        }

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

    def insert_governance_provenance(
        self,
        governance_provenance_hash: str,
        previous_provenance_hash: str,
        new_allowlist_hash: str,
        reason_category: str,
        reason_text: str,
    ) -> int:
        """Record a provenance chain entry for an allowlist governance event (Phase 225).

        The governance_provenance_hash is SHA-256(prev_prov || new_hash || category || text || ts_ns_8b),
        forming a tamper-evident hash-linked audit trail.

        Returns:
            Row id of the inserted record.
        """
        import time as _t225
        ts = _t225.time()
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO governance_provenance_chain "
                "(governance_provenance_hash, previous_provenance_hash, new_allowlist_hash, "
                "reason_category, reason_text, created_at) VALUES (?,?,?,?,?,?)",
                (governance_provenance_hash, previous_provenance_hash, new_allowlist_hash,
                 reason_category, reason_text, ts),
            )
            row_id = int(cur.lastrowid or 0)
            # Also stamp the most recent invariant_gate_log row with the hash
            conn.execute(
                "UPDATE invariant_gate_log SET governance_provenance_hash = ? "
                "WHERE id = (SELECT MAX(id) FROM invariant_gate_log)",
                (governance_provenance_hash,),
            )
        return row_id

    def get_governance_provenance_history(self, limit: int = 20) -> list:
        """Return the most recent governance provenance chain entries (Phase 225).

        Returns list of dicts ordered newest-first with keys:
            id / governance_provenance_hash / previous_provenance_hash / new_allowlist_hash /
            reason_category / reason_text / created_at
        """
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT id, governance_provenance_hash, previous_provenance_hash, "
                "new_allowlist_hash, reason_category, reason_text, created_at "
                "FROM governance_provenance_chain ORDER BY id DESC LIMIT ?",
                (max(1, int(limit)),),
            ).fetchall()
        return [
            {
                "id":                         int(r["id"]),
                "governance_provenance_hash":  str(r["governance_provenance_hash"]),
                "previous_provenance_hash":    str(r["previous_provenance_hash"]),
                "new_allowlist_hash":          str(r["new_allowlist_hash"]),
                "reason_category":             str(r["reason_category"]),
                "reason_text":                 str(r["reason_text"]),
                "created_at":                  float(r["created_at"]),
            }
            for r in rows
        ]

    def get_latest_governance_provenance_hash(self) -> str:
        """Return the most recent governance_provenance_hash from governance_provenance_chain (Phase 225).

        Returns '0' * 64 (genesis sentinel) when no entries exist.
        """
        with self._conn() as conn:
            row = conn.execute(
                "SELECT governance_provenance_hash FROM governance_provenance_chain "
                "ORDER BY id DESC LIMIT 1"
            ).fetchone()
        return str(row["governance_provenance_hash"]) if row else "0" * 64

    def get_invariant_gate_status(self) -> dict:
        """Return PV-CI invariant gate summary (Phase 223).

        Returns dict with keys:
            pv_ci_enabled / gate_pass / total_checked / failure_count /
            last_failures / last_run_ts / timestamp
        """
        import json as _json223
        import time as _t223

        with self._conn() as conn:
            row = conn.execute(
                "SELECT gate_pass, total_checked, failures_json, created_at "
                "FROM invariant_gate_log ORDER BY created_at DESC LIMIT 1"
            ).fetchone()

        if row:
            failures = _json223.loads(row[1] if False else row["failures_json"])
            return {
                "pv_ci_enabled":  True,
                "gate_pass":      bool(row["gate_pass"]),
                "total_checked":  int(row["total_checked"]),
                "failure_count":  len(failures),
                "last_failures":  failures,
                "last_run_ts":    float(row["created_at"]),
                "timestamp":      _t223.time(),
            }
        return {
            "pv_ci_enabled":  True,
            "gate_pass":      None,
            "total_checked":  0,
            "failure_count":  0,
            "last_failures":  [],
            "last_run_ts":    None,
            "timestamp":      _t223.time(),
        }

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

    def get_controller_hardware_profiles(self, active_only: bool = True) -> list:
        """Return controller hardware profiles (Phase 155)."""
        with self._conn() as con:
            if active_only:
                rows = con.execute(
                    "SELECT * FROM controller_hardware_profiles WHERE active=1 ORDER BY id DESC"
                ).fetchall()
            else:
                rows = con.execute(
                    "SELECT * FROM controller_hardware_profiles ORDER BY id DESC"
                ).fetchall()
        return [dict(r) for r in rows]

    # Phase 156 — Enrollment Guidance Log
    # -------------------------------------------------------------------------

    def insert_enrollment_guidance_log(
        self,
        sessions_needed_total: int,
        overall_ready: bool,
        recommended_action: str,
        urgency_level: str = "low",
        stagnant_probes: "list | None" = None,
        estimated_days: float = -1.0,
        activation_chain_event: "str | None" = None,
        cov_regime_status: str = "unknown",
    ) -> int:
        """Insert an autonomous enrollment guidance report (Phase 156/157)."""
        import json as _j156
        with self._conn() as con:
            cur = con.execute(
                "INSERT INTO enrollment_guidance_log "
                "(sessions_needed_total, overall_ready, recommended_action, "
                " urgency_level, stagnant_probes, estimated_days, "
                " activation_chain_event, cov_regime_status, created_at)"
                " VALUES (?,?,?,?,?,?,?,?,?)",
                (
                    int(sessions_needed_total),
                    1 if overall_ready else 0,
                    recommended_action,
                    urgency_level,
                    _j156.dumps(stagnant_probes or []),
                    float(estimated_days),
                    activation_chain_event,
                    cov_regime_status,
                    time.time(),
                ),
            )
        return cur.lastrowid  # type: ignore[return-value]

    def get_enrollment_guidance_status(self) -> "dict | None":
        """Return the latest enrollment guidance report (Phase 156/157)."""
        import json as _j156
        with self._conn() as con:
            row = con.execute(
                "SELECT * FROM enrollment_guidance_log ORDER BY id DESC LIMIT 1"
            ).fetchone()
        if row is None:
            return None
        d = dict(row)
        try:
            d["stagnant_probes"] = _j156.loads(d.get("stagnant_probes", "[]"))
        except Exception:
            d["stagnant_probes"] = []
        if "cov_regime_status" not in d:
            d["cov_regime_status"] = "unknown"
        return d

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

    def insert_gsr_hmac_validation(
        self,
        *,
        device_id: str,
        frame_size: int,
        valid: bool,
        rejection_reason: str = "",
        ts_ns: int = 0,
    ) -> int:
        """Log a GSR HMAC frame validation attempt (Phase 158 WIF-014)."""
        with self._conn() as con:
            cur = con.execute(
                "INSERT INTO gsr_hmac_validation_log "
                "(device_id, frame_size, valid, rejection_reason, ts_ns, created_at)"
                " VALUES (?,?,?,?,?,?)",
                (device_id, int(frame_size), int(valid), rejection_reason, int(ts_ns), time.time()),
            )
        return cur.lastrowid  # type: ignore[return-value]

    def get_gsr_hmac_validation_status(self, limit: int = 20) -> dict:
        """Return HMAC validation summary + recent entries (Phase 158)."""
        with self._conn() as con:
            total = con.execute(
                "SELECT COUNT(*) FROM gsr_hmac_validation_log"
            ).fetchone()[0]
            valid_count = con.execute(
                "SELECT COUNT(*) FROM gsr_hmac_validation_log WHERE valid=1"
            ).fetchone()[0]
            rows = con.execute(
                "SELECT * FROM gsr_hmac_validation_log ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return {
            "gsr_hmac_enabled": False,  # populated by operator_api from cfg
            "total_validations": total,
            "valid_count": valid_count,
            "rejected_count": total - valid_count,
            "recent_entries": [dict(r) for r in rows],
        }

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

    def _check_consent_gate(
        self,
        device_id: str,
        operation: str,
        category: str | None = None,
    ) -> None:
        """Raise ValueError + log if device has revoked consent or erasure_requested.

        Callers must check self._consent_ledger_enabled before calling this method.
        Fails open for unknown devices (no record = allowed) to avoid blocking new
        devices before consent is registered via POST /agent/register-consent.

        Phase 237-CONSENT extension: when `category` is provided, the gate checks
        the per-category record (consent_type=category) instead of the default
        biometric_processing record. Backward-compatible: callers omitting
        `category` retain Phase 161 semantics exactly.
        """
        consent_type = category if category else "biometric_processing"
        status = self.get_consent_status(device_id, consent_type)
        if status["erasure_requested"] or status["revoked"]:
            reason = "erasure_requested" if status["erasure_requested"] else "consent_revoked"
            with self._conn() as con:
                con.execute(
                    "INSERT INTO consent_gate_violation_log"
                    " (device_id, operation, blocked_reason, created_at)"
                    " VALUES (?,?,?,?)",
                    (device_id, operation, reason, time.time()),
                )
            raise ValueError(
                f"Consent gate: device {device_id!r} blocked for operation "
                f"{operation!r} (category={consent_type!r}) — reason: {reason} "
                f"(GDPR Art.7/17, Phase 161 BP-002 / Phase 237-CONSENT)."
            )

    # --- Phase 237-CONSENT: per-category consent helpers ---
    #
    # Thin wrappers over the Phase 160 consent_ledger primitives. Each helper
    # accepts a category (string name from consent_categories.CATEGORY_NAMES)
    # and writes/reads `consent_ledger` with `consent_type=category`. The
    # UNIQUE(device_id, consent_type) constraint plus the existing UPSERT in
    # insert_consent_record means re-grant on the same category just updates
    # the existing row.

    def grant_category_consent(
        self,
        device_id: str,
        category: str,
        ttl_s: int = 0,
        consent_hash: str = "",
        ts_ns: int | None = None,
    ) -> int:
        """Grant per-category consent (Phase 237-CONSENT).

        Args:
            device_id:    Device identifier.
            category:     Category name from consent_categories.CATEGORY_NAMES
                          (TOURNAMENT_GATE / ANONYMIZED_RESEARCH / MANUFACTURER_CERT / MARKETPLACE).
            ttl_s:        Consent TTL in seconds. 0 = no expiry. Stored as the
                          consent_ts offset for now (full expiry enforcement at
                          gate-check time is Phase 238 work).
            consent_hash: Optional FROZEN-v1 hex commitment from
                          consent_categories.compute_consent_hash() — 64 hex chars or "".
            ts_ns:        Grant time in ns. Defaults to time.time_ns().

        Returns:
            Row id from the underlying consent_ledger.
        """
        from .consent_categories import NAME_TO_CATEGORY  # validate category name
        if category not in NAME_TO_CATEGORY:
            raise ValueError(
                f"unknown consent category: {category!r}. "
                f"Valid: {sorted(NAME_TO_CATEGORY.keys())}"
            )
        if consent_hash and len(consent_hash) != 64:
            raise ValueError(f"consent_hash must be 64 hex chars or empty, got {len(consent_hash)}")
        # Reuse Phase 160 UPSERT — re-grant updates the existing row.
        # consent_ts persists the grant timestamp; ttl_s is advisory metadata
        # for now (full expiry-at-gate-check is Phase 238 work).
        consent_ts = (ts_ns / 1e9) if ts_ns is not None else None
        return self.insert_consent_record(
            device_id=device_id,
            consent_type=category,
            consent_given=True,
            consent_ts=consent_ts,
        )

    def revoke_category_consent(
        self,
        device_id: str,
        category: str,
        reason: str = "",
    ) -> bool:
        """Revoke per-category consent (Phase 237-CONSENT). Returns True if a row updated.

        Wraps Phase 160 revoke_consent() with category enum validation.
        """
        from .consent_categories import NAME_TO_CATEGORY
        if category not in NAME_TO_CATEGORY:
            raise ValueError(f"unknown consent category: {category!r}")
        return self.revoke_consent(
            device_id=device_id,
            consent_type=category,
            reason=reason,
        )

    def get_category_consent_status(
        self,
        device_id: str,
        category: str | None = None,
    ) -> dict:
        """Return per-category consent state for a device (Phase 237-CONSENT).

        When `category` is provided, returns the single-category status dict
        (same shape as Phase 160 get_consent_status, with `category` key added).

        When `category` is None, returns aggregated status across all four
        categories: {"device_id": ..., "categories": {NAME: status_dict, ...}}.
        Any category with no record reports `granted=False, found=False`
        (fail-closed by absence — operationally safe).
        """
        from .consent_categories import ALL_CATEGORIES, CATEGORY_NAMES, NAME_TO_CATEGORY

        if category is not None:
            if category not in NAME_TO_CATEGORY:
                raise ValueError(f"unknown consent category: {category!r}")
            base = self.get_consent_status(device_id, consent_type=category)
            return {
                **base,
                "category": category,
                "granted": bool(base["consent_given"]) and not base["revoked"]
                                                       and not base["erasure_requested"],
            }

        out: dict[str, dict] = {}
        for cat in ALL_CATEGORIES:
            name = CATEGORY_NAMES[cat]
            base = self.get_consent_status(device_id, consent_type=name)
            out[name] = {
                **base,
                "category": name,
                "granted": bool(base["consent_given"]) and not base["revoked"]
                                                       and not base["erasure_requested"],
            }
        return {
            "device_id":  device_id,
            "categories": out,
        }

    def get_consent_gate_status(self) -> dict:
        """Return consent gate violation summary (Phase 161 BP-002)."""
        with self._conn() as con:
            row = con.execute(
                "SELECT COUNT(*) as total, MAX(created_at) as last_ts,"
                " MAX(device_id) as last_device"
                " FROM consent_gate_violation_log"
            ).fetchone()
        d = dict(row) if row else {}
        return {
            "violations_total":      int(d.get("total") or 0),
            "last_violation_ts":     d.get("last_ts"),
            "last_violation_device": d.get("last_device"),
        }

    def get_active_consent_devices(self) -> list:
        """Return devices with active consent (Phase 162 WIF-021)."""
        with self._conn() as con:
            rows = con.execute(
                "SELECT device_id, consent_type, consent_ts FROM consent_ledger"
                " WHERE consent_given=1 AND erasure_requested=0"
                "   AND (revoked_at IS NULL)"
            ).fetchall()
        return [dict(r) for r in rows]

    def get_consent_corpus_coverage(self) -> dict:
        """Return consent coverage statistics for corpus defensibility (Phase 162 WIF-021)."""
        with self._conn() as con:
            row = con.execute(
                "SELECT"
                "  COUNT(*) as total,"
                "  SUM(CASE WHEN consent_given=1 AND erasure_requested=0"
                "           AND revoked_at IS NULL THEN 1 ELSE 0 END) as active_count,"
                "  SUM(CASE WHEN revoked_at IS NOT NULL THEN 1 ELSE 0 END) as revoked_count,"
                "  SUM(CASE WHEN erasure_requested=1 THEN 1 ELSE 0 END) as erasure_count"
                " FROM consent_ledger"
            ).fetchone()
        d = dict(row) if row else {}
        total   = int(d.get("total",        0) or 0)
        active  = int(d.get("active_count", 0) or 0)
        revoked = int(d.get("revoked_count", 0) or 0)
        erasure = int(d.get("erasure_count", 0) or 0)
        return {
            "total_registered":        total,
            "active_consent_count":    active,
            "revoked_count":           revoked,
            "erasure_requested_count": erasure,
            "consent_corpus_defensible": (revoked == 0 and erasure == 0 and total > 0),
        }

    def insert_consent_snapshot(
        self,
        commit_hash: str,
        n_consented_at_commit: int,
        revoked_count_at_commit: int,
        erasure_count_at_commit: int,
    ) -> None:
        """Record consent coverage snapshot linked to a ratio commit (Phase 164 WIF-023).

        Called immediately after insert_separation_ratio_registry_log so that
        post-commit revocations produce a verifiable delta chain.
        commit_hash links to separation_ratio_registry_log.commit_hash.
        """
        with self._conn() as con:
            con.execute(
                "INSERT INTO consent_snapshot_log"
                " (commit_hash, n_consented_at_commit, revoked_count_at_commit,"
                "  erasure_count_at_commit, snapshot_ts, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                (
                    commit_hash,
                    n_consented_at_commit,
                    revoked_count_at_commit,
                    erasure_count_at_commit,
                    time.time(),
                    time.time(),
                ),
            )

    # ------------------------------------------------------------------
    # Phase 165 — Post-Erasure Separation Ratio Recompute (WIF-024)
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

    def insert_separation_ratio_recovery_log(
        self,
        current_ratio: float,
        trend_velocity: float,
        n_snapshots_used: int,
        recovery_needed: bool,
        recovery_action: str,
        recommendation: str,
    ) -> int:
        """Insert a separation ratio recovery assessment (Phase 173).

        trend_velocity: dRatio/dSession — negative means converging downward.
        recovery_action: one of STABLE | AGE_WEIGHTING | P1_RE_ENROLLMENT | MORE_SESSIONS.
        """
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO separation_ratio_recovery_log "
                "(current_ratio, trend_velocity, n_snapshots_used, recovery_needed, "
                "recovery_action, recommendation, created_at) VALUES (?,?,?,?,?,?,?)",
                (
                    float(current_ratio),
                    float(trend_velocity),
                    int(n_snapshots_used),
                    1 if recovery_needed else 0,
                    str(recovery_action),
                    str(recommendation),
                    time.time(),
                ),
            )
        return cur.lastrowid  # type: ignore[return-value]

    def get_separation_ratio_recovery_status(self, limit: int = 1) -> "list[dict]":
        """Return most recent recovery assessments, newest first (Phase 173)."""
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT id, current_ratio, trend_velocity, n_snapshots_used, "
                "recovery_needed, recovery_action, recommendation, created_at "
                "FROM separation_ratio_recovery_log ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [
            {
                "id":               r[0],
                "current_ratio":    float(r[1]),
                "trend_velocity":   float(r[2]),
                "n_snapshots_used": int(r[3]),
                "recovery_needed":  bool(r[4]),
                "recovery_action":  r[5],
                "recommendation":   r[6],
                "created_at":       r[7],
            }
            for r in rows
        ]

    # --- Phase 175: AgeWeightedRatioPersistenceAgent ---

    def insert_age_weight_analysis_log(
        self,
        probe_type: str,
        raw_ratio: float,
        age_weighted_ratio: float,
        halflife_days: float,
        n_sessions_used: int,
    ) -> int:
        """Insert an age-weighted separation ratio analysis result (Phase 175).

        temporal_drift_index = raw_ratio - age_weighted_ratio.
          positive  → old sessions inflate ratio (P1 non-stationarity)
          negative  → new sessions stronger (player stabilising)
          near-zero → biometrically stationary (ideal)
        drift_direction: P1_NONSTATIONARITY | IMPROVING | STABLE
        """
        tdi = round(float(raw_ratio) - float(age_weighted_ratio), 6)
        if tdi > 0.05:
            direction = "P1_NONSTATIONARITY"
        elif tdi < -0.05:
            direction = "IMPROVING"
        else:
            direction = "STABLE"
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO age_weight_analysis_log "
                "(probe_type, raw_ratio, age_weighted_ratio, temporal_drift_index, "
                "halflife_days, n_sessions_used, drift_direction, created_at) "
                "VALUES (?,?,?,?,?,?,?,?)",
                (
                    str(probe_type),
                    float(raw_ratio),
                    float(age_weighted_ratio),
                    tdi,
                    float(halflife_days),
                    int(n_sessions_used),
                    direction,
                    time.time(),
                ),
            )
        return cur.lastrowid  # type: ignore[return-value]

    def get_age_weight_analysis_status(self, limit: int = 1) -> "list[dict]":
        """Return most recent age-weight analysis results, newest first (Phase 175)."""
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT id, probe_type, raw_ratio, age_weighted_ratio, "
                "temporal_drift_index, halflife_days, n_sessions_used, "
                "drift_direction, created_at "
                "FROM age_weight_analysis_log ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [
            {
                "id":                   r[0],
                "probe_type":           r[1],
                "raw_ratio":            float(r[2]),
                "age_weighted_ratio":   float(r[3]),
                "temporal_drift_index": float(r[4]),
                "halflife_days":        float(r[5]),
                "n_sessions_used":      int(r[6]),
                "drift_direction":      r[7],
                "created_at":           r[8],
            }
            for r in rows
        ]

    # --- Phase 176: PoACChainIntegrityMonitor ---

    def insert_poac_chain_audit_log(
        self,
        device_id: str,
        total_records: int,
        valid_links: int,
        broken_links: int,
    ) -> int:
        """Insert a PoAC chain integrity audit result (Phase 176).

        integrity_score = valid_links / total_links (0.0 when total=0 → score=1.0 vacuous).
        audit_passed = True when integrity_score >= 1.0 (no broken links).
        W1 mitigation: only aggregate counts stored — no broken record IDs.
        """
        if total_records > 0:
            integrity_score = round(float(valid_links) / float(total_records), 6)
        else:
            integrity_score = 1.0  # vacuously intact
        audit_passed = 1 if broken_links == 0 else 0
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO poac_chain_audit_log "
                "(device_id, total_records, valid_links, broken_links, "
                "integrity_score, audit_passed, created_at) VALUES (?,?,?,?,?,?,?)",
                (
                    str(device_id),
                    int(total_records),
                    int(valid_links),
                    int(broken_links),
                    integrity_score,
                    audit_passed,
                    time.time(),
                ),
            )
        return cur.lastrowid  # type: ignore[return-value]

    def get_poac_chain_audit_status(
        self, device_id: "str | None" = None, limit: int = 1
    ) -> "list[dict]":
        """Return most recent chain audit results (Phase 176).

        If device_id is provided, filters to that device only.
        Returns newest-first. W1: never exposes broken record IDs.
        """
        with self._conn() as conn:
            if device_id:
                rows = conn.execute(
                    "SELECT id, device_id, total_records, valid_links, broken_links, "
                    "integrity_score, audit_passed, created_at "
                    "FROM poac_chain_audit_log WHERE device_id=? "
                    "ORDER BY id DESC LIMIT ?",
                    (device_id, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT id, device_id, total_records, valid_links, broken_links, "
                    "integrity_score, audit_passed, created_at "
                    "FROM poac_chain_audit_log ORDER BY id DESC LIMIT ?",
                    (limit,),
                ).fetchall()
        return [
            {
                "id":              r[0],
                "device_id":       r[1],
                "total_records":   int(r[2]),
                "valid_links":     int(r[3]),
                "broken_links":    int(r[4]),
                "integrity_score": float(r[5]),
                "audit_passed":    bool(r[6]),
                "created_at":      r[7],
            }
            for r in rows
        ]

    # --- Phase 180: Biometric Renewal Engine (WIF-029 W2 closure) ---

    def insert_biometric_renewal_chain_log(
        self,
        prev_commit_hash: str,
        new_commit_hash: str,
        n_consented: int,
        n_sessions: int,
        ttl_days: float,
        on_chain_tx: "str | None" = None,
        dry_run: bool = True,
        renewal_reason: str = "TTL_EXPIRY",
    ) -> int:
        """Insert a biometric renewal chain record (Phase 180).

        Stores the consent-bound renewal commitment chain entry.
        new_commit_hash = SHA-256(prev_hash + ratio_str + N + N_consented + players + ttl_days + ts_ns).
        Raises sqlite3.IntegrityError on duplicate new_commit_hash (anti-replay).
        """
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO biometric_renewal_chain_log "
                "(prev_commit_hash, new_commit_hash, renewal_reason, "
                "n_consented, n_sessions, ttl_days, on_chain_tx, dry_run, created_at) "
                "VALUES (?,?,?,?,?,?,?,?,?)",
                (
                    str(prev_commit_hash),
                    str(new_commit_hash),
                    str(renewal_reason),
                    int(n_consented),
                    int(n_sessions),
                    float(ttl_days),
                    str(on_chain_tx) if on_chain_tx else None,
                    1 if dry_run else 0,
                    time.time(),
                ),
            )
        return cur.lastrowid  # type: ignore[return-value]

    def get_biometric_renewal_chain_status(self) -> "dict":
        """Return the renewal chain status for GET /agent/renewal-chain-status (Phase 180).

        Returns 7 keys: renewal_enabled/total_renewals/latest_renewal_ts/
        prev_commit_hash/new_commit_hash/ttl_days/timestamp.
        """
        ts_now = time.time()
        with self._conn() as conn:
            total_row = conn.execute(
                "SELECT COUNT(*) FROM biometric_renewal_chain_log"
            ).fetchone()
            total_renewals = int(total_row[0]) if total_row else 0
            latest_row = conn.execute(
                "SELECT prev_commit_hash, new_commit_hash, ttl_days, created_at "
                "FROM biometric_renewal_chain_log ORDER BY id DESC LIMIT 1"
            ).fetchone()
        if latest_row:
            return {
                "renewal_enabled":    False,      # caller overlays from cfg
                "total_renewals":     total_renewals,
                "latest_renewal_ts":  float(latest_row[3]),
                "prev_commit_hash":   str(latest_row[0]),
                "new_commit_hash":    str(latest_row[1]),
                "ttl_days":           float(latest_row[2]),
                "timestamp":          ts_now,
            }
        return {
            "renewal_enabled":    False,
            "total_renewals":     0,
            "latest_renewal_ts":  0.0,
            "prev_commit_hash":   "",
            "new_commit_hash":    "",
            "ttl_days":           90.0,
            "timestamp":          ts_now,
        }

    # --- Phase 179: ZK Ceremony Audit Gate (WIF-030 W1 closure) ---

    def insert_ceremony_audit_entry(
        self,
        ceremony_id: str,
        circuit_name: str,
        participant_address: str,
        contribution_hash: str,
        ts_ns: int = 0,
    ) -> int:
        """Insert a ZK ceremony participant entry (Phase 179).

        Anti-replay: UNIQUE(ceremony_id, participant_address, circuit_name).
        Duplicate entries raise sqlite3.IntegrityError (caller should catch and skip).
        Returns new row id on success.
        """
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO ceremony_audit_log "
                "(ceremony_id, circuit_name, participant_address, "
                "contribution_hash, ts_ns, created_at) "
                "VALUES (?,?,?,?,?,?)",
                (
                    str(ceremony_id),
                    str(circuit_name),
                    str(participant_address),
                    str(contribution_hash),
                    int(ts_ns),
                    time.time(),
                ),
            )
        return cur.lastrowid  # type: ignore[return-value]

    def count_ceremony_participants(self, circuit_name: str) -> int:
        """Return count of distinct participant_address entries for a ZK circuit (Phase 179)."""
        with self._conn() as conn:
            row = conn.execute(
                "SELECT COUNT(DISTINCT participant_address) FROM ceremony_audit_log "
                "WHERE circuit_name = ?",
                (str(circuit_name),),
            ).fetchone()
        return int(row[0]) if row else 0

    def get_ceremony_audit_status(self) -> "dict":
        """Return ceremony audit summary for GET /agent/ceremony-audit-status (Phase 179).

        Returns 7 keys: ceremony_audit_enabled/total_entries/distinct_participants/
        circuits_audited/min_participants/audit_passed/timestamp.
        audit_passed=True when distinct_participants >= min_participants across all circuits.
        When ceremony_audit_enabled=False (default): audit_passed=True (gate inactive).
        """
        ts_now = time.time()
        with self._conn() as conn:
            total_entries = conn.execute(
                "SELECT COUNT(*) FROM ceremony_audit_log"
            ).fetchone()[0]
            distinct_participants = conn.execute(
                "SELECT COUNT(DISTINCT participant_address) FROM ceremony_audit_log"
            ).fetchone()[0]
            circuits_row = conn.execute(
                "SELECT COUNT(DISTINCT circuit_name) FROM ceremony_audit_log"
            ).fetchone()
            circuits_audited = int(circuits_row[0]) if circuits_row else 0
        return {
            "ceremony_audit_enabled":   False,  # always reported; caller overlays from cfg
            "total_entries":            int(total_entries),
            "distinct_participants":    int(distinct_participants),
            "circuits_audited":         circuits_audited,
            "min_participants":         3,       # caller overlays from cfg
            "audit_passed":             True,    # caller overlays when enabled
            "timestamp":                ts_now,
        }

    # --- Phase 178: Biometric Credential TTL Gate (WIF-029 W1 closure) ---

    def insert_biometric_renewal_log(
        self,
        commit_hash: str,
        age_days: float,
        ttl_days: float,
        ttl_expired: bool,
        recalibration_required: bool,
        checked_by: str = "tournament_activation_chain_agent",
    ) -> int:
        """Insert a biometric credential TTL check record (Phase 178).

        Called by TournamentActivationChainAgent each time it evaluates whether the
        latest SeparationRatioRegistry.sol commitment has expired.
        ttl_expired=True blocks tournament authorization and sets recalibration_required=True.
        """
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO biometric_renewal_log "
                "(commit_hash, age_days, ttl_days, ttl_expired, "
                "recalibration_required, checked_by, created_at) "
                "VALUES (?,?,?,?,?,?,?)",
                (
                    str(commit_hash),
                    float(age_days),
                    float(ttl_days),
                    1 if ttl_expired else 0,
                    1 if recalibration_required else 0,
                    str(checked_by),
                    time.time(),
                ),
            )
        return cur.lastrowid  # type: ignore[return-value]

    def get_biometric_credential_age_status(self, ttl_days: float = 90.0) -> "dict":
        """Return the current biometric credential age and TTL status (Phase 178).

        Computes age_days live from the most recent separation_ratio_registry_log commit
        and compares against ttl_days (default 90, overridden by cfg.biometric_credential_ttl_days).
        ttl_expired=True is computed HERE — the biometric_renewal_log is an audit trail only,
        not the authority on current expiry state.

        Returns a dict with 8 keys: ttl_enabled/commit_hash/commit_ts/age_days/
        ttl_days/ttl_expired/recalibration_required/timestamp.
        """
        import time as _time

        ts_now = _time.time()
        # Get latest on-chain commit timestamp from separation_ratio_registry_log
        with self._conn() as conn:
            reg_row = conn.execute(
                "SELECT commit_hash, created_at FROM separation_ratio_registry_log "
                "ORDER BY id DESC LIMIT 1"
            ).fetchone()

        if reg_row is not None:
            commit_hash = str(reg_row[0])
            commit_ts = float(reg_row[1])
            age_days = (ts_now - commit_ts) / 86400.0
        else:
            commit_hash = ""
            commit_ts = 0.0
            age_days = 0.0

        # Compute expiry live: only expired when a commit exists AND age exceeds TTL
        ttl_expired = bool(commit_hash) and (age_days > float(ttl_days))
        recalibration_required = ttl_expired

        return {
            "ttl_enabled":             True,
            "commit_hash":             commit_hash,
            "commit_ts":               commit_ts,
            "age_days":                round(age_days, 4),
            "ttl_days":                float(ttl_days),
            "ttl_expired":             ttl_expired,
            "recalibration_required":  recalibration_required,
            "timestamp":               ts_now,
        }

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

    def insert_biometric_stationarity_log(
        self,
        player_id: str,
        p_genuine_drift: float,
        p_adversarial_window: float,
        stationarity_verdict: str,
        chain_integrity_score: float,
        trend_velocity: float,
        temporal_drift_index: float,
        session_count_used: int,
    ) -> int:
        """Insert a biometric stationarity assessment (Phase 188)."""
        confidence = max(p_genuine_drift, p_adversarial_window)
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO biometric_stationarity_log "
                "(player_id, p_genuine_drift, p_adversarial_window, stationarity_verdict, "
                "biometric_stationarity_confidence, chain_integrity_score, trend_velocity, "
                "temporal_drift_index, session_count_used, created_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?)",
                (
                    player_id,
                    float(p_genuine_drift),
                    float(p_adversarial_window),
                    stationarity_verdict,
                    float(confidence),
                    float(chain_integrity_score),
                    float(trend_velocity),
                    float(temporal_drift_index),
                    int(session_count_used),
                    time.time(),
                ),
            )
        return cur.lastrowid  # type: ignore[return-value]

    def get_biometric_stationarity_status(self, player_id: "str | None" = None) -> "dict | None":
        """Return latest biometric stationarity assessment (Phase 188)."""
        try:
            with self._conn() as conn:
                if player_id:
                    row = conn.execute(
                        "SELECT player_id, p_genuine_drift, p_adversarial_window, "
                        "stationarity_verdict, biometric_stationarity_confidence, "
                        "chain_integrity_score, trend_velocity, temporal_drift_index, "
                        "session_count_used, created_at "
                        "FROM biometric_stationarity_log WHERE player_id=? "
                        "ORDER BY id DESC LIMIT 1",
                        (player_id,),
                    ).fetchone()
                else:
                    row = conn.execute(
                        "SELECT player_id, p_genuine_drift, p_adversarial_window, "
                        "stationarity_verdict, biometric_stationarity_confidence, "
                        "chain_integrity_score, trend_velocity, temporal_drift_index, "
                        "session_count_used, created_at "
                        "FROM biometric_stationarity_log ORDER BY id DESC LIMIT 1"
                    ).fetchone()
                total_adversarial = conn.execute(
                    "SELECT COUNT(*) FROM biometric_stationarity_log "
                    "WHERE stationarity_verdict='ADVERSARIAL_WINDOW'"
                ).fetchone()[0]
        except Exception:
            return None
        if row is None:
            return {
                "player_id": player_id or "",
                "p_genuine_drift": 0.0,
                "p_adversarial_window": 0.0,
                "stationarity_verdict": "STABLE",
                "biometric_stationarity_confidence": 0.5,
                "chain_integrity_score": 1.0,
                "trend_velocity": 0.0,
                "temporal_drift_index": 0.0,
                "session_count_used": 0,
                "total_adversarial_alerts": 0,
                "created_at": 0.0,
            }
        return {
            "player_id":                        row[0],
            "p_genuine_drift":                  float(row[1]),
            "p_adversarial_window":             float(row[2]),
            "stationarity_verdict":             row[3],
            "biometric_stationarity_confidence": float(row[4]),
            "chain_integrity_score":            float(row[5]),
            "trend_velocity":                   float(row[6]),
            "temporal_drift_index":             float(row[7]),
            "session_count_used":               int(row[8]),
            "total_adversarial_alerts":         int(total_adversarial),
            "created_at":                       float(row[9]),
        }

    # --- Phase 187: AttestationOpSecAdvisorAgent + VHPReenrollmentBadge ---

    def insert_attestation_opsec_log(
        self,
        player_id: str,
        timing_disclosure_risk: str,
        active_attestations: int,
        re_enrollment_window_active: bool,
        recommendation: str,
    ) -> int:
        """Insert an attestation OpSec advisory record (Phase 187)."""
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO attestation_opsec_log "
                "(player_id, timing_disclosure_risk, active_attestations, "
                "re_enrollment_window_active, recommendation, created_at) "
                "VALUES (?,?,?,?,?,?)",
                (
                    player_id,
                    timing_disclosure_risk,
                    int(active_attestations),
                    1 if re_enrollment_window_active else 0,
                    recommendation,
                    time.time(),
                ),
            )
        return cur.lastrowid  # type: ignore[return-value]

    def get_attestation_opsec_status(self, player_id: "str | None" = None) -> dict:
        """Return latest attestation OpSec advisory status (Phase 187)."""
        try:
            with self._conn() as conn:
                if player_id:
                    row = conn.execute(
                        "SELECT player_id, timing_disclosure_risk, active_attestations, "
                        "re_enrollment_window_active, recommendation, created_at "
                        "FROM attestation_opsec_log WHERE player_id=? ORDER BY id DESC LIMIT 1",
                        (player_id,),
                    ).fetchone()
                else:
                    row = conn.execute(
                        "SELECT player_id, timing_disclosure_risk, active_attestations, "
                        "re_enrollment_window_active, recommendation, created_at "
                        "FROM attestation_opsec_log ORDER BY id DESC LIMIT 1"
                    ).fetchone()
                total_high = conn.execute(
                    "SELECT COUNT(*) FROM attestation_opsec_log WHERE timing_disclosure_risk='HIGH'"
                ).fetchone()[0]
        except Exception:
            return {
                "player_id": player_id or "",
                "timing_disclosure_risk": "LOW",
                "active_attestations": 0,
                "re_enrollment_window_active": False,
                "recommendation": "STANDARD_TX_OK",
                "total_high_risk_events": 0,
                "created_at": 0.0,
            }
        if row is None:
            return {
                "player_id": player_id or "",
                "timing_disclosure_risk": "LOW",
                "active_attestations": 0,
                "re_enrollment_window_active": False,
                "recommendation": "STANDARD_TX_OK",
                "total_high_risk_events": int(total_high),
                "created_at": 0.0,
            }
        return {
            "player_id":                  row[0],
            "timing_disclosure_risk":     row[1],
            "active_attestations":        int(row[2]),
            "re_enrollment_window_active": bool(row[3]),
            "recommendation":             row[4],
            "total_high_risk_events":     int(total_high),
            "created_at":                 float(row[5]),
        }

    def insert_reenrollment_badge_log(
        self,
        player_id: str,
        attestation_hash: str,
        badge_token_id: int,
        ttl_days: float,
        on_chain_tx: str,
        dry_run: bool,
    ) -> int:
        """Insert a VHP re-enrollment badge log record (Phase 187)."""
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO vhp_reenrollment_badge_log "
                "(player_id, attestation_hash, badge_token_id, ttl_days, "
                "on_chain_tx, dry_run, created_at) VALUES (?,?,?,?,?,?,?)",
                (
                    player_id,
                    attestation_hash,
                    int(badge_token_id),
                    float(ttl_days),
                    on_chain_tx,
                    1 if dry_run else 0,
                    time.time(),
                ),
            )
        return cur.lastrowid  # type: ignore[return-value]

    def get_reenrollment_badge_status(self, player_id: "str | None" = None) -> dict:
        """Return VHP re-enrollment badge status (Phase 187)."""
        try:
            with self._conn() as conn:
                if player_id:
                    row = conn.execute(
                        "SELECT player_id, attestation_hash, badge_token_id, ttl_days, "
                        "on_chain_tx, dry_run, created_at "
                        "FROM vhp_reenrollment_badge_log WHERE player_id=? ORDER BY id DESC LIMIT 1",
                        (player_id,),
                    ).fetchone()
                    total_badges = conn.execute(
                        "SELECT COUNT(*) FROM vhp_reenrollment_badge_log WHERE player_id=?",
                        (player_id,),
                    ).fetchone()[0]
                else:
                    row = conn.execute(
                        "SELECT player_id, attestation_hash, badge_token_id, ttl_days, "
                        "on_chain_tx, dry_run, created_at "
                        "FROM vhp_reenrollment_badge_log ORDER BY id DESC LIMIT 1"
                    ).fetchone()
                    total_badges = conn.execute(
                        "SELECT COUNT(*) FROM vhp_reenrollment_badge_log"
                    ).fetchone()[0]
        except Exception:
            return {
                "player_id": player_id or "",
                "attestation_hash": "",
                "badge_token_id": 0,
                "re_enrollment_count": 0,
                "total_badges": 0,
                "ttl_days": 90.0,
                "dry_run": True,
            }
        if row is None:
            return {
                "player_id": player_id or "",
                "attestation_hash": "",
                "badge_token_id": 0,
                "re_enrollment_count": 0,
                "total_badges": 0,
                "ttl_days": 90.0,
                "dry_run": True,
            }
        return {
            "player_id":          row[0],
            "attestation_hash":   row[1],
            "badge_token_id":     int(row[2]),
            "re_enrollment_count": int(total_badges),
            "total_badges":       int(total_badges),
            "ttl_days":           float(row[3]),
            "dry_run":            bool(row[5]),
        }

    # --- Phase 186: AttestationBoundRenewalAgent ---

    def insert_attestation_bound_renewal_log(
        self,
        player_id: str,
        attestation_hash: str,
        renewal_approved: bool,
        denial_reason: str,
        new_commit_hash: str,
    ) -> int:
        """Insert an attestation-bound renewal validation record (Phase 186)."""
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO attestation_bound_renewal_log "
                "(player_id, attestation_hash, renewal_approved, denial_reason, "
                "new_commit_hash, created_at) VALUES (?,?,?,?,?,?)",
                (
                    player_id,
                    attestation_hash,
                    1 if renewal_approved else 0,
                    denial_reason,
                    new_commit_hash,
                    time.time(),
                ),
            )
        return cur.lastrowid  # type: ignore[return-value]

    def get_attestation_bound_renewal_status(self, player_id: "str | None" = None) -> dict:
        """Return attestation-bound renewal status (Phase 186)."""
        try:
            with self._conn() as conn:
                if player_id:
                    row = conn.execute(
                        "SELECT player_id, attestation_hash, renewal_approved, denial_reason, "
                        "new_commit_hash, created_at "
                        "FROM attestation_bound_renewal_log WHERE player_id=? "
                        "ORDER BY id DESC LIMIT 1",
                        (player_id,),
                    ).fetchone()
                else:
                    row = conn.execute(
                        "SELECT player_id, attestation_hash, renewal_approved, denial_reason, "
                        "new_commit_hash, created_at "
                        "FROM attestation_bound_renewal_log ORDER BY id DESC LIMIT 1"
                    ).fetchone()
                total_blocked = conn.execute(
                    "SELECT COUNT(*) FROM attestation_bound_renewal_log WHERE renewal_approved=0"
                ).fetchone()[0]
                total_approved = conn.execute(
                    "SELECT COUNT(*) FROM attestation_bound_renewal_log WHERE renewal_approved=1"
                ).fetchone()[0]
        except Exception:
            return {
                "player_id": player_id or "",
                "attestation_hash": "",
                "renewal_approved": False,
                "denial_reason": "",
                "total_blocked": 0,
                "total_approved": 0,
            }
        if row is None:
            return {
                "player_id": player_id or "",
                "attestation_hash": "",
                "renewal_approved": False,
                "denial_reason": "",
                "total_blocked": int(total_blocked),
                "total_approved": int(total_approved),
            }
        return {
            "player_id":        row[0],
            "attestation_hash": row[1],
            "renewal_approved": bool(row[2]),
            "denial_reason":    row[3],
            "total_blocked":    int(total_blocked),
            "total_approved":   int(total_approved),
        }

    # --- Phase 185: ReEnrollmentAttestationAgent ---

    def insert_persona_break_attestation(
        self,
        player_id: str,
        hash: str,
        loo_trend: float,
        tdi: float,
        ttl_days: float,
        issued_at: float,
        expires_at: float,
    ) -> int:
        """Insert a persona break attestation token (Phase 185)."""
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO persona_break_attestation_log "
                "(player_id, attestation_hash, active, issued_at, expires_at, "
                "loo_trend_at_break, tdi_at_break, ttl_days, created_at) "
                "VALUES (?,?,?,?,?,?,?,?,?)",
                (
                    player_id,
                    hash,
                    1,
                    float(issued_at),
                    float(expires_at),
                    float(loo_trend),
                    float(tdi),
                    float(ttl_days),
                    time.time(),
                ),
            )
        return cur.lastrowid  # type: ignore[return-value]

    def get_active_attestation(self, player_id: str) -> dict:
        """Return latest active attestation for a player (Phase 185).

        Returns safe dict with active=False when no active row found.
        """
        try:
            with self._conn() as conn:
                row = conn.execute(
                    "SELECT player_id, attestation_hash, active, issued_at, expires_at, "
                    "loo_trend_at_break, tdi_at_break, ttl_days, created_at "
                    "FROM persona_break_attestation_log "
                    "WHERE player_id=? AND active=1 ORDER BY id DESC LIMIT 1",
                    (player_id,),
                ).fetchone()
        except Exception:
            row = None
        if row is None:
            return {
                "player_id": player_id,
                "attestation_hash": "",
                "active": False,
                "issued_at": 0.0,
                "expires_at": 0.0,
                "loo_trend_at_break": 0.0,
                "tdi_at_break": 0.0,
                "ttl_days": 7.0,
            }
        return {
            "player_id":        row[0],
            "attestation_hash": row[1],
            "active":           bool(row[2]),
            "issued_at":        float(row[3]),
            "expires_at":       float(row[4]),
            "loo_trend_at_break": float(row[5]),
            "tdi_at_break":     float(row[6]),
            "ttl_days":         float(row[7]),
        }

    def expire_stale_attestations(self) -> int:
        """Set active=0 for all attestations past their expires_at (Phase 185).

        Returns count of rows deactivated.
        """
        now = time.time()
        with self._conn() as conn:
            cur = conn.execute(
                "UPDATE persona_break_attestation_log SET active=0 "
                "WHERE active=1 AND expires_at <= ?",
                (now,),
            )
        return cur.rowcount

    # --- Phase 183: MaturityElevationGateAgent ---

    def insert_maturity_elevation_log(
        self,
        current_tier: str,
        target_tier: str,
        gap_to_target: float,
        elevation_plan_json: str,
        elevation_available: bool,
        critical_component: str,
        estimated_sessions_total: int,
    ) -> int:
        """Insert a maturity elevation assessment (Phase 183)."""
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO maturity_elevation_log "
                "(current_tier, target_tier, gap_to_target, elevation_plan_json, "
                "elevation_available, critical_component, estimated_sessions_total, created_at) "
                "VALUES (?,?,?,?,?,?,?,?)",
                (
                    current_tier,
                    target_tier,
                    float(gap_to_target),
                    elevation_plan_json,
                    1 if elevation_available else 0,
                    critical_component,
                    int(estimated_sessions_total),
                    time.time(),
                ),
            )
        return cur.lastrowid  # type: ignore[return-value]

    def get_maturity_elevation_status(self) -> dict:
        """Return latest maturity elevation status (Phase 183)."""
        try:
            with self._conn() as conn:
                row = conn.execute(
                    "SELECT current_tier, target_tier, gap_to_target, elevation_plan_json, "
                    "elevation_available, critical_component, estimated_sessions_total, created_at "
                    "FROM maturity_elevation_log ORDER BY id DESC LIMIT 1"
                ).fetchone()
        except Exception:
            row = None
        if row is None:
            return {
                "current_tier": "ALPHA",
                "target_tier": "BETA",
                "gap_to_target": 1.0,
                "elevation_plan_json": "{}",
                "elevation_available": False,
                "critical_component": "",
                "estimated_sessions_total": 0,
                "created_at": 0.0,
            }
        return {
            "current_tier":            row[0],
            "target_tier":             row[1],
            "gap_to_target":           float(row[2]),
            "elevation_plan_json":     row[3],
            "elevation_available":     bool(row[4]),
            "critical_component":      row[5],
            "estimated_sessions_total": int(row[6]),
            "created_at":              float(row[7]),
        }

    # --- Phase 182: PersonaBreakDetectorAgent ---

    def insert_persona_break_log(
        self,
        player_id: str,
        loo_accuracy_trend: float,
        tdi_current: float,
        persona_break_detected: bool,
        urgency: str,
        n_snapshots: int,
    ) -> int:
        """Insert a persona break detection record (Phase 182)."""
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO persona_break_log "
                "(player_id, loo_accuracy_trend, tdi_current, persona_break_detected, "
                "re_enrollment_urgency, n_snapshots_used, created_at) VALUES (?,?,?,?,?,?,?)",
                (
                    player_id,
                    float(loo_accuracy_trend),
                    float(tdi_current),
                    1 if persona_break_detected else 0,
                    urgency,
                    int(n_snapshots),
                    time.time(),
                ),
            )
        return cur.lastrowid  # type: ignore[return-value]

    def get_persona_break_status(self, player_id: "str | None" = None) -> dict:
        """Return latest persona break status (Phase 182).

        Returns safe defaults when no data exists.
        """
        try:
            with self._conn() as conn:
                if player_id:
                    row = conn.execute(
                        "SELECT player_id, loo_accuracy_trend, tdi_current, "
                        "persona_break_detected, re_enrollment_urgency, n_snapshots_used, created_at "
                        "FROM persona_break_log WHERE player_id=? ORDER BY id DESC LIMIT 1",
                        (player_id,),
                    ).fetchone()
                else:
                    row = conn.execute(
                        "SELECT player_id, loo_accuracy_trend, tdi_current, "
                        "persona_break_detected, re_enrollment_urgency, n_snapshots_used, created_at "
                        "FROM persona_break_log ORDER BY id DESC LIMIT 1"
                    ).fetchone()
        except Exception:
            row = None
        if row is None:
            return {
                "player_id":              player_id or "",
                "loo_accuracy_trend":     1.0,
                "tdi_current":            0.0,
                "persona_break_detected": False,
                "re_enrollment_urgency":  "MEDIUM",
                "n_snapshots_used":       0,
                "created_at":             0.0,
            }
        return {
            "player_id":              row[0],
            "loo_accuracy_trend":     float(row[1]),
            "tdi_current":            float(row[2]),
            "persona_break_detected": bool(row[3]),
            "re_enrollment_urgency":  row[4],
            "n_snapshots_used":       int(row[5]),
            "created_at":             float(row[6]),
        }

    # --- Phase 181: Consent-Bound Renewal Provenance ---

    def insert_renewal_consent_snapshot(
        self,
        new_commit_hash: str,
        n_consented: int,
        players_json: str,
        revoked: int,
        delta: bool,
    ) -> int:
        """Insert a renewal consent snapshot linked by new_commit_hash (Phase 181)."""
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO renewal_consent_snapshot_log "
                "(new_commit_hash, n_consented_at_renewal, players_consented_json, "
                "revoked_at_renewal, corpus_delta_detected, created_at) VALUES (?,?,?,?,?,?)",
                (
                    new_commit_hash,
                    int(n_consented),
                    players_json,
                    int(revoked),
                    1 if delta else 0,
                    time.time(),
                ),
            )
        return cur.lastrowid  # type: ignore[return-value]

    def get_renewal_consent_snapshot(self, new_commit_hash: str) -> "dict | None":
        """Return renewal consent snapshot for a given commit hash (Phase 181).

        Returns None when hash not found.
        """
        try:
            with self._conn() as conn:
                row = conn.execute(
                    "SELECT new_commit_hash, n_consented_at_renewal, players_consented_json, "
                    "revoked_at_renewal, corpus_delta_detected, created_at "
                    "FROM renewal_consent_snapshot_log WHERE new_commit_hash=?",
                    (new_commit_hash,),
                ).fetchone()
        except Exception:
            return None
        if row is None:
            return None
        return {
            "new_commit_hash":        row[0],
            "n_consented_at_renewal": int(row[1]),
            "players_consented_json": row[2],
            "revoked_at_renewal":     int(row[3]),
            "corpus_delta_detected":  int(row[4]),
            "created_at":             float(row[5]),
        }

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

    def register_calibration_session(self, session_file: str, player_id: str,
                                     phase: int) -> str:
        """Create a CALIBRATION_SESSION root node in the provenance DAG (Phase 192).
        node_id = SHA-256(session_file + player_id + str(phase))."""
        import hashlib
        node_id = "sha256:" + hashlib.sha256(
            (session_file + player_id + str(phase)).encode()
        ).hexdigest()
        self.insert_provenance_node({
            "node_id":        node_id,
            "node_type":      "CALIBRATION_SESSION",
            "source_table":   "calibration_sessions",
            "source_row_id":  None,
            "source_hash":    None,
            "parent_node_id": None,
            "edge_type":      None,
            "phase_produced": phase,
            "player_id":      player_id,
            "on_chain_ref":   None,
        })
        return node_id

    # Task 2: Corpus Entropy Monitor

    def insert_corpus_entropy(self, score: float, per_player_json: str,
                              per_feature_json: str, low_entropy_features_json: str,
                              clustering_warning: bool, n_sessions: int,
                              session_type_filter: str = "touchpad_corners",
                              computed_at_ts: int = 0) -> int:
        """Insert a corpus entropy measurement (Phase 192)."""
        if computed_at_ts == 0:
            computed_at_ts = int(time.time())
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO corpus_entropy_log "
                "(corpus_entropy_score, per_player_entropy, per_feature_entropy, "
                "low_entropy_features, clustering_warning, n_sessions_analyzed, "
                "session_type_filter, computed_at_ts) VALUES (?,?,?,?,?,?,?,?)",
                (score, per_player_json, per_feature_json, low_entropy_features_json,
                 1 if clustering_warning else 0, n_sessions, session_type_filter,
                 computed_at_ts),
            )
        return cur.lastrowid  # type: ignore[return-value]

    def get_latest_corpus_entropy(self, session_type: str = "touchpad_corners") -> "dict | None":
        """Return most recent corpus entropy record (Phase 192)."""
        try:
            with self._conn() as conn:
                row = conn.execute(
                    "SELECT corpus_entropy_score, per_player_entropy, per_feature_entropy, "
                    "low_entropy_features, clustering_warning, n_sessions_analyzed, "
                    "session_type_filter, computed_at_ts, created_at "
                    "FROM corpus_entropy_log WHERE session_type_filter=? "
                    "ORDER BY computed_at_ts DESC LIMIT 1",
                    (session_type,),
                ).fetchone()
        except Exception:
            row = None
        if row is None:
            return None
        return {
            "corpus_entropy_score":  float(row[0]),
            "per_player_entropy":    row[1],
            "per_feature_entropy":   row[2],
            "low_entropy_features":  row[3],
            "clustering_warning":    bool(row[4]),
            "n_sessions_analyzed":   int(row[5]),
            "session_type_filter":   row[6],
            "computed_at_ts":        int(row[7]),
            "created_at":            row[8],
        }

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

    # Task 4: Federated Corpus Quality Aggregator

    def insert_federation_corpus_quality(self, bridge_id_hash: str, session_type: str,
                                         n_sessions: int, entropy_score: float,
                                         stationarity_score: float,
                                         centroid_velocity_mean: float,
                                         received_at_ts: int) -> int:
        """Insert anonymized federation corpus quality record (Phase 192, BP-007)."""
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO federation_corpus_quality_log "
                "(bridge_id_hash, session_type, n_sessions, entropy_score, "
                "stationarity_score, centroid_velocity_mean, received_at_ts) "
                "VALUES (?,?,?,?,?,?,?)",
                (bridge_id_hash, session_type, n_sessions, entropy_score,
                 stationarity_score, centroid_velocity_mean, received_at_ts),
            )
        return cur.lastrowid  # type: ignore[return-value]

    def get_federated_corpus_quality(self, session_type: str = "touchpad_corners",
                                     limit: int = 10) -> list:
        """Return recent federation corpus quality records (Phase 192)."""
        try:
            with self._conn() as conn:
                rows = conn.execute(
                    "SELECT bridge_id_hash, session_type, n_sessions, entropy_score, "
                    "stationarity_score, centroid_velocity_mean, federation_entropy_mean, "
                    "federation_outlier, outlier_sigma, received_at_ts, created_at "
                    "FROM federation_corpus_quality_log WHERE session_type=? "
                    "ORDER BY received_at_ts DESC LIMIT ?",
                    (session_type, limit),
                ).fetchall()
        except Exception:
            rows = []
        return [
            {
                "bridge_id_hash":         r[0],
                "session_type":           r[1],
                "n_sessions":             int(r[2]),
                "entropy_score":          float(r[3]),
                "stationarity_score":     float(r[4]),
                "centroid_velocity_mean": float(r[5]),
                "federation_entropy_mean": float(r[6]) if r[6] is not None else None,
                "federation_outlier":     bool(r[7]),
                "outlier_sigma":          float(r[8]) if r[8] is not None else None,
                "received_at_ts":         int(r[9]),
                "created_at":             r[10],
            }
            for r in rows
        ]

    # Task 5: Cross-Feature Temporal Correlation Engine

    def insert_feature_correlation(self, player_id: str, session_type: str,
                                   n_sessions_used: int, correlation_upper_tri: str,
                                   high_correlation_pairs: str,
                                   frobenius_vs_p1: "float | None",
                                   frobenius_vs_p2: "float | None",
                                   frobenius_vs_p3: "float | None",
                                   correlation_separable: bool,
                                   computed_at_ts: int = 0) -> int:
        """Insert per-player feature correlation matrix (Phase 192)."""
        if computed_at_ts == 0:
            computed_at_ts = int(time.time())
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO feature_correlation_log "
                "(player_id, session_type, n_sessions_used, correlation_upper_tri, "
                "high_correlation_pairs, frobenius_vs_p1, frobenius_vs_p2, frobenius_vs_p3, "
                "correlation_separable, computed_at_ts) VALUES (?,?,?,?,?,?,?,?,?,?)",
                (player_id, session_type, n_sessions_used, correlation_upper_tri,
                 high_correlation_pairs, frobenius_vs_p1, frobenius_vs_p2, frobenius_vs_p3,
                 1 if correlation_separable else 0, computed_at_ts),
            )
        return cur.lastrowid  # type: ignore[return-value]

    def get_feature_correlation(self, player_id: str = "",
                                session_type: str = "touchpad_corners") -> "dict | None":
        """Return most recent correlation entry for player_id (Phase 192)."""
        try:
            with self._conn() as conn:
                if player_id:
                    row = conn.execute(
                        "SELECT player_id, session_type, n_sessions_used, correlation_upper_tri, "
                        "high_correlation_pairs, frobenius_vs_p1, frobenius_vs_p2, frobenius_vs_p3, "
                        "correlation_separable, computed_at_ts, created_at "
                        "FROM feature_correlation_log WHERE player_id=? AND session_type=? "
                        "ORDER BY computed_at_ts DESC LIMIT 1",
                        (player_id, session_type),
                    ).fetchone()
                else:
                    row = conn.execute(
                        "SELECT player_id, session_type, n_sessions_used, correlation_upper_tri, "
                        "high_correlation_pairs, frobenius_vs_p1, frobenius_vs_p2, frobenius_vs_p3, "
                        "correlation_separable, computed_at_ts, created_at "
                        "FROM feature_correlation_log WHERE session_type=? "
                        "ORDER BY computed_at_ts DESC LIMIT 1",
                        (session_type,),
                    ).fetchone()
        except Exception:
            row = None
        if row is None:
            return None
        return {
            "player_id":              row[0],
            "session_type":           row[1],
            "n_sessions_used":        int(row[2]),
            "correlation_upper_tri":  row[3],
            "high_correlation_pairs": row[4],
            "frobenius_vs_p1":        float(row[5]) if row[5] is not None else None,
            "frobenius_vs_p2":        float(row[6]) if row[6] is not None else None,
            "frobenius_vs_p3":        float(row[7]) if row[7] is not None else None,
            "correlation_separable":  bool(row[8]),
            "computed_at_ts":         int(row[9]),
            "created_at":             row[10],
        }

    # Task 6: Data Readiness Certificate Engine

    def insert_data_readiness_certificate(self, certificate_hash: str,
                                          certification_status: str,
                                          blocking_failures: str,
                                          advisory_warnings: str,
                                          dimension_results: str,
                                          separation_ratio: float,
                                          valid_until_ts: int,
                                          ts_ns: int) -> int:
        """Insert a data readiness certificate (idempotent on UNIQUE hash). Phase 192."""
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT OR IGNORE INTO data_readiness_certificate_log "
                "(certificate_hash, certification_status, blocking_failures, advisory_warnings, "
                "dimension_results, separation_ratio, valid_until_ts, ts_ns) "
                "VALUES (?,?,?,?,?,?,?,?)",
                (certificate_hash, certification_status, blocking_failures, advisory_warnings,
                 dimension_results, separation_ratio, valid_until_ts, ts_ns),
            )
        return cur.lastrowid or 0  # type: ignore[return-value]

    def get_latest_data_readiness_certificate(self) -> "dict | None":
        """Return most recent data readiness certificate (Phase 192)."""
        try:
            with self._conn() as conn:
                row = conn.execute(
                    "SELECT certificate_hash, certification_status, blocking_failures, "
                    "advisory_warnings, dimension_results, separation_ratio, on_chain_tx_hash, "
                    "anchored, valid_until_ts, ts_ns, created_at "
                    "FROM data_readiness_certificate_log ORDER BY ts_ns DESC LIMIT 1"
                ).fetchone()
        except Exception:
            row = None
        if row is None:
            return None
        return {
            "certificate_hash":    row[0],
            "certification_status": row[1],
            "blocking_failures":   row[2],
            "advisory_warnings":   row[3],
            "dimension_results":   row[4],
            "separation_ratio":    float(row[5]),
            "on_chain_tx_hash":    row[6],
            "anchored":            bool(row[7]),
            "valid_until_ts":      int(row[8]),
            "ts_ns":               int(row[9]),
            "created_at":          row[10],
        }

    def anchor_data_readiness_certificate(self, certificate_hash: str, tx_hash: str) -> None:
        """Mark a data readiness certificate as anchored on-chain (Phase 192)."""
        with self._conn() as conn:
            conn.execute(
                "UPDATE data_readiness_certificate_log SET on_chain_tx_hash=?, anchored=1 "
                "WHERE certificate_hash=?",
                (tx_hash, certificate_hash),
            )

    # Task 7: Session Contribution Weight Table

    def insert_session_contribution_weight(self, session_file: str, player_id: str,
                                           session_type: str,
                                           session_captured_at_ts: int,
                                           age_days: float, tbd_weight: float,
                                           type_multiplier: float,
                                           stationarity_multiplier: float,
                                           effective_weight: float,
                                           centroid_influence_rank: "int | None" = None,
                                           computed_at_ts: int = 0) -> int:
        """Insert session contribution weight (Phase 192). FROZEN: lambda=ln(2)/90."""
        if computed_at_ts == 0:
            computed_at_ts = int(time.time())
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO session_contribution_weight_log "
                "(session_file, player_id, session_type, session_captured_at_ts, age_days, "
                "tbd_weight, type_multiplier, stationarity_multiplier, effective_weight, "
                "centroid_influence_rank, computed_at_ts) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (session_file, player_id, session_type, session_captured_at_ts, age_days,
                 tbd_weight, type_multiplier, stationarity_multiplier, effective_weight,
                 centroid_influence_rank, computed_at_ts),
            )
        return cur.lastrowid  # type: ignore[return-value]

    def get_session_weights(self, player_id: str = "",
                            limit: int = 50) -> list:
        """Return session contribution weights, ordered by effective_weight DESC (Phase 192)."""
        try:
            with self._conn() as conn:
                if player_id:
                    rows = conn.execute(
                        "SELECT session_file, player_id, session_type, session_captured_at_ts, "
                        "age_days, tbd_weight, type_multiplier, stationarity_multiplier, "
                        "effective_weight, centroid_influence_rank, computed_at_ts, created_at "
                        "FROM session_contribution_weight_log WHERE player_id=? "
                        "ORDER BY effective_weight DESC LIMIT ?",
                        (player_id, limit),
                    ).fetchall()
                else:
                    rows = conn.execute(
                        "SELECT session_file, player_id, session_type, session_captured_at_ts, "
                        "age_days, tbd_weight, type_multiplier, stationarity_multiplier, "
                        "effective_weight, centroid_influence_rank, computed_at_ts, created_at "
                        "FROM session_contribution_weight_log "
                        "ORDER BY effective_weight DESC LIMIT ?",
                        (limit,),
                    ).fetchall()
        except Exception:
            rows = []
        return [
            {
                "session_file":           r[0],
                "player_id":              r[1],
                "session_type":           r[2],
                "session_captured_at_ts": int(r[3]),
                "age_days":               float(r[4]),
                "tbd_weight":             float(r[5]),
                "type_multiplier":        float(r[6]),
                "stationarity_multiplier": float(r[7]),
                "effective_weight":       float(r[8]),
                "centroid_influence_rank": int(r[9]) if r[9] is not None else None,
                "computed_at_ts":         int(r[10]),
                "created_at":             r[11],
            }
            for r in rows
        ]

    def get_session_weight(self, session_file: str) -> float:
        """Return effective_weight for a specific session file (Phase 192, 1.0 if not found)."""
        try:
            with self._conn() as conn:
                row = conn.execute(
                    "SELECT effective_weight FROM session_contribution_weight_log "
                    "WHERE session_file=? ORDER BY computed_at_ts DESC LIMIT 1",
                    (session_file,),
                ).fetchone()
        except Exception:
            row = None
        return float(row[0]) if row else 1.0

    # -----------------------------------------------------------------------
    # Phase 193: FleetSignalCoherenceAgent (Agent #36) — fleet_coherence_log
    # -----------------------------------------------------------------------

    def insert_coherence_entry(self, entry: dict) -> str:
        """INSERT OR IGNORE on coherence_id (idempotent). Returns coherence_id.
        evidence_json must already be BP-007 scrubbed (no raw biometric fields)."""
        import json as _json
        try:
            with self._conn() as conn:
                conn.execute(
                    "INSERT OR IGNORE INTO fleet_coherence_log "
                    "(coherence_id, failure_mode, rule_name, agents_involved, severity, "
                    " explanation, resolution, evidence_json, phase_detected, ts_ns) "
                    "VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (
                        entry["coherence_id"],
                        entry["failure_mode"],
                        entry["rule_name"],
                        entry["agents_involved"]
                        if isinstance(entry["agents_involved"], str)
                        else _json.dumps(entry["agents_involved"]),
                        entry["severity"],
                        entry["explanation"],
                        entry["resolution"],
                        entry.get("evidence_json", "[]"),
                        entry.get("phase_detected", 193),
                        entry.get("ts_ns", 0),
                    ),
                )
        except Exception:
            pass
        return entry["coherence_id"]

    def get_open_coherence_entries(
        self,
        severity: "str | None" = None,
        failure_mode: "str | None" = None,
    ) -> "list[dict]":
        """Return all unresolved fleet_coherence_log entries, optionally filtered."""
        import json as _json
        clauses = ["resolved = 0"]
        params: list = []
        if severity:
            clauses.append("severity = ?")
            params.append(severity)
        if failure_mode:
            clauses.append("failure_mode = ?")
            params.append(failure_mode)
        where = " AND ".join(clauses)
        try:
            with self._conn() as conn:
                rows = conn.execute(
                    f"SELECT * FROM fleet_coherence_log WHERE {where} "
                    "ORDER BY created_at DESC LIMIT 100",
                    params,
                ).fetchall()
        except Exception:
            return []
        cols = [
            "id", "coherence_id", "failure_mode", "rule_name", "agents_involved",
            "severity", "explanation", "resolution", "evidence_json",
            "promoted_to_wif", "wif_entry_id", "wiki_contradict_written",
            "alert_published", "resolved", "resolved_at", "resolved_by",
            "phase_detected", "ts_ns", "created_at",
        ]
        result = []
        for row in rows:
            d = dict(zip(cols, row))
            d["promoted_to_wif"] = bool(d["promoted_to_wif"])
            d["resolved"] = bool(d["resolved"])
            try:
                d["agents_involved"] = _json.loads(d["agents_involved"])
            except Exception:
                pass
            result.append(d)
        return result

    def get_coherence_summary(self) -> dict:
        """Return aggregated fleet coherence status for GET /agent/fleet-coherence-summary."""
        from datetime import datetime, timezone
        try:
            with self._conn() as conn:
                total_row = conn.execute(
                    "SELECT COUNT(*) FROM fleet_coherence_log WHERE resolved=0"
                ).fetchone()
                total_open = int(total_row[0]) if total_row else 0

                sev_rows = conn.execute(
                    "SELECT severity, COUNT(*) FROM fleet_coherence_log "
                    "WHERE resolved=0 GROUP BY severity"
                ).fetchall()
                by_severity = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0}
                for sev, cnt in sev_rows:
                    if sev in by_severity:
                        by_severity[sev] = int(cnt)

                mode_rows = conn.execute(
                    "SELECT failure_mode, COUNT(*) FROM fleet_coherence_log "
                    "WHERE resolved=0 GROUP BY failure_mode"
                ).fetchall()
                by_mode = {"CONTRADICTION": 0, "ORPHAN": 0, "INVERSION": 0}
                for mode, cnt in mode_rows:
                    if mode in by_mode:
                        by_mode[mode] = int(cnt)

                promo_row = conn.execute(
                    "SELECT COUNT(*) FROM fleet_coherence_log WHERE promoted_to_wif=1"
                ).fetchone()
                promoted = int(promo_row[0]) if promo_row else 0

                last_row = conn.execute(
                    "SELECT created_at FROM fleet_coherence_log ORDER BY created_at DESC LIMIT 1"
                ).fetchone()
                last_checked = last_row[0] if last_row else ""
        except Exception:
            total_open, by_severity, by_mode, promoted, last_checked = (
                0,
                {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0},
                {"CONTRADICTION": 0, "ORPHAN": 0, "INVERSION": 0},
                0,
                "",
            )
        return {
            "total_open":      total_open,
            "by_severity":     by_severity,
            "by_mode":         by_mode,
            "promoted_to_wif": promoted,
            "last_checked_at": last_checked,
        }

    def mark_coherence_resolved(self, coherence_id: str, resolved_by: str) -> None:
        """Mark a coherence entry as resolved."""
        from datetime import datetime, timezone
        ts = datetime.now(timezone.utc).isoformat()
        try:
            with self._conn() as conn:
                conn.execute(
                    "UPDATE fleet_coherence_log SET resolved=1, resolved_at=?, resolved_by=? "
                    "WHERE coherence_id=?",
                    (ts, resolved_by, coherence_id),
                )
        except Exception:
            pass

    def mark_coherence_promoted(self, coherence_id: str, wif_id: str) -> None:
        """Mark a coherence entry as promoted to a WIF entry."""
        try:
            with self._conn() as conn:
                conn.execute(
                    "UPDATE fleet_coherence_log SET promoted_to_wif=1, wif_entry_id=? "
                    "WHERE coherence_id=?",
                    (wif_id, coherence_id),
                )
        except Exception:
            pass

    # Phase 194: CoherenceFingerprintRegistry — coherence_fingerprint_log

    def upsert_coherence_fingerprint(self, rule_name: str, failure_mode: str) -> None:
        """Insert or increment occurrence_count for rule_name in coherence_fingerprint_log.

        Called once per detection cycle per rule that fires. Sets persistent=1 when
        occurrence_count reaches N_PROMOTE_THRESHOLD (3). Fail-open: never raises.
        Uses two-statement insert-or-ignore + update pattern for broad SQLite compatibility.
        """
        N_PROMOTE_THRESHOLD = 3
        try:
            from datetime import datetime, timezone
            now = datetime.now(timezone.utc).isoformat()
            with self._conn() as conn:
                # Step 1: ensure row exists (occurrence_count starts at 0 so
                #          the UPDATE always owns the increment logic)
                conn.execute(
                    "INSERT OR IGNORE INTO coherence_fingerprint_log "
                    "(rule_name, failure_mode, first_seen_at, last_seen_at, "
                    " occurrence_count, persistent) "
                    "VALUES (?, ?, ?, ?, 0, 0)",
                    (rule_name, failure_mode, now, now),
                )
                # Step 2: increment occurrence_count and flip persistent when threshold met
                conn.execute(
                    "UPDATE coherence_fingerprint_log SET "
                    "  occurrence_count = occurrence_count + 1, "
                    "  last_seen_at     = ?, "
                    "  failure_mode     = ?, "
                    "  persistent       = CASE WHEN (occurrence_count + 1) >= ? "
                    "                    THEN 1 ELSE persistent END "
                    "WHERE rule_name = ?",
                    (now, failure_mode, N_PROMOTE_THRESHOLD, rule_name),
                )
        except Exception:
            pass

    def get_coherence_fingerprint_status(self) -> dict:
        """Return summary of coherence_fingerprint_log for GET /agent/coherence-fingerprint-status.

        Returns: total_rules, persistent_count, total_occurrences, top_rules (list),
                 maturity_penalty (0.0–1.0), timestamp.
        """
        try:
            import sqlite3 as _sq194
            with _sq194.connect(self._db_path) as conn:
                conn.row_factory = _sq194.Row
                total_row = conn.execute(
                    "SELECT COUNT(*) as n FROM coherence_fingerprint_log"
                ).fetchone()
                total_rules = int(total_row["n"]) if total_row else 0

                pers_row = conn.execute(
                    "SELECT COUNT(*) as n FROM coherence_fingerprint_log WHERE persistent=1"
                ).fetchone()
                persistent_count = int(pers_row["n"]) if pers_row else 0

                occ_row = conn.execute(
                    "SELECT SUM(occurrence_count) as s FROM coherence_fingerprint_log"
                ).fetchone()
                total_occurrences = int(occ_row["s"]) if (occ_row and occ_row["s"] is not None) else 0

                top_rows = conn.execute(
                    "SELECT rule_name, failure_mode, occurrence_count, persistent, "
                    "       first_seen_at, last_seen_at "
                    "FROM coherence_fingerprint_log "
                    "ORDER BY occurrence_count DESC LIMIT 5"
                ).fetchall()
                top_rules = [dict(r) for r in top_rows]

            maturity_penalty = round(min(1.0, persistent_count * 0.10), 4)
            return {
                "total_rules":       total_rules,
                "persistent_count":  persistent_count,
                "total_occurrences": total_occurrences,
                "maturity_penalty":  maturity_penalty,
                "top_rules":         top_rules,
            }
        except Exception:
            return {
                "total_rules":       0,
                "persistent_count":  0,
                "total_occurrences": 0,
                "maturity_penalty":  0.0,
                "top_rules":         [],
            }

    def get_persistent_contradictions(self) -> list:
        """Return all rules with persistent=1 (occurrence_count >= N_PROMOTE_THRESHOLD).

        Used by ProtocolMaturityScoringAgent._threat_forecast_accuracy_component()
        to apply the persistent contradiction penalty.
        """
        try:
            import sqlite3 as _sq194b
            with _sq194b.connect(self._db_path) as conn:
                conn.row_factory = _sq194b.Row
                rows = conn.execute(
                    "SELECT rule_name, failure_mode, occurrence_count, last_seen_at "
                    "FROM coherence_fingerprint_log WHERE persistent=1 "
                    "ORDER BY occurrence_count DESC"
                ).fetchall()
                return [dict(r) for r in rows]
        except Exception:
            return []

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
                    pass

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

    def insert_tremor_convergence_log(
        self,
        session_type: str,
        ratio: float,
        velocity: float,
        n_sessions: int,
        convergence_stable: bool,
        consecutive_positive: int,
        sessions_to_target_est: int = 0,
    ) -> int:
        """Insert a tremor convergence velocity snapshot (Phase 202).

        Called after each tremor_resting defensibility update.
        velocity = (ratio_curr - ratio_prev) / N_delta.
        convergence_stable=True when velocity >= 0 for 2 consecutive sessions.
        sessions_to_target_est: linear extrapolation of sessions needed to reach ratio=1.0.
        """
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO tremor_convergence_log "
                "(session_type, ratio, velocity, n_sessions, convergence_stable, "
                " consecutive_positive, sessions_to_target_est, created_at)"
                " VALUES (?,?,?,?,?,?,?,?)",
                (
                    session_type,
                    float(ratio),
                    float(velocity),
                    int(n_sessions),
                    1 if convergence_stable else 0,
                    int(consecutive_positive),
                    int(sessions_to_target_est),
                    time.time(),
                ),
            )
        return cur.lastrowid  # type: ignore[return-value]

    # Non-convergence threshold: 5 consecutive negative velocities → non-convergence declared.
    _N_NONCONV_THRESHOLD: int = 5

    def get_tremor_convergence_status(
        self, session_type: str = "tremor_resting"
    ) -> "dict | None":
        """Return the latest tremor convergence status for a session type (Phase 202).

        Phase 206 addition: also computes non_convergence_detected and
        consecutive_negative from the last _N_NONCONV_THRESHOLD rows.
        non_convergence_detected=True when _N_NONCONV_THRESHOLD consecutive readings
        all have velocity < 0 — P3 genuine non-stationarity diagnosis gate.
        """
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM tremor_convergence_log "
                "WHERE session_type=? ORDER BY id DESC LIMIT 1",
                (session_type,),
            ).fetchone()
            # Compute consecutive_negative from recent history (Phase 206)
            recent_rows = conn.execute(
                "SELECT velocity FROM tremor_convergence_log "
                "WHERE session_type=? ORDER BY id DESC LIMIT ?",
                (session_type, self._N_NONCONV_THRESHOLD),
            ).fetchall()
        if row is None:
            return None
        result = dict(row)
        # Count how many leading (most-recent) rows have velocity < 0
        _consec_neg = 0
        for _rrow in recent_rows:
            if float(_rrow[0]) < 0.0:
                _consec_neg += 1
            else:
                break
        result["consecutive_negative"] = _consec_neg
        result["non_convergence_detected"] = (
            len(recent_rows) >= self._N_NONCONV_THRESHOLD
            and _consec_neg >= self._N_NONCONV_THRESHOLD
        )
        return result

    def get_tremor_convergence_history(
        self, session_type: str = "tremor_resting", limit: int = 10
    ) -> "list[dict]":
        """Return recent tremor convergence snapshots, newest first (Phase 202)."""
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM tremor_convergence_log "
                "WHERE session_type=? ORDER BY id DESC LIMIT ?",
                (session_type, limit),
            ).fetchall()
        return [dict(r) for r in rows]

    # --- Phase 203: AgentContextRegistry ---

    def upsert_agent_context_hash(
        self,
        agent_id: str,
        prompt_sha256: str,
        phase_number: int,
    ) -> int:
        """Insert or ignore an agent context hash record (Phase 203).

        UNIQUE(agent_id, prompt_sha256) — same hash for same agent is a no-op.
        Returns the row id of the inserted or existing record.
        """
        with self._conn() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO agent_context_log "
                "(agent_id, prompt_sha256, phase_number, created_at)"
                " VALUES (?,?,?,?)",
                (agent_id, prompt_sha256, int(phase_number), time.time()),
            )
            row = conn.execute(
                "SELECT id FROM agent_context_log "
                "WHERE agent_id=? AND prompt_sha256=? LIMIT 1",
                (agent_id, prompt_sha256),
            ).fetchone()
        return int(row["id"]) if row else 0

    def get_agent_context_status(
        self, agent_id: str
    ) -> "dict | None":
        """Return the latest agent context hash record for an agent (Phase 203)."""
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM agent_context_log "
                "WHERE agent_id=? ORDER BY id DESC LIMIT 1",
                (agent_id,),
            ).fetchone()
        if row is None:
            return None
        return dict(row)

    def get_all_agent_context_status(self) -> "list[dict]":
        """Return the latest context hash record for all agents (Phase 203)."""
        with self._conn() as conn:
            rows = conn.execute(
                """
                SELECT a.* FROM agent_context_log a
                INNER JOIN (
                    SELECT agent_id, MAX(id) as max_id
                    FROM agent_context_log GROUP BY agent_id
                ) b ON a.agent_id = b.agent_id AND a.id = b.max_id
                ORDER BY a.agent_id
                """
            ).fetchall()
        return [dict(r) for r in rows]

    # --- Phase 207: StagedDryRunGraduationGate ---

    def insert_graduation_stage(
        self,
        agent_id: str,
        stage_number: int,
        notes: str = "",
    ) -> int:
        """Insert a new graduation stage record for an agent (Phase 207).

        Called when an operator activates dry_run=False for a specific agent.
        stage_number indicates sequential graduation order (1 = first agent).
        Returns the row id of the inserted record.
        """
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO dry_run_graduation_log "
                "(agent_id, stage_number, activated_at, dry_run_disabled_at, "
                " n_clean_sessions, n_false_positives, notes, created_at)"
                " VALUES (?,?,?,?,?,?,?,?)",
                (
                    agent_id,
                    int(stage_number),
                    time.time(),
                    time.time(),
                    0,
                    0,
                    notes,
                    time.time(),
                ),
            )
        return cur.lastrowid  # type: ignore[return-value]

    def record_graduation_clean_session(self, agent_id: str) -> bool:
        """Increment n_clean_sessions for the active graduation stage (Phase 207).

        Called when an adjudication completes without triggering a false positive.
        Returns True if a live graduation stage was found and updated, False otherwise.
        """
        with self._conn() as conn:
            row = conn.execute(
                "SELECT id FROM dry_run_graduation_log "
                "WHERE agent_id=? AND rollback_triggered=0 ORDER BY id DESC LIMIT 1",
                (agent_id,),
            ).fetchone()
            if row is None:
                return False
            conn.execute(
                "UPDATE dry_run_graduation_log SET n_clean_sessions=n_clean_sessions+1 "
                "WHERE id=?",
                (row["id"],),
            )
        return True

    def record_graduation_false_positive(
        self, agent_id: str, fp_threshold: int = 2
    ) -> bool:
        """Increment n_false_positives and auto-trigger rollback if threshold exceeded (Phase 207).

        Returns True when rollback was auto-triggered (n_false_positives >= fp_threshold),
        False when false positive was recorded but threshold not yet reached.
        """
        with self._conn() as conn:
            row = conn.execute(
                "SELECT id, n_false_positives FROM dry_run_graduation_log "
                "WHERE agent_id=? AND rollback_triggered=0 ORDER BY id DESC LIMIT 1",
                (agent_id,),
            ).fetchone()
            if row is None:
                return False
            new_fp = int(row["n_false_positives"]) + 1
            if new_fp >= fp_threshold:
                conn.execute(
                    "UPDATE dry_run_graduation_log "
                    "SET n_false_positives=?, rollback_triggered=1, "
                    "    rollback_triggered_at=?, rollback_reason=? "
                    "WHERE id=?",
                    (new_fp, time.time(), f"auto: {new_fp}>={fp_threshold} false positives", row["id"]),
                )
                return True
            conn.execute(
                "UPDATE dry_run_graduation_log SET n_false_positives=? WHERE id=?",
                (new_fp, row["id"]),
            )
        return False

    def trigger_graduation_rollback(self, agent_id: str, reason: str) -> bool:
        """Manually trigger rollback for an agent's active graduation stage (Phase 207).

        Returns True if an active stage was found and rolled back, False otherwise.
        """
        with self._conn() as conn:
            row = conn.execute(
                "SELECT id FROM dry_run_graduation_log "
                "WHERE agent_id=? AND rollback_triggered=0 ORDER BY id DESC LIMIT 1",
                (agent_id,),
            ).fetchone()
            if row is None:
                return False
            conn.execute(
                "UPDATE dry_run_graduation_log "
                "SET rollback_triggered=1, rollback_triggered_at=?, rollback_reason=? "
                "WHERE id=?",
                (time.time(), reason, row["id"]),
            )
        return True

    def get_graduation_stage_status(self, agent_id: str) -> "dict | None":
        """Return the latest graduation stage for an agent (Phase 207)."""
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM dry_run_graduation_log "
                "WHERE agent_id=? ORDER BY id DESC LIMIT 1",
                (agent_id,),
            ).fetchone()
        return dict(row) if row else None

    def get_all_graduation_stages(self) -> "list[dict]":
        """Return all graduation stages, ordered by stage_number then creation (Phase 207)."""
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM dry_run_graduation_log "
                "ORDER BY stage_number ASC, id ASC"
            ).fetchall()
        return [dict(r) for r in rows]

    # --- Phase 214: GraduationAutowatchBridge ---

    def insert_graduation_autowatch_log(
        self,
        probe_type: str,
        ratio: float,
        all_pairs_above_1: bool,
        trigger_fired: bool,
        preconditions_evaluated: bool = False,
        preconditions_met: "bool | None" = None,
        blockers_json: str = "[]",
    ) -> int:
        """Insert a graduation autowatch event (Phase 214 — WIF-041 mitigation).

        Called by SeparationRatioMonitorAgent when all_pairs_p0_ok transitions False→True
        (trigger_fired=True) and by StagedDryRunGraduationAgent after evaluating
        preconditions (preconditions_evaluated=True).
        """
        import time as _t214
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO graduation_autowatch_log "
                "(probe_type, ratio, all_pairs_above_1, trigger_fired, "
                " preconditions_evaluated, preconditions_met, blockers_json, created_at) "
                "VALUES (?,?,?,?,?,?,?,?)",
                (
                    probe_type,
                    float(ratio),
                    int(bool(all_pairs_above_1)),
                    int(bool(trigger_fired)),
                    int(bool(preconditions_evaluated)),
                    int(bool(preconditions_met)) if preconditions_met is not None else None,
                    blockers_json,
                    _t214.time(),
                ),
            )
            return int(cur.lastrowid)

    def get_graduation_autowatch_status(
        self, probe_type: str | None = None, limit: int = 10
    ) -> "dict":
        """Return graduation autowatch summary: latest trigger + precondition results (Phase 214)."""
        import json as _json214
        import time as _t214

        with self._conn() as conn:
            if probe_type:
                rows = conn.execute(
                    "SELECT * FROM graduation_autowatch_log "
                    "WHERE probe_type=? ORDER BY id DESC LIMIT ?",
                    (probe_type, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM graduation_autowatch_log "
                    "ORDER BY id DESC LIMIT ?",
                    (limit,),
                ).fetchall()

        entries = [dict(r) for r in rows]
        trigger_count   = sum(1 for e in entries if e.get("trigger_fired"))
        evaluated_count = sum(1 for e in entries if e.get("preconditions_evaluated"))
        last_trigger    = next((e for e in entries if e.get("trigger_fired")), None)
        last_evaluated  = next((e for e in entries if e.get("preconditions_evaluated")), None)

        return {
            "total_entries":            len(entries),
            "trigger_count":            trigger_count,
            "evaluated_count":          evaluated_count,
            "last_trigger_ratio":       last_trigger["ratio"] if last_trigger else None,
            "last_trigger_probe_type":  last_trigger["probe_type"] if last_trigger else None,
            "last_preconditions_met":   bool(last_evaluated["preconditions_met"]) if last_evaluated and last_evaluated.get("preconditions_met") is not None else None,
            "last_blockers":            _json214.loads(last_evaluated["blockers_json"]) if last_evaluated else [],
            "entries":                  entries,
            "timestamp":                _t214.time(),
        }

    # --- Phase 229: AIT Separation Log ---

    def insert_ait_session(
        self,
        n_sessions:          int,
        n_per_player:        dict,
        separation_ratio:    float,
        all_pairs_above_1:   bool,
        inter_player_mean:   float,
        intra_player_mean:   float,
        loo_accuracy:        float,
        cov_mode:            str  = "",
        pair_distances:      dict = None,
        analysis_date:       str  = "",
        per_player_features: dict = None,
        centroids:           dict = None,
        cov_inv:             list = None,
    ) -> int:
        """Insert AIT separation analysis result (Phase 229).

        Phase 230: also mirrors into separation_defensibility_log with session_type='ait'
        so tournament_preflight all_pairs_p0_ok reads AIT data instead of being locked to
        touchpad_corners history.  guard_enabled=False (regression guard off by default).

        Phase 237-ZK-SEPPROOF: optional `centroids` (player_id -> [feat0, feat1, ...]) +
        `cov_inv` (FxF inverse covariance matrix) persist the geometric inputs needed
        for ZK witness reconstruction.  Both default to empty for backward compat with
        callers that don't yet supply them.

        Called by analyze_interperson_separation.py --session-type ait --write-snapshot
        and by POST /agent/run-ait-analysis bridge endpoint.
        """
        import json  as _j229
        import time  as _t229
        _pair_dist_229  = pair_distances or {}
        _ppf_229        = per_player_features or {}
        _centroids_229  = centroids or {}
        _cov_inv_229    = cov_inv or []
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO ait_session_log "
                "(probe_type, n_sessions, n_per_player_json, separation_ratio, "
                " all_pairs_above_1, inter_player_mean, intra_player_mean, "
                " loo_accuracy, cov_mode, pair_distances_json, analysis_date, "
                " per_player_features_json, centroids_json, cov_inv_json, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    "ait",
                    int(n_sessions),
                    _j229.dumps(n_per_player),
                    float(separation_ratio),
                    int(bool(all_pairs_above_1)),
                    float(inter_player_mean),
                    float(intra_player_mean),
                    float(loo_accuracy),
                    str(cov_mode),
                    _j229.dumps(_pair_dist_229),
                    str(analysis_date),
                    _j229.dumps(_ppf_229),
                    _j229.dumps(_centroids_229),
                    _j229.dumps(_cov_inv_229),
                    _t229.time(),
                ),
            )
            row_id = int(cur.lastrowid)

        # Phase 230: mirror into separation_defensibility_log so all_pairs_p0_ok
        # tournament_preflight gate reads AIT results instead of touchpad_corners.
        _min_n230 = 10
        _n_vals230 = list(n_per_player.values()) if n_per_player else []
        _defensible230 = (
            all_pairs_above_1
            and bool(_n_vals230)
            and all(v >= _min_n230 for v in _n_vals230)
        )
        self.insert_separation_defensibility_log_guarded(
            session_type      = "ait",
            n_sessions_total  = n_sessions,
            n_per_player      = n_per_player,
            min_n_per_player  = _min_n230,
            defensible        = _defensible230,
            ratio             = separation_ratio,
            all_pairs_above_1 = all_pairs_above_1,
            guard_enabled     = False,
        )
        return row_id

    def get_ait_separation_status(self) -> dict:
        """Return AIT separation analysis summary (Phase 229).

        Returns dict with keys:
            ait_separation_enabled: bool (always True when table has rows)
            n_sessions: int
            separation_ratio: float
            all_pairs_above_1: bool
            inter_player_mean: float
            intra_player_mean: float
            loo_accuracy: float
            pair_distances: dict
            analysis_date: str
            last_run_ts: float | None
            timestamp: float
        """
        import json as _j229s
        import time as _t229s
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM ait_session_log ORDER BY id DESC LIMIT 1"
            ).fetchone()

        _now = _t229s.time()
        if row is None:
            return {
                "ait_separation_enabled": False,
                "n_sessions":             0,
                "separation_ratio":       0.0,
                "all_pairs_above_1":      False,
                "inter_player_mean":      0.0,
                "intra_player_mean":      0.0,
                "loo_accuracy":           0.0,
                "pair_distances":         {},
                "analysis_date":          "",
                "last_run_ts":            None,
                "timestamp":              _now,
            }

        import math as _math229s
        d = dict(row)
        try:
            pd = _j229s.loads(d.get("pair_distances_json") or "{}")
        except Exception:
            pd = {}
        try:
            npp = _j229s.loads(d.get("n_per_player_json") or "{}")
        except Exception:
            npp = {}
        try:
            ppf = _j229s.loads(d.get("per_player_features_json") or "{}")
        except Exception:
            ppf = {}

        # Derive per-player biometric means for live radar visualisation.
        # Existing rows without per_player_features_json return empty dicts.
        _tremor_hz:  dict = {}
        _roll_deg:   dict = {}
        _pitch_deg:  dict = {}
        for _p, _feats in ppf.items():
            if not isinstance(_feats, dict):
                continue
            _hz = _feats.get("accel_tremor_peak_hz")
            if _hz is not None:
                _tremor_hz[_p] = float(_hz)
            _rs = _feats.get("roll_sin")
            _rc = _feats.get("roll_cos")
            if _rs is not None and _rc is not None:
                _roll_deg[_p] = round(_math229s.degrees(_math229s.atan2(float(_rs), float(_rc))), 2)
            _pc = _feats.get("pitch_cos")
            if _pc is not None:
                _pitch_deg[_p] = round(_math229s.degrees(_math229s.acos(max(-1.0, min(1.0, float(_pc))))), 2)

        return {
            "ait_separation_enabled":   True,
            "n_sessions":               int(d.get("n_sessions", 0)),
            "n_per_player":             npp,
            "separation_ratio":         float(d.get("separation_ratio", 0.0)),
            "all_pairs_above_1":        bool(d.get("all_pairs_above_1", 0)),
            "inter_player_mean":        float(d.get("inter_player_mean", 0.0)),
            "intra_player_mean":        float(d.get("intra_player_mean", 0.0)),
            "loo_accuracy":             float(d.get("loo_accuracy", 0.0)),
            "pair_distances":           pd,
            "analysis_date":            str(d.get("analysis_date") or ""),
            "last_run_ts":              float(d.get("created_at", 0.0)),
            "per_player_tremor_hz":     _tremor_hz,
            "per_player_roll_angle_deg": _roll_deg,
            "per_player_pitch_angle_deg": _pitch_deg,
            "timestamp":                _now,
        }

    # -----------------------------------------------------------------------
    # Phase 234.7 — Physical Capture Continuity (PCC)
    # -----------------------------------------------------------------------

    def insert_capture_health_event(
        self,
        capture_state: str,
        host_state: str,
        poll_rate_hz: float,
        transition_reason: str = "",
        grind_mode: bool = False,
        session_id: str = "",
        prev_session_id: str = "",
        gap_duration_ms: float = 0.0,
    ) -> int:
        """Log a PCC state transition or periodic health snapshot."""
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO capture_health_log "
                "(capture_state, host_state, poll_rate_hz, transition_reason, "
                " grind_mode, session_id, prev_session_id, gap_duration_ms, created_at) "
                "VALUES (?,?,?,?,?,?,?,?,?)",
                (capture_state, host_state, float(poll_rate_hz), transition_reason,
                 int(grind_mode), session_id, prev_session_id,
                 float(gap_duration_ms), time.time()),
            )
            return cur.lastrowid or 0

    def get_capture_health_status(self, limit: int = 10) -> dict:
        """Return latest capture health event + recent history."""
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM capture_health_log ORDER BY created_at DESC LIMIT 1"
            ).fetchone()
            n_total = conn.execute(
                "SELECT COUNT(*) FROM capture_health_log"
            ).fetchone()[0]
            history = conn.execute(
                "SELECT capture_state, host_state, poll_rate_hz, transition_reason, created_at "
                "FROM capture_health_log ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()

        if row is None:
            return {
                "capture_state":    "DISCONNECTED",
                "host_state":       "UNKNOWN",
                "poll_rate_hz":     0.0,
                "grind_mode":       False,
                "n_events":         0,
                "history":          [],
                "timestamp":        time.time(),
            }
        d = dict(row)
        return {
            "capture_state":    d.get("capture_state", "DISCONNECTED"),
            "host_state":       d.get("host_state", "UNKNOWN"),
            "poll_rate_hz":     float(d.get("poll_rate_hz", 0.0)),
            "grind_mode":       bool(d.get("grind_mode", 0)),
            "last_event_ts":    float(d.get("created_at", 0.0)),
            "n_events":         int(n_total),
            "history":          [dict(r) for r in history],
            "timestamp":        time.time(),
        }

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

    def get_operator_agent_activation_log(
        self,
        agent_id: str | None = None,
        limit: int = 20,
    ) -> list[dict]:
        """Return paginated activation history (most recent first).

        If agent_id is None, returns rows for all agents.  Otherwise filters
        to the specific Q9-frozen agentId.  Caps at 200 rows regardless of
        requested limit to prevent unbounded queries.
        """
        limit = max(1, min(200, int(limit)))
        with self._conn() as conn:
            if agent_id is None:
                rows = conn.execute(
                    "SELECT * FROM operator_agent_activation_log "
                    "ORDER BY activated_at DESC LIMIT ?",
                    (limit,),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM operator_agent_activation_log "
                    "WHERE agent_id = ? ORDER BY activated_at DESC LIMIT ?",
                    (agent_id, limit),
                ).fetchall()
            return [dict(r) for r in rows]

    def get_current_operational_phase(self, agent_id: str) -> str:
        """Return latest to_phase for the agent, or 'O0_DORMANT' if no activations.

        This is the off-chain mirror of the agent's on-chain operational state.
        FSCA SCOPE_HASH_GOVERNANCE_DRIFT (Phase O1 C2/C3 deferred) cross-checks
        this against AgentScope.getScopeRoot to detect divergence.
        """
        with self._conn() as conn:
            row_get_to_phase = conn.execute(
                "SELECT to_phase FROM operator_agent_activation_log "
                "WHERE agent_id = ? ORDER BY activated_at DESC LIMIT 1",
                (agent_id,),
            ).fetchone()
            if row_get_to_phase is None:
                return "O0_DORMANT"
            return str(row_get_to_phase["to_phase"])

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

    def get_operator_agent_shadow_log(
        self,
        agent_id: str | None = None,
        decision_filter: str | None = None,
        limit: int = 50,
    ) -> list[dict]:
        """Paginated shadow log read (most recent first).

        Args:
            agent_id: filter to one agent or None for all
            decision_filter: filter to one CedarDecision value or None for all
            limit: capped at 500 to prevent unbounded queries
        """
        limit = max(1, min(500, int(limit)))
        with self._conn() as conn:
            sql = "SELECT * FROM operator_agent_shadow_log WHERE 1=1"
            args: list = []
            if agent_id is not None:
                sql += " AND agent_id = ?"
                args.append(agent_id)
            if decision_filter is not None:
                sql += " AND decision = ?"
                args.append(decision_filter)
            sql += " ORDER BY evaluated_at DESC LIMIT ?"
            args.append(limit)
            rows = conn.execute(sql, tuple(args)).fetchall()
            return [dict(r) for r in rows]

    def get_operator_agent_shadow_summary(
        self,
        agent_id: str | None = None,
    ) -> dict:
        """Aggregated decision counts for an agent (or fleet-wide).

        Returns:
            {
                "total": int,
                "by_decision": {decision: count, ...},
                "latest_at": float | None,
                "earliest_at": float | None,
            }
        """
        with self._conn() as conn:
            base_where = "WHERE agent_id = ?" if agent_id else ""
            base_args = (agent_id,) if agent_id else ()
            total = conn.execute(
                f"SELECT COUNT(*) FROM operator_agent_shadow_log {base_where}",
                base_args,
            ).fetchone()[0]
            by_dec_rows = conn.execute(
                f"SELECT decision, COUNT(*) as n FROM operator_agent_shadow_log "
                f"{base_where} GROUP BY decision",
                base_args,
            ).fetchall()
            by_decision = {r["decision"]: int(r["n"]) for r in by_dec_rows}
            ts_row = conn.execute(
                f"SELECT MIN(evaluated_at) as earliest, MAX(evaluated_at) as latest "
                f"FROM operator_agent_shadow_log {base_where}",
                base_args,
            ).fetchone()
            return {
                "total":       int(total),
                "by_decision": by_decision,
                "latest_at":   ts_row["latest"] if ts_row else None,
                "earliest_at": ts_row["earliest"] if ts_row else None,
            }

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

    def get_operator_agent_drift_log(
        self,
        agent_id: str | None = None,
        drift_type: str | None = None,
        limit: int = 50,
    ) -> list[dict]:
        """Paginated drift log read (most recent first)."""
        limit = max(1, min(500, int(limit)))
        with self._conn() as conn:
            sql = "SELECT * FROM operator_agent_drift_log WHERE 1=1"
            args: list = []
            if agent_id is not None:
                sql += " AND agent_id = ?"
                args.append(agent_id)
            if drift_type is not None:
                sql += " AND drift_type = ?"
                args.append(drift_type)
            sql += " ORDER BY detected_at DESC LIMIT ?"
            args.append(limit)
            return [dict(r) for r in conn.execute(sql, tuple(args)).fetchall()]

    # --- Phase O4-VPM-INT follow-up: CFSS lane drift helpers ---
    #
    # Findings from cfss_drift_sweeper.py (continuous Cedar policy
    # CFSS lane authority detection). Each row = one matrix-row
    # CFSS_VIOLATION. Consumed by the 27th FSCA contradiction rule
    # CFSS_LANE_AUTHORITY_DRIFT (CRITICAL severity).

    def insert_cfss_lane_drift(
        self,
        *,
        sweep_id: str,
        agent_id: str,
        action: str,
        resource: str | None,
        expected_effect: str,
        actual_effect: str,
        bundle_path: str = "",
        evidence_json: str = "",
    ) -> int:
        """Persist one CFSS lane-authority drift finding. Never raises."""
        try:
            now = time.time()
            with self._conn() as conn:
                cur = conn.execute(
                    "INSERT INTO cfss_lane_drift_log "
                    "(sweep_id, agent_id, action, resource, "
                    "expected_effect, actual_effect, bundle_path, "
                    "evidence_json, created_at) "
                    "VALUES (?,?,?,?,?,?,?,?,?)",
                    (
                        sweep_id, agent_id, action, resource,
                        expected_effect, actual_effect,
                        bundle_path, evidence_json, now,
                    ),
                )
                return int(cur.lastrowid) if cur.lastrowid else 0
        except Exception:
            return 0

    def get_cfss_lane_drift_recent(
        self,
        since_seconds: int = 3600,
        limit: int = 50,
    ) -> list[dict]:
        """Return CFSS drift findings within the trailing window."""
        try:
            since = time.time() - max(1, int(since_seconds))
            limit = max(1, min(500, int(limit)))
            with self._conn() as conn:
                return [
                    dict(r) for r in conn.execute(
                        "SELECT * FROM cfss_lane_drift_log "
                        "WHERE created_at >= ? "
                        "ORDER BY created_at DESC LIMIT ?",
                        (since, limit),
                    ).fetchall()
                ]
        except Exception:
            return []

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

    def get_latest_operator_agent_activation(self, agent_id: str) -> dict | None:
        """Return the most-recent activation_log row for one agent, with
        watcher-compatible field shape (bundle_filename + anchored_at_unix).

        Returns None when no activation exists.  Never raises."""
        try:
            with self._conn() as conn:
                row = conn.execute(
                    "SELECT * FROM operator_agent_activation_log "
                    "WHERE agent_id = ? "
                    "ORDER BY activated_at DESC LIMIT 1",
                    (agent_id,),
                ).fetchone()
            if row is None:
                return None
            d = dict(row)
            bundle_path = str(d.get("bundle_path", "") or "")
            d["bundle_filename"] = bundle_path.replace("\\", "/").rsplit("/", 1)[-1] if bundle_path else ""
            d["anchored_at_unix"] = float(d.get("activated_at", 0.0) or 0.0)
            return d
        except Exception:
            return None

    def get_first_operator_agent_activation(self, agent_id: str) -> dict | None:
        """Return the EARLIEST activation_log row for one agent (= when
        shadow observation began).  Same field shape as
        get_latest_operator_agent_activation.  Never raises."""
        try:
            with self._conn() as conn:
                row = conn.execute(
                    "SELECT * FROM operator_agent_activation_log "
                    "WHERE agent_id = ? "
                    "ORDER BY activated_at ASC LIMIT 1",
                    (agent_id,),
                ).fetchone()
            if row is None:
                return None
            d = dict(row)
            bundle_path = str(d.get("bundle_path", "") or "")
            d["bundle_filename"] = bundle_path.replace("\\", "/").rsplit("/", 1)[-1] if bundle_path else ""
            d["anchored_at_unix"] = float(d.get("activated_at", 0.0) or 0.0)
            return d
        except Exception:
            return None

    def count_cedar_shadow_evaluations(self, agent_id: str) -> int:
        """Count rows in operator_agent_shadow_log for an agent.  Used by
        Phase O2 SUGGEST gate (PHASE_O2_EVAL_MIN_COUNT=100).  Returns 0
        on any failure (fail-open per INV-INITIATIVE-ADVANCEMENT-002)."""
        try:
            with self._conn() as conn:
                row = conn.execute(
                    "SELECT COUNT(*) AS n FROM operator_agent_shadow_log "
                    "WHERE agent_id = ?",
                    (agent_id,),
                ).fetchone()
            return int(row["n"]) if row else 0
        except Exception:
            return 0

    def count_operator_agent_drift_findings(
        self,
        *,
        agent_id: str,
        drift_type: str,
        since_seconds: int,
    ) -> int:
        """Count drift findings of a given type for an agent within the
        last N seconds.  Used by Phase O2 SUGGEST gate to enforce
        bundle/scope drift = 0 over the trailing 30-day window.  Returns 0
        on any failure (fail-open)."""
        try:
            cutoff = time.time() - max(0, int(since_seconds))
            with self._conn() as conn:
                row = conn.execute(
                    "SELECT COUNT(*) AS n FROM operator_agent_drift_log "
                    "WHERE agent_id = ? AND drift_type = ? AND detected_at >= ?",
                    (agent_id, drift_type, cutoff),
                ).fetchone()
            return int(row["n"]) if row else 0
        except Exception:
            return 0

    # ------------------------------------------------------------------
    # Phase O2-DRAFT-GENERATION (2026-05-10) — operator_agent_drafts helpers
    # ------------------------------------------------------------------
    def insert_operator_agent_draft(
        self,
        *,
        agent_id: str,
        action_category: str,   # 'skill' | 'tool'
        action_name: str,        # e.g. 'kms-sign' or 'provenance-recording'
        draft_uri: str,          # full draft://... URI
        payload_hash: str,       # SHA-256 of payload body, lowercase hex
        payload_bytes: int,
        kms_sig_present: bool = False,
    ) -> int:
        """Persist one draft payload produced by an Operator agent under
        O2 SUGGEST authority. Returns new row id; 0 on UNIQUE collision
        (same agent_id+payload_hash already persisted -- idempotent)."""
        try:
            with self._conn() as conn:
                cur = conn.execute(
                    "INSERT OR IGNORE INTO operator_agent_drafts "
                    "(agent_id, action_category, action_name, draft_uri, "
                    " payload_hash, payload_bytes, kms_sig_present, created_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        str(agent_id),
                        str(action_category),
                        str(action_name),
                        str(draft_uri),
                        str(payload_hash),
                        int(payload_bytes),
                        1 if kms_sig_present else 0,
                        time.time(),
                    ),
                )
                if cur.lastrowid:
                    return int(cur.lastrowid)
                # UNIQUE collision -- return existing row id
                row = conn.execute(
                    "SELECT id FROM operator_agent_drafts "
                    "WHERE agent_id = ? AND payload_hash = ?",
                    (str(agent_id), str(payload_hash)),
                ).fetchone()
                return int(row["id"]) if row else 0
        except Exception:
            return 0

    def count_operator_agent_drafts(
        self,
        *,
        agent_id: str,
        since_seconds: int,
    ) -> int:
        """Count drafts produced by an agent within the last N seconds.
        Used by Phase O3-ACT-WATCHER PHASE_O3_DRAFT_PAYLOAD_MIN gate
        (default 50 drafts in a 30-day window). Returns 0 on any failure
        (fail-open per INV-INITIATIVE-ADVANCEMENT-002)."""
        try:
            cutoff = time.time() - max(0, int(since_seconds))
            with self._conn() as conn:
                row = conn.execute(
                    "SELECT COUNT(*) AS n FROM operator_agent_drafts "
                    "WHERE agent_id = ? AND created_at >= ?",
                    (str(agent_id), cutoff),
                ).fetchone()
            return int(row["n"]) if row else 0
        except Exception:
            return 0

    def record_operator_decision(
        self,
        *,
        draft_id: int,
        decision: str,           # 'accept' | 'reject' | 'overturn_curator'
        reason: str | None = None,
    ) -> bool:
        """Operator review of a draft -- updates operator_decision +
        operator_decision_at + (optional) operator_disagreement_reason.
        Idempotent: re-recording the same decision is a no-op; recording
        a different decision overwrites (operator may revise their own
        review). Returns True on success, False on missing draft."""
        if decision not in ("accept", "reject", "overturn_curator"):
            return False
        try:
            with self._conn() as conn:
                cur = conn.execute(
                    "UPDATE operator_agent_drafts "
                    "SET operator_decision = ?, "
                    "    operator_decision_at = ?, "
                    "    operator_disagreement_reason = ? "
                    "WHERE id = ?",
                    (
                        str(decision),
                        time.time(),
                        str(reason) if reason else None,
                        int(draft_id),
                    ),
                )
                return int(cur.rowcount) > 0
        except Exception:
            return False

    def compute_operator_agent_disagreement_rate(
        self,
        *,
        agent_id: str,
        since_seconds: int,
    ) -> float:
        """Fraction of REVIEWED drafts where operator rejected.
        denominator = drafts with operator_decision IN ('accept', 'reject')
                      created within window
        numerator   = drafts with operator_decision = 'reject'
                      created within window

        Excludes 'overturn_curator' (Curator-specific; tracked separately
        by compute_operator_agent_false_positive_rate). Excludes drafts
        with NULL operator_decision (unreviewed -- not part of disagreement
        signal).

        Returns 0.0 on:
          - any DB failure
          - zero reviewed drafts in window (no signal yet)

        Used by Phase O3-ACT-WATCHER PHASE_O3_DISAGREEMENT_RATE_MAX gate
        (default 0.05 = 5%). Fail-open."""
        try:
            cutoff = time.time() - max(0, int(since_seconds))
            with self._conn() as conn:
                row = conn.execute(
                    "SELECT "
                    "  SUM(CASE WHEN operator_decision = 'reject' THEN 1 ELSE 0 END) AS n_reject, "
                    "  SUM(CASE WHEN operator_decision IN ('accept','reject') THEN 1 ELSE 0 END) AS n_reviewed "
                    "FROM operator_agent_drafts "
                    "WHERE agent_id = ? AND created_at >= ?",
                    (str(agent_id), cutoff),
                ).fetchone()
            if not row:
                return 0.0
            n_reject = int(row["n_reject"] or 0)
            n_reviewed = int(row["n_reviewed"] or 0)
            if n_reviewed <= 0:
                return 0.0
            return float(n_reject) / float(n_reviewed)
        except Exception:
            return 0.0

    def compute_operator_agent_false_positive_rate(
        self,
        *,
        agent_id: str,
        since_seconds: int,
    ) -> float:
        """Fraction of REVIEWED drafts where operator overturned the agent's
        verdict. Curator-specific: marketplace-listing-review verdicts that
        the operator reverses post-review count as false positives.

        denominator = drafts with operator_decision IN ('accept','reject',
                      'overturn_curator') created within window
        numerator   = drafts with operator_decision = 'overturn_curator'
                      created within window

        Returns 0.0 on:
          - any DB failure
          - zero reviewed drafts in window (no signal yet)

        Used by Phase O3-ACT-WATCHER PHASE_O3_FALSE_POSITIVE_RATE_MAX gate
        (Curator-only; default 0.0 = zero tolerance). Fail-open."""
        try:
            cutoff = time.time() - max(0, int(since_seconds))
            with self._conn() as conn:
                row = conn.execute(
                    "SELECT "
                    "  SUM(CASE WHEN operator_decision = 'overturn_curator' THEN 1 ELSE 0 END) AS n_overturn, "
                    "  SUM(CASE WHEN operator_decision IN ('accept','reject','overturn_curator') THEN 1 ELSE 0 END) AS n_reviewed "
                    "FROM operator_agent_drafts "
                    "WHERE agent_id = ? AND created_at >= ?",
                    (str(agent_id), cutoff),
                ).fetchone()
            if not row:
                return 0.0
            n_overturn = int(row["n_overturn"] or 0)
            n_reviewed = int(row["n_reviewed"] or 0)
            if n_reviewed <= 0:
                return 0.0
            return float(n_overturn) / float(n_reviewed)
        except Exception:
            return 0.0

    def get_operator_agent_drafts(
        self,
        *,
        agent_id: str | None = None,
        decision: str | None = None,
        since_seconds: int | None = None,
        limit: int = 50,
    ) -> list[dict]:
        """Return drafts (most recent first), filtered by agent / decision /
        time window. Capped at 500 rows. Used by operator review surface
        (frontend dashboards) and by audit query tooling."""
        limit = max(1, min(500, int(limit)))
        try:
            sql = "SELECT * FROM operator_agent_drafts WHERE 1=1"
            args: list = []
            if agent_id is not None:
                sql += " AND agent_id = ?"
                args.append(str(agent_id))
            if decision is not None:
                sql += " AND operator_decision = ?"
                args.append(str(decision))
            if since_seconds is not None:
                cutoff = time.time() - max(0, int(since_seconds))
                sql += " AND created_at >= ?"
                args.append(cutoff)
            sql += " ORDER BY created_at DESC LIMIT ?"
            args.append(limit)
            with self._conn() as conn:
                rows = conn.execute(sql, tuple(args)).fetchall()
            return [dict(r) for r in rows]
        except Exception:
            return []

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

    def insert_mythos_cadence_run(
        self,
        *,
        variant: str,
        cadence: str,
        findings_count: int,
        duration_ms: int,
        triggered_by: str = "schedule",
        error: str | None = None,
    ) -> int:
        """Persist one cadence-engine wakeup record for a variant. Returns
        new row id; 0 on error. Fail-open."""
        try:
            with self._conn() as conn:
                cur = conn.execute(
                    "INSERT INTO mythos_cadence_log "
                    "(variant, cadence, findings_count, duration_ms, "
                    " triggered_by, error, created_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (
                        str(variant),
                        str(cadence),
                        int(findings_count),
                        int(duration_ms),
                        str(triggered_by),
                        error,
                        time.time(),
                    ),
                )
                return int(cur.lastrowid or 0)
        except Exception:
            return 0

    def get_mythos_findings(
        self,
        *,
        variant: str | None = None,
        severity: str | None = None,
        unresolved_only: bool = False,
        limit: int = 50,
    ) -> list[dict]:
        """Read Mythos findings with optional filters. Fail-open: returns
        [] on any DB error."""
        try:
            sql = "SELECT * FROM mythos_finding_log WHERE 1=1"
            args: list = []
            if variant:
                sql += " AND variant = ?"
                args.append(str(variant))
            if severity:
                sql += " AND severity = ?"
                args.append(str(severity).upper())
            if unresolved_only:
                sql += " AND resolved = 0"
            sql += " ORDER BY created_at DESC LIMIT ?"
            args.append(max(1, min(int(limit), 500)))
            with self._conn() as conn:
                rows = conn.execute(sql, tuple(args)).fetchall()
            return [dict(r) for r in rows]
        except Exception:
            return []

    def get_mythos_cadence_status(self) -> dict:
        """Summary of cadence-engine activity. Fail-open: returns
        {variants: {}, total_runs: 0, ...} on DB error."""
        try:
            with self._conn() as conn:
                rows = conn.execute(
                    "SELECT variant, COUNT(*) AS n_runs, "
                    "       SUM(findings_count) AS total_findings, "
                    "       MAX(created_at) AS last_run_ts "
                    "FROM mythos_cadence_log "
                    "GROUP BY variant"
                ).fetchall()
            variants: dict = {}
            total_runs = 0
            total_findings = 0
            for r in rows:
                d = dict(r)
                vname = d["variant"]
                variants[vname] = {
                    "n_runs": int(d["n_runs"] or 0),
                    "total_findings": int(d["total_findings"] or 0),
                    "last_run_ts": float(d["last_run_ts"] or 0.0),
                }
                total_runs += int(d["n_runs"] or 0)
                total_findings += int(d["total_findings"] or 0)
            return {
                "variants": variants,
                "total_runs": total_runs,
                "total_findings": total_findings,
                "timestamp": time.time(),
            }
        except Exception:
            return {"variants": {}, "total_runs": 0, "total_findings": 0, "timestamp": time.time()}

    def insert_operator_initiative_advancement_log(
        self,
        *,
        timestamp: float,
        fleet_phase_aligned: bool,
        fleet_at_o1_count: int,
        fleet_at_o2_ready_count: int,
        fleet_at_o3_ready_count: int,
        next_alignment_target: str,
        per_agent_json: str,
        frr_hex: str = "",
        frr_ts_ns: int = 0,
        error: str | None = None,
    ) -> int:
        """Persist one fleet-advancement evaluation cycle, including the
        FRR commitment.  Returns new row id; raises sqlite3.Error only
        on hard DB failures (caller handles)."""
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO operator_initiative_advancement_log "
                "(timestamp, fleet_phase_aligned, fleet_at_o1_count, "
                "fleet_at_o2_ready_count, fleet_at_o3_ready_count, "
                "next_alignment_target, per_agent_json, frr_hex, frr_ts_ns, "
                "error, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    float(timestamp),
                    1 if fleet_phase_aligned else 0,
                    int(fleet_at_o1_count),
                    int(fleet_at_o2_ready_count),
                    int(fleet_at_o3_ready_count),
                    str(next_alignment_target),
                    str(per_agent_json),
                    str(frr_hex or ""),
                    int(frr_ts_ns or 0),
                    str(error) if error else None,
                    time.time(),
                ),
            )
            return int(cur.lastrowid)

    def get_latest_operator_initiative_advancement(self) -> dict | None:
        """Return the most-recent advancement-log row, or None."""
        try:
            with self._conn() as conn:
                row = conn.execute(
                    "SELECT * FROM operator_initiative_advancement_log "
                    "ORDER BY timestamp DESC LIMIT 1",
                ).fetchone()
            return dict(row) if row else None
        except Exception:
            return None

    def get_operator_initiative_advancement_history(self, limit: int = 50) -> list[dict]:
        """Return advancement-log history (most recent first), capped at 500."""
        limit = max(1, min(500, int(limit)))
        try:
            with self._conn() as conn:
                rows = conn.execute(
                    "SELECT * FROM operator_initiative_advancement_log "
                    "ORDER BY timestamp DESC LIMIT ?",
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

    def update_grind_chain_hash(
        self, row_id: int, gic_hex: str, ts_ns: int, grind_session_id: str = ""
    ) -> None:
        """Stamp a completed GIC hash, timestamp, and session ID on a validation row.

        INV-GIC-001 fix: grind_session_id is now persisted so get_prev_grind_chain_hash
        can scope lookups to the correct session.
        """
        with self._conn() as conn:
            conn.execute(
                "UPDATE ruling_validation_log "
                "SET grind_chain_hash = ?, gic_ts_ns = ?, grind_session_id = ? "
                "WHERE id = ?",
                (gic_hex, ts_ns, grind_session_id or None, row_id),
            )

    def get_ruling_rows_for_chain(self, grind_session_id: str = "") -> list[dict]:
        """Return GIC-stamped validation rows ordered by gic_ts_ns ASC.

        INV-GIC-001 fix: when grind_session_id is provided, only rows belonging to
        that session are returned, preventing cross-session chain reconstruction.
        """
        with self._conn() as conn:
            if grind_session_id:
                rows = conn.execute(
                    "SELECT rvl.id, rvl.grind_chain_hash, rvl.pcc_host_state, "
                    "       rvl.fallback_verdict, rvl.gic_ts_ns, "
                    "       ar.commitment_hash "
                    "FROM ruling_validation_log AS rvl "
                    "JOIN agent_rulings AS ar ON ar.id = rvl.ruling_id "
                    "WHERE rvl.grind_chain_hash IS NOT NULL "
                    "AND rvl.grind_session_id = ? "
                    "ORDER BY rvl.gic_ts_ns ASC",
                    (grind_session_id,),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT rvl.id, rvl.grind_chain_hash, rvl.pcc_host_state, "
                    "       rvl.fallback_verdict, rvl.gic_ts_ns, "
                    "       ar.commitment_hash "
                    "FROM ruling_validation_log AS rvl "
                    "JOIN agent_rulings AS ar ON ar.id = rvl.ruling_id "
                    "WHERE rvl.grind_chain_hash IS NOT NULL "
                    "ORDER BY rvl.gic_ts_ns ASC",
                ).fetchall()
        return [dict(r) for r in rows]

    def get_grind_chain_status(self, grind_session_id: str, cfg=None) -> dict:
        """Recompute and verify the full GIC chain.

        Returns:
            grind_session_id, chain_length, latest_gic_hash (hex), chain_intact (bool),
            genesis_ts (float), latest_ts (float).
        """
        from .grind_chain import compute_gic, genesis_gic

        rows = self.get_ruling_rows_for_chain(grind_session_id)
        if not rows:
            return {
                "grind_session_id":  grind_session_id,
                "chain_length":      0,
                "latest_gic_hash":   "",
                "chain_intact":      True,  # empty chain is vacuously intact
                "genesis_ts":        0.0,
                "latest_ts":         0.0,
            }

        chain_intact = True

        for i, row in enumerate(rows):
            ts_ns = int(row.get("gic_ts_ns") or 0)
            commitment_hex = row.get("commitment_hash") or ""
            pcc_host = row.get("pcc_host_state") or "DISCONNECTED"
            verdict = row.get("fallback_verdict") or "FLAG"
            stored_hex = row.get("grind_chain_hash") or ""

            if i == 0:
                # Session 1: genesis_gic anchors with same ts_ns; compute_gic folds in session data.
                genesis = genesis_gic(grind_session_id, ts_ns)
                expected = compute_gic(genesis, commitment_hex, pcc_host, verdict, ts_ns)
            else:
                expected = compute_gic(
                    bytes.fromhex(rows[i - 1]["grind_chain_hash"]),
                    commitment_hex, pcc_host, verdict, ts_ns,
                )

            if expected.hex() != stored_hex:
                chain_intact = False
                break

        genesis_ts = float(rows[0].get("gic_ts_ns", 0)) / 1e9 if rows[0].get("gic_ts_ns") else 0.0
        latest_ts = float(rows[-1].get("gic_ts_ns", 0)) / 1e9 if rows[-1].get("gic_ts_ns") else 0.0

        return {
            "grind_session_id":  grind_session_id,
            "chain_length":      len(rows),
            "latest_gic_hash":   rows[-1]["grind_chain_hash"],
            "chain_intact":      chain_intact,
            "genesis_ts":        genesis_ts,
            "latest_ts":         latest_ts,
        }

    def get_prev_gic_ts_ns(self) -> int:
        """Return the maximum gic_ts_ns across all GIC-stamped rows (0 if none).

        Used to enforce monotonicity in GIC timestamp sequence.
        """
        with self._conn() as conn:
            row = conn.execute(
                "SELECT MAX(gic_ts_ns) FROM ruling_validation_log WHERE gic_ts_ns IS NOT NULL"
            ).fetchone()
        if row and row[0] is not None:
            return int(row[0])
        return 0

    # --- Phase 236-WATCHDOG: Watchdog Event Chain (WEC) ---

    def get_prev_watchdog_event_hash(self, grind_session_id: str) -> bytes | None:
        """Return the most recent WEC hash bytes for the given grind session, or None.

        Scoped by grind_session_id so a new grind run starts a fresh WEC chain
        (parallels INV-GIC-001 grind_session_id scoping).
        """
        with self._conn() as conn:
            if grind_session_id:
                row = conn.execute(
                    "SELECT wec_hash FROM watchdog_event_log "
                    "WHERE grind_session_id = ? "
                    "ORDER BY ts_ns DESC LIMIT 1",
                    (grind_session_id,),
                ).fetchone()
            else:
                row = conn.execute(
                    "SELECT wec_hash FROM watchdog_event_log "
                    "ORDER BY ts_ns DESC LIMIT 1"
                ).fetchone()
        if row is None:
            return None
        return bytes.fromhex(row["wec_hash"])

    def insert_watchdog_event(
        self,
        event_code: int,
        event_name: str,
        pid: int,
        grind_session_id: str,
        ts_ns: int,
        metadata_json: str = "{}",
    ) -> str:
        """Append one watchdog event to the WEC chain. Returns wec_hash hex.

        WEC formula is delegated to watchdog_chain.compute_wec / genesis_wec —
        the formula module is the single source of truth (parallels grind_chain).

        Monotonicity guard: if ts_ns <= prev event ts_ns for this session,
        bump to prev_ts + 1 to preserve chain ordering across NTP backsteps.
        """
        from .watchdog_chain import compute_wec, genesis_wec

        # Monotonicity: ensure ts_ns strictly increases within a session
        with self._conn() as conn:
            row = conn.execute(
                "SELECT MAX(ts_ns) FROM watchdog_event_log WHERE grind_session_id = ?",
                (grind_session_id,),
            ).fetchone()
        prev_ts = int(row[0]) if (row and row[0] is not None) else 0
        if ts_ns <= prev_ts:
            ts_ns = prev_ts + 1

        prev_wec = self.get_prev_watchdog_event_hash(grind_session_id)
        if prev_wec is None:
            prev_wec = genesis_wec(grind_session_id, ts_ns)
            prev_wec_hex = ""  # genesis link — no on-chain prior hash to record
        else:
            prev_wec_hex = prev_wec.hex()

        wec = compute_wec(prev_wec, event_code, pid, grind_session_id, ts_ns)
        wec_hex = wec.hex()

        with self._conn() as conn:
            conn.execute(
                "INSERT INTO watchdog_event_log "
                "(event_code, event_name, pid, grind_session_id, "
                " wec_hash, prev_wec_hash, metadata_json, ts_ns, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    int(event_code), str(event_name)[:64], int(pid),
                    str(grind_session_id),
                    wec_hex, prev_wec_hex, str(metadata_json),
                    int(ts_ns), time.time(),
                ),
            )
        return wec_hex

    def get_watchdog_event_chain_status(
        self, grind_session_id: str = "", limit: int = 100
    ) -> dict:
        """Recompute and verify the WEC chain for a grind session.

        Returns:
            grind_session_id, chain_length, latest_wec_hash (hex), chain_intact (bool),
            last_event_code (int|None), last_event_name (str), last_event_ts (float),
            restarts_last_hour (int), genesis_ts (float).
        """
        from .watchdog_chain import compute_wec, genesis_wec, EVENT_CODES

        with self._conn() as conn:
            if grind_session_id:
                rows = conn.execute(
                    "SELECT event_code, event_name, pid, wec_hash, ts_ns "
                    "FROM watchdog_event_log "
                    "WHERE grind_session_id = ? "
                    "ORDER BY ts_ns ASC LIMIT ?",
                    (grind_session_id, int(limit)),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT event_code, event_name, pid, wec_hash, ts_ns, grind_session_id "
                    "FROM watchdog_event_log "
                    "ORDER BY ts_ns ASC LIMIT ?",
                    (int(limit),),
                ).fetchall()

        if not rows:
            return {
                "grind_session_id":      grind_session_id,
                "chain_length":          0,
                "latest_wec_hash":       "",
                "chain_intact":          True,  # vacuously intact
                "last_event_code":       None,
                "last_event_name":       "",
                "last_event_ts":         0.0,
                "restarts_last_hour":    0,
                "genesis_ts":            0.0,
            }

        # Verify chain
        rows = [dict(r) for r in rows]
        sid_for_chain = grind_session_id or rows[-1].get("grind_session_id", "")
        chain_intact = True
        for i, row in enumerate(rows):
            ts_ns = int(row["ts_ns"])
            ec = int(row["event_code"])
            pid = int(row["pid"])
            stored_hex = row["wec_hash"]
            if i == 0:
                prev = genesis_wec(sid_for_chain, ts_ns)
            else:
                prev = bytes.fromhex(rows[i - 1]["wec_hash"])
            expected = compute_wec(prev, ec, pid, sid_for_chain, ts_ns)
            if expected.hex() != stored_hex:
                chain_intact = False
                break

        # Restarts last hour: BRIDGE_RESTART_TRIGGERED events in last 3600s
        restart_code = EVENT_CODES["BRIDGE_RESTART_TRIGGERED"]
        now_ns = time.time_ns()
        cutoff_ns = now_ns - 3_600_000_000_000  # 1 hour in ns
        restarts_last_hour = sum(
            1 for r in rows
            if int(r["event_code"]) == restart_code and int(r["ts_ns"]) >= cutoff_ns
        )

        latest = rows[-1]
        return {
            "grind_session_id":      sid_for_chain,
            "chain_length":          len(rows),
            "latest_wec_hash":       latest["wec_hash"],
            "chain_intact":          chain_intact,
            "last_event_code":       int(latest["event_code"]),
            "last_event_name":       str(latest.get("event_name", "")),
            "last_event_ts":         float(latest["ts_ns"]) / 1e9,
            "restarts_last_hour":    restarts_last_hour,
            "genesis_ts":            float(rows[0]["ts_ns"]) / 1e9,
        }

    # --- Phase 236-CORPUS-SNAPSHOT ---

    def insert_corpus_snapshot(
        self,
        snapshot_commitment: str,
        wiki_hash: str,
        agent_root: str,
        separation_ratio: float,
        corpus_n: int,
        ts_ns: int,
        trigger_reason: str = "",
        on_chain_confirmed: bool = False,
        tx_hash: str = "",
        ipfs_cid: str = "",
    ) -> int:
        """Insert one corpus snapshot row. Returns row id.

        UNIQUE(snapshot_commitment) enforced — duplicate inserts (e.g. two
        triggers firing on the same wiki+ratio+corpus+fleet+ts_ns) are
        idempotent: the duplicate raises sqlite3.IntegrityError which we
        translate to "already recorded" by returning the existing row id.
        """
        try:
            with self._conn() as conn:
                cur = conn.execute(
                    "INSERT INTO corpus_snapshot_log "
                    "(snapshot_commitment, wiki_hash, agent_root, separation_ratio, "
                    " corpus_n, ts_ns, on_chain_confirmed, ipfs_cid, tx_hash, "
                    " trigger_reason, created_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        str(snapshot_commitment), str(wiki_hash), str(agent_root),
                        float(separation_ratio), int(corpus_n), int(ts_ns),
                        1 if on_chain_confirmed else 0,
                        str(ipfs_cid), str(tx_hash), str(trigger_reason)[:128],
                        time.time(),
                    ),
                )
                return int(cur.lastrowid)
        except Exception:
            # Likely UNIQUE collision — return the existing row id
            with self._conn() as conn:
                row = conn.execute(
                    "SELECT id FROM corpus_snapshot_log WHERE snapshot_commitment = ?",
                    (str(snapshot_commitment),),
                ).fetchone()
            return int(row["id"]) if row else 0

    def get_corpus_snapshot_status(self) -> dict:
        """Return latest corpus snapshot with chain length.

        Returns 10 keys: total_snapshots, latest_commitment, wiki_hash,
        agent_root, separation_ratio, corpus_n, last_snapshot_ts,
        on_chain_confirmed, trigger_reason, timestamp.
        """
        import time as _t236s
        with self._conn() as conn:
            total = (conn.execute(
                "SELECT COUNT(*) FROM corpus_snapshot_log"
            ).fetchone() or (0,))[0]
            row = conn.execute(
                "SELECT snapshot_commitment, wiki_hash, agent_root, separation_ratio, "
                "       corpus_n, ts_ns, on_chain_confirmed, trigger_reason "
                "FROM corpus_snapshot_log ORDER BY ts_ns DESC LIMIT 1"
            ).fetchone()
        if row is None:
            return {
                "total_snapshots":    0,
                "latest_commitment":  "",
                "wiki_hash":          "",
                "agent_root":         "",
                "separation_ratio":   0.0,
                "corpus_n":           0,
                "last_snapshot_ts":   0.0,
                "on_chain_confirmed": False,
                "trigger_reason":     "",
                "timestamp":          _t236s.time(),
            }
        return {
            "total_snapshots":    int(total),
            "latest_commitment":  str(row[0]),
            "wiki_hash":          str(row[1]),
            "agent_root":         str(row[2]),
            "separation_ratio":   float(row[3]),
            "corpus_n":           int(row[4]),
            "last_snapshot_ts":   float(row[5]) / 1e9,
            "on_chain_confirmed": bool(row[6]),
            "trigger_reason":     str(row[7]),
            "timestamp":          _t236s.time(),
        }

    def get_corpus_snapshot_history(self, limit: int = 20) -> list[dict]:
        """Return last N snapshots in DESC ts_ns order (newest first)."""
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT id, snapshot_commitment, wiki_hash, agent_root, "
                "       separation_ratio, corpus_n, ts_ns, on_chain_confirmed, "
                "       trigger_reason, created_at "
                "FROM corpus_snapshot_log ORDER BY ts_ns DESC LIMIT ?",
                (int(limit),),
            ).fetchall()
        return [dict(r) for r in rows]

    # --- Phase O3-ZKBA-TRACK1: ZKBA artifact log (PATTERN-017 family) ---

    def insert_zkba_artifact(
        self,
        *,
        zkba_class: int,
        proof_weight: int,
        commitment_hex: str,
        preimage_json: str,
        ts_ns: int,
        manifest_uri: str | None = None,
        compiler_output_hash_hex: str | None = None,
    ) -> int:
        """Insert one ZKBA artifact row. Returns row id.

        UNIQUE(commitment_hex) enforced — re-inserting the same commitment
        returns the existing row id (matches corpus_snapshot_log idempotency
        precedent).  anchor_tx_hash is intentionally NOT writable in Track 1
        (populated by Stream A3 parallel_zkba_anchor.py post-activation).
        """
        try:
            with self._conn() as conn:
                cur = conn.execute(
                    "INSERT INTO zkba_artifact_log "
                    "(commitment_hex, zkba_class, proof_weight, preimage_json, "
                    " ts_ns, manifest_uri, compiler_output_hash_hex, "
                    " anchor_tx_hash, created_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, NULL, ?)",
                    (
                        str(commitment_hex), int(zkba_class), int(proof_weight),
                        str(preimage_json), int(ts_ns),
                        str(manifest_uri) if manifest_uri is not None else None,
                        str(compiler_output_hash_hex) if compiler_output_hash_hex is not None else None,
                        time.time(),
                    ),
                )
                return int(cur.lastrowid)
        except Exception:
            # Likely UNIQUE collision — return the existing row id
            with self._conn() as conn:
                row = conn.execute(
                    "SELECT id FROM zkba_artifact_log WHERE commitment_hex = ?",
                    (str(commitment_hex),),
                ).fetchone()
            return int(row["id"]) if row else 0

    def get_zkba_artifact_status(self, commitment_hex: str) -> dict | None:
        """Return one ZKBA artifact row by commitment_hex, or None."""
        with self._conn() as conn:
            row = conn.execute(
                "SELECT id, commitment_hex, zkba_class, proof_weight, "
                "       preimage_json, ts_ns, manifest_uri, "
                "       compiler_output_hash_hex, anchor_tx_hash, created_at "
                "FROM zkba_artifact_log WHERE commitment_hex = ?",
                (str(commitment_hex),),
            ).fetchone()
        return dict(row) if row is not None else None

    def get_zkba_artifact_history(self, limit: int = 20) -> list[dict]:
        """Return last N ZKBA artifacts in DESC ts_ns order (newest first)."""
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT id, commitment_hex, zkba_class, proof_weight, ts_ns, "
                "       manifest_uri, compiler_output_hash_hex, anchor_tx_hash, "
                "       created_at "
                "FROM zkba_artifact_log ORDER BY ts_ns DESC LIMIT ?",
                (int(limit),),
            ).fetchall()
        return [dict(r) for r in rows]

    def get_zkba_artifact_summary(self) -> dict:
        """Phase O3-ZKBA-TRACK1 (post-C5) — aggregate stats over zkba_artifact_log.

        Returned dict shape (matches VAPIZKBA.status() SDK wire contract at
        sdk/vapi_sdk.py:9272-9283):

            {
                "total_artifacts":        int,
                "anchored_count":         int,        # rows with anchor_tx_hash IS NOT NULL
                "track1_invariant_holds": bool,        # anchored_count == 0 holds across Track 1
                "class_breakdown":        {zkba_class_int: count_int, ...},
                "latest":                 dict | None,  # newest row (DESC ts_ns) or None
            }

        Reads only — no mutation.  Fail-open on DB errors via outer try/except
        returning the zero-state shape (total=0, anchored=0, holds=True,
        breakdown={}, latest=None).
        """
        try:
            with self._conn() as conn:
                total_row = conn.execute(
                    "SELECT COUNT(*) AS n FROM zkba_artifact_log"
                ).fetchone()
                anchored_row = conn.execute(
                    "SELECT COUNT(*) AS n FROM zkba_artifact_log "
                    "WHERE anchor_tx_hash IS NOT NULL"
                ).fetchone()
                breakdown_rows = conn.execute(
                    "SELECT zkba_class, COUNT(*) AS n FROM zkba_artifact_log "
                    "GROUP BY zkba_class"
                ).fetchall()
                latest_row = conn.execute(
                    "SELECT id, commitment_hex, zkba_class, proof_weight, ts_ns, "
                    "       manifest_uri, compiler_output_hash_hex, anchor_tx_hash, "
                    "       created_at "
                    "FROM zkba_artifact_log ORDER BY ts_ns DESC LIMIT 1"
                ).fetchone()
            total = int(total_row["n"]) if total_row else 0
            anchored = int(anchored_row["n"]) if anchored_row else 0
            breakdown = {int(r["zkba_class"]): int(r["n"]) for r in breakdown_rows}
            latest = dict(latest_row) if latest_row is not None else None
            return {
                "total_artifacts":        total,
                "anchored_count":         anchored,
                "track1_invariant_holds": anchored == 0,
                "class_breakdown":        breakdown,
                "latest":                 latest,
            }
        except Exception:
            return {
                "total_artifacts":        0,
                "anchored_count":         0,
                "track1_invariant_holds": True,
                "class_breakdown":        {},
                "latest":                 None,
            }

    # --- Phase O4-VPM-INT B.0: vpm_artifact_log helpers ---

    def insert_vpm_artifact(
        self,
        *,
        commitment_hex: str,
        vpm_id: str,
        zkba_class: int,
        proof_weight: int,
        visual_state: str,
        capture_mode: str,
        integrity_label_hash_hex: str,
        wrapper_schema: str,
        zkba_manifest_hash_hex: str,
        manifest_uri: str | None,
        compiler_output_hash_hex: str | None,
        preimage_json: str,
        ts_ns: int,
    ) -> int:
        """Insert one VPM artifact row. Returns row id.

        UNIQUE(commitment_hex) enforced — re-inserting the same commitment
        returns the existing row id (matches zkba_artifact_log idempotency
        precedent from commit 625007ab).

        All fields keyword-only to keep the insert call site self-describing
        at compile-vpm-artifact orchestrators + at the bridge POST /operator/
        vpm-compile endpoint.
        """
        try:
            with self._conn() as conn:
                cur = conn.execute(
                    "INSERT INTO vpm_artifact_log "
                    "(commitment_hex, vpm_id, zkba_class, proof_weight, "
                    " visual_state, capture_mode, integrity_label_hash_hex, "
                    " wrapper_schema, zkba_manifest_hash_hex, manifest_uri, "
                    " compiler_output_hash_hex, preimage_json, ts_ns, created_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        str(commitment_hex), str(vpm_id),
                        int(zkba_class), int(proof_weight),
                        str(visual_state), str(capture_mode),
                        str(integrity_label_hash_hex),
                        str(wrapper_schema), str(zkba_manifest_hash_hex),
                        str(manifest_uri) if manifest_uri is not None else None,
                        str(compiler_output_hash_hex) if compiler_output_hash_hex is not None else None,
                        str(preimage_json), int(ts_ns),
                        time.time(),
                    ),
                )
                return int(cur.lastrowid)
        except Exception:
            # Likely UNIQUE collision — return the existing row id
            with self._conn() as conn:
                row = conn.execute(
                    "SELECT id FROM vpm_artifact_log WHERE commitment_hex = ?",
                    (str(commitment_hex),),
                ).fetchone()
            return int(row["id"]) if row else 0

    def get_vpm_artifact_status(self, commitment_hex: str) -> dict | None:
        """Return one VPM artifact row by commitment_hex, or None."""
        with self._conn() as conn:
            row = conn.execute(
                "SELECT id, commitment_hex, vpm_id, zkba_class, proof_weight, "
                "       visual_state, capture_mode, integrity_label_hash_hex, "
                "       wrapper_schema, zkba_manifest_hash_hex, manifest_uri, "
                "       compiler_output_hash_hex, preimage_json, ts_ns, created_at "
                "FROM vpm_artifact_log WHERE commitment_hex = ?",
                (str(commitment_hex),),
            ).fetchone()
        return dict(row) if row is not None else None

    def get_vpm_artifact_history(
        self,
        vpm_id: str | None = None,
        visual_state: str | None = None,
        since_minutes: int = 0,
        limit: int = 20,
    ) -> list[dict]:
        """Return VPM artifacts filtered by optional vpm_id / visual_state /
        since_minutes window, DESC ts_ns (newest first), capped at `limit`.

        `since_minutes`=0 means no time filter. Filter parameters are
        composable; passing none = unbounded query (clamped by `limit`).
        """
        clauses: list[str] = []
        args: list = []
        if vpm_id is not None and vpm_id != "":
            clauses.append("vpm_id = ?")
            args.append(str(vpm_id))
        if visual_state is not None and visual_state != "":
            clauses.append("visual_state = ?")
            args.append(str(visual_state))
        if since_minutes > 0:
            cutoff = time.time() - (int(since_minutes) * 60.0)
            clauses.append("created_at >= ?")
            args.append(cutoff)
        where_sql = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        args.append(int(limit))
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT id, commitment_hex, vpm_id, zkba_class, proof_weight, "
                "       visual_state, capture_mode, integrity_label_hash_hex, "
                "       wrapper_schema, zkba_manifest_hash_hex, manifest_uri, "
                "       compiler_output_hash_hex, ts_ns, created_at "
                f"FROM vpm_artifact_log{where_sql} ORDER BY ts_ns DESC LIMIT ?",
                tuple(args),
            ).fetchall()
        return [dict(r) for r in rows]

    def get_vpm_artifact_summary(self) -> dict:
        """Phase O4-VPM-INT B.0 — aggregate stats over vpm_artifact_log.

        Mirrors the zkba_artifact_log summary shape but with VPM-specific
        breakdowns. Returned dict shape:

            {
                "total_artifacts":    int,
                "vpm_id_breakdown":   {vpm_id_str: count_int, ...},
                "visual_state_breakdown": {state_str: count_int, ...},
                "latest":             dict | None,
            }

        Reads only — no mutation. Fail-open on DB errors via outer
        try/except returning the zero-state shape.
        """
        try:
            with self._conn() as conn:
                total_row = conn.execute(
                    "SELECT COUNT(*) AS n FROM vpm_artifact_log"
                ).fetchone()
                vpm_id_rows = conn.execute(
                    "SELECT vpm_id, COUNT(*) AS n FROM vpm_artifact_log "
                    "GROUP BY vpm_id"
                ).fetchall()
                state_rows = conn.execute(
                    "SELECT visual_state, COUNT(*) AS n FROM vpm_artifact_log "
                    "GROUP BY visual_state"
                ).fetchall()
                latest_row = conn.execute(
                    "SELECT id, commitment_hex, vpm_id, zkba_class, proof_weight, "
                    "       visual_state, capture_mode, ts_ns, manifest_uri, "
                    "       created_at "
                    "FROM vpm_artifact_log ORDER BY ts_ns DESC LIMIT 1"
                ).fetchone()
            total = int(total_row["n"]) if total_row else 0
            vpm_id_breakdown = {str(r["vpm_id"]): int(r["n"]) for r in vpm_id_rows}
            state_breakdown = {str(r["visual_state"]): int(r["n"]) for r in state_rows}
            latest = dict(latest_row) if latest_row is not None else None
            return {
                "total_artifacts":        total,
                "vpm_id_breakdown":       vpm_id_breakdown,
                "visual_state_breakdown": state_breakdown,
                "latest":                 latest,
            }
        except Exception:
            return {
                "total_artifacts":        0,
                "vpm_id_breakdown":       {},
                "visual_state_breakdown": {},
                "latest":                 None,
            }

    # --- Phase 237-ZK-SEPPROOF: BIOMETRIC-SNAPSHOT-v1 anchor history ---

    def insert_biometric_snapshot(
        self,
        snapshot_commitment: str,
        feature_dim: int,
        sorted_player_ids: list,
        centroids_by_player: dict,
        cov_inv: list,
        ts_ns: int,
        ait_session_log_id: int = 0,
        trigger_reason: str = "",
        on_chain_confirmed: bool = False,
        tx_hash: str = "",
    ) -> int:
        """Insert one BIOMETRIC-SNAPSHOT-v1 row.  Returns row id.

        UNIQUE(snapshot_commitment) enforces idempotency: re-inserting the
        same commitment returns the existing row id (matching corpus_snapshot_log
        precedent at Phase 237.5).
        """
        import json as _j237s
        try:
            with self._conn() as conn:
                cur = conn.execute(
                    "INSERT INTO biometric_snapshot_log "
                    "(snapshot_commitment, feature_dim, n_players, sorted_player_ids, "
                    " centroids_json, cov_inv_json, ts_ns, on_chain_confirmed, tx_hash, "
                    " trigger_reason, ait_session_log_id, created_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        str(snapshot_commitment),
                        int(feature_dim),
                        int(len(sorted_player_ids)),
                        _j237s.dumps([int(x) for x in sorted_player_ids]),
                        _j237s.dumps(centroids_by_player),
                        _j237s.dumps(cov_inv),
                        int(ts_ns),
                        1 if on_chain_confirmed else 0,
                        str(tx_hash),
                        str(trigger_reason)[:128],
                        int(ait_session_log_id),
                        time.time(),
                    ),
                )
                return int(cur.lastrowid)
        except Exception:
            with self._conn() as conn:
                row = conn.execute(
                    "SELECT id FROM biometric_snapshot_log WHERE snapshot_commitment = ?",
                    (str(snapshot_commitment),),
                ).fetchone()
            return int(row["id"]) if row else 0

    def get_latest_biometric_snapshot(self) -> dict:
        """Return the most recent biometric snapshot or empty dict.

        Returned keys (when present): snapshot_commitment, feature_dim,
        n_players, sorted_player_ids, centroids_by_player, cov_inv, ts_ns,
        on_chain_confirmed, tx_hash, trigger_reason, ait_session_log_id.
        """
        import json as _j237g
        with self._conn() as conn:
            row = conn.execute(
                "SELECT snapshot_commitment, feature_dim, n_players, sorted_player_ids, "
                "       centroids_json, cov_inv_json, ts_ns, on_chain_confirmed, tx_hash, "
                "       trigger_reason, ait_session_log_id "
                "FROM biometric_snapshot_log ORDER BY ts_ns DESC LIMIT 1"
            ).fetchone()
        if row is None:
            return {}
        # Defensive JSON parsing
        try:
            sids = _j237g.loads(row["sorted_player_ids"]) or []
        except Exception:
            sids = []
        try:
            cents = _j237g.loads(row["centroids_json"]) or {}
            # JSON keys are always strings — coerce back to int
            cents = {int(k): list(v) for k, v in cents.items()}
        except Exception:
            cents = {}
        try:
            cov = _j237g.loads(row["cov_inv_json"]) or []
        except Exception:
            cov = []
        return {
            "snapshot_commitment":  str(row["snapshot_commitment"]),
            "feature_dim":          int(row["feature_dim"]),
            "n_players":            int(row["n_players"]),
            "sorted_player_ids":    sids,
            "centroids_by_player":  cents,
            "cov_inv":              cov,
            "ts_ns":                int(row["ts_ns"]),
            "on_chain_confirmed":   bool(row["on_chain_confirmed"]),
            "tx_hash":              str(row["tx_hash"]),
            "trigger_reason":       str(row["trigger_reason"]),
            "ait_session_log_id":   int(row["ait_session_log_id"]),
        }

    def get_biometric_snapshot_status(self) -> dict:
        """Return summary of biometric_snapshot_log: total + latest.

        Mirrors get_corpus_snapshot_status shape so the operator endpoint
        can return both with consistent keys.
        """
        import time as _t237gs
        with self._conn() as conn:
            total = (conn.execute(
                "SELECT COUNT(*) FROM biometric_snapshot_log"
            ).fetchone() or (0,))[0]
        latest = self.get_latest_biometric_snapshot()
        return {
            "total_snapshots":     int(total),
            "latest_commitment":   latest.get("snapshot_commitment", ""),
            "feature_dim":         latest.get("feature_dim", 0),
            "n_players":           latest.get("n_players", 0),
            "ts_ns":               latest.get("ts_ns", 0),
            "on_chain_confirmed":  latest.get("on_chain_confirmed", False),
            "tx_hash":             latest.get("tx_hash", ""),
            "trigger_reason":      latest.get("trigger_reason", ""),
            "timestamp":           _t237gs.time(),
        }

    # --- Phase 238-MARKETPLACE: LISTING-v1 anchor history ---

    def insert_marketplace_listing(
        self,
        listing_commitment: str,
        seller_address: str,
        sepproof_commitment: str,
        biometric_snapshot_hash: str,
        corpus_snapshot_hash: str,
        gic_hash: str,
        consent_bitmask: int,
        data_class: int,
        price_iotx: float,
        ipfs_cid: str,
        ipfs_cid_hash: str,
        ts_ns: int,
        anchors_present_count: int = 0,
        trigger_reason: str = "",
        on_chain_confirmed: bool = False,
        tx_hash: str = "",
    ) -> int:
        """Insert one LISTING-v1 row.  Returns row id.

        UNIQUE(listing_commitment) enforces idempotency: re-inserting the
        same commitment returns the existing row id (matches
        biometric_snapshot_log precedent).
        """
        try:
            with self._conn() as conn:
                cur = conn.execute(
                    "INSERT INTO marketplace_listing_log "
                    "(listing_commitment, seller_address, sepproof_commitment, "
                    " biometric_snapshot_hash, corpus_snapshot_hash, gic_hash, "
                    " consent_bitmask, data_class, price_iotx, ipfs_cid, ipfs_cid_hash, "
                    " ts_ns, on_chain_confirmed, tx_hash, anchors_present_count, "
                    " trigger_reason, created_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        str(listing_commitment),
                        str(seller_address),
                        str(sepproof_commitment),
                        str(biometric_snapshot_hash),
                        str(corpus_snapshot_hash),
                        str(gic_hash),
                        int(consent_bitmask),
                        int(data_class),
                        float(price_iotx),
                        str(ipfs_cid),
                        str(ipfs_cid_hash),
                        int(ts_ns),
                        1 if on_chain_confirmed else 0,
                        str(tx_hash),
                        int(anchors_present_count),
                        str(trigger_reason)[:128],
                        time.time(),
                    ),
                )
                return int(cur.lastrowid)
        except Exception:
            with self._conn() as conn:
                row = conn.execute(
                    "SELECT id FROM marketplace_listing_log WHERE listing_commitment = ?",
                    (str(listing_commitment),),
                ).fetchone()
            return int(row["id"]) if row else 0

    def get_latest_marketplace_listing(self) -> dict:
        """Return the most recent listing or empty dict.

        Returned keys mirror insert columns (parsed JSON-friendly).
        """
        with self._conn() as conn:
            row = conn.execute(
                "SELECT listing_commitment, seller_address, sepproof_commitment, "
                "       biometric_snapshot_hash, corpus_snapshot_hash, gic_hash, "
                "       consent_bitmask, data_class, price_iotx, ipfs_cid, "
                "       ipfs_cid_hash, ts_ns, on_chain_confirmed, tx_hash, "
                "       anchors_present_count, trigger_reason "
                "FROM marketplace_listing_log ORDER BY ts_ns DESC LIMIT 1"
            ).fetchone()
        if row is None:
            return {}
        return {
            "listing_commitment":      str(row["listing_commitment"]),
            "seller_address":          str(row["seller_address"]),
            "sepproof_commitment":     str(row["sepproof_commitment"]),
            "biometric_snapshot_hash": str(row["biometric_snapshot_hash"]),
            "corpus_snapshot_hash":    str(row["corpus_snapshot_hash"]),
            "gic_hash":                str(row["gic_hash"]),
            "consent_bitmask":         int(row["consent_bitmask"]),
            "data_class":              int(row["data_class"]),
            "price_iotx":              float(row["price_iotx"]),
            "ipfs_cid":                str(row["ipfs_cid"]),
            "ipfs_cid_hash":           str(row["ipfs_cid_hash"]),
            "ts_ns":                   int(row["ts_ns"]),
            "on_chain_confirmed":      bool(row["on_chain_confirmed"]),
            "tx_hash":                 str(row["tx_hash"]),
            "anchors_present_count":   int(row["anchors_present_count"]),
            "trigger_reason":          str(row["trigger_reason"]),
        }

    def get_marketplace_listing_status(self) -> dict:
        """Return summary of marketplace_listing_log: total + latest.

        Mirrors get_biometric_snapshot_status shape so the operator
        endpoint can return both with consistent keys.
        """
        import time as _t238ls
        with self._conn() as conn:
            total = (conn.execute(
                "SELECT COUNT(*) FROM marketplace_listing_log"
            ).fetchone() or (0,))[0]
            anchored = (conn.execute(
                "SELECT COUNT(*) FROM marketplace_listing_log "
                "WHERE on_chain_confirmed = 1"
            ).fetchone() or (0,))[0]
        latest = self.get_latest_marketplace_listing()
        return {
            "total_listings":         int(total),
            "anchored_listings":      int(anchored),
            "latest_commitment":      latest.get("listing_commitment", ""),
            "latest_seller":          latest.get("seller_address", ""),
            "latest_data_class":      latest.get("data_class", 0),
            "latest_price_iotx":      latest.get("price_iotx", 0.0),
            "latest_anchors_present": latest.get("anchors_present_count", 0),
            "latest_ts_ns":           latest.get("ts_ns", 0),
            "latest_on_chain":        latest.get("on_chain_confirmed", False),
            "latest_tx_hash":         latest.get("tx_hash", ""),
            "timestamp":              _t238ls.time(),
        }

    def get_marketplace_listings_by_seller(
        self, seller_address: str, limit: int = 20
    ) -> list[dict]:
        """Return last N listings by seller_address (DESC ts_ns)."""
        if not seller_address:
            return []
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT listing_commitment, data_class, price_iotx, ipfs_cid, "
                "       ts_ns, on_chain_confirmed, tx_hash, anchors_present_count "
                "FROM marketplace_listing_log "
                "WHERE seller_address = ? "
                "ORDER BY ts_ns DESC LIMIT ?",
                (str(seller_address), int(limit)),
            ).fetchall()
        return [dict(r) for r in rows]

    # --- Phase 238 Step I — Curator Shadow Infrastructure ---

    def insert_curator_review(
        self,
        listing_commitment: str,
        verdict: str,
        severity: str,
        anchors_recorded_count: int,
        anchors_breakdown_json: str,
        consent_marketplace_bit_set: bool,
        ipfs_resolvable,  # bool | None
        declared_tier: int,
        tier_at_review_time: int,
        tier_changed: bool,
        shadow_mode: bool,
        reason_detail: str,
        trigger_reason: str,
        ts_ns: int,
    ) -> int:
        """Insert one Curator review row.  Returns row id.

        No UNIQUE constraint on listing_commitment — Curator may re-review the
        same listing any number of times (timeline-style ledger).
        """
        ipfs_int = None if ipfs_resolvable is None else (1 if ipfs_resolvable else 0)
        try:
            with self._conn() as conn:
                cur = conn.execute(
                    "INSERT INTO curator_listing_review_log "
                    "(listing_commitment, verdict, severity, anchors_recorded_count, "
                    " anchors_breakdown_json, consent_marketplace_bit_set, ipfs_resolvable, "
                    " declared_tier, tier_at_review_time, tier_changed, shadow_mode, "
                    " reason_detail, trigger_reason, ts_ns, created_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        str(listing_commitment),
                        str(verdict),
                        str(severity),
                        int(anchors_recorded_count),
                        str(anchors_breakdown_json)[:512],
                        1 if consent_marketplace_bit_set else 0,
                        ipfs_int,
                        int(declared_tier),
                        int(tier_at_review_time),
                        1 if tier_changed else 0,
                        1 if shadow_mode else 0,
                        str(reason_detail)[:256],
                        str(trigger_reason)[:128],
                        int(ts_ns),
                        time.time(),
                    ),
                )
                return int(cur.lastrowid)
        except Exception:
            return 0

    def get_curator_review_status(self) -> dict:
        """Return aggregated Curator review summary.

        Shape matches CuratorStatusResult SDK dataclass + GET
        /agent/curator-status endpoint wire contract (10 keys).
        """
        import time as _t238cur
        with self._conn() as conn:
            total = (conn.execute(
                "SELECT COUNT(*) FROM curator_listing_review_log"
            ).fetchone() or (0,))[0]
            approved = (conn.execute(
                "SELECT COUNT(*) FROM curator_listing_review_log WHERE verdict = 'APPROVED'"
            ).fetchone() or (0,))[0]
            flagged = (conn.execute(
                "SELECT COUNT(*) FROM curator_listing_review_log WHERE verdict LIKE 'FLAGGED_%'"
            ).fetchone() or (0,))[0]
            rejected = (conn.execute(
                "SELECT COUNT(*) FROM curator_listing_review_log WHERE verdict LIKE 'REJECTED_%'"
            ).fetchone() or (0,))[0]
            latest = conn.execute(
                "SELECT verdict, listing_commitment, ts_ns "
                "FROM curator_listing_review_log "
                "ORDER BY ts_ns DESC LIMIT 1"
            ).fetchone()
        latest_d = dict(latest) if latest else {}
        return {
            "total_reviews":             int(total),
            "approved_reviews":          int(approved),
            "flagged_reviews":           int(flagged),
            "rejected_reviews":          int(rejected),
            "latest_verdict":            str(latest_d.get("verdict", "")),
            "latest_listing_commitment": str(latest_d.get("listing_commitment", "")),
            "latest_review_ts_ns":       int(latest_d.get("ts_ns", 0)),
            "shadow_mode":               True,  # FROZEN True in O1
            "timestamp":                 _t238cur.time(),
        }

    def get_curator_reviews_for_listing(
        self, listing_commitment: str, limit: int = 50
    ) -> list[dict]:
        """Return all Curator reviews for one listing, DESC ts_ns."""
        if not listing_commitment:
            return []
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT id, verdict, severity, anchors_recorded_count, "
                "       anchors_breakdown_json, consent_marketplace_bit_set, "
                "       ipfs_resolvable, declared_tier, tier_at_review_time, "
                "       tier_changed, shadow_mode, reason_detail, "
                "       trigger_reason, ts_ns "
                "FROM curator_listing_review_log "
                "WHERE listing_commitment = ? "
                "ORDER BY ts_ns DESC LIMIT ?",
                (str(listing_commitment), int(limit)),
            ).fetchall()
        return [dict(r) for r in rows]

    def get_curator_flagged_listings(
        self, since_minutes: int = 1440, limit: int = 50
    ) -> list[dict]:
        """Return distinct listings with at least one FLAGGED_* / REJECTED_*
        verdict within the lookback window.  DESC by latest review ts_ns.

        Caps: limit <= 100; since_minutes <= 30d (43200).
        """
        limit = max(1, min(int(limit), 100))
        since_minutes = max(1, min(int(since_minutes), 43200))
        cutoff_ns = int((time.time() - since_minutes * 60) * 1e9)
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT listing_commitment, verdict, severity, "
                "       anchors_recorded_count, declared_tier, tier_at_review_time, "
                "       tier_changed, reason_detail, ts_ns "
                "FROM curator_listing_review_log "
                "WHERE ts_ns >= ? "
                "  AND (verdict LIKE 'FLAGGED_%' OR verdict LIKE 'REJECTED_%') "
                "ORDER BY ts_ns DESC LIMIT ?",
                (cutoff_ns, limit),
            ).fetchall()
        return [dict(r) for r in rows]

    # --- Phase O0 Stream 3-prep Session 1 — AGENT_COMMIT v1 ---

    def insert_agent_commit(
        self,
        commit_hash: str,
        agent_id: str,
        commit_sha: str,
        prev_commit_hash: str,
        repo_uri_sha: str,
        ts_ns: int,
        tx_hash: str = "",
        on_chain_confirmed: bool = False,
        anchor_id: int = -1,
    ) -> int:
        """Insert one AGENT_COMMIT v1 row into agent_commit_log. Returns row id.

        UNIQUE(commit_hash) enforced — duplicate inserts (same agent_commit
        hash from re-running the same git commit attestation) are idempotent:
        the duplicate raises sqlite3.IntegrityError which we translate to
        "already recorded" by returning the existing row id. Mirrors the
        pattern from insert_corpus_snapshot.
        """
        try:
            with self._conn() as conn:
                cur = conn.execute(
                    "INSERT INTO agent_commit_log "
                    "(commit_hash, agent_id, commit_sha, prev_commit_hash, "
                    " repo_uri_sha, ts_ns, tx_hash, on_chain_confirmed, "
                    " anchor_id, created_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        str(commit_hash), str(agent_id), str(commit_sha),
                        str(prev_commit_hash), str(repo_uri_sha), int(ts_ns),
                        str(tx_hash), 1 if on_chain_confirmed else 0,
                        int(anchor_id), time.time(),
                    ),
                )
                return int(cur.lastrowid)
        except Exception:
            # Likely UNIQUE collision — return the existing row id
            with self._conn() as conn:
                row = conn.execute(
                    "SELECT id FROM agent_commit_log WHERE commit_hash = ?",
                    (str(commit_hash),),
                ).fetchone()
            return int(row["id"]) if row else 0

    def get_agent_commit_status(self) -> dict:
        """Return latest AGENT_COMMIT v1 record summary.

        Returns 8 keys: total_commits, latest_hash, latest_agent_id,
        latest_commit_sha, latest_ts_ns, on_chain_confirmed, anchor_id,
        timestamp.
        """
        import time as _tac
        with self._conn() as conn:
            total = conn.execute(
                "SELECT COUNT(*) AS n FROM agent_commit_log"
            ).fetchone()["n"]
            row = conn.execute(
                "SELECT commit_hash, agent_id, commit_sha, ts_ns, "
                "       on_chain_confirmed, anchor_id "
                "FROM agent_commit_log ORDER BY ts_ns DESC LIMIT 1"
            ).fetchone()
        if row is None:
            return {
                "total_commits":      0,
                "latest_hash":        "",
                "latest_agent_id":    "",
                "latest_commit_sha":  "",
                "latest_ts_ns":       0,
                "on_chain_confirmed": False,
                "anchor_id":          -1,
                "timestamp":          _tac.time(),
            }
        return {
            "total_commits":      int(total),
            "latest_hash":        str(row["commit_hash"]),
            "latest_agent_id":    str(row["agent_id"]),
            "latest_commit_sha":  str(row["commit_sha"]),
            "latest_ts_ns":       int(row["ts_ns"]),
            "on_chain_confirmed": bool(row["on_chain_confirmed"]),
            "anchor_id":          int(row["anchor_id"]),
            "timestamp":          _tac.time(),
        }

    def get_agent_commit_history(self, agent_id: str = "", limit: int = 20) -> list[dict]:
        """Return last N AGENT_COMMIT v1 records, optionally filtered by agent_id.

        DESC ts_ns ordering (newest first). agent_id="" means all agents.
        """
        with self._conn() as conn:
            if agent_id:
                rows = conn.execute(
                    "SELECT id, commit_hash, agent_id, commit_sha, "
                    "       prev_commit_hash, repo_uri_sha, ts_ns, "
                    "       tx_hash, on_chain_confirmed, anchor_id, created_at "
                    "FROM agent_commit_log WHERE agent_id = ? "
                    "ORDER BY ts_ns DESC LIMIT ?",
                    (str(agent_id), int(limit)),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT id, commit_hash, agent_id, commit_sha, "
                    "       prev_commit_hash, repo_uri_sha, ts_ns, "
                    "       tx_hash, on_chain_confirmed, anchor_id, created_at "
                    "FROM agent_commit_log ORDER BY ts_ns DESC LIMIT ?",
                    (int(limit),),
                ).fetchall()
        return [dict(r) for r in rows]

    def insert_physical_data_attestation(
        self,
        pda_commitment: str,
        hardware_data_hash: str,
        agent_id: str,
        attestation_type: str,
        attestation_type_hash: str,
        ts_ns: int,
        tx_hash: str = "",
        on_chain_confirmed: bool = False,
        anchor_id: int = -1,
    ) -> int:
        """Insert one PHYSICAL_DATA_ATTESTATION v1 row into
        physical_data_attestation_log. Returns row id.

        UNIQUE(pda_commitment) enforced — duplicate inserts (same PDA
        hash from re-attesting the same physical-data artifact) are
        idempotent: the duplicate raises sqlite3.IntegrityError which
        we translate to "already recorded" by returning the existing
        row id. Mirrors insert_agent_commit / insert_corpus_snapshot.

        Phase O0 Stream 3-prep Session 2 — Pass 2C Section 4.2.
        """
        try:
            with self._conn() as conn:
                cur = conn.execute(
                    "INSERT INTO physical_data_attestation_log "
                    "(pda_commitment, hardware_data_hash, agent_id, "
                    " attestation_type, attestation_type_hash, ts_ns, "
                    " tx_hash, on_chain_confirmed, anchor_id, created_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        str(pda_commitment), str(hardware_data_hash),
                        str(agent_id), str(attestation_type),
                        str(attestation_type_hash), int(ts_ns),
                        str(tx_hash), 1 if on_chain_confirmed else 0,
                        int(anchor_id), time.time(),
                    ),
                )
                return int(cur.lastrowid)
        except Exception:
            # Likely UNIQUE collision — return the existing row id
            with self._conn() as conn:
                row = conn.execute(
                    "SELECT id FROM physical_data_attestation_log "
                    "WHERE pda_commitment = ?",
                    (str(pda_commitment),),
                ).fetchone()
            return int(row["id"]) if row else 0

    def get_physical_data_attestation_status(self) -> dict:
        """Return latest PHYSICAL_DATA_ATTESTATION v1 record summary.

        Returns 8 keys: total_attestations, latest_pda_commitment,
        latest_agent_id, latest_attestation_type, latest_ts_ns,
        on_chain_confirmed, anchor_id, timestamp.
        """
        import time as _tac
        with self._conn() as conn:
            total = conn.execute(
                "SELECT COUNT(*) AS n FROM physical_data_attestation_log"
            ).fetchone()["n"]
            row = conn.execute(
                "SELECT pda_commitment, agent_id, attestation_type, ts_ns, "
                "       on_chain_confirmed, anchor_id "
                "FROM physical_data_attestation_log ORDER BY ts_ns DESC LIMIT 1"
            ).fetchone()
        if row is None:
            return {
                "total_attestations":       0,
                "latest_pda_commitment":    "",
                "latest_agent_id":          "",
                "latest_attestation_type":  "",
                "latest_ts_ns":             0,
                "on_chain_confirmed":       False,
                "anchor_id":                -1,
                "timestamp":                _tac.time(),
            }
        return {
            "total_attestations":       int(total),
            "latest_pda_commitment":    str(row["pda_commitment"]),
            "latest_agent_id":          str(row["agent_id"]),
            "latest_attestation_type":  str(row["attestation_type"]),
            "latest_ts_ns":             int(row["ts_ns"]),
            "on_chain_confirmed":       bool(row["on_chain_confirmed"]),
            "anchor_id":                int(row["anchor_id"]),
            "timestamp":                _tac.time(),
        }

    def get_physical_data_attestation_history(
        self,
        agent_id: str = "",
        attestation_type: str = "",
        limit: int = 20,
    ) -> list[dict]:
        """Return last N PHYSICAL_DATA_ATTESTATION v1 records.

        Filterable by agent_id and/or attestation_type. DESC ts_ns
        ordering (newest first). Empty filter strings disable that
        filter. Mirrors get_agent_commit_history() pattern with the
        added attestation_type filter (Pass 2C Section 4.2 indexed).
        """
        cols = (
            "SELECT id, pda_commitment, hardware_data_hash, agent_id, "
            "       attestation_type, attestation_type_hash, ts_ns, "
            "       tx_hash, on_chain_confirmed, anchor_id, created_at "
            "FROM physical_data_attestation_log "
        )
        with self._conn() as conn:
            if agent_id and attestation_type:
                rows = conn.execute(
                    cols
                    + "WHERE agent_id = ? AND attestation_type = ? "
                      "ORDER BY ts_ns DESC LIMIT ?",
                    (str(agent_id), str(attestation_type), int(limit)),
                ).fetchall()
            elif agent_id:
                rows = conn.execute(
                    cols
                    + "WHERE agent_id = ? ORDER BY ts_ns DESC LIMIT ?",
                    (str(agent_id), int(limit)),
                ).fetchall()
            elif attestation_type:
                rows = conn.execute(
                    cols
                    + "WHERE attestation_type = ? "
                      "ORDER BY ts_ns DESC LIMIT ?",
                    (str(attestation_type), int(limit)),
                ).fetchall()
            else:
                rows = conn.execute(
                    cols + "ORDER BY ts_ns DESC LIMIT ?",
                    (int(limit),),
                ).fetchall()
        return [dict(r) for r in rows]

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
