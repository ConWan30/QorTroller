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


def _env_float(key: str, default: float = 0.0) -> float:
    return float(os.environ.get(key, str(default)))


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

    # --- Phase 235.x-STABILITY (2026-05-07): bridge zombie root cause fix ---
    uvicorn_timeout_keep_alive_s: int = field(
        default_factory=lambda: _env_int("UVICORN_TIMEOUT_KEEP_ALIVE_S", 120)
    )
    """Phase 235.x-STABILITY — uvicorn HTTP keep-alive timeout (seconds).
    Default raised from uvicorn's 5s to 120s. Under frontend polling load
    (capture-health every 3s, grind-chain 5s, drift-log 30s) the 5s default
    causes constant connection cycling, triggering Windows asyncio
    _ProactorBasePipeTransport._call_connection_lost crashes (the chronic
    'bridge zombie' pattern). 120s amortizes connection cost dramatically."""

    dualshock_poll_timeout_multiplier: int = field(
        default_factory=lambda: _env_int("DUALSHOCK_POLL_TIMEOUT_MULTIPLIER", 10)
    )
    """Phase 235.x-STABILITY — multiplier on dualshock_record_interval_s
    used as the _poll_frames asyncio.wait_for timeout. Default raised
    4x → 10x. Empirical finding: 4× was too aggressive for real Windows
    USB stacks; transient 1-3s USB hiccups triggered timeouts that
    compounded into event-loop pressure (each timeout schedules
    signal_disconnect + retries). 10x tolerates real hiccup windows
    without triggering the watchdog zombie cascade."""

    # --- Phase 235.x-STABILITY-2 (2026-05-08): asyncio loop-block instrumentation (WIF-064) ---
    asyncio_debug_enabled: bool = field(
        default_factory=lambda: _env_bool("ASYNCIO_DEBUG_ENABLED", False)
    )
    """Phase 235.x-STABILITY-2 — Enable asyncio debug mode. When True, sets
    loop.set_debug(True) which logs slow callbacks via the configured slow
    callback duration. Default OFF; opt-in for diagnostic sessions only.
    Has minor performance overhead (~5%) when enabled."""

    asyncio_slow_callback_threshold_s: float = field(
        default_factory=lambda: float(_env("ASYNCIO_SLOW_CALLBACK_THRESHOLD_S", "1.0"))
    )
    """Phase 235.x-STABILITY-2 — Threshold (seconds) above which asyncio logs
    a "slow callback" warning identifying the function that blocked the loop.
    Default raised from asyncio's 0.1s default to 1.0s — anything above 1s
    on the event loop thread is the WIF-064 zombie pattern signature. Lower
    to 0.5s when actively diagnosing; raise above 1.0s for noisy environments."""

    # --- Phase 235.x-STABILITY-3 (2026-05-08): loop health monitor (WIF-065 closure) ---
    loop_health_monitor_enabled: bool = field(
        default_factory=lambda: _env_bool("LOOP_HEALTH_MONITOR_ENABLED", True)
    )
    """Phase 235.x-STABILITY-3 — Enable independent heartbeat task that
    detects asyncio event loop starvation regardless of asyncio's debug mode.
    asyncio's built-in slow_callback_duration warning is gated by
    loop.set_debug(True) which we keep OFF in production due to ~5% perf
    overhead. The heartbeat task measures its own scheduling latency and
    logs WARNING when expected sleep time is exceeded by more than the
    threshold. Default ON; opt-out via LOOP_HEALTH_MONITOR_ENABLED=false."""

    loop_health_check_interval_s: float = field(
        default_factory=lambda: float(_env("LOOP_HEALTH_CHECK_INTERVAL_S", "2.0"))
    )
    """Phase 235.x-STABILITY-3 — Heartbeat cadence (seconds). Task sleeps
    this long between checks. Lower = finer detection but more wakeups.
    2.0s default = good balance for catching ~12-30s zombie windows."""

    loop_health_starvation_threshold_s: float = field(
        default_factory=lambda: float(_env("LOOP_HEALTH_STARVATION_THRESHOLD_S", "1.0"))
    )
    """Phase 235.x-STABILITY-3 — Excess time (seconds) above the heartbeat
    interval that triggers a STARVATION warning. If sleep(2.0) actually
    took 4.0s, excess is 2.0s — fires warning if > threshold. 1.0s default
    matches WIF-064 zombie pattern signature (12-30s blocks, much higher
    than 1s)."""

    # --- Phase 235.x-STABILITY-4 (2026-05-09): on_record sync chain offload (WIF-066 closure) ---
    loop_persist_to_thread_enabled: bool = field(
        default_factory=lambda: _env_bool("LOOP_PERSIST_TO_THREAD_ENABLED", True)
    )
    """Phase 235.x-STABILITY-4 — Move on_record's heavy sync work
    (ECDSA-P256 signature verify + 3 SQLite writes + PITL meta apply)
    to a worker thread via asyncio.to_thread. Empirically validated
    2026-05-08 to address 60+ STARVATION events/13 min attributed to the
    per-record sync chain (WIF-066 real-controller bisection run).
    Default ON; opt-out via LOOP_PERSIST_TO_THREAD_ENABLED=false for A/B
    comparison or rollback. Per-source record ordering is preserved by
    sequential await in the caller's loop (DualShockTransport._session_loop
    awaits _dispatch which awaits on_record one at a time per source)."""

    # --- Phase 235.x-STABILITY-5 (2026-05-09): _resolve_pubkey miss path offload ---
    loop_resolve_pubkey_to_thread_enabled: bool = field(
        default_factory=lambda: _env_bool("LOOP_RESOLVE_PUBKEY_TO_THREAD_ENABLED", True)
    )
    """Phase 235.x-STABILITY-5 — Move _resolve_pubkey cache-miss path to a
    worker thread via asyncio.to_thread. The miss path runs
    store.list_devices() (SQLite scan) which empirically can take 100+ms on
    a populated devices table. Hit path stays synchronous (no overhead for
    the steady-state branch handling every record after the first).
    Default ON; opt-out via LOOP_RESOLVE_PUBKEY_TO_THREAD_ENABLED=false."""

    # --- Phase 235.x-STABILITY-7 (2026-05-09): explicit ThreadPoolExecutor sizing ---
    thread_pool_max_workers: int = field(
        default_factory=lambda: int(_env("THREAD_POOL_MAX_WORKERS", "64"))
    )
    """Phase 235.x-STABILITY-7 — Explicit max_workers for the asyncio default
    ThreadPoolExecutor (used by all asyncio.to_thread + run_in_executor(None,
    ...) call sites including STABILITY-2 FSCA + STABILITY-4 on_record persist
    + STABILITY-5 pubkey resolve + capture-health endpoint). Default 64,
    chosen as 2x asyncio's auto-default (~32 on 8-core machines) for
    headroom under concurrent persist + capture-health + pubkey-resolve +
    session_adjudicator load. STABILITY-5 smoke testing observed 1 watchdog
    restart in 90s under default sizing — empirical pool saturation.
    Set to 0 to skip explicit configuration and use asyncio's built-in
    default sizing (rollback path). Thread name prefix is "vapi-persist"
    when explicit executor is configured (helps py-spy + procmon
    identify the bridge worker pool)."""

    # --- Phase 237-ZK-SEPPROOF Step G (2026-05-09): VHP gating ---
    vhp_sepproof_required: bool = field(
        default_factory=lambda: _env_bool("VHP_SEPPROOF_REQUIRED", False)
    )
    """Phase 237-ZK-SEPPROOF Step G — Two-tier VHP gating.

    When False (default): mint-vhp accepts an optional sepproof_commitment
    query param; if supplied, the snapshot must be anchored. Mint proceeds
    regardless. Backward-compatible with all existing VHP issuance flows.

    When True (operator opt-in): sepproof_commitment is REQUIRED. Mint
    rejects with 422 if missing or unanchored. Tournament-grade VHP gate.
    Set to True only after AIT corpus + biometric_snapshot anchoring +
    ZK ceremony are operationally complete."""

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

    chain_submission_paused: bool = field(
        default_factory=lambda: _env("CHAIN_SUBMISSION_PAUSED", "false").lower() == "true"
    )
    """Phase 237.5 Path C+ — Global on-chain submission kill-switch (default False).
    When True: every chain.* method that sends a transaction short-circuits
    with (None, False) instead of submitting. Gates DualShock per-PITL-proof
    fire-and-forget chain calls (dualshock_integration.py:2324-2335) and the
    central _send_tx chokepoint (chain.py:_send_tx). Eliminates wallet drain
    against IoTeX testnet's broken P256 precompile (which causes silent
    failed-tx gas burn at ~3 IOTX/hour). Read-only paths (eth_call, view
    functions) are unaffected. Local PoAC capture, GIC chain stamping, and
    PITL pipeline continue normally — only the optional on-chain anchoring
    is suspended. Restore via CHAIN_SUBMISSION_PAUSED=false in bridge/.env
    + bridge restart when wallet is funded."""

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

    # --- Phase 202: TremorRestingConvergenceOracle ---
    tremor_convergence_enabled: bool = field(
        default_factory=lambda: _env("TREMOR_CONVERGENCE_ENABLED", "false").lower() == "true"
    )
    """Phase 202 — Enable TremorRestingConvergenceOracle velocity gate.
    Default False (infrastructure-first).  When True, fires RATIO_VELOCITY_NEGATIVE
    coherence event into FleetSignalCoherenceAgent when velocity < 0 for 2 consecutive
    tremor_resting sessions, blocking VHP MINT_QUORUM=0.80 from firing prematurely."""

    # --- Phase 203: AgentContextRegistry ---
    agent_context_on_chain_enabled: bool = field(
        default_factory=lambda: _env("AGENT_CONTEXT_ON_CHAIN_ENABLED", "false").lower() == "true"
    )
    """Phase 203 — Enable AgentContextRegistry.sol on-chain prompt hash anchoring.
    Default False (infrastructure-first).  When True, POST /agent/anchor-context-hashes
    calls AgentContextRegistry.anchor() for each of the 3 LLM agents, providing an
    immutable tournament audit trail for the exact AI instructions behind any ruling."""

    # --- Phase 204: IoSwarm Adjudication Primer ---
    ioswarm_adjudication_primer_enabled: bool = field(
        default_factory=lambda: _env_bool("IOSWARM_ADJUDICATION_PRIMER_ENABLED", False)
    )
    """Phase 204 — WIF-038 W2 closure.  Enable POST /agent/prime-ioswarm-adjudication.
    When True, the primer endpoint replays synthetic device sessions through
    IoSwarmAdjudicationCoordinator in emulator mode, seeding ioswarm_adjudication_log
    and unblocking the IOSWARM_ACTIVE_NO_ADJUDICATIONS CONTRADICTION rule.
    Default False (infrastructure-first; requires explicit activation)."""

    # --- Phase 205: AccelTremorFFT ---
    accel_tremor_fallback_enabled: bool = field(
        default_factory=lambda: _env("ACCEL_TREMOR_FALLBACK_ENABLED", "true").lower() != "false"
    )
    """Phase 205 — Enable accel magnitude FFT fallback for tremor_peak_hz when
    right_stick_x variance < _STILL_HOLD_VAR_THRESHOLD (4.0 LSB²).  When True,
    still-hold sessions (tremor_seed probe type) use IMU accelerometer data to
    compute per-player neurological tremor peak frequencies instead of returning 0.0.
    Default True.  Set ACCEL_TREMOR_FALLBACK_ENABLED=false to disable."""

    # --- Phase 213: AccelTremorFFT FFT Resolution ---
    accel_fft_nfft: int = field(
        default_factory=lambda: int(_env("ACCEL_FFT_NFFT", "4096"))
    )
    """Phase 213 — Zero-padded FFT point count for accel tremor peak resolution.
    At 1000 Hz: 4096-point FFT → 0.244 Hz/bin vs 1024-point raw → 0.977 Hz/bin.
    Resolves P1 (3.1 Hz) / P3 (3.7 Hz) aliasing: 0.6 Hz gap becomes ~2.5 bins.
    Default 4096.  Set ACCEL_FFT_NFFT=<N> to override."""

    # --- Phase 207: StagedDryRunGraduationGate ---
    staged_graduation_enabled: bool = field(
        default_factory=lambda: _env("STAGED_GRADUATION_ENABLED", "false").lower() == "true"
    )
    """Phase 207 — Enable the StagedDryRunGraduationGate.  When True, operators may
    activate POST /agent/activate-graduation-stage to transition individual agents from
    dry_run=True to dry_run=False sequentially.  Default False (infrastructure-first).
    Requires tournament preflight overall_pass=True and non_convergence_clear=True."""

    graduation_rollback_window_sessions: int = field(
        default_factory=lambda: int(_env("GRADUATION_ROLLBACK_WINDOW_SESSIONS", "10"))
    )
    """Phase 207 — Rolling window of sessions within which false-positive rate is assessed.
    An agent reverts to dry_run=True when n_false_positives >= graduation_fp_threshold
    within this window.  Default 10."""

    graduation_fp_threshold: int = field(
        default_factory=lambda: int(_env("GRADUATION_FP_THRESHOLD", "2"))
    )
    """Phase 207 — Maximum tolerated false positives within graduation_rollback_window_sessions
    before automatic rollback is triggered.  Default 2 (≥2 false positives → rollback)."""

    # --- Phase 214: GraduationAutowatchBridge ---
    graduation_autowatch_enabled: bool = field(
        default_factory=lambda: _env("GRADUATION_AUTOWATCH_ENABLED", "true").lower() == "true"
    )
    """Phase 214 — Enable GraduationAutowatchBridge (WIF-041 mitigation).  When True,
    SeparationRatioMonitorAgent watches all_pairs_p0_ok state via get_separation_defensibility_status()
    and fires graduation_readiness_check bus event on False→True transition; inserts
    graduation_autowatch_log entry.  StagedDryRunGraduationAgent auto-evaluates
    check_graduation_preconditions() when a new trigger_fired entry is found.
    Default True (always-on monitoring — does NOT auto-activate graduation, only observes
    and evaluates; staged_graduation_enabled=False still gates actual stage activation)."""

    # --- Phase 208: CorpusRatioRegressionGuard ---
    corpus_ratio_regression_guard_enabled: bool = field(
        default_factory=lambda: _env("CORPUS_RATIO_REGRESSION_GUARD_ENABLED", "false").lower() == "true"
    )
    """Phase 208 — Enable the CorpusRatioRegressionGuard (WIF-039 W1).  When True,
    insert_separation_defensibility_log_guarded() raises CorpusRegressionError if the new
    entry has all_pairs_above_1=False and a prior breakthrough (all_pairs_above_1=True) exists
    for that probe type, unless an override is registered.  Default False (infrastructure-first).
    Set CORPUS_RATIO_REGRESSION_GUARD_ENABLED=true once separation ratio exceeds 1.0."""

    # --- Phase 215: L4DimSyncConfirmation ---
    l4_dim_sync_enabled: bool = field(
        default_factory=lambda: _env("L4_DIM_SYNC_ENABLED", "true").lower() == "true"
    )
    """Phase 215 — Enable L4 calibration dimension sync confirmation.  When True, the bridge
    records a sync entry confirming that live_feature_dim=13 thresholds remain valid despite
    calibration_feature_dim=12, because touchpad_spatial_entropy (index 12) is structurally
    zero in gameplay sessions (NCAA CFB 26).  Default True (safe: sync-only, thresholds unchanged).
    Closes G-003 L4 staleness gap from gap registry."""

    # --- Phase 216: PerPairGapLog ---
    per_pair_gap_log_enabled: bool = field(
        default_factory=lambda: _env("PER_PAIR_GAP_LOG_ENABLED", "true").lower() == "true"
    )
    """Phase 216 — Enable per-pair Mahalanobis distance logging.  Stores individual
    inter-player pair distances (e.g. P1vP3=0.032) from separation analysis runs so the
    tournament blocker is visible in the live API and can be trended over time.  Default True."""

    # --- Phase 217: PerPairGapTrend ---
    per_pair_gap_trend_enabled: bool = field(
        default_factory=lambda: _env("PER_PAIR_GAP_TREND_ENABLED", "true").lower() == "true"
    )
    """Phase 217 — Enable per-pair gap trend velocity analysis.  When True, the
    GET /agent/per-pair-gap-trend endpoint computes distance velocity (delta per day) for
    each pair key across recent analysis runs, classifying trend as IMPROVING/WORSENING/STABLE.
    Also activates the PER_PAIR_GAP_BLOCKER_UNRESOLVED ORPHAN rule in FleetSignalCoherenceAgent.
    Default True (safe: read-only analysis)."""

    # --- Phase 218: CaptureVelocityOracle ---
    capture_velocity_oracle_enabled: bool = field(
        default_factory=lambda: _env("CAPTURE_VELOCITY_ORACLE_ENABLED", "true").lower() == "true"
    )
    """Phase 218 — Enable unified capture velocity oracle.  Synthesizes Phase 152 centroid
    velocity + Phase 154 capture stagnation into one GET /agent/capture-velocity-oracle endpoint
    with recommended_action.  Default True (safe: read-only synthesis)."""

    # --- Phase 219: TournamentBlockerSummary ---
    tournament_blocker_summary_enabled: bool = field(
        default_factory=lambda: _env("TOURNAMENT_BLOCKER_SUMMARY_ENABLED", "true").lower() == "true"
    )
    """Phase 219 — Enable tournament blocker summary aggregation.  When True,
    GET /agent/tournament-blocker-summary returns a consolidated list of all active
    TGE blockers from preflight, per-pair gaps, and capture velocity.  Default True."""

    # --- Phase 220: PerPairGapProjection ---
    per_pair_gap_projection_enabled: bool = field(
        default_factory=lambda: _env("PER_PAIR_GAP_PROJECTION_ENABLED", "true").lower() == "true"
    )
    """Phase 220 — Enable per-pair gap TGE timeline projection.  When True,
    GET /agent/per-pair-gap-projection returns estimated days until each blocker
    pair reaches distance=1.0, plus a projected TGE date.  Default True."""

    # --- Phase 221: ProtocolCoherence (PoPC) ---
    protocol_coherence_enabled: bool = field(
        default_factory=lambda: _env("PROTOCOL_COHERENCE_ENABLED", "false").lower() == "true"
    )
    """Phase 221 — Enable ProtocolCoherenceAgent (agent #37).  When True, the agent
    periodically computes a Merkle root over all 36 VAPI agent fleet observations and
    anchors it on-chain via ProtocolCoherenceRegistry.anchorCoherence().
    Default False (on-chain anchor requires PROTOCOL_COHERENCE_REGISTRY_ADDRESS)."""

    protocol_coherence_anchor_interval_s: int = field(
        default_factory=lambda: int(_env("PROTOCOL_COHERENCE_ANCHOR_INTERVAL_S", "3600"))
    )
    """Phase 221 — Interval in seconds between PoPC Merkle root anchor cycles.
    Default 3600 (1 hour).  Lower values increase on-chain gas cost."""

    protocol_coherence_registry_address: str = field(
        default_factory=lambda: _env("PROTOCOL_COHERENCE_REGISTRY_ADDRESS", "")
    )
    """Phase 221 — Deployed ProtocolCoherenceRegistry address on IoTeX testnet.
    Empty string = on-chain anchoring disabled; local protocol_coherence_log only."""

    # --- Phase 222: BiometricBoundGovernance (BBG) ---
    bbg_enabled: bool = field(
        default_factory=lambda: _env("BBG_ENABLED", "false").lower() == "true"
    )
    """Phase 222 — Enable BiometricGovernanceAgent (agent #38).  When True, the agent
    validates governance proposals against the proposer's live VHP before accepting.
    Default False (requires BBG_CONTRACT_ADDRESS on IoTeX testnet)."""

    bbg_max_age_seconds: int = field(
        default_factory=lambda: int(_env("BBG_MAX_AGE_SECONDS", "3600"))
    )
    """Phase 222 — Minimum VHP freshness required for a governance proposal to be accepted.
    VHP must not expire within bbg_max_age_seconds from proposal time.  Default 3600 (1 hour)."""

    bbg_contract_address: str = field(
        default_factory=lambda: _env("BBG_CONTRACT_ADDRESS", "")
    )
    """Phase 222 — Deployed VAPIBiometricGovernance contract address on IoTeX testnet.
    Empty string = on-chain BBG proposal submission disabled."""

    # --- Phase 237-CONSENT: per-category gamer consent registry ---
    consent_registry_address: str = field(
        default_factory=lambda: _env("CONSENT_REGISTRY_ADDRESS", "")
    )
    """Phase 237-CONSENT — Deployed VAPIConsentRegistry address on IoTeX testnet.
    Empty string = on-chain consent disabled; bridge uses local consent_ledger as
    operational truth and chain.is_consent_valid() / get_consent_record() return
    fail-open default values (False / empty dict).  Set after deploy-phase237.js
    runs successfully."""

    vpm_anchor_registry_address: str = field(
        default_factory=lambda: _env("VPM_ANCHOR_REGISTRY_ADDRESS", "")
    )
    """Phase O4-VPM-ANCHOR — Deployed VPMAnchorRegistry address on IoTeX testnet.
    Empty string = on-chain VPM anchoring disabled; chain.anchor_vpm() short-
    circuits and returns (None, False) fail-open. Set in bridge/.env after the
    operator three-factor deploy ceremony per
    wiki/runbooks/vpm_anchor_registry_deploy_runbook.md fires successfully.
    Contract source: contracts/contracts/VPMAnchorRegistry.sol.
    Deploy script: contracts/scripts/deploy-vpm-anchor-registry.js."""

    # --- Phase 238 Step I — Curator Shadow Infrastructure ---
    curator_review_enabled: bool = field(
        default_factory=lambda: _env_bool("CURATOR_REVIEW_ENABLED", False)
    )
    """Phase 238 Step I — Opt-in flag for the Curator Operator Initiative
    agent's shadow-mode review pipeline. Default False because:
      - Step I-FINAL on-chain registration (VAPIOperatorAgentNFT mint +
        Cedar bundle dual-anchor) is wallet-gated (~0.07 IOTX).
      - Until on-chain registration completes, the Cedar bundle agentId
        remains placeholder (0xc0c0...c0c0) and reviews are operator-
        triggered only.  Setting True before that activation step is
        valid (manual operator triggers work) but operator MUST remember
        that the placeholder agentId means policy enforcement runs against
        an unregistered agent identity.  Real autonomous review loop is
        Step I-FINAL.
    Set CURATOR_REVIEW_ENABLED=true in bridge/.env to opt in."""

    curator_anchor_freshness_blocks: int = field(
        default_factory=lambda: _env_int("CURATOR_ANCHOR_FRESHNESS_BLOCKS", 1_000_000)
    )
    """Phase 238 Step I — Anchor freshness threshold in IoTeX block count.
    A listing's referenced anchor is FLAGGED_ANCHOR_STALE if its block.number
    is older than (current_block - N).  Default 1_000_000 ≈ 30 days on
    IoTeX testnet (5s block time → 17,280 blocks/day → 30d = 518k blocks;
    1M is conservative buffer for long-grind sessions)."""

    curator_ipfs_timeout_s: float = field(
        default_factory=lambda: _env_float("CURATOR_IPFS_TIMEOUT_S", 5.0)
    )
    """Phase 238 Step I — IPFS gateway resolvability check timeout in seconds.
    Curator HEAD-fetches the listing's ipfs_cid against the configured Pinata
    gateway; non-200 within timeout → FLAGGED_IPFS_UNAVAILABLE.
    Default 5.0s — matches Pinata gateway p95 latency baseline.  Operator
    can extend for slower gateways or tighten for tighter SLA enforcement."""

    # --- Phase 238 Step I-AUTOLOOP-1 — autonomous review loop tuning ---
    curator_review_interval_s: float = field(
        default_factory=lambda: _env_float("CURATOR_REVIEW_INTERVAL_S", 300.0)
    )
    """Phase 238 Step I-AUTOLOOP-1 — Autonomous Curator review loop poll
    cadence in seconds.  Default 300s (5 min) matches FSCA + cedar_drift_sweeper
    cadences; aligns with the Phase O1 D shadow data accumulation window."""

    curator_review_batch_limit: int = field(
        default_factory=lambda: _env_int("CURATOR_REVIEW_BATCH_LIMIT", 25)
    )
    """Phase 238 Step I-AUTOLOOP-1 — Maximum listings reviewed per autonomous
    loop iteration.  Default 25; bounded so a single iteration cannot stall
    the loop beyond ~30s even under worst-case anchor verification latency."""

    curator_review_idempotency_window_minutes: int = field(
        default_factory=lambda: _env_int("CURATOR_REVIEW_IDEMPOTENCY_WINDOW_MINUTES", 60)
    )
    """Phase 238 Step I-AUTOLOOP-1 — Listings already reviewed within this
    window are skipped by the autonomous loop (prevents 12-rows/listing/hour
    spam).  Default 60 min; operator audits via bulk-review can override the
    skip by manual trigger."""

    # --- Phase O0 Stream 3-prep — AgentAdjudicationRegistry (sixth FROZEN-v1 host) ---
    agent_adjudication_registry_address: str = field(
        default_factory=lambda: _env("AGENT_ADJUDICATION_REGISTRY_ADDRESS", "")
    )
    """Phase O0 Stream 2 / Stream 3-prep — Deployed AgentAdjudicationRegistry
    contract address on IoTeX testnet. Empty string = AgentAdjudicationRegistry
    not yet deployed (Stream 2-deploy gated on wallet ≥3 IOTX per Pass 2A V8);
    chain.anchor_agent_commit and chain.anchor_pda_attestation log at INFO and
    return (None, False), permitting the bridge to record AGENT_COMMIT v1 +
    PHYSICAL_DATA_ATTESTATION v1 rows locally with on_chain_confirmed=False
    while deployment is pending. Set after deploy-agent-adjudication-registry.js
    runs successfully."""

    # --- Phase O0 Stream 4-prep Session 2 — AgentRegistry ---
    agent_registry_address: str = field(
        default_factory=lambda: _env("AGENT_REGISTRY_ADDRESS", "")
    )
    """Phase O0 Stream 2-prep / Stream 4-prep Session 2 — Deployed
    AgentRegistry contract address on IoTeX testnet. Empty string =
    AgentRegistry not yet deployed (Stream 2-deploy gated on wallet
    ≥3 IOTX). The /agent/agent-registry-status endpoint returns a
    deferred-activation response when this is empty (mirrors the
    chain.anchor_agent_commit / anchor_pda_attestation pattern from
    Stream 3-prep). Set after deploy-agent-registry.js runs."""

    # --- Phase O0 Stream 4-prep — OAuth 2.1 + HMAC agent authentication ---
    # Per Pass 2C Section 5.1 + Decisions A1..A7 (Stream 4-prep Session 1).
    # Operational infrastructure for /agent/* endpoint authentication —
    # NOT a FROZEN-v1 primitive. Session 1 ships oauth_issuer.py +
    # hmac_middleware.py as standalone primitives; Session 2 will wire
    # them into bridge endpoints via a FastAPI Depends(_check_agent_token)
    # dependency. Existing _check_key / _check_read_key patterns for the
    # 154+ operator endpoints stay UNCHANGED — the new layers compose
    # alongside, not replace.
    oauth_issuer_secret: str = field(
        default_factory=lambda: _env("OAUTH_ISSUER_SECRET", "")
    )
    """HS256 JWT signing secret for the OAuth 2.1 token issuer. Empty =
    OAuth disabled (issuer cannot be constructed; agent endpoints will
    reject all requests once Session 2 wires the dependency)."""

    oauth_token_ttl_seconds: int = field(
        default_factory=lambda: _env_int("OAUTH_TOKEN_TTL_SECONDS", 300)
    )
    """JWT token TTL in seconds. Default 300 (top of Pass 2C's 60-300s
    range per Decision A5). Pass 2C Section 5.1 line 713 freezes this
    range; OAuthIssuer rejects values outside [60, 300]."""

    oauth_issuer_url: str = field(
        default_factory=lambda: _env("OAUTH_ISSUER_URL", "vapi-bridge-oauth")
    )
    """JWT 'iss' claim value. Default 'vapi-bridge-oauth' per Pass 2C
    Section 5.1 line 711 (FROZEN). Override only for multi-bridge
    federation tests."""

    oauth_audience: str = field(
        default_factory=lambda: _env("OAUTH_AUDIENCE", "vapi-bridge-agent-endpoints")
    )
    """JWT 'aud' claim value. Default 'vapi-bridge-agent-endpoints' per
    Pass 2C Section 5.1 line 712 (FROZEN). Override only for multi-
    bridge federation tests."""

    hmac_nonce_window_seconds: int = field(
        default_factory=lambda: _env_int("HMAC_NONCE_WINDOW_SECONDS", 600)
    )
    """NonceDedupTracker TTL in seconds. Default 600 per Pass 2C
    Section 5.1 line 750 (twice the ±300s clock skew window per
    Decision A4)."""

    hmac_timestamp_tolerance_seconds: int = field(
        default_factory=lambda: _env_int("HMAC_TIMESTAMP_TOLERANCE_SECONDS", 300)
    )
    """check_timestamp_freshness tolerance in seconds. Default 300 per
    Pass 2C Section 5.1 line 741 (Decision A4). Operator prompt's 60s
    suggestion was drift; Pass 2C is the design contract."""

    # --- Phase O0 Stream 5-prep Session 2 — IPFS pinning (Pinata) ---
    # Per Pass 2C Q7 (Pinata as IPFS pinning provider, operator approved
    # 2026-04-27) + Decisions D1 (Bearer JWT) and D2 (urllib.request).
    # Used by ipfs_pinning.PinataClient to pin populated DID documents
    # during Phase O0 Section 6.4 agent registration after Stream 2-deploy.
    pinata_jwt: str = field(
        default_factory=lambda: _env("PINATA_JWT", "")
    )
    """Pinata Bearer JWT. Empty = IPFS pinning disabled; PinataClient
    raises IpfsCredentialsNotConfigured on any pin_did_document call
    (deferred-activation pattern matching Stream 3-prep chain wrappers
    and Stream 4-prep OAuth issuer). Set after operator generates a
    Pinata JWT at https://app.pinata.cloud/developers/api-keys."""

    pinata_api_base_url: str = field(
        default_factory=lambda: _env("PINATA_API_BASE_URL", "https://api.pinata.cloud")
    )
    """Pinata API base URL. Default https://api.pinata.cloud is the
    canonical endpoint; override only for testing against an alternate
    Pinata-compatible service."""

    pinata_gateway_url: str = field(
        default_factory=lambda: _env("PINATA_GATEWAY_URL", "https://gateway.pinata.cloud")
    )
    """Pinata gateway URL for pin verification (verify_pin reads
    /ipfs/<hash> from this base). Default https://gateway.pinata.cloud
    is the public gateway; operators with dedicated gateways can
    override."""

    # --- Phase 223: PV-CI Invariant Gate ---
    pv_ci_enabled: bool = field(
        default_factory=lambda: _env("PV_CI_ENABLED", "true").lower() == "true"
    )
    """Phase 223 — Enable Protocol Verification CI invariant gate.  When True,
    GET /agent/invariant-gate-status reports 15 frozen protocol invariant checks.
    POST /agent/run-invariant-gate triggers a manual gate run.  Default True."""

    # --- Phase 228: VHP-Gated Invariant Change ---
    vhp_gated_invariant_change_enabled: bool = field(
        default_factory=lambda: _env("VHP_GATED_INVARIANT_CHANGE_ENABLED", "false").lower() == "true"
    )
    """Phase 228 — When True, POST /agent/allowlist-governance-event with
    reason_category='invariant_change' requires a vhp_token_id in the request body.
    The bridge verifies VHP validity on-chain (fail-open if chain unreachable).
    Default False (requires enrolled VHP to activate)."""

    # --- Phase 234.7: Physical Capture Continuity (PCC) ---
    pcc_enabled: bool = field(
        default_factory=lambda: _env_bool("PCC_ENABLED", True)
    )
    """Phase 234.7 — Enable CaptureHealthMonitor (always-on by default; monitoring only)."""

    pcc_nominal_hz: int = field(
        default_factory=lambda: _env_int("PCC_NOMINAL_HZ", 950)
    )
    """Phase 234.7 — HID poll rate threshold for NOMINAL capture state. Default 950 Hz."""

    pcc_degraded_hz: int = field(
        default_factory=lambda: _env_int("PCC_DEGRADED_HZ", 100)
    )
    """Phase 234.7 — HID poll rate floor for DEGRADED state. Below this → DISCONNECTED."""

    pcc_stable_window_s: int = field(
        default_factory=lambda: _env_int("PCC_STABLE_WINDOW_S", 30)
    )
    """Phase 234.7 — Seconds of sustained NOMINAL required before grind_ready=True."""

    pcc_smoke_bypass: bool = field(
        default_factory=lambda: _env_bool("PCC_SMOKE_BYPASS", False)
    )
    """Phase 235-SMOKE-BYPASS — when True, session_adjudicator_validator forces
    _pcc_eligible=True regardless of capture_state/host_state.  Validates the
    GIC chain-stamping pipeline end-to-end on hardware where USB enumeration
    is unstable.  SMOKE-ONLY — disables USB-vs-BT discrimination.  Disable
    before the real 100-session grind."""

    # --- Phase 235-PCC-SPC: Statistical Process Control + 3-signal haptic-tolerance binding ---
    # Defaults DATA-ANCHORED from session 2026-05-03 (35.5 min, 887 PCC snapshots,
    # 26.6K record obs). When pcc_spc_enabled=False, classifier behavior is
    # byte-identical to pre-Phase-235-PCC-SPC (Phase 234.7).  Opt-in via
    # PCC_SPC_ENABLED=true; rollback = set False + bridge restart.
    pcc_spc_enabled: bool = field(
        default_factory=lambda: _env_bool("PCC_SPC_ENABLED", False)
    )
    """Phase 235-PCC-SPC — opt-in SPC classifier (USL outlier trim + in-control
    capability + 3-signal haptic-tolerance binding + frequency-band gate).
    Default False; behavior identical to Phase 234.7 when disabled."""

    pcc_upper_hz: int = field(
        default_factory=lambda: _env_int("PCC_UPPER_HZ", 3500)
    )
    """Phase 235-PCC-SPC — Upper Spec Limit.  Samples above this trim from CV
    calc (treated as outliers, not stability data).  Data-anchored: p99=3240,
    max=7252 (reconnect bursts) → 3500 catches outliers without trimming
    legitimate variance."""

    pcc_haptic_tolerance_window_ms: int = field(
        default_factory=lambda: _env_int("PCC_HAPTIC_TOLERANCE_WINDOW_MS", 500)
    )
    """Phase 235-PCC-SPC — Max duration of tolerated rate dip per 3-signal binding.
    Sub-second haptic events get suppressed; >500ms dips fall through to
    DEGRADED.  Bot exploit ceiling — longer dip indicates real degradation."""

    pcc_haptic_min_dip_hz: int = field(
        default_factory=lambda: _env_int("PCC_HAPTIC_MIN_DIP_HZ", 200)
    )
    """Phase 235-PCC-SPC — Floor for tolerated rate dip; below this, DEGRADED
    classification fires regardless of haptic context.  Sub-200Hz cannot be
    masked even with valid trigger_active+accel_var."""

    pcc_spc_window_n: int = field(
        default_factory=lambda: _env_int("PCC_SPC_WINDOW_N", 30)
    )
    """Phase 235-PCC-SPC — Sample count in capability window for in-control
    calculation."""

    pcc_spc_in_control_pct: float = field(
        default_factory=lambda: _env_float("PCC_SPC_IN_CONTROL_PCT", 0.85)
    )
    """Phase 235-PCC-SPC — Fraction of last N samples that must be within
    [LSL=pcc_nominal_hz, USL=pcc_upper_hz] for "in control" classification.
    Data-anchored: 96.4% of snapshots NOMINAL → 0.85 tighter than initial 0.80
    proposal (still permissive enough to absorb haptic-induced sub-window
    jitter)."""

    pcc_haptic_tremor_min_hz: float = field(
        default_factory=lambda: _env_float("PCC_HAPTIC_TREMOR_MIN_HZ", 4.0)
    )
    """Phase 235-PCC-SPC INV-PCC-005 — Lower bound of valid tremor_peak_hz for
    haptic-tolerance binding.  Excludes "OTHER" sub-tremor class (data:
    69% of OTHER bursts had tremor_peak_hz < 4Hz; without this constraint a
    bot could spoof low-frequency oscillations to satisfy accel_var threshold
    without producing real motor or human-tremor signature)."""

    pcc_haptic_tremor_max_hz: float = field(
        default_factory=lambda: _env_float("PCC_HAPTIC_TREMOR_MAX_HZ", 60.0)
    )
    """Phase 235-PCC-SPC INV-PCC-005 — Upper bound of valid tremor_peak_hz for
    haptic-tolerance binding.  Caps at high-motor band (rumble + adaptive
    trigger motor signatures cluster 40-60 Hz); rejects aliased >60Hz."""

    pcc_haptic_accel_threshold: float = field(
        default_factory=lambda: _env_float("PCC_HAPTIC_ACCEL_THRESHOLD", 0.0003)
    )
    """Phase 235-PCC-SPC — Minimum micro_tremor_accel_variance for a sample to
    qualify as a haptic burst.  Data-anchored: distribution p90=0.000323;
    0.0003 captures top-decile bursts (motor + human + transient classes)."""

    grind_mode: bool = field(
        default_factory=lambda: _env_bool("GRIND_MODE", False)
    )
    """Phase 234.7 — Activate grind-mode fail-closed enforcement.
    When True: session_counting_paused=True if capture is not NOMINAL+EXCLUSIVE_USB.
    Set via GRIND_MODE=true in bridge/.env or --grind-mode CLI flag (startup).
    Default False. Only activate for calibration grind sessions."""

    grind_target: int = field(
        default_factory=lambda: _env_int("GRIND_TARGET", 100)
    )
    """Phase 234.7 — Target consecutive_clean count for grind completion.
    Reported in GET /bridge/capture-health as progress N/target.
    Default 100 (matches validation_gate_n default)."""

    auto_trigger_enabled: bool = field(
        default_factory=lambda: _env_bool("AUTO_TRIGGER_ENABLED", False)
    )
    """Phase 235-AUTO-TRIGGER — Activate the SessionBoundaryDetectorAgent.
    When True: agent #38 polls every 60s; on detected session-end
    (gameplay activity in the recent window followed by extended trigger
    quiescence) and PCC NOMINAL+EXCLUSIVE_USB, publishes a ruling_request
    event to the bus.  Throttled to one trigger per auto_trigger_min
    _interval_s.  Off by default — operator opts in via env var when
    starting the grind."""

    auto_trigger_min_interval_s: int = field(
        default_factory=lambda: _env_int("AUTO_TRIGGER_MIN_INTERVAL_S", 300)
    )
    """Phase 235-AUTO-TRIGGER — Minimum seconds between consecutive
    auto-fired ruling_request events.  Default 300s matches Session
    Adjudicator's 5-min poll cadence; firing faster has zero throughput
    gain and weakens the W1 rate-limit mitigation.  Lowering this
    requires a corresponding update to the FleetSignalCoherenceAgent
    AUTO_TRIGGER_RATE_LIMIT_VIOLATION rule's per-hour ceiling."""

    auto_trigger_quiescence_window: int = field(
        default_factory=lambda: _env_int("AUTO_TRIGGER_QUIESCENCE_WINDOW", 60)
    )
    """Phase 235-AUTO-TRIGGER — Number of trailing records that must all
    have trigger_active=0 to classify as game-end (return-to-menu)
    quiescence rather than between-play quiescence.  At ~1 record per
    second from the session loop, default 60 = ~60 seconds of no
    trigger activity.  NCAA CFB 26 has natural ~30s quiescence between
    plays (huddle / play-call); the window must be long enough to skip
    those without firing.  Tune during live grind verification — raise
    if firing too frequently between plays, lower if firing too rarely
    (e.g. only when player fully exits to home)."""

    auto_trigger_activity_window: int = field(
        default_factory=lambda: _env_int("AUTO_TRIGGER_ACTIVITY_WINDOW", 600)
    )
    """Phase 235-SBD-FIX — Lookback window (records past the quiescence
    tail) searched for ANY trigger_active==1.  Anchors on the last
    gameplay moment rather than requiring a fraction in a fixed window —
    fixes silent skip when player spends >2 minutes on menu post-game
    (old 120-record head_frac check would silently return 0.00).
    Default 600 records ~ 10 minutes; covers typical dynasty/menu
    navigation time between games."""

    grind_session_id: str = field(
        default_factory=lambda: os.environ.get(
            "GRIND_SESSION_ID",
            f"grind_{__import__('datetime').date.today().strftime('%Y%m%d')}",
        )
    )
    """Phase 235-A — Stable identifier for this grind run used as GIC chain root.
    Set GRIND_SESSION_ID in bridge/.env for multi-day grinds. Auto-generated
    as grind_YYYYMMDD if not set. A new value starts a new chain (new genesis)."""

    # --- Phase O1 C1: Operator Agent activation arc (Cedar bundle dual-anchor) ---
    agent_scope_address: str = field(
        default_factory=lambda: _env("AGENT_SCOPE_ADDRESS", "")
    )
    """Phase O1 C1 — VAPI AgentScope contract address (operational layer).
    Deployed Phase O0 at 0xc694692a69bbf1cDAda87d5bc43D345C4579FF13. Live
    read path used by AgentAdjudicationRegistry.requireAgentScope. Cedar
    bundle anchor (cedar_bundle_anchor.py) calls setAgentScopeRoot here
    FIRST per INV-OPERATOR-AGENT-001. Empty default = chain.get/set methods
    raise RuntimeError (fail-closed; Phase O1 cannot operate without scope state)."""

    agent_registry_address: str = field(
        default_factory=lambda: _env("AGENT_REGISTRY_ADDRESS", "")
    )
    """Phase O1 C1 — VAPI AgentRegistry contract address (governance layer).
    Deployed Phase O0 at 0x9548E9d17c2d40350629b1b88ff1D2c01B0414a4. Stores
    per-agentId scopeHash governance commitment. Cedar bundle anchor calls
    updateAgentScope here SECOND per INV-OPERATOR-AGENT-001."""

    cedar_bundle_dir: str = field(
        default_factory=lambda: _env("CEDAR_BUNDLE_DIR", "bridge/vapi_bridge/cedar_bundles")
    )
    """Phase O1 C1 — Repo-relative directory containing Cedar bundle JSON files
    (per Pass 2C Q10 Option B: bundles stored in repo, Merkle root anchored
    on-chain via AgentScope). cedar_bundle_anchor.anchor_bundle resolves
    relative bundle_path arguments against this directory."""

    operator_agent_anchor_sentry_id: str = field(
        default_factory=lambda: _env(
            "OPERATOR_AGENT_ANCHOR_SENTRY_ID",
            "0xb21e1ec258d2d381c313f84944bd36fbc63badb2c9a24c2412212d3a27e3e42c",
        )
    )
    """Phase O1 C1 — Q9-frozen agentId for the Anchor Sentry operator agent.
    FROZEN per Pass 2C Q9 — registered on AgentRegistry Phase O0 (2026-05-03,
    commit 44c26ce0). Any change here breaks bundle anchoring."""

    operator_agent_guardian_id: str = field(
        default_factory=lambda: _env(
            "OPERATOR_AGENT_GUARDIAN_ID",
            "0xbd8c7fba08815b7ed343973c9c7300c062303b1acd19e8d9847a953ce5fa38d1",
        )
    )
    """Phase O1 C1 — Q9-frozen agentId for the Guardian operator agent.
    FROZEN per Pass 2C Q9 — registered on AgentRegistry Phase O0 (2026-05-03,
    commit 44c26ce0). Any change here breaks bundle anchoring."""

    operator_agent_curator_id: str = field(
        default_factory=lambda: _env(
            "OPERATOR_AGENT_CURATOR_ID",
            "0xed6a2df58e5ec50c1f88e127f6982a348f6855202b662b8ad73ffa1c1fda11a8",
        )
    )
    """Phase O1-CURATOR C2 — Q9-frozen agentId for the Curator operator agent
    (third Operator Initiative agent). Registered on AgentRegistry Phase 238
    Step I-FINAL (2026-05-09, Sessions 1+2+3 commit eeeeb366). Any change
    here breaks Curator bundle anchoring + cedar_shadow_runtime resolution.

    Architectural divergence from Sentry/Guardian: Curator was registered
    via the MockKMSClient TESTNET path (no GitHub App, no AWS KMS HSM).
    Production mainnet activation requires AWS KMS HSM provisioning + steps
    7+8 re-run + Cedar bundle re-anchor with new agentId. This is Curator's
    dedicated development avenue — separate from Sentry/Guardian's ceremony
    and KMS infrastructure but advances through the same Phase O ladder."""

    # --- Phase O1 D: Operator Initiative Advancement Watcher (parallel-fleet) ---
    operator_initiative_advancement_enabled: bool = field(
        default_factory=lambda: _env_bool(
            "OPERATOR_INITIATIVE_ADVANCEMENT_ENABLED", False
        )
    )
    """Phase O1 D — Enable the parallel-fleet advancement watcher that
    evaluates Phase O2 SUGGEST + O3 ACT readiness criteria for all three
    Operator Initiative agents (Sentry, Guardian, Curator) on a single
    1-hour cadence. Default False = opt-in observability (matches Phase
    O1 C4 cedar_drift_sweep_enabled pattern). Activates the watcher in
    main.py's task list when True. Never advances any agent — only
    publishes readiness state."""

    operator_initiative_advancement_interval_s: float = field(
        default_factory=lambda: _env_float(
            "OPERATOR_INITIATIVE_ADVANCEMENT_INTERVAL_S", 3600.0
        )
    )
    """Phase O1 D — Watcher poll cadence in seconds. Default 3600 (1 hour)
    matches the slow-moving criteria (3-week shadow age threshold). Lowered
    only for testing; in production the criteria don't change fast enough
    to warrant tighter polling."""

    kms_hsm_production_ready: bool = field(
        default_factory=lambda: _env_bool("KMS_HSM_PRODUCTION_READY", False)
    )
    """Phase O1 D / O3 ACT gate — Sentry + Guardian require AWS KMS HSM
    provisioning before Phase O3 ACT advancement. Set True when KMS HSM
    is provisioned + tested + Cedar bundle re-anchored against production
    keys. Curator does NOT consult this flag (it uses MockKMS testnet
    path on its dedicated avenue)."""

    marketplace_curator_role_assigned: bool = field(
        default_factory=lambda: _env_bool(
            "MARKETPLACE_CURATOR_ROLE_ASSIGNED", False
        )
    )
    """Phase O1 D / O3 ACT gate — Curator agent requires VAPIDataMarketplace
    Listings.setCurator(curator_agent_address) called by deploy-wallet
    before Phase O3 ACT advancement. The setCurator(address) hook was
    reserved on the contract per Phase 238 Step F. Set True after the
    on-chain role assignment completes (~0.05 IOTX). Sentry + Guardian
    do NOT consult this flag — they use the kms_hsm_production_ready
    gate instead."""

    # --- O3 expedite arc 2026-05-15: surface previously-getattr-only flags ---
    operator_dual_key_present: bool = field(
        default_factory=lambda: _env_bool("OPERATOR_DUAL_KEY_PRESENT", False)
    )
    """Phase O1 D / O3 ACT gate — all three Operator Initiative agents
    require dual-key operator authorization before Phase O3 ACT
    advancement. The watcher previously read this via getattr fallback
    (defaulting to False if cfg attr missing); promoted to a first-class
    Config field 2026-05-15 so operators can set it via env var
    OPERATOR_DUAL_KEY_PRESENT=true once dual-key authorization is in
    place. Surfaced by scripts/operator_initiative_o3_preflight.py."""

    github_app_oauth_tokens_valid: bool = field(
        default_factory=lambda: _env_bool(
            "GITHUB_APP_OAUTH_TOKENS_VALID", False
        )
    )
    """Phase O1 D / O3 ACT gate — Guardian-only. Guardian's audit-drafting
    workflow lifts at O3_ACTING to write directly to the audits/ lane
    via GitHub App + OAuth-scoped tokens. Set True after the operator
    completes GitHub App OAuth setup. Sentry + Curator do NOT consult
    this flag. Surfaced by scripts/operator_initiative_o3_preflight.py."""

    # --- Phase O1 C4: Drift Auto-Sweep Scheduler ---
    cedar_drift_sweep_enabled: bool = field(
        default_factory=lambda: _env_bool("CEDAR_DRIFT_SWEEP_ENABLED", False)
    )
    """Phase O1 C4 — Enable cedar_drift_sweeper background task. When False
    (default), drift detection only runs on operator-triggered POST. When True,
    runs at dual cadence (bundle 60s, scope 600s) catching mutations within
    one sweep window. Default False = opt-in observability."""

    cedar_drift_sweep_interval_bundle_s: int = field(
        default_factory=lambda: int(_env("CEDAR_DRIFT_SWEEP_INTERVAL_BUNDLE_S", "60"))
    )
    """Phase O1 C4 — Bundle hash drift sweep interval. Cheap path (local file
    SHA-256 + 1 DB read per agent). 60s default. INV-OPERATOR-AGENT-008
    freezes the cheap+frequent / expensive+rare cadence split."""

    cedar_drift_sweep_interval_scope_s: int = field(
        default_factory=lambda: int(_env("CEDAR_DRIFT_SWEEP_INTERVAL_SCOPE_S", "600"))
    )
    """Phase O1 C4 — Scope hash governance drift sweep interval. Expensive
    path (2 chain RPC reads per agent). 600s default to bound testnet RPC
    quota. INV-OPERATOR-AGENT-008 freezes the dual-cadence shape."""

    # --- Phase O5-MYTHOS-MINIMAL M.1: Mythos cadence engine ---
    mythos_cadence_enabled: bool = field(
        default_factory=lambda: _env_bool("MYTHOS_CADENCE_ENABLED", False)
    )
    """Phase O5-MYTHOS-MINIMAL M.1 — Enable the Mythos cadence background
    task. When False (default), Mythos variants only run on operator-
    triggered MCP tool invocation. When True, variants registered with
    get_pending_variants run at the daily cadence; findings persist to
    mythos_finding_log and route via fleet_coherence_log (M.3 FSCA
    rules). Default False = opt-in observability — same pattern as the
    cedar_drift_sweep family above."""

    mythos_cadence_interval_s: int = field(
        default_factory=lambda: int(_env("MYTHOS_CADENCE_INTERVAL_S", "86400"))
    )
    """Phase O5-MYTHOS-MINIMAL M.1 — Mythos cadence engine heartbeat
    interval. 86400s (24h) default — daily cadence per the M.1 plan."""

    # --- Phase O5-MLGA Stage 3: runtime session tracker ---
    mlga_session_tracker_enabled: bool = field(
        default_factory=lambda: _env_bool("MLGA_SESSION_TRACKER_ENABLED", False)
    )
    """Phase O5-MLGA Stage 3 — operationalizes the MLGA capability. When
    True, mlga_session_tracker polls capture_health_log + records + APOP
    + ruling_validation_log every mlga_session_tracker_interval_s seconds
    during active gameplay; opens sessions on controller-connect; closes
    on disconnect / max_duration; computes + persists session dataproof
    to mlga_session_log. Default False = opt-in observability."""

    mlga_session_tracker_interval_s: int = field(
        default_factory=lambda: int(_env("MLGA_SESSION_TRACKER_INTERVAL_S", "30"))
    )
    """Phase O5-MLGA Stage 3 — tracker poll cadence. 30s default — fast
    enough to catch session transitions; slow enough to be background."""

    mlga_session_max_duration_s: int = field(
        default_factory=lambda: int(_env("MLGA_SESSION_MAX_DURATION_S", "3600"))
    )
    """Phase O5-MLGA Stage 3 — session duration cap. 3600s (1h) default.
    Auto-closes long sessions to prevent runaway accumulator state; a fresh
    session opens immediately on the next poll if controller still NOMINAL."""

    # --- Phase O5-MLGA Stage 5: GIC-LEDGER-BETA-v1 autonomous emission ---
    gic_ledger_beta_tracker_enabled: bool = field(
        default_factory=lambda: _env_bool("GIC_LEDGER_BETA_TRACKER_ENABLED", True)
    )
    """Phase O5-MLGA Stage 5 — second autonomous VPM artifact class
    (after MLGA-SESSION-v1). When True, gic_ledger_beta_tracker polls
    grind_chain_status every gic_ledger_beta_interval_s seconds and
    emits one GIC-LEDGER-BETA-v1 VPM artifact each time the chain
    crosses a 10-link milestone (10, 20, 30, …, 100, 110, …). Default
    True — emission is wallet-free, local-only, idempotent on bridge
    restart. Set False to disable."""

    gic_ledger_beta_interval_s: int = field(
        default_factory=lambda: int(_env("GIC_LEDGER_BETA_INTERVAL_S", "30"))
    )
    """Phase O5-MLGA Stage 5 — GIC-BETA tracker poll cadence. 30s
    default. Chain advances roughly every 1s during active play (per
    MLGA tracker observation: 105 advances in 95s session), so 30s
    catches every 10-link milestone within ~3 minutes of crossing."""

    # --- Phase O5-MLGA Stage 6: HONESTY-BOARD-v1 autonomous weekly emission ---
    honesty_board_tracker_enabled: bool = field(
        default_factory=lambda: _env_bool("HONESTY_BOARD_TRACKER_ENABLED", True)
    )
    """Phase O5-MLGA Stage 6 — third autonomous VPM artifact class.
    When True, honesty_board_tracker snapshots protocol-state honesty
    fields weekly and emits one HONESTY-BOARD-v1 VPM artifact per
    week. Wallet-free; local-only; idempotent on restart via
    vpm_artifact_log last-emit seed."""

    honesty_board_poll_interval_s: int = field(
        default_factory=lambda: int(_env("HONESTY_BOARD_POLL_INTERVAL_S", "3600"))
    )
    """Phase O5-MLGA Stage 6 — HONESTY-BOARD tracker poll cadence.
    1h default. Emission gated by 7-day interval, so most polls are
    no-ops."""

    honesty_board_emission_interval_s: int = field(
        default_factory=lambda: int(_env("HONESTY_BOARD_EMISSION_INTERVAL_S", "604800"))
    )
    """Phase O5-MLGA Stage 6 — HONESTY-BOARD emission cadence. 7 days
    default (Sentry weekly self-report cycle per VBDIP-0002A §10)."""

    # --- Phase O5-MLGA Stage 8: CDRR-DAG-v1 autonomous on-rejection ---
    cdrr_dag_tracker_enabled: bool = field(
        default_factory=lambda: _env_bool("CDRR_DAG_TRACKER_ENABLED", True)
    )
    """Phase O5-MLGA Stage 8 — fifth autonomous VPM artifact class.
    Polls fleet_coherence_log; emits one CDRR-DAG-v1 artifact when a
    HIGH or CRITICAL contradiction lands (the 'coherence rule
    re-rejection' trigger per VBDIP-0002A §10.4). Wallet-free;
    idempotent on restart via vpm_artifact_log seed."""

    cdrr_dag_poll_interval_s: int = field(
        default_factory=lambda: int(_env("CDRR_DAG_POLL_INTERVAL_S", "60"))
    )
    """Phase O5-MLGA Stage 8 — CDRR-DAG tracker poll cadence. 60s
    matches FSCA poll cycle."""

    # --- Phase O5-PUBLIC-VIEWER: rate-limit for the public sub-app ---
    public_forensic_rate_limit_per_min: int = field(
        default_factory=lambda: int(_env("PUBLIC_FORENSIC_RATE_LIMIT_PER_MIN", "60"))
    )
    """Phase O5-PUBLIC-VIEWER — sliding-window per-IP rate limit on
    /public/* endpoints. 60 req/min/IP default. The public sub-app
    has NO auth; the rate limit is the only abuse defense at the
    bridge layer. Operators may lower behind a CDN/edge that also
    rate-limits."""

    # --- Phase 242-BT Stream 1 — BT-WITNESS v1 capability ---
    bt_witness_enabled: bool = field(
        default_factory=lambda: _env_bool("BT_WITNESS_ENABLED", False)
    )
    """Phase 242-BT Stream 1 — Enable the LAN-tower BlueZ BT-WITNESS
    background task. When False (default), no witness service runs and
    no commitments are produced. When True, Stream 2 will wire the
    BlueZ subprocess + HCI Read_RSSI capture loop (NOT YET SHIPPED).
    Default False = opt-in observability per the canonical anchor's
    6-month timeline: Stage-2 measurement campaign (weeks 7-14) +
    Stage-3 adversarial validation (weeks 15-24) must complete before
    first calibration capture.  See wiki/methodology/
    bt_calibration_v1_1_architectural_revision.md."""

    bt_witness_dongle_path: str = field(
        default_factory=lambda: _env("BT_WITNESS_DONGLE_PATH", "")
    )
    """Phase 242-BT Stream 1 — BlueZ USB BT dongle HCI device path
    (Stream 2 reads this; Stream 1 stores it as documentation).
    Empty default — operator sets when witness rig is provisioned.
    Typical Linux path: '/dev/hci0' or 'hci0' (BlueZ identifier)."""

    bt_witness_interval_s: int = field(
        default_factory=lambda: int(_env("BT_WITNESS_INTERVAL_S", "60"))
    )
    """Phase 242-BT Stream 1 — Commitment write cadence for the
    Stream 2 witness service. 60s default — matches cedar_drift_sweep
    cheap+frequent cadence tier (file-only / HCI-socket evaluation;
    no chain RPC). Operator sets via env var BT_WITNESS_INTERVAL_S
    when Stream 2 is wired."""

    # --- Phase O4-VPM-INT follow-up: Continuous CFSS lane drift sweep ---
    cfss_drift_sweep_enabled: bool = field(
        default_factory=lambda: _env_bool("CFSS_DRIFT_SWEEP_ENABLED", False)
    )
    """Phase O4-VPM-INT follow-up — Enable cfss_drift_sweeper background task
    that runs the EXPECTED_LANE_MATRIX evaluation continuously at 60s cadence.
    When False (default), CFSS lane authority is verified only by the
    operator-runtime post-ceremony audit. When True, silent Cedar bundle
    mutations surface within one sweep window. Default False = opt-in
    observability. Findings land in cfss_lane_drift_log → consumed by
    FSCA rule CFSS_LANE_AUTHORITY_DRIFT (CRITICAL)."""

    cfss_drift_sweep_interval_s: int = field(
        default_factory=lambda: int(_env("CFSS_DRIFT_SWEEP_INTERVAL_S", "60"))
    )
    """Phase O4-VPM-INT follow-up — CFSS drift sweep interval. Aligns with
    cedar_drift_sweep_interval_bundle_s (60s) per INV-OPERATOR-AGENT-008
    cheap+frequent cadence tier (file-only evaluation; no chain RPC)."""

    # --- Phase O2-DRAFT-AUTOLOOP: Operator-agent O2 drafting polling loops ---
    operator_agent_sentry_polling_enabled: bool = field(
        default_factory=lambda: _env_bool("OPERATOR_AGENT_SENTRY_POLLING_ENABLED", False)
    )
    """Phase O2-DRAFT-AUTOLOOP (Sentry) — Enable Sentry's autonomous draft
    polling loop. When False (default), Sentry produces drafts only via
    operator-triggered calls. When True, run_sentry_polling_loop() runs in
    background dispatching trigger-driven kms-sign / provenance-recording /
    pda-anchor drafts to operator_agent_drafts (Phase 1005). Default False =
    opt-in observability."""

    operator_agent_sentry_polling_interval_s: int = field(
        default_factory=lambda: int(_env("OPERATOR_AGENT_SENTRY_POLLING_INTERVAL_S", "30"))
    )
    """Phase O2-DRAFT-AUTOLOOP (Sentry) — Sentry polling cycle interval.
    30s default keeps draft generation responsive to fresh commits / PoAC
    chain updates while bounding store write rate to <= 1 per cycle."""

    operator_agent_guardian_polling_enabled: bool = field(
        default_factory=lambda: _env_bool("OPERATOR_AGENT_GUARDIAN_POLLING_ENABLED", False)
    )
    """Phase O2-DRAFT-AUTOLOOP (Guardian) — Enable Guardian's autonomous draft
    polling loop. When False (default), Guardian produces drafts only via
    operator-triggered calls. When True, run_guardian_polling_loop() dispatches
    audit-drafting / operational-diagnostic / kms-sign drafts on sweep_completed
    + fsca_finding + commit triggers. Default False = opt-in."""

    operator_agent_guardian_polling_interval_s: int = field(
        default_factory=lambda: int(_env("OPERATOR_AGENT_GUARDIAN_POLLING_INTERVAL_S", "30"))
    )
    """Phase O2-DRAFT-AUTOLOOP (Guardian) — Guardian polling cycle interval.
    30s default mirrors Sentry; Guardian's audit cadence is event-driven rather
    than time-driven so this primarily bounds queue drain rate."""

    operator_agent_curator_polling_enabled: bool = field(
        default_factory=lambda: _env_bool("OPERATOR_AGENT_CURATOR_POLLING_ENABLED", False)
    )
    """Phase O2-DRAFT-AUTOLOOP (Curator) — Enable Curator's autonomous draft
    polling loop. When False (default), Curator produces drafts only via
    operator-triggered calls. When True, run_curator_polling_loop() dispatches
    marketplace-listing-review + operator-notify drafts on listing_event +
    anchor_freshness_alert + periodic_compliance triggers. Default False =
    opt-in."""

    operator_agent_curator_polling_interval_s: int = field(
        default_factory=lambda: int(_env("OPERATOR_AGENT_CURATOR_POLLING_INTERVAL_S", "30"))
    )
    """Phase O2-DRAFT-AUTOLOOP (Curator) — Curator polling cycle interval.
    30s default; Curator additionally runs a 6h periodic_compliance batch
    independent of this base interval."""

    # --- Phase O2-GIT-TRIGGER-SOURCE: live commit trigger source ---
    operator_agent_git_trigger_enabled: bool = field(
        default_factory=lambda: _env_bool("OPERATOR_AGENT_GIT_TRIGGER_ENABLED", False)
    )
    """Phase O2-GIT-TRIGGER-SOURCE — Enable GitTriggerSource as the live
    commit trigger source feeding Sentry's polling loop. When False
    (default), Sentry receives no commit triggers and produces no
    kms-sign/provenance drafts on commits. When True, GitTriggerSource
    polls `git rev-parse HEAD` each polling cycle and emits
    {kind:'commit', payload:{commit_hash, repo, branch}} triggers on
    HEAD advancement. Pure stdlib subprocess; no bus dependency.
    Default False = opt-in (live event source)."""

    # --- Phase O2-GUARDIAN-TRIGGERS: Guardian live trigger sources ---
    operator_agent_guardian_git_trigger_enabled: bool = field(
        default_factory=lambda: _env_bool("OPERATOR_AGENT_GUARDIAN_GIT_TRIGGER_ENABLED", False)
    )
    """Phase O2-GUARDIAN-TRIGGERS — Enable GitTriggerSource feeding Guardian's
    polling loop with commit triggers (kms-sign + audit-drafting drafts per
    commit). Distinct from operator_agent_git_trigger_enabled (Sentry's path)
    so operators can enable Sentry+Guardian commit-driven drafting independently.
    Default False = opt-in."""

    operator_agent_guardian_fsca_trigger_enabled: bool = field(
        default_factory=lambda: _env_bool("OPERATOR_AGENT_GUARDIAN_FSCA_TRIGGER_ENABLED", False)
    )
    """Phase O2-GUARDIAN-TRIGGERS — Enable GuardianFscaTriggerSource: subscribes
    to fleet_coherence_log new rows (by id high-water mark) and emits
    {kind:'fsca_finding', payload:{finding_id, severity, agents_involved, subject}}
    triggers feeding Guardian's draft_operational_diagnostic skill. Default
    False = opt-in (live event source)."""

    # --- Phase O2-CURATOR-TRIGGERS: Curator live trigger sources ---
    operator_agent_curator_marketplace_trigger_enabled: bool = field(
        default_factory=lambda: _env_bool("OPERATOR_AGENT_CURATOR_MARKETPLACE_TRIGGER_ENABLED", False)
    )
    """Phase O2-CURATOR-TRIGGERS — Enable CuratorMarketplaceListingTriggerSource:
    subscribes to marketplace_listing_log new rows (by id) and emits
    {kind:'listing_event', payload:{listing_id, verdict, review_payload}}
    triggers feeding Curator's draft_marketplace_listing_review +
    draft_kms_sign_review chained drafts. Default False = opt-in."""

    operator_agent_curator_anchor_freshness_trigger_enabled: bool = field(
        default_factory=lambda: _env_bool("OPERATOR_AGENT_CURATOR_ANCHOR_FRESHNESS_TRIGGER_ENABLED", False)
    )
    """Phase O2-CURATOR-TRIGGERS — Enable CuratorAnchorFreshnessTriggerSource:
    cron-style periodic check via chain.is_adjudication_recorded() of recent
    listing anchors; emits {kind:'anchor_freshness_alert', ...} triggers
    when a listing's anchor age exceeds the freshness window. Default
    False = opt-in (live chain RPC poll)."""

    operator_agent_curator_anchor_freshness_interval_s: int = field(
        default_factory=lambda: int(_env("OPERATOR_AGENT_CURATOR_ANCHOR_FRESHNESS_INTERVAL_S", "3600"))
    )
    """Phase O2-CURATOR-TRIGGERS — Cron interval for anchor-freshness checks.
    1h default keeps testnet chain RPC quota bounded while still catching
    stale anchors within the operator's review window."""

    operator_agent_curator_periodic_compliance_trigger_enabled: bool = field(
        default_factory=lambda: _env_bool("OPERATOR_AGENT_CURATOR_PERIODIC_COMPLIANCE_TRIGGER_ENABLED", False)
    )
    """Phase O2-CURATOR-TRIGGERS — Enable CuratorPeriodicComplianceTriggerSource:
    6h cron emitting {kind:'periodic_compliance', payload:{listings:[...]}}
    BATCH triggers (one trigger per cron fire; the batch produces N draft
    rows where N = listings count). Default False = opt-in."""

    operator_agent_curator_periodic_compliance_interval_s: int = field(
        default_factory=lambda: int(_env("OPERATOR_AGENT_CURATOR_PERIODIC_COMPLIANCE_INTERVAL_S", "21600"))
    )
    """Phase O2-CURATOR-TRIGGERS — Cron interval for periodic-compliance batches.
    6h default = 4×/day; balances batch throughput against operator review
    burden."""

    # --- Phase O1-D-PATH-B v1 2026-05-17: per-agent live-write executor ---
    phase_o3_anchor_sentry_live_writes_enabled: bool = field(
        default_factory=lambda: _env_bool("PHASE_O3_ANCHOR_SENTRY_LIVE_WRITES_ENABLED", False)
    )
    """Phase O1-D-PATH-B v1 — Enable Sentry's live-write executor (chain ops
    via chain.record_adjudication for PoAd anchoring). Default False = OPT-IN.
    When True AND agent at O3_ACTING AND budget remaining AND emergency
    kill-all not active AND global CHAIN_SUBMISSION_PAUSED=false, the
    executor processes Sentry's accepted drafts → real chain operations."""

    phase_o3_guardian_live_writes_enabled: bool = field(
        default_factory=lambda: _env_bool("PHASE_O3_GUARDIAN_LIVE_WRITES_ENABLED", False)
    )
    """Phase O1-D-PATH-B v1 — Enable Guardian's live-write executor. Guardian's
    O3 actions are local writes (audits/, ops/) — no chain dependency, so this
    flag activates Guardian autonomously even with CHAIN_SUBMISSION_PAUSED=true.
    Default False = OPT-IN."""

    phase_o3_curator_live_writes_enabled: bool = field(
        default_factory=lambda: _env_bool("PHASE_O3_CURATOR_LIVE_WRITES_ENABLED", False)
    )
    """Phase O1-D-PATH-B v1 — Enable Curator's live-write executor (chain ops
    via VAPIDataMarketplaceListings.suspendListing). Default False = OPT-IN."""

    # Per-agent daily IOTX budget caps — runaway prevention. Executor refuses
    # drafts that would push daily spending over budget. Defaults align with
    # DEFAULT_BUDGET_IOTX_BY_AGENT in operator_initiative_live_write_executor.py.
    phase_o3_anchor_sentry_daily_iotx_budget: float = field(
        default_factory=lambda: float(_env("PHASE_O3_ANCHOR_SENTRY_DAILY_IOTX_BUDGET", "0.5"))
    )
    """Phase O1-D-PATH-B v1 — Sentry's daily IOTX spending cap. At ~0.0008 IOTX
    per PoAd anchor, default 0.5 = ~625 anchors/day budget. Default-conservative."""

    phase_o3_guardian_daily_iotx_budget: float = field(
        default_factory=lambda: float(_env("PHASE_O3_GUARDIAN_DAILY_IOTX_BUDGET", "0.0"))
    )
    """Phase O1-D-PATH-B v1 — Guardian's daily IOTX cap. Default 0.0 because
    Guardian's O3 actions are local writes only (no chain ops). Operator can
    raise if a future Guardian action requires chain submission."""

    phase_o3_curator_daily_iotx_budget: float = field(
        default_factory=lambda: float(_env("PHASE_O3_CURATOR_DAILY_IOTX_BUDGET", "0.5"))
    )
    """Phase O1-D-PATH-B v1 — Curator's daily IOTX cap. At ~0.001 IOTX per
    marketplace suspension, default 0.5 = ~500 suspensions/day budget."""

    phase_o3_executor_kill_all: bool = field(
        default_factory=lambda: _env_bool("PHASE_O3_EXECUTOR_KILL_ALL", False)
    )
    """Phase O1-D-PATH-B v1 — Emergency kill-all flag. When True, the live-write
    executor halts ALL agent executions regardless of per-agent flags. Single-
    flip safety hatch for the operator. Default False (executor allowed to
    operate when per-agent flags + budgets permit)."""

    phase_o3_executor_interval_s: int = field(
        default_factory=lambda: int(_env("PHASE_O3_EXECUTOR_INTERVAL_S", "60"))
    )
    """Phase O1-D-PATH-B v1 — Executor poll interval. 60s default; slower than
    the 30s polling-loop cadence to keep executor load light + spread chain
    op timing across cycles."""

    # --- Phase O1-D-AUTO-SUPERSEDE 2026-05-17 ---
    phase_o3_auto_supersede_enabled: bool = field(
        default_factory=lambda: _env_bool("PHASE_O3_AUTO_SUPERSEDE_ENABLED", False)
    )
    """Phase O1-D-AUTO-SUPERSEDE — Enable the Empirical-Evidence Supersession
    primitive (VAPI-O3-SUPERSEDE-v1).  When True, the
    operator_initiative_advancement watcher records a cryptographically-
    attested supersession event when all non-calendar O3 gates are
    empirically clear AND treats the 504h shadow_age calendar floor as
    satisfied.  Audit trail in operator_initiative_auto_supersede_log.
    Default False = opt-in (conservative; FROZEN safety behavior preserved
    unless operator explicitly enables for THIS cohort).  See
    bridge/vapi_bridge/operator_initiative_auto_supersede.py for the
    primitive + the docstring there for the architectural intent."""

    # --- Phase 235-GAD: Gameplay Activity Discrimination ---
    gameplay_discrimination_enabled: bool = field(
        default_factory=lambda: _env_bool("GAMEPLAY_DISCRIMINATION_ENABLED", True)
    )
    """Phase 235-GAD — Require trigger activity evidence for grind consecutive_clean.
    When True: gameplay_context=MENU_DETECTED breaks the streak (fail-closed on confirmed menu).
    NULL gameplay_context (pre-GAD or discrimination disabled) passes through.
    Default True (correctness gate, not optional feature)."""

    # --- Phase 241-APOP: Active Play Occupancy Proof ---
    active_play_occupancy_enabled: bool = field(
        default_factory=lambda: _env_bool("ACTIVE_PLAY_OCCUPANCY_ENABLED", True)
    )
    """Phase 241-APOP — compute controller-native active-play occupancy evidence."""

    active_play_occupancy_gate_mode: str = field(
        default_factory=lambda: _env("ACTIVE_PLAY_OCCUPANCY_GATE_MODE", "shadow")
    )
    """Phase 241-APOP — shadow|hybrid|strict. Default shadow preserves Phase 235-GAD."""

    # --- Phase 229: AIT Separation ---
    ait_separation_enabled: bool = field(
        default_factory=lambda: _env("AIT_SEPARATION_ENABLED", "true").lower() == "true"
    )
    """Phase 229 — Enable AIT (Active Isometric Trigger) separation status API.
    When True, GET /agent/ait-separation-status returns the latest AIT separation
    analysis result from ait_session_log.  Default True (infrastructure always on;
    data populated by analyze_interperson_separation.py --session-type ait --write-snapshot
    or POST /agent/run-ait-analysis)."""

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

    def get_oauth_clients(
        self,
        agent_names: "tuple[str, ...]" = ("SENTRY", "GUARDIAN"),
    ) -> "dict[str, tuple[str, list[str]]]":
        """Read OAUTH_CLIENT_ID_<AGENT> / OAUTH_CLIENT_SECRET_<AGENT> env vars.

        Phase O0 Stream 4-prep Decision A6: env-var-per-agent client
        credentials matching the existing OPERATOR_API_KEY pattern. Both
        SENTRY and GUARDIAN agents are issued the read-only Phase O0
        scope `bridge:agent:phases:read` per Pass 2C Section 5.1 line 801.

        Returns a dict {client_id: (client_secret, allowed_scopes)}. An
        agent is included only when both its CLIENT_ID and CLIENT_SECRET
        env vars are set; otherwise it is silently omitted. Empty dict
        means OAuth issuer cannot mint any tokens (will raise
        OAuthClientNotFound for every issue_token call).

        Read at call time (not at Config construction) so operators can
        rotate credentials without bridge restart by re-invoking the
        accessor — though FastAPI dependencies typically construct the
        OAuthIssuer once at app startup, so rotation in the live process
        is a Session 2 operational concern.
        """
        # Phase O0 scope vocabulary per Pass 2C Section 5.1 line 801.
        # Write scopes deferred to P1+; both agents share read-only scope.
        _PHASE_O0_AGENT_SCOPES = ["bridge:agent:phases:read"]

        clients: "dict[str, tuple[str, list[str]]]" = {}
        for agent_name in agent_names:
            client_id_env = f"OAUTH_CLIENT_ID_{agent_name.upper()}"
            client_secret_env = f"OAUTH_CLIENT_SECRET_{agent_name.upper()}"
            client_id = _env(client_id_env, "")
            client_secret = _env(client_secret_env, "")
            if client_id and client_secret:
                clients[client_id] = (client_secret, list(_PHASE_O0_AGENT_SCOPES))
        return clients

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
                # In dry_run mode (AGENT_DRY_RUN=true, the default), no private key is needed
                # because all chain writes are advisory and skipped. Only require the key when
                # live enforcement is explicitly activated.
                if not getattr(self, "agent_dry_run_mode", True):
                    errors.append(
                        "BRIDGE_PRIVATE_KEY is required when AGENT_DRY_RUN=false. "
                        "Add BRIDGE_PRIVATE_KEY=0x<64-char-hex> to bridge/.env."
                    )
        if not any([self.mqtt_enabled, self.coap_enabled,
                    self.http_enabled, self.dualshock_enabled]):
            errors.append("At least one transport must be enabled")
        return errors
