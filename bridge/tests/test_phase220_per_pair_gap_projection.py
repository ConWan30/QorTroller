"""
Phase 220 — PerPairGapProjection Tests
T220-1..8

Tests:
  T220-1: get_per_pair_gap_projection returns 6 keys
  T220-2: projections list is empty when no gap data
  T220-3: resolved pair returns status=RESOLVED and days=0
  T220-4: IMPROVING pair returns feasible projection with days > 0
  T220-5: WORSENING pair returns projection_feasible=False
  T220-6: per_pair_gap_projection_enabled config defaults to True
  T220-7: GET /agent/per-pair-gap-projection returns 7 keys
  T220-8: GET /agent/per-pair-gap-projection any_feasible=False with no gap data
"""
import os
import sys
import tempfile
import time
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
    return Store(os.path.join(d, "test220.db"))


# ── T220-1: get_per_pair_gap_projection returns 6 keys ───────────────────────
def test_T220_1_projection_returns_6_keys():
    """get_per_pair_gap_projection returns 6 expected keys."""
    store = _make_store()
    result = store.get_per_pair_gap_projection()
    expected_keys = {
        "projections", "any_feasible", "max_days_to_1_0",
        "projected_tge_date", "session_type", "timestamp",
    }
    assert expected_keys.issubset(set(result.keys()))


# ── T220-2: projections is empty when no gap data ────────────────────────────
def test_T220_2_projections_empty_when_no_data():
    """get_per_pair_gap_projection returns empty projections when no gap entries."""
    store = _make_store()
    result = store.get_per_pair_gap_projection()
    assert result["projections"] == []
    assert result["any_feasible"] is False
    assert result["max_days_to_1_0"] is None
    assert result["projected_tge_date"] is None


# ── T220-3: resolved pair returns RESOLVED status ────────────────────────────
def test_T220_3_resolved_pair_status():
    """A pair with above_1_0=True appears as RESOLVED with days=0."""
    store = _make_store()
    store.insert_per_pair_gap(
        session_type="touchpad_corners", pair_key="P1vP2",
        player_i="P1", player_j="P2", distance=1.133, above_1_0=True,
        analysis_date="2026-04-16",
    )
    result = store.get_per_pair_gap_projection()
    assert len(result["projections"]) == 1
    p = result["projections"][0]
    assert p["status"] == "RESOLVED"
    assert p["projection_feasible"] is True
    assert p["estimated_days_to_1_0"] == 0


# ── T220-4: IMPROVING pair produces feasible projection ──────────────────────
def test_T220_4_improving_pair_feasible():
    """A pair with IMPROVING velocity produces a feasible projection with days > 0."""
    store = _make_store()
    now = time.time()
    # Insert 2 entries to enable trend: old distance=0.032, new=0.500 (IMPROVING)
    with store._conn() as conn:
        conn.execute(
            "INSERT INTO per_pair_gap_log "
            "(session_type, pair_key, player_i, player_j, distance, above_1_0, "
            "n_sessions_i, n_sessions_j, analysis_date, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("touchpad_corners", "P1vP3", "P1", "P3",
             0.032, 0, 12, 10, "2026-04-13", now - 86400 * 3),
        )
        conn.execute(
            "INSERT INTO per_pair_gap_log "
            "(session_type, pair_key, player_i, player_j, distance, above_1_0, "
            "n_sessions_i, n_sessions_j, analysis_date, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("touchpad_corners", "P1vP3", "P1", "P3",
             0.500, 0, 12, 12, "2026-04-16", now),
        )
    result = store.get_per_pair_gap_projection(session_type="touchpad_corners")
    assert len(result["projections"]) == 1
    p = result["projections"][0]
    assert p["projection_feasible"] is True
    assert p["estimated_days_to_1_0"] is not None
    assert p["estimated_days_to_1_0"] > 0
    assert p["projected_date"] is not None
    assert result["max_days_to_1_0"] is not None
    assert result["projected_tge_date"] is not None


# ── T220-5: WORSENING pair returns projection_feasible=False ─────────────────
def test_T220_5_worsening_pair_infeasible():
    """A pair with WORSENING velocity returns projection_feasible=False."""
    store = _make_store()
    now = time.time()
    with store._conn() as conn:
        # Old entry higher, new entry lower = WORSENING
        conn.execute(
            "INSERT INTO per_pair_gap_log "
            "(session_type, pair_key, player_i, player_j, distance, above_1_0, "
            "n_sessions_i, n_sessions_j, analysis_date, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("touchpad_corners", "P2vP3", "P2", "P3",
             0.500, 0, 12, 10, "2026-04-13", now - 86400 * 3),
        )
        conn.execute(
            "INSERT INTO per_pair_gap_log "
            "(session_type, pair_key, player_i, player_j, distance, above_1_0, "
            "n_sessions_i, n_sessions_j, analysis_date, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("touchpad_corners", "P2vP3", "P2", "P3",
             0.032, 0, 12, 12, "2026-04-16", now),
        )
    result = store.get_per_pair_gap_projection(session_type="touchpad_corners")
    assert len(result["projections"]) == 1
    p = result["projections"][0]
    assert p["projection_feasible"] is False
    assert result["any_feasible"] is False


# ── T220-6: per_pair_gap_projection_enabled defaults to True ─────────────────
def test_T220_6_config_default_true():
    """per_pair_gap_projection_enabled config field defaults to True."""
    from vapi_bridge.config import Config
    cfg = Config()
    assert cfg.per_pair_gap_projection_enabled is True


# ── T220-7: endpoint returns 7 keys ──────────────────────────────────────────
def test_T220_7_endpoint_returns_correct_keys():
    """GET /agent/per-pair-gap-projection returns all 7 expected keys."""
    from fastapi.testclient import TestClient
    from vapi_bridge.config import Config
    from vapi_bridge.operator_api import create_operator_app

    store220 = _make_store()
    cfg220 = Config()
    app220 = create_operator_app(cfg220, store220)
    client = TestClient(app220)

    resp = client.get("/agent/per-pair-gap-projection")
    assert resp.status_code == 200
    body = resp.json()
    expected_keys = {
        "per_pair_gap_projection_enabled", "projections", "any_feasible",
        "max_days_to_1_0", "projected_tge_date", "session_type", "timestamp",
    }
    assert set(body.keys()) == expected_keys


# ── T220-8: endpoint any_feasible=False with no data ─────────────────────────
def test_T220_8_endpoint_no_feasible_when_empty():
    """GET /agent/per-pair-gap-projection returns any_feasible=False with no gap data."""
    from fastapi.testclient import TestClient
    from vapi_bridge.config import Config
    from vapi_bridge.operator_api import create_operator_app

    store220 = _make_store()
    cfg220 = Config()
    app220 = create_operator_app(cfg220, store220)
    client = TestClient(app220)

    resp = client.get("/agent/per-pair-gap-projection")
    assert resp.status_code == 200
    body = resp.json()
    assert body["any_feasible"] is False
    assert body["projections"] == []
