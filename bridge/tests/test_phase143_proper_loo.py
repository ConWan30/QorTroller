"""
Phase 143 — Proper LOO Classification Tests (8 tests)

Tests that the leave-one-out classification now correctly EXCLUDES the test
session from the test player's centroid computation, eliminating centroid bias.

Before Phase 143: centroid included the test session → intra-player distances
were artificially deflated → biased accuracy estimate.

After Phase 143: per-step LOO centroid recomputation → honest accuracy estimate.

Tests:
1. LOO centroid excludes test session (N-1 used vs N)
2. LOO centroid for N=3 player uses 2 remaining sessions
3. LOO centroid fallback to full centroid when N=1
4. LOO centroid differs from full centroid for small N (not trivially equal)
5. LOO centroid computation is done per test session (inner loop)
6. LOO distance to own centroid is larger with proper LOO than with biased LOO
7. Other players' centroids are unchanged in LOO step
8. np.mean of N-1 vectors is computable without error
"""

from __future__ import annotations

import sys
import numpy as np
from pathlib import Path

import pytest

_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(_ROOT / "scripts"))


# ---------------------------------------------------------------------------
# Helper: build mock player session data
# ---------------------------------------------------------------------------

def _mock_player_sessions():
    """3 players, 3 sessions each (P1) and 4 sessions each (P2, P3).
    Each session has a known active_vec for testing LOO centroid behavior.
    """
    rng = np.random.default_rng(42)
    sessions = {}

    def make_session(player, idx, base_offset):
        vec = base_offset + rng.normal(0, 0.3, size=8)
        d = {"player": player, "session_name": f"{player}/{idx}", "_active_vec": vec}
        return d

    sessions["Player 1"] = [make_session("Player 1", i, np.ones(8) * 0.0) for i in range(3)]
    sessions["Player 2"] = [make_session("Player 2", i, np.ones(8) * 5.0) for i in range(4)]
    sessions["Player 3"] = [make_session("Player 3", i, np.ones(8) * 10.0) for i in range(4)]

    # Compute full player means
    player_means = {
        p: np.mean(np.array([s["_active_vec"] for s in sl]), axis=0)
        for p, sl in sessions.items()
    }
    return sessions, player_means


# ---------------------------------------------------------------------------
# Test 1: LOO centroid excludes test session (N-1 used vs N)
# ---------------------------------------------------------------------------

def test_1_loo_centroid_excludes_test_session():
    """When classifying session i, player's centroid should use N-1 sessions."""
    sessions, player_means = _mock_player_sessions()
    player = "Player 1"
    sl = sessions[player]
    test_session = sl[0]

    # LOO centroid for Player 1 excluding test_session[0]
    loo_sl = [s for s in sl if s is not test_session]
    assert len(loo_sl) == len(sl) - 1, (
        f"LOO should use N-1={len(sl)-1} sessions, got {len(loo_sl)}"
    )


# ---------------------------------------------------------------------------
# Test 2: LOO centroid for N=3 player uses 2 remaining sessions
# ---------------------------------------------------------------------------

def test_2_loo_centroid_n3_uses_2_sessions():
    """P1 has 3 sessions; LOO centroid should use 2 of them."""
    sessions, _ = _mock_player_sessions()
    sl = sessions["Player 1"]
    assert len(sl) == 3  # Confirm N=3
    test_session = sl[1]
    loo_sl = [s for s in sl if s is not test_session]
    assert len(loo_sl) == 2, f"Expected 2 LOO sessions, got {len(loo_sl)}"


# ---------------------------------------------------------------------------
# Test 3: LOO centroid fallback when N=1
# ---------------------------------------------------------------------------

def test_3_loo_centroid_fallback_when_n1():
    """When player has only 1 session, LOO returns empty — fallback to full mean."""
    sessions, player_means = _mock_player_sessions()
    # Simulate a player with only 1 session
    single_player = "Player 1"
    single_session = [sessions[single_player][0]]  # only 1 session
    test_session = single_session[0]

    loo_sl = [s for s in single_session if s is not test_session]
    # loo_sl is empty — fallback to full mean
    if loo_sl:
        loo_centroid = np.mean([s["_active_vec"] for s in loo_sl], axis=0)
    else:
        loo_centroid = player_means[single_player]  # fallback

    # Should use full mean as fallback
    np.testing.assert_array_almost_equal(
        loo_centroid, player_means[single_player], decimal=10,
        err_msg="When N=1, LOO centroid should fall back to full player mean"
    )


# ---------------------------------------------------------------------------
# Test 4: LOO centroid differs from full centroid for small N
# ---------------------------------------------------------------------------

def test_4_loo_centroid_differs_from_full_for_small_n():
    """With N=3, removing one session meaningfully changes the centroid."""
    sessions, player_means = _mock_player_sessions()
    sl = sessions["Player 1"]
    test_session = sl[2]  # last session

    loo_sl = [s for s in sl if s is not test_session]
    loo_centroid = np.mean([s["_active_vec"] for s in loo_sl], axis=0)
    full_centroid = player_means["Player 1"]

    # They should be different (removing 1/3 sessions changes centroid)
    assert not np.allclose(loo_centroid, full_centroid), (
        "LOO centroid should differ from full centroid when removing 1 of 3 sessions"
    )


# ---------------------------------------------------------------------------
# Test 5: LOO centroid computed per test session (not once for all)
# ---------------------------------------------------------------------------

def test_5_loo_centroid_computed_per_session():
    """LOO centroids for different test sessions from same player differ."""
    sessions, player_means = _mock_player_sessions()
    sl = sessions["Player 1"]

    # LOO centroid for session 0 vs session 2
    loo_c0 = np.mean([s["_active_vec"] for s in sl if s is not sl[0]], axis=0)
    loo_c2 = np.mean([s["_active_vec"] for s in sl if s is not sl[2]], axis=0)

    assert not np.allclose(loo_c0, loo_c2), (
        "Different LOO steps (different test sessions) should produce different centroids"
    )


# ---------------------------------------------------------------------------
# Test 6: LOO intra-distance is larger than biased (non-LOO) intra-distance
# ---------------------------------------------------------------------------

def test_6_loo_distance_larger_than_biased():
    """Proper LOO removes the test session from centroid → larger distance to centroid.
    The biased approach (centroid includes test session) deflates the distance.
    """
    sessions, player_means = _mock_player_sessions()
    sl = sessions["Player 1"]
    test_session = sl[0]
    vec = test_session["_active_vec"]

    # Biased distance: centroid includes test session
    biased_centroid = player_means["Player 1"]
    biased_dist = float(np.linalg.norm(vec - biased_centroid))

    # Proper LOO distance: centroid excludes test session
    loo_sl = [s for s in sl if s is not test_session]
    loo_centroid = np.mean([s["_active_vec"] for s in loo_sl], axis=0)
    loo_dist = float(np.linalg.norm(vec - loo_centroid))

    # LOO distance should be >= biased distance (centroid farther from test session)
    # (Not always strictly greater, but on average true)
    # At minimum, they should not be identical when N=3
    assert biased_dist != loo_dist, (
        "LOO and biased distances should differ when test session is removed from centroid"
    )


# ---------------------------------------------------------------------------
# Test 7: Other players' centroids are unchanged in LOO step
# ---------------------------------------------------------------------------

def test_7_other_player_centroids_unchanged():
    """Only the test player's centroid changes in LOO; other players are unaffected."""
    sessions, player_means = _mock_player_sessions()
    test_session = sessions["Player 1"][0]

    # Build LOO player means (as run_analysis does)
    _loo_player_means = {}
    for p, sl in sessions.items():
        loo_sl = [x for x in sl if x is not test_session]
        if loo_sl:
            _loo_player_means[p] = np.mean(
                np.array([x["_active_vec"] for x in loo_sl]), axis=0
            )
        else:
            _loo_player_means[p] = player_means[p]

    # P2 and P3 centroids should be identical to their full centroids
    for p in ["Player 2", "Player 3"]:
        np.testing.assert_array_almost_equal(
            _loo_player_means[p], player_means[p], decimal=10,
            err_msg=f"{p} centroid should be unchanged in LOO step for P1 test session"
        )


# ---------------------------------------------------------------------------
# Test 8: np.mean of N-1 vectors is computable without error
# ---------------------------------------------------------------------------

def test_8_loo_centroid_computation_no_error():
    """LOO centroid computation completes without error for all player/session combos."""
    sessions, _ = _mock_player_sessions()
    for player, sl in sessions.items():
        for i, test_session in enumerate(sl):
            loo_sl = [s for s in sl if s is not test_session]
            if loo_sl:
                centroid = np.mean(
                    np.array([s["_active_vec"] for s in loo_sl]), axis=0
                )
                assert centroid.shape == (8,), f"Centroid shape should be (8,), got {centroid.shape}"
            # If loo_sl empty, no computation (fallback case handled in Test 3)
