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
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

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
            ]:
                conn.execute(
                    "INSERT OR IGNORE INTO schema_versions (phase, migration_name, applied_at)"
                    " VALUES (?, ?, ?)",
                    (_ph, _nm, time.time()),
                )

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
                         pitl_e4_cognitive_drift, pitl_humanity_prob)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                "ORDER BY created_at DESC LIMIT 1",
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
    ) -> int:
        """Insert a validation comparison record. Returns row id.

        divergence_reason (Phase 88): JSON string of non-nominal evidence fields that
        may explain why LLM and _rule_fallback disagreed. None for non-diverging records.
        """
        if self._consent_ledger_enabled:
            self._check_consent_gate(device_id, "insert_validation_record")
        now = time.time()
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO ruling_validation_log "
                "(ruling_id, device_id, llm_verdict, fallback_verdict, "
                "llm_confidence, fallback_confidence, divergence, divergence_reason, created_at) "
                "VALUES (?,?,?,?,?,?,?,?,?)",
                (ruling_id, device_id, llm_verdict, fallback_verdict,
                 llm_confidence, fallback_confidence, divergence, divergence_reason, now),
            )
            return cur.lastrowid

    def get_validation_summary(
        self, gate_n: int = 100, max_divergence_rate: float = 1.0
    ) -> dict:
        """Return validation statistics, consecutive_clean count, and window divergence rate.

        Phase 78: adds divergence_rate and divergence_rate_ok to the summary.

        Both consecutive_clean and divergence_rate are evaluated over the most recent
        gate_n rulings only (W1 mitigation — pre-gate divergences from early sessions
        do not permanently block the gate).

        gate_passed = (consecutive_clean >= gate_n) AND (divergence_rate <= max_divergence_rate)
        """
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
                "SELECT divergence FROM ruling_validation_log "
                "ORDER BY created_at DESC LIMIT ?",
                (gate_n,),
            ).fetchall()

        # consecutive_clean: leading non-divergent streak from most recent
        consecutive_clean = 0
        for row in window_rows:
            if row["divergence"] == 0:
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
    ) -> int:
        """Insert a tournament preflight run record (Phase 127).

        Returns the new row id.
        """
        with self._conn() as conn:
            cur = conn.execute(
                """INSERT INTO tournament_preflight_log
                   (separation_ok, l4_ok, gate_ok, cert_ok, audit_ok,
                    dual_gate_warned, epoch_window_warned, ioswarm_warned,
                    overall_pass, conditions_json, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    int(separation_ok), int(l4_ok), int(gate_ok),
                    int(cert_ok), int(audit_ok),
                    int(dual_gate_warned), int(epoch_window_warned), int(ioswarm_warned),
                    int(overall_pass), conditions_json,
                    time.time(),
                ),
            )
            return cur.lastrowid

    def get_tournament_preflight_status(self, limit: int = 5) -> "list[dict]":
        """Return recent tournament preflight run records, newest first (Phase 127)."""
        with self._conn() as conn:
            rows = conn.execute(
                """SELECT id, separation_ok, l4_ok, gate_ok, cert_ok, audit_ok,
                          dual_gate_warned, epoch_window_warned, ioswarm_warned,
                          overall_pass, conditions_json, created_at
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
                "created_at":            r[11],
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

    def _check_consent_gate(self, device_id: str, operation: str) -> None:
        """Raise ValueError + log if device has revoked consent or erasure_requested.

        Callers must check self._consent_ledger_enabled before calling this method.
        Fails open for unknown devices (no record = allowed) to avoid blocking new
        devices before consent is registered via POST /agent/register-consent.
        """
        status = self.get_consent_status(device_id)
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
                f"{operation!r} — reason: {reason} (GDPR Art.7/17, Phase 161 BP-002)."
            )

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
