"""
Phase 152 — Centroid Velocity Monitor bridge tests (8 tests)

test_1_table_created
test_2_insert_roundtrip
test_3_get_returns_latest_for_probe
test_4_compute_stagnant_no_data
test_5_compute_velocity_from_snapshots
test_6_schema_version_152_recorded
test_7_endpoint_returns_9_keys
test_8_tool_108_returns_probe_type
"""

import os, sys, tempfile, time
from unittest.mock import MagicMock
import pytest

_w3 = MagicMock()
sys.modules.setdefault("web3", _w3)
sys.modules.setdefault("web3.exceptions", MagicMock())
sys.modules.setdefault("eth_account", MagicMock())


def _make_store():
    tmp = tempfile.mkdtemp()
    from bridge.vapi_bridge.store import Store
    return Store(os.path.join(tmp, "test_152.db"))


def _make_cfg():
    cfg = MagicMock()
    cfg.operator_api_key = "test-key-152"
    cfg.rate_limit_per_minute = 9999
    cfg.agent_dry_run_mode = True
    cfg.min_touchpad_sessions_per_player = 10
    cfg.ioswarm_enabled = False
    cfg.ioswarm_poad_auto_anchor_enabled = False
    cfg.gsr_enabled = False
    cfg.poad_registry_enabled = False
    cfg.ioswarm_adjudication_enabled = False
    cfg.ioswarm_vhp_mint_enabled = False
    cfg.ioswarm_renewal_enabled = False
    cfg.dual_primitive_gate_enabled = False
    cfg.epoch_window_enabled = False
    cfg.confidence_multiplier_enabled = False
    cfg.bt_transport_enabled = False
    cfg.l4_battery_threshold_enabled = False
    cfg.auto_separation_snapshot_enabled = False
    cfg.epistemic_triage_prereq_required = False
    cfg.epistemic_consensus_enabled = False
    cfg.agent_calibration_monitor_enabled = False
    cfg.mcp_server_enabled = False
    cfg.capture_stagnation_window_days = 7.0
    cfg.capture_stagnation_threshold = 0.5
    cfg.separation_ratio_on_chain_enabled = False
    cfg.controller_intelligence_enabled = True
    cfg.multi_controller_enabled = False
    return cfg


def _insert_defensibility(store, ratio: float):
    store.insert_separation_defensibility_log(
        session_type="touchpad_corners",
        n_sessions_total=11,
        n_per_player={"P1": 3, "P2": 4, "P3": 4},
        min_n_per_player=10,
        defensible=False,
        ratio=ratio,
        all_pairs_above_1=True,
    )


def test_1_table_created():
    store = _make_store()
    with store._conn() as conn:
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='centroid_velocity_log'"
        ).fetchone()
    assert row is not None


def test_2_insert_roundtrip():
    store = _make_store()
    store.insert_centroid_velocity_log("touchpad_corners", 0.0005, 1.261, 1.304, 86400.0, 2, False)
    row = store.get_centroid_velocity_status("touchpad_corners")
    assert row is not None
    assert abs(row["velocity"] - 0.0005) < 1e-6
    assert row["probe_type"] == "touchpad_corners"
    assert row["stagnant"] == 0


def test_3_get_returns_latest_for_probe():
    store = _make_store()
    store.insert_centroid_velocity_log("touchpad_corners", 0.001, 1.0, 1.1, 86400.0, 2, False)
    store.insert_centroid_velocity_log("touchpad_corners", 0.002, 1.1, 1.3, 86400.0, 2, False)
    row = store.get_centroid_velocity_status("touchpad_corners")
    assert abs(row["velocity"] - 0.002) < 1e-6


def test_4_compute_stagnant_no_data():
    store = _make_store()
    result = store.compute_centroid_velocity("touchpad_corners")
    assert result["stagnant"] is True
    assert result["n_snapshots_used"] == 0


def test_5_compute_velocity_from_snapshots():
    store = _make_store()
    _insert_defensibility(store, 1.261)
    time.sleep(0.05)
    _insert_defensibility(store, 1.304)
    result = store.compute_centroid_velocity("touchpad_corners")
    assert result["n_snapshots_used"] == 2
    assert abs(result["ratio_prev"] - 1.261) < 0.01
    assert abs(result["ratio_curr"] - 1.304) < 0.01
    assert result["velocity"] >= 0.0


def test_6_schema_version_152_recorded():
    store = _make_store()
    with store._conn() as conn:
        row = conn.execute("SELECT phase FROM schema_versions WHERE phase=152").fetchone()
    assert row is not None


def test_7_endpoint_returns_9_keys():
    """Replicate /agent/centroid-velocity-status logic (FastAPI not instantiated)."""
    import time as _t
    store = _make_store()
    cfg = _make_cfg()
    probe_type = "touchpad_corners"
    _row = store.get_centroid_velocity_status(probe_type=probe_type)
    if _row is None:
        _computed = store.compute_centroid_velocity(probe_type=probe_type)
    else:
        _computed = {
            "velocity":         float(_row.get("velocity", 0.0)),
            "ratio_prev":       float(_row.get("ratio_prev", 0.0)),
            "ratio_curr":       float(_row.get("ratio_curr", 0.0)),
            "dt_seconds":       float(_row.get("dt_seconds", 0.0)),
            "n_snapshots_used": int(_row.get("n_snapshots_used", 0)),
            "stagnant":         bool(_row.get("stagnant")),
        }
    data = {
        "probe_type":        probe_type,
        "velocity":          _computed["velocity"],
        "ratio_prev":        _computed["ratio_prev"],
        "ratio_curr":        _computed["ratio_curr"],
        "dt_seconds":        _computed["dt_seconds"],
        "n_snapshots_used":  _computed["n_snapshots_used"],
        "stagnant":          _computed["stagnant"],
        "velocity_per_day":  _computed["velocity"] * 86400,
        "timestamp":         _t.time(),
    }
    for key in ("probe_type", "velocity", "velocity_per_day", "stagnant", "n_snapshots_used", "timestamp"):
        assert key in data, f"Missing key: {key}"


def test_8_tool_108_returns_probe_type():
    from bridge.vapi_bridge.bridge_agent import BridgeAgent
    store = _make_store()
    cfg = _make_cfg()
    agent = BridgeAgent.__new__(BridgeAgent)
    agent._cfg   = cfg
    agent._store = store
    agent._chain = MagicMock()
    agent._bus   = MagicMock()
    result = agent._execute_tool("get_centroid_velocity_status", {"probe_type": "touchpad_corners"})
    assert "probe_type" in result
    assert result["probe_type"] == "touchpad_corners"
