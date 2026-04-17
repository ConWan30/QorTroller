"""
Phase 216 — PerPairGapLog Tests
T216-1..8

Tests:
  T216-1: insert_per_pair_gap stores row and returns row id
  T216-2: get_per_pair_gap_status returns 5 keys when no data
  T216-3: get_per_pair_gap_status returns all_pairs_above_1=False before insert
  T216-4: get_per_pair_gap_status reflects inserted pair correctly
  T216-5: all_pairs_above_1=False when any pair is below 1.0
  T216-6: per_pair_gap_log_enabled config defaults to True
  T216-7: GET /agent/per-pair-gap-status returns 7 keys
  T216-8: GET /agent/per-pair-gap-status blocker_pairs populated correctly
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
    return Store(os.path.join(d, "test216.db"))


# ── T216-1: insert_per_pair_gap stores row and returns row id ─────────────────
def test_T216_1_insert_stores_row():
    """insert_per_pair_gap returns a positive row id."""
    store = _make_store()
    row_id = store.insert_per_pair_gap(
        session_type="touchpad_corners",
        pair_key="P1vP3",
        player_i="P1",
        player_j="P3",
        distance=0.032,
        above_1_0=False,
        n_sessions_i=12,
        n_sessions_j=10,
        analysis_date="2026-04-16",
    )
    assert isinstance(row_id, int)
    assert row_id >= 1


# ── T216-2: get_per_pair_gap_status returns 5 keys when empty ────────────────
def test_T216_2_status_empty_returns_keys():
    """get_per_pair_gap_status returns expected keys when no data."""
    store = _make_store()
    status = store.get_per_pair_gap_status()
    expected_keys = {
        "all_pairs_above_1", "pairs", "session_type", "pair_count", "timestamp",
    }
    assert expected_keys.issubset(set(status.keys()))


# ── T216-3: all_pairs_above_1=False before any insert ────────────────────────
def test_T216_3_all_pairs_false_before_insert():
    """get_per_pair_gap_status returns all_pairs_above_1=False when no entries."""
    store = _make_store()
    status = store.get_per_pair_gap_status()
    assert status["all_pairs_above_1"] is False
    assert status["pairs"] == []
    assert status["pair_count"] == 0


# ── T216-4: inserted pair is reflected correctly ──────────────────────────────
def test_T216_4_pair_reflected_correctly():
    """get_per_pair_gap_status reflects inserted pair distance."""
    store = _make_store()
    store.insert_per_pair_gap(
        session_type="touchpad_corners",
        pair_key="P1vP2",
        player_i="P1",
        player_j="P2",
        distance=1.133,
        above_1_0=True,
        n_sessions_i=12,
        n_sessions_j=12,
        analysis_date="2026-04-16",
    )
    status = store.get_per_pair_gap_status()
    assert status["pair_count"] == 1
    pair = status["pairs"][0]
    assert pair["pair_key"] == "P1vP2"
    assert pair["player_i"] == "P1"
    assert pair["player_j"] == "P2"
    assert abs(pair["distance"] - 1.133) < 1e-6
    assert pair["above_1_0"] is True


# ── T216-5: all_pairs_above_1=False when any pair is below 1.0 ───────────────
def test_T216_5_all_pairs_false_when_any_below():
    """all_pairs_above_1=False when at least one pair distance < 1.0."""
    store = _make_store()
    today = "2026-04-16"
    store.insert_per_pair_gap(
        session_type="touchpad_corners", pair_key="P1vP2",
        player_i="P1", player_j="P2", distance=1.133, above_1_0=True,
        analysis_date=today,
    )
    store.insert_per_pair_gap(
        session_type="touchpad_corners", pair_key="P1vP3",
        player_i="P1", player_j="P3", distance=0.032, above_1_0=False,
        analysis_date=today,
    )
    store.insert_per_pair_gap(
        session_type="touchpad_corners", pair_key="P2vP3",
        player_i="P2", player_j="P3", distance=0.401, above_1_0=False,
        analysis_date=today,
    )
    status = store.get_per_pair_gap_status()
    assert status["all_pairs_above_1"] is False
    assert status["pair_count"] == 3


# ── T216-6: per_pair_gap_log_enabled defaults to True ────────────────────────
def test_T216_6_config_default_true():
    """per_pair_gap_log_enabled config field defaults to True."""
    from vapi_bridge.config import Config
    cfg = Config()
    assert cfg.per_pair_gap_log_enabled is True


# ── T216-7: endpoint returns 7 keys ──────────────────────────────────────────
def test_T216_7_endpoint_returns_correct_keys():
    """GET /agent/per-pair-gap-status returns all 7 expected keys."""
    from fastapi.testclient import TestClient
    from vapi_bridge.config import Config
    from vapi_bridge.operator_api import create_operator_app

    store216 = _make_store()
    cfg216 = Config()
    app216 = create_operator_app(cfg216, store216)
    client = TestClient(app216)

    resp = client.get("/agent/per-pair-gap-status")
    assert resp.status_code == 200
    body = resp.json()
    expected_keys = {
        "per_pair_gap_log_enabled", "all_pairs_above_1", "pairs",
        "session_type", "pair_count", "blocker_pairs", "timestamp",
    }
    assert set(body.keys()) == expected_keys


# ── T216-8: blocker_pairs populated correctly ─────────────────────────────────
def test_T216_8_endpoint_blocker_pairs_populated():
    """GET /agent/per-pair-gap-status blocker_pairs contains pairs with above_1_0=False."""
    from fastapi.testclient import TestClient
    from vapi_bridge.config import Config
    from vapi_bridge.operator_api import create_operator_app

    store216 = _make_store()
    cfg216 = Config()
    app216 = create_operator_app(cfg216, store216)
    today = "2026-04-16"
    store216.insert_per_pair_gap(
        session_type="touchpad_corners", pair_key="P1vP2",
        player_i="P1", player_j="P2", distance=1.133, above_1_0=True,
        analysis_date=today,
    )
    store216.insert_per_pair_gap(
        session_type="touchpad_corners", pair_key="P1vP3",
        player_i="P1", player_j="P3", distance=0.032, above_1_0=False,
        analysis_date=today,
    )
    client = TestClient(app216)
    resp = client.get("/agent/per-pair-gap-status")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["blocker_pairs"]) == 1
    assert body["blocker_pairs"][0]["pair_key"] == "P1vP3"
    assert body["all_pairs_above_1"] is False
