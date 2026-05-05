"""Background persistence for live PCC monitor state.

Phase 235-PCC-PERSIST closes the gap where capture_health_log freshness
depended on someone polling /operator/bridge/capture-health. The in-memory
CaptureHealthMonitor is the live source of truth; this module periodically
flushes its state to SQLite so DB-backed observers stay current even when the
HTTP endpoint is idle.
"""

from __future__ import annotations

import asyncio
import logging
import time

log = logging.getLogger(__name__)


def persist_pcc_monitor_once(
    store,
    monitor,
    cfg,
    *,
    last_snapshot_monotonic: float = 0.0,
    snapshot_interval_s: float = 5.0,
) -> float:
    """Flush live PCC state to the store and return the new snapshot timestamp.

    Transition rows are always persisted immediately when present. When the
    state is stable, a lightweight periodic snapshot is written at
    ``snapshot_interval_s`` cadence so DB-backed monitors can still observe
    freshness without depending on API polling side effects.
    """
    if monitor is None:
        return float(last_snapshot_monotonic)

    status = monitor.get_status()
    transitions = monitor.pop_transitions()
    now = time.monotonic()

    grind_mode = bool(getattr(cfg, "grind_mode", False))
    session_id = str(getattr(cfg, "grind_session_id", "") or "")
    prev_session_id = str(getattr(cfg, "prev_grind_session_id", "") or "")

    for row in transitions:
        try:
            store.insert_capture_health_event(
                capture_state=row.get("new_state", status.get("capture_state", "DISCONNECTED")),
                host_state=row.get("host_state", status.get("host_state", "UNKNOWN")),
                poll_rate_hz=float(row.get("poll_rate_hz", status.get("poll_rate_hz", 0.0))),
                transition_reason=str(row.get("reason", "state_transition") or "state_transition"),
                grind_mode=grind_mode,
                session_id=session_id,
                prev_session_id=prev_session_id,
            )
        except Exception:
            log.debug("PCC transition persistence failed", exc_info=True)

    if transitions:
        return now

    sample_count = int(status.get("sample_count", 0) or 0)
    if sample_count <= 0:
        return float(last_snapshot_monotonic)

    if last_snapshot_monotonic > 0.0 and (now - last_snapshot_monotonic) < snapshot_interval_s:
        return float(last_snapshot_monotonic)

    try:
        store.insert_capture_health_event(
            capture_state=str(status.get("capture_state", "DISCONNECTED")),
            host_state=str(status.get("host_state", "UNKNOWN")),
            poll_rate_hz=float(status.get("poll_rate_hz", 0.0)),
            transition_reason="periodic_snapshot",
            grind_mode=grind_mode,
            session_id=session_id,
            prev_session_id=prev_session_id,
        )
        return now
    except Exception:
        log.debug("PCC periodic snapshot persistence failed", exc_info=True)
        return float(last_snapshot_monotonic)


async def run_pcc_persistence_loop(
    store,
    monitor,
    cfg,
    *,
    flush_interval_s: float | None = None,
    snapshot_interval_s: float | None = None,
) -> None:
    """Persist live PCC state in the background until cancelled."""
    if monitor is None:
        return

    flush_interval = max(
        1.0,
        float(
            flush_interval_s
            if flush_interval_s is not None
            else getattr(cfg, "dualshock_record_interval_s", 1.0)
        ),
    )
    snapshot_interval = max(
        flush_interval,
        float(
            snapshot_interval_s
            if snapshot_interval_s is not None
            else max(5.0, flush_interval * 5.0)
        ),
    )

    last_snapshot_monotonic = 0.0
    while True:
        try:
            last_snapshot_monotonic = await asyncio.to_thread(
                persist_pcc_monitor_once,
                store,
                monitor,
                cfg,
                last_snapshot_monotonic=last_snapshot_monotonic,
                snapshot_interval_s=snapshot_interval,
            )
        except asyncio.CancelledError:
            raise
        except Exception:
            log.warning("PCC persistence loop iteration failed", exc_info=True)
        await asyncio.sleep(flush_interval)
