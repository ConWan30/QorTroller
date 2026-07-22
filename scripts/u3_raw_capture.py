"""U3 raw capture — timestamped game frames + full DualSense HID input (sticks/triggers/buttons
AND gyro/accel), read-only. Standalone: no bridge, no DB, no writes to the controller. Safe during
BT-to-PS5 (or any console) play; requires dual-connection (controller USB->laptop for HID capture).

Promoted from the ad-hoc run1_cfb27 recorder (2026-07-21) after the Composite-B real-data adapter
work found run1 was missing IMU data — G3 (tremor) and G4 (causal binding) both need accel/gyro,
which the original script never parsed. Byte offsets below are NOT guessed: they match the tested
offsets in controller/dualshock_emulator.py (`UvcFrameSource`/pydualsense `ds.states` normalized
array, USB transport = inReport unstripped): gyro int16 LE at [22,24,26], accel int16 LE at
[16,18,20], accel scale ~8192/g (Edge is gravity-compensated).

Usage: python scripts/u3_raw_capture.py <out_dir> [duration_s] [--vid=0x054C] [--pid=0x0DF2]
"""
from __future__ import annotations

import argparse
import json
import os
import struct
import sys
import threading
import time

import cv2
import hid

DS_VID = 0x054C
DS_EDGE_PID = 0x0DF2
FRAME_MS = 200  # ~5 fps — enough for scoreboard-level event timing, not frame-perfect

# Byte offsets into the raw 64-byte USB HID input report (pydualsense ds.states-equivalent).
# See controller/dualshock_emulator.py lines ~730-767 for the reference parse this mirrors.
OFF_ACCEL_X, OFF_ACCEL_Y, OFF_ACCEL_Z = 16, 18, 20
OFF_GYRO_X, OFF_GYRO_Y, OFF_GYRO_Z = 22, 24, 26
ACCEL_SCALE = 8192.0  # raw int16 -> g
# F-RIG27-8 device clock: uint32 LE @ ~3MHz immediately after the IMU block (emulator.py:746-751).
# This is the anti-replay rail's layer-1 clock (realplay_liveness.py §2.5) — without it the
# Composite-B evaluator fails closed to UNVERIFIABLE regardless of everything else.
OFF_SENSOR_TS = 28


def parse_imu(data: bytes) -> dict:
    """Pure: raw HID bytes -> {accel_x,y,z (g), gyro_x,y,z (scaled /1000.0, matching the emulator's
    "rad/s-ish" convention in controller/dualshock_emulator.py:738-740 — grok r03 residual fix:
    the original version here returned raw int16 gyro with a docstring that WRONGLY claimed the
    /1000.0 scaling was already applied), sensor_ts_ticks (device clock, 0 if unavailable)}.
    Returns zeros if the buffer is too short (never raises)."""
    if len(data) < 28:
        return {"accel_x": 0.0, "accel_y": 0.0, "accel_z": 0.0, "gyro_x": 0.0, "gyro_y": 0.0, "gyro_z": 0.0,
                "sensor_ts_ticks": 0}
    ax, ay, az = (struct.unpack_from("<h", data, o)[0] for o in (OFF_ACCEL_X, OFF_ACCEL_Y, OFF_ACCEL_Z))
    _gx, _gy, _gz = (struct.unpack_from("<h", data, o)[0] for o in (OFF_GYRO_X, OFF_GYRO_Y, OFF_GYRO_Z))
    gx, gy, gz = _gx / 1000.0, _gy / 1000.0, _gz / 1000.0
    ticks = struct.unpack_from("<I", data, OFF_SENSOR_TS)[0] if len(data) >= 32 else 0
    return {"accel_x": ax / ACCEL_SCALE, "accel_y": ay / ACCEL_SCALE, "accel_z": az / ACCEL_SCALE,
            "gyro_x": gx, "gyro_y": gy, "gyro_z": gz, "sensor_ts_ticks": ticks}


def run(out_dir: str, duration_s: float, vid: int = DS_VID, pid: int = DS_EDGE_PID) -> dict:
    os.makedirs(os.path.join(out_dir, "frames"), exist_ok=True)
    hid_log = open(os.path.join(out_dir, "hid_events.jsonl"), "w", encoding="utf-8")
    stop = threading.Event()
    counts = {"frames": 0, "hid": 0}

    def hid_reader() -> None:
        try:
            h = hid.device()
            h.open(vid, pid)
            h.set_nonblocking(True)
        except Exception as e:  # noqa: BLE001
            print("HID open failed:", e)
            return
        last_key = None
        while not stop.is_set():
            try:
                data = h.read(64)
            except Exception:  # noqa: BLE001
                data = None
            if data:
                t = time.time_ns()
                imu = parse_imu(bytes(data))
                rec = {
                    "t_ns": t,
                    "lx": data[1], "ly": data[2], "rx": data[3], "ry": data[4],
                    "l2": data[5], "r2": data[6],
                    "btn0": data[8] if len(data) > 8 else 0, "btn1": data[9] if len(data) > 9 else 0,
                    **imu,
                }
                # log on meaningful change (movement/press/imu) to keep it event-like, not a 1kHz dump
                key = (rec["l2"] // 8, rec["r2"] // 8, rec["btn0"], rec["btn1"],
                       rec["lx"] // 16, rec["ly"] // 16, rec["rx"] // 16, rec["ry"] // 16,
                       round(rec["accel_x"], 2), round(rec["accel_y"], 2), round(rec["accel_z"], 2))
                if key != last_key:
                    hid_log.write(json.dumps(rec) + "\n")
                    counts["hid"] += 1
                    last_key = key
            else:
                time.sleep(0.001)
        h.close()

    def frame_reader() -> None:
        cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
        cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)
        last_save = 0.0
        while not stop.is_set():
            ok, frame = cap.read()
            if not ok or frame is None:
                time.sleep(0.01)
                continue
            now = time.time()
            if (now - last_save) * 1000 >= FRAME_MS:
                t_ns = time.time_ns()
                cv2.imwrite(os.path.join(out_dir, "frames", f"f_{t_ns}.jpg"), frame,
                           [cv2.IMWRITE_JPEG_QUALITY, 85])
                counts["frames"] += 1
                last_save = now
        cap.release()

    th = threading.Thread(target=hid_reader, daemon=True)
    tf = threading.Thread(target=frame_reader, daemon=True)
    print(f"U3 CAPTURE START dur={duration_s}s out={out_dir}")
    th.start()
    tf.start()
    t0 = time.time()
    while time.time() - t0 < duration_s:
        time.sleep(2.0)
        print(f"  t={int(time.time() - t0)}s frames={counts['frames']} hid_events={counts['hid']}")
    stop.set()
    time.sleep(0.5)
    hid_log.close()
    print(f"U3 CAPTURE DONE frames={counts['frames']} hid_events={counts['hid']}")
    manifest = {"out": out_dir, "duration_s": duration_s, "frames": counts["frames"],
                "hid_events": counts["hid"], "frame_ms": FRAME_MS, "backend": "dshow_idx0_mjpg",
                "imu_captured": True, "sensor_ts_ticks_captured": True,
                "device_vid_pid": f"{vid:#06x}:{pid:#06x}"}
    with open(os.path.join(out_dir, "manifest.json"), "w") as f:
        json.dump(manifest, f, indent=2)
    return manifest


def main() -> None:
    ap = argparse.ArgumentParser(description="U3 raw capture: frames + full DualSense HID incl. IMU")
    ap.add_argument("out_dir")
    ap.add_argument("duration_s", type=float, nargs="?", default=240.0)
    ap.add_argument("--vid", type=lambda x: int(x, 0), default=DS_VID)
    ap.add_argument("--pid", type=lambda x: int(x, 0), default=DS_EDGE_PID)
    args = ap.parse_args()
    run(args.out_dir, args.duration_s, args.vid, args.pid)
    os._exit(0)  # hard-exit: non-daemon-safe cleanup of hid/cv2 handles across threads


if __name__ == "__main__":
    main()
