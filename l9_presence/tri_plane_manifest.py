"""TPF-1 F1/F3 - tri-plane session manifest (sidecar, REFERENCE-AND-BIND + earned hard join).

Federates QorTroller's three planes into ONE session object WITHOUT mutating any
artifact: it cites the ASSERTION + OBSERVATION plane (the PoSP record, by session_id
plus its two named roots) and the MEANING plane (the WMP bundle, by bundle_hash).
Each plane stays independently verifiable; NONE asserts in another's lane -
federation, not conflation (observation may suggest; only assertion may claim;
meaning belongs to the gamer).

JOIN HONESTY (grounded F0/F1/F3 on real M17; fork semantics per D-CDM-1, operator-decided
2026-07-12 via the A2A-CDM loop):
  assertion <-> observation : CRYPTOGRAPHIC - both roots live under one session_id in the PoSP.
  meaning   <-> session     : REFERENCE_ATTESTED by default (the WMP bundle carries no
                              session_id, so it binds by bundle_hash + an explicit operator
                              attestation). UPGRADES to CRYPTOGRAPHIC only when the PoSP carries
                              a poac_chain_root byte-equal to the bundle's poacChainRoot (F3) -
                              earned by a verified root match, never asserted. If both roots are
                              present and DISAGREE -> CONTENT_FORK, terminal fail-closed on the
                              JOINED object (plane-local artifacts stay verifiable).

F3 hard-join (BUILT as mechanism, gated on data). The WMP bundle exposes poacChainRoot (its
FROZEN Groth16 public input, INV-VHR-005) as a BN254 field element. F3 grounding CORRECTED the
optimistic F1 assumption: the PoSP's KAS commitment is a SHA-256 over KAS-domain data, NOT the
Arc-5 Poseidon PoAC-chain root - different domain, cannot byte-match. So the hard join requires
the PoSP to ALSO carry the SAME Arc-5 poac_chain_root the replay pipeline computes; then
poac_chain_join() byte-compares the two planes and the meaning join earns CRYPTOGRAPHIC. Absent
(the committed M17, whose PoSP predates the field) it stays honestly REFERENCE_ATTESTED - and a
CRYPTOGRAPHIC claim without a verified match is REJECTED by verify (defeats the S4 splice).
Activation: a live PoSP carries poac_chain_root at mint (daemon wiring), or M17 is re-derived
from bridge_match17.db offline (DB-gated).

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
# D-CDM-1 (operator-decided 2026-07-12): when BOTH planes carry poac_chain_roots and they
# DISAGREE, the joined object is terminal fail-closed - the cryptographic evidence
# contradicts the same-session attestation, so no "attested" label survives. Plane-local
# objects (PoSP, WMP bundle) stay independently verifiable - the TO's plane-split escape.
JOIN_CONTENT_FORK = "CONTENT_FORK"

# Fields that only the ASSERTION plane may carry (the separation law, machine-checked).
_ASSERTING_FIELDS = frozenset({"verdict", "authored_kills", "claim", "asserts", "presence_score"})

# F3 hard-join result taxonomy.
POAC_VERIFIED_MATCH = "VERIFIED_MATCH"   # both planes carry byte-equal PoAC-chain roots
POAC_MISMATCH = "MISMATCH"               # a real cross-plane inconsistency (a splice)
POAC_ABSENT = "ABSENT"                   # one side has no poac_chain_root yet (M17 - honest defer)


def _norm_root(x):
    """Normalize a PoAC-chain root to a canonical int (BN254 field element),
    representation-robust across decimal str / int / 0x-hex. None if absent/unparseable."""
    if x is None:
        return None
    try:
        if isinstance(x, str):
            s = x.strip()
            return int(s, 16) if s.lower().startswith("0x") else int(s)
        return int(x)
    except (ValueError, TypeError):
        return None


def poac_chain_join(assertion_root, meaning_root) -> str:
    """F3: do the assertion plane (PoSP) and the meaning plane (WMP bundle) reference the
    SAME PoAC chain? VERIFIED_MATCH only when BOTH roots are present and byte-equal as BN254
    field elements - the cryptographic upgrade the meaning join must EARN, never assert.
    ABSENT when either side lacks a poac_chain_root (today's committed M17 - the join stays
    honestly attested). MISMATCH is a caught splice. Pure; no PoAC/228B/chain contact."""
    a = _norm_root(assertion_root)
    m = _norm_root(meaning_root)
    if a is None or m is None:
        return POAC_ABSENT
    return POAC_VERIFIED_MATCH if a == m else POAC_MISMATCH


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
    posp_poac_root = posp.get("poac_chain_root")   # F3: optional Arc-5 PoAC-chain root on the PoSP side
    pub = wmp_bundle.get("humanity_proof_public_inputs") or {}
    wmp_poac_root = pub.get("poacChainRoot")

    ao_join = (JOIN_CRYPTOGRAPHIC if (session_id and kas_root and ret_root)
               else JOIN_INCOMPLETE)
    # F3: the meaning join EARNS CRYPTOGRAPHIC only when the PoSP carries a poac_chain_root
    # that byte-matches the WMP bundle's poacChainRoot (both planes over the same PoAC chain).
    # Absent -> it stays attested/unattested (the join is never asserted, only earned).
    # MISMATCH -> CONTENT_FORK (D-CDM-1 fail-closed): contradicted attestation never reads
    # "attested" - the joined object is terminal; plane-local objects verify independently.
    poac_join = poac_chain_join(posp_poac_root, wmp_poac_root)
    if poac_join == POAC_VERIFIED_MATCH:
        meaning_join = JOIN_CRYPTOGRAPHIC
    elif poac_join == POAC_MISMATCH:
        meaning_join = JOIN_CONTENT_FORK
    elif attested_same_session:
        meaning_join = JOIN_REFERENCE_ATTESTED
    else:
        meaning_join = JOIN_UNATTESTED

    manifest = {
        "schema": SCHEMA,
        "generated_at": generated_at,
        "session_id": session_id,
        "planes": {
            "assertion": {"source": "posp", "session_id": session_id,
                          "kas_session_root": kas_root, "poac_chain_root": posp_poac_root,
                          "verdict": posp.get("verdict")},
            "observation": {"source": "posp", "session_id": session_id,
                            "retina_perception_root": ret_root,
                            "note": "advisory; commitment-referenced; may suggest, never assert"},
            "meaning": {"source": "wmp", "bundle_hash": _bundle_hash(wmp_bundle),
                        "poac_chain_root": wmp_poac_root,
                        "consent_gamer_address": wmp_bundle.get("consent_gamer_address"),
                        "note": "gamer-owned; certified-human data; joins by reference + attestation"},
        },
        "join_status": {"assertion_observation": ao_join, "meaning_session": meaning_join,
                        "poac_chain_join": poac_join},
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

    # F3 HONESTY: the meaning join MAY now be CRYPTOGRAPHIC - but ONLY when the assertion +
    # meaning planes carry byte-equal poac_chain_roots (same PoAC chain). A CRYPTOGRAPHIC claim
    # without that verified match is an overclaim and is REJECTED (defeats the S4 meaning splice).
    if js.get("meaning_session") == JOIN_CRYPTOGRAPHIC:
        a_root = (planes.get("assertion") or {}).get("poac_chain_root")
        m_root = (planes.get("meaning") or {}).get("poac_chain_root")
        ok &= _chk("meaning_join_honest", poac_chain_join(a_root, m_root) == POAC_VERIFIED_MATCH,
                   "CRYPTOGRAPHIC meaning join requires byte-equal poac_chain_roots on both planes")
    else:
        ok &= _chk("meaning_join_honest", True, "meaning<->session attested/unattested (honest)")

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

    # CONTENT-FORK rail (D-CDM-1). ARTIFACT-DERIVED roots are AUTHORITATIVE when artifacts are
    # supplied (Round-07 T1-A2/A1 fix): a forger who deletes the plane roots while the real PoSP
    # + bundle still DISAGREE is now CAUGHT - the fork is read from the artifacts, not the
    # producer's plane fields. With no artifacts, the planes' own declared roots are used (the
    # original artifact-free rail). A fork is terminal either way; fail-closed beats false-comfort.
    a_root_plane = (planes.get("assertion") or {}).get("poac_chain_root")
    m_root_plane = (planes.get("meaning") or {}).get("poac_chain_root")
    wroot = None
    if wmp_bundle is not None:
        wroot = (wmp_bundle.get("humanity_proof_public_inputs") or {}).get("poacChainRoot")
    a_root = posp.get("poac_chain_root") if (posp is not None
             and posp.get("poac_chain_root") is not None) else a_root_plane
    m_root = wroot if wroot is not None else m_root_plane
    ok &= _chk("content_fork", poac_chain_join(a_root, m_root) != POAC_MISMATCH,
               "assertion + meaning poac_chain_roots present and unequal -> terminal (D-CDM-1); "
               "artifact-derived roots authoritative when artifacts supplied")

    # BINDING (optional artifacts): assertion binds to the PoSP; meaning to the bundle.
    if posp is not None:
        a = planes.get("assertion") or {}
        ok &= _chk("assertion_binds_posp",
                   a.get("session_id") == posp.get("session_id")
                   and a.get("kas_session_root") == (posp.get("events_roots") or {}).get("kas_session_root"),
                   "assertion plane must cite this PoSP")
        # Round-07 T1-A2: a plane that DECLARES a root may not disagree with the artifact's.
        if a_root_plane is not None:
            ok &= _chk("assertion_root_matches_posp",
                       _norm_root(a_root_plane) == _norm_root(posp.get("poac_chain_root")),
                       "assertion plane poac_chain_root must equal the PoSP's")
    if wmp_bundle is not None:
        m = planes.get("meaning") or {}
        ok &= _chk("meaning_binds_bundle", m.get("bundle_hash") == _bundle_hash(wmp_bundle),
                   "meaning plane must cite this WMP bundle by hash")
        if m_root_plane is not None:
            ok &= _chk("meaning_root_matches_bundle",
                       _norm_root(m_root_plane) == _norm_root(wroot),
                       "meaning plane poac_chain_root must equal the bundle's public input")

    return {"ok": bool(ok), "checks": checks, "manifest_hash": manifest.get("manifest_hash")}


def consumer_status(manifest: dict, verify_result: dict = None) -> dict:
    """Q4-P4 multi-status consumer surface (D-CDM-1 companion): NEVER a single boolean -
    neither a TO nor a data buyer gets one green light to misuse. Names adapted from grok's
    Round-04 proposal: JOINED_* instead of SYNCHRONIZED to avoid colliding with the PoSP
    verdict enum (separation discipline applies to naming too).

    joined_status: JOINED_VERIFIED (earned cryptographic meaning join) / JOINED_ATTESTED
    (reference + operator attestation) / JOINED_PARTIAL (unattested or incomplete) /
    CONTENT_FORK (terminal - D-CDM-1) / UNVERIFIABLE (verify failed for any other reason)."""
    js = manifest.get("join_status") or {}
    meaning = js.get("meaning_session")
    verified = bool(verify_result["ok"]) if verify_result is not None else None

    # Round-07 T2-A1: recompute the fork from the planes' own roots ALWAYS - never trust the
    # producer's label alone (a skim-reader calling consumer_status() without first running
    # verify_tri_plane_manifest must still see a fork), and honor CRYPTOGRAPHIC only when the
    # roots actually match (or a passing verify_result vouches for it).
    planes = manifest.get("planes") or {}
    plane_join = poac_chain_join((planes.get("assertion") or {}).get("poac_chain_root"),
                                 (planes.get("meaning") or {}).get("poac_chain_root"))
    verify_fork = (verify_result is not None and not verified
                   and any(c["name"] == "content_fork" and not c["ok"]
                           for c in verify_result.get("checks", [])))

    if meaning == JOIN_CONTENT_FORK or plane_join == POAC_MISMATCH or verify_fork:
        joined = "CONTENT_FORK"
    elif verify_result is not None and not verified:
        joined = "UNVERIFIABLE"
    elif meaning == JOIN_CRYPTOGRAPHIC:
        joined = "JOINED_VERIFIED" if (plane_join == POAC_VERIFIED_MATCH or verified) else "UNVERIFIABLE"
    elif meaning == JOIN_REFERENCE_ATTESTED:
        joined = "JOINED_ATTESTED"
    else:
        joined = "JOINED_PARTIAL"

    return {
        "humanity_plane": (manifest.get("planes") or {}).get("assertion", {}).get("verdict"),
        "observation_plane": js.get("assertion_observation"),
        "joined_status": joined,
        "poac_chain_join": js.get("poac_chain_join"),
        "note": "plane-local artifacts (PoSP / WMP bundle) verify independently of joined_status",
    }
