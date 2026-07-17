"""GP-3 — gameplay-embedded PoEP session CLI (A2A-POEP-GAMEPLAY round-01, dry-first).

Operator-facing session shell for sparse, activity-gated, in-play presence challenges. DRY-FIRST:
`challenge-dry` injects a SYNTHETIC outcome (no HID) but runs the REAL verify_live_response + catch
scoring, so the plumbing is genuine and a dry run can NEVER be mistaken for live (`live_hardware=False`
everywhere). A `--live` path is a documented stub (LIVE_TODO) — real HID fire is a later increment and
requires the bridge UP + dual-connect topology.

    python scripts/poep_gameplay_session.py start --player P1 --device-id <hex>
    python scripts/poep_gameplay_session.py tick  --activity-json '{"gameplay_context":"ACTIVE_GAMEPLAY"}'
    python scripts/poep_gameplay_session.py challenge-dry --kind GO --outcome pass
    python scripts/poep_gameplay_session.py stop  --out audits/poep_gameplay_session_<label>.json

`poep_enabled` / `L6B` / `L6_CHALLENGES` stay False. No HID, no chain, no spend in this CLI.
"""
from __future__ import annotations

import argparse
import json
import secrets
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from l9_presence.poep_gameplay_session import (  # noqa: E402
    ActivityState,
    ChallengeKind,
    LOW_AMPLITUDE_FORCE_DEFAULT,
    LOW_AMPLITUDE_FORCE_MAX,
    PlaySession,
    SessionChallengeEvent,
    now_ns,
    session_from_dict,
    session_to_dict,
    summarize_session,
)
from l9_presence.poep_live_verify import (  # noqa: E402
    ChallengeResponse,
    LiveChallenge,
    poep_commitment,
    response_feature_digest,
    verify_live_response,
)
from l9_presence.poep_catch_trials import score_trial  # noqa: E402

_ACTIVE = ROOT / "audits" / ".poep_gameplay_session_active.json"


def _load() -> PlaySession:
    if not _ACTIVE.exists():
        print(f"ERROR: no active session ({_ACTIVE}). Run `start` first.", file=sys.stderr)
        sys.exit(2)
    return session_from_dict(json.loads(_ACTIVE.read_text(encoding="utf-8")))


def _save(session: PlaySession) -> None:
    _ACTIVE.parent.mkdir(parents=True, exist_ok=True)
    _ACTIVE.write_text(json.dumps(session_to_dict(session), indent=2), encoding="utf-8")


def _synthetic_challenge(kind: ChallengeKind, outcome: str, device_id: str, amplitude: int) -> SessionChallengeEvent:
    """Build a challenge by running the REAL verify/catch primitives over INJECTED values.

    Dry only: live_hardware=False. `outcome` in {pass, fail}. For GO/pass we synthesize an in-band,
    correctly-committed response (verify ok); for GO/fail an out-of-band/mismatched one. For NO_GO we
    model the honest-human 'no response' (pass) vs a false-alarm peak (fail) and score the catch trial.
    """
    nonce = secrets.token_hex(16)
    t_ch = now_ns()

    if kind == ChallengeKind.GO:
        if outcome == "pass":
            latency_ms, peak_lsb, precursor = 250.0, 3000.0, 5.0
            t_resp = t_ch + int(latency_ms * 1e6)
            fd = response_feature_digest(latency_ms, peak_lsb, precursor)
            commitment = poep_commitment(device_id=device_id, nonce=nonce, feature_digest=fd, ts_ns=t_resp)
        else:  # fail: out-of-band latency + a deliberately wrong commitment
            latency_ms, peak_lsb, precursor = 20.0, 3000.0, 5.0  # 20ms < reaction band -> fail
            t_resp = t_ch + int(latency_ms * 1e6)
            commitment = "00" * 32
        resp = ChallengeResponse(t_response_ns=t_resp, latency_ms=latency_ms, peak_lsb=peak_lsb,
                                 precursor_gap_ms=precursor, nonce=nonce, commitment=commitment)
        ch = LiveChallenge(device_id=device_id, nonce=nonce, t_challenge_ns=t_ch)
        verify = verify_live_response(ch, resp)
        return SessionChallengeEvent(kind=kind, ts_ns=t_ch, nonce=nonce, verify=verify,
                                     amplitude_force=amplitude, live_hardware=False)

    # NO_GO: same schedule, NO force write. Honest human = no peak (clean); fail = a twitch FA peak.
    peak = 100.0 if outcome == "pass" else 1200.0  # >=1000 floor = false alarm
    catch = score_trial("NO_GO", peak_lsb=peak, latency_ms=None, live_verify_ok=False)
    verify = {"ok": False, "poep_enabled": False, "is_presence_verdict": False,
              "note": "NO_GO catch trial — no force written; a relaxed human should not respond"}
    return SessionChallengeEvent(
        kind=kind, ts_ns=t_ch, nonce=nonce, verify=verify,
        catch={"kind": catch.kind, "peak_lsb": catch.peak_lsb, "human_ok": catch.human_ok,
               "reason": catch.reason, "always_fire_caught": catch.always_fire_caught},
        amplitude_force=0, live_hardware=False)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_start = sub.add_parser("start", help="begin a play session")
    p_start.add_argument("--player", required=True)
    p_start.add_argument("--device-id", required=True)
    p_start.add_argument("--session-id", default=None, help="default: derived from label+time")

    p_tick = sub.add_parser("tick", help="inject one activity sample")
    p_tick.add_argument("--activity-json", required=True, help="e.g. '{\"gameplay_context\":\"ACTIVE_GAMEPLAY\"}'")

    p_ch = sub.add_parser("challenge-dry", help="schedule + record a SYNTHETIC (no-HID) challenge (activity-gated)")
    p_ch.add_argument("--kind", choices=["GO", "NO_GO"], default="GO")
    p_ch.add_argument("--outcome", choices=["pass", "fail"], default="pass")
    p_ch.add_argument("--amplitude", type=int, default=LOW_AMPLITUDE_FORCE_DEFAULT)
    p_ch.add_argument("--ignore-gate", action="store_true",
                      help="bypass the activity gate (loud plumbing-only; a challenge with no active play)")

    sub.add_parser("challenge-live", help="LIVE_TODO — not wired in this increment")

    p_stop = sub.add_parser("stop", help="finalize + write the session summary artifact")
    p_stop.add_argument("--out", default=None)

    args = ap.parse_args()

    if args.cmd == "start":
        sid = args.session_id or f"poep_gp_{args.player}_{now_ns()}"
        # This CLI is DRY-ONLY plumbing: mode='dry', activity_source='cli_inject'. Neither can be
        # flipped from the CLI — a presence CANDIDATE needs mode='live' + bridge-attested activity,
        # which only the (unwired) live path can set (round-04 F-GP-2/4).
        session = PlaySession(session_id=sid, device_id=args.device_id,
                              player_label=args.player, t_start_ns=now_ns(),
                              mode="dry", activity_source="cli_inject")
        _save(session)
        print(f"[START] session_id={sid} device_id={args.device_id} player={args.player} mode=dry activity_source=cli_inject")
        print(f"  state -> {_ACTIVE}")
        return

    if args.cmd == "tick":
        session = _load()
        try:
            sample = json.loads(args.activity_json)
        except json.JSONDecodeError as exc:
            print(f"ERROR: --activity-json not valid JSON: {exc}", file=sys.stderr)
            sys.exit(2)
        st = session.record_activity(sample)
        _save(session)
        print(f"[TICK] activity={st.value}  (samples={len(session.activity_samples)})")
        return

    if args.cmd == "challenge-dry":
        session = _load()
        # round-04 F-GP-1: HONOR THE ACTIVITY GATE in the operator path, not just the pure scheduler.
        # A challenge fires only when the LATEST recorded activity is ACTIVE_GAMEPLAY (fail-closed on
        # MENU/UNKNOWN/none) — unless --ignore-gate is passed, which is loud plumbing-only.
        latest = session.activity_samples[-1] if session.activity_samples else None
        if latest != ActivityState.ACTIVE_GAMEPLAY and not args.ignore_gate:
            print(f"REFUSED: latest activity is {latest.value if latest else 'none'}, not ACTIVE_GAMEPLAY. "
                  f"The activity gate fires challenges only during active play — `tick` an "
                  f"ACTIVE_GAMEPLAY sample first, or pass --ignore-gate for pure plumbing.",
                  file=sys.stderr)
            sys.exit(3)
        amp = max(0, min(int(args.amplitude), LOW_AMPLITUDE_FORCE_MAX))  # never exceed the gameplay ceiling
        if amp != args.amplitude:
            print(f"[amplitude clamped {args.amplitude} -> {amp} (gameplay ceiling {LOW_AMPLITUDE_FORCE_MAX}, never 255)]")
        ev = _synthetic_challenge(ChallengeKind(args.kind), args.outcome, session.device_id, amp)
        session.record_challenge(ev)
        _save(session)
        gate = "GATED(active)" if not args.ignore_gate else "UNGATED(--ignore-gate)"
        print(f"[CHALLENGE-DRY] {gate} kind={ev.kind.value} outcome={args.outcome} live_hardware=False "
              f"verify_ok={ev.verify.get('ok')} amplitude={ev.amplitude_force}")
        return

    if args.cmd == "challenge-live":
        print("LIVE_TODO: real HID challenge is not wired in this increment. It requires the bridge UP "
              "+ dual-connect topology (USB->PC challenge, BT->console play), low amplitude, and reuse "
              "of the live fire primitive. Ship dry first; the live hook is a later PR. Not fired.",
              file=sys.stderr)
        sys.exit(3)

    if args.cmd == "stop":
        session = _load()
        session.t_stop_ns = now_ns()
        summary = summarize_session(session)
        out = Path(args.out) if args.out else (ROOT / "audits" / f"poep_gameplay_session_{session.player_label}_{session.t_start_ns}.json")
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(summary, indent=2), encoding="utf-8")
        _ACTIVE.unlink(missing_ok=True)
        print(f"[STOP] mode={summary['mode']} activity_source={summary['activity_source']}")
        print(f"  dry_plumbing_ok={summary['dry_plumbing_ok']} "
              f"(go_pass={summary['n_go_verify_pass']}/{summary['n_go_issued']}, "
              f"min={summary['min_go_verify_pass']}; active_frac={summary['gameplay_active_fraction']})")
        print(f"  presence_session_candidate_ok={summary['presence_session_candidate_ok']} "
              f"(needs live+trusted — DRY sessions are always False)")
        print(f"  live_hardware={summary['live_hardware']}  poep_enabled={summary['poep_enabled']}  "
              f"is_presence_verdict={summary['is_presence_verdict']}")
        print(f"  summary -> {out}")
        return


if __name__ == "__main__":
    main()
