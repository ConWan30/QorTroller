"""QorTroller L9 — the decisive 10-minute de-risk check (run FIRST).

Answers the two go/no-go questions before any build effort is spent:
  1. Does the PS Remote Play window actually SCREEN-CAPTURE (non-black frames)?
  2. Does the DualShock Edge HID still READ while capture is running?

If (1) fails -> black frames -> the overlay-decode gotcha: disable Windows
"Hardware-accelerated GPU scheduling" + reboot, OR install a WGC backend. If (2)
fails -> the controller path is contended; investigate before building.

USAGE (operator runs, with Remote Play open + Warzone visible, controller in hand):
  python -m l9_presence.derisk_check
  python -m l9_presence.derisk_check --region 0 0 1920 1080 --frames 120

Hardware + Remote Play required; this is NOT a unit test.
EXIT: 0 GO (capture non-black AND HID reads) · 2 capture black · 3 no backend
      · 4 HID not reading
"""
from __future__ import annotations

import argparse
import sys
import time

from .screen_capture import ScreenCapturer, available_backends, is_black_frame

DUALSENSE_VID = 0x054C
DUALSENSE_EDGE_PID = 0x0DF2


def _probe_hid() -> tuple[bool, str]:
    """Try to read one HID report from the DualShock Edge (pip install hidapi)."""
    try:
        import hid  # hidapi
    except Exception:
        return False, "hidapi not installed (pip install hidapi)"
    try:
        d = hid.device()
        d.open(DUALSENSE_VID, DUALSENSE_EDGE_PID)
        d.set_nonblocking(True)
        got = b""
        for _ in range(200):  # ~1s of attempts
            r = d.read(64)
            if r:
                got = bytes(r)
                break
            time.sleep(0.005)
        d.close()
        if got:
            return True, f"HID read OK ({len(got)} bytes)"
        return False, "HID opened but no report read (controller idle? wrong interface?)"
    except Exception as exc:
        return False, f"HID open failed: {exc}"


def _run(region, n_frames: int, backend: str = "auto") -> int:
    backends = available_backends()
    print(f"  capture backends available: {backends or 'NONE'}")
    if not backends:
        print("  ABORT: install `bettercam` (recommended) or `mss`."); return 3

    cap = ScreenCapturer(region=region, backend=backend)
    print(f"  using backend: {cap.backend}  region: {region or 'full monitor'}")

    grabbed, black = 0, 0
    res = None
    t0 = time.time()
    for _ in range(n_frames):
        f = cap.grab()
        if f is None:
            time.sleep(0.005); continue
        grabbed += 1
        if res is None:
            res = f.shape
        if is_black_frame(f):
            black += 1
        time.sleep(0.001)
    dt = max(time.time() - t0, 1e-3)
    cap.close()

    fps = grabbed / dt
    black_frac = (black / grabbed) if grabbed else 1.0
    print(f"  grabbed {grabbed} frames in {dt:.1f}s (~{fps:.0f} fps) | resolution {res}")
    print(f"  black-frame fraction: {black_frac:.0%}")

    hid_ok, hid_msg = _probe_hid()
    print(f"  HID: {hid_msg}")

    print("  " + "=" * 60)
    if grabbed == 0 or black_frac > 0.5:
        print("  RESULT: NO-GO (capture) — Remote Play frames are black/empty.")
        print("  FIX: disable 'Hardware-accelerated GPU scheduling' + reboot, OR")
        print("       install a WGC backend (windows-capture / wincam). Keep")
        print("       Remote Play MAXIMIZED and re-run.")
        return 2
    if not hid_ok:
        print("  RESULT: NO-GO (HID) — capture works but controller not reading.")
        return 4
    print("  RESULT: GO — capture is non-black AND HID reads. Proceed to record")
    print("          ~10 human + ~10 scripted sessions, then compute separation.")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--region", nargs=4, type=int, metavar=("L", "T", "R", "B"),
                    default=None, help="crop region (left top right bottom); default full monitor")
    ap.add_argument("--frames", type=int, default=120, help="frames to sample")
    ap.add_argument("--backend", choices=("auto", "wgc", "bettercam", "dxcam", "mss"),
                    default="auto", help="capture backend (default auto: wgc>bettercam>dxcam>mss)")
    a = ap.parse_args()
    region = tuple(a.region) if a.region else None
    print("=" * 64)
    print("QorTroller L9 — Remote Play capture + HID de-risk check")
    print("=" * 64)
    return _run(region, a.frames, a.backend)


if __name__ == "__main__":
    sys.exit(main())
