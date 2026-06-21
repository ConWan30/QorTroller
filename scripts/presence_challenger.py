"""In-session presence challenger (standalone, coexists with the running bridge).

Confirmed architecture: a separate pydualsense process can drive the controller's
motors + read inputs WHILE the bridge captures via hidapi (coexistence verified
2026-06-21). So this runs alongside the bridge during NCAA CFB capture:

  on a JITTERED, unpredictable cadence (idle-gated):
    - REAL challenge: fire the felt MOTOR SIGNATURE + orange LED, then watch for ANY
      accepted response gesture (default L5 paddle OR a touchpad touch) within the
      human band. --response is '+'-joined (e.g. l5+touch); any one counts.
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
    MotorSignature,
)
from bridge.controller.probe_gate import (  # noqa: E402
    GateConfig,
    GateSample,
    GateState,
    accel_variance,
    clear_to_fire,
    echo_confirmed,
    update_baseline,
)
from bridge.controller.probe_context import clear_to_fire_context  # noqa: E402
from bridge.controller.probe_screen import clear_to_fire_screen, read_screen_region  # noqa: E402

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


def _challenge_on(ds) -> None:
    """Arm all challenge channels: max trigger vibration on both sides + lightbar orange."""
    try:
        from pydualsense import TriggerModes
        for trigger in (ds.triggerL, ds.triggerR):
            trigger.setMode(TriggerModes(0x02))  # PULSE/vibration mode
            for i in range(7):                   # all 7 force slots maxed
                trigger.setForce(i, 255)
    except Exception:
        pass
    try:
        ds.light.setColorI(255, 80, 0)  # bright orange — never a game lightbar color
    except Exception:
        pass


def _challenge_off(ds) -> None:
    """Reset all challenge channels: stop trigger vibration + restore lightbar."""
    try:
        from pydualsense import TriggerModes
        for trigger in (ds.triggerL, ds.triggerR):
            trigger.setMode(TriggerModes(0x00))
            for i in range(7):
                trigger.setForce(i, 0)
    except Exception:
        pass
    try:
        ds.light.setColorI(0, 0, 4)  # dim blue — resting state
    except Exception:
        pass


_KNOWN_GESTURES = ("l5", "r5", "l4", "r4", "touch")


def parse_accepted(response: str) -> list[str]:
    """'l5+touch' -> ['l5','touch'] (any one of them counts as a response).

    Tokens split on '+' or ','; 'swipe'/'touchpad' alias to 'touch'. Raises ValueError
    on an unknown token. Empty -> ['l5'] (back-compat default)."""
    toks = [t.strip().lower() for t in response.replace(",", "+").split("+") if t.strip()]
    out: list[str] = []
    for t in toks:
        if t in ("touch", "swipe", "touchpad"):
            t = "touch"
        if t not in _KNOWN_GESTURES:
            raise ValueError(f"unknown gesture '{t}' (known: {'+'.join(_KNOWN_GESTURES)})")
        if t not in out:
            out.append(t)
    return out or ["l5"]


def gesture_active_from_state(state, accepted: list[str]) -> bool:
    """True if ANY accepted gesture is active on this controller state (pure; testable)."""
    for g in accepted:
        if g == "touch":
            if bool(getattr(getattr(state, "trackPadTouch0", None), "isActive", False)):
                return True
        elif bool(getattr(state, g.upper(), False)):  # l5 -> L5, r5 -> R5, ...
            return True
    return False


def _gesture_active(ds, accepted: list[str]) -> bool:
    return gesture_active_from_state(ds.state, accepted)


def _accel_mag(st) -> float:
    """|accel| from the controller IMU; 0.0 if the field isn't exposed (tolerant)."""
    acc = getattr(st, "accelerometer", None)
    if acc is None:
        return 0.0
    try:
        x = float(getattr(acc, "X", 0) or 0)
        y = float(getattr(acc, "Y", 0) or 0)
        z = float(getattr(acc, "Z", 0) or 0)
    except Exception:
        return 0.0
    return (x * x + y * y + z * z) ** 0.5


def _gate_sample(ds) -> GateSample:
    st = ds.state
    return GateSample(
        lx=int(getattr(st, "LX", 128)),
        ly=int(getattr(st, "LY", 128)),
        l2=int(getattr(st, "L2_value", 0)),
        r2=int(getattr(st, "R2_value", 0)),
        accel_mag=_accel_mag(st),
    )


def _sample_window(ds, dur_s: float, hz: float = 250.0) -> list[GateSample]:
    """Read controller input for dur_s into GateSamples (for the pre-fire lull check)."""
    out: list[GateSample] = []
    t0 = time.monotonic()
    dt = 1.0 / hz
    while time.monotonic() - t0 < dur_s:
        out.append(_gate_sample(ds))
        time.sleep(dt)
    return out


def _var(xs: list[float]) -> float:
    n = len(xs)
    if n < 2:
        return 0.0
    m = sum(xs) / n
    return sum((x - m) ** 2 for x in xs) / n


def format_selftest_line(sample: GateSample, window: list[GateSample],
                         baseline_var: float, gate_cfg: GateConfig) -> str:
    """One human-readable diagnostic line for --selftest: live IMU + sticks + gate verdict.
    Pure (no controller); the live loop builds the window and feeds it here."""
    wv = accel_variance(window)
    clear, state = clear_to_fire(window, baseline_var, gate_cfg)
    return (f"accel|mag|={sample.accel_mag:8.1f}  var={wv:9.2f}  base={baseline_var:9.2f}  "
            f"lx={sample.lx:3d} ly={sample.ly:3d} l2={sample.l2:3d} r2={sample.r2:3d}  "
            f"-> {state.value:<9} {'CLEAR-to-fire' if clear else 'defer'}")


def run_selftest(ds, secs: float, gate_cfg: GateConfig, *, hz: float = 50.0,
                 print_hz: float = 5.0) -> int:
    """Read-only diagnostic: print live IMU + gate state for `secs`, then verdict whether the
    IMU is actually exposed (so the veto/echo have a real signal). Fires NO buzz."""
    print(f"[selftest] reading IMU + gate state for {secs:.0f}s (no buzz). Move sticks / press "
          "triggers to watch the gate flip ACTIVE; hold still to see LULL.")
    window: list[GateSample] = []
    baseline_var: float | None = None
    t0 = time.monotonic()
    last_print = 0.0
    max_accel = 0.0
    dt = 1.0 / hz
    while time.monotonic() - t0 < secs:
        s = _gate_sample(ds)
        window.append(s)
        if len(window) > 60:
            window.pop(0)
        max_accel = max(max_accel, s.accel_mag)
        now = time.monotonic()
        if now - last_print >= 1.0 / print_hz and len(window) >= gate_cfg.min_samples:
            wv = accel_variance(window)
            if baseline_var is None:
                baseline_var = wv
            print("[selftest] " + format_selftest_line(s, window, baseline_var, gate_cfg))
            _clear, state = clear_to_fire(window, baseline_var, gate_cfg)
            if state is GateState.LULL:
                baseline_var = update_baseline(baseline_var, wv)
            last_print = now
        time.sleep(dt)
    if max_accel <= 0.0:
        print("[selftest] WARNING: accel magnitude stayed 0 — pydualsense did not expose the IMU "
              "(check the accelerometer attr names in _accel_mag). The pre-fire veto and haptic "
              "self-echo will silently no-op until this reads non-zero.")
        return 1
    print(f"[selftest] IMU OK — peak |accel|={max_accel:.1f} (non-zero); the veto + echo have a "
          "real signal. Gate transitions LULL<->ACTIVE above are live.")
    return 0


def fetch_bridge_context(base_url: str, api_key: str = "", timeout: float = 1.5) -> dict | None:
    """Fetch the bridge's live gameplay context (APOP richest, GAD fallback). Returns the
    status dict, or None on ANY failure (bridge down / endpoint missing) so the caller
    treats the context gate as inert rather than blocking the probe loop."""
    import json as _json
    import urllib.request

    for path in ("/agent/active-play-occupancy-status", "/bridge/capture-health"):
        try:
            req = urllib.request.Request(base_url.rstrip("/") + path)
            if api_key:
                req.add_header("x-api-key", api_key)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = _json.loads(resp.read().decode("utf-8"))
            if isinstance(data, dict) and (
                data.get("latest_state") or data.get("latest_gameplay_context")
            ):
                return data
        except Exception:
            continue
    return None


def _is_active_player(ds) -> bool:
    """Light idle-gate: stick off-center or a face button / trigger engaged."""
    st = ds.state
    lx, ly = getattr(st, "LX", 128), getattr(st, "LY", 128)
    if abs(lx - 128) > 12 or abs(ly - 128) > 12:
        return True
    if getattr(st, "R2_value", 0) > 12 or getattr(st, "L2_value", 0) > 12:
        return True
    return any(getattr(st, b, False) for b in ("cross", "circle", "square", "triangle"))


def run_challenge(ds, sig, accepted: list[str], window_ms: float, real: bool,
                  band_max_ms: float = 800.0, baseline_var: float | None = None) -> dict:
    """Fire (or sham) + sample the gesture(s) for the reaction window. ANY accepted
    gesture (e.g. L5 paddle OR touchpad) counts. While firing, also sample the IMU during
    our own pulses for the HAPTIC SELF-ECHO check. Returns the classify dict, augmented
    (on real challenges) with during_accel_var and, if baseline_var given, echo_confirmed."""
    steps = sig.steps() if real else []
    sched, t = [], 0.0
    for left, right, dur in steps:
        sched.append((t, t + dur, left, right)); t += dur
    sig_dur_s = t
    total_s = max(window_ms / 1000.0, t)
    if real:
        _challenge_on(ds)  # trigger vibration + orange lightbar
    t0 = time.monotonic()
    samples, cur, accel_during = [], None, []
    try:
        while True:
            el = time.monotonic() - t0
            if el > total_s:
                break
            if real:
                seg = next(((l, r) for (s, e, l, r) in sched if s <= el < e), (0, 0))
                if seg != cur:
                    ds.setLeftMotor(seg[0]); ds.setRightMotor(seg[1]); cur = seg
                if el <= sig_dur_s:                       # IMU echo only while our motors run
                    accel_during.append(_accel_mag(ds.state))
            el_ms = el * 1000.0
            if el_ms <= window_ms:
                samples.append((el_ms, _gesture_active(ds, accepted)))
            time.sleep(0.005)
    finally:
        if real:
            ds.setLeftMotor(0); ds.setRightMotor(0)
            _challenge_off(ds)  # stop trigger vibration + restore lightbar
    res = classify_gesture_response(samples, human_max_ms=band_max_ms)
    if real:
        dv = _var(accel_during)
        res["during_accel_var"] = round(dv, 4)
        if baseline_var is not None:
            res["echo_confirmed"] = echo_confirmed(dv, baseline_var)
    return res


def _ensure_record_hash_column(conn: sqlite3.Connection) -> bool:
    """Additive, idempotent migration: give l6b_probe_log a record_hash column so a
    presence proof can carry the PoAC anchor of the gameplay record it was bound to.
    ADD COLUMN is metadata-only in SQLite (fast, non-destructive); existing inserts
    that don't name the column are unaffected. Returns True if the column is present."""
    cols = [c[1] for c in conn.execute("PRAGMA table_info(l6b_probe_log)").fetchall()]
    if "record_hash" in cols:
        return True
    try:
        conn.execute("ALTER TABLE l6b_probe_log ADD COLUMN record_hash TEXT")
        conn.commit()
        return True
    except sqlite3.OperationalError:
        return False  # racing add or locked — fall back to no-hash insert


def _live_record_hash(conn: sqlite3.Connection, device_id: str) -> str | None:
    """The most recent gameplay PoAC record_hash for this device = the cryptographic
    anchor co-temporal with this probe. None if the bridge has written no records yet
    (e.g. menu-only / no active gameplay), in which case the probe logs unbound."""
    try:
        row = conn.execute(
            "SELECT record_hash FROM records WHERE device_id=? ORDER BY rowid DESC LIMIT 1",
            (device_id,),
        ).fetchone()
        return row[0] if row else None
    except sqlite3.OperationalError:
        return None


def log_probe(db: str, device_id: str, result: dict, cco_profile_id: str) -> None:
    conn = sqlite3.connect(db, timeout=5.0)
    try:
        conn.execute("PRAGMA busy_timeout=5000")
        has_rh = _ensure_record_hash_column(conn)
        if has_rh:
            # PRODUCTION BINDING: stamp the live PoAC record_hash so the presence proof
            # and the gameplay record share one verifiable anchor (not just a timestamp).
            record_hash = _live_record_hash(conn, device_id)
            conn.execute(
                "INSERT INTO l6b_probe_log (device_id, probe_ts_ms, latency_ms, classification, "
                "accel_delta_peak, reflex_verdict, cco_profile_id, record_hash) "
                "VALUES (?,?,?,?,?,?,?,?)",
                (device_id, int(time.time() * 1000), result.get("latency_ms"),
                 result["classification"], 0.0, result.get("reflex_verdict"),
                 cco_profile_id, record_hash),
            )
        else:
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
    ap.add_argument("--response", default="l5+touch",
                    help="accepted response gesture(s), '+'-joined; ANY one counts. "
                         "Tokens: l5 r5 l4 r4 touch (swipe/touchpad alias touch). "
                         "Default 'l5+touch' = L5 paddle OR a touchpad touch while the LED is orange.")
    ap.add_argument("--amp", type=int, default=255)
    ap.add_argument("--pulses", type=int, default=6)
    ap.add_argument("--on-ms", type=int, default=300,
                    help="motor-on duration per pulse ms (default 300)")
    ap.add_argument("--off-ms", type=int, default=20,
                    help="gap between pulses ms (default 20 — near-continuous, side-switch only)")
    ap.add_argument("--alternate", action="store_true", default=True,
                    help="alternate left/right motors (default ON — games fire both simultaneously; "
                         "alternating is perceptually distinct from any in-game haptic)")
    ap.add_argument("--no-alternate", dest="alternate", action="store_false",
                    help="disable alternating (both motors simultaneously)")
    ap.add_argument("--window-ms", type=float, default=800.0)
    ap.add_argument("--band-max-ms", type=float, default=800.0,
                    help="upper edge of human reaction band in ms (default 800 for gameplay)")
    ap.add_argument("--interval", type=float, default=30.0)
    ap.add_argument("--jitter", type=float, default=10.0)
    ap.add_argument("--sham-rate", type=float, default=0.3)
    ap.add_argument("--lull-gate", action="store_true", default=True,
                    help="fire ONLY in a quiet between-plays lull (still sticks + no trigger + "
                         "quiet IMU); defer otherwise (default ON — avoids in-game haptic collision)")
    ap.add_argument("--no-lull-gate", dest="lull_gate", action="store_false",
                    help="disable the lull gate (fire on the jittered schedule regardless)")
    ap.add_argument("--prefire-ms", type=float, default=300.0,
                    help="pre-fire IMU sniff window in ms used by the lull gate (default 300)")
    ap.add_argument("--haptic-ratio", type=float, default=3.0,
                    help="defer if pre-fire accel variance > baseline*ratio (default 3.0)")
    # context gate (opt-in): reuse the bridge's APOP/GAD classifier as a semantic lull source
    ap.add_argument("--context-gate", action="store_true", default=False,
                    help="ALSO require the bridge to report a between-plays lull (APOP "
                         "MATCH_TRANSITION); inert if the bridge is unreachable")
    ap.add_argument("--bridge-url", default="http://127.0.0.1:8000",
                    help="bridge base URL for the context gate (default http://127.0.0.1:8000)")
    ap.add_argument("--bridge-api-key", default="",
                    help="x-api-key for the bridge context endpoints, if required")
    ap.add_argument("--context-allow-menu", action="store_true", default=False,
                    help="context gate also accepts NON_COMPETITIVE_MENU as a quiet window")
    # screen gate (opt-in, heaviest): OCR the play-clock / stoppage banner
    ap.add_argument("--screen-gate", action="store_true", default=False,
                    help="ALSO require an on-screen pre-snap/stoppage window (needs pytesseract "
                         "+ the game visible); inert if OCR/capture unavailable")
    ap.add_argument("--screen-region", nargs=4, type=int, default=[0, 0, 400, 120],
                    metavar=("X", "Y", "W", "H"),
                    help="screen region (x y w h) to OCR for the play clock / banner")
    ap.add_argument("--once", action="store_true", help="fire one REAL challenge + report, then exit")
    ap.add_argument("--selftest", action="store_true",
                    help="read-only: print live IMU + gate state (no buzz), then verify the IMU "
                         "is actually exposed. Use to validate the rig before a real run.")
    ap.add_argument("--selftest-secs", type=float, default=10.0,
                    help="duration of --selftest in seconds (default 10)")
    args = ap.parse_args()

    try:
        accepted = parse_accepted(args.response)
    except ValueError as exc:
        print(f"[challenger] {exc}"); return 2

    sig = MotorSignature(amp=max(0, min(255, args.amp)), pulses=max(1, args.pulses),
                         on_ms=args.on_ms, off_ms=args.off_ms, alternate=args.alternate)
    ds = _connect()
    if ds is None:
        return 2
    alt_tag = "alternate-L/R" if args.alternate else "bilateral"
    gate_cfg = GateConfig(haptic_ratio=args.haptic_ratio)
    baseline_var: float | None = None
    gates = ["IMU"] if args.lull_gate else []
    if args.context_gate:
        gates.append("CTX")
    if args.screen_gate:
        gates.append("SCR")
    print(f"[challenger] response={'+'.join(accepted)} amp={args.amp} pulses={args.pulses} "
          f"sig={alt_tag} on={args.on_ms}ms/off={args.off_ms}ms "
          f"band=[120,{args.band_max_ms:.0f}]ms gates={'+'.join(gates) or 'none'} db={args.db}")
    rng = random.Random()
    tallies = {"real": 0, "real_hit": 0, "sham": 0, "sham_hit": 0}

    try:
        if args.selftest:
            return run_selftest(ds, args.selftest_secs, gate_cfg)

        if args.once:
            print("[challenger] ONE real challenge in 3s — feel the buzz, then respond with "
                  f"{' OR '.join(g.upper() for g in accepted)}...")
            time.sleep(3)
            res = run_challenge(ds, sig, accepted, args.window_ms, real=True,
                                band_max_ms=args.band_max_ms, baseline_var=baseline_var)
            log_probe(args.db, args.device, res, args.cco_profile_id)
            print(f"[challenger] result: {res}  (logged to l6b_probe_log)")
            return 0

        sched = ChallengeScheduler(interval_s=args.interval, jitter_s=args.jitter)
        print("[challenger] running — Ctrl-C to stop. Press your gesture only when you FEEL a buzz.")
        while True:
            now = time.monotonic()
            if sched.should_fire(now, _is_active_player(ds), rng):
                # IMU LULL GATE: sniff a pre-fire window; fire only in a quiet between-plays lull.
                if args.lull_gate:
                    win = _sample_window(ds, args.prefire_ms / 1000.0)
                    wv = accel_variance(win)
                    if baseline_var is None:
                        baseline_var = wv  # establish the quiet reference on first read
                    clear, state = clear_to_fire(win, baseline_var, gate_cfg)
                    if state is GateState.LULL:
                        baseline_var = update_baseline(baseline_var, wv)
                    if not clear:
                        print(f"[challenger] defer (IMU:{state.value}) — waiting for a lull")
                        sched.schedule_next(now, rng)
                        time.sleep(0.1)
                        continue

                # CONTEXT GATE (opt-in): require the bridge to agree we're between plays.
                # Inert when the bridge is unreachable (health=None) so it never blocks.
                if args.context_gate:
                    health = fetch_bridge_context(args.bridge_url, args.bridge_api_key)
                    if health is not None:
                        cclear, cverdict = clear_to_fire_context(
                            health, allow_menu=args.context_allow_menu)
                        if not cclear:
                            print(f"[challenger] defer (CTX:{cverdict.value}) — bridge not in a lull")
                            sched.schedule_next(now, rng)
                            time.sleep(0.1)
                            continue

                # SCREEN GATE (opt-in, heaviest): require an on-screen pre-snap/stoppage.
                # Inert when OCR/capture unavailable (text=None) so it never blocks.
                if args.screen_gate:
                    text = read_screen_region(tuple(args.screen_region))
                    if text is not None:
                        sclear, sverdict = clear_to_fire_screen(text)
                        if not sclear:
                            print(f"[challenger] defer (SCR:{sverdict.value}) — no on-screen lull")
                            sched.schedule_next(now, rng)
                            time.sleep(0.1)
                            continue
                is_sham = rng.random() < args.sham_rate
                res = run_challenge(ds, sig, accepted, args.window_ms, real=not is_sham,
                                    band_max_ms=args.band_max_ms, baseline_var=baseline_var)
                hit = res["classification"] == "HUMAN"
                if is_sham:
                    tallies["sham"] += 1; tallies["sham_hit"] += int(hit)
                else:
                    tallies["real"] += 1; tallies["real_hit"] += int(hit)
                    log_probe(args.db, args.device, res, args.cco_profile_id)
                rr = tallies["real_hit"] / tallies["real"] if tallies["real"] else 0.0
                sr = tallies["sham_hit"] / tallies["sham"] if tallies["sham"] else 0.0
                tag = "SHAM " if is_sham else "REAL "
                echo = res.get("echo_confirmed")
                echo_tag = "" if echo is None else f" echo={'OK' if echo else 'MISS'}"
                print(f"[challenger] {tag} {res['classification']:<11} lat={res.get('latency_ms')}"
                      f"{echo_tag}  "
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
