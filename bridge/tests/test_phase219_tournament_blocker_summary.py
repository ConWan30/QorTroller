"""
Phase 219 — TournamentBlockerSummary Tests
T219-1..8

Tests:
  T219-1: get_tournament_blocker_summary returns 7 keys
  T219-2: overall_blocked=True by default (no preflight run)
  T219-3: blockers list contains no_preflight_run entry when no preflight
  T219-4: per-pair gap blocker surfaces in blockers list
  T219-5: total_blockers count matches len(blockers)
  T219-6: tournament_blocker_summary_enabled config defaults to True
  T219-7: GET /agent/tournament-blocker-summary returns 8 keys
  T219-8: GET /agent/tournament-blocker-summary overall_blocked=True with no preflight
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
    return Store(os.path.join(d, "test219.db"))


# ── T219-1: get_tournament_blocker_summary returns 7 keys ────────────────────
def test_T219_1_summary_returns_7_keys():
    """get_tournament_blocker_summary returns 7 expected keys."""
    store = _make_store()
    result = store.get_tournament_blocker_summary()
    expected_keys = {
        "total_blockers", "blockers", "overall_blocked",
        "preflight_pass", "capture_healthy", "all_pairs_above_1", "timestamp",
    }
    assert expected_keys.issubset(set(result.keys()))


# ── T219-2: overall_blocked=True by default ───────────────────────────────────
def test_T219_2_overall_blocked_by_default():
    """get_tournament_blocker_summary returns overall_blocked=True when no preflight has run."""
    store = _make_store()
    result = store.get_tournament_blocker_summary()
    assert result["overall_blocked"] is True
    assert result["preflight_pass"] is False


# ── T219-3: no_preflight_run blocker present when no preflight ────────────────
def test_T219_3_no_preflight_blocker_present():
    """Blockers list contains no_preflight_run entry when tournament preflight never run."""
    store = _make_store()
    result = store.get_tournament_blocker_summary()
    keys = [b["key"] for b in result["blockers"]]
    assert "no_preflight_run" in keys


# ── T219-4: per-pair gap blocker surfaces in list ────────────────────────────
def test_T219_4_per_pair_gap_blocker_in_list():
    """A per-pair gap entry with above_1_0=False appears in blockers list."""
    store = _make_store()
    store.insert_per_pair_gap(
        session_type="touchpad_corners", pair_key="P1vP3",
        player_i="P1", player_j="P3", distance=0.032, above_1_0=False,
        analysis_date="2026-04-16",
    )
    result = store.get_tournament_blocker_summary()
    sources = [b["source"] for b in result["blockers"]]
    keys = [b["key"] for b in result["blockers"]]
    assert "per_pair_gap" in sources
    assert "P1vP3" in keys


# ── T219-5: total_blockers matches len(blockers) ─────────────────────────────
def test_T219_5_total_blockers_matches_list():
    """total_blockers equals len(blockers) always."""
    store = _make_store()
    result = store.get_tournament_blocker_summary()
    assert result["total_blockers"] == len(result["blockers"])


# ── T219-6: tournament_blocker_summary_enabled defaults to True ──────────────
def test_T219_6_config_default_true():
    """tournament_blocker_summary_enabled config field defaults to True."""
    from vapi_bridge.config import Config
    cfg = Config()
    assert cfg.tournament_blocker_summary_enabled is True


# ── T219-7: endpoint returns 8 keys ──────────────────────────────────────────
def test_T219_7_endpoint_returns_correct_keys():
    """GET /agent/tournament-blocker-summary returns all 8 expected keys."""
    from fastapi.testclient import TestClient
    from vapi_bridge.config import Config
    from vapi_bridge.operator_api import create_operator_app

    store219 = _make_store()
    cfg219 = Config()
    app219 = create_operator_app(cfg219, store219)
    client = TestClient(app219)

    resp = client.get("/agent/tournament-blocker-summary")
    assert resp.status_code == 200
    body = resp.json()
    expected_keys = {
        "tournament_blocker_summary_enabled", "total_blockers", "blockers",
        "overall_blocked", "preflight_pass", "capture_healthy",
        "all_pairs_above_1", "timestamp",
    }
    assert set(body.keys()) == expected_keys


# ── T219-8: endpoint overall_blocked=True with no preflight ──────────────────
def test_T219_8_endpoint_blocked_no_preflight():
    """GET /agent/tournament-blocker-summary returns overall_blocked=True with no preflight."""
    from fastapi.testclient import TestClient
    from vapi_bridge.config import Config
    from vapi_bridge.operator_api import create_operator_app

    store219 = _make_store()
    cfg219 = Config()
    app219 = create_operator_app(cfg219, store219)
    client = TestClient(app219)

    resp = client.get("/agent/tournament-blocker-summary")
    assert resp.status_code == 200
    body = resp.json()
    assert body["overall_blocked"] is True
    assert body["total_blockers"] >= 1
