"""
bridge/tests/test_phase230_ait_p0_gate.py
Phase 230 — AIT P0 Gate Wire-up (8 tests)

T230-1: insert_ait_session() writes row to separation_defensibility_log with session_type='ait'
T230-2: get_separation_defensibility_status() (no filter) returns AIT row after insert
T230-3: get_separation_defensibility_status(session_type='ait') returns correct ratio
T230-4: tournament_preflight all_pairs_p0_ok=True after AIT insert with all_pairs_above_1=True
T230-5: AIT row in separation_defensibility_log has correct all_pairs_above_1 value
T230-6: defensible=False when players have < min_n sessions even if all_pairs_above_1=True
T230-7: defensible=True when all players have >= 10 sessions AND all_pairs_above_1=True
T230-8: multiple AIT inserts; most recent wins in unfiltered get_separation_defensibility_status()
"""

import sys
import os
from pathlib import Path
from unittest.mock import MagicMock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "bridge"))

import types
for _mod in ["web3", "web3.exceptions", "eth_account", "eth_account.messages"]:
    if _mod not in sys.modules:
        sys.modules[_mod] = types.ModuleType(_mod)

import tempfile


def make_store(tmp_dir=None):
    from vapi_bridge.store import Store
    if tmp_dir is None:
        tmp_dir = tempfile.mkdtemp()
    return Store(os.path.join(tmp_dir, "test_phase230.db"))


def make_cfg(**overrides):
    from vapi_bridge.config import Config
    cfg = Config()
    for k, v in overrides.items():
        setattr(cfg, k, v)
    return cfg


_SAMPLE_PAIRS = {"P1vP2": 1.850, "P1vP3": 1.846, "P2vP3": 1.349}


def _insert_ait(store, n=24, ratio=1.199, all_pairs=True,
                n_per_player=None, date="2026-04-18"):
    if n_per_player is None:
        n_per_player = {"P1": 6, "P2": 5, "P3": 13}
    return store.insert_ait_session(
        n_sessions        = n,
        n_per_player      = n_per_player,
        separation_ratio  = ratio,
        all_pairs_above_1 = all_pairs,
        inter_player_mean = 1.682,
        intra_player_mean = 0.991,
        loo_accuracy      = 0.667,
        cov_mode          = "full",
        pair_distances    = _SAMPLE_PAIRS,
        analysis_date     = date,
    )


# ---------------------------------------------------------------------------
# T230-1: insert_ait_session writes to separation_defensibility_log
# ---------------------------------------------------------------------------

def test_t230_1_ait_insert_writes_defensibility_log(tmp_path):
    """insert_ait_session() should also create a row in separation_defensibility_log."""
    store = make_store(str(tmp_path))
    _insert_ait(store)

    row = store.get_separation_defensibility_status(session_type="ait")
    assert row is not None, "No separation_defensibility_log row found for session_type='ait'"
    assert row["session_type"] == "ait"


# ---------------------------------------------------------------------------
# T230-2: get_separation_defensibility_status() (no filter) returns AIT row
# ---------------------------------------------------------------------------

def test_t230_2_unfiltered_status_returns_ait_row(tmp_path):
    """get_separation_defensibility_status() without filter returns AIT row when it is most recent."""
    store = make_store(str(tmp_path))
    _insert_ait(store)

    row = store.get_separation_defensibility_status()
    assert row is not None
    assert row["session_type"] == "ait"
    assert abs(row["ratio"] - 1.199) < 1e-4


# ---------------------------------------------------------------------------
# T230-3: get_separation_defensibility_status(session_type='ait') returns correct ratio
# ---------------------------------------------------------------------------

def test_t230_3_ait_filtered_status_correct_ratio(tmp_path):
    """get_separation_defensibility_status(session_type='ait') returns inserted ratio."""
    store = make_store(str(tmp_path))
    _insert_ait(store, ratio=1.199, all_pairs=True)

    row = store.get_separation_defensibility_status(session_type="ait")
    assert row is not None
    assert abs(row["ratio"] - 1.199) < 1e-4
    assert bool(row["all_pairs_above_1"]) is True


# ---------------------------------------------------------------------------
# T230-4: tournament_preflight all_pairs_p0_ok=True after AIT insert
# ---------------------------------------------------------------------------

def test_t230_4_preflight_all_pairs_p0_ok_after_ait(tmp_path):
    """POST /agent/run-tournament-preflight returns all_pairs_p0_ok=True after AIT insert."""
    import unittest.mock
    from fastapi.testclient import TestClient
    from vapi_bridge.operator_api import create_operator_app

    store = make_store(str(tmp_path))
    _insert_ait(store, all_pairs=True)

    with unittest.mock.patch.dict(
        os.environ,
        {"OPERATOR_API_KEY": "test-key-230", "ALL_PAIRS_GATE_ENABLED": "true"},
        clear=False,
    ):
        cfg = make_cfg()
        app = create_operator_app(cfg, store)
        client = TestClient(app)
        resp = client.post("/agent/run-tournament-preflight?api_key=test-key-230")

    assert resp.status_code == 200
    body = resp.json()
    assert body.get("all_pairs_p0_ok") is True, (
        f"Expected all_pairs_p0_ok=True but got {body.get('all_pairs_p0_ok')!r}. "
        f"Full response: {body}"
    )


# ---------------------------------------------------------------------------
# T230-5: AIT row has correct all_pairs_above_1 value in defensibility log
# ---------------------------------------------------------------------------

def test_t230_5_all_pairs_above_1_stored_correctly(tmp_path):
    """separation_defensibility_log row written by insert_ait_session has correct all_pairs_above_1."""
    store = make_store(str(tmp_path))
    _insert_ait(store, all_pairs=True)

    row = store.get_separation_defensibility_status(session_type="ait")
    assert row is not None
    assert bool(row["all_pairs_above_1"]) is True

    # Also verify a False case is stored correctly
    store2 = make_store()
    _insert_ait(store2, ratio=0.850, all_pairs=False)
    row2 = store2.get_separation_defensibility_status(session_type="ait")
    assert row2 is not None
    assert bool(row2["all_pairs_above_1"]) is False


# ---------------------------------------------------------------------------
# T230-6: defensible=False when players below min_n (P1=6, P2=5 < 10)
# ---------------------------------------------------------------------------

def test_t230_6_defensible_false_below_min_n(tmp_path):
    """defensible=False when player N counts are below min_n_per_player=10."""
    store = make_store(str(tmp_path))
    # Current AIT corpus: P1=6, P2=5, P3=13 — P1 and P2 below min 10
    _insert_ait(store, n_per_player={"P1": 6, "P2": 5, "P3": 13}, all_pairs=True)

    row = store.get_separation_defensibility_status(session_type="ait")
    assert row is not None
    # defensible requires all players >= 10; P1=6 and P2=5 fail
    assert bool(row["defensible"]) is False
    # But all_pairs_above_1 is still True — the P0 gate only needs this
    assert bool(row["all_pairs_above_1"]) is True


# ---------------------------------------------------------------------------
# T230-7: defensible=True when all players >= 10 AND all_pairs_above_1=True
# ---------------------------------------------------------------------------

def test_t230_7_defensible_true_when_all_above_min(tmp_path):
    """defensible=True when all players have >= 10 sessions AND all_pairs_above_1=True."""
    store = make_store(str(tmp_path))
    _insert_ait(
        store,
        n_per_player={"P1": 10, "P2": 11, "P3": 13},
        all_pairs=True,
        ratio=1.199,
    )

    row = store.get_separation_defensibility_status(session_type="ait")
    assert row is not None
    assert bool(row["defensible"]) is True
    assert bool(row["all_pairs_above_1"]) is True


# ---------------------------------------------------------------------------
# T230-8: multiple AIT inserts; most recent wins in unfiltered status
# ---------------------------------------------------------------------------

def test_t230_8_multiple_inserts_latest_wins(tmp_path):
    """Most recent insert_ait_session row wins in unfiltered get_separation_defensibility_status."""
    store = make_store(str(tmp_path))

    _insert_ait(store, ratio=0.980, all_pairs=False, date="2026-04-10")
    _insert_ait(store, ratio=1.199, all_pairs=True,  date="2026-04-18")

    row = store.get_separation_defensibility_status()
    assert row is not None
    assert row["session_type"] == "ait"
    assert abs(row["ratio"] - 1.199) < 1e-4
    assert bool(row["all_pairs_above_1"]) is True
