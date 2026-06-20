"""Phase B — retina_perception orchestration + RetinaMixin store."""

from __future__ import annotations

import json
import os
import sys
import time

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

try:
    import retina  # noqa: F401
    _HAS_RETINA = True
except ImportError:
    _HAS_RETINA = False

from vapi_bridge.retina_controller_embedder import synthetic_snaps
from vapi_bridge.retina_perception import (
    SCHEMA_TAG,
    persist_retina_result,
    run_controller_perception,
    RetinaPerceptionResult,
)


def _make_store(db_path: str):
    from vapi_bridge.store import Store

    return Store(db_path)


@pytest.fixture()
def tmp_db(tmp_path):
    return str(tmp_path / "retina_test.db")


@pytest.mark.skipif(not _HAS_RETINA, reason="trio-retina not installed")
def test_run_controller_perception_disabled():
    snaps = synthetic_snaps(150)
    result = run_controller_perception(snaps, enabled=False, source_id="t")
    assert result.enabled is False
    assert result.event_count == 0


@pytest.mark.skipif(not _HAS_RETINA, reason="trio-retina not installed")
def test_run_controller_perception_buffer_short():
    snaps = synthetic_snaps(10)
    result = run_controller_perception(snaps, enabled=True, source_id="t", window=120)
    assert result.enabled is True
    assert "buffer_short" in result.error


@pytest.mark.skipif(not _HAS_RETINA, reason="trio-retina not installed")
def test_run_controller_perception_aimbot_snap(tmp_db):
    snaps = synthetic_snaps(150, aimbot_snap_at=100)
    result = run_controller_perception(
        snaps,
        enabled=True,
        source_id="device_test",
        window=120,
        dynamics_horizon=5,
        record_hash_hex="ab" * 32,
    )
    assert result.error == ""
    assert result.event_count > 0
    assert result.trajectory_anomalies > 0
    assert result.record_hash_hex == "ab" * 32


@pytest.mark.skipif(not _HAS_RETINA, reason="trio-retina not installed")
def test_insert_retina_event_batch_roundtrip(tmp_db):
    store = _make_store(tmp_db)
    events = [{"type": "controller.trigger.onset", "src": "device_x"}]
    row_id = store.insert_retina_event_batch(
        device_id="device_x",
        events_json=json.dumps(events),
        world_state_json="{}",
        record_hash_hex="cd" * 32,
        anomaly_count=1,
        ts_ns=time.time_ns(),
    )
    assert row_id > 0
    status = store.get_retina_event_status(device_id="device_x")
    assert status["total_rows"] == 1
    assert status["latest_record_hash"] == "cd" * 32


def test_get_retina_by_record_hash_latest(tmp_db):
    store = _make_store(tmp_db)
    rh = "aa" * 32
    store.insert_retina_event_batch(
        device_id="device_x",
        events_json=json.dumps([{"type": "a"}]),
        record_hash_hex=rh,
        anomaly_count=0,
    )
    store.insert_retina_event_batch(
        device_id="device_x",
        events_json=json.dumps([{"type": "b"}]),
        record_hash_hex=rh,
        anomaly_count=3,
    )
    row = store.get_retina_by_record_hash(rh)
    assert row is not None
    assert row["anomaly_count"] == 3


@pytest.mark.skipif(not _HAS_RETINA, reason="trio-retina not installed")
def test_get_retina_alerts_since(tmp_db):
    store = _make_store(tmp_db)
    now = time.time()
    store.insert_retina_event_batch(
        device_id="d1",
        events_json=json.dumps([{"type": "controller.trajectory.anomalous"}]),
        anomaly_count=2,
        record_hash_hex="ef" * 32,
        ts_ns=int(now * 1e9),
    )
    alerts = store.get_retina_alerts_since(since_ts=now - 60)
    assert len(alerts) == 1
    assert alerts[0]["record_hash_hex"] == "ef" * 32
    assert alerts[0]["anomaly_count"] == 2


@pytest.mark.skipif(not _HAS_RETINA, reason="trio-retina not installed")
def test_persist_retina_result_writes_agent_event(tmp_db):
    store = _make_store(tmp_db)
    snaps = synthetic_snaps(150, aimbot_snap_at=100)
    result = run_controller_perception(
        snaps,
        enabled=True,
        source_id="device_persist",
        window=120,
        record_hash_hex="11" * 32,
    )
    persist_retina_result(store, "device_persist", result)
    status = store.get_retina_event_status(device_id="device_persist")
    assert status["total_rows"] >= 1
    with store._conn() as conn:
        rows = conn.execute(
            "SELECT event_type, payload_json FROM agent_events WHERE event_type = ?",
            ("retina_trajectory_anomaly",),
        ).fetchall()
    assert len(rows) >= 1
    payload = json.loads(rows[0]["payload_json"])
    assert payload["schema"] == SCHEMA_TAG
    assert payload["record_hash"] == "11" * 32
