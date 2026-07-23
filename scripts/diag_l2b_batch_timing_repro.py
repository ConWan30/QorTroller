"""C-fail-4 empirical repro (grok unavailable -- proceeding solo per operator
instruction; leaning harder on empirical verification since no adversarial
audit is available this round).

Round-05's hypothesis (docs/a2a/live-l2b-unit-scale-investigation/
round-05-claude-open.md): InputSnapshot has no timestamp_ms field;
ImuPressCorrelationOracle.push_snapshot() falls back to time.monotonic()*1000.0
on every call; dualshock_integration.py's _session_loop collects a full
1-second batch via _poll_frames (dt_ms=8, ~120Hz) BEFORE the oracle-feeding
loop ever runs -- so "for snap in frames: oracle.push_snapshot(snap)" executes
as a tight few-millisecond loop AFTER the real 1-second collection window has
already elapsed, collapsing ~125 real per-frame timestamps into a
near-simultaneous cluster and breaking the 5-80ms precursor window regardless
of threshold.

This script builds ONE real batch -- via real time.sleep(dt_ms/1000) between
each simulated frame "collection", exactly matching _poll_frames' true 8ms
cadence -- with a genuinely embedded, physically-realistic precursor+press
pattern (gyro spike ~24-40ms before each Cross rising edge, squarely inside
the 5-80ms precursor window). The IDENTICAL batch is then fed through
push_snapshot() TWO ways, using the REAL, unmodified ImuPressCorrelationOracle
class both times:

  MODE A "bridge-style" (batch replay): for snap in frames:
    oracle.push_snapshot(snap) -- tight loop, no delay between calls --
    exactly matching dualshock_integration.py's post-hoc processing of an
    already-collected batch.
  MODE B "realtime-style" (live replay): push_snapshot(snap) called AS EACH
    FRAME IS COLLECTED, with the SAME real 8ms delay between calls -- matching
    scripts/diag_l2b_live_probe.py's (Step B / C-fail-2) approach.

If the hypothesis is correct: Mode A's recorded _imu_history timestamps
cluster into a tiny span (order of the loop's real execution time, not
~1000ms), the precursor is never found in-window, coupled_fraction stays low
even though a real, well-formed precursor pattern was injected. Mode B's
history should span close to the true ~1000ms collection window and correctly
detect the injected precursors.

No hardware, no bridge, no production code touched.
"""
from __future__ import annotations

import statistics
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "controller"))

from l2b_imu_press_correlation import ImuPressCorrelationOracle, CROSS_BIT  # noqa: E402

N_FRAMES = 125          # ~1s at dt_ms=8, matching _poll_frames' real cadence
DT_MS = 8.0
N_PRESS_CYCLES = 16     # >= _MIN_PRESS_EVENTS=15
PRECURSOR_LAG_FRAMES = 4   # 4 * 8ms = 32ms before the press -- inside [5,80]ms window
BASELINE_GYRO_MAG = 2.0
SPIKE_GYRO_MAG = 80.0   # well above default adaptive_thresh (~30-70 depending on baseline)


def _snap(buttons: int, gyro_mag: float):
    """Minimal InputSnapshot-alike: NO timestamp_ms attribute, matching the real
    controller.dualshock_emulator.InputSnapshot dataclass exactly (verified this
    session: fields are buttons/left_stick_x/.../gyro_x/y/z/accel_x/y/z/.../
    sensor_ts_ticks -- no timestamp_ms)."""
    return type("_S", (), {
        "buttons": buttons,
        "r2_trigger": 0,
        "gyro_x": gyro_mag, "gyro_y": 0.0, "gyro_z": 0.0,
    })()


def build_batch() -> list:
    """Collect N_FRAMES snaps with a real time.sleep(DT_MS/1000) between each,
    exactly matching _poll_frames' true collection cadence. Embeds
    N_PRESS_CYCLES precursor+press pairs spread evenly across the batch."""
    press_frame_indices = set()
    spacing = N_FRAMES // (N_PRESS_CYCLES + 1)
    for i in range(1, N_PRESS_CYCLES + 1):
        idx = i * spacing
        if PRECURSOR_LAG_FRAMES < idx < N_FRAMES:
            press_frame_indices.add(idx)
    spike_frame_indices = {idx - PRECURSOR_LAG_FRAMES for idx in press_frame_indices}

    frames = []
    for i in range(N_FRAMES):
        gyro_mag = SPIKE_GYRO_MAG if i in spike_frame_indices else BASELINE_GYRO_MAG
        buttons = CROSS_BIT if i in press_frame_indices else 0
        frames.append(_snap(buttons, gyro_mag))
        time.sleep(DT_MS / 1000.0)
    return frames, press_frame_indices, spike_frame_indices


def run_mode_a_batch(frames: list) -> ImuPressCorrelationOracle:
    """Bridge-style: tight loop over an already-collected batch, no delay."""
    oracle = ImuPressCorrelationOracle()
    for snap in frames:
        oracle.push_snapshot(snap)
    return oracle


def run_mode_b_realtime(n_frames: int, press_frame_indices: set, spike_frame_indices: set) -> ImuPressCorrelationOracle:
    """Realtime-style: push_snapshot called as each frame is collected, same
    real DT_MS delay between calls -- rebuilds an equivalent stream rather
    than replaying the same list, since the whole point is call-time timing."""
    oracle = ImuPressCorrelationOracle()
    for i in range(n_frames):
        gyro_mag = SPIKE_GYRO_MAG if i in spike_frame_indices else BASELINE_GYRO_MAG
        buttons = CROSS_BIT if i in press_frame_indices else 0
        oracle.push_snapshot(_snap(buttons, gyro_mag))
        time.sleep(DT_MS / 1000.0)
    return oracle


def history_span_ms(oracle: ImuPressCorrelationOracle) -> float:
    ts = [t for (t, _mag) in oracle._imu_history]
    return (max(ts) - min(ts)) if len(ts) >= 2 else 0.0


def main() -> None:
    print(f"Building one real batch: {N_FRAMES} frames @ {DT_MS}ms real cadence "
          f"(~{N_FRAMES * DT_MS / 1000.0:.2f}s wall-clock), {N_PRESS_CYCLES} embedded "
          f"precursor+press cycles (precursor {PRECURSOR_LAG_FRAMES * DT_MS:.0f}ms before each press)...")
    t0 = time.time()
    frames, press_idx, spike_idx = build_batch()
    build_elapsed = time.time() - t0
    print(f"  batch built in {build_elapsed:.3f}s real time "
          f"({len(press_idx)} presses, {len(spike_idx)} precursor spikes embedded)")

    print("\n--- MODE A: bridge-style batch replay (tight loop, no delay) ---")
    t0 = time.time()
    oracle_a = run_mode_a_batch(frames)
    a_elapsed = time.time() - t0
    span_a = history_span_ms(oracle_a)
    feats_a = oracle_a.extract_features()
    print(f"  processing loop took {a_elapsed*1000:.2f}ms real time")
    print(f"  _imu_history timestamp span: {span_a:.2f}ms "
          f"(true collection window was ~{N_FRAMES * DT_MS:.0f}ms)")
    print(f"  n_press_events={len(oracle_a._press_events)}")
    if feats_a is not None:
        print(f"  coupled_fraction={feats_a.coupled_fraction:.4f} anomaly={feats_a.anomaly}")
    else:
        print("  extract_features() = None (below _MIN_PRESS_EVENTS)")

    print("\n--- MODE B: realtime-style (push_snapshot called as each frame arrives) ---")
    t0 = time.time()
    oracle_b = run_mode_b_realtime(N_FRAMES, press_idx, spike_idx)
    b_elapsed = time.time() - t0
    span_b = history_span_ms(oracle_b)
    feats_b = oracle_b.extract_features()
    print(f"  processing took {b_elapsed:.3f}s real time (matches collection cadence by design)")
    print(f"  _imu_history timestamp span: {span_b:.2f}ms "
          f"(true collection window was ~{N_FRAMES * DT_MS:.0f}ms)")
    print(f"  n_press_events={len(oracle_b._press_events)}")
    if feats_b is not None:
        print(f"  coupled_fraction={feats_b.coupled_fraction:.4f} anomaly={feats_b.anomaly}")
    else:
        print("  extract_features() = None (below _MIN_PRESS_EVENTS)")

    print("\n--- verdict ---")
    a_cf = feats_a.coupled_fraction if feats_a else None
    b_cf = feats_b.coupled_fraction if feats_b else None
    print(f"Mode A (bridge-style) history span: {span_a:.2f}ms, coupled_fraction={a_cf}")
    print(f"Mode B (realtime-style) history span: {span_b:.2f}ms, coupled_fraction={b_cf}")
    if span_a < 50.0 and span_b > 500.0:
        print("HISTORY-SPAN COLLAPSE CONFIRMED: Mode A's timestamps cluster into "
              "<50ms despite ~1000ms of real collection time; Mode B correctly "
              "spans the real window.")
    else:
        print("HISTORY-SPAN COLLAPSE NOT CLEARLY CONFIRMED -- spans do not show "
              "the predicted pattern; re-examine the hypothesis.")
    if a_cf is not None and b_cf is not None:
        if a_cf < 0.20 and b_cf > 0.80:
            print("PRECURSOR-DETECTION FAILURE CONFIRMED: identical injected "
                  "precursor pattern is correctly detected in realtime mode "
                  f"(coupled_fraction={b_cf:.2f}) but missed in batch mode "
                  f"(coupled_fraction={a_cf:.2f}) -- matches round-05's C-fail-4 "
                  "hypothesis exactly.")
        else:
            print("PRECURSOR-DETECTION FAILURE NOT CLEARLY CONFIRMED -- both "
                  "modes produced similar coupled_fraction; hypothesis needs "
                  "re-examination.")


if __name__ == "__main__":
    main()
