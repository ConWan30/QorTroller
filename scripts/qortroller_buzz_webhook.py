#!/usr/bin/env python3
"""Webhook adapter for Buzz -> @EA (EA-ACP Buzz import, Option A).

Buzz (or any external workflow) POSTs an event to this HTTP endpoint.
The adapter runs the same `qortroller_acp_gateway.handle_message` path
used by the Nostr bot and the `--eval` CLI, then returns the reply so the
caller can publish it as `@EA`.

Usage:
    BUZZ_WEBHOOK_SECRET=token BUZZ_WEBHOOK_PORT=8080 \
        python scripts/qortroller_buzz_webhook.py

POST /buzz
    Authorization: Bearer <BUZZ_WEBHOOK_SECRET> (optional; enforced if set)
    {
      "pubkey": "<caller-hex>",
      "content": "@EA status"
    }

Returns:
    {
      "ok": true,
      "content": "[grok-build] ...",
      "tags": [["acp_tool", "get_rig_status"], ...],
      "tool": "get_rig_status",
      "harness": "grok-build"
    }

The caller is still bound by `handle_message`:
- `pubkey` must be in `ACP_OPERATOR_PUBKEYS`.
- Commands are fixed-argv and digest-only.
- Replies are scrubbed and bounded before JSON serialization.
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


@dataclass
class WebhookConfig:
    operator_pubkeys: tuple[str, ...] = ()
    webhook_secret: str = ""
    max_reply_chars: int = 480


def load_webhook_config() -> WebhookConfig:
    pubkeys = tuple(
        p.strip()
        for p in os.environ.get("ACP_OPERATOR_PUBKEYS", "").split(",")
        if p.strip()
    )
    secret = os.environ.get("BUZZ_WEBHOOK_SECRET", "")
    max_chars = int(os.environ.get("ACP_MAX_REPLY_CHARS", "480"))
    return WebhookConfig(
        operator_pubkeys=pubkeys,
        webhook_secret=secret,
        max_reply_chars=max_chars,
    )


def make_app(
    webhook_cfg: WebhookConfig | None = None,
    acp_cfg: gw.GatewayConfig | None = None,
) -> FastAPI:
    """Build a FastAPI app wired to the ACP gateway."""
    if webhook_cfg is None:
        webhook_cfg = load_webhook_config()
    if acp_cfg is None:
        acp_cfg = gw.GatewayConfig(
            operator_pubkeys=webhook_cfg.operator_pubkeys,
            max_reply_chars=webhook_cfg.max_reply_chars,
        )

    app = FastAPI(title="QorTroller Buzz Webhook")

    @app.post("/buzz")
    async def buzz_post(
        request: Request,
        authorization: str | None = Header(None),
    ) -> JSONResponse:
        # Shared-secret layer (fail-open: if no secret is configured, skip).
        if webhook_cfg.webhook_secret:
            expected = f"Bearer {webhook_cfg.webhook_secret}"
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

        # This is the same path the Nostr bot and CLI use.
        reply = gw.handle_message(pubkey, content, acp_cfg)
        if reply is None:
            raise HTTPException(status_code=204, detail="no reply")
        content_out, tags = reply
        # Extract the tool/harness from the first tag pair if present.
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


# Default app for `uvicorn`.
app = make_app()


if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("BUZZ_WEBHOOK_PORT", "8080"))
    uvicorn.run("qortroller_buzz_webhook:app", host="0.0.0.0", port=port)
