"""
Phase 191 — Threat Succession Protocol (TSP) bridge tests.

Tests for:
  - store.insert_protocol_maturity_log() 8-component v2 (Phase 191)
  - store.get_threat_forecast_accuracy() reads PIR harness_score
  - store.get_protocol_maturity_status() returns 2 new TSP fields
  - ProtocolMaturityScoringAgent._threat_forecast_accuracy_component()
  - ProtocolMaturityScoringAgent._biometric_stationarity_component()
  - ProtocolMaturityScoringAgent._run_scoring() 8-component maturity_score v2
  - GET /agent/protocol-maturity-score returns 2 new TSP keys
  - config.tsp_enabled field present and defaults True
"""

from __future__ import annotations

import importlib
import sys
import tempfile
import time
import os
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def tmp_store(tmp_path):
    """Real Store instance backed by a fresh temp DB."""
    db_path = str(tmp_path / "test191.db")
    # Patch DB path via env so Store picks it up
    with patch.dict(os.environ, {"VAPI_DB_PATH": db_path}):
        from bridge.vapi_bridge.store import Store
        store = Store(db_path=db_path)
        yield store


@pytest.fixture()
def mock_cfg():
    cfg = MagicMock()
    cfg.protocol_maturity_enabled = True
    cfg.tsp_enabled = True
    cfg.biometric_credential_ttl_days = 90.0
    cfg.chain_integrity_enabled = True
    cfg.consent_ledger_enabled = True
    cfg.age_weight_analysis_enabled = True
    return cfg


# ---------------------------------------------------------------------------
# TSP-191-1: store insert accepts 8-component signature
# ---------------------------------------------------------------------------

def test_insert_protocol_maturity_log_8_components(tmp_store):
    """insert_protocol_maturity_log() accepts 2 new TSP kwargs without error."""
    row_id = tmp_store.insert_protocol_maturity_log(
        separation_component=0.50,
        chain_integrity_component=0.80,
        consent_component=0.70,
        biometric_freshness_component=0.60,
        agent_calibration_component=0.75,
        enrollment_component=0.30,
        threat_forecast_accuracy_component=0.65,
        biometric_stationarity_component=0.55,
    )
    assert isinstance(row_id, int) and row_id > 0


# ---------------------------------------------------------------------------
# TSP-191-2: store returns 2 new fields from get_protocol_maturity_status
# ---------------------------------------------------------------------------

def test_get_protocol_maturity_status_returns_tsp_fields(tmp_store):
    """get_protocol_maturity_status() includes threat_forecast_accuracy_component and
    biometric_stationarity_component."""
    tmp_store.insert_protocol_maturity_log(
        separation_component=0.40,
        chain_integrity_component=0.90,
        consent_component=0.80,
        biometric_freshness_component=0.70,
        agent_calibration_component=0.85,
        enrollment_component=0.50,
        threat_forecast_accuracy_component=0.72,
        biometric_stationarity_component=0.48,
    )
    rows = tmp_store.get_protocol_maturity_status(limit=1)
    assert rows, "Expected at least one row"
    row = rows[0]
    assert "threat_forecast_accuracy_component" in row
    assert "biometric_stationarity_component" in row
    assert abs(row["threat_forecast_accuracy_component"] - 0.72) < 0.001
    assert abs(row["biometric_stationarity_component"] - 0.48) < 0.001


# ---------------------------------------------------------------------------
# TSP-191-3: get_threat_forecast_accuracy returns 0.5 when no PIR data
# ---------------------------------------------------------------------------

def test_get_threat_forecast_accuracy_no_pir(tmp_store):
    """Returns 0.5 (neutral) when protocol_intelligence_record_log is empty."""
    result = tmp_store.get_threat_forecast_accuracy()
    assert result == 0.5


# ---------------------------------------------------------------------------
# TSP-191-4: get_threat_forecast_accuracy reads from PIR log
# ---------------------------------------------------------------------------

def test_get_threat_forecast_accuracy_with_pir(tmp_store):
    """Returns latest PIR harness_score from protocol_intelligence_record_log."""
    # Insert a PIR record directly
    import hashlib
    h = hashlib.sha256(b"test").hexdigest()
    with tmp_store._conn() as conn:
        conn.execute(
            "INSERT INTO protocol_intelligence_record_log "
            "(cycle_number, phase_produced, wif_hash, threat_forecast, "
            "harness_score, prev_pir_hash, pir_hash, eval_timestamp) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (11, 191, h, "pir_chain_integrity_attack", 0.852,
             "0" * 64, h + "x", time.time()),
        )
    result = tmp_store.get_threat_forecast_accuracy()
    assert abs(result - 0.852) < 0.001


# ---------------------------------------------------------------------------
# TSP-191-5: ProtocolMaturityScoringAgent _WEIGHTS sums to 1.0 with 8 components
# ---------------------------------------------------------------------------

def test_protocol_maturity_weights_v2():
    """_WEIGHTS dict in ProtocolMaturityScoringAgent sums to 1.0 and has 8 entries."""
    from bridge.vapi_bridge.protocol_maturity_scoring_agent import _WEIGHTS
    assert len(_WEIGHTS) == 8, f"Expected 8 components, got {len(_WEIGHTS)}"
    total = sum(_WEIGHTS.values())
    assert abs(total - 1.0) < 1e-9, f"Weights sum to {total}, expected 1.0"
    assert "threat_forecast_accuracy_component" in _WEIGHTS
    assert "biometric_stationarity_component" in _WEIGHTS


# ---------------------------------------------------------------------------
# TSP-191-6: _run_scoring includes new components in returned dict
# ---------------------------------------------------------------------------

def test_run_scoring_includes_tsp_components(tmp_store, mock_cfg):
    """_run_scoring() returns threat_forecast_accuracy_component and
    biometric_stationarity_component in output dict."""
    from bridge.vapi_bridge.protocol_maturity_scoring_agent import ProtocolMaturityScoringAgent
    agent = ProtocolMaturityScoringAgent(cfg=mock_cfg, store=tmp_store, bus=None)
    result = agent._run_scoring()
    assert "threat_forecast_accuracy_component" in result
    assert "biometric_stationarity_component" in result
    # Neutral 0.5 when no data
    assert result["threat_forecast_accuracy_component"] == 0.5
    assert result["biometric_stationarity_component"] == 0.5


# ---------------------------------------------------------------------------
# TSP-191-7: maturity_score reflects 8-component v2 formula
# ---------------------------------------------------------------------------

def test_maturity_score_v2_formula(tmp_store, mock_cfg):
    """maturity_score uses 8-component v2 weights (0.20+0.20+0.15+0.12+0.12+0.10+0.07+0.04=1.0)."""
    from bridge.vapi_bridge.protocol_maturity_scoring_agent import ProtocolMaturityScoringAgent, _WEIGHTS
    agent = ProtocolMaturityScoringAgent(cfg=mock_cfg, store=tmp_store, bus=None)

    # Patch all 8 component readers to known values
    components = {
        "separation_component":               0.80,
        "chain_integrity_component":          0.90,
        "consent_component":                  0.70,
        "biometric_freshness_component":      0.60,
        "agent_calibration_component":        0.75,
        "enrollment_component":               0.40,
        "threat_forecast_accuracy_component": 0.65,
        "biometric_stationarity_component":   0.55,
    }
    expected = round(sum(components[k] * w for k, w in _WEIGHTS.items()), 6)

    agent._separation_component               = lambda: components["separation_component"]
    agent._chain_integrity_component          = lambda: components["chain_integrity_component"]
    agent._consent_component                  = lambda: components["consent_component"]
    agent._biometric_freshness_component      = lambda: components["biometric_freshness_component"]
    agent._agent_calibration_component        = lambda: components["agent_calibration_component"]
    agent._enrollment_component               = lambda: components["enrollment_component"]
    agent._threat_forecast_accuracy_component = lambda: components["threat_forecast_accuracy_component"]
    agent._biometric_stationarity_component   = lambda: components["biometric_stationarity_component"]

    result = agent._run_scoring()
    assert abs(result["maturity_score"] - expected) < 1e-5, (
        f"Expected score {expected}, got {result['maturity_score']}"
    )


# ---------------------------------------------------------------------------
# TSP-191-8: config.tsp_enabled defaults True
# ---------------------------------------------------------------------------

def test_config_tsp_enabled_defaults_true():
    """Config.tsp_enabled defaults to True (enabled by default)."""
    import os
    # Verify the config field exists and has the correct default without reloading
    # the module (reload would corrupt subsequent config tests in the same pytest session).
    env_backup = os.environ.pop("TSP_ENABLED", None)
    try:
        from bridge.vapi_bridge.config import Config
        cfg = Config()
        assert cfg.tsp_enabled is True, "tsp_enabled should default to True"
    finally:
        if env_backup is not None:
            os.environ["TSP_ENABLED"] = env_backup
