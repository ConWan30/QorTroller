"""
Phase O1 C4 — Drift Auto-Sweep Scheduler

Operationalizes the C3 drift-detection primitives (detect_bundle_hash_drift +
detect_scope_hash_governance_drift) by running them on monotonic interval
gates inside a long-lived asyncio loop. Without this scheduler, drift findings
only land in operator_agent_drift_log when the operator manually pokes
POST /operator/evaluate-agent-action — meaning real-world bundle mutations or
on-chain scope divergence can sit undetected indefinitely.

INV-OPERATOR-AGENT-008 freezes the dual-cadence pattern:
- Bundle drift   : 60s default. Cheap (local file SHA-256 + 1 DB row read).
- Scope drift    : 600s default. Expensive (2 chain RPC reads × N agents).
                   Throttled to bound IoTeX testnet RPC quota burn.

Both intervals are configurable but the dual-cadence shape is invariant.

Fail-open by design: any exception in either sweep is caught + logged; the
loop continues. This matches the C3 helpers' own fail-open contract
(detect_bundle_hash_drift never raises; detect_scope_hash_governance_drift
returns DriftSweepResult.error on chain failure rather than raising). The
sweeper is observability infrastructure — it must never bring the bridge down.
"""

import asyncio
import logging
import time
from typing import Optional

from .cedar_shadow_runtime import (
    detect_bundle_hash_drift,
    detect_scope_hash_governance_drift,
)

log = logging.getLogger(__name__)

# INV-OPERATOR-AGENT-008 — FROZEN dual-cadence defaults (overridable via cfg).
# The split between cheap+frequent vs expensive+rare is the invariant; the
# specific second-counts are configurable.
_BUNDLE_DRIFT_INTERVAL_DEFAULT_S = 60
_SCOPE_DRIFT_INTERVAL_DEFAULT_S = 600


async def run_drift_sweep_loop(*, cfg, store, chain) -> None:
    """Long-lived asyncio loop driving both drift sweeps.

    Wakes on a heartbeat (min of the two intervals, capped at 30s) and fires
    each sweep when its monotonic gap >= configured interval. First sweep of
    each kind fires immediately on startup (last_*=0.0 ensures gap>=interval).

    Returns only on asyncio.CancelledError (graceful shutdown). All other
    exceptions are caught + logged; loop continues.
    """
    if not getattr(cfg, "cedar_drift_sweep_enabled", False):
        log.info("cedar_drift_sweeper: disabled (cedar_drift_sweep_enabled=False)")
        return

    bundle_interval = int(
        getattr(cfg, "cedar_drift_sweep_interval_bundle_s",
                _BUNDLE_DRIFT_INTERVAL_DEFAULT_S)
    )
    scope_interval = int(
        getattr(cfg, "cedar_drift_sweep_interval_scope_s",
                _SCOPE_DRIFT_INTERVAL_DEFAULT_S)
    )
    heartbeat_s = max(1, min(30, bundle_interval, scope_interval))

    log.info(
        "cedar_drift_sweeper: started bundle=%ds scope=%ds heartbeat=%ds",
        bundle_interval, scope_interval, heartbeat_s,
    )

    last_bundle = 0.0
    last_scope = 0.0

    while True:
        try:
            now = time.monotonic()

            if (now - last_bundle) >= bundle_interval:
                last_bundle = now
                _run_bundle_sweep(cfg=cfg, store=store)

            if (now - last_scope) >= scope_interval:
                last_scope = now
                await _run_scope_sweep(cfg=cfg, store=store, chain=chain)

            await asyncio.sleep(heartbeat_s)
        except asyncio.CancelledError:
            log.info("cedar_drift_sweeper: cancelled, exiting cleanly")
            raise
        except Exception as exc:  # noqa: BLE001 — observability loop must not die
            log.exception("cedar_drift_sweeper: outer loop error: %s", exc)
            await asyncio.sleep(heartbeat_s)


def _run_bundle_sweep(*, cfg, store) -> None:
    """Single bundle-drift sweep. Sync wrapper that catches all errors."""
    try:
        res = detect_bundle_hash_drift(cfg=cfg, store=store)
    except Exception as exc:  # noqa: BLE001 — fail-open per C3 contract
        log.error("cedar_drift_sweeper: bundle sweep error: %s", exc)
        return

    if res.findings:
        log.warning(
            "cedar_drift_sweeper: BUNDLE_HASH_DRIFT findings=%d sweep=%s",
            len(res.findings), res.sweep_id,
        )
        for f in res.findings:
            log.warning(
                "  drift agent=%s expected=%s actual=%s",
                f.agent_id[:18],
                (f.expected_value or "")[:24],
                (f.actual_value or "")[:24],
            )
    else:
        log.debug(
            "cedar_drift_sweeper: bundle sweep CLEAN agents=%d sweep=%s",
            res.agents_checked, res.sweep_id,
        )


async def _run_scope_sweep(*, cfg, store, chain) -> None:
    """Single scope-governance-drift sweep. Async wrapper that catches all errors."""
    try:
        res = await detect_scope_hash_governance_drift(
            cfg=cfg, store=store, chain=chain,
        )
    except Exception as exc:  # noqa: BLE001 — fail-open per C3 contract
        log.error("cedar_drift_sweeper: scope sweep error: %s", exc)
        return

    if res.findings:
        log.warning(
            "cedar_drift_sweeper: SCOPE_HASH_GOVERNANCE_DRIFT findings=%d sweep=%s",
            len(res.findings), res.sweep_id,
        )
        for f in res.findings:
            log.warning(
                "  drift agent=%s op=%s gov=%s",
                f.agent_id[:18],
                (f.expected_value or "")[:24],
                (f.actual_value or "")[:24],
            )
    elif res.error:
        log.info(
            "cedar_drift_sweeper: scope sweep skipped (%s) sweep=%s",
            res.error, res.sweep_id,
        )
    else:
        log.debug(
            "cedar_drift_sweeper: scope sweep CLEAN agents=%d sweep=%s",
            res.agents_checked, res.sweep_id,
        )
