"""POEP session-identity-attach CLI - one command: live session -> summary -> ioID identity attach.

DRY-FIRST (default): honest injected fire (`real_hardware=False`) -> the sealed model forces the
presence candidate to False -> verdict IDENTITY_ONLY. Proves the whole attach pipeline end-to-end
WITHOUT a rig. `--live` is GATED on POEP_LIVE_FIRE_ENABLED=1 and uses the operator rig fire path; it
stays IDENTITY_ONLY (honest) until the L3 real fire+IMU adapter exists - it NEVER synthesizes
`real_hardware=True`.

    python scripts/poep_session_identity_attach.py --dry            # -> IDENTITY_ONLY (no rig)
    POEP_LIVE_FIRE_ENABLED=1 python scripts/poep_session_identity_attach.py --live   # operator rig

`poep_enabled` / `L6B` / `L6_CHALLENGES` stay False. Identity/provenance lane only - ZERO liveness
content added. The DID subject is the gamer wallet, never the silicon. Zero spend, no chain write.
"""
from __future__ import annotations

import argparse
import json
import secrets
import sys
import time
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from l9_presence.poep_gameplay_live import (  # noqa: E402
    FireResult,
    ImuWindow,
    clamp_amplitude,
)
from l9_presence.poep_gameplay_session import ChallengeKind  # noqa: E402
from l9_presence.poep_session_identity_run import run_session_identity_attach  # noqa: E402

# ── live ioID ceremony constants (91449f41) - fixture defaults, passed explicitly ─────────────
_DEV = "581a836c98b3a1b6c0f598bfca88e6a3cc3bd7c34591b506692cb40ddf66a9f8"
_OWNER_DID = "did:io:0x0cf36db57fc4680bcdfc65d1aff96993c57a4692"
_TBA = "0xFCee237789FA91a141781aFB574ADAbcA2660e7b"
_REG_TX = "0xab4d041b8ffeab257178e04dddd69e1033912766842803e0386c3640468e9b1f"
_VMDR_PKH = "0x235a2c04de3319661dd637ad296e37b59c23b0fe1f78509965f77bc5d9247802"
_NFT = "0x93b77eB6D8F9e12A801aC06b81bb6E37b7dcdE55"


# ── DRY injected doubles (honest: real_hardware=False -> candidate can never be True) ──────────
def _dry_fire(amplitude: int, nonce: str) -> FireResult:
    return FireResult(
        fired=True, real_hardware=False, t_fire_ns=time.time_ns(),
        amplitude=clamp_amplitude(amplitude),
    )


def _dry_imu(t_fire_ns: int) -> ImuWindow:
    # In-band response so the GO plumbing verifies (dry_plumbing_ok can be True); presence stays False.
    return ImuWindow(
        t_response_ns=int(t_fire_ns) + 250_000_000, latency_ms=250.0,
        peak_lsb=3000.0, precursor_gap_ms=5.0,
    )


def _dry_activity() -> dict:
    return {"gameplay_context": "ACTIVE_GAMEPLAY"}


def _dry_pcc() -> dict:
    return {"capture_state": "NOMINAL", "host_state": "EXCLUSIVE_USB"}


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--dry", action="store_true", default=True,
                      help="injected fire, no rig (default) -> IDENTITY_ONLY")
    mode.add_argument("--live", action="store_true",
                      help="operator rig path; requires POEP_LIVE_FIRE_ENABLED=1")
    ap.add_argument("--player", default="P1")
    ap.add_argument("--device-id", default=_DEV)
    ap.add_argument("--owner-did", default=_OWNER_DID)
    ap.add_argument("--ioid-token-id", type=int, default=498)
    ap.add_argument("--tba", default=_TBA)
    ap.add_argument("--reg-tx", default=_REG_TX)
    ap.add_argument("--vmdr-pubkey-hash", default=_VMDR_PKH)
    ap.add_argument("--controller-nft", default=_NFT)
    ap.add_argument("--controller-nft-token-id", type=int, default=1)
    ap.add_argument("--challenges", type=int, default=2, help="GO challenges to run (>= MIN_GO_ISSUED)")
    ap.add_argument("--no-custody-seal", action="store_true", help="omit the seal v0.2 custody sidecar")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    live = bool(args.live)

    if live:
        from l9_presence.poep_gameplay_live import make_real_hid_fire, real_hid_fire_available
        if not real_hid_fire_available():
            print("REFUSED: --live requires POEP_LIVE_FIRE_ENABLED=1 on the operator rig (never CI).",
                  file=sys.stderr)
            return 2
        # Operator rig fire path. Honest today: the real fire is an L3 stub that returns fired=False
        # until the pad-write + IMU adapter lands, so --live yields IDENTITY_ONLY - it NEVER fabricates.
        fire_fn = make_real_hid_fire()
        imu_fn = lambda _t: None  # noqa: E731  no real IMU adapter yet; GO refuses on fired=False first
        print("[live] real fire path is gated + honest: expect IDENTITY_ONLY until the L3 "
              "fire+IMU adapter exists (no real_hardware synthesized).")
    else:
        fire_fn = _dry_fire
        imu_fn = _dry_imu

    plan = [(ChallengeKind.GO, secrets.token_hex(16)) for _ in range(max(1, args.challenges))]

    artifact = run_session_identity_attach(
        device_id=args.device_id,
        player_label=args.player,
        t_start_ns=time.time_ns(),
        process_nonce=secrets.token_hex(16),
        challenge_plan=plan,
        fire_fn=fire_fn,
        imu_capture_fn=imu_fn,
        activity_fetcher=_dry_activity,   # dry activity source (bridge-attested activity is the rig path)
        pcc_sampler=_dry_pcc,
        ioid_identity={
            "owner_did": args.owner_did,
            "ioid_token_id": args.ioid_token_id,
            "tba_address": args.tba,
            "registration_tx": args.reg_tx,
            "vmdr_pubkey_hash": args.vmdr_pubkey_hash,
            "controller_nft": args.controller_nft,
            "controller_nft_token_id": args.controller_nft_token_id,
        },
        include_custody_seal=not args.no_custody_seal,
    )

    ps = artifact["presence_summary"]
    sid = ps.get("session_id", "unknown")
    out = Path(args.out) if args.out else ROOT / "audits" / f"poep_session_identity_attach_{sid}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(artifact, indent=2), encoding="utf-8")

    verdict = artifact["controller_presence"]["verdict"]
    print(f"verdict            : {verdict}")
    print(f"presence_candidate : {ps.get('presence_session_candidate_ok')}  "
          f"(dry_plumbing_ok={ps.get('dry_plumbing_ok')}, live_hardware={ps.get('live_hardware')})")
    print(f"identity_bound     : {artifact['controller_presence']['identity_bound']}  "
          f"(owner_did={artifact['identity']['owner_did']})")
    print(f"did_subject        : {artifact['identity']['did_subject']}  "
          f"(did_names_silicon={artifact['identity']['did_names_silicon']})")
    print(f"artifact           : {out}")

    # IDENTITY_ONLY and SYNCHRONIZED_CONTROLLER are BOTH valid successes (grok r02 FIX #7); only a
    # structural failure (UNVERIFIABLE / mismatch) is nonzero.
    if verdict in ("IDENTITY_ONLY", "SYNCHRONIZED_CONTROLLER", "PRESENCE_ONLY", "PARTIAL"):
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
