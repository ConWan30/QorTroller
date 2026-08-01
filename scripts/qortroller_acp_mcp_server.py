#!/usr/bin/env python3
"""MCP server wrapper for the QorTroller ACP gateway (EA-ACP Buzz import Option B).

This is a lightweight FastAPI server that exposes `@EA` as an MCP tool. It
speaks a simple HTTP/JSON dialect compatible with the custom MCP convention
already used in `bridge/vapi_bridge/mcp_server.py`.

Endpoints:
    GET  /mcp              — server info
    GET  /mcp/tools        — list tools
    POST /mcp/tools/ask_ea — call a command

POST body:
    {
      "pubkey": "<caller-hex>",
      "content": "@EA status"
    }

Response:
    {
      "ok": true,
      "content": "[grok-build] ...",
      "tags": [["acp_tool", "get_rig_status"], ...],
      "tool": "get_rig_status",
      "harness": "grok-build"
    }

Environment:
    ACP_OPERATOR_PUBKEYS  — comma-separated allow-list (fail-closed)
    ACP_MAX_REPLY_CHARS   — reply bound (default 480)
    ACP_MCP_SECRET        — optional shared secret for the tool endpoint
    ACP_MCP_PORT          — listen port (default 8090)
"""
from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "scripts"))

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse

import qortroller_acp_gateway as gw

_MCP_VERSION = "0.2.0-acp"


@dataclass
class McpConfig:
    operator_pubkeys: tuple[str, ...] = ()
    mcp_secret: str = ""
    max_reply_chars: int = 480


def load_mcp_config() -> McpConfig:
    pubkeys = tuple(
        p.strip()
        for p in os.environ.get("ACP_OPERATOR_PUBKEYS", "").split(",")
        if p.strip()
    )
    secret = os.environ.get("ACP_MCP_SECRET", "")
    max_chars = int(os.environ.get("ACP_MAX_REPLY_CHARS", "480"))
    return McpConfig(
        operator_pubkeys=pubkeys,
        mcp_secret=secret,
        max_reply_chars=max_chars,
    )


def make_app(mcp_cfg: McpConfig | None = None, acp_cfg: gw.GatewayConfig | None = None) -> FastAPI:
    if mcp_cfg is None:
        mcp_cfg = load_mcp_config()
    if acp_cfg is None:
        acp_cfg = gw.GatewayConfig(
            operator_pubkeys=mcp_cfg.operator_pubkeys,
            max_reply_chars=mcp_cfg.max_reply_chars,
        )

    app = FastAPI(title="QorTroller ACP MCP Server", version=_MCP_VERSION)

    tool_catalog = [
        {
            "name": "ask_ea",
            "description": "Send a command to the @EA Engineering Assistant and get a digest reply.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "pubkey": {"type": "string"},
                    "content": {"type": "string"},
                },
                "required": ["pubkey", "content"],
            },
        }
    ]

    @app.get("/mcp")
    async def mcp_root():
        return {
            "mcp_version": _MCP_VERSION,
            "name": "QorTroller ACP MCP Server",
            "tools_endpoint": "/mcp/tools",
            "tool_call_endpoint": "/mcp/tools/ask_ea",
        }

    @app.get("/mcp/tools")
    async def list_tools():
        return {"tools": tool_catalog, "mcp_version": _MCP_VERSION}

    @app.post("/mcp/tools/ask_ea")
    async def ask_ea(
        request: Request,
        authorization: str | None = Header(None),
    ) -> JSONResponse:
        if mcp_cfg.mcp_secret:
            expected = f"Bearer {mcp_cfg.mcp_secret}"
            if authorization != expected:
                raise HTTPException(status_code=401, detail="unauthorized")

        try:
            body = await request.json()
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"invalid json: {exc}") from exc

        pubkey = str(body.get("pubkey", "")).strip()
        content = str(body.get("content", "")).strip()
        if not pubkey:
            raise HTTPException(status_code=400, detail="pubkey required")
        if not content:
            raise HTTPException(status_code=400, detail="content required")

        reply = gw.handle_message(pubkey, content, acp_cfg)
        if reply is None:
            raise HTTPException(status_code=204, detail="no reply")
        content_out, tags = reply
        tool = next((t[1] for t in tags if t[0] == "acp_tool"), "")
        harness = next((t[1] for t in tags if t[0] == "harness"), gw.HARNESS_GROK)
        ok = not content_out.lower().startswith("rejected")
        return JSONResponse(
            {
                "ok": ok,
                "content": content_out,
                "tags": tags,
                "tool": tool,
                "harness": harness,
            }
        )

    return app


app = make_app()


if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("ACP_MCP_PORT", "8090"))
    uvicorn.run("qortroller_acp_mcp_server:app", host="0.0.0.0", port=port)
