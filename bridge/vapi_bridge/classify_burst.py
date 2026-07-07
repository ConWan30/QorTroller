"""Classify-burst (event-driven densification) controller — Phase C mitigation for the classify
sampling-rate bottleneck (docs/phase-c-classify-sampling-bottleneck-mitigation-2026-07-05.md).

FINDING this exists to fix: the bootstrap-catch path (_session_anchor_fold and everything
downstream — OCR bootstrap, session-anchor promotion, dense-classify) only runs inside
maybe_classify_in_window, called once per _session_loop iteration (dualshock_record_interval_s,
default 1.0s). Dense-classify (Phase W.2) lowers min_gap_ms from 200 to 50ms, but BOTH values are
already far below the 1-second loop period, so min_gap was never the real constraint — the loop's
own once-per-second call rate is. Live-confirmed 2026-07-05: a crop scored 0.756 on feed_v1 (above
both the bootstrap and promote floors) with clean OCR agreement, and R2-window math showed a
window was open at that exact timestamp, yet zero bootstrap catches happened that whole match.

MECHANISM (reuses an already-proven pattern rather than inventing one): presence_burst.py's
should_combat_fire() already fires on an R2 rising edge, in production, from the same per-tick
frame data. This controller is armed on that same rising edge (see dualshock_integration.py's
combat-trigger block) and polls maybe_classify_in_window at a much tighter interval than the main
loop's 1 Hz, for a bounded window after the triggering edge — WITHOUT touching _session_loop's own
interval or any other system riding that loop (HID feed, l2_ads, death-window, ADS coupling).

SAFE BY CONSTRUCTION: InlineAuthorshipMonitor.should_classify() already gates on _inflight
(single-flight), min_gap_ms, and the R2-window bounds themselves — a call outside a valid firing
moment is a cheap no-op. Calling maybe_classify_in_window from this controller's tighter loop in
addition to the main loop's own call is exactly as safe as calling it from one source more often.

Default-off (retina_classify_burst_enabled). No FROZEN-v1 / 228B PoAC / chain / IOTX touch.
"""
from __future__ import annotations

import asyncio
import threading
import time
from typing import Any, Optional


class ClassifyBurstController:
    """Arms a bounded high-frequency polling window on an R2 rising edge; while armed, calls the
    RGC's maybe_classify_in_window at poll_s cadence instead of waiting for the main session loop's
    once-per-second call. The RGC must expose maybe_classify_in_window(now_ms) -> None."""

    def __init__(self, rgc: Any, *, duration_ms: float = 5000.0, poll_s: float = 0.15) -> None:
        self._rgc = rgc
        self._duration_ms = max(100.0, float(duration_ms))
        self._poll_s = max(0.01, float(poll_s))
        self._armed_until_ms = -1e18
        self._running = False

    def arm(self, now_ms: float) -> None:
        """Arm (or extend) the burst window through now_ms + duration_ms. Called on every R2 rising
        edge — sustained fire naturally extends the window forward (unconditional set, not a
        conditional max), matching mark_onset's own 'sustained fire keeps the window open'
        semantics exactly, so the burst state and the classify-window state stay consistent."""
        self._armed_until_ms = float(now_ms) + self._duration_ms

    @property
    def is_active(self) -> bool:
        """True while the burst window is currently armed (now < armed_until)."""
        return (time.time() * 1000.0) < self._armed_until_ms

    async def run(self) -> None:
        """Poll at poll_s cadence, calling maybe_classify_in_window while armed. Fail-open: any
        single call raising never breaks the loop. Runs for the lifetime of the session (started
        once via asyncio.create_task, like presence_burst's run()); stop() ends it at teardown.

        D-BURST-2 CAVEAT (2026-07-05, match 9): this asyncio variant's timers run at the EVENT
        LOOP's effective cadence, not poll_s. Live-measured: the session loop iterated at p50=3.0s
        under game load, so `await asyncio.sleep(0.15)` fired every ~3s and the burst contributed
        ~zero extra classifications (14 total across 7 windows — bare loop cadence). Kept for
        API compatibility; production uses start_thread(), which asyncio starvation cannot touch."""
        self._running = True
        while self._running:
            now_ms = time.time() * 1000.0
            if now_ms < self._armed_until_ms:
                try:
                    self._rgc.maybe_classify_in_window(now_ms)
                except Exception:  # noqa: BLE001 — the burst loop must survive any single failure
                    pass
            await asyncio.sleep(self._poll_s)

    def start_thread(self) -> None:
        """D-BURST-2 (2026-07-05): run the burst on a DEDICATED daemon thread instead of the event
        loop. Motivation is measured, not theoretical — match 9 showed the loop starved to ~3s
        iterations under live capture load, degrading every asyncio timer (including this burst's
        150ms poll) to loop cadence; the OCR-bootstrap chain, which only runs inside classify
        calls, got 14 chances for 15 kills. A time.sleep thread polls at TRUE poll_s regardless of
        loop health (same discipline as the codebase's sync-work-off-the-loop invariant).

        The thread prefers the RGC's thread-native entry `classify_in_window_sync` (runs the
        already-synchronous classify worker directly, lock-guarded admission); it falls back to
        maybe_classify_in_window only if the sync entry is absent (that path schedules onto the
        possibly-starved loop, so the fallback preserves function but not density). Idempotent —
        a second call while the thread lives is a no-op. stop() ends the thread loop."""
        if getattr(self, "_thread", None) is not None and self._thread.is_alive():
            return
        self._running = True
        self._thread: Optional[threading.Thread] = threading.Thread(
            target=self._thread_loop, name="vapi-classify-burst", daemon=True)
        self._thread.start()

    def _thread_loop(self) -> None:
        entry = getattr(self._rgc, "classify_in_window_sync", None) or self._rgc.maybe_classify_in_window
        while self._running:
            now_ms = time.time() * 1000.0
            if now_ms < self._armed_until_ms:
                try:
                    entry(now_ms)
                except Exception:  # noqa: BLE001 — the burst loop must survive any single failure
                    pass
            time.sleep(self._poll_s)

    def stop(self) -> None:
        self._running = False
