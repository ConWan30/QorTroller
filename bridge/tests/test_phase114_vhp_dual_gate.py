"""
Phase 114 — VHP Mint Dual-Primitive Gate
8 bridge tests
"""
import os
import sys
import time
import pytest
from unittest.mock import MagicMock, AsyncMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_store(tmp_path):
    from vapi_bridge.store import Store
    return Store(str(tmp_path / "test_p114.db"))


def _make_cfg(**kwargs):
    cfg = MagicMock()
    cfg.operator_api_key = "testkey114"
    cfg.rate_limit_per_minute = 1000
    cfg.dual_primitive_gate_enabled = False
    cfg.dual_primitive_gate_address = ""
    cfg.adjudication_registry_address = ""
    cfg.ioswarm_vhp_mint_enabled = False
    cfg.poad_registry_enabled = False
    cfg.poad_on_chain_enabled = False
    cfg.ioswarm_adjudication_enabled = False
    cfg.agent_dry_run_mode = True
    for k, v in kwargs.items():
        setattr(cfg, k, v)
    return cfg


# ---------------------------------------------------------------------------
# Test 1 — insert/get roundtrip
# ---------------------------------------------------------------------------

def test_insert_vhp_dual_gate_log_roundtrip(tmp_path):
    store = _make_store(tmp_path)
    row_id = store.insert_vhp_dual_gate_log(
        device_id="dev_t1",
        poad_hash="abc123",
        eligible=True,
        poac_valid=True,
        poad_valid=True,
        mint_allowed=True,
    )
    assert row_id >= 1
    logs = store.get_vhp_dual_gate_log(device_id="dev_t1", limit=5)
    assert len(logs) == 1
    r = logs[0]
    assert r["device_id"] == "dev_t1"
    assert r["poad_hash"] == "abc123"
    assert r["eligible"] is True
    assert r["poac_valid"] is True
    assert r["poad_valid"] is True
    assert r["mint_allowed"] is True
    assert "created_at" in r


# ---------------------------------------------------------------------------
# Test 2 — get_latest_poad_hash_for_device
# ---------------------------------------------------------------------------

def test_get_latest_poad_hash_for_device(tmp_path):
    store = _make_store(tmp_path)
    # No entry → None
    assert store.get_latest_poad_hash_for_device("dev_t2") is None
    # Insert a poad registry entry
    store.insert_poad_registry(
        device_id="dev_t2",
        poad_hash="deadbeef01",
        dual_veto=False,
        classj_verdict="CERTIFY",
        triage_verdict="CERTIFY",
        ts_ns=int(time.time() * 1e9),
    )
    result = store.get_latest_poad_hash_for_device("dev_t2")
    assert result == "deadbeef01"


# ---------------------------------------------------------------------------
# Test 3 — ORDER BY id DESC (newest-first)
# ---------------------------------------------------------------------------

def test_get_vhp_dual_gate_log_newest_first(tmp_path):
    store = _make_store(tmp_path)
    for i in range(3):
        store.insert_vhp_dual_gate_log(
            device_id="dev_t3",
            poad_hash=f"hash_{i}",
            eligible=bool(i % 2),
            poac_valid=True,
            poad_valid=True,
            mint_allowed=bool(i % 2),
        )
    logs = store.get_vhp_dual_gate_log(device_id="dev_t3", limit=10)
    assert len(logs) == 3
    ids = [r["id"] for r in logs]
    assert ids == sorted(ids, reverse=True), "must be newest-first (ORDER BY id DESC)"


# ---------------------------------------------------------------------------
# Test 4 — schema version 114
# ---------------------------------------------------------------------------

def test_schema_version_114(tmp_path):
    store = _make_store(tmp_path)
    with store._conn() as conn:
        row = conn.execute(
            "SELECT phase, migration_name FROM schema_versions WHERE phase = 114"
        ).fetchone()
    assert row is not None, "schema version 114 missing"
    assert row[0] == 114
    assert row[1] == "vhp_dual_gate"


# ---------------------------------------------------------------------------
# Test 5 — GET /agent/vhp-dual-gate-log returns 200 with all 6 required keys
# ---------------------------------------------------------------------------

def test_vhp_dual_gate_log_endpoint_6_keys(tmp_path):
    from fastapi.testclient import TestClient
    from vapi_bridge.operator_api import create_operator_app

    cfg = _make_cfg()
    store = _make_store(tmp_path)
    app = create_operator_app(cfg, store, chain=None)
    client = TestClient(app)

    resp = client.get("/agent/vhp-dual-gate-log?api_key=testkey114")
    assert resp.status_code == 200
    body = resp.json()
    for key in ("dual_primitive_gate_enabled", "total_checks",
                "eligible_count", "mint_allowed_count", "recent_logs", "timestamp"):
        assert key in body, f"missing key: {key}"
    assert isinstance(body["recent_logs"], list)


# ---------------------------------------------------------------------------
# Test 6 — device_id filter returns only that device's entries
# ---------------------------------------------------------------------------

def test_vhp_dual_gate_log_endpoint_device_filter(tmp_path):
    from fastapi.testclient import TestClient
    from vapi_bridge.operator_api import create_operator_app

    store = _make_store(tmp_path)
    for dev in ("dev_A", "dev_B"):
        store.insert_vhp_dual_gate_log(
            device_id=dev,
            poad_hash=f"h_{dev}",
            eligible=True,
            poac_valid=True,
            poad_valid=True,
            mint_allowed=True,
        )
    cfg = _make_cfg()
    app = create_operator_app(cfg, store, chain=None)
    client = TestClient(app)

    resp = client.get("/agent/vhp-dual-gate-log?api_key=testkey114&device_id=dev_A")
    assert resp.status_code == 200
    logs = resp.json()["recent_logs"]
    assert len(logs) == 1
    assert logs[0]["device_id"] == "dev_A"


# ---------------------------------------------------------------------------
# Test 7 — gate disabled → 422 hits audit gate, NOT dual-prim gate
# ---------------------------------------------------------------------------

def test_mint_vhp_gate_disabled_hits_early_gate(tmp_path):
    """When dual_primitive_gate_enabled=False, mint still rejects at audit gate
    (Gate 1) — NOT the dual-prim gate — confirming gate 5 is skipped."""
    from fastapi.testclient import TestClient
    from vapi_bridge.operator_api import create_operator_app

    cfg = _make_cfg(dual_primitive_gate_enabled=False, agent_dry_run_mode=True)
    store = _make_store(tmp_path)
    app = create_operator_app(cfg, store, chain=None)
    client = TestClient(app)

    resp = client.post(
        "/agent/mint-vhp?api_key=testkey114",
        json={"device_id": "dev_t7", "to_address": "0x1234"},
    )
    assert resp.status_code == 422
    detail = resp.json().get("detail", {})
    # The error must be about audit/validation — NOT dual_primitive_gate
    err_str = str(detail)
    assert "dual_primitive_gate" not in err_str, (
        "Gate 5 fired when dual_primitive_gate_enabled=False — should be skipped"
    )


# ---------------------------------------------------------------------------
# Test 8 — Tool #81 handler returns dict with all 6 required keys
# ---------------------------------------------------------------------------

def test_tool_81_structure(tmp_path):
    from vapi_bridge.bridge_agent import BridgeAgent

    store = _make_store(tmp_path)
    cfg = _make_cfg()
    agent = BridgeAgent.__new__(BridgeAgent)
    agent._store = store
    agent._cfg = cfg

    result = agent._execute_tool("get_vhp_dual_gate_log", {})

    required_keys = {
        "dual_primitive_gate_enabled",
        "total_checks",
        "eligible_count",
        "mint_allowed_count",
        "recent_logs",
        "timestamp",
    }
    assert required_keys.issubset(set(result.keys())), (
        f"Tool #81 missing keys: {required_keys - set(result.keys())}"
    )
