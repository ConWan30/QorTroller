"""Controller Presence composition (QORTROLLER-CONTROLLER-PRESENCE-v0 CANDIDATE).

REFERENCE-AND-BIND only — no FROZEN-v1 family, no domain-tag commitment, no chain write.
Integrity derives from the surfaces it *references*:

  - ioID identity surface: DID / tokenId / TBA / registered device_id (live ceremony 91449f41)
  - PoEP gameplay-live surface: presence_session_candidate_ok + live seal / session_id / device_id

THE CLAIM (when SYNCHRONIZED_CONTROLLER): for ONE device_id, a gamer-sovereign ioID binding
and a host-trusted PoEP live session-candidate describe the SAME Edge — dual bits, never OR-merged.

ANTI-ASSERTION rails (fail-closed):
  - device_id mismatch across surfaces → UNVERIFIABLE (never papered into partial success)
  - identity alone NEVER implies presence_session_candidate_ok
  - presence alone NEVER implies identity_bound
  - no field advances poep_enabled / L6B (composition is off-chain bookkeeping only)

Join key: device_id (physical Edge). session_id is optional session join (PoSP-style), not required
for IDENTITY_ONLY. Pure stdlib. Pattern mirrors l9_presence/posp.py (named parallel roots).
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Optional

SCHEMA = "qortroller-controller-presence-v0"  # CANDIDATE — not a domain tag / not FROZEN

# Closed verdict enum
SYNCHRONIZED_CONTROLLER = "SYNCHRONIZED_CONTROLLER"
IDENTITY_ONLY = "IDENTITY_ONLY"
PRESENCE_ONLY = "PRESENCE_ONLY"
PARTIAL = "PARTIAL"
UNVERIFIABLE = "UNVERIFIABLE"

# Canonical Edge from ioID Inc-D live ceremony (informational default for docs/tests only)
EDGE_DEVICE_ID_LIVE = (
    "581a836c98b3a1b6c0f598bfca88e6a3cc3bd7c34591b506692cb40ddf66a9f8"
)


@dataclass
class ControllerPresenceRecord:
    """Dual-bit composition postcard. Deliberately has no commitment() / domain tag."""

    schema: str
    verdict: str
    device_id: Optional[str]
    session_id: Optional[str]
    # Dual bits — NEVER collapse to a single "ok"
    identity_bound: bool
    presence_candidate: bool
    # Named parallel roots (PoSP §2.3 style)
    ioid: Optional[dict]  # {token_id, did, tba, registered_device_id, id_verified, note?}
    poep_live: Optional[dict]  # {presence_session_candidate_ok, device_id, session_id, seal?, id_verified}
    notes: list = field(default_factory=list)
    # Hard non-claims (machine-readable so dashboards cannot invent flag flips)
    advances_poep_enabled: bool = False
    advances_presence_session_candidate: bool = False  # composition never *creates* the candidate
    advisory: bool = True

    def to_dict(self) -> dict:
        return {
            "schema": self.schema,
            "verdict": self.verdict,
            "device_id": self.device_id,
            "session_id": self.session_id,
            "identity_bound": self.identity_bound,
            "presence_candidate": self.presence_candidate,
            "ioid": self.ioid,
            "poep_live": self.poep_live,
            "notes": list(self.notes),
            "advances_poep_enabled": False,
            "advances_presence_session_candidate": False,
            "advisory": True,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, sort_keys=True)


def _norm_dev(d: Any) -> str:
    return str(d or "").strip().lower()


def build_controller_presence(
    *,
    device_id: Optional[str] = None,
    session_id: Optional[str] = None,
    ioid: Optional[dict] = None,
    poep_live_summary: Optional[dict] = None,
) -> ControllerPresenceRecord:
    """Compose identity (ioID) + session liveness candidate (PoEP live).

    `ioid` keys (any subset; missing → not bound):
      token_id | ioid_token_id, did, tba | tba_address, registered_device_id | device_id
    `poep_live_summary` keys:
      presence_session_candidate_ok (bool), device_id, session_id (optional), live_seal (optional)

    Fail-closed: no device_id and nothing resolvable → UNVERIFIABLE.
    Mismatch of device across surfaces → UNVERIFIABLE (anti-assertion).
    """
    notes: list[str] = []
    wrapper_dev = _norm_dev(device_id)

    ioid_block: Optional[dict] = None
    identity_bound = False
    ioid_dev = ""

    if isinstance(ioid, dict) and ioid:
        token_id = ioid.get("token_id", ioid.get("ioid_token_id"))
        did = ioid.get("did")
        tba = ioid.get("tba", ioid.get("tba_address"))
        ioid_dev = _norm_dev(ioid.get("registered_device_id") or ioid.get("device_id"))
        has_identity_material = token_id is not None or bool(did) or bool(tba)
        if not has_identity_material:
            notes.append("ioid: no token_id/did/tba — identity surface empty")
            id_verified = False
        elif not ioid_dev:
            notes.append("ioid: missing registered_device_id — cannot bind to Edge")
            id_verified = False
        elif wrapper_dev and ioid_dev != wrapper_dev:
            notes.append(
                f"ioid: device_id MISMATCH ({ioid_dev[:16]}… != {wrapper_dev[:16]}…)"
            )
            id_verified = False
        else:
            id_verified = True
            identity_bound = True
            if not wrapper_dev:
                wrapper_dev = ioid_dev
        ioid_block = {
            "token_id": token_id,
            "did": did,
            "tba": tba,
            "registered_device_id": ioid_dev or None,
            "id_verified": id_verified,
        }
    else:
        notes.append("ioid: absent — identity_bound stays False")

    poep_block: Optional[dict] = None
    presence_candidate = False

    if isinstance(poep_live_summary, dict) and poep_live_summary:
        cand = bool(poep_live_summary.get("presence_session_candidate_ok") is True)
        poep_dev = _norm_dev(poep_live_summary.get("device_id"))
        poep_sid = poep_live_summary.get("session_id")
        seal = poep_live_summary.get("live_seal") or poep_live_summary.get("seal")
        id_verified: Optional[bool]
        if not poep_dev:
            notes.append("poep_live: missing device_id — cannot bind")
            id_verified = False
            cand = False  # refuse candidate without device bind
        elif wrapper_dev and poep_dev != wrapper_dev:
            notes.append(
                f"poep_live: device_id MISMATCH ({poep_dev[:16]}… != {wrapper_dev[:16]}…)"
            )
            id_verified = False
            cand = False  # anti-assertion: wrong device never contributes presence bit
        else:
            id_verified = True
            if not wrapper_dev:
                wrapper_dev = poep_dev
            if cand:
                presence_candidate = True
            else:
                notes.append(
                    "poep_live: presence_session_candidate_ok is not True — "
                    "presence_candidate stays False"
                )
        if session_id and poep_sid and str(poep_sid) != str(session_id):
            notes.append(
                f"poep_live: session_id MISMATCH ({str(poep_sid)[:16]}… != {str(session_id)[:16]}…)"
            )
            # session mismatch poisons synchronized claim even if device matches
            presence_candidate = False
            id_verified = False
        poep_block = {
            "presence_session_candidate_ok": bool(
                poep_live_summary.get("presence_session_candidate_ok") is True
            ),
            "device_id": poep_dev or None,
            "session_id": poep_sid,
            "live_seal": seal,
            "id_verified": id_verified,
        }
    else:
        notes.append("poep_live: absent — presence_candidate stays False")

    # Explicit anti-OR: never invent a merged green light
    if identity_bound and not presence_candidate:
        notes.append(
            "non-claim: identity_bound does NOT imply presence_session_candidate_ok"
        )
    if presence_candidate and not identity_bound:
        notes.append(
            "non-claim: presence_candidate does NOT imply ioID / DID / TBA binding"
        )
    notes.append(
        "non-claim: composition does not advance poep_enabled or L6B_ENABLED"
    )

    # Verdict selection (fail-closed on mismatch notes)
    mismatch = any("MISMATCH" in n for n in notes)
    if mismatch or not wrapper_dev:
        verdict = UNVERIFIABLE
        if not wrapper_dev:
            notes.append("unverifiable: no device_id resolvable from any surface")
        # mismatch clears both bits for the synchronized claim path
        if mismatch:
            identity_bound = False
            presence_candidate = False
    elif identity_bound and presence_candidate:
        verdict = SYNCHRONIZED_CONTROLLER
    elif identity_bound and not presence_candidate:
        verdict = IDENTITY_ONLY
    elif presence_candidate and not identity_bound:
        verdict = PRESENCE_ONLY
    elif ioid_block or poep_block:
        verdict = PARTIAL
    else:
        verdict = UNVERIFIABLE

    return ControllerPresenceRecord(
        schema=SCHEMA,
        verdict=verdict,
        device_id=wrapper_dev or None,
        session_id=str(session_id) if session_id else None,
        identity_bound=identity_bound and not mismatch,
        presence_candidate=presence_candidate and not mismatch,
        ioid=ioid_block,
        poep_live=poep_block,
        notes=notes,
    )
