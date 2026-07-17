"""Catch trials + adversary re-run software gate."""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from l9_presence.poep_adversary_rerun import run_adversary_suite, to_markdown
from l9_presence.poep_catch_trials import (
    ALWAYS_FIRE_CATCH_BAR,
    HUMAN_FA_BUDGET,
    plan_trial_kinds,
    score_session,
    score_trial,
    simulate_always_fire_on_schedule,
    simulate_honest_human_on_schedule,
)


def test_plan_ratio_about_20_percent_nogo():
    kinds = plan_trial_kinds(20, go_per_no_go=4, seed=1)
    assert len(kinds) == 20
    n_nogo = sum(1 for k in kinds if k == "NO_GO")
    assert n_nogo == 4  # 20 // 5
    assert sum(1 for k in kinds if k == "GO") == 16


def test_plan_deterministic_under_seed():
    a = plan_trial_kinds(12, seed=42)
    b = plan_trial_kinds(12, seed=42)
    assert a == b


def test_score_go_and_nogo():
    go_ok = score_trial("GO", peak_lsb=2000, latency_ms=250, live_verify_ok=True)
    assert go_ok.human_ok
    go_bad = score_trial("GO", peak_lsb=200, latency_ms=500, live_verify_ok=False)
    assert not go_bad.human_ok
    nogo_clean = score_trial("NO_GO", peak_lsb=100, latency_ms=None, live_verify_ok=False)
    assert nogo_clean.human_ok and nogo_clean.reason == "nogo_clean"
    nogo_fa = score_trial("NO_GO", peak_lsb=1500, latency_ms=200, live_verify_ok=False)
    assert not nogo_fa.human_ok


def test_always_fire_catch_bar():
    kinds = plan_trial_kinds(100, go_per_no_go=4, seed=7)
    scores = simulate_always_fire_on_schedule(kinds)
    agg = score_session(scores, mode="always_fire_bot")
    assert agg["n_nogo"] >= 15
    assert agg["always_fire_catch_rate"] >= ALWAYS_FIRE_CATCH_BAR
    assert agg["always_fire_catch_ok"] is True


def test_honest_human_fa_budget_sim():
    kinds = plan_trial_kinds(100, go_per_no_go=4, seed=9)
    scores = simulate_honest_human_on_schedule(kinds, nogo_fa_rate=0.02, seed=9)
    agg = score_session(scores, mode="human")
    assert agg["human_fa_rate"] is not None
    assert agg["human_fa_rate"] <= HUMAN_FA_BUDGET + 0.05  # stochastic slack
    assert agg["human_fa_ok"] is True or agg["human_fa_rate"] <= 0.10


def test_adversary_suite_software_gate():
    rep = run_adversary_suite(n_tell=200, n_catch=100, seed=0xC7C4)
    assert rep["poep_enabled"] is False
    assert rep["flip_authorized"] is False
    assert rep["tell_watcher"]["passes_tell_removal_proof"] is True
    assert rep["catch_trials"]["always_fire_catch_ok"] is True
    assert rep["band_only_macro"]["far"] >= 0.9  # honesty: band alone fails
    assert rep["software_gate_pass"] is True  # tell + always-fire structural
    assert rep["human_fa_sim_ok"] is True     # large-N honest human sim under budget
    md = to_markdown(rep)
    assert "TellWatcher" in md
    assert "Catch trials" in md
