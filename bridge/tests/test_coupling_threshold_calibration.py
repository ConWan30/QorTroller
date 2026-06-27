"""Coupling-threshold calibration harness — honesty rails (s-coupling-threshold-calibration).

Validates the FAR-controlled separation logic: ADOPTABLE only on clean separation from the null with a
measured TPR at a bounded FAR; INSEPARABLE when real coupling overlaps the shuffle null (the honest
"native-PC for the lag pillar" outcome, not a lowered bar); INSUFFICIENT_DATA below the N floor; and the
shuffle-only / anti-GCAP caveat always surfaced until structured negatives are supplied.
"""
from __future__ import annotations

import numpy as np

from vapi_bridge.coupling_threshold_calibration import (
    CURRENT_THRESHOLD,
    N_FLOOR,
    calibrate,
)


def _rng(seed):
    return np.random.default_rng(seed)


def test_clean_separation_is_adoptable():
    r = _rng(1)
    coupled = list(r.normal(0.42, 0.05, 30))          # real aim well above the null
    null = list(r.normal(0.05, 0.02, 30))             # shuffle baseline
    res = calibrate(coupled, null, structured_null=True)
    assert res.verdict == "ADOPTABLE"
    assert res.recommended_threshold is not None
    # FAR-controlled: threshold sits in the gap, above the null tail, below the coupled mass
    assert 0.05 < res.recommended_threshold < 0.42
    assert res.far_at_threshold <= 0.10 and res.tpr_at_threshold >= 0.5
    assert res.separation > 0


def test_overlap_is_inseparable_not_lowered():
    r = _rng(2)
    coupled = list(r.normal(0.10, 0.03, 30))          # weak Remote-Play-like coupling
    null = list(r.normal(0.10, 0.03, 30))             # null overlaps it
    res = calibrate(coupled, null, structured_null=True)
    assert res.verdict == "INSEPARABLE"
    assert res.recommended_threshold is None           # never invents a passing threshold
    assert any("native-PC" in c for c in res.caveats)


def test_small_n_is_insufficient():
    res = calibrate([0.4, 0.45, 0.5], [0.02, 0.03], structured_null=True)
    assert res.verdict == "INSUFFICIENT_DATA"
    assert res.recommended_threshold is None
    assert res.n_coupled == 3 and res.n_null == 2
    assert any(str(N_FLOOR) in c for c in res.caveats)


def test_shuffle_only_carries_antigcap_caveat():
    r = _rng(3)
    res = calibrate(list(r.normal(0.4, 0.05, 30)), list(r.normal(0.05, 0.02, 30)), structured_null=False)
    assert res.structured_null is False
    assert any("anti-GCAP" in c or "structured" in c for c in res.caveats)


def test_far_controlled_threshold_is_near_null_p95():
    r = _rng(4)
    null = list(r.normal(0.05, 0.02, 200))
    res = calibrate(list(r.normal(0.4, 0.05, 200)), null, structured_null=True, far_cap=0.05)
    # recommended threshold ~= the 95th percentile of the null (by construction; module rounds to 4dp)
    assert abs(res.recommended_threshold - float(np.quantile(null, 0.95))) < 1e-3
    assert res.far_at_threshold <= 0.06


def test_session_seed_is_honest_insufficient():
    # the ACTUAL 2026-06-27 Remote-Play / Warzone session: 3 active-aim coupling_scores vs the shuffle null.
    coupled = [0.110, 0.148, 0.141]
    null = [0.02, 0.03, 0.018]
    res = calibrate(coupled, null, structured_null=False)
    assert res.verdict == "INSUFFICIENT_DATA"          # N=3 — feasibility, not a verdict
    # but the preliminary separation is positive (coupled ~0.14 vs null ~0.02) -> worth a real campaign
    assert res.separation is not None and res.separation > 0
    assert res.current_threshold == CURRENT_THRESHOLD


def test_to_dict_roundtrip():
    res = calibrate([0.4] * 12, [0.05] * 12, structured_null=True)
    d = res.to_dict()
    assert d["verdict"] == res.verdict and d["current_threshold"] == CURRENT_THRESHOLD
    assert "caveats" in d and isinstance(d["caveats"], list)
