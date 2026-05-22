"""Tests for the F0 fusion harness (numpy-only; no hardware).

Two synthetic regimes prove the harness does its job: it should report fusion HELPS
when the two views' errors are independent, and NOT help when they're correlated.
"""
import numpy as np

from l9_presence.fusion import (
    MultiViewSession, assemble_rounds, error_independence, fuse, fusion_report, view_loo,
)

_PLAYERS = ("P1", "P2", "P3")


def _make_records(n_per=12, seed=0, sep=2.2, view_b_independent=True):
    """Two views, each moderately separable; independent or correlated noise."""
    rng = np.random.default_rng(seed)
    P = len(_PLAYERS)
    recs = []
    for ki, pl in enumerate(_PLAYERS):
        cA = np.zeros(P); cA[ki] = sep
        cB = np.zeros(P); cB[(ki + 1) % P] = sep   # different layout for view B
        for _ in range(n_per):
            a = cA + rng.normal(0, 1.0, P)
            b = (cB + rng.normal(0, 1.0, P)) if view_b_independent else a.copy()
            recs.append(MultiViewSession(pl, {"l9": a.tolist(), "l4": b.tolist()}))
    return recs


def test_error_independence_metrics():
    # a wrong on 0,1; b wrong on 2,3 -> complementary, double_fault 0
    a = np.array([False, False, True, True, True, True])
    b = np.array([True, True, False, False, True, True])
    m = error_independence(a, b)
    assert m["double_fault_rate"] == 0.0
    assert m["yule_q"] < 0.0           # complementary errors


def test_fusion_helps_with_independent_errors():
    recs = _make_records(seed=1, view_b_independent=True)
    rep = fusion_report(recs, ["l9", "l4"], n_perm=400)
    best_view = max(rep["view_accuracy"].values())
    assert rep["fused_accuracy"] >= best_view          # fusion does not hurt
    assert rep["fusion_helps"] is True                 # and is significant
    assert rep["error_independence"]["l9|l4"]["double_fault_rate"] < 0.2


def test_fusion_no_help_with_correlated_errors():
    recs = _make_records(seed=2, view_b_independent=False)  # view B == view A
    rep = fusion_report(recs, ["l9", "l4"], n_perm=400)
    # identical views -> errors fully correlated -> Q at the ceiling, no real gain
    assert rep["error_independence"]["l9|l4"]["yule_q"] > 0.9
    assert rep["gain_over_best_view"] <= 0.0


def test_assemble_rounds_pairs_per_player():
    l9 = {"P1": [[1, 2], [3, 4], [5, 6]], "P2": [[7, 8], [9, 10]]}
    ait = {"P1": [[0.1, 0.2, 0.3, 0.4]] * 5, "P2": [[1, 1, 1, 1]] * 2}
    rounds = assemble_rounds(l9, ait)
    assert len(rounds) == 3 + 2          # min(3,5)=3 for P1, min(2,2)=2 for P2
    r = rounds[0]
    assert set(r.views.keys()) == {"l9", "ait"}
    assert len(r.views["l9"]) == 2 and len(r.views["ait"]) == 4


def test_view_loo_runs():
    recs = _make_records(seed=3)
    vr = view_loo(recs, "l9")
    assert 0.0 <= vr["accuracy"] <= 1.0
    assert len(vr["correct"]) == len(recs)
