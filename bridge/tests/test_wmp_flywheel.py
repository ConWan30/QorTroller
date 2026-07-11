"""WMP Two-Engines Flywheel (FLY-1) — breadth-gated read-only baseline tests.

The load-bearing safety: below the breadth floor it DEFERS; it never emits a
recommendation and never a threshold. At today's N=1 it defers.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from sdk.wmp_flywheel import corpus_baseline, MIN_BREADTH, STATUS_DEFERRED, STATUS_BASELINE


def _session(trigger=0.1, stick=0.99, buttons=17) -> list:
    """A minimal VDC claim-set for one session (only the fields the baseline reads)."""
    return [
        {"derivation_id": "TRIGGER_ENGAGEMENT_FRACTION_v1", "value": {"fraction": trigger}},
        {"derivation_id": "STICK_ENGAGEMENT_FRACTION_v1", "value": {"fraction": stick}},
        {"derivation_id": "BUTTON_PRESS_COUNT_v1", "value": {"press_events": buttons}},
    ]


def test_n1_defers_today():
    res = corpus_baseline([_session()])
    assert res["status"] == STATUS_DEFERRED
    assert res["n"] == 1
    assert res["baseline"] is None
    assert res["recommendation"] is None


def test_below_breadth_defers():
    res = corpus_baseline([_session() for _ in range(MIN_BREADTH - 1)])
    assert res["status"] == STATUS_DEFERRED
    assert res["recommendation"] is None


def test_at_breadth_emits_baseline_no_recommendation():
    sessions = [_session(trigger=0.05 + i * 0.01, buttons=10 + i) for i in range(MIN_BREADTH)]
    res = corpus_baseline(sessions)
    assert res["status"] == STATUS_BASELINE
    assert res["n"] == MIN_BREADTH
    b = res["baseline"]
    assert b["trigger_fraction"]["n"] == MIN_BREADTH
    assert b["trigger_fraction"]["min"] == 0.05
    assert b["button_press_events"]["max"] == 10 + MIN_BREADTH - 1
    # SAFETY: never a recommendation, never a threshold
    assert res["recommendation"] is None
    assert "threshold" not in res


def test_baseline_carries_only_stats_no_actionable_output():
    """Safety (structural): the baseline carries only descriptive stats
    (n/min/max/mean) — never a threshold key, never an actionable recommendation."""
    sessions = [_session() for _ in range(MIN_BREADTH)]
    res = corpus_baseline(sessions)
    assert res["recommendation"] is None
    for _feat, stats in res["baseline"].items():
        assert set(stats.keys()) == {"n", "min", "max", "mean"}
        assert "threshold" not in stats


def test_breadth_floor_is_declared():
    assert isinstance(MIN_BREADTH, int) and MIN_BREADTH >= 2
