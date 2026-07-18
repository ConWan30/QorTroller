"""POEP-DID-SYNC - identity/provenance attach (QORTROLLER-POEP-SESSION-IDENTITY-ATTACH-v0 CANDIDATE).

IDENTITY / PROVENANCE ONLY. ZERO liveness or humanity content. This does NOT promote FLIP-A -> FLIP-B,
does NOT advance poep_enabled / the presence candidate, and does NOT touch floors or the dry/live model.

It COMPOSES ON TOP OF l9_presence.controller_presence (the existing ioID x PoEP dual-bit record - its
fail-closed device-mismatch anti-assertion, its advances_*: False non-claims) and ADDS the one thing that
record lacks: the FULL two-hop device->owner link the round-01 ceiling requires, so a stranger WALKS
device -> owner rather than collapsing the chain into one assertion. The DID subject is the GAMER WALLET, never
the silicon (birth-cert -> NFT -> TBA is how the physical Edge hangs off the wallet's DID).

Rails: no edit to the sealed round-04/05 summarize_session or to poep_gameplay_live.compute_live_seal
(v0); `attach_session_identity` NEVER mutates its input; seal v0.2 is a NEW domain (v0 byte-unchanged).
Design forward-brainstormed with grok (round-did-sync-r02): wrap-schema not flat-merge; the DID is
named as the OWNER's; explicit `did_subject`; seal v0.2 binds the CUSTODY holder (TBA), not just tokenId.
"""
from __future__ import annotations

import copy
import hashlib
from typing import Optional

from l9_presence.controller_presence import build_controller_presence

ATTACH_SCHEMA = "qortroller-poep-session-identity-attach-v0"  # CANDIDATE - not FROZEN / not a domain tag
IDENTITY_LANE = "identity-provenance"

# The round-01 pinned claim ceiling, verbatim (byte-checked against the r01 open in tests). It ships in
# the emitted artifact so a reader sees the bar, not just the fields.
CLAIM_CEILING = (
    "This increment strengthens the identity/provenance attached to session evidence. It adds ZERO "
    "liveness or humanity content. The DID subject is the gamer wallet (`did:io:0x0cf36db5...`); the "
    "device's link to it is the two-hop birth-cert->NFT->TBA chain, which the summary must carry in "
    "full. Candidate semantics, floors, and the dry/live model are byte-unchanged."
)


def _norm(d) -> str:
    return str(d or "").strip().lower()


def attach_session_identity(
    *,
    presence_summary: dict,
    owner_did: str,
    ioid_token_id: int,
    tba_address: str,
    registration_tx: str,
    device_id: str,
    vmdr_pubkey_hash: str,
    controller_nft: str,
    controller_nft_token_id: int,
    session_id: Optional[str] = None,
) -> dict:
    """Wrap a PoEP session summary with its GAMER-WALLET ioID identity + the full device->owner link.

    Returns a NEW top-level schema (identity is a SURFACE, structurally separate from presence - never
    flat-merged into the v0.1 presence schema). `presence_summary` is deep-copied, NEVER mutated.

    GUARD (anti-assertion): the session's device_id must equal the link device_id - the identity must
    describe the SAME Edge, or the attach is REFUSED (mirrors controller_presence's mismatch rail).
    """
    ps_dev = _norm(presence_summary.get("device_id"))
    link_dev = _norm(device_id)
    # Fail-closed (grok r03 residual): the identity must bind to a KNOWN session device. A session with
    # no device_id can't be honestly bound to an identity; a mismatch is a wrong-Edge assertion.
    if link_dev and not ps_dev:
        raise ValueError(
            "identity attach REFUSED: presence_summary has no device_id - the identity must bind to a "
            "KNOWN session device (anti-assertion).")
    if ps_dev and link_dev and ps_dev != link_dev:
        raise ValueError(
            f"identity attach REFUSED: session device_id ({ps_dev[:16]}...) != link device_id "
            f"({link_dev[:16]}...) - identity must describe the SAME Edge (anti-assertion).")

    # Reuse controller_presence's dual-bit verdict + fail-closed rails (identity_bound / candidate).
    cp = build_controller_presence(
        device_id=device_id,
        session_id=session_id or presence_summary.get("session_id"),
        ioid={"token_id": ioid_token_id, "did": owner_did, "tba": tba_address,
              "registered_device_id": device_id},
        poep_live_summary=presence_summary,
    ).to_dict()

    return {
        "schema": ATTACH_SCHEMA,
        # exact v0.1 presence summary, copied + untouched (never re-scored, never mutated):
        "presence_summary": copy.deepcopy(presence_summary),
        "controller_presence": cp,   # the existing dual-bit verdict record (SYNCHRONIZED / IDENTITY_ONLY / ...)
        "identity": {
            # explicit machine subject: the DID names the WALLET, not the silicon
            "did_subject": "gamer_wallet",
            "did_names_silicon": False,
            "owner_did": owner_did,          # named as the OWNER's, not the device's; OUTSIDE the link
            "ioid_token_id": ioid_token_id,
            "tba_address": tba_address,
            "registration_tx": registration_tx,
            # the two-hop device->owner link a stranger WALKS (no key named `did` inside it):
            "device_to_owner_link": {
                "device_id": device_id,
                "vmdr_pubkey_hash": vmdr_pubkey_hash,
                "controller_nft": controller_nft,
                "controller_nft_token_id": controller_nft_token_id,
                "tba_address": tba_address,
            },
            "link_hops": ["device_pubkey_hash", "controller_nft", "tba", "owner_did"],
        },
        "identity_lane": IDENTITY_LANE,
        # hard non-claims, machine-readable (mirror controller_presence - dashboards cannot invent flips):
        "advances_poep_enabled": False,
        "advances_presence_session_candidate": False,
        "advisory": True,
        "claim_ceiling": CLAIM_CEILING,
    }


# -- Seal v0.2 (H2: custody-tracking; v0 compute_live_seal is byte-unchanged elsewhere) ----------------
_LIVE_SEAL_V02_DOMAIN = b"QORTROLLER-POEP-GAMEPLAY-LIVESEAL-v0.2-CANDIDATE"


def compute_live_seal_v2(
    session_id: str,
    device_id: str,
    t_start_ns: int,
    process_nonce: str,
    controller_nft: str,
    controller_nft_token_id: int,
    tba_address: str,
) -> str:
    """Seal v0.2 CANDIDATE - binds the live session to the NFT CUSTODY HOLDER (H2).

    grok r02 FIX: `controller_nft_token_id` alone is STABLE across transfer, so binding only it does
    NOT distinguish custody epochs. v0.2 also binds `tba_address` (the holder that MOVES on transfer),
    so pre/post custody-transfer seals are cryptographically distinguishable. This is a **NFT/TBA-custody
    epoch**, NOT a device-identity epoch. Distinct new domain; v0 `compute_live_seal` is byte-unchanged.
    """
    if not (session_id and device_id and process_nonce and controller_nft and tba_address):
        raise ValueError("session_id, device_id, process_nonce, controller_nft, tba_address required")
    body = (
        _LIVE_SEAL_V02_DOMAIN + b"|"
        + session_id.encode() + b"|"
        + device_id.encode() + b"|"
        + str(int(t_start_ns)).encode() + b"|"
        + process_nonce.encode() + b"|"
        + controller_nft.encode() + b"|"
        + str(int(controller_nft_token_id)).encode() + b"|"
        + tba_address.encode()
    )
    return hashlib.sha256(body).hexdigest()
