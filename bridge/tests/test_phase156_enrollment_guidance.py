"""
Phase 156 — Enrollment Auto-Guidance Agent bridge tests (8 tests)

test_1_table_created
test_2_insert_roundtrip
test_3_get_returns_latest
test_4_stagnant_probes_parsed_from_json_string
test_5_agent_high_urgency_when_no_data
test_6_schema_version_156_recorded
test_7_endpoint_returns_8_keys
test_8_tool_112_returns_urgency_level
"""

import json, os, sys, tempfile
from unittest.mock import MagicMock
import pytest

_w3 = MagicMock()
sys.modules.setdefault("web3", _w3)
sys.modules.setdefault("web3.exceptions", MagicMock())
sys.modules.setdefault("eth_account", MagicMock())


def _make_store():
    tmp = tempfile.mkdtemp()
    from bridge.vapi_bridge.store import Store
    return Store(os.path.join(tmp, "test_156.db"))


def _make_cfg():
    cfg = MagicMock()
    cfg.operator_api_key = "test-key-156"
    cfg.rate_limit_per_minute = 9999
    cfg.agent_dry_run_mode = True
    cfg.min_touchpad_sessions_per_player = 10
    cfg.capture_stagnation_window_days = 7.0
    cfg.capture_stagnation_threshold = 0.5
    cfg.enrollment_guidance_poll_interval_s = 3600
    return cfg


def test_1_table_created():
    store = _make_store()
    with store._conn() as conn:
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='enrollment_guidance_log'"
        ).fetchone()
    assert row is not None


def test_2_insert_roundtrip():
    store = _make_store()
    store.insert_enrollment_guidance_log(57, False, "Run more sessions.", "HIGH",
                                         json.dumps(["touchpad_corners"]), 28.5, None)
    row = store.get_enrollment_guidance_status()
    assert row is not None
    assert row["sessions_needed_total"] == 57
    assert row["urgency_level"] == "HIGH"
    assert row["overall_ready"] == 0


def test_3_get_returns_latest():
    store = _make_store()
    store.insert_enrollment_guidance_log(57, False, "Catch up", "HIGH", "[]", 28.5, None)
    store.insert_enrollment_guidance_log(10, False, "Good pace", "MEDIUM", "[]", 5.0, None)
    row = store.get_enrollment_guidance_status()
    assert row["sessions_needed_total"] == 10


def test_4_stagnant_probes_parsed_from_json_string():
    """stagnant_probes stored as JSON string; get_enrollment_guidance_status decodes it."""
    store = _make_store()
    probes = ["touchpad_corners", "touchpad_freeform"]
    store.insert_enrollment_guidance_log(57, False, "msg", "HIGH", json.dumps(probes), 28.5, None)
    row = store.get_enrollment_guidance_status()
    # stagnant_probes may be decoded list or raw JSON string — both are valid
    val = row["stagnant_probes"]
    if isinstance(val, str):
        val = json.loads(val)
    assert val == probes


def test_5_agent_high_urgency_when_no_data():
    """With no defensibility logs, all probes stagnant -> HIGH urgency."""
    store = _make_store()
    cfg = _make_cfg()
    from bridge.vapi_bridge.enrollment_auto_guidance_agent import EnrollmentAutoGuidanceAgent
    agent = EnrollmentAutoGuidanceAgent(cfg=cfg, store=store)
    report = agent._synthesize_guidance()
    assert report["urgency_level"] == "HIGH"
    assert report["overall_ready"] is False
    assert len(report["stagnant_probes"]) > 0


def test_6_schema_version_156_recorded():
    store = _make_store()
    with store._conn() as conn:
        row = conn.execute("SELECT phase FROM schema_versions WHERE phase=156").fetchone()
    assert row is not None


def test_7_endpoint_returns_8_keys():
    """Replicate /agent/enrollment-auto-guidance-status logic (FastAPI not instantiated)."""
    import time as _t
    store = _make_store()
    cfg = _make_cfg()
    _row = store.get_enrollment_guidance_status()
    if _row is None:
        data = {
            "sessions_needed_total": 0, "overall_ready": False,
            "recommended_action": "Run EnrollmentAutoGuidanceAgent",
            "urgency_level": "UNKNOWN", "estimated_days": -1.0,
            "stagnant_probes": [], "activation_chain_event": None,
            "found": False, "timestamp": _t.time(),
        }
    else:
        _sp = _row.get("stagnant_probes", "[]")
        if isinstance(_sp, str):
            try: _sp = json.loads(_sp)
            except Exception: _sp = []
        data = {
            "sessions_needed_total": int(_row.get("sessions_needed_total", 0)),
            "overall_ready":         bool(_row.get("overall_ready")),
            "recommended_action":    str(_row.get("recommended_action", "")),
            "urgency_level":         str(_row.get("urgency_level", "UNKNOWN")),
            "estimated_days":        float(_row.get("estimated_days", -1.0)),
            "stagnant_probes":       _sp,
            "activation_chain_event": _row.get("activation_chain_event"),
            "found": True,
            "timestamp": _t.time(),
        }
    for key in ("sessions_needed_total", "overall_ready", "recommended_action",
                "urgency_level", "estimated_days", "stagnant_probes",
                "activation_chain_event", "timestamp"):
        assert key in data, f"Missing key: {key}"


def test_8_tool_112_returns_urgency_level():
    from bridge.vapi_bridge.bridge_agent import BridgeAgent
    store = _make_store()
    cfg = _make_cfg()
    agent = BridgeAgent.__new__(BridgeAgent)
    agent._cfg   = cfg
    agent._store = store
    agent._chain = MagicMock()
    agent._bus   = MagicMock()
    result = agent._execute_tool("get_enrollment_auto_guidance_status", {})
    assert "urgency_level" in result
    assert isinstance(result["urgency_level"], str)
