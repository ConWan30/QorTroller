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
        default_factory=lambda: float(_env("EPISTEMIC_CONSENSUS_THRESHOLD", "0.60"))
    )
    """Minimum consensus score for BLOCK execution in live mode (Phase 98). Default 0.60.

    W1 VULNERABILITY: threshold=0.60 is exactly reachable by ClassJDetector alone
    (class_j=0.40 + supervisor=0.20 = 0.60). An adversary who suppresses triage
    escalation across sessions reduces the 3-agent design to a 1-agent gate.
    Operators in sustained adversarial deployments should raise this to 0.65.
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
        default_factory=lambda: _env_bool("EPISTEMIC_TRIAGE_PREREQ_REQUIRED", False)
    )
    """Require triage_score > 0.0 before epistemic vote runs (Phase 105 W1 mitigation, opt-in)."""

    # --- Phase 108: Tournament Readiness Hardware Conditions ---
    separation_ratio_current: float = field(
        default_factory=lambda: float(_env("SEPARATION_RATIO_CURRENT", "0.362"))
    )
    """Inter-person L4 separation ratio. Phase 57 N=74 empirical baseline=0.362.
    Update ONLY after running scripts/interperson_separation_analyzer.py against real
    calibration sessions. Required >1.0 for tournament deployment."""

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
