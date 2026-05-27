"""Path A Arc 1 Commit 3 — DeviceBirthCertificate format + ceremony helpers.

   T-DBC-1  Serialization round-trip — cert_to_json → cert_from_json yields a
            structurally-equivalent cert (including None-valued optionals).
   T-DBC-2  compute_cert_hash is DETERMINISTIC — re-hashing the same signed cert
            returns the same 32-byte digest across multiple calls; permuting
            field-declaration order in code MUST NOT change the hash (canonical
            JSON's sort_keys guarantees this).
   T-DBC-3  sign_cert + verify_cert round-trip — a freshly-issued cert verifies
            green under verify_cert; the sig is exactly 64 bytes raw r||s; the
            signed cert's hash matches compute_cert_hash(cert).
   T-DBC-4  Tampering ANY signed-body field invalidates the sig (manufacturing_date
            mutation flagged, controller_model mutation flagged, etc.) — also
            tests that mutating signature_hex itself breaks verify.
   T-DBC-5  Anti-foot-shooting guards — (a) sign_cert refuses to double-sign
            (raises), (b) sign_cert refuses if cert.issuer_pubkey_hex disagrees
            with root_ca.issuer_pubkey_hex(), (c) canonical_bytes_full raises
            on unsigned cert, (d) verify_cert returns (False, reason) for an
            unsigned cert (does NOT raise).
   T-DBC-6  Bad-sig case — a cert with a corrupted signature_hex fails verify
            with a specific "ECDSA-P256 signature verification failed" reason
            (NOT a hex-decode or length error — proves we exercised the actual
            crypto path).
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from bridge.vapi_bridge.device_birth_cert import (
    CERT_VERSION, DeviceBirthCertificate,
    cert_from_json, cert_to_json, compute_cert_hash, sign_cert, verify_cert,
)
from bridge.vapi_bridge.manufacturer_root_ca import ManufacturerRootCA


@pytest.fixture
def tmp_ca_key_path():
    """Isolated ManufacturerRootCA key file per test — never touches real ~/.vapi."""
    d = tempfile.mkdtemp(prefix="vapi_mfg_ca_")
    p = Path(d) / "qortroller_foundation_mfg_ca.json"
    yield str(p)
    try:
        if p.exists():
            p.unlink()
        Path(d).rmdir()
    except OSError:
        pass


@pytest.fixture
def root_ca(tmp_ca_key_path):
    """Fresh QorTroller Foundation root CA, generated in a temp path."""
    return ManufacturerRootCA(key_path=tmp_ca_key_path)


def _make_unsigned_cert(issuer_pubkey_hex: str) -> DeviceBirthCertificate:
    """Helper — minimal Path B FULL DualSense Edge cert (no atecc_chip_id)."""
    return DeviceBirthCertificate(
        version=CERT_VERSION,
        device_id_hex="581a836c98b3a1b6c0f598bfca88e6a3cc3bd7c34591b506692cb40ddf66a9f8",
        ecdsa_p256_pubkey_hex="02" + "ab" * 32,  # compressed dummy (33 B = 66 hex)
        controller_model="CFI-ZCP1",
        manufacturer_id="QorTrollerFoundation",
        manufacturing_date="2026-05-26T03:11:00Z",
        signing_path="B",
        proof_tier="FULL",
        issuer_pubkey_hex=issuer_pubkey_hex,
        atecc_chip_id=None,
        issuer_backend="software",
        signature_hex=None,
    )


# ── T-DBC-1 ───────────────────────────────────────────────────────────────────

def test_T_DBC_1_serialization_round_trip(root_ca):
    cert = _make_unsigned_cert(root_ca.issuer_pubkey_hex())
    sign_cert(cert, root_ca)
    s = cert_to_json(cert)
    back = cert_from_json(s)
    # All required + optional fields preserved exactly
    assert back.version == cert.version
    assert back.device_id_hex == cert.device_id_hex
    assert back.ecdsa_p256_pubkey_hex == cert.ecdsa_p256_pubkey_hex
    assert back.controller_model == cert.controller_model
    assert back.manufacturer_id == cert.manufacturer_id
    assert back.manufacturing_date == cert.manufacturing_date
    assert back.signing_path == cert.signing_path
    assert back.proof_tier == cert.proof_tier
    assert back.issuer_pubkey_hex == cert.issuer_pubkey_hex
    assert back.atecc_chip_id == cert.atecc_chip_id
    assert back.issuer_backend == cert.issuer_backend
    assert back.signature_hex == cert.signature_hex
    # Hash equivalence is the canonical equivalence test
    assert compute_cert_hash(back) == compute_cert_hash(cert)


# ── T-DBC-2 ───────────────────────────────────────────────────────────────────

def test_T_DBC_2_compute_cert_hash_is_deterministic(root_ca):
    cert = _make_unsigned_cert(root_ca.issuer_pubkey_hex())
    sign_cert(cert, root_ca)
    h1 = compute_cert_hash(cert)
    h2 = compute_cert_hash(cert)
    h3 = compute_cert_hash(cert)
    assert h1 == h2 == h3
    assert len(h1) == 32

    # Round-tripping through JSON MUST also preserve the hash (proves the
    # canonical-JSON discipline survives Python dict iteration order quirks)
    cert2 = cert_from_json(cert_to_json(cert))
    assert compute_cert_hash(cert2) == h1


# ── T-DBC-3 ───────────────────────────────────────────────────────────────────

def test_T_DBC_3_sign_then_verify_round_trip(root_ca):
    cert = _make_unsigned_cert(root_ca.issuer_pubkey_hex())
    assert cert.signature_hex is None
    sign_cert(cert, root_ca)
    assert cert.signature_hex is not None
    assert len(bytes.fromhex(cert.signature_hex)) == 64  # raw r||s
    ok, reason = verify_cert(cert)
    assert ok, f"verify failed: {reason}"
    assert reason == ""
    # The cert's canonical_bytes_full() is well-formed and hashable
    h = compute_cert_hash(cert)
    assert isinstance(h, bytes) and len(h) == 32


# ── T-DBC-4 ───────────────────────────────────────────────────────────────────

def test_T_DBC_4_tampering_any_signed_body_field_invalidates_sig(root_ca):
    cert = _make_unsigned_cert(root_ca.issuer_pubkey_hex())
    sign_cert(cert, root_ca)
    ok, _ = verify_cert(cert)
    assert ok  # baseline

    # (a) tamper manufacturing_date
    cert2 = cert_from_json(cert_to_json(cert))
    cert2.manufacturing_date = "2026-05-26T03:12:00Z"  # +1 minute
    ok, reason = verify_cert(cert2)
    assert not ok and "signature verification failed" in reason

    # (b) tamper controller_model
    cert3 = cert_from_json(cert_to_json(cert))
    cert3.controller_model = "CFI-ZCT1"
    ok, _ = verify_cert(cert3)
    assert not ok

    # (c) tamper proof_tier
    cert4 = cert_from_json(cert_to_json(cert))
    cert4.proof_tier = "BASIC"
    ok, _ = verify_cert(cert4)
    assert not ok

    # (d) tamper signing_path
    cert5 = cert_from_json(cert_to_json(cert))
    cert5.signing_path = "A"
    ok, _ = verify_cert(cert5)
    assert not ok

    # (e) tamper signature_hex itself — flip one byte
    cert6 = cert_from_json(cert_to_json(cert))
    orig = bytearray(bytes.fromhex(cert6.signature_hex))
    orig[0] ^= 0xFF
    cert6.signature_hex = bytes(orig).hex()
    ok, _ = verify_cert(cert6)
    assert not ok


# ── T-DBC-5 ───────────────────────────────────────────────────────────────────

def test_T_DBC_5_anti_foot_shooting_guards(root_ca, tmp_ca_key_path):
    cert = _make_unsigned_cert(root_ca.issuer_pubkey_hex())

    # (a) canonical_bytes_full raises on unsigned cert
    with pytest.raises(ValueError, match="signature_hex is None"):
        cert.canonical_bytes_full()

    # (b) verify_cert returns (False, reason) for unsigned cert — does NOT raise
    ok, reason = verify_cert(cert)
    assert not ok
    assert "unsigned" in reason

    # (c) sign_cert refuses if issuer_pubkey_hex disagrees with root_ca's pubkey
    bogus_cert = _make_unsigned_cert("04" + "00" * 64)  # bogus issuer pubkey
    with pytest.raises(ValueError, match="issuer_pubkey_hex mismatch"):
        sign_cert(bogus_cert, root_ca)

    # (d) sign_cert refuses to double-sign
    sign_cert(cert, root_ca)
    assert cert.signature_hex is not None
    with pytest.raises(ValueError, match="already signed"):
        sign_cert(cert, root_ca)


# ── T-DBC-6 ───────────────────────────────────────────────────────────────────

def test_T_DBC_6_corrupted_signature_specifically_fails_crypto_path(root_ca):
    """Distinguish the crypto-failure mode from format-failure modes — proves we
    exercised the actual ECDSA verify and didn't short-circuit on length /
    hex-decode checks."""
    cert = _make_unsigned_cert(root_ca.issuer_pubkey_hex())
    sign_cert(cert, root_ca)
    # Replace sig with a SYNTACTICALLY valid but cryptographically invalid sig
    # (correct length, valid hex, but wrong r/s for this body+pubkey)
    cert.signature_hex = ("00" * 32) + ("01" * 32)  # 64 bytes valid hex
    assert len(bytes.fromhex(cert.signature_hex)) == 64
    ok, reason = verify_cert(cert)
    assert not ok
    # Critical: reason is the CRYPTO failure, not "wrong length" or "decode"
    assert reason == "ECDSA-P256 signature verification failed", (
        f"expected crypto path failure, got: {reason!r}"
    )
