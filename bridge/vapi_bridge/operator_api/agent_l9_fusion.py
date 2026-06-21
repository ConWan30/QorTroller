"""L9 x Retina Fusion v2 routes — read-only oracle-panel / capture-telemetry surface.

Advisory only: gated on cfg.l9_fusion_v2_enabled; reads l9_fusion_event_log. Does NOT touch
the 228-byte PoAC, chain, or any FROZEN-v1 primitive. UNCALIBRATED until real co-capture.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Callable

from fastapi import FastAPI, Header, HTTPException

log = logging.getLogger(__name__)


def register_agent_l9_fusion_routes(
    app: FastAPI,
    *,
    cfg,
    store,
    check_read_key: Callable[[str], None],
) -> None:
    """Register the read-only L9 fusion v2 endpoints."""

    # NOTE: the static route MUST be declared before the /{device_id} route so FastAPI
    # does not match "capture-telemetry" as a device_id.
    @app.get("/bridge/l9-fusion/capture-telemetry")
    async def get_l9_capture_telemetry(x_api_key: str = Header(default="")):
        """Latest Adaptive Capture Governor telemetry (fps stability / lag / downscale history)."""
        check_read_key(x_api_key)
        if not bool(getattr(cfg, "l9_fusion_v2_enabled", False)):
            return {"enabled": False, "calibration": "UNCALIBRATED"}
        status = await asyncio.to_thread(store.get_l9_fusion_status, None, 1)
        return {
            "enabled": True,
            "calibration": "UNCALIBRATED",
            "adaptive_capture_enabled": bool(getattr(cfg, "adaptive_capture_enabled", True)),
            "latest_capture_telemetry": status.get("latest_capture_telemetry", {}),
            "latest_fusion_verdict": status.get("latest_fusion_verdict", ""),
        }

    @app.get("/bridge/l9-fusion/{device_id}")
    async def get_l9_fusion_report(device_id: str, x_api_key: str = Header(default="")):
        """Latest tri-channel fusion verdict(s) + capture telemetry for a device."""
        check_read_key(x_api_key)
        if not bool(getattr(cfg, "l9_fusion_v2_enabled", False)):
            return {"enabled": False, "calibration": "UNCALIBRATED", "device_id": device_id}
        status = await asyncio.to_thread(store.get_l9_fusion_status, device_id, 20)
        return {"enabled": True, "calibration": "UNCALIBRATED", "device_id": device_id, **status}
