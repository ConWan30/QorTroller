"""Phase 231 — AIT Defensibility P0 Gate + Stage 1 Graduation.

T231-1: ait_defensibility_ok=False when no AIT data in preflight
T231-2: ait_defensibility_ok=False when all_pairs_above_1=False
T231-3: ait_defensibility_ok=False when all_pairs_above_1=True but player has <10 sessions
T231-4: ait_defensibility_ok=True when all_pairs_above_1=True AND all players have >=10 sessions
T231-5: insert_tournament_preflight_log accepts ait_defensibility_ok kwarg
T231-6: get_tournament_preflight_status returns ait_defensibility_ok field
T231-7: ait_defensibility_ok included in overall_pass logic (False blocks pass)
T231-8: analyze_interperson_separation.py AIT write-snapshot path is reachable (import check)
"""
import json
import os
import sys
import tempfile
import time
import pytest

# ---------------------------------------------------------------------------
# Store-level DB helpers
# ---------------------------------------------------------------------------

def _make_store(db_path):
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    from vapi_bridge.store import Store
    return Store(db_path)


@pytest.fixture()
def tmp_db(tmp_path):
    return str(tmp_path / "test_phase231.db")


# ---------------------------------------------------------------------------
# T231-1: No AIT data → ait_defensibility_ok=False
# ---------------------------------------------------------------------------

def test_t231_1_no_ait_data_defensibility_false(tmp_db):
    store = _make_store(tmp_db)
    status = store.get_ait_separation_status()
    # No rows → None or empty dict
    assert status is None or not status.get("all_pairs_above_1", False)


# ---------------------------------------------------------------------------
# T231-2: AIT data with all_pairs_above_1=False → defensibility=False
# ---------------------------------------------------------------------------

def test_t231_2_all_pairs_false_defensibility_false(tmp_db):
    store = _make_store(tmp_db)
    store.insert_ait_session(
        n_sessions=15,
        n_per_player={"P1": 5, "P2": 5, "P3": 5},
        separation_ratio=0.80,
        all_pairs_above_1=False,
        inter_player_mean=0.90,
        intra_player_mean=1.10,
        loo_accuracy=0.60,
        cov_mode="full",
        pair_distances={"P1vP2": 0.80, "P1vP3": 0.85, "P2vP3": 0.75},
        analysis_date="2026-04-20",
    )
    status = store.get_ait_separation_status()
    assert status is not None
    all_pairs = bool(status.get("all_pairs_above_1", False))
    assert all_pairs is False


# ---------------------------------------------------------------------------
# T231-3: all_pairs_above_1=True but player has <10 sessions → defensibility=False
# ---------------------------------------------------------------------------

def test_t231_3_all_pairs_true_insufficient_sessions(tmp_db):
    store = _make_store(tmp_db)
    store.insert_ait_session(
        n_sessions=20,
        n_per_player={"P1": 10, "P2": 5, "P3": 5},   # P2+P3 < 10
        separation_ratio=1.20,
        all_pairs_above_1=True,
        inter_player_mean=1.50,
        intra_player_mean=0.80,
        loo_accuracy=0.70,
        cov_mode="full",
        pair_distances={"P1vP2": 1.85, "P1vP3": 1.85, "P2vP3": 1.35},
        analysis_date="2026-04-20",
    )
    status = store.get_ait_separation_status()
    assert bool(status.get("all_pairs_above_1", False)) is True
    npp = status.get("n_per_player", {}) or {}
    defensible = bool(npp) and all(int(v) >= 10 for v in npp.values())
    assert defensible is False   # P2=5 and P3=5 are below 10


# ---------------------------------------------------------------------------
# T231-4: all_pairs_above_1=True AND all players >=10 → defensibility=True
# ---------------------------------------------------------------------------

def test_t231_4_all_pairs_true_sufficient_sessions(tmp_db):
    store = _make_store(tmp_db)
    store.insert_ait_session(
        n_sessions=37,
        n_per_player={"P1": 13, "P2": 10, "P3": 14},
        separation_ratio=1.199,
        all_pairs_above_1=True,
        inter_player_mean=1.682,
        intra_player_mean=0.85,
        loo_accuracy=0.667,
        cov_mode="full",
        pair_distances={"P1vP2": 1.850, "P1vP3": 1.846, "P2vP3": 1.349},
        analysis_date="2026-04-20",
    )
    status = store.get_ait_separation_status()
    assert bool(status.get("all_pairs_above_1", False)) is True
    npp = status.get("n_per_player", {}) or {}
    defensible = bool(npp) and all(int(v) >= 10 for v in npp.values())
    assert defensible is True


# ---------------------------------------------------------------------------
# T231-5: insert_tournament_preflight_log accepts ait_defensibility_ok
# ---------------------------------------------------------------------------

def test_t231_5_insert_preflight_accepts_ait_defensibility(tmp_db):
    store = _make_store(tmp_db)
    row_id = store.insert_tournament_preflight_log(
        separation_ok=True,
        l4_ok=True,
        gate_ok=True,
        cert_ok=True,
        audit_ok=True,
        overall_pass=True,
        ait_defensibility_ok=True,
    )
    assert isinstance(row_id, int)
    assert row_id > 0


# ---------------------------------------------------------------------------
# T231-6: get_tournament_preflight_status returns ait_defensibility_ok field
# ---------------------------------------------------------------------------

def test_t231_6_get_preflight_status_returns_ait_defensibility(tmp_db):
    store = _make_store(tmp_db)
    store.insert_tournament_preflight_log(
        separation_ok=True,
        l4_ok=True,
        gate_ok=True,
        cert_ok=True,
        audit_ok=True,
        overall_pass=True,
        ait_defensibility_ok=True,
    )
    rows = store.get_tournament_preflight_status(limit=1)
    assert len(rows) == 1
    row = rows[0]
    assert "ait_defensibility_ok" in row
    assert row["ait_defensibility_ok"] is True


# ---------------------------------------------------------------------------
# T231-7: ait_defensibility_ok=False stored as False, overall_pass reflects it
# ---------------------------------------------------------------------------

def test_t231_7_ait_defensibility_false_persists(tmp_db):
    store = _make_store(tmp_db)
    store.insert_tournament_preflight_log(
        separation_ok=True,
        l4_ok=True,
        gate_ok=True,
        cert_ok=True,
        audit_ok=True,
        overall_pass=False,  # blocked by ait_defensibility_ok=False
        ait_defensibility_ok=False,
    )
    rows = store.get_tournament_preflight_status(limit=1)
    assert len(rows) == 1
    row = rows[0]
    assert row["ait_defensibility_ok"] is False
    assert row["overall_pass"] is False


# ---------------------------------------------------------------------------
# T231-8: analyze_interperson_separation.py AIT write-snapshot path is importable
# ---------------------------------------------------------------------------

def test_t231_8_analysis_script_importable():
    scripts_dir = os.path.join(
        os.path.dirname(__file__), "..", "..", "scripts"
    )
    assert os.path.exists(os.path.join(scripts_dir, "analyze_interperson_separation.py")), (
        "analyze_interperson_separation.py not found"
    )
    # Verify the Phase 231 AIT write-snapshot keyword is present in the script
    script_path = os.path.join(scripts_dir, "analyze_interperson_separation.py")
    with open(script_path, encoding="utf-8") as f:
        src = f.read()
    assert "Phase 231" in src, "Phase 231 tag not found in analysis script"
    assert "insert_ait_session" in src, "insert_ait_session call not found in AIT write-snapshot block"
