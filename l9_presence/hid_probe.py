"""QorTroller L9 — HID right-stick byte-offset validator (run on-device).

The coupling probe is only as good as the stick signal feeding it. The DualSense
Edge exposes multiple HID interfaces and more than one report layout (standard
input report id 0x01 vs the vendor "full" report), so the right-stick byte offsets
MUST be confirmed on THIS controller before any recording is trusted — a wrong
offset silently produces garbage coupling.

This is the input-side analog of derisk_check.py. It records raw HID reports while
you move ONLY the right stick, then reports which byte indices actually vary. The
two highest-variance bytes that rest near 128 are the right-stick X/Y offsets.

USAGE (controller plugged in via USB):
  python -m l9_presence.hid_probe
  -> follow the prompts: hold the stick centered, then circle the RIGHT stick.

EXIT: 0 offsets identified · 4 HID not reading · 5 inconclusive (no clear movers)
"""
from __future__ import annotations

import sys
import time

import numpy as np

DUALSENSE_VID = 0x054C
DUALSENSE_EDGE_PID = 0x0DF2
_REST_CENTER = 128          # 8-bit sticks rest at ~128
_REST_TOL = 40              # "rests near center" tolerance
_MOVER_STD = 12.0           # min std (LSB) to count a byte as actively moving


def _open():
    """Open the DualSense Edge HID. Prefer the standard input interface (where the
    0x01 report with sticks lives); fall back to the first matching device."""
    import hid  # hidapi
    target = None
    for d in hid.enumerate(DUALSENSE_VID, DUALSENSE_EDGE_PID):
        # interface 0 carries the standard input report on Windows hidapi
        if d.get("interface_number") in (0, -1) and d.get("path"):
            target = d
            break
    dev = hid.device()
    if target and target.get("path"):
        dev.open_path(target["path"])
    else:
        dev.open(DUALSENSE_VID, DUALSENSE_EDGE_PID)
    dev.set_nonblocking(True)
    return dev


def _collect(dev, seconds: float) -> np.ndarray:
    """Read raw reports for `seconds`; return an (n_reports, 64) uint8 matrix."""
    rows = []
    t0 = time.time()
    while time.time() - t0 < seconds:
        r = dev.read(64)
        if r:
            buf = bytes(r)[:64]
            if len(buf) < 64:
                buf = buf + b"\x00" * (64 - len(buf))
            rows.append(np.frombuffer(buf, dtype=np.uint8))
        else:
            time.sleep(0.001)
    return np.vstack(rows) if rows else np.zeros((0, 64), dtype=np.uint8)


def main() -> int:
    print("=" * 64)
    print("QorTroller L9 — HID right-stick offset validator")
    print("=" * 64)
    try:
        dev = _open()
    except Exception as exc:
        print(f"  HID open failed: {exc}  (pip install hidapi; controller plugged in?)")
        return 4

    try:
        # quick liveness check
        warm = _collect(dev, 1.0)
        if warm.shape[0] < 5:
            print("  HID opened but few/no reports read — wrong interface or idle.")
            return 4
        report_id = int(warm[0, 0])
        print(f"  reports read: {warm.shape[0]} in 1s | report id (byte0)=0x{report_id:02x} "
              f"| width={warm.shape[1]}B")

        print("\n  [1/2] HOLD the right stick CENTERED (don't touch it)… 2s")
        time.sleep(0.4)
        rest = _collect(dev, 2.0)

        print("  [2/2] Now CIRCLE the RIGHT stick fully, several times… 4s")
        time.sleep(0.4)
        move = _collect(dev, 4.0)
    finally:
        dev.close()

    if rest.shape[0] < 5 or move.shape[0] < 5:
        print("  inconclusive — not enough samples captured."); return 5

    rest_mean = rest.mean(axis=0)
    move_std = move.std(axis=0)
    # candidate right-stick bytes: rest near center AND high movement variance
    order = np.argsort(move_std)[::-1]
    print("\n  per-byte movement (top 8 by std during right-stick circling):")
    print("   idx  rest_mean  move_std  rests_near_center")
    movers = []
    for idx in order[:8]:
        near = abs(rest_mean[idx] - _REST_CENTER) <= _REST_TOL
        flag = "yes" if near else "no"
        print(f"   {idx:3d}   {rest_mean[idx]:7.1f}   {move_std[idx]:7.1f}      {flag}")
        if near and move_std[idx] >= _MOVER_STD:
            movers.append(int(idx))

    print("  " + "=" * 60)
    if len(movers) >= 2:
        rx, ry = movers[0], movers[1]
        print(f"  RESULT: right-stick bytes look like RX=byte{rx}, RY=byte{ry}")
        print(f"          (the two center-resting bytes that moved most)")
        print(f"  Next: record with --rx {rx} --ry {ry}, e.g.")
        print(f"        python -m l9_presence.session_recorder record "
              f"--label human --rx {rx} --ry {ry} --region 640 360 1280 720 "
              f"--out sessions_l9/human_01.npz")
        return 0
    print("  RESULT: inconclusive — no two center-resting bytes moved clearly.")
    print("          Make sure you moved ONLY the right stick, fully, during step 2.")
    return 5


if __name__ == "__main__":
    sys.exit(main())
