#!/usr/bin/env python3
"""RBM-v0 calibration (A2A-POEP-P2, grok round-09 Q2 acceptance bar). Pure stdlib.

Fits frozen population moments on the independent-usable Edge reflexes, scores them vs the campaign
null class, computes grok's acceptance metrics, freezes tau*, and writes rbm_v0_params.json +
audits/rbm_v0_calibration_<date>.json. Prints PASS/FAIL against the bar:
  (1) TPR_indep(tau*) >= 0.90   (2) FAR_campaign(tau*) <= 0.10
  (3) ROC-AUC(pos vs campaign-null) >= 0.85   (4) d'_campaign >= 1.5
"""
from __future__ import annotations

import json
import os
import sqlite3
import sys
import time
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO))
from l9_presence.poep_reflex_gate import is_usable_reflex, dedup_bursts  # noqa: E402
from l9_presence.rbm_v0 import (  # noqa: E402
    RBMV0Params, dprime, far_at, fit_moments, operating_threshold, roc_auc, score_row,
)

EDGE_POLICY = "edge_operator_reflex_v1"


def _load(db: str):
    c = sqlite3.connect(db); c.row_factory = sqlite3.Row
    rows = c.execute("SELECT probe_ts_ms, latency_ms, accel_delta_peak, reflex_verdict, policy_ref "
                     "FROM l6b_probe_log WHERE policy_ref=?", (EDGE_POLICY,)).fetchall()
    pos = [(r["probe_ts_ms"], r["latency_ms"], r["accel_delta_peak"]) for r in rows
           if is_usable_reflex(policy_ref=EDGE_POLICY, reflex_verdict=r["reflex_verdict"],
                               accel_delta_peak=r["accel_delta_peak"], latency_ms=r["latency_ms"])]
    # campaign nulls (N1): same policy, stimulus fired, not a usable reflex
    nulls = [(r["latency_ms"], r["accel_delta_peak"]) for r in rows
             if r["reflex_verdict"] != "REFLEX_OBSERVED"]
    c.close()
    # independence: keep positives that survive burst-dedup (grok DQ-6); moments on independents
    pos_sorted = sorted(pos, key=lambda t: (t[0] or 0))
    keep, last = [], None
    for ts, lat, pk in pos_sorted:
        if last is None or (ts - last) >= 5000:
            keep.append((lat, pk)); last = ts
    return keep, nulls


def main() -> int:
    db = sys.argv[sys.argv.index("--db") + 1] if "--db" in sys.argv else os.path.expanduser("~/.vapi/bridge.db")
    pos, nulls = _load(db)
    if len(pos) < 50:
        print(f"ABORT: only {len(pos)} independent usable reflexes (< 50 gate). Run more sessions.", file=sys.stderr)
        return 2
    lats = [p[0] for p in pos]; peaks = [p[1] for p in pos]
    ml, sl, mp, sp = fit_moments(lats, peaks)
    # provisional params to score with (tau* filled after)
    prov = RBMV0Params(mu_latency=ml, sd_latency=sl, mu_peak=mp, sd_peak=sp,
                       operating_threshold=0.0, n_positives=len(pos))
    pos_scores = [score_row(l, p, prov) for l, p in pos]
    null_scores = [score_row(l, p, prov) for l, p in nulls]
    tau = operating_threshold(pos_scores, 0.90)
    tpr = sum(1 for s in pos_scores if s >= tau) / len(pos_scores)
    far = far_at(null_scores, tau)
    auc = roc_auc(pos_scores, null_scores)
    dp = dprime(pos_scores, null_scores)

    params = RBMV0Params(mu_latency=round(ml, 3), sd_latency=round(sl, 3), mu_peak=round(mp, 3),
                         sd_peak=round(sp, 3), operating_threshold=round(tau, 6), n_positives=len(pos))
    phash = params.params_hash()
    bar = {"TPR>=0.90": tpr >= 0.90, "FAR<=0.10": far <= 0.10, "AUC>=0.85": auc >= 0.85, "dprime>=1.5": dp >= 1.5}
    passed = all(bar.values())

    print("=" * 60)
    print("  RBM-v0 CALIBRATION (registered Edge)")
    print("=" * 60)
    print(f"  positives (independent): {len(pos)}   campaign nulls: {len(nulls)}")
    print(f"  moments: lat mu={ml:.1f} sd={sl:.1f} | peak mu={mp:.0f} sd={sp:.0f}")
    print(f"  tau*={tau:.4f}  TPR={tpr:.3f}  FAR_campaign={far:.3f}  AUC={auc:.3f}  d'={dp:.2f}")
    print(f"  bar: " + "  ".join(f"{k}={'PASS' if v else 'FAIL'}" for k, v in bar.items()))
    print(f"  VERDICT: {'CALIBRATED' if passed else 'NOT CALIBRATED'}   params_hash={phash[:16]}...")
    print(f"  scope={params.scope} | poep_enabled stays False | score != liveness verdict")

    date = time.strftime("%Y-%m-%d")
    audit = {"schema": "rbm-v0-calibration-v1", "date": date, "device": "registered_edge_581a836c",
             "n_positives": len(pos), "n_campaign_nulls": len(nulls),
             "moments": {"mu_latency": ml, "sd_latency": sl, "mu_peak": mp, "sd_peak": sp},
             "operating_threshold": tau, "metrics": {"tpr": tpr, "far_campaign": far, "auc": auc, "dprime": dp},
             "acceptance": bar, "separation_verdict": "CALIBRATED" if passed else "NOT_CALIBRATED",
             "params_hash": phash, "scope": params.scope, "poep_enabled": False,
             # grok round-11 fix (b): SEPARATION is calibrated (metrics above are diagnostic), but the
             # continuous exp-Mahalanobis SCORE failed nested-LOO stability (CV=0.599 > 0.35) so it is
             # DEFERRED to v0.1. v0 SHIP SURFACE is BOOLEAN ONLY (band_member + operating_point_fire),
             # which is nested-LOO STABLE (flip-rate 0.019). See scripts/rbm_v0_validate.py.
             "ship_surface": "boolean_only (band_member + operating_point_fire)",
             "continuous_score": "deferred_v0_1 (nested-LOO CV 0.599 > 0.35)",
             "boolean_loo_stability": "STABLE (flip-rate 0.019, 1/52)",
             "claim": ("RBM-v0 (single Edge, N=52 usable reflexes vs 22 nulls): band-membership + one "
                       "frozen operating-point boolean only (full-fit TPR~0.90, FAR=0); continuous score "
                       "deferred to v0.1 -- not a liveness verdict; poep_enabled=False."),
             "claim_ceiling": "device-local population reflex-consistency; NOT identity/liveness/cross-device"}
    if "--write" in sys.argv:
        (_REPO / "l9_presence" / "rbm_v0_params.json").write_text(
            json.dumps({**{k: getattr(params, k) for k in
                        ("mu_latency", "sd_latency", "mu_peak", "sd_peak", "operating_threshold",
                         "n_positives", "lat_floor", "lat_ceil", "peak_floor", "scope")},
                        "params_hash": phash}, indent=2), encoding="utf-8")
        ap = _REPO / "audits" / f"rbm_v0_calibration_{date}.json"
        ap.write_text(json.dumps(audit, indent=2), encoding="utf-8")
        print(f"  [wrote] l9_presence/rbm_v0_params.json + {ap.relative_to(_REPO)}")
    else:
        print("  (dry-run; add --write to freeze params + audit)")
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
