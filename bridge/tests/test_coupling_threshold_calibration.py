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
    gate_coupled_by_decoupled_energy,
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


# --- decoupled-energy gate (input-activity refinement; campaign 2026-06-27) -----------------------------

def test_gate_keeps_lowest_decoupled_energy_windows():
    # 2 genuine-aim (low DE, high coupling) + 2 walking (high DE, low coupling)
    windows = [(0.30, 0.80), (0.25, 0.82), (0.05, 0.99), (0.04, 0.995)]
    g = gate_coupled_by_decoupled_energy(windows, keep_quantile=0.5)
    assert g.n_total == 4 and g.n_kept == 2
    assert sorted(g.coupling_kept) == [0.25, 0.30]   # the right-stick-driven (aim) windows survive


def test_gate_lifts_tpr_by_dropping_diluted_windows():
    # the empirical campaign shape: genuine-aim coupling concentrated in low-DE windows; walking dilutes
    aim = [(0.18, 0.97)] * 15            # right-stick-driven
    walk = [(0.02, 0.999)] * 15          # world-scroll, near-null coupling
    null = [0.025] * 15 + [0.035] * 15
    res_u = calibrate([c for c, _ in aim + walk], null, structured_null=True)
    g = gate_coupled_by_decoupled_energy(aim + walk, keep_quantile=0.5)
    res_g = calibrate(g.coupling_kept, null, structured_null=True)
    assert g.n_kept == 15                              # only the aim windows survive the gate
    assert res_g.tpr_at_threshold >= res_u.tpr_at_threshold   # gate never hurts TPR; here lifts 0.5 -> 1.0
    assert res_g.separation >= res_u.separation


def test_gate_empty_and_none_safe():
    g0 = gate_coupled_by_decoupled_energy([], keep_quantile=0.5)
    assert g0.n_total == 0 and g0.n_kept == 0 and g0.cutoff is None and g0.coupling_kept == []
    g1 = gate_coupled_by_decoupled_energy([(0.3, 0.8), (None, 0.9), (0.2, None), (0.1, 0.99)])
    assert g1.n_total == 2                             # only fully-present (coupling, DE) pairs counted
