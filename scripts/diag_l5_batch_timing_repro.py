"""Investigates whether L5 (controller/temporal_rhythm_oracle.py) shares the
batch-timestamp-collapse exposure found and fixed in L2B (docs/a2a/
live-l2b-unit-scale-investigation/). Read-only investigation, no production
code touched -- this script only tests a hypothesis, it does not fix anything.

L5's push_snapshot() is MORE exposed than L2B/L2C's was, not less: it never
even attempts getattr(snap, "timestamp_ms", None) -- every single call
unconditionally uses `now_wall = time.monotonic() * 1000.0`. The C-fail-4 fix
(which stamps snap.timestamp_ms) is therefore a structural no-op for L5 --
shipping it did not touch this exposure at all.

L5's mechanism is different from L2B's (interval CV/entropy/quantization
across REPEATED presses of the same button, not a single precursor-window
check per press), so the SAME fix would not obviously transfer even if this
confirms a bug -- this script only tests whether one exists, matching the
"ground first, then decide" discipline used throughout the L2B investigation.

Mechanism under test: dualshock_integration.py feeds L5 via the identical
`for snap in frames: oracle.push_snapshot(snap)` pattern as L2B/L2C
(line ~2312), over a batch collected across a real ~1s window
(_interval=1.0s default). Since L5 always uses call-time monotonic(), TWO
real button presses that both happen to land within the SAME ~1s batch would
get their `now_wall` values computed within the same few-ms processing burst
-- collapsing their TRUE inter-press gap toward ~0, instead of the real gap
that occurred in the physical world. Presses straddling a batch boundary
would instead reflect roughly the ~1s batch-processing cadence, not their
true sub-second gap either -- a different, second-order distortion this
script does not attempt to isolate.

This only matters for INTERVAL computation, not edge DETECTION -- L5 only
appends an interval on a rising edge, and doesn't care about the volume/
spacing of non-press frames in between. This lets the repro skip simulating
full 125-frame raw-HID batches (unlike the L2B repro, which needed real IMU
history) and instead directly control real-time gaps between rising-edge
events only -- a legitimate simplification of the SAME mechanism, not a
different one.

Usage: python scripts/diag_l5_batch_timing_repro.py
(takes ~30-45 real seconds -- both modes replay the same real press schedule)
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "controller"))

from temporal_rhythm_oracle import TemporalRhythmOracle, CROSS_BIT  # noqa: E402

BATCH_INTERVAL_S = 1.0  # matches dualshock_integration.py's default self._interval


def _snap(pressed: bool):
    return type("_S", (), {"buttons": CROSS_BIT if pressed else 0, "r2_trigger": 0, "l2_trigger": 0})()


def build_press_schedule(seed: int = 42, n_presses: int = 30, mash_prob: float = 0.35) -> list[float]:
    """Deterministic, realistic-shaped inter-press gaps (seconds): a mix of
    fast double-taps (0.05-0.15s, common when mashing a button) and normal
    spaced presses (0.4-1.3s) -- not adversarial, just plausible human play.
    Returns cumulative real press TIMES (seconds from t=0), not gaps."""
    rng = np.random.default_rng(seed)
    gaps = []
    for i in range(n_presses - 1):
        if rng.random() < mash_prob:  # a quick double-tap
            gaps.append(float(rng.uniform(0.05, 0.15)))
        else:
            gaps.append(float(max(0.35, rng.normal(0.75, 0.3))))
    times = [0.0]
    for g in gaps:
        times.append(times[-1] + g)
    return times


def run_mode_b_realtime(press_times: list[float]) -> TemporalRhythmOracle:
    """Ground truth: push_snapshot called at real wall-clock instants matching
    each press's true intended time -- no batching at all."""
    oracle = TemporalRhythmOracle()
    t0 = time.monotonic()
    for pt in press_times:
        target = t0 + pt
        now = time.monotonic()
        if target > now:
            time.sleep(target - now)
        oracle.push_snapshot(_snap(False))  # ensure release state between presses
        oracle.push_snapshot(_snap(True))   # the rising edge
    return oracle


def run_mode_a_batched(press_times: list[float]) -> TemporalRhythmOracle:
    """Bridge-style: presses grouped into BATCH_INTERVAL_S-wide real-time
    batches; all rising edges within one batch are pushed in a tight loop
    (no delay) once that batch's real time window has elapsed, matching
    dualshock_integration.py's for-snap-in-frames processing of an
    already-collected batch."""
    oracle = TemporalRhythmOracle()
    max_batch = int(press_times[-1] // BATCH_INTERVAL_S) + 1
    batches: dict[int, list[float]] = {i: [] for i in range(max_batch + 1)}
    for pt in press_times:
        batches[int(pt // BATCH_INTERVAL_S)].append(pt)

    t0 = time.monotonic()
    for batch_idx in range(max_batch + 1):
        batch_end_real = t0 + (batch_idx + 1) * BATCH_INTERVAL_S
        now = time.monotonic()
        if batch_end_real > now:
            time.sleep(batch_end_real - now)
        for _pt in batches[batch_idx]:
            oracle.push_snapshot(_snap(False))
            oracle.push_snapshot(_snap(True))
    return oracle


def main() -> None:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--n-presses", type=int, default=30)
    ap.add_argument("--mash-prob", type=float, default=0.35)
    args = ap.parse_args()

    press_times = build_press_schedule(seed=args.seed, n_presses=args.n_presses, mash_prob=args.mash_prob)
    n = len(press_times)
    total_s = press_times[-1]
    same_batch_pairs = sum(
        1 for i in range(1, n)
        if int(press_times[i] // BATCH_INTERVAL_S) == int(press_times[i - 1] // BATCH_INTERVAL_S)
    )
    print(f"Press schedule: {n} presses over {total_s:.2f}s real time, "
          f"{same_batch_pairs} consecutive pairs land in the same ~1s batch")

    print("\n--- MODE B: realtime (ground truth, no batching) ---")
    t_start = time.time()
    oracle_b = run_mode_b_realtime(press_times)
    print(f"  ({time.time() - t_start:.1f}s real time elapsed)")
    feats_b = oracle_b.extract_features()

    print("\n--- MODE A: bridge-style batched (for snap in frames pattern) ---")
    t_start = time.time()
    oracle_a = run_mode_a_batched(press_times)
    print(f"  ({time.time() - t_start:.1f}s real time elapsed)")
    feats_a = oracle_a.extract_features()

    def _report(name: str, feats) -> None:
        if feats is None:
            print(f"{name}: extract_features() = None (< _MIN_SAMPLES)")
            return
        print(f"{name}: n={feats.sample_count} source={feats.source} "
              f"cv={feats.cv:.4f} entropy_bits={feats.entropy_bits:.4f} "
              f"quant_score={feats.quant_score:.4f} anomaly_signals={feats.anomaly_signals}/3 "
              f"classify_fires={feats.anomaly_signals >= 2}")

    print("\n--- comparison ---")
    _report("Mode B (realtime)", feats_b)
    _report("Mode A (batched)", feats_a)

    if feats_a is not None and feats_b is not None:
        if feats_a.anomaly_signals > feats_b.anomaly_signals:
            print(f"\nDIVERGENCE CONFIRMED: batched processing fires MORE anomaly signals "
                  f"({feats_a.anomaly_signals}/3) than realtime ({feats_b.anomaly_signals}/3) "
                  f"on the IDENTICAL underlying press schedule -- same class of bug as L2B, "
                  f"pushing genuinely human timing toward a false TEMPORAL_ANOMALY read.")
        elif feats_a.anomaly_signals == feats_b.anomaly_signals:
            print(f"\nNO DIVERGENCE in signal count ({feats_a.anomaly_signals}/3 both) -- "
                  f"raw cv/entropy/quant numbers above may still differ; inspect them directly.")
        else:
            print(f"\nUNEXPECTED: batched fires FEWER signals than realtime -- re-examine.")


if __name__ == "__main__":
    main()
