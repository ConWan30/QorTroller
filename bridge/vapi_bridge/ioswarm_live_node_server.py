"""
Phase 132 — IoSwarm Live Node Server (standalone operator process)

A FastAPI application that operators run as a standalone process alongside their staking
setup. Imports existing emulators for testnet consistency; production operators replace
the emulator calls with their own ML adjudication pipeline.

Endpoints:
  POST /evaluate   — accept adjudication task, return verdict + confidence
  GET  /status     — 7-key node health status
  GET  /identity   — 5-key node identity / capabilities

HMAC auth (opt-in, Phase 132 W1):
  Response header X-VAPI-HMAC = HMAC-SHA256(IOSWARM_NODE_SECRET, sorted_json_body)
  Client verifies when ioswarm_hmac_enabled=True.

VAPI-exclusive novelty: first DePIN protocol where staked AI nodes independently evaluate
controller biometrics and sign their verdicts with an economic stake commitment.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
import uuid
from typing import Any

try:
    from fastapi import FastAPI, HTTPException, Request, Response
    from fastapi.responses import JSONResponse
    from pydantic import BaseModel
    _FASTAPI_AVAILABLE = True
except ImportError:  # pragma: no cover
    _FASTAPI_AVAILABLE = False
    FastAPI = object  # type: ignore
    BaseModel = object  # type: ignore

# ---------------------------------------------------------------------------
# Node identity — read from environment at startup
# ---------------------------------------------------------------------------

_NODE_ID = os.environ.get("IOSWARM_NODE_ID", f"node_{uuid.uuid4().hex[:8]}")
_STAKER_ADDRESS = os.environ.get("IOSWARM_STAKER_ADDRESS", "")
_STAKE_AMOUNT = int(os.environ.get("IOSWARM_STAKE_AMOUNT", "10000"))
_NODE_SECRET = os.environ.get("IOSWARM_NODE_SECRET", "")
_HMAC_ENABLED = os.environ.get("IOSWARM_HMAC_ENABLED", "false").lower() == "true"
_NODE_VERSION = "3.0.0-phase132"
_STARTUP_TS = time.time()
_EVALUATION_CAPABILITIES = ["renewal", "adjudication_classj", "adjudication_triage", "vhp_mint"]

# ---------------------------------------------------------------------------
# Lazy emulator imports (production operators replace with their own pipeline)
# ---------------------------------------------------------------------------

def _get_renewal_emulator():
    from .ioswarm_node_emulator import IoSwarmNodeEmulator
    return IoSwarmNodeEmulator(n_nodes=1, seed=109)


def _get_classj_emulator():
    from .ioswarm_classj_emulator import IoSwarmClassJEmulator
    return IoSwarmClassJEmulator(n_nodes=1, seed=109)


def _get_triage_emulator():
    from .ioswarm_triage_emulator import IoSwarmTriageEmulator
    return IoSwarmTriageEmulator(n_nodes=1, seed=109)


def _get_mint_emulator():
    from .ioswarm_vhp_mint_emulator import IoSwarmVHPMintEmulator
    return IoSwarmVHPMintEmulator(n_nodes=1, seed=110)


# ---------------------------------------------------------------------------
# HMAC signing helper
# ---------------------------------------------------------------------------

def _sign_response(body_dict: dict) -> str:
    """Return HMAC-SHA256(secret, sorted_json) as hex string."""
    if not _NODE_SECRET:
        return ""
    body_bytes = json.dumps(body_dict, sort_keys=True, separators=(",", ":")).encode()
    return hmac.new(_NODE_SECRET.encode(), body_bytes, hashlib.sha256).hexdigest()


def _make_response(body_dict: dict) -> JSONResponse:
    """Build a JSONResponse, adding X-VAPI-HMAC header when HMAC enabled."""
    resp = JSONResponse(content=body_dict)
    if _HMAC_ENABLED and _NODE_SECRET:
        resp.headers["X-VAPI-HMAC"] = _sign_response(body_dict)
    return resp


# ---------------------------------------------------------------------------
# FastAPI application
# ---------------------------------------------------------------------------

if _FASTAPI_AVAILABLE:
    app = FastAPI(title="VAPI IoSwarm Node", version=_NODE_VERSION)

    class EvaluateRequest(BaseModel):
        evaluation_type: str = "renewal"
        device_id: str = ""
        session_id: str = ""
        payload: dict = {}

    @app.post("/evaluate")
    async def evaluate(req: EvaluateRequest):
        """Run adjudication task; return verdict + confidence from the appropriate emulator."""
        eval_type = req.evaluation_type
        payload = req.payload or {}

        try:
            if eval_type == "renewal":
                emu = _get_renewal_emulator()
                verdicts = emu.evaluate_renewal(
                    device_id=req.device_id or "emulator_test",
                    token_id=int(payload.get("token_id", 0)),
                    consecutive_clean=int(payload.get("consecutive_clean", 0)),
                    recent_block_count=int(payload.get("blocks", 0)),
                )
                verdict = verdicts[0]["verdict"] if verdicts else "HOLD"
                confidence = verdicts[0].get("confidence", 0.5) if verdicts else 0.5

            elif eval_type == "adjudication_classj":
                emu = _get_classj_emulator()
                entropy = float(payload.get("entropy_variance", 0.1))
                verdicts = emu.evaluate_classj(entropy_variance=entropy)
                verdict = verdicts[0]["verdict"] if verdicts else "CLEAR"
                confidence = 0.7

            elif eval_type == "adjudication_triage":
                emu = _get_triage_emulator()
                escalated = bool(payload.get("escalated", False))
                ml_bot = bool(payload.get("ml_bot_cluster", False))
                verdicts = emu.evaluate_triage(escalated=escalated, ml_bot_cluster=ml_bot)
                verdict = verdicts[0]["verdict"] if verdicts else "CLEAR"
                confidence = 0.7

            elif eval_type == "vhp_mint":
                emu = _get_mint_emulator()
                verdicts = emu.evaluate_vhp_mint(
                    device_id=req.device_id or "emulator_test",
                    consecutive_clean=int(payload.get("consecutive_clean", 0)),
                    recent_block_count=int(payload.get("blocks", 0)),
                )
                verdict = verdicts[0]["verdict"] if verdicts else "DENY"
                confidence = verdicts[0].get("confidence", 0.5) if verdicts else 0.5

            else:
                raise HTTPException(status_code=400, detail=f"Unknown evaluation_type: {eval_type}")

        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

        body = {
            "node_id":         _NODE_ID,
            "staker_address":  _STAKER_ADDRESS,
            "verdict":         verdict,
            "confidence":      float(confidence),
            "evaluation_type": eval_type,
        }
        return _make_response(body)

    @app.get("/status")
    async def status():
        """7-key node health status."""
        uptime_s = time.time() - _STARTUP_TS
        body = {
            "node_id":        _NODE_ID,
            "staker_address": _STAKER_ADDRESS,
            "stake_amount":   _STAKE_AMOUNT,
            "healthy":        True,
            "version":        _NODE_VERSION,
            "uptime_s":       round(uptime_s, 1),
            "timestamp":      time.time(),
        }
        return _make_response(body)

    @app.get("/identity")
    async def identity():
        """5-key node identity + capabilities."""
        body = {
            "node_id":                  _NODE_ID,
            "staker_address":           _STAKER_ADDRESS,
            "node_version":             _NODE_VERSION,
            "evaluation_capabilities":  _EVALUATION_CAPABILITIES,
            "timestamp":                time.time(),
        }
        return _make_response(body)

else:  # pragma: no cover
    app = None  # type: ignore
