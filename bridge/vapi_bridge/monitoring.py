"""
VAPI Phase 18 — Production Monitoring Sub-Application

FastAPI sub-app mounted at /monitor in main.py.
Provides three endpoints for operational observability:

    GET /monitor/health
        Liveness + readiness check. Returns bridge uptime, last submitted
        transaction, chain RPC connectivity, and record counters.
        Suitable for load-balancer health checks.

    GET /monitor/metrics
        Throughput and error metrics. Returns active device count,
        records-per-minute, batch-size average, and error rate.
        Suitable for Prometheus scraping (JSON format).

    GET /monitor/alerts
        Active alert conditions. Returns a list of alert objects
        (each with severity, message, raised_at). Empty list = healthy.
        Suitable for PagerDuty / Grafana polling.

MonitoringState is a module-level singleton. Components update it via:
    from vapi_bridge.monitoring import state as monitoring_state
    monitoring_state.record_submitted(tx_hash)
    monitoring_state.record_rpc_error()
    monitoring_state.record_batch(size)
"""

from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Optional

from fastapi import FastAPI
from fastapi.responses import PlainTextResponse

_log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Monitoring state singleton
# ---------------------------------------------------------------------------

@dataclass
class MonitoringState:
    """
    Thread-safe-ish monitoring state (asyncio single-threaded; no locks needed).

    Updated by bridge components on each significant event. Read by the
    monitoring endpoints on each HTTP request.
    """
    _start_time: float = field(default_factory=time.monotonic)
    records_submitted: int = 0
    records_failed: int = 0
    last_tx_hash: str = ""
    last_submit_time: float = 0.0
    active_devices: int = 0
    total_batches: int = 0
    total_batch_size: int = 0
    rpc_errors: int = 0
    last_rpc_check: float = 0.0
    last_rpc_ok: bool = True
    # Sliding window for records-per-minute (timestamp of each submit, max 1000)
    _submit_times: list = field(default_factory=list)
    # Total records dropped due to a full batcher queue (incremented by Batcher.enqueue)
    records_dropped: int = 0
    # VBSV: controller presence at bridge startup (set by lifespan handler)
    controller_detected_at_startup: Optional[bool] = None
    startup_manifest: dict = field(default_factory=dict)

    def record_dropped(self) -> None:
        """Call when a record is dropped because the batcher queue is full."""
        self.records_dropped += 1

    def record_submitted(self, tx_hash: str = "") -> None:
        """Call after each successful PoAC record submission to the chain."""
        self.records_submitted += 1
        self.last_tx_hash = tx_hash
        self.last_submit_time = time.monotonic()
        now = time.time()
        self._submit_times.append(now)
        # Keep only last 5 minutes of timestamps
        cutoff = now - 300
        self._submit_times = [t for t in self._submit_times if t > cutoff]

    def record_failed(self) -> None:
        """Call when a record submission fails after all retries."""
        self.records_failed += 1

    def record_batch(self, size: int) -> None:
        """Call after each batch is submitted with the batch size."""
        self.total_batches += 1
        self.total_batch_size += size

    def record_rpc_error(self) -> None:
        """Call when an RPC call fails."""
        self.rpc_errors += 1
        self.last_rpc_ok = False
        self.last_rpc_check = time.monotonic()

    def record_rpc_ok(self) -> None:
        """Call when an RPC call succeeds (clear error flag)."""
        self.last_rpc_ok = True
        self.last_rpc_check = time.monotonic()

    def update_active_devices(self, count: int) -> None:
        """Call when the device count changes."""
        self.active_devices = count

    @property
    def uptime_s(self) -> float:
        return time.monotonic() - self._start_time

    @property
    def records_per_minute(self) -> float:
        now = time.time()
        cutoff = now - 60
        recent = [t for t in self._submit_times if t > cutoff]
        return float(len(recent))

    @property
    def batch_size_avg(self) -> float:
        if self.total_batches == 0:
            return 0.0
        return self.total_batch_size / self.total_batches

    @property
    def error_rate(self) -> float:
        total = self.records_submitted + self.records_failed
        if total == 0:
            return 0.0
        return self.records_failed / total


# Module-level singleton — imported by other bridge components
state = MonitoringState()


# ---------------------------------------------------------------------------
# Alert detection
# ---------------------------------------------------------------------------

def _compute_alerts(s: MonitoringState) -> list[dict]:
    """Compute active alert conditions from the current monitoring state."""
    alerts = []

    # Alert: RPC endpoint unreachable
    if not s.last_rpc_ok and s.last_rpc_check > 0:
        alerts.append({
            "severity": "critical",
            "code": "RPC_UNREACHABLE",
            "message": "IoTeX RPC endpoint is not responding",
            "raised_at": s.last_rpc_check,
        })

    # Alert: high error rate (>10% after at least 10 attempts)
    total = s.records_submitted + s.records_failed
    if total >= 10 and s.error_rate > 0.10:
        alerts.append({
            "severity": "warning",
            "code": "HIGH_ERROR_RATE",
            "message": f"Record submission error rate is {s.error_rate:.1%} (threshold: 10%)",
            "raised_at": time.monotonic(),
        })

    # Alert: no records submitted in last 5 minutes (bridge may be stalled)
    if s.uptime_s > 300 and s.last_submit_time > 0:
        time_since_last = time.monotonic() - s.last_submit_time
        if time_since_last > 300:
            alerts.append({
                "severity": "warning",
                "code": "NO_RECENT_SUBMISSIONS",
                "message": f"No records submitted in {time_since_last:.0f}s (threshold: 300s)",
                "raised_at": s.last_submit_time,
            })

    # Alert: no active devices (bridge started but nothing connected)
    if s.uptime_s > 60 and s.active_devices == 0:
        alerts.append({
            "severity": "info",
            "code": "NO_ACTIVE_DEVICES",
            "message": "No active devices detected since bridge started",
            "raised_at": s._start_time,
        })

    return alerts


# ---------------------------------------------------------------------------
# FastAPI sub-application
# ---------------------------------------------------------------------------

def create_monitoring_app(
    cfg=None, state: MonitoringState = None, store=None
) -> FastAPI:
    """Create a monitoring FastAPI sub-app with Prometheus-compatible /metrics.

    Phase 36: accepts optional `store` to expose synthesis gauges.
    """
    _state = state or globals().get("state") or MonitoringState()
    _store = store

    # VBSV: Bridge Startup Validation — probe controller presence at HTTP service start.
    # Non-blocking: runs once at uvicorn startup, never prevents bridge from serving.
    @asynccontextmanager
    async def _lifespan(app: FastAPI):
        # ── startup ──────────────────────────────────────────────────────────
        import importlib, sys as _sys
        _controller_present: Optional[bool] = None
        try:
            _hid = importlib.import_module("hid")
            _devs = _hid.enumerate(0x054C, 0x0DF2)  # DualShock Edge VID/PID
            _controller_present = len(_devs) > 0
        except Exception:
            pass  # hid not installed or device enumerate failed — non-fatal; fail-open: M-1 cleanup 2026-05-16

        _state.controller_detected_at_startup = _controller_present
        _state.startup_manifest = {
            "fastapi": importlib.import_module("fastapi").__version__,
            "starlette": importlib.import_module("starlette").__version__,
            "python": f"{_sys.version_info.major}.{_sys.version_info.minor}.{_sys.version_info.micro}",
            "controller_present": _controller_present,
            "startup_ts": time.time(),
        }

        if _controller_present is True:
            _log.info("VBSV: DualShock Edge detected at startup (VID=054C PID=0DF2)")
        elif _controller_present is False:
            _log.warning(
                "VBSV: DualShock Edge NOT detected at startup — "
                "plug controller via USB then restart bridge or wait for auto-reconnect"
            )
        else:
            _log.debug("VBSV: hid module unavailable — controller probe skipped (pip install hidapi)")

        yield
        # ── shutdown ─────────────────────────────────────────────────────────
        _log.info("VAPI monitoring sub-app shutdown (uptime=%.0fs)", _state.uptime_s)

    app = FastAPI(
        title="VAPI Monitoring",
        description="Operational health, metrics, and alerts for the VAPI bridge",
        version="1.0.0-phase36",
        docs_url="/docs",
        redoc_url=None,
        lifespan=_lifespan,
    )

    @app.get("/health")
    async def health() -> dict:
        """Liveness and readiness check."""
        alerts = _compute_alerts(_state)
        status = "degraded" if any(a["severity"] == "critical" for a in alerts) else "ok"
        return {
            "status": status,
            "uptime_s": round(_state.uptime_s, 1),
            "records_submitted": _state.records_submitted,
            "records_failed": _state.records_failed,
            "last_tx_hash": _state.last_tx_hash,
            "chain_rpc_ok": _state.last_rpc_ok,
            "active_devices": _state.active_devices,
            "alerts_count": len(alerts),
            # VBSV fields (None = probe not yet run / hid unavailable)
            "controller_detected_at_startup": _state.controller_detected_at_startup,
            "startup_manifest": _state.startup_manifest,
        }

    @app.get("/metrics", response_class=PlainTextResponse)
    async def metrics():
        """Prometheus-compatible text format metrics endpoint (Phase 36)."""
        lines = []

        def _gauge(name, help_text, value):
            lines.append(f"# HELP {name} {help_text}")
            lines.append(f"# TYPE {name} gauge")
            lines.append(f"{name} {value}")

        def _counter(name, help_text, value):
            lines.append(f"# HELP {name} {help_text}")
            lines.append(f"# TYPE {name} counter")
            lines.append(f"{name} {value}")

        _counter("vapi_records_submitted_total",
                 "Total PoAC records successfully submitted to chain",
                 _state.records_submitted)
        _counter("vapi_records_failed_total",
                 "Total PoAC records that failed after all retries",
                 _state.records_failed)
        _counter("vapi_records_dropped_total",
                 "Total PoAC records dropped due to full batcher queue",
                 _state.records_dropped)
        _gauge("vapi_records_per_minute",
               "Rolling 60-second PoAC record submission rate",
               round(_state.records_per_minute, 2))
        _gauge("vapi_active_devices",
               "Number of active devices seen by the bridge",
               _state.active_devices)
        _counter("vapi_rpc_errors_total",
                 "Total RPC call failures since bridge started",
                 _state.rpc_errors)
        _gauge("vapi_uptime_seconds",
               "Bridge uptime in seconds",
               round(_state.uptime_s, 1))

        # Phase 36: Synthesis gauges from store (default 0 if unavailable)
        critical_devices = 0
        warming_devices = 0
        digests_synthesized = 0
        active_policies = 0
        if _store is not None:
            try:
                critical_devices = len(_store.get_devices_by_risk_label("critical"))
            except Exception:
                pass  # fail-open: M-1 cleanup 2026-05-16 — intentional silent skip
            try:
                warming_devices = len(_store.get_devices_by_risk_label("warming"))
            except Exception:
                pass  # fail-open: M-1 cleanup 2026-05-16 — intentional silent skip
            try:
                digests_synthesized = len(_store.get_all_latest_digests())
            except Exception:
                pass  # fail-open: M-1 cleanup 2026-05-16 — intentional silent skip
            try:
                active_policies = len(_store.get_all_active_policies())
            except Exception:
                pass  # fail-open: M-1 cleanup 2026-05-16 — intentional silent skip

        _gauge("vapi_critical_devices",
               "Devices currently labeled critical by InsightSynthesizer",
               critical_devices)
        _gauge("vapi_warming_devices",
               "Devices currently labeled warming by InsightSynthesizer",
               warming_devices)
        _gauge("vapi_digests_synthesized",
               "Number of active longitudinal insight digests",
               digests_synthesized)
        _gauge("vapi_active_detection_policies",
               "Number of active adaptive detection policies",
               active_policies)

        return "\n".join(lines) + "\n"

    @app.get("/alerts")
    async def alerts() -> list:
        """Active alert conditions."""
        return _compute_alerts(_state)

    return app


# Module-level singleton — backward-compatible with existing imports
monitoring_app = create_monitoring_app()
