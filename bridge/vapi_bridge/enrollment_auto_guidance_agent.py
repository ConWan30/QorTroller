"""
Phase 156 — EnrollmentAutoGuidanceAgent (agent #20)

Synthesizes Phase 151 capture guidance + Phase 154 stagnation + Phase 152 centroid velocity
+ Phase 155 controller status into a unified recommended_action with urgency_level.

Polls every 1 hour (enrollment_guidance_poll_interval_s=3600).
Publishes enrollment_guidance_update bus events.
Coordinates with TournamentActivationChainAgent (#16) when overall_ready=True.

Never raises from run_poll_loop().
"""

from __future__ import annotations

import asyncio
import json
import logging
import time

log = logging.getLogger(__name__)


class EnrollmentAutoGuidanceAgent:
    """
    Agent #20 — EnrollmentAutoGuidanceAgent.

    Reads:
        - Phase 151: get_enrollment_capture_guidance() — sessions_needed_total, overall_ready
        - Phase 154: compute_capture_stagnation() — stagnant, sessions_per_day
        - Phase 152: compute_centroid_velocity() — velocity_per_day, stagnant
        - Phase 155: get_controller_hardware_profiles() — attested_count

    Derives:
        - urgency_level: HIGH (stagnant + not ready), MEDIUM (velocity low), LOW (on track)
        - recommended_action: actionable text for operator
        - estimated_days: sessions_needed / sessions_per_day if not stagnant, else -1

    Publishes:
        - enrollment_guidance_update bus event with latest guidance

    Coordinates with TournamentActivationChainAgent (#16):
        - When overall_ready=True, emits activation_chain_event="enrollment_complete"
    """

    def __init__(self, cfg, store, bus=None) -> None:
        self._cfg   = cfg
        self._store = store
        self._bus   = bus

    # ------------------------------------------------------------------
    # Core synthesis
    # ------------------------------------------------------------------

    # Phase 157: covariance stability constants (WIF-016)
    _COV_MIN_RATIO    = 3.0   # Threshold below which diagonal covariance is used (Phase 142)
    _COV_FEAT_COUNT   = 8     # Touchpad feature dimensions used in Phase 143 analysis

    @staticmethod
    def _cov_stability_check(cov_np_ratio: float, cov_min_ratio: float, margin: float) -> str:
        """Classify the covariance regime from the N/p ratio (WIF-016/017).

        Returns:
          "diagonal_stable"      — N/p < cov_min_ratio - margin (safe diagonal zone)
          "transition_warning"   — N/p in [cov_min_ratio ± margin] (adversary exploit zone)
          "full_covariance_active" — N/p >= cov_min_ratio + margin (full covariance engaged)
        """
        if cov_np_ratio < (cov_min_ratio - margin):
            return "diagonal_stable"
        if cov_np_ratio < (cov_min_ratio + margin):
            return "transition_warning"
        return "full_covariance_active"

    def _synthesize_guidance(self) -> dict:
        """Synthesize all guidance signals into a unified report."""
        try:
            min_n = int(getattr(self._cfg, "min_touchpad_sessions_per_player", 10))
            guidance_report = self._store.get_enrollment_capture_guidance(min_n=min_n)
        except Exception:
            guidance_report = {"sessions_needed_total": 0, "overall_ready": False}

        sessions_needed          = int(guidance_report.get("sessions_needed_total", 0))
        guidance_overall_ready   = bool(guidance_report.get("overall_ready", False))

        # Phase 157 WIF-012: dual-condition — also require separation defensibility
        defensible = False
        n_per_player: dict = {}
        try:
            def_status = self._store.get_separation_defensibility_status(
                session_type="touchpad_corners"
            )
            if def_status:
                defensible   = bool(def_status.get("defensible", False))
                n_per_player = def_status.get("n_per_player", {}) or {}
        except Exception:
            pass  # fail-open: M-1 cleanup 2026-05-16 — intentional silent skip

        overall_ready = guidance_overall_ready and defensible

        # Phase 157 WIF-016/017: covariance stability check
        try:
            n_total   = sum(int(v) for v in n_per_player.values()) if n_per_player else 0
            cov_ratio = n_total / self._COV_FEAT_COUNT if n_total > 0 else 0.0
            margin    = float(getattr(self._cfg, "cov_stability_margin_np", 0.5))
            cov_regime_status = self._cov_stability_check(cov_ratio, self._COV_MIN_RATIO, margin)
        except Exception:
            cov_regime_status = "unknown"

        # Phase 154 — stagnation per probe type
        stagnant_probes: list[str] = []
        probe_types = ["touchpad_corners", "touchpad_freeform", "touchpad_swipes"]
        sessions_per_day_max = 0.0
        window_days = float(getattr(self._cfg, "capture_stagnation_window_days", 7.0))
        threshold   = float(getattr(self._cfg, "capture_stagnation_threshold", 0.5))
        for pt in probe_types:
            try:
                stag = self._store.compute_capture_stagnation(
                    probe_type=pt, window_days=window_days, threshold=threshold
                )
                if stag.get("stagnant", True):
                    stagnant_probes.append(pt)
                spd = float(stag.get("sessions_per_day", 0.0))
                if spd > sessions_per_day_max:
                    sessions_per_day_max = spd
            except Exception:
                stagnant_probes.append(pt)

        # Phase 152 — centroid velocity
        velocity_stagnant = True
        try:
            vel = self._store.compute_centroid_velocity(probe_type="touchpad_corners")
            velocity_stagnant = bool(vel.get("stagnant", True))
        except Exception:
            pass  # fail-open: M-1 cleanup 2026-05-16 — intentional silent skip

        # Derive urgency
        if overall_ready:
            urgency_level      = "LOW"
            recommended_action = "Enrollment complete. Run tournament preflight."
            activation_chain_event = "enrollment_complete"
        elif stagnant_probes and not overall_ready:
            urgency_level      = "HIGH"
            recommended_action = (
                f"URGENT: Capture stagnant on {stagnant_probes}. "
                f"Schedule {sessions_needed} more structured probe sessions."
            )
            activation_chain_event = None
        elif velocity_stagnant:
            urgency_level      = "MEDIUM"
            recommended_action = (
                f"Velocity plateaued. Continue capture sessions — "
                f"{sessions_needed} sessions remaining."
            )
            activation_chain_event = None
        else:
            urgency_level      = "LOW"
            recommended_action = (
                f"On track. {sessions_needed} sessions remaining to enrollment readiness."
            )
            activation_chain_event = None

        # Estimated days to completion
        if overall_ready:
            estimated_days = 0.0
        elif sessions_per_day_max > 0:
            estimated_days = round(sessions_needed / sessions_per_day_max, 1)
        else:
            estimated_days = -1.0

        return {
            "sessions_needed_total":  sessions_needed,
            "overall_ready":          overall_ready,
            "recommended_action":     recommended_action,
            "urgency_level":          urgency_level,
            "stagnant_probes":        stagnant_probes,
            "estimated_days":         estimated_days,
            "activation_chain_event": activation_chain_event,
            "cov_regime_status":      cov_regime_status,
        }

    # ------------------------------------------------------------------
    # Poll loop
    # ------------------------------------------------------------------

    async def run_poll_loop(self) -> None:
        """1-hour poll loop — synthesizes guidance and persists report."""
        poll_s = int(getattr(self._cfg, "enrollment_guidance_poll_interval_s", 3600))
        while True:
            try:
                report = self._synthesize_guidance()
                self._store.insert_enrollment_guidance_log(
                    sessions_needed_total  = report["sessions_needed_total"],
                    overall_ready          = report["overall_ready"],
                    recommended_action     = report["recommended_action"],
                    urgency_level          = report["urgency_level"],
                    stagnant_probes        = json.dumps(report["stagnant_probes"]),
                    estimated_days         = report["estimated_days"],
                    activation_chain_event = report["activation_chain_event"],
                    cov_regime_status      = report.get("cov_regime_status", "unknown"),
                )

                if self._bus is not None:
                    try:
                        self._bus.publish_sync("enrollment_guidance_update", {
                            **report,
                            "ts": time.time(),
                        })
                    except Exception:
                        pass  # fail-open: M-1 cleanup 2026-05-16 — intentional silent skip

                log.debug(
                    "[EnrollmentAutoGuidanceAgent] urgency=%s sessions_needed=%d ready=%s",
                    report["urgency_level"],
                    report["sessions_needed_total"],
                    report["overall_ready"],
                )
            except Exception:
                log.debug("[EnrollmentAutoGuidanceAgent] poll error", exc_info=True)

            await asyncio.sleep(poll_s)
