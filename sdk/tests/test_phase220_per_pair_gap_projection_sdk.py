"""
Phase 220 SDK Tests
T220-SDK-1..4: PerPairGapProjectionResult / VAPIPerPairGapProjection
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "sdk"))


# ── T220-SDK-1: PerPairGapProjectionResult has required slots ────────────────
def test_T220_sdk_1_dataclass_fields():
    """PerPairGapProjectionResult has required slots (Phase 220)."""
    from vapi_sdk import PerPairGapProjectionResult
    import dataclasses
    fields = {f.name for f in dataclasses.fields(PerPairGapProjectionResult)}
    assert "per_pair_gap_projection_enabled" in fields
    assert "projections"                     in fields
    assert "any_feasible"                    in fields
    assert "max_days_to_1_0"                 in fields
    assert "projected_tge_date"              in fields
    assert "session_type"                    in fields
    assert "error"                           in fields


# ── T220-SDK-2: PerPairGapProjectionResult instantiation ─────────────────────
def test_T220_sdk_2_result_instantiation():
    """PerPairGapProjectionResult can be created with projection data."""
    from vapi_sdk import PerPairGapProjectionResult
    projections = [
        {
            "pair_key": "P1vP3", "current_distance": 0.032,
            "velocity_per_day": 0.156, "estimated_days_to_1_0": 6.2,
            "projected_date": "2026-04-22", "projection_feasible": True,
            "status": "IMPROVING",
        },
    ]
    r = PerPairGapProjectionResult(
        per_pair_gap_projection_enabled = True,
        projections                     = projections,
        any_feasible                    = True,
        max_days_to_1_0                 = 6.2,
        projected_tge_date              = "2026-04-22",
        session_type                    = "touchpad_corners",
    )
    assert r.per_pair_gap_projection_enabled is True
    assert len(r.projections) == 1
    assert r.any_feasible is True
    assert abs(r.max_days_to_1_0 - 6.2) < 1e-9
    assert r.projected_tge_date == "2026-04-22"
    assert r.error is None


# ── T220-SDK-3: VAPIPerPairGapProjection returns error on network failure ─────
def test_T220_sdk_3_client_network_error():
    """VAPIPerPairGapProjection returns result with error on connection failure."""
    from vapi_sdk import VAPIPerPairGapProjection, PerPairGapProjectionResult
    client = VAPIPerPairGapProjection("http://localhost:19999", api_key="test")
    result = client.get_projection()
    assert isinstance(result, PerPairGapProjectionResult)
    assert result.error is not None
    assert result.any_feasible is False
    assert result.per_pair_gap_projection_enabled is False


# ── T220-SDK-4: VAPIPerPairGapProjection.get_projection() parses response ─────
def test_T220_sdk_4_get_projection_parses_response():
    """VAPIPerPairGapProjection.get_projection() parses all fields from 200 response."""
    import json
    from unittest.mock import MagicMock, patch
    from vapi_sdk import VAPIPerPairGapProjection, PerPairGapProjectionResult

    projections = [
        {
            "pair_key": "P1vP3", "current_distance": 0.032,
            "velocity_per_day": 0.156, "estimated_days_to_1_0": 6.2,
            "projected_date": "2026-04-22", "projection_feasible": True,
            "status": "IMPROVING",
        },
    ]
    body = json.dumps({
        "per_pair_gap_projection_enabled": True,
        "projections":                     projections,
        "any_feasible":                    True,
        "max_days_to_1_0":                 6.2,
        "projected_tge_date":              "2026-04-22",
        "session_type":                    "touchpad_corners",
        "timestamp":                       1712400000.0,
    }).encode()

    mock_resp = MagicMock()
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = MagicMock(return_value=False)
    mock_resp.read.return_value = body

    with patch("urllib.request.urlopen", return_value=mock_resp):
        client = VAPIPerPairGapProjection("http://localhost:8080", api_key="test")
        result = client.get_projection()

    assert isinstance(result, PerPairGapProjectionResult)
    assert result.per_pair_gap_projection_enabled is True
    assert len(result.projections) == 1
    assert result.any_feasible is True
    assert abs(result.max_days_to_1_0 - 6.2) < 1e-9
    assert result.projected_tge_date == "2026-04-22"
    assert result.error is None
