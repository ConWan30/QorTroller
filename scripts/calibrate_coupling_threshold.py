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


def _num(m):
    return None if (m is None or m.group(1) == "None") else float(m.group(1))


def _harvest(log_path: str):
    """Return per-window tuples (coupling_score, negative_control, decoupled_energy) for every computed
    RGC-diag window (coupling_score present = non-abstained), so the decoupled-energy gate can pair coupling
    with its decoupled_energy. Abstained windows (right-stick idle) carry no coupling and are skipped."""
    windows = []
    try:
        text = open(log_path, encoding="utf-8", errors="replace").read()
    except Exception as exc:  # noqa: BLE001
        print(f"could not read log {log_path}: {exc}", flush=True)
        return windows
    for line in text.splitlines():
        if "RGC diag" not in line:
            continue
        tail = line.split("RGC diag:", 1)[-1]
        cs = _num(re.search(r"'coupling_score':\s*([0-9.]+|None)", tail))
        if cs is None:
            continue
        nc = _num(re.search(r"'negative_control':\s*([0-9.]+|None)", tail))
        de = _num(re.search(r"'decoupled_energy':\s*([0-9.]+|None)", tail))
        windows.append((cs, nc, de))
    return windows


def main() -> None:
    from vapi_bridge.coupling_threshold_calibration import (
        calibrate, gate_coupled_by_decoupled_energy, CURRENT_THRESHOLD)

    ap = argparse.ArgumentParser()
    ap.add_argument("--log", default="C:/Users/Contr/bridge_coupling_check.log")
    ap.add_argument("--session-null", action="store_true",
                    help="use the 2026-06-27 shuffle baseline as null if the log has none (pre-surfacing)")
    ap.add_argument("--structured-null", action="store_true",
                    help="assert the null set includes structured decoupled (auto-camera/replay) negatives")
    ap.add_argument("--gate-decoupled", action="store_true",
                    help="apply the decoupled-energy gate: keep the lowest-DE (genuine right-stick-driven) "
                         "windows before calibrating, dropping walking/world-scroll-diluted windows")
    ap.add_argument("--gate-quantile", type=float, default=0.5,
                    help="fraction of computed windows to keep by decoupled_energy (default 0.5 = cleaner half)")
    args = ap.parse_args()

    windows = _harvest(args.log)
    coupled = [c for c, _n, _d in windows]
    null = [n for _c, n, _d in windows if n is not None]
    if not null and args.session_null:
        null = [0.02, 0.03, 0.018, 0.025, 0.015]   # documented 2026-06-27 shuffle baseline (placeholder)
        print("NOTE: log has no negative_control (pre-surfacing) -> using session shuffle baseline placeholder")

    if args.gate_decoupled:
        g = gate_coupled_by_decoupled_energy([(c, d) for c, _n, d in windows], keep_quantile=args.gate_quantile)
        print(f"DECOUPLED-ENERGY GATE: kept {g.n_kept}/{g.n_total} windows (decoupled_energy <= {g.cutoff} "
              f"= p{int(args.gate_quantile*100)}); dropped walking/world-scroll-diluted windows")
        coupled = g.coupling_kept

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
    print("\nNote: shuffle null is the weakest honest null. Before PRODUCTION adoption, add structured "
          "(auto-camera/replay) negatives and re-run with --structured-null. The gate is a RELATIVE rank-filter "
          "(decoupled_energy runs high in busy scenes); a live oracle should rank windows within a burst.")


if __name__ == "__main__":
    main()
