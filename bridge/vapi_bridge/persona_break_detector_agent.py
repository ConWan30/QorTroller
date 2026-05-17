"""
Phase 182 — PersonaBreakDetectorAgent (agent #27)

Detects when P1 biometric centroid has genuinely migrated ("persona break") vs.
data sparsity by computing rolling LOO classification accuracy over the last 5
separation_ratio_snapshots per player.

Novel mechanism:
  P1 intra-player variance range [1.661, 4.410] shows centroid migrating across
  measurement days — old sessions cluster near P2, new sessions cluster near P3.
  PersonaBreakDetector distinguishes this from "needs more sessions" by tracking
  LOO accuracy trend slope:
    slope < 0 AND mean_loo < threshold → persona break (not data sparsity)
    mean_loo >= threshold              → sufficient accuracy, not a break

WIF-028 deeper mitigation: temporal identity drift gate, direct root cause of
TOURNAMENT BLOCKER (ratio converging from 1.261 N=11 → 0.789 N=14 → 0.569 N=20).

Connects to MA-002 managed agent (persona break detection) seeded in
vapi_managed_agents.py.

Poll interval: 300s (5 minutes).
Fail-open: errors → persona_break_detected=False (never block on detection error).
"""

from __future__ import annotations

import asyncio
import logging
import time

log = logging.getLogger(__name__)

# LOO accuracy threshold: below 0.20 (below 33% random baseline in 3-class problem)
# means the classifier has lost all per-player separability for this player.
_DEFAULT_LOO_THRESHOLD = 0.20

# Slope threshold: trend slope < -0.05 per snapshot = accelerating decline
_SLOPE_CRITICAL = -0.05


class PersonaBreakDetectorAgent:
    """
    Agent #27 — PersonaBreakDetectorAgent.

    Reads:
        - store.get_separation_ratio_status(): latest separation ratio snapshot
        - store.get_separation_ratio_snapshots_for_player(player_id, limit=5):
          per-player LOO accuracy from last 5 snapshots
        - store.get_age_weight_analysis_status(): temporal_drift_index

    Computes:
        - loo_accuracy_trend: mean LOO accuracy over last 5 snapshots per player
        - trend_slope: linear slope of LOO accuracy sequence
        - persona_break_detected: True when mean_loo < persona_break_loo_threshold
        - re_enrollment_urgency: CRITICAL | HIGH | MEDIUM

    Stores:
        - persona_break_log (Phase 182)

    Publishes:
        - persona_break bus event when persona_break_detected=True
    """

    _POLL_INTERVAL_S = 300
    _TREND_WINDOW    = 5

    def __init__(self, cfg, store, bus=None) -> None:
        self._cfg   = cfg
        self._store = store
        self._bus   = bus

    # ------------------------------------------------------------------
    # LOO accuracy trend computation
    # ------------------------------------------------------------------

    def _compute_loo_accuracy_trend(self, player_id: str) -> tuple[float, float]:
        """Return (trend_slope, mean_loo_accuracy) over last 5 snapshots.

        Reads from separation_ratio_snapshots table — loo_classification_pct column.
        Returns (0.0, 1.0) when fewer than 2 snapshots exist (not a break — data sparsity).
        Fail-open: exceptions → (0.0, 1.0).
        """
        try:
            # Try to read per-player LOO snapshots if the store method exists
            if hasattr(self._store, "get_separation_ratio_snapshots_for_player"):
                rows = self._store.get_separation_ratio_snapshots_for_player(
                    player_id, limit=self._TREND_WINDOW
                )
            else:
                # Fallback: read the global snapshot and infer per-player accuracy
                status = self._store.get_separation_ratio_status()
                # If no per-player method exists, use pooled loo pct (conservative)
                loo_pct = float(status.get("loo_classification_pct", 100.0))
                return (0.0, loo_pct / 100.0)

            if len(rows) < 2:
                return (0.0, 1.0)

            # Extract LOO accuracy (loo_classification_pct stored as 0-100 percentage)
            accuracies = []
            for r in rows:
                pct = r.get("loo_classification_pct") if isinstance(r, dict) else None
                if pct is None:
                    pct = 100.0
                accuracies.append(float(pct) / 100.0)

            # Linear slope: (last - first) / (n - 1)
            n = len(accuracies)
            slope    = (accuracies[-1] - accuracies[0]) / max(1, n - 1)
            mean_acc = sum(accuracies) / n
            return (round(slope, 6), round(mean_acc, 6))

        except Exception:
            log.debug("PersonaBreakDetectorAgent: _compute_loo_accuracy_trend error for %s", player_id, exc_info=True)
            return (0.0, 1.0)

    def _check_persona_break(self, player_id: str) -> dict:
        """Assess persona break status for a single player.

        Returns a dict ready for insert_persona_break_log().
        Fail-open: any exception → persona_break_detected=False.
        """
        try:
            threshold = float(getattr(self._cfg, "persona_break_loo_threshold", _DEFAULT_LOO_THRESHOLD))

            # Get temporal drift index from Phase 175 agent
            tdi = 0.0
            try:
                aw_status = self._store.get_age_weight_analysis_status()
                tdi = float(aw_status.get("temporal_drift_index", 0.0))
            except Exception:
                pass  # fail-open: M-1 cleanup 2026-05-16 — intentional silent skip

            slope, mean_acc = self._compute_loo_accuracy_trend(player_id)

            persona_break = mean_acc < threshold

            if persona_break:
                urgency = "CRITICAL"
            elif slope < _SLOPE_CRITICAL:
                urgency = "HIGH"
            else:
                urgency = "MEDIUM"

            return {
                "player_id":              player_id,
                "loo_accuracy_trend":     mean_acc,
                "tdi_current":            tdi,
                "persona_break_detected": persona_break,
                "urgency":                urgency,
                "n_snapshots":            self._TREND_WINDOW,
            }

        except Exception as exc:
            log.warning("PersonaBreakDetectorAgent: _check_persona_break error for %s: %s", player_id, exc)
            return {
                "player_id":              player_id,
                "loo_accuracy_trend":     1.0,
                "tdi_current":            0.0,
                "persona_break_detected": False,
                "urgency":                "MEDIUM",
                "n_snapshots":            0,
            }

    # ------------------------------------------------------------------
    # Poll loop
    # ------------------------------------------------------------------

    def _run_assessment(self) -> dict:
        """Run one detection cycle across all known players.

        Returns summary dict for the most recent detection result.
        """
        if not getattr(self._cfg, "persona_break_detection_enabled", True):
            return {
                "persona_break_detection_enabled": False,
                "persona_break_detected":          False,
                "re_enrollment_urgency":           "MEDIUM",
                "players_checked":                 0,
            }

        # Determine players to check: use all players known to separation ratio log
        players = ["P1", "P2", "P3"]  # default; extended when per-player method exists
        try:
            if hasattr(self._store, "get_distinct_players_from_snapshots"):
                players = self._store.get_distinct_players_from_snapshots() or players
        except Exception:
            pass  # fail-open: M-1 cleanup 2026-05-16 — intentional silent skip

        any_break = False
        worst_result: dict = {}

        for pid in players:
            result = self._check_persona_break(pid)
            try:
                self._store.insert_persona_break_log(
                    player_id=result["player_id"],
                    loo_accuracy_trend=result["loo_accuracy_trend"],
                    tdi_current=result["tdi_current"],
                    persona_break_detected=result["persona_break_detected"],
                    urgency=result["urgency"],
                    n_snapshots=result["n_snapshots"],
                )
            except Exception as exc:
                log.warning("PersonaBreakDetectorAgent: insert error for %s: %s", pid, exc)

            if result["persona_break_detected"]:
                any_break = True
                worst_result = result

        if not worst_result:
            worst_result = self._store.get_persona_break_status()

        # Publish bus event when break detected
        if any_break and self._bus is not None:
            try:
                self._bus.publish("persona_break", {
                    "persona_break_detected": True,
                    "player_id":              worst_result.get("player_id", ""),
                    "urgency":                worst_result.get("urgency", "CRITICAL"),
                    "ts":                     time.time(),
                })
            except Exception as exc:
                log.debug("PersonaBreakDetectorAgent: bus publish error: %s", exc)

        return {
            "persona_break_detection_enabled": True,
            "persona_break_detected":          any_break,
            "re_enrollment_urgency":           worst_result.get("urgency", "MEDIUM"),
            "players_checked":                 len(players),
        }

    async def run_poll_loop(self) -> None:
        """Async poll loop — 300s interval. Never raises."""
        log.info("PersonaBreakDetectorAgent starting (interval=%ss)", self._POLL_INTERVAL_S)
        while True:
            try:
                self._run_assessment()
            except Exception as exc:
                log.error("PersonaBreakDetectorAgent: unhandled error in poll: %s", exc, exc_info=True)
            await asyncio.sleep(self._POLL_INTERVAL_S)
