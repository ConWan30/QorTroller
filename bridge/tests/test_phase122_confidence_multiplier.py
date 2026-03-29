"""
Phase 122 — VHP Confidence Score Separation Ratio Multiplier
Bridge tests: 8 tests covering store, endpoint, and config.

Test plan:
1. Empty log returns []
2. insert_confidence_multiplier_log roundtrip — all 7 fields correct
3. get_confidence_multiplier_log newest-first ordering
4. get_confidence_multiplier_log device_id filter
5. schema_version 122 present after store init
6. GET /agent/confidence-score-multiplier-status returns 7 required keys
7. effective_multiplier computation — bt_strat_ratio=0.62→0.62; ratio>1→1.0; no snap→1.0
8. config defaults: confidence_multiplier_enabled=False, confidence_multiplier_floor=0.0
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
    db_path = os.path.join(tmp_path, "test_phase122.db")
    return Store(db_path)


def _make_cfg(**kwargs):
    cfg = MagicMock()
    cfg.operator_api_key = "test-key"
    cfg.rate_limit_per_minute = 6000
    cfg.confidence_multiplier_enabled = kwargs.get("confidence_multiplier_enabled", False)
    cfg.confidence_multiplier_floor = kwargs.get("confidence_multiplier_floor", 0.0)
    cfg.separation_ratio_current = kwargs.get("separation_ratio_current", 0.474)
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

def test_confidence_multiplier_log_empty():
    store = _make_store()
    result = store.get_confidence_multiplier_log()
    assert isinstance(result, list)
    assert result == []


# ---------------------------------------------------------------------------
# Test 2 — insert + roundtrip — all fields correct
# ---------------------------------------------------------------------------

def test_insert_confidence_multiplier_roundtrip():
    store = _make_store()
    rid = store.insert_confidence_multiplier_log(
        device_id="dev-abc",
        original_score=9000,
        multiplier=0.62,
        final_score=5580,
        bt_strat_ratio=0.62,
    )
    assert isinstance(rid, int) and rid > 0
    log = store.get_confidence_multiplier_log()
    assert len(log) == 1
    entry = log[0]
    assert entry["device_id"] == "dev-abc"
    assert entry["original_score"] == 9000
    assert entry["multiplier"] == pytest.approx(0.62, abs=1e-4)
    assert entry["final_score"] == 5580
    assert entry["bt_strat_ratio"] == pytest.approx(0.62, abs=1e-4)
    assert "created_at" in entry
    assert "id" in entry


# ---------------------------------------------------------------------------
# Test 3 — newest-first ordering
# ---------------------------------------------------------------------------

def test_get_confidence_multiplier_log_newest_first():
    store = _make_store()
    store.insert_confidence_multiplier_log("d1", 8000, 0.50, 4000, 0.50)
    store.insert_confidence_multiplier_log("d2", 9000, 0.70, 6300, 0.70)
    log = store.get_confidence_multiplier_log()
    assert log[0]["device_id"] == "d2"
    assert log[1]["device_id"] == "d1"


# ---------------------------------------------------------------------------
# Test 4 — device_id filter
# ---------------------------------------------------------------------------

def test_get_confidence_multiplier_log_device_filter():
    store = _make_store()
    store.insert_confidence_multiplier_log("devX", 8000, 0.60, 4800, 0.60)
    store.insert_confidence_multiplier_log("devY", 9000, 0.70, 6300, 0.70)
    log = store.get_confidence_multiplier_log(device_id="devX")
    assert len(log) == 1
    assert log[0]["device_id"] == "devX"


# ---------------------------------------------------------------------------
# Test 5 — schema_version 122
# ---------------------------------------------------------------------------

def test_schema_version_122():
    store = _make_store()
    with store._conn() as conn:
        row = conn.execute(
            "SELECT migration_name FROM schema_versions WHERE phase=122"
        ).fetchone()
    assert row is not None
    assert row[0] == "confidence_multiplier"


# ---------------------------------------------------------------------------
# Test 6 — endpoint returns 7 required keys
# ---------------------------------------------------------------------------

def test_confidence_multiplier_endpoint_7_keys():
    from fastapi.testclient import TestClient
    from vapi_bridge.operator_api import create_operator_app
    store = _make_store()
    cfg = _make_cfg()
    app = create_operator_app(cfg=cfg, store=store)
    client = TestClient(app, raise_server_exceptions=True)
    resp = client.get(
        "/agent/confidence-score-multiplier-status",
        params={"api_key": "test-key"},
    )
    assert resp.status_code == 200
    data = resp.json()
    required_keys = {
        "multiplier_enabled", "current_bt_strat_ratio", "effective_multiplier",
        "floor", "log_count", "recent_applications", "timestamp",
    }
    assert required_keys.issubset(data.keys())


# ---------------------------------------------------------------------------
# Test 7 — effective_multiplier computation
# ---------------------------------------------------------------------------

def test_effective_multiplier_computation():
    """bt_strat_ratio=0.62→0.62; ratio>1→clamped 1.0; no snapshot→1.0."""
    from fastapi.testclient import TestClient
    from vapi_bridge.operator_api import create_operator_app
    store = _make_store()
    cfg = _make_cfg(confidence_multiplier_enabled=True)
    app = create_operator_app(cfg=cfg, store=store)
    client = TestClient(app, raise_server_exceptions=True)

    # No snapshot → effective=1.0
    resp = client.get(
        "/agent/confidence-score-multiplier-status", params={"api_key": "test-key"}
    )
    data = resp.json()
    assert data["effective_multiplier"] == pytest.approx(1.0)
    assert data["current_bt_strat_ratio"] == pytest.approx(-1.0)

    # Snapshot with bt_strat_ratio=0.62
    store.insert_separation_ratio_snapshot(
        pooled_ratio=0.474, bt_strat_ratio=0.62,
        n_sessions=97, n_players=3, active_features=13, tournament_ready=False,
    )
    resp2 = client.get(
        "/agent/confidence-score-multiplier-status", params={"api_key": "test-key"}
    )
    data2 = resp2.json()
    assert data2["effective_multiplier"] == pytest.approx(0.62, abs=1e-3)

    # Snapshot with bt_strat_ratio=1.25 → clamped to 1.0
    store.insert_separation_ratio_snapshot(
        pooled_ratio=1.10, bt_strat_ratio=1.25,
        n_sessions=120, n_players=3, active_features=13, tournament_ready=True,
    )
    resp3 = client.get(
        "/agent/confidence-score-multiplier-status", params={"api_key": "test-key"}
    )
    data3 = resp3.json()
    assert data3["effective_multiplier"] == pytest.approx(1.0, abs=1e-4)


# ---------------------------------------------------------------------------
# Test 8 — config defaults
# ---------------------------------------------------------------------------

def test_config_defaults_phase122():
    from vapi_bridge.config import Config
    cfg = Config()
    assert cfg.confidence_multiplier_enabled is False
    assert cfg.confidence_multiplier_floor == pytest.approx(0.0)
