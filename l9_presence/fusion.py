"""QorTroller L9 Fusion F0 — score-level combiner + error-independence harness.

Operates on an abstract MULTI-VIEW session (each session has a player label and one
feature vector per VIEW, e.g. 'l9' and 'l4'), so it is ready for the F2 co-captured
corpus without rework. F0 answers the decisive question BEFORE the heavier F1 build:

  1. Are the two classifiers' errors INDEPENDENT? (Yule's Q, double-fault rate) — if
     they miss the same sessions, fusion cannot help.
  2. Does SCORE-LEVEL fusion (combine per-view posteriors) beat each view alone, and
     is the gain real (permutation null)?

Score-level (late) fusion deliberately keeps each view's classifier low-dimensional —
N/p-safe, avoids the Phase-138 inflation trap that feature-level concatenation invites.

No FROZEN-v1 primitive, no chain, no PoAC. numpy only.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np

_EPS = 1e-12


@dataclass
class MultiViewSession:
    player: str
    views: dict          # {view_name: list[float]}


def _matrix(records, view):
    X = np.array([r.views[view] for r in records], float)
    mu, sd = X.mean(0), X.std(0)
    sd[sd < 1e-9] = 1.0
    return (X - mu) / sd


def _loo_posteriors(X, labels, players, temp=1.0):
    """Leave-one-out softmax posteriors over players + predicted labels (nearest
    centroid in z-scored space; centroids exclude the held-out session)."""
    n = len(labels)
    post = np.zeros((n, len(players)))
    pred = []
    for i in range(n):
        d = np.empty(len(players))
        for k, pl in enumerate(players):
            idx = [j for j in range(n) if labels[j] == pl and j != i]
            d[k] = np.linalg.norm(X[i] - X[idx].mean(0)) if idx else np.inf
        s = -d / temp
        s -= np.nanmax(s[np.isfinite(s)]) if np.any(np.isfinite(s)) else 0.0
        w = np.where(np.isfinite(s), np.exp(s), 0.0)
        post[i] = w / (w.sum() + _EPS)
        pred.append(players[int(np.argmin(d))])
    return post, np.array(pred)


def view_loo(records, view, temp=1.0):
    """Standalone LOO for one view: accuracy, per-session correctness, posteriors."""
    labels = np.array([r.player for r in records])
    players = sorted(set(labels))
    X = _matrix(records, view)
    post, pred = _loo_posteriors(X, labels, players, temp)
    correct = (pred == labels)
    return {"view": view, "players": players, "accuracy": float(correct.mean()),
            "correct": correct, "posteriors": post}


def error_independence(correct_a, correct_b) -> dict:
    """How independent are two classifiers' LOO errors? Yule's Q (~0 independent,
    ~+1 correlated/agree, <0 complementary), double-fault rate (both wrong — the
    fusion-killer; low is good), and disagreement rate."""
    a, b = np.asarray(correct_a), np.asarray(correct_b)
    n11 = int(np.sum(a & b)); n00 = int(np.sum(~a & ~b))
    n10 = int(np.sum(a & ~b)); n01 = int(np.sum(~a & b))
    denom = n11 * n00 + n10 * n01
    q = (n11 * n00 - n10 * n01) / denom if denom else 0.0
    n = len(a)
    return {"yule_q": round(float(q), 4),
            "double_fault_rate": round(n00 / n, 4),
            "disagreement_rate": round((n10 + n01) / n, 4)}


def fuse(records, views, weights: Optional[list] = None, temp=1.0):
    """Score-level fusion: combine per-view LOO posteriors (weighted sum of log-
    posteriors = weighted product of posteriors), argmax -> fused prediction."""
    labels = np.array([r.player for r in records])
    players = sorted(set(labels))
    w = weights or [1.0] * len(views)
    logp = np.zeros((len(records), len(players)))
    per_view = {}
    for vw, wi in zip(views, w):
        vr = view_loo(records, vw, temp)
        per_view[vw] = vr
        logp += wi * np.log(vr["posteriors"] + _EPS)
    fused_pred = np.array([players[int(np.argmax(row))] for row in logp])
    return {"players": players, "fused_pred": fused_pred,
            "fused_accuracy": float((fused_pred == labels).mean()),
            "per_view": per_view, "labels": labels}


def assemble_rounds(l9_by_player: dict, ait_by_player: dict, seed: int = 0):
    """Option B (FB0): pair each player's L9 vectors with their AIT vectors 1:1 (min
    count) into MultiViewSession rounds for player-level fusion. Valid because a
    person's sessions are exchangeable; shuffled to avoid capture-order artifacts."""
    rng = np.random.default_rng(seed)
    rounds = []
    for pl in sorted(set(l9_by_player) & set(ait_by_player)):
        l9s, aits = list(l9_by_player[pl]), list(ait_by_player[pl])
        if not l9s or not aits:
            continue
        rng.shuffle(l9s); rng.shuffle(aits)
        for i in range(min(len(l9s), len(aits))):
            rounds.append(MultiViewSession(pl, {"l9": list(l9s[i]), "ait": list(aits[i])}))
    return rounds


def fusion_report(records, views, n_perm=2000, temp=1.0, seed=0) -> dict:
    """Full F0 verdict: per-view accuracy, fused accuracy + gain, pairwise error
    independence, and a permutation null on the fused accuracy. Recommendation fires
    only when fusion beats the best view AND the gain is significant."""
    labels = np.array([r.player for r in records])
    players = sorted(set(labels))
    if len(records) < 6 or len(players) < 2:
        return {"status": "insufficient_data"}
    base = fuse(records, views, temp=temp)
    view_acc = {vw: base["per_view"][vw]["accuracy"] for vw in views}
    best_view = max(view_acc.values())
    indep = {}
    for i in range(len(views)):
        for j in range(i + 1, len(views)):
            a, b = views[i], views[j]
            indep[f"{a}|{b}"] = error_independence(
                base["per_view"][a]["correct"], base["per_view"][b]["correct"])

    # permutation null on fused accuracy (shuffle labels, keep views)
    rng = np.random.default_rng(seed)
    null = np.empty(n_perm)
    for t in range(n_perm):
        perm = rng.permutation(labels)
        shuffled = [MultiViewSession(perm[k], records[k].views) for k in range(len(records))]
        null[t] = fuse(shuffled, views, temp=temp)["fused_accuracy"]
    pval = float((null >= base["fused_accuracy"]).mean())

    gain = base["fused_accuracy"] - best_view
    return {
        "n_sessions": len(records),
        "players": {pl: int((labels == pl).sum()) for pl in players},
        "view_accuracy": {k: round(v, 4) for k, v in view_acc.items()},
        "fused_accuracy": round(base["fused_accuracy"], 4),
        "gain_over_best_view": round(gain, 4),
        "error_independence": indep,
        "permutation": {"null_mean": round(float(null.mean()), 4),
                        "null_p95": round(float(np.percentile(null, 95)), 4),
                        "p_value": round(pval, 4)},
        "fusion_helps": bool(gain > 0 and pval < 0.05
                             and base["fused_accuracy"] > float(np.percentile(null, 95))),
        "reaches_80": bool(base["fused_accuracy"] >= 0.80),
    }
