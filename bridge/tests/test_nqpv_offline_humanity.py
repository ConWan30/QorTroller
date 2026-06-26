"""Cycle-35 — NQPV offline humanity adapter (hw_* -> human-positive NqpvCorpusRecord).

Pure tests (no controller extractor / no session files): the Mahalanobis math, the study-only p_L4
re-anchor, and the record-builder logic (LOO distance -> l4_l5_l6_ok = d<threshold, abstain on
cco/poep/retina, label=human, binding present). Mirrors the harness's consumption shape.
"""
from __future__ import annotations

import numpy as np

from vapi_bridge.nqpv_corpus_loader import LABEL_HUMAN
from vapi_bridge.nqpv_offline_humanity import (
    DEFAULT_ANOMALY_THRESHOLD,
    diag_mahalanobis,
    reanchored_p_l4,
    records_from_fingerprints,
)


# --- diagonal Mahalanobis ---

def test_mahalanobis_zero_at_centroid():
    v = np.array([1.0, 2.0, 3.0])
    assert diag_mahalanobis(v, v, np.array([1.0, 1.0, 1.0])) == 0.0


def test_mahalanobis_one_sigma_offset():
    # offset of sqrt(var) in a single dim -> distance 1.0
    mean = np.array([0.0, 0.0]); var = np.array([4.0, 9.0])
    assert abs(diag_mahalanobis(np.array([2.0, 0.0]), mean, var) - 1.0) < 1e-9   # 2/sqrt(4)=1
    assert abs(diag_mahalanobis(np.array([0.0, 3.0]), mean, var) - 1.0) < 1e-9   # 3/sqrt(9)=1


def test_mahalanobis_var_floor_prevents_explosion():
    # a structurally-zero feature (var=0) must not divide-by-zero / explode
    d = diag_mahalanobis(np.array([0.0, 0.0]), np.array([0.0, 0.0]), np.array([0.0, 0.0]))
    assert d == 0.0  # zero diff over floored var = 0, not nan/inf


# --- study-only p_L4 re-anchor ---

def test_p_l4_anchor_endpoints_and_monotonic():
    thr = DEFAULT_ANOMALY_THRESHOLD
    assert abs(reanchored_p_l4(0.0, thr) - 1.0) < 1e-9        # d=0 -> certain human
    assert abs(reanchored_p_l4(thr, thr) - 0.5) < 1e-9        # d==threshold -> 0.5
    assert abs(reanchored_p_l4(2 * thr, thr) - 0.25) < 1e-9   # d=2*threshold -> 0.25
    # strictly decreasing in d
    ds = [reanchored_p_l4(d, thr) for d in (0, 1, 3, 5, 8)]
    assert all(a > b for a, b in zip(ds, ds[1:]))


def test_p_l4_beats_the_live_undershoot_at_human_distances():
    # the whole point: at the corpus mean distance ~2.45 the re-anchor gives a usable p_L4,
    # whereas the live exp(-(d-2)) gives ~0.64 (and ~0.0067 at the threshold).
    import math
    d = 2.45
    assert reanchored_p_l4(d) > 0.6
    # the live exp(-(d-2)) badly under-scores even a human-mean distance: ~0.64 at d=2.45 but it
    # decays so fast it is ~0.03 at the threshold, vs the re-anchor's 0.5 there.
    assert math.exp(-(d - 2.0)) < reanchored_p_l4(d)        # live undershoots the re-anchor at human d
    assert reanchored_p_l4(DEFAULT_ANOMALY_THRESHOLD) == 0.5
    assert math.exp(-(DEFAULT_ANOMALY_THRESHOLD - 2.0)) < 0.05  # live collapses near the threshold


# --- record builder ---

def _fp(*vals):
    return np.array(vals, dtype=np.float64)


def test_records_human_label_binding_and_abstain():
    fps = [("s1", _fp(1, 1, 1)), ("s2", _fp(1.1, 0.9, 1.0)), ("s3", _fp(0.9, 1.1, 1.0))]
    recs = records_from_fingerprints(fps)
    assert len(recs) == 3
    for r in recs:
        assert r.label == LABEL_HUMAN
        assert r.source == "offline_1khz"
        assert r.binding_ok                      # synthetic device_id + record_hash present
        assert r.cco_tier is None                # abstain
        assert r.poep_present is None            # abstain
        assert r.retina_coupled_verdict is None  # abstain (no camera witness)
        assert 0.0 <= r.humanity_prob <= 1.0


def test_tight_cluster_is_l4_nominal_human():
    # near-identical fingerprints -> small LOO distance -> well under threshold -> l4_l5_l6_ok True
    fps = [(f"s{i}", _fp(5.0 + 0.01 * i, 3.0, 1.0)) for i in range(6)]
    recs = records_from_fingerprints(fps)
    assert all(r.l4_l5_l6_ok is True for r in recs)
    assert all(r.humanity_prob > 0.5 for r in recs)


def test_outlier_fingerprint_flagged_non_nominal():
    # one wild outlier among a tight cluster -> large LOO distance -> not L4-nominal
    fps = [("a", _fp(1, 1, 1)), ("b", _fp(1.05, 1.0, 1.0)), ("c", _fp(0.95, 1.0, 1.0)),
           ("d", _fp(1.0, 1.02, 1.0)), ("outlier", _fp(900.0, 900.0, 900.0))]
    recs = {r.device_id: r for r in records_from_fingerprints(fps)}
    from vapi_bridge.nqpv_offline_humanity import _synth_binding
    out = recs[_synth_binding("outlier", "dev")]
    assert out.l4_l5_l6_ok is False              # the adversary-like outlier is caught
    assert out.humanity_prob < 0.5


def test_injectable_p_l4_anchor():
    fps = [("s1", _fp(1, 1, 1)), ("s2", _fp(1.1, 1.0, 1.0))]
    recs = records_from_fingerprints(fps, p_l4_fn=lambda d, thr: 0.123)
    assert all(r.humanity_prob == 0.123 for r in recs)
