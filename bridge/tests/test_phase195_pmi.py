"""
Phase 195 — Protocol Metabolism Index (PMI) tests.

PMI = max(0.0, 1.0 - mean_orphan_resolution_hours / 48.0)
Feeds as pmi_component (weight=0.03) into ProtocolMaturityScoringAgent.
"""
import sys
import tempfile
import time
import os
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "bridge"))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_store():
    from vapi_bridge.store import Store
    d = tempfile.mkdtemp()
    return Store(os.path.join(d, "test195.db"))


def _insert_orphan(store, created_at: str, resolved_at: str | None = None,
                   rule_name: str = "ORPHAN_TEST_RULE"):
    """Insert a synthetic ORPHAN entry into fleet_coherence_log."""
    import sqlite3
    with sqlite3.connect(store._db_path) as conn:
        conn.execute(
            "INSERT INTO fleet_coherence_log "
            "(coherence_id, rule_name, failure_mode, severity, agents_involved, "
            "explanation, resolution, evidence_json, resolved_at, on_chain_confirmed, created_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (
                f"coh_t195_{int(time.time_ns() % 10_000_000_000):016x}",
                rule_name,
                "ORPHAN",
                "MEDIUM",
                "[]",
                "test orphan explanation",
                "none",
                "{}",
                resolved_at,
                0,
                created_at,
            ),
        )
        conn.commit()


# ---------------------------------------------------------------------------
# T195-1: empty fleet_coherence_log → pmi_score=1.0 (no orphans ever)
# ---------------------------------------------------------------------------

def test_t195_1_empty_table_pmi_is_1():
    store = _make_store()
    stats = store.get_orphan_resolution_stats()
    assert stats["pmi_score"] == 1.0
    assert stats["mean_resolution_hours"] == 0.0
    assert stats["orphan_count_resolved"] == 0
    assert stats["orphan_count_open"] == 0


# ---------------------------------------------------------------------------
# T195-2: open orphans (unresolved) do not affect PMI score
# ---------------------------------------------------------------------------

def test_t195_2_open_orphans_pmi_still_1():
    store = _make_store()
    _insert_orphan(store, created_at="2026-04-11T10:00:00", resolved_at=None)
    _insert_orphan(store, created_at="2026-04-11T11:00:00", resolved_at=None)
    stats = store.get_orphan_resolution_stats()
    # Open orphans don't contribute to mean — no resolved rows
    assert stats["pmi_score"] == 1.0
    assert stats["orphan_count_open"] == 2
    assert stats["orphan_count_resolved"] == 0


# ---------------------------------------------------------------------------
# T195-3: fast resolution (< 48h) yields high PMI score
# ---------------------------------------------------------------------------

def test_t195_3_fast_resolution_high_pmi():
    store = _make_store()
    # 12h resolution → PMI = 1 - 12/48 = 0.75
    _insert_orphan(store, "2026-04-11T00:00:00", "2026-04-11T12:00:00")
    stats = store.get_orphan_resolution_stats()
    assert abs(stats["pmi_score"] - 0.75) < 0.001
    assert abs(stats["mean_resolution_hours"] - 12.0) < 0.01
    assert stats["orphan_count_resolved"] == 1


# ---------------------------------------------------------------------------
# T195-4: slow resolution (>= 48h) yields PMI=0.0
# ---------------------------------------------------------------------------

def test_t195_4_slow_resolution_pmi_zero():
    store = _make_store()
    # 96h resolution → PMI = max(0, 1 - 96/48) = max(0, -1) = 0.0
    _insert_orphan(store, "2026-04-09T00:00:00", "2026-04-11T00:00:00")
    stats = store.get_orphan_resolution_stats()
    assert stats["pmi_score"] == 0.0
    assert stats["mean_resolution_hours"] >= 48.0


# ---------------------------------------------------------------------------
# T195-5: domain filter narrows query
# ---------------------------------------------------------------------------

def test_t195_5_domain_filter():
    store = _make_store()
    # 6h resolution for ORPHAN_TEST_RULE → PMI = 1 - 6/48 = 0.875
    _insert_orphan(store, "2026-04-11T00:00:00", "2026-04-11T06:00:00")
    # Add unrelated ORPHAN with different rule (insert directly)
    _insert_orphan(store, created_at="2026-04-08T00:00:00",
                   resolved_at="2026-04-09T00:00:00", rule_name="OTHER_RULE")
    # Filter to just ORPHAN_TEST_RULE
    stats = store.get_orphan_resolution_stats(domain="ORPHAN_TEST")
    assert abs(stats["pmi_score"] - 0.875) < 0.001
    assert stats["orphan_count_resolved"] == 1
    # Without filter — both rows counted
    stats_all = store.get_orphan_resolution_stats()
    assert stats_all["orphan_count_resolved"] == 2


# ---------------------------------------------------------------------------
# T195-6: insert_protocol_maturity_log persists pmi_component
# ---------------------------------------------------------------------------

def test_t195_6_insert_maturity_log_pmi_column():
    store = _make_store()
    row_id = store.insert_protocol_maturity_log(
        separation_component=0.9,
        chain_integrity_component=1.0,
        consent_component=1.0,
        biometric_freshness_component=0.8,
        agent_calibration_component=0.9,
        enrollment_component=1.0,
        threat_forecast_accuracy_component=0.8,
        biometric_stationarity_component=0.7,
        pmi_component=0.75,
    )
    assert row_id is not None
    rows = store.get_protocol_maturity_status(limit=1)
    assert len(rows) == 1
    assert abs(rows[0]["pmi_component"] - 0.75) < 0.001


# ---------------------------------------------------------------------------
# T195-7: maturity score formula includes pmi weight=0.03
# ---------------------------------------------------------------------------

def test_t195_7_maturity_score_includes_pmi():
    store = _make_store()
    # All ones except pmi_component=0.0
    store.insert_protocol_maturity_log(
        separation_component=1.0,
        chain_integrity_component=1.0,
        consent_component=1.0,
        biometric_freshness_component=1.0,
        agent_calibration_component=1.0,
        enrollment_component=1.0,
        threat_forecast_accuracy_component=1.0,
        biometric_stationarity_component=1.0,
        pmi_component=0.0,
    )
    rows = store.get_protocol_maturity_status(limit=1)
    # Expected: 0.18+0.20+0.15+0.11+0.12+0.10+0.07+0.04+0.0*0.03 = 0.97
    assert abs(rows[0]["maturity_score"] - 0.97) < 0.001


# ---------------------------------------------------------------------------
# T195-8: all ones → score=1.0 (PRODUCTION_CANDIDATE)
# ---------------------------------------------------------------------------

def test_t195_8_all_ones_production_candidate():
    store = _make_store()
    store.insert_protocol_maturity_log(
        separation_component=1.0,
        chain_integrity_component=1.0,
        consent_component=1.0,
        biometric_freshness_component=1.0,
        agent_calibration_component=1.0,
        enrollment_component=1.0,
        threat_forecast_accuracy_component=1.0,
        biometric_stationarity_component=1.0,
        pmi_component=1.0,
    )
    rows = store.get_protocol_maturity_status(limit=1)
    assert rows[0]["maturity_score"] == 1.0
    assert rows[0]["maturity_tier"] == "PRODUCTION_CANDIDATE"
    assert abs(rows[0]["pmi_component"] - 1.0) < 0.001
