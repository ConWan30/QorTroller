"""Mint/verify split + chain-first device binding (F-PATHA-1 / A2A round-26).

Canon (DEVICE_ID_CANON_v1 keccak) is the MINT-only gate; verification of a
VMDR-REGISTERED device is authoritative against the on-chain pubkeyHash
(sha256 of the compressed cert pubkey the manufacturer attested). Chain wins
in BOTH directions; offline is honest canon best-effort, never a skip.

   T-BIND-1  chain binding grandfathers a non-canon device_id (581a836c shape):
             matching on-chain pubkeyHash → VALID even though canon disagrees.
   T-BIND-2  chain wins the other way too: canon-consistent pair FAILS when the
             on-chain pubkeyHash attests a DIFFERENT key (evil key swap).
   T-BIND-3  offline (None) + canon-consistent → VALID (pre-split behavior).
   T-BIND-4  offline + canon-mismatch → INVALID with honest best-effort reason
             (never a silent pass; the pre-canon registered device reads
             INVALID-OFFLINE until chain evidence is supplied).
   T-BIND-5  assert_mint_device_id_canon: mint gate raises on mismatch, passes
             on canon match — mint and verify cannot be confused.
   T-BIND-6  fail-closed on malformed inputs: bad on-chain hash length, bad
             device_id length, undecodable pubkey → (False, reason), no crash.
   T-BIND-7  verify_cert default kwarg is byte-identical to pre-split: a
             canon-mismatched cert still fails with "device_id_hex mismatch".
   T-BIND-8  verify_cert(on_chain_pubkey_hash_hex=match) grandfathers a signed
             cert whose device_id is NOT canon(pubkey) — the 581a836c re-issue
             shape end-to-end (sign under CA → verify with chain evidence).
   T-BIND-9  verify_cert(on_chain_pubkey_hash_hex=WRONG) fails even when the
             cert is canon-consistent (chain evidence is authoritative).
   T-BIND-10 REAL live-device pin: the actual VMDR bind (581a836c, cert pubkey
             02997c…, on-chain pubkeyHash 235a2c04…) verifies; the same pair
             offline reads INVALID (public data only — no key material).
   T-BIND-11 ioID DID build honors the split: live pair passes WITH chain
             evidence, raises ValueError without it.
   T-BIND-12 compute_pubkey_hash_hex: compressed and uncompressed input agree;
             wrong-length input raises ValueError.

NOTE (round-27 F4): T-BIND-11 imports controller_ioid_registration, which uses
`from vapi_bridge...` absolute imports — run with the bridge harness (repo-root
pytest / CI) or PYTHONPATH=bridge; a bare `pytest <this file>` from elsewhere
fails on import pathing, not on product behavior.
"""
from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from bridge.vapi_bridge.device_birth_cert import (
    CERT_VERSION, DeviceBirthCertificate,
    assert_mint_device_id_canon,
    compress_sec1_p256_pubkey,
    compute_device_id_from_pubkey_hex,
    compute_pubkey_hash_hex,
    sign_cert,
    verify_cert,
    verify_registered_device_binding,
)
from bridge.vapi_bridge.manufacturer_root_ca import ManufacturerRootCA

# The one live registered device — ALL PUBLIC data (on-chain + committed fixture).
LIVE_DEVICE_ID = "581a836c98b3a1b6c0f598bfca88e6a3cc3bd7c34591b506692cb40ddf66a9f8"
LIVE_CERT_PUBKEY = "02997ca227f9fb4dc11a98518520b27d73dc3d44f9e8f7e4530f3c6a6f0627477b"
LIVE_ONCHAIN_PUBKEY_HASH = "235a2c04de3319661dd637ad296e37b59c23b0fe1f78509965f77bc5d9247802"


@pytest.fixture
def root_ca():
    """Isolated ManufacturerRootCA key file per test — never touches real ~/.vapi."""
    d = tempfile.mkdtemp(prefix="vapi_mfg_ca_bind_")
    p = Path(d) / "qortroller_foundation_mfg_ca.json"
    ca = ManufacturerRootCA(key_path=str(p))
    yield ca
    try:
        if p.exists():
            p.unlink()
        Path(d).rmdir()
    except OSError:
        pass


def _fresh_pubkey_hex(compressed: bool = True) -> str:
    pub = ec.generate_private_key(ec.SECP256R1()).public_key().public_bytes(
        Encoding.X962, PublicFormat.UncompressedPoint)
    return compress_sec1_p256_pubkey(pub).hex() if compressed else pub.hex()


def _make_cert(device_id_hex: str, pubkey_hex: str, issuer_pubkey_hex: str) -> DeviceBirthCertificate:
    return DeviceBirthCertificate(
        version=CERT_VERSION,
        device_id_hex=device_id_hex,
        ecdsa_p256_pubkey_hex=pubkey_hex,
        controller_model="CFI-ZCP1",
        manufacturer_id="QorTrollerFoundation",
        manufacturing_date="2026-07-16T00:00:00Z",
        signing_path="B",
        proof_tier="FULL",
        issuer_pubkey_hex=issuer_pubkey_hex,
        atecc_chip_id=None,
        issuer_backend="software",
        signature_hex=None,
    )


# ── T-BIND-1 ──────────────────────────────────────────────────────────────────

def test_T_BIND_1_chain_binding_grandfathers_non_canon_id():
    pubkey = _fresh_pubkey_hex()
    non_canon_id = "ab" * 32  # NOT keccak(pubkey) — the pre-canon registration shape
    assert compute_device_id_from_pubkey_hex(pubkey) != non_canon_id
    ok, reason = verify_registered_device_binding(
        non_canon_id, pubkey,
        on_chain_pubkey_hash_hex=compute_pubkey_hash_hex(pubkey),
    )
    assert ok, reason
    assert reason == ""


# ── T-BIND-2 ──────────────────────────────────────────────────────────────────

def test_T_BIND_2_chain_wins_over_canon_on_key_swap():
    pubkey = _fresh_pubkey_hex()
    other_key = _fresh_pubkey_hex()
    canon_id = compute_device_id_from_pubkey_hex(pubkey)
    ok, reason = verify_registered_device_binding(
        canon_id, pubkey,
        on_chain_pubkey_hash_hex=compute_pubkey_hash_hex(other_key),
    )
    assert not ok
    assert "pubkeyHash mismatch" in reason


# ── T-BIND-3 ──────────────────────────────────────────────────────────────────

def test_T_BIND_3_offline_canon_consistent_passes():
    pubkey = _fresh_pubkey_hex()
    canon_id = compute_device_id_from_pubkey_hex(pubkey)
    ok, reason = verify_registered_device_binding(canon_id, pubkey,
                                                  on_chain_pubkey_hash_hex=None)
    assert ok, reason


# ── T-BIND-4 ──────────────────────────────────────────────────────────────────

def test_T_BIND_4_offline_canon_mismatch_fails_honestly():
    pubkey = _fresh_pubkey_hex()
    ok, reason = verify_registered_device_binding("cd" * 32, pubkey,
                                                  on_chain_pubkey_hash_hex=None)
    assert not ok
    assert "device_id_hex mismatch" in reason
    assert "best-effort" in reason  # honest INVALID-OFFLINE, never a skip


# ── T-BIND-5 ──────────────────────────────────────────────────────────────────

def test_T_BIND_5_mint_gate_raises_on_mismatch():
    pubkey = _fresh_pubkey_hex()
    with pytest.raises(ValueError, match="mint canon violation"):
        assert_mint_device_id_canon("ef" * 32, pubkey)
    # canon-consistent pair passes silently
    assert_mint_device_id_canon(compute_device_id_from_pubkey_hex(pubkey), pubkey)


# ── T-BIND-6 ──────────────────────────────────────────────────────────────────

def test_T_BIND_6_fail_closed_on_malformed_inputs():
    pubkey = _fresh_pubkey_hex()
    good_hash = compute_pubkey_hash_hex(pubkey)
    # malformed chain evidence → refuse, never pass
    ok, reason = verify_registered_device_binding(
        "ab" * 32, pubkey, on_chain_pubkey_hash_hex="deadbeef")
    assert not ok and "wrong length" in reason
    # malformed device_id → refuse
    ok, reason = verify_registered_device_binding(
        "ab" * 8, pubkey, on_chain_pubkey_hash_hex=good_hash)
    assert not ok and "wrong length" in reason
    # undecodable pubkey → refuse, no crash
    ok, reason = verify_registered_device_binding(
        "ab" * 32, "zz-not-hex", on_chain_pubkey_hash_hex=good_hash)
    assert not ok


# ── T-BIND-7 ──────────────────────────────────────────────────────────────────

def test_T_BIND_7_verify_cert_default_is_presplit_canon(root_ca):
    pubkey = _fresh_pubkey_hex()
    cert = _make_cert("12" * 32, pubkey, root_ca.issuer_pubkey_hex())
    sign_cert(cert, root_ca)
    ok, reason = verify_cert(cert)
    assert not ok
    assert "device_id_hex mismatch" in reason


# ── T-BIND-8 ──────────────────────────────────────────────────────────────────

def test_T_BIND_8_verify_cert_chain_evidence_grandfathers(root_ca):
    """The 581a836c re-issue shape end-to-end: device_id != canon(pubkey), but
    the on-chain pubkeyHash attests this exact key → VALID."""
    pubkey = _fresh_pubkey_hex()
    cert = _make_cert("12" * 32, pubkey, root_ca.issuer_pubkey_hex())
    sign_cert(cert, root_ca)
    ok, reason = verify_cert(
        cert, on_chain_pubkey_hash_hex=compute_pubkey_hash_hex(pubkey))
    assert ok, reason


# ── T-BIND-9 ──────────────────────────────────────────────────────────────────

def test_T_BIND_9_verify_cert_wrong_chain_evidence_fails(root_ca):
    pubkey = _fresh_pubkey_hex()
    other_key = _fresh_pubkey_hex()
    cert = _make_cert(compute_device_id_from_pubkey_hex(pubkey), pubkey,
                      root_ca.issuer_pubkey_hex())
    sign_cert(cert, root_ca)
    ok, reason = verify_cert(
        cert, on_chain_pubkey_hash_hex=compute_pubkey_hash_hex(other_key))
    assert not ok
    assert "pubkeyHash mismatch" in reason


# ── T-BIND-10 ─────────────────────────────────────────────────────────────────

def test_T_BIND_10_live_device_581a836c_grandfathered_by_real_chain_bind():
    """Pins the ACTUAL production grandfather: the live VMDR record's pubkeyHash
    (sha256 of the registered cert pubkey) validates 581a836c; offline canon
    honestly rejects the same pair. Public data only."""
    # sanity: the committed on-chain hash IS sha256(compressed cert pubkey)
    assert compute_pubkey_hash_hex(LIVE_CERT_PUBKEY) == LIVE_ONCHAIN_PUBKEY_HASH
    # canon genuinely disagrees for this pair (why F-PATHA-1 existed)
    assert compute_device_id_from_pubkey_hex(LIVE_CERT_PUBKEY) != LIVE_DEVICE_ID

    ok, reason = verify_registered_device_binding(
        LIVE_DEVICE_ID, LIVE_CERT_PUBKEY,
        on_chain_pubkey_hash_hex=LIVE_ONCHAIN_PUBKEY_HASH,
    )
    assert ok, reason

    ok_off, reason_off = verify_registered_device_binding(
        LIVE_DEVICE_ID, LIVE_CERT_PUBKEY, on_chain_pubkey_hash_hex=None)
    assert not ok_off
    assert "best-effort" in reason_off


# ── T-BIND-11 ─────────────────────────────────────────────────────────────────

def test_T_BIND_11_ioid_did_build_honors_split():
    from bridge.vapi_bridge.controller_ioid_registration import (
        build_controller_did_document,
    )
    gamer = "0x" + "aa" * 20
    # WITH chain evidence: the live device builds a DID document
    doc = build_controller_did_document(
        device_id_hex=LIVE_DEVICE_ID,
        ecdsa_p256_pubkey_hex=LIVE_CERT_PUBKEY,
        gamer_address=gamer,
        on_chain_pubkey_hash_hex=LIVE_ONCHAIN_PUBKEY_HASH,
    )
    assert doc["id"] == f"did:io:{LIVE_DEVICE_ID}"
    # WITHOUT: canon best-effort refuses (honest, not a skip)
    with pytest.raises(ValueError, match="binding failed"):
        build_controller_did_document(
            device_id_hex=LIVE_DEVICE_ID,
            ecdsa_p256_pubkey_hex=LIVE_CERT_PUBKEY,
            gamer_address=gamer,
        )


# ── T-BIND-12 ─────────────────────────────────────────────────────────────────

def test_T_BIND_12_pubkey_hash_compressed_uncompressed_agree():
    uncompressed = _fresh_pubkey_hex(compressed=False)
    compressed = compress_sec1_p256_pubkey(bytes.fromhex(uncompressed)).hex()
    assert compute_pubkey_hash_hex(uncompressed) == compute_pubkey_hash_hex(compressed)
    with pytest.raises(ValueError):
        compute_pubkey_hash_hex("ab" * 10)
