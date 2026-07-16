"""HSM expansion Inc-1 — KMSIdentityBackend (P-256, non-exportable-key path for the MFG Root CA).

Pins grok round-13's two load-bearing footguns:
  1. the single-SHA256-then-DIGEST contract (the ABC hashes internally; KMS wants a 32-byte prehash —
     so the backend must hash the body EXACTLY ONCE and never pass the raw body as a digest);
  2. the wire round-trip (DER->raw r||s 64B + SPKI->uncompressed 65B) verifies against the REAL
     verify_cert_signature path — and a wrong-curve key fails closed.
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

from bridge.vapi_bridge.hardware_identity import (
    KMSIdentityBackend,
    _der_sig_to_raw_rs,
    _spki_to_uncompressed_p256,
    create_backend,
)
from bridge.vapi_bridge.manufacturer_root_ca import verify_cert_signature


class _FakeKMSPort:
    """Local P-256 key that mimics AWS KMS: sign(digest, DIGEST-mode) -> DER; get_public_key -> SPKI.
    Records every digest it is asked to sign so the single-hash contract can be asserted."""
    def __init__(self, curve=ec.SECP256R1()):
        self._priv = ec.generate_private_key(curve)
        self.received_digests: list = []

    def sign_digest_der(self, digest: bytes) -> bytes:
        self.received_digests.append(digest)
        # KMS DIGEST mode == sign a pre-computed hash: Prehashed(SHA256)
        return self._priv.sign(digest, ec.ECDSA(Prehashed(SHA256())))

    def get_pubkey_spki(self) -> bytes:
        return self._priv.public_key().public_bytes(Encoding.DER, PublicFormat.SubjectPublicKeyInfo)


def _backend(port=None):
    port = port or _FakeKMSPort()
    b = KMSIdentityBackend(sign_digest_der=port.sign_digest_der, get_pubkey_spki=port.get_pubkey_spki)
    b.setup()
    return b, port


# --- footgun 1: single-hash DIGEST contract --------------------------------------------------------

def test_body_is_hashed_exactly_once():
    b, port = _backend()
    body = b"device-birth-cert-canonical-bytes"
    b.sign(body)
    assert len(port.received_digests) == 1
    # the port must receive SHA256(body) — NOT the raw body, NOT SHA256(SHA256(body))
    assert port.received_digests[-1] == hashlib.sha256(body).digest()
    assert len(port.received_digests[-1]) == 32
    assert port.received_digests[-1] != hashlib.sha256(hashlib.sha256(body).digest()).digest()


def test_signature_verifies_against_real_cert_verify_path():
    b, _ = _backend()
    body = b"the exact bytes a DeviceBirthCertificate signs"
    raw_sig = b.sign(body)
    assert verify_cert_signature(b.public_key_bytes, body, raw_sig) is True


def test_a_double_hashed_signature_would_fail_verify():
    # proves the single-hash contract is load-bearing: signing the pre-digest (double hash) breaks verify
    b, port = _backend()
    body = b"body-under-test"
    double = port.sign_digest_der(hashlib.sha256(hashlib.sha256(body).digest()).digest())
    bad_raw = _der_sig_to_raw_rs(double)
    assert verify_cert_signature(b.public_key_bytes, body, bad_raw) is False


# --- footgun 2: wire shape + SPKI round-trip -------------------------------------------------------

def test_wire_shapes():
    b, _ = _backend()
    assert len(b.public_key_bytes) == 65 and b.public_key_bytes[0] == 0x04
    assert len(b.sign(b"x")) == 64
    assert b.backend_type == "kms" and b.is_hardware_backed is True


def test_wrong_curve_key_fails_closed_at_setup():
    # a secp256k1 key (the agent-key curve) must NOT be accepted as a P-256 CA key
    k1 = _FakeKMSPort(curve=ec.SECP256K1())
    b = KMSIdentityBackend(sign_digest_der=k1.sign_digest_der, get_pubkey_spki=k1.get_pubkey_spki)
    try:
        b.setup()
        assert False, "expected wrong-curve setup to fail closed"
    except ValueError as exc:
        assert "P-256" in str(exc)


# --- pure converters -------------------------------------------------------------------------------

def test_spki_to_uncompressed_matches_x962():
    port = _FakeKMSPort()
    uncompressed = _spki_to_uncompressed_p256(port.get_pubkey_spki())
    expected = port._priv.public_key().public_bytes(Encoding.X962, PublicFormat.UncompressedPoint)
    assert uncompressed == expected and len(uncompressed) == 65


def test_der_to_raw_is_64_bytes():
    port = _FakeKMSPort()
    der = port.sign_digest_der(hashlib.sha256(b"m").digest())
    raw = _der_sig_to_raw_rs(der)
    assert len(raw) == 64


# --- factory ---------------------------------------------------------------------------------------

def test_create_backend_kms_with_injected_ports():
    port = _FakeKMSPort()
    b = create_backend("kms", sign_digest_der=port.sign_digest_der, get_pubkey_spki=port.get_pubkey_spki)
    b.setup()
    body = b"factory path"
    assert verify_cert_signature(b.public_key_bytes, body, b.sign(body)) is True


def test_create_backend_kms_requires_ports_or_alias():
    try:
        create_backend("kms")
        assert False, "expected missing-ports/alias to raise"
    except ValueError as exc:
        assert "sign_digest_der" in str(exc) or "alias" in str(exc)


# --- Inc-2: ManufacturerRootCA backend selection --------------------------------------------------

def test_mfg_ca_with_injected_kms_backend_signs_and_verifies():
    from bridge.vapi_bridge.manufacturer_root_ca import ManufacturerRootCA
    port = _FakeKMSPort()
    kms_backend = create_backend("kms", sign_digest_der=port.sign_digest_der,
                                 get_pubkey_spki=port.get_pubkey_spki)
    ca = ManufacturerRootCA(backend=kms_backend)
    body = b"a device birth certificate body signed by the HSM CA"
    sig = ca.sign_cert_body(body)
    assert verify_cert_signature(ca.issuer_pubkey_uncompressed(), body, sig) is True
    assert ca.backend_type() == "kms"


def test_mfg_ca_default_is_software(tmp_path, monkeypatch):
    # DEFAULT (no env, no injection) must stay the plaintext SoftwareIdentityBackend — byte-identical.
    # delenv so a leaked operator MFG_CA_BACKEND can't flake this (grok round-14 test hygiene).
    monkeypatch.delenv("MFG_CA_BACKEND", raising=False)
    from bridge.vapi_bridge.manufacturer_root_ca import ManufacturerRootCA
    ca = ManufacturerRootCA(key_path=str(tmp_path / "ca.json"))
    assert type(ca._backend).__name__ == "SoftwareIdentityBackend"


def test_mfg_ca_unknown_backend_fails_loud(monkeypatch):
    # a typo'd flip must NOT silently fall through to the software key (grok round-14)
    from bridge.vapi_bridge.manufacturer_root_ca import ManufacturerRootCA
    monkeypatch.setenv("MFG_CA_BACKEND", "kme")
    try:
        ManufacturerRootCA()
        assert False, "expected unknown MFG_CA_BACKEND to fail loud"
    except ValueError as exc:
        assert "unknown MFG_CA_BACKEND" in str(exc)


def test_mfg_ca_backend_kms_env_requires_alias(monkeypatch):
    from bridge.vapi_bridge.manufacturer_root_ca import ManufacturerRootCA
    monkeypatch.setenv("MFG_CA_BACKEND", "kms")
    monkeypatch.delenv("VAPI_KMS_MFG_CA_ALIAS", raising=False)
    try:
        ManufacturerRootCA()
        assert False, "expected kms-without-alias to fail closed"
    except ValueError as exc:
        assert "VAPI_KMS_MFG_CA_ALIAS" in str(exc)
