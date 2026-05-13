"""Phase O4-VPM-INT follow-up — Continuous CFSS lane authority drift sweeper.

Mirrors the cedar_drift_sweeper pattern (Phase O1 C4) at the Cedar
POLICY layer rather than the BUNDLE layer. Without this sweeper, the
12-row EXPECTED_LANE_MATRIX in scripts/zkba_post_ceremony_audit.py is
only verified by the operator-runtime post-ceremony audit; silent
mutations to a Cedar v2 bundle file post-anchor would not surface
until the next operator-triggered audit.

This sweeper closes that gap. Runs on the same 60s cadence as the
cedar_drift_sweeper's bundle path (per INV-OPERATOR-AGENT-008 frozen
dual-cadence). Findings land in cfss_lane_drift_log table → consumed
by the 27th FSCA contradiction rule CFSS_LANE_AUTHORITY_DRIFT
(CRITICAL severity — protocol-architectural integrity violation).

Default disabled. Opt-in via cfg.cfss_drift_sweep_enabled=True (env
CFSS_DRIFT_SWEEP_ENABLED=true in bridge/.env).

Fail-open by design: any exception in the sweep is caught + logged;
the loop continues. The sweeper is observability infrastructure — it
must never bring the bridge down.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import time
from pathlib import Path

log = logging.getLogger(__name__)

# Cadence default — same as cedar_drift_sweeper's bundle interval per
# INV-OPERATOR-AGENT-008.
_CFSS_DRIFT_INTERVAL_DEFAULT_S = 60


def _load_audit_module():
    """Lazy-import the CFSS audit module from scripts/. Done at runtime
    not import-time because scripts/ is not a Python package and the
    bridge package shouldn't hard-import it."""
    import importlib.util
    import sys as _sys

    bridge_root = Path(__file__).resolve().parent.parent.parent
    script_path = bridge_root / "scripts" / "cfss_lane_drift_sweep.py"
    if not script_path.exists():
        return None
    if str(bridge_root / "scripts") not in _sys.path:
        _sys.path.insert(0, str(bridge_root / "scripts"))
    spec = importlib.util.spec_from_file_location(
        "cfss_lane_drift_sweep", script_path,
    )
    module = importlib.util.module_from_spec(spec)  # type: ignore
    _sys.modules["cfss_lane_drift_sweep"] = module
    spec.loader.exec_module(module)  # type: ignore
    return module


async def run_cfss_drift_sweep_loop(*, cfg, store) -> None:
    """Long-lived asyncio loop driving CFSS lane authority drift sweeps.

    Wakes on a heartbeat (min of interval, capped at 30s) and fires the
    sweep when its monotonic gap >= configured interval. First sweep
    fires immediately on startup.

    Returns only on asyncio.CancelledError (graceful shutdown). All
    other exceptions are caught + logged; loop continues.
    """
    if not getattr(cfg, "cfss_drift_sweep_enabled", False):
        log.info(
            "cfss_drift_sweeper: disabled (cfss_drift_sweep_enabled=False)"
        )
        return

    audit_module = _load_audit_module()
    if audit_module is None:
        log.warning(
            "cfss_drift_sweeper: audit module not loadable; sweep disabled"
        )
        return

    bundle_dir = Path(getattr(
        cfg, "cedar_bundles_dir",
        Path(__file__).resolve().parent / "cedar_bundles",
    ))

    interval_s = int(getattr(
        cfg, "cfss_drift_sweep_interval_s",
        _CFSS_DRIFT_INTERVAL_DEFAULT_S,
    ))
    heartbeat_s = max(1, min(30, interval_s))

    log.info(
        "cfss_drift_sweeper: started interval=%ds bundle_dir=%s",
        interval_s, bundle_dir,
    )

    last_sweep = 0.0
    while True:
        try:
            now = time.monotonic()
            if (now - last_sweep) >= interval_s:
                last_sweep = now
                await asyncio.to_thread(
                    _run_sweep,
                    audit_module=audit_module,
                    bundle_dir=bundle_dir,
                    store=store,
                )
            await asyncio.sleep(heartbeat_s)
        except asyncio.CancelledError:
            log.info("cfss_drift_sweeper: cancelled, exiting cleanly")
            raise
        except Exception as exc:
            log.exception(
                "cfss_drift_sweeper: outer loop error: %s", exc
            )
            await asyncio.sleep(heartbeat_s)


def _run_sweep(*, audit_module, bundle_dir: Path, store) -> None:
    """Single CFSS sweep. Sync wrapper that catches all errors."""
    try:
        report = audit_module.sweep_once(bundle_dir)
    except Exception as exc:
        log.error("cfss_drift_sweeper: sweep error: %s", exc)
        return

    verdict = report.get("verdict", "UNKNOWN")
    violations = report.get("violations") or []

    if not violations:
        log.debug(
            "cfss_drift_sweeper: CLEAN verdict=%s rows=%d",
            verdict, len(report.get("rows", [])),
        )
        return

    # Persist each violation as a row in cfss_lane_drift_log.
    sweep_id = _compute_sweep_id(report)
    persisted = 0
    for v in violations:
        try:
            evidence = json.dumps({
                "verdict": verdict,
                "row": v,
                "timestamp_unix": report.get("timestamp_unix"),
            }, sort_keys=True, separators=(",", ":"))
        except Exception:
            evidence = ""
        row_id = store.insert_cfss_lane_drift(
            sweep_id=sweep_id,
            agent_id=v.get("agent_id", ""),
            action=v.get("action", ""),
            resource=v.get("resource") if v.get("resource") != "(any)" else None,
            expected_effect=v.get("expected_effect", ""),
            actual_effect=v.get("actual_effect", ""),
            bundle_path=str(bundle_dir),
            evidence_json=evidence,
        )
        if row_id:
            persisted += 1

    log.warning(
        "cfss_drift_sweeper: CFSS_VIOLATION sweep=%s findings=%d persisted=%d",
        sweep_id[:12], len(violations), persisted,
    )
    for v in violations:
        log.warning(
            "  drift agent=%s action=%s expected=%s actual=%s",
            v.get("agent_id", "")[:18],
            v.get("action", "")[:30],
            v.get("expected_effect", "")[:8],
            v.get("actual_effect", "")[:8],
        )


def _compute_sweep_id(report: dict) -> str:
    """Deterministic sweep_id = SHA-256(canonical-report-bytes)[:16].
    Lets duplicate sweep-fires (e.g. operator running CLI alongside the
    bridge sweeper) coalesce on the same sweep_id."""
    try:
        body = json.dumps(
            {
                "ts": int(report.get("timestamp_unix", 0)),
                "verdict": report.get("verdict"),
                "rows": report.get("rows"),
            },
            sort_keys=True, separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(body).hexdigest()[:16]
    except Exception:
        return "unknown"
