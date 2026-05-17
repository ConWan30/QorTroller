"""Phase 75 — SessionAdjudicatorValidationAgent.

Autonomous dry-run gate: cross-validates every SessionAdjudicator LLM ruling
against the deterministic _rule_fallback() engine. Tracks consecutive_clean count.

When consecutive_clean >= cfg.validation_gate_n (default 100) with zero divergences
in that window, emits 'dry_run_gate_passed' agent_event — the operator can then safely
set AGENT_DRY_RUN=false via POST /agent/config.

Divergence criterion: verdicts differ AND |LLM_confidence - fallback_confidence| > threshold.

Design: polls agent_rulings table directly for entries not yet in ruling_validation_log
(LEFT JOIN). No modification to session_adjudicator.py required.

Never raises — all errors logged, agent continues.
"""

import asyncio
import json
import logging
import time

from .active_play_occupancy import (
    active_play_gate_allows,
    classify_active_play_occupancy,
    normalize_active_play_gate_mode,
)

log = logging.getLogger(__name__)

_POLL_INTERVAL_S = 300  # 5 minutes


def _rule_fallback(evidence: dict) -> tuple:
    """Deterministic rule-based verdict (mirrors SessionAdjudicator._rule_fallback).

    This is the validation oracle — it must stay in sync with the source truth in
    session_adjudicator.py. If the rules there change, update here identically.
    """
    if evidence.get("hard_cheat_codes"):
        return "BLOCK", 0.9, "Hard cheat code detected (rule fallback)."
    if evidence.get("enrollment_status") == "eligible":
        return "CERTIFY", 0.8, "Enrollment threshold met (rule fallback)."
    if evidence.get("risk_label") == "critical":
        return "HOLD", 0.7, "Critical risk trajectory (rule fallback)."
    if evidence.get("advisory_codes"):
        return "FLAG", 0.5, "Advisory detection(s) (rule fallback)."
    return "FLAG", 0.05, "No anomalies detected (rule fallback)."


def _extract_divergence_fields(evidence: dict) -> str:
    """Return JSON summary of non-nominal evidence fields that may explain divergence.

    Called only when divergence=True. Captures which evidence signals are non-standard
    so operators can understand why the LLM deviated from _rule_fallback.
    W1 mitigation (Phase 88): without this, divergence reasons are invisible.
    Returns "{}" for fully nominal evidence (expected baseline for real human sessions).
    """
    fields = {}
    if evidence.get("hard_cheat_codes"):
        fields["hard_cheat_codes"] = evidence["hard_cheat_codes"]
    if evidence.get("advisory_codes"):
        fields["advisory_codes"] = evidence["advisory_codes"]
    risk = evidence.get("class_j_ml_bot_risk")
    if risk and risk != "LOW":
        fields["class_j_ml_bot_risk"] = risk
    if evidence.get("ml_bot_candidate"):
        fields["ml_bot_candidate"] = True
    if evidence.get("ceremony_integrity_failed"):
        fields["ceremony_integrity_failed"] = True
    status = evidence.get("enrollment_status")
    if status and status != "eligible":
        fields["enrollment_status"] = status
    if evidence.get("risk_label"):
        fields["risk_label"] = evidence["risk_label"]
    return json.dumps(fields) if fields else "{}"


class SessionAdjudicatorValidationAgent:
    """Cross-validates LLM rulings against rule fallback for dry-run gate (Phase 75).

    Polls agent_rulings every 5 minutes for entries not yet in ruling_validation_log.
    Tracks consecutive_clean toward the validation_gate_n threshold.
    Once threshold is reached with zero divergences, emits dry_run_gate_passed event.
    """

    def __init__(self, cfg, store, bus=None, pcc_monitor=None) -> None:
        self._cfg = cfg
        self._store = store
        self._bus = bus
        self._pcc_monitor = pcc_monitor  # Phase 235-SBD-PCC: live monitor preferred over stale DB log
        self._threshold = float(getattr(cfg, "validation_divergence_threshold", 0.3))
        self._gate_n = int(getattr(cfg, "validation_gate_n", 100))
        self._gate_already_emitted = False

    async def run_event_consumer(self) -> None:
        """Background loop — polls for unvalidated rulings every 5 minutes."""
        log.info(
            "SessionAdjudicatorValidationAgent started (Phase 75) "
            "threshold=%.2f gate_n=%d",
            self._threshold, self._gate_n,
        )
        _consecutive_failures = 0
        while True:
            try:
                await asyncio.sleep(_POLL_INTERVAL_S)
                await self._consume_pending_rulings()
                _consecutive_failures = 0
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                _consecutive_failures += 1
                if _consecutive_failures >= 3:
                    log.error(
                        "SessionAdjudicatorValidationAgent: %d consecutive failures: %s",
                        _consecutive_failures, exc,
                    )
                else:
                    log.warning("SessionAdjudicatorValidationAgent: cycle error: %s", exc)

    async def _consume_pending_rulings(self) -> None:
        """Fetch unvalidated rulings (not yet in ruling_validation_log) and validate each."""
        # Phase 235-BRIDGE-WEDGE-FIX: SQLite open + LEFT JOIN scan must run on
        # a worker thread, not the event loop.  See Store.get_unvalidated_rulings.
        try:
            rows = await asyncio.to_thread(self._store.get_unvalidated_rulings, 50)
        except Exception as exc:
            log.warning("SessionAdjudicatorValidationAgent: query failed: %s", exc)
            return

        if not rows:
            return

        log.info(
            "SessionAdjudicatorValidationAgent: validating %d unvalidated ruling(s)",
            len(rows),
        )
        for row in rows:
            try:
                await self._validate_ruling(dict(row))
            except Exception as exc:
                log.warning(
                    "SessionAdjudicatorValidationAgent: validation error ruling_id=%s: %s",
                    row["id"] if hasattr(row, "__getitem__") else "?", exc,
                )

    async def _validate_ruling(self, row: dict) -> None:
        """Cross-validate one ruling and record in ruling_validation_log."""
        ruling_id = row["id"]
        llm_verdict = row.get("verdict", "FLAG")
        llm_confidence = float(row.get("confidence", 0.5))
        device_id = row.get("device_id", "")

        try:
            evidence = json.loads(row.get("evidence_json") or "{}")
        except (json.JSONDecodeError, TypeError):
            evidence = {}

        fb_verdict, fb_confidence, _ = _rule_fallback(evidence)

        verdicts_differ = llm_verdict != fb_verdict
        delta_conf = abs(llm_confidence - fb_confidence)
        divergence = verdicts_differ and (delta_conf > self._threshold)

        if divergence:
            log.warning(
                "SessionAdjudicatorValidationAgent: DIVERGENCE ruling_id=%d "
                "device=%s llm=%s(%.2f) fallback=%s(%.2f) delta=%.2f",
                ruling_id, device_id[:12],
                llm_verdict, llm_confidence,
                fb_verdict, fb_confidence, delta_conf,
            )
            # Phase 235-BRIDGE-WEDGE-FIX: SQLite write must not run on event loop.
            await asyncio.to_thread(
                self._store.write_agent_event,
                event_type="validation_divergence",
                payload=json.dumps({
                    "ruling_id": ruling_id,
                    "device_id": device_id,
                    "llm_verdict": llm_verdict,
                    "fallback_verdict": fb_verdict,
                    "delta_confidence": round(delta_conf, 4),
                }),
                source="session_adjudicator_validator",
                target="bridge_agent",
                device_id=device_id,
            )

            # Phase 235.x-STABILITY-9 stage 4b 2026-05-17: dual-sink — also
            # publish to in-process bus so DivergenceTriageAgent can subscribe
            # event-driven instead of polling ruling_validation_log every 300s.
            # The DB write above remains the durable audit trail; the bus
            # publish is the live-trigger signal.
            if self._bus is not None:
                try:
                    await self._bus.publish(
                        "validation_divergence",
                        {
                            "ruling_id": ruling_id,
                            "device_id": device_id,
                            "llm_verdict": llm_verdict,
                            "fallback_verdict": fb_verdict,
                            "delta_confidence": round(delta_conf, 4),
                        },
                        source="session_adjudicator_validator",
                    )
                except Exception as _bus_exc:  # noqa: BLE001
                    log.debug("validation_divergence bus publish failed: %s", _bus_exc)

        # Phase 88: extract divergence reason for operator insight (W1 mitigation)
        divergence_reason = (
            _extract_divergence_fields(evidence) if divergence else None
        )

        # Phase 235-B: capture PCC state at adjudication time (fail-closed if unavailable).
        # Phase 235-SBD-PCC: prefer live in-memory monitor over stale SQLite log.
        if self._pcc_monitor is not None:
            _pcc_live = self._pcc_monitor.get_status()
            _pcc_state = _pcc_live.get("capture_state")
            _pcc_host  = _pcc_live.get("host_state")
        else:
            # Phase 235-BRIDGE-WEDGE-FIX: SQLite read off the event loop thread.
            _pcc_snap = await asyncio.to_thread(self._store.get_capture_health_status)
            _pcc_state = _pcc_snap.get("capture_state") if _pcc_snap else None
            _pcc_host = _pcc_snap.get("host_state") if _pcc_snap else None

        # Phase 235-GAD: derive gameplay_context from trigger activity in evidence
        _gameplay_disc = bool(getattr(self._cfg, "gameplay_discrimination_enabled", True))
        _taf = float(evidence.get("trigger_active_fraction", -1.0))
        if _taf < 0.0:
            # evidence missing trigger_active_fraction → pre-GAD row or no records
            _gameplay_ctx = None
        elif _gameplay_disc:
            _gameplay_ctx = "ACTIVE_GAMEPLAY" if _taf > 0.0 else "MENU_DETECTED"
        else:
            _gameplay_ctx = "ACTIVE_GAMEPLAY"  # discrimination disabled → treat as active

        _apop_enabled = bool(getattr(self._cfg, "active_play_occupancy_enabled", True))
        _apop_mode = normalize_active_play_gate_mode(
            getattr(self._cfg, "active_play_occupancy_gate_mode", "shadow")
        )
        _apop_result = None
        if _apop_enabled:
            try:
                _apop_records = await asyncio.to_thread(
                    self._store.get_recent_records, 400, device_id
                )
                # Phase 241-APOP-FIX: time-based query (not per-hash join).
                # In grind_mode, frame_checkpoints are sampled at ~10/sec —
                # per-hash join would miss ~99% of recent records and APOP
                # would always return UNKNOWN_LOW_EVIDENCE.
                _apop_checkpoints = await asyncio.to_thread(
                    self._store.get_recent_frame_checkpoints_for_device,
                    device_id, 30
                )
                _apop_result = classify_active_play_occupancy(
                    _apop_records, _apop_checkpoints
                )
            except Exception as _apop_exc:
                log.warning(
                    "SessionAdjudicatorValidationAgent: APOP classify failed "
                    "ruling_id=%d: %s",
                    ruling_id, _apop_exc,
                )

        # Phase 235-BRIDGE-WEDGE-FIX: SQLite write off the event loop thread.
        _val_row_id = await asyncio.to_thread(
            self._store.insert_validation_record,
            ruling_id=ruling_id,
            device_id=device_id,
            llm_verdict=llm_verdict,
            fallback_verdict=fb_verdict,
            llm_confidence=llm_confidence,
            fallback_confidence=fb_confidence,
            divergence=int(divergence),
            divergence_reason=divergence_reason,
            pcc_state=_pcc_state,
            pcc_host_state=_pcc_host,
            gameplay_context=_gameplay_ctx,
        )
        if _apop_result is not None:
            await asyncio.to_thread(
                self._store.insert_active_play_occupancy_log,
                _val_row_id,
                ruling_id,
                device_id,
                _apop_result.state,
                _apop_result.score,
                _apop_result.confidence,
                _apop_result.evidence_json(),
                _apop_mode,
            )

        # Phase 235-A: compute and stamp GIC for count-eligible sessions
        _grind_mode = bool(getattr(self._cfg, "grind_mode", False))
        # Phase 235-SMOKE-BYPASS: when PCC_SMOKE_BYPASS=true, force BOTH
        # _pcc_eligible=True AND _gameplay_ok=True so chain stamping can be
        # validated end-to-end on hardware where USB enumeration is degraded
        # (PCC) and adjudications are triggered while not actively snapping
        # triggers (gameplay_context=MENU_DETECTED).  SMOKE-ONLY — this
        # disables both the USB-vs-BT discrimination AND the gameplay-vs-menu
        # discrimination which together are the entire reason these layers
        # exist. Must be removed before the real 100-session grind. Logged
        # as WARNING on every stamp so it cannot be silently left enabled.
        _pcc_smoke_bypass = bool(getattr(self._cfg, "pcc_smoke_bypass", False))
        if _pcc_smoke_bypass:
            _pcc_eligible = True
            log.warning(
                "SessionAdjudicatorValidationAgent: PCC_SMOKE_BYPASS=true — "
                "GIC stamp bypassing capture_state/host_state AND "
                "gameplay_context checks. DISABLE before real grind."
            )
        else:
            _pcc_eligible = (
                _pcc_state == "NOMINAL"
                and _pcc_host in ("EXCLUSIVE_USB", "UNKNOWN")
            ) if _pcc_state is not None else False
        # Phase 235-SMOKE-BYPASS: when bypass is on, treat every gameplay
        # context (including MENU_DETECTED) as eligible.  Otherwise the
        # default rule applies: MENU_DETECTED blocks; NULL passes through.
        if _pcc_smoke_bypass:
            _gameplay_ok = True
        elif _apop_enabled:
            _gameplay_ok = active_play_gate_allows(
                _apop_result.state if _apop_result is not None else None,
                _apop_result.confidence if _apop_result is not None else None,
                _gameplay_ctx,
                _apop_mode,
            )
        else:
            _gameplay_ok = _gameplay_ctx != "MENU_DETECTED"
        # INV-GIC-003: skip GIC stamp entirely when chain is broken — do not extend
        # a corrupt chain.  Row will have NULL grind_chain_hash.
        if _grind_mode and getattr(self._store, "_gic_chain_broken", False):
            log.warning(
                "SessionAdjudicatorValidationAgent: GIC chain broken — "
                "skipping GIC stamp ruling_id=%d",
                ruling_id,
            )
        elif _grind_mode and _pcc_eligible and not divergence and _gameplay_ok:
            try:
                from .grind_chain import compute_gic, genesis_gic
                _grind_sid = getattr(self._cfg, "grind_session_id", "grind_unknown")
                _commitment_hash = row.get("commitment_hash") or ("00" * 32)
                # Phase 235-BRIDGE-WEDGE-FIX: SQLite reads / writes off the event loop.
                _prev = await asyncio.to_thread(
                    self._store.get_prev_grind_chain_hash, _grind_sid
                )
                _ts_ns = time.time_ns()
                # Monotonicity guard: GIC ts_ns must be strictly > last stamped ts_ns.
                # Protects against backward NTP corrections creating audit confusion.
                _prev_ts = await asyncio.to_thread(self._store.get_prev_gic_ts_ns)
                if _ts_ns <= _prev_ts:
                    _ts_ns = _prev_ts + 1
                if _prev is None:
                    # Session 1: genesis anchors the chain; compute_gic incorporates session data.
                    # Both steps use the same ts_ns so verification can reconstruct the genesis.
                    _genesis = genesis_gic(_grind_sid, _ts_ns)
                    _gic = compute_gic(_genesis, _commitment_hash, _pcc_host, fb_verdict, _ts_ns)
                else:
                    _gic = compute_gic(_prev, _commitment_hash, _pcc_host, fb_verdict, _ts_ns)
                # INV-GIC-001: pass grind_session_id so the row is scoped to this session.
                await asyncio.to_thread(
                    self._store.update_grind_chain_hash,
                    _val_row_id, _gic.hex(), _ts_ns, _grind_sid,
                )
            except Exception as _gic_exc:
                log.warning(
                    "SessionAdjudicatorValidationAgent: GIC stamp failed ruling_id=%d: %s",
                    ruling_id, _gic_exc,
                )

        # Check gate condition (emit once per bridge lifetime)
        # Phase 78: pass max_divergence_rate so gate logic is consistent with operator_api
        _max_rate = float(getattr(self._cfg, "validation_max_divergence_rate", 1.0))
        if not self._gate_already_emitted:
            # Phase 235-BRIDGE-WEDGE-FIX: SQLite reads / writes off the event loop.
            summary = await asyncio.to_thread(
                self._store.get_validation_summary, self._gate_n, _max_rate,
                _apop_mode if _apop_enabled else "shadow",
            )
            if summary["gate_passed"]:
                self._gate_already_emitted = True
                await asyncio.to_thread(
                    self._store.write_agent_event,
                    event_type="dry_run_gate_passed",
                    payload=json.dumps({
                        "consecutive_clean": summary["consecutive_clean"],
                        "divergence_count": summary["divergence_count"],
                        "gate_n": self._gate_n,
                        "recommendation": (
                            "Set AGENT_DRY_RUN=false via POST /agent/config "
                            "to enable live enforcement."
                        ),
                    }),
                    source="session_adjudicator_validator",
                    target="bridge_agent",
                    device_id="",
                )
                log.info(
                    "SessionAdjudicatorValidationAgent: DRY-RUN GATE PASSED "
                    "consecutive_clean=%d — safe to set AGENT_DRY_RUN=false",
                    summary["consecutive_clean"],
                )
                # Phase 79: also publish to bus for LiveModeActivationAgent
                if self._bus is not None:
                    import asyncio as _asyncio
                    try:
                        _asyncio.ensure_future(self._bus.publish(
                            "dry_run_gate_passed",
                            {
                                "consecutive_clean": summary["consecutive_clean"],
                                "divergence_count": summary["divergence_count"],
                                "gate_n": self._gate_n,
                            },
                            "session_adjudicator_validator",
                        ))
                    except Exception as _bus_exc:
                        log.debug(
                            "SessionAdjudicatorValidationAgent: bus publish failed: %s",
                            _bus_exc,
                        )
