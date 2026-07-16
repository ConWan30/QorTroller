"""A2A-STEWARD-EVOLVE — operator co-sign (REAL non-repudiation) tests. Pins grok round-17's footguns:
  T1 bridge-wallet refuse (trust collapse) — the co-sign key must never be the bridge wallet;
  T2 cross-package / half-auth / mutation / non-raw-sig / non-address operator_id — fully_authorized requires
     Guardian's HSM sig AND an operator sig over the SAME digest whose recovered signer == operator_id.
"""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import Prehashed
from cryptography.hazmat.primitives.hashes import SHA256
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from eth_keys import keys

from bridge.vapi_bridge.steward_sel_attestation import attest_graduation
from bridge.vapi_bridge.steward_sel_cosign import (
    BRIDGE_WALLET,
    add_operator_cosignature,
    assert_operator_key_not_bridge,
    cryptographic_dual_key_satisfied,
    verify_dual_signed_attestation,
)

_HEAD = "ab" * 32


class _FakeGuardianKMS:
    def __init__(self):
        self._priv = ec.generate_private_key(ec.SECP256K1())

    def sign_digest(self, digest: bytes) -> bytes:
        return self._priv.sign(digest, ec.ECDSA(Prehashed(SHA256())))

    def pubkey_hex(self) -> str:
        return self._priv.public_key().public_bytes(
            Encoding.DER, PublicFormat.SubjectPublicKeyInfo).hex()

    def verify_sig(self, digest, der):
        try:
            self._priv.public_key().verify(der, digest, ec.ECDSA(Prehashed(SHA256())))
            return True
        except Exception:
            return False


def _op_key(seed: str = "11"):
    return keys.PrivateKey(bytes.fromhex(seed * 32))


def _op_sign(priv):
    return lambda digest: priv.sign_msg_hash(digest).to_bytes()


def _guardian_attestation(operator_id, gk=None, **over):
    gk = gk or _FakeGuardianKMS()
    base = dict(steward="guardian", task_class="PCRA", precision=0.95, n_labels=20, min_samples=20,
                precision_floor=0.90, decision="ACCEPT", operator_id=operator_id, ts_ns=1700,
                sel_chain_head_hex=_HEAD)
    base.update(over)
    rec = attest_graduation(sign_digest=gk.sign_digest, pubkey_hex=gk.pubkey_hex(),
                            verify_sig=gk.verify_sig, **base)
    return rec, gk


# --- happy path: real dual-sign ---------------------------------------------------------------------

def test_dual_sign_round_trip_fully_authorized():
    op = _op_key()
    rec, _ = _guardian_attestation(op.public_key.to_checksum_address())
    dual = add_operator_cosignature(rec, operator_sign=_op_sign(op))
    v = verify_dual_signed_attestation(dual)
    assert v["guardian_ok"] and v["operator_sig_ok"] and v["operator_id_authenticated"]
    assert v["fully_authorized"] is True
    assert dual["operator_signing_method"] == "raw-sha256-digest-secp256k1"
    assert cryptographic_dual_key_satisfied(dual) is True


def test_guardian_only_is_not_fully_authorized():
    op = _op_key()
    rec, _ = _guardian_attestation(op.public_key.to_checksum_address())
    v = verify_dual_signed_attestation(rec)     # no operator cosign added
    assert v["guardian_ok"] is True
    assert v["operator_sig_ok"] is False and v["fully_authorized"] is False
    assert cryptographic_dual_key_satisfied(rec) is False


# --- T1: bridge-wallet refuse -----------------------------------------------------------------------

def test_bridge_wallet_refused_as_operator_key():
    try:
        assert_operator_key_not_bridge(BRIDGE_WALLET)
        assert False, "expected bridge wallet to be refused"
    except ValueError as exc:
        assert "BRIDGE wallet" in str(exc)
    assert_operator_key_not_bridge("0x1111111111111111111111111111111111111111")  # a real operator key OK


# --- T2: authentication + tamper + cross-package ---------------------------------------------------

def test_cosign_refuses_non_address_operator_id():
    op = _op_key()
    rec, _ = _guardian_attestation("operator")     # declarative free-text id (v0-style)
    try:
        add_operator_cosignature(rec, operator_sign=_op_sign(op))
        assert False, "expected non-address operator_id to be refused"
    except ValueError as exc:
        assert "address" in str(exc)


def test_cosign_refuses_when_signer_ne_operator_id():
    op_a = _op_key("11")
    op_b = _op_key("22")
    rec, _ = _guardian_attestation(op_a.public_key.to_checksum_address())   # id = A
    try:
        add_operator_cosignature(rec, operator_sign=_op_sign(op_b))          # but B signs
        assert False, "expected signer != operator_id to be refused"
    except ValueError as exc:
        assert "override the signed decision package" in str(exc)


def test_mutating_operator_id_after_dual_sign_fails_closed():
    op = _op_key()
    rec, _ = _guardian_attestation(op.public_key.to_checksum_address())
    dual = add_operator_cosignature(rec, operator_sign=_op_sign(op))
    tampered = dict(dual)
    tampered["operator_id"] = "0x2222222222222222222222222222222222222222"
    v = verify_dual_signed_attestation(tampered)
    assert v["guardian_ok"] is False              # operator_id is inside the Guardian preimage
    assert v["operator_id_authenticated"] is False and v["fully_authorized"] is False


def test_cross_package_operator_sig_not_authenticated():
    # operator co-signs package A; transplanting that operator_signature onto a DIFFERENT package B
    # (different ts_ns, valid Guardian sig) must NOT authenticate — the operator sig is over A's digest
    op = _op_key()
    addr = op.public_key.to_checksum_address()
    rec_a, _ = _guardian_attestation(addr, ts_ns=1700)
    dual_a = add_operator_cosignature(rec_a, operator_sign=_op_sign(op))
    rec_b, _ = _guardian_attestation(addr, ts_ns=9999)   # genuine, valid Guardian sig, different package
    transplanted = dict(rec_b)
    transplanted["operator_signature_hex"] = dual_a["operator_signature_hex"]
    transplanted["operator_signing_method"] = dual_a["operator_signing_method"]
    v = verify_dual_signed_attestation(transplanted)
    assert v["guardian_ok"] is True               # B's own Guardian sig is valid
    assert v["operator_id_authenticated"] is False and v["fully_authorized"] is False


def test_bridge_wallet_operator_id_cannot_dual_sign_at_library_boundary(monkeypatch):
    # grok round-18 F1: the trust-collapse path — bridge sets operator_id=itself, signs with the deployer
    # key it holds -> both halves bridge-held. The library (not just the CLI) must refuse it. We can't
    # derive the real bridge key, so treat a test key AS the bridge wallet via monkeypatch.
    import bridge.vapi_bridge.steward_sel_cosign as cosign
    op = _op_key("44")
    addr = op.public_key.to_checksum_address()
    monkeypatch.setattr(cosign, "BRIDGE_WALLET", addr)   # this test key now counts as the bridge wallet
    rec, _ = _guardian_attestation(addr)
    # (a) add_operator_cosignature refuses a bridge-wallet operator_id at the library boundary
    try:
        cosign.add_operator_cosignature(rec, operator_sign=_op_sign(op))
        assert False, "expected bridge-wallet operator_id refused in the library, not just the CLI"
    except ValueError as exc:
        assert "BRIDGE wallet" in str(exc)
    # (b) verify refuses a hand-crafted bridge-wallet dual-signed record (fully_authorized=False)
    digest = cosign._digest_from_record(rec)
    crafted = dict(rec)
    crafted["operator_signature_hex"] = op.sign_msg_hash(digest).to_bytes().hex()
    crafted["operator_signing_method"] = "raw-sha256-digest-secp256k1"
    v = cosign.verify_dual_signed_attestation(crafted)
    assert v["fully_authorized"] is False and v["operator_id_authenticated"] is False


def test_non_raw_signature_not_authenticated():
    # grok T2(c): signing anything other than the EXACT raw digest (e.g. an EIP-191-wrapped hash) must not
    # authenticate — recovering over the raw digest yields a different address
    op = _op_key()
    rec, _ = _guardian_attestation(op.public_key.to_checksum_address())
    from bridge.vapi_bridge.steward_sel_cosign import _digest_from_record
    digest = _digest_from_record(rec)
    wrapped = hashlib.sha256(b"\x19Ethereum Signed Message:\n32" + digest).digest()   # NOT the raw digest
    wrong_sig = op.sign_msg_hash(wrapped).to_bytes()
    bad = dict(rec)
    bad["operator_signature_hex"] = wrong_sig.hex()
    bad["operator_signing_method"] = "raw-sha256-digest-secp256k1"
    v = verify_dual_signed_attestation(bad)
    assert v["operator_id_authenticated"] is False and v["fully_authorized"] is False
