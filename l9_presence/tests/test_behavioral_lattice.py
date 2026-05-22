"""Tests for the behavioral-lattice geometry (no hardware).

The synthetic tests prove the MECHANISM works on ideal (separated) data — the lattice
rejects gap/centroid adversaries that Mahalanobis accepts. Whether REAL data is separated
enough for the win is the empirical question the CLI answers honestly.
"""
import numpy as np

from l9_presence.behavioral_lattice import (
    accept, evaluate, fit_model, lattice_decode, maha, whiten_transform,
)


def test_whiten_centroid_zero_distance():
    rng = np.random.default_rng(0)
    X = rng.standard_normal((40, 3)) * [2.0, 0.5, 1.0] + [1.0, -2.0, 3.0]
    mu, W = whiten_transform(X)
    assert maha(mu, mu, W)[0] < 1e-6                      # the mean is distance 0 from itself
    Z = (X - mu) @ W
    cov = np.cov(Z.T)
    assert np.allclose(cov, np.eye(3), atol=0.25)          # whitening -> ~isotropic


def test_lattice_decode_rounds():
    idx, err = lattice_decode(np.array([[0.4, -0.6, 1.1]]), spacing=1.0)
    assert idx[0].tolist() == [0, -1, 1]
    assert np.allclose(err[0], [0.4, 0.4, 0.1], atol=1e-9)


def _two_clusters(seed=0, spread=0.3):
    rng = np.random.default_rng(seed)
    a = np.array([5.0, 0.0]) + spread * rng.standard_normal((15, 2))
    b = np.array([-5.0, 0.0]) + spread * rng.standard_normal((15, 2))
    return np.vstack([a, b])


def test_lattice_rejects_gap_that_mahalanobis_accepts():
    X = _two_clusters()
    m = fit_model(X, spacing=1.0)
    gap = np.array([0.0, 0.0])                            # midpoint between the two people
    assert accept(gap, m, "mahalanobis_upper") is True    # inside the pooled ellipsoid -> accepted
    assert accept(gap, m, "lattice") is False             # unoccupied node -> rejected (the win)


def test_lattice_accepts_genuine_members():
    X = _two_clusters()
    m = fit_model(X, spacing=1.0)
    acc = float(np.mean([accept(x, m, "lattice") for x in X]))
    assert acc >= 0.7                                      # most real members still accepted


def test_evaluate_reports_all_methods_and_verdict():
    X = _two_clusters()
    labels = ["P1"] * 15 + ["P2"] * 15
    r = evaluate(X, labels, spacing=1.0)
    assert set(r["methods"]) == {"mahalanobis_upper", "mahalanobis_band", "lattice"}
    assert "lattice_beats_mahalanobis_band" in r["verdict"]
    # on cleanly-separated synthetic people the lattice should reject the gap the band accepts
    assert r["methods"]["lattice"]["far"]["gap"] <= r["methods"]["mahalanobis_band"]["far"]["gap"]
