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
"""

import asyncio
import logging
import time

_log = logging.getLogger(__name__)

POLL_INTERVAL_S = 300  # 5 minutes


class SeparationRatioMonitorAgent:
    """Monitor agent #15 — polls separation ratio; fires breakthrough event."""

    def __init__(self, cfg, store, bus=None):
        self._cfg   = cfg
        self._store = store
        self._bus   = bus
        # W1: require 2 consecutive snapshots >= 1.0 before declaring breakthrough
        self._prev_crossed: bool = False       # was previous snapshot >= 1.0?
        self._prev_ratio: float = 0.0          # previous pooled_ratio value
        self._breakthrough_fired: bool = False  # one-shot guard — never re-fire

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
        """Read latest snapshot; detect breakthrough with 2-consecutive guard."""
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
            pass  # Config may not support attribute, non-blocking

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
