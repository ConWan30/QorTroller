"""
bridge/tests/test_phase239_gamer_readiness.py
Phase 239 — Gamer Readiness and Fatigue Monitoring (8 tests)

T239-1: insert_gamer_readiness_log() stores a row; get_gamer_readiness_status() retrieves it correctly.
T239-2: get_gamer_readiness_status() returns None when no log exists for the device.
T239-3: GET /agent/gamer-readiness-status returns 200 with nominal defaults when no data is stored.
T239-4: GET /agent/gamer-readiness-status returns 200 with stored values when data is stored.
T239-5: GamerReadinessAgent._analyze_device_readiness returns nominal defaults when no data exists.
T239-6: GamerReadinessAgent._analyze_device_readiness computes fatigue/RSI indices when mock data exists.
T239-7: GamerReadinessAgent._run_evaluation saves log and publishes event on low readiness.
T239-8: GET /agent/gamer-readiness-status reflects config state of gamer_readiness_enabled.
"""

import sys
from pathlib import Path
import os
import json
import time
import tempfile
import sqlite3
import asyncio
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "bridge"))

import types
for _mod in ["web3", "web3.exceptions", "eth_account", "eth_account.messages"]:
    if _mod not in sys.modules:
        sys.modules[_mod] = types.ModuleType(_mod)


def make_store(tmp_dir=None):
    from vapi_bridge.store import Store
    if tmp_dir is None:
        tmp_dir = tempfile.mkdtemp()
    return Store(os.path.join(tmp_dir, "test_phase239.db"))


def make_cfg(**overrides):
    from vapi_bridge.config import Config
    env_overrides = {}
    for k, v in overrides.items():
        if k == "gamer_readiness_enabled":
            env_overrides["GAMER_READINESS_ENABLED"] = "true" if v else "false"
    
    with patch.dict(os.environ, env_overrides):
        cfg = Config()
    return cfg


def register_mock_device(store, device_id="D1"):
    with store._conn() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO devices (device_id, pubkey_hex, first_seen, last_seen, records_verified) VALUES (?,?,?,?,0)",
            (device_id, "unknown_pubkey", time.time(), time.time())
        )


def insert_mock_l4_record(store, device_id, features_dict):
    import uuid
    record_hash = uuid.uuid4().hex
    with store._conn() as conn:
        conn.execute(
            "INSERT INTO records (record_hash, device_id, counter, timestamp_ms, inference, action_code, confidence, battery_pct, created_at, pitl_l4_features) "
            "VALUES (?, ?, 1, ?, 1, 0, 95, 100, ?, ?)",
            (record_hash, device_id, int(time.time() * 1000), time.time(), json.dumps(features_dict))
        )


# ---------------------------------------------------------------------------
# T239-1: insert_gamer_readiness_log() and get_gamer_readiness_status() roundtrip
# ---------------------------------------------------------------------------
def test_t239_1_insert_and_retrieve(tmp_path):
    """T239-1: Verify that a readiness log can be inserted and retrieved correctly."""
    store = make_store(str(tmp_path))
    register_mock_device(store, "D1")

    row_id = store.insert_gamer_readiness_log(
        device_id="D1",
        readiness_score=0.75,
        rsi_risk_score=0.25,
        fatigue_index=0.20,
        avg_tremor_hz=7.5,
        touchpad_entropy=1.8,
        reaction_latency_ms=160.0,
        recommendation="ADVISE_STRETCH"
    )
    assert row_id > 0

    status = store.get_gamer_readiness_status("D1")
    assert status is not None
    assert status["device_id"] == "D1"
    assert status["readiness_score"] == 0.75
    assert status["rsi_risk_score"] == 0.25
    assert status["fatigue_index"] == 0.20
    assert status["avg_tremor_hz"] == 7.5
    assert status["touchpad_entropy"] == 1.8
    assert status["reaction_latency_ms"] == 160.0
    assert status["recommendation"] == "ADVISE_STRETCH"


# ---------------------------------------------------------------------------
# T239-2: get_gamer_readiness_status() returns None when no log exists
# ---------------------------------------------------------------------------
def test_t239_2_empty_status(tmp_path):
    """T239-2: Verify that get_gamer_readiness_status() returns None for non-existent log."""
    store = make_store(str(tmp_path))
    status = store.get_gamer_readiness_status("D1")
    assert status is None


# ---------------------------------------------------------------------------
# T239-3: GET /agent/gamer-readiness-status returns 200 with nominal defaults
# ---------------------------------------------------------------------------
def test_t239_3_endpoint_empty_database(tmp_path):
    """T239-3: GET /agent/gamer-readiness-status returns 200 with default fields when DB is empty."""
    from fastapi.testclient import TestClient
    from vapi_bridge.operator_api import create_operator_app

    store = make_store(str(tmp_path))
    cfg = make_cfg(gamer_readiness_enabled=True)

    headers = {}
    if cfg.operator_api_key:
        headers["x-api-key"] = cfg.operator_api_key

    app = create_operator_app(cfg, store)
    client = TestClient(app)
    resp = client.get("/agent/gamer-readiness-status?device_id=D1", headers=headers)

    assert resp.status_code == 200
    data = resp.json()
    assert data["gamer_readiness_enabled"] is True
    assert data["device_id"] == "D1"
    assert data["readiness_score"] == 1.0
    assert data["rsi_risk_score"] == 0.0
    assert data["fatigue_index"] == 0.0
    assert data["avg_tremor_hz"] == 8.0
    assert data["touchpad_entropy"] == 1.5
    assert data["reaction_latency_ms"] == 150.0
    assert data["recommendation"] == "NOMINAL"
    assert data["created_at"] == 0.0
    assert "timestamp" in data


# ---------------------------------------------------------------------------
# T239-4: GET /agent/gamer-readiness-status returns 200 with stored values
# ---------------------------------------------------------------------------
def test_t239_4_endpoint_with_data(tmp_path):
    """T239-4: GET /agent/gamer-readiness-status returns 200 with stored readiness log values."""
    from fastapi.testclient import TestClient
    from vapi_bridge.operator_api import create_operator_app

    store = make_store(str(tmp_path))
    register_mock_device(store, "D2")
    store.insert_gamer_readiness_log(
        device_id="D2",
        readiness_score=0.55,
        rsi_risk_score=0.45,
        fatigue_index=0.40,
        avg_tremor_hz=6.2,
        touchpad_entropy=1.1,
        reaction_latency_ms=180.5,
        recommendation="ADVISE_BREAK"
    )

    cfg = make_cfg(gamer_readiness_enabled=True)

    headers = {}
    if cfg.operator_api_key:
        headers["x-api-key"] = cfg.operator_api_key

    app = create_operator_app(cfg, store)
    client = TestClient(app)
    resp = client.get("/agent/gamer-readiness-status?device_id=D2", headers=headers)

    assert resp.status_code == 200
    data = resp.json()
    assert data["gamer_readiness_enabled"] is True
    assert data["device_id"] == "D2"
    assert data["readiness_score"] == 0.55
    assert data["rsi_risk_score"] == 0.45
    assert data["fatigue_index"] == 0.40
    assert data["avg_tremor_hz"] == 6.2
    assert data["touchpad_entropy"] == 1.1
    assert data["reaction_latency_ms"] == 180.5
    assert data["recommendation"] == "ADVISE_BREAK"
    assert data["created_at"] > 0.0


# ---------------------------------------------------------------------------
# T239-5: GamerReadinessAgent._analyze_device_readiness returns nominal defaults
# ---------------------------------------------------------------------------
def test_t239_5_agent_analyze_empty(tmp_path):
    """T239-5: GamerReadinessAgent._analyze_device_readiness returns defaults if no data exists."""
    from vapi_bridge.gamer_readiness_agent import GamerReadinessAgent
    store = make_store(str(tmp_path))
    cfg = make_cfg()
    agent = GamerReadinessAgent(cfg, store)

    metrics = agent._analyze_device_readiness("D1")
    assert metrics["device_id"] == "D1"
    # Note: entropy defaults to 1.5 in GamerReadinessAgent, which translates
    # to a default readiness score of 0.8 under formula logic.
    assert metrics["readiness_score"] == 0.8
    assert metrics["rsi_risk_score"] == 0.2
    assert metrics["fatigue_index"] == 0.0
    assert metrics["avg_tremor_hz"] == 8.0
    assert metrics["touchpad_entropy"] == 1.5
    assert metrics["reaction_latency_ms"] == 150.0
    assert metrics["recommendation"] == "NOMINAL"


# ---------------------------------------------------------------------------
# T239-6: GamerReadinessAgent._analyze_device_readiness computes indices
# ---------------------------------------------------------------------------
def test_t239_6_agent_analyze_with_fatigue_and_rsi(tmp_path):
    """T239-6: GamerReadinessAgent computes expected fatigue and RSI scores under simulated metrics."""
    from vapi_bridge.gamer_readiness_agent import GamerReadinessAgent
    store = make_store(str(tmp_path))
    register_mock_device(store, "D1")

    # Insert simulated records indicating strain/fatigue
    # Low tremor frequency (4.5 Hz), high tremor variance (0.0018), low touchpad entropy (0.5), high grip asymmetry (1.4)
    for _ in range(5):
        insert_mock_l4_record(store, "D1", {
            "tremor_peak_hz": 4.5,
            "micro_tremor_accel_variance": 0.0018,
            "touchpad_spatial_entropy": 0.5,
            "grip_asymmetry": 1.4
        })

    # Insert simulated haptic responses in l6b_probe (high latency: 250.0 ms)
    for i in range(3):
        store.insert_l6b_probe(
            device_id="D1",
            probe_ts_ms=int(time.time() * 1000) - i * 1000,
            latency_ms=250.0,
            classification="HUMAN",
            accel_delta_peak=0.5
        )

    cfg = make_cfg()
    agent = GamerReadinessAgent(cfg, store)

    metrics = agent._analyze_device_readiness("D1")
    assert metrics["device_id"] == "D1"
    assert metrics["avg_tremor_hz"] == 4.5
    assert metrics["touchpad_entropy"] == 0.5
    assert metrics["reaction_latency_ms"] == 250.0
    
    # Assert fatigue index and rsi risk are computed and elevated
    assert metrics["fatigue_index"] > 0.3
    assert metrics["rsi_risk_score"] > 0.4
    assert metrics["readiness_score"] < 0.6
    assert metrics["recommendation"] in ("ADVISE_BREAK", "HIGH_RSI_RISK")


# ---------------------------------------------------------------------------
# T239-7: GamerReadinessAgent._run_evaluation saves log and publishes event
# ---------------------------------------------------------------------------
def test_t239_7_agent_run_evaluation(tmp_path):
    """T239-7: _run_evaluation persists logs to database and fires bus alerts on low readiness."""
    from vapi_bridge.gamer_readiness_agent import GamerReadinessAgent
    store = make_store(str(tmp_path))
    register_mock_device(store, "D1")

    # Low readiness data setup
    for _ in range(5):
        insert_mock_l4_record(store, "D1", {
            "tremor_peak_hz": 4.0,
            "micro_tremor_accel_variance": 0.0022,
            "touchpad_spatial_entropy": 0.3,
            "grip_asymmetry": 1.5
        })

    cfg = make_cfg()
    bus = MagicMock()
    agent = GamerReadinessAgent(cfg, store, bus)

    # Run evaluation
    asyncio.run(agent._run_evaluation())

    # Check that database has the log entry
    status = store.get_gamer_readiness_status("D1")
    assert status is not None
    assert status["readiness_score"] < 0.6

    # Check that bus published alert
    bus.publish_sync.assert_called_once()
    args, kwargs = bus.publish_sync.call_args
    assert args[0] == "gamer_readiness_alert"
    event_payload = args[1]
    assert event_payload["device_id"] == "D1"
    assert event_payload["readiness_score"] < 0.6
    assert "recommendation" in event_payload


# ---------------------------------------------------------------------------
# T239-8: GET /agent/gamer-readiness-status reflects config state
# ---------------------------------------------------------------------------
def test_t239_8_endpoint_disabled(tmp_path):
    """T239-8: GET /agent/gamer-readiness-status returns correct gamer_readiness_enabled flag from config."""
    from fastapi.testclient import TestClient
    from vapi_bridge.operator_api import create_operator_app

    store = make_store(str(tmp_path))
    
    # 1. Test when disabled
    cfg = make_cfg(gamer_readiness_enabled=False)
    headers = {}
    if cfg.operator_api_key:
        headers["x-api-key"] = cfg.operator_api_key

    app = create_operator_app(cfg, store)
    client = TestClient(app)
    resp = client.get("/agent/gamer-readiness-status", headers=headers)
    
    assert resp.status_code == 200
    assert resp.json()["gamer_readiness_enabled"] is False

    # 2. Test when enabled
    cfg = make_cfg(gamer_readiness_enabled=True)
    headers = {}
    if cfg.operator_api_key:
        headers["x-api-key"] = cfg.operator_api_key

    app = create_operator_app(cfg, store)
    client = TestClient(app)
    resp = client.get("/agent/gamer-readiness-status", headers=headers)
    
    assert resp.status_code == 200
    assert resp.json()["gamer_readiness_enabled"] is True
