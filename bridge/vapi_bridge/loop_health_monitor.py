"""
Phase 235.x-STABILITY-3 — Loop health monitor (WIF-065 closure).

Independent heartbeat task that detects asyncio event loop starvation
regardless of asyncio's debug mode. Closes the instrumentation gap
identified in WIF-065:

    asyncio's built-in `slow_callback_duration` warning is gated by
    `loop.set_debug(True)` which defaults OFF (Phase 235.x-STABILITY-2
    set the threshold but not the debug flag, producing 0 warnings
    during 16 zombie events).

How this works:
    The heartbeat task sleeps for `check_interval_s` then measures actual
    elapsed time. If actual exceeds expected by more than
    `starvation_threshold_s`, the event loop was blocked / saturated
    during that window — fire a WARNING with the timing details.

Why this works:
    `await asyncio.sleep(N)` schedules a wakeup N seconds in the future.
    The wakeup happens when the event loop reaches it in the next iteration
    after time passes. If the loop is busy (sync work blocking, executor
    saturation, OS scheduling pressure), the wakeup is DELAYED — observable
    as elapsed > expected.

    This independent detection mechanism is bulletproof:
    - No monkey-patching asyncio internals
    - Works regardless of debug mode
    - Catches ANY cause of loop starvation (sync work, executor saturation,
      OS scheduler, GIL contention)

Operator action with a STARVATION warning in logs:
    1. Note the timestamp + excess (e.g., "starved 8.3s above expected 2.0s")
    2. Cross-reference watchdog log for BRIDGE_UNRESPONSIVE around same time
    3. Bisect: disable suspected sync sources (drift sweeper, FSCA) one at
       a time and re-test (Phase 235.x-STABILITY-3 bisection step)
"""

import asyncio
import logging
import time

log = logging.getLogger(__name__)


async def run_loop_health_monitor(*, cfg) -> None:
    """Long-lived heartbeat that detects event-loop starvation windows.

    Returns only on `asyncio.CancelledError` (graceful shutdown).
    All other exceptions are caught and the loop continues.
    """
    if not getattr(cfg, "loop_health_monitor_enabled", True):
        log.info("loop_health_monitor: disabled (LOOP_HEALTH_MONITOR_ENABLED=false)")
        return

    check_interval_s = float(getattr(cfg, "loop_health_check_interval_s", 2.0))
    threshold_s = float(getattr(cfg, "loop_health_starvation_threshold_s", 1.0))

    log.info(
        "Phase 235.x-STABILITY-3: loop_health_monitor started "
        "(check=%.1fs, starvation_threshold=%.1fs)",
        check_interval_s, threshold_s,
    )

    # Stats for periodic summary (every 60 heartbeats = ~2 min at default cadence)
    starvation_events = 0
    max_excess_s = 0.0
    summary_every_n = max(1, int(60.0 / check_interval_s))
    iter_count = 0

    while True:
        try:
            iter_count += 1
            before = time.monotonic()
            await asyncio.sleep(check_interval_s)
            elapsed = time.monotonic() - before
            excess = elapsed - check_interval_s

            if excess > threshold_s:
                starvation_events += 1
                if excess > max_excess_s:
                    max_excess_s = excess
                log.warning(
                    "Phase 235.x-STABILITY-3 LOOP STARVATION: "
                    "expected sleep=%.1fs, actual=%.2fs (excess=%.2fs above threshold=%.1fs) — "
                    "event loop blocked by sync work, executor saturation, "
                    "or OS scheduling pressure",
                    check_interval_s, elapsed, excess, threshold_s,
                )

            # Periodic summary so operator can see "no starvation in last N min"
            if iter_count % summary_every_n == 0:
                log.info(
                    "loop_health_monitor: %d checks, %d starvation events "
                    "(max excess %.2fs)",
                    iter_count, starvation_events, max_excess_s,
                )
        except asyncio.CancelledError:
            log.info(
                "loop_health_monitor: cancelled (final stats: "
                "%d checks, %d starvation events, max excess %.2fs)",
                iter_count, starvation_events, max_excess_s,
            )
            raise
        except Exception as exc:  # noqa: BLE001 — observability loop must not die
            log.exception("loop_health_monitor: outer error: %s", exc)
            try:
                await asyncio.sleep(check_interval_s)
            except asyncio.CancelledError:
                raise
