"""QorTroller PoEP — the decisive de-risk check (run FIRST, before any PoEP build).

Answers the two go/no-go questions from POEP_SCOPE.md before any effort is spent:
  1. Can the bridge ISSUE a stimulus to the DualSense Edge (rumble + adaptive trigger)?
  2. Can it CAPTURE a human reflex to that stimulus in the human reaction band, timed?

Protocol (operator holds the controller, USB to the laptop): for each trial, after a
random delay the bridge fires a sub-perceptual-ish stimulus; the operator reacts the
instant they feel it (press R2 / flick the right stick); the loop measures the reaction
latency. GO iff the write works AND reactions land in the human band [120, 450] ms.

Controller-ownership note (POEP_SCOPE P0): run STANDALONE first (bridge owns the
controller). GO standalone → then a follow-up in-game test decides in-game vs
enrollment/between-match PoEP (the PS5 owns haptics over BT during Remote Play).

Hardware required; NOT a unit test. The write/timing LOGIC is unit-tested separately.
EXIT: 0 GO · 4 controller not reachable · 5 stimulus write failed · 6 no usable reactions
"""
from __future__ import annotations

import random
import statistics
import sys
import time
from typing import Optional, Tuple

HUMAN_BAND_MS: Tuple[float, float] = (120.0, 450.0)  # voluntary reaction; <120 = anticipation/bot, >450 = inattention
_STICK_DELTA = 40       # |axis-128| that counts as a deliberate stick move
_TRIG_PRESS = 64        # analog trigger value that counts as a press


def in_human_band(latency_ms: float, band: Tuple[float, float] = HUMAN_BAND_MS) -> bool:
    """True if a reaction latency is physiologically plausible for a live human."""
    return band[0] <= float(latency_ms) <= band[1]


def reaction_detected(baseline: dict, current: dict) -> bool:
    """True if `current` shows a deliberate input change vs `baseline` (the reflex)."""
    if abs(current.get("RX", 128) - baseline.get("RX", 128)) > _STICK_DELTA:
        return True
    if abs(current.get("RY", 128) - baseline.get("RY", 128)) > _STICK_DELTA:
        return True
    if current.get("R2", 0) > _TRIG_PRESS or current.get("L2", 0) > _TRIG_PRESS:
        return True
    return current.get("buttons", 0) != baseline.get("buttons", 0)


def assess_control(buzz_lats, sham_lats, n_buzz: int, n_sham: int) -> dict:
    """Negative-control verdict: is the in-game reaction genuinely BUZZ-driven, or just
    gameplay tripping the detector? buzz_lats/sham_lats = detected latencies (ms) for
    live (buzz) vs sham (no-buzz) trials. Genuine iff buzz reactions are common + in the
    human band AND sham trials (gameplay alone) rarely trip the detector."""
    buzz_rate = (len(buzz_lats) / n_buzz) if n_buzz else 0.0
    sham_rate = (len(sham_lats) / n_sham) if n_sham else 0.0
    buzz_med = statistics.median(buzz_lats) if buzz_lats else None
    sham_med = statistics.median(sham_lats) if sham_lats else None
    genuine = bool(buzz_rate >= 0.6 and buzz_med is not None
                   and in_human_band(buzz_med) and sham_rate <= 0.3)
    return {"buzz_detect_rate": round(buzz_rate, 3), "sham_detect_rate": round(sham_rate, 3),
            "buzz_median_ms": round(buzz_med, 1) if buzz_med is not None else None,
            "sham_median_ms": round(sham_med, 1) if sham_med is not None else None,
            "genuine_buzz_driven": genuine,
            "verdict": ("in-game PoEP viable (reflex is buzz-driven, not gameplay)" if genuine
                        else "in-game confounded by gameplay -> use enrollment/between-match form")}


def _snapshot(ds) -> dict:
    s = ds.state
    btn = sum(int(bool(getattr(s, b, False))) for b in
              ("cross", "circle", "square", "triangle", "R1", "L1"))
    return {"RX": getattr(s, "RX", 128), "RY": getattr(s, "RY", 128),
            "R2": getattr(s, "R2", 0), "L2": getattr(s, "L2", 0), "buttons": btn}


def _test_write(ds) -> dict:
    """Confirm both stimulus channels accept writes. Returns {rumble, trigger} bools."""
    out = {"rumble": False, "trigger": False}
    try:
        ds.setLeftMotor(180); ds.setRightMotor(180); time.sleep(0.15)
        ds.setLeftMotor(0); ds.setRightMotor(0)
        out["rumble"] = True
    except Exception as exc:
        print(f"  rumble write failed: {exc}")
    try:
        from pydualsense import TriggerModes
        ds.triggerR.setMode(TriggerModes.Rigid); ds.triggerR.setForce(1, 200)
        time.sleep(0.15)
        ds.triggerR.setMode(TriggerModes.Off)
        out["trigger"] = True
    except Exception as exc:
        print(f"  adaptive-trigger write failed (rumble still usable): {exc}")
    return out


def _fire(ds):
    try:
        ds.setLeftMotor(220); ds.setRightMotor(220)
    except Exception:
        pass


def _stop(ds):
    try:
        ds.setLeftMotor(0); ds.setRightMotor(0)
    except Exception:
        pass


def run_derisk(trials: int = 6, timeout_s: float = 1.2) -> dict:
    try:
        from pydualsense import pydualsense
    except Exception as exc:
        return {"status": "no_pydualsense", "error": str(exc)}
    ds = pydualsense()
    try:
        ds.init()
    except Exception as exc:
        return {"status": "controller_unreachable", "error": str(exc)}

    write = _test_write(ds)
    print(f"  stimulus write: rumble={write['rumble']} adaptive_trigger={write['trigger']}")
    latencies = []
    try:
        for i in range(trials):
            time.sleep(random.uniform(1.0, 3.0))   # nonce-like unpredictable timing
            base = _snapshot(ds)
            _fire(ds); t0 = time.time(); lat = None
            while time.time() - t0 < timeout_s:
                if reaction_detected(base, _snapshot(ds)):
                    lat = (time.time() - t0) * 1000.0
                    break
                time.sleep(0.001)
            _stop(ds)
            if lat is not None:
                latencies.append(lat)
                print(f"  trial {i + 1}/{trials}: reacted {lat:.0f} ms"
                      f"{' (in band)' if in_human_band(lat) else ' (out of band)'}")
            else:
                print(f"  trial {i + 1}/{trials}: no reaction within {timeout_s:.1f}s")
            time.sleep(0.3)
    finally:
        _stop(ds)
        try:
            ds.close()
        except Exception:
            pass

    in_band = [x for x in latencies if in_human_band(x)]
    med = statistics.median(latencies) if latencies else None
    return {
        "status": "ok",
        "write_rumble": write["rumble"],
        "write_trigger": write["trigger"],
        "trials": trials,
        "reactions": len(latencies),
        "in_band": len(in_band),
        "median_latency_ms": round(med, 1) if med is not None else None,
        "go": bool((write["rumble"] or write["trigger"]) and len(in_band) >= max(1, trials // 2)
                   and med is not None and in_human_band(med)),
    }


def run_controlled_derisk(trials: int = 12, timeout_s: float = 1.2) -> dict:
    """In-game negative-control: interleave BUZZ and SHAM (no-stimulus) trials and compare.
    Isolates a genuine buzz-reaction from gameplay tripping the detector."""
    try:
        from pydualsense import pydualsense
    except Exception as exc:
        return {"status": "no_pydualsense", "error": str(exc)}
    ds = pydualsense()
    try:
        ds.init()
    except Exception as exc:
        return {"status": "controller_unreachable", "error": str(exc)}
    write = _test_write(ds)
    buzz_lats, sham_lats, n_buzz, n_sham = [], [], 0, 0
    try:
        for i in range(trials):
            is_buzz = random.random() < 0.5
            time.sleep(random.uniform(1.0, 3.0))
            base = _snapshot(ds)
            if is_buzz:
                _fire(ds)
            t0 = time.time(); lat = None
            while time.time() - t0 < timeout_s:
                if reaction_detected(base, _snapshot(ds)):
                    lat = (time.time() - t0) * 1000.0
                    break
                time.sleep(0.001)
            if is_buzz:
                _stop(ds); n_buzz += 1
                if lat is not None:
                    buzz_lats.append(lat)
            else:
                n_sham += 1
                if lat is not None:
                    sham_lats.append(lat)
            tag = "BUZZ" if is_buzz else "SHAM"
            print(f"  trial {i + 1}/{trials} [{tag}]: "
                  f"{f'{lat:.0f} ms' if lat is not None else 'no detection'}")
            time.sleep(0.3)
    finally:
        _stop(ds)
        try:
            ds.close()
        except Exception:
            pass
    out = assess_control(buzz_lats, sham_lats, n_buzz, n_sham)
    out["status"] = "ok"
    out["write_ok"] = bool(write["rumble"] or write["trigger"])
    return out


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--trials", type=int, default=6)
    ap.add_argument("--control", action="store_true",
                    help="in-game negative control: interleave sham (no-buzz) trials to rule out gameplay confound")
    a = ap.parse_args()
    if a.control:
        print("=" * 64)
        print("QorTroller PoEP — negative control (buzz vs sham)")
        print("=" * 64)
        print("  React to a buzz when you feel one; some trials fire no buzz (sham).")
        print("  STANDALONE (not playing) validates the enrollment form (expect SHAM rate ~0);")
        print("  in-game tests that mode (gameplay usually trips SHAM -> confounded).\n")
        r = run_controlled_derisk(max(a.trials, 12))
        print("  " + "=" * 60)
        if r.get("status") != "ok":
            print(f"  ABORT: {r.get('status')} {r.get('error','')}"); return 4
        print(f"  BUZZ: detect_rate={r['buzz_detect_rate']} median={r['buzz_median_ms']} ms")
        print(f"  SHAM: detect_rate={r['sham_detect_rate']} median={r['sham_median_ms']} ms (gameplay false-positives)")
        print(f"  RESULT: {r['verdict']}")
        return 0 if r["genuine_buzz_driven"] else 6
    print("=" * 64)
    print("QorTroller PoEP — stimulus-write + reflex-capture de-risk")
    print("=" * 64)
    print("  Hold the controller (USB). React the instant you feel the buzz:")
    print("  press R2 or flick the RIGHT stick.\n")
    r = run_derisk(a.trials)
    print("  " + "=" * 60)
    if r["status"] == "no_pydualsense":
        print("  ABORT: pip install pydualsense"); return 4
    if r["status"] == "controller_unreachable":
        print(f"  NO-GO: controller not reachable ({r['error']})"); return 4
    if not (r["write_rumble"] or r["write_trigger"]):
        print("  NO-GO: could not write any stimulus to the controller."); return 5
    if r["reactions"] == 0:
        print("  NO-GO: stimulus fired but no reflex captured (wrong interface? not reacting?)")
        return 6
    print(f"  reactions {r['reactions']}/{r['trials']}, in-band {r['in_band']}, "
          f"median {r['median_latency_ms']} ms")
    if r["go"]:
        print("  RESULT: GO — stimulus writes AND a human-band reflex is captured. Build P1.")
        return 0
    print("  RESULT: NO-GO — write or reflex-timing did not meet the human-band gate.")
    return 6


if __name__ == "__main__":
    sys.exit(main())
