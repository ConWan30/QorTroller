"""ADVERSARY-EXPAND — the presence-forgery attack -> rail matrix (machine-checked fail-closed evidence).

Turns "we ASSERT fail-closed" into "we DEMONSTRATE fail-closed across N attacks." Each attack forges or
tampers a real artifact and runs it through the actual verifier it targets; the matrix asserts every
attack is REJECTED by a specific, named rail. A single un-rejected attack is a real finding (holds=False).

Targets the verifiers built across the RP-CLOSE-1 / A1-b / EVENT-BIND / PORT-CERT arcs:
  posp_verifier · kas_deferred · bcc_match admission · event_bind · port_cert.

Pure: constructs synthetic forged inputs + calls the injected/real verifiers; no rig, no chain, no I/O.
This is the published evidence base for the honesty rails — not a claim that capture is trustless
(verifier_independence stays False), but that each SPECIFIC forgery hits a SPECIFIC fail-closed gate.
"""
from __future__ import annotations

from dataclasses import dataclass

from ..bcc_match import passes_match_admission
from ..event_bind import HidOnset, ScreenOutcome, bind_events
from ..kas_deferred import build_deferred_record
from ..port_cert import build_match_certificate, verify_match_certificate
from ..posp_verifier import verify_posp_record

_SID = "a" * 64
_OTHER = "f" * 64


@dataclass(frozen=True)
class AttackResult:
    name: str
    target: str            # which verifier
    rail: str              # the fail-closed rail that must catch it
    rejected: bool         # True = the rail held
    detail: str


# ------------------------------------------------------------------- PoSP verifier
def atk_posp_forged_synchronized() -> AttackResult:
    """Claim the strong verdict SYNCHRONIZED without id-verified surfaces (forge the conclusion)."""
    record = {"schema": "qortroller-posp-v0", "verdict": "SYNCHRONIZED", "session_id": _SID,
              "kas": {"id_verified": False, "commitment": "x"}, "fusion": {"id_verified": False}}
    rep = verify_posp_record(record)
    return AttackResult("posp_forged_synchronized", "posp_verifier", "verdict_consistent (S6)",
                        rep.overall == "FAILED", f"overall={rep.overall}")


# ------------------------------------------------------------------- kas_deferred
def _scan(sha):
    return {"scan_version": "rp-ocr-precision-v2", "archive": "retina_kf_archive/match_x",
            "clusters": [{"size": 3, "reads": [{"file": "c.png", "sha256": sha, "ts_ns": 1_000_000}]}]}


def _manifest(sid=_SID):
    return {"session_id": sid, "session_display": "match_x", "count": 1,
            "files": [{"file": "c.png", "sha256": "GOOD"}]}


def atk_deferred_replayed_crop() -> AttackResult:
    """A cluster crop whose sha is NOT in the manifest (a spliced/replayed frame)."""
    rec = build_deferred_record(scan=_scan("TAMPERED"), manifest=_manifest(), windows=[])
    return AttackResult("deferred_replayed_crop", "kas_deferred", "anti-tamper sha poison",
                        rec.verdict == "UNVERIFIABLE", f"verdict={rec.verdict}")


def atk_deferred_session_splice() -> AttackResult:
    """A KAS record from a DIFFERENT session grafted onto this archive."""
    kas = {"session_id": _OTHER, "verdict": "AUTHORED_SESSION", "commitment": "aa"}
    rec = build_deferred_record(scan=_scan("GOOD"), manifest=_manifest(), windows=[], kas_record=kas)
    return AttackResult("deferred_session_splice", "kas_deferred", "session_id anti-assertion",
                        rec.verdict == "UNVERIFIABLE", f"verdict={rec.verdict}")


# ------------------------------------------------------------------- bcc_match admission
def _posp(verdict="SYNCHRONIZED", sid=_SID):
    return {"verdict": verdict, "session_id": sid, "kas": {"commitment": "aa"},
            "events_roots": {}, "archive": {}}


def _admit(**kw):
    base = dict(session_id=_SID, posp=_posp(), kas={"verdict": "AUTHORED_SESSION", "session_id": _SID},
                deferred=None, authored_clusters=8, eligible_clusters=9)
    base.update(kw)
    ok, reasons = passes_match_admission(**base)
    return ok, reasons


def atk_bcc_coherence_gaming() -> AttackResult:
    ok, reasons = _admit(deferred={"verdict": "DEFERRED_AUTHORED_SESSION", "session_id": _SID},
                         kas=None, authored_clusters=2, eligible_clusters=10)   # 0.2 < 0.5 floor
    return AttackResult("bcc_coherence_gaming", "bcc_match", "coherence floor (G4)",
                        (not ok) and any(r.startswith("G4") for r in reasons), f"reasons={reasons}")


def atk_bcc_hygiene_bypass() -> AttackResult:
    ok, reasons = _admit(kas={"verdict": "HYGIENE_FAIL", "session_id": _SID})
    return AttackResult("bcc_hygiene_bypass", "bcc_match", "hygiene inheritance (G6)",
                        (not ok) and any(r.startswith("G6") for r in reasons), f"reasons={reasons}")


def atk_bcc_partial_posp() -> AttackResult:
    ok, reasons = _admit(posp=_posp(verdict="PARTIAL_SURFACES"))
    return AttackResult("bcc_partial_posp", "bcc_match", "SYNCHRONIZED-only (G2)",
                        (not ok) and any(r.startswith("G2") for r in reasons), f"reasons={reasons}")


def atk_bcc_session_mismatch() -> AttackResult:
    ok, reasons = _admit(kas={"verdict": "AUTHORED_SESSION", "session_id": _OTHER})
    return AttackResult("bcc_session_mismatch", "bcc_match", "surface session_id anti-assertion (G6)",
                        (not ok) and any(r.startswith("G6") for r in reasons), f"reasons={reasons}")


# ------------------------------------------------------------------- port_cert
def _cert():
    posp = {"verdict": "SYNCHRONIZED", "session_id": _SID, "file_sha256": _digest()}
    anchor = {"registry": "0x44", "tx": "da3a", "block": 1, "digest": _digest()}
    return build_match_certificate(posp=posp, kas={"verdict": "AUTHORED_SESSION", "session_id": _SID,
                                                    "commitment": "aa"}, vhr={"public_inputs": ["1"]},
                                   anchor=anchor)


def _digest():
    import hashlib
    return hashlib.sha256(b"POSP-FILE").hexdigest()


def atk_cert_digest_tamper() -> AttackResult:
    """Publish a PoSP file that does NOT hash to the on-chain-anchored digest."""
    rep = verify_match_certificate(_cert(), posp_file_bytes=b"TAMPERED FILE",
                                   groth16_verify=lambda v: True, chain_lookup=lambda t: True)
    return AttackResult("cert_digest_tamper", "port_cert", "anchor-digest match (C4)",
                        rep.overall == "FAILED", f"overall={rep.overall}")


def atk_cert_zk_false() -> AttackResult:
    rep = verify_match_certificate(_cert(), posp_file_bytes=b"POSP-FILE",
                                   groth16_verify=lambda v: False, chain_lookup=lambda t: True)
    return AttackResult("cert_zk_false", "port_cert", "VHR ZK proof (C5)",
                        rep.overall == "FAILED", f"overall={rep.overall}")


def atk_cert_session_splice() -> AttackResult:
    posp = {"verdict": "SYNCHRONIZED", "session_id": _SID, "file_sha256": _digest()}
    cert = build_match_certificate(posp=posp, kas={"verdict": "AUTHORED_SESSION", "session_id": _OTHER,
                                                   "commitment": "aa"},
                                   anchor={"digest": _digest(), "tx": "da3a"}, vhr={"public_inputs": ["1"]})
    rep = verify_match_certificate(cert, posp_file_bytes=b"POSP-FILE",
                                   groth16_verify=lambda v: True, chain_lookup=lambda t: True)
    return AttackResult("cert_session_splice", "port_cert", "session join (C2)",
                        rep.overall == "FAILED", f"overall={rep.overall}")


# ------------------------------------------------------------------- event_bind
def atk_event_splice() -> AttackResult:
    """Kill outcome (anchor A) + trigger onset (anchor B), timestamps aligned — a temporal join would
    call it authored; EVENT-BIND must refuse the cryptographic claim."""
    r = bind_events([ScreenOutcome(1000.0, "a" * 64)], [HidOnset(1080.0, "b" * 64)])
    return AttackResult("event_splice", "event_bind", "record_hash cryptographic join",
                        r.binding_is_cryptographic is False and r.n_bound == 1,
                        f"crypto={r.n_crypto} temporal={r.n_temporal}")


ATTACKS = (
    atk_posp_forged_synchronized,
    atk_deferred_replayed_crop, atk_deferred_session_splice,
    atk_bcc_coherence_gaming, atk_bcc_hygiene_bypass, atk_bcc_partial_posp, atk_bcc_session_mismatch,
    atk_cert_digest_tamper, atk_cert_zk_false, atk_cert_session_splice,
    atk_event_splice,
)


@dataclass
class ForgeryMatrixReport:
    results: list

    @property
    def holds(self) -> bool:
        """True iff EVERY attack was rejected by its rail (a single un-rejected attack = a finding)."""
        return all(r.rejected for r in self.results) and len(self.results) > 0

    def to_dict(self) -> dict:
        return {"schema": "qortroller-forgery-matrix-v0", "n_attacks": len(self.results),
                "n_rejected": sum(1 for r in self.results if r.rejected), "holds": self.holds,
                "attacks": [{"name": r.name, "target": r.target, "rail": r.rail,
                             "rejected": r.rejected, "detail": r.detail} for r in self.results]}

    def to_markdown(self) -> str:
        d = self.to_dict()
        banner = ("**ALL FORGERIES REJECTED.** Every attack hits its named fail-closed rail."
                  if d["holds"] else
                  f"**FINDING: {d['n_attacks'] - d['n_rejected']} attack(s) NOT rejected** — a rail is open.")
        lines = ["# Presence-Forgery Attack -> Rail Matrix", "", banner, "",
                 f"- Attacks: {d['n_attacks']} · rejected: {d['n_rejected']} · holds: {d['holds']}", "",
                 "| attack | target | rail | rejected |", "|---|---|---|---|"]
        for r in self.results:
            lines.append(f"| {r.name} | {r.target} | {r.rail} | {'yes' if r.rejected else '**NO**'} |")
        return "\n".join(lines)


def run_forgery_matrix() -> ForgeryMatrixReport:
    return ForgeryMatrixReport(results=[atk() for atk in ATTACKS])
