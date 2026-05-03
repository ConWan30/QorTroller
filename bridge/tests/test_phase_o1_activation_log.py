"""Phase O1 C1 — operator_agent_activation_log store helper tests.

T-O1-AL-1   insert + round-trip via get_operator_agent_activation_log
T-O1-AL-2   UNIQUE(agent_id, to_scope_root) anti-replay (INV-OPERATOR-AGENT-002)
T-O1-AL-3   get_current_operational_phase derives latest to_phase or O0_DORMANT
T-O1-AL-4   pagination + agent_id filter
T-O1-AL-5   monotonicity — most-recent-first ordering by activated_at DESC
"""
import os
import sqlite3
import sys
import tempfile
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from vapi_bridge.store import Store


SENTRY = "0xb21e1ec258d2d381c313f84944bd36fbc63badb2c9a24c2412212d3a27e3e42c"
GUARDIAN = "0xbd8c7fba08815b7ed343973c9c7300c062303b1acd19e8d9847a953ce5fa38d1"


@pytest.fixture
def store(tmp_path):
    db_path = str(tmp_path / "test.db")
    return Store(db_path)


def _row_id(store, agent_id, to_root, **overrides):
    defaults = dict(
        agent_id=agent_id,
        from_phase="O0_DORMANT",
        to_phase="O1_SHADOW",
        from_scope_root="0x" + "0" * 64,
        to_scope_root=to_root,
        bundle_path="test.json",
        governance_tx_hash="0xgov",
        operational_tx_hash="0xop",
        governance_block_number=100,
        operational_block_number=99,
        operator_authority_hash="0xauth",
        reason_text="Phase O1 activation test",
    )
    defaults.update(overrides)
    return store.insert_operator_agent_activation(**defaults)


# ----------------------------------------------------------------------
# T-O1-AL-1 — insert + round-trip
# ----------------------------------------------------------------------
def test_t_o1_al_1_insert_round_trip(store):
    rid = _row_id(store, SENTRY, "0x" + "a" * 64)
    assert rid > 0
    rows = store.get_operator_agent_activation_log(agent_id=SENTRY, limit=5)
    assert len(rows) == 1
    r = rows[0]
    assert r["agent_id"] == SENTRY
    assert r["to_scope_root"] == "0x" + "a" * 64
    assert r["to_phase"] == "O1_SHADOW"
    assert r["operational_tx_hash"] == "0xop"


# ----------------------------------------------------------------------
# T-O1-AL-2 — UNIQUE anti-replay
# ----------------------------------------------------------------------
def test_t_o1_al_2_unique_anti_replay(store):
    _row_id(store, SENTRY, "0x" + "a" * 64)
    with pytest.raises(sqlite3.IntegrityError, match="UNIQUE constraint failed"):
        _row_id(store, SENTRY, "0x" + "a" * 64)
    # Different to_scope_root for same agent → succeeds
    rid2 = _row_id(store, SENTRY, "0x" + "b" * 64)
    assert rid2 > 0


# ----------------------------------------------------------------------
# T-O1-AL-3 — get_current_operational_phase derivation
# ----------------------------------------------------------------------
def test_t_o1_al_3_current_phase_derivation(store):
    # Empty → O0_DORMANT
    assert store.get_current_operational_phase(SENTRY) == "O0_DORMANT"
    # After O1 activation
    _row_id(store, SENTRY, "0x" + "a" * 64, to_phase="O1_SHADOW")
    assert store.get_current_operational_phase(SENTRY) == "O1_SHADOW"
    # Insert later O2 → should override
    time.sleep(0.01)  # ensure activated_at differs
    _row_id(store, SENTRY, "0x" + "b" * 64, to_phase="O2_SUGGEST")
    assert store.get_current_operational_phase(SENTRY) == "O2_SUGGEST"


# ----------------------------------------------------------------------
# T-O1-AL-4 — pagination + agent_id filter
# ----------------------------------------------------------------------
def test_t_o1_al_4_pagination_and_filter(store):
    _row_id(store, SENTRY, "0x" + "1" * 64)
    _row_id(store, SENTRY, "0x" + "2" * 64)
    _row_id(store, GUARDIAN, "0x" + "3" * 64)
    # All agents
    all_rows = store.get_operator_agent_activation_log(agent_id=None, limit=10)
    assert len(all_rows) == 3
    # Sentry only
    sentry_only = store.get_operator_agent_activation_log(agent_id=SENTRY, limit=10)
    assert len(sentry_only) == 2
    assert all(r["agent_id"] == SENTRY for r in sentry_only)
    # Guardian only
    guard_only = store.get_operator_agent_activation_log(agent_id=GUARDIAN, limit=10)
    assert len(guard_only) == 1
    # Limit cap
    limited = store.get_operator_agent_activation_log(agent_id=None, limit=2)
    assert len(limited) == 2


# ----------------------------------------------------------------------
# T-O1-AL-5 — monotonicity (most-recent-first ordering)
# ----------------------------------------------------------------------
def test_t_o1_al_5_monotonicity(store):
    _row_id(store, SENTRY, "0x" + "1" * 64)
    time.sleep(0.01)
    _row_id(store, SENTRY, "0x" + "2" * 64)
    time.sleep(0.01)
    _row_id(store, SENTRY, "0x" + "3" * 64)
    rows = store.get_operator_agent_activation_log(agent_id=SENTRY, limit=10)
    # Most recent first
    assert rows[0]["to_scope_root"] == "0x" + "3" * 64
    assert rows[1]["to_scope_root"] == "0x" + "2" * 64
    assert rows[2]["to_scope_root"] == "0x" + "1" * 64
    # activated_at strictly increasing in original insertion order
    activated_descending = [r["activated_at"] for r in rows]
    assert activated_descending == sorted(activated_descending, reverse=True)
