"""Investigates round-05's flagged-but-unverified L2C hypothesis (docs/a2a/
live-l2b-unit-scale-investigation/round-05-claude-open.md, "Open question
surfaced"): does the batch-timestamp-collapse mechanism that broke L2B (and
was found in L5) cause a VELOCITY BLOWUP in L2C's stick-velocity computation,
rather than the "always decoupled" symptom L2B showed?

L2C's push_snapshot() (controller/l2c_stick_imu_correlation.py:167-190)
computes dt_s = max(dt_ms/1000, 1e-4) and vx = (rx-prev_rx)/32768/dt_s. If
dt_ms collapses toward 0 under batch processing, dt_s clamps near the 1e-4
floor and vx could be driven toward extreme values -- structurally different
from L2B's "always decoupled" failure mode.

Read-only investigation, no production code touched. L2C already has the
getattr(snap, "timestamp_ms", None) fallback pattern (same as L2B had before
its fix, same as L5 had before its fix) -- and dualshock_integration.py's
already-shipped C-fail-4 fix (_stamp_frame_collection_times) ALREADY stamps
real timestamps onto every frame it processes, which L2C already prefers
when present. So this investigation answers two related but distinct
questions:
  (a) HISTORICAL: would the pre-fix batch-collapsed state (no timestamp_ms,
      tight-loop monotonic() calls) actually have produced a velocity
      blowup that corrupted classification, confirming round-05's concern
      was real?
  (b) CURRENT: does L2C behave correctly now that it receives the
      already-shipped real per-frame timestamps?

A key mathematical subtlety worth testing rather than assuming: if the
batch-collapsed dt_s ends up roughly CONSTANT across a whole batch (every
push_snapshot call in a tight loop takes about the same wall-clock time),
vx would be uniformly rescaled by a constant factor -- and Pearson
correlation is invariant to constant rescaling of one variable, the same
property that made L2C immune to the ORIGINAL unit-scale bug. The exposure
would only be real if dt_s is NON-uniformly collapsed (irregular jitter
between calls), which requires empirical measurement, not assumption.

Usage: python scripts/diag_l2c_velocity_blowup_repro.py
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "controller"))

from l2c_stick_imu_correlation import StickImuCorrelationOracle, _MIN_FRAMES, _CORR_THRESHOLD  # noqa: E402

N_FRAMES = 120  # > _MIN_FRAMES=80
LAG = 15        # frames, within [_LAG_MIN_FRAMES=10, _LAG_MAX_FRAMES=60]
REAL_DT_MS = 8.0  # matches _poll_frames' target ~120Hz cadence


def _build_causal_signal(seed: int = 99):
    """Genuine causally-coupled human-like pattern: stick velocity signal,
    gyro_z responding LAG frames later -- mirrors the oracle's own test
    suite's synthetic-human pattern (test_l2c_stick_imu_correlation.py
    TestSyntheticHuman)."""
    rng = np.random.default_rng(seed)
    vx_signal = rng.normal(0, 1000, size=N_FRAMES)
    rx = np.cumsum(vx_signal) % 32768
    gz = np.zeros(N_FRAMES)
    for i in range(N_FRAMES):
        gz[i] = vx_signal[max(0, i - LAG)] * 0.6 + rng.normal(0, 15)
    return rx.astype(int), gz


def _snap(rx: int, gz: float, timestamp_ms: float | None = None):
    attrs = {"right_stick_x": rx, "gyro_z": gz}
    if timestamp_ms is not None:
        attrs["timestamp_ms"] = timestamp_ms
    return type("_S", (), attrs)()


def run_mode_a_batch_collapsed(rx_arr, gz_arr) -> tuple:
    """Reproduces the PRE-FIX state: tight loop, no timestamp_ms, real
    monotonic() calls with no artificial delay between them -- exactly what
    dualshock_integration.py's for-snap-in-frames loop looked like for L2C
    before the C-fail-4 fix started stamping timestamp_ms on every frame."""
    oracle = StickImuCorrelationOracle()
    dt_s_observed = []
    for rx, gz in zip(rx_arr, gz_arr):
        prev_ts = oracle._prev_ts_ms
        was_first = oracle._first_frame
        oracle.push_snapshot(_snap(int(rx), float(gz)))
        if not was_first:
            dt_s_observed.append((oracle._prev_ts_ms - prev_ts) / 1000.0)
    return oracle, dt_s_observed


def run_mode_b_real_timestamps(rx_arr, gz_arr) -> StickImuCorrelationOracle:
    """Current, fixed state: each snap carries a realistic ~8ms-spaced
    timestamp_ms, matching what dualshock_integration.py's
    _stamp_frame_collection_times() now actually provides in production."""
    oracle = StickImuCorrelationOracle()
    t = 0.0
    for rx, gz in zip(rx_arr, gz_arr):
        oracle.push_snapshot(_snap(int(rx), float(gz), timestamp_ms=t))
        t += REAL_DT_MS
    return oracle


def _report(name: str, oracle: StickImuCorrelationOracle) -> None:
    feats = oracle.extract_features()
    if feats is None:
        print(f"{name}: extract_features() = None")
        return
    print(f"{name}: max_causal_corr={feats.max_causal_corr:.4f} "
          f"lag_at_max={feats.lag_at_max} anomaly={feats.anomaly} "
          f"classify_fires={oracle.classify() is not None} "
          f"humanity_score={oracle.humanity_score():.4f}")


def main() -> None:
    rx_arr, gz_arr = _build_causal_signal()

    print("--- MODE A: batch-collapsed (pre-fix reproduction, no timestamp_ms) ---")
    oracle_a, dt_s_observed = run_mode_a_batch_collapsed(rx_arr, gz_arr)
    dt_s_arr = np.array(dt_s_observed)
    print(f"  observed dt_s: min={dt_s_arr.min():.6f}s max={dt_s_arr.max():.6f}s "
          f"mean={dt_s_arr.mean():.6f}s std={dt_s_arr.std():.6f}s "
          f"cv={dt_s_arr.std()/dt_s_arr.mean():.4f} "
          f"n_at_floor(1e-4)={(dt_s_arr <= 1.0001e-4).sum()}/{len(dt_s_arr)}")
    vx_arr = np.array(oracle_a._stick_vx)
    print(f"  resulting vx: min={vx_arr.min():.2e} max={vx_arr.max():.2e} "
          f"mean_abs={np.abs(vx_arr).mean():.2e}")
    _report("Mode A (batch-collapsed)", oracle_a)

    print("\n--- MODE B: real per-frame timestamps (current, fixed production state) ---")
    oracle_b = run_mode_b_real_timestamps(rx_arr, gz_arr)
    vx_b = np.array(oracle_b._stick_vx)
    print(f"  resulting vx: min={vx_b.min():.2e} max={vx_b.max():.2e} "
          f"mean_abs={np.abs(vx_b).mean():.2e}")
    _report("Mode B (real timestamps)", oracle_b)

    print("\n--- verdict ---")
    feats_a = oracle_a.extract_features()
    feats_b = oracle_b.extract_features()
    if feats_a is not None and feats_b is not None:
        corr_diff = abs(feats_a.max_causal_corr - feats_b.max_causal_corr)
        same_classify = (oracle_a.classify() is None) == (oracle_b.classify() is None)
        print(f"max_causal_corr difference: {corr_diff:.4f}")
        print(f"classify() agreement: {'SAME' if same_classify else 'DIVERGED'}")
        if not same_classify:
            print("VELOCITY-BLOWUP HYPOTHESIS CONFIRMED: batch-collapsed processing "
                  "produces a DIFFERENT classify() verdict than real-timestamp "
                  "processing on the IDENTICAL underlying stick/gyro signal.")
        elif corr_diff > 0.1:
            print("PARTIAL: classify() verdict agrees, but max_causal_corr differs "
                  "meaningfully -- worth a closer look even though the binary "
                  "outcome matches.")
        else:
            print("VELOCITY-BLOWUP HYPOTHESIS REFUTED (this signal/scenario): "
                  "batch-collapsed and real-timestamp processing produce "
                  "consistent results -- correlation's scale-invariance appears "
                  "to protect L2C here, matching the theoretical prediction that "
                  "a roughly-uniform dt_s collapse doesn't corrupt correlation.")
    else:
        print("One or both modes returned None from extract_features() -- inconclusive.")


if __name__ == "__main__":
    main()
