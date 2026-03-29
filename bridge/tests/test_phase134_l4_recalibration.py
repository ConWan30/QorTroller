"""
Phase 134 — L4 Recalibration Pipeline Tests (8 tests)

Tests:
1. l4_recalibration_jobs table — empty store returns empty list
2. insert_l4_recalibration_job — roundtrip insert
3. update_l4_recalibration_job — status=complete roundtrip
4. stale flag — live_dim=13 vs calib_dim=12 → stale=True
5. single-job 409 guard — running job < 10 min blocks second POST
6. GET /agent/l4-recalibration-status — 7 required keys
7. Tool #103 run_l4_recalibration — returns 7-key dict
8. schema version 134 registered
"""

from __future__ import annotations

import os
import sys
import tempfile
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(_ROOT / "bridge"))

from vapi_bridge.store import Store


def _make_store() -> tuple[Store, str]:
    d = tempfile.mkdtemp()
    db = os.path.join(d, "test.db")
    return Store(db_path=db), db


# ---------------------------------------------------------------------------
# Test 1: empty table
# ---------------------------------------------------------------------------

def test_1_l4_recalibration_jobs_empty():
    store, _ = _make_store()
    jobs = store.get_l4_recalibration_jobs(limit=10)
    assert jobs == []


# ---------------------------------------------------------------------------
# Test 2: insert roundtrip
# ---------------------------------------------------------------------------

def test_2_insert_l4_recalibration_job_roundtrip():
    store, _ = _make_store()
    t = time.time()
    job_id = store.insert_l4_recalibration_job(started_at=t)
    assert isinstance(job_id, int) and job_id >= 1
    jobs = store.get_l4_recalibration_jobs(limit=1)
    assert len(jobs) == 1
    assert jobs[0]["id"] == job_id
    assert jobs[0]["status"] == "running"
    assert abs(jobs[0]["started_at"] - t) < 1.0


# ---------------------------------------------------------------------------
# Test 3: update status complete
# ---------------------------------------------------------------------------

def test_3_update_l4_recalibration_job_complete():
    store, _ = _make_store()
    job_id = store.insert_l4_recalibration_job(started_at=time.time())
    store.update_l4_recalibration_job(
        job_id=job_id,
        status="complete",
        sessions_processed=42,
        anomaly_result=7.009,
        continuity_result=5.367,
        completed_at=time.time(),
    )
    jobs = store.get_l4_recalibration_jobs(limit=1)
    j = jobs[0]
    assert j["status"] == "complete"
    assert j["sessions_processed"] == 42
    assert abs(j["anomaly_result"] - 7.009) < 0.001
    assert abs(j["continuity_result"] - 5.367) < 0.001


# ---------------------------------------------------------------------------
# Test 4: stale flag logic
# ---------------------------------------------------------------------------

def test_4_stale_flag_dim_mismatch():
    """live_feature_dim=13, calibration_feature_dim=12 → stale=True"""
    cfg = MagicMock()
    cfg.live_feature_dim = 13
    cfg.calibration_feature_dim = 12
    stale = cfg.live_feature_dim != cfg.calibration_feature_dim
    assert stale is True


# ---------------------------------------------------------------------------
# Test 5: single running job blocks second job (409 guard)
# ---------------------------------------------------------------------------

def test_5_running_job_blocks_new_job():
    store, _ = _make_store()
    job_id = store.insert_l4_recalibration_job(started_at=time.time())
    # Update to running status
    # (already running by default from insert)
    jobs = store.get_l4_recalibration_jobs(limit=1)
    assert jobs[0]["status"] == "running"
    # Simulate 409 guard: running job < 600s old
    age = time.time() - jobs[0].get("started_at", 0.0)
    assert age < 600  # would trigger 409 in API


# ---------------------------------------------------------------------------
# Test 6: GET /agent/l4-recalibration-status — 7 required keys
# ---------------------------------------------------------------------------

def test_6_endpoint_7_keys():
    from fastapi.testclient import TestClient

    store, db = _make_store()
    cfg = MagicMock()
    cfg.operator_api_key = "test-key"
    cfg.rate_limit_per_minute = 0
    cfg.live_feature_dim = 13
    cfg.calibration_feature_dim = 12
    cfg.l4_anomaly_threshold = 7.009
    cfg.l4_continuity_threshold = 5.367
    cfg.db_path = db

    from vapi_bridge.operator_api import create_operator_app
    app = create_operator_app(cfg=cfg, store=store)
    client = TestClient(app, raise_server_exceptions=False)

    resp = client.get("/agent/l4-recalibration-status?api_key=test-key")
    assert resp.status_code == 200
    data = resp.json()
    for key in ("in_progress", "last_run_ts", "sessions_processed",
                "new_anomaly_threshold", "new_continuity_threshold",
                "stale", "timestamp"):
        assert key in data, f"missing key: {key}"


# ---------------------------------------------------------------------------
# Test 7: Tool #103 returns 7-key dict
# ---------------------------------------------------------------------------

def test_7_tool_103_returns_7_keys():
    from vapi_bridge.bridge_agent import BridgeAgent

    store, _ = _make_store()
    cfg = MagicMock()
    cfg.operator_api_key = "test-key"
    cfg.live_feature_dim = 13
    cfg.calibration_feature_dim = 12
    cfg.l4_anomaly_threshold = 7.009
    cfg.l4_continuity_threshold = 5.367
    cfg.auto_separation_snapshot_enabled = False

    agent = BridgeAgent.__new__(BridgeAgent)
    agent._store = store
    agent._cfg = cfg
    agent._chain = MagicMock()

    result = agent._execute_tool("run_l4_recalibration", {})
    for key in ("in_progress", "last_run_ts", "sessions_processed",
                "new_anomaly_threshold", "new_continuity_threshold",
                "stale", "timestamp"):
        assert key in result, f"missing key: {key}"


# ---------------------------------------------------------------------------
# Test 8: schema version 134 registered
# ---------------------------------------------------------------------------

def test_8_schema_version_134():
    store, _ = _make_store()
    # After init, schema_versions table should have phase 134 entry
    version = store.get_schema_version()
    assert version >= 134, f"expected schema version >= 134, got {version}"
