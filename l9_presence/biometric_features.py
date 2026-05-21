"""QorTroller L9 — render-loop biometric feature vector + within-player stability.

Enhancement #1: the first biometric derived from the RENDERED output loop rather than
the controller alone. Per session it extracts {per-axis causal coupling, causal lag,
yaw/pitch dominance ratio, decoupled energy}. These are candidate features for the
inter-person separation that gates tournaments — but a biometric must be TIGHT within
one person before it can separate people, so within_player_stability() reports the
coefficient of variation (CV) across a single player's sessions, gated to sessions
with real aim activity (low-aim sessions carry no usable signal and only add noise).

STATUS: design-only probe. No FROZEN-v1 primitive, no chain, no PoAC change.
"""
from __future__ import annotations

from typing import Optional

import numpy as np

from . import coupling as C
from .session_recorder import load_session

_EPS = 1e-9
_LAG_MIN = int(round(C.LAG_MIN_MS / 1000.0 * C.COMMON_RATE_HZ))
_LAG_MAX = int(round(C.LAG_MAX_MS / 1000.0 * C.COMMON_RATE_HZ))


def _axis_features(in_ts, stick, mo_ts, cam, grid):
    """(|coupling|, lag_ms, decoupled_energy) for one input/camera axis."""
    s = np.asarray(stick, float)
    s = s - np.median(s)
    pred = C.resample_uniform(np.asarray(in_ts, float), C.aim_response(s), grid)
    meas = C.resample_uniform(np.asarray(mo_ts, float), np.asarray(cam, float), grid)
    r, lag = C.lagged_xcorr(pred, meas, _LAG_MIN, _LAG_MAX)
    dec = C.decoupled_energy_fraction(pred, meas, lag)
    return abs(r), lag * 1000.0 / C.COMMON_RATE_HZ, dec


def extract_feature_vector(s, coupling_floor: float = 0.2) -> Optional[dict]:
    """Per-session L9 biometric feature vector, or None if too short to grid."""
    in_ts, mo_ts = np.asarray(s.in_ts, float), np.asarray(s.mo_ts, float)
    if in_ts.size < 4 or mo_ts.size < 4:
        return None
    t0, t1 = max(in_ts[0], mo_ts[0]), min(in_ts[-1], mo_ts[-1])
    if t1 - t0 < (C.MIN_GRID_SAMPLES / C.COMMON_RATE_HZ) * 1000.0:
        return None
    grid = np.arange(t0, t1, 1000.0 / C.COMMON_RATE_HZ)
    yc, yl, yd = _axis_features(in_ts, s.in_sx, mo_ts, s.mo_yaw, grid)
    pc, pl, pd = _axis_features(in_ts, s.in_sy, mo_ts, s.mo_pitch, grid)
    sx = np.asarray(s.in_sx, float); sx -= np.median(sx)
    sy = np.asarray(s.in_sy, float); sy -= np.median(sy)
    dom_yaw = yc >= pc
    return {
        "yaw_coupling": yc, "pitch_coupling": pc,
        "yaw_lag_ms": yl, "pitch_lag_ms": pl,
        "yaw_decoupled": yd, "pitch_decoupled": pd,
        "dominant_coupling": max(yc, pc),
        "dominant_lag_ms": yl if dom_yaw else pl,
        "yaw_pitch_ratio": yc / (yc + pc + _EPS),   # 1.0 = pure yaw aimer, 0.5 = balanced
        "aim_activity": float(max(sx.std(), sy.std())),
        "reliable": bool(max(yc, pc) >= coupling_floor),
    }


def _stats(xs) -> dict:
    xs = np.asarray(xs, float)
    m, sd = float(xs.mean()), float(xs.std())
    return {"mean": round(m, 4), "std": round(sd, 4),
            "cv": round(sd / abs(m), 4) if abs(m) > _EPS else None, "n": int(xs.size)}


# features that are candidate biometrics; report stability on each
_FEATURE_KEYS = ("dominant_coupling", "dominant_lag_ms", "yaw_coupling",
                 "yaw_lag_ms", "yaw_pitch_ratio", "yaw_decoupled")


def within_player_stability(paths: list[str], coupling_floor: float = 0.2) -> dict:
    """CV of each candidate feature across one player's sessions (reliable subset).
    Low CV (< ~0.3) = stable enough to be a biometric; high CV = needs finer capture
    or better gating before it can help separation."""
    vecs = [extract_feature_vector(load_session(p), coupling_floor) for p in paths]
    vecs = [v for v in vecs if v is not None]
    reliable = [v for v in vecs if v["reliable"]]
    src = reliable if reliable else vecs
    out = {
        "n_total": len(vecs),
        "n_reliable": len(reliable),
        "coupling_floor": coupling_floor,
        "features": {k: _stats([v[k] for v in src]) for k in _FEATURE_KEYS},
        "verdict": {},
    }
    for k in _FEATURE_KEYS:
        cv = out["features"][k]["cv"]
        out["verdict"][k] = ("stable" if (cv is not None and cv < 0.3)
                             else "noisy" if cv is not None else "undefined")
    return out


# stable within-player features (lag excluded until 60fps capture sharpens it)
_SEP_FEATURES = ("dominant_coupling", "yaw_pitch_ratio", "yaw_decoupled")
# richer set: gives BOTH axes a voice (P3 is pitch-dominant). 5 features, N/p=3.6 at N=18.
_SEP_FEATURES_RICH = ("dominant_coupling", "yaw_pitch_ratio", "yaw_decoupled",
                      "pitch_coupling", "pitch_decoupled")


def between_player_separation(paths: list[str], coupling_floor: float = 0.2,
                              features=None) -> dict:
    """GATE 2 — does the render-loop feature vector SEPARATE players? Groups reliable
    sessions by player id, z-scores the features, and reports the separation ratio =
    mean between-player centroid distance / mean within-player spread (the same
    between/within concept as the project's biometric separation). ratio > 1.0 = the
    feature carries inter-person identity. Sessions with no player id group as 'P1'.
    `features` defaults to _SEP_FEATURES; pass _SEP_FEATURES_RICH to give both axes a voice."""
    from collections import defaultdict
    feats = tuple(features) if features else _SEP_FEATURES
    groups: dict = defaultdict(list)
    for p in paths:
        s = load_session(p)
        v = extract_feature_vector(s, coupling_floor)
        if v is None or not v["reliable"]:
            continue
        player = (getattr(s, "player", "") or "P1")
        groups[player].append([v[k] for k in feats])
    players = sorted(groups)
    counts = {pl: len(groups[pl]) for pl in players}
    if len(players) < 2:
        return {"status": "need_>=2_players", "players": counts}
    X = np.array([row for pl in players for row in groups[pl]], float)
    mu, sd = X.mean(0), X.std(0)
    sd[sd < 1e-9] = 1.0
    Z = (X - mu) / sd
    z, idx = {}, 0
    for pl in players:
        z[pl] = Z[idx: idx + counts[pl]]
        idx += counts[pl]
    cent = {pl: z[pl].mean(0) for pl in players}
    within = float(np.mean([np.linalg.norm(r - cent[pl]) for pl in players for r in z[pl]]))
    pairs = [(players[i], players[j]) for i in range(len(players)) for j in range(i + 1, len(players))]
    between = float(np.mean([np.linalg.norm(cent[a] - cent[b]) for a, b in pairs]))
    ratio = between / (within + _EPS)

    # proper leave-one-out: classify each session to the nearest OTHER-sessions centroid
    labels = [pl for pl in players for _ in range(counts[pl])]
    correct = 0
    for i in range(len(labels)):
        cents = {}
        for pl in players:
            idx = [j for j in range(len(labels)) if labels[j] == pl and j != i]
            if idx:
                cents[pl] = Z[idx].mean(0)
        pred = min(cents, key=lambda pl: float(np.linalg.norm(Z[i] - cents[pl])))
        correct += int(pred == labels[i])
    loo_acc = correct / len(labels)

    return {
        "players": counts,
        "n_players": len(players),
        "features_used": list(feats),
        "within_player_spread": round(within, 4),
        "between_player_spread": round(between, 4),
        "separation_ratio": round(ratio, 4),
        "separable": bool(ratio > 1.0),
        "loo_accuracy": round(loo_acc, 4),
        "loo_correct": correct,
        "loo_total": len(labels),
    }


def _load_reliable(paths, coupling_floor, features=None):
    """(Z standardized matrix, labels array, players list) for reliable sessions."""
    feats = tuple(features) if features else _SEP_FEATURES
    rows, labels = [], []
    for p in paths:
        s = load_session(p)
        v = extract_feature_vector(s, coupling_floor)
        if v is None or not v["reliable"]:
            continue
        rows.append([v[k] for k in feats])
        labels.append(s.player or "P1")
    X = np.array(rows, float)
    labels = np.array(labels)
    if X.shape[0] < 4 or len(set(labels)) < 2:
        return None, None, None
    mu, sd = X.mean(0), X.std(0)
    sd[sd < 1e-9] = 1.0
    return (X - mu) / sd, labels, sorted(set(labels))


def _ratio_for(Z, labels, players):
    cent = {pl: Z[labels == pl].mean(0) for pl in players}
    within = np.mean([np.linalg.norm(Z[i] - cent[labels[i]]) for i in range(len(labels))])
    pairs = [(players[i], players[j]) for i in range(len(players)) for j in range(i + 1, len(players))]
    between = np.mean([np.linalg.norm(cent[a] - cent[b]) for a, b in pairs])
    return float(between / (within + _EPS))


def permutation_test(paths: list[str], n_perm: int = 2000, coupling_floor: float = 0.2,
                     seed: int = 0, features=None) -> dict:
    """Is the observed separation real, or could random player labels do as well? Keeps
    group sizes fixed, shuffles labels n_perm times, and reports the fraction of
    permutations whose ratio >= the real one (p-value). The decisive robustness check
    at small N / few players (no extra players required)."""
    Z, labels, players = _load_reliable(paths, coupling_floor, features)
    if Z is None:
        return {"status": "insufficient_data"}
    real = _ratio_for(Z, labels, players)
    rng = np.random.default_rng(seed)
    null = np.array([_ratio_for(Z, rng.permutation(labels), players) for _ in range(n_perm)])
    pval = float((null >= real).mean())
    return {
        "players": {pl: int((labels == pl).sum()) for pl in players},
        "real_ratio": round(real, 4),
        "null_mean": round(float(null.mean()), 4),
        "null_p95": round(float(np.percentile(null, 95)), 4),
        "p_value": round(pval, 4),
        "n_perm": n_perm,
        "significant": bool(pval < 0.05),
    }


def _balance(Z, labels, players, seed=0):
    """Subsample each player to the min session count (WIF-007 imbalance fix)."""
    rng = np.random.default_rng(seed)
    m = min(int((labels == pl).sum()) for pl in players)
    keep = []
    for pl in players:
        idx = np.where(labels == pl)[0]
        keep.extend(rng.choice(idx, size=m, replace=False))
    keep = np.array(sorted(keep))
    return Z[keep], labels[keep]


def _loo_accuracy(Z, labels, players, metric="euclidean", reg=0.1):
    """Leave-one-out nearest-centroid accuracy. metric='mahalanobis' uses the pooled
    within-class covariance (Tikhonov-regularized) — accounts for feature correlations;
    'euclidean' is the isotropic baseline."""
    n = len(labels)
    correct = 0
    for i in range(n):
        tr = [j for j in range(n) if j != i]
        cents = {pl: Z[[j for j in tr if labels[j] == pl]].mean(0) for pl in players
                 if any(labels[j] == pl for j in tr)}
        if metric == "mahalanobis":
            dev = [Z[[j for j in tr if labels[j] == pl]] - cents[pl]
                   for pl in players if any(labels[j] == pl for j in tr)]
            D = np.vstack(dev)
            W = D.T @ D / max(1, (D.shape[0] - len(cents)))
            W = W + reg * np.eye(W.shape[0])
            try:
                Winv = np.linalg.inv(W)
            except np.linalg.LinAlgError:
                Winv = np.linalg.pinv(W)
            def _d(pl):
                v = Z[i] - cents[pl]
                return float(v @ Winv @ v)
        else:
            def _d(pl):
                return float(np.linalg.norm(Z[i] - cents[pl]))
        correct += int(min(cents, key=_d) == labels[i])
    return correct / n


def mahalanobis_separation(paths: list[str], balance: bool = False, reg: float = 0.1,
                           n_perm: int = 2000, coupling_floor: float = 0.2, seed: int = 0,
                           features=None) -> dict:
    """Stronger classifier (Mahalanobis) vs the Euclidean baseline, WITH a permutation
    guardrail so a covariance-overfit gain (the Phase-138 trap) cannot masquerade as
    real: the null shuffles labels and recomputes the SAME Mahalanobis LOO, so spurious
    small-N fits inflate the null too. Real iff mahalanobis_loo beats null_p95 (p<0.05)."""
    Z, labels, players = _load_reliable(paths, coupling_floor, features)
    if Z is None:
        return {"status": "insufficient_data"}
    if balance:
        Z, labels = _balance(Z, labels, players, seed)
    eucl = _loo_accuracy(Z, labels, players, "euclidean")
    maha = _loo_accuracy(Z, labels, players, "mahalanobis", reg)
    rng = np.random.default_rng(seed)
    null = np.array([_loo_accuracy(Z, rng.permutation(labels), players, "mahalanobis", reg)
                     for _ in range(n_perm)])
    pval = float((null >= maha).mean())
    return {
        "players": {pl: int((labels == pl).sum()) for pl in players},
        "balanced": balance, "reg": reg,
        "euclidean_loo": round(eucl, 4),
        "mahalanobis_loo": round(maha, 4),
        "null_loo_mean": round(float(null.mean()), 4),
        "null_loo_p95": round(float(np.percentile(null, 95)), 4),
        "p_value": round(pval, 4),
        "reaches_80": bool(maha >= 0.80),
        "significant_and_real": bool(pval < 0.05 and maha > float(np.percentile(null, 95))),
    }


def _cli() -> int:
    import argparse
    import json
    ap = argparse.ArgumentParser(description="L9 render-loop biometric stability/separation")
    ap.add_argument("paths", nargs="+")
    ap.add_argument("--coupling-floor", type=float, default=0.2)
    ap.add_argument("--between", action="store_true",
                    help="gate 2: between-player separation (needs >=2 player ids)")
    ap.add_argument("--permute", action="store_true",
                    help="label-permutation null test (is the separation significant?)")
    ap.add_argument("--mahalanobis", action="store_true",
                    help="Mahalanobis LOO vs Euclidean baseline + permutation guardrail")
    ap.add_argument("--balance", action="store_true", help="balance sessions per player")
    ap.add_argument("--rich", action="store_true",
                    help="use the 5-feature set (both axes) instead of 3")
    a = ap.parse_args()
    feats = _SEP_FEATURES_RICH if a.rich else None
    if a.mahalanobis:
        out = mahalanobis_separation(a.paths, balance=a.balance,
                                     coupling_floor=a.coupling_floor, features=feats)
    elif a.permute:
        out = permutation_test(a.paths, coupling_floor=a.coupling_floor, features=feats)
    elif a.between:
        out = between_player_separation(a.paths, a.coupling_floor, features=feats)
    else:
        out = within_player_stability(a.paths, a.coupling_floor)
    print(json.dumps(out, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
