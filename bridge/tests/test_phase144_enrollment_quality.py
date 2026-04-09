"""
Phase 144 — Per-Player Enrollment Quality Tests (8 tests)

Tests that _compute_player_quality_scores() correctly evaluates biometric
enrollment readiness per player using centroid_stability and n_probe_types.

Constants:
  ENROLLMENT_STABILITY_THRESHOLD = 0.70
  ENROLLMENT_MIN_PROBE_TYPES = 2

Tests:
1. _compute_player_quality_scores() function exists and is callable
2. Returns player_quality dict keyed by player name
3. Returns enrollment_ready_count and enrollment_total_players int fields
4. centroid_stability matches intra-player mean Euclidean distance to centroid
5. Player with high centroid_stability (> 0.70) is not enrollment-ready
6. Player with tight cluster (stability < 0.70, probe_types >= 2) is enrollment-ready
7. n_probe_types is count of distinct session types (from session_details)
8. recommendations list is non-empty when player is not enrollment-ready
"""

from __future__ import annotations

import sys
import numpy as np
from pathlib import Path

import pytest

_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(_ROOT / "scripts"))


# ---------------------------------------------------------------------------
# Import the function under test
# ---------------------------------------------------------------------------

def _import_quality_fn():
    from analyze_interperson_separation import _compute_player_quality_scores
    return _compute_player_quality_scores


# ---------------------------------------------------------------------------
# Helper: build a mock result dict similar to run_analysis() output
# ---------------------------------------------------------------------------

def _mock_result(p1_mean=2.9, p2_mean=0.5, p3_mean=0.4, session_type_filter="touchpad_corners"):
    """Build a minimal result dict as _compute_player_quality_scores() expects."""
    rng = np.random.default_rng(42)

    def make_intra_stats(mean_val, n=3):
        # intra_player_stats keys used: mean, std, n_sessions
        return {
            "mean": mean_val,
            "std": mean_val * 0.2,
            "n_sessions": n,
            "median": mean_val,
            "range": [mean_val * 0.7, mean_val * 1.3],
        }

    return {
        "intra_player_stats": {
            "Player 1": make_intra_stats(p1_mean, n=3),
            "Player 2": make_intra_stats(p2_mean, n=4),
            "Player 3": make_intra_stats(p3_mean, n=4),
        },
        "player_session_counts": {"Player 1": 3, "Player 2": 4, "Player 3": 4},
        "session_type_filter": session_type_filter,
        "session_details": [],
    }


def _mock_result_no_filter():
    """Result dict with no session_type_filter — uses session_details for probe types."""
    rng = np.random.default_rng(42)
    session_details = [
        # Player 1: 2 probe types
        {"player": "Player 1", "session": "terminal_cal_P1/touchpad_corners_20260327T031241Z"},
        {"player": "Player 1", "session": "terminal_cal_P1/touchpad_freeform_20260327T030955Z"},
        {"player": "Player 1", "session": "terminal_cal_P1/touchpad_swipes_20260327T030742Z"},
        # Player 2: 1 probe type
        {"player": "Player 2", "session": "terminal_cal_P2/touchpad_corners_20260328T003556Z"},
        {"player": "Player 2", "session": "terminal_cal_P2/touchpad_corners_20260328T153820Z"},
    ]
    return {
        "intra_player_stats": {
            "Player 1": {"mean": 0.4, "std": 0.1, "n_sessions": 3},
            "Player 2": {"mean": 0.5, "std": 0.1, "n_sessions": 2},
        },
        "player_session_counts": {"Player 1": 3, "Player 2": 2},
        "session_type_filter": None,  # No filter — use session_details
        "session_details": session_details,
    }


# ---------------------------------------------------------------------------
# Test 1: Function exists and is callable
# ---------------------------------------------------------------------------

def test_1_function_exists():
    """_compute_player_quality_scores() is importable and callable."""
    fn = _import_quality_fn()
    assert callable(fn), "_compute_player_quality_scores should be callable"


# ---------------------------------------------------------------------------
# Test 2: Returns player_quality dict keyed by player name
# ---------------------------------------------------------------------------

def test_2_returns_player_quality_dict():
    """Return value contains player_quality dict keyed by player name."""
    fn = _import_quality_fn()
    result = fn(_mock_result())
    assert "player_quality" in result, "Should return 'player_quality' key"
    pq = result["player_quality"]
    assert isinstance(pq, dict), "player_quality should be a dict"
    for player in ["Player 1", "Player 2", "Player 3"]:
        assert player in pq, f"{player} should be a key in player_quality"


# ---------------------------------------------------------------------------
# Test 3: Returns enrollment_ready_count and enrollment_total_players
# ---------------------------------------------------------------------------

def test_3_returns_count_fields():
    """Return value has enrollment_ready_count (int) and enrollment_total_players (int)."""
    fn = _import_quality_fn()
    result = fn(_mock_result())
    assert "enrollment_ready_count" in result, "Should return 'enrollment_ready_count'"
    assert "enrollment_total_players" in result, "Should return 'enrollment_total_players'"
    assert isinstance(result["enrollment_ready_count"], int)
    assert isinstance(result["enrollment_total_players"], int)
    assert result["enrollment_total_players"] == 3, "Should have 3 players"


# ---------------------------------------------------------------------------
# Test 4: centroid_stability matches intra_player_stats mean
# ---------------------------------------------------------------------------

def test_4_centroid_stability_matches_intra_mean():
    """centroid_stability should equal intra_player_stats mean for each player."""
    fn = _import_quality_fn()
    res = _mock_result(p1_mean=2.963, p2_mean=1.976, p3_mean=1.711)
    quality = fn(res)
    pq = quality["player_quality"]
    # centroid_stability is rounded to 4 decimal places
    assert abs(pq["Player 1"]["centroid_stability"] - 2.963) < 0.001
    assert abs(pq["Player 2"]["centroid_stability"] - 1.976) < 0.001
    assert abs(pq["Player 3"]["centroid_stability"] - 1.711) < 0.001


# ---------------------------------------------------------------------------
# Test 5: High centroid_stability (> 0.70) → not enrollment-ready
# ---------------------------------------------------------------------------

def test_5_high_stability_not_enrollment_ready():
    """Player with centroid_stability > ENROLLMENT_STABILITY_THRESHOLD is not ready."""
    fn = _import_quality_fn()
    # P1 has stability 2.963 >> 0.70
    res = _mock_result(p1_mean=2.963, p2_mean=2.0, p3_mean=2.0)
    quality = fn(res)
    pq = quality["player_quality"]
    assert pq["Player 1"]["enrollment_ready"] is False, (
        "Player 1 with stability=2.963 > threshold=0.70 should NOT be enrollment-ready"
    )


# ---------------------------------------------------------------------------
# Test 6: Tight cluster (stability < 0.70, n_probe_types >= 2) → enrollment-ready
# ---------------------------------------------------------------------------

def test_6_tight_cluster_enrollment_ready():
    """Player with centroid_stability < 0.70 and enough probe types is enrollment-ready."""
    fn = _import_quality_fn()
    # Use session_type_filter=None so n_probe_types is computed from session_details
    # OR use filter with stability < 0.70 but must have n_probe_types >= 2
    # With session_type_filter set, n_probe_types=1 — player won't be ready even with low stability.
    # So test with no filter and 2+ probe types.
    res = _mock_result_no_filter()
    # Player 1 has stability=0.4 < 0.70 and 3 probe types >= 2 → should be ready
    quality = fn(res)
    pq = quality["player_quality"]
    assert pq["Player 1"]["enrollment_ready"] is True, (
        "Player 1 with stability=0.4 < 0.70 and n_probe_types=3 >= 2 should be enrollment-ready"
    )


# ---------------------------------------------------------------------------
# Test 7: n_probe_types counts distinct session types from session_details
# ---------------------------------------------------------------------------

def test_7_n_probe_types_from_session_details():
    """n_probe_types counts distinct non-gameplay session types in session_details."""
    fn = _import_quality_fn()
    res = _mock_result_no_filter()
    quality = fn(res)
    pq = quality["player_quality"]
    # Player 1 has corners + freeform + swipes = 3 distinct types
    assert pq["Player 1"]["n_probe_types"] == 3, (
        f"Player 1 should have 3 probe types, got {pq['Player 1']['n_probe_types']}"
    )
    # Player 2 has only corners = 1 distinct type
    assert pq["Player 2"]["n_probe_types"] == 1, (
        f"Player 2 should have 1 probe type, got {pq['Player 2']['n_probe_types']}"
    )


# ---------------------------------------------------------------------------
# Test 8: recommendations non-empty when not enrollment-ready
# ---------------------------------------------------------------------------

def test_8_recommendations_when_not_ready():
    """Players not enrollment-ready should have non-empty recommendations list."""
    fn = _import_quality_fn()
    # P1 has high stability → not ready → should have recommendations
    res = _mock_result(p1_mean=2.963, p2_mean=2.0, p3_mean=2.0)
    quality = fn(res)
    pq = quality["player_quality"]
    for player in ["Player 1", "Player 2", "Player 3"]:
        if not pq[player]["enrollment_ready"]:
            assert len(pq[player]["recommendations"]) > 0, (
                f"{player} is not enrollment-ready but has empty recommendations"
            )
