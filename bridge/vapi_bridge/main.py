"""
VAPI Bridge — Main entry point and orchestration.

Starts all enabled transports, the batcher, and the HTTP dashboard
as concurrent asyncio tasks. Handles graceful shutdown on SIGINT/SIGTERM.
"""

import asyncio
import json
import logging
import signal
import sys

from .batcher import Batcher
from .chain import ChainClient
from .codec import (
    PoACRecord,
    compute_device_id,
    parse_record,
    verify_signature,
)
from .config import Config
from .store import Store

log = logging.getLogger(__name__)


def _log_startup_diagnostics(cfg):
    """Log readiness status for Phase 28/29 features (Phase 29).

    Purely informational — never raises, never blocks startup.
    """
    from pathlib import Path
    _dlog = logging.getLogger("vapi_bridge.startup")
    circuits_dir = Path(__file__).parents[2] / "contracts" / "circuits"
    for circuit in ("TeamProof", "PitlSessionProof"):
        zkey = circuits_dir / f"{circuit}_final.zkey"
        _dlog.info("ZK %s: %s", circuit, "READY" if zkey.exists() else "MISSING (.zkey not found — run contracts/scripts/run-ceremony.js)")
    _dlog.info("PHGCredential: %s", getattr(cfg, "phg_credential_address", "") or "NOT SET")
    _dlog.info("OperatorAPI: %s", "ENABLED" if getattr(cfg, "operator_api_key", "") else "DISABLED (set OPERATOR_API_KEY to enable)")


async def _run_ds_with_restart(ds, max_restarts: int = 3) -> None:
    """Run DualShock transport and restart on unexpected crash (Phase 52).

    Passes CancelledError through immediately (clean shutdown). Any other
    exception is logged at ERROR level and the transport is restarted after a
    short delay, up to max_restarts times. After that the exception is re-raised
    so asyncio.gather() can surface it to the operator.
    """
    _restart_log = logging.getLogger(__name__)
    restarts = 0
    while True:
        try:
            await ds.run()
            return  # clean shutdown path
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            restarts += 1
            if restarts > max_restarts:
                _restart_log.critical(
                    "DualShock transport crashed %d times — giving up: %s",
                    restarts, exc,
                )
                raise
            _restart_log.error(
                "DualShock transport crashed (restart %d/%d in 2s): %s",
                restarts, max_restarts, exc,
            )
            await asyncio.sleep(2.0)
            _restart_log.info("Restarting DualShock transport (attempt %d)…", restarts)


def _task_done_handler(t: asyncio.Task) -> None:
    """Log CRITICAL when a managed bridge task dies unexpectedly (Phase 54)."""
    if t.cancelled():
        return
    exc = t.exception()
    if exc is not None:
        log.critical(
            "Bridge core task %s died unexpectedly: %s",
            t.get_name(), exc,
            exc_info=exc,
        )


class Bridge:
    """Top-level orchestrator for the VAPI bridge service."""

    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.store = Store(cfg.db_path)
        self.chain = ChainClient(cfg)
        self.batcher = Batcher(cfg, self.store, self.chain)
        self._tasks: list[asyncio.Task] = []
        self._ds_transport = None  # DualShockTransport, set in run() if dualshock_enabled

    async def on_record(self, raw_data: bytes, source: str):
        """
        Unified callback for all transports.

        Parses the record, validates it, persists it, and enqueues for batching.
        """
        # 1. Parse
        try:
            record = parse_record(raw_data)
        except ValueError as e:
            log.warning("Invalid record from %s: %s", source, e)
            raise

        # 2. Look up device public key
        # Try local store first, then on-chain registry
        device_id_hex = record.record_hash_hex  # placeholder until we have pubkey
        pubkey_hex = None

        # If we know this device, use cached pubkey
        # For now, try to fetch from on-chain registry
        # The device_id is keccak256(pubkey) but we need the pubkey to verify the sig
        # Chicken-and-egg: we need a device registration step or the pubkey in the payload

        # Strategy: devices must be pre-registered via the dashboard or auto-discovered
        # from on-chain DeviceRegistry. For first contact, we accept unverified records
        # and flag them for manual review.

        # Check if we can find the pubkey from any known device
        # whose chain state matches this record's prev_hash
        pubkey_bytes = await self._resolve_pubkey(record, source)

        # Tag schema version for known transports (Gate Fix A, Phase 19: from profile)
        pitl_meta = None  # Phase 52: initialise before dualshock block so it's always defined
        if source == "dualshock":
            if (self._ds_transport is not None
                    and getattr(self._ds_transport, "_device_profile", None) is not None):
                record.schema_version = self._ds_transport._device_profile.schema_version
            else:
                record.schema_version = 2  # backward-compat fallback

            # Phase 21: apply PITL sidecar metadata from DualShockTransport
            pitl_meta = getattr(self._ds_transport, "_pending_pitl_meta", None) \
                if self._ds_transport is not None else None
            if pitl_meta:
                record.pitl_l4_distance        = pitl_meta.get("l4_distance")
                record.pitl_l4_warmed_up       = pitl_meta.get("l4_warmed_up")
                record.pitl_l4_features_json   = pitl_meta.get("l4_features_json")
                record.pitl_l5_cv              = pitl_meta.get("l5_cv")
                record.pitl_l5_entropy_bits    = pitl_meta.get("l5_entropy_bits")
                record.pitl_l5_quant_score     = pitl_meta.get("l5_quant_score")
                record.pitl_l5_anomaly_signals = pitl_meta.get("l5_anomaly_signals")
                # Phase 25: agent intelligence sidecar fields
                record.pitl_l5_rhythm_humanity = pitl_meta.get("l5_rhythm_humanity")
                record.pitl_l4_drift_velocity  = pitl_meta.get("l4_drift_velocity")
                record.pitl_e4_cognitive_drift = pitl_meta.get("e4_cognitive_drift")
                record.pitl_humanity_prob      = pitl_meta.get("humanity_prob")

        if pubkey_bytes:
            device_id = compute_device_id(pubkey_bytes)
            record.device_id = device_id

            # 3. Verify signature
            if not verify_signature(record, pubkey_bytes):
                log.warning(
                    "Signature verification FAILED: device=%s counter=%d source=%s",
                    device_id.hex()[:16], record.monotonic_ctr, source,
                )
                raise ValueError("Invalid signature")

            log.info(
                "Record verified: device=%s counter=%d action=%s conf=%d src=%s",
                device_id.hex()[:16], record.monotonic_ctr,
                record.action_name, record.confidence, source,
            )

            # Update device state
            self.store.upsert_device(device_id.hex(), pubkey_bytes.hex())
            self.store.update_device_state(device_id.hex(), record)
        else:
            # No pubkey available — accept but log warning
            # Use record_hash as a temporary device_id for tracking
            record.device_id = record.record_hash
            log.warning(
                "No pubkey for record counter=%d — accepted unverified from %s",
                record.monotonic_ctr, source,
            )
            self.store.upsert_device(record.record_hash_hex, "unknown")
            self.store.update_device_state(record.record_hash_hex, record)

        # 4. Persist
        is_new = self.store.insert_record(record, raw_data)
        if not is_new:
            return  # Duplicate, skip

        # 5. Broadcast to WebSocket clients (Phase 21 — non-blocking, best-effort)
        # Phase 44: pass pitl_meta so enriched fields (L2B/L2C/l5_source) reach the frontend
        try:
            from .transports.http import ws_broadcast, _record_to_ws_msg, ws_twin_broadcast_record
            _ws_msg = _record_to_ws_msg(record, pitl_meta)
            asyncio.create_task(ws_broadcast(_ws_msg))
            # Phase 59: also send to per-device twin clients
            _twin_device_id = record.device_id.hex() if record.device_id else ""
            if _twin_device_id:
                _twin_msg = json.dumps({"type": "record", "data": json.loads(_ws_msg)})
                asyncio.create_task(ws_twin_broadcast_record(_twin_device_id, _twin_msg))
        except Exception as _ws_exc:
            log.error("WS broadcast failed (record=%s): %s",
                      record.record_hash.hex()[:8], _ws_exc)

        # 6. Enqueue for batching
        await self.batcher.enqueue(record, raw_data)

    async def _resolve_pubkey(
        self, record: PoACRecord, source: str
    ) -> bytes | None:
        """
        Attempt to find the public key for a record's signing device.

        Resolution order:
        1. Local store (device whose chain_head matches record.prev_poac_hash)
        2. On-chain DeviceRegistry
        """
        # Check all known devices for chain continuity
        devices = self.store.list_devices()
        for dev in devices:
            if dev["pubkey_hex"] == "unknown":
                continue
            if dev["chain_head"] == record.prev_poac_hash.hex():
                return bytes.fromhex(dev["pubkey_hex"])

        # For genesis records (prev_hash all zeros), check all registered devices
        if record.prev_poac_hash == b"\x00" * 32:
            for dev in devices:
                if dev["pubkey_hex"] != "unknown":
                    return bytes.fromhex(dev["pubkey_hex"])

        # Try on-chain registry (brute-force check is impractical; need device_id)
        # In production, the uplink message should include the device_id as a header
        return None

    async def run(self):
        """Start all services and run until shutdown."""
        # Validate configuration
        errors = self.cfg.validate()
        if errors:
            for err in errors:
                log.error("Config error: %s", err)
            sys.exit(1)

        log.info("=" * 60)
        log.info("VAPI Bridge v0.2.0-rc1 starting")
        log.info("=" * 60)
        _log_startup_diagnostics(self.cfg)
        log.info("IoTeX RPC: %s (chain_id=%d)", self.cfg.iotex_rpc_url, self.cfg.chain_id)
        log.info("Bridge wallet: %s", self.chain.bridge_address)
        log.info("Verifier: %s", self.cfg.verifier_address)
        if self.cfg.bounty_market_address:
            log.info("BountyMarket: %s", self.cfg.bounty_market_address)
        if self.cfg.device_registry_address:
            log.info("DeviceRegistry: %s", self.cfg.device_registry_address)
        log.info("Database: %s", self.cfg.db_path)

        try:
            balance = await self.chain.get_balance()
            log.info("Bridge balance: %.4f IOTX", balance)
            if balance < 1.0:
                log.warning("Low balance — bridge may fail to submit transactions")
        except Exception as e:
            log.warning("Could not fetch balance: %s", e)

        # Phase 79: Instantiate AgentMessageBus — shared in-process pub/sub
        # Must be initialized after event loop is running (asyncio.Lock requires running loop)
        from .agent_message_bus import AgentMessageBus
        _bus = AgentMessageBus()
        await _bus._init_lock()
        log.info("Phase 79: AgentMessageBus initialized (in-process pub/sub)")

        # Phase 104: Restore dry_run=False if activation_committed persisted in store
        _restore_activation_state(self.cfg, self.store)

        # Start batcher
        _t = asyncio.create_task(self.batcher.run())
        _t.add_done_callback(_task_done_handler)
        self._tasks.append(_t)

        # Start manufacturer revocation listener (Gate Fix G3)
        if self.cfg.device_registry_address:
            _t = asyncio.create_task(self.chain.watch_manufacturer_revocations())
            _t.add_done_callback(_task_done_handler)
            self._tasks.append(_t)
            log.info("Manufacturer revocation listener started")

        # Start enabled transports
        if self.cfg.mqtt_enabled:
            from .transports.mqtt import MqttTransport
            mqtt = MqttTransport(self.cfg, self.on_record)
            _t = asyncio.create_task(mqtt.run())
            _t.add_done_callback(_task_done_handler)
            self._tasks.append(_t)

        if self.cfg.coap_enabled:
            from .transports.coap import CoapTransport
            coap = CoapTransport(self.cfg, self.on_record)
            _t = asyncio.create_task(coap.run())
            _t.add_done_callback(_task_done_handler)
            self._tasks.append(_t)

        # Phase 32: Hoist intelligence modules so ProactiveMonitor and HTTP dashboard share instances
        from .behavioral_archaeologist import BehavioralArchaeologist
        from .continuity_prover import ContinuityProver
        from .network_correlation_detector import NetworkCorrelationDetector
        _arch = BehavioralArchaeologist(self.store)
        _prover = ContinuityProver(self.store)
        _net_det = NetworkCorrelationDetector(self.store, _prover)

        # Phase 52: Validate Anthropic API key at startup — agents appear initialised but
        # fail on first request without it. Warn early so operators know before hitting 500s.
        import os as _os_main
        if getattr(self.cfg, "operator_api_key", "") and not _os_main.getenv("ANTHROPIC_API_KEY"):
            log.warning(
                "ANTHROPIC_API_KEY not set — BridgeAgent and CalibrationIntelligenceAgent "
                "will raise AuthenticationError on first request"
            )

        # Phase 32: Eagerly create BridgeAgent with cross-device intelligence injection
        _agent_instance = None
        if getattr(self.cfg, "operator_api_key", ""):
            try:
                from .bridge_agent import BridgeAgent
                _agent_instance = BridgeAgent(
                    self.cfg, self.store,
                    behavioral_arch=_arch,
                    network_detector=_net_det,
                )
                log.info("BridgeAgent initialized eagerly with cross-device intelligence (Phase 32)")
            except ImportError:
                log.warning("anthropic not installed — BridgeAgent disabled")

        # Phase 50: Eagerly create CalibrationIntelligenceAgent peer
        _calib_intel_agent = None
        if getattr(self.cfg, "operator_api_key", ""):
            try:
                from .calibration_intelligence_agent import CalibrationIntelligenceAgent
                _calib_intel_agent = CalibrationIntelligenceAgent(self.cfg, self.store)
                _t = asyncio.create_task(_calib_intel_agent.run_event_consumer())
                _t.add_done_callback(_task_done_handler)
                self._tasks.append(_t)
                log.info("Phase 50: CalibrationIntelligenceAgent started (30-min event consumer)")
            except Exception as _cia_exc:
                log.warning("Phase 50: CalibrationIntelligenceAgent unavailable: %s", _cia_exc)

        if self.cfg.http_enabled:
            from .transports.http import create_app
            from .monitoring import create_monitoring_app, state as monitor_state
            from .dashboard_api import create_dashboard_app
            from .operator_api import create_operator_app
            import uvicorn

            app = create_app(self.cfg, self.store, self.on_record)
            mon_app = create_monitoring_app(cfg=self.cfg, state=monitor_state, store=self.store)
            app.mount("/monitor", mon_app)
            app.mount("/dash", create_dashboard_app(self.store, _arch, _net_det))
            app.mount("/operator", create_operator_app(
                self.cfg, self.store,
                _agent=_agent_instance,
                _calib_agent=_calib_intel_agent,
            ))
            config = uvicorn.Config(
                app,
                host=self.cfg.http_host,
                port=self.cfg.http_port,
                log_level=self.cfg.log_level.lower(),
                access_log=False,
            )
            server = uvicorn.Server(config)
            _t = asyncio.create_task(server.serve())
            _t.add_done_callback(_task_done_handler)
            self._tasks.append(_t)

        if self.cfg.dualshock_enabled:
            from .dualshock_integration import DualShockTransport
            from .continuity_prover import ContinuityProver
            from .pitl_prover import PITLProver, PITL_ZK_ARTIFACTS_AVAILABLE
            ds = DualShockTransport(self.cfg, self.store, self.on_record, self.chain)
            # Phase 23: inject continuity prover when Identity Registry is configured
            if getattr(self.cfg, "identity_registry_address", ""):
                ds._continuity_prover = ContinuityProver(
                    self.store,
                    threshold=getattr(self.cfg, "continuity_threshold", 2.0),
                )
                log.info(
                    "Phase 23: ContinuityProver active (threshold=%.1f)",
                    self.cfg.continuity_threshold,
                )
            # Phase 27: inject PITLProver for session-end ZK proof generation (always active)
            ds._pitl_prover = PITLProver()
            log.info("Phase 27: PITLProver injected (zk_artifacts=%s)", PITL_ZK_ARTIFACTS_AVAILABLE)
            self._ds_transport = ds
            _t = asyncio.create_task(_run_ds_with_restart(ds))
            _t.add_done_callback(_task_done_handler)
            self._tasks.append(_t)
            log.info("DualShock Edge transport enabled (interval=%.1fs)",
                     self.cfg.dualshock_record_interval_s)

            # Phase 26: WorldModelAttestation startup check (fix: _device_id_hex → _device_id.hex())
            _ewc = getattr(ds, "_ewc_model", None)
            _dev_id_hex = ds._device_id.hex() if hasattr(ds, "_device_id") and ds._device_id else None
            if _ewc is not None and _dev_id_hex:
                from .world_model_attestation import WorldModelAttestation
                _attest = WorldModelAttestation(self.store, _ewc)
                _ok, _reason = _attest.verify_current_weights(_dev_id_hex)
                if not _ok:
                    log.critical(
                        "EWC WEIGHT MISMATCH: %s — possible model poisoning attack!",
                        _reason,
                    )
                else:
                    log.info("WorldModelAttestation: %s", _reason)

        # Phase 25: Start chain reconciler for PHG checkpoint confirmation
        if getattr(self.cfg, "phg_registry_address", ""):
            from .chain_reconciler import ChainReconciler
            reconciler = ChainReconciler(
                self.store,
                self.chain,
                poll_interval=getattr(self.cfg, "reconciler_poll_interval", 30.0),
            )
            _t = asyncio.create_task(reconciler.run())
            _t.add_done_callback(_task_done_handler)
            self._tasks.append(_t)
            log.info(
                "Phase 25: ChainReconciler started (interval=%.0fs)",
                getattr(self.cfg, "reconciler_poll_interval", 30.0),
            )

        # Phase 32: Start ProactiveMonitor — autonomous protocol surveillance
        # Phase 52: decoupled from _agent_instance — starts whenever operator_api_key is set
        # so drift monitoring runs even when BridgeAgent init failed (e.g. anthropic absent).
        if getattr(self.cfg, "operator_api_key", ""):
            from .proactive_monitor import ProactiveMonitor
            # Phase 17: Auto-calibration agent (4th ProactiveMonitor surveillance check)
            _calibration_agent = None
            try:
                from .calibration_agent import CalibrationAgent
                _calibration_agent = CalibrationAgent(store=self.store, cfg=self.cfg)
                log.info("Phase 17: CalibrationAgent attached to ProactiveMonitor")
            except Exception as _cal_exc:
                log.warning("CalibrationAgent unavailable: %s", _cal_exc)
            monitor = ProactiveMonitor(
                self.store, _arch, _net_det, _agent_instance, self.cfg,
                poll_interval=getattr(self.cfg, "monitor_poll_interval", 60.0),
                calibration_agent=_calibration_agent,
            )
            _t = asyncio.create_task(monitor.run())
            _t.add_done_callback(_task_done_handler)
            self._tasks.append(_t)
            log.info(
                "Phase 32: ProactiveMonitor started (interval=%.0fs)",
                getattr(self.cfg, "monitor_poll_interval", 60.0),
            )

        # Phase 34: Start FederationBus — cross-bridge cluster correlation
        if getattr(self.cfg, "federation_peers", ""):
            try:
                import httpx  # validate httpx available before creating task
                from .federation_bus import FederationBus
                _fed_interval = getattr(self.cfg, "federation_poll_interval", 120.0)
                fed_bus = FederationBus(
                    self.store, _net_det, self.chain, self.cfg,
                    poll_interval=_fed_interval,
                )
                _t = asyncio.create_task(fed_bus.run())
                _t.add_done_callback(_task_done_handler)
                self._tasks.append(_t)
                log.info(
                    "Phase 34: FederationBus started (interval=%.0fs)",
                    _fed_interval,
                )
            except ImportError:
                log.warning("Phase 34: httpx not installed — FederationBus disabled")

        # Phase 35: InsightSynthesizer — longitudinal synthesis, always starts (no guard)
        from .insight_synthesizer import InsightSynthesizer
        _synth_interval = getattr(self.cfg, "synthesizer_poll_interval", 21600.0)
        # Phase 50: Mode 6 callback wires BridgeAgent drift detection
        _mode6_callback = (
            _agent_instance.check_threshold_drift if _agent_instance is not None else None
        )
        synth = InsightSynthesizer(
            self.store, self.cfg,
            poll_interval=_synth_interval,
            chain=self.chain,
            on_mode6_complete=_mode6_callback,
        )
        _t = asyncio.create_task(synth.run())
        _t.add_done_callback(_task_done_handler)
        self._tasks.append(_t)
        log.info("Phase 35: InsightSynthesizer started (interval=%.0fs)", _synth_interval)
        log.info(
            "Phase 36: Adaptive feedback loop active (floor=%.2f)",
            getattr(self.cfg, "policy_multiplier_floor", 0.5),
        )

        # Phase 37: AlertRouter — webhook dispatch for enforcement events (always starts)
        from .alert_router import AlertRouter
        _alert_router = AlertRouter(self.cfg, self.store)
        _t = asyncio.create_task(_alert_router.run())
        _t.add_done_callback(_task_done_handler)
        self._tasks.append(_t)
        log.info(
            "Phase 37: AlertRouter started (threshold=%s)",
            getattr(self.cfg, "alert_severity_threshold", "medium"),
        )
        log.info(
            "Phase 37: Credential enforcement active (min_consecutive=%d, base=%.0fd)",
            getattr(self.cfg, "credential_enforcement_min_consecutive", 2),
            getattr(self.cfg, "credential_suspension_base_days", 7.0),
        )

        # Phase 70: Wire all three autonomous agents into the main event loop.
        # Each agent runs as an independent asyncio task with _task_done_handler
        # so a crash in one does not kill the others.

        # DataCuratorAgent — always started; self-guards via cfg.curator_enabled
        try:
            from .data_curator_agent import DataCuratorAgent
            _curator = DataCuratorAgent(self.cfg, self.store, self.chain)
            _t = asyncio.create_task(_curator.run_poll_loop())
            _t.set_name("DataCuratorAgent")
            _t.add_done_callback(_task_done_handler)
            self._tasks.append(_t)
            log.info("Phase 70: DataCuratorAgent started (5-min poll, 7-class taxonomy)")
        except Exception as _dca_exc:
            log.warning("Phase 70: DataCuratorAgent unavailable: %s", _dca_exc)

        # SessionAdjudicator — guarded by operator_api_key configured
        if getattr(self.cfg, "operator_api_key", ""):
            try:
                from .session_adjudicator import SessionAdjudicator
                _adjudicator = SessionAdjudicator(self.cfg, self.store, bus=_bus)
                _t = asyncio.create_task(_adjudicator.run_event_consumer())
                _t.set_name("SessionAdjudicator")
                _t.add_done_callback(_task_done_handler)
                self._tasks.append(_t)
                log.info(
                    "Phase 70: SessionAdjudicator started (5-min poll, dry_run=%s)",
                    getattr(self.cfg, "agent_dry_run_mode", True),
                )
            except Exception as _sa_exc:
                log.warning("Phase 70: SessionAdjudicator unavailable: %s", _sa_exc)
        else:
            log.info("Phase 70: SessionAdjudicator skipped (OPERATOR_API_KEY not set)")

        # RulingEnforcementAgent — guarded by ruling_enforcement_enabled
        if getattr(self.cfg, "ruling_enforcement_enabled", False):
            try:
                from .ruling_enforcement_agent import RulingEnforcementAgent
                _enforcer = RulingEnforcementAgent(self.cfg, self.store, self.chain, bus=_bus)
                _t = asyncio.create_task(_enforcer.run_event_consumer())
                _t.set_name("RulingEnforcementAgent")
                _t.add_done_callback(_task_done_handler)
                self._tasks.append(_t)
                log.info("Phase 70: RulingEnforcementAgent started (streak escalation live)")
            except Exception as _rea_exc:
                log.warning("Phase 70: RulingEnforcementAgent unavailable: %s", _rea_exc)
        else:
            log.info("Phase 70: RulingEnforcementAgent skipped (RULING_ENFORCEMENT_ENABLED not set)")

        # Phase 75: SessionAdjudicatorValidationAgent — always started alongside SessionAdjudicator
        # Guards dry-run → live enforcement transition via consecutive_clean counter
        if getattr(self.cfg, "operator_api_key", ""):
            try:
                from .session_adjudicator_validator import SessionAdjudicatorValidationAgent
                _validator = SessionAdjudicatorValidationAgent(self.cfg, self.store, bus=_bus)
                _t = asyncio.create_task(_validator.run_event_consumer())
                _t.set_name("SessionAdjudicatorValidationAgent")
                _t.add_done_callback(_task_done_handler)
                self._tasks.append(_t)
                log.info(
                    "Phase 75: SessionAdjudicatorValidationAgent started "
                    "(gate_n=%d, divergence_threshold=%.2f)",
                    getattr(self.cfg, "validation_gate_n", 100),
                    getattr(self.cfg, "validation_divergence_threshold", 0.3),
                )
            except Exception as _sva_exc:
                log.warning("Phase 75: SessionAdjudicatorValidationAgent unavailable: %s", _sva_exc)
        else:
            log.info("Phase 75: SessionAdjudicatorValidationAgent skipped (OPERATOR_API_KEY not set)")

        # Phase 75: CeremonyWatchdogAgent — guarded by ceremony_watchdog_enabled
        # Polls CeremonyRegistry every 5 min; invalidates SA cache on key rotation (W1 mitigation)
        if getattr(self.cfg, "ceremony_watchdog_enabled", True):
            try:
                from .ceremony_watchdog import CeremonyWatchdogAgent
                _watchdog = CeremonyWatchdogAgent(self.cfg, self.store, bus=_bus)
                _t = asyncio.create_task(_watchdog.run_event_consumer())
                _t.set_name("CeremonyWatchdogAgent")
                _t.add_done_callback(_task_done_handler)
                self._tasks.append(_t)
                log.info(
                    "Phase 75: CeremonyWatchdogAgent started "
                    "(registry=%s, poll=300s)",
                    getattr(self.cfg, "ceremony_registry_address", "not-set")[:10] or "not-set",
                )
            except Exception as _cwa_exc:
                log.warning("Phase 75: CeremonyWatchdogAgent unavailable: %s", _cwa_exc)
        else:
            log.info("Phase 75: CeremonyWatchdogAgent skipped (CEREMONY_WATCHDOG_ENABLED=false)")

        # Phase 76: RulingProvenanceAnchorAgent — guarded by ruling_provenance_enabled
        # Computes SHA-256 provenance anchors binding ruling + ceremony + evidence
        if getattr(self.cfg, "ruling_provenance_enabled", True):
            try:
                from .ruling_provenance_anchor_agent import RulingProvenanceAnchorAgent
                _provenance = RulingProvenanceAnchorAgent(
                    self.cfg, self.store,
                    chain=self.chain if getattr(self.cfg, "ruling_provenance_publish_enabled", False) else None,
                )
                _t = asyncio.create_task(_provenance.run_event_consumer())
                _t.set_name("RulingProvenanceAnchorAgent")
                _t.add_done_callback(_task_done_handler)
                self._tasks.append(_t)
                log.info(
                    "Phase 76: RulingProvenanceAnchorAgent started "
                    "(publish_enabled=%s)",
                    getattr(self.cfg, "ruling_provenance_publish_enabled", False),
                )
            except Exception as _rpa_exc:
                log.warning("Phase 76: RulingProvenanceAnchorAgent unavailable: %s", _rpa_exc)
        else:
            log.info("Phase 76: RulingProvenanceAnchorAgent skipped (RULING_PROVENANCE_ENABLED=false)")

        # Phase 79: LiveModeActivationAgent — multi-condition live-mode readiness checker
        # Subscribes to dry_run_gate_passed via bus; emits advisory when all 5 conditions pass
        if getattr(self.cfg, "operator_api_key", ""):
            try:
                from .live_mode_activation_agent import LiveModeActivationAgent
                _live_mode = LiveModeActivationAgent(self.cfg, self.store, bus=_bus)
                _t = asyncio.create_task(_live_mode.run_event_consumer())
                _t.set_name("LiveModeActivationAgent")
                _t.add_done_callback(_task_done_handler)
                self._tasks.append(_t)
                log.info("Phase 79: LiveModeActivationAgent started (bus-subscribed)")
            except Exception as _lma_exc:
                log.warning("Phase 79: LiveModeActivationAgent unavailable: %s", _lma_exc)
        else:
            log.info("Phase 79: LiveModeActivationAgent skipped (OPERATOR_API_KEY not set)")

        # Phase 80: FederationBroadcastAgent — event-driven BLOCK ruling broadcaster
        # First purely event-driven agent in VAPI fleet (no polling loop)
        if getattr(self.cfg, "federation_broadcast_enabled", False):
            try:
                from .federation_broadcast_agent import FederationBroadcastAgent
                _federation = FederationBroadcastAgent(self.cfg, self.store, bus=_bus)
                _t = asyncio.create_task(_federation.run_event_consumer())
                _t.set_name("FederationBroadcastAgent")
                _t.add_done_callback(_task_done_handler)
                self._tasks.append(_t)
                log.info(
                    "Phase 80: FederationBroadcastAgent started (event-driven, peers=%d)",
                    len([p for p in getattr(self.cfg, "federation_broadcast_peers", "").split(",") if p.strip()]),
                )
            except Exception as _fba_exc:
                log.warning("Phase 80: FederationBroadcastAgent unavailable: %s", _fba_exc)
        else:
            log.info(
                "Phase 80: FederationBroadcastAgent skipped (FEDERATION_BROADCAST_ENABLED=false)"
            )

        # Phase 81: ClassJDetector — per-device ML-bot entropy variance detection
        if getattr(self.cfg, "class_j_detection_enabled", True):
            try:
                from .class_j_detector import ClassJDetector
                _class_j = ClassJDetector(self.cfg, self.store, bus=_bus)
                _t = asyncio.create_task(_class_j.run_poll_loop())
                _t.set_name("ClassJDetector")
                _t.add_done_callback(_task_done_handler)
                self._tasks.append(_t)
                log.info(
                    "Phase 81: ClassJDetector started (5-min poll, n_windows=%d)",
                    getattr(self.cfg, "class_j_entropy_windows", 10),
                )
            except Exception as _cj_exc:
                log.warning("Phase 81: ClassJDetector unavailable: %s", _cj_exc)
        else:
            log.info("Phase 81: ClassJDetector skipped (CLASS_J_DETECTION_ENABLED=false)")

        # Phase 83: AgentSupervisor — fleet health monitor
        if getattr(self.cfg, "supervisor_enabled", True):
            try:
                from .agent_supervisor import AgentSupervisor
                _supervisor = AgentSupervisor(self.cfg, self.store, bus=_bus)
                _t = asyncio.create_task(_supervisor.run_supervisor_loop())
                _t.set_name("AgentSupervisor")
                _t.add_done_callback(_task_done_handler)
                self._tasks.append(_t)
                log.info(
                    "Phase 83: AgentSupervisor started (stale_threshold=%dmin)",
                    getattr(self.cfg, "supervisor_stale_threshold_minutes", 15),
                )
            except Exception as _sup_exc:
                log.warning("Phase 83: AgentSupervisor unavailable: %s", _sup_exc)
        else:
            log.info("Phase 83: AgentSupervisor skipped (SUPERVISOR_ENABLED=false)")

        # Phase 89: ProtocolIntelligenceAgent — unified protocol_health_score synthesizer
        if getattr(self.cfg, "protocol_intelligence_enabled", True):
            try:
                from .protocol_intelligence_agent import ProtocolIntelligenceAgent
                _pia = ProtocolIntelligenceAgent(self.cfg, self.store, bus=_bus)
                _t = asyncio.create_task(_pia.run_event_consumer())
                _t.set_name("ProtocolIntelligenceAgent")
                _t.add_done_callback(_task_done_handler)
                self._tasks.append(_t)
                log.info("Phase 89: ProtocolIntelligenceAgent started")
            except Exception as _pia_exc:
                log.warning("Phase 89: ProtocolIntelligenceAgent unavailable: %s", _pia_exc)
        else:
            log.info("Phase 89: ProtocolIntelligenceAgent skipped (PROTOCOL_INTELLIGENCE_ENABLED=false)")

        # Phase 92: LiveModeActivationPipeline — automated readiness audit logger
        if getattr(self.cfg, "activation_pipeline_enabled", True):
            try:
                from .live_mode_activation_pipeline import LiveModeActivationPipeline
                _activation_pipeline = LiveModeActivationPipeline(self.cfg, self.store, bus=_bus)
                _t = asyncio.create_task(_activation_pipeline.run_poll_loop())
                _t.set_name("LiveModeActivationPipeline")
                _t.add_done_callback(_task_done_handler)
                self._tasks.append(_t)
                log.info("Phase 92: LiveModeActivationPipeline started (5-min audit poll)")
            except Exception as _lap_exc:
                log.warning("Phase 92: LiveModeActivationPipeline unavailable: %s", _lap_exc)
        else:
            log.info("Phase 92: LiveModeActivationPipeline skipped (ACTIVATION_PIPELINE_ENABLED=false)")

        # Phase 91: DivergenceTriageAgent — cross-session adversarial pattern detector
        if getattr(self.cfg, "divergence_triage_enabled", True):
            try:
                from .divergence_triage_agent import DivergenceTriageAgent
                _triage = DivergenceTriageAgent(self.cfg, self.store, bus=_bus)
                _t = asyncio.create_task(_triage.run_event_consumer())
                _t.set_name("DivergenceTriageAgent")
                _t.add_done_callback(_task_done_handler)
                self._tasks.append(_t)
                log.info("Phase 91: DivergenceTriageAgent started")
            except Exception as _triage_exc:
                log.warning("Phase 91: DivergenceTriageAgent unavailable: %s", _triage_exc)
        else:
            log.info("Phase 91: DivergenceTriageAgent skipped (DIVERGENCE_TRIAGE_ENABLED=false)")

        # Phase 99B: GSRRegistryAgent — physiological biometric layer (gsr_enabled=false default)
        if getattr(self.cfg, "gsr_enabled", False):
            try:
                from .gsr_registry_agent import GSRRegistryAgent
                _chain = getattr(self, "chain", None)
                _gsr = GSRRegistryAgent(self.cfg, self.store, chain=_chain, bus=_bus)
                _gt = asyncio.create_task(_gsr.run_poll_loop())
                _gt.set_name("GSRRegistryAgent")
                _gt.add_done_callback(_task_done_handler)
                self._tasks.append(_gt)
                log.info("Phase 99B: GSRRegistryAgent started (GSR_ENABLED=true)")
            except Exception as _gsr_exc:
                log.warning("Phase 99B: GSRRegistryAgent unavailable: %s", _gsr_exc)
        else:
            log.info("Phase 99B: GSRRegistryAgent skipped (GSR_ENABLED=false, default)")

        # Phase 102: VHPRenewalAgent — soulbound token TTL lifecycle manager (14th agent)
        if getattr(self.cfg, "vhp_renewal_enabled", True):
            try:
                from .vhp_renewal_agent import VHPRenewalAgent
                _chain_ref   = getattr(self, "chain", None)
                _vhp_renewal = VHPRenewalAgent(
                    self.cfg, self.store, chain=_chain_ref, bus=_bus
                )
                _vt = asyncio.create_task(_vhp_renewal.run_poll_loop())
                _vt.set_name("VHPRenewalAgent")
                _vt.add_done_callback(_task_done_handler)
                self._tasks.append(_vt)
                log.info(
                    "Phase 102: VHPRenewalAgent started (poll=6h, warning_days=%s)",
                    getattr(self.cfg, "vhp_renewal_warning_days", 7),
                )
            except Exception as _vhp_exc:
                log.warning("Phase 102: VHPRenewalAgent unavailable: %s", _vhp_exc)
        else:
            log.info("Phase 102: VHPRenewalAgent skipped (VHP_RENEWAL_ENABLED=false)")

        log.info("All services started — bridge is operational")

        # Wait for shutdown
        try:
            await asyncio.gather(*self._tasks)
        except asyncio.CancelledError:
            pass

    def shutdown(self):
        """Cancel all running tasks."""
        log.info("Shutdown requested")
        for task in self._tasks:
            task.cancel()


def _restore_activation_state(cfg, store) -> None:
    """Phase 104 W1 mitigation: restore dry_run=False on bridge restart if
    activation_committed=True in store. Runs BEFORE any agent tasks start.
    Uses object.__setattr__ because Config is @dataclass(frozen=True).
    """
    try:
        if not getattr(cfg, "activation_auto_restore", True):
            return
        state = store.get_activation_state()
        if state.get("activation_committed", False):
            object.__setattr__(cfg, "agent_dry_run_mode", False)
            log.info(
                "Phase 104: _restore_activation_state: restored dry_run=False "
                "(committed_at=%s, committed_by=%s)",
                state.get("committed_at"), state.get("committed_by"),
            )
    except Exception as exc:
        log.warning("Phase 104: _restore_activation_state failed: %s", exc)


def main():
    """CLI entry point."""
    cfg = Config()

    # Configure logging
    logging.basicConfig(
        level=getattr(logging, cfg.log_level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    bridge = Bridge(cfg)

    # Handle signals for graceful shutdown
    loop = asyncio.new_event_loop()
    for sig_name in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig_name, bridge.shutdown)
        except NotImplementedError:
            # Windows doesn't support add_signal_handler
            pass

    try:
        loop.run_until_complete(bridge.run())
    except KeyboardInterrupt:
        bridge.shutdown()
        loop.run_until_complete(asyncio.sleep(1))
    finally:
        loop.close()


if __name__ == "__main__":
    main()
