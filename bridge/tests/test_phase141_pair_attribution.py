"""
Phase 141 — Per-Pair Feature Attribution Diagnostic Tests (8 tests)

Tests the _compute_pair_attribution() function that diagnoses covariance
suppression — the mechanism causing P1/P3 full Mahalanobis distance (0.127)
to be far below the diagonal approximation distance (3.925).

Key insight: suppression_ratio = full_mahalanobis / diagonal_distance.
When ratio << 1.0, the full covariance matrix is SUPPRESSING the true
per-feature differences — a small-N covariance estimation artifact.

Tests:
1. _compute_pair_attribution returns 'pair_attribution' key
2. All player pairs present in pair_attribution keys
3. Each pair has required keys: full_mahalanobis, diagonal_distance, suppression_ratio
4. suppression_ratio = full_mahalanobis / diagonal_distance (within tolerance)
5. top_features is sorted descending by std_diff
6. P1vP3 suppression_ratio < 0.1 (confirms covariance suppression from mock data)
7. diagonal_distance > full_mahalanobis when suppression < 1.0
8. per_feature_std_diff values are non-negative
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(_ROOT / "scripts"))


# ---------------------------------------------------------------------------
# Shared mock result (matches touchpad_corners analysis structure)
# ---------------------------------------------------------------------------

def _mock_result():
    return {
        "inter_distance_matrix": {
            "players": ["Player 1", "Player 2", "Player 3"],
            "values": [[0.0, 1.428, 0.127], [1.428, 0.0, 1.304], [0.127, 1.304, 0.0]],
        },
        "player_session_counts": {"Player 1": 3, "Player 2": 4, "Player 3": 4},
        "feature_player_means": {
            "touchpad_spatial_entropy": {"Player 1": 1.7478, "Player 2": 1.5598, "Player 3": 0.9829},
            "touch_position_variance":  {"Player 1": 0.0465, "Player 2": 0.0352, "Player 3": 0.0163},
            "micro_tremor_accel_variance": {"Player 1": 2942.3, "Player 2": 7123.3, "Player 3": 3306.8},
        },
        "feature_player_stds": {
            "touchpad_spatial_entropy": {"Player 1": 0.30, "Player 2": 0.15, "Player 3": 0.12},
            "touch_position_variance":  {"Player 1": 0.02, "Player 2": 0.01, "Player 3": 0.008},
            "micro_tremor_accel_variance": {"Player 1": 800, "Player 2": 1200, "Player 3": 600},
        },
        "active_feature_names": [
            "touchpad_spatial_entropy", "touch_position_variance", "micro_tremor_accel_variance",
        ],
    }


# ---------------------------------------------------------------------------
# Test 1: _compute_pair_attribution returns 'pair_attribution' key
# ---------------------------------------------------------------------------

def test_1_returns_pair_attribution_key():
    from analyze_interperson_separation import _compute_pair_attribution
    result = _compute_pair_attribution(_mock_result())
    assert "pair_attribution" in result, "Must return 'pair_attribution' key"


# ---------------------------------------------------------------------------
# Test 2: All player pairs present in pair_attribution keys
# ---------------------------------------------------------------------------

def test_2_all_player_pairs_present():
    from analyze_interperson_separation import _compute_pair_attribution
    result = _compute_pair_attribution(_mock_result())
    pairs = result["pair_attribution"]
    expected = {"Player 1 vs Player 2", "Player 1 vs Player 3", "Player 2 vs Player 3"}
    assert set(pairs.keys()) == expected, f"Expected pairs {expected}, got {set(pairs.keys())}"


# ---------------------------------------------------------------------------
# Test 3: Each pair has required keys
# ---------------------------------------------------------------------------

def test_3_each_pair_has_required_keys():
    from analyze_interperson_separation import _compute_pair_attribution
    result = _compute_pair_attribution(_mock_result())
    required = {"full_mahalanobis", "diagonal_distance", "suppression_ratio",
                "top_features", "per_feature_std_diff"}
    for pair_key, data in result["pair_attribution"].items():
        missing = required - set(data.keys())
        assert not missing, f"Pair '{pair_key}' missing keys: {missing}"


# ---------------------------------------------------------------------------
# Test 4: suppression_ratio = full_mahalanobis / diagonal_distance
# ---------------------------------------------------------------------------

def test_4_suppression_ratio_formula():
    from analyze_interperson_separation import _compute_pair_attribution
    result = _compute_pair_attribution(_mock_result())
    for pair_key, data in result["pair_attribution"].items():
        full_d = data["full_mahalanobis"]
        diag_d = data["diagonal_distance"]
        supp   = data["suppression_ratio"]
        if diag_d > 1e-9:
            expected = full_d / diag_d
            assert abs(supp - expected) < 0.001, (
                f"Pair '{pair_key}': suppression_ratio={supp:.4f} != "
                f"full/diag={expected:.4f}"
            )


# ---------------------------------------------------------------------------
# Test 5: top_features sorted descending by std_diff
# ---------------------------------------------------------------------------

def test_5_top_features_sorted_descending():
    from analyze_interperson_separation import _compute_pair_attribution
    result = _compute_pair_attribution(_mock_result())
    for pair_key, data in result["pair_attribution"].items():
        top = data["top_features"]
        diffs = [d for _, d in top]
        assert diffs == sorted(diffs, reverse=True), (
            f"Pair '{pair_key}': top_features not sorted descending: {diffs}"
        )


# ---------------------------------------------------------------------------
# Test 6: P1vP3 suppression_ratio < 0.1 (covariance suppression confirmed)
# ---------------------------------------------------------------------------

def test_6_p1vp3_suppression_ratio_below_threshold():
    from analyze_interperson_separation import _compute_pair_attribution
    result = _compute_pair_attribution(_mock_result())
    data = result["pair_attribution"]["Player 1 vs Player 3"]
    assert data["suppression_ratio"] < 0.1, (
        f"P1 vs P3 suppression_ratio={data['suppression_ratio']:.4f} should be < 0.1. "
        "This confirms the covariance suppression artifact that causes low Mahalanobis distance "
        "despite large per-feature differences."
    )


# ---------------------------------------------------------------------------
# Test 7: diagonal_distance > full_mahalanobis when suppression < 1.0
# ---------------------------------------------------------------------------

def test_7_diagonal_gt_full_when_suppressed():
    from analyze_interperson_separation import _compute_pair_attribution
    result = _compute_pair_attribution(_mock_result())
    for pair_key, data in result["pair_attribution"].items():
        if data["suppression_ratio"] < 1.0:
            assert data["diagonal_distance"] > data["full_mahalanobis"], (
                f"Pair '{pair_key}': when suppression < 1.0, "
                f"diagonal ({data['diagonal_distance']}) should exceed "
                f"full ({data['full_mahalanobis']})"
            )


# ---------------------------------------------------------------------------
# Test 8: per_feature_std_diff values are non-negative
# ---------------------------------------------------------------------------

def test_8_per_feature_std_diff_nonnegative():
    from analyze_interperson_separation import _compute_pair_attribution
    result = _compute_pair_attribution(_mock_result())
    for pair_key, data in result["pair_attribution"].items():
        for fn, sd in data["per_feature_std_diff"].items():
            assert sd >= 0.0, (
                f"Pair '{pair_key}', feature '{fn}': std_diff={sd:.4f} is negative. "
                "Standardized mean differences must be non-negative (using abs)."
            )
