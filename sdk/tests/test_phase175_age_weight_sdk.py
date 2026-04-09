"""Phase 175 SDK tests — AgeWeightAnalysisResult + VAPIAgeWeightAnalysis.

4 tests:
  T175-SDK-1  AgeWeightAnalysisResult has expected slots
  T175-SDK-2  Default error is None
  T175-SDK-3  VAPIAgeWeightAnalysis.get_status() populates all fields from body
  T175-SDK-4  Error path returns STABLE defaults with error set
"""
import json
import sys
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "sdk"))

import pytest


# ---------------------------------------------------------------------------
# T175-SDK-1  Result has expected slots
# ---------------------------------------------------------------------------

def test_t175_sdk_1_result_has_expected_slots():
    from vapi_sdk import AgeWeightAnalysisResult
    r = AgeWeightAnalysisResult(
        age_weight_analysis_enabled = True,
        raw_ratio            = 0.569,
        age_weighted_ratio   = 0.720,
        temporal_drift_index = -0.151,
        halflife_days        = 90.0,
        drift_direction      = "IMPROVING",
    )
    assert r.age_weight_analysis_enabled is True
    assert abs(r.raw_ratio - 0.569) < 1e-9
    assert abs(r.age_weighted_ratio - 0.720) < 1e-9
    assert abs(r.temporal_drift_index - (-0.151)) < 1e-9
    assert abs(r.halflife_days - 90.0) < 1e-9
    assert r.drift_direction == "IMPROVING"
    assert r.error is None


# ---------------------------------------------------------------------------
# T175-SDK-2  Default error is None
# ---------------------------------------------------------------------------

def test_t175_sdk_2_default_error_none():
    from vapi_sdk import AgeWeightAnalysisResult
    r = AgeWeightAnalysisResult(
        age_weight_analysis_enabled = True,
        raw_ratio            = 1.0,
        age_weighted_ratio   = 1.0,
        temporal_drift_index = 0.0,
        halflife_days        = 90.0,
        drift_direction      = "STABLE",
    )
    assert r.error is None


# ---------------------------------------------------------------------------
# T175-SDK-3  get_status() populates all fields from API body
# ---------------------------------------------------------------------------

def test_t175_sdk_3_get_status_populates_from_body():
    from vapi_sdk import VAPIAgeWeightAnalysis

    mock_body = {
        "age_weight_analysis_enabled": True,
        "raw_ratio":            0.569,
        "age_weighted_ratio":   0.720,
        "temporal_drift_index": -0.151,
        "halflife_days":        90.0,
        "n_sessions_used":      20,
        "drift_direction":      "IMPROVING",
        "timestamp":            1234567890.0,
    }

    class _FakeResp:
        def __enter__(self): return self
        def __exit__(self, *a): pass
        def read(self): return json.dumps(mock_body).encode()

    with patch("urllib.request.urlopen", return_value=_FakeResp()):
        client = VAPIAgeWeightAnalysis("http://localhost:8080", "k")
        result = client.get_status()

    assert result.age_weight_analysis_enabled is True
    assert abs(result.raw_ratio - 0.569) < 1e-9
    assert abs(result.age_weighted_ratio - 0.720) < 1e-9
    assert abs(result.temporal_drift_index - (-0.151)) < 1e-9
    assert result.drift_direction == "IMPROVING"
    assert result.error is None


# ---------------------------------------------------------------------------
# T175-SDK-4  Error path returns STABLE defaults
# ---------------------------------------------------------------------------

def test_t175_sdk_4_error_path_stable_defaults():
    from vapi_sdk import VAPIAgeWeightAnalysis

    with patch("urllib.request.urlopen", side_effect=Exception("conn refused")):
        client = VAPIAgeWeightAnalysis("http://localhost:8080", "k")
        result = client.get_status()

    assert result.error is not None
    assert "conn refused" in result.error
    assert result.drift_direction == "STABLE"
    assert result.temporal_drift_index == 0.0
    assert abs(result.halflife_days - 90.0) < 1e-9
