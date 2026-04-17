"""
Phase 207 — StagedDryRunGraduationGate Tests
T207-1..8

Tests:
  T207-1: insert_graduation_stage stores row correctly
  T207-2: get_graduation_stage_status returns latest stage for agent
  T207-3: record_graduation_clean_session increments n_clean_sessions
  T207-4: record_graduation_false_positive increments n_false_positives and auto-rollback
  T207-5: trigger_graduation_rollback sets rollback_triggered=1
  T207-6: staged_graduation_enabled config field defaults to False
  T207-7: GET /agent/dry-run-graduation-status returns correct keys when disabled
  T207-8: POST /agent/activate-graduation-stage rejects when preconditions not met
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
    return Store(os.path.join(d, "test207.db"))


# ── T207-1: insert_graduation_stage stores row correctly ──────────────────────
def test_T207_1_insert_graduation_stage():
    store = _make_store()
    row_id = store.insert_graduation_stage(
        agent_id="session_adjudicator",
        stage_number=1,
        notes="Phase 207 stage 1 test",
    )
    assert isinstance(row_id, int)
    assert row_id >= 1
    status = store.get_graduation_stage_status("session_adjudicator")
    assert status is not None
    assert status["agent_id"] == "session_adjudicator"
    assert status["stage_number"] == 1
    assert status["n_clean_sessions"] == 0
    assert status["n_false_positives"] == 0
    assert status["rollback_triggered"] == 0
    assert "Phase 207 stage 1 test" in status["notes"]


# ── T207-2: get_graduation_stage_status returns latest stage ──────────────────
def test_T207_2_get_graduation_stage_status_latest():
    store = _make_store()
    store.insert_graduation_stage("ruling_enforcement_agent", 1, "stage 1")
    store.insert_graduation_stage("ruling_enforcement_agent", 2, "stage 2")
    status = store.get_graduation_stage_status("ruling_enforcement_agent")
    assert status is not None
    assert status["stage_number"] == 2
    assert "stage 2" in status["notes"]


# ── T207-3: record_graduation_clean_session increments n_clean_sessions ───────
def test_T207_3_record_graduation_clean_session():
    store = _make_store()
    store.insert_graduation_stage("session_adjudicator", 1, "")
    updated1 = store.record_graduation_clean_session("session_adjudicator")
    updated2 = store.record_graduation_clean_session("session_adjudicator")
    updated3 = store.record_graduation_clean_session("session_adjudicator")
    assert updated1 is True
    assert updated2 is True
    assert updated3 is True
    status = store.get_graduation_stage_status("session_adjudicator")
    assert status["n_clean_sessions"] == 3
    assert status["rollback_triggered"] == 0


# ── T207-4: record_graduation_false_positive auto-triggers rollback ───────────
def test_T207_4_record_graduation_false_positive_auto_rollback():
    store = _make_store()
    store.insert_graduation_stage("session_adjudicator", 1, "")
    # First FP: below threshold (fp_threshold default=2)
    rollback1 = store.record_graduation_false_positive("session_adjudicator", fp_threshold=2)
    assert rollback1 is False
    status_mid = store.get_graduation_stage_status("session_adjudicator")
    assert status_mid["n_false_positives"] == 1
    assert status_mid["rollback_triggered"] == 0
    # Second FP: hits threshold → auto-rollback
    rollback2 = store.record_graduation_false_positive("session_adjudicator", fp_threshold=2)
    assert rollback2 is True
    status_final = store.get_graduation_stage_status("session_adjudicator")
    assert status_final["n_false_positives"] == 2
    assert status_final["rollback_triggered"] == 1
    assert status_final["rollback_triggered_at"] is not None


# ── T207-5: trigger_graduation_rollback sets rollback_triggered=1 ─────────────
def test_T207_5_trigger_graduation_rollback():
    store = _make_store()
    store.insert_graduation_stage("ruling_enforcement_agent", 1, "")
    result = store.trigger_graduation_rollback(
        agent_id="ruling_enforcement_agent",
        reason="operator manual rollback test",
    )
    assert result is True
    status = store.get_graduation_stage_status("ruling_enforcement_agent")
    assert status["rollback_triggered"] == 1
    assert "operator manual rollback test" in (status.get("rollback_reason") or "")

    # Calling rollback again on already-rolled-back stage returns False
    result2 = store.trigger_graduation_rollback(
        agent_id="ruling_enforcement_agent",
        reason="second attempt",
    )
    assert result2 is False


# ── T207-6: staged_graduation_enabled config field defaults to False ──────────
def test_T207_6_config_default():
    _saved = {}
    for _k in ("STAGED_GRADUATION_ENABLED", "GRADUATION_ROLLBACK_WINDOW_SESSIONS",
               "GRADUATION_FP_THRESHOLD"):
        _saved[_k] = os.environ.pop(_k, None)
    try:
        import importlib
        import vapi_bridge.config as _cfg_mod
        importlib.reload(_cfg_mod)
        cfg = _cfg_mod.Config()
        assert hasattr(cfg, "staged_graduation_enabled")
        assert cfg.staged_graduation_enabled is False
        assert hasattr(cfg, "graduation_rollback_window_sessions")
        assert cfg.graduation_rollback_window_sessions == 10
        assert hasattr(cfg, "graduation_fp_threshold")
        assert cfg.graduation_fp_threshold == 2
    finally:
        for _k, _v in _saved.items():
            if _v is not None:
                os.environ[_k] = _v


# ── T207-7: GET /agent/dry-run-graduation-status returns correct keys ─────────
def test_T207_7_get_graduation_status_endpoint():
    store = _make_store()
    import vapi_bridge.config as _cfg_mod
    cfg = _cfg_mod.Config()

    from vapi_bridge.operator_api import create_operator_app
    from fastapi.testclient import TestClient

    app = create_operator_app(cfg, store)
    client = TestClient(app)
    resp = client.get("/agent/dry-run-graduation-status")
    assert resp.status_code == 200
    body = resp.json()
    assert "staged_graduation_enabled" in body
    assert "rollback_window_sessions" in body
    assert "fp_threshold" in body
    assert "stages" in body
    assert "active_stage_count" in body
    assert "timestamp" in body
    assert body["staged_graduation_enabled"] is False
    assert body["stages"] == []
    assert body["active_stage_count"] == 0


# ── T207-8: POST /agent/activate-graduation-stage rejects when disabled ───────
def test_T207_8_activate_graduation_stage_blocked_when_disabled():
    store = _make_store()
    import vapi_bridge.config as _cfg_mod
    cfg = _cfg_mod.Config()
    # staged_graduation_enabled=False by default

    from vapi_bridge.operator_api import create_operator_app
    from fastapi.testclient import TestClient

    app = create_operator_app(cfg, store)
    client = TestClient(app)
    resp = client.post(
        "/agent/activate-graduation-stage",
        json={"agent_id": "session_adjudicator"},
        headers={"x-api-key": cfg.operator_api_key or "test-key"},
    )
    # Should be 422 because staged_graduation_enabled=False
    assert resp.status_code == 422
    detail = resp.json().get("detail", "")
    assert "staged_graduation_enabled=False" in detail or "preconditions" in detail.lower() or "P0" in detail
