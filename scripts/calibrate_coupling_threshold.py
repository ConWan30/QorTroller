"""Coupling-threshold calibration runner (s-coupling-threshold-calibration).

Harvests (coupling_score, negative_control) pairs from RGC-diag log lines and runs the FAR-controlled
calibration. coupling_score from active-aim windows is the COUPLED class; negative_control (time-shuffled
chance null) is the NULL class. READ-ONLY (reads a log, computes; no capture, no controller writes).

  python scripts/calibrate_coupling_threshold.py --log C:/Users/Contr/bridge_coupling_check.log

Note: negative_control is only logged after the RGC.status() surfacing change (needs a bridge restart).
On a pre-surfacing log only coupling_score is present; pass --session-null to use the documented 2026-06-27
shuffle baseline as a placeholder so the runner still produces an honest (INSUFFICIENT_DATA) verdict.
"""
from __future__ import annotations

import argparse
import os
import re
import sys

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_REPO, "bridge"))


def _harvest(log_path: str):
    coupled, null = [], []
    try:
        text = open(log_path, encoding="utf-8", errors="replace").read()
    except Exception as exc:  # noqa: BLE001
        print(f"could not read log {log_path}: {exc}", flush=True)
        return coupled, null
    for line in text.splitlines():
        if "RGC diag" not in line:
            continue
        tail = line.split("RGC diag:", 1)[-1]
        cs = re.search(r"'coupling_score':\s*([0-9.]+)", tail)
        nc = re.search(r"'negative_control':\s*([0-9.]+)", tail)
        if cs:
            coupled.append(float(cs.group(1)))
        if nc:
            null.append(float(nc.group(1)))
    return coupled, null


def main() -> None:
    from vapi_bridge.coupling_threshold_calibration import calibrate, CURRENT_THRESHOLD

    ap = argparse.ArgumentParser()
    ap.add_argument("--log", default="C:/Users/Contr/bridge_coupling_check.log")
    ap.add_argument("--session-null", action="store_true",
                    help="use the 2026-06-27 shuffle baseline as null if the log has none (pre-surfacing)")
    ap.add_argument("--structured-null", action="store_true",
                    help="assert the null set includes structured decoupled (auto-camera/replay) negatives")
    args = ap.parse_args()

    coupled, null = _harvest(args.log)
    if not null and args.session_null:
        null = [0.02, 0.03, 0.018, 0.025, 0.015]   # documented 2026-06-27 shuffle baseline (placeholder)
        print("NOTE: log has no negative_control (pre-surfacing) -> using session shuffle baseline placeholder")
    print(f"harvested: coupled(coupling_score) N={len(coupled)} | null(negative_control) N={len(null)}")
    if coupled:
        print(f"  coupled range {min(coupled):.3f}..{max(coupled):.3f}")
    if null:
        print(f"  null    range {min(null):.3f}..{max(null):.3f}")
    res = calibrate(coupled, null, structured_null=args.structured_null)
    print(f"\ncurrent threshold (hypothesis): {CURRENT_THRESHOLD}")
    print(f"VERDICT: {res.verdict}")
    print(f"  recommended_threshold: {res.recommended_threshold}  (FAR {res.far_at_threshold}, "
          f"TPR {res.tpr_at_threshold}, separation {res.separation})")
    for c in res.caveats:
        print(f"  - {c}")
    print("\nTo collect real data: restart the bridge (surfacing change logs negative_control), play active-aim "
          "Remote-Play sessions, then re-run this on the fresh log. Target N>=30/class; add structured "
          "(auto-camera/replay) negatives before adopting any threshold.")


if __name__ == "__main__":
    main()
