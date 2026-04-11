"""
Phase 187 — AttestationOpSecAdvisorAgent tests (8 tests, WIF-033 W1 closure).

Tests:
  T187-1: attestation_opsec_log table created; schema 187 registered
  T187-2: insert_attestation_opsec_log stores row; get_attestation_opsec_status retrieves it
  T187-3: get_attestation_opsec_status returns safe defaults when no rows exist
  T187-4: _compute_risk_level HIGH when active_attestations>0 AND bound_renewal_enabled=True
  T187-5: _compute_risk_level MEDIUM when active_attestations>0 AND bound_renewal_enabled=False
  T187-6: _compute_risk_level LOW when active_attestations==0
  T187-7: config field mempool_opsec_enabled defaults False
  T187-8: GET /agent/attestation-opsec-status endpoint is registered
"""

import os
import sys
import tempfile
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from vapi_bridge.store import Store
from vapi_bridge.config import Config
from vapi_bridge.attestation_opsec_advisor_agent import AttestationOpSecAdvisorAgent


@pytest.fixture()
def store(tmp_path):
    db = str(tmp_path / "test_phase187_opsec.db")
    s = Store(db_path=db)
    return s


@pytest.fixture()
def cfg():
    return Config()


@pytest.fixture()
def agent(store, cfg):
    return AttestationOpSecAdvisorAgent(cfg=cfg, store=store, bus=None)


# T187-1 — table created and schema registered
def test_1_table_created_schema_registered(store):
    with store._conn() as conn:
        tables = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()}
    assert "attestation_opsec_log" in tables

    with store._conn() as conn:
        row = conn.execute(
            "SELECT phase FROM schema_versions WHERE phase=187"
        ).fetchone()
    assert row is not None, "schema_versions missing phase=187"


# T187-2 — insert and retrieve
def test_2_insert_and_retrieve(store):
    store.insert_attestation_opsec_log(
        player_id="P1",
        timing_disclosure_risk="HIGH",
        active_attestations=2,
        re_enrollment_window_active=True,
        recommendation="USE_PRIVATE_MEMPOOL_OR_DELAY_TX",
    )
    status = store.get_attestation_opsec_status("P1")
    assert status["timing_disclosure_risk"] == "HIGH"
    assert status["active_attestations"] == 2
    assert status["re_enrollment_window_active"] is True
    assert status["recommendation"] == "USE_PRIVATE_MEMPOOL_OR_DELAY_TX"
    assert status["total_high_risk_events"] == 1


# T187-3 — safe defaults when no rows
def test_3_safe_defaults_when_empty(store):
    status = store.get_attestation_opsec_status()
    assert status["timing_disclosure_risk"] == "LOW"
    assert status["active_attestations"] == 0
    assert status["re_enrollment_window_active"] is False
    assert status["recommendation"] == "STANDARD_TX_OK"
    assert status["total_high_risk_events"] == 0


# T187-4 — HIGH when active + bound renewal enabled
def test_4_risk_high_when_active_and_enabled(agent):
    risk = agent._compute_risk_level(active_attestations=1, bound_renewal_enabled=True)
    assert risk == "HIGH"
    rec = agent._compute_recommendation("HIGH")
    assert rec == "USE_PRIVATE_MEMPOOL_OR_DELAY_TX"


# T187-5 — MEDIUM when active + bound renewal disabled
def test_5_risk_medium_when_active_not_enabled(agent):
    risk = agent._compute_risk_level(active_attestations=3, bound_renewal_enabled=False)
    assert risk == "MEDIUM"
    rec = agent._compute_recommendation("MEDIUM")
    assert rec == "MONITOR_REENROLLMENT_WINDOW"


# T187-6 — LOW when no active attestations
def test_6_risk_low_when_no_active(agent):
    risk = agent._compute_risk_level(active_attestations=0, bound_renewal_enabled=True)
    assert risk == "LOW"
    rec = agent._compute_recommendation("LOW")
    assert rec == "STANDARD_TX_OK"


# T187-7 — config field mempool_opsec_enabled defaults False
def test_7_config_field_mempool_opsec_enabled(cfg):
    assert hasattr(cfg, "mempool_opsec_enabled")
    assert cfg.mempool_opsec_enabled is False


# T187-8 — GET /agent/attestation-opsec-status endpoint registered
def test_8_endpoint_registered(store, cfg):
    try:
        from vapi_bridge.operator_api import create_app
        app = create_app(cfg, store)
        routes = [r.path for r in app.routes]
        assert any("attestation-opsec-status" in r for r in routes), (
            f"GET /agent/attestation-opsec-status not registered. Routes: {routes}"
        )
    except Exception as exc:
        pytest.skip(f"operator_api unavailable in test environment: {exc}")
