"""Tests for Mythos-Spending-Log-Drift variant (2026-05-19).

T-MYTHOS-SLD-1  Healthy state (no spending events) yields 0 findings
T-MYTHOS-SLD-2  Missing table -> fail-open returns []
T-MYTHOS-SLD-3  DAILY_BUDGET_EXCEEDED fires CRITICAL when 24h sum > budget
T-MYTHOS-SLD-4  REFUSAL_BURST fires MEDIUM when > 5 refusals in last hour
T-MYTHOS-SLD-5  UNATTRIBUTED_CHAIN_TX fires HIGH when cost>0 but empty tx_hash
T-MYTHOS-SLD-6  SPENDING_WITHOUT_ACTIVATION fires HIGH when cross-table drift
T-MYTHOS-SLD-7  Coherence-id deterministic across runs
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


SENTRY_Q9 = "0xb21e1ec258d2d381c313f84944bd36fbc63badb2c9a24c2412212d3a27e3e42c"


def _make_db_with_schema():
    """Create a temp SQLite DB with the operator_agent_chain_spending_log +
    operator_agent_activation_log schemas matching production."""
    db_path = str(Path(tempfile.mkdtemp()) / "test_spending.db")
    con = sqlite3.connect(db_path)
    con.execute("""
        CREATE TABLE operator_agent_chain_spending_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            agent_id TEXT NOT NULL,
            draft_id INTEGER NOT NULL,
            action_name TEXT NOT NULL,
            cost_iotx REAL NOT NULL DEFAULT 0.0,
            tx_hash TEXT NOT NULL DEFAULT '',
            error TEXT,
            created_at REAL NOT NULL DEFAULT (unixepoch('now'))
        )
    """)
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
    con.commit()
    con.close()
    return db_path


def _seed_activation(db_path: str, agent_q9: str):
    con = sqlite3.connect(db_path)
    con.execute(
        "INSERT INTO operator_agent_activation_log "
        "(agent_id, from_phase, to_phase, activated_at) "
        "VALUES (?, 'O0_DORMANT', 'O3_ACTING', ?)",
        (agent_q9, time.time()),
    )
    con.commit()
    con.close()


# ----- T-MYTHOS-SLD-1 -----------------------------------------------------

def test_t_mythos_sld_1_healthy_no_findings():
    """Empty spending_log + populated activation_log -> 0 findings."""
    from vapi_bridge.mythos_variants import mythos_spending_log_drift
    db = _make_db_with_schema()
    _seed_activation(db, SENTRY_Q9)
    findings = asyncio.run(mythos_spending_log_drift(db_path=db))
    assert findings == []


# ----- T-MYTHOS-SLD-2 -----------------------------------------------------

def test_t_mythos_sld_2_missing_table_fail_open():
    """Missing spending_log table -> fail-open returns []."""
    from vapi_bridge.mythos_variants import mythos_spending_log_drift
    db_path = str(Path(tempfile.mkdtemp()) / "test_empty.db")
    # Create empty DB with no tables
    con = sqlite3.connect(db_path)
    con.close()
    findings = asyncio.run(mythos_spending_log_drift(db_path=db_path))
    assert findings == []


# ----- T-MYTHOS-SLD-3 -----------------------------------------------------

def test_t_mythos_sld_3_budget_exceeded_critical():
    """24h sum > budget fires CRITICAL."""
    from vapi_bridge.mythos_variants import mythos_spending_log_drift
    db = _make_db_with_schema()
    _seed_activation(db, SENTRY_Q9)
    con = sqlite3.connect(db)
    # Insert spending events totaling > 0.5 IOTX (Sentry default budget)
    # within last 24h
    for i in range(6):
        con.execute(
            "INSERT INTO operator_agent_chain_spending_log "
            "(agent_id, draft_id, action_name, cost_iotx, tx_hash, created_at) "
            "VALUES (?, ?, 'pda-attestation-anchor', 0.1, ?, ?)",
            (SENTRY_Q9, i, f"0x{i:064x}", time.time() - 100),
        )
    con.commit()
    con.close()

    findings = asyncio.run(mythos_spending_log_drift(db_path=db))
    crit = [f for f in findings if "DAILY_BUDGET_EXCEEDED" in f.description]
    assert len(crit) >= 1
    assert crit[0].severity == "CRITICAL"


# ----- T-MYTHOS-SLD-4 -----------------------------------------------------

def test_t_mythos_sld_4_refusal_burst_medium():
    """> 5 refusals (cost=0 + error) in last hour fires MEDIUM."""
    from vapi_bridge.mythos_variants import mythos_spending_log_drift
    db = _make_db_with_schema()
    _seed_activation(db, SENTRY_Q9)
    con = sqlite3.connect(db)
    for i in range(7):  # 7 refusals > threshold 5
        con.execute(
            "INSERT INTO operator_agent_chain_spending_log "
            "(agent_id, draft_id, action_name, cost_iotx, tx_hash, error, created_at) "
            "VALUES (?, ?, 'pda-attestation-anchor', 0.0, '', ?, ?)",
            (SENTRY_Q9, i, f"chain-side error iteration {i}", time.time() - 100),
        )
    con.commit()
    con.close()

    findings = asyncio.run(mythos_spending_log_drift(db_path=db))
    burst = [f for f in findings if "REFUSAL_BURST" in f.description]
    assert len(burst) >= 1
    assert burst[0].severity == "MEDIUM"


# ----- T-MYTHOS-SLD-5 -----------------------------------------------------

def test_t_mythos_sld_5_unattributed_tx_high():
    """cost_iotx > 0 + empty tx_hash fires HIGH."""
    from vapi_bridge.mythos_variants import mythos_spending_log_drift
    db = _make_db_with_schema()
    _seed_activation(db, SENTRY_Q9)
    con = sqlite3.connect(db)
    con.execute(
        "INSERT INTO operator_agent_chain_spending_log "
        "(agent_id, draft_id, action_name, cost_iotx, tx_hash, created_at) "
        "VALUES (?, 100, 'pda-attestation-anchor', 0.001, '', ?)",
        (SENTRY_Q9, time.time() - 100),
    )
    con.commit()
    con.close()

    findings = asyncio.run(mythos_spending_log_drift(db_path=db))
    unattr = [f for f in findings if "UNATTRIBUTED_CHAIN_TX" in f.description]
    assert len(unattr) >= 1
    assert unattr[0].severity == "HIGH"


# ----- T-MYTHOS-SLD-6 -----------------------------------------------------

def test_t_mythos_sld_6_spending_without_activation_high():
    """spending_log row for agent NOT in activation_log fires HIGH."""
    from vapi_bridge.mythos_variants import mythos_spending_log_drift
    db = _make_db_with_schema()
    # NOTE: do NOT seed activation_log — leave empty
    con = sqlite3.connect(db)
    con.execute(
        "INSERT INTO operator_agent_chain_spending_log "
        "(agent_id, draft_id, action_name, cost_iotx, tx_hash, created_at) "
        "VALUES (?, 1, 'pda-attestation-anchor', 0.001, '0xdeadbeef', ?)",
        (SENTRY_Q9, time.time() - 100),
    )
    con.commit()
    con.close()

    findings = asyncio.run(mythos_spending_log_drift(db_path=db))
    cross = [f for f in findings if "SPENDING_WITHOUT_ACTIVATION" in f.description]
    assert len(cross) >= 1
    assert cross[0].severity == "HIGH"


# ----- T-MYTHOS-SLD-7 -----------------------------------------------------

def test_t_mythos_sld_7_coherence_id_deterministic():
    """Same DB state -> identical coherence_ids across runs."""
    from vapi_bridge.mythos_variants import mythos_spending_log_drift
    db = _make_db_with_schema()
    _seed_activation(db, SENTRY_Q9)
    con = sqlite3.connect(db)
    con.execute(
        "INSERT INTO operator_agent_chain_spending_log "
        "(agent_id, draft_id, action_name, cost_iotx, tx_hash, created_at) "
        "VALUES (?, 200, 'pda-attestation-anchor', 0.001, '', ?)",
        (SENTRY_Q9, time.time() - 100),
    )
    con.commit()
    con.close()

    ids_a = sorted(f.coherence_id for f in asyncio.run(mythos_spending_log_drift(db_path=db)))
    ids_b = sorted(f.coherence_id for f in asyncio.run(mythos_spending_log_drift(db_path=db)))
    assert ids_a == ids_b
    assert all(cid.startswith("mythos_spending_log_drift_") for cid in ids_a)
