"""QorTroller — Behavioral-Lattice geometry: a falsifiable test of "GCAP".

CLAIM UNDER TEST: a human session decodes as `x = A·s + e` — a lattice point s (the stable
anatomical "secret") plus a BOUNDED, STRUCTURED error e (human variability = the Mahalanobis
error-ball). The novel prediction is that this beats a single-Gaussian Mahalanobis model on
the cases Mahalanobis is blind to:
  - CENTROID bot: emits the population mean -> Mahalanobis distance 0 -> "looks maximally
    human" (false-accept). The lattice rejects it because e ~ 0 (too clean / on-node).
  - GAP bot: an interpolation between two different people -> sits INSIDE the pooled
    Mahalanobis ellipsoid but in a region no real person occupies. The lattice rejects it
    because it decodes to an UNOCCUPIED node.

This is the discipline gate: the lattice EARNS the name only if it beats the STRONG
Mahalanobis baseline (a band lo<=d<=hi, not the naive upper-only) on those adversaries
WITHOUT losing human acceptance (LOO TAR). Otherwise it is an elegant metaphor, reported
honestly as such. Geometry is genuinely there either way (Mahalanobis = a learned metric
tensor); this asks whether the DISCRETE lattice adds anything over the Gaussian on real data.

STATUS: research probe. No FROZEN-v1/PoAC/chain/contract touched. Standalone l9_presence/.
"""
from __future__ import annotations

import glob
import os

import numpy as np

from .biometric_features import _SEP_FEATURES, _session_from_file, extract_feature_vector


def load_human_matrix(paths, coupling_floor: float = 0.2):
    """Return (X[N,p], labels) of reliable human _SEP_FEATURES vectors."""
    X, labels = [], []
    for p in paths:
        s = _session_from_file(p)
        if s is None:
            continue
        v = extract_feature_vector(s, coupling_floor)
        if v is None or not v.get("reliable"):
            continue
        X.append([v[k] for k in _SEP_FEATURES])
        labels.append(getattr(s, "player", "") or "P1")
    return np.asarray(X, float), labels


def whiten_transform(X: np.ndarray, reg: float = 1e-6):
    """Return (mu, W) with W = Σ^(-1/2). After z=(x-mu)@W the human cloud is isotropic and
    ||z|| equals the Mahalanobis distance. W is the square root of the learned metric tensor."""
    mu = X.mean(axis=0)
    p = X.shape[1]
    cov = np.cov((X - mu).T) + reg * np.eye(p)
    vals, vecs = np.linalg.eigh(cov)
    vals = np.clip(vals, reg, None)
    W = vecs @ np.diag(1.0 / np.sqrt(vals)) @ vecs.T
    return mu, W


def maha(X: np.ndarray, mu: np.ndarray, W: np.ndarray) -> np.ndarray:
    Z = np.atleast_2d(X - mu) @ W
    return np.linalg.norm(Z, axis=1)


def lattice_decode(Z: np.ndarray, spacing: float):
    """Round whitened points to the nearest node of the scaled integer lattice; return
    (node_indices[int], error_vectors)."""
    Z = np.atleast_2d(Z)
    idx = np.round(Z / spacing).astype(int)
    err = Z - idx * spacing
    return idx, err


def fit_model(X: np.ndarray, spacing: float = 1.0, lo_q: float = 5.0, hi_q: float = 95.0) -> dict:
    """Fit both geometries on a human matrix: the Mahalanobis band AND the lattice support
    (occupied nodes) + human error-norm band."""
    mu, W = whiten_transform(X)
    Z = (X - mu) @ W
    d = np.linalg.norm(Z, axis=1)
    idx, err = lattice_decode(Z, spacing)
    en = np.linalg.norm(err, axis=1)
    return {
        "mu": mu, "W": W, "spacing": spacing,
        "maha_lo": float(np.percentile(d, lo_q)), "maha_hi": float(np.percentile(d, hi_q)),
        "e_lo": float(np.percentile(en, lo_q)), "e_hi": float(np.percentile(en, hi_q)),
        "occupied": {tuple(r) for r in idx},
    }


def accept(x: np.ndarray, model: dict, method: str) -> bool:
    z = (np.asarray(x, float) - model["mu"]) @ model["W"]
    d = float(np.linalg.norm(z))
    if method == "mahalanobis_upper":
        return d <= model["maha_hi"]
    if method == "mahalanobis_band":
        return model["maha_lo"] <= d <= model["maha_hi"]
    if method == "lattice":
        idx, err = lattice_decode(z, model["spacing"])
        node = tuple(idx[0])
        en = float(np.linalg.norm(err[0]))
        return (node in model["occupied"]) and (model["e_lo"] <= en <= model["e_hi"])
    raise ValueError(method)


_METHODS = ("mahalanobis_upper", "mahalanobis_band", "lattice")


def make_adversaries(X: np.ndarray, labels, seed: int = 0) -> dict:
    """Synthetic adversary classes with the DEFINING failure-mode properties."""
    rng = np.random.default_rng(seed)
    mu = X.mean(axis=0)
    n = len(X)
    centroid = np.tile(mu, (max(8, n), 1))                       # mean vector -> Mahalanobis 0
    gaps = []                                                     # cross-person interpolations
    for i in range(n):
        for j in range(i + 1, n):
            if labels[i] != labels[j]:
                gaps.append(0.5 * (X[i] + X[j]))
    gaps = np.asarray(gaps, float) if gaps else np.empty((0, X.shape[1]))
    # shuffle: break the joint covariance structure (per-feature permuted across samples)
    shuf = np.column_stack([rng.permutation(X[:, k]) for k in range(X.shape[1])])
    return {"centroid": centroid, "gap": gaps, "shuffle": shuf}


def evaluate(X: np.ndarray, labels, spacing: float = 1.0) -> dict:
    """LOO human true-accept rate + per-class false-accept rate for each method, + verdict."""
    n = len(X)
    advs = make_adversaries(X, labels)
    out = {"n_human": n, "spacing": spacing, "methods": {}}
    full = fit_model(X, spacing)
    for method in _METHODS:
        hits = 0
        for i in range(n):
            train = np.delete(X, i, axis=0)
            hits += int(accept(X[i], fit_model(train, spacing), method))
        tar = hits / n
        far = {cls: (float(np.mean([accept(a, full, method) for a in arr])) if len(arr) else None)
               for cls, arr in advs.items()}
        out["methods"][method] = {"human_tar": round(tar, 3),
                                  "far": {k: (round(v, 3) if v is not None else None)
                                          for k, v in far.items()}}
    lat, band = out["methods"]["lattice"], out["methods"]["mahalanobis_band"]
    # GO iff lattice beats the STRONG baseline on the decisive classes without losing >0.1 TAR
    decisive = [c for c in ("centroid", "gap") if band["far"].get(c) is not None]
    beats = all(lat["far"][c] < band["far"][c] for c in decisive) if decisive else False
    out["verdict"] = {
        "lattice_beats_mahalanobis_band": bool(beats and lat["human_tar"] >= band["human_tar"] - 0.1),
        "decisive_classes": decisive,
        "note": ("lattice earns the name on this corpus" if beats
                 else "lattice does NOT beat the Mahalanobis band — elegant metaphor, not a primitive (likely "
                      "separation-limited, same ceiling as identity)"),
    }
    return out


def _cli() -> int:
    import argparse
    import json
    ap = argparse.ArgumentParser(description="Behavioral-Lattice vs Mahalanobis (falsifiable GCAP test)")
    ap.add_argument("paths", nargs="*", default=None)
    ap.add_argument("--corpus", default="cocapture_l9", help="dir of *.npz if paths omitted")
    ap.add_argument("--spacing", type=float, default=1.0)
    a = ap.parse_args()
    paths = a.paths or sorted(glob.glob(os.path.join(a.corpus, "*.npz")))
    X, labels = load_human_matrix(paths)
    if len(X) < 6:
        print(json.dumps({"status": "insufficient_data", "n": len(X)})); return 4
    print(json.dumps(evaluate(X, labels, a.spacing), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
