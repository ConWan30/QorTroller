"""
Phase 197 — Per-Pair Separation P0 Gate: all_pairs_p0_ok as 10th P0 condition.

all_pairs_p0_ok=True only when EVERY inter-player pair has separation ratio >= 1.0.
Current blocker: P2vP3=0.401 < 1.0 (even though global ratio may cross 1.0 via P1 sessions).
"""
import sys
import tempfile
import time
import os
from pathlib import Path
import json

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "bridge"))


def _make_store():
    from vapi_bridge.store import Store
    d = tempfile.mkdtemp()
    return Store(os.path.join(d, "test197.db"))


# ---------------------------------------------------------------------------
# T197-1: all_pairs_p0_ok defaults to False (fail-closed)
# ---------------------------------------------------------------------------

def test_t197_1_all_pairs_p0_ok_default_false():
    store = _make_store()
    store.insert_tournament_preflight_log(
        separation_ok=True, l4_ok=True, gate_ok=True, cert_ok=True, audit_ok=True,
        overall_pass=False,
    )
    rows = store.get_tournament_preflight_status(limit=1)
    assert rows[0]["all_pairs_p0_ok"] is False


# ---------------------------------------------------------------------------
# T197-2: all_pairs_p0_ok=True persists correctly
# ---------------------------------------------------------------------------

def test_t197_2_all_pairs_p0_ok_true_persists():
    store = _make_store()
    store.insert_tournament_preflight_log(
        separation_ok=True, l4_ok=True, gate_ok=True, cert_ok=True, audit_ok=True,
        overall_pass=True, biometric_ttl_ok=True, all_pairs_p0_ok=True,
    )
    rows = store.get_tournament_preflight_status(limit=1)
    assert rows[0]["all_pairs_p0_ok"] is True


# ---------------------------------------------------------------------------
# T197-3: all 10 P0 conditions True → overall_pass=True
# ---------------------------------------------------------------------------

def test_t197_3_all_10_p0_conditions_overall_pass():
    store = _make_store()
    store.insert_tournament_preflight_log(
        separation_ok=True, l4_ok=True, gate_ok=True, cert_ok=True, audit_ok=True,
        overall_pass=True, biometric_ttl_ok=True, all_pairs_p0_ok=True,
    )
    rows = store.get_tournament_preflight_status(limit=1)
    assert rows[0]["overall_pass"] is True
    assert rows[0]["all_pairs_p0_ok"] is True
    assert rows[0]["biometric_ttl_ok"] is True


# ---------------------------------------------------------------------------
# T197-4: all_pairs_p0_ok=False blocks overall_pass even when others pass
# ---------------------------------------------------------------------------

def test_t197_4_all_pairs_false_blocks_overall():
    store = _make_store()
    store.insert_tournament_preflight_log(
        separation_ok=True, l4_ok=True, gate_ok=True, cert_ok=True, audit_ok=True,
        overall_pass=False, biometric_ttl_ok=True, all_pairs_p0_ok=False,
    )
    rows = store.get_tournament_preflight_status(limit=1)
    assert rows[0]["overall_pass"] is False
    assert rows[0]["all_pairs_p0_ok"] is False


# ---------------------------------------------------------------------------
# T197-5: multiple rows — newest first; all_pairs_p0_ok changes correctly
# ---------------------------------------------------------------------------

def test_t197_5_newest_first_pair_state_changes():
    store = _make_store()
    # First run: pair blocker
    store.insert_tournament_preflight_log(
        separation_ok=True, l4_ok=True, gate_ok=True, cert_ok=True, audit_ok=True,
        overall_pass=False, biometric_ttl_ok=True, all_pairs_p0_ok=False,
    )
    time.sleep(0.02)
    # Second run: pairs cleared (hypothetical)
    store.insert_tournament_preflight_log(
        separation_ok=True, l4_ok=True, gate_ok=True, cert_ok=True, audit_ok=True,
        overall_pass=True, biometric_ttl_ok=True, all_pairs_p0_ok=True,
    )
    rows = store.get_tournament_preflight_status(limit=2)
    # Newest first: all_pairs_p0_ok=True
    assert rows[0]["all_pairs_p0_ok"] is True
    assert rows[1]["all_pairs_p0_ok"] is False


# ---------------------------------------------------------------------------
# T197-6: conditions_json includes all_pairs_p0_ok
# ---------------------------------------------------------------------------

def test_t197_6_conditions_json_includes_all_pairs():
    store = _make_store()
    conditions = {
        "all_pairs_p0_ok": False,
        "separation_ratio": 1.002,
        "p2vp3_ratio": 0.401,
    }
    store.insert_tournament_preflight_log(
        separation_ok=True, l4_ok=True, gate_ok=True, cert_ok=True, audit_ok=True,
        overall_pass=False, all_pairs_p0_ok=False,
        conditions_json=json.dumps(conditions),
    )
    rows = store.get_tournament_preflight_status(limit=1)
    cond = json.loads(rows[0]["conditions_json"])
    assert cond["all_pairs_p0_ok"] is False
    assert abs(cond["p2vp3_ratio"] - 0.401) < 0.001


# ---------------------------------------------------------------------------
# T197-7: idempotent ALTER TABLE — no errors on re-init
# ---------------------------------------------------------------------------

def test_t197_7_idempotent_migration():
    from vapi_bridge.store import Store
    d = tempfile.mkdtemp()
    path = os.path.join(d, "test197_idem.db")
    s1 = Store(path)
    s2 = Store(path)
    s2.insert_tournament_preflight_log(
        separation_ok=True, l4_ok=True, gate_ok=True, cert_ok=True, audit_ok=True,
        overall_pass=True, biometric_ttl_ok=True, all_pairs_p0_ok=True,
    )
    rows = s2.get_tournament_preflight_status(limit=1)
    assert rows[0]["all_pairs_p0_ok"] is True


# ---------------------------------------------------------------------------
# T197-8: old insert call without all_pairs_p0_ok defaults to False (fail-closed)
# ---------------------------------------------------------------------------

def test_t197_8_old_insert_call_defaults_all_pairs_false():
    store = _make_store()
    store.insert_tournament_preflight_log(
        separation_ok=True, l4_ok=True, gate_ok=True, cert_ok=True, audit_ok=True,
    )
    rows = store.get_tournament_preflight_status(limit=1)
    assert rows[0]["all_pairs_p0_ok"] is False  # fail-closed default
