"""Health + tournament gate routes (D-DECON-2 operator_api residue #10).

Register-function split per audits/decon-store-map.md F-DECON-2.2.
Routes byte-identical to the former inline handlers in _app.py.
"""
from __future__ import annotations

from typing import Callable

from fastapi import FastAPI, Query


def register_health_gate_routes(
    app: FastAPI,
    *,
    cfg,
    check_key: Callable[[str], None],
    check_rate: Callable[[str], None],
    gate_response: Callable[[str], dict],
    batch_cap: int = 50,
) -> None:
    """Register /health, /gate/{device_id}, POST /gate/batch on *app*."""

    @app.get("/health")
    def health():
        """API liveness check — does NOT require api_key."""
        return {
            "status": "ok",
            "operator_key_configured": bool(cfg.operator_api_key),
        }

    @app.get("/gate/{device_id}")
    def gate(device_id: str, api_key: str = Query(..., description="Shared operator API key")):
        """Single-device eligibility check with HMAC-signed response."""
        check_key(api_key)
        check_rate(api_key)
        return gate_response(device_id)

    @app.post("/gate/batch")
    def gate_batch(
        device_ids: list[str],
        api_key: str = Query(..., description="Shared operator API key"),
    ):
        """Batch eligibility check for up to 50 device IDs."""
        check_key(api_key)
        check_rate(api_key)
        return [gate_response(d) for d in device_ids[:batch_cap]]
