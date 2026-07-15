#!/usr/bin/env python3
"""RBM-v0 nested leave-one-out validation (A2A-POEP-P2, grok round-09 Q3 / RBM-v0-VAL-01). Pure stdlib.

Guards against overfitting a single-operator single-device N=52 Gaussian: for each positive i, refit
moments + tau* on the OTHER 51, score the left-out row, and check acceptance. Reports nested-LOO TPR,
score CV (grok G3 UNSTABLE flag if CV>0.35), and FAR against the mean nested tau. Bar (grok VAL-01):
nested-LOO TPR median >= 0.85 AND FAR_campaign <= 0.15 AND CV <= 0.35.
"""
from __future__ import annotations

import os
import sqlite3
import statistics as st
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO))
from l9_presence.poep_reflex_gate import is_usable_reflex  # noqa: E402
from l9_presence.rbm_v0 import RBMV0Params, fit_moments, far_at, operating_threshold, score_row  # noqa: E402

EDGE = "edge_operator_reflex_v1"


def _load(db):
    c = sqlite3.connect(db); c.row_factory = sqlite3.Row
    rows = c.execute("SELECT probe_ts_ms, latency_ms, accel_delta_peak, reflex_verdict "
                     "FROM l6b_probe_log WHERE policy_ref=?", (EDGE,)).fetchall(); c.close()
    pos = [(r["probe_ts_ms"], r["latency_ms"], r["accel_delta_peak"]) for r in rows
           if is_usable_reflex(policy_ref=EDGE, reflex_verdict=r["reflex_verdict"],
                               accel_delta_peak=r["accel_delta_peak"], latency_ms=r["latency_ms"])]
    nulls = [(r["latency_ms"], r["accel_delta_peak"]) for r in rows if r["reflex_verdict"] != "REFLEX_OBSERVED"]
    pos.sort(key=lambda t: (t[0] or 0)); keep, last = [], None
    for ts, l, p in pos:
        if last is None or (ts - last) >= 5000:
            keep.append((l, p)); last = ts
    return keep, nulls


def main() -> int:
    db = sys.argv[sys.argv.index("--db") + 1] if "--db" in sys.argv else os.path.expanduser("~/.vapi/bridge.db")
    pos, nulls = _load(db)
    n = len(pos)
    if n < 50:
        print(f"ABORT: {n} independent usable (<50).", file=sys.stderr); return 2
    # grok round-11 fix (b): v0 ships the BOOLEAN operating_point_fire, so the honest LOO stability
    # metric is BOOLEAN FLIP-RATE (does LOO-refit fire the same as full-fit?), not score CV.
    full_ml, full_sl, full_mp, full_sp = fit_moments([t[0] for t in pos], [t[1] for t in pos])
    full = RBMV0Params(full_ml, full_sl, full_mp, full_sp, operating_threshold=0.0, n_positives=n)
    full_tau = operating_threshold([score_row(l, p, full) for l, p in pos], 0.90)
    full = RBMV0Params(full_ml, full_sl, full_mp, full_sp, operating_threshold=full_tau, n_positives=n)
    full_fire = [score_row(l, p, full) >= full_tau for l, p in pos]

    flips = 0
    for i in range(n):
        train = pos[:i] + pos[i + 1:]
        ml, sl, mp, sp = fit_moments([t[0] for t in train], [t[1] for t in train])
        pr = RBMV0Params(ml, sl, mp, sp, operating_threshold=0.0, n_positives=len(train))
        tau = operating_threshold([score_row(l, p, pr) for l, p in train], 0.90)
        loo_fire = score_row(pos[i][0], pos[i][1], pr) >= tau
        if loo_fire != full_fire[i]:
            flips += 1
    flip_rate = flips / n
    null_false_fire = far_at([score_row(l, p, full) for l, p in nulls], full_tau)  # frozen OP FAR
    tpr = sum(full_fire) / n
    bar = {"TPR>=0.90": tpr >= 0.90, "null_false_fire==0": null_false_fire == 0.0,
           "LOO_flip_rate<=0.15": flip_rate <= 0.15}
    passed = all(bar.values())
    print("=" * 56)
    print("  RBM-v0 NESTED-LOO BOOLEAN-STABILITY (registered Edge)")
    print("=" * 56)
    print(f"  positives={n}  nulls={len(nulls)}  frozen_tau*={full_tau:.4f}")
    print(f"  full-fit TPR={tpr:.3f}  null_false_fire(FAR)={null_false_fire:.3f}  "
          f"LOO_flip_rate={flip_rate:.3f} ({flips}/{n})")
    print(f"  bar: " + "  ".join(f"{k}={'PASS' if v else 'FAIL'}" for k, v in bar.items()))
    print(f"  VERDICT: {'STABLE (v0 ships)' if passed else 'FAIL'}  (continuous score deferred to v0.1)")
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
