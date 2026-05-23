"""QorTroller composite (classical + post-quantum) credential signatures.

Reference implementation of ``wiki/methodology/composite_sig_v1_scope.md``
(DRAFT scope, operator-approved 2026-05-23). Wire-format dependency root for
**P4b** (PoEP commitment registration) and **PoEP P4c** (hybrid signing).

Adopts IETF ``draft-ietf-lamps-pq-composite-sigs-16`` message-binding +
AND-composition. Three tiers (scope-doc Section 3):

  - ML-DSA-65 + ECDSA-P256 + SHA-512
      Label  COMPSIG-MLDSA65-ECDSA-P256-SHA512
      OID    1.3.6.1.5.5.7.6.45   (IETF-registered, draft-16)
  - ML-DSA-44 + ECDSA-P256 + SHA-256
      Label  COMPSIG-MLDSA44-ECDSA-P256-SHA256
      OID    1.3.6.1.5.5.7.6.40   (IETF-registered, draft-16)
  - SLH-DSA-128s + ECDSA-P256 + SHA-256
      Label  COMPSIG-SLHDSA128S-ECDSA-P256-SHA256-QORTROLLER
      OID    QorTroller arc - TBD (deferred until external-need trigger; Decision OID-2b)
      QorTroller-custom; deliberate, bounded divergence from draft-16
      (which registers no SLH-DSA composite). See scope Sections 3.1/3.2/7.

STATUS: DRAFT. No FROZEN-v1 tag pinned (the tag is RESERVED, ceremony ffa887d6;
it freezes only in a separate later ceremony when scope + this module + vectors
land and the operator chooses). Touches no 228-byte PoAC wire format /
SHA-256(raw[:164]) chain hash / contract / state flag. PoEP remains a v0
candidate, default-OFF (poep_enabled=False); the L6B N>=50 gate is unaffected.

ctx-byte-format (LOCKED against draft-16 Section 2.2/3.2):
    M'  = Prefix || Label || len(ctx) || ctx || PH(M)
    Prefix   = b"CompositeAlgorithmSignatures2025"  (32 ASCII bytes)
    Label    = the per-algorithm identifier (registered or QorTroller-allocated)
    len(ctx) = single unsigned octet (0..255)
    ctx      = raw PATTERN-017 family domain-tag bytes, e.g. b"QORTROLLER-POEP-v0"
               (inserted verbatim; NOT hashed, NOT double-length-prefixed; <=255 B)
    M        = the 32-byte PATTERN-017 SHA-256 commitment value
    PH(M)    = the composite hash of M (SHA-512 tier-1, SHA-256 tiers-2/3)

Bounded, documented divergences (scope Section 7):
  (1) mldsa_ctx: PQClean's ML-DSA (via quantcrypt) does not expose the ML-DSA
      context parameter, so draft-16's ``mldsa_ctx = Label`` belt-and-suspenders
      layer cannot be passed into the ML-DSA primitive. Label binding is preserved
      via M' (the load-bearing property holds); this is one fewer defense-in-depth
      layer than strict draft-16 compliance. Inherent to PQClean.
  (2) The SLH-DSA component signs M' binding slhdsa_ctx = Label (the slh-dsa lib
      DOES expose ctx) - draft-16-faithful native PQ-component ctx binding. This
      restores the belt-and-suspenders binding layer for the device-identity tier
      (the longest-lived, highest-stakes credential in the stack) where the
      library exposes the capability. The asymmetry with ML-DSA (#1) is deliberate
      and backend-driven, not uniform-by-default. Label is also bound via M'.
  (3) Outer container: this v1 uses a simple length-prefixed framing (see
      ``encode_composite`` / ``decode_composite``), not draft-16's ASN.1
      CompositeSignatureValue SEQUENCE. The *component* signatures are
      draft-16-conformant; a draft-16 ASN.1 adapter is deferred alongside the
      0x0B precompile adapter (scope Section 4).

Backends (pinned; test-only signing latency at the SLH-DSA tier is acceptable):
  - cryptography >= 46  : ECDSA-P256, SHA-256/512 (classical half)
  - quantcrypt == 1.0.1 : ML-DSA-44 / ML-DSA-65 (PQClean ml-dsa-44 / ml-dsa-65)
  - slh-dsa   == 0.2.2  : SLH-DSA-SHA2-128s (FIPS-205; KAT-validated 42/42 against
                          NIST ACVP SLH-DSA-sigVer-FIPS205, SLH-DSA-SHA2-128s)
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Callable, Optional

# --- classical half -------------------------------------------------------
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.ec import (
    EllipticCurvePrivateKey,
    EllipticCurvePublicKey,
)

# --- post-quantum halves (imported lazily-tolerant) -----------------------
# quantcrypt: ML-DSA-44 / ML-DSA-65 ; slhdsa: SLH-DSA-SHA2-128s
from quantcrypt import dss as _qc_dss
import slhdsa as _slhdsa

# ===========================================================================
# Frozen construction constants (draft-16 + scope-doc lock)
# ===========================================================================

#: draft-16 Section 2.2 domain-separation Prefix - 32 ASCII bytes, verbatim.
PREFIX: bytes = b"CompositeAlgorithmSignatures2025"
assert len(PREFIX) == 32, "Prefix must be exactly 32 bytes (draft-16)"

#: Maximum ctx length (draft-16 Section 3.2: error if len(ctx) > 255).
MAX_CTX_LEN: int = 255

# Per-algorithm Labels (the ASCII alg-id bound into M' and the wire container).
LABEL_MLDSA65 = b"COMPSIG-MLDSA65-ECDSA-P256-SHA512"
LABEL_MLDSA44 = b"COMPSIG-MLDSA44-ECDSA-P256-SHA256"
LABEL_SLHDSA128S = b"COMPSIG-SLHDSA128S-ECDSA-P256-SHA256-QORTROLLER"

# QorTroller composite-sig v1 outer container framing (divergence #3).
_WIRE_VERSION = 0x01
_EC_LEN_BYTES = 2  # ECDSA-P256 DER signature is well under 65535 bytes
_PQ_LEN_BYTES = 4  # PQ signatures: ML-DSA<=3309, SLH-DSA-128s=7856; 4B future-proof


def _ph_sha256(data: bytes) -> bytes:
    return hashlib.sha256(data).digest()


def _ph_sha512(data: bytes) -> bytes:
    return hashlib.sha512(data).digest()


# ===========================================================================
# PQ backend abstraction (opaque pub/priv per kind)
# ===========================================================================


class _PQBackend:
    """Uniform sign/verify over an opaque (pub, priv) pair for one PQ kind."""

    kind: str

    def keygen(self):  # -> (pub, priv)
        raise NotImplementedError

    def sign(self, priv, msg: bytes, native_ctx: bytes = b"") -> bytes:
        raise NotImplementedError

    def verify(self, pub, msg: bytes, sig: bytes, native_ctx: bytes = b"") -> bool:
        raise NotImplementedError


class _MLDSABackend(_PQBackend):
    """ML-DSA via quantcrypt (PQClean). ``native_ctx`` is unavoidably IGNORED:
    PQClean exposes no ML-DSA ctx parameter (divergence #1), so draft-16's
    mldsa_ctx=Label cannot be applied. Label is bound via M'."""

    def __init__(self, kind: str):
        self.kind = kind
        self._impl = {
            "mldsa44": _qc_dss.MLDSA_44,
            "mldsa65": _qc_dss.MLDSA_65,
        }[kind]()

    def keygen(self):
        pk, sk = self._impl.keygen()
        return pk, sk

    def sign(self, priv, msg: bytes, native_ctx: bytes = b"") -> bytes:
        # native_ctx ignored (PQClean has no ctx param) - divergence #1.
        return self._impl.sign(priv, msg)

    def verify(self, pub, msg: bytes, sig: bytes, native_ctx: bytes = b"") -> bool:
        # native_ctx ignored (PQClean has no ctx param) - divergence #1.
        try:
            return bool(self._impl.verify(pub, msg, sig, raises=False))
        except Exception:
            return False


class _SLHDSABackend(_PQBackend):
    """SLH-DSA-SHA2-128s via slh-dsa (FIPS-205). Signs M' with the pure variant
    binding ``native_ctx`` = Label (slhdsa_ctx) - draft-16-faithful native
    PQ-component ctx binding, restoring belt-and-suspenders for the
    device-identity tier where the library exposes the capability (divergence #2)."""

    kind = "slhdsa128s"
    _PARAM = _slhdsa.sha2_128s

    def keygen(self):
        kp = _slhdsa.KeyPair.gen(self._PARAM)
        # hold native key objects (pub: PublicKey, priv: SecretKey)
        return kp.pub, kp.sec

    def sign(self, priv, msg: bytes, native_ctx: bytes = b"") -> bytes:
        # slhdsa_ctx = native_ctx (= Label); randomize=False -> deterministic
        return priv.sign_pure(msg, ctx=native_ctx)

    def verify(self, pub, msg: bytes, sig: bytes, native_ctx: bytes = b"") -> bool:
        try:
            return bool(pub.verify_pure(msg, sig, ctx=native_ctx))
        except Exception:
            return False


# ===========================================================================
# Tier registry
# ===========================================================================


@dataclass(frozen=True)
class CompositeAlg:
    """One composite tier: its Label, hashes, ECDSA hash, OID, PQ backend kind."""

    label: bytes
    pq_kind: str  # "mldsa44" | "mldsa65" | "slhdsa128s"
    ph: Callable[[bytes], bytes]  # PH(M) over the 32-byte commitment
    ec_hash: Callable[[], hashes.HashAlgorithm]  # ECDSA hash over M'
    oid: Optional[str]  # dotted OID, or None for the deferred QorTroller tier

    def _backend(self) -> _PQBackend:
        if self.pq_kind == "slhdsa128s":
            return _SLHDSABackend()
        return _MLDSABackend(self.pq_kind)


ALG_MLDSA65_ECDSA_P256_SHA512 = CompositeAlg(
    label=LABEL_MLDSA65,
    pq_kind="mldsa65",
    ph=_ph_sha512,
    ec_hash=hashes.SHA512,
    oid="1.3.6.1.5.5.7.6.45",
)
ALG_MLDSA44_ECDSA_P256_SHA256 = CompositeAlg(
    label=LABEL_MLDSA44,
    pq_kind="mldsa44",
    ph=_ph_sha256,
    ec_hash=hashes.SHA256,
    oid="1.3.6.1.5.5.7.6.40",
)
ALG_SLHDSA128S_ECDSA_P256_SHA256 = CompositeAlg(
    label=LABEL_SLHDSA128S,
    pq_kind="slhdsa128s",
    ph=_ph_sha256,
    ec_hash=hashes.SHA256,
    oid=None,  # QorTroller arc - TBD (Decision OID-2b)
)

#: Registry keyed by Label (used for algorithm-identifier validation on verify).
ALGS_BY_LABEL = {
    a.label: a
    for a in (
        ALG_MLDSA65_ECDSA_P256_SHA512,
        ALG_MLDSA44_ECDSA_P256_SHA256,
        ALG_SLHDSA128S_ECDSA_P256_SHA256,
    )
}


# ===========================================================================
# Message-binding (M') construction - draft-16 Section 2.2/3.2, ctx LOCKED
# ===========================================================================


def build_message_representative(alg: CompositeAlg, ctx: bytes, commitment: bytes) -> bytes:
    """Return M' = Prefix || Label || len(ctx) || ctx || PH(commitment).

    ``ctx`` is the raw PATTERN-017 family domain-tag bytes (<=255). ``commitment``
    is the 32-byte PATTERN-017 SHA-256 commitment (M). Deterministic - this is the
    byte-pinnable, QorTroller-novel artifact.
    """
    if not isinstance(ctx, (bytes, bytearray)):
        raise TypeError("ctx must be bytes")
    if not isinstance(commitment, (bytes, bytearray)):
        raise TypeError("commitment must be bytes")
    if len(ctx) > MAX_CTX_LEN:
        raise ValueError(f"len(ctx)={len(ctx)} exceeds {MAX_CTX_LEN} (draft-16 Section 3.2)")
    if len(commitment) != 32:
        raise ValueError(
            f"commitment must be the 32-byte PATTERN-017 SHA-256 value, got {len(commitment)}"
        )
    return PREFIX + alg.label + bytes([len(ctx)]) + bytes(ctx) + alg.ph(bytes(commitment))


# ===========================================================================
# Keypairs
# ===========================================================================


@dataclass
class CompositeKeyPair:
    alg: CompositeAlg
    ec_private: EllipticCurvePrivateKey
    pq_public: object
    pq_private: object

    def public(self) -> "CompositePublicKey":
        return CompositePublicKey(self.alg, self.ec_private.public_key(), self.pq_public)


@dataclass
class CompositePublicKey:
    alg: CompositeAlg
    ec_public: EllipticCurvePublicKey
    pq_public: object


def generate_keypair(alg: CompositeAlg) -> CompositeKeyPair:
    """Generate an ECDSA-P256 keypair + the tier's PQ keypair."""
    ec_priv = ec.generate_private_key(ec.SECP256R1())
    pq_pub, pq_priv = alg._backend().keygen()
    return CompositeKeyPair(alg=alg, ec_private=ec_priv, pq_public=pq_pub, pq_private=pq_priv)


# ===========================================================================
# Wire container (QorTroller composite-sig v1 framing - divergence #3)
# ===========================================================================


def encode_composite(label: bytes, ec_sig: bytes, pq_sig: bytes) -> bytes:
    """version || label_len(1) || label || ec_len(2) || ec_sig || pq_len(4) || pq_sig."""
    if len(label) > 255:
        raise ValueError("label too long")
    if len(ec_sig) >= (1 << (8 * _EC_LEN_BYTES)):
        raise ValueError("ec_sig too long for framing")
    if len(pq_sig) >= (1 << (8 * _PQ_LEN_BYTES)):
        raise ValueError("pq_sig too long for framing")
    return (
        bytes([_WIRE_VERSION])
        + bytes([len(label)])
        + label
        + len(ec_sig).to_bytes(_EC_LEN_BYTES, "big")
        + ec_sig
        + len(pq_sig).to_bytes(_PQ_LEN_BYTES, "big")
        + pq_sig
    )


def decode_composite(blob: bytes) -> tuple[bytes, bytes, bytes]:
    """Inverse of ``encode_composite``. Raises ValueError on any malformation
    (truncation, trailing bytes, version mismatch, or a missing/empty half)."""
    try:
        mv = memoryview(blob)
        off = 0
        if len(mv) < 2:
            raise ValueError("too short")
        if mv[0] != _WIRE_VERSION:
            raise ValueError(f"unknown wire version {mv[0]}")
        off = 1
        label_len = mv[off]
        off += 1
        label = bytes(mv[off : off + label_len])
        if len(label) != label_len:
            raise ValueError("truncated label")
        off += label_len
        ec_len = int.from_bytes(mv[off : off + _EC_LEN_BYTES], "big")
        off += _EC_LEN_BYTES
        ec_sig = bytes(mv[off : off + ec_len])
        if len(ec_sig) != ec_len:
            raise ValueError("truncated ec_sig")
        off += ec_len
        pq_len = int.from_bytes(mv[off : off + _PQ_LEN_BYTES], "big")
        off += _PQ_LEN_BYTES
        pq_sig = bytes(mv[off : off + pq_len])
        if len(pq_sig) != pq_len:
            raise ValueError("truncated pq_sig")
        off += pq_len
        if off != len(mv):
            raise ValueError("trailing bytes")
    except (IndexError, ValueError) as e:
        raise ValueError(f"malformed composite signature: {e}") from None
    # AND-composition: both halves MUST be present and non-empty (downgrade resistance).
    if len(ec_sig) == 0:
        raise ValueError("missing classical (ECDSA) half")
    if len(pq_sig) == 0:
        raise ValueError("missing post-quantum half")
    return label, ec_sig, pq_sig


# ===========================================================================
# Sign / verify
# ===========================================================================


def sign(keypair: CompositeKeyPair, ctx: bytes, commitment: bytes) -> bytes:
    """Produce an AND-composite signature over M'(alg, ctx, commitment).

    Both component signatures are computed over the identical M'. Returns the
    encoded composite signature (see ``encode_composite``).
    """
    alg = keypair.alg
    mprime = build_message_representative(alg, ctx, commitment)
    ec_sig = keypair.ec_private.sign(mprime, ec.ECDSA(alg.ec_hash()))
    # PQ component binds native_ctx=Label: ignored by ML-DSA (PQClean, divergence
    # #1), bound as slhdsa_ctx by SLH-DSA (divergence #2). Label is in M' regardless.
    pq_sig = alg._backend().sign(keypair.pq_private, mprime, native_ctx=alg.label)
    return encode_composite(alg.label, ec_sig, pq_sig)


def verify(
    public: CompositePublicKey,
    ctx: bytes,
    commitment: bytes,
    composite_sig: bytes,
    expected_alg: Optional[CompositeAlg] = None,
) -> bool:
    """AND-verify a composite signature. Returns True iff:

      * the container is well-formed with BOTH halves present,
      * the embedded Label matches the expected algorithm (alg-id validation),
      * the ECDSA half verifies over M', AND
      * the PQ half verifies over M'.

    No exceptions for cryptographic failure - any failure returns False.
    There is NO OR-composition and NO ECDSA-fallback-on-PQ-failure.
    """
    alg = expected_alg or public.alg
    # alg-id validation: the verifier's expected alg must match the public key's alg.
    if alg.label != public.alg.label:
        return False
    try:
        label, ec_sig, pq_sig = decode_composite(composite_sig)
    except ValueError:
        return False
    # algorithm-identifier validation: presented Label must match expected alg.
    if label != alg.label:
        return False
    try:
        mprime = build_message_representative(alg, ctx, commitment)
    except (ValueError, TypeError):
        return False
    # classical half
    try:
        public.ec_public.verify(ec_sig, mprime, ec.ECDSA(alg.ec_hash()))
    except InvalidSignature:
        return False
    except Exception:
        return False
    # post-quantum half - both must pass (AND). native_ctx=Label mirrors sign().
    if not alg._backend().verify(public.pq_public, mprime, pq_sig, native_ctx=alg.label):
        return False
    return True


# ===========================================================================
# v1.1 capability extension - public-key wire format (backlog #8)
# See wiki/methodology/composite_sig_v1_scope.md §9. Capability extension, NOT a
# spec change: M' construction, tier table, OIDs, divergences all UNTOUCHED.
# ===========================================================================

#: Expected ML-DSA / SLH-DSA raw public-key lengths per pq_kind (FIPS 204 / 205).
_PQ_PUBKEY_LEN = {
    "mldsa65": 1952,      # FIPS 204
    "mldsa44": 1312,      # FIPS 204
    "slhdsa128s": 32,     # FIPS 205 (PK.seed16 || PK.root16)
}


def _ec_pubkey_to_bytes(ec_public: EllipticCurvePublicKey) -> bytes:
    """SEC1 uncompressed P-256 point: 0x04 || X(32) || Y(32) = 65 bytes."""
    return ec_public.public_bytes(
        serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint
    )


def _pq_pubkey_to_bytes(alg: CompositeAlg, pq_public: object) -> bytes:
    """Raw PQ public-key bytes per tier.

    ML-DSA: quantcrypt returns the public key as raw FIPS-204 bytes already.
    SLH-DSA-128s: slh-dsa exposes PublicKey.key == (PK.seed16, PK.root16); concatenate
    key[0] || key[1] = FIPS-205 §10 canonical pk = PK.seed || PK.root (seed first).
    """
    if alg.pq_kind == "slhdsa128s":
        seed, root = pq_public.key  # (PK.seed16, PK.root16) - FIPS-205 tuple order
        return bytes(seed) + bytes(root)
    return bytes(pq_public)  # ML-DSA: raw FIPS-204 bytes


def encode_pubkey(public: CompositePublicKey) -> bytes:
    """Serialize a CompositePublicKey to the v1.1 wire format.

        version(1)=0x01 || label_len(1) || label
        || ec_len(2,BE) || ec_point(65, SEC1 uncompressed)
        || pq_len(4,BE) || pq_pubkey_raw (1952 / 1312 / 32 per tier)

    Length-prefixed framing mirrors encode_composite. Deterministic / byte-pinnable.
    """
    alg = public.alg
    ec_point = _ec_pubkey_to_bytes(public.ec_public)
    pq_raw = _pq_pubkey_to_bytes(alg, public.pq_public)
    if len(alg.label) > 255:
        raise ValueError("label too long")
    if len(ec_point) >= (1 << (8 * _EC_LEN_BYTES)):
        raise ValueError("ec_point too long for framing")
    if len(pq_raw) >= (1 << (8 * _PQ_LEN_BYTES)):
        raise ValueError("pq_pubkey too long for framing")
    return (
        bytes([_WIRE_VERSION])
        + bytes([len(alg.label)])
        + alg.label
        + len(ec_point).to_bytes(_EC_LEN_BYTES, "big")
        + ec_point
        + len(pq_raw).to_bytes(_PQ_LEN_BYTES, "big")
        + pq_raw
    )


def decode_pubkey(blob: bytes) -> CompositePublicKey:
    """Inverse of ``encode_pubkey``. Reconstructs a CompositePublicKey.

    Forward-compatibility: accepts ONLY version=0x01. A future v2 of the pubkey wire
    format requires a new domain tag/Label or a new function (e.g. encode_pubkey_v2),
    NOT a version-range expansion. Version-byte changes are explicit freeze events.

    Raises ValueError on any malformation (truncation, trailing bytes, unknown version,
    unknown label, wrong-width fields).
    """
    try:
        mv = memoryview(blob)
        if len(mv) < 2:
            raise ValueError("too short")
        if mv[0] != _WIRE_VERSION:
            raise ValueError(f"unknown wire version {mv[0]} (only 0x01 accepted)")
        off = 1
        label_len = mv[off]
        off += 1
        label = bytes(mv[off : off + label_len])
        if len(label) != label_len:
            raise ValueError("truncated label")
        off += label_len
        ec_len = int.from_bytes(mv[off : off + _EC_LEN_BYTES], "big")
        off += _EC_LEN_BYTES
        ec_point = bytes(mv[off : off + ec_len])
        if len(ec_point) != ec_len:
            raise ValueError("truncated ec_point")
        off += ec_len
        pq_len = int.from_bytes(mv[off : off + _PQ_LEN_BYTES], "big")
        off += _PQ_LEN_BYTES
        pq_raw = bytes(mv[off : off + pq_len])
        if len(pq_raw) != pq_len:
            raise ValueError("truncated pq_pubkey")
        off += pq_len
        if off != len(mv):
            raise ValueError("trailing bytes")
    except (IndexError, ValueError) as e:
        raise ValueError(f"malformed composite pubkey: {e}") from None

    alg = ALGS_BY_LABEL.get(label)
    if alg is None:
        raise ValueError(f"unknown composite label {label!r}")
    if ec_len != 65:
        raise ValueError(f"ec_point must be 65 bytes (SEC1 uncompressed), got {ec_len}")
    expected_pq = _PQ_PUBKEY_LEN[alg.pq_kind]
    if pq_len != expected_pq:
        raise ValueError(
            f"pq_pubkey for {alg.pq_kind} must be {expected_pq} bytes, got {pq_len}"
        )
    # reconstruct ECDSA-P256 public key from the SEC1 uncompressed point
    try:
        ec_public = ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), ec_point)
    except ValueError as e:
        raise ValueError(f"invalid ec_point: {e}") from None
    # reconstruct the PQ public key
    if alg.pq_kind == "slhdsa128s":
        pq_public: object = _slhdsa.PublicKey((pq_raw[:16], pq_raw[16:]), _slhdsa.sha2_128s)
    else:
        pq_public = pq_raw  # ML-DSA: raw bytes consumed directly by the backend verify
    return CompositePublicKey(alg=alg, ec_public=ec_public, pq_public=pq_public)
