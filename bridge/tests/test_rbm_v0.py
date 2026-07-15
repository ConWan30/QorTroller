"""RBM-v0 model tests (A2A-POEP-P2, grok round-09). Pure-Python reflex-consistency scorer.

Pins the hard floor (fail-closed), the score range/shape, the calibration math (AUC/d'/tau*/FAR),
and the honesty rails (score != liveness verdict; poep stays off).
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from l9_presence.rbm_v0 import (
    RBMV0Params, dprime, evaluate, far_at, fit_moments, hard_floor, operating_threshold,
    roc_auc, score_row,
)

_P = RBMV0Params(mu_latency=173.0, sd_latency=63.0, mu_peak=1500.0, sd_peak=370.0,
                 operating_threshold=0.10, n_positives=52)


# --- hard floor (grok RBM-v0-DEF-01) -------------------------------------------
def test_hard_floor_rejects_out_of_band_and_low_peak():
    assert hard_floor(169.0, 1500.0, _P)                 # in-band, strong IMU
    assert not hard_floor(60.0, 1500.0, _P)              # too fast
    assert not hard_floor(400.0, 1500.0, _P)             # too slow
    assert not hard_floor(169.0, 500.0, _P)              # peak below floor (CCO-physics-class)
    assert not hard_floor(None, 1500.0, _P)              # missing -> fail-closed


def test_score_zero_below_floor_inband_positive_high():
    assert score_row(60.0, 1500.0, _P) == 0.0            # floor fail -> 0
    assert score_row(169.0, 400.0, _P) == 0.0            # peak fail -> 0
    s = score_row(173.0, 1500.0, _P)                     # dead-centre -> ~1.0
    assert 0.9 <= s <= 1.0


def test_score_in_unit_interval():
    for lat, pk in [(90.0, 1100.0), (295.0, 2100.0), (173.0, 1500.0), (120.0, 1600.0)]:
        assert 0.0 <= score_row(lat, pk, _P) <= 1.0


def test_evaluate_is_boolean_only_no_continuous_score():
    # grok round-11 fix (b): v0 product surface is BOOLEAN ONLY -- continuous score deferred to v0.1.
    e = evaluate(173.0, 1500.0, _P)
    assert e["is_liveness_verdict"] is False
    assert e["band_member"] is True and e["operating_point_fire"] is True
    assert e["score_status"] == "deferred_v0_1" and e["rbm_version"] == "RBM-v0"
    assert "score" not in e and "above_operating_point" not in e   # forbidden in v0 (over-precise)


def test_evaluate_floor_fail_is_not_member_not_fire():
    e = evaluate(60.0, 1500.0, _P)                                  # too fast -> floor fail
    assert e["band_member"] is False and e["operating_point_fire"] is False


# --- calibration math (pure Python; grok Q2) ----------------------------------
def test_roc_auc_perfect_and_chance():
    assert roc_auc([1.0, 0.9, 0.8], [0.1, 0.2, 0.0]) == 1.0     # perfect separation
    assert roc_auc([0.5], [0.5]) == 0.5                          # tie -> chance


def test_operating_threshold_hits_tpr_target():
    scores = [i / 100 for i in range(100)]                       # 0.00..0.99
    tau = operating_threshold(scores, 0.90)
    tpr = sum(1 for s in scores if s >= tau) / len(scores)
    assert tpr >= 0.90


def test_far_and_dprime():
    assert far_at([0.0, 0.05, 0.2], 0.1) == 1 / 3                # one null >= 0.1
    assert dprime([1.0, 0.9, 0.95], [0.0, 0.1, 0.05]) > 1.5     # separated -> high d'


def test_fit_moments_matches_hand():
    ml, sl, mp, sp = fit_moments([100.0, 200.0], [1000.0, 2000.0])
    assert ml == 150.0 and mp == 1500.0 and sl == 50.0 and sp == 500.0


def test_params_hash_stable_and_content_addressed():
    a = RBMV0Params(173.0, 63.0, 1500.0, 370.0, 0.10, 52)
    b = RBMV0Params(173.0, 63.0, 1500.0, 370.0, 0.10, 52)
    c = RBMV0Params(174.0, 63.0, 1500.0, 370.0, 0.10, 52)       # different moment
    assert a.params_hash() == b.params_hash() != c.params_hash()
