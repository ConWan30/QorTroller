"""
Phase 218 SDK Tests
T218-SDK-1..4: CaptureVelocityResult / VAPICaptureVelocityOracle
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "sdk"))


# ── T218-SDK-1: CaptureVelocityResult has required slots ─────────────────────
def test_T218_sdk_1_dataclass_fields():
    """CaptureVelocityResult has required slots (Phase 218)."""
    from vapi_sdk import CaptureVelocityResult
    import dataclasses
    fields = {f.name for f in dataclasses.fields(CaptureVelocityResult)}
    assert "capture_velocity_oracle_enabled" in fields
    assert "probe_type"                      in fields
    assert "sessions_per_day"               in fields
    assert "sessions_stagnant"              in fields
    assert "ratio_velocity"                 in fields
    assert "velocity_stagnant"              in fields
    assert "overall_capture_healthy"        in fields
    assert "recommended_action"             in fields
    assert "error"                          in fields


# ── T218-SDK-2: CaptureVelocityResult instantiation ──────────────────────────
def test_T218_sdk_2_result_instantiation():
    """CaptureVelocityResult can be created with oracle data."""
    from vapi_sdk import CaptureVelocityResult
    r = CaptureVelocityResult(
        capture_velocity_oracle_enabled = True,
        probe_type                      = "touchpad_corners",
        sessions_per_day                = 0.0,
        sessions_stagnant               = True,
        ratio_velocity                  = 0.0,
        velocity_stagnant               = True,
        overall_capture_healthy         = False,
        recommended_action              = "URGENT_CAPTURE_SESSIONS_AND_REANALYZE",
    )
    assert r.capture_velocity_oracle_enabled is True
    assert r.probe_type == "touchpad_corners"
    assert r.sessions_stagnant is True
    assert r.velocity_stagnant is True
    assert r.overall_capture_healthy is False
    assert r.recommended_action == "URGENT_CAPTURE_SESSIONS_AND_REANALYZE"
    assert r.error is None


# ── T218-SDK-3: VAPICaptureVelocityOracle returns error on network failure ────
def test_T218_sdk_3_client_network_error():
    """VAPICaptureVelocityOracle returns CaptureVelocityResult with error on connection failure."""
    from vapi_sdk import VAPICaptureVelocityOracle, CaptureVelocityResult
    client = VAPICaptureVelocityOracle("http://localhost:19999", api_key="test")
    result = client.get_status()
    assert isinstance(result, CaptureVelocityResult)
    assert result.error is not None
    assert result.overall_capture_healthy is False
    assert result.capture_velocity_oracle_enabled is False


# ── T218-SDK-4: VAPICaptureVelocityOracle.get_status() parses response ────────
def test_T218_sdk_4_get_status_parses_response():
    """VAPICaptureVelocityOracle.get_status() parses all fields from a 200 response."""
    import json
    from unittest.mock import MagicMock, patch
    from vapi_sdk import VAPICaptureVelocityOracle, CaptureVelocityResult

    body = json.dumps({
        "capture_velocity_oracle_enabled": True,
        "probe_type":                      "touchpad_corners",
        "sessions_per_day":                0.0,
        "sessions_stagnant":               True,
        "ratio_velocity":                  0.0,
        "velocity_stagnant":               True,
        "overall_capture_healthy":         False,
        "recommended_action":              "URGENT_CAPTURE_SESSIONS_AND_REANALYZE",
        "timestamp":                       1712400000.0,
    }).encode()

    mock_resp = MagicMock()
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = MagicMock(return_value=False)
    mock_resp.read.return_value = body

    with patch("urllib.request.urlopen", return_value=mock_resp):
        client = VAPICaptureVelocityOracle("http://localhost:8080", api_key="test")
        result = client.get_status()

    assert isinstance(result, CaptureVelocityResult)
    assert result.capture_velocity_oracle_enabled is True
    assert result.probe_type == "touchpad_corners"
    assert result.sessions_stagnant is True
    assert result.velocity_stagnant is True
    assert result.overall_capture_healthy is False
    assert result.recommended_action == "URGENT_CAPTURE_SESSIONS_AND_REANALYZE"
    assert result.error is None
