"""WMP UC-15 self-analytics tests. The gamer's OWN verified history, self-view only. Pins the streak /
cadence / authored-progression math + the hard ceiling rails (no cross-player comparison, advisory,
developer_self). poep/chain untouched.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from bridge.vapi_bridge.wmp.self_analytics import (
    SCHEMA,
    compute_authored_progression,
    compute_clean_streaks,
    compute_self_analytics,
    compute_session_cadence,
)

_NS_PER_DAY = 86_400 * 1_000_000_000


def test_clean_streaks_with_breaks():
    # clean, clean, BREAK, clean, clean, clean  -> current=3 (trailing), max=3, segments=[2,3]
    s = compute_clean_streaks([True, True, False, True, True, True])
    assert s["current_clean_streak"] == 3
    assert s["max_clean_streak"] == 3
    assert s["streak_segments"] == [2, 3]
    assert s["total_clean_sessions"] == 5
    assert s["total_sessions"] == 6
    assert s["clean_rate"] == round(5 / 6, 4)


def test_clean_streaks_trailing_break_zeroes_current():
    s = compute_clean_streaks([True, True, True, False])
    assert s["current_clean_streak"] == 0        # last session broke the streak
    assert s["max_clean_streak"] == 3


def test_clean_streaks_empty():
    s = compute_clean_streaks([])
    assert s["current_clean_streak"] == 0 and s["max_clean_streak"] == 0 and s["clean_rate"] == 0.0


def test_session_cadence_multi_day():
    base = 1_700_000_000 * 1_000_000_000
    ts = [base, base + 3600 * 10**9, base + _NS_PER_DAY, base + 2 * _NS_PER_DAY]  # 3 distinct days
    c = compute_session_cadence(ts)
    assert c["total_sessions"] == 4
    assert c["active_days"] == 3
    assert c["sessions_per_active_day"] == round(4 / 3, 2)
    assert c["first_ts_ns"] == base and c["last_ts_ns"] == base + 2 * _NS_PER_DAY


def test_session_cadence_empty():
    c = compute_session_cadence([])
    assert c["total_sessions"] == 0 and c["active_days"] == 0 and c["first_ts_ns"] is None


def test_authored_progression():
    a = compute_authored_progression([3, 0, 5, 2])
    assert a["authored_total"] == 10
    assert a["cumulative"] == [3, 3, 8, 10]
    assert a["matches"] == 4
    assert a["best_match"] == 5
    assert a["authored_per_match_mean"] == 2.5


def test_authored_progression_clamps_negatives():
    a = compute_authored_progression([-1, 4])
    assert a["per_match"] == [0, 4] and a["authored_total"] == 4


def test_self_analytics_assembles_with_honest_ceiling():
    r = compute_self_analytics(
        clean_flags=[True, True, False, True],
        session_timestamps_ns=[1_700_000_000 * 10**9, 1_700_000_000 * 10**9 + _NS_PER_DAY],
        authored_per_match=[2, 3],
    )
    assert r["schema"] == SCHEMA
    # the hard rails are present and correct
    assert r["self_view_only"] is True
    assert r["cross_player_comparison"] is False
    assert r["population_certified"] is False
    assert r["advisory"] is True
    assert r["scope"] == "developer_self"
    assert "no cross-player comparison" in r["note"].lower()
    # sections wired
    assert r["clean_streaks"]["total_sessions"] == 4
    assert r["authored_kills"]["authored_total"] == 5


def test_current_streak_override_wins():
    # the authoritative live GIC chain length overrides a partial-log trailing run
    r = compute_self_analytics(clean_flags=[True], session_timestamps_ns=[1], current_streak_override=42)
    assert r["clean_streaks"]["current_clean_streak"] == 42


def test_no_comparison_or_rank_data_leaks():
    # ceiling guard: no rank/comparison DATA may appear. The "note" legitimately DISCLAIMS these in prose,
    # so guard the data sections + flags, not the disclaimer. Word-boundary match ("elo" must not hit
    # "devELOper").
    import json
    import re
    r = compute_self_analytics(clean_flags=[True, True], session_timestamps_ns=[1, 2], authored_per_match=[1])
    data = {k: v for k, v in r.items() if k != "note"}
    blob = json.dumps(data).lower()
    for banned in ("percentile", "rank", "leaderboard", "versus", "vs_other", "best_player", "elo"):
        assert re.search(r"\b" + re.escape(banned) + r"\b", blob) is None, f"leaked: {banned}"
    assert r["cross_player_comparison"] is False
