"""
Phase 191 SDK tests — ProtocolMaturityScoringResult v2 + VAPIProtocolMaturityScoring.

Tests:
  T191S-1: ProtocolMaturityScoringResult has 2 new TSP slots with safe defaults (0.0)
  T191S-2: get_score populates threat_forecast_accuracy_component from HTTP response
  T191S-3: get_score populates biometric_stationarity_component from HTTP response
  T191S-4: error path returns 0.0 for both new TSP fields (never raises)
"""

import sys
import os
from unittest.mock import MagicMock, patch
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from vapi_sdk import ProtocolMaturityScoringResult, VAPIProtocolMaturityScoring  # noqa: E402


# ---------------------------------------------------------------------------
# T191S-1: new TSP slots exist with safe defaults
# ---------------------------------------------------------------------------

def test_t191s_1_tsp_slots_and_defaults():
    """T191S-1: ProtocolMaturityScoringResult has threat_forecast_accuracy_component
    and biometric_stationarity_component slots defaulting to 0.0."""
    r = ProtocolMaturityScoringResult(
        protocol_maturity_enabled=True,
        maturity_score=0.0,
        maturity_tier="ALPHA",
        separation_component=0.0,
        chain_integrity_component=0.0,
        consent_component=0.0,
        biometric_freshness_component=0.0,
        agent_calibration_component=0.0,
        enrollment_component=0.0,
    )
    # New TSP fields have default 0.0
    assert hasattr(r, "threat_forecast_accuracy_component"), \
        "ProtocolMaturityScoringResult missing threat_forecast_accuracy_component"
    assert hasattr(r, "biometric_stationarity_component"), \
        "ProtocolMaturityScoringResult missing biometric_stationarity_component"
    assert r.threat_forecast_accuracy_component == 0.0
    assert r.biometric_stationarity_component == 0.0


# ---------------------------------------------------------------------------
# T191S-2: get_score populates threat_forecast_accuracy_component
# ---------------------------------------------------------------------------

def test_t191s_2_get_score_populates_tfa():
    """T191S-2: get_score() correctly maps threat_forecast_accuracy_component from API body."""
    client = VAPIProtocolMaturityScoring("http://localhost:9999", api_key="test")

    body = {
        "protocol_maturity_enabled": True,
        "maturity_score": 0.63,
        "maturity_tier": "BETA",
        "separation_component": 0.56,
        "chain_integrity_component": 1.0,
        "consent_component": 1.0,
        "biometric_freshness_component": 0.80,
        "agent_calibration_component": 0.75,
        "enrollment_component": 0.20,
        "threat_forecast_accuracy_component": 0.852,
        "biometric_stationarity_component": 0.45,
    }

    class _FakeResp:
        def read(self):
            return json.dumps(body).encode()
        def __enter__(self):
            return self
        def __exit__(self, *a):
            pass

    with patch("urllib.request.urlopen", return_value=_FakeResp()):
        result = client.get_score()

    assert abs(result.threat_forecast_accuracy_component - 0.852) < 0.001


# ---------------------------------------------------------------------------
# T191S-3: get_score populates biometric_stationarity_component
# ---------------------------------------------------------------------------

def test_t191s_3_get_score_populates_bso():
    """T191S-3: get_score() correctly maps biometric_stationarity_component from API body."""
    client = VAPIProtocolMaturityScoring("http://localhost:9999", api_key="test")

    body = {
        "protocol_maturity_enabled": True,
        "maturity_score": 0.61,
        "maturity_tier": "BETA",
        "separation_component": 0.50,
        "chain_integrity_component": 0.95,
        "consent_component": 1.0,
        "biometric_freshness_component": 0.75,
        "agent_calibration_component": 0.80,
        "enrollment_component": 0.15,
        "threat_forecast_accuracy_component": 0.70,
        "biometric_stationarity_component": 0.612,
    }

    class _FakeResp:
        def read(self):
            return json.dumps(body).encode()
        def __enter__(self):
            return self
        def __exit__(self, *a):
            pass

    with patch("urllib.request.urlopen", return_value=_FakeResp()):
        result = client.get_score()

    assert abs(result.biometric_stationarity_component - 0.612) < 0.001


# ---------------------------------------------------------------------------
# T191S-4: error path — both new fields default to 0.0
# ---------------------------------------------------------------------------

def test_t191s_4_error_path_safe_defaults():
    """T191S-4: on network error, threat_forecast_accuracy_component and
    biometric_stationarity_component both default to 0.0."""
    client = VAPIProtocolMaturityScoring("http://localhost:9999", api_key="test")

    with patch("urllib.request.urlopen", side_effect=ConnectionRefusedError("refused")):
        result = client.get_score()

    assert result.error is not None
    assert result.threat_forecast_accuracy_component == 0.0
    assert result.biometric_stationarity_component == 0.0
    assert result.maturity_tier == "ALPHA"
