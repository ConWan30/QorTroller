"""
Phase 215 — L4DimSyncConfirmation Tests
T215-1..8

Tests:
  T215-1: insert_l4_dim_sync stores row and returns row id
  T215-2: get_l4_dim_sync_status returns all 6 keys when no data
  T215-3: get_l4_dim_sync_status returns sync_completed=True after insert
  T215-4: get_l4_dim_sync_status returns from_dim=12, to_dim=13 correctly
  T215-5: get_l4_dim_sync_status returns correct thresholds (7.009, 5.367)
  T215-6: l4_dim_sync_enabled config defaults to True
  T215-7: GET /agent/l4-dim-sync-status returns all 7 keys
  T215-8: GET /agent/l4-dim-sync-status sync_completed=False when no DB entry
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
    return Store(os.path.join(d, "test215.db"))


# ── T215-1: insert_l4_dim_sync stores row and returns row id ──────────────────
def test_T215_1_insert_stores_row():
    """insert_l4_dim_sync returns a positive row id."""
    store = _make_store()
    row_id = store.insert_l4_dim_sync(
        from_dim=12,
        to_dim=13,
        anomaly_threshold=7.009,
        continuity_threshold=5.367,
        n_sessions=74,
        sync_reason="dim_sync: feature_12_struct_zero_in_gameplay",
    )
    assert isinstance(row_id, int)
    assert row_id >= 1


# ── T215-2: get_l4_dim_sync_status returns 6 keys when empty ─────────────────
def test_T215_2_status_empty_returns_6_keys():
    """get_l4_dim_sync_status returns 6 expected keys when no sync has been recorded."""
    store = _make_store()
    status = store.get_l4_dim_sync_status()
    expected_keys = {
        "sync_completed", "from_dim", "to_dim",
        "anomaly_threshold", "continuity_threshold", "timestamp",
    }
    assert set(status.keys()) == expected_keys


# ── T215-3: sync_completed=False until an entry is inserted ──────────────────
def test_T215_3_sync_completed_false_before_insert():
    """sync_completed is False when no l4_dim_sync_log entry exists."""
    store = _make_store()
    status = store.get_l4_dim_sync_status()
    assert status["sync_completed"] is False
    assert status["from_dim"] is None
    assert status["to_dim"] is None


# ── T215-4: from_dim/to_dim reflect inserted values ──────────────────────────
def test_T215_4_from_dim_to_dim_correct():
    """get_l4_dim_sync_status returns from_dim=12, to_dim=13 after insert."""
    store = _make_store()
    store.insert_l4_dim_sync(
        from_dim=12, to_dim=13, anomaly_threshold=7.009,
        continuity_threshold=5.367, n_sessions=74,
        sync_reason="test",
    )
    status = store.get_l4_dim_sync_status()
    assert status["sync_completed"] is True
    assert status["from_dim"] == 12
    assert status["to_dim"] == 13


# ── T215-5: thresholds reflect Phase 57 calibration values ───────────────────
def test_T215_5_thresholds_match_phase57():
    """get_l4_dim_sync_status returns anomaly=7.009, continuity=5.367 (Phase 57 values)."""
    store = _make_store()
    store.insert_l4_dim_sync(
        from_dim=12, to_dim=13, anomaly_threshold=7.009,
        continuity_threshold=5.367, n_sessions=74,
        sync_reason="phase57_confirm",
    )
    status = store.get_l4_dim_sync_status()
    assert abs(status["anomaly_threshold"] - 7.009) < 1e-6
    assert abs(status["continuity_threshold"] - 5.367) < 1e-6


# ── T215-6: l4_dim_sync_enabled defaults to True ─────────────────────────────
def test_T215_6_config_default_true():
    """l4_dim_sync_enabled config field defaults to True."""
    from vapi_bridge.config import Config
    cfg = Config()
    assert cfg.l4_dim_sync_enabled is True


# ── T215-7: endpoint returns 7 keys ──────────────────────────────────────────
def test_T215_7_endpoint_returns_correct_keys():
    """GET /agent/l4-dim-sync-status returns all 7 expected keys."""
    from fastapi.testclient import TestClient
    from vapi_bridge.config import Config
    from vapi_bridge.operator_api import create_operator_app

    store215 = _make_store()
    cfg215 = Config()
    app215 = create_operator_app(cfg215, store215)
    client = TestClient(app215)

    resp = client.get("/agent/l4-dim-sync-status")
    assert resp.status_code == 200
    body = resp.json()
    expected_keys = {
        "l4_dim_sync_enabled", "sync_completed", "from_dim", "to_dim",
        "anomaly_threshold", "continuity_threshold", "timestamp",
    }
    assert set(body.keys()) == expected_keys


# ── T215-8: endpoint sync_completed=False when no DB entry ───────────────────
def test_T215_8_endpoint_sync_completed_false_when_empty():
    """GET /agent/l4-dim-sync-status returns sync_completed=False when no entry."""
    from fastapi.testclient import TestClient
    from vapi_bridge.config import Config
    from vapi_bridge.operator_api import create_operator_app

    store215 = _make_store()
    cfg215 = Config()
    app215 = create_operator_app(cfg215, store215)
    client = TestClient(app215)

    resp = client.get("/agent/l4-dim-sync-status")
    assert resp.status_code == 200
    body = resp.json()
    assert body["sync_completed"] is False
    assert body["from_dim"] is None
    assert body["to_dim"] is None
