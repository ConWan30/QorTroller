"""Agent supervisor / fleet intelligence routes (D-DECON-2 operator_api residue #20).

Register-function split per audits/decon-store-map.md agent_supervisor domain.
"""
from __future__ import annotations

import asyncio
import json as _json
import logging
import time
from pathlib import Path
from typing import Callable

from fastapi import FastAPI, Header, HTTPException, Query, Request

log = logging.getLogger(__name__)


def register_agent_supervisor_routes(
    app: FastAPI,
    *,
    cfg,
    store,
    chain,
    check_key: Callable[[str], None],
    check_rate: Callable[[str], None],
    check_read_key: Callable[[str], None],
    repo_root: Path,
) -> None:
    """Register supervisor, maturity, coherence, governance, and BBG status routes."""

    # --- Phase 83: Agent supervisor status ---

    @app.get("/agent/supervisor-status")
    def supervisor_status(
        api_key: str = Query(..., description="Shared operator API key"),
    ):
        """Return fleet health snapshot from AgentSupervisor (Phase 83).

        fleet_health: ALL_HEALTHY | DEGRADED | CRITICAL
        Core agents (session_adjudicator, ruling_enforcement_agent) STALE → CRITICAL.
        ZOMBIE: agent writes rows but to 0 distinct devices (W1 loop detection).
        """
        check_key(api_key)
        check_rate(api_key)
        try:
            from ..agent_supervisor import AgentSupervisor
            supervisor = AgentSupervisor(cfg, store)
            snapshot = supervisor.check_fleet_health()
            return snapshot
        except Exception as exc:
            log.warning("supervisor_status: check failed: %s", exc)
            return {"error": str(exc), "fleet_health": "UNKNOWN", "timestamp": __import__("time").time()}

    # --- Phase 84: Adjudication warm-up + gate readiness ---

    @app.post("/agent/warm-up")
    def agent_warm_up(
        api_key: str = Query(..., description="Shared operator API key"),
        batch_size: int = Query(None, description="Override batch_size (default from config)"),
        device_ids: str = Query(default="", description="Comma-separated device_ids to warm up (Phase 100 bootstrap)"),
    ):
        """Trigger a dry-run adjudication warm-up batch (Phase 84/100).

        Phase 100 bootstrap: pass ?device_ids=<id1>,<id2> to explicitly specify
        devices. Falls back to recent agent_rulings, then ioid_devices table.
        W1: WarmUpReport includes llm_available — if False, Anthropic key is missing.
        """
        check_key(api_key)
        check_rate(api_key)
        import asyncio as _asyncio
        from ..adjudication_warm_up import AdjudicationWarmUpRunner
        runner = AdjudicationWarmUpRunner(cfg, store)
        if batch_size is not None:
            runner._batch_size = int(batch_size)

        # Phase 100: explicit device_ids param → ioid fallback
        explicit_ids = [d.strip() for d in device_ids.split(",") if d.strip()]

        if not explicit_ids:
            recent = runner._get_recent_devices(runner._batch_size)
            if not recent:
                ioid_devs = store.get_ioid_devices(limit=runner._batch_size)
                explicit_ids = [d["device_id"] for d in ioid_devs]
                if not explicit_ids:
                    return {
                        "completed": 0, "failed": 0,
                        "reason": "no_devices_registered",
                        "hint": "Register a device via ioID first, or pass ?device_ids=<id>",
                        "timestamp": time.time(),
                    }

        try:
            loop = _asyncio.new_event_loop()
            report = loop.run_until_complete(runner.run_warm_up(
                device_ids=explicit_ids if explicit_ids else None
            ))
            loop.close()
        except Exception as exc:
            log.warning("agent_warm_up: failed: %s", exc)
            report = {"error": str(exc), "completed": 0, "failed": 0, "llm_available": False}
        return report

    @app.get("/agent/gate-readiness")
    def gate_readiness(
        api_key: str = Query(..., description="Shared operator API key"),
    ):
        """Return composite live-mode gate readiness (Phase 84).

        Aggregates:
          validation_gate:  consecutive_clean / gate_n progress + gate_passed
          fleet_health:     AgentSupervisor ALL_HEALTHY / DEGRADED / CRITICAL
          gate_attestations_count: number of on-chain gate proofs recorded
          overall_ready:    gate_passed AND fleet_health != CRITICAL
          dry_run_active:   current AGENT_DRY_RUN config value
        """
        check_key(api_key)
        check_rate(api_key)
        import time as _time
        gate_n = int(getattr(cfg, "validation_gate_n", 100))
        max_rate = float(getattr(cfg, "validation_max_divergence_rate", 1.0))
        dry_run_active = bool(getattr(cfg, "agent_dry_run_mode", True))

        # Validation gate
        try:
            gate_status = store.get_validation_gate_status(gate_n, max_rate)
        except Exception as exc:
            log.warning("gate_readiness: get_validation_gate_status failed: %s", exc)
            gate_status = {"gate_passed": False, "consecutive_clean": 0,
                           "error": str(exc)}

        # Fleet health
        try:
            from ..agent_supervisor import AgentSupervisor
            supervisor = AgentSupervisor(cfg, store)
            fleet = supervisor.check_fleet_health()
        except Exception as exc:
            log.warning("gate_readiness: fleet_health check failed: %s", exc)
            fleet = {"fleet_health": "UNKNOWN", "error": str(exc)}

        # Gate attestations count
        try:
            attestations = store.get_gate_attestations(limit=1)
            att_count = len(store.get_gate_attestations(limit=10000))
        except Exception:
            att_count = 0

        gate_passed = bool(gate_status.get("gate_passed", False))
        fleet_health = fleet.get("fleet_health", "UNKNOWN")
        overall_ready = gate_passed and fleet_health not in ("CRITICAL", "UNKNOWN")

        return {
            "overall_ready": overall_ready,
            "dry_run_active": dry_run_active,
            "gate_attestations_count": att_count,
            "validation_gate": gate_status,
            "fleet_health": fleet,
            "timestamp": _time.time(),
        }

    # --- Phase 86: Synthetic Session Corpus Pipeline ---

    @app.post("/agent/run-synthetic-corpus")
    def run_synthetic_corpus(
        api_key: str = Query(..., description="Shared operator API key"),
        n: int = Query(None, description="Override corpus size (default from config)"),
    ):
        """Trigger a synthetic validation corpus run (Phase 86).

        Runs N synthetic nominal sessions through rule_fallback. Results are stored
        in synthetic_sessions table ONLY — they do NOT affect ruling_validation_log
        or consecutive_clean (W1 isolation invariant).

        Use to: verify rule_fallback logic is correct, exercise the pipeline without
        real hardware, detect regressions after code changes (failed_fallback > 0).
        """
        check_key(api_key)
        check_rate(api_key)
        import asyncio as _asyncio
        from ..validation_corpus_runner import ValidationCorpusRunner
        runner = ValidationCorpusRunner(cfg, store)
        try:
            loop = _asyncio.new_event_loop()
            report = loop.run_until_complete(runner.run_corpus(n=n))
            loop.close()
        except Exception as exc:
            log.warning("run_synthetic_corpus: failed: %s", exc)
            report = {
                "error": str(exc),
                "generated": 0, "passed_fallback": 0, "failed_fallback": 0,
                "all_nominal": False, "corpus_run_id": None, "corpus_size": 0,
            }
        return report

    @app.get("/agent/corpus-status")
    def corpus_status(
        api_key: str = Query(..., description="Shared operator API key"),
    ):
        """Return synthetic validation corpus aggregate statistics (Phase 86).

        Includes isolation_note confirming synthetic sessions do NOT affect the
        production consecutive_clean gate.
        """
        check_key(api_key)
        check_rate(api_key)
        return store.get_corpus_status()

    # --- Phase 88: Adjudication Campaign Tracker ---

    @app.get("/agent/campaign-status")
    def campaign_status(
        api_key: str = Query(..., description="Shared operator API key"),
    ):
        """Return live adjudication campaign progress toward dry_run=False activation (Phase 88).

        Tracks the operator's progress toward the N=100 consecutive_clean validation gate.
        Includes per-session verdict history, divergence_breakdown (which evidence fields
        caused LLM↔fallback splits), and estimated_sessions_to_gate.

        W1 note: consecutive_clean is computed atomically at query time — never cached.
        Once campaign_note shows 'Gate PASSED', set AGENT_DRY_RUN=false to go live.
        """
        check_key(api_key)
        check_rate(api_key)
        gate_n = int(getattr(cfg, "validation_gate_n", 100))
        max_rate = float(getattr(cfg, "validation_max_divergence_rate", 1.0))
        try:
            return store.get_campaign_status(gate_n=gate_n, max_divergence_rate=max_rate)
        except Exception as exc:
            log.warning("campaign_status: query failed: %s", exc)
            return {
                "consecutive_clean": 0, "gate_n": gate_n, "progress_pct": 0.0,
                "session_count": 0, "divergence_count": 0, "divergence_rate": 0.0,
                "gate_passed": False, "estimated_sessions_to_gate": gate_n,
                "verdict_breakdown": {}, "divergence_breakdown": {},
                "recent_sessions": [], "last_session_at": None,
                "campaign_note": f"Error: {exc}",
            }

    # --- Phase 82: Reactive adjudication interrupt log ---

    @app.get("/agent/reactive-adjudication-log")
    def reactive_adjudication_log(
        api_key: str = Query(..., description="Shared operator API key"),
        device_id: str = Query(None, description="Optional device_id filter"),
        limit: int = Query(20, description="Max entries to return"),
    ):
        """Return reactive adjudication interrupt log (Phase 82).

        Lists Class J HIGH-risk triggered out-of-cycle LLM rulings.
        was_deferred=1 entries were rate-limited by the token bucket (W1).
        """
        check_key(api_key)
        check_rate(api_key)
        import time as _time
        try:
            entries = store.get_reactive_adjudication_log(
                device_id=device_id or None, limit=limit
            )
        except Exception as exc:
            log.warning("reactive_adjudication_log: query failed: %s", exc)
            entries = []
        deferred_count = sum(1 for e in entries if e.get("was_deferred"))
        return {
            "entries": entries,
            "total_returned": len(entries),
            "deferred_count": deferred_count,
            "timestamp": _time.time(),
        }

    # --- Phase 89: Protocol Intelligence ---

    @app.get("/agent/protocol-intelligence")
    def protocol_intelligence(
        api_key: str = Query(..., description="Shared operator API key"),
    ):
        """Return unified protocol_health_score synthesized from all VAPI agent streams.

        Reads the most recently stored report from protocol_intelligence_reports.
        Falls back to a live compute if no stored report exists yet.
        Phase 89.
        """
        check_key(api_key)
        check_rate(api_key)
        try:
            report = store.get_latest_protocol_intelligence_report()
            if report is not None:
                return report
            # No stored report — compute live
            from ..protocol_intelligence_agent import ProtocolIntelligenceAgent
            agent = ProtocolIntelligenceAgent(cfg, store)
            return agent.compute_report()
        except Exception as exc:
            log.warning("protocol_intelligence: query failed: %s", exc)
            return {
                "protocol_health_score": 0.0,
                "ready_for_live_mode": False,
                "bottleneck": "error",
                "recommendation": f"Error computing report: {exc}",
                "components": {},
            }

    # --- Phase 90: Shadow Enforcement ---

    @app.get("/agent/shadow-enforcement-log")
    def shadow_enforcement_log(
        api_key: str = Query(..., description="Shared operator API key"),
        device_id: str = Query(None, description="Optional device_id filter"),
        limit: int = Query(50, description="Max entries to return"),
    ):
        """Return shadow enforcement log (BLOCK actions that were suppressed in shadow mode).

        shadow_mode is active when ENFORCEMENT_SHADOW_MODE=true in config.
        Each entry represents a BLOCK ruling that would have suspended a PHGCredential
        but did not because shadow mode is enabled.
        Phase 90.
        """
        check_key(api_key)
        check_rate(api_key)
        try:
            entries = store.get_shadow_enforcement_log(device_id=device_id, limit=limit)
            stats = store.get_shadow_enforcement_stats()
            return {
                "shadow_mode_active": bool(getattr(cfg, "enforcement_shadow_mode", False)),
                "entries": entries,
                "total_returned": len(entries),
                "stats": stats,
                "timestamp": time.time(),
            }
        except Exception as exc:
            log.warning("shadow_enforcement_log: query failed: %s", exc)
            return {
                "shadow_mode_active": False,
                "entries": [],
                "total_returned": 0,
                "stats": {"total": 0, "passed": 0, "would_have_suspended": 0, "pass_rate": None},
                "error": str(exc),
            }

    # --- Phase 98: Epistemic Consensus Log ---

    @app.get("/agent/epistemic-consensus-log")
    def epistemic_consensus_log(
        api_key: str = Query(..., description="Shared operator API key"),
        device_id: str = Query(None, description="Filter by device_id"),
        limit: int = Query(50, description="Max entries to return"),
    ):
        """Return epistemic consensus decisions from Phase 98.

        Every BLOCK verdict that passed through the multi-agent consensus gate
        is recorded here with the weighted score breakdown:
          class_j_score (0.40 weight), triage_score (0.40), supervisor_score (0.20)
          consensus_score = weighted sum; consensus_reached = score >= threshold (default 0.60)
          downgraded=1 means BLOCK was downgraded to HOLD due to insufficient consensus.
        """
        check_key(api_key)
        check_rate(api_key)
        try:
            entries = store.get_epistemic_consensus_log(device_id=device_id, limit=limit)
            downgraded = sum(1 for e in entries if e.get("downgraded"))
            return {
                "entries": entries,
                "count": len(entries),
                "downgraded_count": downgraded,
                "timestamp": time.time(),
            }
        except Exception as exc:
            log.warning("epistemic_consensus_log: %s", exc)
            return {"entries": [], "count": 0, "downgraded_count": 0, "error": str(exc), "timestamp": time.time()}

    @app.get("/agent/protocol-maturity")
    def protocol_maturity(api_key: str = Query(...)):
        """Phase 104 — ProtocolMaturityIndex (PMI) + activation state.
        PMI: 0=uninitiated / 1=simulated / 2=testnet_organic / 3=mainnet.
        """
        check_key(api_key)
        check_rate(api_key)
        try:
            state = store.get_activation_state()
            pmi   = store.compute_pmi()
            vhp   = store.get_first_vhp_status()
            days  = None
            if vhp and vhp.get("expires_at"):
                days = round((vhp["expires_at"] - time.time()) / 86400, 1)
            _labels = {0: "uninitiated", 1: "simulated", 2: "testnet_organic", 3: "mainnet"}
            return {
                "pmi": pmi,
                "pmi_label": _labels.get(pmi, "unknown"),
                "activation_committed": state.get("activation_committed", False),
                "committed_at": state.get("committed_at"),
                "dry_run_active": bool(getattr(cfg, "agent_dry_run_mode", True)),
                "is_simulation": vhp.get("is_simulation", True) if vhp else True,
                "days_until_vhp_expiry": days,
                "vhp_found": vhp is not None,
                "timestamp": time.time(),
            }
        except Exception as exc:
            return {"pmi": 0, "error": str(exc), "timestamp": time.time()}

    @app.get("/agent/epistemic-config")
    def epistemic_config(api_key: str = Query(...)):
        """Phase 105 — Epistemic consensus config + threshold audit log.
        at_risk=True when effective_threshold < recommended (Phase 98 W1 exposure).
        pmi_triggered=True means PMI>=1 has auto-raised threshold (Phase 104/105 synergy).
        """
        check_key(api_key)
        check_rate(api_key)
        try:
            curr    = float(getattr(cfg, "epistemic_consensus_threshold", 0.60))
            rec     = float(getattr(cfg, "epistemic_recommended_threshold", 0.65))
            triage  = bool(getattr(cfg, "epistemic_triage_prereq_required", False))
            pmi     = store.compute_pmi()
            eff     = rec if (pmi >= 1 and rec > curr) else curr
            history = store.get_epistemic_threshold_history(limit=10)
            return {
                "configured_threshold":  curr,
                "recommended_threshold": rec,
                "effective_threshold":   eff,
                "pmi_triggered":         pmi >= 1 and rec > curr,
                "triage_prereq_required": triage,
                "at_risk":               eff < rec,
                "pmi":                   pmi,
                "threshold_history":     history,
                "w1_note": (
                    "threshold=0.60 reachable by ClassJ alone (0.40+0.20). "
                    "Raise EPISTEMIC_RECOMMENDED_THRESHOLD to 0.65."
                    if eff < 0.65 else None
                ),
                "timestamp": time.time(),
            }
        except Exception as exc:
            return {"error": str(exc), "timestamp": time.time()}

    # Phase 177 — GET /agent/protocol-maturity-score
    # ------------------------------------------------------------------
    @app.get("/agent/protocol-maturity-score")
    async def get_protocol_maturity_score_endpoint(api_key: str = ""):
        """ProtocolMaturityScoringAgent status (Phase 177, agent #26).

        Synthesizes 6 agent signals into a unified maturity_score (0.0-1.0).
        Component weights: separation(0.25) + chain_integrity(0.20) +
          consent(0.15) + biometric_freshness(0.15) + agent_calibration(0.15)
          + enrollment(0.10).
        maturity_tier: ALPHA (<0.50) | BETA (0.50-0.85) | PRODUCTION_CANDIDATE (>=0.85)

        Returns: protocol_maturity_enabled, maturity_score, maturity_tier,
        separation_component, chain_integrity_component, consent_component,
        biometric_freshness_component, agent_calibration_component,
        enrollment_component, timestamp.
        """
        check_key(api_key)
        check_rate(api_key)
        import time as _t177
        try:
            _enabled177 = bool(getattr(cfg, "protocol_maturity_enabled", True))
            _rows177    = store.get_protocol_maturity_status(limit=1)
            _latest177  = _rows177[0] if _rows177 else {}
            return {
                "protocol_maturity_enabled":          _enabled177,
                "maturity_score":                     float(_latest177.get("maturity_score",                0.0)),
                "maturity_tier":                      str(_latest177.get("maturity_tier",                   "ALPHA")),
                "separation_component":               float(_latest177.get("separation_component",          0.0)),
                "chain_integrity_component":          float(_latest177.get("chain_integrity_component",     0.0)),
                "consent_component":                  float(_latest177.get("consent_component",             0.0)),
                "biometric_freshness_component":      float(_latest177.get("biometric_freshness_component", 0.0)),
                "agent_calibration_component":        float(_latest177.get("agent_calibration_component",   0.0)),
                "enrollment_component":               float(_latest177.get("enrollment_component",          0.0)),
                "threat_forecast_accuracy_component": float(_latest177.get("threat_forecast_accuracy_component", 0.0)),
                "biometric_stationarity_component":   float(_latest177.get("biometric_stationarity_component",   0.0)),
                "pmi_component":                      float(_latest177.get("pmi_component",                 1.0)),
                "timestamp":                          _t177.time(),
            }
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    # Phase 176 — GET /agent/poac-chain-integrity
    # ------------------------------------------------------------------
    @app.get("/agent/poac-chain-integrity")
    async def get_poac_chain_integrity_endpoint(api_key: str = "", device_id: str = ""):
        """PoACChainIntegrityMonitor status (Phase 176, agent #25).

        Audits SHA-256 chain linkage across PoAC records.
        integrity_score = valid_links / total_records (1.0 = fully intact).
        W1 mitigation: only aggregate counts returned — no broken record IDs exposed.

        Returns: chain_integrity_enabled, device_id, total_records, valid_links,
        broken_links, integrity_score, audit_passed, timestamp.
        """
        check_key(api_key)
        check_rate(api_key)
        import time as _t176
        try:
            _enabled176 = bool(getattr(cfg, "chain_integrity_enabled", True))
            _dev176     = device_id.strip() or None
            _rows176    = store.get_poac_chain_audit_status(device_id=_dev176, limit=1)
            _latest176  = _rows176[0] if _rows176 else {}
            return {
                "chain_integrity_enabled": _enabled176,
                "device_id":       str(_latest176.get("device_id",       "")),
                "total_records":   int(_latest176.get("total_records",   0)),
                "valid_links":     int(_latest176.get("valid_links",     0)),
                "broken_links":    int(_latest176.get("broken_links",    0)),
                "integrity_score": float(_latest176.get("integrity_score", 1.0)),
                "audit_passed":    bool(_latest176.get("audit_passed",   True)),
                "timestamp":       _t176.time(),
            }
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    # Phase 175 — GET /agent/age-weight-analysis-status
    # ------------------------------------------------------------------
    @app.get("/agent/age-weight-analysis-status")
    async def get_age_weight_analysis_status_endpoint(api_key: str = ""):
        """AgeWeightedRatioPersistenceAgent status (Phase 175, agent #24).

        Persists results of --session-age-weight analysis runs (Phase 174 script).
        temporal_drift_index = raw_ratio - age_weighted_ratio:
          positive  -> old sessions inflate ratio (P1_NONSTATIONARITY)
          negative  -> new sessions stronger (IMPROVING)
          near-zero -> biometrically stationary (STABLE)

        Returns: age_weight_analysis_enabled, raw_ratio, age_weighted_ratio,
        temporal_drift_index, halflife_days, n_sessions_used, drift_direction, timestamp.
        """
        check_key(api_key)
        check_rate(api_key)
        import time as _t175
        try:
            _enabled175 = bool(getattr(cfg, "age_weight_analysis_enabled", True))
            _rows175    = store.get_age_weight_analysis_status(limit=1)
            _latest175  = _rows175[0] if _rows175 else {}
            return {
                "age_weight_analysis_enabled": _enabled175,
                "raw_ratio":            float(_latest175.get("raw_ratio",            0.0)),
                "age_weighted_ratio":   float(_latest175.get("age_weighted_ratio",   0.0)),
                "temporal_drift_index": float(_latest175.get("temporal_drift_index", 0.0)),
                "halflife_days":        float(_latest175.get("halflife_days",        90.0)),
                "n_sessions_used":      int(_latest175.get("n_sessions_used",        0)),
                "drift_direction":      str(_latest175.get("drift_direction",        "STABLE")),
                "timestamp":            _t175.time(),
            }
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    # Phase 165 — GET /agent/post-erasure-recompute-status
    # ------------------------------------------------------------------
    @app.get("/agent/post-erasure-recompute-status")
    async def get_post_erasure_recompute_status_endpoint(
        api_key: str = "",
        device_id: str = "",
    ):
        """Post-erasure separation ratio recompute audit status (Phase 165, WIF-024).

        When a device's biometric records are erased (GDPR Art.17), the stored
        separation ratio becomes stale because the anonymised device can no longer
        contribute feature vectors to the next analysis run.
        recompute_needed=True signals that analyze_interperson_separation.py should
        be re-run before the next tournament pre-launch preflight.

        Returns: consent_ledger_enabled/total_recomputes/pending_recomputes/
        latest_recompute_ts/latest_ratio_before/recompute_needed/timestamp.
        """
        check_key(api_key)
        check_rate(api_key)
        import time as _t165
        try:
            _enabled165 = bool(getattr(cfg, "consent_ledger_enabled", True))
            _status165  = store.get_post_erasure_recompute_status(
                device_id=device_id if device_id else None
            )
            return {
                "consent_ledger_enabled": _enabled165,
                "total_recomputes":       _status165["total_recomputes"],
                "pending_recomputes":     _status165["pending_recomputes"],
                "latest_recompute_ts":    _status165["latest_recompute_ts"],
                "latest_ratio_before":    _status165["latest_ratio_before"],
                "recompute_needed":       _status165["recompute_needed"],
                "timestamp":              _t165.time(),
            }
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    # Phase 148 — POST /agent/run-agent-self-test
    # ------------------------------------------------------------------
    @app.post("/agent/run-agent-self-test")
    async def run_agent_self_test_endpoint(api_key: str = ""):
        """Trigger an immediate ACIM self-test cycle (Phase 148)."""
        check_key(api_key)
        check_rate(api_key)
        import time as _t148b
        try:
            from ..agent_calibration_monitor import AgentCalibrationMonitor
            _acim = AgentCalibrationMonitor(cfg, store, bus=None)
            await _acim._run_all_tests()
            rows = store.get_agent_calibration_health(limit=32)
            seen: dict = {}
            for row in rows:
                aid = row.get("agent_id", 0)
                if aid not in seen:
                    seen[aid] = row
            healthy  = sum(1 for r in seen.values() if r.get("result") == "PASS")
            degraded = sum(1 for r in seen.values() if r.get("result") != "PASS")
            return {
                "triggered":     True,
                "agent_count":   16,
                "healthy_count": healthy,
                "degraded_count": degraded,
                "timestamp":     _t148b.time(),
            }
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    # -----------------------------------------------------------------------
    # Phase 192: DataCuratorAgent (Agent #35) — Tools #136–#144
    # -----------------------------------------------------------------------

    # Tool #136 — GET /agent/data-provenance-chain
    @app.get("/agent/data-provenance-chain")
    async def get_data_provenance_chain(
        leaf_node_id: str = "",
        record_hash: str = "",
        x_api_key: str = Header(default=""),
    ):
        """Tool #136 — Provenance DAG chain walk from leaf to root (Phase 192)."""
        check_read_key(x_api_key)
        import time as _t192_1
        from ..provenance_nodes import poac_record_node_id

        max_depth = getattr(cfg, "provenance_max_chain_depth", 20)
        resolved_from_record_hash = ""
        retina_commitments: list[dict] = []
        if record_hash.strip():
            resolved_from_record_hash = record_hash.strip()
            leaf_node_id = poac_record_node_id(resolved_from_record_hash)
            try:
                _children = await asyncio.to_thread(
                    store.get_provenance_subtree, leaf_node_id
                )
                retina_commitments = [
                    c for c in _children
                    if c.get("edge_type") == "PERCEPTION_BINDING"
                    or c.get("node_type") == "RETINA_STATE_COMMITMENT"
                ]
            except Exception:
                retina_commitments = []
        elif not leaf_node_id:
            # Return latest provenance node as default leaf
            try:
                with store._conn() as conn:
                    row = conn.execute(
                        "SELECT node_id FROM data_provenance_dag ORDER BY id DESC LIMIT 1"
                    ).fetchone()
                    leaf_node_id = row[0] if row else "none"
            except Exception:
                leaf_node_id = "none"
        chain = store.get_provenance_chain(leaf_node_id, max_depth=max_depth)
        if chain:
            root = chain[0]
            leaf = chain[-1]
            summary = (
                f"{len(chain)}-hop chain from {root.get('node_type', '?')} "
                f"(Phase {root.get('phase_produced', '?')}) to "
                f"{leaf.get('node_type', '?')}"
            )
            if leaf.get("on_chain_ref"):
                summary += f" — on-chain ref: {leaf['on_chain_ref'][:16]}..."
            if retina_commitments:
                summary += f" — {len(retina_commitments)} retina binding(s)"
        else:
            summary = "No provenance chain found for this leaf_node_id"
        return {
            "leaf_node_id":    leaf_node_id,
            "chain_length":    len(chain),
            "chain":           chain,
            "forensic_summary": summary,
            "resolved_from_record_hash": resolved_from_record_hash,
            "retina_commitments": retina_commitments,
            "timestamp":       _t192_1.time(),
        }

    # Tool #137 — GET /agent/corpus-entropy-status
    @app.get("/agent/corpus-entropy-status")
    async def get_corpus_entropy_status(
        x_api_key: str = Header(default=""),
    ):
        """Tool #137 — Corpus entropy monitor status (Phase 192)."""
        check_read_key(x_api_key)
        import time as _t192_2
        row = store.get_latest_corpus_entropy()
        threshold = getattr(cfg, "corpus_entropy_warning_threshold", 1.5)
        if row is None:
            return {
                "corpus_entropy_score":  0.0,
                "clustering_warning":    True,
                "status":                "NO_DATA",
                "per_player_entropy":    "{}",
                "low_entropy_features":  "[]",
                "n_sessions_analyzed":   0,
                "session_type_filter":   "touchpad_corners",
                "warning_threshold":     threshold,
                "timestamp":             _t192_2.time(),
            }
        score = float(row["corpus_entropy_score"])
        return {
            "corpus_entropy_score":  score,
            "clustering_warning":    bool(row["clustering_warning"]),
            "status":                "CLUSTERING_WARNING" if row["clustering_warning"] else "WELL_SAMPLED",
            "per_player_entropy":    row["per_player_entropy"],
            "low_entropy_features":  row["low_entropy_features"],
            "n_sessions_analyzed":   int(row["n_sessions_analyzed"]),
            "session_type_filter":   row["session_type_filter"],
            "warning_threshold":     threshold,
            "timestamp":             _t192_2.time(),
        }

    # Tool #139 — POST /agent/anchor-erasure-certificate
    @app.post("/agent/anchor-erasure-certificate")
    async def anchor_erasure_certificate(
        request: Request,
        x_api_key: str = Header(default=""),
    ):
        """Tool #139 — Anchor erasure certificate to AdjudicationRegistry.sol (Phase 192)."""
        check_read_key(x_api_key)
        import time as _t192_3b
        body = await request.json() if request.headers.get("content-type") else {}
        cert_hash = body.get("certificate_hash", "")
        tx_hash = body.get("tx_hash", f"dry_run_anchor_{int(_t192_3b.time() * 1e9)}")
        if not cert_hash:
            raise HTTPException(status_code=422, detail="certificate_hash required")
        store.anchor_erasure_certificate(cert_hash, tx_hash)
        return {
            "anchored":          True,
            "certificate_hash":  cert_hash,
            "tx_hash":           tx_hash,
            "dry_run":           getattr(cfg, "agent_dry_run_mode", True),
            "timestamp":         _t192_3b.time(),
        }

    # Tool #140 — GET /agent/federated-corpus-quality
    @app.get("/agent/federated-corpus-quality")
    async def get_federated_corpus_quality(
        x_api_key: str = Header(default=""),
    ):
        """Tool #140 — Federated corpus quality aggregator status (Phase 192)."""
        check_read_key(x_api_key)
        import time as _t192_4
        enabled = getattr(cfg, "federated_corpus_quality_enabled", False)
        records = store.get_federated_corpus_quality(limit=10)
        return {
            "federated_corpus_quality_enabled": enabled,
            "record_count":                     len(records),
            "records":                          records,
            "privacy_constraint":               "BP-007: no raw biometric data",
            "timestamp":                        _t192_4.time(),
        }

    # Tool #141 — GET /agent/feature-correlation-status
    @app.get("/agent/feature-correlation-status")
    async def get_feature_correlation_status(
        player_id: str = "",
        x_api_key: str = Header(default=""),
    ):
        """Tool #141 — Per-player 13x13 correlation matrix status (Phase 192)."""
        check_read_key(x_api_key)
        import time as _t192_5
        threshold = getattr(cfg, "correlation_separability_threshold", 0.5)
        row = store.get_feature_correlation(player_id=player_id)
        if row is None:
            return {
                "player_id":             player_id or "all",
                "correlation_found":     False,
                "correlation_separable": False,
                "separability_threshold": threshold,
                "frobenius_vs_p1":       None,
                "frobenius_vs_p2":       None,
                "frobenius_vs_p3":       None,
                "n_sessions_used":       0,
                "timestamp":             _t192_5.time(),
            }
        return {
            "player_id":             row["player_id"],
            "correlation_found":     True,
            "correlation_separable": bool(row["correlation_separable"]),
            "separability_threshold": threshold,
            "frobenius_vs_p1":       row["frobenius_vs_p1"],
            "frobenius_vs_p2":       row["frobenius_vs_p2"],
            "frobenius_vs_p3":       row["frobenius_vs_p3"],
            "n_sessions_used":       int(row["n_sessions_used"]),
            "high_correlation_pairs": row["high_correlation_pairs"],
            "timestamp":             _t192_5.time(),
        }

    # Tool #142 — GET /agent/data-readiness-certificate
    @app.get("/agent/data-readiness-certificate")
    async def get_data_readiness_certificate(
        x_api_key: str = Header(default=""),
    ):
        """Tool #142 — 8-dimension pre-tournament data readiness certificate (Phase 192)."""
        check_read_key(x_api_key)
        import time as _t192_6
        cert = store.get_latest_data_readiness_certificate()
        if cert is None:
            return {
                "certificate_found":     False,
                "certification_status":  "NO_CERTIFICATE",
                "certificate_hash":      None,
                "separation_ratio":      0.0,
                "blocking_failures":     "[]",
                "advisory_warnings":     "[]",
                "anchored":              False,
                "timestamp":             _t192_6.time(),
            }
        return {
            "certificate_found":     True,
            "certification_status":  cert["certification_status"],
            "certificate_hash":      cert["certificate_hash"],
            "separation_ratio":      float(cert["separation_ratio"]),
            "blocking_failures":     cert["blocking_failures"],
            "advisory_warnings":     cert["advisory_warnings"],
            "dimension_results":     cert["dimension_results"],
            "anchored":              bool(cert["anchored"]),
            "on_chain_tx_hash":      cert["on_chain_tx_hash"],
            "valid_until_ts":        int(cert["valid_until_ts"]),
            "timestamp":             _t192_6.time(),
        }

    # Tool #143 — POST /agent/anchor-data-readiness-certificate
    @app.post("/agent/anchor-data-readiness-certificate")
    async def anchor_data_readiness_certificate(
        request: Request,
        x_api_key: str = Header(default=""),
    ):
        """Tool #143 — Anchor data readiness certificate on-chain (Phase 192)."""
        check_read_key(x_api_key)
        import time as _t192_6b
        body = await request.json() if request.headers.get("content-type") else {}
        cert_hash = body.get("certificate_hash", "")
        tx_hash = body.get("tx_hash", f"dry_run_anchor_{int(_t192_6b.time() * 1e9)}")
        if not cert_hash:
            raise HTTPException(status_code=422, detail="certificate_hash required")
        store.anchor_data_readiness_certificate(cert_hash, tx_hash)
        return {
            "anchored":         True,
            "certificate_hash": cert_hash,
            "tx_hash":          tx_hash,
            "dry_run":          getattr(cfg, "agent_dry_run_mode", True),
            "timestamp":        _t192_6b.time(),
        }

    # Tool #144 — GET /agent/session-contribution-weights
    @app.get("/agent/session-contribution-weights")
    async def get_session_contribution_weights(
        player_id: str = "",
        x_api_key: str = Header(default=""),
    ):
        """Tool #144 — TBD-decay session contribution weights (Phase 192).
        FROZEN: lambda=ln(2)/90 (BP-001 TBD half-life=90 days).
        """
        check_read_key(x_api_key)
        import time as _t192_7
        import math as _math192
        weights = store.get_session_weights(player_id=player_id, limit=30)
        tbd_lambda = _math192.log(2) / 90  # FROZEN: BP-001
        return {
            "player_id":          player_id or "all",
            "tbd_lambda":         round(tbd_lambda, 8),
            "tbd_halflife_days":  90,
            "weight_count":       len(weights),
            "weights":            weights,
            "timestamp":          _t192_7.time(),
        }

    # Phase 193: FleetSignalCoherenceAgent (agent #36) endpoints
    # Tool #145 — GET /agent/fleet-coherence-summary
    @app.get("/agent/fleet-coherence-summary")
    async def get_fleet_coherence_summary(
        x_api_key: str = Header(default=""),
    ):
        """Tool #145 — Fleet signal coherence summary (Phase 193).
        Returns total open contradictions/orphans/inversions, severity counts,
        WIF promotion count. CRITICAL entries mean two agents report incompatible states.
        """
        check_read_key(x_api_key)
        import time as _t193_1
        enabled = getattr(cfg, "fleet_coherence_enabled", True)
        summary = store.get_coherence_summary()
        return {
            "fleet_coherence_enabled": enabled,
            "total_open":              summary.get("total_open", 0),
            "by_severity":             summary.get("by_severity",
                                           {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0}),
            "by_mode":                 summary.get("by_mode",
                                           {"CONTRADICTION": 0, "ORPHAN": 0, "INVERSION": 0}),
            "promoted_to_wif":         summary.get("promoted_to_wif", 0),
            "last_cycle_findings":     summary.get("total_open", 0),
            "last_checked_at":         summary.get("last_checked_at", ""),
            "timestamp":               _t193_1.time(),
        }

    # Tool #146 — GET /agent/fleet-coherence-entries
    @app.get("/agent/fleet-coherence-entries")
    async def get_fleet_coherence_entries(
        failure_mode: str = "",
        severity: str = "",
        x_api_key: str = Header(default=""),
    ):
        """Tool #146 — Fleet coherence open entries, filterable by failure_mode and severity (Phase 193)."""
        check_read_key(x_api_key)
        import time as _t193_2
        entries = store.get_open_coherence_entries(
            severity=severity or None,
            failure_mode=failure_mode or None,
        )
        return {
            "entry_count":  len(entries),
            "entries":      entries,
            "failure_mode": failure_mode or "all",
            "severity":     severity or "all",
            "timestamp":    _t193_2.time(),
        }

    # POST /agent/resolve-coherence-entry
    @app.post("/agent/resolve-coherence-entry")
    async def resolve_coherence_entry(
        request: Request,
        x_api_key: str = Header(default=""),
    ):
        """Resolve a fleet coherence entry by coherence_id (Phase 193)."""
        check_read_key(x_api_key)
        import time as _t193_3
        body = await request.json() if request.headers.get("content-type") else {}
        coherence_id = body.get("coherence_id", "")
        resolved_by  = body.get("resolved_by", "operator")
        if not coherence_id:
            raise HTTPException(status_code=422, detail="coherence_id required")
        store.mark_coherence_resolved(coherence_id, resolved_by)
        return {
            "resolved":      True,
            "coherence_id":  coherence_id,
            "resolved_by":   resolved_by,
            "timestamp":     _t193_3.time(),
        }

    # Tool #147 — GET /agent/fleet-coherence-history
    @app.get("/agent/fleet-coherence-history")
    async def get_fleet_coherence_history(
        rule_name: str = "",
        limit: int = 20,
        x_api_key: str = Header(default=""),
    ):
        """Tool #147 — Fleet coherence history for a specific rule (Phase 193)."""
        check_read_key(x_api_key)
        import time as _t193_4
        import sqlite3 as _sq193
        try:
            with _sq193.connect(store._db_path) as _conn193:
                _conn193.row_factory = _sq193.Row
                _q = (
                    "SELECT coherence_id, failure_mode, rule_name, severity, "
                    "resolved, promoted_to_wif, wif_entry_id, created_at "
                    "FROM fleet_coherence_log"
                )
                _params: list = []
                if rule_name:
                    _q += " WHERE rule_name=?"
                    _params.append(rule_name)
                _q += " ORDER BY created_at DESC LIMIT ?"
                _params.append(min(limit, 100))
                rows = [dict(r) for r in _conn193.execute(_q, _params).fetchall()]
        except Exception:
            rows = []
        return {
            "rule_name":    rule_name or "all",
            "entry_count":  len(rows),
            "entries":      rows,
            "timestamp":    _t193_4.time(),
        }

    # Phase 194: CoherenceFingerprintRegistry — Tool #148
    # -----------------------------------------------------------------------

    # Tool #148 — GET /agent/coherence-fingerprint-status
    @app.get("/agent/coherence-fingerprint-status")
    async def get_coherence_fingerprint_status(
        x_api_key: str = Header(default=""),
    ):
        """Tool #148 — Coherence fingerprint registry status (Phase 194).

        Returns per-rule occurrence counts from coherence_fingerprint_log.
        persistent_count = rules with occurrence_count >= 3 (N_PROMOTE_THRESHOLD).
        maturity_penalty = min(1.0, persistent_count × 0.10) — applied to
        ProtocolMaturityScoringAgent threat_forecast_accuracy_component.
        """
        check_read_key(x_api_key)
        import time as _t194
        status = store.get_coherence_fingerprint_status()
        return {
            "total_rules":        status.get("total_rules", 0),
            "persistent_count":   status.get("persistent_count", 0),
            "total_occurrences":  status.get("total_occurrences", 0),
            "maturity_penalty":   status.get("maturity_penalty", 0.0),
            "top_rules":          status.get("top_rules", []),
            "n_promote_threshold": 3,
            "timestamp":          _t194.time(),
        }

    # Phase 195: Protocol Metabolism Index — Tool #149
    # -----------------------------------------------------------------------

    # Tool #149 — GET /agent/protocol-metabolism-index
    @app.get("/agent/protocol-metabolism-index")
    async def get_protocol_metabolism_index(
        x_api_key: str = Header(default=""),
        domain: str = "",
    ):
        """Tool #149 — Protocol Metabolism Index status (Phase 195).

        PMI = max(0.0, 1.0 - mean_orphan_resolution_hours / 48.0)
        Measures how quickly the 36-agent fleet self-heals ORPHAN signal inconsistencies.
        1.0 = instant resolution or no ORPHANs (healthy fleet).
        0.0 = mean resolution >= 48h (fleet metabolises very slowly).
        Feeds into ProtocolMaturityScoringAgent as the 9th component (weight=0.03).

        Returns 6 keys:
          mean_resolution_hours_critical / pmi_score / orphan_count_open /
          orphan_count_resolved / domain / timestamp
        """
        check_read_key(x_api_key)
        import time as _t195
        stats = store.get_orphan_resolution_stats(domain=domain)
        return {
            "mean_resolution_hours_critical": stats.get("mean_resolution_hours", 0.0),
            "pmi_score":                      stats.get("pmi_score", 1.0),
            "orphan_count_open":              stats.get("orphan_count_open", 0),
            "orphan_count_resolved":          stats.get("orphan_count_resolved", 0),
            "domain":                         stats.get("domain", "all"),
            "timestamp":                      _t195.time(),
        }

    # ------------------------------------------------------------------
    # Phase 222 — GET /agent/bbg-status  +  POST /agent/bbg-propose
    # ------------------------------------------------------------------
    @app.get("/agent/bbg-status")
    async def get_bbg_status(
        x_api_key: str = Header(default=""),
    ):
        """BiometricBoundGovernance status (Phase 222).

        Returns the latest BBG proposal record plus configuration state.

        Returns 7 keys: bbg_enabled / total_proposals / latest_proposal_hash /
                        latest_proposer / on_chain_confirmed / last_proposal_ts / timestamp
        """
        check_read_key(x_api_key)
        import time as _t222
        _enabled222 = bool(getattr(cfg, "bbg_enabled", False))
        try:
            _status222 = store.get_bbg_status()
        except Exception:
            _status222 = {
                "total_proposals": 0, "latest_proposal_hash": None,
                "latest_proposer": None, "on_chain_confirmed": False,
                "last_proposal_ts": None, "timestamp": _t222.time(),
            }
        return {
            "bbg_enabled":           _enabled222,
            "total_proposals":       _status222.get("total_proposals", 0),
            "latest_proposal_hash":  _status222.get("latest_proposal_hash"),
            "latest_proposer":       _status222.get("latest_proposer"),
            "on_chain_confirmed":    _status222.get("on_chain_confirmed", False),
            "last_proposal_ts":      _status222.get("last_proposal_ts"),
            "timestamp":             _t222.time(),
        }

    @app.post("/agent/bbg-propose")
    async def post_bbg_propose(
        x_api_key:        str   = Header(default=""),
        proposal_hash:    str   = "",
        proposer_address: str   = "",
        vhp_token_id:     int   = 0,
        vhp_expires_at:   float = 0.0,
    ):
        """Submit a biometric-bound governance proposal (Phase 222).

        Validates the proposal against the proposer's VHP freshness, records locally,
        and optionally submits on-chain if BBG_CONTRACT_ADDRESS is configured.

        Returns 5 keys: valid / on_chain / tx_hash / row_id / rejection_reason
        """
        check_read_key(x_api_key)
        import time as _t222p
        try:
            from ..biometric_governance_agent import BiometricGovernanceAgent as _BGA222
            _bga = _BGA222(store, cfg, chain=None)
            _result222 = await _bga.submit_proposal(
                proposal_hash=str(proposal_hash),
                proposer_address=str(proposer_address),
                vhp_token_id=int(vhp_token_id),
                vhp_expires_at=float(vhp_expires_at),
            )
        except Exception as _exc222:
            _result222 = {
                "valid": False, "on_chain": False,
                "tx_hash": "", "row_id": 0,
                "rejection_reason": str(_exc222),
            }
        return {
            "valid":            _result222.get("valid", False),
            "on_chain":         _result222.get("on_chain", False),
            "tx_hash":          _result222.get("tx_hash", ""),
            "row_id":           _result222.get("row_id", 0),
            "rejection_reason": _result222.get("rejection_reason"),
        }

    # Phase 223 — GET /agent/invariant-gate-status  +  POST /agent/run-invariant-gate
    # ------------------------------------------------------------------
    @app.get("/agent/invariant-gate-status")
    async def get_invariant_gate_status(
        x_api_key: str = Header(default=""),
    ):
        """PV-CI protocol invariant gate status (Phase 223).

        Returns the latest gate run result: pass/fail, checked count, failure list.

        Returns 7 keys: pv_ci_enabled / gate_pass / total_checked / failure_count /
                        last_failures / last_run_ts / timestamp
        """
        check_read_key(x_api_key)
        _enabled223 = bool(getattr(cfg, "pv_ci_enabled", True))
        try:
            _status223 = store.get_invariant_gate_status()
        except Exception as _e223:
            import time as _t223e
            _status223 = {
                "pv_ci_enabled": _enabled223, "gate_pass": None,
                "total_checked": 0, "failure_count": 0,
                "last_failures": [str(_e223)], "last_run_ts": None,
                "timestamp": _t223e.time(),
            }
        _status223["pv_ci_enabled"] = _enabled223
        return _status223

    @app.post("/agent/run-invariant-gate")
    async def run_invariant_gate(
        x_api_key: str = Header(default=""),
    ):
        """Trigger a PV-CI invariant gate run (Phase 223).

        Executes vapi_invariant_gate.check_invariants() inline, stores result,
        returns same 7 keys as GET /agent/invariant-gate-status.
        """
        check_read_key(x_api_key)
        import json as _json223
        import sys as _sys223
        import time as _t223p
        from pathlib import Path as _Path223

        _gate_mod_path = str(repo_root / "scripts")
        if _gate_mod_path not in _sys223.path:
            _sys223.path.insert(0, _gate_mod_path)
        try:
            import importlib, importlib.util
            _spec = importlib.util.spec_from_file_location(
                "vapi_invariant_gate",
                str(repo_root / "scripts" / "vapi_invariant_gate.py"),
            )
            _gate_mod = importlib.util.module_from_spec(_spec)
            _spec.loader.exec_module(_gate_mod)
            _results = _gate_mod.check_invariants()
            _allowlist = _gate_mod.load_allowlist()
            _failures = []
            for _r in _results:
                if not _r["file_found"]:
                    _failures.append(f"{_r['id']} FILE_NOT_FOUND")
                elif not _r["pattern_matched"]:
                    _failures.append(f"{_r['id']} PATTERN_NOT_MATCHED")
                elif _allowlist and _r["id"] in _allowlist:
                    if _r["digest"] != _allowlist[_r["id"]]["digest"]:
                        _failures.append(f"{_r['id']} DIGEST_DRIFT")
            _pass = len(_failures) == 0
            _row_id = store.insert_invariant_gate_log(
                gate_pass=_pass,
                total_checked=len(_results),
                failures_json=_json223.dumps(_failures),
                run_source="api",
            )
        except Exception as _ex223:
            _failures = [str(_ex223)]
            _pass = False
            _row_id = store.insert_invariant_gate_log(
                gate_pass=False,
                total_checked=0,
                failures_json=_json223.dumps(_failures),
                run_source="api",
            )

        return {
            "pv_ci_enabled":  bool(getattr(cfg, "pv_ci_enabled", True)),
            "gate_pass":      _pass,
            "total_checked":  len(_results) if "_results" in dir() else 0,
            "failure_count":  len(_failures),
            "last_failures":  _failures,
            "last_run_ts":    _t223p.time(),
            "timestamp":      _t223p.time(),
        }

    # Phase 224 — POST /agent/allowlist-governance-event
    # ------------------------------------------------------------------
    @app.post("/agent/allowlist-governance-event")
    async def post_allowlist_governance_event(
        request: Request,
        x_api_key: str = Header(default=""),
    ):
        """Record an allowlist governance event (Phase 224).

        Called by vapi_invariant_gate.py --generate after writing the allowlist.
        Validates reason_category and stores the event in invariant_gate_log.
        Returns 422 on invalid category or reason_text length.

        Body JSON: previous_hash, new_hash, reason_category, reason_text
        Returns: row_id, accepted, category
        """
        check_read_key(x_api_key)
        import time as _t224
        _VALID_CATS_224 = {"refactor", "bugfix", "invariant_change", "ceremony_update"}
        try:
            _body224 = await request.json()
        except Exception:
            from fastapi.responses import JSONResponse as _JR224
            return _JR224({"error": "invalid JSON body"}, status_code=422)
        _prev224  = str(_body224.get("previous_hash", ""))
        _new224   = str(_body224.get("new_hash", ""))
        _cat224   = str(_body224.get("reason_category", ""))
        _text224  = str(_body224.get("reason_text", ""))

        from fastapi.responses import JSONResponse as _JR224
        if _cat224 not in _VALID_CATS_224:
            return _JR224(
                {"error": f"invalid reason_category: {_cat224!r}. "
                 f"Must be one of: {sorted(_VALID_CATS_224)}"},
                status_code=422,
            )
        if not (10 <= len(_text224) <= 200):
            return _JR224(
                {"error": "reason_text must be 10-200 characters"},
                status_code=422,
            )

        # Phase 228: VHP gate for invariant_change category (fail-open when chain unreachable)
        _vhp228_token = str(_body224.get("vhp_token_id", ""))
        _vhp228_enabled = getattr(cfg, "vhp_gated_invariant_change_enabled", False)
        if _cat224 == "invariant_change" and _vhp228_enabled:
            from fastapi.responses import JSONResponse as _JR228
            if not _vhp228_token:
                return _JR228(
                    {"error": "invariant_change requires vhp_token_id when vhp_gated_invariant_change_enabled=True"},
                    status_code=403,
                )
            # Verify VHP is live (fail-open: only hard-block on confirmed invalid)
            _vhp228_valid = None
            try:
                import asyncio as _aio228
                _vhp228_valid = await chain.is_vhp_valid(int(_vhp228_token))
            except Exception:
                pass  # fail-open — chain may be unreachable; allow governance event
            if _vhp228_valid is False:
                return _JR228(
                    {"error": "VHP token expired or invalid — invariant_change blocked"},
                    status_code=403,
                )

        _row_id224 = store.insert_invariant_gate_log(
            gate_pass=True,
            total_checked=0,
            failures_json="[]",
            run_source=f"governance:{_cat224}:{_text224[:40]}",
            previous_allowlist_hash=_prev224,
            new_allowlist_hash=_new224,
            reason_category=_cat224,
            reason_text=_text224,
            vhp_token_id=_vhp228_token,
        )

        # Phase 225: store provenance chain entry if hashes provided.
        _prov_hash225  = str(_body224.get("governance_provenance_hash", ""))
        _prev_prov225  = str(_body224.get("previous_provenance_hash", ""))
        if _prov_hash225:
            try:
                store.insert_governance_provenance(
                    governance_provenance_hash=_prov_hash225,
                    previous_provenance_hash=_prev_prov225,
                    new_allowlist_hash=_new224,
                    reason_category=_cat224,
                    reason_text=_text224,
                )
            except Exception:
                pass  # fail-open — governance record still in invariant_gate_log

        # Fire bus event for invariant_change category (fail-open)
        if _cat224 == "invariant_change":
            try:
                _bus224 = getattr(cfg, "_federation_bus", None)
                if _bus224 is not None:
                    import asyncio as _aio224
                    _aio224.create_task(
                        _bus224.publish("invariant_governance_change", {
                            "category": _cat224,
                            "text": _text224,
                            "new_hash": _new224,
                            "ts": _t224.time(),
                        })
                    )
            except Exception:
                pass  # fail-open

        return {
            "row_id":   _row_id224,
            "accepted": True,
            "category": _cat224,
            "governance_provenance_hash": _prov_hash225 or None,
            "vhp_token_id": _vhp228_token or None,
        }

    # Phase 225 — GET /agent/allowlist-governance-history
    # ------------------------------------------------------------------
    @app.get("/agent/allowlist-governance-history")
    async def get_allowlist_governance_history(
        limit: int = 20,
        x_api_key: str = Header(default=""),
    ):
        """Paginated governance provenance chain (Phase 225).

        Returns the hash-linked audit trail of every --generate governance event.
        Each entry includes the provenance hash that cryptographically chains to the
        previous entry, enabling tamper detection without on-chain anchoring.

        Query params:
            limit: max entries to return (default 20, max 100)

        Returns: {entries, total_entries, chain_intact, timestamp}
        """
        check_read_key(x_api_key)
        import time as _t225
        _lim225 = max(1, min(100, int(limit)))
        _entries225 = store.get_governance_provenance_history(limit=_lim225)
        # Verify chain integrity: each entry's previous_provenance_hash must equal
        # the governance_provenance_hash of the next-older entry.
        _chain_intact = True
        if len(_entries225) > 1:
            for _i225 in range(len(_entries225) - 1):
                _newer = _entries225[_i225]
                _older = _entries225[_i225 + 1]
                if _newer["previous_provenance_hash"] != _older["governance_provenance_hash"]:
                    _chain_intact = False
                    break
        return {
            "entries":       _entries225,
            "total_entries": len(_entries225),
            "chain_intact":  _chain_intact,
            "timestamp":     _t225.time(),
        }

    # Phase 221/227 — GET /agent/protocol-coherence-status
    # ------------------------------------------------------------------
    @app.get("/agent/protocol-coherence-status")
    async def get_protocol_coherence_status(
        x_api_key: str = Header(default=""),
    ):
        """Proof of Protocol Coherence (PoPC) status (Phase 221/227).

        Returns the latest Merkle root anchor over 36 VAPI agent fleet observations,
        plus on-chain confirmation status.

        Phase 227: adds governance_provenance_hash field (latest provenance hash
        stored alongside the Merkle root at last anchor time; empty when no Phase 227
        anchor has been performed yet).

        Returns 8 keys: protocol_coherence_enabled / total_anchors / latest_merkle_root /
                        agent_count / on_chain_confirmed / last_anchor_ts /
                        governance_provenance_hash / timestamp
        """
        check_read_key(x_api_key)
        import time as _t221
        _enabled221 = bool(getattr(cfg, "protocol_coherence_enabled", False))
        try:
            _status221 = store.get_protocol_coherence_status()
        except Exception:
            _status221 = {
                "total_anchors": 0, "latest_merkle_root": None,
                "agent_count": 0, "on_chain_confirmed": False,
                "last_anchor_ts": None, "governance_provenance_hash": "",
                "timestamp": _t221.time(),
            }
        return {
            "protocol_coherence_enabled":  _enabled221,
            "total_anchors":               _status221.get("total_anchors", 0),
            "latest_merkle_root":          _status221.get("latest_merkle_root"),
            "agent_count":                 _status221.get("agent_count", 0),
            "on_chain_confirmed":          _status221.get("on_chain_confirmed", False),
            "last_anchor_ts":              _status221.get("last_anchor_ts"),
            "governance_provenance_hash":  _status221.get("governance_provenance_hash", ""),
            "timestamp":                   _t221.time(),
        }

    # Phase 239 — GET /agent/gamer-readiness-status
    # ------------------------------------------------------------------
    @app.get("/agent/gamer-readiness-status")
    async def get_gamer_readiness_status(
        device_id: str = "D1",
        x_api_key: str = Header(default=""),
    ):
        """Gamer physical/cognitive readiness and RSI risk status (Phase 239).

        Returns the latest calculated fatigue index, touchpad entropy, L6b haptic latency,
        RSI risk score, and stretch/break recommendation for a device.
        """
        check_read_key(x_api_key)
        import time as _t239
        _enabled239 = bool(getattr(cfg, "gamer_readiness_enabled", True))
        try:
            _status239 = store.get_gamer_readiness_status(device_id)
        except Exception:
            _status239 = None

        if _status239:
            return {
                "gamer_readiness_enabled": _enabled239,
                "device_id":               _status239["device_id"],
                "readiness_score":         _status239["readiness_score"],
                "rsi_risk_score":          _status239["rsi_risk_score"],
                "fatigue_index":           _status239["fatigue_index"],
                "avg_tremor_hz":           _status239["avg_tremor_hz"],
                "touchpad_entropy":        _status239["touchpad_entropy"],
                "reaction_latency_ms":     _status239["reaction_latency_ms"],
                "recommendation":          _status239["recommendation"],
                "created_at":              _status239["created_at"],
                "timestamp":               _t239.time(),
            }
        else:
            return {
                "gamer_readiness_enabled": _enabled239,
                "device_id":               device_id,
                "readiness_score":         1.0,
                "rsi_risk_score":          0.0,
                "fatigue_index":           0.0,
                "avg_tremor_hz":           8.0,
                "touchpad_entropy":        1.5,
                "reaction_latency_ms":     150.0,
                "recommendation":          "NOMINAL",
                "created_at":              0.0,
                "timestamp":               _t239.time(),
            }
