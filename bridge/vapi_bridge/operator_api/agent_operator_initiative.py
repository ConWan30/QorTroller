"""Operator Initiative routes (D-DECON-2 operator_api residue #18).

Register-function split per audits/decon-store-map.md agent_operator_initiative domain.
"""
from __future__ import annotations

import asyncio
import hmac
import logging
import time
from pathlib import Path
from typing import Callable

from fastapi import FastAPI, Header, HTTPException, Query

log = logging.getLogger(__name__)


def register_agent_operator_initiative_routes(
    app: FastAPI,
    *,
    cfg,
    store,
    check_key: Callable[[str], None],
    check_rate: Callable[[str], None],
    check_read_key: Callable[[str], None],
    repo_root: Path,
    vapi_bridge_dir: Path,
) -> None:
    """Register Cedar bundle anchoring, operator-agent logs, FRR, and audit HTTP routes."""

    # ------------------------------------------------------------------
    # Phase O1 C1 — Operator Agent activation arc (Cedar bundle dual-anchor)
    # ------------------------------------------------------------------

    @app.post("/operator/anchor-cedar-bundle")
    async def anchor_cedar_bundle(
        api_key: str = Query(default=""),
        bundle_path: str = Query(default=""),
        reason: str = Query(default=""),
    ):
        """Operator-triggered Phase O1 Cedar bundle dual on-chain anchor.

        Fires the dual anchor per D4 + INV-OPERATOR-AGENT-001:
          1. AgentScope.setAgentScopeRoot   (operational layer FIRST)
          2. AgentRegistry.updateAgentScope (governance layer SECOND)
        Inserts operator_agent_activation_log row with both tx hashes.

        Args:
            api_key:     Must match cfg.operator_api_key (full operator auth).
            bundle_path: Repo-relative or absolute path to Cedar bundle JSON.
                         Resolved against cfg.cedar_bundle_dir if relative.
            reason:      Operator audit string; minimum 10 characters.

        Returns:
            Dict shape of cedar_bundle_anchor.AnchorResult (success, agent_id,
            from_phase, to_phase, from_scope_root, to_scope_root, bundle_path,
            governance_tx_hash, operational_tx_hash, governance_block_number,
            operational_block_number, activation_log_id, error).

        Raises:
            HTTPException(401) on bad api_key.
            HTTPException(422) on missing bundle_path or reason < 10 chars.
            HTTPException(500) on bundle parse / chain failures.
        """
        check_key(api_key)
        check_rate(api_key)
        _bp = (bundle_path or "").strip()
        _reason = (reason or "").strip()
        if not _bp:
            raise HTTPException(422, "bundle_path is required (repo-relative or absolute)")
        if len(_reason) < 10:
            raise HTTPException(422, "reason must be at least 10 characters (operator audit field)")

        from ..cedar_bundle_anchor import CedarBundleAnchor, CedarBundleAnchorError
        from pathlib import Path as _Path
        anchor = CedarBundleAnchor(
            chain=chain,
            store=store,
            bundle_dir=_Path(getattr(cfg, "cedar_bundle_dir", "bridge/vapi_bridge/cedar_bundles")),
        )
        try:
            result = await anchor.anchor_bundle(
                bundle_path=_bp,
                reason_text=_reason,
                operator_api_key=api_key,
            )
        except CedarBundleAnchorError as e:
            raise HTTPException(500, f"anchor_bundle failed: {e}")

        # AnchorResult is a slots dataclass; serialize via __slots__ projection
        return {
            "success":                  result.success,
            "agent_id":                 result.agent_id,
            "from_phase":               result.from_phase,
            "to_phase":                 result.to_phase,
            "from_scope_root":          result.from_scope_root,
            "to_scope_root":            result.to_scope_root,
            "bundle_path":              result.bundle_path,
            "governance_tx_hash":       result.governance_tx_hash,
            "operational_tx_hash":      result.operational_tx_hash,
            "governance_block_number":  result.governance_block_number,
            "operational_block_number": result.operational_block_number,
            "activation_log_id":        result.activation_log_id,
            "error":                    result.error,
            "timestamp":                time.time(),
        }

    @app.get("/operator/operator-agent-activation-log")
    async def get_operator_agent_activation_log(
        x_api_key: str = Header(default=""),
        agent_id: str = Query(default=""),
        limit: int = Query(default=20, ge=1, le=200),
    ):
        """Phase O1 C1 — paginated activation history (read-only audit).

        Args:
            x_api_key: Read-key auth (match cfg.operator_api_key).
            agent_id:  Optional filter to specific Q9-frozen agentId. Empty
                       returns rows for all agents.
            limit:     1-200; default 20; most recent first by activated_at.
        """
        check_read_key(x_api_key)
        _aid = agent_id.strip() if agent_id else None
        rows = await asyncio.to_thread(
            store.get_operator_agent_activation_log,
            _aid,
            int(limit),
        )
        return {
            "agent_id_filter":  _aid,
            "limit":            int(limit),
            "row_count":        len(rows),
            "activations":      rows,
            "timestamp":        time.time(),
        }

    @app.get("/operator/operator-agent-shadow-log")
    async def get_operator_agent_shadow_log(
        x_api_key: str = Header(default=""),
        agent_id: str = Query(default=""),
        decision: str = Query(default=""),
        limit: int = Query(default=50, ge=1, le=500),
    ):
        """Phase O1 C2 — paginated shadow log + per-agent decision summary.

        Returns the most recent N Cedar evaluations across one agent or all,
        plus an aggregate decision-distribution summary for analysis.  Used
        by operator review of shadow-mode behavior + future FSCA rules.

        Args:
            x_api_key:  Read-key auth (match cfg.operator_api_key).
            agent_id:   Optional Q9-frozen agentId filter; empty = fleet.
            decision:   Optional CedarDecision filter (permit /
                        permit_with_shadow_constraint /
                        forbid_lane_violation / forbid_capability_inactive /
                        forbid_agent_not_principal / forbid_explicit_policy /
                        forbid_default_deny); empty = all decisions.
            limit:      1-500; default 50; most recent first by evaluated_at.
        """
        check_read_key(x_api_key)
        _aid = agent_id.strip() if agent_id else None
        _dec = decision.strip() if decision else None
        rows = await asyncio.to_thread(
            store.get_operator_agent_shadow_log,
            _aid,
            _dec,
            int(limit),
        )
        summary = await asyncio.to_thread(
            store.get_operator_agent_shadow_summary,
            _aid,
        )
        return {
            "agent_id_filter":  _aid,
            "decision_filter":  _dec,
            "limit":            int(limit),
            "row_count":        len(rows),
            "summary":          summary,
            "evaluations":      rows,
            "timestamp":        time.time(),
        }

    @app.get("/operator/mythos-findings")
    async def get_mythos_findings_endpoint(
        x_api_key: str = Header(default=""),
        variant: str = Query(default=""),
        severity: str = Query(default=""),
        unresolved_only: bool = Query(default=False),
        limit: int = Query(default=100, ge=1, le=500),
    ):
        """Phase O5-MYTHOS — current findings from mythos_finding_log.

        Returns all Mythos audit findings with optional filters.
        Used by the MythosWorkspace (/os/mythos) to render the 15-cell
        mission-control matrix.
        """
        check_read_key(x_api_key)
        try:
            rows = store.get_mythos_findings(
                variant=variant or None,
                severity=severity or None,
                unresolved_only=unresolved_only,
                limit=limit,
            )
            cadence = store.get_mythos_cadence_status()
            return {
                "findings": rows,
                "cadence": cadence,
                "timestamp": time.time(),
            }
        except Exception as exc:
            log.warning("get_mythos_findings_endpoint: %s", exc)
            return {"findings": [], "cadence": {}, "timestamp": time.time()}

    @app.get("/operator/operator-agent-drift-log")
    async def get_operator_agent_drift_log(
        x_api_key: str = Header(default=""),
        agent_id: str = Query(default=""),
        drift_type: str = Query(default=""),
        since_minutes: int = Query(default=0, ge=0, le=43200),
        limit: int = Query(default=50, ge=1, le=500),
    ):
        """Phase O1 C4 — paginated drift findings log + since-window filter.

        Returns the most recent N drift findings from operator_agent_drift_log
        across one agent or all, optionally filtered by drift_type and a
        time-since-now window. Used by operator review of accumulated drift
        events captured by the C4 auto-sweep scheduler.

        Args:
            x_api_key:      Read-key auth (match cfg.operator_api_key).
            agent_id:       Optional Q9-frozen agentId filter; empty = fleet.
            drift_type:     Optional filter — BUNDLE_HASH_DRIFT or
                            SCOPE_HASH_GOVERNANCE_DRIFT (INV-OPERATOR-AGENT-007
                            frozen literals); empty = all types.
            since_minutes:  0-43200 (0 = no time filter; 43200 = 30 days);
                            filters detected_at >= (now - since_minutes*60).
            limit:          1-500; default 50; most recent first.
        """
        check_read_key(x_api_key)
        _aid = agent_id.strip() if agent_id else None
        _dt = drift_type.strip() if drift_type else None
        rows = await asyncio.to_thread(
            store.get_operator_agent_drift_log,
            _aid,
            _dt,
            int(limit),
        )
        if since_minutes > 0:
            cutoff = time.time() - (since_minutes * 60)
            rows = [
                r for r in rows
                if float(r.get("detected_at", 0) or 0) >= cutoff
            ]
        return {
            "agent_id_filter":  _aid,
            "drift_type_filter": _dt,
            "since_minutes":    int(since_minutes),
            "limit":            int(limit),
            "row_count":        len(rows),
            "findings":         rows,
            "timestamp":        time.time(),
        }

    # Phase O2-DRAFT-REVIEW (2026-05-10) — operator review surface for drafts
    # produced by Sentry/Guardian/Curator at O2 SUGGEST. Closes the loop that
    # ends at the watcher's PHASE_O3_DISAGREEMENT_RATE_MAX +
    # PHASE_O3_FALSE_POSITIVE_RATE_MAX gates: without operator review,
    # operator_decision stays NULL and disagreement_rate / false_positive_rate
    # stay at 0.0 (no signal) forever, blocking O3 ACTING readiness.
    # ------------------------------------------------------------------
    @app.get("/operator/operator-agent-drafts")
    async def get_operator_agent_drafts(
        x_api_key: str = Header(default=""),
        agent_id: str = Query(default=""),
        decision: str = Query(default=""),
        since_minutes: int = Query(default=0, ge=0, le=43200),
        limit: int = Query(default=50, ge=1, le=500),
    ):
        """Phase O2-DRAFT-REVIEW — paginated draft browse + filter.

        Returns the most recent N drafts produced by Operator Initiative agents
        at O2 SUGGEST, optionally filtered by agent / operator_decision / time
        window. Used by the operator review surface (frontend dashboards) and
        by audit query tooling.

        Args:
            x_api_key:      Read-key auth (match cfg.operator_api_key).
            agent_id:       Optional Q9-frozen agentId filter; empty = trio.
            decision:       Optional filter — '', 'unreviewed' (NULL),
                            'accept', 'reject', 'overturn_curator'. Empty
                            string returns all decisions including NULL.
                            'unreviewed' translates to NULL filter at store.
            since_minutes:  0-43200 (0 = no time filter; 43200 = 30 days);
                            filters created_at >= (now - since_minutes*60).
            limit:          1-500; default 50; most recent first.
        """
        check_read_key(x_api_key)
        _aid = agent_id.strip() if agent_id else None
        _dec_raw = decision.strip() if decision else ""
        _since = int(since_minutes) * 60 if since_minutes > 0 else None

        # Phase O2-DRAFT-REVIEW: store.get_operator_agent_drafts uses
        # keyword-only args (per Phase O2-DRAFT-GENERATION Sentry signature
        # discipline) -- wrap in lambda for asyncio.to_thread positional arg.
        if _dec_raw == "unreviewed":
            # Special-case: 'unreviewed' means operator_decision IS NULL.
            # The store helper filters on a non-NULL value, so we fetch
            # ALL and filter in-memory (small volume; capped at 500).
            rows_all = await asyncio.to_thread(
                lambda: store.get_operator_agent_drafts(
                    agent_id=_aid,
                    decision=None,
                    since_seconds=_since,
                    limit=int(limit) * 4,
                )
            )
            rows = [r for r in rows_all if r.get("operator_decision") is None][: int(limit)]
            _dec_filter = "unreviewed"
        elif _dec_raw in ("accept", "reject", "overturn_curator"):
            rows = await asyncio.to_thread(
                lambda: store.get_operator_agent_drafts(
                    agent_id=_aid,
                    decision=_dec_raw,
                    since_seconds=_since,
                    limit=int(limit),
                )
            )
            _dec_filter = _dec_raw
        else:
            rows = await asyncio.to_thread(
                lambda: store.get_operator_agent_drafts(
                    agent_id=_aid,
                    decision=None,
                    since_seconds=_since,
                    limit=int(limit),
                )
            )
            _dec_filter = None

        return {
            "agent_id_filter":  _aid,
            "decision_filter":  _dec_filter,
            "since_minutes":    int(since_minutes),
            "limit":            int(limit),
            "row_count":        len(rows),
            "drafts":           rows,
            "timestamp":        time.time(),
        }

    @app.post("/operator/operator-agent-draft-review")
    async def post_operator_agent_draft_review(
        draft_id: int = Query(...),
        decision: str = Query(...),
        reason: str = Query(default=""),
        api_key: str = Query(default=""),
    ):
        """Phase O2-DRAFT-REVIEW — record operator decision on a draft.

        Full operator authorization (api_key as query param matches
        cfg.operator_api_key). reason MUST be ≥10 characters (audit gate).

        decision MUST be one of:
          - 'accept'           — operator confirms agent's draft
          - 'reject'           — operator rejects agent's draft
                                 (feeds disagreement_rate numerator)
          - 'overturn_curator' — Curator-specific; operator reverses
                                 a marketplace verdict
                                 (feeds false_positive_rate numerator;
                                  ZERO TOLERANCE per Curator's
                                  PHASE_O3_FALSE_POSITIVE_RATE_MAX=0.0)

        Idempotent on same decision; allows revision (operator may
        revise their own review). Returns updated draft state.

        Returns:
            200 + JSON on success
            401 if api_key missing/wrong (full-auth)
            422 if reason <10 chars or decision invalid
            404 if draft_id not found
        """
        check_key(api_key)
        import time as _trv

        if decision not in ("accept", "reject", "overturn_curator"):
            raise HTTPException(
                status_code=422,
                detail=(
                    "decision must be one of 'accept' | 'reject' | "
                    "'overturn_curator'"
                ),
            )
        if len(reason.strip()) < 10:
            raise HTTPException(
                status_code=422,
                detail=(
                    "reason must be at least 10 characters "
                    "(e.g., 'verdict reversed after re-checking anchor freshness')"
                ),
            )

        # Phase O2-DRAFT-REVIEW: kwargs-only store helper -- lambda wrap.
        ok = await asyncio.to_thread(
            lambda: store.record_operator_decision(
                draft_id=int(draft_id),
                decision=str(decision),
                reason=str(reason),
            )
        )
        if not ok:
            raise HTTPException(
                status_code=404,
                detail=f"draft_id {draft_id} not found",
            )

        # Surface updated row to the caller for confirmation
        rows = await asyncio.to_thread(
            lambda: store.get_operator_agent_drafts(
                agent_id=None,
                decision=None,
                since_seconds=None,
                limit=500,
            )
        )
        updated = next(
            (r for r in rows if int(r.get("id", 0)) == int(draft_id)),
            None,
        )

        # Phase O5-MLGA Stage 7: AGENT-REVIEW-v1 autonomous emission.
        # Fires after the decision persists. Fail-open: any failure logs
        # internally + does NOT affect the operator's response. Run in
        # a worker thread so we don't block the asyncio loop on the
        # compile + sqlite write.
        try:
            from ..agent_review_emitter import emit_agent_review_for_draft
            await asyncio.to_thread(
                emit_agent_review_for_draft,
                store=store, cfg=cfg, draft_id=int(draft_id),
            )
        except Exception as _arv_exc:  # noqa: BLE001
            log.warning(
                "AGENT-REVIEW emit hook failed (non-fatal): %s", _arv_exc,
            )

        return {
            "accepted":   True,
            "draft_id":   int(draft_id),
            "decision":   decision,
            "reason":     reason,
            "row":        updated,
            "timestamp":  _trv.time(),
        }

    @app.get("/operator/fleet-readiness-root")
    async def get_fleet_readiness_root(
        x_api_key: str = Header(default=""),
    ):
        """Phase O1-FRR — Fleet Readiness Root primitive (eighth FROZEN-v1).

        Computes current FRR over all three Operator Initiative agents
        (Sentry+Guardian+Curator) using the FROZEN-v1 pre-image:

            b"VAPI-FRR-v1" (11B) || sorted_by_agent_id_bytes(
                agent_id_be(32) || phase_code(1)
            ) for each agent || ts_ns_be(8)
            -> SHA-256 -> 32B

        Returns the FRR commitment + per-agent phase resolution + the
        FleetAdvancementSummary state (fleet_phase_aligned,
        next_alignment_target, etc.).  Computation is fail-open:
        any underlying error returns the result with error fields
        populated (caller inspects .error).

        Used by:
          - Frontend dashboards (operator-facing fleet state)
          - Downstream contracts that wish to reference FRR (once
            on-chain getFleetReadinessRoot() ships in follow-up phase)
          - Operator audit (verify FRR baseline accumulating correctly
            across watcher cycles via operator_initiative_advancement_log)

        Args:
            x_api_key: Read-key auth (match cfg.operator_api_key).
        """
        check_read_key(x_api_key)
        from ..operator_initiative_advancement import evaluate_frr_sync
        summary, frr = await asyncio.to_thread(
            evaluate_frr_sync, cfg=cfg, store=store,
        )
        per_agent_dump = [
            {
                "agent_id":                          a.agent_id,
                "current_phase":                     a.current_phase,
                "shadow_age_hours":                  round(a.shadow_age_hours, 2),
                "cedar_eval_count":                  a.cedar_eval_count,
                "bundle_hash_drift_count_30d":       a.bundle_hash_drift_count_30d,
                "scope_hash_governance_drift_count_30d": a.scope_hash_governance_drift_count_30d,
                "o2_ready":                          a.o2_ready,
                "o2_blockers":                       list(a.o2_blockers),
                "o3_ready":                          a.o3_ready,
                "o3_blockers":                       list(a.o3_blockers),
                "error":                             a.error,
            }
            for a in summary.per_agent
        ]
        return {
            "frr_hex":                  frr.frr_hex,
            "frr_ts_ns":                frr.ts_ns,
            "frr_error":                frr.error,
            "fleet_phase_aligned":      bool(summary.fleet_phase_aligned),
            "fleet_size":               int(summary.fleet_size),
            "fleet_at_o1_count":        int(summary.fleet_at_o1_count),
            "fleet_at_o2_ready_count":  int(summary.fleet_at_o2_ready_count),
            "fleet_at_o3_ready_count":  int(summary.fleet_at_o3_ready_count),
            "next_alignment_target":    summary.next_alignment_target,
            "summary_error":            summary.error,
            "per_agent":                per_agent_dump,
            "agents_in_frr":            [
                {"name": name, "agent_id_hex": id_hex, "phase_code": phase_code}
                for name, id_hex, phase_code in frr.agents
            ],
            "domain_tag":               "VAPI-FRR-v1",
            "timestamp":                time.time(),
        }

    @app.get("/operator/operator-initiative-advancement-log")
    async def get_operator_initiative_advancement_log(
        x_api_key: str = Header(default=""),
        limit: int = Query(default=50, ge=1, le=500),
    ):
        """Phase O1-FRR — paginated advancement_log (FRR baseline history).

        Returns the most recent N rows from
        operator_initiative_advancement_log, capturing each watcher
        cycle's evaluation + FRR commitment.  Used by operator to:
          - Inspect FRR drift over time (each row is a 32B commitment)
          - Verify watcher cadence is operating (1h cadence by default
            when OPERATOR_INITIATIVE_ADVANCEMENT_ENABLED=true)
          - Audit fleet phase alignment history

        Args:
            x_api_key: Read-key auth.
            limit:     1-500; default 50; most recent first by timestamp.
        """
        check_read_key(x_api_key)
        rows = await asyncio.to_thread(
            store.get_operator_initiative_advancement_history,
            int(limit),
        )
        return {
            "limit":     int(limit),
            "row_count": len(rows),
            "rows":      rows,
            "timestamp": time.time(),
        }

    @app.post("/operator/evaluate-agent-action")
    async def evaluate_agent_action_endpoint(
        api_key: str = Query(...),
        agent_id: str = Query(...),
        action: str = Query(...),
        resource: str = Query(...),
        reason: str = Query(...),
        shadow_mode: bool = Query(default=True),
        draft_payload_hash: str = Query(default=""),
    ):
        """Phase O1 C2 — operator-triggered Cedar evaluation (synthetic, audit).

        Full operator auth (api_key as Query, not Header — same pattern as
        /operator/anchor-cedar-bundle).  reason MUST be ≥10 chars (audit
        gate).

        Returns the ShadowEvalResult shape PLUS the persisted shadow_log row.
        Used by operator to:
          - Test that bundles are correctly mapped + parseable
          - Probe specific (action, resource) combinations against current
            policy bundle without waiting for real agent activity
          - Generate baseline shadow log entries for FSCA rule validation
        """
        # Fail closed when no key is configured (empty default would otherwise
        # let an empty api_key pass `"" != ""` → False). Use a constant-time
        # compare to avoid a timing oracle on the operator key.
        if not cfg.operator_api_key:
            raise HTTPException(status_code=503, detail="Operator API not configured")
        if not hmac.compare_digest(api_key, cfg.operator_api_key):
            raise HTTPException(status_code=403, detail="invalid api_key")
        if len(reason.strip()) < 10:
            raise HTTPException(
                status_code=422,
                detail="reason must be ≥10 chars (audit gate)",
            )
        from ..cedar_shadow_runtime import evaluate_agent_action
        result = await evaluate_agent_action(
            agent_id=agent_id,
            action=action,
            resource=resource,
            context={"shadow_mode": shadow_mode},
            draft_payload_hash=draft_payload_hash,
            source="operator_endpoint",
            cfg=cfg,
            store=store,
        )
        return {
            "agent_id":               result.agent_id,
            "action":                 result.action,
            "resource":               result.resource,
            "decision":               result.decision.value,
            "is_permit":              result.is_permit,
            "bundle_merkle_root":     result.bundle_merkle_root_hex,
            "bundle_path":            result.bundle_path,
            "shadow_log_row_id":      result.shadow_log_row_id,
            "error":                  result.error,
            "reason":                 reason.strip(),
            "timestamp":              time.time(),
        }

    # Phase O4-VPM-INT follow-up — HTTP endpoint surface for the
    # 6 wallet-free audit scripts shipped in the session arc closing
    # at HEAD 1bbf163f. Three highest-frontend-value audits exposed
    # here for Operator Console dashboard consumption (G7 graduation
    # readiness chip + CFSS lane authority continuous monitor +
    # Curator graduation consolidated readiness).
    #
    # Each endpoint: read-key auth via x-api-key Header; offloads the
    # underlying audit's sweep_once / run_audit function to a worker
    # thread via asyncio.to_thread (keeps the event loop responsive
    # under live frontend polling load per the Phase 235-STAB pattern).

    @app.get("/operator/g7-curator-readiness")
    async def get_g7_curator_readiness(
        x_api_key: str = Header(default=""),
    ):
        """G7 Curator Review Readiness audit — wallet-free read-only.

        Exposes the same payload as scripts/g7_curator_review_readiness
        _audit.py via HTTP. Reports the gate's verdict across 5
        sections (curator presence / 7-day window counts / last-N
        breakdown / gate evaluation / ZERO TOLERANCE invariant).
        """
        check_read_key(x_api_key)
        try:
            import importlib.util
            import sys as _sys
            from pathlib import Path as _Path
            _proj = repo_root
            if str(_proj / "scripts") not in _sys.path:
                _sys.path.insert(0, str(_proj / "scripts"))
            _spec = importlib.util.spec_from_file_location(
                "g7_audit_ep",
                _proj / "scripts" / "g7_curator_review_readiness_audit.py",
            )
            _mod = importlib.util.module_from_spec(_spec)
            _sys.modules["g7_audit_ep"] = _mod
            _spec.loader.exec_module(_mod)
        except Exception as exc:
            raise HTTPException(
                status_code=500,
                detail=f"g7_audit import failed: {exc}",
            )
        db_path = _Path(getattr(cfg, "db_path", "bridge/vapi_store.db"))
        report, exit_code = await asyncio.to_thread(_mod.run_audit, db_path)
        report["http_exit_code"] = exit_code
        report["timestamp"] = time.time()
        return report

    @app.get("/operator/cfss-lane-drift-status")
    async def get_cfss_lane_drift_status(
        x_api_key: str = Header(default=""),
    ):
        """CFSS Cedar v2 lane authority drift status — wallet-free.

        Exposes the same payload as scripts/cfss_lane_drift_sweep.py.
        Reports per-row matrix evaluation + verdict (PASS / CFSS_
        VIOLATION / BUNDLE_LOAD_ERROR). Companion to the runtime
        sweeper shipped at be53cd3c — frontend can poll this for the
        operator console's CFSS chip without polling the FSCA log.
        """
        check_read_key(x_api_key)
        try:
            import importlib.util
            import sys as _sys
            from pathlib import Path as _Path
            _proj = repo_root
            if str(_proj / "scripts") not in _sys.path:
                _sys.path.insert(0, str(_proj / "scripts"))
            _spec = importlib.util.spec_from_file_location(
                "cfss_audit_ep",
                _proj / "scripts" / "cfss_lane_drift_sweep.py",
            )
            _mod = importlib.util.module_from_spec(_spec)
            _sys.modules["cfss_audit_ep"] = _mod
            _spec.loader.exec_module(_mod)
        except Exception as exc:
            raise HTTPException(
                status_code=500,
                detail=f"cfss_audit import failed: {exc}",
            )
        bundle_dir = vapi_bridge_dir / "cedar_bundles"
        report = await asyncio.to_thread(_mod.sweep_once, bundle_dir)
        report["timestamp"] = time.time()
        return report


