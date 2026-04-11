"""
Phase 183 — MaturityElevationGateAgent (agent #28)

Reads the 6-component protocol_maturity_log (Phase 177) and generates an actionable
elevation_plan — a per-component breakdown of gap, action, and estimated sessions
to advance maturity tier.

WIF-027 W2 CLOSED: Phase 177 created the maturity score oracle; Phase 183 creates
the machine-generated path to reach score >= 0.85 (PRODUCTION_CANDIDATE tier,
DePIN trustworthiness oracle).

Maturity tier thresholds:
    ALPHA              < 0.50
    BETA               0.50 - 0.85
    PRODUCTION_CANDIDATE >= 0.85 (requires separation_ratio > 1.0 + all gates met)

Fires maturity_elevation_available bus event when gap_to_target < 0.05 (within
striking distance of next tier upgrade).

Poll interval: 600s (10 minutes).
Fail-safe: errors → ALPHA-tier plan returned (never blocks on error).
"""

from __future__ import annotations

import asyncio
import json
import logging
import time

log = logging.getLogger(__name__)

_BETA_THRESHOLD       = 0.50
_PRODUCTION_THRESHOLD = 0.85
_ELEVATION_PROXIMITY  = 0.05   # gap_to_target < this → elevation_available=True

# Per-component action map: maps component name → actionable recommendation
_COMPONENT_ACTIONS: dict[str, dict] = {
    "separation_component": {
        "action":             "P1_RE_ENROLLMENT — run >=4 mixed_biometric_probe sessions "
                              "(same sitting); target separation_ratio > 0.70",
        "sessions_per_unit":  4,
        "blocking":           True,
    },
    "chain_integrity_component": {
        "action":             "Ensure no broken PoAC chain links; run GET /agent/poac-chain-integrity "
                              "and resolve broken_links == 0",
        "sessions_per_unit":  0,
        "blocking":           False,
    },
    "consent_component": {
        "action":             "Verify all active players have consent_given=1, revoked_at IS NULL; "
                              "run GET /agent/consent-aware-corpus-status",
        "sessions_per_unit":  0,
        "blocking":           False,
    },
    "biometric_freshness_component": {
        "action":             "Credential age < 90 days; trigger POST /agent/renew-separation-ratio-commitment "
                              "when biometric_credential_age status shows ttl_expired=True",
        "sessions_per_unit":  0,
        "blocking":           False,
    },
    "agent_calibration_component": {
        "action":             "Run POST /agent/run-agent-self-test; resolve any FAIL agents; "
                              "target agent_calibration_health.pass_rate == 1.0",
        "sessions_per_unit":  0,
        "blocking":           False,
    },
    "enrollment_component": {
        "action":             "Achieve >= 10 sessions/player (P1=6 currently); "
                              "run python scripts/terminal_calibration_runner.py "
                              "--battery mixed_biometric_probe for P1 (4 sessions needed)",
        "sessions_per_unit":  4,
        "blocking":           True,
    },
}


class MaturityElevationGateAgent:
    """
    Agent #28 — MaturityElevationGateAgent.

    Reads:
        - store.get_protocol_maturity_status(): 6-component maturity score (Phase 177)

    Computes:
        - current_tier: ALPHA | BETA | PRODUCTION_CANDIDATE
        - target_tier: next tier boundary
        - gap_to_target: score gap to reach target tier
        - elevation_plan: per-component breakdown of gap, action, estimated_sessions
        - estimated_sessions_total: sum of blocking component sessions
        - critical_component: component with largest gap * blocking weight

    Stores:
        - maturity_elevation_log (Phase 183)

    Publishes:
        - maturity_elevation_available bus event when gap_to_target < 0.05
    """

    _POLL_INTERVAL_S = 600

    def __init__(self, cfg, store, bus=None) -> None:
        self._cfg   = cfg
        self._store = store
        self._bus   = bus

    # ------------------------------------------------------------------
    # Tier and gap computation
    # ------------------------------------------------------------------

    @staticmethod
    def _classify_tier(score: float) -> str:
        if score >= _PRODUCTION_THRESHOLD:
            return "PRODUCTION_CANDIDATE"
        if score >= _BETA_THRESHOLD:
            return "BETA"
        return "ALPHA"

    @staticmethod
    def _compute_gaps(score: float) -> tuple[str, float]:
        """Return (target_tier, gap_to_target)."""
        if score < _BETA_THRESHOLD:
            return ("BETA", round(_BETA_THRESHOLD - score, 4))
        if score < _PRODUCTION_THRESHOLD:
            return ("PRODUCTION_CANDIDATE", round(_PRODUCTION_THRESHOLD - score, 4))
        return ("PRODUCTION_CANDIDATE", 0.0)

    def _build_elevation_plan(
        self,
        maturity_status: dict,
        current_score: float,
        target_tier: str,
    ) -> tuple[dict, str, int]:
        """Build per-component elevation plan.

        Returns:
            (plan_dict, critical_component, estimated_sessions_total)
        """
        # Component weights from Phase 177 (sum = 1.0)
        _WEIGHTS = {
            "separation_component":          0.25,
            "chain_integrity_component":     0.20,
            "consent_component":             0.15,
            "biometric_freshness_component": 0.15,
            "agent_calibration_component":   0.15,
            "enrollment_component":          0.10,
        }

        target_score = _BETA_THRESHOLD if target_tier == "BETA" else _PRODUCTION_THRESHOLD

        plan:          dict = {}
        sessions_total = 0
        worst_gap_weighted = -1.0
        critical_comp  = ""

        for comp_name, weight in _WEIGHTS.items():
            current_comp = float(maturity_status.get(comp_name, 0.0))
            # Target per-component score: assume proportional contribution
            target_comp = min(1.0, target_score / weight) if weight > 0 else 1.0
            gap = max(0.0, round(target_comp - current_comp, 4))

            comp_meta  = _COMPONENT_ACTIONS.get(comp_name, {})
            action     = comp_meta.get("action", "Investigate this component")
            blocking   = comp_meta.get("blocking", False)
            est_sess   = comp_meta.get("sessions_per_unit", 0) if gap > 0 else 0

            plan[comp_name] = {
                "current":             current_comp,
                "target":              round(target_comp, 4),
                "gap":                 gap,
                "action":              action,
                "estimated_sessions":  est_sess,
                "blocking":            blocking,
            }

            if blocking and gap > 0:
                sessions_total += est_sess

            weighted_gap = gap * weight
            if weighted_gap > worst_gap_weighted:
                worst_gap_weighted = weighted_gap
                critical_comp = comp_name

        return (plan, critical_comp, sessions_total)

    # ------------------------------------------------------------------
    # Poll logic
    # ------------------------------------------------------------------

    def _run_assessment(self) -> dict:
        """Run one elevation planning cycle.

        Returns summary dict. Fail-safe: any error → ALPHA-tier safe defaults.
        """
        if not getattr(self._cfg, "maturity_elevation_enabled", True):
            return {
                "maturity_elevation_enabled": False,
                "current_tier":              "ALPHA",
                "target_tier":               "BETA",
                "gap_to_target":             1.0,
                "elevation_available":       False,
            }

        try:
            maturity_status_rows = self._store.get_protocol_maturity_status()
            maturity_status = maturity_status_rows[0] if maturity_status_rows else {}
            current_score   = float(maturity_status.get("maturity_score", 0.0))
            current_tier    = self._classify_tier(current_score)
            target_tier, gap = self._compute_gaps(current_score)
            elevation_available = gap < _ELEVATION_PROXIMITY

            plan, critical_comp, est_sessions = self._build_elevation_plan(
                maturity_status, current_score, target_tier
            )

            plan_json = json.dumps(plan)

            self._store.insert_maturity_elevation_log(
                current_tier=current_tier,
                target_tier=target_tier,
                gap_to_target=gap,
                elevation_plan_json=plan_json,
                elevation_available=elevation_available,
                critical_component=critical_comp,
                estimated_sessions_total=est_sessions,
            )

            if elevation_available and self._bus is not None:
                try:
                    self._bus.publish("maturity_elevation", {
                        "maturity_elevation_available": True,
                        "current_tier":                 current_tier,
                        "target_tier":                  target_tier,
                        "gap_to_target":                gap,
                        "ts":                           time.time(),
                    })
                except Exception as exc:
                    log.debug("MaturityElevationGateAgent: bus publish error: %s", exc)

            return {
                "maturity_elevation_enabled": True,
                "current_tier":               current_tier,
                "target_tier":                target_tier,
                "gap_to_target":              gap,
                "elevation_available":        elevation_available,
                "elevation_plan":             plan,
                "critical_component":         critical_comp,
                "estimated_sessions_total":   est_sessions,
            }

        except Exception as exc:
            log.error("MaturityElevationGateAgent: assessment error: %s", exc, exc_info=True)
            # Fail-safe: return ALPHA defaults (never raises)
            return {
                "maturity_elevation_enabled": True,
                "current_tier":               "ALPHA",
                "target_tier":                "BETA",
                "gap_to_target":              1.0,
                "elevation_available":        False,
                "elevation_plan":             {},
                "critical_component":         "separation_component",
                "estimated_sessions_total":   4,
            }

    async def run_poll_loop(self) -> None:
        """Async poll loop — 600s interval. Never raises."""
        log.info("MaturityElevationGateAgent starting (interval=%ss)", self._POLL_INTERVAL_S)
        while True:
            try:
                self._run_assessment()
            except Exception as exc:
                log.error("MaturityElevationGateAgent: unhandled error in poll: %s", exc, exc_info=True)
            await asyncio.sleep(self._POLL_INTERVAL_S)
