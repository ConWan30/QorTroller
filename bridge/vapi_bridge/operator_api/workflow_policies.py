"""Workflow Policy Router dashboard API for the operator bridge.

Implements the dashboard surface from `docs/design/buzz-workflow-policy-routers-v0.md`:
- GET  /operator/workflow-policies           — list policy catalog
- POST /operator/workflow-policies/{id}/run  — run one policy

No natural-language authority. No chain. No new Buzz identity.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Callable

from fastapi import APIRouter, FastAPI, Header, HTTPException, Request

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

import qortroller_acp_gateway as gw  # noqa: E402
import workflow_policy_router as wpr  # noqa: E402


def register_workflow_policy_routes(
    app: FastAPI,
    check_read_key: Callable[[str], None],
) -> None:
    """Mount workflow policy routes on the bridge app."""
    router = APIRouter()

    @router.get("/operator/workflow-policies")
    async def list_workflow_policies(
        request: Request,
        x_api_key: str = Header(default=""),
        config: str = "",
    ):
        check_read_key(x_api_key)
        path = config or str(wpr.DEFAULT_POLICIES_PATH)
        try:
            return {"policies": wpr.list_policies(path)}
        except wpr.RouterError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e

    @router.post("/operator/workflow-policies/{policy_id}/run")
    async def run_workflow_policy(
        policy_id: str,
        request: Request,
        dry_run: bool = False,
        x_api_key: str = Header(default=""),
        config: str = "",
        state: str = "",
        pubkey: str = "",
    ):
        check_read_key(x_api_key)
        policies_path = config or str(wpr.DEFAULT_POLICIES_PATH)
        state_path = state or str(wpr.DEFAULT_STATE_PATH)
        resolved_pubkey = wpr._resolve_pubkey(pubkey)
        cfg = gw.load_config()
        run = wpr.run_policy_by_id(
            policy_id,
            policies_path=policies_path,
            state_path=state_path,
            cfg=cfg,
            dry_run=dry_run,
            pubkey=resolved_pubkey,
        )
        record = wpr._run_to_record(run)
        if run.skipped:
            return record
        if not run.ok:
            raise HTTPException(status_code=422, detail=record)
        return record

    app.include_router(router)
