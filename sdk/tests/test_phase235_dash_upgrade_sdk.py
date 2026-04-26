"""Phase 235-DASH-UPGRADE-3 SDK tests.

T235-DASH-SDK-1: AITSeparationResult has all new slots with correct defaults
T235-DASH-SDK-2: VAPIAITSeparation.status() parses per_player_tremor_hz and related dicts
T235-DASH-SDK-3: GrindAnalyticsResult has last_validation_ts / last_stamp_ts slots
T235-DASH-SDK-4: VAPIGrindAnalytics.status() parses last_validation_ts and last_stamp_ts
"""
import json
from unittest.mock import MagicMock, patch

import pytest

from vapi_sdk import (
    AITSeparationResult,
    GrindAnalyticsResult,
    VAPIAITSeparation,
    VAPIGrindAnalytics,
)


# T235-DASH-SDK-1
def test_ait_separation_result_new_slots():
    r = AITSeparationResult()
    assert hasattr(r, "n_per_player")
    assert hasattr(r, "per_player_tremor_hz")
    assert hasattr(r, "per_player_roll_angle_deg")
    assert hasattr(r, "per_player_pitch_angle_deg")
    assert r.n_per_player == {}
    assert r.per_player_tremor_hz == {}
    assert r.per_player_roll_angle_deg == {}
    assert r.per_player_pitch_angle_deg == {}


# T235-DASH-SDK-2
def test_ait_separation_status_parses_per_player_fields():
    payload = {
        "ait_separation_enabled": True,
        "n_sessions": 37,
        "separation_ratio": 1.199,
        "all_pairs_above_1": True,
        "inter_player_mean": 1.682,
        "intra_player_mean": 0.520,
        "loo_accuracy": 0.667,
        "n_per_player": {"P1": 13, "P2": 10, "P3": 14},
        "per_player_tremor_hz": {"P1": 9.37, "P2": 1.71, "P3": 2.85},
        "per_player_roll_angle_deg": {"P1": 36.87, "P2": 60.1, "P3": 25.0},
        "per_player_pitch_angle_deg": {"P1": 18.19, "P2": 45.6, "P3": 36.9},
    }

    mock_resp = MagicMock()
    mock_resp.read.return_value = json.dumps(payload).encode()
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = MagicMock(return_value=False)

    with patch("urllib.request.urlopen", return_value=mock_resp):
        client = VAPIAITSeparation("http://localhost:8080", "test_key")
        result = client.status()

    assert result.n_per_player == {"P1": 13, "P2": 10, "P3": 14}
    assert result.per_player_tremor_hz["P1"] == pytest.approx(9.37)
    assert result.per_player_tremor_hz["P3"] == pytest.approx(2.85)
    assert result.per_player_roll_angle_deg["P1"] == pytest.approx(36.87)
    assert result.per_player_pitch_angle_deg["P2"] == pytest.approx(45.6)


# T235-DASH-SDK-3
def test_grind_analytics_result_new_slots():
    r = GrindAnalyticsResult()
    assert hasattr(r, "last_validation_ts")
    assert hasattr(r, "last_stamp_ts")
    assert r.last_validation_ts == 0.0
    assert r.last_stamp_ts == 0.0


# T235-DASH-SDK-4
def test_grind_analytics_status_parses_timestamps():
    payload = {
        "grind_session_id": "grind_phase235_v1",
        "total_validated": 22,
        "stamped_count": 12,
        "success_rate": 0.545,
        "blocking_reason_counts": {"MENU_DETECTED": 4},
        "sessions_per_day": 3.2,
        "projected_gic100_date": "2026-05-20",
        "last_validation_ts": 1714000100.0,
        "last_stamp_ts": 1714000050.0,
        "timestamp": 1714000200.0,
    }

    mock_resp = MagicMock()
    mock_resp.read.return_value = json.dumps(payload).encode()
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = MagicMock(return_value=False)

    with patch("urllib.request.urlopen", return_value=mock_resp):
        client = VAPIGrindAnalytics("http://localhost:8080", "test_key")
        result = client.status()

    assert result.last_validation_ts == pytest.approx(1714000100.0)
    assert result.last_stamp_ts == pytest.approx(1714000050.0)
    assert result.stamped_count == 12
