# bridge/vapi_bridge/mcp_server.py
# Phase 148 — VAPI MCP (Model Context Protocol) Server
#
# Exposes agent fleet calibration state as MCP resources, enabling autoresearch
# sessions to query live bridge state rather than reading static files.
#
# Infrastructure-first: mcp_server_enabled=False default (zero behavior change until enabled).
# Runs as a separate FastAPI sub-app mounted at /mcp by main.py when enabled.
#
# MCP Resource IDs exposed:
#   vapi://calibration/health           — AgentCalibrationMonitor latest results
#   vapi://agents/fleet                 — 16-agent fleet health snapshot
#   vapi://separation/ratio             — current inter-person separation ratio
#   vapi://l4/thresholds                — L4 anomaly/continuity thresholds + staleness
#   vapi://protocol/maturity            — ProtocolMaturityIndex + activation state
#   vapi://tournament/readiness         — tournament readiness score (0.0–1.0)

import logging
import time

log = logging.getLogger(__name__)

_MCP_VERSION = "0.1.0-phase148"

# All MCP resource definitions (static metadata; values populated at query time)
_RESOURCE_CATALOG = [
    {
        "id":          "vapi://calibration/health",
        "name":        "Agent Calibration Health",
        "description": "Latest AgentCalibrationMonitor results for all 16 agents (Phase 148 ACIM)",
        "mime_type":   "application/json",
    },
    {
        "id":          "vapi://agents/fleet",
        "name":        "Agent Fleet Status",
        "description": "AgentSupervisor fleet health snapshot (HEALTHY/STALE/ZOMBIE per agent)",
        "mime_type":   "application/json",
    },
    {
        "id":          "vapi://separation/ratio",
        "name":        "Inter-Person Separation Ratio",
        "description": "Current biometric separation ratio + tournament blocker status",
        "mime_type":   "application/json",
    },
    {
        "id":          "vapi://l4/thresholds",
        "name":        "L4 Biometric Thresholds",
        "description": "Mahalanobis anomaly/continuity thresholds + staleness flag",
        "mime_type":   "application/json",
    },
    {
        "id":          "vapi://protocol/maturity",
        "name":        "Protocol Maturity Index",
        "description": "PMI 0-3 ladder + activation_committed + dry_run_active",
        "mime_type":   "application/json",
    },
    {
        "id":          "vapi://tournament/readiness",
        "name":        "Tournament Readiness Score",
        "description": "Weighted readiness score 0.0–1.0 from 6 signals (Phase 128)",
        "mime_type":   "application/json",
    },
]


def create_mcp_app(cfg, store):
    """Create and return the FastAPI MCP sub-app (mounted at /mcp by main.py)."""
    try:
        from fastapi import FastAPI, HTTPException
    except ImportError as exc:
        raise ImportError("FastAPI required for MCP server: pip install fastapi") from exc

    app = FastAPI(
        title="VAPI MCP Server",
        version=_MCP_VERSION,
        description="Model Context Protocol server exposing VAPI agent fleet state",
        docs_url="/docs",
    )

    @app.get("/status")
    async def mcp_status():
        """MCP server liveness + version."""
        return {
            "mcp_version":     _MCP_VERSION,
            "mcp_server_enabled": True,
            "resource_count":  len(_RESOURCE_CATALOG),
            "timestamp":       time.time(),
        }

    @app.get("/resources")
    async def list_resources():
        """List all available MCP resources (catalog)."""
        return {
            "resources":   _RESOURCE_CATALOG,
            "total":       len(_RESOURCE_CATALOG),
            "mcp_version": _MCP_VERSION,
            "timestamp":   time.time(),
        }

    @app.get("/resource/{resource_id:path}")
    async def get_resource(resource_id: str):
        """Fetch the content of a specific MCP resource by ID.

        resource_id is the path component after /resource/ — e.g. vapi://calibration/health
        is fetched as /mcp/resource/vapi://calibration/health.
        """
        # Normalize — FastAPI path param captures with double-slash encoded
        rid = resource_id.replace("vapi:/", "vapi://", 1) if not resource_id.startswith("vapi://") else resource_id

        catalog_ids = [r["id"] for r in _RESOURCE_CATALOG]
        if rid not in catalog_ids:
            raise HTTPException(status_code=404, detail=f"Resource '{rid}' not found")

        try:
            content = _fetch_resource_content(rid, cfg, store)
            meta = next(r for r in _RESOURCE_CATALOG if r["id"] == rid)
            return {
                "id":        rid,
                "name":      meta["name"],
                "mime_type": meta["mime_type"],
                "content":   content,
                "timestamp": time.time(),
            }
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.post("/tool")
    async def call_tool(body: dict):
        """MCP tool call — returns agent fleet calibration health summary.

        Accepts: {"tool": "get_calibration_health"}
        Returns: health summary dict.
        """
        tool = body.get("tool", "")
        if tool == "get_calibration_health":
            try:
                return _fetch_resource_content("vapi://calibration/health", cfg, store)
            except Exception as exc:
                return {"error": str(exc)}
        raise HTTPException(status_code=400, detail=f"Unknown tool: '{tool}'")

    return app


def _fetch_resource_content(resource_id: str, cfg, store) -> dict:
    """Populate a resource by reading live state from store/cfg."""
    if resource_id == "vapi://calibration/health":
        rows = store.get_agent_calibration_health(limit=32)
        # Latest result per agent_id
        seen: dict[int, dict] = {}
        for row in rows:
            aid = row.get("agent_id", 0)
            if aid not in seen:
                seen[aid] = row
        healthy  = sum(1 for r in seen.values() if r.get("result") == "PASS")
        degraded = sum(1 for r in seen.values() if r.get("result") != "PASS")
        return {
            "agent_count":     16,
            "healthy_count":   healthy,
            "degraded_count":  degraded,
            "failed_agents":   [r.get("agent_name") for r in seen.values() if r.get("result") != "PASS"],
            "latest_tests":    list(seen.values()),
            "mcp_server_enabled": True,
        }

    if resource_id == "vapi://agents/fleet":
        try:
            from .agent_supervisor import AgentSupervisor
            sup = AgentSupervisor(cfg, store)
            return sup.check_fleet_health()
        except Exception as exc:
            return {"fleet_health": "UNKNOWN", "error": str(exc)}

    if resource_id == "vapi://separation/ratio":
        try:
            status = store.get_separation_ratio_status()
            return status if isinstance(status, dict) else {"error": "no status"}
        except Exception as exc:
            return {"pooled_ratio": 0.0, "tournament_blocker": True, "error": str(exc)}

    if resource_id == "vapi://l4/thresholds":
        return {
            "anomaly_threshold":       float(getattr(cfg, "l4_anomaly_threshold", 7.009)),
            "continuity_threshold":    float(getattr(cfg, "l4_continuity_threshold", 5.367)),
            "live_feature_dim":        int(getattr(cfg, "live_feature_dim", 13)),
            "calibration_feature_dim": int(getattr(cfg, "calibration_feature_dim", 12)),
            "stale": (
                int(getattr(cfg, "live_feature_dim", 13)) !=
                int(getattr(cfg, "calibration_feature_dim", 12))
            ),
        }

    if resource_id == "vapi://protocol/maturity":
        try:
            state = store.get_activation_state()
            pmi   = store.compute_pmi() if hasattr(store, "compute_pmi") else 0
            return {
                "pmi":                  pmi,
                "activation_committed": bool(state.get("activation_committed", False)),
                "dry_run_active":       bool(getattr(cfg, "agent_dry_run_mode", True)),
            }
        except Exception as exc:
            return {"pmi": 0, "activation_committed": False, "dry_run_active": True,
                    "error": str(exc)}

    if resource_id == "vapi://tournament/readiness":
        try:
            reports = store.get_readiness_scores(limit=1)
            if reports:
                r = reports[0]
                return {
                    "score":          float(r.get("protocol_health_score", 0.0)),
                    "conditions_met": str(r.get("recommendation", "")),
                    "ready":          float(r.get("protocol_health_score", 0.0)) >= 0.90,
                }
            return {"score": 0.0, "conditions_met": "", "ready": False}
        except Exception as exc:
            return {"score": 0.0, "conditions_met": "", "ready": False, "error": str(exc)}

    return {"error": f"no content handler for {resource_id}"}
