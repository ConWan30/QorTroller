"""Endpoint test: GET /bridge/connectivity registers + returns an honest BCRA attestation."""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

try:
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
except Exception:  # pragma: no cover
    pytest.skip("fastapi/testclient unavailable", allow_module_level=True)

from vapi_bridge.operator_api.agent_grind import register_agent_grind_routes  # noqa: E402


def _app(monitor_status=None, paused=True, wd=None, gic=None):
    app = FastAPI()
    cfg = SimpleNamespace(chain_submission_paused=paused, grind_session_id="grind_test",
                          pcc_enabled=True, grind_mode=False, grind_target=100)
    store = MagicMock()
    store.get_watchdog_event_chain_status.return_value = wd or {"chain_intact": True, "restarts_last_hour": 0}
    store.get_grind_chain_status.return_value = gic or {"chain_intact": True}
    store.get_validation_summary.return_value = {"latest_gameplay_context": None}
    chain = SimpleNamespace(_sync_w3=None)   # no RPC handle -> rpc_reachable None (UNKNOWN), honest
    noop = lambda *a, **k: None
    register_agent_grind_routes(app, cfg=cfg, store=store, chain=chain,
                                check_key=noop, check_rate=noop, check_read_key=noop,
                                check_agent_token=noop)
    if monitor_status is not None:
        app._pcc_monitor = SimpleNamespace(get_status=lambda: monitor_status)
    return app


def test_route_registered():
    paths = {r.path for r in _app().routes}
    assert "/bridge/connectivity" in paths


def test_connectivity_killswitch_on_is_not_live():
    """With the kill-switch ON, the bridge must NOT report itself fully connected/live."""
    app = _app(monitor_status={"capture_state": "NOMINAL", "host_state": "EXCLUSIVE_USB",
                               "poll_rate_hz": 1000}, paused=True)
    r = TestClient(app).get("/bridge/connectivity")
    assert r.status_code == 200
    body = r.json()
    assert body["schema"] == "vapi-bridge-connectivity-v1"
    assert body["lanes"]["chain"]["state"] == "degraded"        # kill-switch on -> degraded
    assert body["lanes"]["controller"]["state"] == "connected"  # NOMINAL + EXCLUSIVE_USB
    assert body["visual_state"] != "live"                       # honest: not fully live while paused


def test_connectivity_all_green_when_unpaused_and_monitor_ok():
    app = _app(monitor_status={"capture_state": "NOMINAL", "host_state": "EXCLUSIVE_USB",
                               "poll_rate_hz": 1000}, paused=False)
    # chain rpc_reachable is None (no _sync_w3) -> chain UNKNOWN, agents UNKNOWN (deferred)
    body = TestClient(app).get("/bridge/connectivity").json()
    # not live (agents/chain unknown) but controller + operational connected — honest DEGRADED
    assert body["verdict"] in ("degraded", "fully_connected")
    assert body["lanes"]["operational"]["state"] == "connected"


def test_operational_chain_break_disconnects_lane():
    app = _app(monitor_status={"capture_state": "NOMINAL", "host_state": "EXCLUSIVE_USB", "poll_rate_hz": 1000},
               paused=False, wd={"chain_intact": False, "restarts_last_hour": 0})
    body = TestClient(app).get("/bridge/connectivity").json()
    assert body["lanes"]["operational"]["state"] == "disconnected"
    assert body["verdict"] == "partially_connected"
