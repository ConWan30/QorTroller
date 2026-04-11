"""
Phase 175 — AgeWeightedRatioPersistenceAgent (agent #24)

Persists age-weighted separation ratio analysis results.
Reads separation_defensibility_log entries for a probe type, applies
Gaussian session-age decay (halflife_days) to the per-snapshot ratio
series, and stores temporal_drift_index = raw_ratio - age_weighted_ratio.

Drift interpretation:
  tdi > +0.05  → P1_NONSTATIONARITY  (recent runs show lower ratio — new
                  sessions weaker than the long-run mean)
  tdi < -0.05  → IMPROVING           (recent runs show higher ratio — new
                  sessions stronger; centroid stabilising)
  |tdi| <= 0.05 → STABLE

Poll interval: 3600s (1 hour).
Fail-safe: errors → STABLE defaults returned (never raises).
"""

from __future__ import annotations

import asyncio
import logging
import math
import time

log = logging.getLogger(__name__)

_NONSTATIONARITY_THRESHOLD = 0.05
_IMPROVING_THRESHOLD       = -0.05
_DEFAULT_HALFLIFE_DAYS     = 90.0
_DEFAULT_PROBE_TYPE        = "mixed_biometric_probe"


class AgeWeightedRatioPersistenceAgent:
    """Agent #24 — AgeWeightedRatioPersistenceAgent.

    Reads:
        store.get_separation_defensibility_status(session_type) — snapshot series
        (each entry has .ratio and .created_at UNIX timestamp)

    Computes:
        raw_ratio          = unweighted mean of recent snapshot ratios
        age_weighted_ratio = exponential-decay weighted mean (recent → 1.0, old → 0)
        temporal_drift_index (TDI) = raw_ratio - age_weighted_ratio
        drift_direction    = P1_NONSTATIONARITY | IMPROVING | STABLE

    Stores:
        age_weight_analysis_log (Phase 175)
    """

    _POLL_INTERVAL_S = 3600

    def __init__(self, cfg, store, bus=None) -> None:
        self._cfg   = cfg
        self._store = store
        self._bus   = bus

    # ------------------------------------------------------------------
    # Core computation
    # ------------------------------------------------------------------

    @staticmethod
    def _compute_age_weighted_ratio(
        ratios: list[float],
        timestamps: list[float],
        halflife_days: float,
        now_ts: float,
    ) -> float:
        """Compute exponential decay-weighted mean of ratio snapshots."""
        if not ratios:
            return 0.0
        if halflife_days <= 0:
            return sum(ratios) / len(ratios)

        lam = math.log(2) / halflife_days
        weights = []
        for ts in timestamps:
            age_days = (now_ts - ts) / 86400.0
            age_days = max(0.0, age_days)
            weights.append(math.exp(-lam * age_days))

        total_w = sum(weights)
        if total_w <= 0:
            return sum(ratios) / len(ratios)

        return round(sum(r * w for r, w in zip(ratios, weights)) / total_w, 6)

    def _run_assessment(self) -> dict:
        """Run one age-weight analysis cycle.

        Returns summary dict. Fail-safe: any error → STABLE defaults.
        """
        enabled = bool(getattr(self._cfg, "age_weight_analysis_enabled", True))
        if not enabled:
            return {"age_weight_analysis_enabled": False, "drift_direction": "STABLE"}

        try:
            halflife_days = float(
                getattr(self._cfg, "age_weight_halflife_days", _DEFAULT_HALFLIFE_DAYS)
            )
            probe_type = str(
                getattr(self._cfg, "age_weight_probe_type", _DEFAULT_PROBE_TYPE)
            )

            # Read separation_defensibility_log snapshots
            rows = self._store.get_separation_defensibility_status(
                session_type=probe_type, limit=20
            )
            if not rows:
                # No data yet — write a neutral baseline
                self._store.insert_age_weight_analysis_log(
                    probe_type=probe_type,
                    raw_ratio=0.0,
                    age_weighted_ratio=0.0,
                    halflife_days=halflife_days,
                    n_sessions_used=0,
                )
                return {"age_weight_analysis_enabled": True, "drift_direction": "STABLE"}

            ratios     = [float(r.get("ratio", 0.0)) for r in rows]
            timestamps = [float(r.get("created_at", 0.0)) for r in rows]
            now_ts     = time.time()

            raw_ratio          = round(sum(ratios) / len(ratios), 6)
            age_weighted_ratio = self._compute_age_weighted_ratio(
                ratios, timestamps, halflife_days, now_ts
            )
            tdi = round(raw_ratio - age_weighted_ratio, 6)

            if tdi > _NONSTATIONARITY_THRESHOLD:
                drift_direction = "P1_NONSTATIONARITY"
            elif tdi < _IMPROVING_THRESHOLD:
                drift_direction = "IMPROVING"
            else:
                drift_direction = "STABLE"

            self._store.insert_age_weight_analysis_log(
                probe_type=probe_type,
                raw_ratio=raw_ratio,
                age_weighted_ratio=age_weighted_ratio,
                halflife_days=halflife_days,
                n_sessions_used=len(rows),
            )

            if drift_direction == "P1_NONSTATIONARITY" and self._bus is not None:
                try:
                    self._bus.publish("biometric_window_alert", {
                        "source":          "AgeWeightedRatioPersistenceAgent",
                        "drift_direction": drift_direction,
                        "tdi":             tdi,
                        "ts":              now_ts,
                    })
                except Exception as exc:
                    log.debug("AgeWeightedRatioPersistenceAgent: bus publish error: %s", exc)

            return {
                "age_weight_analysis_enabled": True,
                "raw_ratio":            raw_ratio,
                "age_weighted_ratio":   age_weighted_ratio,
                "temporal_drift_index": tdi,
                "halflife_days":        halflife_days,
                "n_sessions_used":      len(rows),
                "drift_direction":      drift_direction,
            }

        except Exception as exc:
            log.error(
                "AgeWeightedRatioPersistenceAgent: assessment error: %s", exc, exc_info=True
            )
            return {
                "age_weight_analysis_enabled": True,
                "drift_direction": "STABLE",
                "raw_ratio": 0.0,
                "age_weighted_ratio": 0.0,
                "temporal_drift_index": 0.0,
            }

    # ------------------------------------------------------------------
    # Poll loop
    # ------------------------------------------------------------------

    async def run_poll_loop(self) -> None:
        """Async poll loop — 3600s interval. Never raises."""
        log.info("AgeWeightedRatioPersistenceAgent starting (interval=%ss)", self._POLL_INTERVAL_S)
        while True:
            try:
                self._run_assessment()
            except Exception as exc:
                log.error(
                    "AgeWeightedRatioPersistenceAgent: unhandled poll error: %s", exc, exc_info=True
                )
            await asyncio.sleep(self._POLL_INTERVAL_S)
