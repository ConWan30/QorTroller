"""
VAPI Bridge — Main entry point and orchestration.

Starts all enabled transports, the batcher, and the HTTP dashboard
as concurrent asyncio tasks. Handles graceful shutdown on SIGINT/SIGTERM.
"""

import asyncio
import json
import logging
import os
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
from .pcc_persistence import run_pcc_persistence_loop
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
        self.store = Store(cfg.db_path, consent_ledger_enabled=cfg.consent_ledger_enabled)
        self.chain = ChainClient(cfg)
        self.batcher = Batcher(cfg, self.store, self.chain)
        self._tasks: list[asyncio.Task] = []
        self._ds_transport = None  # DualShockTransport, set in run() if dualshock_enabled
        # Phase 235.x-STABILITY-7: explicit ThreadPoolExecutor wired in run()
        # when cfg.thread_pool_max_workers > 0. Init to None for attribute safety.
        self._thread_pool_executor = None
        # In-memory cache: prev_poac_hash_hex -> pubkey_bytes  (avoids 392ms list_devices() call per record)
        self._pubkey_cache: dict[str, bytes] = {}

    async def on_record(self, raw_data: bytes, source: str):
        """
        Unified callback for all transports.

        Parses the record, validates it, persists it, and enqueues for batching.

        Phase 235.x-STABILITY-4 (2026-05-09): heavy sync work (signature verify
        + 3 SQLite writes + PITL meta apply) runs on a worker thread via
        asyncio.to_thread when cfg.loop_persist_to_thread_enabled is True
        (default). Per-source record ordering is preserved by the caller's
        sequential await pattern (DualShockTransport awaits _dispatch one at
        a time per session_loop iter).
        """
        # 1. Parse — fast (< 1ms), keep on loop so malformed records raise early
        try:
            record = parse_record(raw_data)
        except ValueError as e:
            log.warning("Invalid record from %s: %s", source, e)
            raise

        # 2. Resolve pubkey (already async; cache hit dominates steady state)
        pubkey_bytes = await self._resolve_pubkey(record, source)

        # 3. Snapshot mutable transport state on loop thread BEFORE crossing
        #    to worker. _pending_pitl_meta and _device_profile are mutated by
        #    _session_loop on the loop thread; the snapshot must happen here
        #    so the worker thread sees a consistent view.
        pitl_meta = None
        schema_version_override = None
        if source == "dualshock":
            if (self._ds_transport is not None
                    and getattr(self._ds_transport, "_device_profile", None) is not None):
                schema_version_override = self._ds_transport._device_profile.schema_version
            pitl_meta = getattr(self._ds_transport, "_pending_pitl_meta", None) \
                if self._ds_transport is not None else None

        # 4. Heavy sync work (verify + 3 DB writes) → worker thread when enabled
        if getattr(self.cfg, "loop_persist_to_thread_enabled", True):
            is_new = await asyncio.to_thread(
                self._persist_record_sync,
                record, raw_data, pubkey_bytes, pitl_meta, source,
                schema_version_override,
            )
        else:
            is_new = self._persist_record_sync(
                record, raw_data, pubkey_bytes, pitl_meta, source,
                schema_version_override,
            )

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

    def _persist_record_sync(
        self,
        record: PoACRecord,
        raw_data: bytes,
        pubkey_bytes: bytes | None,
        pitl_meta: dict | None,
        source: str,
        schema_version_override: int | None,
    ) -> bool:
        """Phase 235.x-STABILITY-4 — sync body of on_record's persist phase.

        Runs in worker thread via asyncio.to_thread (or in-line when the
        loop_persist_to_thread_enabled flag is False). Performs:
          - PITL metadata application (sidecar fields onto the record)
          - schema_version assignment for known transports
          - ECDSA-P256 signature verification (~5-15ms typical)
          - Device upsert + state update + record insert (3 SQLite writes)

        Returns is_new (bool) — True when the record is freshly inserted,
        False when it's a duplicate (caller short-circuits on False).

        Raises ValueError on signature verification failure (preserves the
        pre-STABILITY-4 contract — caller must propagate to transport).

        Per-source record ordering is the caller's responsibility: a single
        source (e.g. DualShockTransport._session_loop) awaits each on_record
        call sequentially, so the to_thread submissions never overlap for
        that source. Cross-source races are intentional (each transport has
        its own chain).
        """
        # Phase 21: apply PITL sidecar metadata + schema version (was inline
        # in on_record pre-STABILITY-4; moved here so the mutation happens
        # on the worker thread alongside the persist writes).
        if source == "dualshock":
            if schema_version_override is not None:
                record.schema_version = schema_version_override
            else:
                record.schema_version = 2  # backward-compat fallback
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
                # Phase 235-GAD: trigger activity flag (1 = any L2/R2 press)
                record.pitl_trigger_active     = pitl_meta.get("trigger_active", 0)

        if pubkey_bytes:
            device_id = compute_device_id(pubkey_bytes)
            record.device_id = device_id

            # ECDSA-P256 verify — empirically the heaviest single sync call
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

            self.store.upsert_device(device_id.hex(), pubkey_bytes.hex())
            self.store.update_device_state(device_id.hex(), record)
        else:
            # No pubkey — accept unverified (will be flagged for review)
            record.device_id = record.record_hash
            log.warning(
                "No pubkey for record counter=%d — accepted unverified from %s",
                record.monotonic_ctr, source,
            )
            self.store.upsert_device(record.record_hash_hex, "unknown")
            self.store.update_device_state(record.record_hash_hex, record)

        return self.store.insert_record(record, raw_data)

    async def _resolve_pubkey(
        self, record: PoACRecord, source: str
    ) -> bytes | None:
        """
        Attempt to find the public key for a record's signing device.

        Resolution order:
        1. In-memory cache keyed by prev_poac_hash_hex — pre-populated after each resolved record
           so that the NEXT record (whose prev_poac_hash == current record_hash) is a cache hit.
        2. Local store (device whose chain_head matches record.prev_poac_hash)
        3. On-chain DeviceRegistry

        Phase 235.x-STABILITY-5 (2026-05-09): cache-miss path moved to a worker
        thread so the SQLite list_devices() scan doesn't block the event loop.
        Cache HIT remains synchronous (no thread-hop overhead for the steady-
        state path that handles every record after the first).
        """
        prev_hex = record.prev_poac_hash.hex()

        # Fast path: cache hit (every record after the first)
        if prev_hex in self._pubkey_cache:
            pk = self._pubkey_cache[prev_hex]
            # Pre-populate for the NEXT record in the chain
            self._pubkey_cache[record.record_hash_hex] = pk
            return pk

        # Slow path: cache miss → worker thread (boot-only or post-restart)
        if getattr(self.cfg, "loop_resolve_pubkey_to_thread_enabled", True):
            return await asyncio.to_thread(self._resolve_pubkey_miss_sync, record, prev_hex)
        return self._resolve_pubkey_miss_sync(record, prev_hex)

    def _resolve_pubkey_miss_sync(
        self, record: PoACRecord, prev_hex: str
    ) -> bytes | None:
        """Phase 235.x-STABILITY-5 — sync body of cache-miss pubkey resolution.

        Runs in worker thread via asyncio.to_thread. Performs:
          - store.list_devices() SQLite scan (the heavy step)
          - chain_head matching across registered devices
          - genesis-record fallback for prev_hash all zeros
          - cache pre-population

        Cache writes happen on this thread; that's safe because Python dict
        ops are atomic for individual __setitem__ / __getitem__ under the
        GIL, and there's no compound read-modify-write that another thread
        could observe in an inconsistent state. The bounded-eviction step
        (pop oldest when len > 4096) is also atomic dict-op level.
        """
        devices = self.store.list_devices()
        for dev in devices:
            if dev["pubkey_hex"] == "unknown":
                continue
            if dev["chain_head"] == prev_hex:
                pk = bytes.fromhex(dev["pubkey_hex"])
                self._pubkey_cache[prev_hex] = pk
                # Pre-populate for the next record in the chain
                self._pubkey_cache[record.record_hash_hex] = pk
                # Bound cache size to avoid unbounded growth
                if len(self._pubkey_cache) > 4096:
                    self._pubkey_cache.pop(next(iter(self._pubkey_cache)))
                return pk

        # For genesis records (prev_hash all zeros), check all registered devices
        if record.prev_poac_hash == b"\x00" * 32:
            for dev in devices:
                if dev["pubkey_hex"] != "unknown":
                    pk = bytes.fromhex(dev["pubkey_hex"])
                    self._pubkey_cache[prev_hex] = pk
                    self._pubkey_cache[record.record_hash_hex] = pk
                    return pk

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

        # Phase 235.x-STABILITY-7: explicit ThreadPoolExecutor sizing.
        # All asyncio.to_thread + run_in_executor(None, ...) call sites share
        # this pool (STABILITY-2 FSCA + STABILITY-4 on_record persist +
        # STABILITY-5 pubkey resolve + capture-health endpoint + 14 other
        # sites). asyncio's auto-default is min(32, cpu_count()+4) ≈ 32-36
        # workers; STABILITY-5 smoke saw 1 watchdog restart in 90s from
        # pool saturation. Default 64 = 2x headroom. Setting
        # THREAD_POOL_MAX_WORKERS=0 keeps asyncio's default (rollback path).
        _tpool_workers = int(getattr(self.cfg, "thread_pool_max_workers", 64))
        if _tpool_workers > 0:
            import concurrent.futures as _cf
            self._thread_pool_executor = _cf.ThreadPoolExecutor(
                max_workers=_tpool_workers,
                thread_name_prefix="vapi-persist",
            )
            asyncio.get_running_loop().set_default_executor(
                self._thread_pool_executor
            )
            log.info(
                "Phase 235.x-STABILITY-7: ThreadPoolExecutor configured "
                "(max_workers=%d, thread_name_prefix='vapi-persist')",
                _tpool_workers,
            )
        else:
            self._thread_pool_executor = None
            log.info(
                "Phase 235.x-STABILITY-7: ThreadPoolExecutor explicit "
                "sizing skipped (THREAD_POOL_MAX_WORKERS=0; using asyncio default)"
            )

        log.info("=" * 60)
        log.info("VAPI Bridge v0.2.0-rc1 starting")
        log.info("=" * 60)
        _log_startup_diagnostics(self.cfg)

        # Phase 235-A: GIC chain integrity check at startup
        try:
            _grind_sid = getattr(self.cfg, "grind_session_id", "")
            _grind_mode = bool(getattr(self.cfg, "grind_mode", False))
            log.info("=" * 60)
            log.info("GRIND SESSION ID : %s", _grind_sid or "(not set)")
            log.info("GRIND MODE       : %s", "ACTIVE" if _grind_mode else "INACTIVE")
            if _grind_mode and not os.environ.get("GRIND_SESSION_ID"):
                log.warning(
                    "GRIND_SESSION_ID not set in environment — auto-generated ID '%s'. "
                    "Set GRIND_SESSION_ID=grind_phase235_v1 in bridge/.env to persist "
                    "the same grind session ID across bridge restarts.",
                    _grind_sid,
                )
            log.info("=" * 60)
            _chain = self.store.get_grind_chain_status(_grind_sid, self.cfg)
            if _chain["chain_length"] > 0 and not _chain["chain_intact"]:
                log.critical(
                    "GIC CHAIN BROKEN — grind_session_id=%s chain_length=%d "
                    "Refusing to advance consecutive_clean until chain is repaired.",
                    _grind_sid, _chain["chain_length"],
                )
                self._gic_chain_broken = True
                self.store.set_gic_chain_broken(True)
            else:
                self._gic_chain_broken = False
                self.store.set_gic_chain_broken(False)
                if _chain["chain_length"] > 0:
                    log.info(
                        "GIC chain intact — grind_session_id=%s chain_length=%d",
                        _grind_sid, _chain["chain_length"],
                    )
        except Exception as _gic_e:
            log.warning("GIC startup check failed (non-fatal): %s", _gic_e)
            self._gic_chain_broken = False
            self.store.set_gic_chain_broken(False)

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

        # Phase 234.7 — instantiate CaptureHealthMonitor BEFORE both http_enabled
        # and dualshock_enabled blocks so we can wire the same instance into
        # the operator sub-app (read-only, for /bridge/capture-health) and into
        # DualShockTransport (write-side, called by _session_loop).
        # Without this wiring the monitor is None forever, /bridge/capture-health
        # falls back to a stale DB read, and grind_ready never flips True.
        from .capture_continuity import CaptureHealthMonitor
        self._pcc_monitor = CaptureHealthMonitor(cfg=self.cfg)

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
            _op_app = create_operator_app(
                self.cfg, self.store,
                _agent=_agent_instance,
                _calib_agent=_calib_intel_agent,
                chain=self.chain,   # Phase 237.5: wire ChainClient so anchor_corpus_snapshot
                                    # (and other previously-broken chain.* endpoints in
                                    # operator_api.py) can reach the bridge wallet.
            )
            _op_app._gic_chain_broken = getattr(self, "_gic_chain_broken", False)
            _op_app._pcc_monitor = self._pcc_monitor  # Phase 234.7 wiring

            # Phase 238 Step I-AUTOLOOP-3: ProtocolStateCache attached to
            # both apps so the SSE Twin stream endpoint can find it via
            # getattr(app, "_protocol_state_cache", None).  Cache creation
            # must happen here (inside http_enabled block) because _op_app
            # is a local var that only exists in this scope.  Heartbeat
            # task wired separately at the task-list section.
            try:
                from .protocol_state_cache import ProtocolStateCache
                _proto_state_cache = ProtocolStateCache()
                self.protocol_state_cache = _proto_state_cache
                _op_app._protocol_state_cache = _proto_state_cache
                app._protocol_state_cache = _proto_state_cache
                log.info("Phase 238 Step I-AUTOLOOP-3: ProtocolStateCache attached to operator + main apps")
            except Exception as _psc_exc:
                log.warning("Phase 238 Step I-AUTOLOOP-3: ProtocolStateCache attach failed: %s", _psc_exc)

            app.mount("/operator", _op_app)
            config = uvicorn.Config(
                app,
                host=self.cfg.http_host,
                port=self.cfg.http_port,
                log_level=self.cfg.log_level.lower(),
                access_log=False,
                # Phase 235.x-STABILITY 2026-05-07 — extended keep-alive.
                # Default is 5s; under frontend polling load (~3s capture-health
                # + 5s grind-chain + 30s drift-log) this churns connections
                # constantly, triggering the Windows _ProactorBasePipeTransport
                # connection-lost bug. 120s amortizes connection cost and
                # dramatically reduces close events.
                timeout_keep_alive=int(getattr(self.cfg, "uvicorn_timeout_keep_alive_s", 120)),
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
            # Phase 234.7: wire the shared CaptureHealthMonitor so _session_loop
            # actually feeds poll-rate samples into PCC.  Same instance is read
            # by /operator/bridge/capture-health.
            ds.set_pcc_monitor(self._pcc_monitor)
            log.info("Phase 234.7: CaptureHealthMonitor wired to DualShock transport")
            self._ds_transport = ds
            # Phase 235-CONTENTION: expose transport to operator app for hid_counter_restarts
            if self.cfg.http_enabled:
                try:
                    _op_app._transport = ds
                except NameError:
                    pass
            _t = asyncio.create_task(_run_ds_with_restart(ds))
            _t.add_done_callback(_task_done_handler)
            self._tasks.append(_t)
            log.info("DualShock Edge transport enabled (interval=%.1fs)",
                     self.cfg.dualshock_record_interval_s)
            if getattr(self.cfg, "pcc_enabled", True):
                _pcc_task = asyncio.create_task(
                    run_pcc_persistence_loop(self.store, self._pcc_monitor, self.cfg)
                )
                _pcc_task.add_done_callback(_task_done_handler)
                self._tasks.append(_pcc_task)
                log.info(
                    "Phase 235-PCC-PERSIST: capture-health persistence loop started"
                )

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
                _validator = SessionAdjudicatorValidationAgent(self.cfg, self.store, bus=_bus,
                                                               pcc_monitor=getattr(self, "_pcc_monitor", None))
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

        # Phase 112: PoAdAnchorAgent — on-chain anchoring of PoAd hashes
        if getattr(self.cfg, "poad_on_chain_enabled", False):
            try:
                from .poad_anchor_agent import PoAdAnchorAgent
                _chain_ref2   = getattr(self, "chain", None)
                _poad_anchor  = PoAdAnchorAgent(cfg=self.cfg, store=self.store, chain=_chain_ref2)
                _pat = asyncio.create_task(_poad_anchor.run_poll_loop())
                _pat.set_name("PoAdAnchorAgent")
                _pat.add_done_callback(_task_done_handler)
                self._tasks.append(_pat)
                log.info("Phase 112: PoAdAnchorAgent started (poll=%ds)", 60)
            except Exception as _poad_exc:
                log.warning("Phase 112: PoAdAnchorAgent unavailable: %s", _poad_exc)
        else:
            log.info("Phase 112: PoAdAnchorAgent skipped (POAD_ON_CHAIN_ENABLED=false, default)")

        # Phase 129: SeparationRatioMonitorAgent — agent #15
        # separation_ratio_monitor_enabled is not in config (always-on infrastructure)
        try:
            from .separation_ratio_monitor_agent import SeparationRatioMonitorAgent
            _srm = SeparationRatioMonitorAgent(self.cfg, self.store, bus=_bus)
            _srmt = asyncio.ensure_future(_srm.run_poll_loop())
            _srmt.set_name("SeparationRatioMonitorAgent")
            self._tasks.append(_srmt)
            log.info("Phase 129: SeparationRatioMonitorAgent started (poll=300s)")
        except Exception as _srm_exc:
            log.warning("Phase 129: SeparationRatioMonitorAgent unavailable: %s", _srm_exc)

        # Phase 135: TournamentActivationChainAgent — agent #16
        # auto_activate_on_breakthrough=False PERMANENT INVARIANT
        try:
            from .tournament_activation_chain_agent import TournamentActivationChainAgent
            _taca = TournamentActivationChainAgent(self.cfg, self.store, bus=_bus)
            _tacat = asyncio.ensure_future(_taca.run_event_consumer())
            _tacat.set_name("TournamentActivationChainAgent")
            self._tasks.append(_tacat)
            log.info(
                "Phase 135: TournamentActivationChainAgent started (agent #16; "
                "auto_activate_on_breakthrough=False PERMANENT)"
            )
        except Exception as _taca_exc:
            log.warning("Phase 135: TournamentActivationChainAgent unavailable: %s", _taca_exc)

        # Phase 148: AgentCalibrationMonitor — agent #18 (ACIM)
        # W1: cross-validates 16 agent invariants independently (no single-validator anti-pattern)
        if getattr(self.cfg, "agent_calibration_monitor_enabled", True):
            try:
                from .agent_calibration_monitor import AgentCalibrationMonitor
                _acim = AgentCalibrationMonitor(self.cfg, self.store, bus=_bus)
                _acim_task = asyncio.ensure_future(_acim.run_poll_loop())
                _acim_task.set_name("AgentCalibrationMonitor")
                self._tasks.append(_acim_task)
                log.info(
                    "Phase 148: AgentCalibrationMonitor started (agent #18; "
                    "poll=900s, 16 self-tests, W1 cross-validation)"
                )
            except Exception as _acim_exc:
                log.warning("Phase 148: AgentCalibrationMonitor unavailable: %s", _acim_exc)
        else:
            log.info("Phase 148: AgentCalibrationMonitor skipped (AGENT_CALIBRATION_MONITOR_ENABLED=false)")

        # Phase 155: ControllerHardwareIntelligenceAgent — agent #19
        # Registers DualShock Edge Attested profile; 5-min poll; multi_controller_enabled=False default.
        if getattr(self.cfg, "controller_intelligence_enabled", True):
            try:
                from .controller_hardware_intelligence_agent import ControllerHardwareIntelligenceAgent
                _chi = ControllerHardwareIntelligenceAgent(self.cfg, self.store, bus=_bus)
                _chi_task = asyncio.ensure_future(_chi.run_poll_loop())
                _chi_task.set_name("ControllerHardwareIntelligenceAgent")
                self._tasks.append(_chi_task)
                log.info(
                    "Phase 155: ControllerHardwareIntelligenceAgent started (agent #19; "
                    "poll=300s, multi_controller=%s)",
                    getattr(self.cfg, "multi_controller_enabled", False),
                )
            except Exception as _chi_exc:
                log.warning("Phase 155: ControllerHardwareIntelligenceAgent unavailable: %s", _chi_exc)
        else:
            log.info("Phase 155: ControllerHardwareIntelligenceAgent skipped (CONTROLLER_INTELLIGENCE_ENABLED=false)")

        # Phase 156: EnrollmentAutoGuidanceAgent — agent #20
        # Synthesizes Phase 151 + 152 + 154 + 155 guidance; 1-hour poll.
        if getattr(self.cfg, "enrollment_auto_guidance_enabled", True):
            try:
                from .enrollment_auto_guidance_agent import EnrollmentAutoGuidanceAgent
                _eag = EnrollmentAutoGuidanceAgent(self.cfg, self.store, bus=_bus)
                _eag_task = asyncio.ensure_future(_eag.run_poll_loop())
                _eag_task.set_name("EnrollmentAutoGuidanceAgent")
                self._tasks.append(_eag_task)
                log.info(
                    "Phase 156: EnrollmentAutoGuidanceAgent started (agent #20; "
                    "poll=%ss)",
                    getattr(self.cfg, "enrollment_guidance_poll_interval_s", 3600),
                )
            except Exception as _eag_exc:
                log.warning("Phase 156: EnrollmentAutoGuidanceAgent unavailable: %s", _eag_exc)
        else:
            log.info("Phase 156: EnrollmentAutoGuidanceAgent skipped (ENROLLMENT_AUTO_GUIDANCE_ENABLED=false)")

        # Phase 157: FleetConsensusSnapshotAgent — agent #21
        # Computes PoFC (Proof of Fleet Consensus) cryptographic snapshots every 30 min.
        if getattr(self.cfg, "fleet_consensus_enabled", True):
            try:
                from .fleet_consensus_snapshot_agent import FleetConsensusSnapshotAgent
                _fcs = FleetConsensusSnapshotAgent(self.cfg, self.store, bus=_bus)
                _fcs_task = asyncio.ensure_future(_fcs.run_poll_loop())
                _fcs_task.set_name("FleetConsensusSnapshotAgent")
                self._tasks.append(_fcs_task)
                log.info(
                    "Phase 157: FleetConsensusSnapshotAgent started (agent #21; "
                    "poll=%ss)",
                    getattr(self.cfg, "fleet_consensus_snapshot_interval_s", 1800),
                )
            except Exception as _fcs_exc:
                log.warning("Phase 157: FleetConsensusSnapshotAgent unavailable: %s", _fcs_exc)
        else:
            log.info("Phase 157: FleetConsensusSnapshotAgent skipped (FLEET_CONSENSUS_ENABLED=false)")

        # Phase 159: BiometricPrivacyComplianceAgent — agent #22
        # BP-001 Temporal Biometric Decay monitor; polls every 6h.
        if getattr(self.cfg, "biometric_privacy_enabled", True):
            try:
                from .biometric_privacy_compliance_agent import BiometricPrivacyComplianceAgent
                _bpca = BiometricPrivacyComplianceAgent(self.cfg, self.store, bus=_bus)
                _bpca_task = asyncio.ensure_future(_bpca.run_poll_loop())
                _bpca_task.set_name("BiometricPrivacyComplianceAgent")
                self._tasks.append(_bpca_task)
                log.info(
                    "Phase 159: BiometricPrivacyComplianceAgent started (agent #22; "
                    "BP-001 half_life=%.0fd)",
                    getattr(self.cfg, "bp001_half_life_days", 90.0),
                )
            except Exception as _bpca_exc:
                log.warning("Phase 159: BiometricPrivacyComplianceAgent unavailable: %s", _bpca_exc)
        else:
            log.info("Phase 159: BiometricPrivacyComplianceAgent skipped (BIOMETRIC_PRIVACY_ENABLED=false)")

        # Phase 173: SeparationRatioRecoveryAgent — agent #23
        # Detects P1 temporal non-stationarity (converging-downward ratio trend) and
        # recommends recovery actions (AGE_WEIGHTING / P1_RE_ENROLLMENT / MORE_SESSIONS).
        if getattr(self.cfg, "separation_recovery_enabled", True):
            try:
                from .separation_ratio_recovery_agent import SeparationRatioRecoveryAgent
                _srra = SeparationRatioRecoveryAgent(self.cfg, self.store, bus=_bus)
                _srra_task = asyncio.ensure_future(_srra.run_poll_loop())
                _srra_task.set_name("SeparationRatioRecoveryAgent")
                self._tasks.append(_srra_task)
                log.info(
                    "Phase 173: SeparationRatioRecoveryAgent started (agent #23; "
                    "poll=%ss min_sep=%.2f)",
                    getattr(self.cfg, "separation_recovery_poll_interval_s", 3600),
                    getattr(self.cfg, "min_separation_ratio", 0.70),
                )
            except Exception as _srra_exc:
                log.warning("Phase 173: SeparationRatioRecoveryAgent unavailable: %s", _srra_exc)
        else:
            log.info("Phase 173: SeparationRatioRecoveryAgent skipped (SEPARATION_RECOVERY_ENABLED=false)")

        # Phase 192: CorpusDataCuratorAgent (agent #35) — 7-task data coherence layer.
        # Runs 30-minute unified poll cycle. Each task is independently fail-open.
        # Tasks: provenance_dag | corpus_entropy | erasure_cert | federation_quality
        #        | correlation_engine | readiness_cert | contribution_weights
        # Depends on: SeparationRatioMonitorAgent (#15), AgeWeightedRatioPersistenceAgent (#24),
        #             PersonaBreakDetectorAgent (#27), BiometricCredentialTTLAgent (#29).
        try:
            from .corpus_curator_agent import CorpusDataCuratorAgent
            _curator192 = CorpusDataCuratorAgent(
                self.store, self.cfg, bus=_bus, logger=log
            )
            _curator192_task = asyncio.ensure_future(_curator192.run())
            _curator192_task.set_name("CorpusDataCuratorAgent")
            self._tasks.append(_curator192_task)
            log.info(
                "Phase 192: CorpusDataCuratorAgent started (agent #35; "
                "7-task data coherence layer; poll=%ss)",
                1800,
            )
        except Exception as _curator192_exc:
            log.warning(
                "Phase 192: CorpusDataCuratorAgent unavailable: %s", _curator192_exc
            )

        # Phase 193: FleetSignalCoherenceAgent (agent #36) — fleet-level coherence observer.
        # Polls every 900s (15 min). Detects contradictions / orphans / inversions across all
        # 35 agents. Auto-promotes persistent contradictions to VAPI_WHAT_IF.md (N>=3).
        # Depends on: data_provenance_dag (Phase 192 Task 1) for INVERSION rules.
        # The first agent whose primary output is WHAT_IF corpus entries, not operational signals.
        try:
            from .fleet_signal_coherence_agent import FleetSignalCoherenceAgent
            _fsca193 = FleetSignalCoherenceAgent(
                self.store, self.cfg, bus=_bus, logger=log
            )
            _fsca193_task = asyncio.ensure_future(_fsca193.run())
            _fsca193_task.set_name("FleetSignalCoherenceAgent")
            self._tasks.append(_fsca193_task)
            log.info(
                "Phase 193: FleetSignalCoherenceAgent started (agent #36; "
                "12 CONTRADICTION + 7 ORPHAN + 5 INVERSION rules; poll=%ss)",
                getattr(self.cfg, "coherence_poll_interval_seconds", 900),
            )
        except Exception as _fsca193_exc:
            log.warning(
                "Phase 193: FleetSignalCoherenceAgent unavailable: %s", _fsca193_exc
            )

        # Phase O1 C4: Cedar drift auto-sweep scheduler.
        # Operationalizes the C3 detect_*_drift primitives by running them on
        # monotonic interval gates (bundle 60s, scope 600s — INV-OPERATOR-AGENT-008
        # frozen dual-cadence). Without this, drift only surfaces on operator-
        # triggered POST. Default disabled (cedar_drift_sweep_enabled=False);
        # operator opts in via CEDAR_DRIFT_SWEEP_ENABLED=true in bridge/.env.
        # Fail-open: any sweep error is caught + logged; loop continues.
        if getattr(self.cfg, "cedar_drift_sweep_enabled", False):
            try:
                from .cedar_drift_sweeper import run_drift_sweep_loop
                _drift_sweep_task = asyncio.ensure_future(
                    run_drift_sweep_loop(
                        cfg=self.cfg, store=self.store, chain=self.chain,
                    )
                )
                _drift_sweep_task.set_name("CedarDriftSweeper")
                self._tasks.append(_drift_sweep_task)
                log.info(
                    "Phase O1 C4: cedar_drift_sweeper started "
                    "(bundle=%ds, scope=%ds)",
                    getattr(self.cfg, "cedar_drift_sweep_interval_bundle_s", 60),
                    getattr(self.cfg, "cedar_drift_sweep_interval_scope_s", 600),
                )
            except Exception as _drift_exc:
                log.warning(
                    "Phase O1 C4: cedar_drift_sweeper unavailable: %s", _drift_exc
                )

        # Phase O2-DRAFT-AUTOLOOP (Sentry/Guardian/Curator) — operator-agent
        # autonomous draft polling loops. Each loop wires the agent's already-
        # shipped draft-generator primitive surface (operator_agent_*_drafting.py)
        # to a trigger source. Default disabled per opt-in observability pattern;
        # operator activates per-agent via OPERATOR_AGENT_<X>_POLLING_ENABLED env
        # var. try/except ImportError is the de-conflict mechanism: until the
        # polling-loop module ships in Wave 1, the import fails silently and the
        # task slot is vacant. Once Wave 1 lands, importable + flag=True activates.
        if getattr(self.cfg, "operator_agent_sentry_polling_enabled", False):
            try:
                from .operator_agent_sentry_polling import run_sentry_polling_loop
                _sentry_poll_task = asyncio.ensure_future(
                    run_sentry_polling_loop(cfg=self.cfg, store=self.store)
                )
                _sentry_poll_task.set_name("SentryPollingLoop")
                self._tasks.append(_sentry_poll_task)
                log.info(
                    "Phase O2-DRAFT-AUTOLOOP (Sentry): polling loop started (interval=%ds)",
                    getattr(self.cfg, "operator_agent_sentry_polling_interval_s", 30),
                )
            except ImportError as _sp_exc:
                log.warning(
                    "Phase O2-DRAFT-AUTOLOOP (Sentry): module not available "
                    "(skipping; ships in Wave 1): %s", _sp_exc
                )
            except Exception as _sp_exc:
                log.warning(
                    "Phase O2-DRAFT-AUTOLOOP (Sentry): task creation failed: %s", _sp_exc
                )

        if getattr(self.cfg, "operator_agent_guardian_polling_enabled", False):
            try:
                from .operator_agent_guardian_polling import run_guardian_polling_loop
                _guardian_poll_task = asyncio.ensure_future(
                    run_guardian_polling_loop(cfg=self.cfg, store=self.store)
                )
                _guardian_poll_task.set_name("GuardianPollingLoop")
                self._tasks.append(_guardian_poll_task)
                log.info(
                    "Phase O2-DRAFT-AUTOLOOP (Guardian): polling loop started (interval=%ds)",
                    getattr(self.cfg, "operator_agent_guardian_polling_interval_s", 30),
                )
            except ImportError as _gp_exc:
                log.warning(
                    "Phase O2-DRAFT-AUTOLOOP (Guardian): module not available "
                    "(skipping; ships in Wave 1): %s", _gp_exc
                )
            except Exception as _gp_exc:
                log.warning(
                    "Phase O2-DRAFT-AUTOLOOP (Guardian): task creation failed: %s", _gp_exc
                )

        if getattr(self.cfg, "operator_agent_curator_polling_enabled", False):
            try:
                from .operator_agent_curator_polling import run_curator_polling_loop
                _curator_poll_task = asyncio.ensure_future(
                    run_curator_polling_loop(cfg=self.cfg, store=self.store)
                )
                _curator_poll_task.set_name("CuratorPollingLoop")
                self._tasks.append(_curator_poll_task)
                log.info(
                    "Phase O2-DRAFT-AUTOLOOP (Curator): polling loop started (interval=%ds)",
                    getattr(self.cfg, "operator_agent_curator_polling_interval_s", 30),
                )
            except ImportError as _cp_exc:
                log.warning(
                    "Phase O2-DRAFT-AUTOLOOP (Curator): module not available "
                    "(skipping; ships in Wave 1): %s", _cp_exc
                )
            except Exception as _cp_exc:
                log.warning(
                    "Phase O2-DRAFT-AUTOLOOP (Curator): task creation failed: %s", _cp_exc
                )

        # Phase 238 Step I-AUTOLOOP-3: SSE Twin stream heartbeat task.
        # Cache itself was attached above inside the http_enabled block.
        # Heartbeat fires every 15s to keep idle SSE connections alive
        # (frontend Twin controller EventSource clients).
        if getattr(self, "protocol_state_cache", None) is not None:
            try:
                from .protocol_state_cache import run_heartbeat_loop
                _heartbeat_task = asyncio.ensure_future(
                    run_heartbeat_loop(self.protocol_state_cache)
                )
                _heartbeat_task.set_name("ProtocolStateCacheHeartbeat")
                self._tasks.append(_heartbeat_task)
                log.info(
                    "Phase 238 Step I-AUTOLOOP-3: heartbeat loop started "
                    "(15s interval)"
                )
            except Exception as _hb_exc:
                log.warning(
                    "Phase 238 Step I-AUTOLOOP-3: heartbeat loop unavailable: %s",
                    _hb_exc,
                )

        # Phase 238 Step I-AUTOLOOP-1: Curator autonomous review loop.
        # Polls every 5 min (default), reviews any marketplace listing not
        # reviewed in past 1 h.  Default DISABLED via CURATOR_REVIEW_ENABLED;
        # operator opts in only after Step I-FINAL on-chain registration
        # (mint VAPIOperatorAgentNFT + dual-anchor Cedar bundle).  Until
        # then, the placeholder agentId 0xc0c0...c0c0 means policy enforcement
        # runs against an unregistered identity — operator-trigger only.
        # Fail-open: per-iteration errors caught + logged; loop continues.
        if getattr(self.cfg, "curator_review_enabled", False):
            try:
                from .curator_agent import run_curator_review_loop
                _curator_loop_task = asyncio.ensure_future(
                    run_curator_review_loop(
                        store=self.store, chain=self.chain, cfg=self.cfg,
                        protocol_state_cache=getattr(
                            self, "protocol_state_cache", None
                        ),
                    )
                )
                _curator_loop_task.set_name("CuratorReviewLoop")
                self._tasks.append(_curator_loop_task)
                log.info(
                    "Phase 238 Step I-AUTOLOOP-1: Curator review loop started "
                    "(interval=%.0fs, batch_limit=%d)",
                    getattr(self.cfg, "curator_review_interval_s", 300.0),
                    getattr(self.cfg, "curator_review_batch_limit", 25),
                )
            except Exception as _curator_exc:
                log.warning(
                    "Phase 238 Step I-AUTOLOOP-1: curator_agent unavailable: %s",
                    _curator_exc,
                )

        # Phase 235.x-STABILITY-3 2026-05-08: loop health monitor (WIF-065 closure).
        # Independent heartbeat task that detects asyncio event loop starvation
        # regardless of asyncio's debug mode. Closes the instrumentation gap
        # discovered in WIF-065 (asyncio's slow_callback warning is gated by
        # set_debug(True) which defaults OFF; STABILITY-2's threshold setting
        # had no effect, producing 0 warnings during 16 zombie events).
        # Default ENABLED. Lightweight (~one wakeup every 2s).
        if getattr(self.cfg, "loop_health_monitor_enabled", True):
            try:
                from .loop_health_monitor import run_loop_health_monitor
                _loop_health_task = asyncio.ensure_future(
                    run_loop_health_monitor(cfg=self.cfg)
                )
                _loop_health_task.set_name("LoopHealthMonitor")
                self._tasks.append(_loop_health_task)
                log.info(
                    "Phase 235.x-STABILITY-3: loop_health_monitor task started "
                    "(check=%.1fs, threshold=%.1fs)",
                    getattr(self.cfg, "loop_health_check_interval_s", 2.0),
                    getattr(self.cfg, "loop_health_starvation_threshold_s", 1.0),
                )
            except Exception as _lh_exc:
                log.warning(
                    "Phase 235.x-STABILITY-3: loop_health_monitor unavailable: %s",
                    _lh_exc,
                )

        # Phase 235-AUTO-TRIGGER: SessionBoundaryDetectorAgent (agent #38).
        # Heuristic detector that publishes ruling_request events on detected
        # session-end (sustained gameplay activity followed by extended trigger
        # quiescence) provided PCC is NOMINAL+EXCLUSIVE_USB.  Replaces manual
        # /agent/adjudicate POSTs during the 100-session grind.
        # Off by default (auto_trigger_enabled=False); operator opts in via
        # AUTO_TRIGGER_ENABLED=true in bridge/.env when starting the grind.
        # Safe to enable in idle bridges — does nothing without prior gameplay.
        if getattr(self.cfg, "auto_trigger_enabled", False):
            try:
                from .session_boundary_detector_agent import SessionBoundaryDetectorAgent
                _sbda = SessionBoundaryDetectorAgent(self.cfg, self.store, bus=_bus,
                                                     pcc_monitor=getattr(self, "_pcc_monitor", None))
                # Phase 235-DASH-UPGRADE: attach the agent instance to the
                # operator sub-app so /operator/agent/auto-trigger-status can
                # read live telemetry (mirrors how _pcc_monitor is attached).
                if self.cfg.http_enabled:
                    try:
                        _op_app._sbda = _sbda
                    except NameError:
                        # _op_app exists only when http_enabled was true; if
                        # the http block was skipped earlier, telemetry endpoint
                        # is also unreachable so the attach is harmless.
                        pass
                _sbda_task = asyncio.ensure_future(_sbda.run_poll_loop())
                _sbda_task.set_name("SessionBoundaryDetectorAgent")
                self._tasks.append(_sbda_task)
                log.info(
                    "Phase 235-AUTO-TRIGGER: SessionBoundaryDetectorAgent started "
                    "(agent #38; poll=%ds; min_interval=%ds)",
                    SessionBoundaryDetectorAgent.POLL_INTERVAL_S,
                    int(getattr(self.cfg, "auto_trigger_min_interval_s", 300)),
                )
            except Exception as _sbda_exc:
                log.warning(
                    "Phase 235-AUTO-TRIGGER: SessionBoundaryDetectorAgent unavailable: %s",
                    _sbda_exc,
                )
        else:
            log.info(
                "Phase 235-AUTO-TRIGGER: SessionBoundaryDetectorAgent skipped "
                "(AUTO_TRIGGER_ENABLED=false; manual /agent/adjudicate triggers required)"
            )

        # Phase 222: BiometricGovernanceAgent (agent #38) — BBG VHP-gated governance.
        # Validates governance proposals against the proposer's live VHP.
        # bbg_enabled=False default — requires BBG_CONTRACT_ADDRESS to activate.
        if getattr(self.cfg, "bbg_enabled", False):
            try:
                from .biometric_governance_agent import BiometricGovernanceAgent
                _bga222 = BiometricGovernanceAgent(
                    self.store, self.cfg,
                    chain=self.chain if getattr(self.cfg, "bbg_contract_address", "") else None,
                    logger=log,
                )
                _bga222_task = asyncio.ensure_future(_bga222.run_poll_loop())
                _bga222_task.set_name("BiometricGovernanceAgent")
                self._tasks.append(_bga222_task)
                log.info(
                    "Phase 222: BiometricGovernanceAgent started (agent #38; "
                    "bbg_max_age_sec=%d)",
                    getattr(self.cfg, "bbg_max_age_seconds", 3600),
                )
            except Exception as _bga222_exc:
                log.warning(
                    "Phase 222: BiometricGovernanceAgent unavailable: %s", _bga222_exc
                )
        else:
            log.info("Phase 222: BiometricGovernanceAgent skipped (BBG_ENABLED=false)")

        # Phase 221: ProtocolCoherenceAgent (agent #37) — PoPC Merkle root anchor.
        # Computes Merkle root over 36 agent fleet observations; anchors on-chain when
        # protocol_coherence_registry_address is set.  protocol_coherence_enabled=False default.
        if getattr(self.cfg, "protocol_coherence_enabled", False):
            try:
                from .protocol_coherence_agent import ProtocolCoherenceAgent
                _pca221 = ProtocolCoherenceAgent(
                    self.store, self.cfg,
                    chain=self.chain if getattr(self.cfg, "protocol_coherence_registry_address", "") else None,
                    logger=log,
                )
                _pca221_task = asyncio.ensure_future(_pca221.run_poll_loop())
                _pca221_task.set_name("ProtocolCoherenceAgent")
                self._tasks.append(_pca221_task)
                log.info(
                    "Phase 221: ProtocolCoherenceAgent started (agent #37; "
                    "poll=%ss)",
                    getattr(self.cfg, "protocol_coherence_anchor_interval_s", 3600),
                )
            except Exception as _pca221_exc:
                log.warning(
                    "Phase 221: ProtocolCoherenceAgent unavailable: %s", _pca221_exc
                )
        else:
            log.info("Phase 221: ProtocolCoherenceAgent skipped (PROTOCOL_COHERENCE_ENABLED=false)")

        # Phase 203: AgentContextRegistry — commit SHA-256 of each LLM agent system
        # prompt to agent_context_log at startup. Enables CONTEXT_HASH_MISMATCH INVERSION
        # rule in FleetSignalCoherenceAgent to detect unregistered or drifted prompts.
        # Fail-open: never raises — bridge startup is never blocked by hash registration.
        try:
            import hashlib as _hashlib203
            _phase203_agents: list = []
            try:
                from . import bridge_agent as _ba_mod203
                _ba_prompt = getattr(_ba_mod203, "_SYSTEM_PROMPT", None)
                if _ba_prompt:
                    _phase203_agents.append(("bridge_agent", _ba_prompt))
            except Exception:
                pass
            try:
                from . import session_adjudicator as _sa_mod203
                _sa_prompt = getattr(_sa_mod203, "_SYSTEM_PROMPT", None)
                if _sa_prompt:
                    _phase203_agents.append(("session_adjudicator", _sa_prompt))
            except Exception:
                pass
            try:
                from . import calibration_intelligence_agent as _cia_mod203
                _cia_prompt = getattr(_cia_mod203, "_CALIB_SYSTEM_PROMPT", None)
                if _cia_prompt:
                    _phase203_agents.append(("calibration_intelligence_agent", _cia_prompt))
            except Exception:
                pass
            _current_phase203 = 203
            for _aid203, _prompt203 in _phase203_agents:
                _sha203 = _hashlib203.sha256(_prompt203.encode()).hexdigest()
                self.store.upsert_agent_context_hash(_aid203, _sha203, _current_phase203)
            if _phase203_agents:
                log.info(
                    "Phase 203: registered %d agent context hash(es) in agent_context_log",
                    len(_phase203_agents),
                )
        except Exception as _ctx203_exc:
            log.warning("Phase 203: agent context hash registration failed: %s", _ctx203_exc)

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

    # Phase 235.x-STABILITY 2026-05-07 — defensive exception handler.
    # Suppresses cascading event-loop crashes from Windows
    # _ProactorBasePipeTransport._call_connection_lost when uvicorn HTTP
    # connections close mid-flight (chronic Windows asyncio bug; cause of
    # the "bridge zombie" pattern documented across multiple sessions).
    # Without this handler, repeated connection-close errors accumulate
    # until uvicorn stops accepting connections while the loop spins on
    # other tasks. With this handler, each error is logged + the loop
    # continues serving requests.
    def _stability_exception_handler(_loop, ctx):
        exc = ctx.get("exception")
        msg = ctx.get("message", "")
        is_proactor_close = (
            "_call_connection_lost" in msg
            or (exc is not None and "_call_connection_lost" in repr(exc))
        )
        if is_proactor_close:
            # Known Windows asyncio bug — log and continue.
            log.warning(
                "Phase 235.x-STABILITY: suppressed Proactor connection-lost "
                "callback (msg=%s exc=%s)",
                msg[:80], type(exc).__name__ if exc else "None",
            )
            return
        # Unknown error — defer to default handler (logs + may crash loop)
        _loop.default_exception_handler(ctx)

    loop.set_exception_handler(_stability_exception_handler)

    # Phase 235.x-STABILITY-2 2026-05-08 — asyncio loop-block instrumentation
    # per WIF-064. Empirical finding: bridge zombie pattern is loop-blocking
    # sync work (12-30s windows where event loop can't accept new HTTP
    # connections), NOT the Proactor _call_connection_lost crashes that
    # 235.x-STABILITY targeted. Setting asyncio.slow_callback_duration to
    # 1.0s logs every callback that exceeds that threshold, identifying the
    # culprit by name. opt-in via ASYNCIO_DEBUG_ENABLED=true.
    _slow_threshold = float(getattr(cfg, "asyncio_slow_callback_threshold_s", 1.0))
    if getattr(cfg, "asyncio_debug_enabled", False):
        loop.set_debug(True)
        loop.slow_callback_duration = _slow_threshold
        log.warning(
            "Phase 235.x-STABILITY-2: asyncio debug ENABLED, slow_callback_duration=%.1fs",
            _slow_threshold,
        )
    else:
        # Even without debug mode, raise the slow-callback threshold so
        # asyncio's built-in warning fires for our zombie pattern signature.
        loop.slow_callback_duration = _slow_threshold

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
