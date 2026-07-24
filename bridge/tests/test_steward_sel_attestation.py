"""A2A-STEWARD-EVOLVE — SEL graduation ATTESTATION tests. Pins grok round-15's two footguns:
  1. preimage canonicalization — one builder; round-trip verify; EVERY field flip breaks verify; wrong
     key fails; malformed record fails CLOSED (never a silent false-OK);
  2. claim/operator binding — verify = f(Guardian pubkey, public fields); operator_id is bound into the
     preimage (integrity) but the note is explicit that the sig does NOT authenticate WHO the operator was.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import Prehashed
from cryptography.hazmat.primitives.hashes import SHA256
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from bridge.vapi_bridge.steward_sel_attestation import (
    attest_from_graduation,
    attest_graduation,
    attestation_log_row,
    build_graduation_attestation_preimage,
    verify_graduation_attestation,
)

_HEAD = "ab" * 32   # 32-byte SEL chain head hex


class _FakeGuardianKMS:
    """Local secp256k1 key mimicking Guardian's AWS KMS: sign a 32-byte DIGEST (DIGEST mode == Prehashed),
    return DER; publish DER-SPKI pubkey hex."""
    def __init__(self, curve=ec.SECP256K1()):
        self._priv = ec.generate_private_key(curve)

    def sign_digest(self, digest: bytes) -> bytes:
        return self._priv.sign(digest, ec.ECDSA(Prehashed(SHA256())))

    def pubkey_hex(self) -> str:
        return self._priv.public_key().public_bytes(
            Encoding.DER, PublicFormat.SubjectPublicKeyInfo).hex()

    def verify_sig(self, digest: bytes, der: bytes) -> bool:
        try:
            self._priv.public_key().verify(der, digest, ec.ECDSA(Prehashed(SHA256())))
            return True
        except Exception:
            return False


def _attest(kms=None, **over):
    kms = kms or _FakeGuardianKMS()
    base = dict(steward="guardian", task_class="PCRA", precision=0.95, n_labels=20, min_samples=20,
                precision_floor=0.90, decision="ACCEPT", operator_id="operator", ts_ns=1_700_000_000_000,
                sel_chain_head_hex=_HEAD)
    base.update(over)
    rec = attest_graduation(sign_digest=kms.sign_digest, pubkey_hex=kms.pubkey_hex(),
                            verify_sig=kms.verify_sig, **base)
    return rec, kms


# --- footgun 1: preimage canonicalization + round-trip + tamper -----------------------------------

def test_attest_then_verify_round_trip():
    rec, _ = _attest()
    assert verify_graduation_attestation(rec) is True
    assert rec["candidate"] is True and rec["domain"] == "VAPI-SEL-GRAD-ATTEST-v0"
    assert rec["kms_verified"] is True
    assert rec["precision_milli"] == 950 and rec["precision_floor_milli"] == 900   # milli-ints, no float


def test_every_field_flip_breaks_verify():
    rec, _ = _attest()
    for field, bad in [("steward", "sentry"), ("task_class", "MPJA"), ("precision_milli", 940),
                       ("n_labels", 19), ("min_samples", 10), ("precision_floor_milli", 800),
                       ("decision", "REJECT"), ("operator_id", "someone-else"),
                       ("ts_ns", 1_700_000_000_001), ("sel_chain_head_hex", "cd" * 32)]:
        tampered = dict(rec)
        tampered[field] = bad
        assert verify_graduation_attestation(tampered) is False, f"tampering {field} should break verify"


def test_wrong_pubkey_fails():
    rec, _ = _attest()
    other = _FakeGuardianKMS()
    assert verify_graduation_attestation(rec, pubkey_hex=other.pubkey_hex()) is False


def test_malformed_record_fails_closed():
    rec, _ = _attest()
    for missing in ("steward", "signature_hex", "sel_chain_head_hex", "pubkey_hex"):
        broken = {k: v for k, v in rec.items() if k != missing}
        assert verify_graduation_attestation(broken) is False   # no exception, just False


def test_decision_enum_and_head_length_pinned():
    kms = _FakeGuardianKMS()
    try:
        build_graduation_attestation_preimage(steward="g", task_class="PCRA", precision_milli=900,
                                              n_labels=1, min_samples=1, precision_floor_milli=900,
                                              decision="MAYBE", operator_id="o", ts_ns=1,
                                              sel_chain_head_hex=_HEAD)
        assert False, "expected decision enum to raise"
    except ValueError as exc:
        assert "ACCEPT or REJECT" in str(exc)
    try:
        build_graduation_attestation_preimage(steward="g", task_class="PCRA", precision_milli=900,
                                              n_labels=1, min_samples=1, precision_floor_milli=900,
                                              decision="ACCEPT", operator_id="o", ts_ns=1,
                                              sel_chain_head_hex="ab")   # not 32 bytes
        assert False, "expected head-length to raise"
    except ValueError as exc:
        assert "32 bytes" in str(exc)


# --- footgun 2: honest claim / operator binding ---------------------------------------------------

def test_note_states_the_honest_claim_not_operator_nonrepudiation():
    rec, _ = _attest()
    n = rec["note"]
    assert "NOT that the operator personally authorized" in n
    assert "DECLARATIVE" in n and "operator key" in n
    assert "not FROZEN" in n and "not --confirm-governance" in n
    assert rec["notary"] == "guardian"


def test_reject_decision_also_attestable():
    rec, _ = _attest(decision="REJECT")
    assert rec["decision"] == "REJECT" and verify_graduation_attestation(rec) is True


# --- log row + compose-over-SEL -------------------------------------------------------------------

def test_log_row_subject_is_short_stable_id_not_preimage():
    rec, _ = _attest()
    row = attestation_log_row(rec)
    assert row["agent_id"] == "guardian"
    assert row["subject"] == f"sel-grad-attest:{rec['digest_hex'][:16]}"
    assert len(row["subject"]) <= 200 and row["signature_hex"] == rec["signature_hex"]


def test_attest_from_graduation_extracts_sel_fields():
    kms = _FakeGuardianKMS()
    grad = {"steward": "guardian", "task_class": "PCRA",
            "score": {"precision": 1.0, "n_external_labels": 25},
            "thresholds": {"min_samples": 20, "precision_floor": 0.90}}
    rec = attest_from_graduation(grad, decision="ACCEPT", operator_id="operator", ts_ns=42,
                                 sel_chain_head_hex=_HEAD, sign_digest=kms.sign_digest,
                                 pubkey_hex=kms.pubkey_hex(), verify_sig=kms.verify_sig)
    assert rec["precision_milli"] == 1000 and rec["n_labels"] == 25 and rec["min_samples"] == 20
    assert verify_graduation_attestation(rec) is True


def test_binds_the_real_sel_candidate_chain_head():
    # the cheap novelty (grok round-15 3b): the attestation is anchored to the REAL SEL evidence head,
    # so it can't be re-used against a different label ledger state
    from bridge.vapi_bridge.steward_sel import chain_head
    kms = _FakeGuardianKMS()
    entries = [{"steward": "guardian", "task_class": "PCRA", "label": "ACCEPTED",
                "label_source": "operator_decision", "label_source_agent": "operator", "ts_ns": i}
               for i in range(1, 21)]
    head = chain_head(entries)
    assert len(head) == 64   # 32-byte hex
    rec, _ = _attest(kms=kms, sel_chain_head_hex=head)
    assert rec["sel_chain_head_hex"] == head and verify_graduation_attestation(rec) is True
    # a DIFFERENT ledger state (one extra label) yields a different head -> the old attestation is not
    # valid against it (the verifier would re-derive the bound head, not the new one)
    head2 = chain_head(entries + [{"steward": "guardian", "task_class": "PCRA", "label": "ACCEPTED",
                                   "label_source": "operator_decision", "label_source_agent": "operator",
                                   "ts_ns": 99}])
    assert head2 != head
