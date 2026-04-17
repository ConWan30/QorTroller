"""
Phase 218 — CaptureVelocityOracle Tests
T218-1..8

Tests:
  T218-1: get_capture_velocity_oracle_status returns 8 keys
  T218-2: overall_capture_healthy=False when no logs exist (stagnant defaults)
  T218-3: sessions_stagnant=True when no capture sessions in window
  T218-4: velocity_stagnant=True when no centroid velocity log exists
  T218-5: recommended_action=URGENT when both stagnant
  T218-6: capture_velocity_oracle_enabled config defaults to True
  T218-7: GET /agent/capture-velocity-oracle returns 9 keys
  T218-8: GET /agent/capture-velocity-oracle recommended_action present
"""
import os
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "bridge"))

# ── web3 / eth_account stubs ──────────────────────────────────────────────────
import types

for _mod in ("web3", "web3.exceptions", "eth_account", "eth_account.messages",
             "web3.middleware", "web3.gas_strategies", "web3.gas_strategies.time_based"):
    if _mod not in sys.modules:
        sys.modules[_mod] = types.ModuleType(_mod)

_fake_web3 = sys.modules["web3"]
if not hasattr(_fake_web3, "Web3"):
    class _W3Stub:
        HTTPProvider = lambda *a, **kw: None
        class middleware_onion:
            inject = lambda *a, **kw: None
    _fake_web3.Web3 = _W3Stub

_fake_exc = sys.modules["web3.exceptions"]
if not hasattr(_fake_exc, "ContractLogicError"):
    _fake_exc.ContractLogicError = type("ContractLogicError", (Exception,), {})


def _make_store():
    from vapi_bridge.store import Store
    d = tempfile.mkdtemp()
    return Store(os.path.join(d, "test218.db"))


# ── T218-1: get_capture_velocity_oracle_status returns 8 keys ─────────────────
def test_T218_1_oracle_returns_8_keys():
    """get_capture_velocity_oracle_status returns 8 expected keys."""
    store = _make_store()
    status = store.get_capture_velocity_oracle_status()
    expected_keys = {
        "probe_type", "sessions_per_day", "sessions_stagnant",
        "ratio_velocity", "velocity_stagnant", "overall_capture_healthy",
        "recommended_action", "timestamp",
    }
    assert expected_keys.issubset(set(status.keys()))


# ── T218-2: overall_capture_healthy=False by default ─────────────────────────
def test_T218_2_unhealthy_by_default():
    """get_capture_velocity_oracle_status returns overall_capture_healthy=False with no data."""
    store = _make_store()
    status = store.get_capture_velocity_oracle_status()
    assert status["overall_capture_healthy"] is False


# ── T218-3: sessions_stagnant=True when no capture sessions in window ─────────
def test_T218_3_sessions_stagnant_when_empty():
    """sessions_stagnant=True when separation_defensibility_log has no recent entries."""
    store = _make_store()
    status = store.get_capture_velocity_oracle_status(
        probe_type="touchpad_corners", window_days=7.0, stagnation_threshold=0.5
    )
    assert status["sessions_stagnant"] is True
    assert status["sessions_per_day"] == 0.0


# ── T218-4: velocity_stagnant=True when no centroid velocity log ──────────────
def test_T218_4_velocity_stagnant_when_empty():
    """velocity_stagnant=True when centroid_velocity_log has no entries."""
    store = _make_store()
    status = store.get_capture_velocity_oracle_status()
    assert status["velocity_stagnant"] is True
    assert status["ratio_velocity"] == 0.0


# ── T218-5: recommended_action=URGENT when both stagnant ─────────────────────
def test_T218_5_recommended_action_urgent_when_both_stagnant():
    """recommended_action is URGENT_CAPTURE_SESSIONS_AND_REANALYZE when both stagnant."""
    store = _make_store()
    status = store.get_capture_velocity_oracle_status()
    assert status["recommended_action"] == "URGENT_CAPTURE_SESSIONS_AND_REANALYZE"


# ── T218-6: capture_velocity_oracle_enabled config defaults to True ───────────
def test_T218_6_config_default_true():
    """capture_velocity_oracle_enabled config field defaults to True."""
    from vapi_bridge.config import Config
    cfg = Config()
    assert cfg.capture_velocity_oracle_enabled is True


# ── T218-7: endpoint returns 9 keys ──────────────────────────────────────────
def test_T218_7_endpoint_returns_correct_keys():
    """GET /agent/capture-velocity-oracle returns all 9 expected keys."""
    from fastapi.testclient import TestClient
    from vapi_bridge.config import Config
    from vapi_bridge.operator_api import create_operator_app

    store218 = _make_store()
    cfg218 = Config()
    app218 = create_operator_app(cfg218, store218)
    client = TestClient(app218)

    resp = client.get("/agent/capture-velocity-oracle")
    assert resp.status_code == 200
    body = resp.json()
    expected_keys = {
        "capture_velocity_oracle_enabled", "probe_type", "sessions_per_day",
        "sessions_stagnant", "ratio_velocity", "velocity_stagnant",
        "overall_capture_healthy", "recommended_action", "timestamp",
    }
    assert set(body.keys()) == expected_keys


# ── T218-8: endpoint recommended_action is a non-empty string ────────────────
def test_T218_8_endpoint_recommended_action_present():
    """GET /agent/capture-velocity-oracle returns a non-empty recommended_action."""
    from fastapi.testclient import TestClient
    from vapi_bridge.config import Config
    from vapi_bridge.operator_api import create_operator_app

    store218 = _make_store()
    cfg218 = Config()
    app218 = create_operator_app(cfg218, store218)
    client = TestClient(app218)

    resp = client.get("/agent/capture-velocity-oracle?probe_type=touchpad_corners")
    assert resp.status_code == 200
    body = resp.json()
    assert isinstance(body["recommended_action"], str)
    assert len(body["recommended_action"]) > 0
    assert body["probe_type"] == "touchpad_corners"
