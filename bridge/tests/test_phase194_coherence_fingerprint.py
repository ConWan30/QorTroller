"""
Phase 194 bridge tests — CoherenceFingerprintRegistry.

Tests (10 total):
  T194-1:  coherence_fingerprint_log table created in fresh DB
  T194-2:  on_chain_confirmed column added to fleet_coherence_log (idempotent ALTER)
  T194-3:  upsert_coherence_fingerprint inserts new row with occurrence_count=1
  T194-4:  upsert_coherence_fingerprint increments occurrence_count on second call
  T194-5:  persistent=1 when occurrence_count reaches N_PROMOTE_THRESHOLD (3)
  T194-6:  get_coherence_fingerprint_status returns correct counts and maturity_penalty
  T194-7:  maturity_penalty = min(1.0, persistent_count × 0.10)
  T194-8:  get_persistent_contradictions returns only persistent=1 rows
  T194-9:  GET /agent/coherence-fingerprint-status endpoint returns expected keys
  T194-10: _threat_forecast_accuracy_component penalises score by persistent contradictions
"""

from __future__ import annotations

import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from vapi_bridge.store import Store  # noqa: E402


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def tmp_store():
    # Use mkdtemp (not TemporaryDirectory) to avoid Windows WAL PermissionError
    d = tempfile.mkdtemp()
    s = Store(db_path=os.path.join(d, "test.db"))
    yield s


# ---------------------------------------------------------------------------
# T194-1: table created
# ---------------------------------------------------------------------------

def test_t194_1_fingerprint_table_created(tmp_store):
    """T194-1: coherence_fingerprint_log table exists in fresh DB."""
    import sqlite3
    with sqlite3.connect(tmp_store._db_path) as conn:
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name='coherence_fingerprint_log'"
        ).fetchall()
    assert len(rows) == 1, "coherence_fingerprint_log table not created"


# ---------------------------------------------------------------------------
# T194-2: on_chain_confirmed column exists in fleet_coherence_log
# ---------------------------------------------------------------------------

def test_t194_2_on_chain_confirmed_column(tmp_store):
    """T194-2: on_chain_confirmed column added to fleet_coherence_log."""
    import sqlite3
    with sqlite3.connect(tmp_store._db_path) as conn:
        cols = [r[1] for r in conn.execute(
            "PRAGMA table_info(fleet_coherence_log)"
        ).fetchall()]
    assert "on_chain_confirmed" in cols, (
        "on_chain_confirmed column missing from fleet_coherence_log"
    )


# ---------------------------------------------------------------------------
# T194-3: upsert inserts new row
# ---------------------------------------------------------------------------

def test_t194_3_upsert_inserts(tmp_store):
    """T194-3: upsert_coherence_fingerprint inserts with occurrence_count=1."""
    tmp_store.upsert_coherence_fingerprint("RENEWAL_WITHOUT_ATTESTATION", "CONTRADICTION")
    status = tmp_store.get_coherence_fingerprint_status()
    assert status["total_rules"] == 1
    assert status["total_occurrences"] == 1
    assert status["top_rules"][0]["rule_name"] == "RENEWAL_WITHOUT_ATTESTATION"
    assert status["top_rules"][0]["occurrence_count"] == 1


# ---------------------------------------------------------------------------
# T194-4: upsert increments occurrence_count
# ---------------------------------------------------------------------------

def test_t194_4_upsert_increments(tmp_store):
    """T194-4: second upsert call increments occurrence_count to 2."""
    tmp_store.upsert_coherence_fingerprint("TTL_COMMITTED_AT_MISMATCH", "CONTRADICTION")
    tmp_store.upsert_coherence_fingerprint("TTL_COMMITTED_AT_MISMATCH", "CONTRADICTION")
    status = tmp_store.get_coherence_fingerprint_status()
    assert status["total_occurrences"] == 2
    assert status["top_rules"][0]["occurrence_count"] == 2


# ---------------------------------------------------------------------------
# T194-5: persistent=1 at N_PROMOTE_THRESHOLD
# ---------------------------------------------------------------------------

def test_t194_5_persistent_at_threshold(tmp_store):
    """T194-5: persistent=1 set when occurrence_count reaches 3."""
    for _ in range(3):
        tmp_store.upsert_coherence_fingerprint("DEFENSIBILITY_N_MISMATCH", "CONTRADICTION")
    status = tmp_store.get_coherence_fingerprint_status()
    assert status["persistent_count"] == 1
    row = status["top_rules"][0]
    assert row["persistent"] == 1
    assert row["occurrence_count"] == 3


# ---------------------------------------------------------------------------
# T194-6: get_coherence_fingerprint_status returns correct counts
# ---------------------------------------------------------------------------

def test_t194_6_fingerprint_status_counts(tmp_store):
    """T194-6: status counts total_rules, persistent_count, total_occurrences correctly."""
    # Two rules: one persistent, one not
    for _ in range(3):
        tmp_store.upsert_coherence_fingerprint("RULE_A", "CONTRADICTION")
    tmp_store.upsert_coherence_fingerprint("RULE_B", "ORPHAN")

    status = tmp_store.get_coherence_fingerprint_status()
    assert status["total_rules"] == 2
    assert status["persistent_count"] == 1
    assert status["total_occurrences"] == 4


# ---------------------------------------------------------------------------
# T194-7: maturity_penalty formula
# ---------------------------------------------------------------------------

def test_t194_7_maturity_penalty_formula(tmp_store):
    """T194-7: maturity_penalty = min(1.0, persistent_count × 0.10)."""
    # 5 persistent rules → penalty = 0.50
    for i in range(5):
        for _ in range(3):
            tmp_store.upsert_coherence_fingerprint(f"RULE_{i}", "CONTRADICTION")

    status = tmp_store.get_coherence_fingerprint_status()
    assert status["persistent_count"] == 5
    assert abs(status["maturity_penalty"] - 0.50) < 0.001


# ---------------------------------------------------------------------------
# T194-8: get_persistent_contradictions
# ---------------------------------------------------------------------------

def test_t194_8_get_persistent_contradictions(tmp_store):
    """T194-8: get_persistent_contradictions returns only persistent=1 rows."""
    # 1 persistent, 1 non-persistent
    for _ in range(3):
        tmp_store.upsert_coherence_fingerprint("PERSISTENT_RULE", "INVERSION")
    tmp_store.upsert_coherence_fingerprint("NON_PERSISTENT_RULE", "ORPHAN")

    result = tmp_store.get_persistent_contradictions()
    assert len(result) == 1
    assert result[0]["rule_name"] == "PERSISTENT_RULE"
    assert result[0]["failure_mode"] == "INVERSION"


# ---------------------------------------------------------------------------
# T194-9: GET /agent/coherence-fingerprint-status endpoint
# ---------------------------------------------------------------------------

def test_t194_9_endpoint_returns_keys(tmp_store):
    """T194-9: GET /agent/coherence-fingerprint-status returns all required keys."""
    from unittest.mock import MagicMock
    from fastapi.testclient import TestClient
    from vapi_bridge.operator_api import create_operator_app

    cfg_mock = MagicMock()
    cfg_mock.operator_api_key = ""
    cfg_mock.rate_limit_rpm = 10000
    cfg_mock.fleet_coherence_enabled = True

    app = create_operator_app(cfg_mock, tmp_store)
    client = TestClient(app)

    resp = client.get("/agent/coherence-fingerprint-status")
    assert resp.status_code == 200
    body = resp.json()
    required = [
        "total_rules", "persistent_count", "total_occurrences",
        "maturity_penalty", "top_rules", "n_promote_threshold", "timestamp",
    ]
    for key in required:
        assert key in body, f"Missing key in response: {key}"
    assert body["n_promote_threshold"] == 3


# ---------------------------------------------------------------------------
# T194-10: threat_forecast_accuracy_component penalises by persistent count
# ---------------------------------------------------------------------------

def test_t194_10_maturity_penalty_applied(tmp_store):
    """T194-10: _threat_forecast_accuracy_component reduces score by persistent contradictions."""
    import logging
    from unittest.mock import MagicMock, patch

    from vapi_bridge.protocol_maturity_scoring_agent import ProtocolMaturityScoringAgent

    cfg_mock = MagicMock()
    cfg_mock.protocol_maturity_enabled = True

    agent = ProtocolMaturityScoringAgent(cfg=cfg_mock, store=tmp_store)

    # Seed 2 persistent rules
    for i in range(2):
        for _ in range(3):
            tmp_store.upsert_coherence_fingerprint(f"TEST_RULE_{i}", "CONTRADICTION")

    # Patch PIR score to 1.0 so we can measure pure penalty
    with patch.object(tmp_store, "get_threat_forecast_accuracy", return_value=1.0):
        score = agent._threat_forecast_accuracy_component()

    # 2 persistent rules → penalty = 0.20 → 1.0 × (1 - 0.20) = 0.80
    assert abs(score - 0.80) < 0.001, f"Expected ~0.80, got {score}"
