"""F-POEP-LIVE-1 tell-removal PROOF (grok round-18 design + round-19 correction). Not "we deleted a
print" — a measured FAR collapse across three capture paths, honestly modelling the PollBurstWatcher
grok round-19 caught: the naive silent fire (sleep -> burst) is genuinely exploitable (~0.56), and it is
the CONTINUOUS-poll fire that collapses it to ~chance. stdout macro forges ~1.0. A-REACTIVE stays out of
claim; poep_enabled stays False.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from l9_presence.poep_tell_watcher import (
    FAR_FIX_BAR,
    FAR_FLAW_MIN,
    FAR_OLD_BAR,
    far_collapse,
    simulate_far,
)


def test_stdout_tell_macro_forges_high():
    r = simulate_far(capture="stdout_tell", bot="stdout_watcher")
    assert r["far"] >= FAR_OLD_BAR


def test_naive_sleep_then_burst_is_genuinely_exploitable():
    # the flaw grok round-19 caught: a poll-burst watcher beats the naive "silent" fire well above chance
    r = simulate_far(capture="sleep_then_burst", bot="poll_burst_watcher")
    assert r["far"] >= FAR_FLAW_MIN


def test_continuous_poll_collapses_the_pollburst_macro():
    # the real fix: continuous uniform polling removes the burst transition -> macro falls to ~chance
    r = simulate_far(capture="continuous_poll", bot="poll_burst_watcher")
    assert r["far"] <= FAR_FIX_BAR


def test_tell_removal_proof_passes_all_three_bars():
    r = far_collapse()
    assert r["passes_tell_removal_proof"] is True
    # the fix is LOAD-BEARING, not decorative: naive path was exploitable, fixed path is not
    assert r["far_pollburst_naive"] - r["far_pollburst_fixed"] >= 0.3


def test_deterministic_under_seed():
    a = far_collapse(seed=12345)
    b = far_collapse(seed=12345)
    assert a == b


def test_fix_holds_across_seeds_and_windows():
    for seed in (1, 7, 99, 0xBEEF):
        assert simulate_far(capture="continuous_poll", bot="poll_burst_watcher", seed=seed)["far"] <= FAR_FIX_BAR
    # a narrower delay window is the harder case for the fix, yet the poll-burst macro still collapses
    assert simulate_far(capture="continuous_poll", bot="poll_burst_watcher",
                        min_delay_s=3.0, max_delay_s=6.0)["far"] <= FAR_FIX_BAR


def test_blind_guesser_is_chance_on_every_path():
    for cap in ("stdout_tell", "sleep_then_burst", "continuous_poll"):
        assert simulate_far(capture=cap, bot="blind_guesser")["far"] <= FAR_FIX_BAR
