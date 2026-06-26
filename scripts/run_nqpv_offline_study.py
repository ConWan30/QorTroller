"""Run the NQPV RETINA-EXCL-2 study over the REAL 1000 Hz human corpus + synthetic adversaries.

Builds human-positive NqpvCorpusRecords from sessions/human/hw_nqpv_*.json via the offline humanity
adapter (1000 Hz extractor + L4 Mahalanobis LOO + study-only p_L4 re-anchor), synthesizes the modeled
adversary corpus, and runs the harness in the l4l5l6-only (pilot) regime — the regime the offline
adapter actually produces (cco/poep/coupled-retina abstain).

HONEST: ONE human at N=10 ("low confidence") -> feasibility, not a population claim. Expect FAIL in the
l4l5l6-only regime (replay-class adversaries carry human physics) — the presence oracles are the unlock.
No FROZEN/PoAC/chain/IOTX; offline only; reads gitignored sessions.

Usage:
    PYTHONPATH=bridge python scripts/run_nqpv_offline_study.py
    PYTHONPATH=bridge python scripts/run_nqpv_offline_study.py --glob 'sessions/human/hw_nqpv_*.json' --adv-per-class 20
"""
from __future__ import annotations

import argparse
import glob
import math

from vapi_bridge.nqpv_offline_humanity import build_human_corpus, DEFAULT_ANOMALY_THRESHOLD
from vapi_bridge.nqpv_adversary_synth import synthesize
from vapi_bridge.nqpv_study_harness import run_study, PILOT_LIVE_ORACLES


def main() -> int:
    ap = argparse.ArgumentParser(description="NQPV offline study over the real 1000 Hz human corpus")
    ap.add_argument("--glob", default="sessions/human/hw_nqpv_*.json", help="human session glob")
    ap.add_argument("--adv-per-class", type=int, default=20, help="synthetic adversaries per class")
    ap.add_argument("--seed", type=int, default=1337)
    args = ap.parse_args()

    files = sorted(glob.glob(args.glob))
    if not files:
        print(f"no sessions matched {args.glob!r}")
        return 1
    print(f"building human corpus from N={len(files)} real 1000 Hz sessions...")
    humans = build_human_corpus(files)

    print("--- real human sessions (LOO L4 Mahalanobis) ---")
    for r in humans:
        d = -DEFAULT_ANOMALY_THRESHOLD * math.log2(r.humanity_prob) if r.humanity_prob > 0 else 99.0
        print(f"  {r.device_id[:8]} l4_NOMINAL={r.l4_l5_l6_ok} p_L4={r.humanity_prob:.3f} implied_d~{d:.2f}")
    nom = sum(1 for r in humans if r.l4_l5_l6_ok)
    print(f"L4-NOMINAL humans: {nom}/{len(humans)} (threshold {DEFAULT_ANOMALY_THRESHOLD})")

    advs = synthesize(n_per_class=args.adv_per_class, seed=args.seed)
    rep = run_study(humans + advs, live_oracles=PILOT_LIVE_ORACLES)
    print("--- STUDY (real humans + synthetic adversaries, l4l5l6-only regime) ---")
    print(f"  feasibility={rep.feasibility}  n_human={rep.n_human}  n_adversary={rep.n_adversary}")
    print(f"  best_single={rep.best_single_oracle}={rep.best_single_tar:.3f}")
    print(f"  max TAR={max(p.tar for p in rep.roc):.3f}  min adversary FAR={min(p.far for p in rep.roc):.3f}")
    print(f"  {rep.notes}")
    print("\nNOTE: FAIL in this regime is the EXPECTED, honest result — L4 alone cannot separate "
          "replay-class adversaries that carry real human physics. The presence oracles (PoEP + "
          "coupled-retina) are the certification unlock (separate, hardware/L6B-gated).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
