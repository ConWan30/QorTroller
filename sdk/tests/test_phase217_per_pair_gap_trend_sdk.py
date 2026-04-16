"""
Phase 217 SDK Tests
T217-SDK-1..4: PerPairGapTrendResult / VAPIPerPairGapTrend
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "sdk"))


# ── T217-SDK-1: PerPairGapTrendResult has required slots ─────────────────────
def test_T217_sdk_1_dataclass_fields():
    """PerPairGapTrendResult has required slots (Phase 217)."""
    from vapi_sdk import PerPairGapTrendResult
    import dataclasses
    fields = {f.name for f in dataclasses.fields(PerPairGapTrendResult)}
    assert "per_pair_gap_trend_enabled" in fields
    assert "pair_key"                   in fields
    assert "distances"                  in fields
    assert "velocity_per_day"           in fields
    assert "trend"                      in fields
    assert "n_runs"                     in fields
    assert "blocker_resolved"           in fields
    assert "error"                      in fields


# ── T217-SDK-2: PerPairGapTrendResult instantiation ──────────────────────────
def test_T217_sdk_2_result_instantiation():
    """PerPairGapTrendResult can be created with trend data."""
    from vapi_sdk import PerPairGapTrendResult
    r = PerPairGapTrendResult(
        per_pair_gap_trend_enabled = True,
        pair_key                   = "P1vP3",
        distances                  = [0.032, 0.200],
        velocity_per_day           = -0.056,
        trend                      = "WORSENING",
        n_runs                     = 2,
        blocker_resolved           = False,
    )
    assert r.per_pair_gap_trend_enabled is True
    assert r.pair_key == "P1vP3"
    assert len(r.distances) == 2
    assert abs(r.velocity_per_day - (-0.056)) < 1e-9
    assert r.trend == "WORSENING"
    assert r.blocker_resolved is False
    assert r.error is None


# ── T217-SDK-3: VAPIPerPairGapTrend returns error on network failure ──────────
def test_T217_sdk_3_client_network_error():
    """VAPIPerPairGapTrend returns PerPairGapTrendResult with error on connection failure."""
    from vapi_sdk import VAPIPerPairGapTrend, PerPairGapTrendResult
    client = VAPIPerPairGapTrend("http://localhost:19999", api_key="test")
    result = client.get_trend(pair_key="P1vP3")
    assert isinstance(result, PerPairGapTrendResult)
    assert result.error is not None
    assert result.trend == "UNKNOWN"
    assert result.per_pair_gap_trend_enabled is False


# ── T217-SDK-4: VAPIPerPairGapTrend.get_trend() parses response ───────────────
def test_T217_sdk_4_get_trend_parses_response():
    """VAPIPerPairGapTrend.get_trend() parses all fields from a 200 response."""
    import json
    from unittest.mock import MagicMock, patch
    from vapi_sdk import VAPIPerPairGapTrend, PerPairGapTrendResult

    body = json.dumps({
        "per_pair_gap_trend_enabled": True,
        "pair_key":                   "P1vP3",
        "distances":                  [0.032, 0.200],
        "velocity_per_day":           -0.056,
        "trend":                      "WORSENING",
        "n_runs":                     2,
        "blocker_resolved":           False,
        "timestamp":                  1712400000.0,
    }).encode()

    mock_resp = MagicMock()
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = MagicMock(return_value=False)
    mock_resp.read.return_value = body

    with patch("urllib.request.urlopen", return_value=mock_resp):
        client = VAPIPerPairGapTrend("http://localhost:8080", api_key="test")
        result = client.get_trend(pair_key="P1vP3")

    assert isinstance(result, PerPairGapTrendResult)
    assert result.per_pair_gap_trend_enabled is True
    assert result.pair_key == "P1vP3"
    assert result.trend == "WORSENING"
    assert len(result.distances) == 2
    assert result.blocker_resolved is False
    assert result.error is None
