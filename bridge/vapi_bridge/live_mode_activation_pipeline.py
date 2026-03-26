"""Phase 92 — Live Mode Activation Pipeline.

Polls Phase 89 ProtocolIntelligenceAgent ready_for_live_mode status every 5 minutes.
Records all readiness checks to live_mode_activation_log audit table.
Provides POST /agent/request-activation operator endpoint that:
  1. Checks ready_for_live_mode from latest protocol_intelligence_reports row
  2. Records operator intent in live_mode_activation_log
  3. Returns status + blocking_conditions + recommended_action
  4. NEVER auto-activates — operator must still set AGENT_DRY_RUN=false

GET /agent/activation-log returns full audit trail.
Tool #59 get_activation_log.
"""

import asyncio
import json
import logging

log = logging.getLogger(__name__)

_POLL_INTERVAL_S = 300  # 5 minutes


class LiveModeActivationPipeline:
    """Phase 92 — Automated readiness audit pipeline for live mode activation.

    Polls Protocol Intelligence Agent data every 5 minutes and records
    every readiness state to the live_mode_activation_log table.
    Never auto-activates; always defers to operator decision.
    """

    def __init__(self, cfg, store, bus=None):
        self._cfg = cfg
        self._store = store
        self._bus = bus

    async def run_poll_loop(self) -> None:
        """5-min poll: check readiness, record to audit log."""
        log.info("LiveModeActivationPipeline started (Phase 92)")
        while True:
            try:
                await asyncio.sleep(_POLL_INTERVAL_S)
                await self._check_and_record("readiness_check")
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                log.warning("LiveModeActivationPipeline: error: %s", exc)

    async def _check_and_record(self, event_type: str, operator_notes=None) -> dict:
        """Read Phase 89 report, compute blocking conditions, record to activation log.

        Returns dict with ready_for_live_mode, protocol_health_score, bottleneck,
        blocking_conditions, and recommended_action.
        """
        try:
            report = self._store.get_latest_protocol_intelligence_report() or {}
        except Exception as exc:
            log.warning("LiveModeActivationPipeline: could not read PI report: %s", exc)
            report = {}

        ready = bool(report.get("ready_for_live_mode", 0))
        score = float(report.get("protocol_health_score", 0.0))
        bottleneck = report.get("bottleneck")

        # Derive blocking conditions
        blocking = []
        gate_progress = float(report.get("gate_progress_score", 0.0))
        if gate_progress < 0.85:
            blocking.append("validation_gate_not_passed")

        # Parse fleet health from components_json
        components_json = report.get("components_json")
        if isinstance(components_json, str):
            try:
                comps = json.loads(components_json)
            except Exception:
                comps = {}
        else:
            comps = components_json or {}

        if comps.get("fleet_health") in ("CRITICAL", "UNKNOWN"):
            blocking.append("fleet_health_critical")

        if score < 85.0:
            blocking.append(f"score_below_85_{score:.1f}")

        blocking_json = json.dumps(blocking)

        try:
            self._store.insert_live_mode_activation_log(
                event_type=event_type,
                ready_for_live_mode=1 if ready else 0,
                protocol_health_score=score,
                bottleneck=bottleneck,
                blocking_conditions=blocking_json,
                operator_notes=operator_notes,
            )
        except Exception as exc:
            log.warning("LiveModeActivationPipeline: could not write log: %s", exc)

        return {
            "ready_for_live_mode": ready,
            "protocol_health_score": score,
            "bottleneck": bottleneck,
            "blocking_conditions": blocking,
            "recommended_action": (
                "Set AGENT_DRY_RUN=false via POST /agent/config"
                if ready
                else f"Not ready — blocking: {blocking}"
            ),
        }
