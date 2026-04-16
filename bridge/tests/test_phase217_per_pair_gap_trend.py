"""
Phase 217 — PerPairGapTrend Tests
T217-1..8

Tests:
  T217-1: get_per_pair_gap_trend returns UNKNOWN when no data
  T217-2: get_per_pair_gap_trend returns distances list with 1 entry
  T217-3: get_per_pair_gap_trend computes WORSENING when distance declines
  T217-4: get_per_pair_gap_trend computes IMPROVING when distance grows
  T217-5: get_per_pair_gap_trend returns STABLE when velocity near zero
  T217-6: per_pair_gap_trend_enabled config defaults to True
  T217-7: GET /agent/per-pair-gap-trend returns 8 keys
  T217-8: GET /agent/per-pair-gap-trend blocker_resolved=False when distance < 1.0
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
    return Store(os.path.join(d, "test217.db"))


# ── T217-1: get_per_pair_gap_trend returns UNKNOWN when no data ───────────────
def test_T217_1_trend_unknown_when_empty():
    """get_per_pair_gap_trend returns trend=UNKNOWN when no entries exist."""
    store = _make_store()
    result = store.get_per_pair_gap_trend(pair_key="P1vP3")
    assert result["trend"] == "UNKNOWN"
    assert result["n_runs"] == 0
    assert result["distances"] == []
    assert result["velocity_per_day"] is None


# ── T217-2: single entry returns UNKNOWN trend ────────────────────────────────
def test_T217_2_single_entry_unknown_trend():
    """get_per_pair_gap_trend with only 1 run returns trend=UNKNOWN (need ≥2)."""
    store = _make_store()
    store.insert_per_pair_gap(
        session_type="touchpad_corners", pair_key="P1vP3",
        player_i="P1", player_j="P3", distance=0.032, above_1_0=False,
        analysis_date="2026-04-16",
    )
    result = store.get_per_pair_gap_trend(pair_key="P1vP3")
    assert result["n_runs"] == 1
    assert result["trend"] == "UNKNOWN"
    assert abs(result["distances"][0] - 0.032) < 1e-6


# ── T217-3: WORSENING when distance declines over time ───────────────────────
def test_T217_3_worsening_trend():
    """get_per_pair_gap_trend returns WORSENING when distance declines (pair moving closer)."""
    import sqlite3 as _sql217
    store = _make_store()
    now = time.time()
    # Insert older entry with higher distance first, then newer with lower distance
    # (simulate pair getting closer = bad)
    with store._conn() as conn:
        conn.execute(
            "INSERT INTO per_pair_gap_log "
            "(session_type, pair_key, player_i, player_j, distance, above_1_0, "
            "n_sessions_i, n_sessions_j, analysis_date, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("touchpad_corners", "P1vP3", "P1", "P3",
             0.200, 0, 12, 10, "2026-04-14", now - 86400 * 3),
        )
        conn.execute(
            "INSERT INTO per_pair_gap_log "
            "(session_type, pair_key, player_i, player_j, distance, above_1_0, "
            "n_sessions_i, n_sessions_j, analysis_date, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("touchpad_corners", "P1vP3", "P1", "P3",
             0.032, 0, 12, 10, "2026-04-16", now),
        )
    result = store.get_per_pair_gap_trend(pair_key="P1vP3", session_type="touchpad_corners")
    assert result["trend"] == "WORSENING"
    assert result["velocity_per_day"] is not None
    assert result["velocity_per_day"] < 0


# ── T217-4: IMPROVING when distance grows ────────────────────────────────────
def test_T217_4_improving_trend():
    """get_per_pair_gap_trend returns IMPROVING when distance grows (pair moving apart)."""
    store = _make_store()
    now = time.time()
    with store._conn() as conn:
        conn.execute(
            "INSERT INTO per_pair_gap_log "
            "(session_type, pair_key, player_i, player_j, distance, above_1_0, "
            "n_sessions_i, n_sessions_j, analysis_date, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("touchpad_corners", "P1vP3", "P1", "P3",
             0.032, 0, 12, 10, "2026-04-14", now - 86400 * 3),
        )
        conn.execute(
            "INSERT INTO per_pair_gap_log "
            "(session_type, pair_key, player_i, player_j, distance, above_1_0, "
            "n_sessions_i, n_sessions_j, analysis_date, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("touchpad_corners", "P1vP3", "P1", "P3",
             0.500, 0, 12, 12, "2026-04-16", now),
        )
    result = store.get_per_pair_gap_trend(pair_key="P1vP3", session_type="touchpad_corners")
    assert result["trend"] == "IMPROVING"
    assert result["velocity_per_day"] is not None
    assert result["velocity_per_day"] > 0


# ── T217-5: STABLE when velocity near zero ───────────────────────────────────
def test_T217_5_stable_trend():
    """get_per_pair_gap_trend returns STABLE when distance change is negligible."""
    store = _make_store()
    now = time.time()
    with store._conn() as conn:
        conn.execute(
            "INSERT INTO per_pair_gap_log "
            "(session_type, pair_key, player_i, player_j, distance, above_1_0, "
            "n_sessions_i, n_sessions_j, analysis_date, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("touchpad_corners", "P1vP3", "P1", "P3",
             0.032, 0, 12, 10, "2026-04-14", now - 86400 * 2),
        )
        conn.execute(
            "INSERT INTO per_pair_gap_log "
            "(session_type, pair_key, player_i, player_j, distance, above_1_0, "
            "n_sessions_i, n_sessions_j, analysis_date, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("touchpad_corners", "P1vP3", "P1", "P3",
             0.033, 0, 12, 10, "2026-04-16", now),
        )
    result = store.get_per_pair_gap_trend(pair_key="P1vP3", session_type="touchpad_corners")
    assert result["trend"] == "STABLE"


# ── T217-6: per_pair_gap_trend_enabled defaults to True ──────────────────────
def test_T217_6_config_default_true():
    """per_pair_gap_trend_enabled config field defaults to True."""
    from vapi_bridge.config import Config
    cfg = Config()
    assert cfg.per_pair_gap_trend_enabled is True


# ── T217-7: endpoint returns 8 keys ──────────────────────────────────────────
def test_T217_7_endpoint_returns_correct_keys():
    """GET /agent/per-pair-gap-trend returns all 8 expected keys."""
    from fastapi.testclient import TestClient
    from vapi_bridge.config import Config
    from vapi_bridge.operator_api import create_operator_app

    store217 = _make_store()
    cfg217 = Config()
    app217 = create_operator_app(cfg217, store217)
    client = TestClient(app217)

    resp = client.get("/agent/per-pair-gap-trend?pair_key=P1vP3")
    assert resp.status_code == 200
    body = resp.json()
    expected_keys = {
        "per_pair_gap_trend_enabled", "pair_key", "distances",
        "velocity_per_day", "trend", "n_runs", "blocker_resolved", "timestamp",
    }
    assert set(body.keys()) == expected_keys


# ── T217-8: blocker_resolved=False when distance < 1.0 ───────────────────────
def test_T217_8_endpoint_blocker_resolved_false():
    """GET /agent/per-pair-gap-trend returns blocker_resolved=False for sub-1.0 pair."""
    from fastapi.testclient import TestClient
    from vapi_bridge.config import Config
    from vapi_bridge.operator_api import create_operator_app

    store217 = _make_store()
    cfg217 = Config()
    app217 = create_operator_app(cfg217, store217)
    store217.insert_per_pair_gap(
        session_type="touchpad_corners", pair_key="P1vP3",
        player_i="P1", player_j="P3", distance=0.032, above_1_0=False,
        analysis_date="2026-04-16",
    )
    client = TestClient(app217)
    resp = client.get("/agent/per-pair-gap-trend?pair_key=P1vP3")
    assert resp.status_code == 200
    body = resp.json()
    assert body["blocker_resolved"] is False
    assert body["pair_key"] == "P1vP3"
