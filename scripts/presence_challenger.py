"""In-session presence challenger (standalone, coexists with the running bridge).

Confirmed architecture: a separate pydualsense process can drive the controller's
motors + read inputs WHILE the bridge captures via hidapi (coexistence verified
2026-06-21). So this runs alongside the bridge during NCAA CFB capture:

  on a JITTERED, unpredictable cadence (idle-gated):
    - REAL challenge: fire the felt MOTOR SIGNATURE, then watch for the response
      gesture (default R5 back paddle) within the human band [120,450] ms.
    - SHAM trial (no buzz): open the same window; a response here is a false alarm.
  -> log each presence proof to l6b_probe_log; report the in-band response RATE to
     real buzzes vs shams. The buzz-vs-sham GAP is the determination that a live
     human is perceiving + responding (not gameplay coincidence).

Presence proof = stimulus-locked, human-latency response to an UNPREDICTABLE buzz,
validated against shams. It proves "a human is in the loop responding," NOT identity
and NOT "a human is generating all the gameplay" (the relay gap the retina axis covers).

Run the bridge first (real-controller mode), then this. Validate with --once.
    py scripts/presence_challenger.py --once
    py scripts/presence_challenger.py --interval 30 --jitter 10 --sham-rate 0.3
"""
from __future__ import annotations

import argparse
import os
import random
import sqlite3
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from bridge.controller.presence_challenge import (  # noqa: E402
    ChallengeScheduler,
    classify_gesture_response,
    forceful_motor_signature,
)

_DEFAULT_DEVICE = "581a836c98b3a1b6c0f598bfca88e6a3cc3bd7c34591b506692cb40ddf66a9f8"
_DEFAULT_DB = os.path.expanduser("~/.vapi/bridge.db")


def _connect():
    try:
        from pydualsense import pydualsense
    except ImportError:
        print("[challenger] pydualsense not installed."); return None
    try:
        ds = pydualsense(); ds.init()
    except Exception as exc:
        print(f"[challenger] could not open controller ({exc})."); return None
    return ds


def _gesture_active(ds, response: str) -> bool:
    st = ds.state
    if response == "swipe":
        return bool(getattr(getattr(st, "trackPadTouch0", None), "isActive", False))
    return bool(getattr(st, response.upper(), False))  # r5 -> R5, l5 -> L5


def _is_active_player(ds) -> bool:
    """Light idle-gate: stick off-center or a face button / trigger engaged."""
    st = ds.state
    lx, ly = getattr(st, "LX", 128), getattr(st, "LY", 128)
    if abs(lx - 128) > 12 or abs(ly - 128) > 12:
        return True
    if getattr(st, "R2_value", 0) > 12 or getattr(st, "L2_value", 0) > 12:
        return True
    return any(getattr(st, b, False) for b in ("cross", "circle", "square", "triangle"))


def run_challenge(ds, sig, response: str, window_ms: float, real: bool) -> dict:
    """Fire (or sham) + sample the gesture for the reaction window. Returns the classify dict."""
    steps = sig.steps() if real else []
    sched, t = [], 0.0
    for left, right, dur in steps:
        sched.append((t, t + dur, left, right)); t += dur
    total_s = max(window_ms / 1000.0, t)
    t0 = time.monotonic()
    samples, cur = [], None
    while True:
        el = time.monotonic() - t0
        if el > total_s:
            break
        if real:
            seg = next(((l, r) for (s, e, l, r) in sched if s <= el < e), (0, 0))
            if seg != cur:
                ds.setLeftMotor(seg[0]); ds.setRightMotor(seg[1]); cur = seg
        el_ms = el * 1000.0
        if el_ms <= window_ms:
            samples.append((el_ms, _gesture_active(ds, response)))
        time.sleep(0.005)
    if real:
        ds.setLeftMotor(0); ds.setRightMotor(0)
    return classify_gesture_response(samples)


def log_probe(db: str, device_id: str, result: dict, cco_profile_id: str) -> None:
    conn = sqlite3.connect(db, timeout=5.0)
    try:
        conn.execute("PRAGMA busy_timeout=5000")
        conn.execute(
            "INSERT INTO l6b_probe_log (device_id, probe_ts_ms, latency_ms, classification, "
            "accel_delta_peak, reflex_verdict, cco_profile_id) VALUES (?,?,?,?,?,?,?)",
            (device_id, int(time.time() * 1000), result.get("latency_ms"),
             result["classification"], 0.0, result.get("reflex_verdict"), cco_profile_id),
        )
        conn.commit()
    finally:
        conn.close()


def main() -> int:
    ap = argparse.ArgumentParser(description="In-session presence challenger")
    ap.add_argument("--device", default=_DEFAULT_DEVICE)
    ap.add_argument("--db", default=_DEFAULT_DB)
    ap.add_argument("--cco-profile-id", default="sony_dualshock_edge_v1")
    ap.add_argument("--response", default="r5", choices=["r5", "l5", "swipe"])
    ap.add_argument("--amp", type=int, default=255)
    ap.add_argument("--pulses", type=int, default=3)
    ap.add_argument("--window-ms", type=float, default=450.0)
    ap.add_argument("--interval", type=float, default=30.0)
    ap.add_argument("--jitter", type=float, default=10.0)
    ap.add_argument("--sham-rate", type=float, default=0.3)
    ap.add_argument("--once", action="store_true", help="fire one REAL challenge + report, then exit")
    args = ap.parse_args()

    sig = forceful_motor_signature(args.amp, args.pulses)
    ds = _connect()
    if ds is None:
        return 2
    print(f"[challenger] response={args.response} amp={args.amp} band=[120,{args.window_ms:.0f}]ms "
          f"db={args.db}")
    rng = random.Random()
    tallies = {"real": 0, "real_hit": 0, "sham": 0, "sham_hit": 0}

    try:
        if args.once:
            print("[challenger] ONE real challenge in 3s — feel the buzz, then press your "
                  f"{args.response.upper()} gesture...")
            time.sleep(3)
            res = run_challenge(ds, sig, args.response, args.window_ms, real=True)
            log_probe(args.db, args.device, res, args.cco_profile_id)
            print(f"[challenger] result: {res}  (logged to l6b_probe_log)")
            return 0

        sched = ChallengeScheduler(interval_s=args.interval, jitter_s=args.jitter)
        print("[challenger] running — Ctrl-C to stop. Press your gesture only when you FEEL a buzz.")
        while True:
            now = time.monotonic()
            if sched.should_fire(now, _is_active_player(ds), rng):
                is_sham = rng.random() < args.sham_rate
                res = run_challenge(ds, sig, args.response, args.window_ms, real=not is_sham)
                hit = res["classification"] == "HUMAN"
                if is_sham:
                    tallies["sham"] += 1; tallies["sham_hit"] += int(hit)
                else:
                    tallies["real"] += 1; tallies["real_hit"] += int(hit)
                    log_probe(args.db, args.device, res, args.cco_profile_id)
                rr = tallies["real_hit"] / tallies["real"] if tallies["real"] else 0.0
                sr = tallies["sham_hit"] / tallies["sham"] if tallies["sham"] else 0.0
                tag = "SHAM " if is_sham else "REAL "
                print(f"[challenger] {tag} {res['classification']:<11} lat={res.get('latency_ms')}  "
                      f"| real-in-band={rr:.2f} ({tallies['real_hit']}/{tallies['real']})  "
                      f"sham-false={sr:.2f} ({tallies['sham_hit']}/{tallies['sham']})  "
                      f"GAP={rr - sr:+.2f}")
                sched.schedule_next(now, rng)
            time.sleep(0.1)
    except KeyboardInterrupt:
        print("\n[challenger] stopped. Presence is verified when real-in-band >> sham-false (the GAP).")
    finally:
        try:
            ds.setLeftMotor(0); ds.setRightMotor(0); ds.close()
        except Exception:
            pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
