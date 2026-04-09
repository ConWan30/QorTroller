# bridge/tests/test_phase148_acim.py
# Phase 148 — AgentCalibrationIntegrityMonitor (ACIM) tests
# 8 tests: table schema, insert/get roundtrip, per-agent filter, config fields,
#          _test_agent_16 permanent-false invariant, agent #2 threshold cross-validation,
#          endpoint 6 keys, Tool #105 6 keys.

import asyncio
import sys
import tempfile
import os
import time

# -- Web3/eth_account stub (same pattern as prior phases) ---------------------
from unittest.mock import MagicMock, AsyncMock, patch
_w3 = MagicMock()
sys.modules.setdefault("web3", _w3)
sys.modules.setdefault("web3.exceptions", MagicMock())
sys.modules.setdefault("eth_account", MagicMock())

import pytest

# ---------------------------------------------------------------------------

def _make_store():
    tmp = tempfile.mkdtemp()
    db  = os.path.join(tmp, "test_phase148.db")
    from bridge.vapi_bridge.store import Store
    return Store(db)


def _make_cfg(**kwargs):
    from bridge.vapi_bridge.config import Config
    from dataclasses import fields
    valid = {f.name for f in fields(Config)}
    base = dict(
        http_enabled=True,
        bridge_private_key="0x" + "aa" * 32,
        verifier_address="0x" + "bb" * 20,
        operator_api_key="test-key",
        agent_calibration_monitor_enabled=True,
        mcp_server_enabled=False,
        mcp_server_port=8081,
        auto_activate_on_breakthrough=False,
    )
    base.update({k: v for k, v in kwargs.items() if k in valid})
    return Config(**{k: v for k, v in base.items() if k in valid})


# Test 1 — agent_calibration_health table exists and insert+get roundtrip
def test_1_table_and_insert_roundtrip():
    store = _make_store()
    row_id = store.insert_agent_calibration_health(
        agent_id=1,
        agent_name="SessionIngestAgent",
        test_name="poac_wire_format_228_bytes",
        result="PASS",
        details="POAC_RECORD_SIZE=228 (expected 228)",
    )
    assert row_id >= 1
    rows = store.get_agent_calibration_health(limit=10)
    assert len(rows) == 1
    r = rows[0]
    assert r["agent_id"] == 1
    assert r["agent_name"] == "SessionIngestAgent"
    assert r["test_name"] == "poac_wire_format_228_bytes"
    assert r["result"] == "PASS"
    assert "details" in r
    assert r["created_at"] > 0


# Test 2 — FAIL result stored correctly
def test_2_fail_result_stored():
    store = _make_store()
    store.insert_agent_calibration_health(
        agent_id=2,
        agent_name="L4GateAgent",
        test_name="l4_threshold_bounds_cross_validation",
        result="FAIL",
        details="anomaly=99.0 out of bounds [5.0-15.0]",
    )
    rows = store.get_agent_calibration_health(limit=10)
    assert rows[0]["result"] == "FAIL"
    assert "out of bounds" in rows[0]["details"]


# Test 3 — per-agent filter works correctly
def test_3_per_agent_filter():
    store = _make_store()
    store.insert_agent_calibration_health(1, "SessionIngestAgent", "test_a", "PASS", "")
    store.insert_agent_calibration_health(2, "L4GateAgent", "test_b", "FAIL", "")
    store.insert_agent_calibration_health(3, "CertAgent", "test_c", "PASS", "")

    rows_all    = store.get_agent_calibration_health(limit=10)
    rows_agent2 = store.get_agent_calibration_health(limit=10, agent_id=2)
    assert len(rows_all) == 3
    assert len(rows_agent2) == 1
    assert rows_agent2[0]["agent_name"] == "L4GateAgent"


# Test 4 — config fields present (agent_calibration_monitor_enabled + mcp_server_enabled)
def test_4_config_fields():
    cfg = _make_cfg()
    assert hasattr(cfg, "agent_calibration_monitor_enabled")
    assert hasattr(cfg, "mcp_server_enabled")
    assert hasattr(cfg, "mcp_server_port")
    assert cfg.agent_calibration_monitor_enabled is True
    assert cfg.mcp_server_enabled is False
    assert cfg.mcp_server_port == 8081


# Test 5 — _test_agent_16: auto_activate_on_breakthrough PERMANENT False invariant
def test_5_agent16_auto_activate_false():
    store = _make_store()
    cfg   = _make_cfg(auto_activate_on_breakthrough=False)
    from bridge.vapi_bridge.agent_calibration_monitor import AgentCalibrationMonitor
    acim = AgentCalibrationMonitor(cfg, store, bus=None)

    result = asyncio.get_event_loop().run_until_complete(acim._test_agent_16())
    assert result["passed"] is True
    assert "PERMANENT INVARIANT" in result["details"] or "False" in result["details"]

    # Simulate a hypothetical True value (should fail)
    cfg2 = _make_cfg()
    object.__setattr__(cfg2, "auto_activate_on_breakthrough", True)  # type: ignore
    acim2 = AgentCalibrationMonitor(cfg2, store, bus=None)
    result2 = asyncio.get_event_loop().run_until_complete(acim2._test_agent_16())
    assert result2["passed"] is False


# Test 6 — _test_agent_2: L4 threshold cross-validation against bounds
def test_6_agent2_threshold_cross_validation():
    store = _make_store()
    cfg   = _make_cfg()
    from bridge.vapi_bridge.agent_calibration_monitor import AgentCalibrationMonitor
    acim  = AgentCalibrationMonitor(cfg, store, bus=None)

    result = asyncio.get_event_loop().run_until_complete(acim._test_agent_2())
    assert result["passed"] is True
    assert "anomaly" in result["details"]
    assert "continuity" in result["details"]


# Test 7 — GET /agent/calibration-health endpoint returns 6 required keys
def test_7_endpoint_6_keys():
    store = _make_store()
    cfg   = _make_cfg()
    store.insert_agent_calibration_health(1, "SessionIngestAgent", "test_a", "PASS", "ok")
    store.insert_agent_calibration_health(2, "L4GateAgent", "test_b", "PASS", "ok")

    from fastapi.testclient import TestClient
    from bridge.vapi_bridge.operator_api import create_operator_app
    app    = create_operator_app(cfg, store)
    client = TestClient(app, raise_server_exceptions=True)
    resp   = client.get("/agent/calibration-health", params={"api_key": "test-key"})
    assert resp.status_code == 200
    data   = resp.json()
    for key in ("agent_count", "healthy_count", "degraded_count",
                "failed_agents", "latest_tests", "mcp_server_enabled"):
        assert key in data, f"missing key: {key}"
    assert data["agent_count"] == 16
    assert isinstance(data["failed_agents"], list)
    assert isinstance(data["latest_tests"], list)


# Test 8 — Tool #105 get_agent_calibration_health returns 6 required keys
def test_8_tool_105_six_keys():
    store = _make_store()
    cfg   = _make_cfg()
    store.insert_agent_calibration_health(16, "TournamentActivationChainAgent",
                                          "auto_activate_false", "PASS", "PERMANENT False")

    from bridge.vapi_bridge.bridge_agent import BridgeAgent
    agent = BridgeAgent(cfg=cfg, store=store)
    result = agent._execute_tool("get_agent_calibration_health", {})

    required_keys = ("agent_count", "healthy_count", "degraded_count",
                     "failed_agents", "mcp_server_enabled", "timestamp")
    for key in required_keys:
        assert key in result, f"missing key: {key}"
    assert result["agent_count"] == 16
    assert isinstance(result["failed_agents"], list)
