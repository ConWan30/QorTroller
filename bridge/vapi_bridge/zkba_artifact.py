"""Phase O3-ZKBA-TRACK1 — Zero-Knowledge Biometric Artifact (ZKBA) primitive.

FROZEN-v1 cryptographic primitive in the PATTERN-017 family. Tenth member
(pending VBDIP-0001 Step 3 Amendment #1 count reconciliation; the State
Assessment §2.3 convention treats it as #10 post-FRR pre-VRR/CDRR).

A ZKBA artifact commits an artifact-class + proof-weight bound composition
of one or more existing FROZEN-v1 primitive commitments. The composition is
canonical: component hashes are sorted lexicographically before hashing,
so the commitment does not depend on caller-side iteration order.

FROZEN FORMULA v1:

    ZKBA_commitment = SHA-256(
        _DOMAIN_TAG             (21 bytes — VAPI-ZKBA-ARTIFACT-v1)
        || zkba_class_byte       (1 byte BE — ZKBAClass IntEnum value)
        || proof_weight_byte     (1 byte BE — ProofWeightClass IntEnum value)
        || n_components_byte     (1 byte — uint8 count of 32B component hashes; 0..255)
        || sorted_component_hashes (n × 32 bytes — each 32B; sorted lexicographically)
        || ts_ns_be              (8 bytes — uint64 big-endian, unix epoch nanoseconds)
    )                            = 32B output

Pre-image total bytes: 24 + (n_components × 32).

Any change to byte order, ZKBAClass enum values, ProofWeightClass enum
values, domain tag string, or hash algorithm requires ZKBA v2 + new
domain tag. v1 is permanently frozen.

VBDIP-0002 §5 binds artifact classes; §6 binds proof-weight taxonomy.
The IntEnum values pin the bytewise representation that the FROZEN-v1
formula commits to.

Author: VAPI Architect, sole deployer (0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692)
Date: 2026-05-10
"""
import hashlib
import struct
from dataclasses import dataclass, field
from enum import IntEnum


_DOMAIN_TAG = b"VAPI-ZKBA-ARTIFACT-v1"  # 21 bytes — FROZEN; never reused
_COMPONENT_HASH_LEN = 32                  # FROZEN; each component is exactly 32 bytes (SHA-256 output)


class ZKBAClass(IntEnum):
    """ZKBA artifact class per VBDIP-0002 §5. FROZEN-v1 enum values.

    Any rename / value change / addition requires ZKBA v2 + new domain tag.
    The bytewise encoding (1 byte BE) commits to these values.
    """
    AIT          = 1   # §5.1 Active Isometric Trigger threshold
    GIC          = 2   # §5.2 Grind Integrity Chain milestone
    VHP          = 3   # §5.3 Verified Human Proof credential state
    HARDWARE     = 4   # §5.4 Certified hardware participation
    CONSENT      = 5   # §5.5 Per-category consent authorization
    TOURNAMENT   = 6   # §5.6 Tournament eligibility composite
    MARKET       = 7   # §5.7 Marketplace buyer-facing wrapper


class ProofWeightClass(IntEnum):
    """ZKBA proof-weight class per VBDIP-0002 §6. FROZEN-v1 enum values.

    Any rename / value change / addition requires ZKBA v2 + new domain tag.
    The bytewise encoding (1 byte BE) commits to these values.
    """
    DIRECT_HID                = 1   # §6.1 fresh capture + ZK + PCC NOMINAL + APOP ACTIVE_MATCH_PLAY
    CALIBRATION_PLUS_CONTEXT  = 2   # §6.2 calibration evidence + gameplay context
    CHAIN_ONLY                = 3   # §6.3 on-chain state only; no fresh biometric
    MARKETPLACE_DERIVED       = 4   # §6.4 derived from existing anchored artifact
    DEMO                      = 5   # §6.5 non-production; visibly watermarked (>=15% diagonal)
    FROZEN_DISABLED           = 6   # §6.6 reserved layer or gated feature; cannot render active


@dataclass(frozen=True, slots=True)
class ZKBADraftResult:
    """Result of compute_zkba_commitment() — slot-pinned, immutable.

    Fields commit to the FROZEN-v1 formula inputs that produced commitment_hex.
    Any caller may recompute the commitment from these fields to verify
    determinism.
    """
    commitment_hex:       str                              # 64-char lowercase hex
    zkba_class:           ZKBAClass
    proof_weight:         ProofWeightClass
    preimage_components:  tuple[bytes, ...] = field(default_factory=tuple)  # original (unsorted) component hashes
    ts_ns:                int = 0                           # uint64 nanoseconds


def compute_zkba_commitment(
    *,
    zkba_class: ZKBAClass,
    proof_weight: ProofWeightClass,
    component_hashes: tuple[bytes, ...],
    ts_ns: int,
) -> bytes:
    """Compute the 32-byte ZKBA commitment per FROZEN-v1 formula.

    Args:
        zkba_class:       Artifact class (1B BE — see ZKBAClass).
        proof_weight:     Proof-weight class (1B BE — see ProofWeightClass).
        component_hashes: Tuple of 32-byte SHA-256 component hashes. Each
                          MUST be exactly 32 bytes. Tuple length 0..255.
                          Order does NOT affect commitment: hashes are
                          sorted lexicographically before hashing for
                          canonical commitment.
        ts_ns:            Unix timestamp in nanoseconds (uint64 BE).

    Returns:
        32-byte SHA-256 commitment.

    Raises:
        TypeError:  if zkba_class or proof_weight is not the expected IntEnum.
        ValueError: if any component_hash is not exactly 32 bytes, or
                    if there are more than 255 component hashes, or
                    if ts_ns is negative / does not fit in uint64.
    """
    if not isinstance(zkba_class, ZKBAClass):
        raise TypeError(
            f"zkba_class must be ZKBAClass; got {type(zkba_class).__name__}"
        )
    if not isinstance(proof_weight, ProofWeightClass):
        raise TypeError(
            f"proof_weight must be ProofWeightClass; got {type(proof_weight).__name__}"
        )
    if not isinstance(component_hashes, tuple):
        raise TypeError(
            f"component_hashes must be a tuple; got {type(component_hashes).__name__}"
        )
    if len(component_hashes) > 255:
        raise ValueError(
            f"too many component hashes: {len(component_hashes)} > 255 (uint8 cap)"
        )
    for i, ch in enumerate(component_hashes):
        if not isinstance(ch, (bytes, bytearray)):
            raise ValueError(
                f"component_hashes[{i}] must be bytes; got {type(ch).__name__}"
            )
        if len(ch) != _COMPONENT_HASH_LEN:
            raise ValueError(
                f"component_hashes[{i}] must be {_COMPONENT_HASH_LEN} bytes; got {len(ch)}"
            )
    if ts_ns < 0 or ts_ns > 0xFFFFFFFFFFFFFFFF:
        raise ValueError(f"ts_ns out of uint64 range: {ts_ns}")

    sorted_hashes = sorted(bytes(ch) for ch in component_hashes)
    return hashlib.sha256(
        _DOMAIN_TAG
        + zkba_class.value.to_bytes(1, "big")
        + proof_weight.value.to_bytes(1, "big")
        + len(component_hashes).to_bytes(1, "big")
        + b"".join(sorted_hashes)
        + struct.pack(">Q", ts_ns)
    ).digest()


def build_zkba_draft(
    *,
    zkba_class: ZKBAClass,
    proof_weight: ProofWeightClass,
    component_hashes: tuple[bytes, ...],
    ts_ns: int,
) -> ZKBADraftResult:
    """Build a ZKBADraftResult by computing the commitment.

    Convenience wrapper: hashes via compute_zkba_commitment(), packages the
    result into a slotted dataclass. Preserves the caller-provided component
    order in preimage_components (so callers can record their intent even
    though the commitment is order-independent).
    """
    commitment = compute_zkba_commitment(
        zkba_class=zkba_class,
        proof_weight=proof_weight,
        component_hashes=component_hashes,
        ts_ns=ts_ns,
    )
    return ZKBADraftResult(
        commitment_hex=commitment.hex(),
        zkba_class=zkba_class,
        proof_weight=proof_weight,
        preimage_components=tuple(bytes(ch) for ch in component_hashes),
        ts_ns=ts_ns,
    )
