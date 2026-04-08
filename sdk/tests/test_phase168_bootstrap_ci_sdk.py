"""Phase 168 SDK tests — Bootstrap CI fields in SeparationRatioResult.

4 tests:
  T168-SDK-1  SeparationRatioResult has ci_lower/ci_upper/n_bootstrap fields
  T168-SDK-2  Default values are 0.0/0.0/0
  T168-SDK-3  VAPISeparationStatus.get_status() populates CI from response body
  T168-SDK-4  Error path populates ci_lower=0.0/ci_upper=0.0/n_bootstrap=0
"""
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch
import json

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "sdk"))

import pytest


# ---------------------------------------------------------------------------
# T168-SDK-1  SeparationRatioResult has CI fields
# ---------------------------------------------------------------------------

def test_t168_sdk_1_separation_ratio_result_has_ci_fields():
    """SeparationRatioResult dataclass has ci_lower, ci_upper, n_bootstrap slots."""
    from vapi_sdk import SeparationRatioResult
    r = SeparationRatioResult(
        pooled_ratio=1.261,
        battery_stratified_ratio=1.35,
        tournament_blocker=False,
        gap_to_target=0.0,
        tournament_ready=True,
        ci_lower=0.95,
        ci_upper=1.58,
        n_bootstrap=1000,
    )
    assert abs(r.ci_lower - 0.95) < 1e-9, f"ci_lower mismatch: {r.ci_lower}"
    assert abs(r.ci_upper - 1.58) < 1e-9, f"ci_upper mismatch: {r.ci_upper}"
    assert r.n_bootstrap == 1000, f"n_bootstrap mismatch: {r.n_bootstrap}"


# ---------------------------------------------------------------------------
# T168-SDK-2  Default values are 0.0/0.0/0
# ---------------------------------------------------------------------------

def test_t168_sdk_2_ci_defaults_are_zero():
    """SeparationRatioResult CI fields default to 0.0/0.0/0 when not provided."""
    from vapi_sdk import SeparationRatioResult
    r = SeparationRatioResult(
        pooled_ratio=0.569,
        battery_stratified_ratio=-1.0,
        tournament_blocker=True,
        gap_to_target=0.431,
        tournament_ready=False,
    )
    assert r.ci_lower == 0.0, f"ci_lower default should be 0.0, got {r.ci_lower}"
    assert r.ci_upper == 0.0, f"ci_upper default should be 0.0, got {r.ci_upper}"
    assert r.n_bootstrap == 0, f"n_bootstrap default should be 0, got {r.n_bootstrap}"


# ---------------------------------------------------------------------------
# T168-SDK-3  VAPISeparationStatus.get_status() populates CI from response body
# ---------------------------------------------------------------------------

def test_t168_sdk_3_get_status_populates_ci_from_body():
    """VAPISeparationStatus.get_status() reads ci_lower/ci_upper/n_bootstrap from API response."""
    from vapi_sdk import VAPISeparationStatus

    mock_body = {
        "pooled_ratio": 1.261,
        "battery_stratified_ratio": 1.35,
        "tournament_blocker": False,
        "target_ratio": 1.0,
        "gap_to_target": 0.0,
        "tournament_ready": True,
        "ci_lower": 0.980,
        "ci_upper": 1.550,
        "n_bootstrap": 2000,
        "timestamp": 1234567890.0,
    }

    import io, urllib.request as _ur

    class _FakeResp:
        def __enter__(self): return self
        def __exit__(self, *a): pass
        def read(self): return json.dumps(mock_body).encode()

    with patch("urllib.request.urlopen", return_value=_FakeResp()):
        status = VAPISeparationStatus(base_url="http://localhost:8080", api_key="k")
        result = status.get_status()

    assert abs(result.ci_lower - 0.980) < 1e-9, f"ci_lower mismatch: {result.ci_lower}"
    assert abs(result.ci_upper - 1.550) < 1e-9, f"ci_upper mismatch: {result.ci_upper}"
    assert result.n_bootstrap == 2000, f"n_bootstrap mismatch: {result.n_bootstrap}"
    assert result.error is None


# ---------------------------------------------------------------------------
# T168-SDK-4  Error path populates CI defaults
# ---------------------------------------------------------------------------

def test_t168_sdk_4_error_path_ci_defaults():
    """On connection error, SeparationRatioResult.ci_* fields default to 0.0/0.0/0."""
    from vapi_sdk import VAPISeparationStatus

    with patch("urllib.request.urlopen", side_effect=Exception("timeout")):
        status = VAPISeparationStatus(base_url="http://localhost:8080", api_key="k")
        result = status.get_status()

    assert result.error is not None, "error should be set on exception"
    assert result.ci_lower == 0.0, f"ci_lower should be 0.0 on error, got {result.ci_lower}"
    assert result.ci_upper == 0.0, f"ci_upper should be 0.0 on error, got {result.ci_upper}"
    assert result.n_bootstrap == 0, f"n_bootstrap should be 0 on error, got {result.n_bootstrap}"
    assert result.tournament_blocker is True
