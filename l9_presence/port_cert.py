"""PORT-CERT — portable, independently re-verifiable Match Certificate (qortroller-match-certificate-v0).

THE CLAIM: "the cryptographic claims of ONE match — PoSP SYNCHRONIZED, authorship (KAS/deferred), a
verified VHR zero-knowledge replay proof, and an on-chain anchor of the exact PoSP record — are
composed into a self-contained bundle that a THIRD PARTY (not the rig) can re-verify against PUBLIC
parameters (the Groth16 vkey + the on-chain anchor), WITHOUT the rig and WITHOUT the raw session data."

THE GAP: every current surface is self-witnessed by the same rig (verifier_independence=False). But
that conflates the CAPTURE (rig-generated, not trustless) with the PROOFS (ZK validity, commitment
consistency, session-join, anchor presence — checkable by anyone with the public parameters). PORT-CERT
makes the PROOFS portable; it does NOT make the capture trustless.

REFERENCE-AND-BIND (PoSP/KAS precedent, D-CERT-6): NO new commitment primitive, NO domain tag, NO
FROZEN-v1 family. Schema string only. The bundle REFERENCES the surfaces' existing commitments and
carries the ZK public inputs (zero-knowledge safe — no raw data). Integrity derives from what a
verifier RE-COMPUTES: the Groth16 proof, the PoSP-file SHA-256 vs the anchored digest, the session-join.

INJECTED CHECKS (the discipline): the pure verifier NEVER shells snarkjs or reads the chain — it takes
`groth16_verify` and `chain_lookup` as injected callables (the runner supplies them), so this module is
pure + deterministic and the network/subprocess blast radius is one script. Absent an injected check the
verifier reports UNCHECKED (-> PARTIAL), never a false VERIFIED. PURE stdlib. HONEST SCOPE §3 of
docs/port-cert-design-2026-07-09.md: cross-trust-boundary RE-verifiability, NOT witness independence.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Callable, Optional

MATCH_CERT_SCHEMA = "qortroller-match-certificate-v0"     # schema string — NOT a domain tag / FROZEN-v1

_POSP_SYNCHRONIZED = "SYNCHRONIZED"
_KAS_AUTHORED = "AUTHORED_SESSION"
_DEFERRED_AUTHORED = "DEFERRED_AUTHORED_SESSION"


# ------------------------------------------------------------------------------------- builder
def _posp_surface(posp: dict) -> dict:
    return {"verdict": posp.get("verdict"), "session_id": posp.get("session_id"),
            "device_id": posp.get("device_id"), "file_sha256": posp.get("file_sha256"),
            "record_path": posp.get("record_path")}


def build_match_certificate(*, posp: dict, kas: Optional[dict] = None, deferred: Optional[dict] = None,
                            vhr: Optional[dict] = None, anchor: Optional[dict] = None,
                            consent: Optional[dict] = None) -> dict:
    """Assemble a Match Certificate from the session's already-produced artifacts. REFERENCE-ONLY —
    carries verdicts, commitments, ZK public inputs and the anchor ref; NEVER raw frames/crops/matrix.
    `posp` should carry a `file_sha256` (the published-record digest) + optional `record_path`."""
    session_id = posp.get("session_id")
    surfaces: dict = {"posp": _posp_surface(posp)}
    surfaces["kas"] = ({"commitment": kas.get("commitment"), "verdict": kas.get("verdict"),
                        "session_id": kas.get("session_id")} if kas else None)
    surfaces["deferred"] = ({"verdict": deferred.get("verdict"),
                             "deferred_authored": deferred.get("deferred_authored"),
                             "session_id": deferred.get("session_id")} if deferred else None)
    surfaces["vhr"] = (dict(vhr) if vhr else None)         # {replay_proof_token, public_inputs[], roots, refs}
    surfaces["anchor"] = (dict(anchor) if anchor else None)
    surfaces["consent"] = (dict(consent) if consent else None)
    return {
        "schema": MATCH_CERT_SCHEMA,
        "session_id": session_id,
        "advisory": True,
        "cert_scope": "developer_self",
        "population_certified": False,
        # the CAPTURE stays rig-witnessed; PORT-CERT makes only the PROOFS portable
        "verifier_independence": False,
        "surfaces": surfaces,
    }


# ------------------------------------------------------------------------------------- verifier
@dataclass(slots=True)
class CheckResult:
    name: str
    passed: Optional[bool]        # True / False / None (UNCHECKED — no injected checker)
    note: str


@dataclass
class MatchCertVerificationReport:
    schema_found: Optional[str]
    session_id: Optional[str]
    checks: list = field(default_factory=list)
    overall: str = "UNVERIFIED"   # VERIFIED / PARTIAL / FAILED / SCHEMA_ERROR

    def passed(self) -> bool:
        return self.overall == "VERIFIED"

    def to_dict(self) -> dict:
        return {"schema_found": self.schema_found, "session_id": self.session_id,
                "overall": self.overall,
                "checks": [{"name": c.name, "passed": c.passed, "note": c.note} for c in self.checks]}


def _sha256_hex(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def verify_match_certificate(cert: dict, *, posp_file_bytes: Optional[bytes] = None,
                             groth16_verify: Optional[Callable[[dict], bool]] = None,
                             chain_lookup: Optional[Callable[[str], bool]] = None
                             ) -> MatchCertVerificationReport:
    """Off-rig verifier. Hard checks (C2/C3/C4 + C5 when injected) gate FAILED; UNCHECKED checks
    (no snarkjs / no chain RPC) gate PARTIAL — never a false VERIFIED. See design §2."""
    rep = MatchCertVerificationReport(schema_found=(cert or {}).get("schema"),
                                      session_id=(cert or {}).get("session_id"))
    checks = rep.checks

    def chk(name, passed, note):
        checks.append(CheckResult(name, passed, note))

    # C1 schema
    if not isinstance(cert, dict) or cert.get("schema") != MATCH_CERT_SCHEMA:
        chk("schema", False, f"schema={cert.get('schema') if isinstance(cert, dict) else type(cert).__name__!r}")
        rep.overall = "SCHEMA_ERROR"
        return rep
    chk("schema", True, MATCH_CERT_SCHEMA)

    sid = cert.get("session_id")
    surf = cert.get("surfaces") or {}
    posp = surf.get("posp") or {}
    anchor = surf.get("anchor") or {}
    vhr = surf.get("vhr") or {}

    # C2 session join — every PRESENT surface carries the cert's session_id (anti-splice)
    join_ok = bool(sid)
    mism = []
    for name in ("posp", "kas", "deferred"):
        s = surf.get(name)
        if s and s.get("session_id") not in (None, "", sid):
            join_ok = False
            mism.append(name)
    chk("session_join", join_ok,
        "all surfaces share session_id" if join_ok else f"session_id mismatch in {mism or 'missing sid'}")

    # C3 PoSP SYNCHRONIZED
    posp_ok = posp.get("verdict") == _POSP_SYNCHRONIZED
    chk("posp_synchronized", posp_ok, f"posp.verdict={posp.get('verdict')!r}")

    # C4 anchor-digest match — the exact published PoSP file is the one anchored on-chain.
    # tri-state: True / False (hard fail) / None (UNCHECKED — no anchor and no file to compare)
    dig = posp.get("file_sha256")
    anchor_dig = anchor.get("digest")
    c4: Optional[bool]
    if posp_file_bytes is not None:
        recomputed = _sha256_hex(posp_file_bytes)
        c4 = (recomputed == dig) and (dig is not None) and (anchor_dig in (None, dig))
        chk("anchor_digest_match", c4,
            f"sha256(posp file)={recomputed[:16]}.. vs cert={str(dig)[:16]}.. / anchor={str(anchor_dig)[:16]}..")
    elif anchor:
        c4 = (dig is not None) and (anchor_dig is not None) and (dig == anchor_dig)
        chk("anchor_digest_match", c4, "posp.file_sha256 == anchor.digest (offline consistency)")
    else:
        c4 = None
        chk("anchor_digest_match", None, "no anchor surface and no posp file supplied (UNCHECKED)")

    # C5 VHR ZK proof — injected snarkjs verify (the runner shells it). tri-state.
    c5: Optional[bool]
    if not vhr:
        c5 = None
        chk("vhr_zk_proof", None, "no vhr surface (UNCHECKED)")
    elif groth16_verify is None:
        c5 = None
        chk("vhr_zk_proof", None, "no groth16_verify injected (UNCHECKED — run via scripts/match_certificate.py)")
    else:
        try:
            c5 = bool(groth16_verify(vhr))
        except Exception as e:                      # noqa: BLE001 — a verifier error is a FAIL, not a crash
            c5 = False
            chk("vhr_zk_proof", False, f"groth16_verify raised: {e}")
        else:
            chk("vhr_zk_proof", c5, "snarkjs groth16 verify OK" if c5 else "snarkjs groth16 verify FALSE")

    # C6 anchor on-chain — injected chain lookup (read-only). tri-state.
    tx = anchor.get("tx")
    c6: Optional[bool]
    if chain_lookup is None or not tx:
        c6 = None
        chk("anchor_onchain", None, "no chain_lookup injected or no tx (UNCHECKED)")
    else:
        try:
            c6 = bool(chain_lookup(tx))
        except Exception as e:                      # noqa: BLE001
            c6 = False
            chk("anchor_onchain", False, f"chain_lookup raised: {e}")
        else:
            chk("anchor_onchain", c6, "anchor tx present on-chain" if c6 else "anchor tx NOT found")

    # C7 authorship (advisory note only — never gates overall)
    kas = surf.get("kas") or {}
    deferred = surf.get("deferred") or {}
    authored = kas.get("verdict") == _KAS_AUTHORED or deferred.get("verdict") == _DEFERRED_AUTHORED
    chk("authorship", authored, f"kas={kas.get('verdict')!r} deferred={deferred.get('verdict')!r}")

    # ---- overall: hard gates C2/C3/C4/C5; any False -> FAILED; any UNCHECKED -> PARTIAL; else VERIFIED ----
    hard = [join_ok, posp_ok, c4, c5]
    if any(v is False for v in hard):
        rep.overall = "FAILED"
    elif any(v is None for v in hard) or c6 is None:
        # a hard check couldn't be run (no snarkjs / no anchor / no chain RPC) -> honest PARTIAL
        rep.overall = "PARTIAL"
    else:
        rep.overall = "VERIFIED"
    return rep


def load_and_verify(path: str, **kw) -> MatchCertVerificationReport:
    """Convenience: load a certificate JSON and verify it (injected checks via kw). Fail-open on I/O."""
    try:
        with open(path, encoding="utf-8") as fh:
            cert = json.load(fh)
    except Exception as e:                          # noqa: BLE001
        rep = MatchCertVerificationReport(schema_found=None, session_id=None)
        rep.checks.append(CheckResult("load", False, f"cannot load {path!r}: {e}"))
        rep.overall = "SCHEMA_ERROR"
        return rep
    return verify_match_certificate(cert, **kw)
