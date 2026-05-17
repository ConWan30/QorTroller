"""Phase 89 — Protocol Intelligence Synthesis Agent.

Synthesizes all VAPI agent data streams into a unified protocol_health_score (0-100)
and ready_for_live_mode boolean. Replaces 7 separate endpoint calls with one.

Score formula (5-component base, weights sum to 1.0):
  protocol_health_score = 100 * (
    0.35 * gate_progress_score        # consecutive_clean / gate_n
    + 0.25 * fleet_health_score       # ALL_HEALTHY=1.0, DEGRADED=0.5, CRITICAL/UNKNOWN=0.0
    + 0.20 * divergence_clarity_score # 1 - unexplained_divergence_fraction
    + 0.10 * corpus_pass_score        # synthetic corpus pass_rate (0.5 neutral if no runs)
    + 0.10 * class_j_confidence_score # fraction of devices with LOW Class J risk (0.5 neutral)
  )

  Phase 90 bonus (+5 pts max): shadow_pass_score if shadow_enforcement_log has rows.
  Phase 91 bonus (+5 pts max): triage_confidence_score if divergence_triage_reports has rows.
  Score capped at 100.0.

ready_for_live_mode = score >= 85.0 AND gate_passed AND fleet_health not in (CRITICAL, UNKNOWN)
bottleneck = name of lowest-contributing component (what to fix next).
estimated_days_to_gate = remaining / sessions_per_day (velocity from ruling_validation_log timestamps).

Subscribes to dry_run_gate_passed + agent_health_report bus events for immediate rescore.
Polls every 5 minutes as fallback. Never raises.
"""
import asyncio
import json
import logging
import time

log = logging.getLogger(__name__)

_POLL_INTERVAL_S = 300  # 5 minutes


class ProtocolIntelligenceAgent:
    """Phase 89 — Synthesizes all VAPI agent streams into unified protocol_health_score."""

    def __init__(self, cfg, store, bus=None) -> None:
        self._cfg = cfg
        self._store = store
        self._bus = bus
        self._gate_n = int(getattr(cfg, "validation_gate_n", 100))
        self._max_rate = float(getattr(cfg, "validation_max_divergence_rate", 1.0))

    async def run_event_consumer(self) -> None:
        log.info("ProtocolIntelligenceAgent started (Phase 89) gate_n=%d", self._gate_n)
        if self._bus is not None:
            try:
                await self._bus.subscribe("dry_run_gate_passed")
                await self._bus.subscribe("agent_health_report")
            except Exception as _sub_exc:
                log.debug("ProtocolIntelligenceAgent: bus subscribe failed: %s", _sub_exc)

        while True:
            try:
                await asyncio.sleep(_POLL_INTERVAL_S)
                await self._compute_and_store()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                log.warning("ProtocolIntelligenceAgent: cycle error: %s", exc)

    async def _compute_and_store(self) -> dict:
        from .loop_timing import timed_block
        _warn_s = float(getattr(
            self._cfg, "protocol_intel_compute_warn_duration_s", 2.0
        ))
        try:
            # Phase 235.x-STABILITY-9 stage 7 (2026-05-17): instrumented.
            # Outer timing covers both compute_report (10+ sync SQL via
            # to_thread, stage 3) + insert_protocol_intelligence_report.
            with timed_block(
                "PIA_compute_and_store",
                warn_s=_warn_s,
                logger=log,
                prefix="[ProtocolIntelligenceAgent] STAGE-7",
                always_info=True,
                slow_word="SLOW COMPUTE",
                hint="compute_report (10+ SQL) or insert exceeded threshold "
                     "— investigate query plan or executor saturation",
            ):
                # Phase 235.x-STABILITY-9 stage 3 2026-05-17: compute_report makes
                # 10+ sync SQLite queries on the event loop. Wrap in to_thread.
                # insert_protocol_intelligence_report is single-row sync write —
                # quick enough to keep on the main loop after to_thread returns.
                report = await asyncio.to_thread(self.compute_report)
                self._store.insert_protocol_intelligence_report(report)
            log.info(
                "ProtocolIntelligenceAgent: score=%.1f ready=%s bottleneck=%s",
                report["protocol_health_score"],
                report["ready_for_live_mode"],
                report["bottleneck"],
            )
            if self._bus is not None:
                try:
                    import asyncio as _asyncio
                    _asyncio.ensure_future(self._bus.publish(
                        "protocol_intelligence_ready",
                        {
                            "protocol_health_score": report["protocol_health_score"],
                            "ready_for_live_mode": report["ready_for_live_mode"],
                            "bottleneck": report["bottleneck"],
                        },
                        "protocol_intelligence_agent",
                    ))
                except Exception as _bus_exc:
                    log.debug("ProtocolIntelligenceAgent: bus publish failed: %s", _bus_exc)
            return report
        except Exception as exc:
            log.warning("ProtocolIntelligenceAgent: compute failed: %s", exc)
            return {}

    def compute_report(self) -> dict:
        """Synchronously compute the full protocol intelligence report. Used by tests + REST."""
        gate_n = self._gate_n

        # Component 1: Gate Progress
        # Phase 239 fix 2026-05-06: chain_length is the cumulative GIC_N
        # milestone semantic; consecutive_clean is the leading-streak signal
        # that breaks on PCC DISCONNECT. Use max(consecutive_clean, chain_length)
        # so the score reflects either (live streak) OR (cumulative achievement).
        # Mirrors the preflight gate_ok fix (commit 5c7dff73).
        summary = self._store.get_validation_summary(gate_n, self._max_rate)
        consecutive_clean = int(summary.get("consecutive_clean", 0))
        gate_passed = bool(summary.get("gate_passed", False))
        chain_length = 0
        try:
            _grind_sid = str(getattr(self._cfg, "grind_session_id", "") or "")
            if _grind_sid:
                _chain = self._store.get_grind_chain_status(_grind_sid, cfg=self._cfg) or {}
                chain_length = int(_chain.get("chain_length", 0))
        except Exception:
            chain_length = 0
        progress_count = max(consecutive_clean, chain_length)
        gate_progress_score = min(1.0, progress_count / max(1, gate_n))
        if not gate_passed and chain_length >= gate_n:
            gate_passed = True

        # Component 2: Fleet Health
        # Phase 239 G2.1 fix 2026-05-06: aggregate only over CORE_AGENTS, not
        # the full agent fleet. Pre-fix-3 code read non-existent 'fleet_health'
        # column. Fix-3 aggregated all 10 tracked agents, including config-
        # disabled (federation_broadcast_enabled=False) + chain-submission-
        # gated (ruling_enforcement, ruling_provenance_anchor — silent when
        # CHAIN_SUBMISSION_PAUSED=true) + ceremony-driven (ceremony_watchdog
        # — idle by design unless ceremony in progress). UNKNOWN/STALE of
        # those agents does NOT mean fleet unhealthy — they're expected-
        # quiet under their respective conditions. Aggregating over them
        # locked fleet_health=UNKNOWN regardless of actual core-agent state.
        #
        # Phase 239 G2.1: aggregate only over CORE_AGENTS — the on-demand
        # adjudication-layer agents that should always be reachable. For
        # these, STALE means "fired in the past, currently idle" which is
        # the EXPECTED state outside active grind windows. UNKNOWN of a
        # core agent (never fired) IS a real concern.
        #
        # Mirrors the _CORE_AGENTS concept already present in
        # agent_supervisor.py:40 — extends it to PIA aggregation.
        CORE_AGENTS = frozenset({
            "session_adjudicator",
            "session_adjudicator_validator",
        })
        fleet_health = "UNKNOWN"
        try:
            health_rows = self._store.get_latest_supervisor_health() or []
            core_states = [
                (r.get("health") or "").upper()
                for r in health_rows
                if r.get("agent_name") in CORE_AGENTS
            ]
            if core_states:
                # Both HEALTHY and STALE count as "has activity" — STALE is
                # expected idle for on-demand adjudication agents.
                active = sum(1 for s in core_states if s in ("HEALTHY", "STALE"))
                total = len(core_states)
                if active == total:
                    fleet_health = "ALL_HEALTHY"
                elif active * 2 >= total:
                    fleet_health = "DEGRADED"
                # else: keep "UNKNOWN" (fail-closed when most cores never fired)
        except Exception:
            pass  # fail-open: M-1 cleanup 2026-05-16 — intentional silent skip
        fleet_health_score = {"ALL_HEALTHY": 1.0, "DEGRADED": 0.5}.get(fleet_health, 0.0)

        # Component 3: Divergence Clarity
        # 1 - (unexplained_divergences / total_divergences)
        # unexplained = divergence=1 AND (divergence_reason IS NULL OR divergence_reason='{}')
        divergence_clarity_score = 1.0
        try:
            with self._store._conn() as conn:
                drow = conn.execute(
                    "SELECT "
                    "SUM(CASE WHEN divergence=1 THEN 1 ELSE 0 END) as diverged, "
                    "SUM(CASE WHEN divergence=1 AND "
                    "(divergence_reason IS NULL OR divergence_reason='{}') "
                    "THEN 1 ELSE 0 END) as unexplained "
                    "FROM ruling_validation_log"
                ).fetchone()
                if drow and int(drow["diverged"] or 0) > 0:
                    unexplained = int(drow["unexplained"] or 0)
                    diverged = int(drow["diverged"])
                    divergence_clarity_score = 1.0 - (unexplained / diverged)
        except Exception:
            pass  # fail-open: M-1 cleanup 2026-05-16 — intentional silent skip

        # Component 4: Corpus Pass Score (0.5 neutral if no corpus runs)
        corpus_pass_score = 0.5
        try:
            corpus = self._store.get_corpus_status()
            total = int(corpus.get("total", 0))
            if total > 0:
                passed = int(corpus.get("passed", 0))
                corpus_pass_score = passed / total
        except Exception:
            pass  # fail-open: M-1 cleanup 2026-05-16 — intentional silent skip

        # Component 5: Class J Confidence (0.5 neutral if no assessments)
        class_j_confidence_score = 0.5
        try:
            with self._store._conn() as conn:
                jrow = conn.execute(
                    "SELECT COUNT(*) as total, "
                    "SUM(CASE WHEN risk_level='LOW' THEN 1 ELSE 0 END) as low_count "
                    "FROM (SELECT device_id, risk_level FROM class_j_assessments "
                    "GROUP BY device_id HAVING MAX(assessed_at))"
                ).fetchone()
                if jrow and int(jrow["total"] or 0) > 0:
                    low_count = int(jrow["low_count"] or 0)
                    class_j_confidence_score = low_count / int(jrow["total"])
        except Exception:
            pass  # fail-open: M-1 cleanup 2026-05-16 — intentional silent skip

        # Phase 90 bonus: Shadow Pass Score
        shadow_pass_score = None
        try:
            with self._store._conn() as conn:
                srow = conn.execute(
                    "SELECT COUNT(*) as total, "
                    "SUM(CASE WHEN would_have_suspended=0 THEN 1 ELSE 0 END) as passed "
                    "FROM shadow_enforcement_log"
                ).fetchone()
                if srow and int(srow["total"] or 0) > 0:
                    shadow_pass_score = int(srow["passed"] or 0) / int(srow["total"])
        except Exception:
            pass  # Phase 90 table not yet migrated; fail-open: M-1 cleanup 2026-05-16

        # Phase 91 bonus: Triage Confidence Score
        triage_confidence_score = None
        try:
            with self._store._conn() as conn:
                trow = conn.execute(
                    "SELECT COUNT(DISTINCT device_id) as total, "
                    "SUM(CASE WHEN escalated=0 THEN 1 ELSE 0 END) as clean "
                    "FROM divergence_triage_reports"
                ).fetchone()
                if trow and int(trow["total"] or 0) > 0:
                    triage_confidence_score = int(trow["clean"] or 0) / int(trow["total"])
        except Exception:
            pass  # Phase 91 table not yet migrated; fail-open: M-1 cleanup 2026-05-16

        # Compute Score
        base_score = (
            0.35 * gate_progress_score
            + 0.25 * fleet_health_score
            + 0.20 * divergence_clarity_score
            + 0.10 * corpus_pass_score
            + 0.10 * class_j_confidence_score
        )
        bonus = 0.0
        if shadow_pass_score is not None:
            bonus += 0.05 * shadow_pass_score
        if triage_confidence_score is not None:
            bonus += 0.05 * triage_confidence_score
        protocol_health_score = round(min(100.0, (base_score + bonus) * 100), 1)

        # Bottleneck — lowest-contributing component
        components = {
            "gate_progress": round(0.35 * gate_progress_score * 100, 1),
            "fleet_health": round(0.25 * fleet_health_score * 100, 1),
            "divergence_clarity": round(0.20 * divergence_clarity_score * 100, 1),
            "corpus_pass": round(0.10 * corpus_pass_score * 100, 1),
            "class_j_confidence": round(0.10 * class_j_confidence_score * 100, 1),
        }
        if shadow_pass_score is not None:
            components["shadow_pass"] = round(0.05 * shadow_pass_score * 100, 1)
        if triage_confidence_score is not None:
            components["triage_confidence"] = round(0.05 * triage_confidence_score * 100, 1)
        bottleneck = min(components, key=components.get)

        # Estimated days to gate (session velocity)
        estimated_days_to_gate = None
        try:
            with self._store._conn() as conn:
                vrow = conn.execute(
                    "SELECT COUNT(*) as count, MIN(created_at) as first, MAX(created_at) as last "
                    "FROM ruling_validation_log"
                ).fetchone()
                if vrow:
                    count = int(vrow["count"] or 0)
                    first_ts = vrow["first"]
                    last_ts = vrow["last"]
                    if count >= 2 and first_ts and last_ts:
                        span_days = (float(last_ts) - float(first_ts)) / 86400.0
                        if span_days > 0:
                            sessions_per_day = count / span_days
                            remaining = max(0, gate_n - consecutive_clean)
                            if sessions_per_day > 0:
                                estimated_days_to_gate = round(remaining / sessions_per_day, 1)
        except Exception:
            pass  # fail-open: M-1 cleanup 2026-05-16 — intentional silent skip

        # Ready for live mode
        ready_for_live_mode = (
            protocol_health_score >= 85.0
            and gate_passed
            and fleet_health not in ("CRITICAL", "UNKNOWN")
        )

        # Recommendation
        if ready_for_live_mode:
            recommendation = (
                f"Protocol health {protocol_health_score}/100 — all conditions met. "
                "Set AGENT_DRY_RUN=false via POST /agent/config to activate live enforcement."
            )
        elif not gate_passed:
            remaining = max(0, gate_n - consecutive_clean)
            day_str = (
                f" (~{estimated_days_to_gate:.0f} days at current velocity)"
                if estimated_days_to_gate else ""
            )
            recommendation = (
                f"Gate not yet passed: {consecutive_clean}/{gate_n} consecutive clean "
                f"({remaining} remaining{day_str}). Bottleneck: {bottleneck}."
            )
        else:
            recommendation = (
                f"Protocol health {protocol_health_score}/100. "
                f"Bottleneck: {bottleneck} ({components[bottleneck]:.1f}/max). "
                f"Fleet: {fleet_health}."
            )

        return {
            "protocol_health_score": protocol_health_score,
            "ready_for_live_mode": ready_for_live_mode,
            "gate_passed": gate_passed,
            "consecutive_clean": consecutive_clean,
            "gate_n": gate_n,
            "fleet_health": fleet_health,
            "components": components,
            "bottleneck": bottleneck,
            "estimated_days_to_gate": estimated_days_to_gate,
            "recommendation": recommendation,
            "components_json": json.dumps(components),
            "created_at": time.time(),
        }
