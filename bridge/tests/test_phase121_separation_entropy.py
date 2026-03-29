"""
Phase 121 — touchpad_spatial_entropy + separation_ratio_snapshots bridge tests.
8 tests total.
"""

import sys
import tempfile
import time
import pytest
from pathlib import Path

# Add bridge root and controller root to sys.path
BRIDGE_DIR = Path(__file__).parents[1]
CONTROLLER_DIR = Path(__file__).parents[2] / "controller"
sys.path.insert(0, str(BRIDGE_DIR))
sys.path.insert(0, str(CONTROLLER_DIR))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

from vapi_bridge.store import Store


def _make_store(tmp_path=None):
    import os
    if tmp_path is None:
        tmp_path = tempfile.mkdtemp()
    import os as _os
    db_path = _os.path.join(tmp_path, "test_phase121.db")
    return Store(db_path)


def _make_cfg():
    from unittest.mock import MagicMock
    cfg = MagicMock()
    cfg.separation_ratio_current = 0.474
    cfg.bt_transport_enabled = False
    cfg.bt_device_address = ""
    cfg.bt_sampling_rate_hz = 250
    cfg.operator_api_key = "test-key"
    cfg.rate_limit_requests_per_minute = 600
    cfg.ioswarm_enabled = False
    cfg.poad_registry_enabled = False
    cfg.ioswarm_adjudication_enabled = False
    cfg.ioswarm_vhp_mint_enabled = False
    cfg.ioswarm_renewal_enabled = False
    cfg.epoch_window_enabled = False
    cfg.dual_primitive_gate_enabled = False
    return cfg


# ---------------------------------------------------------------------------
# Test 1 — empty store returns []
# ---------------------------------------------------------------------------

def test_separation_ratio_snapshots_empty():
    store = _make_store()
    result = store.get_separation_ratio_status(limit=1)
    assert result == []


# ---------------------------------------------------------------------------
# Test 2 — insert + roundtrip
# ---------------------------------------------------------------------------

def test_insert_separation_ratio_snapshot_roundtrip():
    store = _make_store()
    row_id = store.insert_separation_ratio_snapshot(
        pooled_ratio=0.474,
        bt_strat_ratio=0.62,
        n_sessions=97,
        n_players=3,
        active_features=10,
        tournament_ready=False,
    )
    assert isinstance(row_id, int) and row_id > 0
    rows = store.get_separation_ratio_status(limit=1)
    assert len(rows) == 1
    r = rows[0]
    assert r["pooled_ratio"] == pytest.approx(0.474, abs=1e-4)
    assert r["bt_strat_ratio"] == pytest.approx(0.62, abs=1e-4)
    assert r["n_sessions"] == 97
    assert r["n_players"] == 3
    assert r["active_features"] == 10
    assert r["tournament_ready"] is False
    assert "id" in r
    assert "created_at" in r


# ---------------------------------------------------------------------------
# Test 3 — newest first ordering
# ---------------------------------------------------------------------------

def test_get_separation_ratio_newest_first():
    store = _make_store()
    store.insert_separation_ratio_snapshot(0.30, -1.0, 50, 2, 9, False)
    store.insert_separation_ratio_snapshot(0.55, 0.70, 97, 3, 10, False)
    rows = store.get_separation_ratio_status(limit=2)
    assert len(rows) == 2
    # Newest first
    assert rows[0]["pooled_ratio"] == pytest.approx(0.55, abs=1e-4)
    assert rows[1]["pooled_ratio"] == pytest.approx(0.30, abs=1e-4)


# ---------------------------------------------------------------------------
# Test 4 — schema version 121
# ---------------------------------------------------------------------------

def test_schema_version_121():
    store = _make_store()
    with store._conn() as conn:
        row = conn.execute(
            "SELECT migration_name FROM schema_versions WHERE phase=121"
        ).fetchone()
    assert row is not None
    assert row[0] == "separation_ratio"


# ---------------------------------------------------------------------------
# Test 5 — endpoint returns 7 keys
# ---------------------------------------------------------------------------

def test_separation_ratio_endpoint_7_keys():
    from fastapi.testclient import TestClient
    from vapi_bridge.operator_api import create_operator_app
    store = _make_store()
    cfg = _make_cfg()
    app = create_operator_app(cfg=cfg, store=store)
    client = TestClient(app, raise_server_exceptions=True)
    resp = client.get("/agent/separation-ratio-status", params={"api_key": "test-key"})
    assert resp.status_code == 200
    body = resp.json()
    required_keys = {
        "pooled_ratio", "battery_stratified_ratio", "tournament_blocker",
        "target_ratio", "gap_to_target", "tournament_ready", "timestamp",
    }
    assert required_keys.issubset(body.keys())


# ---------------------------------------------------------------------------
# Test 6 — endpoint values when ratio < 1.0
# ---------------------------------------------------------------------------

def test_separation_ratio_tournament_blocker_true():
    from fastapi.testclient import TestClient
    from vapi_bridge.operator_api import create_operator_app
    store = _make_store()
    cfg = _make_cfg()
    cfg.separation_ratio_current = 0.474
    app = create_operator_app(cfg=cfg, store=store)
    client = TestClient(app, raise_server_exceptions=True)
    resp = client.get("/agent/separation-ratio-status", params={"api_key": "test-key"})
    body = resp.json()
    assert body["tournament_blocker"] is True
    assert body["tournament_ready"] is False
    assert body["gap_to_target"] == pytest.approx(0.526, abs=0.01)
    assert body["target_ratio"] == 1.0


# ---------------------------------------------------------------------------
# Test 7 — touchpad_spatial_entropy static method
# ---------------------------------------------------------------------------

def test_touchpad_spatial_entropy_uniform_grid():
    from collections import deque
    from tinyml_biometric_fusion import BiometricFeatureExtractor

    # Build 64 unique (x, y) positions — one per cell of 8x8 grid
    # x range [0, 1920), y range [0, 1079)
    xy_ring: deque = deque(maxlen=1024)
    x_max, y_max = 1920.0, 1079.0
    grid_size = 8
    for row in range(grid_size):
        for col in range(grid_size):
            # Place one point in the centre of each cell
            x = int((col + 0.5) / grid_size * x_max)
            y = int((row + 0.5) / grid_size * y_max)
            xy_ring.append((x, y))

    import math
    entropy = BiometricFeatureExtractor._touchpad_spatial_entropy(
        xy_ring, grid_size=grid_size, x_max=x_max, y_max=y_max, min_frames=32
    )
    # Uniform distribution over 64 cells → max entropy = log2(64) = 6.0 bits
    assert abs(entropy - math.log2(64)) < 1e-6

    # Non-uniform: all points in one corner → entropy < uniform
    concentrated: deque = deque(maxlen=1024)
    for _ in range(64):
        concentrated.append((0, 0))
    low_entropy = BiometricFeatureExtractor._touchpad_spatial_entropy(
        concentrated, grid_size=grid_size, x_max=x_max, y_max=y_max, min_frames=32
    )
    assert low_entropy < entropy

    # Fewer than min_frames → returns 0.0
    short: deque = deque(maxlen=1024)
    for i in range(10):
        short.append((i * 100, i * 50))
    assert BiometricFeatureExtractor._touchpad_spatial_entropy(
        short, min_frames=32
    ) == 0.0


# ---------------------------------------------------------------------------
# Test 8 — Tool #89 structure
# ---------------------------------------------------------------------------

def test_tool_89_structure():
    from vapi_bridge.bridge_agent import BridgeAgent
    from unittest.mock import MagicMock
    cfg = _make_cfg()
    store = _make_store()
    agent = BridgeAgent(cfg, store)
    result = agent._execute_tool("get_separation_ratio_status", {})
    required = {
        "pooled_ratio", "battery_stratified_ratio", "tournament_blocker",
        "target_ratio", "gap_to_target", "tournament_ready", "timestamp",
    }
    assert required.issubset(result.keys())
