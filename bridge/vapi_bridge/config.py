"""
VAPI Bridge Configuration — Environment-based with sensible defaults.

All config is read from environment variables (or .env file via python-dotenv).
"""

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


def _env(key: str, default: str = "") -> str:
    return os.environ.get(key, default)


def _env_int(key: str, default: int = 0) -> int:
    return int(os.environ.get(key, str(default)))


def _env_bool(key: str, default: bool = False) -> bool:
    return os.environ.get(key, str(default)).lower() in ("1", "true", "yes")


@dataclass(frozen=True)
class Config:
    """Immutable bridge configuration, loaded once at startup."""

    # --- IoTeX RPC ---
    iotex_rpc_url: str = field(
        default_factory=lambda: _env("IOTEX_RPC_URL", "https://babel-api.testnet.iotex.io")
    )
    chain_id: int = field(default_factory=lambda: _env_int("IOTEX_CHAIN_ID", 4690))

    # --- Contract addresses ---
    verifier_address: str = field(
        default_factory=lambda: _env("POAC_VERIFIER_ADDRESS", "")
    )
    bounty_market_address: str = field(
        default_factory=lambda: _env("BOUNTY_MARKET_ADDRESS", "")
    )
    device_registry_address: str = field(
        default_factory=lambda: _env("DEVICE_REGISTRY_ADDRESS", "")
    )

    # --- Bridge wallet ---
    bridge_private_key: str = field(
        default_factory=lambda: _env("BRIDGE_PRIVATE_KEY", "")
    )

    # --- MQTT ---
    mqtt_enabled: bool = field(
        default_factory=lambda: _env_bool("MQTT_ENABLED", True)
    )
    mqtt_broker: str = field(
        default_factory=lambda: _env("MQTT_BROKER", "localhost")
    )
    mqtt_port: int = field(default_factory=lambda: _env_int("MQTT_PORT", 1883))
    mqtt_topic_prefix: str = field(
        default_factory=lambda: _env("MQTT_TOPIC_PREFIX", "vapi/poac")
    )
    mqtt_username: str = field(default_factory=lambda: _env("MQTT_USERNAME", ""))
    mqtt_password: str = field(default_factory=lambda: _env("MQTT_PASSWORD", ""))

    # --- CoAP ---
    coap_enabled: bool = field(
        default_factory=lambda: _env_bool("COAP_ENABLED", False)
    )
    coap_bind: str = field(
        default_factory=lambda: _env("COAP_BIND", "0.0.0.0")
    )
    coap_port: int = field(default_factory=lambda: _env_int("COAP_PORT", 5683))

    # --- HTTP API / Dashboard ---
    http_enabled: bool = field(
        default_factory=lambda: _env_bool("HTTP_ENABLED", True)
    )
    http_host: str = field(
        default_factory=lambda: _env("HTTP_HOST", "0.0.0.0")
    )
    http_port: int = field(default_factory=lambda: _env_int("HTTP_PORT", 8080))

    # --- Batching ---
    batch_size: int = field(default_factory=lambda: _env_int("BATCH_SIZE", 10))
    batch_timeout_s: int = field(
        default_factory=lambda: _env_int("BATCH_TIMEOUT_S", 30)
    )

    # --- Retry ---
    max_retries: int = field(default_factory=lambda: _env_int("MAX_RETRIES", 5))
    retry_base_delay_s: float = field(
        default_factory=lambda: float(_env("RETRY_BASE_DELAY_S", "2.0"))
    )

    # --- Storage ---
    db_path: str = field(
        default_factory=lambda: _env(
            "DB_PATH",
            str(Path.home() / ".vapi" / "bridge.db"),
        )
    )

    # --- Logging ---
    log_level: str = field(
        default_factory=lambda: _env("LOG_LEVEL", "INFO")
    )

    # --- DualShock Edge transport ---
    dualshock_enabled: bool = field(
        default_factory=lambda: _env_bool("DUALSHOCK_ENABLED", False)
    )
    dualshock_record_interval_s: float = field(
        default_factory=lambda: float(_env("DUALSHOCK_RECORD_INTERVAL_S", "1.0"))
    )
    skill_oracle_address: str = field(
        default_factory=lambda: _env("SKILL_ORACLE_ADDRESS", "")
    )
    # Comma-separated active bounty IDs, e.g. "1001,1002"
    dualshock_active_bounties: str = field(
        default_factory=lambda: _env("DUALSHOCK_ACTIVE_BOUNTIES", "")
    )
    # Directory for persistent device keypair (default: ~/.vapi)
    dualshock_key_dir: str = field(
        default_factory=lambda: _env(
            "DUALSHOCK_KEY_DIR",
            str(Path.home() / ".vapi"),
        )
    )

    # --- Phase 4: ProgressAttestation + TeamProofAggregator ---
    progress_attestation_address: str = field(
        default_factory=lambda: _env("PROGRESS_ATTESTATION_ADDRESS", "")
    )
    team_aggregator_address: str = field(
        default_factory=lambda: _env("TEAM_AGGREGATOR_ADDRESS", "")
    )

    # --- Phase 7: Tiered Registration ---
    device_registration_tier: str = field(
        default_factory=lambda: _env("DEVICE_REGISTRATION_TIER", "Standard")
    )
    attestation_proof_hex: str = field(
        default_factory=lambda: _env("ATTESTATION_PROOF_HEX", "")
    )

    # --- Phase 8: Physical Input Trust Layer ---
    hid_oracle_enabled: bool = field(
        default_factory=lambda: _env_bool("HID_ORACLE_ENABLED", False)
    )
    hid_oracle_threshold: float = field(
        default_factory=lambda: float(_env("HID_ORACLE_THRESHOLD", "0.15"))
    )
    hid_oracle_gamepad_index: int = field(
        default_factory=lambda: _env_int("HID_ORACLE_GAMEPAD_INDEX", 0)
    )
    backend_cheat_enabled: bool = field(
        default_factory=lambda: _env_bool("BACKEND_CHEAT_ENABLED", False)
    )
    backend_cheat_model_path: str = field(
        default_factory=lambda: _env("BACKEND_CHEAT_MODEL_PATH", "")
    )

    # --- Phase 9: Hardware Signing Bridge ---
    identity_backend: str = field(
        default_factory=lambda: _env("IDENTITY_BACKEND", "software")
    )
    yubikey_piv_slot: str = field(
        default_factory=lambda: _env("YUBIKEY_PIV_SLOT", "9c")
    )
    atecc608_i2c_bus: int = field(
        default_factory=lambda: _env_int("ATECC608_I2C_BUS", 1)
    )

    # --- Phase 11: Bridge Key Security ---
    # --- Phase 14B: EWC + Preference model persistence paths ---
    ewc_model_path: str = field(
        default_factory=lambda: str(
            Path(os.getenv("VAPI_EWC_MODEL_PATH",
                           str(Path.home() / ".vapi" / "ewc_model.json")))
        )
    )
    preference_model_path: str = field(
        default_factory=lambda: str(
            Path(os.getenv("VAPI_PREF_MODEL_PATH",
                           str(Path.home() / ".vapi" / "pref_model.bin")))
        )
    )

    # "env"      — read BRIDGE_PRIVATE_KEY plaintext from env (default; dev/testnet only)
    # "keystore" — decrypt an Ethereum keystore JSON file at keystore_path (mainnet)
    bridge_private_key_source: str = field(
        default_factory=lambda: _env("BRIDGE_PRIVATE_KEY_SOURCE", "env")
    )
    # Absolute path to the Ethereum keystore JSON file (required when source="keystore")
    keystore_path: str = field(
        default_factory=lambda: _env("BRIDGE_KEYSTORE_PATH", "")
    )
    # Name of the env var that holds the keystore decryption password
    keystore_password_env: str = field(
        default_factory=lambda: _env("BRIDGE_KEYSTORE_PASSWORD_ENV", "BRIDGE_KEYSTORE_PASSWORD")
    )

    # --- Phase 22: PHG Registry (On-Chain Humanity Credential) ---
    phg_registry_address: str = field(
        default_factory=lambda: _env("PHG_REGISTRY_ADDRESS", "")
    )
    phg_checkpoint_interval: int = field(
        default_factory=lambda: _env_int("PHG_CHECKPOINT_INTERVAL", 10)
    )

    # --- Phase 23: Identity Continuity Registry ---
    identity_registry_address: str = field(
        default_factory=lambda: _env("IDENTITY_REGISTRY_ADDRESS", "")
    )
    continuity_threshold: float = field(
        default_factory=lambda: float(_env("CONTINUITY_THRESHOLD", "2.0"))
    )

    # --- Phase 25: Agent Intelligence & Chain Reconciler ---
    phg_humanity_weighted: bool = field(
        default_factory=lambda: _env_bool("PHG_HUMANITY_WEIGHTED", True)
    )
    reconciler_poll_interval: float = field(
        default_factory=lambda: float(_env("RECONCILER_POLL_INTERVAL", "30.0"))
    )

    # --- Phase 26: ZK PITL Session Proof ---
    pitl_session_registry_address: str = field(
        default_factory=lambda: _env("PITL_SESSION_REGISTRY_ADDRESS", "")
    )

    # --- Phase 62: PITLSessionRegistryV2 (Phase 62 C3 circuit) ---
    # When set, submit_pitl_proof routes to v2 instead of v1.
    pitl_session_registry_v2_address: str = field(
        default_factory=lambda: _env("PITL_SESSION_REGISTRY_V2_ADDRESS", "")
    )

    # --- Phase 28: PHG Credential (Soulbound On-Chain Credential Registry) ---
    phg_credential_address: str = field(
        default_factory=lambda: _env("PHG_CREDENTIAL_ADDRESS", "")
    )

    # --- Phase 29: Tournament Operator Gate API ---
    operator_api_key: str = field(
        default_factory=lambda: _env("OPERATOR_API_KEY", "")
    )
    """
    Shared secret for the /operator/gate API. If empty, operator endpoints
    return HTTP 503. Set to any secure random string (32+ bytes hex recommended).
    """

    # --- Phase 32: ProactiveMonitor poll interval ---
    monitor_poll_interval: float = field(
        default_factory=lambda: float(_env("MONITOR_POLL_INTERVAL", "60.0"))
    )

    # --- Phase 34: Federation Bus ---
    federation_peers: str = field(
        default_factory=lambda: _env("FEDERATION_PEERS", "")
    )
    federation_api_key: str = field(
        default_factory=lambda: _env("FEDERATION_API_KEY", "")
    )
    federation_poll_interval: float = field(
        default_factory=lambda: float(_env("FEDERATION_POLL_INTERVAL", "120.0"))
    )
    federated_threat_registry_address: str = field(
        default_factory=lambda: _env("FEDERATED_THREAT_REGISTRY_ADDRESS", "")
    )

    # --- Phase 35: Longitudinal Insight Synthesis ---
    synthesizer_poll_interval: float = field(
        default_factory=lambda: float(_env("SYNTHESIZER_POLL_INTERVAL", "21600.0"))
    )
    digest_retention_days: float = field(
        default_factory=lambda: float(_env("DIGEST_RETENTION_DAYS", "90.0"))
    )

    # --- Phase 36: Adaptive Adversarial Feedback ---
    adaptive_thresholds_enabled: bool = field(
        default_factory=lambda: _env("ADAPTIVE_THRESHOLDS_ENABLED", "true").lower() == "true"
    )
    policy_multiplier_floor: float = field(
        default_factory=lambda: float(_env("POLICY_MULTIPLIER_FLOOR", "0.5"))
    )
    rate_limit_per_minute: int = field(
        default_factory=lambda: int(_env("RATE_LIMIT_PER_MINUTE", "60"))
    )

    # --- L4 Calibration: Hardware-derived Mahalanobis thresholds ---
    # Calibrated from N=69 sessions (2 players, DualShock Edge USB, 2026-03-07).
    # anomaly  = mean+3sigma (99.7th pct) = 6.905  [converging — delta vs N=54 was +0.124]
    # continuity = mean+2sigma (95th pct)
    # Phase 57 recalibration (N=74, HIGH confidence, 12-feature space with jitter_var):
    #   anomaly=7.009, continuity=5.367 (+4.2% / +5.3% vs Phase 46 6.726/5.097)
    # Threshold rise is expected: adding press_timing_jitter_variance (feature 12) expands
    # the Mahalanobis distance distribution; 3σ compensates correctly.
    # Use scripts/threshold_calibrator.py to recalibrate after new sessions.
    l4_anomaly_threshold: float = field(
        default_factory=lambda: float(_env("L4_ANOMALY_THRESHOLD", "7.009"))
    )
    l4_continuity_threshold: float = field(
        default_factory=lambda: float(_env("L4_CONTINUITY_THRESHOLD", "5.367"))
    )

    # --- L5 Calibration: TemporalRhythmOracle thresholds ---
    # CV threshold: bot timing CV < 0.08 (adversarially calibrated; human 10th pct N=54: 0.789 -- 10x margin)
    # Entropy threshold: bot entropy < 1.0 bits (human 10th pct N=54: 1.259 -- safe margin)
    # NOTE: DO NOT raise CV/entropy thresholds to human percentiles -- that creates FP rate.
    # These thresholds are adversarially set far below the human floor, not from human data.
    l5_cv_threshold: float = field(
        default_factory=lambda: float(_env("L5_CV_THRESHOLD", "0.08"))
    )
    l5_entropy_threshold: float = field(
        default_factory=lambda: float(_env("L5_ENTROPY_THRESHOLD", "1.0"))
    )

    # --- Bluetooth transport thresholds ---
    # Defaults mirror USB calibrated values until BT-specific calibration (N>=50 BT sessions).
    # BT polling ~125-250 Hz vs USB 1000 Hz; 50-report windows cover 4x more wall-clock time.
    # Recalibrate: python scripts/threshold_calibrator.py sessions/bt/*.json
    bt_l4_anomaly_threshold: float = field(
        default_factory=lambda: float(
            _env("BT_L4_ANOMALY_THRESHOLD", _env("L4_ANOMALY_THRESHOLD", "6.905"))
        )
    )
    bt_l5_cv_threshold: float = field(
        default_factory=lambda: float(
            _env("BT_L5_CV_THRESHOLD", _env("L5_CV_THRESHOLD", "0.08"))
        )
    )
    bt_polling_rate_hz: float = field(
        default_factory=lambda: float(_env("BT_POLLING_RATE_HZ", "250.0"))
    )

    # --- Phase 37: TournamentGateV3 + Credential Enforcement + AlertRouter ---
    tournament_gate_v3_address: str = field(
        default_factory=lambda: _env("TOURNAMENT_GATE_V3_ADDRESS", "")
    )
    phg_credential_enforcement_enabled: bool = field(
        default_factory=lambda: _env("PHG_CREDENTIAL_ENFORCEMENT_ENABLED", "true").lower() == "true"
    )
    credential_enforcement_min_consecutive: int = field(
        default_factory=lambda: int(_env("CREDENTIAL_ENFORCEMENT_MIN_CONSECUTIVE", "2"))
    )
    credential_suspension_base_days: float = field(
        default_factory=lambda: float(_env("CREDENTIAL_SUSPENSION_BASE_DAYS", "7.0"))
    )
    credential_suspension_max_days: float = field(
        default_factory=lambda: float(_env("CREDENTIAL_SUSPENSION_MAX_DAYS", "28.0"))
    )
    alert_webhook_url: str = field(
        default_factory=lambda: _env("ALERT_WEBHOOK_URL", "")
    )
    alert_webhook_format: str = field(
        default_factory=lambda: _env("ALERT_WEBHOOK_FORMAT", "generic")
    )
    alert_severity_threshold: str = field(
        default_factory=lambda: _env("ALERT_SEVERITY_THRESHOLD", "medium")
    )
    agent_max_history_before_compress: int = field(
        default_factory=lambda: int(_env("AGENT_MAX_HISTORY_BEFORE_COMPRESS", "60"))
    )

    # --- Phase 19: Device Profile (Universal Controller Abstraction) ---
    device_profile_id: str = field(
        default_factory=lambda: _env("DEVICE_PROFILE_ID", "")
    )
    """
    Override controller auto-detection with an explicit profile slug.
    Examples: 'scuf_reflex_pro_v1', 'battle_beaver_dualshock_edge_v1'.
    Empty string (default) = auto-detect from HID VID/PID or fallback to
    'sony_dualshock_edge_v1'.
    """

    auto_detect_device: bool = field(
        default_factory=lambda: _env_bool("AUTO_DETECT_DEVICE", True)
    )
    """
    If True (default), enumerate connected HID devices to find a matching
    DeviceProfile via VID/PID lookup. Disable for headless CI or Docker
    environments where USB enumeration fails or is undesirable.
    """

    # --- Phase C: L6 Active Physical Challenge-Response ---
    l6_challenges_enabled: bool = field(
        default_factory=lambda: _env("L6_CHALLENGES_ENABLED", "false").lower() == "true"
    )
    l6_challenge_interval_ticks: int = field(
        default_factory=lambda: int(_env("L6_CHALLENGE_INTERVAL_TICKS", "300"))
    )
    l6_challenge_timeout_s: float = field(
        default_factory=lambda: float(_env("L6_CHALLENGE_TIMEOUT_S", "3.0"))
    )
    # Phase 42: L6 capture session metadata (set by l6_capture_session.py via PATCH /config)
    l6_capture_player_id: str = field(
        default_factory=lambda: _env("L6_CAPTURE_PLAYER_ID", "")
    )
    l6_capture_game_title: str = field(
        default_factory=lambda: _env("L6_CAPTURE_GAME_TITLE", "")
    )
    l6_capture_hw_session_ref: str = field(
        default_factory=lambda: _env("L6_CAPTURE_HW_SESSION_REF", "")
    )
    l6_capture_notes: str = field(
        default_factory=lambda: _env("L6_CAPTURE_NOTES", "")
    )

    # --- Phase 51: Game-Aware Profiling ---
    game_profile_id: str = field(
        default_factory=lambda: _env("GAME_PROFILE_ID", "")
    )
    """
    Active game profile slug. Overrides L5 button priority and enables L6-Passive.
    Example: 'ncaa_cfb_26'. Empty = default priority, no L6-Passive.
    Set via GAME_PROFILE_ID env var or bridge/.env.
    """

    # --- Phase 55: ioID Device Identity Registry ---
    ioid_registry_address: str = field(
        default_factory=lambda: _env("IOID_REGISTRY_ADDRESS", ""),
    )

    # --- Phase 56: ZK Tournament Passport ---
    tournament_passport_address: str = field(
        default_factory=lambda: _env("TOURNAMENT_PASSPORT_ADDRESS", ""),
    )

    # --- Phase 63: L6b Neuromuscular Reflex Layer ---
    l6b_enabled: bool = field(
        default_factory=lambda: _env("L6B_ENABLED", "false").lower() == "true"
    )
    """False by default — L6b disabled unless L6B_ENABLED=true env var set."""
    l6b_probe_interval_ticks: int = field(
        default_factory=lambda: int(_env("L6B_PROBE_INTERVAL_TICKS", "6750"))
    )
    """Ticks between L6b probe opportunities. Default 6750 ≈ 67.5s at 100Hz session loop."""
    l6b_accel_delta_threshold_lsb: float = field(
        default_factory=lambda: float(_env("L6B_ACCEL_DELTA_THRESHOLD_LSB", "500.0"))
    )
    """Min |accel_mag - pre_mean| (LSB) to count as a reflex impulse above noise floor."""
    l6b_human_min_ms: float = field(
        default_factory=lambda: float(_env("L6B_HUMAN_MIN_MS", "80.0"))
    )
    """Minimum latency (ms) to classify as HUMAN reflex (spinal reflex arc lower bound)."""
    l6b_human_max_ms: float = field(
        default_factory=lambda: float(_env("L6B_HUMAN_MAX_MS", "280.0"))
    )
    """Maximum latency (ms) to classify as HUMAN reflex (cortical loop upper bound)."""

    # --- Phase 62: Player Enrollment Ceremony ---
    enrollment_min_sessions: int = field(
        default_factory=lambda: _env_int("ENROLLMENT_MIN_SESSIONS", 10)
    )
    """Minimum NOMINAL PITL sessions required to qualify for PHGCredential mint."""
    enrollment_humanity_min: float = field(
        default_factory=lambda: float(_env("ENROLLMENT_HUMANITY_MIN", "0.60"))
    )
    """Minimum average humanity probability (across NOMINAL sessions) for enrollment."""

    # --- Phase 66: Ruling Enforcement Pipeline ---
    ruling_enforcement_enabled: bool = field(
        default_factory=lambda: _env_bool("RULING_ENFORCEMENT_ENABLED", True)
    )
    """Enable RulingEnforcementAgent background loop (Phase 66)."""
    ruling_streak_block_threshold: int = field(
        default_factory=lambda: _env_int("RULING_STREAK_BLOCK_THRESHOLD", 3)
    )
    """Consecutive BLOCK rulings before credential suspension fires."""
    ruling_registry_address: str = field(
        default_factory=lambda: _env("RULING_REGISTRY_ADDRESS", "")
    )
    """RulingRegistry.sol contract address (Phase 66). Empty = on-chain anchoring disabled."""
    ceremony_registry_address: str = field(
        default_factory=lambda: _env("CEREMONY_REGISTRY_ADDRESS", "")
    )
    """CeremonyRegistry.sol contract address (Phase 67). Empty = ceremony verification disabled."""

    # --- Phase 68-B: ZKVerifier local pre-verification ---
    pitl_vkey_path: str = field(
        default_factory=lambda: _env(
            "PITL_VKEY_PATH",
            "bridge/zk_artifacts/PitlSession_verification_key.json",
        )
    )
    """Path to PitlSessionProof verification_key.json for local Groth16 pre-verify (Phase 68)."""

    # --- Phase 68-C: SessionAdjudicator live mode ---
    agent_dry_run_mode: bool = field(
        default_factory=lambda: _env("AGENT_DRY_RUN", "true").lower() in ("1", "true", "yes")
    )
    """When True (default), SessionAdjudicator rulings are advisory only (dry_run=True).
    Set AGENT_DRY_RUN=false to enable live enforcement. Requires prior validation on ≥100 sessions."""

    # Phase 69 — Data Sovereignty Layer + DePIN Tokenomics
    curator_enabled: bool = field(
        default_factory=lambda: _env("CURATOR_ENABLED", "true").lower() in ("1", "true", "yes")
    )
    """Enable DataCuratorAgent poll loop (default: True). Set CURATOR_ENABLED=false to disable."""

    curator_oracle_publish: bool = field(
        default_factory=lambda: _env("CURATOR_ORACLE_PUBLISH", "false").lower() in ("1", "true", "yes")
    )
    """When True, DataCuratorAgent publishes oracle updates to IoTeX on-chain.
    Requires HUMANITY_ORACLE_ADDRESS + RULING_ORACLE_ADDRESS + PASSPORT_ORACLE_ADDRESS.
    Default: false (dry-run until addresses configured)."""

    humanity_oracle_address: str = field(
        default_factory=lambda: _env("HUMANITY_ORACLE_ADDRESS", "")
    )
    """HumanityOracle.sol contract address on IoTeX testnet (Phase 69)."""

    ruling_oracle_address: str = field(
        default_factory=lambda: _env("RULING_ORACLE_ADDRESS", "")
    )
    """RulingOracle.sol contract address on IoTeX testnet (Phase 69)."""

    passport_oracle_address: str = field(
        default_factory=lambda: _env("PASSPORT_ORACLE_ADDRESS", "")
    )
    """PassportOracle.sol contract address on IoTeX testnet (Phase 69)."""

    data_sovereignty_reg_address: str = field(
        default_factory=lambda: _env("DATA_SOVEREIGNTY_REG_ADDRESS", "")
    )
    """DataSovereigntyRegistry.sol contract address on IoTeX testnet (Phase 69)."""

    reward_distributor_address: str = field(
        default_factory=lambda: _env("REWARD_DISTRIBUTOR_ADDRESS", "")
    )
    """VAPIRewardDistributor.sol contract address on IoTeX testnet (Phase 69)."""

    data_marketplace_address: str = field(
        default_factory=lambda: _env("DATA_MARKETPLACE_ADDRESS", "")
    )
    """VAPIDataMarketplace.sol contract address on IoTeX testnet (Phase 69)."""

    governance_timelock_address: str = field(
        default_factory=lambda: _env("GOVERNANCE_TIMELOCK_ADDRESS", "")
    )
    """VAPIGovernanceTimelock.sol contract address on IoTeX testnet (Phase 70)."""

    protocol_lens_address: str = field(
        default_factory=lambda: _env("PROTOCOL_LENS_ADDRESS", "")
    )
    """VAPIProtocolLens.sol contract address on IoTeX testnet (Phase 70)."""

    # --- Phase 72: PHGCredential bridge-layer multi-sig ---
    suspension_multisig_threshold: int = field(
        default_factory=lambda: int(_env("SUSPENSION_MULTISIG_THRESHOLD", "1"))
    )
    """Number of confirmations required before a suspension proposal is executed on-chain.
    Default 1 = current behaviour (immediate execution).
    Set SUSPENSION_MULTISIG_THRESHOLD=2 to require a second operator confirmation.
    NOTE: PHGCredential.bridge is immutable post-deploy — this is a software safeguard,
    not cryptographic enforcement. Key separation must be operational, not just config."""

    # --- Phase 75: Validation gate + Ceremony Watchdog ---
    validation_divergence_threshold: float = field(
        default_factory=lambda: float(_env("VALIDATION_DIVERGENCE_THRESHOLD", "0.3"))
    )
    """Confidence delta above which a verdict mismatch is counted as a divergence.
    Default 0.3 — LLM and fallback must agree within 30% confidence or produce the same verdict."""

    validation_gate_n: int = field(
        default_factory=lambda: int(_env("VALIDATION_GATE_N", "100"))
    )
    """Number of consecutive clean (non-divergent) rulings required before the
    SessionAdjudicatorValidationAgent emits dry_run_gate_passed. Default 100."""

    validation_max_divergence_rate: float = field(
        default_factory=lambda: float(_env("VALIDATION_MAX_DIVERGENCE_RATE", "1.0"))
    )
    """Maximum allowed divergence rate in the trailing gate_n window before gate blocks.
    Default 1.0 (disabled — any rate passes). Set to e.g. 0.05 for ≤5% divergences
    over the last gate_n rulings. Evaluated alongside consecutive_clean (Phase 78).
    W1 mitigation: rate is computed over the trailing gate_n window only — pre-gate
    divergences from early sessions do not permanently block the gate."""

    ceremony_watchdog_enabled: bool = field(
        default_factory=lambda: _env_bool("CEREMONY_WATCHDOG_ENABLED", True)
    )
    """Enable CeremonyWatchdogAgent (Phase 75). Polls CeremonyRegistry every 5 minutes.
    On key rotation: invalidates _CEREMONY_CACHE and emits ceremony_key_rotated event."""

    # --- Phase 76: Ruling provenance anchors ---
    ruling_provenance_enabled: bool = field(
        default_factory=lambda: _env_bool("RULING_PROVENANCE_ENABLED", True)
    )
    """Enable RulingProvenanceAnchorAgent (Phase 76). Computes provenance hashes for all
    rulings and stores them in ruling_provenance_anchors table. Local-only by default."""

    ruling_provenance_publish_enabled: bool = field(
        default_factory=lambda: _env_bool("RULING_PROVENANCE_PUBLISH_ENABLED", False)
    )
    """Enable on-chain publication of provenance hashes via RulingRegistry.sol (Phase 76).
    Default False — costs gas per ruling. Only enable for live (dry_run=False) rulings.
    Requires RULING_ENFORCEMENT_ENABLED=true and a configured chain client."""

    # --- Phase 79: Live mode activation ---
    live_mode_auto_candidate: bool = field(
        default_factory=lambda: _env_bool("LIVE_MODE_AUTO_CANDIDATE", False)
    )
    """Enable live mode auto-candidate advisory (Phase 79). When True, LiveModeActivationAgent
    emits live_mode_candidate events when all 5 checklist conditions pass.
    Operator must still manually set AGENT_DRY_RUN=false."""

    # --- Phase 80: Federation broadcast ---
    federation_broadcast_enabled: bool = field(
        default_factory=lambda: _env_bool("FEDERATION_BROADCAST_ENABLED", False)
    )
    """Enable FederationBroadcastAgent (Phase 80). Broadcasts BLOCK rulings to peer bridges.
    Requires FEDERATION_BROADCAST_PEERS and FEDERATION_BROADCAST_API_KEY."""

    federation_broadcast_peers: str = field(
        default_factory=lambda: _env("FEDERATION_BROADCAST_PEERS", "")
    )
    """Comma-separated list of peer bridge base URLs for federation broadcast (Phase 80).
    Example: http://peer1:8080,http://peer2:8080"""

    federation_broadcast_api_key: str = field(
        default_factory=lambda: _env("FEDERATION_BROADCAST_API_KEY", "")
    )
    """Shared HMAC-SHA256 key for federation broadcast authentication (Phase 80)."""

    # --- Phase 81: Class J ML-bot detection ---
    class_j_detection_enabled: bool = field(
        default_factory=lambda: _env_bool("CLASS_J_DETECTION_ENABLED", True)
    )
    """Enable ClassJDetector ML-bot detection via temporal entropy variance (Phase 81).
    Tracks entropy variance per device; HIGH risk published to bus for SessionAdjudicator."""

    class_j_entropy_windows: int = field(
        default_factory=lambda: int(_env("CLASS_J_ENTROPY_WINDOWS", "10"))
    )
    """Number of session entropy windows to maintain per device for Class J detection (Phase 81).
    Variance computed over these windows; >= 2 required for assessment."""

    # --- Phase 82: Reactive Adjudication Interrupt rate limiting ---
    reactive_adjudication_rate_limit: int = field(
        default_factory=lambda: int(_env("REACTIVE_ADJUDICATION_RATE_LIMIT", "2"))
    )
    """Max reactive LLM calls per window (Phase 82 W1 mitigation). Default 2."""

    reactive_adjudication_window_seconds: int = field(
        default_factory=lambda: int(_env("REACTIVE_ADJUDICATION_WINDOW_SECONDS", "60"))
    )
    """Token-bucket window duration in seconds for reactive adjudication (Phase 82). Default 60."""

    # --- Phase 83: Agent Supervisor ---
    supervisor_enabled: bool = field(
        default_factory=lambda: _env_bool("SUPERVISOR_ENABLED", True)
    )
    """Enable AgentSupervisor fleet health monitor (Phase 83). Default True."""

    supervisor_stale_threshold_minutes: int = field(
        default_factory=lambda: int(_env("SUPERVISOR_STALE_THRESHOLD_MINUTES", "15"))
    )
    """Minutes of inactivity before an agent is marked STALE (Phase 83). Default 15."""

    # --- Phase 84: Live Mode Gate Completion ---
    gate_attestation_anchor_address: str = field(
        default_factory=lambda: _env("GATE_ATTESTATION_ANCHOR_ADDRESS", "")
    )
    """GateAttestationAnchor.sol contract address on IoTeX testnet (Phase 84)."""

    warm_up_batch_size: int = field(
        default_factory=lambda: int(_env("WARM_UP_BATCH_SIZE", "5"))
    )
    """Max devices to adjudicate per AdjudicationWarmUpRunner batch (Phase 84). Default 5."""

    # --- Phase 86: Synthetic Session Corpus Pipeline ---
    synthetic_corpus_enabled: bool = field(
        default_factory=lambda: _env("SYNTHETIC_CORPUS_ENABLED", "false").lower() == "true"
    )
    """Enable the synthetic validation corpus pipeline (Phase 86). Default false."""

    synthetic_corpus_size: int = field(
        default_factory=lambda: int(_env("SYNTHETIC_CORPUS_SIZE", "120"))
    )
    """Number of synthetic sessions per corpus run (Phase 86). Default 120 = gate_n target."""

    # --- Phase 89: Protocol Intelligence Synthesis Agent ---
    protocol_intelligence_enabled: bool = field(
        default_factory=lambda: _env("PROTOCOL_INTELLIGENCE_ENABLED", "true").lower()
        not in ("0", "false", "no")
    )
    """Enable ProtocolIntelligenceAgent (Phase 89). Default true."""

    # --- Phase 90: Shadow Enforcement Mode ---
    enforcement_shadow_mode: bool = field(
        default_factory=lambda: _env("ENFORCEMENT_SHADOW_MODE", "false").lower()
        in ("1", "true", "yes")
    )
    """Shadow enforcement: log BLOCK actions without calling PHGCredential.suspend() (Phase 90).
    Enables safe dry run of the enforcement pipeline against real sessions before go-live.
    Set ENFORCEMENT_SHADOW_MODE=true to activate. Default false."""

    # --- Phase 91: Divergence Triage Agent ---
    divergence_triage_enabled: bool = field(
        default_factory=lambda: _env("DIVERGENCE_TRIAGE_ENABLED", "true").lower()
        not in ("0", "false", "no")
    )
    """Enable DivergenceTriageAgent (Phase 91). Default true."""

    # --- Phase 92: Live Mode Activation Pipeline ---
    activation_pipeline_enabled: bool = field(
        default_factory=lambda: _env("ACTIVATION_PIPELINE_ENABLED", "true").lower()
        not in ("0", "false", "no")
    )
    """Enable LiveModeActivationPipeline audit logging (Phase 92). Default true."""

    # --- Phase 94: Class J Reactive Triage Loop ---
    triage_reactive_rate_limit: int = field(
        default_factory=lambda: int(_env("TRIAGE_REACTIVE_RATE_LIMIT", "1"))
    )
    """Max triage reactive adjudications per per-device window (Phase 94). Default 1."""

    triage_reactive_window_seconds: float = field(
        default_factory=lambda: float(_env("TRIAGE_REACTIVE_WINDOW_SECONDS", "3600.0"))
    )
    """Per-device token bucket window for triage reactive adjudications (Phase 94). Default 3600s."""

    enforcement_cert_ttl_s: int = field(
        default_factory=lambda: int(_env("ENFORCEMENT_CERT_TTL_S", "86400"))
    )
    """Enforcement Readiness Certificate TTL in seconds (Phase 96). Default 86400 (24h)."""

    epistemic_consensus_enabled: bool = field(
        default_factory=lambda: _env_bool("EPISTEMIC_CONSENSUS_ENABLED", "true")
    )
    """Enable multi-agent consensus check before live BLOCK execution (Phase 98). Default True."""

    epistemic_consensus_threshold: float = field(
        default_factory=lambda: float(_env("EPISTEMIC_CONSENSUS_THRESHOLD", "0.65"))
    )
    """Minimum consensus score for BLOCK execution in live mode (Phase 98). Default 0.65.

    Phase 147: raised from 0.60 → 0.65 to close W1 vulnerability.
    W1 MITIGATED (Phase 147): threshold=0.60 was exactly reachable by ClassJDetector alone
    (class_j=0.40 + supervisor=0.20 = 0.60). Raised to 0.65 — ClassJ+Supervisor sum=0.60
    cannot reach 0.65 without positive triage_score contribution.
    """

    # --- Phase 99A: AGaaS Foundation Token Stack ---
    vapi_token_address: str = field(
        default_factory=lambda: _env("VAPI_TOKEN_ADDRESS", "")
    )
    """VAPIToken.sol ERC-20 utility token address (IoTeX testnet). Empty until Phase 99A deploys."""

    operator_registry_address: str = field(
        default_factory=lambda: _env("OPERATOR_REGISTRY_ADDRESS", "")
    )
    """VAPIOperatorRegistry.sol staking/slashing address. Empty until Phase 99A deploys."""

    hardware_cert_registry_address: str = field(
        default_factory=lambda: _env("HARDWARE_CERT_REGISTRY_ADDRESS", "")
    )
    """VAPIHardwareCertRegistry.sol hardware certification address. Empty until Phase 99A deploys."""

    # --- Phase 99B: GSR Biometric Layer ---
    gsr_enabled: bool = field(
        default_factory=lambda: _env_bool("GSR_ENABLED", False)
    )
    """Enable L7 GSR biometric layer (Phase 99B). Default False.

    GSR_ENABLED=false is the correct default until N≥30 real calibration sessions per
    player are collected. Current N=0 real sessions. Hardware BOM: ~$30–45 (Ag/AgCl
    + ESP32-S3 + INA128). MockGSRGrip is always available for code-path testing.
    """

    gsr_sample_interval_s: int = field(
        default_factory=lambda: _env_int("GSR_SAMPLE_INTERVAL_S", 30)
    )
    """GSR sample collection interval in seconds (Phase 99B). Default 30s."""

    gsr_registry_address: str = field(
        default_factory=lambda: _env("GSR_REGISTRY_ADDRESS", "")
    )
    """VAPIGSRRegistry.sol address (Phase 99B). Empty until Phase 99B deploys."""

    w3bstream_project_id: str = field(
        default_factory=lambda: _env("W3BSTREAM_PROJECT_ID", "")
    )
    """W3bstream project ID for PoAC + GSR packet validation applets (Phase 99B)."""

    # --- Phase 99C: VHP Soulbound Token + LayerZero Bridge ---
    vhp_contract_address: str = field(
        default_factory=lambda: _env("VHP_CONTRACT_ADDRESS", "")
    )
    """VAPIVerifiedHumanProof.sol address (Phase 99C). Empty until Phase 99C deploys."""

    layerzero_endpoint_address: str = field(
        default_factory=lambda: _env("LAYERZERO_ENDPOINT_ADDRESS", "")
    )
    """LayerZero V2 endpoint address used by VAPIVerifiedHumanProofBridge (Phase 99C)."""

    # Phase 101: QuickSilver stIOTX collateral
    stiotx_token_address: str = field(
        default_factory=lambda: _env("STIOTX_TOKEN_ADDRESS", "")
    )
    """stIOTX (QuickSilver liquid staking token) ERC-20 address (Phase 101)."""

    quicksilver_collateral_address: str = field(
        default_factory=lambda: _env("QUICKSILVER_COLLATERAL_ADDRESS", "")
    )
    """VAPIQuickSilverCollateral.sol contract address (Phase 101). Empty until Phase 101 deploys."""

    # Phase 102: VHP Renewal Agent
    vhp_renewal_enabled: bool = field(
        default_factory=lambda: _env_bool("VHP_RENEWAL_ENABLED", True)
    )
    """Enable VHPRenewalAgent (14th agent). Polls every 6h to renew expiring VHP tokens."""

    vhp_renewal_warning_days: int = field(
        default_factory=lambda: _env_int("VHP_RENEWAL_WARNING_DAYS", 7)
    )
    """Renew VHPs expiring within this many days (Phase 102)."""

    # Phase 104 — Persistent Activation + PMI
    protocol_maturity_enabled: bool = field(
        default_factory=lambda: _env_bool("PROTOCOL_MATURITY_ENABLED", True)
    )
    """Enable ProtocolMaturityIndex tracking (Phase 104)."""

    activation_auto_restore: bool = field(
        default_factory=lambda: _env_bool("ACTIVATION_AUTO_RESTORE", True)
    )
    """Auto-restore dry_run=False on bridge restart if activation_committed=True (Phase 104 W1 mitigation)."""

    # Phase 105 — Epistemic Consensus Hardening
    epistemic_recommended_threshold: float = field(
        default_factory=lambda: float(_env("EPISTEMIC_RECOMMENDED_THRESHOLD", "0.65"))
    )
    """Recommended epistemic threshold (Phase 105). Auto-applied when PMI>=1 (Phase 104/105 synergy)."""

    epistemic_triage_prereq_required: bool = field(
        default_factory=lambda: _env_bool("EPISTEMIC_TRIAGE_PREREQ_REQUIRED", True)
    )
    """Require triage_score > 0.0 before epistemic vote runs (Phase 105 W1 mitigation; Phase 147: default True).

    Phase 147: changed from opt-in (False) to default-on (True) to close Phase 98 W1.
    Combined with threshold=0.65, prevents ClassJ-only BLOCK without triage involvement.
    Set EPISTEMIC_TRIAGE_PREREQ_REQUIRED=false to revert to Phase 105 opt-in behavior.
    """

    # --- Phase 108: Tournament Readiness Hardware Conditions ---
    separation_ratio_current: float = field(
        default_factory=lambda: float(_env("SEPARATION_RATIO_CURRENT", "1.261"))
    )
    """Inter-person L4 separation ratio. Phase 143 honest diagonal LOO result=1.261
    (N=11 touchpad_corners, 3 players; classification 63.6% — BLOCKER until ≥80%).
    Update ONLY after running scripts/interperson_separation_analyzer.py against real
    calibration sessions. Required >1.0 for tournament deployment."""

    # --- Phase 123: L4 Calibration Staleness Monitor ---
    live_feature_dim: int = field(
        default_factory=lambda: int(_env("LIVE_FEATURE_DIM", "13"))
    )
    """Current _BIO_FEATURE_DIM value in production (Phase 121 added index 12 → 13).
    Update when BiometricFeatureFrame adds or removes a feature slot.
    Staleness = live_feature_dim != calibration_feature_dim."""

    calibration_feature_dim: int = field(
        default_factory=lambda: int(_env("CALIBRATION_FEATURE_DIM", "12"))
    )
    """Feature dimension used in the last threshold_calibrator.py run.
    Phase 57: 12-feature space (N=74, anomaly=7.009, continuity=5.367).
    Phase 123 default=12; update to 13 after 13-feature recalibration run."""

    calibration_n_sessions: int = field(
        default_factory=lambda: int(_env("CALIBRATION_N_SESSIONS", "74"))
    )
    """Number of sessions used in the last threshold_calibrator.py run.
    Phase 57 baseline: N=74. Required >=74 for production-grade thresholds."""

    calibration_timestamp: float = field(
        default_factory=lambda: float(_env("CALIBRATION_TIMESTAMP", "0.0"))
    )
    """Unix epoch of the last threshold recalibration (0.0 = pre-tracking).
    Phase 57 calibration date: ~2025-03 (pre-epoch-tracking; set 0.0)."""

    # --- Phase 122: VHP Confidence Score Separation Ratio Multiplier ---
    confidence_multiplier_enabled: bool = field(
        default_factory=lambda: _env_bool("CONFIDENCE_MULTIPLIER_ENABLED", False)
    )
    """When True, multiplies VHP confidence_score by min(1.0, bt_strat_ratio) before
    minting. Reduces effective score when battery-stratified separation ratio < 1.0,
    ensuring the on-chain credential reflects actual identity-discrimination confidence.
    Infrastructure-first: False default until bt_strat_ratio confirmed stable."""

    confidence_multiplier_floor: float = field(
        default_factory=lambda: float(_env("CONFIDENCE_MULTIPLIER_FLOOR", "0.0"))
    )
    """Minimum multiplier applied to confidence_score (Phase 122).
    Default 0.0: score can be driven to zero at very low separation ratios.
    Set to e.g. 0.10 to preserve a minimum non-zero signal."""

    # --- Phase 124: L4 Per-Battery Threshold Track Registry ---
    l4_battery_threshold_enabled: bool = field(
        default_factory=lambda: _env_bool("L4_BATTERY_THRESHOLD_ENABLED", False)
    )
    """When True, per-battery L4 threshold tracks are available via the registry API.
    Infrastructure-first: False default. Activate after running threshold_calibrator.py
    per battery type against 13-feature corpus (Phase 123 recalibration prerequisite).
    W1 mitigation: insert bounds enforced [5.0–15.0] anomaly / [3.0–10.0] continuity."""

    touchpad_recapture_complete: bool = field(
        default_factory=lambda: _env_bool("TOUCHPAD_RECAPTURE_COMPLETE", False)
    )
    """Post-Phase-17 touchpad recapture complete (requires hardware + gameplay).
    Set True only after touch_position_variance calibration sessions confirm
    non-zero variance across all players."""

    # --- Phase 109A: ioSwarm Bridge Adapter ---
    ioswarm_enabled: bool = field(
        default_factory=lambda: _env_bool("IOSWARM_ENABLED", False)
    )
    """ioSwarm consensus integration enabled. Default False — infrastructure-only
    until live ioSwarm operator nodes are registered. NEVER enable without live nodes."""

    ioswarm_quorum_threshold: float = field(
        default_factory=lambda: float(os.environ.get("IOSWARM_QUORUM_THRESHOLD", "0.60"))
    )
    """General quorum threshold for non-BLOCK verdicts (Phase 109A default 0.60)."""

    ioswarm_block_quorum_threshold: float = field(
        default_factory=lambda: float(os.environ.get("IOSWARM_BLOCK_QUORUM_THRESHOLD", "0.67"))
    )
    """Block-specific quorum threshold — W1 mitigation. Must stay >= ioswarm_quorum_threshold."""

    ioswarm_node_count: int = field(
        default_factory=lambda: int(os.environ.get("IOSWARM_NODE_COUNT", "5"))
    )
    """Expected number of ioSwarm executor nodes (informational; quorum uses actual verdicts)."""

    ioswarm_endpoint: str = field(
        default_factory=lambda: os.environ.get("IOSWARM_ENDPOINT", "")
    )
    """ioSwarm API endpoint for task submission (empty = not configured)."""

    # Phase 109B — ioSwarm Renewal Coordinator
    ioswarm_renewal_enabled: bool = field(
        default_factory=lambda: _env_bool("IOSWARM_RENEWAL_ENABLED", False)
    )
    """Enable ioSwarm quorum guard for VHP renewal (Phase 109B). Default False (fail-open)."""

    ioswarm_renewal_min_quorum: int = field(
        default_factory=lambda: _env_int("IOSWARM_RENEWAL_MIN_QUORUM", 3)
    )
    """Minimum ioSwarm node count for renewal quorum (informational). Default 3."""

    # Phase 109C — ioSwarm Adjudication Coordinator
    ioswarm_adjudication_enabled: bool = field(
        default_factory=lambda: _env_bool("IOSWARM_ADJUDICATION_ENABLED", False)
    )
    """Enable ioSwarm quorum for ClassJ+Triage adjudication (Phase 109C). Default False."""

    ioswarm_classj_block_quorum: float = field(
        default_factory=lambda: float(os.environ.get("IOSWARM_CLASSJ_BLOCK_QUORUM", "0.67"))
    )
    """ClassJ block quorum threshold (enforcement standard; NOT 0.60 renewal). Default 0.67."""

    ioswarm_triage_block_quorum: float = field(
        default_factory=lambda: float(os.environ.get("IOSWARM_TRIAGE_BLOCK_QUORUM", "0.67"))
    )
    """Triage block quorum threshold (enforcement standard). Default 0.67."""

    # Phase 110 — ioSwarm VHP Mint Coordinator
    ioswarm_vhp_mint_enabled: bool = field(
        default_factory=lambda: _env_bool("IOSWARM_VHP_MINT_ENABLED", False)
    )
    """Enable ioSwarm quorum gate for VHP mint (fail-CLOSED). Default False."""

    ioswarm_vhp_mint_quorum: float = field(
        default_factory=lambda: float(os.environ.get("IOSWARM_VHP_MINT_QUORUM", "0.80"))
    )
    """VHP mint authorization quorum threshold (stricter than BLOCK_QUORUM=0.67). Default 0.80."""

    # Phase 111 — PoAd Registry
    poad_registry_enabled: bool = field(
        default_factory=lambda: _env_bool("POAD_REGISTRY_ENABLED", False)
    )
    """Enable PoAd hash computation and local registry. Default False (infrastructure-only)."""

    adjudication_registry_address: str = field(
        default_factory=lambda: os.environ.get("ADJUDICATION_REGISTRY_ADDRESS", "")
    )
    """AdjudicationRegistry.sol contract address for Phase 112 on-chain anchoring. Default empty."""

    # Phase 112 — PoAd On-Chain Anchoring
    poad_on_chain_enabled: bool = field(
        default_factory=lambda: _env_bool("POAD_ON_CHAIN_ENABLED", False)
    )
    """Enable on-chain anchoring of PoAd hashes via record_adjudication(). Default False."""

    # Phase 113 — Dual-Primitive Composability Gate
    dual_primitive_gate_address: str = field(
        default_factory=lambda: os.environ.get("DUAL_PRIMITIVE_GATE_ADDRESS", "")
    )
    """VAPIDualPrimitiveGate.sol contract address (Phase 113). Default empty."""

    dual_primitive_gate_enabled: bool = field(
        default_factory=lambda: _env_bool("DUAL_PRIMITIVE_GATE_ENABLED", False)
    )
    """Enable POST /agent/check-dual-eligibility endpoint. Default False (infrastructure-only)."""

    # Phase 115 — Epoch-Window Dual-Primitive Temporal Proof
    epoch_window_enabled: bool = field(
        default_factory=lambda: _env_bool("EPOCH_WINDOW_ENABLED", False)
    )
    """Enable epoch-window staleness check in 5th gate. Default False (infrastructure-only). Phase 115."""

    epoch_window_seconds: float = field(
        default_factory=lambda: float(os.environ.get("EPOCH_WINDOW_SECONDS", "86400"))
    )
    """Max PoAd age in seconds for epoch-window check. Default 86400 (24h). Phase 115."""

    # Phase 120 — Bluetooth Transport Foundation
    bt_transport_enabled: bool = field(
        default_factory=lambda: _env_bool("BT_TRANSPORT_ENABLED", False)
    )
    """Enable BLE transport for DualShock Edge at 250 Hz. Default False (infrastructure-only). Phase 120.
    W1 INVARIANT: BT sessions must NOT use USB L4 thresholds (7.009/5.367). Separate BT threshold
    track required (not yet calibrated). Activate only after BT-specific calibration complete."""

    bt_device_address: str = field(
        default_factory=lambda: _env("BT_DEVICE_ADDRESS", "")
    )
    """BLE device address for DualShock Edge (e.g. 'AA:BB:CC:DD:EE:FF'). Empty = auto-scan. Phase 120."""

    bt_sampling_rate_hz: int = field(
        default_factory=lambda: _env_int("BT_SAMPLING_RATE_HZ", 250)
    )
    """BLE sampling rate in Hz. Default 250 (DualShock Edge BLE notification rate). Phase 120."""

    swarm_operator_gate_address: str = field(
        default_factory=lambda: _env("SWARM_OPERATOR_GATE_ADDRESS", "")
    )
    """IoTeX address of VAPISwarmOperatorGate.sol (WIF-001 mitigation). Empty = gate not configured. Phase 130A."""

    # Phase 131 — IoSwarm Live Node Foundation
    ioswarm_node_urls: str = field(
        default_factory=lambda: _env("IOSWARM_NODE_URLS", "")
    )
    """Comma-separated list of ioSwarm live node base URLs (Phase 131).
    Empty string = emulator mode (uses IoSwarmNodeEmulator seed=109, zero behavior change).
    Example: IOSWARM_NODE_URLS=http://node1:8080,http://node2:8080"""

    ioswarm_node_timeout_seconds: float = field(
        default_factory=lambda: float(_env("IOSWARM_NODE_TIMEOUT_S", "5.0"))
    )
    """Per-node HTTP request timeout in seconds (Phase 131 W1 mitigation).
    Timed-out nodes are skipped; quorum computed from responding nodes only. Default 5.0."""

    ps5_compat_mode: bool = field(
        default_factory=lambda: _env("PS5_COMPAT_MODE", "false").lower() == "true"
    )
    """Phase 131B — PS5 coexistence mode (default False).
    When True: ALL HID output writes (set_led, haptic) are suppressed in _apply_feedback.
    Eliminates the USB instability that causes the PS5 to show reconnect notifications
    when DualShock Edge is simultaneously connected via USB (VAPI bridge) and BT (PS5).
    Trade-off: no LED colour or haptic feedback during gameplay.
    PoAC biometric capture is completely unaffected — read-only, zero data impact."""

    ioswarm_node_secret: str = field(
        default_factory=lambda: _env("IOSWARM_NODE_SECRET", "")
    )
    """Phase 132 — HMAC-SHA256 shared secret for ioSwarm node response verification.
    When ioswarm_hmac_enabled=True, the server signs responses and the client verifies.
    Default empty string = HMAC disabled."""

    ioswarm_hmac_enabled: bool = field(
        default_factory=lambda: _env("IOSWARM_HMAC_ENABLED", "false").lower() == "true"
    )
    """Phase 132 — Enable HMAC-SHA256 request/response authentication between bridge and
    ioSwarm live nodes. When True, X-VAPI-HMAC header required on all /evaluate responses.
    Default False = opt-in for testnet operators."""

    ioswarm_poad_auto_anchor_enabled: bool = field(
        default_factory=lambda: _env("IOSWARM_POAD_AUTO_ANCHOR_ENABLED", "false").lower() == "true"
    )
    """Phase 133 — Enable automatic PoAd on-chain anchoring when dual_veto fires.
    Default False = infrastructure-first, zero behavior change until enabled."""

    auto_separation_snapshot_enabled: bool = field(
        default_factory=lambda: _env_bool("AUTO_SEPARATION_SNAPSHOT_ENABLED", False)
    )
    """Phase 134 — After each live session, run analyze_interperson_separation.py as subprocess
    to write a separation ratio snapshot. Non-blocking; failure logged at DEBUG; never raises.
    Default False = infrastructure-first, zero behavior change until enabled."""

    auto_activate_on_breakthrough: bool = False
    """Phase 135 — PERMANENT INVARIANT: auto-activation on separation ratio breakthrough is
    NEVER permitted. TournamentActivationChainAgent fires one-shot notification only.
    This field is hard-coded False and MUST NOT be changed. Tournament activation requires
    explicit operator action via POST /agent/commit-activation."""

    audio_passthrough_enabled: bool = field(
        default_factory=lambda: _env_bool("AUDIO_PASSTHROUGH_ENABLED", True)
    )
    """Phase 136 — Restore game audio device if DualSense Edge captures Windows default
    output on USB connect. Uses IPolicyConfigVista COM vtable dispatch (no external deps).
    Default True = auto-restore system audio; set False to keep whatever Windows chose."""

    audio_device_preference: str = field(
        default_factory=lambda: _env("AUDIO_DEVICE_PREFERENCE", "system")
    )
    """Phase 136 — Audio routing preference: 'system' (restore Realtek/built-in when
    DualSense captures default), 'dualsense' (prefer DualSense headphone jack),
    'keep' (no change). Default 'system' = game audio plays through speakers/headphones."""

    agent_calibration_monitor_enabled: bool = field(
        default_factory=lambda: _env_bool("AGENT_CALIBRATION_MONITOR_ENABLED", True)
    )
    """Phase 148 — Enable AgentCalibrationIntegrityMonitor (ACIM, agent #18).
    Runs 16 agent self-tests every 15 minutes; cross-validates calibration invariants
    independently (W1 anti-single-validator mitigation). Default True."""

    mcp_server_enabled: bool = field(
        default_factory=lambda: _env_bool("MCP_SERVER_ENABLED", False)
    )
    """Phase 148 — Enable VAPI MCP (Model Context Protocol) server at /mcp.
    Exposes agent fleet calibration state as MCP resources for autoresearch sessions.
    Infrastructure-first: Default False = zero behavior change until enabled."""

    mcp_server_port: int = field(
        default_factory=lambda: int(_env("MCP_SERVER_PORT", "8081"))
    )
    """Phase 148 — Port for standalone MCP server if run independently.
    When mounted as sub-app, this is informational only. Default 8081."""

    min_touchpad_sessions_per_player: int = field(
        default_factory=lambda: int(_env("MIN_TOUCHPAD_SESSIONS_PER_PLAYER", "10"))
    )
    """Phase 150 — Minimum touchpad_corners sessions per player required for a defensible
    separation ratio claim (WIF-010 closure). Current state: P1=3, P2=4, P3=4 — all below
    target=10. defensible=True requires all players >= this threshold AND ratio > 1.0.
    Default 10 (per WIF-010 N-thin analysis)."""

    # --- Phase 152: Centroid Velocity Monitor ---
    centroid_velocity_monitor_enabled: bool = field(
        default_factory=lambda: _env("CENTROID_VELOCITY_MONITOR_ENABLED", "true").lower() == "true"
    )
    """Phase 152 — Enable per-probe biometric fingerprint drift rate monitoring.
    stagnant=True when velocity_per_day < 0.001 ratio/day (plateau threshold). Default True."""

    # --- Phase 153: SeparationRatioRegistry ---
    separation_ratio_registry_address: str = field(
        default_factory=lambda: _env("SEPARATION_RATIO_REGISTRY_ADDRESS", "")
    )
    """Phase 153 — SeparationRatioRegistry.sol address on IoTeX testnet. Empty = not deployed."""

    separation_ratio_on_chain_enabled: bool = field(
        default_factory=lambda: _env("SEPARATION_RATIO_ON_CHAIN_ENABLED", "false").lower() == "true"
    )
    """Phase 153 — Enable on-chain separation ratio commitment publishing. Default False."""

    # --- Phase 166: Configurable Defensibility Gate ---
    min_separation_ratio: float = field(
        default_factory=lambda: float(_env("MIN_SEPARATION_RATIO", "0.70"))
    )
    """Phase 166 — Minimum inter-person separation ratio for defensible=True.
    Lowered from hardcoded 1.0 to 0.70 (single shared-controller ceiling; all 3 players
    use the same physical DualShock Edge, removing hardware variance as discriminator).
    Configurable via MIN_SEPARATION_RATIO env. Default 0.70."""

    # --- Phase 199: Prototype Separation Gate + Tremor Resting Probe ---
    all_pairs_gate_enabled: bool = field(
        default_factory=lambda: _env("ALL_PAIRS_GATE_ENABLED", "true").lower() == "true"
    )
    """Phase 199 — When True (default/production), all_pairs_p0_ok requires all inter-player
    pair distances >= 1.0 (Phase 197 P0 gate).  When False (prototype mode), per-pair gate
    is disabled and overall_pass is determined by the global separation_ok check alone.
    Set ALL_PAIRS_GATE_ENABLED=false for known-proximity personal prototypes (e.g. P2/P3
    touchpad_corners distance=0.401 — structurally limited by protocol ceiling)."""

    tremor_resting_probe_enabled: bool = field(
        default_factory=lambda: _env("TREMOR_RESTING_PROBE_ENABLED", "false").lower() == "true"
    )
    """Phase 199 — Enable tremor_resting structured probe session type in the analysis
    pipeline.  Default False (infrastructure-first).  30-second still-hold capture
    isolates neurological tremor signal (tremor_peak_hz primary discriminator) from
    gameplay motion artifacts."""

    # --- Phase 154: Capture Stagnation Monitor ---
    capture_stagnation_threshold: float = field(
        default_factory=lambda: float(_env("CAPTURE_STAGNATION_THRESHOLD", "0.5"))
    )
    """Phase 154 — sessions/day rate below which capture is stagnant. Default 0.5/day."""

    capture_stagnation_window_days: float = field(
        default_factory=lambda: float(_env("CAPTURE_STAGNATION_WINDOW_DAYS", "7.0"))
    )
    """Phase 154 — Rolling window in days for capture rate computation. Default 7.0."""

    # --- Phase 155: Controller Hardware Intelligence ---
    controller_intelligence_enabled: bool = field(
        default_factory=lambda: _env("CONTROLLER_INTELLIGENCE_ENABLED", "true").lower() == "true"
    )
    """Phase 155 — Enable ControllerHardwareIntelligenceAgent (agent #19). Default True."""

    multi_controller_enabled: bool = field(
        default_factory=lambda: _env("MULTI_CONTROLLER_ENABLED", "false").lower() == "true"
    )
    """Phase 155 — Enable multi-controller routing (Xbox/Switch Standard tier). Default False.
    Never change without N>=50 per-controller calibration. DualShock Edge always active."""

    # --- Phase 156: Enrollment Auto-Guidance Agent ---
    enrollment_auto_guidance_enabled: bool = field(
        default_factory=lambda: _env("ENROLLMENT_AUTO_GUIDANCE_ENABLED", "true").lower() == "true"
    )
    """Phase 156 — Enable EnrollmentAutoGuidanceAgent (agent #20). Default True."""

    enrollment_guidance_poll_interval_s: int = field(
        default_factory=lambda: int(_env("ENROLLMENT_GUIDANCE_POLL_INTERVAL_S", "3600"))
    )
    """Phase 156 — Poll interval for EnrollmentAutoGuidanceAgent in seconds. Default 3600."""

    # --- Phase 157: Covariance Stability + FleetConsensusSnapshotAgent ---
    cov_stability_margin_np: float = field(
        default_factory=lambda: float(_env("COV_STABILITY_MARGIN_NP", "0.5"))
    )
    """Phase 157 — Safety margin around COV_MIN_RATIO=3.0 for regime transition warning.
    'transition_warning' fires when N/p in [3.0-margin, 3.0+margin]. Default 0.5."""

    fleet_consensus_enabled: bool = field(
        default_factory=lambda: _env("FLEET_CONSENSUS_ENABLED", "true").lower() == "true"
    )
    """Phase 157 — Enable FleetConsensusSnapshotAgent (agent #21). Default True."""

    fleet_consensus_snapshot_interval_s: int = field(
        default_factory=lambda: int(_env("FLEET_CONSENSUS_SNAPSHOT_INTERVAL_S", "1800"))
    )
    """Phase 157 — Poll interval for FleetConsensusSnapshotAgent in seconds. Default 1800."""

    # --- Phase 158: Class K HMAC Validation + PoHBG ---
    gsr_hmac_enabled: bool = field(
        default_factory=lambda: _env("GSR_HMAC_ENABLED", "false").lower() == "true"
    )
    """Phase 158 — Enable Class K HMAC-SHA256 frame authentication on incoming GSR frames.
    Infrastructure-first default False. Requires gsr_hmac_key_hex to be set."""

    gsr_hmac_key_hex: str = field(
        default_factory=lambda: _env("GSR_HMAC_KEY_HEX", "")
    )
    """Phase 158 — 64-char hex session HMAC key (32 bytes) for GSR frame authentication.
    Must be set when gsr_hmac_enabled=True. Empty string = not configured."""

    pohbg_enabled: bool = field(
        default_factory=lambda: _env("POHBG_ENABLED", "false").lower() == "true"
    )
    """Phase 158 — Enable PoHBG (Proof of Hardware Biometric Grip) hash computation.
    Infrastructure-first default False."""

    # --- Phase 159: BiometricPrivacyComplianceAgent (agent #22) ---
    biometric_privacy_enabled: bool = field(
        default_factory=lambda: _env("BIOMETRIC_PRIVACY_ENABLED", "true").lower() == "true"
    )
    """Phase 159 — Enable BiometricPrivacyComplianceAgent (agent #22). Default True."""

    bp001_half_life_days: float = field(
        default_factory=lambda: float(_env("BP001_HALF_LIFE_DAYS", "90.0"))
    )
    """Phase 159 — BP-001 biometric half-life in days. TBD decay λ = ln(2)/τ_half.
    Default 90 days per GDPR storage limitation guidance. IMMUTABLE per VAPI_INVARIANTS.md §6."""

    # --- Phase 180: Biometric Renewal Engine (WIF-029 W2 closure) ---
    renewal_enabled: bool = field(
        default_factory=lambda: _env("RENEWAL_ENABLED", "false").lower() == "true"
    )
    """Phase 180 — Enable Biometric Renewal Engine (WIF-029 W2 closure).
    Infrastructure-first default: False (dry_run=True on all renewal calls until enabled).
    When True and TTL is expired, POST /agent/renew-separation-ratio-commitment
    calls SeparationRatioRegistry.sol.renewCommit() to chain-link prev_commit_hash
    → new_commit_hash, extending tournament authorization by ttl_days.
    Renewal hash: SHA-256(prev_hash + ratio_str + N + N_consented + players + ttl_days + ts_ns)."""

    # --- Phase 179: ZK Ceremony Audit Gate (WIF-030 W1 closure) ---
    ceremony_audit_enabled: bool = field(
        default_factory=lambda: _env("CEREMONY_AUDIT_ENABLED", "false").lower() == "true"
    )
    """Phase 179 — Enable ZK ceremony multi-party audit gate (WIF-030 W1 closure).
    Infrastructure-first default: False (zero behavior change for existing flows).
    When True, TournamentActivationChainAgent checks that each VAPI ZK circuit has
    >= ceremony_audit_min_participants distinct ceremony participants recorded in
    ceremony_audit_log before accepting any ZK proof as tournament-valid.
    Single-operator Groth16 setup = toxic waste known to one party = forgeable proofs."""

    ceremony_audit_min_participants: int = field(
        default_factory=lambda: int(_env("CEREMONY_AUDIT_MIN_PARTICIPANTS", "3"))
    )
    """Phase 179 — Minimum distinct participant_address entries per ZK circuit (default 3).
    Groth16 MPC trusted-setup ceremony requires >= 3 external participants for safety.
    Each participant contributes randomness; a single compromised entry cannot forge proofs
    when N >= 3 (one honest participant is sufficient for a secure ceremony)."""

    # --- Phase 178: Biometric Credential TTL Gate (WIF-029 W1 closure) ---
    biometric_credential_ttl_days: float = field(
        default_factory=lambda: float(_env("BIOMETRIC_CREDENTIAL_TTL_DAYS", "90.0"))
    )
    """Phase 178 — TTL in days for on-chain separation ratio commitments (WIF-029 W1 closure).
    A SeparationRatioRegistry.sol commitment older than this value is biometrically stale:
    player touchpad tremor patterns measurably drift over 90 days (P1 non-stationarity).
    TournamentActivationChainAgent blocks authorization when age_days > biometric_credential_ttl_days.
    Default 90 days per DSGVO §35 purpose-limitation guidance. Matches BP-001 τ_half=90d constant."""

    # --- Phase 177: ProtocolMaturityScoringAgent (agent #26) ---
    protocol_maturity_enabled: bool = field(
        default_factory=lambda: _env("PROTOCOL_MATURITY_ENABLED", "true").lower() == "true"
    )
    """Phase 177 — Enable ProtocolMaturityScoringAgent (agent #26). Default True.
    Synthesizes 6 signals into maturity_score: ALPHA/BETA/PRODUCTION_CANDIDATE.
    PRODUCTION_CANDIDATE requires separation_ratio>1.0, chain integrity 1.0,
    consent corpus defensible, biometric freshness, all agents calibrated, enrollment done."""

    # --- Phase 176: PoACChainIntegrityMonitor (agent #25) ---
    chain_integrity_enabled: bool = field(
        default_factory=lambda: _env("CHAIN_INTEGRITY_ENABLED", "true").lower() == "true"
    )
    """Phase 176 — Enable PoACChainIntegrityMonitor (agent #25). Default True.
    Audits SHA-256 chain linkage across PoAC records.
    W1 mitigation: only aggregate counts exposed; broken record IDs never returned."""

    # --- Phase 175: AgeWeightedRatioPersistenceAgent (agent #24) ---
    age_weight_analysis_enabled: bool = field(
        default_factory=lambda: _env("AGE_WEIGHT_ANALYSIS_ENABLED", "true").lower() == "true"
    )
    """Phase 175 — Enable AgeWeightedRatioPersistenceAgent (agent #24). Default True.
    Persists temporal_drift_index from --session-age-weight analysis runs.
    temporal_drift_index > 0 signals P1 non-stationarity (old sessions inflate ratio)."""

    # --- Phase 160: Consent Ledger + Right-to-Erasure (BP-002 foundation) ---
    consent_ledger_enabled: bool = field(
        default_factory=lambda: _env("CONSENT_LEDGER_ENABLED", "true").lower() == "true"
    )
    """Phase 160 — Enable BP-002 Consent Ledger (WIF-018/019). Default True.
    When True, POST /agent/register-consent and POST /agent/revoke-consent are active.
    anonymize_device_records() enforces GDPR Art.17 on revocation."""

    # --- Phase 181: Consent-Bound Renewal Provenance (WIF-030 W2 + WIF-031 W1) ---
    ceremony_audit_registry_address: str = field(
        default_factory=lambda: _env("CEREMONY_AUDIT_REGISTRY_ADDRESS", "")
    )
    """Phase 181 — On-chain CeremonyAuditRegistry.sol address (WIF-030 W2 closure).
    Empty string = dry-run mode (no on-chain audit calls). Set CEREMONY_AUDIT_REGISTRY_ADDRESS
    to the deployed contract address to enable live on-chain ceremony verification.
    CeremonyAuditRegistry.sol LIVE 2026-04-10 at 0xb9164E6d74Dde1508df2a39b01d3702ACC8230C2."""

    # --- Phase 182: PersonaBreakDetectorAgent (WIF-028 deeper mitigation) ---
    persona_break_detection_enabled: bool = field(
        default_factory=lambda: _env("PERSONA_BREAK_DETECTION_ENABLED", "true").lower() == "true"
    )
    """Phase 182 — Enable PersonaBreakDetectorAgent (agent #27). Default True.
    Monitors LOO accuracy trend over last 5 separation_ratio_snapshots per player.
    persona_break_detected=True when mean_loo < persona_break_loo_threshold (0.20).
    Fires persona_break bus event; triggers re-enrollment urgency escalation."""

    persona_break_loo_threshold: float = field(
        default_factory=lambda: float(_env("PERSONA_BREAK_LOO_THRESHOLD", "0.20"))
    )
    """Phase 182 — LOO accuracy threshold below which a persona break is flagged (default 0.20).
    Below 33% random-baseline for 3-class classification — signals genuine centroid migration.
    P1 empirically measured at LOO=0% on latest N=20 corpus (2026-04-05)."""

    # --- Phase 183: MaturityElevationGateAgent (WIF-027 W2 closure) ---
    maturity_elevation_enabled: bool = field(
        default_factory=lambda: _env("MATURITY_ELEVATION_ENABLED", "true").lower() == "true"
    )
    """Phase 183 — Enable MaturityElevationGateAgent (agent #28). Default True.
    Reads 6-component protocol_maturity_log (Phase 177) and generates actionable
    elevation_plan per component (gap/action/estimated_sessions/blocking).
    elevation_available=True when gap_to_target < 0.05."""

    # --- Phase 185: ReEnrollmentAttestationAgent (WIF-032 W1 closure) ---
    reauth_attestation_enabled: bool = field(
        default_factory=lambda: _env("REAUTH_ATTESTATION_ENABLED", "true").lower() == "true"
    )
    """Phase 185 — Enable ReEnrollmentAttestationAgent (agent #29). Default True.
    HMAC-SHA256 attestation token gates re-enrollment window so adversary cannot
    trigger re-enrollment without operator secret (WIF-032 W1 closure)."""

    reauth_attestation_ttl_days: float = field(
        default_factory=lambda: float(_env("REAUTH_ATTESTATION_TTL_DAYS", "7.0"))
    )
    """Phase 185 — Attestation token TTL in days (default 7.0). Tokens expire automatically.
    expire_stale_attestations() deactivates expired rows on each agent cycle."""

    reauth_attestation_secret: str = field(
        default_factory=lambda: _env("REAUTH_ATTESTATION_SECRET", "")
    )
    """Phase 185 — Operator HMAC-SHA256 signing secret (empty = SHA-256 test-mode fallback).
    Set REAUTH_ATTESTATION_SECRET to a strong random string in production. Empty default
    prevents accidental HMAC activation; SHA-256 fallback is weaker but non-blocking."""

    # --- Phase 186: AttestationBoundRenewalAgent (WIF-032 W2 closure) ---
    attestation_bound_renewal_enabled: bool = field(
        default_factory=lambda: _env("ATTESTATION_BOUND_RENEWAL_ENABLED", "false").lower() == "true"
    )
    """Phase 186 — Enable AttestationBoundRenewalAgent (agent #30). Default False (infra-first).
    When True, every separation-ratio renewal must have a valid active HMAC attestation
    from Phase 185 ReEnrollmentAttestationAgent. Adversary cannot forge without operator secret."""

    # --- Phase 187: AttestationOpSecAdvisorAgent + VHPReenrollmentBadge ---
    mempool_opsec_enabled: bool = field(
        default_factory=lambda: _env("MEMPOOL_OPSEC_ENABLED", "false").lower() == "true"
    )
    """Phase 187 — Enable mempool OpSec advisor (WIF-033 W1 closure). Default False (infra-first).
    When True, AttestationOpSecAdvisorAgent monitors active attestations and flags HIGH risk
    when attestation_bound_renewal_enabled=True and active_attestations > 0 simultaneously
    (timing disclosure vector: adversary monitors IoTeX mempool for registerAttestation() tx)."""

    reenrollment_badge_enabled: bool = field(
        default_factory=lambda: _env("REENROLLMENT_BADGE_ENABLED", "false").lower() == "true"
    )
    """Phase 187 — Enable VHPReenrollmentBadge.sol soulbound minting. Default False (infra-first).
    ERC-4671 soulbound badge minted after each successful re-enrollment attestation cycle.
    Anti-replay: attestationUsed mapping prevents double-minting per attestation hash."""

    vhp_reenrollment_badge_address: str = field(
        default_factory=lambda: _env("VHP_REENROLLMENT_BADGE_ADDRESS", "")
    )
    """Phase 187 — VHPReenrollmentBadge.sol deployed address. Empty = dry-run.
    LIVE 2026-04-10 at 0x42E7A25d0E5667BBae45e5cF33a6e2CC6E42d45C (IoTeX testnet 4690)."""

    # --- Phase 188: BiometricStationarityOracleAgent ---
    biometric_stationarity_enabled: bool = field(
        default_factory=lambda: _env("BIOMETRIC_STATIONARITY_ENABLED", "false").lower() == "true"
    )
    """Phase 188 — Enable BiometricStationarityOracleAgent (agent #32). Default False (infra-first).
    Closes P1 genuine-drift vs adversarial-window ambiguity. Discriminator: Agent 25
    chain_integrity_score — genuine drift leaves PoAC chain intact; adversarial window
    exploitation produces chain anomalies coincident with drift."""

    stationarity_adversarial_threshold: float = field(
        default_factory=lambda: float(_env("STATIONARITY_ADVERSARIAL_THRESHOLD", "0.60"))
    )
    """Phase 188 — P(adversarial_window) above which ADVERSARIAL_WINDOW verdict fires (default 0.60).
    Calibrated against Phase 173 corpus: genuine drift P1 chain_integrity_score remains near 1.0
    while adversarial window exploitation produces chain anomalies (score < 0.95 floor)."""

    stationarity_chain_integrity_floor: float = field(
        default_factory=lambda: float(_env("STATIONARITY_CHAIN_INTEGRITY_FLOOR", "0.95"))
    )
    """Phase 188 — Minimum chain_integrity_score below which ADVERSARIAL_WINDOW risk escalates.
    Agent 25 (PoACChainIntegrityMonitor) provides this score; score < 0.95 coincident with
    large trend_velocity is the key discriminating signal for adversarial window exploitation."""

    # --- Phase 189: ProtocolIntelligenceRecordAgent ---
    pir_chain_enabled: bool = field(
        default_factory=lambda: _env("PIR_CHAIN_ENABLED", "false").lower() == "true"
    )
    """Phase 189 — Enable ProtocolIntelligenceRecordAgent (agent #33). Default False (infra-first).
    SHA-256 hash-linked PIR chain analogous to PoAC record chain.
    pir_hash = SHA-256(prev_pir_hash + cycle + phase + wif_hash + forecast + score + ts).
    Genesis PIR-0010 anchors Cycle 10/WIF-033/Phase 187 as chain origin."""

    pir_anchor_interval: int = field(
        default_factory=lambda: int(_env("PIR_ANCHOR_INTERVAL", "10"))
    )
    """Phase 189 — AutoResearch cycle interval between PIR anchor writes (default 10).
    Every 10th cycle produces a new PIR record linked into the hash chain.
    insert_pir() raises ValueError on UNIQUE duplicate (anti-replay invariant)."""

    # --- Phase 190: LivePresenceSignalingAgent ---
    live_presence_signaling_enabled: bool = field(
        default_factory=lambda: _env("LIVE_PRESENCE_SIGNALING_ENABLED", "false").lower() == "true"
    )
    """Phase 190 — Enable LivePresenceSignalingAgent (agent #34). Default False (infra-first).
    Bidirectional VAPI presence channel: dual-path routing via controller LED+haptic
    (ps5_compat_mode aware) + ANSI terminal color stream (always active when enabled).
    Solves 'nothing happens during gameplay' gap from Phase 131B ps5_compat_mode suppression."""

    live_presence_haptic_enabled: bool = field(
        default_factory=lambda: _env("LIVE_PRESENCE_HAPTIC_ENABLED", "true").lower() == "true"
    )
    """Phase 190 — Enable haptic feedback in LivePresenceSignalingAgent (default True).
    When True and ps5_compat_mode=False, haptic pulses accompany LED color signals.
    HARD_CHEAT_DETECTED: 3×200ms, CERTIFY: 1×100ms, BIOMETRIC_ANOMALY: 1×80ms."""

    live_presence_chain_milestone_interval: int = field(
        default_factory=lambda: int(_env("LIVE_PRESENCE_CHAIN_MILESTONE_INTERVAL", "100"))
    )
    """Phase 190 — PoAC record count interval that triggers a CHAIN_MILESTONE signal (default 100).
    Every 100th PoAC record produces a Cyan(0,255,200) LED flash + no haptic.
    Provides operator visual confirmation that the PoAC chain is progressing."""

    # --- Phase 191: Threat Succession Protocol (TSP) ---
    tsp_enabled: bool = field(
        default_factory=lambda: _env("TSP_ENABLED", "true").lower() == "true"
    )
    """Phase 191 — Enable Threat Succession Protocol (TSP). Default True.
    Wires threat_forecast_accuracy_component (PIR harness_score, weight=0.07) and
    biometric_stationarity_component (BSO confidence, weight=0.04) into 8-component
    maturity_score v2 formula. AutoResearch Cycle 11 threat: WIF-034 PIR chain integrity attack."""

    # --- Phase 192: DataCuratorAgent (Agent #35) ---
    # Task 1: Provenance DAG Engine
    data_provenance_dag_enabled: bool = field(
        default_factory=lambda: _env("DATA_PROVENANCE_DAG_ENABLED", "true").lower() == "true"
    )
    """Phase 192 — Enable Provenance DAG Engine. Tracks causal lineage from calibration
    session to VHP badge as a directed acyclic graph. Default True."""

    provenance_max_chain_depth: int = field(
        default_factory=lambda: int(_env("PROVENANCE_MAX_CHAIN_DEPTH", "20"))
    )
    """Phase 192 — Maximum hop depth for provenance chain traversal (prevents infinite
    loop on corrupt graph). Default 20."""

    # Task 2: Corpus Entropy Monitor
    corpus_entropy_enabled: bool = field(
        default_factory=lambda: _env("CORPUS_ENTROPY_ENABLED", "true").lower() == "true"
    )
    """Phase 192 — Enable Corpus Entropy Monitor. Tracks Shannon entropy of the 13-dim
    feature space per player. Score < 1.5 = CLUSTERING_WARNING. Default True."""

    corpus_entropy_warning_threshold: float = field(
        default_factory=lambda: float(_env("CORPUS_ENTROPY_WARNING_THRESHOLD", "1.5"))
    )
    """Phase 192 — Corpus entropy score below this threshold triggers CLUSTERING_WARNING.
    Range: 0.0 (all sessions identical) to 3.32 (uniform). Default 1.5."""

    corpus_entropy_poll_interval: int = field(
        default_factory=lambda: int(_env("CORPUS_ENTROPY_POLL_INTERVAL", "3600"))
    )
    """Phase 192 — Corpus entropy recompute interval in seconds. Default 3600 (1 hour)."""

    # Task 4: Federated Corpus Quality Aggregator
    federated_corpus_quality_enabled: bool = field(
        default_factory=lambda: _env("FEDERATED_CORPUS_QUALITY_ENABLED", "false").lower() == "true"
    )
    """Phase 192 — Enable Federated Corpus Quality Aggregator. Off until 2+ bridges active.
    Publishes anonymized corpus stats (N, entropy, stationarity, velocity) to federation bus.
    Never sends raw biometric data (BP-007). Default False."""

    corpus_outlier_sigma_threshold: float = field(
        default_factory=lambda: float(_env("CORPUS_OUTLIER_SIGMA_THRESHOLD", "2.0"))
    )
    """Phase 192 — Flag local corpus as outlier if > N sigma from federation mean.
    Default 2.0."""

    # Task 5: Cross-Feature Temporal Correlation Engine
    correlation_engine_enabled: bool = field(
        default_factory=lambda: _env("CORRELATION_ENGINE_ENABLED", "true").lower() == "true"
    )
    """Phase 192 — Enable Cross-Feature Temporal Correlation Engine. Computes 13x13
    per-player feature correlation matrices and Frobenius separability distances.
    Default True."""

    correlation_separability_threshold: float = field(
        default_factory=lambda: float(_env("CORRELATION_SEPARABILITY_THRESHOLD", "0.5"))
    )
    """Phase 192 — Frobenius distance floor for correlation_separable=True.
    A player pair with frobenius_distance > 0.5 is separable by correlation structure.
    Default 0.5."""

    correlation_high_pair_threshold: float = field(
        default_factory=lambda: float(_env("CORRELATION_HIGH_PAIR_THRESHOLD", "0.7"))
    )
    """Phase 192 — |corr| above this threshold is logged as a high-correlation pair.
    Default 0.7."""

    # Task 7: Session Contribution Weight Table
    contribution_weight_enabled: bool = field(
        default_factory=lambda: _env("CONTRIBUTION_WEIGHT_ENABLED", "true").lower() == "true"
    )
    """Phase 192 — Enable Session Contribution Weight Table. Computes TBD-decay x
    type_multiplier x stationarity_multiplier per session. FROZEN: lambda=ln(2)/90 (BP-001).
    Default True."""

    # --- Phase 193: FleetSignalCoherenceAgent (Agent #36) ---
    fleet_coherence_enabled: bool = field(
        default_factory=lambda: _env("FLEET_COHERENCE_ENABLED", "true").lower() == "true"
    )
    """Phase 193 — Enable FleetSignalCoherenceAgent. Polls every 900s. Detects when
    agents are individually correct but collectively contradictory. Three failure modes:
    CONTRADICTION, ORPHAN, INVERSION. Default True."""

    coherence_poll_interval_seconds: int = field(
        default_factory=lambda: int(_env("COHERENCE_POLL_INTERVAL_SECONDS", "900"))
    )
    """Phase 193 — Poll interval for FleetSignalCoherenceAgent in seconds. Default 900 (15 min)."""

    coherence_promote_threshold: int = field(
        default_factory=lambda: int(_env("COHERENCE_PROMOTE_THRESHOLD", "3"))
    )
    """Phase 193 — Number of occurrences before a coherence failure is auto-promoted
    to a WIF entry in VAPI_WHAT_IF.md. Default 3."""

    coherence_alert_on_critical: bool = field(
        default_factory=lambda: _env("COHERENCE_ALERT_ON_CRITICAL", "true").lower() == "true"
    )
    """Phase 193 — Publish to alert bus channel on CRITICAL coherence failures. Default True."""

    coherence_alert_on_high: bool = field(
        default_factory=lambda: _env("COHERENCE_ALERT_ON_HIGH", "true").lower() == "true"
    )
    """Phase 193 — Publish to alert bus channel on HIGH coherence failures. Default True."""

    coherence_alert_on_medium: bool = field(
        default_factory=lambda: _env("COHERENCE_ALERT_ON_MEDIUM", "false").lower() == "true"
    )
    """Phase 193 — Publish to alert bus channel on MEDIUM coherence failures. Default False
    (advisory only — reduce noise; MEDIUM contradictions logged to wiki but not alerted)."""

    def validate(self) -> list[str]:
        """Return list of configuration errors (empty = valid)."""
        errors = []
        if not self.verifier_address:
            errors.append("POAC_VERIFIER_ADDRESS is required")
        # Key validation depends on source
        source = getattr(self, "bridge_private_key_source", "env")
        if source == "keystore":
            if not getattr(self, "keystore_path", ""):
                errors.append("BRIDGE_KEYSTORE_PATH is required when BRIDGE_PRIVATE_KEY_SOURCE=keystore")
        else:
            if not self.bridge_private_key:
                errors.append("BRIDGE_PRIVATE_KEY is required")
        if not any([self.mqtt_enabled, self.coap_enabled,
                    self.http_enabled, self.dualshock_enabled]):
            errors.append("At least one transport must be enabled")
        return errors
