"""
Phase 207 SDK Tests
T207-SDK-1..4: DryRunGraduationResult / VAPIDryRunGraduation
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "sdk"))


# ── T207-SDK-1: DryRunGraduationResult has required slots ────────────────────
def test_T207_sdk_1_dataclass_fields():
    """DryRunGraduationResult has required slots (Phase 207)."""
    from vapi_sdk import DryRunGraduationResult
    import dataclasses
    fields = {f.name for f in dataclasses.fields(DryRunGraduationResult)}
    assert "staged_graduation_enabled" in fields
    assert "rollback_window_sessions"  in fields
    assert "fp_threshold"              in fields
    assert "stages"                    in fields
    assert "active_stage_count"        in fields
    assert "timestamp"                 in fields
    assert "error"                     in fields


# ── T207-SDK-2: DryRunGraduationResult instantiation ─────────────────────────
def test_T207_sdk_2_result_instantiation():
    """DryRunGraduationResult can be created with stages."""
    from vapi_sdk import DryRunGraduationResult
    stages = [
        {
            "agent_id":          "session_adjudicator",
            "stage_number":      1,
            "n_clean_sessions":  7,
            "n_false_positives": 0,
            "rollback_triggered": 0,
        }
    ]
    r = DryRunGraduationResult(
        staged_graduation_enabled = True,
        rollback_window_sessions  = 10,
        fp_threshold              = 2,
        stages                    = stages,
        active_stage_count        = 1,
        timestamp                 = 1712200000.0,
    )
    assert r.staged_graduation_enabled is True
    assert r.active_stage_count == 1
    assert len(r.stages) == 1
    assert r.stages[0]["agent_id"] == "session_adjudicator"
    assert r.error is None


# ── T207-SDK-3: VAPIDryRunGraduation returns error on network failure ─────────
def test_T207_sdk_3_client_network_error():
    """VAPIDryRunGraduation returns DryRunGraduationResult with error on failure."""
    from vapi_sdk import VAPIDryRunGraduation, DryRunGraduationResult
    client = VAPIDryRunGraduation("http://localhost:19999", api_key="test")
    result = client.get_status()
    assert isinstance(result, DryRunGraduationResult)
    assert result.error is not None
    assert result.staged_graduation_enabled is False
    assert result.stages == []
    assert result.active_stage_count == 0


# ── T207-SDK-4: VAPIDryRunGraduation.get_status() parses response ─────────────
def test_T207_sdk_4_get_status_parses_response():
    """VAPIDryRunGraduation.get_status() parses all fields from a 200 response."""
    import json
    from unittest.mock import MagicMock, patch
    from vapi_sdk import VAPIDryRunGraduation, DryRunGraduationResult

    stages_data = [
        {
            "id": 1, "agent_id": "ruling_enforcement_agent",
            "stage_number": 1, "n_clean_sessions": 12, "n_false_positives": 0,
            "rollback_triggered": 0, "rollback_reason": None,
        },
        {
            "id": 2, "agent_id": "session_adjudicator",
            "stage_number": 2, "n_clean_sessions": 5, "n_false_positives": 1,
            "rollback_triggered": 0, "rollback_reason": None,
        },
    ]
    body = json.dumps({
        "staged_graduation_enabled": True,
        "rollback_window_sessions":  10,
        "fp_threshold":              2,
        "stages":                    stages_data,
        "active_stage_count":        2,
        "timestamp":                 1712200000.0,
    }).encode()

    mock_resp = MagicMock()
    mock_resp.read.return_value = body
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = MagicMock(return_value=False)

    with patch("urllib.request.urlopen", return_value=mock_resp):
        client = VAPIDryRunGraduation("http://localhost:8080", "test-key")
        result = client.get_status()

    assert result.error is None
    assert result.staged_graduation_enabled is True, (
        f"Expected staged_graduation_enabled=True; got {result.staged_graduation_enabled}"
    )
    assert result.active_stage_count == 2, (
        f"Expected active_stage_count=2; got {result.active_stage_count}"
    )
    assert len(result.stages) == 2
    assert result.stages[0]["agent_id"] == "ruling_enforcement_agent"
    assert result.stages[1]["n_clean_sessions"] == 5
    assert result.fp_threshold == 2
    assert result.timestamp == pytest.approx(1712200000.0)
