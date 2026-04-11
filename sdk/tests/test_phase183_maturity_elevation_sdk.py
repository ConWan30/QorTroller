"""Phase 183 SDK tests — MaturityElevationGateAgent (WIF-027 W2 closure).

4 tests:
  T183-SDK-1  MaturityElevationResult has 7 slots; error=None default; elevation_plan is dict
  T183-SDK-2  get_status populates all fields from response body
  T183-SDK-3  error path returns ALPHA-tier safe defaults (fail-safe)
  T183-SDK-4  elevation_plan dict populated from response body
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "sdk"))


# ---------------------------------------------------------------------------
# T183-SDK-1  MaturityElevationResult has 7 slots; error=None default
# ---------------------------------------------------------------------------

def test_t183_sdk_1_maturity_elevation_result_slots():
    from vapi_sdk import MaturityElevationResult
    r = MaturityElevationResult(
        current_tier="ALPHA",
        target_tier="BETA",
        gap_to_target=0.27,
        elevation_available=False,
        elevation_plan={},
        critical_component="separation_component",
    )
    assert r.current_tier == "ALPHA"
    assert r.target_tier == "BETA"
    assert r.gap_to_target == 0.27
    assert r.elevation_available is False
    assert isinstance(r.elevation_plan, dict)
    assert r.critical_component == "separation_component"
    assert r.error is None


# ---------------------------------------------------------------------------
# T183-SDK-2  get_status populates all fields from response body
# ---------------------------------------------------------------------------

def test_t183_sdk_2_get_status_populates_fields():
    from unittest.mock import patch, MagicMock
    import json as _j
    from vapi_sdk import VAPIMaturityElevation, MaturityElevationResult

    plan = {
        "separation_component": {"gap": 0.17, "action": "P1_RE_ENROLLMENT", "estimated_sessions": 4},
    }
    body = {
        "maturity_elevation_enabled": True,
        "current_tier":              "ALPHA",
        "target_tier":               "BETA",
        "gap_to_target":             0.27,
        "elevation_available":       False,
        "elevation_plan":            plan,
        "estimated_sessions_total":  4,
        "critical_component":        "separation_component",
        "timestamp":                 1.0,
    }
    mock_resp = MagicMock()
    mock_resp.read.return_value = _j.dumps(body).encode()
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = MagicMock(return_value=False)

    with patch("urllib.request.urlopen", return_value=mock_resp):
        me = VAPIMaturityElevation("http://localhost:8080", "test-key")
        result = me.get_status()

    assert isinstance(result, MaturityElevationResult)
    assert result.current_tier == "ALPHA"
    assert result.gap_to_target == 0.27
    assert result.critical_component == "separation_component"
    assert "separation_component" in result.elevation_plan
    assert result.error is None


# ---------------------------------------------------------------------------
# T183-SDK-3  error path returns ALPHA-tier safe defaults (fail-safe)
# ---------------------------------------------------------------------------

def test_t183_sdk_3_error_path_alpha_defaults():
    from unittest.mock import patch
    from vapi_sdk import VAPIMaturityElevation

    with patch("urllib.request.urlopen", side_effect=Exception("timeout")):
        me = VAPIMaturityElevation("http://localhost:8080", "test-key")
        result = me.get_status()

    assert result.current_tier == "ALPHA"
    assert result.target_tier == "BETA"
    assert result.gap_to_target == 1.0
    assert result.elevation_available is False
    assert result.error is not None
    assert "timeout" in result.error


# ---------------------------------------------------------------------------
# T183-SDK-4  elevation_plan dict populated from body
# ---------------------------------------------------------------------------

def test_t183_sdk_4_elevation_plan_dict():
    from unittest.mock import patch, MagicMock
    import json as _j
    from vapi_sdk import VAPIMaturityElevation

    plan = {
        "separation_component":          {"gap": 0.17, "blocking": True},
        "chain_integrity_component":     {"gap": 0.0,  "blocking": False},
        "consent_component":             {"gap": 0.05, "blocking": False},
        "biometric_freshness_component": {"gap": 0.0,  "blocking": False},
        "agent_calibration_component":   {"gap": 0.02, "blocking": False},
        "enrollment_component":          {"gap": 0.10, "blocking": True},
    }
    body = {
        "current_tier":        "ALPHA",
        "target_tier":         "BETA",
        "gap_to_target":       0.27,
        "elevation_available": False,
        "elevation_plan":      plan,
        "critical_component":  "separation_component",
    }
    mock_resp = MagicMock()
    mock_resp.read.return_value = _j.dumps(body).encode()
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = MagicMock(return_value=False)

    with patch("urllib.request.urlopen", return_value=mock_resp):
        me = VAPIMaturityElevation("http://localhost:8080", "test-key")
        result = me.get_status()

    assert len(result.elevation_plan) == 6
    assert result.elevation_plan["separation_component"]["blocking"] is True
