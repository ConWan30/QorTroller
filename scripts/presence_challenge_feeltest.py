"""Presence-challenge FEEL TEST (MAIN-MOTOR signature) — operator certifies the
stimulus is forceful + distinguishable from NCAA CFB 26 rumble, and tunes it.

RUN WITH THE BRIDGE STOPPED (opens the DualSense directly; the bridge can't hold the
HID handle at the same time). Confirmed on a real Edge: main motors are felt strongly
in the palms regardless of trigger position — that is the channel used here.

    py scripts/presence_challenge_feeltest.py --reps 5 --amp 255            # both motors, 3-pulse signature
    py scripts/presence_challenge_feeltest.py --alternate                   # left/right sweep (more distinct)
    py scripts/presence_challenge_feeltest.py --amp 200 --pulses 4          # tune amplitude / cadence

The job: find the cadence + amplitude that you (a) feel every time and (b) can tell apart
from a tackle's rumble. That confirmed config is wired into the in-session challenger.
Requires `pydualsense` + a connected DualSense; exits cleanly otherwise.
"""
from __future__ import annotations

import argparse
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from bridge.controller.presence_challenge import (  # noqa: E402
    forceful_motor_signature,
    is_forceful,
    is_signature,
)


def _connect():
    try:
        from pydualsense import pydualsense
    except ImportError:
        print("[feeltest] pydualsense not installed. `pip install pydualsense`.")
        return None
    try:
        ds = pydualsense()
        ds.init()
    except Exception as exc:
        print(f"[feeltest] could not open DualSense ({exc}). Connect via USB + STOP the bridge.")
        return None
    if not (hasattr(ds, "setLeftMotor") and hasattr(ds, "setRightMotor")):
        print("[feeltest] this pydualsense build has no setLeftMotor/setRightMotor.")
        return None
    return ds


def _off(ds):
    try:
        ds.setLeftMotor(0); ds.setRightMotor(0)
    except Exception:
        pass


def _fire(ds, sig):
    for left, right, dur in sig.steps():
        ds.setLeftMotor(left); ds.setRightMotor(right)
        time.sleep(dur)
    _off(ds)


def main() -> int:
    ap = argparse.ArgumentParser(description="Presence-challenge feel test (motor signature)")
    ap.add_argument("--amp", type=int, default=255)
    ap.add_argument("--pulses", type=int, default=3)
    ap.add_argument("--on-ms", type=int, default=200)
    ap.add_argument("--off-ms", type=int, default=180)
    ap.add_argument("--alternate", action="store_true", help="left/right sweep instead of both motors")
    ap.add_argument("--reps", type=int, default=5)
    ap.add_argument("--gap", type=float, default=4.0, help="seconds between reps")
    args = ap.parse_args()

    sig = forceful_motor_signature(args.amp, args.pulses, args.alternate)
    object.__setattr__(sig, "on_ms", args.on_ms)   # frozen dataclass tune
    object.__setattr__(sig, "off_ms", args.off_ms)
    print(f"[feeltest] motor signature: amp={sig.amp}/255  pulses={sig.pulses}  "
          f"on={sig.on_ms}ms off={sig.off_ms}ms  alternate={sig.alternate}  "
          f"forceful={is_forceful(sig)}  signature={is_signature(sig)}")

    ds = _connect()
    if ds is None:
        return 2
    try:
        for r in range(1, args.reps + 1):
            for c in (3, 2, 1):
                sys.stdout.write(f"\r[feeltest] rep {r}/{args.reps} — challenge in {c}... ")
                sys.stdout.flush()
                time.sleep(1.0)
            print(f"\r[feeltest] rep {r}/{args.reps} — >>> CHALLENGE NOW <<<            ")
            _fire(ds, sig)
            time.sleep(args.gap)
    finally:
        _off(ds)
        try:
            ds.close()
        except Exception:
            pass

    print("\n[feeltest] done. Confirm: felt every rep? distinguishable from tackle rumble?")
    print("  weak -> raise --amp;  blends in -> try --alternate or change --pulses/--on-ms.")
    print(f"[feeltest] candidate: amp={args.amp} pulses={args.pulses} alternate={args.alternate}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
