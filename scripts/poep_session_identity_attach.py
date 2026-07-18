"""POEP session-identity-attach CLI - one command: live session -> summary -> ioID identity attach.

DRY-FIRST (default): honest injected fire (`real_hardware=False`) -> the sealed model forces the
presence candidate to False -> verdict IDENTITY_ONLY. Proves the whole attach pipeline end-to-end
WITHOUT a rig. `--live` (GATED on POEP_LIVE_FIRE_ENABLED=1, never CI) is served by the RUNNING
bridge's single-HID ring: fire+capture via POST /operator/poep/fire (BridgeFireCaptureAdapter) and
activity/PCC from the SAME bridge (GET /bridge/capture-health) - one reader attests everything, so
`SYNCHRONIZED_CONTROLLER` is honestly reachable iff the bridge's gates (l6b_enabled - operator
decision - + POEP_LIVE_FIRE_ENABLED) are open AND real fires verify. Every refusal fail-closes to an
honest IDENTITY_ONLY; the CLI NEVER synthesizes `real_hardware=True`, activity, or PCC.

    python scripts/poep_session_identity_attach.py --dry            # -> IDENTITY_ONLY (no rig)
    POEP_LIVE_FIRE_ENABLED=1 python scripts/poep_session_identity_attach.py --live   # operator rig

`poep_enabled` / `L6B` / `L6_CHALLENGES` stay False. Identity/provenance lane only - ZERO liveness
content added. The DID subject is the gamer wallet, never the silicon. Zero spend, no chain write.
"""
from __future__ import annotations

import argparse
import json
import os
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


# ── LIVE attestation fetchers (hidring): activity/PCC from the REAL bridge, never fabricated ──
def _make_bridge_health_fetcher(bridge_url: str, api_key: str, kind: str):
    """GET /bridge/capture-health -> activity dict ({'gameplay_context': ...}) or PCC dict.

    Fail-closed: bridge unreachable / malformed -> empty/None -> classify_activity yields UNKNOWN and
    pcc_allows_challenge yields False -> the sealed challenge_live REFUSES. The live path never
    fabricates activity or PCC - the bridge that fires is the bridge that attests (one reader).
    """
    import urllib.request

    # Measured live 2026-07-18: capture-health lives on the operator sub-app (mounted at /operator).
    url = bridge_url.rstrip("/") + "/operator/bridge/capture-health"

    def _fetch():
        try:
            req = urllib.request.Request(url)
            if api_key:
                req.add_header("x-api-key", api_key)
            with urllib.request.urlopen(req, timeout=3.0) as r:  # noqa: S310 - operator-local bridge
                data = json.loads(r.read().decode())
        except Exception:
            return {} if kind == "activity" else None
        if not isinstance(data, dict):
            return {} if kind == "activity" else None
        if kind == "activity":
            # ATTEST-FEEDS (F-RIG27-2, grok attestfeeds-r02 B): the LIVE bridge-attested fraction is
            # the honest activity path (the adjudication-time gameplay_context never stamps in a
            # campaign config, and a stale/null ctx must never shadow live truth — so it is NOT
            # passed here). Omit-when-cold: window_n < 3 -> {} -> the sealed classifier yields
            # UNKNOWN -> challenge_live refuses (fail-closed). fraction==0 with a filled window ->
            # MENU; > 0 -> ACTIVE_GAMEPLAY — the sealed grammar decides, the CLI never invents.
            n = data.get("live_activity_window_n")
            v = data.get("live_trigger_active_fraction")
            if isinstance(n, int) and n >= 3 and isinstance(v, (int, float)):
                return {"trigger_active_fraction": float(v)}
            return {}
        return {"capture_state": data.get("capture_state"), "host_state": data.get("host_state")}

    return _fetch


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
    ap.add_argument("--bridge-url", default="http://localhost:8080", dest="bridge_url",
                    help="running bridge base URL (live path: fire endpoint + capture-health attestation)")
    ap.add_argument("--api-key", default=os.environ.get("OPERATOR_API_KEY", ""), dest="api_key",
                    help="operator api key for the bridge (default: OPERATOR_API_KEY env; never printed)")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    live = bool(args.live)
    activity_fetcher = _dry_activity
    pcc_sampler = _dry_pcc

    if live:
        # HID-RING live path: fire+capture served by the RUNNING bridge's single-HID ring
        # (POST /operator/poep/fire) + activity/PCC from the SAME bridge (capture-health) - one
        # reader attests everything. Client-side env gate kept as defense-in-depth (never CI); the
        # bridge enforces its own fail-closed gates (POEP_LIVE_FIRE_ENABLED + l6b_enabled) and a
        # refused fire is honestly NOT a fire (no real_hardware synthesized anywhere).
        from l9_presence.poep_gameplay_live import real_hid_fire_available
        if not real_hid_fire_available():
            print("REFUSED: --live requires POEP_LIVE_FIRE_ENABLED=1 on this shell (and on the "
                  "bridge process, which enforces its own gates; never CI).", file=sys.stderr)
            return 2
        from l9_presence.poep_bridge_fire_adapter import make_bridge_fire_adapter
        adapter = make_bridge_fire_adapter(bridge_url=args.bridge_url, api_key=args.api_key)
        fire_fn = adapter.fire_fn
        imu_fn = adapter.imu_capture_fn
        activity_fetcher = _make_bridge_health_fetcher(args.bridge_url, args.api_key, "activity")
        pcc_sampler = _make_bridge_health_fetcher(args.bridge_url, args.api_key, "pcc")
        print("[live] served by the bridge's single-HID ring: fire=/operator/poep/fire, "
              "activity/PCC=/bridge/capture-health (same reader). Bridge gates refuse fail-closed "
              "-> honest IDENTITY_ONLY when closed.")
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
        activity_fetcher=activity_fetcher,   # live: the REAL bridge's attestation; dry: injected
        pcc_sampler=pcc_sampler,
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
