"""
Phase 132 — IoSwarm Live Node Server
Tests: +8 (Bridge 1675 → 1683)

VAPI-exclusive: first DePIN protocol where staked AI nodes independently evaluate
controller biometrics and sign verdicts with HMAC-SHA256 for tamper-evidence.
"""

import os
import sys
import time
import tempfile

import pytest

ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
sys.path.insert(0, os.path.join(ROOT, "bridge"))

from vapi_bridge.store import Store


def _make_store():
    d = tempfile.mkdtemp()
    return Store(db_path=os.path.join(d, "test_132.db"))


# ---------------------------------------------------------------------------

def test_1_node_health_log_table_exists():
    """ioswarm_node_health_log table created at store init."""
    store = _make_store()
    with store._conn() as conn:
        cur = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='ioswarm_node_health_log'"
        )
        row = cur.fetchone()
    assert row is not None, "ioswarm_node_health_log table must exist"


def test_2_insert_node_health_roundtrip():
    """insert_ioswarm_node_health + get_ioswarm_node_health roundtrip."""
    store = _make_store()
    row_id = store.insert_ioswarm_node_health(
        node_url="http://node1:8090",
        healthy=True,
        latency_ms=42.5,
        staker_address="0xABCD",
        error_msg="",
    )
    assert isinstance(row_id, int) and row_id > 0

    entries = store.get_ioswarm_node_health()
    assert len(entries) == 1
    e = entries[0]
    assert e["node_url"] == "http://node1:8090"
    assert e["healthy"] == 1
    assert abs(e["latency_ms"] - 42.5) < 0.01
    assert e["staker_address"] == "0xABCD"


def test_3_node_health_filtered_by_url():
    """get_ioswarm_node_health filters by node_url."""
    store = _make_store()
    store.insert_ioswarm_node_health("http://node1:8090", True, 10.0)
    store.insert_ioswarm_node_health("http://node2:8090", False, -1.0, error_msg="timeout")

    r1 = store.get_ioswarm_node_health(node_url="http://node1:8090")
    r2 = store.get_ioswarm_node_health(node_url="http://node2:8090")
    assert len(r1) == 1 and r1[0]["healthy"] == 1
    assert len(r2) == 1 and r2[0]["healthy"] == 0


def test_4_node_server_evaluate_endpoint_structure():
    """POST /evaluate returns the 5 required keys."""
    try:
        from fastapi.testclient import TestClient
        from vapi_bridge.ioswarm_live_node_server import app
    except ImportError:
        pytest.skip("fastapi or httpx not available")

    client = TestClient(app)
    resp = client.post("/evaluate", json={"evaluation_type": "renewal", "payload": {"consecutive_clean": 5, "blocks": 0}})
    assert resp.status_code == 200
    data = resp.json()
    for key in ("node_id", "staker_address", "verdict", "confidence", "evaluation_type"):
        assert key in data, f"Missing key: {key}"


def test_5_node_server_status_7_keys():
    """GET /status returns the 7 required keys."""
    try:
        from fastapi.testclient import TestClient
        from vapi_bridge.ioswarm_live_node_server import app
    except ImportError:
        pytest.skip("fastapi or httpx not available")

    client = TestClient(app)
    resp = client.get("/status")
    assert resp.status_code == 200
    data = resp.json()
    for key in ("node_id", "staker_address", "stake_amount", "healthy", "version", "uptime_s", "timestamp"):
        assert key in data, f"Missing key: {key}"


def test_6_node_server_identity_5_keys():
    """GET /identity returns the 5 required keys."""
    try:
        from fastapi.testclient import TestClient
        from vapi_bridge.ioswarm_live_node_server import app
    except ImportError:
        pytest.skip("fastapi or httpx not available")

    client = TestClient(app)
    resp = client.get("/identity")
    assert resp.status_code == 200
    data = resp.json()
    for key in ("node_id", "staker_address", "node_version", "evaluation_capabilities", "timestamp"):
        assert key in data, f"Missing key: {key}"


def test_7_endpoint_ioswarm_node_health_6_keys():
    """GET /agent/ioswarm-node-health returns the 6 required keys."""
    from unittest.mock import MagicMock, patch
    import importlib

    store = _make_store()
    cfg = MagicMock()
    cfg.operator_api_key = "testkey"
    cfg.ioswarm_node_urls = ""  # emulator mode
    cfg.ioswarm_node_timeout_seconds = 5.0

    import vapi_bridge.operator_api as _oa
    app = _oa.create_operator_app(cfg=cfg, store=store)

    try:
        from fastapi.testclient import TestClient
    except ImportError:
        pytest.skip("fastapi not available")

    client = TestClient(app)
    resp = client.get("/agent/ioswarm-node-health?api_key=testkey")
    assert resp.status_code == 200
    data = resp.json()
    for key in ("nodes_configured", "nodes_healthy", "emulator_mode", "avg_latency_ms", "health_log_count", "timestamp"):
        assert key in data, f"Missing key: {key}"


def test_8_schema_version_132_present():
    """schema_versions contains (phase=132, migration_name='ioswarm_node_health')."""
    store = _make_store()
    with store._conn() as conn:
        cur = conn.execute(
            "SELECT migration_name FROM schema_versions WHERE phase = 132"
        )
        row = cur.fetchone()
    assert row is not None, "schema_versions must have phase=132"
    assert row[0] == "ioswarm_node_health"
