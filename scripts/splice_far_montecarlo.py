#!/usr/bin/env python
"""Composite-authorship replay-splice FAR — Phase 0 Monte Carlo harness (SIMULATED evidence grade).

Measures the composite AUTHORED path's false-accept rate against its actual threat model: a forger replays
the operator's own archived gameplay (real own-handle kill rows) on screen while pressing R2 live on the
certified controller. The composite fires AUTHORED only when a replayed kill row falls inside a live R2
window AND clears match_floor. This quantifies how often that coincidence occurs.

Simulates TIMING COINCIDENCE only — it assumes the replayed rows score as they did live (the Phase 1
physical session tests that assumption; see docs/composite-splice-far-2026-07-01.md). Two attacker timing
models (Poisson/uniform + clustered/burst), both deployed + original window widths, dwell-time sensitivity.

    python scripts/splice_far_montecarlo.py                 # recorded ground truth (3 kills / 640s loop)
    python scripts/splice_far_montecarlo.py --from-archive  # re-derive kill positions from the seg3 archive
"""
from __future__ import annotations

import argparse
import glob
import sys
from pathlib import Path

import numpy as np

_REPO = Path(__file__).resolve().parents[1]

# Deployed R2 window is (50, 5000)ms — widened from the original (50, 900) in 15e2b487 to fix a live
# detection bug (windows closing between loop iterations). Window width is the dominant FAR driver.
WINDOWS = [(5000.0, "DEPLOYED (50,5000)"), (900.0, "ORIGINAL (50,900)")]
DWELLS = [500.0, 2000.0, 4000.0]           # ms the kill row is >=floor on screen (archive samples it once)
FLOOR = 0.66
DEFAULT_KILLS_MS = [0.0, 155315.0, 476543.0]   # 3 kills, re-based (from seg3 archive)
DEFAULT_TSEG_MS = 640_000.0                     # gameplay-segment length


def _kills_from_archive():
    import cv2
    sys.path.insert(0, str(_REPO))
    from l9_presence import killfeed_cv as kc
    anchor = kc.load_anchor(str(_REPO / "l9_presence/assets/own_handle_anchor.png"))
    crops = sorted(glob.glob(str(_REPO / "retina_kf_archive/seg3_*/panel_*.png")),
                   key=lambda p: int(p.split("panel_")[1].split(".")[0]))
    kmax, ygate = kc.KILLER_MAX_FRAC_PANEL, kc.FEED_REGION_MAX_YFRAC
    kills = []
    for p in crops:
        im = cv2.imread(p)
        s, cx, cy, _ = kc.multiscale_match(anchor, kc.binarize_glyphs(im))
        H, W = im.shape[:2]
        if s >= FLOOR and cx is not None and (cy / H) < ygate and (cx / W) < kmax:
            kills.append(int(p.split("panel_")[1].split(".")[0]) / 1e6)
    kills = np.array(sorted(kills))
    return (kills - kills.min()).tolist()


def _far_poisson(kills, T, rate_per_min, d, w, N, rng):
    """Uniform/Poisson model: presses at random times; window [p+50, p+d]. Kill caught iff a press lands
    in (k - w/2 - (d-50), k + w/2 - 50)."""
    lam, eff, hits = rate_per_min / 60000.0, d - 50.0, 0
    for _ in range(N):
        p = rng.uniform(0, T, rng.poisson(lam * T))
        if any(np.any((p > k - w / 2 - eff) & (p < k + w / 2 - 50.0)) for k in kills):
            hits += 1
    rho = 1.0 - (1.0 - min(eff, T) / T) ** (lam * T) if lam > 0 else 0.0
    return hits / N, rho


def _far_burst(kills, T, bursts_per_min, burst_dur, d, w, N, rng):
    """Clustered/burst model: each burst -> one merged coverage window of width (burst_dur + d - 50)."""
    lam, width, hits = bursts_per_min / 60000.0, burst_dur + d - 50.0, 0
    for _ in range(N):
        s = rng.uniform(0, T, rng.poisson(lam * T))
        if any(np.any((s > k - w / 2 - width) & (s < k + w / 2 - 50.0)) for k in kills):
            hits += 1
    rho = 1.0 - (1.0 - min(width, T) / T) ** (lam * T) if lam > 0 else 0.0
    return hits / N, rho


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--from-archive", action="store_true", help="re-derive kill positions by classifying seg3")
    ap.add_argument("--trials", type=int, default=8000)
    ap.add_argument("--tseg-ms", type=float, default=DEFAULT_TSEG_MS)
    args = ap.parse_args()
    rng = np.random.default_rng(42)

    kills = _kills_from_archive() if args.from_archive else list(DEFAULT_KILLS_MS)
    T, N, K = args.tseg_ms, args.trials, len(kills)
    kills = [k - min(kills) + 60_000 for k in kills]   # margin into the loop
    print("SPLICE FAR — Monte Carlo (N=%d), K=%d kills in a %.0fs replay loop" % (N, K, T / 1000))
    print("per-window FAR = P(one R2 window coincidentally catches a kill row); "
          "per-session FAR = P(>=1 of %d caught)" % K)
    print("base-rate: per-session FAR ~= 1-(1-rho)^K, rho = R2 coverage (driven by the window tail)\n")
    for d, lab in WINDOWS:
        print("=== window %s  eff=%.0fms ===" % (lab, d - 50))
        for w in DWELLS:
            pw = min(1.0, K * (d - 50 + w) / T)
            print("  dwell=%4.0fms  per-window FAR=%.4f" % (w, pw))
            for r in [5, 10, 20, 40]:
                fs, rho = _far_poisson(kills, T, r, d, w, N, rng)
                print("       Poisson %2d/min  rho=%.2f  per-session FAR=%.3f" % (r, rho, fs))
        for b in [2, 4, 6, 10]:
            fs, rho = _far_burst(kills, T, b, 1500.0, d, 2000.0, N, rng)
            print("  burst %2d/min (dur1500,w2000)  rho=%.2f  per-session FAR=%.3f" % (b, rho, fs))
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
