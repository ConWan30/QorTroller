"""
Phase 216 SDK Tests
T216-SDK-1..4: PerPairGapResult / VAPIPerPairGap
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "sdk"))


# ── T216-SDK-1: PerPairGapResult has required slots ──────────────────────────
def test_T216_sdk_1_dataclass_fields():
    """PerPairGapResult has required slots (Phase 216)."""
    from vapi_sdk import PerPairGapResult
    import dataclasses
    fields = {f.name for f in dataclasses.fields(PerPairGapResult)}
    assert "per_pair_gap_log_enabled" in fields
    assert "all_pairs_above_1"       in fields
    assert "pair_count"              in fields
    assert "pairs"                   in fields
    assert "blocker_pairs"           in fields
    assert "error"                   in fields


# ── T216-SDK-2: PerPairGapResult instantiation ───────────────────────────────
def test_T216_sdk_2_result_instantiation():
    """PerPairGapResult can be created with pair data."""
    from vapi_sdk import PerPairGapResult
    pairs = [
        {"pair_key": "P1vP3", "player_i": "P1", "player_j": "P3",
         "distance": 0.032, "above_1_0": False},
    ]
    r = PerPairGapResult(
        per_pair_gap_log_enabled = True,
        all_pairs_above_1        = False,
        pair_count               = 1,
        pairs                    = pairs,
        blocker_pairs            = pairs,
    )
    assert r.per_pair_gap_log_enabled is True
    assert r.all_pairs_above_1 is False
    assert r.pair_count == 1
    assert len(r.pairs) == 1
    assert r.pairs[0]["pair_key"] == "P1vP3"
    assert r.error is None


# ── T216-SDK-3: VAPIPerPairGap returns error on network failure ───────────────
def test_T216_sdk_3_client_network_error():
    """VAPIPerPairGap returns PerPairGapResult with error on connection failure."""
    from vapi_sdk import VAPIPerPairGap, PerPairGapResult
    client = VAPIPerPairGap("http://localhost:19999", api_key="test")
    result = client.get_status()
    assert isinstance(result, PerPairGapResult)
    assert result.error is not None
    assert result.all_pairs_above_1 is False
    assert result.per_pair_gap_log_enabled is False


# ── T216-SDK-4: VAPIPerPairGap.get_status() parses response ──────────────────
def test_T216_sdk_4_get_status_parses_response():
    """VAPIPerPairGap.get_status() parses all fields from a 200 response."""
    import json
    from unittest.mock import MagicMock, patch
    from vapi_sdk import VAPIPerPairGap, PerPairGapResult

    pairs = [
        {"pair_key": "P1vP2", "player_i": "P1", "player_j": "P2",
         "distance": 1.133, "above_1_0": True, "n_sessions_i": 12, "n_sessions_j": 12},
        {"pair_key": "P1vP3", "player_i": "P1", "player_j": "P3",
         "distance": 0.032, "above_1_0": False, "n_sessions_i": 12, "n_sessions_j": 10},
        {"pair_key": "P2vP3", "player_i": "P2", "player_j": "P3",
         "distance": 0.401, "above_1_0": False, "n_sessions_i": 12, "n_sessions_j": 10},
    ]
    blockers = [p for p in pairs if not p["above_1_0"]]
    body = json.dumps({
        "per_pair_gap_log_enabled": True,
        "all_pairs_above_1":        False,
        "pairs":                    pairs,
        "blocker_pairs":            blockers,
        "pair_count":               3,
        "session_type":             "2026-04-16",
        "timestamp":                1712400000.0,
    }).encode()

    mock_resp = MagicMock()
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = MagicMock(return_value=False)
    mock_resp.read.return_value = body

    with patch("urllib.request.urlopen", return_value=mock_resp):
        client = VAPIPerPairGap("http://localhost:8080", api_key="test")
        result = client.get_status()

    assert isinstance(result, PerPairGapResult)
    assert result.per_pair_gap_log_enabled is True
    assert result.all_pairs_above_1 is False
    assert result.pair_count == 3
    assert len(result.pairs) == 3
    assert len(result.blocker_pairs) == 2
    assert result.error is None
