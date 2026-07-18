"""CLI for live dual-connect PoEP session (arc poep-gameplay-live, L1+L2).

  start-live  --player Pn [--device-id ...]
  tick        [--bridge-url ...]
  challenge   [--kind GO|NO_GO] [--amplitude N] [--i-am-playing] [--fire mock|real]
  stop-live

Mock fires: real_hardware=False -> cannot mint presence_session_candidate_ok.
Real force: POEP_LIVE_FIRE_ENABLED=1 + L3 pad path. poep_enabled never flipped.
"""
from __future__ import annotations

import argparse
import json
import secrets
import sys
import time
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from l9_presence.poep_gameplay_live import (  # noqa: E402
    FireResult,
    ImuWindow,
    challenge_live,
    clamp_amplitude,
    make_real_hid_fire,
    poll_bridge_activity,
    real_hid_fire_available,
    start_live_session,
    summarize_live_session,
)
from l9_presence.poep_gameplay_session import (  # noqa: E402
    ChallengeKind,
    LOW_AMPLITUDE_FORCE_DEFAULT,
    session_from_dict,
    session_to_dict,
)

DEV_DEFAULT = "581a836c98b3a1b6c0f598bfca88e6a3cc3bd7c34591b506692cb40ddf66a9f8"
STATE_DIR = Path("audits")
STATE_FILE = STATE_DIR / "poep_gameplay_live_active.json"
SEAL_FILE = STATE_DIR / "poep_gameplay_live_active.seal.json"


def _bridge_fetcher(url: str):
    def fetch():
        try:
            with urllib.request.urlopen(url, timeout=5) as r:
                return json.loads(r.read().decode())
        except Exception:
            return None

    return fetch


def _load():
    state = json.loads(STATE_FILE.read_text(encoding="utf-8"))
    sealrec = json.loads(SEAL_FILE.read_text(encoding="utf-8"))
    return session_from_dict(state), sealrec["seal"], sealrec["process_nonce"]


def _save(session, seal=None, process_nonce=None):
    STATE_DIR.mkdir(exist_ok=True)
    STATE_FILE.write_text(
        json.dumps(session_to_dict(session), indent=2) + "\n", encoding="utf-8"
    )
    if seal is not None:
        SEAL_FILE.write_text(
            json.dumps({"seal": seal, "process_nonce": process_nonce}, indent=2)
            + "\n",
            encoding="utf-8",
        )


def cmd_start_live(args) -> int:
    if STATE_FILE.exists():
        print("REFUSE: active session file exists; stop-live first")
        return 2
    t0 = time.time_ns()
    process_nonce = secrets.token_hex(16)
    session, seal = start_live_session(
        device_id=args.device_id,
        player_label=args.player,
        t_start_ns=t0,
        process_nonce=process_nonce,
    )
    _save(session, seal=seal, process_nonce=process_nonce)
    print(
        f"started live session {session.session_id} "
        f"(mode=live, activity_source=bridge, sealed)"
    )
    print(
        "topology: USB->PC challenge+IMU, BT->console play. "
        "poep_enabled=False. Not a flip."
    )
    return 0


def cmd_tick(args) -> int:
    session, _seal, _nonce = _load()
    state = poll_bridge_activity(session, _bridge_fetcher(args.bridge_url))
    _save(session)
    print(f"activity tick: {state.value} (bridge-attested path)")
    return 0


def cmd_challenge(args) -> int:
    session, seal, process_nonce = _load()
    if not session.challenges and not args.i_am_playing:
        print(
            "REFUSE: first challenge requires --i-am-playing "
            "(operator ready gate)."
        )
        print(
            f"Would fire: kind={args.kind} "
            f"amplitude={clamp_amplitude(args.amplitude)} "
            f"on device {session.device_id[:8]}..."
        )
        return 2
    pcc = _bridge_fetcher(args.bridge_url)()
    if args.fire == "real":
        if not real_hid_fire_available():
            print(
                "REFUSE: --fire real requires POEP_LIVE_FIRE_ENABLED=1 "
                "(rig only, never CI)"
            )
            return 2
        fire_fn = make_real_hid_fire()
    else:

        def fire_fn(amp, n):
            return FireResult(
                fired=True,
                real_hardware=False,
                t_fire_ns=time.time_ns(),
                amplitude=amp,
            )

    # Mock IMU: in-band pass for GO plumbing; NO_GO quiet peak
    def imu_fn(t_fire):
        if args.kind == "NO_GO":
            return ImuWindow(
                t_response_ns=t_fire + 1,
                latency_ms=0.0,
                peak_lsb=50.0,
                precursor_gap_ms=0.0,
            )
        if t_fire <= 0:
            return None
        return ImuWindow(
            t_response_ns=t_fire + int(250e6),
            latency_ms=250.0,
            peak_lsb=2500.0,
            precursor_gap_ms=5.0,
        )

    out = challenge_live(
        session,
        seal=seal,
        process_nonce=process_nonce,
        nonce=secrets.token_hex(8),
        kind=ChallengeKind(args.kind),
        fire_fn=fire_fn,
        imu_capture_fn=imu_fn,
        pcc_sample=pcc
        if pcc is not None
        else {"capture_state": "NOMINAL", "host_state": "EXCLUSIVE_USB"},
        amplitude=args.amplitude,
    )
    # When bridge is down, pcc_sample None would refuse — for mock local smoke allow override
    if not out.get("issued") and out.get("refused") == "refused_pcc" and args.allow_offline_pcc:
        out = challenge_live(
            session,
            seal=seal,
            process_nonce=process_nonce,
            nonce=secrets.token_hex(8),
            kind=ChallengeKind(args.kind),
            fire_fn=fire_fn,
            imu_capture_fn=imu_fn,
            pcc_sample={
                "capture_state": "NOMINAL",
                "host_state": "EXCLUSIVE_USB",
            },
            amplitude=args.amplitude,
        )
    _save(session)
    print(json.dumps(out, indent=2, sort_keys=True))
    return 0 if out.get("issued") else 3


def cmd_stop_live(args) -> int:
    session, seal, process_nonce = _load()
    session.t_stop_ns = time.time_ns()
    summary = summarize_live_session(
        session, seal=seal, process_nonce=process_nonce
    )
    out = STATE_DIR / (
        f"poep_gameplay_live_{session.player_label}_{session.t_stop_ns}.json"
    )
    out.write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    STATE_FILE.unlink(missing_ok=True)
    SEAL_FILE.unlink(missing_ok=True)
    print(f"summary -> {out}")
    print(
        f"presence_session_candidate_ok={summary['presence_session_candidate_ok']} "
        f"dry_plumbing_ok={summary['dry_plumbing_ok']} "
        f"live_seal_valid={summary['live_seal_valid']} "
        f"poep_enabled=False"
    )
    return 0


def main() -> int:
    p = argparse.ArgumentParser(
        description="live dual-connect PoEP session (L1+L2)"
    )
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("start-live")
    s.add_argument("--player", required=True)
    s.add_argument("--device-id", default=DEV_DEFAULT)
    t = sub.add_parser("tick")
    t.add_argument(
        "--bridge-url",
        default="http://127.0.0.1:8000/bridge/capture-health",
    )
    c = sub.add_parser("challenge")
    c.add_argument("--kind", choices=["GO", "NO_GO"], default="GO")
    c.add_argument("--amplitude", type=int, default=LOW_AMPLITUDE_FORCE_DEFAULT)
    c.add_argument("--fire", choices=["mock", "real"], default="mock")
    c.add_argument(
        "--bridge-url",
        default="http://127.0.0.1:8000/bridge/capture-health",
    )
    c.add_argument(
        "--i-am-playing",
        action="store_true",
        help="operator ready-gate for FIRST challenge of a session",
    )
    c.add_argument(
        "--allow-offline-pcc",
        action="store_true",
        help="plumbing only: use NOMINAL PCC when bridge unreachable",
    )
    sub.add_parser("stop-live")
    args = p.parse_args()
    return {
        "start-live": cmd_start_live,
        "tick": cmd_tick,
        "challenge": cmd_challenge,
        "stop-live": cmd_stop_live,
    }[args.cmd](args)


if __name__ == "__main__":
    raise SystemExit(main())
