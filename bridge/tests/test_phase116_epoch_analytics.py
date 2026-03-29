"""
Phase 116 — Epoch-Window Analytics + Recommended Window Advisor
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
    return Store(str(tmp_path / "test_p116.db"))


def _make_cfg(**kwargs):
    cfg = MagicMock()
    cfg.operator_api_key = "testkey116"
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
        poad_hash=f"hash_{poad_age_seconds}",
        eligible=True,
        poac_valid=True,
        poad_valid=True,
        mint_allowed=epoch_window_ok,
        poad_age_seconds=poad_age_seconds,
        epoch_window_ok=epoch_window_ok,
    )


# ---------------------------------------------------------------------------
# Test 1 — empty store returns safe defaults
# ---------------------------------------------------------------------------

def test_get_epoch_window_analytics_empty(tmp_path):
    store = _make_store(tmp_path)
    result = store.get_epoch_window_analytics()
    assert result["total_gate5_checks"] == 0
    assert result["staleness_blocked_count"] == 0
    assert result["checked_count"] == 0
    assert result["p50_age_seconds"] == -1.0
    assert result["p95_age_seconds"] == -1.0
    assert result["recommended_window_seconds"] == 86400.0


# ---------------------------------------------------------------------------
# Test 2 — percentiles computed correctly from known age values
# ---------------------------------------------------------------------------

def test_epoch_window_analytics_percentiles(tmp_path):
    store = _make_store(tmp_path)
    # Insert 10 entries with ages 100, 200, ..., 1000 seconds
    for age in range(100, 1100, 100):
        _insert_gate_log(store, "dev_pct", poad_age_seconds=float(age))
    result = store.get_epoch_window_analytics()
    assert result["checked_count"] == 10
    # p50 should be around 500–600 (idx=5 of 10 sorted values = 600)
    assert result["p50_age_seconds"] >= 400.0
    assert result["p95_age_seconds"] >= 800.0
    # recommended = 2 × p95 floored 3600
    assert result["recommended_window_seconds"] >= 3600.0


# ---------------------------------------------------------------------------
# Test 3 — staleness_blocked_count counts epoch_window_ok=False rows
# ---------------------------------------------------------------------------

def test_epoch_window_analytics_blocked_count(tmp_path):
    store = _make_store(tmp_path)
    _insert_gate_log(store, "dev_b", poad_age_seconds=3600.0, epoch_window_ok=True)
    _insert_gate_log(store, "dev_b", poad_age_seconds=172800.0, epoch_window_ok=False)
    _insert_gate_log(store, "dev_b", poad_age_seconds=90000.0, epoch_window_ok=False)
    result = store.get_epoch_window_analytics()
    assert result["staleness_blocked_count"] == 2


# ---------------------------------------------------------------------------
# Test 4 — rows with poad_age_seconds = -1 excluded from percentile computation
# ---------------------------------------------------------------------------

def test_epoch_window_analytics_excludes_negative_age(tmp_path):
    store = _make_store(tmp_path)
    # 5 rows with real ages
    for age in [1000.0, 2000.0, 3000.0, 4000.0, 5000.0]:
        _insert_gate_log(store, "dev_ex", poad_age_seconds=age)
    # 3 rows with default -1 (no epoch window check)
    for _ in range(3):
        store.insert_vhp_dual_gate_log(
            device_id="dev_ex2", poad_hash="hp_neg",
            eligible=True, poac_valid=True, poad_valid=True, mint_allowed=True,
        )
    result = store.get_epoch_window_analytics()
    # total includes all 8 rows; checked_count only the 5 with real ages
    assert result["total_gate5_checks"] == 8
    assert result["checked_count"] == 5


# ---------------------------------------------------------------------------
# Test 5 — schema version 116
# ---------------------------------------------------------------------------

def test_schema_version_116(tmp_path):
    store = _make_store(tmp_path)
    with store._conn() as conn:
        row = conn.execute(
            "SELECT phase, migration_name FROM schema_versions WHERE phase = 116"
        ).fetchone()
    assert row is not None, "schema version 116 missing"
    assert row[0] == 116
    assert row[1] == "epoch_window_analytics"


# ---------------------------------------------------------------------------
# Test 6 — GET /agent/epoch-window-analytics returns 200 with required keys
# ---------------------------------------------------------------------------

def test_epoch_window_analytics_endpoint_keys(tmp_path):
    from fastapi.testclient import TestClient
    from vapi_bridge.operator_api import create_operator_app

    cfg = _make_cfg()
    store = _make_store(tmp_path)
    app = create_operator_app(cfg, store, chain=None)
    client = TestClient(app)

    resp = client.get("/agent/epoch-window-analytics?api_key=testkey116")
    assert resp.status_code == 200
    body = resp.json()
    for key in (
        "epoch_window_enabled", "epoch_window_seconds",
        "total_gate5_checks", "staleness_blocked_count",
        "checked_count", "p50_age_seconds", "p95_age_seconds",
        "recommended_window_seconds", "timestamp",
    ):
        assert key in body, f"missing key: {key}"


# ---------------------------------------------------------------------------
# Test 7 — Tool #82 handler returns required keys
# ---------------------------------------------------------------------------

def test_tool_82_structure(tmp_path):
    from vapi_bridge.bridge_agent import BridgeAgent

    store = _make_store(tmp_path)
    cfg = _make_cfg()
    agent = BridgeAgent.__new__(BridgeAgent)
    agent._store = store
    agent._cfg = cfg

    result = agent._execute_tool("get_epoch_window_analytics", {})

    required_keys = {
        "epoch_window_enabled", "epoch_window_seconds",
        "total_gate5_checks", "staleness_blocked_count",
        "checked_count", "p50_age_seconds", "p95_age_seconds",
        "recommended_window_seconds", "timestamp",
    }
    assert required_keys.issubset(set(result.keys())), (
        f"Tool #82 missing keys: {required_keys - set(result.keys())}"
    )


# ---------------------------------------------------------------------------
# Test 8 — recommended_window_seconds defaults to 86400 when < 10 checked samples
# ---------------------------------------------------------------------------

def test_recommended_window_fallback_under_10_samples(tmp_path):
    store = _make_store(tmp_path)
    # Only 5 real age samples — below the 10-sample threshold
    for age in [100.0, 200.0, 300.0, 400.0, 500.0]:
        _insert_gate_log(store, "dev_fw", poad_age_seconds=age)
    result = store.get_epoch_window_analytics()
    assert result["checked_count"] == 5
    assert result["recommended_window_seconds"] == 86400.0
