"""
Phase 173 — SeparationRatioRecoveryAgent (agent #23)

Detects converging-downward separation ratio trend (P1 temporal non-stationarity)
and recommends recovery actions.

Root cause context (Phase 168 analysis):
  N=11 → ratio=1.261, N=14 → ratio=0.789, N=20 → ratio=0.569
  trend_velocity ≈ -0.077 per session (strongly negative)
  Root cause: P1 intra-player variance range=[1.661, 4.410] across capture dates.
  Old P1 sessions cluster near P2; new P1 sessions cluster near P3.
  This is P1 temporal non-stationarity — multiple biometric "personas" over time.

Recovery actions (in priority order):
  AGE_WEIGHTING      — apply --session-age-weight 30 to analyze_interperson_separation.py
                        to down-weight stale P1 sessions (Phase 174 flag)
  P1_RE_ENROLLMENT   — P1 must re-capture ≥10 fresh touchpad_corners sessions
                        to rebuild a current biometric baseline
  MORE_SESSIONS      — capture more sessions for players below min_n_per_player
  STABLE             — no recovery needed

Poll interval: 1 hour (separation_recovery_poll_interval_s=3600).
Never raises from run_poll_loop().
"""

from __future__ import annotations

import asyncio
import logging
import time

log = logging.getLogger(__name__)

# Velocity thresholds (dRatio/dSession)
_VELOCITY_CRITICAL_THRESHOLD = -0.05   # strongly converging → P1_RE_ENROLLMENT
_VELOCITY_WARNING_THRESHOLD  = -0.01   # mildly converging → AGE_WEIGHTING


class SeparationRatioRecoveryAgent:
    """
    Agent #23 — SeparationRatioRecoveryAgent.

    Reads:
        - store.get_separation_ratio_status(): last 5 separation ratio snapshots
        - cfg.min_separation_ratio: defensibility gate (default 0.70)

    Computes:
        - trend_velocity: linear slope of pooled_ratio vs snapshot index
          (negative = converging downward; CRITICAL when < -0.05/session)
        - recovery_action: STABLE | AGE_WEIGHTING | P1_RE_ENROLLMENT | MORE_SESSIONS

    Stores:
        - separation_ratio_recovery_log (Phase 173)

    Publishes:
        - ratio_recovery_needed bus event when recovery_needed=True
    """

    # Number of recent snapshots to use for trend computation
    _TREND_WINDOW = 5

    def __init__(self, cfg, store, bus=None) -> None:
        self._cfg   = cfg
        self._store = store
        self._bus   = bus

    # ------------------------------------------------------------------
    # Trend computation
    # ------------------------------------------------------------------

    @staticmethod
    def compute_trend_velocity(ratios: list[float]) -> float:
        """Linear regression slope of ratio vs index (dRatio/dSnapshot).

        Returns 0.0 if fewer than 2 data points.
        Negative = converging downward. Positive = improving.
        """
        n = len(ratios)
        if n < 2:
            return 0.0
        xs = list(range(n))
        mean_x = sum(xs) / n
        mean_y = sum(ratios) / n
        numerator   = sum((xs[i] - mean_x) * (ratios[i] - mean_y) for i in range(n))
        denominator = sum((xs[i] - mean_x) ** 2 for i in range(n))
        if denominator == 0:
            return 0.0
        return round(numerator / denominator, 6)

    def _determine_recovery_action(
        self,
        current_ratio: float,
        trend_velocity: float,
        min_sep_ratio: float,
    ) -> tuple[bool, str, str]:
        """Determine if recovery is needed and what action to take.

        Returns:
            (recovery_needed, recovery_action, recommendation)
        """
        if current_ratio >= min_sep_ratio and trend_velocity >= 0:
            return (
                False,
                "STABLE",
                "Separation ratio above gate and trend is stable or improving. "
                "Continue capturing structured probe sessions.",
            )

        if trend_velocity <= _VELOCITY_CRITICAL_THRESHOLD:
            return (
                True,
                "P1_RE_ENROLLMENT",
                f"P1 temporal non-stationarity: velocity={trend_velocity:.4f}/snapshot "
                f"(threshold={_VELOCITY_CRITICAL_THRESHOLD}). P1's biometric fingerprint "
                "is drifting across capture dates. Action: capture >=10 fresh "
                "touchpad_corners sessions for P1 to rebuild current baseline. "
                "Also run analyze_interperson_separation.py --session-age-weight 30 "
                "to bracket the age-weighted ratio before full re-enrollment.",
            )

        if trend_velocity <= _VELOCITY_WARNING_THRESHOLD and current_ratio < min_sep_ratio:
            return (
                True,
                "AGE_WEIGHTING",
                f"Mild downward trend: velocity={trend_velocity:.4f}/snapshot. "
                "Apply session age weighting to mitigate P1 temporal non-stationarity. "
                "Run: python scripts/analyze_interperson_separation.py "
                "--session-type touchpad_corners --session-age-weight 30 --write-snapshot. "
                "This down-weights old P1 sessions clustered near other players.",
            )

        if current_ratio < min_sep_ratio:
            return (
                True,
                "MORE_SESSIONS",
                f"Ratio {current_ratio:.3f} below gate {min_sep_ratio:.3f}. "
                "Capture more mixed_biometric_probe sessions (target >=10/player "
                "for defensibility gate per Phase 150). Current trend is flat. "
                "Run: python scripts/terminal_calibration_runner.py "
                "--battery mixed_biometric_probe.",
            )

        return (
            False,
            "STABLE",
            "Separation ratio at or above gate. Continue monitoring.",
        )

    # ------------------------------------------------------------------
    # Poll logic
    # ------------------------------------------------------------------

    def _run_assessment(self) -> dict:
        """Run one recovery assessment cycle."""
        min_sep = float(getattr(self._cfg, "min_separation_ratio", 0.70))

        # Load recent snapshots
        rows = []
        try:
            rows = self._store.get_separation_ratio_status(limit=self._TREND_WINDOW)
        except Exception:
            pass  # fail-open: M-1 cleanup 2026-05-16 — intentional silent skip

        # Build ratio series (oldest first)
        ratios = [float(r.get("pooled_ratio", 0.0)) for r in reversed(rows)]
        current_ratio = ratios[-1] if ratios else 0.0

        trend_velocity  = self.compute_trend_velocity(ratios)
        n_snapshots_used = len(ratios)

        recovery_needed, recovery_action, recommendation = self._determine_recovery_action(
            current_ratio, trend_velocity, min_sep
        )

        return {
            "current_ratio":    current_ratio,
            "trend_velocity":   trend_velocity,
            "n_snapshots_used": n_snapshots_used,
            "recovery_needed":  recovery_needed,
            "recovery_action":  recovery_action,
            "recommendation":   recommendation,
        }

    # ------------------------------------------------------------------
    # Poll loop
    # ------------------------------------------------------------------

    async def run_poll_loop(self) -> None:
        """1-hour poll loop — runs recovery assessment and persists result."""
        poll_s = int(getattr(self._cfg, "separation_recovery_poll_interval_s", 3600))
        while True:
            try:
                assessment = self._run_assessment()

                self._store.insert_separation_ratio_recovery_log(
                    current_ratio    = assessment["current_ratio"],
                    trend_velocity   = assessment["trend_velocity"],
                    n_snapshots_used = assessment["n_snapshots_used"],
                    recovery_needed  = assessment["recovery_needed"],
                    recovery_action  = assessment["recovery_action"],
                    recommendation   = assessment["recommendation"],
                )

                if assessment["recovery_needed"] and self._bus is not None:
                    try:
                        self._bus.publish_sync("ratio_recovery_needed", {
                            "current_ratio":   assessment["current_ratio"],
                            "trend_velocity":  assessment["trend_velocity"],
                            "recovery_action": assessment["recovery_action"],
                            "ts":              time.time(),
                        })
                    except Exception:
                        pass  # fail-open: M-1 cleanup 2026-05-16 — intentional silent skip

                log.debug(
                    "[SeparationRatioRecoveryAgent] ratio=%.3f velocity=%.4f "
                    "action=%s recovery=%s",
                    assessment["current_ratio"],
                    assessment["trend_velocity"],
                    assessment["recovery_action"],
                    assessment["recovery_needed"],
                )

            except Exception:
                log.debug("[SeparationRatioRecoveryAgent] poll error", exc_info=True)

            await asyncio.sleep(poll_s)
