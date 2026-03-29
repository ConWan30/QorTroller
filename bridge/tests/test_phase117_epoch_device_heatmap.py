"""
Phase 117 — Per-Device Epoch Freshness Heatmap
8 bridge tests
"""
import os
import sys
import time
import pytest
from unittest.mock import MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_store(tmp_path):
    from vapi_bridge.store import Store
    return Store(str(tmp_path / "test_p117.db"))


def _make_cfg(**kwargs):
    cfg = MagicMock()
    cfg.operator_api_key = "testkey117"
    cfg.rate_limit_per_minute = 1000
    cfg.dual_primitive_gate_enabled = False
    cfg.dual_primitive_gate_address = ""
    cfg.adjudication_registry_address = ""
    cfg.ioswarm_vhp_mint_enabled = False
    cfg.poad_registry_enabled = False
    cfg.poad_on_chain_enabled = False
    cfg.ioswarm_adjudication_enabled = False
    cfg.agent_dry_run_mode = True
    cfg.epoch_window_enabled = False
    cfg.epoch_window_seconds = 86400.0
    for k, v in kwargs.items():
        setattr(cfg, k, v)
    return cfg


def _insert_gate_log(store, device_id, poad_age_seconds, epoch_window_ok=True):
    store.insert_vhp_dual_gate_log(
        device_id=device_id,
        poad_hash=f"hash_{poad_age_seconds}_{device_id}",
        eligible=True,
        poac_valid=True,
        poad_valid=True,
        mint_allowed=epoch_window_ok,
        poad_age_seconds=poad_age_seconds,
        epoch_window_ok=epoch_window_ok,
    )


# ---------------------------------------------------------------------------
# Test 1 — empty store returns empty devices list
# ---------------------------------------------------------------------------

def test_epoch_device_heatmap_empty(tmp_path):
    store = _make_store(tmp_path)
    result = store.get_epoch_window_analytics_by_device()
    assert result == []


# ---------------------------------------------------------------------------
# Test 2 — single device appears in result with correct analytics
# ---------------------------------------------------------------------------

def test_epoch_device_heatmap_single_device(tmp_path):
    store = _make_store(tmp_path)
    for age in [100.0, 200.0, 300.0, 400.0, 500.0]:
        _insert_gate_log(store, "dev_a", poad_age_seconds=age)
    result = store.get_epoch_window_analytics_by_device()
    assert len(result) == 1
    entry = result[0]
    assert entry["device_id"] == "dev_a"
    assert entry["check_count"] == 5
    assert entry["p50_age_seconds"] >= 200.0
    assert entry["p95_age_seconds"] >= 400.0


# ---------------------------------------------------------------------------
# Test 3 — multiple devices sorted by p95 DESC (worst first)
# ---------------------------------------------------------------------------

def test_epoch_device_heatmap_sorted_by_p95(tmp_path):
    store = _make_store(tmp_path)
    # dev_high has p95 around 9000
    for age in [8000.0, 9000.0, 9500.0]:
        _insert_gate_log(store, "dev_high", poad_age_seconds=age)
    # dev_low has p95 around 200
    for age in [100.0, 200.0, 300.0]:
        _insert_gate_log(store, "dev_low", poad_age_seconds=age)
    result = store.get_epoch_window_analytics_by_device()
    assert result[0]["device_id"] == "dev_high"
    assert result[1]["device_id"] == "dev_low"
    assert result[0]["p95_age_seconds"] > result[1]["p95_age_seconds"]


# ---------------------------------------------------------------------------
# Test 4 — blocked_count counts epoch_window_ok=False per device
# ---------------------------------------------------------------------------

def test_epoch_device_heatmap_blocked_count(tmp_path):
    store = _make_store(tmp_path)
    _insert_gate_log(store, "dev_b", poad_age_seconds=3600.0, epoch_window_ok=True)
    _insert_gate_log(store, "dev_b", poad_age_seconds=172800.0, epoch_window_ok=False)
    _insert_gate_log(store, "dev_b", poad_age_seconds=90000.0, epoch_window_ok=False)
    result = store.get_epoch_window_analytics_by_device()
    assert len(result) == 1
    assert result[0]["blocked_count"] == 2


# ---------------------------------------------------------------------------
# Test 5 — devices with only poad_age_seconds=-1 excluded
# ---------------------------------------------------------------------------

def test_epoch_device_heatmap_excludes_negative_age_only_devices(tmp_path):
    store = _make_store(tmp_path)
    # dev_real has genuine ages
    _insert_gate_log(store, "dev_real", poad_age_seconds=5000.0)
    # dev_neg has only -1 (default, no epoch check)
    store.insert_vhp_dual_gate_log(
        device_id="dev_neg", poad_hash="hp_neg",
        eligible=True, poac_valid=True, poad_valid=True, mint_allowed=True,
    )
    result = store.get_epoch_window_analytics_by_device()
    device_ids = [r["device_id"] for r in result]
    assert "dev_real" in device_ids
    assert "dev_neg" not in device_ids


# ---------------------------------------------------------------------------
# Test 6 — schema version 117
# ---------------------------------------------------------------------------

def test_schema_version_117(tmp_path):
    store = _make_store(tmp_path)
    with store._conn() as conn:
        row = conn.execute(
            "SELECT phase, migration_name FROM schema_versions WHERE phase = 117"
        ).fetchone()
    assert row is not None, "schema version 117 missing"
    assert row[0] == 117
    assert row[1] == "epoch_window_device_heatmap"


# ---------------------------------------------------------------------------
# Test 7 — GET /agent/epoch-window-device-heatmap returns 200 with required keys
# ---------------------------------------------------------------------------

def test_epoch_device_heatmap_endpoint_keys(tmp_path):
    from fastapi.testclient import TestClient
    from vapi_bridge.operator_api import create_operator_app

    cfg = _make_cfg()
    store = _make_store(tmp_path)
    app = create_operator_app(cfg, store, chain=None)
    client = TestClient(app)

    _insert_gate_log(store, "dev_ep", poad_age_seconds=1234.0)

    resp = client.get("/agent/epoch-window-device-heatmap?api_key=testkey117")
    assert resp.status_code == 200
    body = resp.json()
    for key in ("epoch_window_enabled", "epoch_window_seconds", "total_devices", "devices", "timestamp"):
        assert key in body, f"missing key: {key}"
    assert body["total_devices"] == 1
    assert body["devices"][0]["device_id"] == "dev_ep"


# ---------------------------------------------------------------------------
# Test 8 — Tool #83 handler returns required keys
# ---------------------------------------------------------------------------

def test_tool_83_structure(tmp_path):
    from vapi_bridge.bridge_agent import BridgeAgent

    store = _make_store(tmp_path)
    cfg = _make_cfg()
    agent = BridgeAgent.__new__(BridgeAgent)
    agent._store = store
    agent._cfg = cfg

    result = agent._execute_tool("get_epoch_window_device_heatmap", {})

    required_keys = {
        "epoch_window_enabled", "epoch_window_seconds",
        "total_devices", "devices", "timestamp",
    }
    assert required_keys.issubset(set(result.keys())), (
        f"Tool #83 missing keys: {required_keys - set(result.keys())}"
    )
