"""Test vectors for l9_presence/composite_sig.py (scope: composite_sig_v1_scope.md).

Test-responsibility division (operator-framed):
    QorTroller owns the COMPOSITION; NIST + PQClean own the PRIMITIVES.

  * Byte-pinned KATs for what QorTroller is responsible for:
      - the M' construction (deterministic; byte-pinnable; QorTroller-novel)
      - the AND-verify decision logic (missing-half / OR-fallback rejected)
      - the Label-binding negatives (wrong-Label composites rejected)
      - the ctx-binding negatives (wrong-PATTERN-017-tag composites rejected)
      - algorithm-identifier validation (presented alg_id must match components)
  * Round-trip sign->verify for what the PQ library is responsible for:
      - functional correctness per pairing (randomized signatures are NOT
        byte-pinned; ML-DSA bytes vary per run; SLH-DSA here is deterministic).

Underlying-primitive trust basis (NOT re-validated per run - the primitives are
not QorTroller's to own):
  * SLH-DSA-SHA2-128s: slh-dsa 0.2.2 was validated 42/42 against NIST ACVP
    SLH-DSA-sigVer-FIPS205 (parameterSet SLH-DSA-SHA2-128s; 6 valid sigs
    accepted, 36 tampered rejected; external/pure + external/preHash + internal
    interfaces) during the Phase B item-① Step-3 verification (2026-05-23).
    Here we assert only the cheap structural FIPS-205 invariants (parameter set
    + signature size) plus a functional round-trip.
  * ML-DSA-44 / ML-DSA-65: quantcrypt 1.0.1 over PQClean ml-dsa-44 / ml-dsa-65.
"""

from __future__ import annotations

import hashlib

import pytest

from l9_presence import composite_sig as C

# --- fixed, deterministic test inputs --------------------------------------
M = hashlib.sha256(b"QORTROLLER-COMPSIG-KAT-v1").digest()  # 32-byte commitment
CTX = b"QORTROLLER-POEP-v0"  # raw PATTERN-017 family domain tag
CTX_OTHER = b"QORTROLLER-BCC-GENESIS-v0"  # a different PATTERN-017 family

# --- byte-pinned M' KATs (the QorTroller-novel deterministic artifact) ------
# M' = Prefix || Label || len(ctx) || ctx || PH(M)   [draft-16 Section 2.2/3.2]
KAT_MPRIME = {
    C.LABEL_MLDSA65: (
        "436f6d706f73697465416c676f726974686d5369676e6174757265733230323543"
        "4f4d505349472d4d4c44534136352d45434453412d503235362d53484135313212"
        "514f5254524f4c4c45522d504f45502d76302628efe10e97b3e8e09efd60b5c14e"
        "7bec2c432120557e6fe31e91c780fb73d9edf78a7493c030c049102ec9512b01a1"
        "5ed57431adff709dc449438782d1a86d"
    ),
    C.LABEL_MLDSA44: (
        "436f6d706f73697465416c676f726974686d5369676e6174757265733230323543"
        "4f4d505349472d4d4c44534134342d45434453412d503235362d53484132353612"
        "514f5254524f4c4c45522d504f45502d7630ca57a91be17440ec1de5e3101d2d45"
        "d621f3887ffe78bf291ffb5d95bf778d47"
    ),
    C.LABEL_SLHDSA128S: (
        "436f6d706f73697465416c676f726974686d5369676e6174757265733230323543"
        "4f4d505349472d534c48445341313238532d45434453412d503235362d53484132"
        "35362d514f5254524f4c4c455212514f5254524f4c4c45522d504f45502d7630ca"
        "57a91be17440ec1de5e3101d2d45d621f3887ffe78bf291ffb5d95bf778d47"
    ),
}

ALL_ALGS = [
    C.ALG_MLDSA65_ECDSA_P256_SHA512,
    C.ALG_MLDSA44_ECDSA_P256_SHA256,
    C.ALG_SLHDSA128S_ECDSA_P256_SHA256,
]
MLDSA_ALGS = [C.ALG_MLDSA65_ECDSA_P256_SHA512, C.ALG_MLDSA44_ECDSA_P256_SHA256]


# ===========================================================================
# (d) KATs - byte-pinned construction (deterministic; QorTroller-owned)
# ===========================================================================


def test_prefix_is_frozen_32_bytes():
    assert C.PREFIX == b"CompositeAlgorithmSignatures2025"
    assert len(C.PREFIX) == 32
    assert C.PREFIX.hex() == "436f6d706f73697465416c676f726974686d5369676e61747572657332303235"


@pytest.mark.parametrize("alg", ALL_ALGS, ids=lambda a: a.label.decode())
def test_mprime_byte_pinned_kat(alg):
    mprime = C.build_message_representative(alg, CTX, M)
    assert mprime.hex() == KAT_MPRIME[alg.label]


@pytest.mark.parametrize("alg", ALL_ALGS, ids=lambda a: a.label.decode())
def test_mprime_structure(alg):
    mprime = C.build_message_representative(alg, CTX, M)
    # Prefix || Label || len(ctx) || ctx || PH(M)
    assert mprime.startswith(C.PREFIX + alg.label)
    off = len(C.PREFIX) + len(alg.label)
    assert mprime[off] == len(CTX)
    off += 1
    assert mprime[off : off + len(CTX)] == CTX
    off += len(CTX)
    assert mprime[off:] == alg.ph(M)


def test_ctx_length_limit_enforced():
    with pytest.raises(ValueError):
        C.build_message_representative(C.ALG_MLDSA44_ECDSA_P256_SHA256, b"x" * 256, M)
    # exactly 255 is allowed
    ok = C.build_message_representative(C.ALG_MLDSA44_ECDSA_P256_SHA256, b"x" * 255, M)
    assert ok[len(C.PREFIX) + len(C.LABEL_MLDSA44)] == 255


def test_commitment_must_be_32_bytes():
    with pytest.raises(ValueError):
        C.build_message_representative(C.ALG_MLDSA44_ECDSA_P256_SHA256, CTX, b"short")


def test_ph_pairing_per_tier():
    # tier-1 uses SHA-512, tiers 2/3 use SHA-256 (scope Section 3)
    assert C.ALG_MLDSA65_ECDSA_P256_SHA512.ph(M) == hashlib.sha512(M).digest()
    assert C.ALG_MLDSA44_ECDSA_P256_SHA256.ph(M) == hashlib.sha256(M).digest()
    assert C.ALG_SLHDSA128S_ECDSA_P256_SHA256.ph(M) == hashlib.sha256(M).digest()


def test_oids_match_scope_doc():
    assert C.ALG_MLDSA65_ECDSA_P256_SHA512.oid == "1.3.6.1.5.5.7.6.45"
    assert C.ALG_MLDSA44_ECDSA_P256_SHA256.oid == "1.3.6.1.5.5.7.6.40"
    # QorTroller tier OID deferred (Decision OID-2b)
    assert C.ALG_SLHDSA128S_ECDSA_P256_SHA256.oid is None


# ===========================================================================
# (a) AND-composite sign + verify (functional round-trip; PQ-lib-owned)
# ===========================================================================


@pytest.mark.parametrize("alg", MLDSA_ALGS, ids=lambda a: a.label.decode())
def test_mldsa_sign_verify_roundtrip(alg):
    kp = C.generate_keypair(alg)
    sig = C.sign(kp, CTX, M)
    assert C.verify(kp.public(), CTX, M, sig) is True


# --- SLH-DSA is slow to sign (~24s); generate + sign ONCE, reuse everywhere --
@pytest.fixture(scope="module")
def slhdsa_signed():
    alg = C.ALG_SLHDSA128S_ECDSA_P256_SHA256
    kp = C.generate_keypair(alg)
    sig = C.sign(kp, CTX, M)
    return {"alg": alg, "kp": kp, "pub": kp.public(), "sig": sig}


def test_slhdsa_sign_verify_roundtrip(slhdsa_signed):
    s = slhdsa_signed
    assert C.verify(s["pub"], CTX, M, s["sig"]) is True


def test_slhdsa_primitive_fips205_structural(slhdsa_signed):
    # Cheap structural FIPS-205 SLH-DSA-SHA2-128s invariants (full NIST ACVP
    # KAT validation was the Step-3 gate; not re-run per suite).
    import slhdsa

    p = slhdsa.sha2_128s
    assert (p.n, p.h, p.d, p.a, p.k, p.m) == (16, 63, 7, 12, 14, 30)
    # signature size for SLH-DSA-SHA2-128s is exactly 7856 bytes (FIPS-205)
    _, _, pq_sig = C.decode_composite(slhdsa_signed["sig"])
    assert len(pq_sig) == 7856


def test_slhdsa_native_ctx_label_binding_is_active(slhdsa_signed):
    # Decision SLHDSA-CTX -> (ii): prove slhdsa_ctx = Label actually contributes
    # to verification (the native ctx binding is active, not silently ignored).
    s = slhdsa_signed
    alg, pub = s["alg"], s["pub"]
    _, _, pq_sig = C.decode_composite(s["sig"])
    mprime = C.build_message_representative(alg, CTX, M)
    backend = alg._backend()
    # correct native ctx (= Label) verifies
    assert backend.verify(pub.pq_public, mprime, pq_sig, native_ctx=alg.label) is True
    # a DIFFERENT native ctx fails -> the slhdsa_ctx binding is load-bearing
    assert backend.verify(pub.pq_public, mprime, pq_sig, native_ctx=b"COMPSIG-WRONG-LABEL") is False
    # empty native ctx (the pre-(ii) behavior) now also fails
    assert backend.verify(pub.pq_public, mprime, pq_sig, native_ctx=b"") is False


# ===========================================================================
# (b) Downgrade-rejection (AND-verify decision logic; QorTroller-owned)
# ===========================================================================


def _ec_pq_halves(alg):
    kp = C.generate_keypair(alg)
    sig = C.sign(kp, CTX, M)
    label, ec_sig, pq_sig = C.decode_composite(sig)
    return kp, label, ec_sig, pq_sig


def test_missing_pq_half_rejected():
    _, label, ec_sig, _ = _ec_pq_halves(C.ALG_MLDSA44_ECDSA_P256_SHA256)
    blob = (
        bytes([0x01, len(label)]) + label
        + len(ec_sig).to_bytes(2, "big") + ec_sig
        + (0).to_bytes(4, "big")  # pq_len = 0
    )
    with pytest.raises(ValueError, match="post-quantum"):
        C.decode_composite(blob)


def test_missing_ecdsa_half_rejected():
    _, label, _, pq_sig = _ec_pq_halves(C.ALG_MLDSA44_ECDSA_P256_SHA256)
    blob = (
        bytes([0x01, len(label)]) + label
        + (0).to_bytes(2, "big")  # ec_len = 0
        + len(pq_sig).to_bytes(4, "big") + pq_sig
    )
    with pytest.raises(ValueError, match="classical"):
        C.decode_composite(blob)


def test_ecdsa_only_fallback_blob_rejected():
    # An attacker presents an "ECDSA-only" signature (no PQ): there is NO
    # OR-composition / fallback - verify must return False, never True.
    kp, label, ec_sig, _ = _ec_pq_halves(C.ALG_MLDSA44_ECDSA_P256_SHA256)
    blob = (
        bytes([0x01, len(label)]) + label
        + len(ec_sig).to_bytes(2, "big") + ec_sig
        + (0).to_bytes(4, "big")
    )
    assert C.verify(kp.public(), CTX, M, blob) is False


@pytest.mark.parametrize(
    "blob",
    [b"", b"\x01", b"\x02" + b"\x00" * 8, b"\x01\xff", b"\x01\x00\x00\x05\x00"],
)
def test_malformed_container_rejected(blob):
    with pytest.raises(ValueError):
        C.decode_composite(blob)


def test_trailing_bytes_rejected():
    _, label, ec_sig, pq_sig = _ec_pq_halves(C.ALG_MLDSA44_ECDSA_P256_SHA256)
    good = C.encode_composite(label, ec_sig, pq_sig)
    with pytest.raises(ValueError, match="trailing"):
        C.decode_composite(good + b"\x00")


# ===========================================================================
# (c) Domain-separation (ctx + commitment binding; QorTroller-owned)
# ===========================================================================


def test_wrong_ctx_rejected():
    # signed under CTX, verified under a different PATTERN-017 tag -> reject
    kp = C.generate_keypair(C.ALG_MLDSA65_ECDSA_P256_SHA512)
    sig = C.sign(kp, CTX, M)
    assert C.verify(kp.public(), CTX_OTHER, M, sig) is False


def test_wrong_commitment_rejected():
    kp = C.generate_keypair(C.ALG_MLDSA65_ECDSA_P256_SHA512)
    sig = C.sign(kp, CTX, M)
    M_bad = bytes([M[0] ^ 0x01]) + M[1:]
    assert C.verify(kp.public(), CTX, M_bad, sig) is False


def test_both_halves_fail_without_shared_mprime():
    # EDIT-1 binding: both components are bound to the SAME M'. Under a wrong
    # ctx, BOTH the classical and the PQ verification individually fail.
    alg = C.ALG_MLDSA44_ECDSA_P256_SHA256
    kp = C.generate_keypair(alg)
    sig = C.sign(kp, CTX, M)
    _, ec_sig, pq_sig = C.decode_composite(sig)
    mprime_wrong = C.build_message_representative(alg, CTX_OTHER, M)
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives.asymmetric import ec as _ec

    ec_ok = True
    try:
        kp.public().ec_public.verify(ec_sig, mprime_wrong, _ec.ECDSA(alg.ec_hash()))
    except InvalidSignature:
        ec_ok = False
    assert ec_ok is False
    pq_ok = alg._backend().verify(kp.public().pq_public, mprime_wrong, pq_sig)
    assert pq_ok is False


# ===========================================================================
# (e) Algorithm-identifier validation (QorTroller-owned)
# ===========================================================================


def test_relabeled_composite_rejected():
    # Take a valid ML-DSA-44 composite, relabel it as ML-DSA-65 -> reject.
    kp = C.generate_keypair(C.ALG_MLDSA44_ECDSA_P256_SHA256)
    sig = C.sign(kp, CTX, M)
    _, ec_sig, pq_sig = C.decode_composite(sig)
    relabeled = C.encode_composite(C.LABEL_MLDSA65, ec_sig, pq_sig)
    assert C.verify(kp.public(), CTX, M, relabeled) is False


def test_expected_alg_mismatch_rejected():
    # Verifier expects a different tier than the public key's tier -> reject.
    kp = C.generate_keypair(C.ALG_MLDSA44_ECDSA_P256_SHA256)
    sig = C.sign(kp, CTX, M)
    assert (
        C.verify(kp.public(), CTX, M, sig, expected_alg=C.ALG_MLDSA65_ECDSA_P256_SHA512)
        is False
    )


def test_substitution_attack_rejected():
    # Splice a second keypair's PQ half into the first's composite -> reject
    # (the PQ half will not verify against the first key's PQ public key).
    alg = C.ALG_MLDSA65_ECDSA_P256_SHA512
    kp1 = C.generate_keypair(alg)
    kp2 = C.generate_keypair(alg)
    sig1 = C.sign(kp1, CTX, M)
    label, ec_sig1, _ = C.decode_composite(sig1)
    _, _, pq_sig2 = C.decode_composite(C.sign(kp2, CTX, M))
    spliced = C.encode_composite(label, ec_sig1, pq_sig2)
    assert C.verify(kp1.public(), CTX, M, spliced) is False


def test_label_registry_complete():
    assert set(C.ALGS_BY_LABEL) == {
        C.LABEL_MLDSA65,
        C.LABEL_MLDSA44,
        C.LABEL_SLHDSA128S,
    }


# ===========================================================================
# v1.1 capability extension — public-key wire format (backlog #8)
# encode_pubkey / decode_pubkey. Same KAT discipline as the signature vectors.
# ===========================================================================

import slhdsa  # noqa: E402
from cryptography.hazmat.primitives.asymmetric import ec as _ec  # noqa: E402

_FIXED_EC_PUB = _ec.derive_private_key(0x1111, _ec.SECP256R1()).public_key()

# Byte-pinned blob digests for FIXED inputs (fixed-scalar ec pubkey + deterministic
# pq_raw = bytes(range(n) & 0xFF)). PQ keygen is random per run, so the byte-pin is
# over fixed-input construction; the round-trip property tests random keys.
_PUBKEY_KAT_SHA256 = {
    C.LABEL_MLDSA65: ("4850642d5b222834d51f5c6221077346ca00eff39efafc9b628dfa690b5bafd8", 1952, 2058),
    C.LABEL_MLDSA44: ("3634a7e27263d9bd4223bca20930a96523bbf40f1ac5611f21a4f390bdd58e97", 1312, 1418),
    C.LABEL_SLHDSA128S: ("872b9b8ad257738b9135eb3941de648d391bc7746e56d367d5199f8b1375232a", 32, 152),
}


def _fixed_pubkey(alg, n):
    pq_raw = bytes([i & 0xFF for i in range(n)])
    if alg.pq_kind == "slhdsa128s":
        pqpub = slhdsa.PublicKey((pq_raw[:16], pq_raw[16:]), slhdsa.sha2_128s)
    else:
        pqpub = pq_raw
    return C.CompositePublicKey(alg=alg, ec_public=_FIXED_EC_PUB, pq_public=pqpub)


@pytest.mark.parametrize("alg", ALL_ALGS, ids=lambda a: a.label.decode())
def test_pubkey_byte_pinned_kat(alg):
    digest, n, exp_len = _PUBKEY_KAT_SHA256[alg.label]
    blob = C.encode_pubkey(_fixed_pubkey(alg, n))
    assert len(blob) == exp_len
    assert hashlib.sha256(blob).hexdigest() == digest


@pytest.mark.parametrize("alg", ALL_ALGS, ids=lambda a: a.label.decode())
def test_pubkey_envelope_structure(alg):
    # version(1) || label_len(1) || label || ec_len(2) || ec_point(65) || pq_len(4) || pq_raw
    blob = C.encode_pubkey(_fixed_pubkey(alg, C._PQ_PUBKEY_LEN[alg.pq_kind]))
    assert blob[0] == 0x01
    assert blob[1] == len(alg.label)
    off = 2 + len(alg.label)
    ec_len = int.from_bytes(blob[off:off + 2], "big"); off += 2
    assert ec_len == 65
    assert blob[off] == 0x04  # SEC1 uncompressed prefix
    off += ec_len
    pq_len = int.from_bytes(blob[off:off + 4], "big")
    assert pq_len == C._PQ_PUBKEY_LEN[alg.pq_kind]


@pytest.mark.parametrize("alg", MLDSA_ALGS + [C.ALG_SLHDSA128S_ECDSA_P256_SHA256],
                         ids=lambda a: a.label.decode())
def test_pubkey_roundtrip_and_functional(alg):
    # round-trip on REAL random keys: encode -> decode -> re-encode is identical,
    # and a signature made by the keypair verifies under the DECODED public key.
    kp = C.generate_keypair(alg)
    blob = C.encode_pubkey(kp.public())
    decoded = C.decode_pubkey(blob)
    assert C.encode_pubkey(decoded) == blob
    sig = C.sign(kp, CTX, M)
    assert C.verify(decoded, CTX, M, sig) is True


def test_pubkey_version_byte_strict_acceptance():
    # Forward-compatibility lock: ONLY version=0x01 is accepted.
    blob = bytearray(C.encode_pubkey(C.generate_keypair(C.ALG_MLDSA44_ECDSA_P256_SHA256).public()))
    assert C.decode_pubkey(bytes(blob)) is not None  # 0x01 accepted
    for bad in (0x00, 0x02, 0xFF):
        with pytest.raises(ValueError, match="version"):
            C.decode_pubkey(bytes([bad]) + bytes(blob[1:]))


def test_pubkey_malformed_rejected():
    good = C.encode_pubkey(C.generate_keypair(C.ALG_MLDSA44_ECDSA_P256_SHA256).public())
    with pytest.raises(ValueError):
        C.decode_pubkey(good + b"\x00")          # trailing bytes
    with pytest.raises(ValueError):
        C.decode_pubkey(good[:-5])               # truncated pq
    with pytest.raises(ValueError, match="unknown composite label"):
        # valid frame, unknown label
        bad = bytes([0x01, 4]) + b"NOPE" + (65).to_bytes(2, "big") + b"\x04" + b"\x00" * 64 + (32).to_bytes(4, "big") + b"\x00" * 32
        C.decode_pubkey(bad)


def test_pubkey_wrong_pq_width_rejected():
    # an ML-DSA-44 label with an ML-DSA-65-sized pq field must be rejected
    kp = C.generate_keypair(C.ALG_MLDSA65_ECDSA_P256_SHA512)
    blob = C.encode_pubkey(kp.public())  # label=MLDSA65, pq=1952
    # relabel to MLDSA44 (expects 1312) while keeping the 1952-byte pq → width mismatch
    relabeled = bytearray(blob)
    # replace label bytes (both labels differ in length, so rebuild via decode is easier):
    # construct a frame with MLDSA44 label but 1952 pq
    lbl = C.LABEL_MLDSA44
    ec_point = b"\x04" + b"\x11" * 64
    pq = b"\x00" * 1952
    forged = bytes([0x01, len(lbl)]) + lbl + (65).to_bytes(2, "big") + ec_point + (1952).to_bytes(4, "big") + pq
    with pytest.raises(ValueError, match="must be 1312 bytes"):
        C.decode_pubkey(forged)
