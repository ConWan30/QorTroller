"""Tests for 2026-05-19 Gap 1 + Gap 2 closures.

Gap 1 — Guardian local-write authority functional through executor:
  T-GAP1-1  evaluate_live_write_authorization_for_agent permits budget=0 + cost=0
  T-GAP1-2  budget=0 + cost>0 still blocked with original blocker
  T-GAP1-3  _estimate_cost_iotx returns 0.0 for audit-drafting
  T-GAP1-4  _exec_guardian_audit_draft returns synthetic local: tx_hash + cost=0

Gap 2 — Curator graduation audit:
  T-GAP2-1  mythos_curator_graduation_audit fires DIRECT_O3_BYPASS_DOCUMENTED when curator at O3
  T-GAP2-2  GRADUATION_PENDING fires when N < 50 reviews
  T-GAP2-3  GRADUATION_BACKFILLED fires when N >= 50 reviews
  T-GAP2-4  variant returns [] when curator NOT at O3 (nothing to audit)
  T-GAP2-5  missing tables -> fail-open returns []
"""
import asyncio
import sqlite3
import sys
import tempfile
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "bridge"))


CURATOR_Q9 = "0xed6a2df58e5ec50c1f88e127f6982a348f6855202b662b8ad73ffa1c1fda11a8"
GUARDIAN_Q9 = "0xbd8c7fba08815b7ed343973c9c7300c062303b1acd19e8d9847a953ce5fa38d1"


def _make_db_with_full_schema():
    """Create temp DB with activation_log + spending_log + curator_review schemas."""
    db_path = str(Path(tempfile.mkdtemp()) / "test_gap.db")
    con = sqlite3.connect(db_path)
    con.execute("""
        CREATE TABLE operator_agent_activation_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            agent_id TEXT NOT NULL,
            from_phase TEXT, to_phase TEXT,
            from_scope_root TEXT, to_scope_root TEXT,
            bundle_path TEXT,
            governance_tx_hash TEXT, operational_tx_hash TEXT,
            governance_block_number INTEGER, operational_block_number INTEGER,
            operator_authority_hash TEXT, reason_text TEXT,
            activated_at REAL
        )
    """)
    con.execute("""
        CREATE TABLE operator_agent_chain_spending_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            agent_id TEXT NOT NULL, draft_id INTEGER NOT NULL,
            action_name TEXT NOT NULL, cost_iotx REAL NOT NULL DEFAULT 0.0,
            tx_hash TEXT NOT NULL DEFAULT '', error TEXT,
            created_at REAL NOT NULL DEFAULT (unixepoch('now'))
        )
    """)
    con.execute("""
        CREATE TABLE curator_listing_review_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            listing_commitment TEXT NOT NULL,
            verdict TEXT NOT NULL,
            severity TEXT NOT NULL,
            shadow_mode INTEGER NOT NULL DEFAULT 1,
            ts_ns INTEGER NOT NULL,
            created_at REAL NOT NULL
        )
    """)
    con.commit()
    con.close()
    return db_path


def _seed_o3_activation(db_path: str, agent_q9: str):
    con = sqlite3.connect(db_path)
    con.execute(
        "INSERT INTO operator_agent_activation_log "
        "(agent_id, from_phase, to_phase, activated_at) "
        "VALUES (?, 'PRE_O1_UNKNOWN', 'O3_ACTING', ?)",
        (agent_q9, time.time()),
    )
    con.commit()
    con.close()


# ============================================================
# Gap 1 tests
# ============================================================

def test_t_gap1_1_auth_permits_budget_zero_cost_zero():
    """Guardian's auth (budget=0, cost=0) MUST be PERMITTED post-fix.

    This is the load-bearing Gap 1 closure: L38 NOTE intent for Guardian
    local writes through the executor."""
    from vapi_bridge.operator_initiative_live_write_executor import (
        evaluate_live_write_authorization_for_agent,
    )

    db = _make_db_with_full_schema()
    _seed_o3_activation(db, GUARDIAN_Q9)

    class _Cfg:
        phase_o3_executor_kill_all = False
        phase_o3_anchor_sentry_live_writes_enabled = False
        phase_o3_guardian_live_writes_enabled = True
        phase_o3_curator_live_writes_enabled = False
        phase_o3_anchor_sentry_daily_iotx_budget = 0.05
        phase_o3_guardian_daily_iotx_budget = 0.0
        phase_o3_curator_daily_iotx_budget = 0.05
        operator_agent_anchor_sentry_id = "0x" + "0" * 64
        operator_agent_guardian_id = GUARDIAN_Q9
        operator_agent_curator_id = "0x" + "0" * 64

    from vapi_bridge.store import Store
    store = Store(db)

    auth = evaluate_live_write_authorization_for_agent(
        agent_id="guardian", cfg=_Cfg(), store=store,
        intended_cost_iotx=0.0,
    )
    assert auth.authorized is True, \
        f"Guardian cost=0 should be authorized post-Gap-1; blockers={list(auth.blockers)}"
    assert auth.blockers == ()


def test_t_gap1_2_auth_blocks_budget_zero_cost_positive():
    """Guardian (budget=0) + cost > 0 still blocked — chain ops require positive budget."""
    from vapi_bridge.operator_initiative_live_write_executor import (
        evaluate_live_write_authorization_for_agent,
    )

    db = _make_db_with_full_schema()
    _seed_o3_activation(db, GUARDIAN_Q9)

    class _Cfg:
        phase_o3_executor_kill_all = False
        phase_o3_anchor_sentry_live_writes_enabled = False
        phase_o3_guardian_live_writes_enabled = True
        phase_o3_curator_live_writes_enabled = False
        phase_o3_anchor_sentry_daily_iotx_budget = 0.05
        phase_o3_guardian_daily_iotx_budget = 0.0
        phase_o3_curator_daily_iotx_budget = 0.05
        operator_agent_anchor_sentry_id = "0x" + "0" * 64
        operator_agent_guardian_id = GUARDIAN_Q9
        operator_agent_curator_id = "0x" + "0" * 64

    from vapi_bridge.store import Store
    store = Store(db)

    auth = evaluate_live_write_authorization_for_agent(
        agent_id="guardian", cfg=_Cfg(), store=store,
        intended_cost_iotx=0.001,  # hypothetical chain op
    )
    assert auth.authorized is False
    assert any("daily_budget_zero_no_chain_ops_permitted" in b for b in auth.blockers), \
        f"Expected daily_budget_zero blocker; got {list(auth.blockers)}"


def test_t_gap1_3_audit_drafting_cost_is_zero():
    """_estimate_cost_iotx returns 0.0 for audit-drafting (local action; no chain cost)."""
    from vapi_bridge.operator_initiative_live_write_executor import (
        OperatorAgentLiveWriteExecutor,
    )
    cost = OperatorAgentLiveWriteExecutor._estimate_cost_iotx("audit-drafting")
    assert cost == 0.0
    # Other known actions unchanged
    assert OperatorAgentLiveWriteExecutor._estimate_cost_iotx("pda-attestation-anchor") == 0.001
    assert OperatorAgentLiveWriteExecutor._estimate_cost_iotx("marketplace-listing-suspend") == 0.002


def test_t_gap1_4_exec_guardian_audit_draft_returns_local_tx():
    """_exec_guardian_audit_draft returns synthetic local: tx_hash + cost=0."""
    from unittest.mock import MagicMock
    from vapi_bridge.operator_initiative_live_write_executor import (
        OperatorAgentLiveWriteExecutor,
    )

    executor = OperatorAgentLiveWriteExecutor(
        cfg=MagicMock(), store=MagicMock(), chain=MagicMock(),
    )
    draft = {"id": 42, "payload_bytes_decoded": "{}"}
    tx_hash, cost = asyncio.run(executor._exec_guardian_audit_draft(draft))
    assert tx_hash == "local:audit:42"
    assert cost == 0.0


# ============================================================
# Gap 2 tests
# ============================================================

def test_t_gap2_1_direct_o3_bypass_documented():
    """Curator at O3_ACTING fires CURATOR_DIRECT_O3_BYPASS_DOCUMENTED."""
    from vapi_bridge.mythos_variants import mythos_curator_graduation_audit
    db = _make_db_with_full_schema()
    _seed_o3_activation(db, CURATOR_Q9)
    findings = asyncio.run(mythos_curator_graduation_audit(db_path=db))
    bypasses = [f for f in findings if "DIRECT_O3_BYPASS_DOCUMENTED" in f.description]
    assert len(bypasses) >= 1
    assert bypasses[0].severity == "LOW"


def test_t_gap2_2_graduation_pending_when_no_reviews():
    """N=0 reviews fires CURATOR_GRADUATION_PENDING."""
    from vapi_bridge.mythos_variants import mythos_curator_graduation_audit
    db = _make_db_with_full_schema()
    _seed_o3_activation(db, CURATOR_Q9)
    findings = asyncio.run(mythos_curator_graduation_audit(db_path=db))
    pending = [f for f in findings if "GRADUATION_PENDING" in f.description]
    assert len(pending) >= 1
    assert "N=0 reviews" in pending[0].description


def test_t_gap2_3_graduation_backfilled_when_n_above_50():
    """N >= 50 reviews fires CURATOR_GRADUATION_BACKFILLED."""
    from vapi_bridge.mythos_variants import mythos_curator_graduation_audit
    db = _make_db_with_full_schema()
    _seed_o3_activation(db, CURATOR_Q9)
    # Seed 55 reviews
    con = sqlite3.connect(db)
    for i in range(55):
        con.execute(
            "INSERT INTO curator_listing_review_log "
            "(listing_commitment, verdict, severity, ts_ns, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (f"0x{i:064x}", "CERTIFY", "INFO", i * 1_000_000_000, time.time()),
        )
    con.commit()
    con.close()
    findings = asyncio.run(mythos_curator_graduation_audit(db_path=db))
    backfilled = [f for f in findings if "GRADUATION_BACKFILLED" in f.description]
    assert len(backfilled) >= 1
    assert "N=55" in backfilled[0].description


def test_t_gap2_4_no_findings_when_curator_not_at_o3():
    """Variant returns [] when curator NOT at O3_ACTING (nothing to audit)."""
    from vapi_bridge.mythos_variants import mythos_curator_graduation_audit
    db = _make_db_with_full_schema()
    # Seed Curator at O1_SHADOW instead of O3_ACTING
    con = sqlite3.connect(db)
    con.execute(
        "INSERT INTO operator_agent_activation_log "
        "(agent_id, from_phase, to_phase, activated_at) "
        "VALUES (?, 'O0_DORMANT', 'O1_SHADOW', ?)",
        (CURATOR_Q9, time.time()),
    )
    con.commit()
    con.close()
    findings = asyncio.run(mythos_curator_graduation_audit(db_path=db))
    assert findings == []


def test_t_gap2_5_missing_tables_fail_open():
    """Missing tables -> fail-open returns []."""
    from vapi_bridge.mythos_variants import mythos_curator_graduation_audit
    db_path = str(Path(tempfile.mkdtemp()) / "empty.db")
    con = sqlite3.connect(db_path)
    con.close()  # empty DB, no tables
    findings = asyncio.run(mythos_curator_graduation_audit(db_path=db_path))
    assert findings == []
