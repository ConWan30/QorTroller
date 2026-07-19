#!/usr/bin/env python3
"""Runner for the QorTroller anti-cheat detector (candidate, advisory) — session verdict over a dump directory.

Reads the nonce-bound R2-onset fire dumps (qortroller-poep-ring-dump-v0) from --dir and emits the
session-level verdict via l9_presence.qortroller_anticheat.detect_session. Advisory only — gates nothing.
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_ROOT, "l9_presence"))
sys.path.insert(0, os.path.join(_ROOT, "scripts"))
from qortroller_anticheat import detect_session  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description="QorTroller anti-cheat detector — session verdict")
    ap.add_argument("--dir", default=os.path.join("audits", "poep_ring_dump"))
    ap.add_argument("--k", type=int, default=5, help="absolute in-band GO floor")
    ap.add_argument("--rate-min", type=float, default=0.20, help="GO-rate floor (threshold scales with N)")
    ap.add_argument("--isi-ms", type=float, default=3000.0, help="inter-stimulus interval for the blind-bot FAR")
    args = ap.parse_args()

    recs = []
    for fp in sorted(glob.glob(os.path.join(args.dir, "*.json"))):
        try:
            r = json.load(open(fp, encoding="utf-8"))
        except Exception:
            continue
        if r.get("schema") == "qortroller-poep-ring-dump-v0":
            recs.append(r)
    if not recs:
        print(f"no fire dumps in {args.dir}")
        return 2

    res = detect_session(recs, k_required=args.k, rate_min=args.rate_min, isi_ms=args.isi_ms)
    print(f"=== QorTroller anti-cheat detector (advisory; gates nothing) ===")
    print(f"  session: {res['n_challenges']} challenges from {args.dir}")
    print(f"  per-fire: GO={res['n_go']} SOFT={res['n_soft']} sub_floor={res['n_sub_floor']} "
          f"no_reaction={res['n_no_reaction']} bad_ref={res['n_bad_reference']}")
    print(f"  go_rate={res['go_rate']}  threshold={res['go_threshold']} (=max(K={res['k_required']}, "
          f"{res['rate_min']:.0%}*N))  blind-bot p_go={res['blind_bot_p_go']} p_sub_floor={res['blind_bot_p_sub_floor']}")
    print(f"  ISI: assumed={res['assumed_isi_ms']:.0f}ms  observed(median, advisory)={res['observed_isi_ms']}")
    print(f"\n  VERDICT: {res['verdict']}")
    print(f"  why: {res['why']}")
    print(f"  blind-bot FAR (TRUE multinomial, fire-time-BLIND, at assumed ISI): {res['blind_bot_far']:.2e}")
    print(f"  blind-bot FAR (loose binomial upper bound): {res['blind_bot_far_binom_ub']:.2e}")
    print(f"  FAR note: {res['far_note']}")
    print(f"  RESIDUAL: {res['residual_note']}")
    print(f"  {res['gate_note']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
