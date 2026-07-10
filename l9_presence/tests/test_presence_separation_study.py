"""P0-A presence-separation study tests — pins design §8 acceptance tests T1-T10.

T1 identical metric path · T2 no negative->positive leakage / no disk rewrite · T3 frozen constants ·
T4 fail-closed INSUFFICIENT_N · T5 insufficient-aim excluded/skipped · T6 causality-fail not SEPARATED ·
T7 paired construction n_auto=3x · T8 honesty fields on report · T9 offline (no capture-path imports) ·
T10 golden fixture (coupled scores high, decoupled low).
"""
from __future__ import annotations

import sys

import numpy as np

from l9_presence.presence_separation_study import (
    AUTO_MODES,
    GAP_MIN,
    INCONCLUSIVE,
    INSUFFICIENT_N,
    N_MIN_NEG,
    N_MIN_POS,
    SEPARATED,
    STUDY_SCHEMA,
    TAU_AUTO,
    TAU_HUMAN,
    TAU_NC,
    UNVERIFIABLE,
    decide_verdict,
    run_separation_study,
)
from l9_presence.session_recorder import SessionData, analyze_session_data


def _coupled(seed=0, player="P1"):
    """A human-like session: strong right-stick aim activity, camera tracks the stick (high coupling)."""
    n = 1200
    t = np.linspace(0, 10000, n)
    f = 0.6 + 0.05 * seed
    sx = 128 + 70 * np.sin(2 * np.pi * f * t / 1000.0 + seed)
    sy = np.full(n, 128.0)
    yaw = np.cumsum(sx - 128.0) * 0.001
    return SessionData(t, sx, sy, t, yaw, np.zeros(n), "human", None, player)


def _insufficient():
    """Too few samples / no aim activity -> analyze_session_data returns insufficient_aim_activity."""
    t = np.linspace(0, 50, 5)
    return SessionData(t, np.full(5, 128.0), np.full(5, 128.0), t,
                       np.zeros(5), np.zeros(5), "human", None, "P1")


# ------------------------------------------------------------------- T3 constants
def test_constants_frozen():
    assert (TAU_HUMAN, TAU_AUTO, GAP_MIN, TAU_NC, N_MIN_POS, N_MIN_NEG) == (0.20, 0.10, 0.15, 0.10, 8, 24)
    assert AUTO_MODES == ("static", "snap", "track")


# ------------------------------------------------------------------- T4/T6 + verdict logic (pure)
def test_decide_separated():
    v, g, _ = decide_verdict(n_pos=10, n_neg=30, med_human=0.40, med_auto=0.05, gap=0.35,
                             med_nc=0.02, med_margin=0.38)
    assert v == SEPARATED and all(g.values())


def test_decide_insufficient_n_never_separated():   # T4
    v, _, _ = decide_verdict(n_pos=5, n_neg=15, med_human=0.40, med_auto=0.05, gap=0.35,
                             med_nc=0.02, med_margin=0.38)
    assert v == INSUFFICIENT_N and v != SEPARATED


def test_decide_causality_fail_unverifiable():      # T6
    v, g, reason = decide_verdict(n_pos=10, n_neg=30, med_human=0.40, med_auto=0.05, gap=0.35,
                                  med_nc=0.30, med_margin=0.38)     # NC does not collapse
    assert v == UNVERIFIABLE and g["M6_causality"] is False and "CAUSALITY_FAIL" in reason


def test_decide_inconclusive():
    v, _, _ = decide_verdict(n_pos=10, n_neg=30, med_human=0.40, med_auto=0.30, gap=0.10,
                             med_nc=0.02, med_margin=0.38)          # auto too strong / gap too small
    assert v == INCONCLUSIVE


def test_decide_no_human_unverifiable():
    v, _, _ = decide_verdict(n_pos=0, n_neg=0, med_human=None, med_auto=None, gap=None,
                             med_nc=None, med_margin=None)
    assert v == UNVERIFIABLE


# ------------------------------------------------------------------- T7 paired construction
def test_paired_construction_n_auto_3x():
    rep = run_separation_study([_coupled(i) for i in range(3)], seed=0)
    assert rep.n["n_human_scored"] == 3 and rep.n["n_auto_scored"] == 3 * 3


# ------------------------------------------------------------------- T2 no leakage / no mutation
def test_no_leakage_no_mutation():
    humans = [_coupled(i) for i in range(3)]
    before = [(np.array(h.mo_yaw).copy()) for h in humans]
    rep = run_separation_study(humans, seed=0)
    # human class counts only humans; negatives never enter it
    assert rep.n["n_human_scored"] == 3
    # synthesize must not mutate the input human camera tracks (no disk/obj rewrite, T2)
    for h, b in zip(humans, before):
        assert np.array_equal(np.array(h.mo_yaw), b)


# ------------------------------------------------------------------- T5 insufficient excluded
def test_insufficient_excluded_and_skipped():
    rep = run_separation_study([_coupled(0), _coupled(1), _insufficient()], seed=0)
    assert rep.n["n_human_scored"] == 2 and rep.n["n_human_skipped"] == 1
    assert rep.n["n_auto_scored"] == 2 * 3     # negatives derived only from the 2 that scored


# ------------------------------------------------------------------- T1 + full end-to-end SEPARATED
def test_end_to_end_separated():
    """8 coupled humans -> 24 modeled-automation negatives; human median high, auto low -> SEPARATED.
    Exercises T1: both classes scored through the same analyze_session_data path."""
    rep = run_separation_study([_coupled(i) for i in range(8)], seed=0)
    assert rep.n["n_human_scored"] == 8 and rep.n["n_auto_scored"] == 24
    assert rep.verdict == SEPARATED, f"{rep.verdict} / {rep.reason} / {rep.to_dict()}"
    assert rep.medians["human"] >= TAU_HUMAN and rep.medians["auto"] <= TAU_AUTO
    assert rep.gap >= GAP_MIN


# ------------------------------------------------------------------- T8 honesty fields
def test_report_honesty_fields():
    d = run_separation_study([_coupled(i) for i in range(3)], seed=7).to_dict()
    assert d["advisory"] is True and d["cert_scope"] == "developer_self"
    assert d["population_certified"] is False and d["schema"] == STUDY_SCHEMA and d["seed"] == 7
    assert set(d["constants"]) == {"TAU_HUMAN", "TAU_AUTO", "GAP_MIN", "TAU_NC", "N_MIN_POS", "N_MIN_NEG"}
    import json
    assert json.dumps(d)          # serializable


# ------------------------------------------------------------------- T9 offline (no capture-path imports)
def test_offline_no_capture_path_imports():
    # clean-interpreter check: importing the study module must not pull in any capture-path module
    # (run in a subprocess so other tests' sys.modules pollution can't mask it)
    import subprocess
    code = ("import sys, l9_presence.presence_separation_study;"
            "bad=[m for m in sys.modules if 'dualshock' in m or 'qortroller_retina_capture' in m or 'daemon' in m];"
            "assert not bad, bad")
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert r.returncode == 0, (r.stdout + r.stderr)


# ------------------------------------------------------------------- T10 golden fixture
def test_golden_fixture_coupled_vs_decoupled():
    coupled = analyze_session_data(_coupled(0))
    assert coupled["coupling_score"] >= TAU_HUMAN and coupled["coupled"] is True
    n = 1200
    t = np.linspace(0, 10000, n)
    sx = 128 + 70 * np.sin(2 * np.pi * 0.6 * t / 1000.0)
    rng = np.random.default_rng(0)
    yaw = np.cumsum(rng.standard_normal(n)) * 0.05      # camera unrelated to stick
    decoupled = analyze_session_data(SessionData(t, sx, np.full(n, 128.0), t, yaw, np.zeros(n),
                                                 "human", None, "P1"))
    assert decoupled["coupling_score"] < TAU_HUMAN
