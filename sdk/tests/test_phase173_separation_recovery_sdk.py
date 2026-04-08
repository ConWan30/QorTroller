"""Phase 173 SDK tests — SeparationRatioRecoveryResult + VAPISeparationRatioRecovery.

4 tests:
  T173-SDK-1  SeparationRatioRecoveryResult has expected slots
  T173-SDK-2  Default error is None
  T173-SDK-3  VAPISeparationRatioRecovery.get_status() populates all fields from body
  T173-SDK-4  Error path returns STABLE defaults with error set
"""
import json
import sys
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "sdk"))

import pytest


# ---------------------------------------------------------------------------
# T173-SDK-1  Result has expected slots
# ---------------------------------------------------------------------------

def test_t173_sdk_1_result_has_expected_slots():
    from vapi_sdk import SeparationRatioRecoveryResult
    r = SeparationRatioRecoveryResult(
        separation_recovery_enabled = True,
        current_ratio    = 0.569,
        trend_velocity   = -0.077,
        recovery_needed  = True,
        recovery_action  = "P1_RE_ENROLLMENT",
        recommendation   = "Re-enroll P1.",
    )
    assert r.separation_recovery_enabled is True
    assert abs(r.current_ratio - 0.569) < 1e-9
    assert abs(r.trend_velocity - (-0.077)) < 1e-9
    assert r.recovery_needed is True
    assert r.recovery_action == "P1_RE_ENROLLMENT"
    assert r.error is None


# ---------------------------------------------------------------------------
# T173-SDK-2  Default error is None
# ---------------------------------------------------------------------------

def test_t173_sdk_2_default_error_none():
    from vapi_sdk import SeparationRatioRecoveryResult
    r = SeparationRatioRecoveryResult(
        separation_recovery_enabled = True,
        current_ratio    = 1.5,
        trend_velocity   = 0.1,
        recovery_needed  = False,
        recovery_action  = "STABLE",
        recommendation   = "All good.",
    )
    assert r.error is None


# ---------------------------------------------------------------------------
# T173-SDK-3  get_status() populates all fields from API body
# ---------------------------------------------------------------------------

def test_t173_sdk_3_get_status_populates_from_body():
    from vapi_sdk import VAPISeparationRatioRecovery

    mock_body = {
        "separation_recovery_enabled": True,
        "current_ratio":    0.569,
        "trend_velocity":   -0.077,
        "n_snapshots_used": 3,
        "recovery_needed":  True,
        "recovery_action":  "P1_RE_ENROLLMENT",
        "recommendation":   "Re-enroll P1 with fresh sessions.",
        "timestamp":        1234567890.0,
    }

    class _FakeResp:
        def __enter__(self): return self
        def __exit__(self, *a): pass
        def read(self): return json.dumps(mock_body).encode()

    with patch("urllib.request.urlopen", return_value=_FakeResp()):
        client = VAPISeparationRatioRecovery("http://localhost:8080", "k")
        result = client.get_status()

    assert result.separation_recovery_enabled is True
    assert abs(result.current_ratio - 0.569) < 1e-9
    assert abs(result.trend_velocity - (-0.077)) < 1e-9
    assert result.recovery_needed is True
    assert result.recovery_action == "P1_RE_ENROLLMENT"
    assert result.error is None


# ---------------------------------------------------------------------------
# T173-SDK-4  Error path returns STABLE defaults
# ---------------------------------------------------------------------------

def test_t173_sdk_4_error_path_stable_defaults():
    from vapi_sdk import VAPISeparationRatioRecovery

    with patch("urllib.request.urlopen", side_effect=Exception("conn refused")):
        client = VAPISeparationRatioRecovery("http://localhost:8080", "k")
        result = client.get_status()

    assert result.error is not None
    assert "conn refused" in result.error
    assert result.recovery_needed is False
    assert result.recovery_action == "STABLE"
    assert result.current_ratio == 0.0
