"""TPF-1 F1 - tri-plane session manifest (sidecar, REFERENCE-AND-BIND).

Federates QorTroller's three planes into ONE session object WITHOUT mutating any
artifact: it cites the ASSERTION + OBSERVATION plane (the PoSP record, by session_id
plus its two named roots) and the MEANING plane (the WMP bundle, by bundle_hash).
Each plane stays independently verifiable; NONE asserts in another's lane -
federation, not conflation (observation may suggest; only assertion may claim;
meaning belongs to the gamer).

JOIN HONESTY (grounded F0/F1 on real M17):
  assertion <-> observation : CRYPTOGRAPHIC - both roots live under one session_id in
                              the PoSP record.
  meaning   <-> session     : REFERENCE_ATTESTED - the WMP bundle carries no session_id,
                              so the manifest binds it by bundle_hash + an explicit
                              operator attestation, and says 'attested', never 'proven'.

F3 hard-join path (a beneficial catch from F1 grounding, cleaner than re-hashing the
published bundle): the WMP bundle ALREADY exposes poacChainRoot (its FROZEN Groth16
public input, INV-VHR-005), and the PoSP's KAS is committed over the SAME M17 PoAC
records. Surfacing a matching poac_chain_root on the PoSP side would join the meaning
plane CRYPTOGRAPHICALLY without touching the published WMP bundle. Named here; gated.

Pure stdlib + sdk.wmp_verify (bundle hash). No PoAC/228B/chain/FROZEN contact.
"""
from __future__ import annotations

import hashlib
import json

from sdk.wmp_verify import _bundle_hash

SCHEMA = "qortroller-tri-plane-session-v0"

JOIN_CRYPTOGRAPHIC = "CRYPTOGRAPHIC"
JOIN_REFERENCE_ATTESTED = "REFERENCE_ATTESTED"
JOIN_UNATTESTED = "UNATTESTED"
JOIN_INCOMPLETE = "INCOMPLETE"

# Fields that only the ASSERTION plane may carry (the separation law, machine-checked).
_ASSERTING_FIELDS = frozenset({"verdict", "authored_kills", "claim", "asserts", "presence_score"})


def _mhash(manifest: dict) -> str:
    m = {k: v for k, v in manifest.items() if k != "manifest_hash"}
    return hashlib.sha256(json.dumps(m, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def build_tri_plane_manifest(posp: dict, wmp_bundle: dict, *,
                             attested_same_session: bool = False,
                             generated_at: str = "") -> dict:
    """Federate the PoSP (assertion + observation) and the WMP bundle (meaning) under
    one session object. `attested_same_session` is the operator's explicit claim that
    the bundle is from this session (the meaning plane carries no session_id to prove
    it cryptographically yet - see the F3 path in the module docstring)."""
    session_id = posp.get("session_id")
    roots = posp.get("events_roots") or {}
    kas_root = roots.get("kas_session_root")
    ret_root = roots.get("retina_perception_root")
    pub = wmp_bundle.get("humanity_proof_public_inputs") or {}

    ao_join = (JOIN_CRYPTOGRAPHIC if (session_id and kas_root and ret_root)
               else JOIN_INCOMPLETE)
    meaning_join = JOIN_REFERENCE_ATTESTED if attested_same_session else JOIN_UNATTESTED

    manifest = {
        "schema": SCHEMA,
        "generated_at": generated_at,
        "session_id": session_id,
        "planes": {
            "assertion": {"source": "posp", "session_id": session_id,
                          "kas_session_root": kas_root, "verdict": posp.get("verdict")},
            "observation": {"source": "posp", "session_id": session_id,
                            "retina_perception_root": ret_root,
                            "note": "advisory; commitment-referenced; may suggest, never assert"},
            "meaning": {"source": "wmp", "bundle_hash": _bundle_hash(wmp_bundle),
                        "poac_chain_root": pub.get("poacChainRoot"),
                        "consent_gamer_address": wmp_bundle.get("consent_gamer_address"),
                        "note": "gamer-owned; certified-human data; joins by reference + attestation"},
        },
        "join_status": {"assertion_observation": ao_join, "meaning_session": meaning_join},
        "hard_join_path_F3": ("surface poac_chain_root on the PoSP side to match the WMP bundle's "
                              "existing poacChainRoot - CRYPTOGRAPHIC join without re-hashing the "
                              "published bundle"),
        "federation_law": "each plane independently verifiable; none asserts in another's lane",
        "ceiling": ("N=1, developer_self, IoTeX testnet; meaning<->session is ATTESTED not PROVEN "
                    "(F3-gated); federation not conflation; advisory planes stay advisory"),
        "advisory": True,
    }
    manifest["manifest_hash"] = _mhash(manifest)
    return manifest


def verify_tri_plane_manifest(manifest: dict, *, posp: dict = None, wmp_bundle: dict = None) -> dict:
    """Fail-closed. Confirms the manifest is internally honest (never overclaims a join)
    and, when the artifacts are provided, that it binds to them; and pins the separation
    law (observation/meaning planes carry no asserting field)."""
    checks: list = []

    def _chk(name, ok, note=""):
        checks.append({"name": name, "ok": bool(ok), "note": note})
        return bool(ok)

    ok = _chk("schema", manifest.get("schema") == SCHEMA)
    ok &= _chk("manifest_hash", manifest.get("manifest_hash") == _mhash(manifest), "record integrity")
    ok &= _chk("session_id", bool(manifest.get("session_id")), "join key present")
    planes = manifest.get("planes") or {}
    js = manifest.get("join_status") or {}

    # HONESTY: meaning<->session must NOT claim CRYPTOGRAPHIC (no hard join exists yet, F3).
    ok &= _chk("meaning_join_honest", js.get("meaning_session") != JOIN_CRYPTOGRAPHIC,
               "meaning<->session may only be attested/unattested until F3 (never overclaimed)")

    # SEPARATION LAW: only the assertion plane may carry an asserting field.
    sep = True
    for pname in ("observation", "meaning"):
        p = planes.get(pname) or {}
        if any(f in p for f in _ASSERTING_FIELDS):
            sep = False
    ok &= _chk("separation_law", sep, "observation/meaning must not carry an asserting field")

    # SPLICE rail (F4 hardening): the manifest's join key must equal the assertion +
    # observation planes' own session_id - an INTERNAL cross-plane splice (top-level
    # join key disagreeing with the planes it federates) is caught without artifacts.
    a_sid = (planes.get("assertion") or {}).get("session_id")
    o_sid = (planes.get("observation") or {}).get("session_id")
    ok &= _chk("session_consistency",
               manifest.get("session_id") == a_sid and a_sid == o_sid,
               "manifest session_id must match the assertion + observation planes")

    # BINDING (optional artifacts): assertion binds to the PoSP; meaning to the bundle.
    if posp is not None:
        a = planes.get("assertion") or {}
        ok &= _chk("assertion_binds_posp",
                   a.get("session_id") == posp.get("session_id")
                   and a.get("kas_session_root") == (posp.get("events_roots") or {}).get("kas_session_root"),
                   "assertion plane must cite this PoSP")
    if wmp_bundle is not None:
        m = planes.get("meaning") or {}
        ok &= _chk("meaning_binds_bundle", m.get("bundle_hash") == _bundle_hash(wmp_bundle),
                   "meaning plane must cite this WMP bundle by hash")

    return {"ok": bool(ok), "checks": checks, "manifest_hash": manifest.get("manifest_hash")}
