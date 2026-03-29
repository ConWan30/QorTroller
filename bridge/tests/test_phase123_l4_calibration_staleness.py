"""
Phase 123 — L4 Calibration Staleness Monitor
Bridge tests: 8 tests covering store, endpoint, and staleness logic.

Test plan:
1. Empty l4_calibration_log returns []
2. insert_l4_calibration_log roundtrip — all 8 fields correct
3. get_l4_calibration_log newest-first ordering
4. schema_version 123 present after store init
5. GET /agent/l4-calibration-status returns 8 required keys
6. stale=True when live_feature_dim=13 != calibration_feature_dim=12 (default state)
7. stale=False when dims match (live=13, calib=13)
8. config defaults: live_feature_dim=13, calibration_feature_dim=12, n_sessions=74
"""
from __future__ import annotations

import sys
import os
import tempfile
import pytest
from pathlib import Path
from unittest.mock import MagicMock

BRIDGE_DIR = Path(__file__).parents[1]
sys.path.insert(0, str(BRIDGE_DIR))

from vapi_bridge.store import Store


def _make_store(tmp_path=None):
    if tmp_path is None:
        tmp_path = tempfile.mkdtemp()
    db_path = os.path.join(tmp_path, "test_phase123.db")
    return Store(db_path)


def _make_cfg(**kwargs):
    cfg = MagicMock()
    cfg.operator_api_key = "test-key"
    cfg.rate_limit_per_minute = 6000
    cfg.live_feature_dim = kwargs.get("live_feature_dim", 13)
    cfg.calibration_feature_dim = kwargs.get("calibration_feature_dim", 12)
    cfg.calibration_n_sessions = kwargs.get("calibration_n_sessions", 74)
    cfg.calibration_timestamp = kwargs.get("calibration_timestamp", 0.0)
    cfg.l4_anomaly_threshold = kwargs.get("l4_anomaly_threshold", 7.009)
    cfg.l4_continuity_threshold = kwargs.get("l4_continuity_threshold", 5.367)
    cfg.confidence_multiplier_enabled = False
    cfg.separation_ratio_current = 0.474
    cfg.ioswarm_enabled = False
    cfg.poad_registry_enabled = False
    cfg.ioswarm_adjudication_enabled = False
    cfg.ioswarm_vhp_mint_enabled = False
    cfg.ioswarm_renewal_enabled = False
    cfg.epoch_window_enabled = False
    cfg.dual_primitive_gate_enabled = False
    cfg.bt_transport_enabled = False
    return cfg


# ---------------------------------------------------------------------------
# Test 1 — empty log returns []
# ---------------------------------------------------------------------------

def test_l4_calibration_log_empty():
    store = _make_store()
    result = store.get_l4_calibration_log()
    assert isinstance(result, list)
    assert result == []


# ---------------------------------------------------------------------------
# Test 2 — insert + roundtrip — all fields correct
# ---------------------------------------------------------------------------

def test_insert_l4_calibration_log_roundtrip():
    store = _make_store()
    import time
    ts = time.time() - 1000.0
    rid = store.insert_l4_calibration_log(
        feature_dim=12,
        n_sessions=74,
        anomaly_threshold=7.009,
        continuity_threshold=5.367,
        calibration_timestamp=ts,
        stale_flag=True,
    )
    assert isinstance(rid, int) and rid > 0
    log = store.get_l4_calibration_log()
    assert len(log) == 1
    entry = log[0]
    assert entry["feature_dim"] == 12
    assert entry["n_sessions"] == 74
    assert entry["anomaly_threshold"] == pytest.approx(7.009, abs=1e-4)
    assert entry["continuity_threshold"] == pytest.approx(5.367, abs=1e-4)
    assert entry["calibration_timestamp"] == pytest.approx(ts, abs=1.0)
    assert entry["stale_flag"] is True
    assert "created_at" in entry
    assert "id" in entry


# ---------------------------------------------------------------------------
# Test 3 — newest-first ordering
# ---------------------------------------------------------------------------

def test_l4_calibration_log_newest_first():
    store = _make_store()
    store.insert_l4_calibration_log(12, 74, 7.009, 5.367, 0.0, True)
    store.insert_l4_calibration_log(13, 97, 7.150, 5.490, 1.0, False)
    log = store.get_l4_calibration_log()
    assert log[0]["feature_dim"] == 13
    assert log[1]["feature_dim"] == 12


# ---------------------------------------------------------------------------
# Test 4 — schema_version 123
# ---------------------------------------------------------------------------

def test_schema_version_123():
    store = _make_store()
    with store._conn() as conn:
        row = conn.execute(
            "SELECT migration_name FROM schema_versions WHERE phase=123"
        ).fetchone()
    assert row is not None
    assert row[0] == "l4_calibration_staleness"


# ---------------------------------------------------------------------------
# Test 5 — endpoint returns 8 required keys
# ---------------------------------------------------------------------------

def test_l4_calibration_endpoint_8_keys():
    from fastapi.testclient import TestClient
    from vapi_bridge.operator_api import create_operator_app
    store = _make_store()
    cfg = _make_cfg()
    app = create_operator_app(cfg=cfg, store=store)
    client = TestClient(app, raise_server_exceptions=True)
    resp = client.get("/agent/l4-calibration-status", params={"api_key": "test-key"})
    assert resp.status_code == 200
    data = resp.json()
    required_keys = {
        "current_feature_dim", "calibration_feature_dim", "stale",
        "anomaly_threshold", "continuity_threshold",
        "calibration_n_sessions", "calibration_timestamp", "timestamp",
    }
    assert required_keys.issubset(data.keys())


# ---------------------------------------------------------------------------
# Test 6 — stale=True when live_feature_dim=13 != calibration_feature_dim=12
# ---------------------------------------------------------------------------

def test_stale_true_when_dims_differ():
    from fastapi.testclient import TestClient
    from vapi_bridge.operator_api import create_operator_app
    store = _make_store()
    cfg = _make_cfg(live_feature_dim=13, calibration_feature_dim=12)
    app = create_operator_app(cfg=cfg, store=store)
    client = TestClient(app, raise_server_exceptions=True)
    resp = client.get("/agent/l4-calibration-status", params={"api_key": "test-key"})
    data = resp.json()
    assert data["stale"] is True
    assert data["current_feature_dim"] == 13
    assert data["calibration_feature_dim"] == 12


# ---------------------------------------------------------------------------
# Test 7 — stale=False when dims match
# ---------------------------------------------------------------------------

def test_stale_false_when_dims_match():
    from fastapi.testclient import TestClient
    from vapi_bridge.operator_api import create_operator_app
    store = _make_store()
    cfg = _make_cfg(live_feature_dim=13, calibration_feature_dim=13)
    app = create_operator_app(cfg=cfg, store=store)
    client = TestClient(app, raise_server_exceptions=True)
    resp = client.get("/agent/l4-calibration-status", params={"api_key": "test-key"})
    data = resp.json()
    assert data["stale"] is False
    assert data["current_feature_dim"] == 13
    assert data["calibration_feature_dim"] == 13


# ---------------------------------------------------------------------------
# Test 8 — config defaults
# ---------------------------------------------------------------------------

def test_config_defaults_phase123():
    from vapi_bridge.config import Config
    cfg = Config()
    assert cfg.live_feature_dim == 13
    assert cfg.calibration_feature_dim == 12
    assert cfg.calibration_n_sessions == 74
    assert cfg.calibration_timestamp == pytest.approx(0.0)
