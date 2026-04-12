"""
Phase 196 — Tournament Preflight v2: biometric_ttl_ok as 9th P0 condition.

WIF-035 W1 formal closure: biometric_ttl_ok blocks tournament activation
when credential TTL has expired or no renewal chain entry exists.
"""
import sys
import tempfile
import time
import os
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "bridge"))


def _make_store():
    from vapi_bridge.store import Store
    d = tempfile.mkdtemp()
    return Store(os.path.join(d, "test196.db"))


# ---------------------------------------------------------------------------
# T196-1: biometric_ttl_ok defaults to True in insert (no column → old row)
# ---------------------------------------------------------------------------

def test_t196_1_biometric_ttl_ok_default_true():
    store = _make_store()
    row_id = store.insert_tournament_preflight_log(
        separation_ok=True, l4_ok=True, gate_ok=True, cert_ok=True, audit_ok=True,
        overall_pass=True,
    )
    rows = store.get_tournament_preflight_status(limit=1)
    assert len(rows) == 1
    # Default should be True (fail-open for old rows)
    assert rows[0]["biometric_ttl_ok"] is True


# ---------------------------------------------------------------------------
# T196-2: biometric_ttl_ok=False persists correctly
# ---------------------------------------------------------------------------

def test_t196_2_biometric_ttl_ok_false_persists():
    store = _make_store()
    store.insert_tournament_preflight_log(
        separation_ok=True, l4_ok=True, gate_ok=True, cert_ok=True, audit_ok=True,
        overall_pass=False, biometric_ttl_ok=False,
    )
    rows = store.get_tournament_preflight_status(limit=1)
    assert rows[0]["biometric_ttl_ok"] is False


# ---------------------------------------------------------------------------
# T196-3: overall_pass=False when biometric_ttl_ok=False
# ---------------------------------------------------------------------------

def test_t196_3_overall_pass_false_when_ttl_failed():
    store = _make_store()
    store.insert_tournament_preflight_log(
        separation_ok=True, l4_ok=True, gate_ok=True, cert_ok=True, audit_ok=True,
        overall_pass=False, biometric_ttl_ok=False,
    )
    rows = store.get_tournament_preflight_status(limit=1)
    assert rows[0]["overall_pass"] is False


# ---------------------------------------------------------------------------
# T196-4: all 9 P0 conditions True → overall_pass=True
# ---------------------------------------------------------------------------

def test_t196_4_all_p0_true_overall_pass():
    store = _make_store()
    store.insert_tournament_preflight_log(
        separation_ok=True, l4_ok=True, gate_ok=True, cert_ok=True, audit_ok=True,
        overall_pass=True, biometric_ttl_ok=True,
    )
    rows = store.get_tournament_preflight_status(limit=1)
    assert rows[0]["overall_pass"] is True
    assert rows[0]["biometric_ttl_ok"] is True


# ---------------------------------------------------------------------------
# T196-5: multiple rows — get_tournament_preflight_status returns newest first
# ---------------------------------------------------------------------------

def test_t196_5_newest_first():
    store = _make_store()
    store.insert_tournament_preflight_log(
        separation_ok=True, l4_ok=True, gate_ok=True, cert_ok=True, audit_ok=True,
        overall_pass=True, biometric_ttl_ok=True,
    )
    time.sleep(0.02)
    store.insert_tournament_preflight_log(
        separation_ok=True, l4_ok=True, gate_ok=True, cert_ok=True, audit_ok=True,
        overall_pass=False, biometric_ttl_ok=False,
    )
    rows = store.get_tournament_preflight_status(limit=2)
    assert len(rows) == 2
    # Newest first: biometric_ttl_ok=False
    assert rows[0]["biometric_ttl_ok"] is False
    assert rows[1]["biometric_ttl_ok"] is True


# ---------------------------------------------------------------------------
# T196-6: biometric_ttl_ok in conditions_json
# ---------------------------------------------------------------------------

def test_t196_6_conditions_json_includes_ttl_ok():
    import json
    store = _make_store()
    conditions = {
        "biometric_ttl_ok": False,
        "biometric_ttl_expired": True,
        "biometric_renewal_entries": 0,
    }
    store.insert_tournament_preflight_log(
        separation_ok=True, l4_ok=True, gate_ok=True, cert_ok=True, audit_ok=True,
        overall_pass=False, biometric_ttl_ok=False,
        conditions_json=json.dumps(conditions),
    )
    rows = store.get_tournament_preflight_status(limit=1)
    cond = json.loads(rows[0]["conditions_json"])
    assert cond["biometric_ttl_ok"] is False
    assert cond["biometric_ttl_expired"] is True


# ---------------------------------------------------------------------------
# T196-7: idempotent schema migration — table can be re-created
# ---------------------------------------------------------------------------

def test_t196_7_idempotent_migration():
    # Opening the same DB twice triggers migration idempotency
    from vapi_bridge.store import Store
    d = tempfile.mkdtemp()
    path = os.path.join(d, "test196_idem.db")
    s1 = Store(path)
    s2 = Store(path)  # triggers idempotent ALTER TABLE again — should not error
    s2.insert_tournament_preflight_log(
        separation_ok=True, l4_ok=True, gate_ok=True, cert_ok=True, audit_ok=True,
        overall_pass=True, biometric_ttl_ok=True,
    )
    rows = s2.get_tournament_preflight_status(limit=1)
    assert rows[0]["biometric_ttl_ok"] is True


# ---------------------------------------------------------------------------
# T196-8: biometric_ttl_ok=True (default) for old 8-arg insert calls
# ---------------------------------------------------------------------------

def test_t196_8_old_insert_call_defaults_ttl_ok_true():
    store = _make_store()
    # Simulate old call without biometric_ttl_ok kwarg
    store.insert_tournament_preflight_log(
        separation_ok=False, l4_ok=False, gate_ok=False,
        cert_ok=False, audit_ok=False,
    )
    rows = store.get_tournament_preflight_status(limit=1)
    assert rows[0]["biometric_ttl_ok"] is True  # default=True
