"""Session Continuum composition (QORTROLLER-SESSION-CONTINUUM-v0 CANDIDATE).

REFERENCE-AND-BIND only — no FROZEN-v1 family, no domain-tag commitment, no chain write.
Integrity derives from the surfaces it *references*:

  - RWM L0 optical chain: session_id + device_id_hex + tip + caller-supplied l0_verified
  - U1 session identity: session_id = SHA-256(UTF-8(session_display)) when display is cited
  - ioID identity surface: DID / tokenId / TBA / registered device_id
  - PoEP gameplay-live surface: presence_session_candidate_ok + device_id / session_id
  - Stack cites (optional): NOV-2 bind, NOV-3 escrow, PoSP, KAS — session_id join only

THE CLAIM (when SYNCHRONIZED_CONTINUUM): for ONE session_id and ONE device_id, a verified
L0 RWM optical chain, a gamer-sovereign ioID binding, and a host-trusted PoEP live session
candidate describe the SAME play continuum — multi-bit, never OR-merged.

ANTI-ASSERTION rails (fail-closed):
  - device_id mismatch across any cited surface → UNVERIFIABLE
  - session_id mismatch across any cited surface → UNVERIFIABLE
  - optical alone NEVER implies identity_bound or presence_candidate
  - identity / presence alone NEVER invent optical_rwm
  - stack cite (PoAC/GIC tip bind, escrow, PoSP, KAS) never OR-merges into SYNCHRONIZED
  - no field advances poep_enabled / L6B / FROZEN seal

Join keys: session_id (U1) + device_id (Edge). Pure stdlib.
Pattern mirrors l9_presence/controller_presence.py (named parallel roots).
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, Optional

SCHEMA = "qortroller-session-continuum-v0"  # CANDIDATE — not a domain tag / not FROZEN

# Closed verdict enum
SYNCHRONIZED_CONTINUUM = "SYNCHRONIZED_CONTINUUM"
OPTICAL_IDENTITY = "OPTICAL_IDENTITY"
OPTICAL_PRESENCE = "OPTICAL_PRESENCE"
OPTICAL_SESSION = "OPTICAL_SESSION"
STACK_WITHOUT_OPTICAL = "STACK_WITHOUT_OPTICAL"
PARTIAL = "PARTIAL"
UNVERIFIABLE = "UNVERIFIABLE"

# Canonical Edge from ioID Inc-D live ceremony (informational default for docs/tests only)
EDGE_DEVICE_ID_LIVE = (
    "581a836c98b3a1b6c0f598bfca88e6a3cc3bd7c34591b506692cb40ddf66a9f8"
)


@dataclass
class SessionContinuumRecord:
    """Multi-bit composition postcard. Deliberately has no commitment() / domain tag."""

    schema: str
    verdict: str
    device_id: Optional[str]
    session_id: Optional[str]
    session_display: Optional[str]
    # Parallel bits — NEVER collapse to a single "ok"
    optical_rwm: bool
    session_join: bool
    device_join: bool
    identity_bound: bool
    presence_candidate: bool
    stack_cited: bool
    # Named parallel roots
    rwm: Optional[dict]
    ioid: Optional[dict]
    poep_live: Optional[dict]
    stack: Optional[dict]
    notes: list = field(default_factory=list)
    # Hard non-claims
    advances_poep_enabled: bool = False
    advances_l6b_enabled: bool = False
    advances_presence_session_candidate: bool = False
    advisory: bool = True

    def to_dict(self) -> dict:
        return {
            "schema": self.schema,
            "verdict": self.verdict,
            "device_id": self.device_id,
            "session_id": self.session_id,
            "session_display": self.session_display,
            "optical_rwm": self.optical_rwm,
            "session_join": self.session_join,
            "device_join": self.device_join,
            "identity_bound": self.identity_bound,
            "presence_candidate": self.presence_candidate,
            "stack_cited": self.stack_cited,
            "rwm": self.rwm,
            "ioid": self.ioid,
            "poep_live": self.poep_live,
            "stack": self.stack,
            "notes": list(self.notes),
            "advances_poep_enabled": False,
            "advances_l6b_enabled": False,
            "advances_presence_session_candidate": False,
            "advisory": True,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, sort_keys=True)


def _norm_dev(d: Any) -> str:
    s = str(d or "").strip().lower().removeprefix("0x")
    return s


def _norm_sid(s: Any) -> str:
    return str(s or "").strip().lower()


def _u1_matches(session_id: str, session_display: str) -> bool:
    """U1: session_id == SHA-256(UTF-8(session_display))."""
    if not session_id or not session_display:
        return False
    expect = hashlib.sha256(session_display.encode("utf-8")).hexdigest()
    return expect == session_id.lower()


def build_session_continuum(
    *,
    device_id: Optional[str] = None,
    session_id: Optional[str] = None,
    session_display: Optional[str] = None,
    rwm: Optional[dict] = None,
    ioid: Optional[dict] = None,
    poep_live_summary: Optional[dict] = None,
    stack: Optional[dict] = None,
) -> SessionContinuumRecord:
    """Compose RWM optical + U1 session + optional ioID / PoEP / stack cites.

    `rwm` keys (caller-loaded; pure module does not touch disk):
      session_id, device_id | device_id_hex, l0_chain_tip_hex, l0_verified (bool),
      n_frames (optional), schema (optional)

    `ioid` keys — same as controller_presence:
      token_id | ioid_token_id, did, tba | tba_address, registered_device_id | device_id

    `poep_live_summary` keys:
      presence_session_candidate_ok, device_id, session_id, live_seal (optional)

    `stack` optional cites (any subset; each may carry session_id / tip fields):
      nov2_bind: {session_id, bind_ok?, l0_chain_tip_hex?}
      escrow: {session_id, commitment_root? / ok?}
      posp: {session_id, verdict?}
      kas: {session_id, verdict?}
      poac_tip_hex / gic_tip_hex (informational)

    Fail-closed: device or session mismatch across surfaces → UNVERIFIABLE.
    """
    notes: list[str] = []
    wrapper_dev = _norm_dev(device_id)
    wrapper_sid = _norm_sid(session_id)
    display = str(session_display).strip() if session_display else None

    # ---- RWM optical plane ----
    rwm_block: Optional[dict] = None
    optical_rwm = False
    rwm_dev = ""
    rwm_sid = ""

    if isinstance(rwm, dict) and rwm:
        rwm_sid = _norm_sid(rwm.get("session_id"))
        rwm_dev = _norm_dev(rwm.get("device_id_hex") or rwm.get("device_id"))
        tip = str(rwm.get("l0_chain_tip_hex") or rwm.get("chain_tip_hex") or "").strip().lower()
        verified = rwm.get("l0_verified") is True
        n_frames = rwm.get("n_frames")
        id_verified: Optional[bool]
        if not verified:
            notes.append("rwm: l0_verified is not True — optical_rwm stays False")
            id_verified = False
        elif not rwm_sid or not rwm_dev:
            notes.append("rwm: missing session_id or device_id — cannot bind optical plane")
            id_verified = False
        elif len(rwm_dev) != 64:
            notes.append(f"rwm: device_id must be 32-byte hex (64 chars), got {len(rwm_dev)}")
            id_verified = False
        else:
            id_verified = True
            optical_rwm = True
            if not wrapper_dev:
                wrapper_dev = rwm_dev
            if not wrapper_sid:
                wrapper_sid = rwm_sid

        if wrapper_dev and rwm_dev and rwm_dev != wrapper_dev:
            notes.append(
                f"rwm: device_id MISMATCH ({rwm_dev[:16]}… != {wrapper_dev[:16]}…)"
            )
            id_verified = False
            optical_rwm = False
        if wrapper_sid and rwm_sid and rwm_sid != wrapper_sid:
            notes.append(
                f"rwm: session_id MISMATCH ({rwm_sid[:16]}… != {wrapper_sid[:16]}…)"
            )
            id_verified = False
            optical_rwm = False

        rwm_block = {
            "session_id": rwm_sid or None,
            "device_id": rwm_dev or None,
            "l0_chain_tip_hex": tip or None,
            "l0_verified": verified,
            "n_frames": n_frames,
            "schema": rwm.get("schema"),
            "id_verified": id_verified,
        }
    else:
        notes.append("rwm: absent — optical_rwm stays False")

    # ---- U1 session_display re-check (optional) ----
    session_join = bool(wrapper_sid)
    if display and wrapper_sid:
        if _u1_matches(wrapper_sid, display):
            notes.append("u1: session_display re-derives session_id (U1 join held)")
        else:
            notes.append("u1: session_display MISMATCH vs session_id — U1 join broken")
            session_join = False
    elif display and not wrapper_sid:
        # derive session_id from display if wrapper empty
        wrapper_sid = hashlib.sha256(display.encode("utf-8")).hexdigest()
        session_join = True
        notes.append("u1: session_id derived from session_display")
    elif wrapper_sid:
        notes.append("u1: session_id present; session_display not cited (join by equality only)")
    else:
        notes.append("u1: no session_id resolvable")
        session_join = False

    # ---- ioID identity ----
    ioid_block: Optional[dict] = None
    identity_bound = False
    ioid_dev = ""

    if isinstance(ioid, dict) and ioid:
        token_id = ioid.get("token_id", ioid.get("ioid_token_id"))
        did = ioid.get("did")
        tba = ioid.get("tba", ioid.get("tba_address"))
        ioid_dev = _norm_dev(ioid.get("registered_device_id") or ioid.get("device_id"))
        has_material = token_id is not None or bool(did) or bool(tba)
        if not has_material:
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

    # ---- PoEP presence ----
    poep_block: Optional[dict] = None
    presence_candidate = False

    if isinstance(poep_live_summary, dict) and poep_live_summary:
        cand = poep_live_summary.get("presence_session_candidate_ok") is True
        poep_dev = _norm_dev(poep_live_summary.get("device_id"))
        poep_sid = _norm_sid(poep_live_summary.get("session_id"))
        seal = poep_live_summary.get("live_seal") or poep_live_summary.get("seal")
        if not poep_dev:
            notes.append("poep_live: missing device_id — cannot bind")
            id_verified = False
            cand = False
        elif wrapper_dev and poep_dev != wrapper_dev:
            notes.append(
                f"poep_live: device_id MISMATCH ({poep_dev[:16]}… != {wrapper_dev[:16]}…)"
            )
            id_verified = False
            cand = False
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
        if wrapper_sid and poep_sid and poep_sid != wrapper_sid:
            notes.append(
                f"poep_live: session_id MISMATCH ({poep_sid[:16]}… != {wrapper_sid[:16]}…)"
            )
            presence_candidate = False
            id_verified = False
            session_join = False
        elif poep_sid and not wrapper_sid:
            wrapper_sid = poep_sid
        poep_block = {
            "presence_session_candidate_ok": bool(
                poep_live_summary.get("presence_session_candidate_ok") is True
            ),
            "device_id": poep_dev or None,
            "session_id": poep_sid or None,
            "live_seal": seal,
            "id_verified": id_verified,
        }
    else:
        notes.append("poep_live: absent — presence_candidate stays False")

    # ---- Stack cites (NOV-2 / escrow / PoSP / KAS) — session join only ----
    stack_block: Optional[dict] = None
    stack_cited = False
    stack_out: dict[str, Any] = {}

    if isinstance(stack, dict) and stack:
        cited_any = False
        for key in ("nov2_bind", "escrow", "posp", "kas"):
            sub = stack.get(key)
            if not isinstance(sub, dict) or not sub:
                continue
            cited_any = True
            sub_sid = _norm_sid(sub.get("session_id"))
            ok_flag = sub.get("bind_ok") if key == "nov2_bind" else sub.get("ok")
            if ok_flag is None:
                ok_flag = True  # presence of cite is enough when no explicit ok
            entry: dict[str, Any] = {
                "session_id": sub_sid or None,
                "ok": bool(ok_flag),
            }
            if sub_sid and wrapper_sid and sub_sid != wrapper_sid:
                notes.append(f"stack.{key}: session_id MISMATCH")
                entry["ok"] = False
                session_join = False
            elif sub_sid and not wrapper_sid:
                wrapper_sid = sub_sid
            if key == "nov2_bind":
                tip = str(sub.get("l0_chain_tip_hex") or "").strip().lower()
                entry["l0_chain_tip_hex"] = tip or None
                entry["bind_kind"] = sub.get("bind_kind")
                if (
                    rwm_block
                    and rwm_block.get("l0_chain_tip_hex")
                    and tip
                    and tip != rwm_block["l0_chain_tip_hex"]
                ):
                    notes.append("stack.nov2_bind: l0 tip MISMATCH vs rwm tip")
                    entry["ok"] = False
            stack_out[key] = entry
            if entry["ok"]:
                stack_cited = True
        for tip_key in ("poac_tip_hex", "gic_tip_hex"):
            if stack.get(tip_key):
                stack_out[tip_key] = str(stack[tip_key]).strip().lower()
                cited_any = True
        if not cited_any:
            notes.append("stack: empty dict — stack_cited stays False")
        stack_block = stack_out or None
    else:
        notes.append("stack: absent — stack_cited stays False")

    # ---- Device join ----
    device_join = bool(wrapper_dev) and len(wrapper_dev) == 64

    # ---- Anti-OR non-claims ----
    if optical_rwm and not identity_bound:
        notes.append("non-claim: optical_rwm does NOT imply identity_bound")
    if optical_rwm and not presence_candidate:
        notes.append("non-claim: optical_rwm does NOT imply presence_session_candidate_ok")
    if identity_bound and not optical_rwm:
        notes.append("non-claim: identity_bound does NOT invent optical_rwm")
    if presence_candidate and not optical_rwm:
        notes.append("non-claim: presence_candidate does NOT invent optical_rwm")
    if stack_cited:
        notes.append(
            "non-claim: stack_cited (bind/escrow/posp/kas) does NOT OR-merge into "
            "SYNCHRONIZED_CONTINUUM"
        )
    notes.append(
        "non-claim: composition does not advance poep_enabled, L6B_ENABLED, or FROZEN seal"
    )

    # ---- Verdict selection (fail-closed on mismatch) ----
    mismatch = any("MISMATCH" in n for n in notes)
    if mismatch or (not wrapper_dev and not wrapper_sid and not optical_rwm):
        verdict = UNVERIFIABLE
        if mismatch:
            optical_rwm = False
            identity_bound = False
            presence_candidate = False
            stack_cited = False
            session_join = False
            device_join = False
            notes.append("unverifiable: anti-assertion MISMATCH cleared all success bits")
        elif not wrapper_dev and not wrapper_sid:
            notes.append("unverifiable: no device_id or session_id resolvable")
    elif optical_rwm and session_join and device_join and identity_bound and presence_candidate:
        verdict = SYNCHRONIZED_CONTINUUM
    elif optical_rwm and session_join and device_join and identity_bound:
        verdict = OPTICAL_IDENTITY
    elif optical_rwm and session_join and device_join and presence_candidate:
        verdict = OPTICAL_PRESENCE
    elif optical_rwm and session_join and device_join:
        verdict = OPTICAL_SESSION
    elif (identity_bound or presence_candidate or stack_cited) and not optical_rwm:
        if session_join or device_join:
            verdict = STACK_WITHOUT_OPTICAL
        else:
            verdict = PARTIAL
    elif rwm_block or ioid_block or poep_block or stack_block:
        verdict = PARTIAL
    else:
        verdict = UNVERIFIABLE

    return SessionContinuumRecord(
        schema=SCHEMA,
        verdict=verdict,
        device_id=wrapper_dev or None,
        session_id=wrapper_sid or None,
        session_display=display,
        optical_rwm=optical_rwm and not mismatch,
        session_join=session_join and not mismatch,
        device_join=device_join and not mismatch,
        identity_bound=identity_bound and not mismatch,
        presence_candidate=presence_candidate and not mismatch,
        stack_cited=stack_cited and not mismatch,
        rwm=rwm_block,
        ioid=ioid_block,
        poep_live=poep_block,
        stack=stack_block,
        notes=notes,
    )


def verify_continuum(record: dict | SessionContinuumRecord) -> dict[str, Any]:
    """Soft structural re-check of a continuum package (no disk I/O)."""
    checks: list[dict[str, Any]] = []

    def _chk(name: str, ok: bool, note: str = "") -> None:
        checks.append({"name": name, "ok": bool(ok), "note": note})

    d = record.to_dict() if isinstance(record, SessionContinuumRecord) else dict(record)
    try:
        _chk("schema", d.get("schema") == SCHEMA, str(d.get("schema")))
        v = d.get("verdict")
        allowed = {
            SYNCHRONIZED_CONTINUUM,
            OPTICAL_IDENTITY,
            OPTICAL_PRESENCE,
            OPTICAL_SESSION,
            STACK_WITHOUT_OPTICAL,
            PARTIAL,
            UNVERIFIABLE,
        }
        _chk("verdict_enum", v in allowed, str(v))
        _chk("advisory", d.get("advisory") is True)
        _chk("no_poep_advance", d.get("advances_poep_enabled") is False)
        _chk("no_l6b_advance", d.get("advances_l6b_enabled") is False)
        # Re-compose from cited surfaces and compare verdict (determinism)
        rebuilt = build_session_continuum(
            device_id=d.get("device_id"),
            session_id=d.get("session_id"),
            session_display=d.get("session_display"),
            rwm=_rwm_input_from_block(d.get("rwm")),
            ioid=_ioid_input_from_block(d.get("ioid")),
            poep_live_summary=_poep_input_from_block(d.get("poep_live")),
            stack=_stack_input_from_block(d.get("stack")),
        )
        _chk("verdict_stable", rebuilt.verdict == v, f"{rebuilt.verdict} vs {v}")
        _chk("optical_stable", rebuilt.optical_rwm == bool(d.get("optical_rwm")))
        _chk("identity_stable", rebuilt.identity_bound == bool(d.get("identity_bound")))
        _chk(
            "presence_stable",
            rebuilt.presence_candidate == bool(d.get("presence_candidate")),
        )
    except Exception as e:  # noqa: BLE001
        _chk("exception", False, repr(e)[:200])
        return {"ok": False, "checks": checks}

    ok = all(c["ok"] for c in checks)
    return {"ok": ok, "checks": checks, "verdict": d.get("verdict")}


def _rwm_input_from_block(block: Optional[dict]) -> Optional[dict]:
    if not isinstance(block, dict) or not block:
        return None
    return {
        "session_id": block.get("session_id"),
        "device_id_hex": block.get("device_id"),
        "l0_chain_tip_hex": block.get("l0_chain_tip_hex"),
        "l0_verified": block.get("l0_verified") is True,
        "n_frames": block.get("n_frames"),
        "schema": block.get("schema"),
    }


def _ioid_input_from_block(block: Optional[dict]) -> Optional[dict]:
    if not isinstance(block, dict) or not block:
        return None
    if block.get("id_verified") is False and not (
        block.get("token_id") or block.get("did") or block.get("tba")
    ):
        return None
    return {
        "token_id": block.get("token_id"),
        "did": block.get("did"),
        "tba": block.get("tba"),
        "registered_device_id": block.get("registered_device_id"),
    }


def _poep_input_from_block(block: Optional[dict]) -> Optional[dict]:
    if not isinstance(block, dict) or not block:
        return None
    return {
        "presence_session_candidate_ok": block.get("presence_session_candidate_ok"),
        "device_id": block.get("device_id"),
        "session_id": block.get("session_id"),
        "live_seal": block.get("live_seal"),
    }


def _stack_input_from_block(block: Optional[dict]) -> Optional[dict]:
    if not isinstance(block, dict) or not block:
        return None
    out: dict[str, Any] = {}
    for key in ("nov2_bind", "escrow", "posp", "kas"):
        sub = block.get(key)
        if isinstance(sub, dict) and sub:
            out[key] = {
                "session_id": sub.get("session_id"),
                "ok": sub.get("ok"),
                "bind_ok": sub.get("ok") if key == "nov2_bind" else None,
                "l0_chain_tip_hex": sub.get("l0_chain_tip_hex"),
                "bind_kind": sub.get("bind_kind"),
            }
    for tip_key in ("poac_tip_hex", "gic_tip_hex"):
        if block.get(tip_key):
            out[tip_key] = block[tip_key]
    return out or None
