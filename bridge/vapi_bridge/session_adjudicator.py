"""Phase 65/82 — SessionAdjudicator: autonomous ruling background agent.

Phase 82 adds Reactive Adjudication Interrupt:
  Subscribes to class_j_high_risk_detected on AgentMessageBus.
  Fires immediate out-of-cycle LLM ruling, bypassing the 5-min poll cycle.
  Token bucket (max 2 calls/60s) mitigates bus-flooding DoS (W1 mitigation).
  Publishes reactive_ruling_completed to bus after each triggered ruling.
"""

import asyncio
import hashlib
import json
import logging
import struct
import time

log = logging.getLogger(__name__)

_ADJUDICATOR_MODEL = "claude-opus-4-6"
_POLL_INTERVAL_S = 300  # 5 minutes

# Phase 73: ceremony integrity cache — keyed by circuit_name, expires after 1h.
# Prevents a blocking eth_call per device per cycle (W1 mitigation).
_CEREMONY_CACHE: dict[str, tuple[float, dict]] = {}
_CEREMONY_CACHE_TTL_S = 3600  # 1 hour

_PITL_CIRCUIT_NAME = "PitlSessionProof"  # Phase 67 registered circuit


class _ReactiveAdjudicationBucket:
    """Phase 82: Token bucket — max N LLM calls per window_seconds.

    W1 mitigation: prevents a class_j_high_risk_detected bus flood from exhausting
    the Anthropic rate limit. consume() returns True and decrements on success;
    returns False (deferred) once the bucket is empty for the current window.
    The window resets on the next call after window_seconds have elapsed.
    """

    def __init__(self, max_calls: int = 2, window_seconds: float = 60.0) -> None:
        self._max = max_calls
        self._win = window_seconds
        self._calls = 0
        self._window_start = 0.0

    def consume(self) -> bool:
        now = time.time()
        if now - self._window_start > self._win:
            self._calls = 0
            self._window_start = now
        if self._calls < self._max:
            self._calls += 1
            return True
        return False


class _TriageRateBucket:
    """Phase 94: Per-device token bucket for triage reactive rate limiting (1/hour default).

    W1 mitigation: prevents DivergenceTriageAgent bus floods from triggering
    unlimited reactive adjudications per device. consume() returns True if the
    device is eligible for a reactive ruling in the current window.
    """

    def __init__(self, max_tokens: int = 1, window_s: float = 3600.0) -> None:
        self._max = max_tokens
        self._window = window_s
        self._tokens = max_tokens
        self._last_reset = time.monotonic()

    def consume(self) -> bool:
        now = time.monotonic()
        if now - self._last_reset >= self._window:
            self._tokens = self._max
            self._last_reset = now
        if self._tokens > 0:
            self._tokens -= 1
            return True
        return False


_SYSTEM_PROMPT = """You are the VAPI SessionAdjudicator — an autonomous anti-cheat ruling agent at Phase 200.
You receive structured PITL session evidence and produce a JSON ruling with:
  verdict: one of FLAG | HOLD | BLOCK | CERTIFY | CLEAR
  confidence: float 0.0-1.0
  reasoning: concise explanation (1-3 sentences)

CURRENT PROTOCOL STATE (Phase 200):
- Separation ratio: 0.728 (N=35, touchpad_corners) — TOURNAMENT BLOCKER (target=1.0)
- ALL_PAIRS_GATE_ENABLED=false (prototype mode; per-pair P0 gate bypassed)
- tremor_peak_hz: P1=9.37Hz, P2=1.71Hz, P3=2.85Hz
- ioSwarm: ENABLED emulator mode (BLOCK_QUORUM=0.67, MINT_QUORUM=0.80)
- 36 active agents, 149 tools, 43 contracts LIVE on IoTeX Testnet
- dry_run=True — rulings are advisory until N≥100 validated live adjudications

RULING RULES:
- Hard cheats {0x28 DRIVER_INJECT, 0x29 WALLHACK, 0x2A AIMBOT} → BLOCK (confidence ≥ 0.9)
- Advisory codes {0x2B TEMPORAL_BOT, 0x30 BIOMETRIC_ANOMALY, 0x31 IMU_PRESS_DECOUPLED,
  0x32 STICK_IMU_DECOUPLED} → FLAG (confidence 0.4–0.7)
- Enrollment 'eligible' + no hard cheats + dry_run=True → CERTIFY (confidence 0.85, advisory)
- risk_label 'critical' + no hard cheats → HOLD (confidence 0.75)
- ioSwarm quorum BLOCK (≥0.67 nodes) corroborates → escalate confidence by +0.10
- biometric_ttl_ok=False → add TTL expiry warning to reasoning
- all_pairs_p0_ok=False (prototype mode active) → note prototype mode in reasoning only
- Epistemic consensus threshold=0.65 (Phase 147 hardened); ClassJ+Supervisor alone cannot reach gate
- No signals → FLAG (confidence 0.05) "No anomalies detected"

FROZEN INVARIANTS (never suggest changing):
- PoAC: 228 bytes, SHA-256(raw[0:164]), ECDSA-P256 at offset 164
- L4 thresholds: anomaly=7.009, continuity=5.367 (Phase 57, N=74)
- BLOCK_QUORUM=0.67, MINT_QUORUM=0.80 — never lower
- L6_CHALLENGES_ENABLED=false, GSR_ENABLED=false, L6B_ENABLED=false

Respond with only valid JSON. No markdown. No explanations outside the JSON."""


class SessionAdjudicator:
    """Autonomous session adjudication background agent (Phase 65).

    Polls agent_events for 'ruling_request' events every 5 minutes.
    Synthesizes rulings via claude-opus-4-6 with PITL evidence context.
    Stores rulings in agent_rulings table. Writes reply events to bridge_agent.
    Fails gracefully — all exceptions caught, logged, never crash the bridge.
    """

    def __init__(self, cfg, store, bus=None) -> None:
        self._cfg = cfg
        self._store = store
        self._bus = bus
        # Phase 82: token bucket for reactive LLM calls (rate limit from config or default 2/60s)
        _max = int(getattr(cfg, "reactive_adjudication_rate_limit", 2))
        _win = float(getattr(cfg, "reactive_adjudication_window_seconds", 60))
        self._reactive_bucket = _ReactiveAdjudicationBucket(_max, _win)
        # Phase 94: per-device triage rate buckets (1/hour default, capped at 1000 entries)
        self._triage_buckets: dict[str, _TriageRateBucket] = {}
        self._triage_bucket_max = int(getattr(cfg, "triage_reactive_rate_limit", 1))
        self._triage_bucket_window = float(getattr(cfg, "triage_reactive_window_seconds", 3600.0))
        self._triage_buckets_maxlen = 1000

    async def run_event_consumer(self) -> None:
        """Background loop: poll every 5 minutes for ruling_request events."""
        log.info("SessionAdjudicator started (Phase 65/82) poll=%ds", _POLL_INTERVAL_S)
        if self._bus is not None:
            import asyncio as _asyncio
            # Phase 79: subscribe to ceremony_key_rotated for cache invalidation
            _asyncio.ensure_future(self._listen_ceremony_bus())
            # Phase 82: subscribe to class_j_high_risk_detected for reactive interrupt
            _asyncio.ensure_future(self._listen_class_j_bus())
            # Phase 94: subscribe to divergence_pattern_detected for triage reactive loop
            _asyncio.ensure_future(self._listen_triage_bus())
            # Phase 97: subscribe to live_mode_enabled for fleet-wide mode shift
            _asyncio.ensure_future(self._listen_live_mode_bus())
        _consecutive_failures = 0
        while True:
            try:
                await asyncio.sleep(_POLL_INTERVAL_S)
                await self._consume_pending_events()
                _consecutive_failures = 0
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                _consecutive_failures += 1
                if _consecutive_failures >= 3:
                    log.error(
                        "SessionAdjudicator: %d consecutive failures: %s",
                        _consecutive_failures, exc,
                    )
                else:
                    log.warning("SessionAdjudicator: cycle error: %s", exc)

    async def _consume_pending_events(self) -> None:
        events = self._store.read_unconsumed_events("session_adjudicator", limit=20)
        if not events:
            return
        log.info("SessionAdjudicator: processing %d ruling_request(s)", len(events))
        for event in events:
            if event.get("event_type") != "ruling_request":
                continue
            try:
                await self._process_ruling_request(event)
            except Exception as exc:
                log.warning("SessionAdjudicator: ruling failed for event %s: %s",
                            event.get("id"), exc)

    async def _process_ruling_request(self, event: dict) -> None:
        payload = json.loads(event.get("payload_json", "{}"))
        device_id = payload.get("device_id", "")
        att_hash = payload.get("attestation_hash", "")
        if not device_id:
            return

        # Gather evidence (sync store calls — acceptable in async context here)
        enrollment = self._store.get_enrollment(device_id) or {}
        trajectory = self._store.get_device_risk_label(device_id) or {}
        records = self._store.get_recent_records(limit=20, device_id=device_id)
        l6b = self._store.get_l6b_baseline(device_id)

        # Build evidence summary
        inference_codes = [r.get("inference") for r in records
                           if r.get("inference") is not None]
        hard_cheats = [c for c in inference_codes if c in (0x28, 0x29, 0x2A)]
        advisories = [c for c in inference_codes if c in (0x2B, 0x30, 0x31, 0x32)]
        evidence_hashes = [r.get("record_hash", "") for r in records]

        # Phase 235-GAD: count trigger-active records in evidence window
        _trigger_active_count = sum(1 for r in records if int(r.get("trigger_active", 0) or 0) == 1)
        _trigger_active_fraction = (
            _trigger_active_count / len(records) if records else 0.0
        )

        evidence_summary = {
            "device_id": device_id,
            "hard_cheat_codes": hard_cheats,
            "advisory_codes": advisories,
            "record_count": len(records),
            "enrollment_status": enrollment.get("status", "unknown"),
            "avg_humanity": enrollment.get("avg_humanity", 0.0),
            "risk_label": trajectory.get("risk_label", "unknown"),
            "l6b_probes": l6b.get("probe_count", 0),
            "trigger_active_count": _trigger_active_count,
            "trigger_active_fraction": round(_trigger_active_fraction, 4),
        }

        # Phase 73: ceremony integrity enrichment (cached per circuit, 1h TTL)
        ceremony_data = await self._get_ceremony_integrity()
        if ceremony_data.get("error"):
            log.debug("SessionAdjudicator: ceremony registry unreachable: %s",
                      ceremony_data["error"])
        elif not ceremony_data.get("on_chain_match"):
            evidence_summary["ceremony_integrity_failed"] = True
            log.warning(
                "SessionAdjudicator: ceremony integrity mismatch for device=%s",
                device_id[:12],
            )

        # Phase 81: Class J ML-bot risk enrichment
        class_j = await self._assess_class_j_risk(device_id)
        evidence_summary["class_j_ml_bot_risk"] = class_j["risk_level"]
        evidence_summary["class_j_entropy_variance"] = class_j["entropy_variance"]
        if class_j["risk_level"] == "HIGH":
            evidence_summary["ml_bot_candidate"] = True

        # Phase 99B: GSR physiological enrichment (advisory only, guarded by gsr_enabled)
        if getattr(self._cfg, "gsr_enabled", False):
            gsr_risk = await self._assess_gsr_risk(device_id)
            evidence_summary["gsr_sympathetic_arousal"] = gsr_risk.get("arousal_index", 0.0)
            evidence_summary["gsr_game_correlation"] = gsr_risk.get("correlation", 0.0)
            if gsr_risk.get("correlation", 1.0) < 0.1:
                evidence_summary["gsr_correlation_absent"] = True
                # Advisory inference code 0x33 — LLM sees this, never hard gate

        # LLM ruling
        verdict, confidence, reasoning = await self._llm_ruling(evidence_summary)

        # Phase 98: Epistemic consensus gate — BLOCK requires multi-agent agreement
        verdict = await self._epistemic_consensus(device_id, verdict)

        # Commitment hash
        ts_ns = time.time_ns()
        blob = (
            verdict.encode()
            + json.dumps(sorted(evidence_hashes)).encode()
            + att_hash.encode()
            + struct.pack(">Q", ts_ns)
        )
        commitment_hash = hashlib.sha256(blob).hexdigest()

        # Phase 68-C: dry_run respects AGENT_DRY_RUN config (default True = advisory only)
        dry_run = getattr(self._cfg, "agent_dry_run_mode", True)
        ruling_id = self._store.insert_agent_ruling(
            device_id=device_id,
            verdict=verdict,
            confidence=confidence,
            reasoning=reasoning,
            evidence_json=json.dumps(evidence_summary),
            commitment_hash=commitment_hash,
            attestation_hash=att_hash,
            dry_run=dry_run,
            source_agent="session_adjudicator",
            ceremony_integrity=json.dumps(ceremony_data),
        )
        self._store.mark_event_consumed(event["id"], "session_adjudicator")
        self._store.write_agent_event(
            event_type="ruling_completed",
            payload=json.dumps({"device_id": device_id, "verdict": verdict,
                                "ruling_id": ruling_id}),
            source="session_adjudicator",
            target="bridge_agent",
            device_id=device_id,
        )
        # Phase 66: also emit to RulingEnforcementAgent for streak escalation + on-chain
        self._store.write_agent_event(
            event_type="ruling_completed",
            payload=json.dumps({"device_id": device_id, "verdict": verdict,
                                "ruling_id": ruling_id}),
            source="session_adjudicator",
            target="ruling_enforcement_agent",
            device_id=device_id,
        )
        log.info("SessionAdjudicator: ruling %s -> %s (%.2f) for %s",
                 ruling_id, verdict, confidence, device_id[:12])

        # Phase 134: trigger async separation snapshot after each live session
        if getattr(self._cfg, "auto_separation_snapshot_enabled", False):
            import asyncio as _aio
            _aio.ensure_future(
                _async_write_separation_snapshot(self._cfg, self._store)
            )

    async def _listen_ceremony_bus(self) -> None:
        """Phase 79 — Subscribe to ceremony_key_rotated bus events and clear own cache.

        Replaces the fragile _sa_mod._CEREMONY_CACHE.clear() call in CeremonyWatchdogAgent.
        Runs as a background task for the lifetime of this agent.
        """
        if self._bus is None:
            return
        try:
            queue = await self._bus.subscribe("ceremony_key_rotated")
            log.info("SessionAdjudicator: subscribed to ceremony_key_rotated (Phase 79)")
            while True:
                try:
                    await asyncio.wait_for(queue.get(), timeout=300.0)
                    _CEREMONY_CACHE.clear()
                    log.info("SessionAdjudicator: _CEREMONY_CACHE cleared via bus event")
                except asyncio.TimeoutError:
                    pass  # Normal — no rotation in this window
                except asyncio.CancelledError:
                    raise
                except Exception as exc:
                    log.warning("SessionAdjudicator: _listen_ceremony_bus error: %s", exc)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            log.warning("SessionAdjudicator: _listen_ceremony_bus setup failed: %s", exc)

    async def _assess_class_j_risk(self, device_id: str) -> dict:
        """Phase 81 — Get Class J ML-bot risk assessment for device. Never raises."""
        try:
            assessment = self._store.get_class_j_assessment(device_id)
            if assessment:
                return {
                    "risk_level": assessment.get("risk_level", "LOW"),
                    "entropy_variance": assessment.get("entropy_variance", 0.0),
                    "window_count": assessment.get("window_count", 0),
                }
        except Exception as exc:
            log.debug("SessionAdjudicator: _assess_class_j_risk failed: %s", exc)
        return {"risk_level": "LOW", "entropy_variance": 0.0, "window_count": 0}

    async def _assess_gsr_risk(self, device_id: str) -> dict:
        """Phase 99B — Get latest GSR assessment for device. Never raises.

        Returns dict with arousal_index (0.0–1.0) and correlation (-1.0–1.0).
        Returns empty dict when no GSR samples are available for the device.
        Only called when cfg.gsr_enabled=True — advisory layer only.
        """
        try:
            samples = self._store.get_gsr_samples(device_id, limit=1)
            if not samples:
                return {}
            s = samples[0]
            return {
                "arousal_index": s.get("arousal_index", 0.0),
                "correlation": s.get("correlation", 0.0),
            }
        except Exception as exc:
            log.warning("SessionAdjudicator: _assess_gsr_risk failed: %s — returning empty", exc)
            return {}

    async def _epistemic_consensus(
        self, device_id: str, proposed_verdict: str, ruling_id: int | None = None
    ) -> str:
        """Phase 98 — Multi-agent weighted consensus before irreversible BLOCK enforcement.

        Only fires when proposed_verdict == "BLOCK" AND epistemic_consensus_enabled=True.
        For all other verdicts (CERTIFY, FLAG, HOLD), returns the verdict unchanged.

        Weighted scoring:
          ClassJDetector    0.40  — ML-bot risk (HIGH=1.0, MEDIUM=0.5, LOW=0.0)
          DivergenceTriageAgent 0.40 — triage escalated signal (escalated=1.0)
          AgentSupervisor   0.20  — fleet health (ALL_HEALTHY=1.0, DEGRADED=0.5, CRITICAL=0.0)

        If consensus_score < threshold (default 0.60): BLOCK → HOLD.
        All consensus decisions persisted to epistemic_consensus_log. Never raises.
        """
        if proposed_verdict != "BLOCK":
            return proposed_verdict
        if not getattr(self._cfg, "epistemic_consensus_enabled", True):
            return proposed_verdict

        # Phase 104/105 synergy: PMI>=1 auto-raises to recommended threshold (W2 mitigation)
        base_threshold  = float(getattr(self._cfg, "epistemic_consensus_threshold", 0.60))
        recommended     = float(getattr(self._cfg, "epistemic_recommended_threshold", 0.65))
        try:
            pmi = self._store.compute_pmi()
        except Exception:
            pmi = 0
        threshold = recommended if (pmi >= 1 and recommended > base_threshold) else base_threshold

        # Phase 105 W1 mitigation: triage_prereq_required guard (opt-in)
        triage_prereq = bool(getattr(self._cfg, "epistemic_triage_prereq_required", False))

        class_j_score = 0.0
        triage_score = 0.0
        supervisor_score = 1.0  # default optimistic

        # Phase 109C: safe defaults for adjudication coordinator inputs
        _entropy_variance = 0.16    # Default LOW (no risk) — above 0.15 CLEAR threshold
        _triage_escalated = False   # Phase 109C
        _triage_patterns  = None    # Phase 109C

        try:
            assessment = self._store.get_class_j_assessment(device_id)
            if assessment:
                risk = assessment.get("risk_level", "LOW")
                class_j_score = 1.0 if risk == "HIGH" else (0.5 if risk == "MEDIUM" else 0.0)
                _entropy_variance = assessment.get("entropy_variance", 0.16)  # Phase 109C capture
        except Exception as exc:
            log.debug("SessionAdjudicator: epistemic class_j lookup failed: %s", exc)

        try:
            reports = self._store.get_divergence_triage_report(limit=50)
            # find the latest triage for this device
            for report in reports:
                if report.get("device_id") == device_id and report.get("escalated"):
                    triage_score = 1.0
                    _triage_escalated = True    # Phase 109C capture
                    _triage_patterns  = report.get("patterns")  # Phase 109C capture
                    break
        except Exception as exc:
            log.debug("SessionAdjudicator: epistemic triage lookup failed: %s", exc)

        try:
            health_log = self._store.get_latest_supervisor_health()
            if health_log:
                fh = health_log.get("fleet_health", "UNKNOWN")
                supervisor_score = 1.0 if fh == "ALL_HEALTHY" else (
                    0.5 if fh == "DEGRADED" else 0.0
                )
        except Exception as exc:
            log.debug("SessionAdjudicator: epistemic supervisor lookup failed: %s", exc)

        # Phase 109C: ioSwarm Adjudication Quorum — replaces single-agent ClassJ + Triage verdicts
        # when ioswarm_adjudication_enabled=True.  Fail-open (errors→CLEAR) to avoid false positives.
        _dual_veto = False
        _adj_result = None  # Phase 111: capture for PoAd hash computation (Step D)
        _ioswarm_adj_on = getattr(self._cfg, "ioswarm_adjudication_enabled", False)
        if _ioswarm_adj_on:
            try:
                from .ioswarm_adjudication_coordinator import (
                    IoSwarmAdjudicationCoordinator,
                    DUAL_VETO_SCORE,
                )
                from .ioswarm_live_node_client import IoSwarmLiveNodeClient as _ILNC131a
                _live_client_a = _ILNC131a(cfg=self._cfg, store=self._store)
                _adj_result = IoSwarmAdjudicationCoordinator(
                    cfg=self._cfg, store=self._store, live_client=_live_client_a
                ).evaluate(
                    device_id=device_id,
                    session_id="",
                    entropy_variance=_entropy_variance,
                    escalated=_triage_escalated,
                    triage_patterns=_triage_patterns,
                )
                _cj_qv = _adj_result.get("classj_quorum_verdict", "CLEAR")
                _tr_qv = _adj_result.get("triage_quorum_verdict", "CLEAR")
                # Map quorum verdicts back to epistemic scores
                class_j_score = 1.0 if _cj_qv == "BLOCK" else (0.5 if _cj_qv == "FLAG" else 0.0)
                triage_score  = 1.0 if _tr_qv == "BLOCK" else (0.5 if _tr_qv == "FLAG" else 0.0)
                _dual_veto = _adj_result.get("dual_veto", False)
            except Exception as _exc:
                log.debug("SessionAdjudicator: adjudication coordinator error (fail-open): %s", _exc)

        if triage_prereq and triage_score <= 0.0:
            log.debug(
                "SessionAdjudicator: epistemic triage_prereq not met "
                "(triage_score=%.3f), returning %s unchanged", triage_score, proposed_verdict
            )
            return proposed_verdict

        # Phase 109A: optional 4th ioSwarm signal — backward-compatible
        _ioswarm_on = getattr(self._cfg, "ioswarm_enabled", False)
        swarm_score = await self._assess_ioswarm_score(device_id) if _ioswarm_on else 0.0

        if _ioswarm_on and swarm_score > 0.0:
            # Rebalanced: ClassJ(0.35) + Triage(0.35) + Supervisor(0.15) + Swarm(0.15) = 1.0
            consensus_score = (
                0.35 * class_j_score + 0.35 * triage_score
                + 0.15 * supervisor_score + 0.15 * swarm_score
            )
        else:
            # Phase 98 weights unchanged when ioswarm disabled or no swarm data
            consensus_score = (
                0.40 * class_j_score
                + 0.40 * triage_score
                + 0.20 * supervisor_score
            )

        # Phase 109C W2: dual-quorum veto — score override when BOTH ClassJ AND Triage quorums BLOCK
        # score = max(score, 0.80) > epistemic threshold 0.60 → always drives BLOCK verdict
        if _ioswarm_adj_on and _dual_veto:
            from .ioswarm_adjudication_coordinator import DUAL_VETO_SCORE as _DVS
            consensus_score = max(consensus_score, _DVS)
            log.info(
                "SessionAdjudicator: dual-quorum veto applied (ClassJ+Triage both BLOCK) "
                "device=%s → consensus_score clamped to %.3f",
                device_id[:12], consensus_score,
            )

        # ─── Phase 111 Step D: PoAd hash computation and local registry ──────────────
        _poad_on = getattr(self._cfg, "poad_registry_enabled", False)
        if _ioswarm_adj_on and _poad_on and _adj_result is not None:
            try:
                import hashlib as _hl111, json as _jj111, time as _tt111
                _adj_payload = _jj111.dumps({
                    "classj_verdicts": sorted(
                        _adj_result.get("classj_node_verdicts", []),
                        key=lambda x: x.get("node_id", "")
                    ),
                    "triage_verdicts": sorted(
                        _adj_result.get("triage_node_verdicts", []),
                        key=lambda x: x.get("node_id", "")
                    ),
                    "classj_quorum": _adj_result.get("classj_quorum_verdict", "CLEAR"),
                    "triage_quorum": _adj_result.get("triage_quorum_verdict", "CLEAR"),
                    "ts_ns": int(_tt111.time_ns()),
                }, sort_keys=True)
                _poad_hash = _hl111.sha256(_adj_payload.encode()).hexdigest()
                self._store.insert_poad_registry(
                    device_id=device_id,
                    poad_hash=_poad_hash,
                    dual_veto=_dual_veto,
                    classj_verdict=_adj_result.get("classj_quorum_verdict", "CLEAR"),
                    triage_verdict=_adj_result.get("triage_quorum_verdict", "CLEAR"),
                    ts_ns=int(_tt111.time_ns()),
                )
            except Exception as _poad_exc:
                log.debug(
                    "SessionAdjudicator: PoAd registry error (non-blocking): %s", _poad_exc
                )
        # ─── End Phase 111 Step D ─────────────────────────────────────────────────────

        consensus_reached = consensus_score >= threshold
        final_verdict = "BLOCK" if consensus_reached else "HOLD"
        downgraded = not consensus_reached

        if downgraded:
            log.info(
                "SessionAdjudicator: epistemic consensus DOWNGRADE BLOCK→HOLD "
                "device=%s score=%.2f threshold=%.2f (classJ=%.2f triage=%.2f sup=%.2f swarm=%.2f)",
                device_id[:12], consensus_score, threshold,
                class_j_score, triage_score, supervisor_score, swarm_score,
            )

        try:
            self._store.insert_epistemic_consensus(
                device_id=device_id,
                ruling_id=ruling_id,
                proposed_verdict=proposed_verdict,
                class_j_score=class_j_score,
                triage_score=triage_score,
                supervisor_score=supervisor_score,
                consensus_score=consensus_score,
                threshold=threshold,
                consensus_reached=consensus_reached,
                final_verdict=final_verdict,
                downgraded=downgraded,
                swarm_score=swarm_score,
            )
        except Exception as exc:
            log.warning("SessionAdjudicator: epistemic log write failed: %s", exc)

        return final_verdict

    async def _assess_ioswarm_score(self, device_id: str) -> float:
        """Phase 109A: swarm_verdict_score from latest ioswarm_consensus_log entry.

        Returns 0.0 when ioswarm_enabled=False or no data. Never raises.
        """
        try:
            if not getattr(self._cfg, "ioswarm_enabled", False):
                return 0.0
            rows = self._store.get_ioswarm_consensus_log(device_id=device_id, limit=1)
            return float(rows[0].get("swarm_verdict_score", 0.0)) if rows else 0.0
        except Exception as exc:
            log.debug("_assess_ioswarm_score: %s", exc)
            return 0.0

    async def _get_ceremony_integrity(self) -> dict:
        """Return cached ceremony integrity result for PitlSessionProof circuit.

        Phase 73: calls VAPIZKProof.verify_ceremony_integrity() once per hour
        (TTL cache) to avoid a blocking eth_call per device per adjudication cycle.

        Returns dict with keys: on_chain_match, contributor_count,
        beacon_block_number, error (or None if success).
        Never raises — errors are returned in the 'error' field.
        """
        global _CEREMONY_CACHE
        now = time.time()
        cached_at, cached_result = _CEREMONY_CACHE.get(_PITL_CIRCUIT_NAME, (0.0, {}))
        if now - cached_at < _CEREMONY_CACHE_TTL_S:
            return cached_result

        registry_addr = getattr(self._cfg, "ceremony_registry_address", "")
        rpc_url = getattr(self._cfg, "iotex_rpc_url", "")

        if not registry_addr or not rpc_url:
            result = {"on_chain_match": False, "contributor_count": 0,
                      "beacon_block_number": 0,
                      "error": "ceremony_registry_address or iotex_rpc_url not configured"}
            _CEREMONY_CACHE[_PITL_CIRCUIT_NAME] = (now, result)
            return result

        try:
            from sdk.vapi_sdk import VAPIZKProof
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                lambda: VAPIZKProof.verify_ceremony_integrity(
                    vkey_dict=None,
                    registry_addr=registry_addr,
                    rpc_url=rpc_url,
                    circuit_name=_PITL_CIRCUIT_NAME,
                ),
            )
        except Exception as exc:
            result = {"on_chain_match": False, "contributor_count": 0,
                      "beacon_block_number": 0, "error": str(exc)}

        _CEREMONY_CACHE[_PITL_CIRCUIT_NAME] = (now, result)
        return result

    async def _llm_ruling(self, evidence: dict) -> tuple:
        """Call claude-opus-4-6 to produce (verdict, confidence, reasoning)."""
        try:
            import anthropic
            client = anthropic.AsyncAnthropic()
            response = await client.messages.create(
                model=_ADJUDICATOR_MODEL,
                max_tokens=256,
                system=_SYSTEM_PROMPT,
                messages=[{"role": "user",
                           "content": json.dumps(evidence, default=str)}],
            )
            text = response.content[0].text.strip()
            parsed = json.loads(text)
            return (
                parsed.get("verdict", "FLAG"),
                float(parsed.get("confidence", 0.5)),
                parsed.get("reasoning", ""),
            )
        except Exception as exc:
            log.warning("SessionAdjudicator: LLM unavailable (%s), using rule fallback", exc)
            return self._rule_fallback(evidence)

    @staticmethod
    def _rule_fallback(evidence: dict) -> tuple:
        """Pure rule-based fallback when LLM is unavailable."""
        if evidence.get("hard_cheat_codes"):
            return "BLOCK", 0.9, "Hard cheat code detected (rule fallback - LLM unavailable)."
        if evidence.get("enrollment_status") == "eligible":
            return "CERTIFY", 0.8, "Enrollment threshold met (rule fallback)."
        if evidence.get("risk_label") == "critical":
            return "HOLD", 0.7, "Critical risk trajectory (rule fallback)."
        if evidence.get("advisory_codes"):
            return "FLAG", 0.5, "Advisory detection(s) (rule fallback)."
        return "FLAG", 0.05, "No anomalies detected (rule fallback)."

    # ------------------------------------------------------------------
    # Phase 82 — Reactive Adjudication Interrupt
    # ------------------------------------------------------------------

    async def _listen_class_j_bus(self) -> None:
        """Phase 82 — Subscribe to class_j_high_risk_detected; fire immediate ruling.

        Each HIGH-risk event triggers _reactive_interrupt() if the token bucket
        allows it. Deferred calls are logged to reactive_adjudication_log with
        was_deferred=1 so operators can audit suppressed interrupts.
        Runs as a background task for the lifetime of this agent.
        """
        if self._bus is None:
            return
        try:
            queue = await self._bus.subscribe("class_j_high_risk_detected")
            log.info("SessionAdjudicator: subscribed to class_j_high_risk_detected (Phase 82)")
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=300.0)
                    # Bus wraps in envelope: {event_type, payload, source, ts}
                    envelope = event if isinstance(event, dict) else {}
                    payload = envelope.get("payload", {}) if isinstance(envelope, dict) else {}
                    device_id = payload.get("device_id", "")
                    entropy_variance = float(payload.get("entropy_variance", 0.0))
                    if not device_id:
                        continue
                    if self._reactive_bucket.consume():
                        asyncio.ensure_future(
                            self._reactive_interrupt(device_id, entropy_variance)
                        )
                    else:
                        log.warning(
                            "SessionAdjudicator: reactive bucket exhausted — deferring "
                            "class_j interrupt for device=%s (W1 rate-limit)", device_id[:12],
                        )
                        try:
                            self._store.insert_reactive_adjudication_log(
                                device_id=device_id,
                                triggered_by="class_j_high_risk_detected",
                                entropy_variance=entropy_variance,
                                verdict=None,
                                was_deferred=True,
                            )
                        except Exception:
                            pass
                except asyncio.TimeoutError:
                    pass  # Normal — no Class J events in this window
                except asyncio.CancelledError:
                    raise
                except Exception as exc:
                    log.warning("SessionAdjudicator: _listen_class_j_bus error: %s", exc)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            log.warning("SessionAdjudicator: _listen_class_j_bus setup failed: %s", exc)

    async def _reactive_interrupt(self, device_id: str, entropy_variance: float) -> None:
        """Phase 82 — Out-of-cycle LLM ruling triggered by Class J HIGH risk.

        Calls _adjudicate_device_directly(), logs result to reactive_adjudication_log,
        and publishes reactive_ruling_completed to AgentMessageBus.
        Never raises — all exceptions caught and logged.
        """
        log.info(
            "SessionAdjudicator: reactive interrupt for device=%s entropy_var=%.4f",
            device_id[:12], entropy_variance,
        )
        try:
            verdict, ruling_id = await self._adjudicate_device_directly(
                device_id=device_id,
                entropy_variance=entropy_variance,
                source="reactive_class_j",
            )
            try:
                self._store.insert_reactive_adjudication_log(
                    device_id=device_id,
                    triggered_by="class_j_high_risk_detected",
                    entropy_variance=entropy_variance,
                    verdict=verdict,
                    was_deferred=False,
                )
            except Exception as exc:
                log.debug("SessionAdjudicator: reactive log write failed: %s", exc)
            if self._bus is not None:
                try:
                    await self._bus.publish(
                        "reactive_ruling_completed",
                        {"device_id": device_id, "verdict": verdict,
                         "ruling_id": ruling_id, "source": "reactive_class_j"},
                        source="session_adjudicator",
                    )
                except Exception as exc:
                    log.debug("SessionAdjudicator: bus publish reactive_ruling_completed failed: %s", exc)
        except Exception as exc:
            log.warning("SessionAdjudicator: _reactive_interrupt failed for device=%s: %s",
                        device_id[:12], exc)

    async def _adjudicate_device_directly(
        self, device_id: str, entropy_variance: float = 0.0, source: str = "direct"
    ) -> tuple:
        """Phase 82 — Core ruling synthesis without SQLite event bookkeeping.

        Used by both the reactive interrupt path and (future) warm-up harness.
        Gathers evidence, calls LLM (with rule fallback), commits ruling to store,
        emits ruling_completed to ruling_enforcement_agent.

        Returns (verdict, ruling_id).
        """
        enrollment = self._store.get_enrollment(device_id) or {}
        trajectory = self._store.get_device_risk_label(device_id) or {}
        records = self._store.get_recent_records(limit=20, device_id=device_id)
        l6b = self._store.get_l6b_baseline(device_id)

        inference_codes = [r.get("inference") for r in records
                           if r.get("inference") is not None]
        hard_cheats = [c for c in inference_codes if c in (0x28, 0x29, 0x2A)]
        advisories = [c for c in inference_codes if c in (0x2B, 0x30, 0x31, 0x32)]
        evidence_hashes = [r.get("record_hash", "") for r in records]

        evidence_summary = {
            "device_id": device_id,
            "hard_cheat_codes": hard_cheats,
            "advisory_codes": advisories,
            "record_count": len(records),
            "enrollment_status": enrollment.get("status", "unknown"),
            "avg_humanity": enrollment.get("avg_humanity", 0.0),
            "risk_label": trajectory.get("risk_label", "unknown"),
            "l6b_probes": l6b.get("probe_count", 0) if l6b else 0,
            # Phase 82 reactive context
            "class_j_ml_bot_risk": "HIGH",
            "class_j_entropy_variance": entropy_variance,
            "ml_bot_candidate": True,
            "adjudication_source": source,
        }

        # Ceremony integrity enrichment (cached)
        ceremony_data = await self._get_ceremony_integrity()
        if ceremony_data.get("error"):
            log.debug("SessionAdjudicator: ceremony registry unreachable: %s",
                      ceremony_data["error"])
        elif not ceremony_data.get("on_chain_match"):
            evidence_summary["ceremony_integrity_failed"] = True

        verdict, confidence, reasoning = await self._llm_ruling(evidence_summary)

        # Phase 98: Epistemic consensus gate (direct path — no ruling_id yet)
        verdict = await self._epistemic_consensus(device_id, verdict)

        ts_ns = time.time_ns()
        blob = (
            verdict.encode()
            + json.dumps(sorted(evidence_hashes)).encode()
            + "".encode()  # no single attestation_hash in reactive path
            + struct.pack(">Q", ts_ns)
        )
        commitment_hash = hashlib.sha256(blob).hexdigest()

        dry_run = getattr(self._cfg, "agent_dry_run_mode", True)
        ruling_id = self._store.insert_agent_ruling(
            device_id=device_id,
            verdict=verdict,
            confidence=confidence,
            reasoning=reasoning,
            evidence_json=json.dumps(evidence_summary),
            commitment_hash=commitment_hash,
            attestation_hash="",
            dry_run=dry_run,
            source_agent="session_adjudicator_reactive",
            ceremony_integrity=json.dumps(ceremony_data),
        )
        self._store.write_agent_event(
            event_type="ruling_completed",
            payload=json.dumps({"device_id": device_id, "verdict": verdict,
                                "ruling_id": ruling_id, "source": source}),
            source="session_adjudicator",
            target="ruling_enforcement_agent",
            device_id=device_id,
        )
        log.info(
            "SessionAdjudicator: reactive ruling %s -> %s (%.2f) for %s [%s]",
            ruling_id, verdict, confidence, device_id[:12], source,
        )
        return verdict, ruling_id

    # ------------------------------------------------------------------
    # Phase 94 — Class J Reactive Triage Loop
    # ------------------------------------------------------------------

    def _get_triage_bucket(self, device_id: str) -> "_TriageRateBucket":
        """Return or create a per-device triage rate bucket (Phase 94).

        Caps the buckets dict at _triage_buckets_maxlen to prevent memory
        leaks from synthetic or adversarial device_ids.
        """
        if device_id not in self._triage_buckets:
            if len(self._triage_buckets) >= self._triage_buckets_maxlen:
                # Evict the oldest entry (insertion order in Python 3.7+)
                oldest = next(iter(self._triage_buckets))
                del self._triage_buckets[oldest]
            self._triage_buckets[device_id] = _TriageRateBucket(
                self._triage_bucket_max, self._triage_bucket_window
            )
        return self._triage_buckets[device_id]

    async def _listen_triage_bus(self) -> None:
        """Phase 94 — Subscribe to divergence_pattern_detected bus events.

        Fires a reactive ruling for each escalated device if the per-device
        rate bucket allows it (default 1/hour). Deferred calls are logged to
        escalation_ruling_log with was_deferred=1.
        Runs as a background task for the lifetime of this agent.
        """
        if self._bus is None:
            return
        try:
            queue = await self._bus.subscribe("divergence_pattern_detected")
            log.info(
                "SessionAdjudicator: subscribed to divergence_pattern_detected (Phase 94)"
            )
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=300.0)
                    envelope = event if isinstance(event, dict) else {}
                    payload = envelope.get("payload", {}) if isinstance(envelope, dict) else {}
                    device_id = payload.get("device_id", "")
                    patterns = payload.get("patterns", "")
                    if not device_id:
                        continue
                    bucket = self._get_triage_bucket(device_id)
                    if bucket.consume():
                        asyncio.ensure_future(
                            self._reactive_interrupt_triage(device_id, patterns)
                        )
                    else:
                        log.warning(
                            "SessionAdjudicator: triage bucket exhausted — deferring "
                            "divergence_pattern_detected for device=%s (Phase 94 W1 rate-limit)",
                            device_id[:12],
                        )
                        try:
                            self._store.insert_escalation_ruling_log(
                                device_id=device_id,
                                patterns=patterns,
                                verdict=None,
                                ruling_id=None,
                                was_deferred=True,
                            )
                        except Exception:
                            pass
                except asyncio.TimeoutError:
                    pass  # Normal — no triage events in this window
                except asyncio.CancelledError:
                    raise
                except Exception as exc:
                    log.warning(
                        "SessionAdjudicator: _listen_triage_bus error: %s", exc
                    )
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            log.warning(
                "SessionAdjudicator: _listen_triage_bus setup failed: %s", exc
            )

    async def _listen_live_mode_bus(self) -> None:
        """Phase 97 — Subscribe to live_mode_enabled bus event for fleet-wide mode shift.

        When operator approves live-mode transition via POST /agent/config,
        this listener fires within <1ms and updates cfg.agent_dry_run_mode=False,
        ensuring SessionAdjudicator shifts from advisory to enforcement mode
        without waiting for the next poll cycle. Never raises.
        """
        try:
            queue = await self._bus.subscribe("live_mode_enabled")
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=300.0)
                    payload = event.get("payload", event) if isinstance(event, dict) else {}
                    dry_run_val = payload.get("dry_run", None)
                    if dry_run_val is not None:
                        self._cfg.agent_dry_run_mode = bool(dry_run_val)
                        log.info(
                            "SessionAdjudicator: live_mode_enabled received — "
                            "agent_dry_run_mode=%s (gate_passed=%s cert_valid=%s audit_valid=%s)",
                            bool(dry_run_val),
                            payload.get("gate_passed"),
                            payload.get("cert_valid"),
                            payload.get("audit_valid"),
                        )
                except asyncio.TimeoutError:
                    pass
                except asyncio.CancelledError:
                    raise
                except Exception as exc:
                    log.warning("SessionAdjudicator: _listen_live_mode_bus error: %s", exc)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            log.warning("SessionAdjudicator: _listen_live_mode_bus setup failed: %s", exc)

    async def _reactive_interrupt_triage(self, device_id: str, patterns: str) -> None:
        """Phase 94 — Reactive ruling triggered by triage escalation (divergence_pattern_detected).

        Calls _adjudicate_device_directly(), logs result to escalation_ruling_log.
        Never raises — all exceptions caught and logged.
        """
        log.info(
            "SessionAdjudicator: triage reactive interrupt for device=%s patterns=%s",
            device_id[:12], patterns,
        )
        try:
            verdict, ruling_id = await self._adjudicate_device_directly(
                device_id=device_id,
                entropy_variance=0.0,
                source="reactive_triage",
            )
            try:
                self._store.insert_escalation_ruling_log(
                    device_id=device_id,
                    patterns=patterns,
                    verdict=verdict,
                    ruling_id=ruling_id,
                    was_deferred=False,
                )
            except Exception as exc:
                log.debug(
                    "SessionAdjudicator: escalation_ruling_log write failed: %s", exc
                )
            log.info(
                "SessionAdjudicator: triage ruling %s -> %s for %s",
                ruling_id, verdict, device_id[:12],
            )
        except Exception as exc:
            log.warning(
                "SessionAdjudicator: _reactive_interrupt_triage failed for device=%s: %s",
                device_id[:12], exc,
            )


# ---------------------------------------------------------------------------
# Phase 134 — Live separation snapshot helper (module-level)
# ---------------------------------------------------------------------------

async def _async_write_separation_snapshot(cfg, store) -> None:
    """Run analyze_interperson_separation.py as subprocess after each live session.

    Non-blocking: called via asyncio.ensure_future; never raises; failure logged DEBUG.
    Writes to separation_ratio_snapshots so SeparationRatioMonitorAgent (agent #15) has
    fresh data without requiring a manual analysis run.
    """
    import subprocess
    import sys
    import os
    try:
        script = os.path.join(
            os.path.dirname(__file__), "..", "..", "scripts",
            "analyze_interperson_separation.py"
        )
        db_path = getattr(cfg, "db_path", os.path.expanduser("~/.vapi/bridge.db"))
        cmd = [
            sys.executable, script,
            "--battery-stratified", "--full-covariance",
            "--write-snapshot", "--db", db_path,
        ]
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await asyncio.wait_for(proc.wait(), timeout=120.0)
        log.debug("Phase134: separation snapshot written (exit=%s)", proc.returncode)
    except Exception as exc:
        log.debug("Phase134: separation snapshot subprocess failed: %s", exc)
