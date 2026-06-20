"""ioSwarm + PoAd + dual-primitive routes (D-DECON-2 operator_api residue #13).

Register-function split per audits/decon-store-map.md agent_ioswarm domain.
Routes byte-identical to the former inline handlers in _app.py.
"""
from __future__ import annotations

import time
from typing import Callable

from fastapi import FastAPI, HTTPException, Query


def register_agent_ioswarm_routes(
    app: FastAPI,
    *,
    cfg,
    store,
    chain,
    check_key: Callable[[str], None],
    check_rate: Callable[[str], None],
) -> None:
    """Register ioSwarm, PoAd, swarm gate, and dual-primitive HTTP routes."""

    # --- Phase 114: VHP Mint Dual-Primitive Gate log ---

    @app.get("/agent/vhp-dual-gate-log")
    def vhp_dual_gate_log_status(
        api_key: str = Query(...),
        device_id: "str | None" = Query(None),
        limit: int = Query(20),
    ):
        """Phase 114 — VHP mint dual-primitive gate log (5th gate in /agent/mint-vhp).
        dual_primitive_gate_enabled=False by default (infrastructure-first).
        """
        check_key(api_key)
        check_rate(api_key)
        try:
            enabled = bool(getattr(cfg, "dual_primitive_gate_enabled", False))
            logs    = store.get_vhp_dual_gate_log(device_id=device_id, limit=limit)
            return {
                "dual_primitive_gate_enabled": enabled,
                "total_checks":      len(logs),
                "eligible_count":    sum(1 for r in logs if r.get("eligible")),
                "mint_allowed_count": sum(1 for r in logs if r.get("mint_allowed")),
                "recent_logs":       logs,
                "timestamp":         time.time(),
            }
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    # --- Phase 113: Dual-Primitive Composability Gate ---

    @app.get("/agent/dual-primitive-status")
    def dual_primitive_status(api_key: str = Query(...)):
        """Phase 113 — VAPIDualPrimitiveGate status (PoAC + PoAd dual-primitive check)."""
        check_key(api_key)
        check_rate(api_key)
        try:
            enabled = bool(getattr(cfg, "dual_primitive_gate_enabled", False))
            addr    = getattr(cfg, "dual_primitive_gate_address", "")
            lens_addr = getattr(cfg, "protocol_lens_address",
                                "0x1972bf756aFE0FFCfaF9842e2FbBb2B084352EAf")
            adj_addr  = getattr(cfg, "adjudication_registry_address", "")
            checks    = store.get_dual_eligibility_history(limit=100)
            total     = len(checks)
            eligible_count = sum(1 for c in checks if c.get("eligible"))
            last_device = checks[0]["device_id"] if checks else None
            return {
                "dual_primitive_gate_enabled":   enabled,
                "dual_primitive_gate_address":   addr,
                "protocol_lens_address":         lens_addr,
                "adjudication_registry_address": adj_addr,
                "checks_total":                  total,
                "checks_eligible":               eligible_count,
                "last_check_device_id":          last_device,
                "timestamp":                     time.time(),
            }
        except Exception:
            return {
                "dual_primitive_gate_enabled": False,
                "dual_primitive_gate_address": "",
                "protocol_lens_address": "",
                "adjudication_registry_address": "",
                "checks_total": 0,
                "checks_eligible": 0,
                "last_check_device_id": None,
                "timestamp": time.time(),
            }

    @app.post("/agent/check-dual-eligibility")
    async def check_dual_eligibility(
        body: dict,
        api_key: str = Query(...),
    ):
        """Phase 113 — Check dual-primitive eligibility (PoAC + PoAd) for a device+poad pair."""
        check_key(api_key)
        check_rate(api_key)
        if not getattr(cfg, "dual_primitive_gate_enabled", False):
            return {
                "eligible": False, "poac_valid": False, "poad_valid": False,
                "device_id": body.get("device_id", ""),
                "error": "dual_primitive_gate disabled",
                "timestamp": time.time(),
            }
        try:
            import hashlib as _hl
            device_id = body["device_id"]
            poad_hash = body["poad_hash"]
            device_id_hash_hex = _hl.sha256(device_id.encode()).hexdigest()
            result = await chain.is_dual_eligible(device_id_hash_hex, poad_hash)
            store.insert_dual_eligibility_check(
                device_id=device_id,
                poad_hash=poad_hash,
                eligible=result["eligible"],
                poac_valid=result["poac_valid"],
                poad_valid=result["poad_valid"],
            )
            return {
                "eligible":   result["eligible"],
                "poac_valid": result["poac_valid"],
                "poad_valid": result["poad_valid"],
                "device_id":  device_id,
                "timestamp":  time.time(),
            }
        except Exception as exc:
            return {
                "eligible": False, "poac_valid": False, "poad_valid": False,
                "device_id": body.get("device_id", ""),
                "error": str(exc),
                "timestamp": time.time(),
            }

    @app.get("/agent/poad-anchor-status")
    def poad_anchor_status(api_key: str = Query(...)):
        """Phase 112 — PoAd on-chain anchor status (PoAdAnchorAgent + poad_registry_log)."""
        check_key(api_key)
        check_rate(api_key)
        try:
            enabled = bool(getattr(cfg, "poad_on_chain_enabled", False))
            addr    = getattr(cfg, "adjudication_registry_address", "")
            logs    = store.get_poad_registry_log(limit=100)
            anchored_count = sum(1 for r in logs if r.get("on_chain_tx"))
            pending_count  = sum(1 for r in logs if not r.get("on_chain_tx"))
            last_tx = next(
                (r["on_chain_tx"] for r in reversed(logs) if r.get("on_chain_tx")),
                None,
            )
            return {
                "poad_on_chain_enabled":           enabled,
                "anchored_count":                  anchored_count,
                "pending_count":                   pending_count,
                "last_anchor_tx":                  last_tx,
                "adjudication_registry_address":   addr,
                "timestamp":                       time.time(),
            }
        except Exception as exc:
            return {
                "poad_on_chain_enabled": False,
                "anchored_count": 0,
                "pending_count": 0,
                "last_anchor_tx": None,
                "adjudication_registry_address": "",
                "timestamp": time.time(),
            }

    @app.get("/agent/adjudication-registry-status")
    def adjudication_registry_status(api_key: str = Query(...)):
        """Phase 111 — PoAd Registry status (local poad_registry_log; on-chain anchoring Phase 112)."""
        check_key(api_key)
        check_rate(api_key)
        try:
            enabled  = bool(getattr(cfg, "poad_registry_enabled", False))
            addr     = getattr(cfg, "adjudication_registry_address", "")
            logs     = store.get_poad_registry_log(limit=100)
            total    = len(logs)
            dv_count = sum(1 for r in logs if r.get("dual_veto"))
            chain_count = sum(1 for r in logs if r.get("on_chain_tx"))
            composable  = bool(addr and enabled)
            return {
                "poad_registry_enabled":       enabled,
                "total_poad_count":            total,
                "dual_veto_poad_count":        dv_count,
                "on_chain_anchor_count":       chain_count,
                "recent_poad_logs":            store.get_poad_registry_log(limit=10),
                "adjudication_registry_address": addr,
                "is_composable":               composable,
                "timestamp":                   time.time(),
            }
        except Exception as exc:
            return {
                "poad_registry_enabled": False,
                "total_poad_count": 0,
                "dual_veto_poad_count": 0,
                "on_chain_anchor_count": 0,
                "recent_poad_logs": [],
                "adjudication_registry_address": "",
                "is_composable": False,
                "timestamp": time.time(),
                "error": str(exc),
            }

    @app.get("/agent/ioswarm-vhp-mint-status")
    def ioswarm_vhp_mint_status(api_key: str = Query(...)):
        """Phase 110 — ioSwarm VHP Mint Authorization status (fail-CLOSED quorum gate, W2 swarm_fingerprint)."""
        check_key(api_key)
        check_rate(api_key)
        try:
            enabled    = bool(getattr(cfg, "ioswarm_vhp_mint_enabled", False))
            mint_q     = float(getattr(cfg, "ioswarm_vhp_mint_quorum", 0.80))
            logs       = store.get_ioswarm_vhp_mint_log(limit=100)
            authorized_count       = sum(1 for r in logs if r.get("authorized"))
            denied_count           = len(logs) - authorized_count
            swarm_fingerprint_count = sum(1 for r in logs if r.get("swarm_fingerprint"))
            return {
                "ioswarm_vhp_mint_enabled":  enabled,
                "mint_quorum":               mint_q,
                "authorized_count":          authorized_count,
                "denied_count":              denied_count,
                "recent_vhp_mint_logs":      store.get_ioswarm_vhp_mint_log(limit=10),
                "task_spec_registered":      True,
                "swarm_fingerprint_count":   swarm_fingerprint_count,
                "timestamp":                 time.time(),
            }
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.get("/agent/ioswarm-adjudication-status")
    def ioswarm_adjudication_status(api_key: str = Query(...)):
        """Phase 109C — ioSwarm Adjudication Coordinator status (ClassJ+Triage dual-quorum veto)."""
        check_key(api_key)
        check_rate(api_key)
        try:
            enabled    = bool(getattr(cfg, "ioswarm_adjudication_enabled", False))
            cj_quorum  = float(getattr(cfg, "ioswarm_classj_block_quorum", 0.67))
            tr_quorum  = float(getattr(cfg, "ioswarm_triage_block_quorum", 0.67))
            logs       = store.get_ioswarm_adjudication_log(limit=100)
            adj_count  = len(logs)
            dual_veto_count = sum(1 for r in logs if r.get("dual_veto"))
            return {
                "ioswarm_adjudication_enabled": enabled,
                "classj_block_quorum":          cj_quorum,
                "triage_block_quorum":          tr_quorum,
                "dual_veto_count":              dual_veto_count,
                "adjudication_count":           adj_count,
                "recent_adjudication_logs":     store.get_ioswarm_adjudication_log(limit=10),
                "task_spec_registered":         True,
                "timestamp":                    time.time(),
            }
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.post("/agent/prime-ioswarm-adjudication")
    def prime_ioswarm_adjudication(api_key: str = Query(...)):
        """Phase 204 — WIF-038 W2 closure: IoSwarm Adjudication Primer.

        Replays up to 5 synthetic device sessions through IoSwarmAdjudicationCoordinator
        in emulator mode to seed ioswarm_adjudication_log with primer entries, resolving
        the IOSWARM_ACTIVE_NO_ADJUDICATIONS CONTRADICTION rule and unblocking the VHP
        MINT_QUORUM=0.80 (FROZEN) authorization pathway.

        Requires IOSWARM_ADJUDICATION_PRIMER_ENABLED=true (primer_enabled=False default).
        Returns 409 when disabled.
        """
        check_key(api_key)
        check_rate(api_key)
        try:
            primer_enabled = bool(getattr(cfg, "ioswarm_adjudication_primer_enabled", False))
            if not primer_enabled:
                raise HTTPException(
                    status_code=409,
                    detail={
                        "error":   "primer_disabled",
                        "message": (
                            "ioswarm_adjudication_primer_enabled=False. "
                            "Set IOSWARM_ADJUDICATION_PRIMER_ENABLED=true to enable."
                        ),
                    },
                )
            from ..ioswarm_adjudication_coordinator import IoSwarmAdjudicationCoordinator
            coord   = IoSwarmAdjudicationCoordinator(cfg=cfg, store=store)
            n_prime = 5
            results = []
            for i in range(n_prime):
                dev_id = f"primer_device_{i:03d}"
                r = coord.evaluate(
                    device_id       = dev_id,
                    session_id      = f"PRIMER:{i}",
                    entropy_variance= 0.5,
                    escalated       = False,
                )
                results.append({
                    "device_id":      dev_id,
                    "classj_verdict": r.get("classj_quorum_verdict"),
                    "triage_verdict": r.get("triage_quorum_verdict"),
                    "dual_veto":      bool(r.get("dual_veto", False)),
                })
            adj_total = len(store.get_ioswarm_adjudication_log(limit=200))
            return {
                "primer_enabled":                  True,
                "devices_primed":                  len(results),
                "results":                         results,
                "ioswarm_adjudication_log_seeded": True,
                "ioswarm_adjudication_log_total":  adj_total,
                "timestamp":                       time.time(),
            }
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.get("/agent/ioswarm-renewal-status")
    def ioswarm_renewal_status(api_key: str = Query(...)):
        """Phase 109B — ioSwarm Renewal Coordinator status + recent renewal log."""
        check_key(api_key)
        check_rate(api_key)
        try:
            from ..ioswarm_renewal_spec import VHPRenewalSwarmTaskSpec
            _spec = VHPRenewalSwarmTaskSpec()
            enabled   = bool(getattr(cfg, "ioswarm_renewal_enabled", False))
            min_q     = int(getattr(cfg, "ioswarm_renewal_min_quorum", 3))
            logs      = store.get_ioswarm_renewal_log(limit=100)
            renewal_count   = len(logs)
            recent_approvals = sum(1 for r in logs if r.get("renewal_approved"))
            recent_skips     = sum(1 for r in logs if not r.get("renewal_approved"))
            return {
                "ioswarm_renewal_enabled": enabled,
                "min_quorum":              min_q,
                "renewal_count":           renewal_count,
                "task_spec_registered":    True,
                "recent_renewal_logs":     store.get_ioswarm_renewal_log(limit=10),
                "recent_approvals":        recent_approvals,
                "recent_skips":            recent_skips,
                "timestamp":               time.time(),
            }
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.get("/agent/ioswarm-status")
    def ioswarm_status(api_key: str = Query(...)):
        """Phase 109A — ioSwarm Bridge Adapter status + recent consensus log."""
        check_key(api_key)
        check_rate(api_key)
        try:
            from ..ioswarm_task_spec import VAPISwarmTaskSpec
            spec = VAPISwarmTaskSpec()
            enabled   = bool(getattr(cfg, "ioswarm_enabled", False))
            q_thresh  = float(getattr(cfg, "ioswarm_quorum_threshold", 0.60))
            bq_thresh = float(getattr(cfg, "ioswarm_block_quorum_threshold", 0.67))
            node_cnt  = int(getattr(cfg, "ioswarm_node_count", 5))
            endpoint  = str(getattr(cfg, "ioswarm_endpoint", ""))
            logs  = store.get_ioswarm_consensus_log(limit=10)
            count = len(store.get_ioswarm_consensus_log(limit=10000))
            return {
                "ioswarm_enabled":           enabled,
                "quorum_threshold":          q_thresh,
                "block_quorum_threshold":    bq_thresh,
                "configured_node_count":     node_cnt,
                "endpoint_configured":       bool(endpoint),
                "consensus_count":           count,
                "recent_consensus_logs":     logs,
                "task_spec_registered":      True,
                "w3bstream_applets":         list(spec.w3bstream_applets),
                "vhp_auth_gate_address":     spec.protocol_lens_address,
                "status_note":               (
                    "Phase 109A infrastructure-only. Enable after live ioSwarm nodes registered."
                ),
                "timestamp": time.time(),
            }
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    # ------------------------------------------------------------------
    # Phase 130A — GET /agent/swarm-operator-gate-status
    # ------------------------------------------------------------------
    @app.get("/agent/swarm-operator-gate-status")
    async def get_swarm_operator_gate_status_endpoint(api_key: str = ""):
        check_key(api_key)
        check_rate(api_key)
        import time as _t130
        try:
            gate_addr = getattr(cfg, "swarm_operator_gate_address", "")
            rows = store.get_swarm_quorum_validation_log(limit=1)
            last_valid = False
            last_node_count = 0
            total_validations = 0
            if rows:
                last_row = rows[0]
                last_valid = bool(last_row.get("quorum_valid", 0))
                last_node_count = int(last_row.get("node_count", 0))
            all_rows = store.get_swarm_quorum_validation_log(limit=10000)
            total_validations = len(all_rows)
            return {
                "swarm_gate_address":  gate_addr,
                "gate_configured":     bool(gate_addr),
                "total_validations":   total_validations,
                "last_valid":          last_valid,
                "last_node_count":     last_node_count,
                "timestamp":           _t130.time(),
            }
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    # Phase 132 — GET /agent/ioswarm-node-health
    # ------------------------------------------------------------------
    @app.get("/agent/ioswarm-node-health")
    async def get_ioswarm_node_health_endpoint(api_key: str = ""):
        check_key(api_key)
        check_rate(api_key)
        import time as _t132
        try:
            from ..ioswarm_live_node_client import IoSwarmLiveNodeClient
            _client132 = IoSwarmLiveNodeClient(cfg=cfg, store=store)
            _emulator_mode = _client132.is_emulator_mode()
            _node_urls_raw = getattr(cfg, "ioswarm_node_urls", "") or ""
            _urls = [u.strip() for u in _node_urls_raw.split(",") if u.strip()]
            _nodes_configured = len(_urls)
            _health_log = store.get_ioswarm_node_health(limit=50)
            _recent = [e for e in _health_log if _t132.time() - e.get("polled_at", 0) < 300]
            _nodes_healthy = sum(1 for e in _recent if e.get("healthy"))
            _latencies = [e.get("latency_ms", -1) for e in _recent if e.get("latency_ms", -1) >= 0]
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

    # Phase 133 — GET /agent/ioswarm-poad-anchor-status
    # ------------------------------------------------------------------
    @app.get("/agent/ioswarm-poad-anchor-status")
    async def get_ioswarm_poad_anchor_status_endpoint(api_key: str = ""):
        check_key(api_key)
        check_rate(api_key)
        import time as _t133
        try:
            _enabled = bool(getattr(cfg, "ioswarm_poad_auto_anchor_enabled", False))
            _log = store.get_ioswarm_poad_anchor_log(limit=50)
            _anchored = sum(1 for e in _log if e.get("anchor_status") == "anchored")
            _pending  = sum(1 for e in _log if e.get("anchor_status") == "pending")
            _dual_veto_count = sum(1 for e in _log if e.get("dual_veto"))
            _failed   = sum(1 for e in _log if e.get("anchor_status") == "failed")
            _last_tx  = next((e.get("on_chain_tx") for e in _log if e.get("on_chain_tx")), None)
            return {
                "poad_auto_anchor_enabled": _enabled,
                "anchored_count":           _anchored,
                "pending_count":            _pending,
                "last_anchor_tx":           _last_tx,
                "dual_veto_count":          _dual_veto_count,
                "anchor_failure_count":     _failed,
                "timestamp":                _t133.time(),
            }
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    # Phase 131 — GET /agent/ioswarm-node-registry-status
    # ------------------------------------------------------------------
    @app.get("/agent/ioswarm-node-registry-status")
    async def get_ioswarm_node_registry_status_endpoint(api_key: str = ""):
        check_key(api_key)
        check_rate(api_key)
        import time as _t131
        try:
            from ..ioswarm_live_node_client import IoSwarmLiveNodeClient
            client = IoSwarmLiveNodeClient(cfg=cfg, store=store)
            node_urls_raw = getattr(cfg, "ioswarm_node_urls", "") or ""
            node_urls_list = [u.strip() for u in node_urls_raw.split(",") if u.strip()]
            emulator_mode = client.is_emulator_mode()
            node_timeout_s = float(getattr(cfg, "ioswarm_node_timeout_seconds", 5.0))
            registry_rows = store.get_ioswarm_node_registry(active_only=False)
            active_rows = [r for r in registry_rows if r.get("active")]
            last_quorum_ts = 0.0
            recent_quorum = store.get_swarm_quorum_validation_log(limit=1)
            if recent_quorum:
                last_quorum_ts = float(recent_quorum[0].get("created_at", 0.0))
            return {
                "live_nodes":     len(active_rows),
                "emulator_mode":  emulator_mode,
                "node_urls":      node_urls_raw,
                "node_timeout_s": node_timeout_s,
                "registry_count": len(registry_rows),
                "last_quorum_ts": last_quorum_ts,
                "timestamp":      _t131.time(),
            }
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
