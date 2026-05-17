"""
Phase 129 — SeparationRatioMonitorAgent

Polls separation_ratio_snapshots every 300s. When pooled_ratio crosses >= 1.0
from below on 2 CONSECUTIVE snapshots (W1 mitigation: single-outlier false
positive prevention), fires separation_ratio_breakthrough bus event, auto-enables
confidence_multiplier_enabled in cfg, and inserts a breakthrough log entry.

W1: False breakthrough from single outlier snapshot.
  Mitigation: require 2 consecutive snapshots >= 1.0 before declaring breakthrough.
  Rationale: one anomalous snapshot can arise from a bad calibration run; two
  consecutive crossings indicate a genuine and stable improvement.

Phase 214 extension — GraduationAutowatchBridge (WIF-041 mitigation):
  Also reads get_separation_defensibility_status(session_type="tremor_resting") on each
  poll to detect all_pairs_p0_ok False→True transition.  When transition fires:
    - inserts graduation_autowatch_log entry (trigger_fired=True)
    - fires graduation_readiness_check bus event
  This wires Phase 213 FFT outcome to Phase 207 graduation pipeline automatically.
"""

import asyncio
import logging
import time

_log = logging.getLogger(__name__)

POLL_INTERVAL_S = 300  # 5 minutes


class SeparationRatioMonitorAgent:
    """Monitor agent #15 — polls separation ratio; fires breakthrough + autowatch events."""

    def __init__(self, cfg, store, bus=None):
        self._cfg   = cfg
        self._store = store
        self._bus   = bus
        # W1: require 2 consecutive snapshots >= 1.0 before declaring breakthrough
        self._prev_crossed: bool = False       # was previous snapshot >= 1.0?
        self._prev_ratio: float = 0.0          # previous pooled_ratio value
        self._breakthrough_fired: bool = False  # one-shot guard — never re-fire
        # Phase 214: all_pairs_p0_ok transition detection (WIF-041 mitigation)
        self._all_pairs_prev: bool = False     # previous all_pairs_above_1 state

    async def run_poll_loop(self) -> None:
        """Continuous poll loop — never raises."""
        _log.info("Phase 129: SeparationRatioMonitorAgent started (poll=%ds)", POLL_INTERVAL_S)
        while True:
            try:
                await self._check_and_record()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                _log.warning("Phase 129: SeparationRatioMonitorAgent poll error: %s", exc)
            await asyncio.sleep(POLL_INTERVAL_S)

    async def _check_and_record(self) -> None:
        """Read latest snapshot; detect breakthrough with 2-consecutive guard.

        Phase 214 extension: also check all_pairs_p0_ok transition via
        get_separation_defensibility_status(session_type='tremor_resting').
        """
        snaps = self._store.get_separation_ratio_status(limit=2)
        if not snaps:
            return

        current_ratio = float(snaps[0].get("pooled_ratio", 0.0))
        n_players     = int(snaps[0].get("n_sessions", 0))  # best proxy from snapshots

        # W1 two-consecutive guard: current AND previous snapshot both >= 1.0
        current_crossed = current_ratio >= 1.0

        if current_crossed and self._prev_crossed and not self._breakthrough_fired:
            # Second consecutive crossing — genuine breakthrough; fire exactly once
            self._breakthrough_fired = True
            await self._fire_breakthrough(
                before_ratio=self._prev_ratio,
                after_ratio=current_ratio,
                n_players=n_players,
            )

        self._prev_ratio   = current_ratio
        self._prev_crossed = current_crossed

        # --- Phase 214: GraduationAutowatchBridge ---
        # Watch all_pairs_p0_ok for False→True transition (WIF-041 mitigation)
        if bool(getattr(self._cfg, "graduation_autowatch_enabled", True)):
            await self._check_all_pairs_transition()

    async def _fire_breakthrough(
        self,
        before_ratio: float,
        after_ratio: float,
        n_players: int,
    ) -> None:
        """Insert breakthrough log entry, auto-enable multiplier, fire bus event."""
        feature_count = int(getattr(self._cfg, "live_feature_dim", 13))

        # 1. Persist breakthrough log
        try:
            self._store.insert_separation_ratio_breakthrough(
                before_ratio=before_ratio,
                after_ratio=after_ratio,
                n_players=n_players,
                feature_count=feature_count,
            )
            _log.info(
                "Phase 129: separation ratio breakthrough logged "
                "(before=%.3f after=%.3f n_players=%d)",
                before_ratio, after_ratio, n_players,
            )
        except Exception as exc:
            _log.warning("Phase 129: failed to insert breakthrough log: %s", exc)

        # 2. Auto-enable confidence_multiplier (W2 opportunity: score becomes meaningful)
        try:
            object.__setattr__(self._cfg, "confidence_multiplier_enabled", True)
            _log.info("Phase 129: confidence_multiplier_enabled=True (auto-set on breakthrough)")
        except Exception:
            pass  # Config may not support attribute, non-blocking; fail-open: M-1 cleanup 2026-05-16

        # 3. Fire bus event
        if self._bus is not None:
            try:
                self._bus.publish_sync(
                    "separation_ratio_breakthrough",
                    {
                        "before_ratio":  before_ratio,
                        "after_ratio":   after_ratio,
                        "n_players":     n_players,
                        "feature_count": feature_count,
                        "ts":            time.time(),
                    },
                )
            except Exception as exc:
                _log.warning("Phase 129: bus publish error: %s", exc)

    # ------------------------------------------------------------------
    # Phase 214: GraduationAutowatchBridge — all_pairs_p0_ok watcher
    # ------------------------------------------------------------------

    async def _check_all_pairs_transition(self) -> None:
        """Detect all_pairs_p0_ok False→True transition; fire graduation_readiness_check.

        Reads the latest separation_defensibility_log entry for 'tremor_resting'
        probe type.  When all_pairs_above_1 transitions from False to True (compared to
        the previous poll value in self._all_pairs_prev):
          - inserts graduation_autowatch_log entry (trigger_fired=True)
          - fires graduation_readiness_check bus event
        """
        try:
            defensibility = self._store.get_separation_defensibility_status(
                session_type="tremor_resting"
            )
        except Exception as exc:
            _log.debug("Phase 214: get_separation_defensibility_status error: %s", exc)
            return

        if not defensibility:
            return

        current_all_pairs = bool(defensibility.get("all_pairs_above_1", False))
        probe_type        = str(defensibility.get("probe_type", "tremor_resting"))
        current_ratio     = float(defensibility.get("ratio", 0.0))

        if current_all_pairs and not self._all_pairs_prev:
            # Transition: False → True — fire once per crossing
            await self._fire_graduation_readiness_check(
                probe_type=probe_type,
                ratio=current_ratio,
            )

        self._all_pairs_prev = current_all_pairs

    async def _fire_graduation_readiness_check(
        self,
        probe_type: str,
        ratio: float,
    ) -> None:
        """Insert autowatch log + fire graduation_readiness_check bus event (Phase 214)."""
        _log.info(
            "Phase 214: all_pairs_p0_ok transition False→True detected "
            "(probe=%s ratio=%.3f) — firing graduation_readiness_check",
            probe_type, ratio,
        )

        # 1. Persist autowatch trigger entry
        try:
            self._store.insert_graduation_autowatch_log(
                probe_type=probe_type,
                ratio=ratio,
                all_pairs_above_1=True,
                trigger_fired=True,
            )
        except Exception as exc:
            _log.warning("Phase 214: failed to insert autowatch log: %s", exc)

        # 2. Fire bus event
        if self._bus is not None:
            try:
                self._bus.publish_sync(
                    "graduation_readiness_check",
                    {
                        "probe_type": probe_type,
                        "ratio":      ratio,
                        "ts":         time.time(),
                    },
                )
            except Exception as exc:
                _log.warning("Phase 214: bus publish error on graduation_readiness_check: %s", exc)
