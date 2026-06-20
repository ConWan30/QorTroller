"""Tournament activation / live-mode routes (D-DECON-2 operator_api residue #17).

Register-function split per audits/decon-store-map.md agent_tournament domain.
"""
from __future__ import annotations

import hashlib
import hmac
import json as _json
import logging
import time
from typing import Callable

from fastapi import FastAPI, HTTPException, Query, Request

log = logging.getLogger(__name__)


def register_agent_tournament_routes(
    app: FastAPI,
    *,
    cfg,
    store,
    check_key: Callable[[str], None],
    check_rate: Callable[[str], None],
) -> None:
    """Register live-mode, activation, enforcement cert, and tournament readiness routes."""

    # --- Phase 79: Live mode status ---

    @app.get("/agent/live-mode-status")
    def live_mode_status(
        api_key: str = Query(..., description="Shared operator API key"),
    ):
        """Return live-mode readiness checklist (Phase 79).

        Evaluates 5 conditions for dry-run -> live enforcement transition.
        Returns ready_for_live_mode, conditions dict, blocking_conditions list,
        and recommended_action string. Operator must set AGENT_DRY_RUN=false manually.
        """
        check_key(api_key)
        check_rate(api_key)
        try:
            from ..live_mode_activation_agent import LiveModeActivationAgent
            _lma = LiveModeActivationAgent(cfg, store, bus=None)
            return _lma.get_live_mode_status()
        except Exception as exc:
            log.warning("live_mode_status: %s", exc)
            return {
                "ready_for_live_mode": False,
                "current_dry_run": getattr(cfg, "agent_dry_run_mode", True),
                "conditions": {},
                "blocking_conditions": [],
                "gate_summary": {},
                "recommended_action": f"Error evaluating status: {exc}",
            }

    # --- Phase 92: Live Mode Activation Pipeline ---

    @app.post("/agent/request-activation")
    async def request_activation(
        request: Request,
        api_key: str = Query(..., description="Shared operator API key"),
    ):
        """Record an operator activation request and check protocol readiness.

        Checks Phase 89 ProtocolIntelligenceAgent ready_for_live_mode status,
        records the operator's intent to the activation audit log, and returns
        current readiness status with blocking conditions.
        NEVER auto-activates — operator must still set AGENT_DRY_RUN=false.
        Phase 92.
        """
        check_key(api_key)
        check_rate(api_key)
        try:
            body = await request.json()
        except Exception:
            body = {}
        notes = body.get("notes") if isinstance(body, dict) else None
        try:
            from ..live_mode_activation_pipeline import LiveModeActivationPipeline
            pipeline = LiveModeActivationPipeline(cfg, store)
            result = await pipeline._check_and_record("operator_request", operator_notes=notes)
            result["timestamp"] = time.time()
            return result
        except Exception as exc:
            log.warning("request_activation: failed: %s", exc)
            return {
                "ready_for_live_mode": False,
                "protocol_health_score": 0.0,
                "bottleneck": "error",
                "blocking_conditions": [str(exc)],
                "recommended_action": f"Error: {exc}",
                "timestamp": time.time(),
            }

    @app.get("/agent/activation-log")
    def activation_log(
        api_key: str = Query(..., description="Shared operator API key"),
        limit: int = Query(50, description="Max entries to return"),
    ):
        """Return the live mode activation audit log.

        Contains all readiness_check and operator_request events with their
        protocol_health_score, blocking_conditions, and notes.
        Phase 92.
        """
        check_key(api_key)
        check_rate(api_key)
        try:
            entries = store.get_live_mode_activation_log(limit=limit)
            latest_ready = any(e.get("ready_for_live_mode") for e in entries)
            return {
                "entries": entries,
                "total_returned": len(entries),
                "latest_ready_for_live_mode": latest_ready,
                "timestamp": time.time(),
            }
        except Exception as exc:
            log.warning("activation_log: query failed: %s", exc)
            return {
                "entries": [],
                "total_returned": 0,
                "latest_ready_for_live_mode": False,
                "error": str(exc),
            }

    # --- Phase 94: Escalation Ruling Log ---

    @app.get("/agent/escalation-ruling-log")
    def escalation_ruling_log(
        api_key: str = Query(..., description="Shared operator API key"),
        device_id: str = Query(None, description="Optional device_id filter"),
        limit: int = Query(50, description="Max entries to return"),
    ):
        """Return the escalation ruling log from the Phase 94 triage reactive loop.

        Entries are written when DivergenceTriageAgent escalates a device and
        SessionAdjudicator fires a reactive ruling via the divergence_pattern_detected bus.
        was_deferred=1 entries were rate-limited (1/hour per device by default).
        Phase 94.
        """
        check_key(api_key)
        check_rate(api_key)
        try:
            entries = store.get_escalation_ruling_log(device_id=device_id, limit=limit)
            return {
                "entries": entries,
                "total_returned": len(entries),
                "timestamp": time.time(),
            }
        except Exception as exc:
            log.warning("escalation_ruling_log: query failed: %s", exc)
            return {
                "entries": [],
                "total_returned": 0,
                "error": str(exc),
            }

    # --- Phase 91: Divergence Triage ---

    @app.get("/agent/triage-report")
    def triage_report(
        api_key: str = Query(..., description="Shared operator API key"),
        limit: int = Query(50, description="Max device entries to return"),
    ):
        """Return divergence triage report: per-device adversarial pattern analysis.

        Populated by DivergenceTriageAgent which polls ruling_validation_log for
        diverged sessions with non-nominal divergence_reason (Phase 88 instrumentation).
        Escalated devices have detected ML-bot clusters, cheat codes, or enrollment anomalies.
        Phase 91.
        """
        check_key(api_key)
        check_rate(api_key)
        try:
            entries = store.get_divergence_triage_report(limit=limit)
            escalated_count = sum(1 for e in entries if e.get("escalated"))
            return {
                "entries": entries,
                "total_returned": len(entries),
                "escalated_count": escalated_count,
                "clean_count": len(entries) - escalated_count,
                "timestamp": time.time(),
            }
        except Exception as exc:
            log.warning("triage_report: query failed: %s", exc)
            return {
                "entries": [],
                "total_returned": 0,
                "escalated_count": 0,
                "clean_count": 0,
                "error": str(exc),
            }

    # --- Phase 95: Activation Audit Verifier ---

    @app.get("/agent/activation-audit")
    def activation_audit(
        api_key: str = Query(..., description="Shared operator API key"),
    ):
        """Return tamper-evident activation audit summary.

        Cross-references live_mode_activation_log (Phase 92) with gate_attestations
        (Phase 84/87) to verify that:
        1. The protocol scored ready_for_live_mode=True (protocol_health_score >= 85)
        2. An on-chain gate attestation was subsequently recorded
        3. The chronological order is intact (ready check BEFORE on-chain anchor)

        audit_valid=True is the cryptographic pre-condition for operators enabling
        AGENT_DRY_RUN=false. This endpoint is callable from tournament CI pipelines
        via VAPITournamentGate.verify_activation_audit() (SDK Phase 95).
        Phase 95.
        """
        check_key(api_key)
        check_rate(api_key)
        try:
            summary = store.get_activation_audit_summary()
            return {
                **summary,
                "timestamp": time.time(),
            }
        except Exception as exc:
            log.warning("activation_audit: query failed: %s", exc)
            return {
                "first_ready_check_at": None,
                "gate_attestation_count": 0,
                "latest_attestation_at": None,
                "audit_valid": False,
                "audit_summary": f"Error: {exc}",
                "timestamp": time.time(),
            }

    # --- Phase 96: Enforcement Readiness Certificate ---

    @app.post("/agent/enforcement-certificate")
    def issue_enforcement_certificate(
        api_key: str = Query(..., description="Shared operator API key"),
    ):
        """Issue a portable Enforcement Readiness Certificate (ERC).

        Reads the current activation audit summary, computes:
          audit_hash = SHA-256(canonical JSON of audit fields)
          hmac_sig = HMAC-SHA256(audit_hash, operator_api_key)
        Persists the cert to enforcement_certificates (UNIQUE audit_hash — idempotent).
        Certs expire after enforcement_cert_ttl_s seconds (default 24h).

        Phase 96 novel primitive: First portable, operator-signed cryptographic proof of
        AI enforcement readiness — callable by tournament operators without VAPI infrastructure.
        Phase 96.
        """
        check_key(api_key)
        check_rate(api_key)
        try:
            audit = store.get_activation_audit_summary()
            canonical = _json.dumps({
                "audit_valid": audit["audit_valid"],
                "first_ready_check_at": audit["first_ready_check_at"],
                "gate_attestation_count": audit["gate_attestation_count"],
                "latest_attestation_at": audit["latest_attestation_at"],
            }, sort_keys=True)
            audit_hash = hashlib.sha256(canonical.encode()).hexdigest()
            hmac_sig = hmac.new(
                cfg.operator_api_key.encode(),
                audit_hash.encode(),
                "sha256",
            ).hexdigest()
            now = time.time()
            expires_at = now + float(getattr(cfg, "enforcement_cert_ttl_s", 86400))
            cert_id = store.insert_enforcement_certificate(
                audit_hash=audit_hash,
                hmac_sig=hmac_sig,
                audit_valid=audit["audit_valid"],
                first_ready_check_at=audit["first_ready_check_at"],
                gate_attestation_count=audit["gate_attestation_count"],
                latest_attestation_at=audit["latest_attestation_at"],
                expires_at=expires_at,
            )
            return {
                "cert_id": cert_id,
                "audit_hash": audit_hash,
                "hmac_sig": hmac_sig,
                "audit_valid": audit["audit_valid"],
                "expires_at": expires_at,
                "issued_at": now,
            }
        except Exception as exc:
            log.warning("issue_enforcement_certificate: failed: %s", exc)
            return {"error": str(exc), "cert_id": None, "audit_valid": False}

    @app.get("/agent/enforcement-certificate")
    def get_enforcement_certificate(
        api_key: str = Query(..., description="Shared operator API key"),
    ):
        """Return the latest Enforcement Readiness Certificate.

        Returns the most recently issued ERC, or empty if none issued.
        Expiry is advisory — the operator is responsible for renewal.
        Phase 96.
        """
        check_key(api_key)
        check_rate(api_key)
        try:
            cert = store.get_latest_enforcement_certificate()
            expired = cert is not None and time.time() > cert.get("expires_at", 0)
            return {
                "certificate": cert,
                "has_certificate": cert is not None,
                "is_expired": expired,
                "timestamp": time.time(),
            }
        except Exception as exc:
            log.warning("get_enforcement_certificate: failed: %s", exc)
            return {
                "certificate": None,
                "has_certificate": False,
                "is_expired": False,
                "error": str(exc),
                "timestamp": time.time(),
            }

    @app.get("/agent/live-mode-guard")
    def live_mode_guard_log(
        api_key: str = Query(..., description="Shared operator API key"),
        limit: int = Query(50, description="Max entries to return"),
    ):
        """Return live-mode guard audit log (Phase 97).

        Every attempt to enable live mode (approved or blocked) is recorded here.
        Use this to audit operator actions and diagnose blocking conditions.
        """
        check_key(api_key)
        check_rate(api_key)
        try:
            entries = store.get_live_mode_guard_log(limit=limit)
            return {
                "entries": entries,
                "count": len(entries),
                "current_dry_run": bool(getattr(cfg, "agent_dry_run_mode", True)),
                "timestamp": time.time(),
            }
        except Exception as exc:
            log.warning("live_mode_guard_log: %s", exc)
            return {"entries": [], "count": 0, "error": str(exc), "timestamp": time.time()}
    @app.get("/agent/activation-status")
    def activation_status(
        api_key: str = Query(..., description="Shared operator API key"),
    ):
        """Return 5-step live-mode activation checklist (Phase 100).

        Steps:
          1 consecutive_clean >= gate_n (validation gate)
          2 enforcement cert issued + valid (not expired)
          3 audit_valid=True (chronological invariant)
          4 AGENT_DRY_RUN=false
          5 VHP mint available (all of 1+3+4 pass)
        """
        check_key(api_key)
        check_rate(api_key)

        gate_n = int(getattr(cfg, "validation_gate_n", 100))
        max_rate = float(getattr(cfg, "validation_max_divergence_rate", 1.0))
        dry_run_active = bool(getattr(cfg, "agent_dry_run_mode", True))

        # Step 1 — validation gate
        try:
            summary = store.get_validation_summary(gate_n, max_rate)
        except Exception:
            summary = {"consecutive_clean": 0, "gate_passed": False, "divergence_rate": 0.0}
        consecutive_clean = int(summary.get("consecutive_clean", 0))
        gate_passed = bool(summary.get("gate_passed", False))
        divergence_rate = float(summary.get("divergence_rate", 0.0))
        sessions_remaining = max(0, gate_n - consecutive_clean)
        progress_pct = round(min(100.0, consecutive_clean / gate_n * 100), 1) if gate_n > 0 else 0.0

        step1 = {
            "passed": gate_passed,
            "consecutive_clean": consecutive_clean,
            "gate_n": gate_n,
            "progress_pct": progress_pct,
            "sessions_remaining": sessions_remaining,
            "divergence_rate": divergence_rate,
        }

        # Step 2 — enforcement cert
        try:
            cert = store.get_latest_enforcement_certificate()
        except Exception:
            cert = None
        cert_ttl = float(getattr(cfg, "enforcement_cert_ttl_s", 86400))
        cert_issued = cert is not None
        cert_expired = cert_issued and (time.time() - cert.get("created_at", 0)) > cert_ttl
        cert_valid = cert_issued and not cert_expired
        step2 = {
            "issued": cert_issued,
            "valid": cert_valid,
            "expires_at": (cert.get("created_at", 0) + cert_ttl) if cert_issued else None,
        }

        # Step 3 — activation audit
        try:
            audit = store.get_activation_audit_summary()
        except Exception:
            audit = {"audit_valid": False, "gate_attestation_count": 0, "first_ready_check_at": None}
        audit_valid = bool(audit.get("audit_valid", False))
        step3 = {
            "audit_valid": audit_valid,
            "gate_attestation_count": int(audit.get("gate_attestation_count", 0)),
            "first_ready_check_at": audit.get("first_ready_check_at"),
        }

        # Step 4 — live mode
        live_mode_enabled = not dry_run_active
        step4 = {
            "dry_run_active": dry_run_active,
            "live_mode_enabled": live_mode_enabled,
        }

        # Step 5 — VHP mint ready
        vhp_blocking = []
        if not gate_passed:
            vhp_blocking.append("gate_not_passed")
        if not audit_valid:
            vhp_blocking.append("audit_invalid")
        if dry_run_active:
            vhp_blocking.append("dry_run_active")
        vhp_ready = len(vhp_blocking) == 0
        step5 = {
            "ready": vhp_ready,
            "blocking_conditions": vhp_blocking,
        }

        # Determine current blocking step
        if not gate_passed:
            blocking_step = 1
        elif not cert_valid:
            blocking_step = 2
        elif not audit_valid:
            blocking_step = 3
        elif dry_run_active:
            blocking_step = 4
        elif not vhp_ready:
            blocking_step = 5
        else:
            blocking_step = 6  # fully activated

        fully_activated = blocking_step == 6

        # Recommended action
        api_key_placeholder = "<your_api_key>"
        if blocking_step == 1:
            recommended_action = (
                f"POST /agent/warm-up (need {sessions_remaining} more clean sessions; "
                "pass ?device_ids=<id> if agent_rulings is empty)"
            )
        elif blocking_step == 2:
            recommended_action = f"POST /agent/enforcement-certificate?api_key={api_key_placeholder}"
        elif blocking_step == 3:
            recommended_action = (
                "Ensure ProtocolIntelligenceAgent has published ready_for_live_mode=True "
                "AND a gate attestation exists after that timestamp"
            )
        elif blocking_step == 4:
            recommended_action = f"POST /agent/config?api_key={api_key_placeholder}&dry_run=false"
        elif blocking_step == 5:
            recommended_action = (
                f"POST /agent/mint-vhp?api_key={api_key_placeholder}"
                "&device_id=<id>&to_address=<addr>"
            )
        else:
            recommended_action = "Live mode ACTIVE. VHP issuance available."

        # Warnings
        warnings_list = []
        if gate_n < 50:
            warnings_list.append(
                f"gate_n={gate_n} is below recommended minimum of 50 — "
                "increase VALIDATION_GATE_N for production use"
            )

        return {
            "steps": {
                "step1_validation_gate": step1,
                "step2_enforcement_cert": step2,
                "step3_audit_valid": step3,
                "step4_live_mode": step4,
                "step5_vhp_mint": step5,
            },
            "current_blocking_step": blocking_step,
            "fully_activated": fully_activated,
            "recommended_action": recommended_action,
            "warnings": warnings_list,
            "timestamp": time.time(),
        }
    @app.post("/agent/commit-activation")
    async def commit_activation(
        api_key: str = Query(...),
        n_sessions: int = Query(default=110),
        notes: str = Query(default=""),
    ):
        """Phase 104 — Persistent Activation Commit (W1 mitigation).
        Runs simulation if needed, verifies Phase 97 gate, writes activation_committed=True
        to store (persists across restarts via _restore_activation_state at startup),
        sets cfg.agent_dry_run_mode=False via object.__setattr__, computes+stores PMI.
        """
        check_key(api_key)
        check_rate(api_key)
        import hashlib as _hl
        result = {"committed": False, "pmi": 0, "error": None, "timestamp": time.time()}
        try:
            # Step 1: simulate if no VHP exists
            if store.get_total_vhp_count() == 0:
                from ..activation_runner import ActivationRunner
                runner = ActivationRunner(cfg, store, bus=getattr(cfg, "_bus", None))
                sim = await runner.run(n_sessions=n_sessions)
                if sim.get("error"):
                    result["error"] = f"simulation_failed: {sim['error']}"
                    return result
            # Step 2: Phase 97 3-condition gate
            gate_n = int(getattr(cfg, "validation_gate_n", 100))
            max_div = float(getattr(cfg, "validation_max_divergence_rate", 1.0))
            gate_s = store.get_validation_summary(gate_n, max_div)
            cert   = store.get_latest_enforcement_certificate()
            audit  = store.get_activation_audit_summary()
            blocking = []
            if not gate_s.get("gate_passed", False):
                blocking.append("gate_not_passed")
            if cert is None or not cert.get("audit_valid") or time.time() > cert.get("expires_at", 0):
                blocking.append("cert_invalid_or_expired")
            if not audit.get("audit_valid", False):
                blocking.append("audit_invalid")
            if blocking:
                result["error"] = f"preconditions_not_met: {blocking}"
                return result
            # Phase 127: Check P0 preflight conditions before activation
            _preflight_logs = store.get_tournament_preflight_status(limit=1)
            if _preflight_logs:
                _latest_pf = _preflight_logs[0]
                _p0_fails = []
                if not _latest_pf.get("separation_ok", False):
                    _p0_fails.append("separation_ratio_below_1.0")
                if not _latest_pf.get("l4_ok", False):
                    _p0_fails.append("l4_calibration_stale")
                if not _latest_pf.get("biometric_ttl_ok", True):
                    _p0_fails.append("biometric_ttl_expired_or_no_renewal_chain")
                if not _latest_pf.get("all_pairs_p0_ok", False):
                    _p0_fails.append("per_pair_separation_below_1.0")
                if not _latest_pf.get("ait_defensibility_ok", False):
                    _p0_fails.append("ait_defensibility_not_confirmed")
                if _p0_fails:
                    result["error"] = (
                        f"preflight_p0_blocked: {_p0_fails}. "
                        f"Run POST /agent/run-tournament-preflight first."
                    )
                    return result
            # Step 3: persist
            op_hash = _hl.sha256(api_key.encode()).hexdigest()[:16]
            store.set_activation_committed(committed_by=op_hash, notes=notes or "commit-activation")
            # Step 4: in-memory (frozen dataclass bypass)
            object.__setattr__(cfg, "agent_dry_run_mode", False)
            # Step 5: bus event
            _bus = getattr(cfg, "_bus", None)
            if _bus:
                try:
                    _bus.publish_sync("activation_committed", {"timestamp": time.time()})
                except Exception:
                    pass  # fail-open: M-1 cleanup 2026-05-16 — intentional silent skip
            # Step 6: compute + store PMI
            pmi = store.compute_pmi()
            store.set_pmi(pmi, notes="post-commit")
            result.update({"committed": True, "pmi": pmi, "dry_run_active": False})
        except Exception as exc:
            result["error"] = str(exc)
        result["timestamp"] = time.time()
        return result
    @app.post("/agent/run-readiness-validation")
    async def run_readiness_validation(
        api_key: str = Query(...),
        n: int = Query(default=100),
    ):
        """Phase 107 — Run live mode readiness validation corpus (N nominal sessions)."""
        check_key(api_key)
        check_rate(api_key)
        from ..live_mode_readiness_validator import LiveModeReadinessValidator
        validator = LiveModeReadinessValidator(cfg, store)
        result = await validator.run_validation(n=n)
        result["timestamp"] = time.time()
        return result

    @app.get("/agent/live-mode-readiness")
    def live_mode_readiness(api_key: str = Query(...)):
        """Phase 107 — Latest live mode readiness report."""
        check_key(api_key)
        check_rate(api_key)
        try:
            report = store.get_latest_readiness_report()
            if report is None:
                return {"ready_for_live": False, "n_tested": 0, "found": False,
                        "timestamp": time.time()}
            report["found"] = True
            report["timestamp"] = time.time()
            return report
        except Exception as exc:
            return {"ready_for_live": False, "error": str(exc), "timestamp": time.time()}

    @app.get("/agent/tournament-readiness")
    def tournament_readiness(api_key: str = Query(...)):
        """Phase 108 — Comprehensive tournament readiness scorecard (5 software + 2 hardware conditions)."""
        check_key(api_key)
        check_rate(api_key)
        import json as _json
        try:
            # Software conditions — read from Phase 107 live-mode-readiness
            lm = store.get_latest_readiness_report()
            n_tested  = lm["n_tested"]             if lm else 0
            fp_count  = lm["false_positive_count"] if lm else 0

            # Activation state
            state     = store.get_activation_state()
            pmi       = store.compute_pmi()
            dry_run   = bool(getattr(cfg, "agent_dry_run_mode", True))
            committed = state.get("activation_committed", False)

            sw_conds = {
                "n_tested_ge_100":            n_tested >= 100,
                "false_positive_count_zero":  fp_count == 0,
                "activation_committed":       committed,
                "dry_run_inactive":           not dry_run,
                "pmi_ge_1":                   pmi >= 1,
            }
            sw_met = sum(sw_conds.values())

            # Hardware conditions — Phase 166: configurable gate (default 0.70)
            _min_sep108   = float(getattr(cfg, "min_separation_ratio", 0.70))
            sep_ratio     = float(getattr(cfg, "separation_ratio_current", 1.261))
            touchpad_ok   = bool(getattr(cfg, "touchpad_recapture_complete", False))
            hw_conds = {
                "separation_ratio_above_gate": sep_ratio >= _min_sep108,
                "touchpad_recapture_complete":  touchpad_ok,
            }
            hw_met = sum(hw_conds.values())

            fully_ready   = (sw_met == 5 and hw_met == 2)
            blocking      = [k for k, v in {**sw_conds, **hw_conds}.items() if not v]
            blocking_json = _json.dumps(blocking)

            store.insert_tournament_readiness_snapshot(
                n_tested=n_tested, false_positive_count=fp_count,
                activation_committed=1 if committed else 0, pmi=pmi,
                dry_run_active=1 if dry_run else 0,
                software_conditions_met=sw_met,
                separation_ratio=sep_ratio,
                separation_ratio_ok=1 if sep_ratio >= _min_sep108 else 0,
                touchpad_recapture_complete=1 if touchpad_ok else 0,
                hardware_conditions_met=hw_met,
                fully_ready=1 if fully_ready else 0,
                blocking_conditions_json=blocking_json,
                notes="phase108_scorecard",
            )

            return {
                "software_conditions":       sw_conds,
                "software_conditions_met":   sw_met,
                "software_conditions_total": 5,
                "hardware_conditions":       hw_conds,
                "hardware_conditions_met":   hw_met,
                "hardware_conditions_total": 2,
                "separation_ratio_current":  sep_ratio,
                "separation_ratio_required": 1.0,
                "fully_ready":               fully_ready,
                "blocking_conditions":       blocking,
                "ready_for_live":            bool(lm["ready_for_live"]) if lm else False,
                "pmi":                       pmi,
                "timestamp":                 time.time(),
            }
        except Exception as exc:
            return {"fully_ready": False, "error": str(exc), "timestamp": time.time()}
    @app.get("/agent/tournament-readiness-score")
    def tournament_readiness_score(api_key: str = Query(...)):
        """Phase 128 — Compute the tournament readiness score synthesizing 6 signals.

        Returns 9 keys:
          score (0.0-1.0 weighted composite), separation_score, l4_score,
          dual_gate_score, epoch_score, ioswarm_score, dry_run_score,
          conditions_met, timestamp

        Weights: separation=0.30, l4=0.20, dual_gate=0.15, epoch=0.15,
                 ioswarm=0.10, dry_run=0.10

        Persists result to protocol_intelligence_reports table for audit trail.
        """
        check_key(api_key)
        check_rate(api_key)
        import json as _json128
        try:
            # 1. separation_score: min(1.0, pooled_ratio / 1.0)
            pooled_ratio = float(getattr(cfg, "separation_ratio_current", 0.0))
            separation_score = min(1.0, pooled_ratio)

            # 2. l4_score: 1.0 if not stale (live_dim == calib_dim) else 0.0
            live_dim = int(getattr(cfg, "live_feature_dim", 13))
            calib_dim = int(getattr(cfg, "calibration_feature_dim", 12))
            l4_score = 1.0 if live_dim == calib_dim else 0.0

            # 3. dual_gate_score: 1.0 if >=1 eligible mint in last 24h else 0.5 if gate enabled else 0.0
            dual_gate_enabled = bool(getattr(cfg, "dual_primitive_gate_enabled", False))
            try:
                gate_logs = store.get_vhp_dual_gate_log(limit=100)
                _now = time.time()
                _window_s = 86400.0
                _recent_eligible = [
                    lg for lg in gate_logs
                    if lg.get("eligible") and (_now - float(lg.get("created_at", 0))) < _window_s
                ]
                if _recent_eligible:
                    dual_gate_score = 1.0
                elif dual_gate_enabled:
                    dual_gate_score = 0.5
                else:
                    dual_gate_score = 0.0
            except Exception:
                dual_gate_score = 0.5 if dual_gate_enabled else 0.0

            # 4. epoch_score: based on p95 vs window_seconds
            epoch_window_enabled = bool(getattr(cfg, "epoch_window_enabled", False))
            epoch_window_seconds = float(getattr(cfg, "epoch_window_seconds", 86400.0))
            try:
                epoch_analytics = store.get_epoch_window_analytics(limit=1000)
                p95 = float(epoch_analytics.get("p95_age_seconds", 0.0))
                if p95 <= 0 or epoch_analytics.get("checked_count", 0) == 0:
                    epoch_score = 0.5 if epoch_window_enabled else 0.0
                elif p95 < epoch_window_seconds:
                    epoch_score = 1.0
                else:
                    epoch_score = max(0.0, 1.0 - p95 / epoch_window_seconds)
            except Exception:
                epoch_score = 0.5 if epoch_window_enabled else 0.0

            # 5. ioswarm_score: 1.0 if ioswarm enabled and last mint log has quorum else 0.5 if enabled else 0.0
            ioswarm_mint_enabled = bool(getattr(cfg, "ioswarm_vhp_mint_enabled", False))
            if ioswarm_mint_enabled:
                try:
                    mint_logs = store.get_ioswarm_vhp_mint_log(limit=1)
                    if mint_logs and mint_logs[0].get("authorized"):
                        ioswarm_score = 1.0
                    else:
                        ioswarm_score = 0.5
                except Exception:
                    ioswarm_score = 0.5
            else:
                ioswarm_score = 0.0

            # 6. dry_run_score: 1.0 if dry_run=False else 0.0
            dry_run_active = bool(getattr(cfg, "agent_dry_run_mode", True))
            dry_run_score = 0.0 if dry_run_active else 1.0

            # Weighted composite
            score = (
                0.30 * separation_score
                + 0.20 * l4_score
                + 0.15 * dual_gate_score
                + 0.15 * epoch_score
                + 0.10 * ioswarm_score
                + 0.10 * dry_run_score
            )
            score = round(min(1.0, max(0.0, score)), 4)

            conditions_met = sum([
                separation_score >= 1.0,
                l4_score >= 1.0,
                dual_gate_score >= 1.0,
                epoch_score >= 1.0,
                ioswarm_score >= 1.0,
                dry_run_score >= 1.0,
            ])

            breakdown = {
                "separation_score": separation_score,
                "l4_score": l4_score,
                "dual_gate_score": dual_gate_score,
                "epoch_score": epoch_score,
                "ioswarm_score": ioswarm_score,
                "dry_run_score": dry_run_score,
            }

            # Persist to protocol_intelligence_reports
            try:
                store.insert_readiness_score(
                    score=score,
                    breakdown_json=_json128.dumps(breakdown),
                    conditions_met=conditions_met,
                )
            except Exception:
                pass  # Non-blocking — never fail the endpoint due to persistence error; fail-open: M-1 cleanup 2026-05-16

            return {
                "score":            score,
                "separation_score": separation_score,
                "l4_score":         l4_score,
                "dual_gate_score":  dual_gate_score,
                "epoch_score":      epoch_score,
                "ioswarm_score":    ioswarm_score,
                "dry_run_score":    dry_run_score,
                "conditions_met":   conditions_met,
                "timestamp":        time.time(),
            }
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

