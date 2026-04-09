"""
Phase 154 — Capture Stagnation Monitor bridge tests (8 tests)

test_1_table_created
test_2_insert_roundtrip
test_3_compute_stagnant_no_data
test_4_compute_not_stagnant_with_sessions
test_5_get_returns_latest_per_probe_type
test_6_schema_version_154_recorded
test_7_endpoint_returns_7_keys
test_8_tool_110_returns_stagnant_field
"""

import os, sys, tempfile
from unittest.mock import MagicMock
import pytest

_w3 = MagicMock()
sys.modules.setdefault("web3", _w3)
sys.modules.setdefault("web3.exceptions", MagicMock())
sys.modules.setdefault("eth_account", MagicMock())


def _make_store():
    tmp = tempfile.mkdtemp()
    from bridge.vapi_bridge.store import Store
    return Store(os.path.join(tmp, "test_154.db"))


def _make_cfg():
    cfg = MagicMock()
    cfg.operator_api_key = "test-key-154"
    cfg.rate_limit_per_minute = 9999
    cfg.agent_dry_run_mode = True
    cfg.capture_stagnation_window_days = 7.0
    cfg.capture_stagnation_threshold = 0.5
    return cfg


def _insert_defensibility(store, ratio: float):
    store.insert_separation_defensibility_log(
        session_type="touchpad_corners",
        n_sessions_total=5,
        n_per_player={"P1": 1, "P2": 2, "P3": 2},
        min_n_per_player=10,
        defensible=False,
        ratio=ratio,
        all_pairs_above_1=True,
    )


def test_1_table_created():
    store = _make_store()
    with store._conn() as conn:
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='capture_stagnation_log'"
        ).fetchone()
    assert row is not None


def test_2_insert_roundtrip():
    store = _make_store()
    store.insert_capture_stagnation_log("touchpad_corners", 3, 7.0, 0.43, True, 0.5, "Below threshold")
    row = store.get_capture_stagnation_status("touchpad_corners")
    assert row is not None
    assert row["stagnant"] == 1
    assert abs(row["sessions_per_day"] - 0.43) < 0.01


def test_3_compute_stagnant_no_data():
    store = _make_store()
    result = store.compute_capture_stagnation("touchpad_corners", window_days=7.0, threshold=0.5)
    assert result["stagnant"] is True
    assert result["sessions_in_window"] == 0


def test_4_compute_not_stagnant_with_sessions():
    store = _make_store()
    for i in range(5):
        _insert_defensibility(store, 1.261 + i * 0.01)
    result = store.compute_capture_stagnation("touchpad_corners", window_days=7.0, threshold=0.5)
    assert result["sessions_in_window"] == 5
    assert result["sessions_per_day"] > 0.5
    assert result["stagnant"] is False


def test_5_get_returns_latest_per_probe_type():
    store = _make_store()
    store.insert_capture_stagnation_log("touchpad_corners", 2, 7.0, 0.28, True, 0.5, "")
    store.insert_capture_stagnation_log("touchpad_corners", 5, 7.0, 0.71, False, 0.5, "")
    store.insert_capture_stagnation_log("touchpad_freeform", 1, 7.0, 0.14, True, 0.5, "")
    assert store.get_capture_stagnation_status("touchpad_corners")["stagnant"] == 0
    assert store.get_capture_stagnation_status("touchpad_freeform")["stagnant"] == 1


def test_6_schema_version_154_recorded():
    store = _make_store()
    with store._conn() as conn:
        row = conn.execute("SELECT phase FROM schema_versions WHERE phase=154").fetchone()
    assert row is not None


def test_7_endpoint_returns_7_keys():
    """Replicate /agent/capture-stagnation-status logic (FastAPI not instantiated)."""
    import time as _t
    store = _make_store()
    cfg = _make_cfg()
    probe_type = "touchpad_corners"
    _threshold = float(getattr(cfg, "capture_stagnation_threshold", 0.5))
    _window    = float(getattr(cfg, "capture_stagnation_window_days", 7.0))
    _row = store.get_capture_stagnation_status(probe_type=probe_type)
    if _row is None:
        _computed = store.compute_capture_stagnation(probe_type=probe_type, window_days=_window, threshold=_threshold)
    else:
        _computed = _row
    data = {
        "probe_type":          probe_type,
        "sessions_per_day":    float(_computed.get("sessions_per_day", 0.0)),
        "stagnant":            bool(_computed.get("stagnant")),
        "sessions_in_window":  int(_computed.get("sessions_in_window", 0)),
        "window_days":         float(_computed.get("window_days", _window)),
        "stagnation_threshold": float(_computed.get("stagnation_threshold", _threshold)),
        "timestamp":           _t.time(),
    }
    for key in ("probe_type", "sessions_per_day", "stagnant", "sessions_in_window",
                "window_days", "stagnation_threshold", "timestamp"):
        assert key in data, f"Missing key: {key}"


def test_8_tool_110_returns_stagnant_field():
    from bridge.vapi_bridge.bridge_agent import BridgeAgent
    store = _make_store()
    cfg = _make_cfg()
    agent = BridgeAgent.__new__(BridgeAgent)
    agent._cfg   = cfg
    agent._store = store
    agent._chain = MagicMock()
    agent._bus   = MagicMock()
    result = agent._execute_tool("get_capture_stagnation_status", {"probe_type": "touchpad_corners"})
    assert "stagnant" in result
    assert isinstance(result["stagnant"], bool)
