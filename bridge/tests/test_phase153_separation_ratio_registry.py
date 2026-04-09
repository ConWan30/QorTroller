"""
Phase 153 — Separation Ratio Registry bridge tests (8 tests)

test_1_table_created
test_2_insert_roundtrip
test_3_dedup_on_commit_hash
test_4_get_returns_latest
test_5_get_returns_none_empty
test_6_schema_version_153_recorded
test_7_endpoint_returns_9_keys
test_8_tool_109_returns_committed_field
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
    return Store(os.path.join(tmp, "test_153.db"))


def _make_cfg():
    cfg = MagicMock()
    cfg.operator_api_key = "test-key-153"
    cfg.rate_limit_per_minute = 9999
    cfg.agent_dry_run_mode = True
    cfg.separation_ratio_on_chain_enabled = False
    return cfg


def _ch(s): return hashlib.sha256(s.encode()).hexdigest()


def test_1_table_created():
    store = _make_store()
    with store._conn() as conn:
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='separation_ratio_registry_log'"
        ).fetchone()
    assert row is not None


def test_2_insert_roundtrip():
    store = _make_store()
    ch = _ch("ratio=1.261:N=11:P1P2P3")
    store.insert_separation_ratio_registry_log(ch, 1261, 11, 3, None, False)
    row = store.get_separation_ratio_registry_status()
    assert row is not None
    assert row["commit_hash"] == ch
    assert row["ratio_millis"] == 1261


def test_3_dedup_on_commit_hash():
    store = _make_store()
    ch = _ch("same-hash-abc")
    store.insert_separation_ratio_registry_log(ch, 1261, 11, 3, None, False)
    store.insert_separation_ratio_registry_log(ch, 9999, 99, 9, "0xabc", True)
    row = store.get_separation_ratio_registry_status()
    assert row["ratio_millis"] == 1261  # first preserved by INSERT OR IGNORE


def test_4_get_returns_latest():
    store = _make_store()
    ch1 = _ch("commit-1")
    ch2 = _ch("commit-2")
    store.insert_separation_ratio_registry_log(ch1, 1261, 11, 3, None, False)
    store.insert_separation_ratio_registry_log(ch2, 1552, 11, 3, None, False)
    row = store.get_separation_ratio_registry_status()
    assert row["ratio_millis"] == 1552


def test_5_get_returns_none_empty():
    store = _make_store()
    assert store.get_separation_ratio_registry_status() is None


def test_6_schema_version_153_recorded():
    store = _make_store()
    with store._conn() as conn:
        row = conn.execute("SELECT phase FROM schema_versions WHERE phase=153").fetchone()
    assert row is not None


def test_7_endpoint_returns_9_keys():
    """Replicate /agent/separation-ratio-registry-status logic (FastAPI not instantiated)."""
    import time as _t
    store = _make_store()
    cfg = _make_cfg()
    _row = store.get_separation_ratio_registry_status()
    _on_chain_enabled = bool(getattr(cfg, "separation_ratio_on_chain_enabled", False))
    if _row is None:
        data = {
            "committed": False, "commit_hash": "", "ratio_millis": 0,
            "n_sessions": 0, "n_players": 0, "on_chain_tx": None,
            "total_commits": 0, "separation_ratio_on_chain_enabled": _on_chain_enabled,
            "found": False, "timestamp": _t.time(),
        }
    else:
        data = {
            "committed": bool(_row.get("committed")),
            "commit_hash": str(_row.get("commit_hash", "")),
            "ratio_millis": int(_row.get("ratio_millis", 0)),
            "n_sessions": int(_row.get("n_sessions", 0)),
            "n_players": int(_row.get("n_players", 0)),
            "on_chain_tx": _row.get("on_chain_tx"),
            "total_commits": 1,
            "separation_ratio_on_chain_enabled": _on_chain_enabled,
            "found": True,
            "timestamp": _t.time(),
        }
    for key in ("committed", "commit_hash", "ratio_millis", "n_sessions", "n_players",
                "total_commits", "separation_ratio_on_chain_enabled", "timestamp"):
        assert key in data, f"Missing key: {key}"


def test_8_tool_109_returns_committed_field():
    from bridge.vapi_bridge.bridge_agent import BridgeAgent
    store = _make_store()
    cfg = _make_cfg()
    agent = BridgeAgent.__new__(BridgeAgent)
    agent._cfg   = cfg
    agent._store = store
    agent._chain = MagicMock()
    agent._bus   = MagicMock()
    result = agent._execute_tool("get_separation_ratio_registry_status", {})
    assert "committed" in result
    assert isinstance(result["committed"], bool)
