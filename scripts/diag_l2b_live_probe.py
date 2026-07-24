"""Grok round-02 Ask 5 Step B -- live diagnostic for the L2B gyro unit-scale finding.
Scope: docs/a2a/live-l2b-unit-scale-investigation/step-b-live-diagnostic-scope.md

Standalone, read-only, no bridge involvement: opens the Edge's HID device directly
(plain hidapi, same approach as scripts/u3_raw_capture.py -- NOT pydualsense/
DualSenseReader, to avoid a new dependency and avoid HID-handle contention with a
running bridge), feeds real polled frames into an UNMODIFIED, imported
ImuPressCorrelationOracle (the actual production class from
controller/l2b_imu_press_correlation.py) at its DEFAULT threshold (no patching --
Step A already proved the patched-recovery behavior; this step observes today's
real default behavior only).

No game required. Connect the Edge via USB data cable, then press Cross and/or
pull R2 repeatedly (>= ~20 times) under real hand movement.

Usage: python scripts/diag_l2b_live_probe.py [duration_s] [--target-presses=25]
"""
from __future__ import annotations

import argparse
import statistics
import sys
import time
from pathlib import Path

import hid
import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))
sys.path.insert(0, str(REPO_ROOT / "controller"))

from u3_raw_capture import parse_imu, DS_VID, DS_EDGE_PID  # noqa: E402
from l2b_imu_press_correlation import (  # noqa: E402
    ImuPressCorrelationOracle,
    CROSS_BIT,
    _IMU_SPIKE_THRESH,
    _MIN_PRESS_EVENTS,
    _COUPLED_FRACTION,
)

STATUS_INTERVAL_S = 2.0


def _snap(t_ms: float, gx: float, gy: float, gz: float, cross: bool, r2: int):
    buttons = CROSS_BIT if cross else 0
    return type("_S", (), {
        "timestamp_ms": t_ms,
        "gyro_x": gx, "gyro_y": gy, "gyro_z": gz,
        "buttons": buttons,
        "r2_trigger": r2,
    })()


def run(duration_s: float, target_presses: int, vid: int, pid: int) -> dict:
    h = hid.device()
    h.open(vid, pid)
    h.set_nonblocking(True)

    oracle = ImuPressCorrelationOracle()
    gyro_mags: list[float] = []
    n_frames = 0
    t0 = time.time()
    t0_ns = time.time_ns()
    last_status = 0.0

    print(f"L2B LIVE PROBE START duration_s={duration_s} target_presses={target_presses} "
          f"live_thresh(default)={_IMU_SPIKE_THRESH} min_press_events={_MIN_PRESS_EVENTS} "
          f"coupled_fraction_anomaly_floor={_COUPLED_FRACTION}")
    print("Connect the Edge via USB and press Cross / pull R2 repeatedly now.")

    while True:
        elapsed = time.time() - t0
        n_press = len(oracle._press_events)
        if elapsed >= duration_s:
            print(f"  [stop] duration reached ({elapsed:.1f}s)")
            break
        if n_press >= target_presses:
            print(f"  [stop] target presses reached ({n_press}/{target_presses})")
            break

        try:
            data = h.read(64)
        except Exception as e:  # noqa: BLE001
            print("HID read error:", e)
            break

        if data:
            data = bytes(data)
            imu = parse_imu(data)
            t_ms = (time.time_ns() - t0_ns) / 1e6
            buttons_0 = data[8] if len(data) > 8 else 0
            cross = bool((buttons_0 >> 5) & 1)
            r2 = data[6] if len(data) > 6 else 0
            gm = (imu["gyro_x"] ** 2 + imu["gyro_y"] ** 2 + imu["gyro_z"] ** 2) ** 0.5
            gyro_mags.append(gm)
            oracle.push_snapshot(_snap(t_ms, imu["gyro_x"], imu["gyro_y"], imu["gyro_z"], cross, r2))
            n_frames += 1
        else:
            time.sleep(0.001)

        if elapsed - last_status >= STATUS_INTERVAL_S:
            last_status = elapsed
            p95 = float(np.percentile(gyro_mags, 95)) if gyro_mags else 0.0
            baseline = statistics.median(oracle._imu_baseline) if oracle._imu_baseline else 0.0
            adaptive_thresh = baseline + _IMU_SPIKE_THRESH
            print(f"  t={elapsed:.1f}s frames={n_frames} presses={len(oracle._press_events)} "
                  f"gyro_mag_p95={p95:.4f} adaptive_thresh~={adaptive_thresh:.4f}")

    h.close()

    feats = oracle.extract_features()
    result = oracle.classify()
    report = {
        "duration_s": round(time.time() - t0, 1),
        "n_frames": n_frames,
        "n_press_events": len(oracle._press_events),
        "min_press_events_required": _MIN_PRESS_EVENTS,
        "imu_spike_thresh_default": _IMU_SPIKE_THRESH,
        "coupled_fraction_anomaly_floor": _COUPLED_FRACTION,
        "gyro_mag_p50": round(float(np.percentile(gyro_mags, 50)), 4) if gyro_mags else None,
        "gyro_mag_p95": round(float(np.percentile(gyro_mags, 95)), 4) if gyro_mags else None,
        "gyro_mag_max": round(float(np.max(gyro_mags)), 4) if gyro_mags else None,
        "coupled_fraction": round(feats.coupled_fraction, 4) if feats else None,
        "anomaly": feats.anomaly if feats else None,
        "fires_0x31": result is not None,
        "humanity_score": round(oracle.humanity_score(), 4),
    }
    return report


def main() -> None:
    ap = argparse.ArgumentParser(description="Live L2B unit-scale diagnostic probe (read-only)")
    ap.add_argument("duration_s", type=float, nargs="?", default=180.0)
    ap.add_argument("--target-presses", type=int, default=25)
    ap.add_argument("--vid", type=lambda x: int(x, 0), default=DS_VID)
    ap.add_argument("--pid", type=lambda x: int(x, 0), default=DS_EDGE_PID)
    args = ap.parse_args()

    report = run(args.duration_s, args.target_presses, args.vid, args.pid)

    import json
    print("\n--- final report ---")
    print(json.dumps(report, indent=2))

    print("\n--- pattern check ---")
    cf = report["coupled_fraction"]
    if report["n_press_events"] < report["min_press_events_required"]:
        print(f"INCONCLUSIVE: only {report['n_press_events']} press events "
              f"(< {report['min_press_events_required']} required) -- press more or run longer.")
    elif cf is not None and cf <= 0.10 and report["fires_0x31"]:
        print(f"MATCHES round-02 hypothesis: coupled_fraction={cf} (near 0), 0x31 fired live.")
    elif cf is not None and cf >= 0.50 and not report["fires_0x31"]:
        print(f"REFUTES round-02 hypothesis: coupled_fraction={cf} (high), no fire -- "
              f"investigate before trusting Step A's conclusion for production.")
    else:
        print(f"AMBIGUOUS: coupled_fraction={cf}, fires_0x31={report['fires_0x31']} -- "
              f"does not cleanly match either pattern.")


if __name__ == "__main__":
    main()
