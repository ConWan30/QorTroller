"""
Phase 207 — StagedDryRunGraduationAgent

Controls the controlled per-agent transition from dry_run=True → dry_run=False.

Graduation is sequential: agents are activated one at a time via
POST /agent/activate-graduation-stage.  Each graduated agent accumulates
clean-session credits while the graduation window is monitored for false positives.

Rollback is automatic: when n_false_positives >= graduation_fp_threshold within
the last graduation_rollback_window_sessions sessions, the agent reverts to
dry_run=True and a rollback entry is recorded in dry_run_graduation_log.

P0 Preconditions (checked at activation time):
  - tournament_preflight overall_pass=True (separation_ok + all_pairs_p0_ok + biometric_ttl_ok)
  - non_convergence_detected=False (TremorRestingConvergenceOracle is stable)
  - staged_graduation_enabled=True

Poll interval: 10 minutes (graduation_poll_interval_s=600).
Never raises from run_poll_loop().
"""

from __future__ import annotations

import asyncio
import logging
import time

log = logging.getLogger(__name__)

# Ordered list of VAPI core agents eligible for sequential graduation.
# Agents are graduated in this order — never simultaneously.
GRADUATION_SEQUENCE = [
    "ruling_enforcement_agent",       # Stage 1: enforcement rulings
    "session_adjudicator",            # Stage 2: autonomous adjudication
    "tournament_activation_chain",    # Stage 3: activation gate
]


class StagedDryRunGraduationAgent:
    """
    Phase 207 — StagedDryRunGraduationAgent.

    Reads:
        - store.get_tremor_convergence_status(): non_convergence_detected gate
        - store.get_tournament_preflight_status(): overall_pass P0 gate
        - store.get_all_graduation_stages(): current graduation state

    Publishes:
        - graduation_stage_activated bus event (when stage activated)
        - graduation_rollback_triggered bus event (when rollback fires)

    Design invariants:
        - P0 preconditions MUST pass before any stage activation
        - Rollback is irreversible for the current stage — a new stage must be
          inserted to re-graduate the same agent after investigation
        - staged_graduation_enabled=False hard-gates all activation; agent
          only monitors but never modifies graduation state when disabled
    """

    def __init__(self, cfg, store, bus=None) -> None:
        self._cfg   = cfg
        self._store = store
        self._bus   = bus

    # ------------------------------------------------------------------
    # P0 precondition check
    # ------------------------------------------------------------------

    def check_graduation_preconditions(self) -> dict:
        """Check all P0 preconditions for graduation activation.

        Returns a dict with:
          - preconditions_met: bool (True only when ALL gates pass)
          - preflight_ok: bool
          - non_convergence_clear: bool
          - graduation_enabled: bool
          - blockers: list[str]
        """
        blockers: list[str] = []

        # Gate 1: staged_graduation_enabled
        graduation_enabled = bool(getattr(self._cfg, "staged_graduation_enabled", False))
        if not graduation_enabled:
            blockers.append("staged_graduation_enabled=False")

        # Gate 2: tournament preflight overall_pass
        preflight_ok = False
        try:
            pf = self._store.get_tournament_preflight_status()
            if pf and pf.get("overall_pass"):
                preflight_ok = True
            else:
                blockers.append("tournament_preflight overall_pass=False")
        except Exception:
            blockers.append("tournament_preflight_unavailable")

        # Gate 3: non_convergence_detected=False
        non_convergence_clear = True
        try:
            tc = self._store.get_tremor_convergence_status("tremor_resting")
            if tc and tc.get("non_convergence_detected"):
                non_convergence_clear = False
                blockers.append("non_convergence_detected=True")
        except Exception:
            pass  # No tremor data yet → no non-convergence block; fail-open: M-1 cleanup 2026-05-16

        return {
            "preconditions_met":   len(blockers) == 0,
            "graduation_enabled":  graduation_enabled,
            "preflight_ok":        preflight_ok,
            "non_convergence_clear": non_convergence_clear,
            "blockers":            blockers,
        }

    # ------------------------------------------------------------------
    # Stage activation
    # ------------------------------------------------------------------

    def activate_stage(self, agent_id: str, notes: str = "") -> dict:
        """Activate a graduation stage for agent_id.

        Returns a result dict with:
          - activated: bool
          - row_id: int or None
          - error: str or None
          - preconditions: dict
        """
        preconditions = self.check_graduation_preconditions()
        if not preconditions["preconditions_met"]:
            return {
                "activated":    False,
                "row_id":       None,
                "error":        "P0 preconditions not met: " + "; ".join(preconditions["blockers"]),
                "preconditions": preconditions,
            }

        # Determine next stage number
        existing = self._store.get_all_graduation_stages()
        next_stage = len(existing) + 1

        try:
            row_id = self._store.insert_graduation_stage(
                agent_id=agent_id,
                stage_number=next_stage,
                notes=notes or f"Stage {next_stage} activated at {time.time():.0f}",
            )
        except Exception as exc:
            return {
                "activated":    False,
                "row_id":       None,
                "error":        str(exc),
                "preconditions": preconditions,
            }

        log.info(
            "[StagedDryRunGraduationAgent] Stage %d activated: agent=%s row_id=%d",
            next_stage, agent_id, row_id,
        )

        if self._bus is not None:
            try:
                self._bus.publish_sync("graduation_stage_activated", {
                    "agent_id":    agent_id,
                    "stage":       next_stage,
                    "row_id":      row_id,
                    "ts":          time.time(),
                })
            except Exception:
                pass  # fail-open: M-1 cleanup 2026-05-16 — intentional silent skip

        return {
            "activated":    True,
            "row_id":       row_id,
            "stage_number": next_stage,
            "agent_id":     agent_id,
            "error":        None,
            "preconditions": preconditions,
        }

    # ------------------------------------------------------------------
    # Rollback monitoring
    # ------------------------------------------------------------------

    def _check_rollbacks(self) -> None:
        """Poll all active graduation stages and trigger rollback when FP threshold exceeded."""
        fp_threshold = int(getattr(self._cfg, "graduation_fp_threshold", 2))
        try:
            stages = self._store.get_all_graduation_stages()
        except Exception:
            return

        for stage in stages:
            if stage.get("rollback_triggered"):
                continue
            fp = int(stage.get("n_false_positives", 0))
            if fp >= fp_threshold:
                agent_id = stage["agent_id"]
                triggered = self._store.trigger_graduation_rollback(
                    agent_id=agent_id,
                    reason=f"poll-detected: {fp}>={fp_threshold} false positives",
                )
                if triggered:
                    log.warning(
                        "[StagedDryRunGraduationAgent] ROLLBACK stage=%d agent=%s fp=%d",
                        stage["stage_number"], agent_id, fp,
                    )
                    if self._bus is not None:
                        try:
                            self._bus.publish_sync("graduation_rollback_triggered", {
                                "agent_id":     agent_id,
                                "stage_number": stage["stage_number"],
                                "n_false_positives": fp,
                                "ts":           time.time(),
                            })
                        except Exception:
                            pass  # fail-open: M-1 cleanup 2026-05-16 — intentional silent skip

    # ------------------------------------------------------------------
    # Poll loop
    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    # Phase 214: GraduationAutowatchBridge — auto-evaluate on trigger
    # ------------------------------------------------------------------

    def _check_autowatch_triggers(self) -> None:
        """Auto-evaluate graduation preconditions for new autowatch triggers (Phase 214).

        Reads graduation_autowatch_log for entries with trigger_fired=True and
        preconditions_evaluated=False.  For each, calls check_graduation_preconditions()
        and inserts a result entry to the autowatch log.
        """
        import json as _json214
        if not bool(getattr(self._cfg, "graduation_autowatch_enabled", True)):
            return

        try:
            status = self._store.get_graduation_autowatch_status(limit=10)
        except Exception as exc:
            log.debug("[StagedDryRunGraduationAgent] autowatch status error: %s", exc)
            return

        # Find unevaluated trigger entries
        unevaluated = [
            e for e in status.get("entries", [])
            if e.get("trigger_fired") and not e.get("preconditions_evaluated")
        ]
        if not unevaluated:
            return

        preconditions = self.check_graduation_preconditions()
        blockers_json = _json214.dumps(preconditions.get("blockers", []))

        for entry in unevaluated:
            try:
                self._store.insert_graduation_autowatch_log(
                    probe_type=entry.get("probe_type", "tremor_resting"),
                    ratio=float(entry.get("ratio", 0.0)),
                    all_pairs_above_1=bool(entry.get("all_pairs_above_1", True)),
                    trigger_fired=False,
                    preconditions_evaluated=True,
                    preconditions_met=preconditions["preconditions_met"],
                    blockers_json=blockers_json,
                )
            except Exception as exc:
                log.debug("[StagedDryRunGraduationAgent] autowatch eval log error: %s", exc)

        if preconditions["preconditions_met"]:
            log.info(
                "[StagedDryRunGraduationAgent] Phase 214: autowatch preconditions MET — "
                "operator may now call POST /agent/activate-graduation-stage"
            )
            if self._bus is not None:
                try:
                    self._bus.publish_sync("graduation_preconditions_met", {
                        "preconditions": preconditions,
                        "ts":            asyncio.get_event_loop().time(),
                    })
                except Exception:
                    pass  # fail-open: M-1 cleanup 2026-05-16 — intentional silent skip
        else:
            log.info(
                "[StagedDryRunGraduationAgent] Phase 214: autowatch preconditions NOT met: %s",
                preconditions.get("blockers", []),
            )

    # ------------------------------------------------------------------
    # Poll loop
    # ------------------------------------------------------------------

    async def run_poll_loop(self) -> None:
        """10-minute poll loop — monitors graduation stages for rollback conditions.

        Phase 214 extension: also checks graduation_autowatch_log for new trigger
        entries and auto-evaluates preconditions (graduation_autowatch_enabled=True).
        """
        poll_s = int(getattr(self._cfg, "graduation_poll_interval_s", 600))
        while True:
            try:
                if bool(getattr(self._cfg, "staged_graduation_enabled", False)):
                    self._check_rollbacks()
                    log.debug("[StagedDryRunGraduationAgent] poll complete")
                # Phase 214: always check autowatch regardless of staged_graduation_enabled
                # (monitoring is always-on; activation still gates on staged_graduation_enabled)
                self._check_autowatch_triggers()
            except Exception:
                log.debug("[StagedDryRunGraduationAgent] poll error", exc_info=True)
            await asyncio.sleep(poll_s)
