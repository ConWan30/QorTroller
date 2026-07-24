"""POEP session-identity-attach RUNNER (orchestration only) - gp-identity r02 build.

Composition-only: runs the SEALED live-session + identity-attach pieces as ONE call so a rig session
emits the identity-attach artifact. Adds ZERO liveness content. SYNCHRONIZED_CONTROLLER is reachable
ONLY on a real-hardware fire (real_hardware=True on every GO); an injected/dry run is always
IDENTITY_ONLY - inherited from the sealed summarize_session rail (effective_live requires all
GO.live_hardware; round-04 F-GP-4 defeats the state-file spoof).

PIPELINE PURITY (grok r02 FIX #2, load-bearing): this module NEVER assigns the candidate /
effective_live / live_hardware bits. The ONLY source of the presence summary is the sealed
summarize_live_session; attach_session_identity trusts that summary's candidate bit, so hand-building
it here would be the one real fabrication path. We don't - we pass the sealed return through untouched.

Sealed + byte-untouched: poep_gameplay_session.py, poep_gameplay_live.py, poep_did_sync.py,
controller_presence.py. Rails: poep_enabled / L6B / L6_CHALLENGES stay False; zero spend; no chain.
The DID subject is the gamer wallet, never the silicon. Design steered by grok
(docs/a2a/poep/round-gp-identity-02-grok-brainstorm.txt).
"""
from __future__ import annotations

from typing import Callable, Optional

from l9_presence.poep_did_sync import attach_session_identity, compute_live_seal_v2
from l9_presence.poep_gameplay_live import (
    BridgeActivityFetcher,
    FireFn,
    ImuCaptureFn,
    challenge_live,
    poll_bridge_activity,
    start_live_session,
    summarize_live_session,
)
from l9_presence.poep_gameplay_session import LOW_AMPLITUDE_FORCE_DEFAULT

RUN_SCHEMA = "qortroller-poep-session-identity-attach-run-v0"  # CANDIDATE - orchestration, not a domain tag

# The r01 orchestration ceiling, shipped in the artifact so a reader sees the bar, not just fields.
RUN_CLAIM_CEILING = (
    "This artifact is ORCHESTRATION ONLY: the sealed live-session and identity-attach pieces run as one "
    "command. It adds ZERO new liveness or humanity content. SYNCHRONIZED_CONTROLLER is reachable ONLY "
    "on a real-hardware fire (real_hardware=True on every GO); an injected or dry run is always "
    "IDENTITY_ONLY. The DID subject is the gamer wallet; the device links by the two-hop "
    "birth-cert->NFT->TBA chain. poep_enabled / L6B / L6_CHALLENGES stay False."
)

PccSampler = Callable[[], Optional[dict]]
_SEAL_V02_DOMAIN = "QORTROLLER-POEP-GAMEPLAY-LIVESEAL-v0.2-CANDIDATE"


def run_session_identity_attach(
    *,
    device_id: str,
    player_label: str,
    t_start_ns: int,
    process_nonce: str,
    challenge_plan: list,          # list[tuple[ChallengeKind, nonce_str]]
    fire_fn: FireFn,
    imu_capture_fn: ImuCaptureFn,
    activity_fetcher: BridgeActivityFetcher,
    pcc_sampler: PccSampler,
    ioid_identity: dict,           # owner_did, ioid_token_id, tba_address, registration_tx,
                                   # vmdr_pubkey_hash, controller_nft, controller_nft_token_id
    session_id: Optional[str] = None,
    include_custody_seal: bool = True,
    amplitude: int = LOW_AMPLITUDE_FORCE_DEFAULT,
) -> dict:
    """start_live_session -> challenge_live* -> summarize_live_session -> attach_session_identity.

    Returns the identity-attach artifact dict. Every I/O boundary (fire / imu / activity / pcc) is an
    INJECTED callable, so the whole path is deterministic + rig-free in tests. PURITY: the presence
    summary comes ONLY from the sealed summarize_live_session; this function never touches the
    candidate / effective_live / live_hardware bits. ``amplitude`` is a thin pass-through to sealed
    ``challenge_live`` (CLI override); never invents activity/PCC/candidate bits.
    """
    session, seal = start_live_session(
        device_id=device_id,
        player_label=player_label,
        t_start_ns=t_start_ns,
        process_nonce=process_nonce,
        session_id=session_id,
    )

    for kind, nonce in challenge_plan:
        poll_bridge_activity(session, activity_fetcher)
        challenge_live(
            session,
            seal=seal,
            process_nonce=process_nonce,
            nonce=nonce,
            kind=kind,
            fire_fn=fire_fn,
            imu_capture_fn=imu_capture_fn,
            pcc_sample=pcc_sampler(),
            amplitude=amplitude,
        )

    # The ONLY source of the presence summary (never hand-built / mutated here):
    summary = summarize_live_session(session, seal=seal, process_nonce=process_nonce)

    ident = dict(ioid_identity)
    artifact = attach_session_identity(
        presence_summary=summary,
        owner_did=ident["owner_did"],
        ioid_token_id=ident["ioid_token_id"],
        tba_address=ident["tba_address"],
        registration_tx=ident["registration_tx"],
        device_id=device_id,
        vmdr_pubkey_hash=ident["vmdr_pubkey_hash"],
        controller_nft=ident["controller_nft"],
        controller_nft_token_id=ident["controller_nft_token_id"],
        session_id=session.session_id,
    )

    # Orchestration provenance - NEW keys only; never overwrites the attach/presence claim strings.
    artifact["run_schema"] = RUN_SCHEMA
    artifact["run_claim_ceiling"] = RUN_CLAIM_CEILING

    # Seal v0.2 sidecar (grok r02 C): custody-epoch bookkeeping under `identity` - NEVER gates candidate.
    if include_custody_seal:
        artifact["identity"]["custody_seal_v02"] = {
            "seal": compute_live_seal_v2(
                session.session_id, device_id, session.t_start_ns, process_nonce,
                ident["controller_nft"], ident["controller_nft_token_id"], ident["tba_address"],
            ),
            "domain": _SEAL_V02_DOMAIN,
            "note": "NFT/TBA custody epoch bookkeeping - NOT a liveness or presence signal",
        }

    return artifact
