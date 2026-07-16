"""A2A-STEWARD-EVOLVE — HSM attestation of SEL graduation decisions (the governance capstone).

SEL-v0 (B4) scores a steward's task-class and drafts a graduation recommendation; the operator accepts or
rejects; SEL never auto-applies. This module makes a Guardian-notarized, externally verifiable RECORD OF A
DECISION PACKAGE: Guardian's HSM signs a canonical attestation over the package (steward / task-class /
precision / N / thresholds / ACCEPT|REJECT / operator_id / ts_ns) BOUND TO the SEL evidence chain head, and
anyone with Guardian's published public key can later verify — with no access to the bridge — that Guardian
recorded exactly this package unaltered. It does NOT prove the operator personally authorized it (see the
HONEST CLAIM below); `operator_id` is declarative.

HONEST CLAIM (grok round-15 — load-bearing, do not overstate):
  This attests that GUARDIAN's HSM recorded a decision package at ts_ns, bound to SEL chain head H. A
  verifier confirms **Guardian said so** and that the package has not been altered — NOT that the operator
  personally authorized it. `operator_id` is DECLARATIVE metadata; it is bound into the signed preimage (so
  it can't be silently changed after the fact) but the signature does NOT authenticate WHO the operator
  was. True operator non-repudiation requires an operator-held signing key (a v1 upgrade), not Guardian's.

This is an HSM SIGNATURE RECORD, NOT a FROZEN-v1 governance seal and NOT the operator-fired
`--confirm-governance` ceremony. Domain `VAPI-SEL-GRAD-ATTEST-v0` is CANDIDATE. It grants nothing — SEL
still never auto-applies a graduation. 0-IOTX, off-chain. The signer is an INJECTABLE SYNC PORT
(digest->DER) wrapping Guardian's secp256k1 KMS key (async-in-sync is a production footgun); wiring an
operator-acceptance endpoint that fires this is v0.1.
"""
from __future__ import annotations

import hashlib

SCHEMA = "qortroller-sel-grad-attest-v0"
DOMAIN = b"VAPI-SEL-GRAD-ATTEST-v0"      # CANDIDATE — not FROZEN, not the --confirm-governance ceremony
DECISIONS = ("ACCEPT", "REJECT")
_DECISION_BYTE = {"ACCEPT": 0x01, "REJECT": 0x00}


def _lp(b: bytes) -> bytes:
    """4-byte length prefix — same delimiter-collision discipline as the SEL candidate chain."""
    return len(b).to_bytes(4, "big") + b


def build_graduation_attestation_preimage(*, steward: str, task_class: str, precision_milli: int,
                                          n_labels: int, min_samples: int, precision_floor_milli: int,
                                          decision: str, operator_id: str, ts_ns: int,
                                          sel_chain_head_hex: str) -> bytes:
    """The ONE canonical preimage builder. Length-prefixed variable fields; milli-INTS for precision (never
    a float in the record); decision pinned to the enum; SEL chain head (32B) bound so the attestation is
    anchored to the evidence-ledger state it was accepted against (grok round-15 3b). verify re-derives via
    THIS function only."""
    d = str(decision).strip().upper()
    if d not in DECISIONS:
        raise ValueError(f"decision must be ACCEPT or REJECT, got {decision!r}")
    head = bytes.fromhex(sel_chain_head_hex)
    if len(head) != 32:
        raise ValueError(f"sel_chain_head_hex must be 32 bytes, got {len(head)}")
    return (DOMAIN
            + _lp(str(steward).encode()) + _lp(str(task_class).encode())
            + int(precision_milli).to_bytes(8, "big")
            + int(n_labels).to_bytes(4, "big")
            + int(min_samples).to_bytes(4, "big")
            + int(precision_floor_milli).to_bytes(8, "big")
            + bytes([_DECISION_BYTE[d]])
            + _lp(str(operator_id).encode())
            + int(ts_ns).to_bytes(8, "big")
            + head)


_HONEST_NOTE = (
    "HSM ATTESTATION by Guardian that this graduation DECISION package was RECORDED at ts_ns, bound to the "
    "SEL chain head. A verifier with Guardian's published pubkey confirms Guardian signed it and the "
    "package is unaltered — NOT that the operator personally authorized it (operator_id is DECLARATIVE, "
    "bound into the preimage but not authenticated by the signature; true operator non-repudiation needs "
    "an operator key, v1). CANDIDATE VAPI-SEL-GRAD-ATTEST-v0 — not FROZEN, not --confirm-governance. Grants "
    "nothing; SEL still never auto-applies. 0-IOTX, off-chain.")


def attest_graduation(*, steward: str, task_class: str, precision, n_labels: int, min_samples: int,
                      precision_floor, decision: str, operator_id: str, ts_ns: int,
                      sel_chain_head_hex: str, sign_digest, pubkey_hex: str, verify_sig=None) -> dict:
    """Produce a signed graduation attestation record. `sign_digest(digest32) -> DER` is the injected sync
    Guardian signer; `pubkey_hex` is Guardian's published DER-SPKI pubkey (embedded for external verify);
    optional `verify_sig(digest, der) -> bool` round-trips the KMS sig. Draft/record only — no auto-apply,
    no spend, no chain."""
    precision_milli = round(float(precision) * 1000) if precision is not None else 0
    precision_floor_milli = round(float(precision_floor) * 1000)
    preimage = build_graduation_attestation_preimage(
        steward=steward, task_class=task_class, precision_milli=precision_milli, n_labels=int(n_labels),
        min_samples=int(min_samples), precision_floor_milli=precision_floor_milli, decision=decision,
        operator_id=operator_id, ts_ns=int(ts_ns), sel_chain_head_hex=sel_chain_head_hex)
    digest = hashlib.sha256(preimage).digest()
    der = sign_digest(digest)
    verified = None
    if verify_sig is not None:
        try:
            verified = bool(verify_sig(digest, der))
        except Exception:  # noqa: BLE001
            verified = False
    return {
        "schema": SCHEMA, "domain": DOMAIN.decode(), "candidate": True, "notary": "guardian",
        "steward": steward, "task_class": task_class,
        "precision_milli": precision_milli, "n_labels": int(n_labels), "min_samples": int(min_samples),
        "precision_floor_milli": precision_floor_milli,
        "decision": str(decision).strip().upper(), "operator_id": operator_id, "ts_ns": int(ts_ns),
        "sel_chain_head_hex": sel_chain_head_hex,
        "digest_hex": digest.hex(), "signature_hex": der.hex(), "pubkey_hex": pubkey_hex,
        "kms_verified": verified,
        "note": _HONEST_NOTE,
    }


def attest_from_graduation(grad_report: dict, *, decision: str, operator_id: str, ts_ns: int,
                           sel_chain_head_hex: str, sign_digest, pubkey_hex: str, verify_sig=None) -> dict:
    """Convenience: extract the score/threshold fields from a steward_sel.recommend_graduation() output and
    attest the operator's decision on it. Composes OVER SEL (SEL stays attestation-free)."""
    score = grad_report.get("score", {})
    thresholds = grad_report.get("thresholds", {})
    return attest_graduation(
        steward=grad_report.get("steward"), task_class=grad_report.get("task_class"),
        precision=score.get("precision"), n_labels=score.get("n_external_labels", 0),
        min_samples=thresholds.get("min_samples", 0), precision_floor=thresholds.get("precision_floor", 0.0),
        decision=decision, operator_id=operator_id, ts_ns=ts_ns, sel_chain_head_hex=sel_chain_head_hex,
        sign_digest=sign_digest, pubkey_hex=pubkey_hex, verify_sig=verify_sig)


def verify_graduation_attestation(record: dict, pubkey_hex: str | None = None) -> bool:
    """PURE external verifier: re-derive the preimage from the record's public fields and verify the DER
    signature against Guardian's pubkey (record's or an externally-supplied one). Fails CLOSED on any
    malformed/missing field — never a silent false-OK. This is the externally-verifiable property: a third
    party needs only Guardian's published pubkey, not the bridge."""
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.hazmat.primitives.hashes import SHA256
    from cryptography.hazmat.primitives.serialization import load_der_public_key
    try:
        preimage = build_graduation_attestation_preimage(
            steward=record["steward"], task_class=record["task_class"],
            precision_milli=record["precision_milli"], n_labels=record["n_labels"],
            min_samples=record["min_samples"], precision_floor_milli=record["precision_floor_milli"],
            decision=record["decision"], operator_id=record["operator_id"], ts_ns=record["ts_ns"],
            sel_chain_head_hex=record["sel_chain_head_hex"])
        pub = load_der_public_key(bytes.fromhex(pubkey_hex or record["pubkey_hex"]))
        # digest = SHA256(preimage); Guardian signed the digest (DIGEST mode) -> verifying the preimage
        # with ECDSA(SHA256()) recomputes the same digest and checks the sig over it.
        pub.verify(bytes.fromhex(record["signature_hex"]), preimage, ec.ECDSA(SHA256()))
        return True
    except Exception:  # noqa: BLE001 - any failure (bad field, wrong key, bad sig) -> fail closed
        return False


def attestation_log_row(record: dict) -> dict:
    """Row for the existing operator_agent_signature_log (reuse — no new table). `subject` is a SHORT stable
    id, never the preimage (grok round-15 subject discipline; the table truncates subject to 200)."""
    return {
        "agent_id": "guardian", "draft_id": 0,
        "subject": f"sel-grad-attest:{str(record.get('digest_hex',''))[:16]}",
        "digest_hex": record.get("digest_hex", ""), "signature_hex": record.get("signature_hex", ""),
        "kms_key_spec": "ECC_SECG_P256K1", "kms_verified": bool(record.get("kms_verified")),
        "ts_ns": int(record.get("ts_ns", 0)),
    }
