"""Presence-challenge FEEL TEST — operator certifies the stimulus is forceful +
distinguishable from NCAA CFB 26 haptics, and tunes the force level.

RUN WITH THE BRIDGE STOPPED (this opens the DualSense directly; the bridge can't
hold the HID handle at the same time). It fires the forceful signature challenge a
few times with on-screen markers so you can correlate the buzz with the event, then
asks you to confirm it was felt and unmistakable, and prints the FORCE to wire into
the in-session challenger.

    # stop the bridge first, controller connected via USB, then:
    python scripts/presence_challenge_feeltest.py --reps 5 --force 230
    python scripts/presence_challenge_feeltest.py --force 255 --pulses 3 --motor   # tune harder + rumble accent
    python scripts/presence_challenge_feeltest.py --rigid-kicks 3                  # alt: discrete hard kicks to compare

HONEST: this is the ONLY way "forceful enough" gets certified — by you, on the
controller. The code can't feel it. Requires `pydualsense` + a connected DualSense;
exits with a clear message otherwise.
"""
from __future__ import annotations

import argparse
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from bridge.controller.presence_challenge import (  # noqa: E402
    forceful_signature_profile,
    is_forceful,
    is_signature,
)


def _connect():
    try:
        from pydualsense import TriggerModes, pydualsense
    except ImportError:
        print("[feeltest] pydualsense not installed. `pip install pydualsense`. "
              "Cannot fire haptics without it.")
        return None, None
    try:
        ds = pydualsense()
        ds.init()
    except Exception as exc:
        print(f"[feeltest] could not open DualSense ({exc}). "
              "Connect the controller via USB and STOP the bridge first.")
        return None, None
    return ds, TriggerModes


def _clear(ds, TriggerModes):
    try:
        ds.triggerL.setMode(TriggerModes(0)); ds.triggerR.setMode(TriggerModes(0))
        for i in range(7):
            ds.triggerL.setForce(i, 0); ds.triggerR.setForce(i, 0)
        if hasattr(ds, "setLeftMotor"):
            ds.setLeftMotor(0); ds.setRightMotor(0)
    except Exception:
        pass


def _fire_profile(ds, TriggerModes, profile, hold_s: float, motor: bool):
    for trig, mode, forces in ((ds.triggerR, profile.r2_mode, profile.r2_forces),
                               (ds.triggerL, profile.l2_mode, profile.l2_forces)):
        trig.setMode(TriggerModes(mode))
        for i, f in enumerate(forces):
            trig.setForce(i, f)
    if motor and hasattr(ds, "setLeftMotor"):
        ds.setLeftMotor(200); ds.setRightMotor(200)
    time.sleep(hold_s)
    _clear(ds, TriggerModes)


def _fire_rigid_kicks(ds, TriggerModes, force: int, kicks: int, motor: bool):
    for _ in range(kicks):
        for trig in (ds.triggerR, ds.triggerL):
            trig.setMode(TriggerModes(1))   # RIGID
            trig.setForce(0, force)
        if motor and hasattr(ds, "setLeftMotor"):
            ds.setLeftMotor(220); ds.setRightMotor(220)
        time.sleep(0.12)
        _clear(ds, TriggerModes)
        time.sleep(0.10)


def main() -> int:
    ap = argparse.ArgumentParser(description="Presence-challenge feel test")
    ap.add_argument("--force", type=int, default=230)
    ap.add_argument("--pulses", type=int, default=3)
    ap.add_argument("--reps", type=int, default=5)
    ap.add_argument("--hold", type=float, default=0.6, help="seconds to hold the pulse profile")
    ap.add_argument("--gap", type=float, default=3.0, help="seconds between reps")
    ap.add_argument("--motor", action="store_true", help="add a main-motor rumble accent")
    ap.add_argument("--rigid-kicks", type=int, default=0,
                    help="alt mode: N discrete hard RIGID kicks instead of the pulse profile")
    args = ap.parse_args()

    profile = forceful_signature_profile(args.force, args.pulses)
    print(f"[feeltest] profile: {profile.name}  force={args.force}/255  pulses={args.pulses}  "
          f"forceful={is_forceful(profile)}  signature={is_signature(profile)}")
    if args.motor:
        print("[feeltest] + main-motor rumble accent")

    ds, TriggerModes = _connect()
    if ds is None:
        return 2

    try:
        for r in range(1, args.reps + 1):
            for c in (3, 2, 1):
                sys.stdout.write(f"\r[feeltest] rep {r}/{args.reps} — challenge in {c}... ")
                sys.stdout.flush()
                time.sleep(1.0)
            print("\r[feeltest] rep %d/%d — >>> CHALLENGE NOW <<<            " % (r, args.reps))
            if args.rigid_kicks > 0:
                _fire_rigid_kicks(ds, TriggerModes, args.force, args.rigid_kicks, args.motor)
            else:
                _fire_profile(ds, TriggerModes, profile, args.hold, args.motor)
            time.sleep(args.gap)
    finally:
        _clear(ds, TriggerModes)
        try:
            ds.close()
        except Exception:
            pass

    print("\n[feeltest] done. Confirm honestly:")
    print("  1) Did you FEEL every challenge?            (if no -> raise --force)")
    print("  2) Was it unmistakable vs game rumble?      (if no -> try --motor or --rigid-kicks, raise --force)")
    print("  3) The lowest --force that passes both is what to wire in-session.")
    print(f"[feeltest] current candidate force = {args.force}. Re-run with a lower/higher --force to find the floor.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
