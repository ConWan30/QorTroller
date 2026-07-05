"""PoSP — Proof of Synchronized Presence (QORTROLLER-POSP-v0, CANDIDATE). Increment U2a.

THE CLAIM: "for ONE session (identified by the U1 session_id), the per-kill-event authorship certificate
(KAS) and the session-level presence fusion evidence (NQPV co-capture rows) describe the SAME session on
the SAME device — verifiably, by a common identifier, not by wall-clock inference."

This is a REFERENCE-AND-BIND proof — it mints NO new commitment primitive, NO domain-tag hash, NO
FROZEN-v1 family (option (b) of docs/d-cert5-unified-presence-design-2026-07-04.md, D-CERT-5.1 hybrid
b->a; D-CERT-5.2 operational; D-CERT-5.3 schema string only). Its integrity derives ENTIRELY from the
commitments it references: the KAS commitment (SHA-256, QORTROLLER-KAS-v0), the fusion rows'
record_hash_hex (PoAC chain), the named events_roots, and the tier-1 archive manifest's per-file SHA-256s.
A verifier recomputes THOSE; PoSP is the map that says which ones belong together. Never mistake this for
an eleventh FROZEN-v1 family — there is deliberately nothing here to freeze.

TWO ROOTS, NAMED (design §2.3 — the load-bearing disambiguation): `kas_session_root` (the KAS dual-lobe
events_root: screen kill outcomes + device-clock HID onsets) and `retina_perception_root` (the trio-retina
perception events_root, when that stack ran) are DIFFERENT roots over DIFFERENT event vocabularies. PoSP
carries both as named fields, either honestly None — "the events_root" without a name is ambiguous.

VERDICTS (closed enum, fail-closed):
  SYNCHRONIZED      both surfaces present AND both carry the wrapper's session_id VERIFIED
  PARTIAL_SURFACES  >=1 surface present but not both id-verified (incl. pre-U1 artifacts with a null id —
                    bound by label+span with an explicit note, NEVER silently promoted)
  UNVERIFIABLE      no session_id, nothing to bind, or an ID MISMATCH (PoSP refuses to assert a join it
                    cannot verify — the anti-assertion rail; a mismatch is never papered into PARTIAL)

Cross-lobe latency stays UNCALIBRATED wherever it rides (inherited from KAS, gated on the USB-direct
calibration capture). verifier_independence semantics inherit unchanged: everything here is self-witnessed
by the same rig, so nothing PoSP binds reaches independent-verifier status today. PURE stdlib.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Optional

POSP_SCHEMA = "qortroller-posp-v0"           # CANDIDATE schema string (D-CERT-5.3) — NOT a domain tag

SYNCHRONIZED = "SYNCHRONIZED"
PARTIAL_SURFACES = "PARTIAL_SURFACES"
UNVERIFIABLE = "UNVERIFIABLE"

_MAX_FUSION_REFS = 200                       # cap the carried record_hash list (references, not evidence)


@dataclass
class PoSPRecord:
    """The reference-and-bind wrapper for one session. No commitment method BY DESIGN (see module doc)."""
    schema: str
    verdict: str
    session_id: Optional[str]
    session_display: Optional[str]
    device_id: Optional[str]
    span_ms: Optional[list]
    kas: Optional[dict]                      # {commitment, verdict, authored_kills, id_verified, note?}
    fusion: Optional[dict]                   # {n_rows, n_id_verified, record_hashes[<=cap], id_verified}
    events_roots: dict = field(default_factory=dict)   # {kas_session_root, retina_perception_root} — NAMED
    archive: Optional[dict] = None           # {manifest_schema, count, dir, id_verified}
    notes: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"schema": self.schema, "verdict": self.verdict, "session_id": self.session_id,
                "session_display": self.session_display, "device_id": self.device_id,
                "span_ms": self.span_ms, "kas": self.kas, "fusion": self.fusion,
                "events_roots": self.events_roots, "archive": self.archive, "notes": self.notes}

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, sort_keys=True)


def _surface_id_check(surface_sid, wrapper_sid: str, name: str, notes: list):
    """Tri-state per-surface id verification: True (verified) / False (MISMATCH — poisons the whole
    record) / None (surface predates U1 / carries no id — honest partial, noted)."""
    if surface_sid is None or surface_sid == "":
        notes.append(f"{name}: no session_id on the artifact (pre-U1) — bound by label/span, NOT id-verified")
        return None
    if str(surface_sid) != wrapper_sid:
        notes.append(f"{name}: session_id MISMATCH ({str(surface_sid)[:16]}… != {wrapper_sid[:16]}…)")
        return False
    return True


def build_posp(*, session_id: Optional[str], session_display: Optional[str] = None,
               kas_record: Optional[dict] = None,
               fusion_rows: Optional[list] = None,
               archive_manifest: Optional[dict] = None,
               retina_perception_root: Optional[str] = None) -> PoSPRecord:
    """Bind one session's surfaces. `kas_record` is a KAS to_dict; `fusion_rows` are nqpv_cocapture_log
    rows; `archive_manifest` is the tier-1 manifest.json dict. FAIL-CLOSED: no session_id or nothing to
    bind -> UNVERIFIABLE; any id mismatch -> UNVERIFIABLE (never assert an unverifiable join)."""
    notes: list = []
    if not session_id:
        return PoSPRecord(schema=POSP_SCHEMA, verdict=UNVERIFIABLE, session_id=None,
                          session_display=session_display, device_id=None, span_ms=None, kas=None,
                          fusion=None, notes=["unverifiable: no session_id (the U1 join key) supplied"])
    sid = str(session_id)

    kas = fusion = archive = None
    span = None
    device_id = None
    checks: list = []

    if kas_record:
        ok = _surface_id_check(kas_record.get("session_id"), sid, "kas", notes)
        checks.append(ok)
        kas = {"commitment": kas_record.get("commitment"), "verdict": kas_record.get("verdict"),
               "authored_kills": kas_record.get("authored_kills"),
               "kas_domain_tag": kas_record.get("kas_domain_tag"), "id_verified": bool(ok)}
        span = kas_record.get("span_ms")

    if fusion_rows:
        verified = [r for r in fusion_rows if str(r.get("session_id") or "") == sid]
        others = [r for r in fusion_rows if r.get("session_id") not in (None, "") and
                  str(r.get("session_id")) != sid]
        if others:
            notes.append(f"fusion: {len(others)} row(s) carry a DIFFERENT session_id")
            checks.append(False)
        else:
            checks.append(True if verified else None)
            if not verified:
                notes.append("fusion: rows present but none id-verified (pre-U1 rows) — NOT id-verified")
        hashes = [r.get("record_hash_hex") for r in (verified or fusion_rows)
                  if r.get("record_hash_hex")][:_MAX_FUSION_REFS]
        dev_ids = {r.get("device_id") for r in (verified or fusion_rows) if r.get("device_id")}
        if len(dev_ids) == 1:
            device_id = next(iter(dev_ids))
        elif len(dev_ids) > 1:
            notes.append(f"fusion: {len(dev_ids)} distinct device_ids in the session's rows")
        fusion = {"n_rows": len(fusion_rows), "n_id_verified": len(verified),
                  "record_hashes": hashes, "id_verified": bool(verified) and not others}

    if archive_manifest:
        ok = _surface_id_check(archive_manifest.get("session_id"), sid, "archive", notes)
        # archive is provenance, not one of the two PROOF surfaces — a mismatch still poisons (False),
        # but a verified archive alone never makes the verdict SYNCHRONIZED.
        if ok is False:
            checks.append(False)
        archive = {"manifest_schema": archive_manifest.get("schema"),
                   "count": archive_manifest.get("count"), "id_verified": bool(ok)}

    if any(c is False for c in checks):
        verdict = UNVERIFIABLE                     # a mismatch is never papered over
    elif kas and fusion and kas["id_verified"] and fusion["id_verified"]:
        verdict = SYNCHRONIZED
    elif kas or fusion:
        verdict = PARTIAL_SURFACES
    else:
        verdict = UNVERIFIABLE
        notes.append("unverifiable: no KAS record and no fusion rows to bind")

    return PoSPRecord(schema=POSP_SCHEMA, verdict=verdict, session_id=sid,
                      session_display=session_display, device_id=device_id, span_ms=span,
                      kas=kas, fusion=fusion,
                      events_roots={"kas_session_root": (kas_record or {}).get("events_root"),
                                    "retina_perception_root": retina_perception_root},
                      archive=archive, notes=notes)
