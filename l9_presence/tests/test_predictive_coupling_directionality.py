"""LUMEN-3 / N5 increment 2 - lag DIRECTIONALITY (TRL-1 A1) tests.

Proves the metric SEPARATES on synthetic classes (the ladder's first rung):
genuine causal lag (input precedes screen) -> DIR_CAUSAL; replay/precognition
(screen precedes input) -> DIR_NONCAUSAL. The real decoupled class is card-gated.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from l9_presence.predictive_coupling import (
    channel_directionality_stats, assess_directionality,
    DIR_CAUSAL, DIR_NONCAUSAL, INSUFFICIENT, LEAD_EPS_MS,
)


def _wins(channel, lag_ms, n=12, coupling=0.5):
    return [{"channel": channel, "coupling": coupling, "lag_ms": lag_ms} for _ in range(n)]


# -- metric --------------------------------------------------------------------

def test_causal_lag_is_dir_causal():
    st = channel_directionality_stats(_wins("b1_flash", 100.0), "b1_flash")
    assert st.verdict == DIR_CAUSAL
    assert st.leading_fraction == 0.0


def test_leading_lag_is_dir_noncausal():
    # screen precedes input beyond the frame quantum -> non-causal
    st = channel_directionality_stats(_wins("b1_flash", -100.0), "b1_flash")
    assert st.verdict == DIR_NONCAUSAL
    assert st.leading_fraction == 1.0


def test_weak_coupling_windows_excluded():
    # coupling below MIN_COUPLING carry no lag info -> INSUFFICIENT
    st = channel_directionality_stats(_wins("b1_flash", -100.0, coupling=0.01), "b1_flash")
    assert st.verdict == INSUFFICIENT


def test_insufficient_windows():
    st = channel_directionality_stats(_wins("b1_flash", 100.0, n=3), "b1_flash")
    assert st.verdict == INSUFFICIENT and st.leading_fraction is None


def test_frame_quantum_not_counted_as_leading():
    # a small negative lag within one frame period is NOT non-causal
    st = channel_directionality_stats(_wins("b1_flash", -(LEAD_EPS_MS - 5.0)), "b1_flash")
    assert st.leading_fraction == 0.0 and st.verdict == DIR_CAUSAL


# -- separation (synthetic rung) -----------------------------------------------

def test_synthetic_separation_bar_met():
    genuine = _wins("b1_flash", 100.0)      # causal
    replay = _wins("b1_flash", -100.0)      # non-causal
    res = assess_directionality(genuine, replay)
    assert res["separates_any"] is True
    ch = next(c for c in res["channels"] if c["channel"] == "b1_flash")
    assert ch["separates"] is True and ch["note"] == "bar met"
    assert res["advisory"] is True


def test_bar_miss_is_honest_negative():
    # genuine ALSO shows leading -> bar missed, reported honestly (not hidden)
    genuine = _wins("b1_flash", -100.0)     # genuine looks non-causal too
    replay = _wins("b1_flash", -100.0)
    res = assess_directionality(genuine, replay)
    ch = next(c for c in res["channels"] if c["channel"] == "b1_flash")
    assert ch["separates"] is False and "bar missed" in ch["note"]


def test_insufficient_class_disqualifies_channel():
    genuine = _wins("b1_flash", 100.0, n=3)   # too few
    replay = _wins("b1_flash", -100.0)
    res = assess_directionality(genuine, replay)
    ch = next(c for c in res["channels"] if c["channel"] == "b1_flash")
    assert ch["separates"] is False and "insufficient" in ch["note"]


def test_offline_scope_names_the_card_gate():
    res = assess_directionality(_wins("b1_flash", 100.0), _wins("b1_flash", -100.0))
    assert "card-gated" in res["offline_scope"]
