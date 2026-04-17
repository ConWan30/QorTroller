"""
Phase 219 SDK Tests
T219-SDK-1..4: TournamentBlockerSummaryResult / VAPITournamentBlockerSummary
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "sdk"))


# ── T219-SDK-1: TournamentBlockerSummaryResult has required slots ─────────────
def test_T219_sdk_1_dataclass_fields():
    """TournamentBlockerSummaryResult has required slots (Phase 219)."""
    from vapi_sdk import TournamentBlockerSummaryResult
    import dataclasses
    fields = {f.name for f in dataclasses.fields(TournamentBlockerSummaryResult)}
    assert "tournament_blocker_summary_enabled" in fields
    assert "total_blockers"                     in fields
    assert "blockers"                           in fields
    assert "overall_blocked"                    in fields
    assert "preflight_pass"                     in fields
    assert "capture_healthy"                    in fields
    assert "all_pairs_above_1"                  in fields
    assert "error"                              in fields


# ── T219-SDK-2: TournamentBlockerSummaryResult instantiation ─────────────────
def test_T219_sdk_2_result_instantiation():
    """TournamentBlockerSummaryResult can be created with blocker data."""
    from vapi_sdk import TournamentBlockerSummaryResult
    blockers = [
        {"source": "per_pair_gap", "key": "P1vP3", "detail": "distance=0.032", "severity": "P0"},
    ]
    r = TournamentBlockerSummaryResult(
        tournament_blocker_summary_enabled = True,
        total_blockers                     = 1,
        blockers                           = blockers,
        overall_blocked                    = True,
        preflight_pass                     = False,
        capture_healthy                    = False,
        all_pairs_above_1                  = False,
    )
    assert r.tournament_blocker_summary_enabled is True
    assert r.total_blockers == 1
    assert len(r.blockers) == 1
    assert r.overall_blocked is True
    assert r.error is None


# ── T219-SDK-3: VAPITournamentBlockerSummary returns error on network failure ──
def test_T219_sdk_3_client_network_error():
    """VAPITournamentBlockerSummary returns result with error on connection failure."""
    from vapi_sdk import VAPITournamentBlockerSummary, TournamentBlockerSummaryResult
    client = VAPITournamentBlockerSummary("http://localhost:19999", api_key="test")
    result = client.get_summary()
    assert isinstance(result, TournamentBlockerSummaryResult)
    assert result.error is not None
    assert result.overall_blocked is True
    assert result.tournament_blocker_summary_enabled is False


# ── T219-SDK-4: VAPITournamentBlockerSummary.get_summary() parses response ────
def test_T219_sdk_4_get_summary_parses_response():
    """VAPITournamentBlockerSummary.get_summary() parses all fields from a 200 response."""
    import json
    from unittest.mock import MagicMock, patch
    from vapi_sdk import VAPITournamentBlockerSummary, TournamentBlockerSummaryResult

    blockers = [
        {"source": "per_pair_gap", "key": "P1vP3", "detail": "distance=0.032 < 1.0", "severity": "P0"},
        {"source": "per_pair_gap", "key": "P2vP3", "detail": "distance=0.401 < 1.0", "severity": "P0"},
    ]
    body = json.dumps({
        "tournament_blocker_summary_enabled": True,
        "total_blockers":                     2,
        "blockers":                           blockers,
        "overall_blocked":                    True,
        "preflight_pass":                     False,
        "capture_healthy":                    False,
        "all_pairs_above_1":                  False,
        "timestamp":                          1712400000.0,
    }).encode()

    mock_resp = MagicMock()
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = MagicMock(return_value=False)
    mock_resp.read.return_value = body

    with patch("urllib.request.urlopen", return_value=mock_resp):
        client = VAPITournamentBlockerSummary("http://localhost:8080", api_key="test")
        result = client.get_summary()

    assert isinstance(result, TournamentBlockerSummaryResult)
    assert result.tournament_blocker_summary_enabled is True
    assert result.total_blockers == 2
    assert len(result.blockers) == 2
    assert result.overall_blocked is True
    assert result.all_pairs_above_1 is False
    assert result.error is None
