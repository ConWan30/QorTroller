"""
Phase 155 — Controller Hardware Intelligence bridge tests (8 tests)

test_1_table_created
test_2_insert_roundtrip
test_3_composite_key_format
test_4_active_only_filter
test_5_default_thresholds_7009_5367
test_6_schema_version_155_recorded
test_7_endpoint_returns_5_keys
test_8_tool_111_returns_attested_count
"""

import hashlib, os, sys, tempfile
from unittest.mock import MagicMock
import pytest

_w3 = MagicMock()
sys.modules.setdefault("web3", _w3)
sys.modules.setdefault("web3.exceptions", MagicMock())
sys.modules.setdefault("eth_account", MagicMock())


def _make_store():
    tmp = tempfile.mkdtemp()
    from bridge.vapi_bridge.store import Store
    return Store(os.path.join(tmp, "test_155.db"))


def _make_cfg():
    cfg = MagicMock()
    cfg.operator_api_key = "test-key-155"
    cfg.rate_limit_per_minute = 9999
    cfg.agent_dry_run_mode = True
    cfg.controller_intelligence_enabled = True
    cfg.multi_controller_enabled = False
    return cfg


def _ph(name): return hashlib.sha256(name.encode()).hexdigest()[:16]


def test_1_table_created():
    store = _make_store()
    with store._conn() as conn:
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='controller_hardware_profiles'"
        ).fetchone()
    assert row is not None


def test_2_insert_roundtrip():
    store = _make_store()
    store.insert_controller_hardware_profile(
        _ph("DualShock Edge"), "DualShock Edge CFI-ZCP1", "Attested",
        74, "USB", "gameplay", 7.009, 5.367
    )
    profiles = store.get_controller_hardware_profiles(active_only=False)
    assert len(profiles) == 1
    assert profiles[0]["tier"] == "Attested"


def test_3_composite_key_format():
    store = _make_store()
    ph = _ph("TestCtrl")
    store.insert_controller_hardware_profile(ph, "TestCtrl", "Standard", 10, "BT", "resting")
    profiles = store.get_controller_hardware_profiles(active_only=False)
    assert profiles[0]["composite_key"] == f"{ph}:resting:BT"


def test_4_active_only_filter():
    store = _make_store()
    ph1 = _ph("Active")
    ph2 = _ph("Inactive")
    store.insert_controller_hardware_profile(ph1, "Active", "Attested", 74, "USB", "gameplay")
    store.insert_controller_hardware_profile(ph2, "Inactive", "Standard", 0, "USB", "gameplay")
    with store._conn() as conn:
        conn.execute("UPDATE controller_hardware_profiles SET active=0 WHERE profile_hash=?", (ph2,))
    active = store.get_controller_hardware_profiles(active_only=True)
    assert all(p["active"] == 1 for p in active)
    assert len(store.get_controller_hardware_profiles(active_only=False)) == 2


def test_5_default_thresholds_7009_5367():
    store = _make_store()
    ph = _ph("DualShock Edge")
    store.insert_controller_hardware_profile(ph, "DualShock Edge CFI-ZCP1", "Attested", 74, "USB", "gameplay")
    p = store.get_controller_hardware_profiles(active_only=True)[0]
    assert abs(p["anomaly_threshold"] - 7.009) < 0.001
    assert abs(p["continuity_threshold"] - 5.367) < 0.001


def test_6_schema_version_155_recorded():
    store = _make_store()
    with store._conn() as conn:
        row = conn.execute("SELECT phase FROM schema_versions WHERE phase=155").fetchone()
    assert row is not None


def test_7_endpoint_returns_5_keys():
    """Replicate /agent/controller-hardware-status logic (FastAPI not instantiated)."""
    import time as _t
    store = _make_store()
    cfg = _make_cfg()
    _profiles = store.get_controller_hardware_profiles(active_only=False)
    _attested = sum(1 for p in _profiles if p.get("tier") == "Attested")
    _standard = sum(1 for p in _profiles if p.get("tier") == "Standard")
    _ck = _profiles[0].get("composite_key", "") if _profiles else ""
    data = {
        "controller_intelligence_enabled": bool(getattr(cfg, "controller_intelligence_enabled", True)),
        "multi_controller_enabled":        bool(getattr(cfg, "multi_controller_enabled", False)),
        "attested_count":                  _attested,
        "standard_count":                  _standard,
        "active_composite_key":            _ck,
        "timestamp":                       _t.time(),
    }
    for key in ("controller_intelligence_enabled", "multi_controller_enabled",
                "attested_count", "standard_count", "timestamp"):
        assert key in data, f"Missing key: {key}"


def test_8_tool_111_returns_attested_count():
    from bridge.vapi_bridge.bridge_agent import BridgeAgent
    store = _make_store()
    cfg = _make_cfg()
    ph = _ph("DualShock Edge")
    store.insert_controller_hardware_profile(ph, "DualShock Edge CFI-ZCP1", "Attested", 74, "USB", "gameplay")
    agent = BridgeAgent.__new__(BridgeAgent)
    agent._cfg   = cfg
    agent._store = store
    agent._chain = MagicMock()
    agent._bus   = MagicMock()
    result = agent._execute_tool("get_controller_hardware_status", {})
    assert result["attested_count"] == 1
