"""Miscellaneous operator API routes (D-DECON-2 operator_api residue #21).

Register-function split: chat, calibration, federation, config, epoch-window,
enrollment, ceremony, and related leftovers per decon-store-map.md agent_misc.
"""
from __future__ import annotations

import asyncio
import hashlib
import json as _json
import logging
import os
import time
from pathlib import Path
from typing import Callable

from fastapi import FastAPI, Header, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

log = logging.getLogger(__name__)


class AgentRequest(BaseModel):
    """Request body for POST /agent."""

    session_id: str
    message: str


class LLMChatMessage(BaseModel):
    role: str
    content: str


class LLMChatRequest(BaseModel):
    messages: list[LLMChatMessage]
    model: str = "deepseek-v4-flash"


class LocalToolExecuteRequest(BaseModel):
    tool: str
    arguments: dict


class FederationSignalRequest(BaseModel):
    """Request body for POST /federation/threat-signal (Phase 80)."""

    device_id: str
    commitment_hash: str
    circuit_id: str = ""
    source_peer: str = "unknown"


def register_agent_misc_routes(
    app: FastAPI,
    *,
    cfg,
    store,
    chain,
    bus,
    get_agent: Callable,
    get_calib_agent: Callable,
    check_key: Callable[[str], None],
    check_rate: Callable[[str], None],
    check_read_key: Callable[[str], None],
    repo_root: Path,
) -> None:
    """Register chat, federation, calibration, config, and remaining agent routes."""

    @app.post("/agent")
    def agent_chat(
        req: AgentRequest,
        api_key: str = Query(..., description="Shared operator API key"),
    ):
        """Conversational AI agent for natural-language protocol queries (Phase 30).

        Requires OPERATOR_API_KEY. Uses Claude to reason over real bridge data
        via tool_use. Session history is preserved in SQLite by session_id (Phase 31).

        Requires: pip install anthropic (503 if not installed).
        """
        check_key(api_key)
        check_rate(api_key)
        try:
            return get_agent().ask(req.session_id, req.message)
        except ImportError:
            raise HTTPException(
                503, "anthropic package not installed (pip install anthropic)"
            )
        except Exception as exc:
            log.error("BridgeAgent error: %s", exc)
            raise HTTPException(500, f"Agent error: {exc}")

    @app.post("/agent/llm-chat")
    def agent_llm_chat(
        req: LLMChatRequest,
        api_key: str = Query(..., description="Shared operator API key"),
    ):
        """Conversational QuickSilver Pro AI agent chat."""
        check_key(api_key)
        check_rate(api_key)
        try:
            msgs = [{"role": m.role, "content": m.content} for m in req.messages]
            
            # If no system prompt is present, insert one
            has_system = any(m.get("role") == "system" for m in msgs)
            if not has_system:
                system_prompt = (
                    "You are a helpful assistant for the QorTroller V.A.P.I. (Verifiable Autonomous Physical Intelligence) protocol. "
                    "Here is the context of the project to prevent hallucinations:\n"
                    "QorTroller is the reference implementation of V.A.P.I., a DePIN (Decentralized Physical Infrastructure) sub-category "
                    "for competitive gaming. In QorTroller's case, gamers and their controllers (specifically the Sony DualShock Edge CFI-ZCP1) "
                    "produce physical telemetry data and own that data. It generates a 228-byte Proof of Autonomous Cognition (PoAC) record "
                    "per cognition cycle, anchored on IoTeX L1, to cryptographically prove liveness and prevent botting/cheating. "
                    "It is NOT a DeFi lending protocol or risk management Comptroller. Answer questions concisely using this context."
                )
                msgs.insert(0, {"role": "system", "content": system_prompt})

            from ..vapi_llm_client import QorTrollerAI
            ai = QorTrollerAI()
            resp = ai.chat(msgs, model=req.model)
            return {"response": resp}
        except Exception as exc:
            log.error("LLM Chat error: %s", exc)
            raise HTTPException(500, f"LLM Chat error: {exc}")

    @app.post("/agent/local-host/execute")
    def agent_local_host_execute(
        req: LocalToolExecuteRequest,
        api_key: str = Query(..., description="Shared operator API key"),
    ):
        """Execute local repository operations to support the frontend autonomous LLM agent."""
        check_key(api_key)
        check_rate(api_key)
        
        # Get absolute repository root directory path
        repo_root_str = str(repo_root)
        tool_name = req.tool
        args = req.arguments
        
        try:
            if tool_name == "list_files":
                file_list = []
                for root, dirs, files in os.walk(repo_root_str):
                    # Prune ignore patterns
                    dirs[:] = [d for d in dirs if d not in (".git", "node_modules", "dist", "__pycache__", ".venv", "build")]
                    for file in files:
                        rel_path = os.path.relpath(os.path.join(root, file), repo_root_str)
                        file_list.append(rel_path.replace("\\", "/"))
                # Return list capped at 300 files
                return {"result": file_list[:300]}
                
            elif tool_name == "read_file":
                path = args.get("path", "")
                if not path:
                    return {"result": "Error: path parameter is required"}
                repo_root_norm = os.path.normpath(repo_root_str)
                safe_path = os.path.normpath(os.path.join(repo_root_norm, path))
                # Containment check must use commonpath, NOT startswith: a bare
                # prefix test admits sibling dirs whose name extends the root
                # (e.g. "../QorTroller-secret/..." resolves outside the repo but
                # still startswith("/home/user/QorTroller")).
                if os.path.commonpath([safe_path, repo_root_norm]) != repo_root_norm:
                    return {"result": "Error: Access denied (path traversal outside workspace)"}
                if not os.path.exists(safe_path) or os.path.isdir(safe_path):
                    return {"result": "Error: File not found or is a directory"}
                    
                with open(safe_path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                return {"result": content[:12000]}
                
            elif tool_name == "git_history":
                import subprocess
                res = subprocess.run(
                    ["git", "log", "-n", "10", "--oneline"],
                    cwd=repo_root_str,
                    capture_output=True,
                    text=True
                )
                if res.returncode == 0:
                    return {"result": res.stdout}
                else:
                    return {"result": f"Error running git log: {res.stderr}"}
            else:
                return {"result": f"Error: Unknown tool {tool_name}"}
        except Exception as e:
            log.error("Local tool execution error: %s", e)
            return {"result": f"Error executing local tool: {str(e)}"}

    @app.get("/agent/stream")
    async def agent_stream(
        session_id: str,
        message: str,
        api_key: str = Query(..., description="Shared operator API key"),
    ):
        """Streaming BridgeAgent via Server-Sent Events (Phase 31).

        Events (text/event-stream):
          {"type": "text_delta", "text": str}        — incremental response text
          {"type": "tool_start", "tool": str}        — agent invoking a bridge tool
          {"type": "tool_result", "tool": str, "preview": str}
          {"type": "done", "tools_used": list[str]}  — stream complete
          {"type": "error", "message": str}          — non-fatal error

        Requires: pip install anthropic (error event if not installed).
        """
        check_key(api_key)
        check_rate(api_key)
        ag = get_agent()

        async def _generate():
            try:
                async for event in ag.stream_ask(session_id, message):
                    yield f"data: {_json.dumps(event)}\n\n"
            except ImportError:
                yield f"data: {_json.dumps({'type': 'error', 'message': 'anthropic not installed'})}\n\n"
            except Exception as exc:
                log.error("agent stream error: %s", exc)
                yield f"data: {_json.dumps({'type': 'error', 'message': str(exc)})}\n\n"

        return StreamingResponse(
            _generate(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    @app.get("/insights")
    def get_insights(
        limit: int = 20,
        api_key: str = Query(..., description="Shared operator API key"),
    ):
        """Return most recent proactive protocol insights (Phase 32).

        Returns insights DESC by created_at. Max limit=100.
        Includes anomaly reactions (from react()), cluster alerts, trajectory flags,
        and eligibility horizon notifications — all generated by ProactiveMonitor.
        """
        check_key(api_key)
        check_rate(api_key)
        return store.get_recent_insights(limit=min(limit, 100))

    @app.get("/federation/clusters")
    def federation_clusters(
        limit: int = 50,
        api_key: str = Query(..., description="Shared operator API key"),
    ):
        """Return locally-detected clusters shared with the federation (Phase 34).

        Only returns is_local=True records to prevent echo amplification when
        peers query this endpoint. Max limit=200.
        """
        check_key(api_key)
        check_rate(api_key)
        return store.get_federation_clusters(limit=min(limit, 200), is_local=True)

    @app.get("/digest")
    def get_digest(
        window: str = "all",
        api_key: str = Query(..., description="Shared operator API key"),
    ):
        """Return synthesized longitudinal insight digests (Phase 35).

        window: '24h', '7d', '30d', or 'all' (default) for all windows.
        Also returns device risk trajectory labels (stable/warming/critical/cleared).
        """
        check_key(api_key)
        check_rate(api_key)
        if window == "all":
            digests = store.get_all_latest_digests()
        elif window in ("24h", "7d", "30d"):
            d = store.get_latest_digest(window)
            digests = [d] if d else []
        else:
            raise HTTPException(status_code=400, detail="window must be '24h', '7d', '30d', or 'all'")
        return {
            "digests":          digests,
            "critical_devices": store.get_devices_by_risk_label("critical"),
            "warming_devices":  store.get_devices_by_risk_label("warming"),
            "synthesis_available": len(digests) > 0,
        }

    @app.post("/calibration/agent")
    def calibration_agent_chat(
        req: AgentRequest,
        api_key: str = Query(..., description="Shared operator API key"),
    ):
        """CalibrationIntelligenceAgent — non-streaming calibration queries (Phase 50).

        Requires OPERATOR_API_KEY. Uses Claude to reason over calibration data
        via 6 specialist tools. Session history is persisted by session_id.
        """
        check_key(api_key)
        check_rate(api_key)
        try:
            return get_calib_agent().ask(req.session_id, req.message)
        except ImportError:
            raise HTTPException(
                503, "anthropic package not installed (pip install anthropic)"
            )
        except Exception as exc:
            log.error("CalibrationIntelligenceAgent error: %s", exc)
            raise HTTPException(500, f"Calibration agent error: {exc}")

    @app.get("/calibration/stream")
    async def calibration_agent_stream(
        session_id: str,
        message: str,
        api_key: str = Query(..., description="Shared operator API key"),
    ):
        """CalibrationIntelligenceAgent SSE streaming endpoint (Phase 50).

        Events (text/event-stream): same format as /agent/stream.
        """
        check_key(api_key)
        check_rate(api_key)
        ag = get_calib_agent()

        async def _generate():
            try:
                async for event in ag.stream_ask(session_id, message):
                    yield f"data: {_json.dumps(event)}\n\n"
            except ImportError:
                yield f"data: {_json.dumps({'type': 'error', 'message': 'anthropic not installed'})}\n\n"
            except Exception as exc:
                log.error("calibration stream error: %s", exc)
                yield f"data: {_json.dumps({'type': 'error', 'message': str(exc)})}\n\n"

        return StreamingResponse(
            _generate(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    @app.get("/enforcement")
    def get_enforcement(
        device_id: str = "",
        api_key: str = Query(..., description="Shared operator API key"),
    ):
        """Return credential enforcement state (Phase 37).

        device_id provided: returns enforcement state for that specific device.
        device_id omitted:  returns all currently suspended credentials.

        Response includes enforcement_enabled and min_consecutive_windows
        configuration values so callers can understand the policy settings.
        """
        check_key(api_key)
        check_rate(api_key)
        if device_id.strip():
            row = store.get_credential_enforcement(device_id.strip())
            suspended_devices = [row] if row else []
        else:
            suspended_devices = store.get_all_suspended_credentials()
        return {
            "suspended_count":         len([d for d in suspended_devices if d.get("suspended")]),
            "suspended_devices":       [d for d in suspended_devices if d.get("suspended")],
            "enforcement_enabled":     bool(getattr(cfg, "phg_credential_enforcement_enabled", True)),
            "min_consecutive_windows": int(getattr(cfg, "credential_enforcement_min_consecutive", 2)),
        }

    @app.get("/agent/validation-stats")
    def get_validation_stats(
        api_key: str = Query(..., description="Shared operator API key"),
    ):
        """Unified validation statistics across all three autonomous agents (Phase 70).

        Returns:
          proof_stats:    ZKVerifier proof acceptance/rejection/timeout counts
          enrollment:     Device pipeline counts (eligible/in_progress/unenrolled)
          curator_stats:  DataCuratorAgent lineage + oracle publication counts
          ruling_stats:   RulingEnforcementAgent streak totals
        """
        check_key(api_key)
        check_rate(api_key)

        # ZK proof stats
        proof_stats = {"enabled": False}
        try:
            from ..chain import ChainClient
            _ch = ChainClient.__new__(ChainClient)
            _ch._zk_verifier = getattr(cfg, "_zk_verifier_instance", None)
            if hasattr(_ch, "get_zk_verifier_stats"):
                proof_stats = _ch.get_zk_verifier_stats()
        except Exception:
            pass  # fail-open: M-1 cleanup 2026-05-16 — intentional silent skip

        # Enrollment pipeline
        enrollment = {"eligible": 0, "in_progress": 0, "unenrolled": 0}
        try:
            all_enr = store.get_all_enrollments() if hasattr(store, "get_all_enrollments") else []
            for e in all_enr:
                st = e.get("status", "unenrolled")
                if st == "eligible":
                    enrollment["eligible"] += 1
                elif st in ("enrolled", "in_progress"):
                    enrollment["in_progress"] += 1
                else:
                    enrollment["unenrolled"] += 1
        except Exception:
            pass  # fail-open: M-1 cleanup 2026-05-16 — intentional silent skip

        # DataCuratorAgent stats from store tables
        curator_stats = {"lineage_count": 0, "oracle_publications": 0, "eligible_devices": 0}
        try:
            with store._conn() as conn:
                row = conn.execute("SELECT COUNT(*) as cnt FROM data_lineage").fetchone()
                curator_stats["lineage_count"] = row["cnt"] if row else 0
                row = conn.execute("SELECT COUNT(*) as cnt FROM oracle_publications").fetchone()
                curator_stats["oracle_publications"] = row["cnt"] if row else 0
                row = conn.execute("SELECT COUNT(*) as cnt FROM token_eligibility WHERE eligibility_score > 0").fetchone()
                curator_stats["eligible_devices"] = row["cnt"] if row else 0
        except Exception:
            pass  # fail-open: M-1 cleanup 2026-05-16 — intentional silent skip

        # Ruling enforcement stats
        ruling_stats = {"total_rulings": 0, "block_rulings": 0, "active_suspensions": 0}
        try:
            with store._conn() as conn:
                row = conn.execute("SELECT COUNT(*) as cnt FROM agent_rulings").fetchone()
                ruling_stats["total_rulings"] = row["cnt"] if row else 0
                row = conn.execute("SELECT COUNT(*) as cnt FROM agent_rulings WHERE verdict='BLOCK'").fetchone()
                ruling_stats["block_rulings"] = row["cnt"] if row else 0
                row = conn.execute(
                    "SELECT COUNT(*) as cnt FROM credential_enforcement "
                    "WHERE suspended=1 AND reinstated=0"
                ).fetchone()
                ruling_stats["active_suspensions"] = row["cnt"] if row else 0
        except Exception:
            pass  # fail-open: M-1 cleanup 2026-05-16 — intentional silent skip

        return {
            "proof_stats":   proof_stats,
            "enrollment":    enrollment,
            "curator_stats": curator_stats,
            "ruling_stats":  ruling_stats,
            "timestamp":     time.time(),
        }

    @app.get("/agent/validation-gate")
    def get_validation_gate(
        api_key: str = Query(..., description="Shared operator API key"),
    ):
        """Dry-run safety gate status from SessionAdjudicatorValidationAgent (Phase 75).

        Returns consecutive_clean count, divergence_count, gate_n, gate_passed, and
        recommended_action. When gate_passed=True, the operator can safely set
        AGENT_DRY_RUN=false via POST /agent/config to enable live enforcement.
        """
        check_key(api_key)
        check_rate(api_key)
        gate_n = int(getattr(cfg, "validation_gate_n", 100))
        max_rate = float(getattr(cfg, "validation_max_divergence_rate", 1.0))
        return store.get_validation_gate_status(gate_n, max_rate)

    # --- Phase 76: Ruling provenance anchor ---

    @app.get("/agent/ruling-provenance/{ruling_id}")
    def get_ruling_provenance(
        ruling_id: int,
        api_key: str = Query(..., description="Shared operator API key"),
    ):
        """Retrieve the provenance anchor for a specific ruling (Phase 76).

        Returns the SHA-256 provenance hash that binds the ruling commitment,
        ceremony integrity data, and evidence set into a single verifiable anchor.
        Returns 404 if the ruling has not yet been anchored.
        """
        check_key(api_key)
        check_rate(api_key)
        anchor = store.get_provenance_anchor(ruling_id)
        if anchor is None:
            from fastapi import Response as _Resp
            from fastapi.responses import JSONResponse as _JSONResp
            return _JSONResp(
                status_code=404,
                content={"error": "Provenance anchor not yet computed", "ruling_id": ruling_id},
            )
        return anchor

    # --- Phase 72: PHGCredential bridge-layer multi-sig suspension ---

    @app.post("/operator/suspension/propose")
    def suspension_propose(
        device_id: str,
        evidence_hash: str,
        duration_s: int,
        api_key: str = Query(..., description="Shared operator API key"),
    ):
        """Propose a PHGCredential suspension for device_id (Phase 72).

        Inserts a pending suspension proposal. Returns proposal_id.
        When suspension_multisig_threshold=1 (default), a single call to
        /operator/suspension/execute/{id} is sufficient.
        When threshold=2, a second /operator/suspension/confirm/{id} call is
        required (from a second operator key) before execute proceeds on-chain.

        NOTE: PHGCredential.bridge is immutable — this is a software safeguard,
        not cryptographic enforcement. Key separation must be operational.
        """
        check_key(api_key)
        check_rate(api_key)
        if duration_s <= 0:
            raise HTTPException(status_code=400, detail="duration_s must be positive")
        proposal_id = store.propose_suspension(
            device_id=device_id,
            evidence_hash=evidence_hash,
            duration_s=duration_s,
            proposed_by=hashlib.sha256(api_key.encode()).hexdigest()[:16],
        )
        log.info(
            "suspension proposed: device=%s proposal_id=%d threshold=%d",
            device_id[:16], proposal_id, cfg.suspension_multisig_threshold,
        )
        return {
            "proposal_id": proposal_id,
            "device_id": device_id,
            "duration_s": duration_s,
            "threshold": cfg.suspension_multisig_threshold,
            "confirmations": 0,
            "status": "proposed",
        }

    @app.post("/operator/suspension/confirm/{proposal_id}")
    def suspension_confirm(
        proposal_id: int,
        api_key: str = Query(..., description="Shared operator API key"),
    ):
        """Confirm a pending suspension proposal (Phase 72).

        Increments the confirmation counter. When confirmations reach
        suspension_multisig_threshold, the proposal becomes executable via
        POST /operator/suspension/execute/{proposal_id}.
        """
        check_key(api_key)
        check_rate(api_key)
        try:
            confirmations = store.confirm_suspension(proposal_id)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        threshold = cfg.suspension_multisig_threshold
        ready = confirmations >= threshold
        log.info(
            "suspension confirmed: proposal_id=%d confirmations=%d/%d ready=%s",
            proposal_id, confirmations, threshold, ready,
        )
        return {
            "proposal_id": proposal_id,
            "confirmations": confirmations,
            "threshold": threshold,
            "ready_to_execute": ready,
        }

    @app.post("/operator/suspension/execute/{proposal_id}")
    async def suspension_execute(
        proposal_id: int,
        api_key: str = Query(..., description="Shared operator API key"),
    ):
        """Execute a confirmed suspension proposal on-chain (Phase 72).

        Calls PHGCredential.suspend() only if proposal.confirmations >= threshold.
        Returns tx_hash on success. If threshold not met, returns 400.

        NOTE: Requires chain client to be live (BRIDGE_PRIVATE_KEY configured).
        """
        check_key(api_key)
        check_rate(api_key)
        proposal = store.get_suspension_proposal(proposal_id)
        if not proposal:
            raise HTTPException(status_code=404, detail=f"Proposal {proposal_id} not found")
        if proposal["executed"]:
            raise HTTPException(status_code=400, detail="Proposal already executed")
        if proposal["expires_at"] < time.time():
            raise HTTPException(status_code=400, detail="Proposal expired")
        threshold = cfg.suspension_multisig_threshold
        if proposal["confirmations"] < threshold:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Insufficient confirmations: {proposal['confirmations']}/{threshold}. "
                    "Call POST /operator/suspension/confirm/{proposal_id} first."
                ),
            )
        # Threshold met — execute on-chain
        if chain is None:
            raise HTTPException(
                status_code=503,
                detail="Chain client not available — BRIDGE_PRIVATE_KEY not configured",
            )
        try:
            evidence_bytes = bytes.fromhex(
                proposal["evidence_hash"].replace("0x", "").ljust(64, "0")
            )[:32]
            tx_hash = await chain.suspend_phg_credential(
                proposal["device_id"],
                evidence_bytes,
                proposal["duration_s"],
            )
        except Exception as exc:
            log.error("suspension execute failed: proposal_id=%d err=%s", proposal_id, exc)
            raise HTTPException(status_code=500, detail=f"On-chain suspension failed: {exc}") from exc
        store.mark_suspension_executed(proposal_id, tx_hash or "")
        log.info(
            "suspension executed on-chain: proposal_id=%d device=%s tx=%s",
            proposal_id, proposal["device_id"][:16], (tx_hash or "")[:16],
        )
        return {
            "proposal_id": proposal_id,
            "device_id": proposal["device_id"],
            "tx_hash": tx_hash or "",
            "duration_s": proposal["duration_s"],
            "status": "executed",
        }

    # --- Phase 80: Federation endpoints ---

    @app.post("/federation/threat-signal")
    async def federation_receive_signal(
        body: FederationSignalRequest,
        api_key: str = Query(..., description="Shared federation API key"),
    ):
        """Receive a federation threat signal from a peer bridge (Phase 80).

        Stores in federation_threat_signals table (deduplicates by commitment_hash).
        """
        check_key(api_key)
        check_rate(api_key)
        if not body.device_id or not body.commitment_hash:
            from fastapi import HTTPException as _HTTPException
            raise _HTTPException(
                status_code=400, detail="device_id and commitment_hash required"
            )
        try:
            signal_id = store.insert_threat_signal(
                device_id=body.device_id,
                commitment_hash=body.commitment_hash,
                circuit_id=body.circuit_id or None,
                source_peer=body.source_peer,
                received_at=time.time(),
            )
            log.info(
                "federation_receive_signal: signal_id=%d device=%s",
                signal_id, body.device_id[:16],
            )
            return {"signal_id": signal_id, "status": "received"}
        except Exception as exc:
            if "UNIQUE" in str(exc).upper():
                return {"status": "duplicate", "note": "commitment_hash already known"}
            from fastapi import HTTPException as _HTTPException
            raise _HTTPException(status_code=500, detail=str(exc)) from exc

    @app.get("/federation/peers")
    def federation_peers(
        api_key: str = Query(..., description="Shared operator API key"),
    ):
        """Return configured federation peer list and signal statistics (Phase 80)."""
        check_key(api_key)
        check_rate(api_key)
        peers_str = getattr(cfg, "federation_broadcast_peers", "")
        peers = [p.strip() for p in peers_str.split(",") if p.strip()] if peers_str else []
        try:
            stats = store.get_federation_stats()
        except Exception as exc:
            log.warning("federation_peers: stats failed: %s", exc)
            stats = {"total_signals": 0, "broadcast": 0, "received_from_peers": 0}
        return {
            "peers": peers,
            "peer_count": len(peers),
            "federation_enabled": getattr(cfg, "federation_broadcast_enabled", False),
            **stats,
        }

    # --- Phase 97: Gated Live Mode Transition ---

    @app.post("/agent/config")
    def set_agent_config(
        api_key: str = Query(..., description="Shared operator API key"),
        dry_run: bool = Query(..., description="Set to false to enable live enforcement"),
    ):
        """Gated live-mode transition guard (Phase 97).

        When dry_run=false is requested, enforces three-condition gate:
          1. gate_passed — consecutive_clean >= gate_n AND divergence_rate OK
          2. cert_valid  — valid non-expired EnforcementReadinessCertificate exists
          3. audit_valid — activation audit chronological invariant satisfied

        Any failure returns HTTP 422 with blocking conditions list.
        On success, updates cfg.agent_dry_run_mode and publishes live_mode_enabled
        to AgentMessageBus so fleet agents shift mode within <1ms.

        All attempts (approved or blocked) logged to live_mode_guard_log.
        Phase 97.
        """
        check_key(api_key)
        check_rate(api_key)
        import hashlib as _hl

        gate_n = int(getattr(cfg, "validation_gate_n", 100))
        max_rate = float(getattr(cfg, "validation_max_divergence_rate", 1.0))
        operator_key_hash = _hl.sha256(api_key.encode()).hexdigest()[:16]

        if not dry_run:
            # Evaluate all three conditions
            blocking = []
            gate_passed = False
            cert_valid = False
            audit_valid_val = False

            try:
                gate_status = store.get_validation_summary(gate_n, max_rate)
                gate_passed = bool(gate_status.get("gate_passed", False))
                if not gate_passed:
                    blocking.append("gate_not_passed")
            except Exception as exc:
                log.warning("config_guard: gate check failed: %s", exc)
                blocking.append("gate_check_error")

            try:
                cert = store.get_latest_enforcement_certificate()
                if cert is None:
                    blocking.append("no_enforcement_certificate")
                elif not cert.get("audit_valid"):
                    blocking.append("cert_audit_invalid")
                elif time.time() > cert.get("expires_at", 0):
                    blocking.append("cert_expired")
                else:
                    cert_valid = True
            except Exception as exc:
                log.warning("config_guard: cert check failed: %s", exc)
                blocking.append("cert_check_error")

            try:
                audit = store.get_activation_audit_summary()
                audit_valid_val = bool(audit.get("audit_valid", False))
                if not audit_valid_val:
                    blocking.append("audit_invalid")
            except Exception as exc:
                log.warning("config_guard: audit check failed: %s", exc)
                blocking.append("audit_check_error")

            try:
                store.insert_live_mode_guard_log(
                    event_type="transition_attempt",
                    attempted_dry_run=0,
                    gate_passed=int(gate_passed),
                    cert_valid=int(cert_valid),
                    audit_valid=int(audit_valid_val),
                    blocking_conditions=_json.dumps(blocking),
                    operator_key_hash=operator_key_hash,
                )
            except Exception as exc:
                log.warning("config_guard: log write failed: %s", exc)

            if blocking:
                from fastapi import HTTPException as _HTTP
                raise _HTTP(422, {"error": "live mode preconditions not met", "blocking": blocking})

            # All conditions met — flip dry_run
            cfg.agent_dry_run_mode = False

            # Publish to bus so fleet agents shift mode immediately
            try:
                if bus is not None:
                    bus.publish_sync("live_mode_enabled", {
                        "dry_run": False,
                        "gate_passed": gate_passed,
                        "cert_valid": cert_valid,
                        "audit_valid": audit_valid_val,
                        "timestamp": time.time(),
                    }, source="operator_api")
            except Exception as exc:
                log.warning("config_guard: bus publish failed: %s", exc)

            try:
                store.insert_live_mode_guard_log(
                    event_type="transition_approved",
                    attempted_dry_run=0,
                    gate_passed=int(gate_passed),
                    cert_valid=int(cert_valid),
                    audit_valid=int(audit_valid_val),
                    blocking_conditions="[]",
                    operator_key_hash=operator_key_hash,
                )
            except Exception as exc:
                log.warning("config_guard: approval log failed: %s", exc)

            return {"dry_run": False, "live_mode_enabled": True, "blocking": []}

        else:
            # dry_run=True is always allowed
            cfg.agent_dry_run_mode = True
            try:
                store.insert_live_mode_guard_log(
                    event_type="dry_run_restored",
                    attempted_dry_run=1,
                    gate_passed=None,
                    cert_valid=None,
                    audit_valid=None,
                    blocking_conditions="[]",
                    operator_key_hash=operator_key_hash,
                )
            except Exception as exc:
                log.warning("config_guard: restore log failed: %s", exc)
            return {"dry_run": True, "live_mode_enabled": False, "blocking": []}


    # --- Phase 99A: AGaaS Foundation — Operator Status ---

    @app.get("/agent/operator-status")
    def operator_status(
        api_key: str = Query(..., description="Shared operator API key"),
        operator_address: str = Query(..., description="Ethereum address of the operator"),
    ):
        """Return latest operator registration event for the given address.

        Reflects bridge-side record of on-chain staking events recorded via
        chain.register_operator_stake() and store.insert_operator_registration().
        Returns null operator_address field if not found.
        """
        check_key(api_key)
        check_rate(api_key)
        try:
            status = store.get_operator_status(operator_address)
            return {
                "operator_address": operator_address,
                "found": status is not None,
                "status": status,
                "vapi_token_address": getattr(cfg, "vapi_token_address", ""),
                "operator_registry_address": getattr(cfg, "operator_registry_address", ""),
                "timestamp": time.time(),
            }
        except Exception as exc:
            log.warning("operator_status: %s", exc)
            return {
                "operator_address": operator_address,
                "found": False,
                "status": None,
                "error": str(exc),
                "timestamp": time.time(),
            }


    @app.get("/agent/quicksilver-status")
    def quicksilver_status(
        api_key: str = Query(..., description="Shared operator API key"),
        operator_address: str = Query(default="", description="Operator address to query"),
    ):
        """Return QuickSilver stIOTX collateral status for an operator (Phase 101).

        Returns the latest collateral event + active status + contract addresses.
        W2: stIOTX earns QuickSilver rebasing yield while locked (double-yield position).
        """
        check_key(api_key)
        check_rate(api_key)
        try:
            record = store.get_quicksilver_collateral_status(operator_address)
            return {
                **record,
                "stiotx_token_address": getattr(cfg, "stiotx_token_address", ""),
                "quicksilver_collateral_address": getattr(cfg, "quicksilver_collateral_address", ""),
                "double_yield_note": (
                    "stIOTX earns QuickSilver rebasing yield while locked as VAPI operator collateral"
                ),
                "timestamp": time.time(),
            }
        except Exception as exc:
            log.warning("quicksilver_status: %s", exc)
            return {
                "operator_address": operator_address,
                "found": False,
                "error": str(exc),
                "timestamp": time.time(),
            }

    @app.get("/agent/edge-ai-profile")
    def edge_ai_profile_endpoint(
        api_key: str = Query(..., description="Shared operator API key"),
    ):
        """Return the VAPI bridge's Edge AI profile for IoTeX ecosystem positioning (Phase 101B).

        Maps the 13-agent autonomous fleet onto IoTeX's Real-World AI stack:
        ioID (Verify) + W3bstream (Process) + Realms (deferred).
        The _rule_fallback() inference engine is a local SLM-equivalent for
        human presence verification — no GPU, no data center required.
        """
        check_key(api_key)
        check_rate(api_key)
        try:
            from ..edge_ai_profile import get_edge_ai_profile
            return get_edge_ai_profile(cfg=cfg, store=store)
        except Exception as exc:
            log.warning("edge_ai_profile_endpoint: %s", exc)
            return {"error": str(exc), "timestamp": time.time()}

    @app.post("/agent/run-activation-simulation")
    async def run_activation_simulation(
        api_key: str = Query(...),
        n_sessions: int = Query(default=110, description="Number of simulation sessions"),
    ):
        """Run Phase 103 live activation simulation. Seeds all gate conditions and
        inserts the protocol's first VHP issuance (simulation, no chain call).
        """
        check_key(api_key)
        check_rate(api_key)
        from ..activation_runner import ActivationRunner
        _bus = getattr(cfg, "_bus", None)
        runner = ActivationRunner(cfg, store, bus=_bus)
        result = await runner.run(n_sessions=n_sessions)
        result["timestamp"] = time.time()
        return result



    @app.get("/agent/confidence-score-multiplier-status")
    def confidence_score_multiplier_status(api_key: str = Query(...)):
        """Phase 122 — VHP confidence_score separation ratio multiplier status.

        When confidence_multiplier_enabled=True, the confidence_score passed to
        chain.mint_vhp() is multiplied by min(1.0, bt_strat_ratio) before minting.
        This ensures the on-chain credential reflects actual identity-discrimination
        confidence: a separation ratio of 0.60 downscales confidence_score to 60%
        of its raw value, signaling the biometric uncertainty to downstream contracts.

        Infrastructure-first: multiplier_enabled=False default (zero behavior change).
        W2 for Phase 123: per-battery threshold tracks using bt_strat_ratio analytics.
        """
        check_key(api_key)
        check_rate(api_key)
        try:
            enabled = bool(getattr(cfg, "confidence_multiplier_enabled", False))
            floor = float(getattr(cfg, "confidence_multiplier_floor", 0.0))
            snaps = store.get_separation_ratio_status(limit=1)
            bt_strat_ratio = snaps[0].get("bt_strat_ratio", -1.0) if snaps else -1.0
            effective_multiplier = (
                max(floor, min(1.0, bt_strat_ratio)) if bt_strat_ratio >= 0 else 1.0
            )
            log = store.get_confidence_multiplier_log(limit=5)
            return {
                "multiplier_enabled":    enabled,
                "current_bt_strat_ratio": round(bt_strat_ratio, 4),
                "effective_multiplier":  round(effective_multiplier, 4),
                "floor":                 floor,
                "log_count":             len(log),
                "recent_applications":   log,
                "timestamp":             time.time(),
            }
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    # --- Phase 120: Bluetooth Transport Foundation ---

    @app.get("/agent/bt-transport-status")
    def bt_transport_status(
        api_key: str = Query(...),
        limit: int = Query(10),
    ):
        """Phase 120 — BLE transport foundation status for DualShock Edge at 250 Hz.

        Returns bt_transport_enabled, device_address, sampling_rate_hz, frames_received,
        frames_dropped, avg_interval_ms, and recent session logs.

        W1 INVARIANT: BT sessions must NOT use USB L4 thresholds (7.009/5.367).
        bt_transport_enabled=False default (infrastructure-only until BT threshold track
        calibrated).
        """
        check_key(api_key)
        check_rate(api_key)
        try:
            enabled   = bool(getattr(cfg, "bt_transport_enabled", False))
            address   = str(getattr(cfg, "bt_device_address", ""))
            rate_hz   = int(getattr(cfg, "bt_sampling_rate_hz", 250))
            logs      = store.get_bt_transport_status(limit=limit)
            total_rx  = sum(r.get("frames_received", 0) for r in logs)
            total_drop = sum(r.get("frames_dropped", 0) for r in logs)
            avg_ms    = (
                sum(r.get("avg_interval_ms", 0.0) for r in logs) / len(logs)
                if logs else 0.0
            )
            return {
                "bt_transport_enabled": enabled,
                "device_address":       address,
                "sampling_rate_hz":     rate_hz,
                "frames_received":      total_rx,
                "frames_dropped":       total_drop,
                "avg_interval_ms":      round(avg_ms, 3),
                "recent_sessions":      logs,
                "timestamp":            time.time(),
            }
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    # --- Phase 119: Override Lifecycle Management ---

    @app.get("/agent/epoch-window-override-status")
    def epoch_window_override_status(api_key: str = Query(...)):
        """Phase 119 — List all per-device epoch overrides with lifecycle fields.

        Returns override_count, overrides_with_max_uses, and the full lifecycle list
        (including max_uses, use_count, expires_at) so operators can audit which
        overrides are ephemeral (auto-graduating) vs permanent.
        """
        check_key(api_key)
        check_rate(api_key)
        try:
            overrides = store.get_override_lifecycle_status()
            with_max_uses = sum(1 for o in overrides if o.get("max_uses") is not None)
            return {
                "override_count":           len(overrides),
                "overrides_with_max_uses":  with_max_uses,
                "overrides":                overrides,
                "epoch_window_enabled":     bool(getattr(cfg, "epoch_window_enabled", False)),
                "timestamp":                time.time(),
            }
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.delete("/agent/epoch-window-override")
    def revoke_epoch_window_override(
        api_key: str = Query(...),
        device_id: str = Query(...),
    ):
        """Phase 119 — Revoke a per-device epoch window override.

        Deletes the override for the given device_id. Subsequent Gate-5 evaluations
        for this device revert to the global cfg.epoch_window_seconds.
        Returns revoked=True if a row was deleted, revoked=False if none existed.
        """
        check_key(api_key)
        check_rate(api_key)
        try:
            revoked = store.delete_device_epoch_override(device_id)
            return {
                "device_id": device_id,
                "revoked":   revoked,
                "timestamp": time.time(),
            }
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    # --- Phase 118: Per-Device Epoch Window Overrides + Auto-Tune ---

    @app.get("/agent/epoch-window-auto-tune")
    def epoch_window_auto_tune(
        api_key: str = Query(...),
        top_n_overrides: int = Query(5),
    ):
        """Phase 118 — Epoch-window auto-tune advisor.

        Analyzes fleet p95 distribution, recommends global fleet window,
        and identifies top devices that need per-device overrides.
        W1: cold-start devices (first check) show artificially large p95 —
            auto-tune identifies them so operators can set generous overrides
            instead of blocking them at gate activation.
        """
        check_key(api_key)
        check_rate(api_key)
        try:
            _analytics = store.get_epoch_window_analytics()
            _devices = store.get_epoch_window_analytics_by_device()
            _overrides = store.get_all_device_epoch_overrides()
            _override_ids = {o["device_id"] for o in _overrides}
            # Eligible devices: no override yet, high p95
            _candidates = [
                d for d in _devices if d["device_id"] not in _override_ids
            ][:top_n_overrides]
            return {
                "epoch_window_enabled":      bool(getattr(cfg, "epoch_window_enabled", False)),
                "current_window_seconds":    float(getattr(cfg, "epoch_window_seconds", 86400.0)),
                "recommended_window_seconds": _analytics.get("recommended_window_seconds", 86400.0),
                "fleet_p95_age_seconds":     _analytics.get("p95_age_seconds", -1.0),
                "override_count":            len(_overrides),
                "override_candidates":       _candidates,
                "timestamp":                 time.time(),
            }
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.post("/agent/epoch-window-override")
    def set_epoch_window_override(
        api_key: str = Query(...),
        device_id: str = Query(...),
        window_seconds: float = Query(...),
        reason: str = Query(""),
    ):
        """Phase 118 — Set a per-device epoch window override.

        Upserts an entry in per_device_epoch_overrides; subsequent Gate-5
        evaluations for this device use override_window_seconds instead of
        the global cfg.epoch_window_seconds.
        Useful for cold-start devices or high-latency adjudication nodes.
        """
        check_key(api_key)
        check_rate(api_key)
        try:
            row_id = store.insert_device_epoch_override(
                device_id=device_id,
                window_seconds=window_seconds,
                reason=reason,
            )
            return {
                "device_id":              device_id,
                "override_window_seconds": window_seconds,
                "reason":                 reason,
                "row_id":                 row_id,
                "timestamp":              time.time(),
            }
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    # --- Phase 117: Per-Device Epoch Freshness Heatmap ---

    @app.get("/agent/epoch-window-device-heatmap")
    def epoch_window_device_heatmap_status(
        api_key: str = Query(...),
        limit_per_device: int = Query(100),
        top_n: int = Query(20),
    ):
        """Phase 117 — Per-device epoch freshness heatmap sorted by p95 DESC.
        Identifies which devices have the stalest PoAd anchors.
        epoch_window_enabled=False by default (infrastructure-first).
        """
        check_key(api_key)
        check_rate(api_key)
        try:
            devices = store.get_epoch_window_analytics_by_device(
                limit_per_device=limit_per_device, top_n=top_n
            )
            return {
                "epoch_window_enabled": bool(getattr(cfg, "epoch_window_enabled", False)),
                "epoch_window_seconds": float(getattr(cfg, "epoch_window_seconds", 86400.0)),
                "total_devices":        len(devices),
                "devices":              devices,
                "timestamp":            time.time(),
            }
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    # --- Phase 116: Epoch-Window Analytics ---

    @app.get("/agent/epoch-window-analytics")
    def epoch_window_analytics_status(
        api_key: str = Query(...),
        limit: int = Query(1000),
    ):
        """Phase 116 — Epoch-window analytics over Gate-5 poad_age_seconds.
        Provides p50/p95/p99 age distribution + recommended epoch_window_seconds.
        epoch_window_enabled=False by default (infrastructure-first).
        """
        check_key(api_key)
        check_rate(api_key)
        try:
            analytics = store.get_epoch_window_analytics(limit=limit)
            return {
                "epoch_window_enabled":   bool(getattr(cfg, "epoch_window_enabled", False)),
                "epoch_window_seconds":   float(getattr(cfg, "epoch_window_seconds", 86400.0)),
                **analytics,
                "timestamp": time.time(),
            }
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc


    # Phase 131B — GET /agent/usb-stability-status
    # ------------------------------------------------------------------
    # VAPI-exclusive: DualShock Edge is the only consumer controller that
    # simultaneously produces a live 228-byte biometric PoAC stream (USB reads)
    # AND writes HID output reports (LED/haptic). When paired to PS5 via BT,
    # those HID writes cause USB micro-drops → PS5 shows reconnect notification.
    # This endpoint exposes the USB instability log and ps5_compat_mode state.
    # ------------------------------------------------------------------
    @app.get("/agent/usb-stability-status")
    async def get_usb_stability_status_endpoint(api_key: str = ""):
        check_key(api_key)
        check_rate(api_key)
        import time as _t131b
        try:
            summary = store.get_usb_stability_status(limit=100)
            _avg_latency = (sum(_latencies) / len(_latencies)) if _latencies else -1.0
            return {
                "nodes_configured":  _nodes_configured,
                "nodes_healthy":     _nodes_healthy,
                "emulator_mode":     _emulator_mode,
                "avg_latency_ms":    round(_avg_latency, 2),
                "health_log_count":  len(_health_log),
                "timestamp":         _t132.time(),
            }
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    # Phase 135 — GET /agent/tournament-activation-chain
    # ------------------------------------------------------------------
    @app.get("/agent/tournament-activation-chain")
    async def get_tournament_activation_chain_endpoint(api_key: str = ""):
        check_key(api_key)
        check_rate(api_key)
        import time as _t135
        try:
            _log135 = store.get_tournament_activation_chain(limit=10)
            _gate_open = any(e.get("gate_open_notified") for e in _log135)
            _last_ratio = _log135[0].get("separation_ratio", 0.0) if _log135 else 0.0
            _last_ts = _log135[0].get("created_at", 0.0) if _log135 else 0.0
            return {
                "gate_open_notified": _gate_open,
                "auto_activate_on_breakthrough": False,  # PERMANENT INVARIANT
                "operator_action_required": True,
                "last_ratio": _last_ratio,
                "last_notification_ts": _last_ts,
                "notification_count": len(_log135),
                "timestamp": _t135.time(),
            }
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    # Phase 163 — POST /agent/commit-separation-ratio
    # ------------------------------------------------------------------
    @app.post("/agent/commit-separation-ratio")
    async def commit_separation_ratio_endpoint(
        ratio: float = 1.261,
        n_sessions: int = 0,
        n_players: int = 3,
        players_sorted: str = "P1,P2,P3",
        api_key: str = "",
    ):
        """Consent-bound separation ratio commitment (Phase 163 WIF-022).

        Computes SHA-256(ratio_str + N + N_consented + players_sorted + ts_ns) where
        N_consented = active_consent_count from consent_ledger — binds consent filtering
        into the on-chain proof. separation_ratio_on_chain_enabled=False → dry_run=True,
        hash computed+stored in SQLite but no chain tx.
        Returns 9 keys: separation_ratio_on_chain_enabled/commit_hash/n_consented/
        n_sessions/n_players/committed/on_chain_tx/dry_run/timestamp.
        """
        check_key(api_key)
        check_rate(api_key)
        import time as _t163
        try:
            _ts_ns = time.time_ns()
            _commit_hash, _n_consented = store.compute_separation_ratio_commit_hash(
                ratio=ratio,
                n_sessions=n_sessions,
                players_sorted=players_sorted,
                ts_ns=_ts_ns,
            )
            _ratio_millis = int(ratio * 1000)
            _enabled = bool(getattr(cfg, "separation_ratio_on_chain_enabled", False))
            store.insert_separation_ratio_registry_log(
                commit_hash=_commit_hash,
                ratio_millis=_ratio_millis,
                n_sessions=n_sessions,
                n_players=n_players,
                on_chain_tx=None,
                committed=False,
                n_consented=_n_consented,
            )
            # Phase 164 WIF-023: snapshot consent state at commit time so post-commit
            # revocations produce a verifiable delta chain rather than silent divergence.
            try:
                _cov164 = store.get_consent_corpus_coverage()
                store.insert_consent_snapshot(
                    commit_hash=_commit_hash,
                    n_consented_at_commit=_n_consented,
                    revoked_count_at_commit=int(_cov164.get("revoked_count", 0)),
                    erasure_count_at_commit=int(_cov164.get("erasure_requested_count", 0)),
                )
            except Exception as _snap_exc:
                log.warning("consent_snapshot insert error (non-fatal): %s", _snap_exc)
            _committed = False
            _on_chain_tx = None
            if _enabled and chain is not None:
                try:
                    _on_chain_tx = await chain.commit_separation_ratio(
                        ratio=ratio,
                        n_sessions=n_sessions,
                        n_players=n_players,
                        players_sorted=players_sorted,
                        n_consented=_n_consented,
                        commit_hash_hex=_commit_hash,
                    )
                    store.update_separation_ratio_registry_committed(_commit_hash, _on_chain_tx)
                    _committed = True
                except Exception as _exc163:
                    log.warning("commit_separation_ratio chain error: %s", _exc163)
            return {
                "separation_ratio_on_chain_enabled": _enabled,
                "commit_hash":  _commit_hash,
                "n_consented":  _n_consented,
                "n_sessions":   n_sessions,
                "n_players":    n_players,
                "committed":    _committed,
                "on_chain_tx":  _on_chain_tx,
                "dry_run":      not _enabled,
                "timestamp":    _t163.time(),
            }
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    # Phase 155 — GET /agent/controller-hardware-status
    # ------------------------------------------------------------------
    @app.get("/agent/controller-hardware-status")
    async def get_controller_hardware_status_endpoint(api_key: str = ""):
        """Controller hardware intelligence status (Phase 155, agent #19).

        Returns: controller_intelligence_enabled, multi_controller_enabled,
        attested_count, standard_count, profiles (list), timestamp.
        Attested tier: DualShock Edge CFI-ZCP1 (full L0–L6 PITL stack).
        Standard tier: Xbox/Switch (L0–L5 only; N=0 calibration pending).
        multi_controller_enabled=False default — never change without N>=50 calibration.
        """
        check_key(api_key)
        check_rate(api_key)
        import time as _t155
        try:
            _ci = bool(getattr(cfg, "controller_intelligence_enabled", True))
            _mc = bool(getattr(cfg, "multi_controller_enabled", False))
            _profiles = store.get_controller_hardware_profiles(active_only=True)
            _attested = sum(1 for p in _profiles if p.get("tier") == "Attested")
            _standard = sum(1 for p in _profiles if p.get("tier") == "Standard")
            return {
                "controller_intelligence_enabled": _ci,
                "multi_controller_enabled":        _mc,
                "attested_count":                  _attested,
                "standard_count":                  _standard,
                "profiles":                        _profiles,
                "timestamp":                       _t155.time(),
            }
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    # Phase 156 — GET /agent/enrollment-auto-guidance-status
    # ------------------------------------------------------------------
    @app.get("/agent/enrollment-auto-guidance-status")
    async def get_enrollment_auto_guidance_status_endpoint(api_key: str = ""):
        """Autonomous enrollment guidance agent status (Phase 156, agent #20).

        Returns: enrollment_auto_guidance_enabled, sessions_needed_total, overall_ready,
        recommended_action, urgency_level, stagnant_probes, estimated_days,
        activation_chain_event, found (bool), timestamp.
        urgency_level: "low" | "medium" | "high" | "critical"
        Integrates Phase 151 guidance + Phase 154 stagnation + Phase 152 velocity.
        """
        check_key(api_key)
        check_rate(api_key)
        import time as _t156
        try:
            _enabled = bool(getattr(cfg, "enrollment_auto_guidance_enabled", True))
            _row = store.get_enrollment_guidance_status()
            if _row is None:
                return {
                    "enrollment_auto_guidance_enabled": _enabled,
                    "sessions_needed_total": 0,
                    "overall_ready":         False,
                    "recommended_action":    "Run EnrollmentAutoGuidanceAgent to generate guidance",
                    "urgency_level":         "low",
                    "stagnant_probes":       [],
                    "estimated_days":        -1.0,
                    "activation_chain_event": None,
                    "found":                 False,
                    "timestamp":             _t156.time(),
                }
            return {
                "enrollment_auto_guidance_enabled": _enabled,
                "sessions_needed_total": int(_row.get("sessions_needed_total", 0)),
                "overall_ready":         bool(_row.get("overall_ready")),
                "recommended_action":    _row.get("recommended_action", ""),
                "urgency_level":         _row.get("urgency_level", "low"),
                "stagnant_probes":       _row.get("stagnant_probes", []),
                "estimated_days":        float(_row.get("estimated_days", -1.0)),
                "activation_chain_event": _row.get("activation_chain_event"),
                "cov_regime_status":     _row.get("cov_regime_status", "unknown"),
                "found":                 True,
                "timestamp":             _t156.time(),
            }
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    # Phase 157 — GET /agent/fleet-consensus-snapshot
    # ------------------------------------------------------------------
    @app.get("/agent/fleet-consensus-snapshot")
    async def get_fleet_consensus_snapshot_endpoint(api_key: str = ""):
        """Fleet Consensus Snapshot agent status (Phase 157, agent #21).

        Returns: fleet_consensus_enabled, total_snapshots, latest_pofc_hash,
        latest_agent_count, latest_separation_ratio, timestamp.
        PoFC_hash = SHA-256(sorted_verdicts_json | ratio_str | ts_ns_str)
        """
        check_key(api_key)
        check_rate(api_key)
        import time as _t157
        try:
            _enabled157 = bool(getattr(cfg, "fleet_consensus_enabled", True))
            _snaps = store.get_fleet_consensus_snapshot(limit=1)
            _latest = _snaps[0] if _snaps else None
            _total_count = 0
            try:
                with store._conn() as _c157:
                    _total_count = _c157.execute(
                        "SELECT COUNT(*) FROM fleet_consensus_snapshot_log"
                    ).fetchone()[0]
            except Exception:
                pass  # fail-open: M-1 cleanup 2026-05-16 — intentional silent skip
            return {
                "fleet_consensus_enabled": _enabled157,
                "total_snapshots":         _total_count,
                "latest_pofc_hash":        _latest["pofc_hash"] if _latest else None,
                "latest_agent_count":      _latest["agent_count"] if _latest else 0,
                "latest_separation_ratio": _latest["separation_ratio"] if _latest else 0.0,
                "timestamp":               _t157.time(),
            }
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    # Phase 181 — renewal endpoint corpus_delta extension (via Phase 180 endpoint)
    # Phase 179 — GET /agent/ceremony-audit-status + POST /agent/register-ceremony-participant
    # ------------------------------------------------------------------
    @app.get("/agent/ceremony-audit-status")
    async def get_ceremony_audit_status_endpoint(api_key: str = ""):
        """ZK Ceremony Audit Gate status (Phase 179, WIF-030 W1 closure).

        Returns ceremony participant audit summary. When ceremony_audit_enabled=False
        (default): audit_passed=True, gate is inactive (zero behavior change).
        When enabled: audit_passed=True only when distinct_participants >= min_participants
        for every VAPI ZK circuit in ceremony_audit_log.

        Returns: ceremony_audit_enabled, total_entries, distinct_participants,
        circuits_audited, min_participants, audit_passed, timestamp.
        """
        check_key(api_key)
        check_rate(api_key)
        import time as _t179
        try:
            _enabled179 = bool(getattr(cfg, "ceremony_audit_enabled", False))
            _min_p179   = int(getattr(cfg, "ceremony_audit_min_participants", 3))
            _status179  = store.get_ceremony_audit_status()
            _distinct   = int(_status179.get("distinct_participants", 0))
            # audit_passed logic: when disabled → True (gate inactive); when enabled →
            # all circuits must have >= min_participants distinct addresses
            if _enabled179:
                _circuits = int(_status179.get("circuits_audited", 0))
                if _circuits == 0:
                    _audit_passed = False  # no circuits registered = gate fails when enabled
                else:
                    # Check per-circuit participant count
                    with store._conn() as _c179:
                        _circuit_rows = _c179.execute(
                            "SELECT circuit_name, COUNT(DISTINCT participant_address) "
                            "AS n FROM ceremony_audit_log GROUP BY circuit_name"
                        ).fetchall()
                    _audit_passed = all(int(r[1]) >= _min_p179 for r in _circuit_rows)
            else:
                _audit_passed = True
            return {
                "ceremony_audit_enabled":  _enabled179,
                "total_entries":           int(_status179.get("total_entries",         0)),
                "distinct_participants":   _distinct,
                "circuits_audited":        int(_status179.get("circuits_audited",      0)),
                "min_participants":        _min_p179,
                "audit_passed":            _audit_passed,
                "timestamp":               _t179.time(),
            }
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.post("/agent/register-ceremony-participant")
    async def register_ceremony_participant_endpoint(
        ceremony_id: str,
        circuit_name: str,
        participant_address: str,
        contribution_hash: str,
        api_key: str = "",
    ):
        """Register a ZK ceremony participant for a circuit (Phase 179).

        Anti-replay: duplicate (ceremony_id, participant_address, circuit_name) is silently
        accepted (idempotent — same participant registering twice is not an error).
        Returns: registered (bool), ceremony_id, circuit_name, participant_address, timestamp.
        """
        check_key(api_key)
        check_rate(api_key)
        import time as _t179p, sqlite3 as _sq179
        try:
            _registered = False
            try:
                store.insert_ceremony_audit_entry(
                    ceremony_id=ceremony_id,
                    circuit_name=circuit_name,
                    participant_address=participant_address,
                    contribution_hash=contribution_hash,
                    ts_ns=int(_t179p.time_ns()),
                )
                _registered = True
            except _sq179.IntegrityError:
                _registered = False  # duplicate — idempotent, not an error
            return {
                "registered":           _registered,
                "ceremony_id":          ceremony_id,
                "circuit_name":         circuit_name,
                "participant_address":  participant_address,
                "timestamp":            _t179p.time(),
            }
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    # Phase 178 — GET /agent/biometric-credential-age
    # Phase 199 — GET /agent/tremor-resting-probe-status
    # Phase 203 — GET /agent/context-integrity-status
    # ------------------------------------------------------------------
    @app.get("/agent/context-integrity-status")
    async def get_context_integrity_status_endpoint(api_key: str = ""):
        """AgentContextRegistry context integrity status (Phase 203).

        Returns the committed SHA-256 system prompt hash for each LLM agent
        alongside the phase number at which it was last registered.
        The bridge registers hashes at startup via main.py Phase 203 block.

        hash_match=True when the stored hash matches the live prompt at the
        last bridge startup. phase_current=True when committed_phase equals
        the current bridge phase (203).

        Returns: agent_context_on_chain_enabled, agents (list of per-agent
                 status dicts with agent_id/prompt_sha256/phase_number/
                 on_chain_tx/anchored_at), all_registered, timestamp.
        """
        check_key(api_key)
        check_rate(api_key)
        import time as _t203
        try:
            _enabled203 = bool(getattr(cfg, "agent_context_on_chain_enabled", False))
            _rows203    = store.get_all_agent_context_status()
            _registered203 = {r["agent_id"]: r for r in _rows203}
            _expected203   = [
                "bridge_agent", "session_adjudicator", "calibration_intelligence_agent"
            ]
            _agents203 = []
            for _aid in _expected203:
                _rec = _registered203.get(_aid)
                _agents203.append({
                    "agent_id":       _aid,
                    "prompt_sha256":  _rec["prompt_sha256"]  if _rec else None,
                    "phase_number":   _rec["phase_number"]   if _rec else None,
                    "on_chain_tx":    _rec.get("on_chain_tx")  if _rec else None,
                    "anchored_at":    _rec.get("anchored_at")  if _rec else None,
                    "registered":     _rec is not None,
                })
            _all_registered = all(a["registered"] for a in _agents203)
            return {
                "agent_context_on_chain_enabled": _enabled203,
                "agents":                         _agents203,
                "all_registered":                 _all_registered,
                "timestamp":                      _t203.time(),
            }
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
