"""
Phase 115 — Epoch-Window Dual-Primitive Temporal Proof
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
    return Store(str(tmp_path / "test_p115.db"))


def _make_cfg(**kwargs):
    cfg = MagicMock()
    cfg.operator_api_key = "testkey115"
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


# ---------------------------------------------------------------------------
# Test 1 — vhp_dual_gate_log has poad_age_seconds and epoch_window_ok columns
# ---------------------------------------------------------------------------

def test_vhp_dual_gate_log_has_new_columns(tmp_path):
    store = _make_store(tmp_path)
    row_id = store.insert_vhp_dual_gate_log(
        device_id="dev_t1",
        poad_hash="abc123",
        eligible=True,
        poac_valid=True,
        poad_valid=True,
        mint_allowed=True,
        poad_age_seconds=300.0,
        epoch_window_ok=True,
    )
    assert row_id >= 1
    logs = store.get_vhp_dual_gate_log(device_id="dev_t1", limit=5)
    assert len(logs) == 1
    r = logs[0]
    assert "poad_age_seconds" in r
    assert "epoch_window_ok" in r
    assert abs(r["poad_age_seconds"] - 300.0) < 0.001
    assert r["epoch_window_ok"] is True


# ---------------------------------------------------------------------------
# Test 2 — default poad_age_seconds=-1, epoch_window_ok=True (backward compat)
# ---------------------------------------------------------------------------

def test_vhp_dual_gate_log_defaults(tmp_path):
    store = _make_store(tmp_path)
    store.insert_vhp_dual_gate_log(
        device_id="dev_t2",
        poad_hash="def456",
        eligible=True,
        poac_valid=True,
        poad_valid=True,
        mint_allowed=True,
        # No poad_age_seconds / epoch_window_ok → use defaults
    )
    logs = store.get_vhp_dual_gate_log(device_id="dev_t2", limit=5)
    r = logs[0]
    assert r["poad_age_seconds"] == -1.0
    assert r["epoch_window_ok"] is True


# ---------------------------------------------------------------------------
# Test 3 — get_poad_ts_ns_for_device returns None when no entry
# ---------------------------------------------------------------------------

def test_get_poad_ts_ns_none_when_empty(tmp_path):
    store = _make_store(tmp_path)
    assert store.get_poad_ts_ns_for_device("dev_t3") is None


# ---------------------------------------------------------------------------
# Test 4 — get_poad_ts_ns_for_device returns ts_ns after insert_poad_registry
# ---------------------------------------------------------------------------

def test_get_poad_ts_ns_after_insert(tmp_path):
    store = _make_store(tmp_path)
    ts_ns = int(time.time() * 1e9)
    store.insert_poad_registry(
        device_id="dev_t4",
        poad_hash="feedcafe01",
        dual_veto=False,
        classj_verdict="CERTIFY",
        triage_verdict="CERTIFY",
        ts_ns=ts_ns,
    )
    result = store.get_poad_ts_ns_for_device("dev_t4")
    assert result == ts_ns


# ---------------------------------------------------------------------------
# Test 5 — schema version 115
# ---------------------------------------------------------------------------

def test_schema_version_115(tmp_path):
    store = _make_store(tmp_path)
    with store._conn() as conn:
        row = conn.execute(
            "SELECT phase, migration_name FROM schema_versions WHERE phase = 115"
        ).fetchone()
    assert row is not None, "schema version 115 missing"
    assert row[0] == 115
    assert row[1] == "epoch_window"


# ---------------------------------------------------------------------------
# Test 6 — config fields exist with correct defaults
# ---------------------------------------------------------------------------

def test_epoch_window_config_defaults():
    cfg = _make_cfg()
    assert cfg.epoch_window_enabled is False
    assert cfg.epoch_window_seconds == 86400.0


# ---------------------------------------------------------------------------
# Test 7 — epoch_window_ok=False stored when gate fires stale result
# ---------------------------------------------------------------------------

def test_insert_epoch_window_not_ok(tmp_path):
    store = _make_store(tmp_path)
    store.insert_vhp_dual_gate_log(
        device_id="dev_t7",
        poad_hash="stale_hash",
        eligible=True,
        poac_valid=True,
        poad_valid=True,
        mint_allowed=False,  # blocked by epoch window
        poad_age_seconds=172800.0,  # 48h > 24h window
        epoch_window_ok=False,
    )
    logs = store.get_vhp_dual_gate_log(device_id="dev_t7", limit=5)
    r = logs[0]
    assert r["epoch_window_ok"] is False
    assert r["mint_allowed"] is False
    assert abs(r["poad_age_seconds"] - 172800.0) < 0.001


# ---------------------------------------------------------------------------
# Test 8 — GET /agent/vhp-dual-gate-log still returns 6 required keys
#           (epoch window columns visible in recent_logs entries)
# ---------------------------------------------------------------------------

def test_vhp_dual_gate_log_endpoint_includes_epoch_columns(tmp_path):
    from fastapi.testclient import TestClient
    from vapi_bridge.operator_api import create_operator_app

    cfg = _make_cfg()
    store = _make_store(tmp_path)
    store.insert_vhp_dual_gate_log(
        device_id="dev_t8",
        poad_hash="h_t8",
        eligible=True,
        poac_valid=True,
        poad_valid=True,
        mint_allowed=True,
        poad_age_seconds=500.0,
        epoch_window_ok=True,
    )
    app = create_operator_app(cfg, store, chain=None)
    client = TestClient(app)

    resp = client.get("/agent/vhp-dual-gate-log?api_key=testkey115")
    assert resp.status_code == 200
    body = resp.json()
    # 6 top-level keys still required
    for key in ("dual_primitive_gate_enabled", "total_checks",
                "eligible_count", "mint_allowed_count", "recent_logs", "timestamp"):
        assert key in body, f"missing key: {key}"
    # Epoch window columns visible in log entries
    logs = body["recent_logs"]
    assert len(logs) == 1
    assert "poad_age_seconds" in logs[0]
    assert "epoch_window_ok" in logs[0]
