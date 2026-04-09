"""Phase 177 SDK tests — ProtocolMaturityResult + VAPIProtocolMaturity.

4 tests:
  T177-SDK-1  ProtocolMaturityResult has expected slots
  T177-SDK-2  Default error is None
  T177-SDK-3  VAPIProtocolMaturity.get_score() populates all fields from body
  T177-SDK-4  Error path returns ALPHA tier with error set
"""
import json
import sys
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "sdk"))

import pytest


# ---------------------------------------------------------------------------
# T177-SDK-1  Result has expected slots
# ---------------------------------------------------------------------------

def test_t177_sdk_1_result_has_expected_slots():
    from vapi_sdk import ProtocolMaturityResult
    r = ProtocolMaturityResult(
        protocol_maturity_enabled       = True,
        maturity_score                   = 0.64,
        maturity_tier                    = "BETA",
        separation_component             = 0.5,
        chain_integrity_component        = 1.0,
        consent_component                = 0.7,
        biometric_freshness_component    = 0.6,
        agent_calibration_component      = 0.7,
        enrollment_component             = 0.3,
    )
    assert r.protocol_maturity_enabled is True
    assert abs(r.maturity_score - 0.64) < 1e-9
    assert r.maturity_tier == "BETA"
    assert abs(r.separation_component - 0.5) < 1e-9
    assert abs(r.chain_integrity_component - 1.0) < 1e-9
    assert r.error is None


# ---------------------------------------------------------------------------
# T177-SDK-2  Default error is None
# ---------------------------------------------------------------------------

def test_t177_sdk_2_default_error_none():
    from vapi_sdk import ProtocolMaturityResult
    r = ProtocolMaturityResult(
        protocol_maturity_enabled       = True,
        maturity_score                   = 1.0,
        maturity_tier                    = "PRODUCTION_CANDIDATE",
        separation_component             = 1.0,
        chain_integrity_component        = 1.0,
        consent_component                = 1.0,
        biometric_freshness_component    = 1.0,
        agent_calibration_component      = 1.0,
        enrollment_component             = 1.0,
    )
    assert r.error is None


# ---------------------------------------------------------------------------
# T177-SDK-3  get_score() populates all fields from API body
# ---------------------------------------------------------------------------

def test_t177_sdk_3_get_score_populates_from_body():
    from vapi_sdk import VAPIProtocolMaturity

    mock_body = {
        "protocol_maturity_enabled":       True,
        "maturity_score":                  0.64,
        "maturity_tier":                   "BETA",
        "separation_component":            0.5,
        "chain_integrity_component":       1.0,
        "consent_component":               0.7,
        "biometric_freshness_component":   0.6,
        "agent_calibration_component":     0.7,
        "enrollment_component":            0.3,
        "timestamp":                       1234567890.0,
    }

    class _FakeResp:
        def __enter__(self): return self
        def __exit__(self, *a): pass
        def read(self): return json.dumps(mock_body).encode()

    with patch("urllib.request.urlopen", return_value=_FakeResp()):
        client = VAPIProtocolMaturity("http://localhost:8080", "k")
        result = client.get_score()

    assert result.protocol_maturity_enabled is True
    assert abs(result.maturity_score - 0.64) < 1e-9
    assert result.maturity_tier == "BETA"
    assert abs(result.separation_component - 0.5) < 1e-9
    assert result.error is None


# ---------------------------------------------------------------------------
# T177-SDK-4  Error path returns ALPHA tier with error set
# ---------------------------------------------------------------------------

def test_t177_sdk_4_error_path_alpha_tier():
    from vapi_sdk import VAPIProtocolMaturity

    with patch("urllib.request.urlopen", side_effect=Exception("conn refused")):
        client = VAPIProtocolMaturity("http://localhost:8080", "k")
        result = client.get_score()

    assert result.error is not None
    assert "conn refused" in result.error
    assert result.maturity_tier == "ALPHA"
    assert result.maturity_score == 0.0
    assert result.separation_component == 0.0
