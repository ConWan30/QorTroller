"""QorTroller L9 — IMU byte-offset validator (de-provisionalizes the L4 view).

The physics analog of hid_probe. cocapture's L4 features need the gyro/accel int16
offsets + scale in the DualSense report, and those were PROVISIONAL guesses. This
validator confirms them on-device using two facts of physics that uniquely fingerprint
the two sensors:

  * ACCELEROMETER: at rest reads gravity (~1g on one axis); its 3-axis MAGNITUDE is
    CONSERVED (~1g) no matter how you rotate the controller.
  * GYROSCOPE: reads angular velocity — ~0 at rest, spikes during rotation, and its
    magnitude is NOT conserved.

Protocol: (1) hold the controller STILL, (2) slowly ROTATE it through all orientations.
The detector finds the 12-byte IMU block, labels the conserved-magnitude triple as
accel and the other as gyro, and derives scale = 1 / mean(rest accel magnitude) so
accel rests at ~1.0 g (what the extractor expects).

Writes cocapture_l9/imu_offsets.json; cocapture loads it and sets l4_provisional=False.

USAGE: python -m l9_presence.imu_probe
EXIT: 0 detected · 4 HID not reading · 5 inconclusive
"""
from __future__ import annotations

import json
import os
import sys
import time

import numpy as np

DUALSENSE_VID = 0x054C
DUALSENSE_EDGE_PID = 0x0DF2
OFFSETS_PATH = os.path.join("cocapture_l9", "imu_offsets.json")


def _i16le(b: bytes, i: int) -> int:
    return int.from_bytes(b[i:i + 2], "little", signed=True) if len(b) >= i + 2 else 0


def _field_matrix(reports, offs):
    return np.array([[_i16le(r, o) for o in offs] for r in reports], float)


def detect_imu_offsets(rest_reports, rot_reports, lo: int = 13, hi: int = 34) -> dict:
    """Find gyro/accel int16 offsets + scale from still vs rotation samples.

    For every 12-byte IMU-block hypothesis (and both gyro|accel orderings), the ACCEL
    triple is the one whose 3-axis magnitude is large at rest (gravity) AND conserved
    under rotation (low CV). Returns the best-scoring assignment."""
    offs = list(range(lo, hi + 1))
    if len(rest_reports) < 5 or len(rot_reports) < 5:
        return {"status": "insufficient_samples"}
    rest = _field_matrix(rest_reports, offs)
    rot = _field_matrix(rot_reports, offs)
    rot_std = rot.std(0)

    def mag(M, idx):
        return np.sqrt((M[:, idx] ** 2).sum(1))

    best = None
    for b in range(lo, hi - 9):
        try:
            blk = [offs.index(b + k) for k in (0, 2, 4, 6, 8, 10)]
        except ValueError:
            continue
        if np.min(rot_std[blk]) < 30:           # all six must respond to rotation
            continue
        for gyro_idx, accel_idx in ((blk[:3], blk[3:]), (blk[3:], blk[:3])):
            a_rest = mag(rest, accel_idx)
            a_rot = mag(rot, accel_idx)
            g_rest = mag(rest, gyro_idx)
            if a_rest.mean() < 500:             # accel must show gravity at rest
                continue
            cv = float(a_rot.std() / (a_rot.mean() + 1e-9))   # conserved -> low
            # prefer: conserved accel mag, accel gravity at rest >> gyro at rest
            sep = a_rest.mean() / (g_rest.mean() + 1e-9)
            if cv > 0.5 or sep < 1.5:
                continue
            score = cv - 0.05 * np.log(max(sep, 1.0))
            if best is None or score < best["score"]:
                best = {"score": score, "cv": cv, "sep": float(sep),
                        "gyro": [offs[i] for i in gyro_idx],
                        "accel": [offs[i] for i in accel_idx],
                        "accel_mag_rest": float(a_rest.mean())}
    if best is None:
        return {"status": "inconclusive"}
    scale = 1.0 / (best["accel_mag_rest"] + 1e-9)
    return {
        "gyro_x": best["gyro"][0], "gyro_y": best["gyro"][1], "gyro_z": best["gyro"][2],
        "accel_x": best["accel"][0], "accel_y": best["accel"][1], "accel_z": best["accel"][2],
        "scale": scale,
        "accel_mag_cv": round(best["cv"], 4),
        "gravity_separation": round(best["sep"], 2),
        "confidence": ("high" if best["cv"] < 0.15 and best["sep"] > 3
                       else "medium" if best["cv"] < 0.35 else "low"),
    }


def _open():
    import hid
    target = None
    for d in hid.enumerate(DUALSENSE_VID, DUALSENSE_EDGE_PID):
        if d.get("interface_number") in (0, -1) and d.get("path"):
            target = d
            break
    dev = hid.device()
    dev.open_path(target["path"]) if (target and target.get("path")) else dev.open(
        DUALSENSE_VID, DUALSENSE_EDGE_PID)
    dev.set_nonblocking(True)
    return dev


def _collect(dev, seconds):
    rows, t0 = [], time.time()
    while time.time() - t0 < seconds:
        r = dev.read(64)
        if r:
            rows.append(bytes(r))
        else:
            time.sleep(0.001)
    return rows


def main() -> int:
    print("=" * 64)
    print("QorTroller L9 — IMU (gyro/accel) offset validator")
    print("=" * 64)
    try:
        dev = _open()
    except Exception as exc:
        print(f"  HID open failed: {exc}")
        return 4
    try:
        if len(_collect(dev, 1.0)) < 5:
            print("  few/no HID reports — wrong interface or idle.")
            return 4
        print("\n  [1/2] Hold the controller FLAT and STILL on a surface… 3s")
        time.sleep(0.4)
        rest = _collect(dev, 3.0)
        print("  [2/2] Slowly ROTATE the controller through all orientations… 5s")
        time.sleep(0.4)
        rot = _collect(dev, 5.0)
    finally:
        dev.close()

    res = detect_imu_offsets(rest, rot)
    print("  " + "=" * 60)
    if "gyro_x" not in res:
        print(f"  RESULT: {res.get('status', 'inconclusive')} — retry; keep still then rotate fully.")
        return 5
    os.makedirs(os.path.dirname(OFFSETS_PATH), exist_ok=True)
    with open(OFFSETS_PATH, "w", encoding="utf-8") as fh:
        json.dump(res, fh, indent=2)
    print(f"  RESULT ({res['confidence']} confidence): gyro@{res['gyro_x']}/{res['gyro_y']}/{res['gyro_z']} "
          f"accel@{res['accel_x']}/{res['accel_y']}/{res['accel_z']}")
    print(f"          scale={res['scale']:.3e}  accel_mag_cv={res['accel_mag_cv']}  "
          f"gravity_sep={res['gravity_separation']}")
    print(f"  wrote {OFFSETS_PATH} — cocapture will use it and set l4_provisional=False.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
