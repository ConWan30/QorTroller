"""
Phase 131B — PS5 Coexistence / USB Stability Monitor
Tests: +6 (Bridge 1669 → 1675)

VAPI-exclusive: DualShock Edge simultaneously streams live PoAC biometrics via USB reads
AND writes HID output (LED/haptic). When BT-paired to a PS5, those HID writes cause USB
micro-drops → PS5 "controller modules not correct" notification 3×/session.
Fix: ps5_compat_mode=True suppresses ALL HID writes → bridge read-only → PS5 never disconnects.
"""

import os
import sys
import time
import tempfile
import sqlite3

import pytest

# ---------------------------------------------------------------------------
# path bootstrap
# ---------------------------------------------------------------------------
ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
sys.path.insert(0, os.path.join(ROOT, "bridge"))

from vapi_bridge.store import Store


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _make_store():
    """Return a fresh Store instance for isolation."""
    d = tempfile.mkdtemp()
    db_path = os.path.join(d, "test_131b.db")
    return Store(db_path=db_path)


# ---------------------------------------------------------------------------
# tests
# ---------------------------------------------------------------------------

def test_1_usb_reconnect_log_table_exists():
    """usb_reconnect_log table created at store init."""
    store = _make_store()
    with store._conn() as conn:
        cur = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='usb_reconnect_log'"
        )
        row = cur.fetchone()
    assert row is not None, "usb_reconnect_log table must exist after store init"


def test_2_insert_usb_reconnect_log_roundtrip():
    """insert_usb_reconnect_log returns valid rowid; retrieved entries match."""
    store = _make_store()
    row_id = store.insert_usb_reconnect_log(
        device_address="aabbccddeeff1234",
        disconnect_reason="hid_feedback_timeout",
        consecutive_fb_timeouts=6,
        ps5_compat_mode_active=False,
        session_id="test-session-1",
    )
    assert isinstance(row_id, int) and row_id > 0

    status = store.get_usb_stability_status(limit=10)
    assert status["disconnect_count"] == 1
    entry = status["entries"][0]
    assert entry["disconnect_reason"] == "hid_feedback_timeout"
    assert entry["consecutive_fb_timeouts"] == 6
    assert entry["ps5_compat_mode_active"] == 0  # SQLite stores bool as int


def test_3_get_usb_stability_status_empty():
    """get_usb_stability_status returns zeros on empty table."""
    store = _make_store()
    status = store.get_usb_stability_status(limit=10)
    assert status["disconnect_count"] == 0
    assert status["last_disconnect_ts"] == 0.0
    assert status["entries"] == []


def test_4_multiple_inserts_counted_correctly():
    """disconnect_count reflects all inserted rows."""
    store = _make_store()
    for i in range(4):
        store.insert_usb_reconnect_log(
            device_address=f"dev{i}",
            disconnect_reason="hid_feedback_timeout",
            consecutive_fb_timeouts=i + 3,
        )
    status = store.get_usb_stability_status(limit=50)
    assert status["disconnect_count"] == 4
    assert len(status["entries"]) == 4


def test_5_ps5_compat_mode_config_default_false():
    """Config ps5_compat_mode defaults to False (env not set)."""
    from unittest.mock import patch
    # Ensure PS5_COMPAT_MODE is not set in environment
    env = {k: v for k, v in os.environ.items() if k != "PS5_COMPAT_MODE"}
    with patch.dict(os.environ, env, clear=True):
        from vapi_bridge.config import Config
        cfg = Config()
        assert cfg.ps5_compat_mode is False, (
            "ps5_compat_mode must default to False — PS5 coexistence opt-in only"
        )


def test_6_schema_version_1315_present():
    """schema_versions table contains entry (phase=1315) for Phase 131B."""
    store = _make_store()
    with store._conn() as conn:
        cur = conn.execute(
            "SELECT migration_name FROM schema_versions WHERE phase = 1315"
        )
        row = cur.fetchone()
    assert row is not None, "schema_versions must have entry with phase=1315"
    assert row[0] == "usb_reconnect"


def test_7_usb_stability_status_endpoint_returns_real_data():
    """CI-debt fix 2026-07-24 (docs/a2a/ci-debt/backlog.md): GET /agent/usb-stability-status
    used to 500 with NameError on every real call (undefined nodes_configured/_nodes_healthy/
    _emulator_mode/_latencies/_health_log/_t132 -- orphaned from a different endpoint by the
    2026-06-19 agent_misc split, never caught because no test exercised the HTTP route
    itself, only the Store layer). This is the missing regression test."""
    from unittest.mock import MagicMock
    from vapi_bridge.operator_api import create_operator_app
    from starlette.testclient import TestClient

    store = _make_store()
    store.insert_usb_reconnect_log(
        device_address="aabbccddeeff1234",
        disconnect_reason="hid_feedback_timeout",
        consecutive_fb_timeouts=6,
        ps5_compat_mode_active=False,
        session_id="test-session-7",
    )
    cfg = MagicMock()
    cfg.operator_api_key = "test-key"
    cfg.rate_limit_per_minute = 60
    cfg.ps5_compat_mode = True

    app = create_operator_app(cfg=cfg, store=store)
    client = TestClient(app)
    resp = client.get("/agent/usb-stability-status?api_key=test-key")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["ps5_compat_mode"] is True
    assert body["disconnect_count"] == 1
    assert "last_disconnect_ts" in body
    assert "entries" in body and len(body["entries"]) == 1
    assert "timestamp" in body
