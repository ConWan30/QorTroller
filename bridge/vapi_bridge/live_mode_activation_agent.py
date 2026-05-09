"""Phase 79 — LiveModeActivationAgent: multi-condition live-mode readiness checker.

Subscribes to dry_run_gate_passed events from SessionAdjudicatorValidationAgent
via AgentMessageBus. On receipt, evaluates the full multi-condition checklist.
NEVER activates live mode automatically. Emits live_mode_candidate advisory only.

Checklist conditions (all must pass for ready_for_live_mode=True):
1. validation_gate_passed       — consecutive_clean >= gate_n AND divergence_rate OK
2. no_recent_operator_overrides — no manual overrides in last gate_n window
3. no_recent_key_rotation       — no ceremony_key_rotated in last 24h
4. divergence_rate_within_tolerance — rate <= max_divergence_rate
5. consecutive_clean_met        — consecutive_clean >= gate_n

Operator must explicitly set AGENT_DRY_RUN=false via POST /agent/config.
"""

import asyncio
import json
import logging
import time

log = logging.getLogger(__name__)

_POLL_INTERVAL_S = 300        # 5-minute fallback cycle
_KEY_ROTATION_LOOKBACK_H = 24  # 24 hours


class LiveModeActivationAgent:
    """Phase 79 — Coordinates dry-run → live enforcement transition.

    Subscribes to dry_run_gate_passed events via AgentMessageBus.
    Evaluates multi-condition checklist on each gate event + 5-min fallback.
    Emits live_mode_candidate advisory to bridge_agent (never auto-activates).
    """

    def __init__(self, cfg, store, bus=None) -> None:
        self._cfg = cfg
        self._store = store
        self._bus = bus

    async def run_event_consumer(self) -> None:
        """Event-driven consumer + 5-min fallback polling."""
        log.info("LiveModeActivationAgent started (Phase 79)")
        if self._bus is None:
            log.warning("LiveModeActivationAgent: no bus — running in poll-only mode")
            await self._poll_loop()
            return

        queue = await self._bus.subscribe("dry_run_gate_passed")
        _consecutive_failures = 0
        while True:
            try:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=_POLL_INTERVAL_S)
                    await self._on_gate_passed(event)
                except asyncio.TimeoutError:
                    # 5-min fallback: check checklist state even without bus event
                    await self._evaluate_checklist_and_maybe_emit()
                _consecutive_failures = 0
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                _consecutive_failures += 1
                if _consecutive_failures >= 3:
                    log.error(
                        "LiveModeActivationAgent: %d consecutive failures: %s",
                        _consecutive_failures, exc,
                    )
                else:
                    log.warning("LiveModeActivationAgent: cycle error: %s", exc)
                # Phase 235.x-STABILITY-6: defensive backoff. See chain_reconciler
                # for the empirical signature ('no running event loop' tight loop
                # at ~100k errors/sec when DUALSHOCK_ENABLED=false).
                try:
                    await asyncio.sleep(min(_POLL_INTERVAL_S, 5.0))
                except asyncio.CancelledError:
                    raise
                except Exception as backoff_exc:
                    log.error(
                        "LiveModeActivationAgent: backoff sleep failed (%s) — "
                        "exiting loop cleanly", backoff_exc,
                    )
                    return

    async def _poll_loop(self) -> None:
        """Fallback polling loop when bus is not available."""
        _consecutive_failures = 0
        while True:
            try:
                await asyncio.sleep(_POLL_INTERVAL_S)
                await self._evaluate_checklist_and_maybe_emit()
                _consecutive_failures = 0
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                _consecutive_failures += 1
                if _consecutive_failures >= 3:
                    log.error(
                        "LiveModeActivationAgent (poll): %d consecutive failures: %s",
                        _consecutive_failures, exc,
                    )
                else:
                    log.warning("LiveModeActivationAgent (poll): cycle error: %s", exc)
                # Phase 235.x-STABILITY-6: defensive backoff (see above).
                try:
                    await asyncio.sleep(min(_POLL_INTERVAL_S, 5.0))
                except asyncio.CancelledError:
                    raise
                except Exception as backoff_exc:
                    log.error(
                        "LiveModeActivationAgent (poll): backoff sleep failed "
                        "(%s) — exiting loop cleanly", backoff_exc,
                    )
                    return

    async def _on_gate_passed(self, event: dict) -> None:
        """Handle dry_run_gate_passed bus event."""
        payload = event.get("payload", {})
        log.info(
            "LiveModeActivationAgent: gate_passed event received "
            "(consecutive_clean=%s gate_n=%s)",
            payload.get("consecutive_clean", "?"),
            payload.get("gate_n", "?"),
        )
        await self._evaluate_checklist_and_maybe_emit()

    async def _evaluate_checklist_and_maybe_emit(self) -> None:
        """Evaluate all 5 conditions and emit advisory if all pass."""
        try:
            status = self.get_live_mode_status()
            if status["ready_for_live_mode"]:
                self._store.write_agent_event(
                    event_type="live_mode_candidate",
                    payload=json.dumps({
                        "conditions": status["conditions"],
                        "gate_summary": status.get("gate_summary", {}),
                        "recommendation": (
                            "All conditions met — operator may set AGENT_DRY_RUN=false "
                            "via POST /agent/config to enable live enforcement."
                        ),
                    }),
                    source="live_mode_activation_agent",
                    target="bridge_agent",
                    device_id="",
                )
                try:
                    self._store.insert_live_mode_transition(
                        event_type="candidate_emitted",
                        consecutive_clean=status["gate_summary"].get("consecutive_clean", 0),
                        divergence_rate=status["gate_summary"].get("divergence_rate", 0.0),
                        conditions_json=json.dumps(status["conditions"]),
                    )
                except Exception as exc:
                    log.debug("LiveModeActivationAgent: insert_live_mode_transition failed: %s", exc)
                log.info(
                    "LiveModeActivationAgent: LIVE MODE CANDIDATE — all conditions met. "
                    "Operator action required."
                )
        except Exception as exc:
            log.warning("LiveModeActivationAgent: checklist evaluation failed: %s", exc)

    def get_live_mode_status(self) -> dict:
        """Return current live-mode readiness status with all 5 conditions.

        This method is called directly by operator_api GET /agent/live-mode-status.
        Never raises.
        """
        gate_n = int(getattr(self._cfg, "validation_gate_n", 100))
        max_rate = float(getattr(self._cfg, "validation_max_divergence_rate", 1.0))
        current_dry_run = bool(getattr(self._cfg, "agent_dry_run_mode", True))

        try:
            summary = self._store.get_validation_summary(gate_n, max_rate)
        except Exception as exc:
            log.warning("LiveModeActivationAgent: get_validation_summary failed: %s", exc)
            summary = {
                "consecutive_clean": 0, "gate_passed": False,
                "divergence_rate": 0.0, "divergence_rate_ok": True,
                "gate_n": gate_n,
            }

        gate_passed = summary.get("gate_passed", False)
        consecutive_clean = summary.get("consecutive_clean", 0)
        divergence_rate = summary.get("divergence_rate", 0.0)
        divergence_rate_ok = summary.get("divergence_rate_ok", True)

        # Condition 2: no recent operator overrides (within last gate_n rulings)
        try:
            override_count = self._store.count_operator_overrides(within_n=gate_n)
            no_recent_overrides = override_count == 0
        except Exception:
            no_recent_overrides = True  # safe default

        # Condition 3: no ceremony key rotation within 24h
        try:
            rotation_count = self._store.count_ceremony_key_rotations(
                within_hours=_KEY_ROTATION_LOOKBACK_H
            )
            no_recent_key_rotation = rotation_count == 0
        except Exception:
            no_recent_key_rotation = True  # safe default

        conditions = {
            "validation_gate_passed": gate_passed,
            "no_recent_operator_overrides": no_recent_overrides,
            "no_recent_key_rotation": no_recent_key_rotation,
            "divergence_rate_within_tolerance": divergence_rate_ok,
            "consecutive_clean_met": consecutive_clean >= gate_n,
        }

        blocking = [k for k, v in conditions.items() if not v]
        ready = len(blocking) == 0

        if ready:
            action = (
                "All conditions met — set AGENT_DRY_RUN=false via POST /agent/config "
                "to enable live enforcement"
            )
        else:
            reasons = []
            if not gate_passed:
                reasons.append(
                    f"gate not passed (consecutive_clean={consecutive_clean}/{gate_n})"
                )
            if not no_recent_overrides:
                reasons.append("recent operator overrides detected")
            if not no_recent_key_rotation:
                reasons.append("ceremony key rotated within 24h")
            if not divergence_rate_ok:
                reasons.append(f"divergence_rate={divergence_rate:.2%} exceeds tolerance")
            action = f"Conditions not met: {blocking} — {'; '.join(reasons)}"

        return {
            "ready_for_live_mode": ready,
            "current_dry_run": current_dry_run,
            "conditions": conditions,
            "blocking_conditions": blocking,
            "gate_summary": {
                "consecutive_clean": consecutive_clean,
                "divergence_rate": divergence_rate,
                "gate_passed": gate_passed,
                "gate_n": gate_n,
            },
            "recommended_action": action,
        }
