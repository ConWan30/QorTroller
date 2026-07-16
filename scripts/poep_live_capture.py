"""POEP-LIVE-1 — live NONCE-SCHEDULED reflex capture on the registered Edge (A2A-POEP, rig runner).

The N=52 usable-reflex corpus was built by the desk reaction session, which fires the challenge on
`input("Press ENTER to fire probe...")` — the operator KNOWS exactly when the resistance is coming.
That predictable timing is the exact hole the P4 adversarial gate exploited (A-CONST macro FAR 0.76,
A-REPLAY 0.90): offline scoring of a reflex whose onset you can pre-schedule against is a band check,
not a presence detector.

This runner reuses the IDENTICAL fire->hold->capture primitive (`_fire_probe_sync`) that recorded the
corpus, but replaces the ENTER cue with a challenge that fires at an UNPREDICTABLE, nonce-derived random
moment, and binds the response to a FRESH per-challenge nonce via `l9_presence.poep_live_verify`. That
one change turns "reflex consistency" (what the corpus measured) into the LIVE presence protocol that
defeats replay + pre-scheduled macros BY CONSTRUCTION (grok round-16 verdict; see
`l9_presence/poep_live_verify.py` docstring for the exact attack-class mapping).

HONEST LIMITS (unchanged — this runner does NOT flip anything):
  - poep_enabled / L6B_ENABLED / L6_CHALLENGES_ENABLED stay FALSE. This produces CANDIDATE live evidence
    + exercises the verify path on real hardware. It does NOT earn the flip.
  - The capture is fully SILENT and polls continuously from arm to fire (F-POEP-LIVE-1 (i), grok
    round-19) so there is no stdout tell and no poll-burst transition to pre-arm on. It still does NOT
    defeat a REACTIVE bot that watches the HID OUTPUT force command and reacts in-band (A-REACTIVE) —
    that is uncloseable for any host-timed proof and is explicitly out of scope until controller-firmware
    force-timestamp / waveform-shape + Stage-A land. The claim is "must react to a live unpredictable
    stimulus a pre-scheduled / stdout-tell / poll-burst macro cannot time", a much stronger bar than
    offline scoring, but not yet "embodied human".

Run this in YOUR OWN terminal (it is interactive — your reflex is the input):
  # stop the bridge first (dual-writer contention), then:
  python scripts/poep_live_capture.py --count 8 --db "C:/Users/Contr/.vapi/bridge.db"

Reuses (no drift): scripts/l6b_desk_reaction_session._fire_probe_sync + _resolve_registered_edge_device_id,
bridge/vapi_bridge/l6b_desk_session.{DeskProbeConfig,analyze_desk_probe,persist_desk_probe,...}, and
l9_presence.poep_live_verify.{LiveChallenge,ChallengeResponse,poep_commitment,response_feature_digest,
verify_live_response}. Edge-reflex defaults mirror the corpus-capture path byte-for-byte.
"""
from __future__ import annotations

import argparse
import json
import secrets
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from l9_presence.poep_live_verify import (  # noqa: E402
    ChallengeResponse,
    LiveChallenge,
    poep_commitment,
    response_feature_digest,
    schedule_commitment,
    verify_live_response,
    waveform_commitment,
    waveform_digest,
)

# --- unpredictable-timing scheduler (pure, testable) ------------------------------------------------

DEFAULT_MIN_DELAY_S = 3.0
DEFAULT_MAX_DELAY_S = 12.0


def fresh_nonce() -> str:
    """A fresh, cryptographically-random per-challenge nonce (never revealed until the challenge)."""
    return secrets.token_hex(16)


# --- FLIP-A rung 2: raw reflex waveform (pure, testable) --------------------------------------------

def _accel_mag(report: dict) -> float:
    """Euclidean accel magnitude (LSB) from an IMU report dict {ax, ay, az, ...}."""
    ax = float(report.get("ax", 0.0) or 0.0)
    ay = float(report.get("ay", 0.0) or 0.0)
    az = float(report.get("az", 0.0) or 0.0)
    return (ax * ax + ay * ay + az * az) ** 0.5


def reflex_curve(pre_reports: list[dict], post_reports: list[dict]) -> list[float]:
    """The DC-removed post-fire reflex curve: ||accel|| per post sample minus the pre-window baseline
    mean. This is the raw waveform P-WAVE-0's shape gate consumes — it lets a rig session answer the
    load-bearing empirical question (does a real reflex settle-to-plateau or return-to-baseline?).
    Onset-aligned near 0 at the fire; rises to the reflex peak; then settles or relaxes."""
    if not post_reports:
        return []
    pre_mags = [_accel_mag(r) for r in pre_reports]
    baseline = (sum(pre_mags) / len(pre_mags)) if pre_mags else 0.0
    return [round(_accel_mag(r) - baseline, 1) for r in post_reports]


def csprng_delay_s(*, min_s: float = DEFAULT_MIN_DELAY_S, max_s: float = DEFAULT_MAX_DELAY_S) -> float:
    """F-POEP-LIVE-1 (ii): the challenge delay from an INDEPENDENT CSPRNG (not the nonce).

    Separating the schedule entropy from the binding nonce ends the round-17 bit-double-duty finding:
    a partial leak of the nonce (logs/crash) no longer leaks the fire schedule. The nonce is used only
    for the response commitment; the delay is drawn here and bound via `schedule_commitment`.
    """
    if max_s <= min_s:
        return max(0.0, min_s)
    span_ms = int(round((max_s - min_s) * 1000.0))
    if span_ms <= 0:
        return max(0.0, min_s)
    return min_s + secrets.randbelow(span_ms) / 1000.0


def nonce_derived_delay_s(nonce: str, *, min_s: float = DEFAULT_MIN_DELAY_S,
                          max_s: float = DEFAULT_MAX_DELAY_S) -> float:
    """DEPRECATED for the security-critical delay (use `csprng_delay_s`) — kept as a utility.

    Derives the challenge delay from the fresh secret nonce -> unpredictable while the nonce is secret.
    The load-bearing property is UNPREDICTABILITY: the nonce is generated fresh and unrevealed until the
    stimulus fires, so neither the operator nor a pre-scheduled macro can anticipate the onset (the
    property P-LIVE-0 needs against replay + pre-schedule).

    NOT provable by the auditor (F-POEP-LIVE-1, grok round-17): the P-LIVE-0 commitment binds
    (device_id, nonce, feature_digest, t_response) but NOT delay_s / arm-time, so `verify_live_response`
    does NOT prove the fire matched this nonce-derived schedule -- it only checks the post-hoc latency
    against the recorded t_challenge. Deriving delay from the nonce also puts schedule + binding entropy
    on ONE secret (bit double-duty). The hygiene upgrade is NOW LIVE via `csprng_delay_s` (independent
    CSPRNG for the delay + the nonce for binding only) + `schedule_commitment`; this function is retained
    only as a utility and is no longer on the security-critical path.
    """
    if max_s <= min_s:
        return max(0.0, min_s)
    span_ms = int(round((max_s - min_s) * 1000.0))
    if span_ms <= 0:
        return max(0.0, min_s)
    offset_ms = int(nonce[:8], 16) % span_ms
    return min_s + offset_ms / 1000.0


# --- pure record builder (testable without hardware) ------------------------------------------------

def build_live_record(
    *,
    device_id: str,
    nonce: str,
    t_challenge_ns: int,
    latency_ms: float | None,
    peak_lsb: float,
    precursor_gap_ms: float | None,
    classification: str,
    challenge_index: int,
    delay_s: float,
    t_arm_ns: int | None = None,
    waveform: list[float] | None = None,
) -> dict:
    """Build the P-LIVE-0 record for one challenge and run the fail-closed verify auditor.

    A no-response (no clean reflex peak) -> latency_ms None/<=0 -> t_response == t_challenge -> the
    auditor fails it honestly (response_not_after_challenge + reaction-band), never a spurious pass.

    When ``t_arm_ns`` is given (F-POEP-LIVE-1 (ii)), the CSPRNG-drawn ``delay_s`` + arm time are bound
    into a `schedule_commitment` so the fire schedule becomes auditable (and the auditor cross-checks
    that the fire landed at-or-after the committed delay). Absent -> legacy 3-field challenge.
    """
    lat = float(latency_ms) if (latency_ms is not None and latency_ms > 0.0) else 0.0
    precursor = float(precursor_gap_ms) if precursor_gap_ms is not None else 0.0
    # anchor the response time to the challenge via the measured reflex latency
    t_response_ns = t_challenge_ns + int(round(lat * 1e6)) if lat > 0.0 else t_challenge_ns

    feature_digest = response_feature_digest(lat, float(peak_lsb), precursor)
    commitment = poep_commitment(
        device_id=device_id, nonce=nonce, feature_digest=feature_digest, ts_ns=t_response_ns,
    )

    delay_ns = int(round(delay_s * 1e9))
    sched_commitment = None
    if t_arm_ns is not None:
        sched_commitment = schedule_commitment(
            nonce=nonce, delay_ns=delay_ns, t_arm_ns=t_arm_ns, t_challenge_ns=t_challenge_ns)

    # FLIP-A rung 2: bind the raw reflex waveform to this challenge (integrity only)
    wave_digest = None
    wave_commitment = None
    if waveform:
        wave_digest = waveform_digest(waveform)
        wave_commitment = waveform_commitment(
            nonce=nonce, wave_digest=wave_digest, t_challenge_ns=t_challenge_ns)

    ch = LiveChallenge(
        device_id=device_id, nonce=nonce, t_challenge_ns=t_challenge_ns,
        t_arm_ns=t_arm_ns, delay_ns=(delay_ns if t_arm_ns is not None else None),
        schedule_commitment=sched_commitment,
    )
    resp = ChallengeResponse(
        t_response_ns=t_response_ns,
        latency_ms=lat,
        peak_lsb=float(peak_lsb),
        precursor_gap_ms=precursor,
        nonce=nonce,
        commitment=commitment,
    )
    verdict = verify_live_response(ch, resp)
    return {
        "challenge_index": challenge_index,
        "nonce": nonce,
        "delay_s": round(delay_s, 3),
        "t_arm_ns": t_arm_ns,
        "t_challenge_ns": t_challenge_ns,
        "t_response_ns": t_response_ns,
        "latency_ms": round(lat, 3) if lat > 0.0 else None,
        "peak_lsb": round(float(peak_lsb), 1),
        "precursor_gap_ms": round(precursor, 3),
        "classification": classification,
        "feature_digest": feature_digest,
        "commitment": commitment,
        "schedule_commitment": sched_commitment,
        "waveform": waveform,                 # raw DC-removed reflex curve (rung 2; gitignored artifact)
        "waveform_digest": wave_digest,
        "waveform_commitment": wave_commitment,
        "verify": verdict,          # {ok, reasons, commitment_ok, schedule_ok, observed_latency_ms, ...}
    }


# --- hardware runner --------------------------------------------------------------------------------

def _iso_date() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _fire_probe_silent(ds, cfg, *, delay_s, reader, reissue=True):  # pragma: no cover - hardware path
    """F-POEP-LIVE-1 (i): SILENT, CONTINUOUS-POLL nonce-scheduled fire — the A-PRE-TELL fix.

    grok round-19 caught the naive fix (sleep -> then dense collect -> fire) leaves a POLL-BURST tell:
    a process watching USB HID poll cadence sees the silence->burst transition ~200-600 ms BEFORE the
    force and pre-arms on it (measured FAR ~0.56 in the harness, not chance). This version removes that
    transition entirely: it polls CONTINUOUSLY at a UNIFORM cadence from t_arm through the fire, keeping
    a ring of the last (randomized) pre_count samples as the pre-window. A poll-cadence watcher therefore
    sees uniform polling from arm-time only (delay-seconds before the force, with the CSPRNG delay still
    hidden) -> no pre-fire burst to key on. The only reliable onset left is the physical force itself
    (A-REACTIVE, explicitly out of P-LIVE-0's claim).

    Returns (probe_ts, pre_reports, post_reports, r2_at_probe, t_arm_ns, t_challenge_ns).
    """
    import asyncio
    from collections import deque
    from bridge.controller.l6_challenge_profiles import l6b_probe_profile
    from bridge.controller.l6_trigger_driver import L6TriggerDriver
    from bridge.vapi_bridge.l6b_desk_session import accel_report_from_snapshot

    accel_scale = float(getattr(reader, "_accel_scale", None) or 8192.0)
    t_arm_ns = time.time_ns()
    arm_mono = time.monotonic()

    # randomized, UNPRINTED ring size in ~[N/2, 3N/2): the pre-window is the last `pre_count` samples
    base = max(1, cfg.pre_samples)
    pre_count = base // 2 + secrets.randbelow(base) + 1
    ring: deque = deque(maxlen=pre_count)

    # CONTINUOUS uniform polling from arm to fire — no silence->burst transition for a watcher to see
    fire_at = arm_mono + max(0.0, delay_s)
    while time.monotonic() < fire_at:
        snap = reader.poll()
        ring.append(accel_report_from_snapshot(snap, accel_scale=accel_scale))
        if cfg.poll_interval_s > 0:
            time.sleep(cfg.poll_interval_s)
    pre_reports = list(ring)

    latest = reader.poll()
    r2_at_probe = int(getattr(latest, "r2_trigger", 0) or 0)

    profile = l6b_probe_profile(cfg.r2_force, mode=cfg.mode)
    probe_ts = time.monotonic()
    t_challenge_ns = time.time_ns()     # exact stimulus onset == the force write
    L6TriggerDriver._sync_write(ds, profile)

    hold_s = cfg.hold_ms / 1000.0
    capture_s = cfg.capture_window_ms / 1000.0
    deadline = time.monotonic() + hold_s + capture_s
    clear_at = time.monotonic() + hold_s
    cleared = False
    driver = L6TriggerDriver()
    post_reports: list[dict] = []
    last_reissue = probe_ts
    while time.monotonic() < deadline:
        now = time.monotonic()
        if not cleared:
            # RE-ISSUE the stimulus through the hold so it's a sustained, perceptible buzz that
            # pydualsense's report-sender thread cannot overwrite (single-shot writes went unfelt).
            # --sharp disables this: a single brief jolt -> clean reflex waveform (needs a reliable actuator).
            if reissue and now - last_reissue >= 0.06:
                L6TriggerDriver._sync_write(ds, profile)
                last_reissue = now
            if now >= clear_at:
                asyncio.run(driver.clear_triggers(ds))
                cleared = True
        snap = reader.poll()
        post_reports.append(accel_report_from_snapshot(snap, accel_scale=accel_scale))
        if cfg.poll_interval_s > 0:
            time.sleep(cfg.poll_interval_s)
    if not cleared:
        asyncio.run(driver.clear_triggers(ds))

    return probe_ts, pre_reports, post_reports, r2_at_probe, t_arm_ns, t_challenge_ns


def run_live_capture(args: argparse.Namespace) -> int:  # pragma: no cover - hardware path
    # Imports that pull in pydualsense / the controller stack are done here so the module (and its
    # pure functions) import cleanly on machines without the hardware toolchain (CI / tests).
    from bridge.vapi_bridge.config import Config
    from bridge.vapi_bridge.l6b_desk_session import (
        DeskProbeConfig,
        analyze_desk_probe,
        persist_desk_probe,
    )
    from bridge.vapi_bridge.cco_l6b_wiring import map_l6b_classification_to_reflex_verdict
    from bridge.vapi_bridge.store import Store
    from controller.dualshock_emulator import DualSenseReader, HAS_DUALSENSE
    from scripts.l6b_desk_reaction_session import (
        _bridge_running,
        _resolve_registered_edge_device_id,
    )

    if not HAS_DUALSENSE:
        print("ERROR: pydualsense not installed -- pip install pydualsense")
        return 1
    if _bridge_running(args.bridge_url):
        print(f"ERROR: Bridge is running at {args.bridge_url}")
        print("  Stop the bridge first to avoid dual-writer contention on the controller.")
        return 1

    reader = DualSenseReader()
    if not reader.connect():
        return 1

    # --sharp: a brief single jolt (no re-issue) so the reaction tail is stimulus-free -> CLEAN reflex
    # waveform for the rung-2 shape analysis. Needs a reliable actuator (post hardware-reset); the long
    # re-issued buzz is the fallback for a jamming trigger, but it corrupts the waveform shape.
    hold_ms_eff = 120 if args.sharp else args.hold_ms
    cfg = DeskProbeConfig(
        r2_force=max(1, min(255, args.force)),
        mode=args.mode,
        hold_ms=max(50, min(2000, hold_ms_eff)),
        pre_samples=args.pre_samples,
        poll_interval_s=args.poll_interval,
        capture_window_ms=args.capture_ms,
        response_threshold_lsb=args.threshold,
    )
    policy_ref = "edge_operator_reflex_v1"
    device_id = (args.device_id or _resolve_registered_edge_device_id()
                 or "unregistered-desk-fallback")
    store = None if args.no_store else Store(args.db or Config().db_path)

    print()
    print("=" * 66)
    print("  POEP-LIVE-1  ·  LIVE NONCE-CHALLENGE CAPTURE (operator-fired)")
    print("=" * 66)
    print(f"  Device ID:  {device_id}")
    print(f"  Policy ref: {policy_ref}   CCO profile: {args.cco_profile_id}")
    print(f"  Challenges: {args.count}   delay window: {args.min_delay}-{args.max_delay}s (independent CSPRNG)")
    print(f"  Actuator:   mode={cfg.mode} force={cfg.r2_force} hold_ms={cfg.hold_ms}")
    print(f"  DB:         {(args.db or Config().db_path) if store else '(dry-run -- not persisting)'}")
    print("-" * 66)
    print("  Hold the controller relaxed with a finger RESTING on R2 (don't press it).")
    print(f"  {args.count} {cfg.mode.upper()} challenges (force {cfg.r2_force}/255, {cfg.hold_ms}ms) fire SILENTLY")
    print("  at random moments over the next ~minute -- NO on-screen cue before each fire.")
    print("  React (a small grip jerk) the instant you feel R2 BUZZ. Results print AFTER.")
    print("  poep_enabled STAYS FALSE -- this is candidate live evidence.")
    print("=" * 66)
    print("  Armed. Hold relaxed, finger on R2...")

    ds = reader.ds
    records: list[dict] = []
    n_ok = 0
    try:
        for idx in range(1, args.count + 1):
            nonce = fresh_nonce()                                     # binding only
            delay_s = csprng_delay_s(min_s=args.min_delay, max_s=args.max_delay)  # (ii) independent CSPRNG
            # SILENT fire: no pre-fire print, randomized unprinted pre-window (F-POEP-LIVE-1 (i))
            (probe_ts, pre_reports, post_reports, r2_at_probe,
             t_arm_ns, t_challenge_ns) = _fire_probe_silent(
                ds, cfg, delay_s=delay_s, reader=reader, reissue=not args.sharp)

            result, diagnostic_json = analyze_desk_probe(pre_reports, post_reports, probe_ts, cfg)
            diag = {}
            try:
                diag = json.loads(diagnostic_json)
            except Exception:  # noqa: BLE001
                diag = {}

            record = build_live_record(
                device_id=device_id,
                nonce=nonce,
                t_challenge_ns=t_challenge_ns,
                latency_ms=result.latency_ms,
                peak_lsb=result.accel_delta_peak,
                precursor_gap_ms=diag.get("precursor_gap_ms"),
                classification=result.classification,
                challenge_index=idx,
                delay_s=delay_s,
                t_arm_ns=t_arm_ns,               # (ii) binds the schedule commitment
                waveform=reflex_curve(pre_reports, post_reports),  # rung 2: raw reflex curve
            )
            record["reflex_verdict"] = map_l6b_classification_to_reflex_verdict(result.classification)
            record["r2_at_probe"] = r2_at_probe
            records.append(record)

            # persist the reflex to the corpus too (same path as the N=52 edge-reflex corpus)
            if store is not None:
                try:
                    persist_desk_probe(
                        store,
                        device_id=device_id,
                        probe_ts=probe_ts,
                        result=result,
                        diagnostic_json=diagnostic_json,
                        protocol="still",
                        player=args.player,
                        r2_at_probe=r2_at_probe,
                        cco_profile_id=args.cco_profile_id,
                        policy_ref_override=policy_ref,
                    )
                except Exception as exc:  # noqa: BLE001
                    print(f"  (persist skipped: {exc})")

            # SILENT during the run — no per-fire output (a post-fire cadence marks challenge
            # boundaries; keeping it silent removes that inter-challenge structure entirely). Results
            # print AFTER the run.
            if record["verify"]["ok"]:
                n_ok += 1
    except KeyboardInterrupt:
        print("\n  (interrupted)")
    finally:
        try:
            from bridge.controller.l6_trigger_driver import L6TriggerDriver
            import asyncio
            asyncio.run(L6TriggerDriver().clear_triggers(ds))
        except Exception:  # noqa: BLE001
            pass
        try:
            if reader.ds:
                reader.ds.close()
        except Exception:  # noqa: BLE001
            pass

    # write the audit artifact (P-LIVE-0 candidate evidence; NOT a flip)
    audit = {
        "schema": "qortroller-poep-live-capture-v1",
        "candidate": True,
        "poep_enabled": False,
        "device_id": device_id,
        "policy_ref": policy_ref,
        "player": args.player,
        "captured_utc": datetime.now(timezone.utc).isoformat(),
        "reaction_band_ms": [80.0, 300.0],
        "silent_fire": True,               # F-POEP-LIVE-1 (i): silent continuous-poll fire (no stdout / poll-burst tell)
        "schedule_bound": True,            # F-POEP-LIVE-1 (ii): independent CSPRNG delay + schedule commitment
        "waveform_captured": True,         # FLIP-A rung 2: raw reflex curve stored per record (run poep_waveform_analyze.py)
        "n_challenges": len(records),
        "n_live_verify_pass": n_ok,
        "claim": "candidate live nonce-challenge evidence on the registered Edge; each PASS = a reflex "
                 "causally bound to a live unpredictable stimulus. Closes replay + pre-scheduled + "
                 "stdout-tell + poll-burst pre-tell macros (silent CONTINUOUS-poll fire + independent-CSPRNG "
                 "delay + schedule commitment; see l9_presence/poep_tell_watcher.py FAR harness). NOT anti-"
                 "reactive-host: a bot watching the HID force command reacts at the true onset (A-REACTIVE) "
                 "and is OUT of claim; that needs firmware force-timestamp / waveform+Stage-A. poep_enabled "
                 "stays False.",
        "records": records,
    }
    out_dir = REPO_ROOT / "audits"
    out_dir.mkdir(exist_ok=True)
    out_path = out_dir / f"poep_live_capture_{args.player}_{_iso_date()}.json"
    out_path.write_text(json.dumps(audit, indent=2), encoding="utf-8")

    print("=" * 66)
    print("  RESULTS (printed after the run — the session itself was silent):")
    for r in records:
        v = r["verify"]
        line = (f"  #{r['challenge_index']:>2}  latency={r['latency_ms']}ms  peak={r['peak_lsb']} LSB  "
                f"class={r['classification']}  -> LIVE-VERIFY {'PASS' if v['ok'] else 'FAIL'}")
        print(line)
        if not v["ok"]:
            print(f"        reasons: {', '.join(v['reasons'])}")
    print("-" * 66)
    print(f"  LIVE-VERIFY PASS: {n_ok}/{len(records)}   (poep_enabled=False -- candidate only)")
    print(f"  Audit: {out_path}")
    print("=" * 66)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--player", "-p", default="P1", help="Player label")
    parser.add_argument("--count", "-n", type=int, default=8, help="Number of live challenges")
    parser.add_argument("--min-delay", type=float, default=DEFAULT_MIN_DELAY_S,
                        dest="min_delay", help="Min challenge delay (s) — independent CSPRNG")
    parser.add_argument("--max-delay", type=float, default=DEFAULT_MAX_DELAY_S,
                        dest="max_delay", help="Max challenge delay (s) — independent CSPRNG")
    # STRONG, clearly-perceptible stimulus so the operator feels it and reacts (supra-perceptual, not the
    # sub-perceptual L6B reflex probe). Crank --force toward 255 if you still can't feel it.
    parser.add_argument("--force", type=int, default=255, help="R2 force 1-255 (255=max — confirmed felt on the rig)")
    parser.add_argument("--mode", choices=("rigid", "pulse"), default="pulse",
                        help="Adaptive trigger mode: pulse=buzzing push (confirmed felt); rigid=hard stiffen")
    parser.add_argument("--hold-ms", type=int, default=1500, dest="hold_ms",
                        help="Stimulus duration (ms) — re-issued ~16Hz so it's a sustained, vigorous buzz")
    parser.add_argument("--sharp", action="store_true",
                        help="Clean-shape mode: a single brief jolt (120ms, NO re-issue) -> clean reflex "
                             "waveform for rung-2 shape analysis. Needs a reliable actuator (post-reset).")
    parser.add_argument("--capture-ms", type=float, default=900.0, dest="capture_ms",
                        help="Post-probe IMU capture window (ms) — long enough for a slow surprise reaction "
                             "(peak up to ~400ms) to still leave a settled tail (grok round-23)")
    parser.add_argument("--pre-samples", type=int, default=50, dest="pre_samples",
                        help="Pre-probe baseline samples")
    parser.add_argument("--poll-interval", type=float, default=0.008, dest="poll_interval",
                        help="IMU poll interval seconds (~8ms = bridge rate)")
    parser.add_argument("--threshold", type=float, default=500.0, help="Response threshold LSB")
    parser.add_argument("--cco-profile-id", default="sony_dualshock_edge_v1", dest="cco_profile_id",
                        help="CCO profile_id tag for l6b_probe_log.cco_profile_id")
    parser.add_argument("--device-id", default=None, dest="device_id",
                        help="Explicit device_id (else auto-resolved from the device birth cert)")
    parser.add_argument("--db", default=None, help="Override bridge DB path")
    parser.add_argument("--no-store", action="store_true", help="Dry-run: do not persist reflexes to DB")
    parser.add_argument("--bridge-url", default="http://localhost:8080", dest="bridge_url",
                        help="Health check URL (must be down)")
    return parser


def main() -> int:  # pragma: no cover
    return run_live_capture(build_parser().parse_args())


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
