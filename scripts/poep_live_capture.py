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
  - P-LIVE-0 does NOT defeat a REACTIVE bot (one that detects the live stimulus onset and reacts in-band).
    The console still prints a baseline tell before firing; a reactive adversary is explicitly out of
    scope until waveform-shape + Stage-A land. The claim is "must react to a live unpredictable stimulus",
    a much stronger bar than offline scoring, but not yet "embodied human".

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
    verify_live_response,
)

# --- unpredictable-timing scheduler (pure, testable) ------------------------------------------------

DEFAULT_MIN_DELAY_S = 3.0
DEFAULT_MAX_DELAY_S = 12.0


def fresh_nonce() -> str:
    """A fresh, cryptographically-random per-challenge nonce (never revealed until the challenge)."""
    return secrets.token_hex(16)


def nonce_derived_delay_s(nonce: str, *, min_s: float = DEFAULT_MIN_DELAY_S,
                          max_s: float = DEFAULT_MAX_DELAY_S) -> float:
    """Derive the challenge delay from the fresh secret nonce -> unpredictable while the nonce is secret.

    The load-bearing property is UNPREDICTABILITY: the nonce is generated fresh and unrevealed until the
    stimulus fires, so neither the operator nor a pre-scheduled macro can anticipate the onset (the
    property P-LIVE-0 needs against replay + pre-schedule).

    NOT provable by the auditor (F-POEP-LIVE-1, grok round-17): the P-LIVE-0 commitment binds
    (device_id, nonce, feature_digest, t_response) but NOT delay_s / arm-time, so `verify_live_response`
    does NOT prove the fire matched this nonce-derived schedule -- it only checks the post-hoc latency
    against the recorded t_challenge. Deriving delay from the nonce also puts schedule + binding entropy
    on ONE secret (bit double-duty). The hygiene upgrade (deferred to the fix arc) is an INDEPENDENT
    CSPRNG for the delay + the nonce for binding only, optionally committing H(nonce||delay||t_arm).
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
) -> dict:
    """Build the P-LIVE-0 record for one challenge and run the fail-closed verify auditor.

    A no-response (no clean reflex peak) -> latency_ms None/<=0 -> t_response == t_challenge -> the
    auditor fails it honestly (response_not_after_challenge + reaction-band), never a spurious pass.
    """
    lat = float(latency_ms) if (latency_ms is not None and latency_ms > 0.0) else 0.0
    precursor = float(precursor_gap_ms) if precursor_gap_ms is not None else 0.0
    # anchor the response time to the challenge via the measured reflex latency
    t_response_ns = t_challenge_ns + int(round(lat * 1e6)) if lat > 0.0 else t_challenge_ns

    feature_digest = response_feature_digest(lat, float(peak_lsb), precursor)
    commitment = poep_commitment(
        device_id=device_id, nonce=nonce, feature_digest=feature_digest, ts_ns=t_response_ns,
    )
    ch = LiveChallenge(device_id=device_id, nonce=nonce, t_challenge_ns=t_challenge_ns)
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
        "t_challenge_ns": t_challenge_ns,
        "t_response_ns": t_response_ns,
        "latency_ms": round(lat, 3) if lat > 0.0 else None,
        "peak_lsb": round(float(peak_lsb), 1),
        "precursor_gap_ms": round(precursor, 3),
        "classification": classification,
        "feature_digest": feature_digest,
        "commitment": commitment,
        "verify": verdict,          # {ok, reasons, commitment_ok, observed_latency_ms, poep_enabled:False, ...}
    }


# --- hardware runner --------------------------------------------------------------------------------

def _iso_date() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


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
        _fire_probe_sync,
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

    cfg = DeskProbeConfig(
        r2_force=max(1, min(255, args.force)),
        mode=args.mode,
        hold_ms=max(50, min(2000, args.hold_ms)),
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
    print(f"  Challenges: {args.count}   delay window: {args.min_delay}-{args.max_delay}s (nonce-derived)")
    print(f"  Actuator:   mode={cfg.mode} force={cfg.r2_force} hold_ms={cfg.hold_ms}")
    print(f"  DB:         {(args.db or Config().db_path) if store else '(dry-run -- not persisting)'}")
    print("-" * 66)
    print("  Hold the controller in a NORMAL, RELAXED grip. Do NOT press R2.")
    print("  A resistance challenge will fire at a RANDOM moment you cannot")
    print("  anticipate. React naturally when you feel it. Do NOT press ENTER.")
    print("  poep_enabled STAYS FALSE -- this is candidate live evidence.")
    print("=" * 66)
    print()

    ds = reader.ds
    records: list[dict] = []
    n_ok = 0
    try:
        for idx in range(1, args.count + 1):
            nonce = fresh_nonce()
            delay_s = nonce_derived_delay_s(nonce, min_s=args.min_delay, max_s=args.max_delay)
            print(f"--- Challenge {idx}/{args.count} --- (arming; hold relaxed)")
            # unpredictable pre-delay: the operator does not know when the stimulus fires
            time.sleep(delay_s)

            mono0 = time.monotonic()
            wall0 = time.time_ns()
            probe_ts, pre_reports, post_reports, r2_at_probe = _fire_probe_sync(
                ds, force=cfg.r2_force, mode=cfg.mode, hold_ms=cfg.hold_ms, reader=reader, cfg=cfg,
            )
            # exact wall-clock stimulus onset (probe_ts is monotonic at the fire instant)
            t_challenge_ns = wall0 + int(round((probe_ts - mono0) * 1e9))

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

            v = record["verify"]
            status = "PASS" if v["ok"] else "FAIL"
            if v["ok"]:
                n_ok += 1
            print(f"  latency={record['latency_ms']}ms peak={record['peak_lsb']} LSB "
                  f"class={result.classification} -> LIVE-VERIFY {status}")
            if not v["ok"]:
                print(f"    reasons: {', '.join(v['reasons'])}")
            print(f"    nonce={nonce[:12]}...  commitment={record['commitment'][:16]}...")
            print()
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
        "schema": "qortroller-poep-live-capture-v0",
        "candidate": True,
        "poep_enabled": False,
        "device_id": device_id,
        "policy_ref": policy_ref,
        "player": args.player,
        "captured_utc": datetime.now(timezone.utc).isoformat(),
        "reaction_band_ms": [80.0, 300.0],
        "n_challenges": len(records),
        "n_live_verify_pass": n_ok,
        "claim": "candidate live nonce-challenge evidence on the registered Edge; each PASS = a reflex "
                 "causally bound to a live unpredictable stimulus (defeats replay + pre-scheduled macro "
                 "by construction). NOT yet anti-reactive-bot; poep_enabled stays False.",
        "records": records,
    }
    out_dir = REPO_ROOT / "audits"
    out_dir.mkdir(exist_ok=True)
    out_path = out_dir / f"poep_live_capture_{args.player}_{_iso_date()}.json"
    out_path.write_text(json.dumps(audit, indent=2), encoding="utf-8")

    print("=" * 66)
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
                        dest="min_delay", help="Min nonce-derived challenge delay (s)")
    parser.add_argument("--max-delay", type=float, default=DEFAULT_MAX_DELAY_S,
                        dest="max_delay", help="Max nonce-derived challenge delay (s)")
    # edge-reflex capture defaults MIRROR the corpus-capture path byte-for-byte
    parser.add_argument("--force", type=int, default=128, help="R2 force 1-255")
    parser.add_argument("--mode", choices=("rigid", "pulse"), default="rigid", help="Adaptive trigger mode")
    parser.add_argument("--hold-ms", type=int, default=200, dest="hold_ms", help="Hold resistance (ms)")
    parser.add_argument("--capture-ms", type=float, default=400.0, dest="capture_ms",
                        help="Post-probe IMU capture window (ms)")
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
