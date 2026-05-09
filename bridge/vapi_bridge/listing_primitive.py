"""Phase 238-MARKETPLACE — LISTING-v1 primitive. FROZEN FORMULA v1.

Seventh member of the PATTERN-016 FROZEN-v1 family alongside GIC (Phase 235-A),
WEC (Phase 236-WATCHDOG), VAME (Phase 236-VAME), CORPUS-SNAPSHOT (Phase 237.5),
CONSENT (Phase 237), and BIOMETRIC-SNAPSHOT (Phase 237-ZK-SEPPROOF).

What this primitive binds (vs the prior six):
    LISTING-v1 is the per-listing cryptographic provenance commitment for
    the Provenance-Anchored Listing Layer (PALL) on top of the Phase 69
    VAPIDataMarketplace.  Each listing references up to 5 prior FROZEN-v1
    anchors (SEPPROOF + BIOMETRIC-SNAPSHOT + CORPUS-SNAPSHOT + GIC + CONSENT
    bitmask) plus the data class + price + IPFS CID hash binding the listing
    metadata archive.  The on-chain LISTING-v1 anchor is what
    VAPIDataMarketplaceListings.sol reads to compute the listing's
    multiplier tier — multiplier is enforced cryptographically, not
    seller-attested.

    Where CORPUS-SNAPSHOT-v1 binds governance posture (ratio + N + wiki +
    agent_root) and BIOMETRIC-SNAPSHOT-v1 binds geometric inputs
    (centroids + cov_inv), LISTING-v1 binds the *economic surface* — what
    a buyer is paying for in this specific session listing.

Snapshot triggers (caller-driven; this module is pure functions):
    - Operator-triggered listing creation via POST /operator/list-data-session
    - Each listing produces exactly one LISTING-v1 commitment, anchored
      via AdjudicationRegistry.recordAdjudication with the LISTING_DEVICE_ID
      constant.

LISTING-v1 commitment formula:
    commitment = SHA-256(
        b"VAPI-LISTING-v1"          (16 bytes)  — domain separation
        || sepproof_commitment      (32 bytes)  — Phase 237 SEPPROOF anchor
                                                    (32 zero bytes if listing
                                                    is Tier 1 Basic without
                                                    SEPPROOF binding)
        || biometric_snapshot_hash  (32 bytes)  — Phase 237 BIOMETRIC-SNAPSHOT
                                                    (32 zero bytes if absent)
        || corpus_snapshot_hash     (32 bytes)  — Phase 237.5 CORPUS-SNAPSHOT
                                                    (32 zero bytes if absent)
        || gic_hash                 (32 bytes)  — GIC chain link
                                                    (32 zero bytes if absent)
        || consent_bitmask_be       (4 bytes)   — uint32 BE: CONSENT category mask
                                                    (Phase 237 enum: bit 0 =
                                                    TOURNAMENT_GATE, bit 1 =
                                                    ANONYMIZED_RESEARCH, bit 2 =
                                                    MANUFACTURER_CERT, bit 3 =
                                                    MARKETPLACE).  MARKETPLACE
                                                    bit MUST be set for any
                                                    valid listing.
        || data_class_be            (1 byte)    — uint8: Phase 69 enum value
                                                    (0..6 — see DATA_TAXONOMY)
        || price_micro_iotx_be      (8 bytes)   — uint64 BE: price * 1e6 IOTX
                                                    (matches CORPUS-SNAPSHOT-v1's
                                                    ratio_milli precedent)
        || ipfs_cid_hash            (32 bytes)  — SHA-256 of CIDv1 string
                                                    (binds data archive)
        || ts_ns_be                 (8 bytes)   — uint64 BE: listing time
    )                                = 229 bytes -> SHA-256 -> 32 bytes

Scale factor (FROZEN): 1_000_000 (1e6) for price.
    Matches CORPUS-SNAPSHOT-v1's `ratio_milli` precedent.  uint64 with 1e6
    scale supports prices up to 18.4 billion micro-IOTX (~18.4 trillion IOTX
    full units) — comfortable for any realistic listing.

Endian (FROZEN): big-endian throughout.

Anchor naming (FROZEN — matches PATTERN-016 family precedent):
    The on-chain attribution constant uses underscores:
        _LISTING_DEVICE_ID = SHA-256(b"VAPI_LISTING_v1")
    The commitment domain tag uses hyphens:
        b"VAPI-LISTING-v1"
    This intentional asymmetry mirrors corpus_snapshot.py and
    biometric_snapshot.py — chain attribution sourceType is underscore-
    delimited; commitment-domain separation is hyphen-delimited.

Optional anchor pattern (Tier 1 Basic listings):
    A Basic-tier listing is one with CONSENT only (no SEPPROOF / BIOMETRIC /
    CORPUS / GIC).  In this case, callers pass 32 zero bytes for the absent
    anchor fields.  The contract-side `_computeTier()` reads
    `IAdjudicationRegistry.isRecorded(commitment)` for each non-zero anchor
    and counts which are present to assign multiplier tier.  Zero-bytes
    anchor inputs collapse to "anchor not present" without breaking the
    canonical body length.

CONSENT bitmask requirement:
    Every valid LISTING-v1 commitment MUST have bit 3 (MARKETPLACE) set in
    consent_bitmask.  Listings without the MARKETPLACE consent are
    cryptographically invalid — the seller has not authorized marketplace
    distribution of their data.  This is verified at compute_listing_commitment
    via ValueError raise rather than silent acceptance.

Any change to byte order, domain tag, scale factor, sort rule, or signed vs
unsigned encoding requires v2 + new tag.  v1 is permanently frozen.
"""
from __future__ import annotations

import hashlib
import struct
from typing import Optional

# ── Frozen constants ─────────────────────────────────────────────────────────

_LISTING_TAG = b"VAPI-LISTING-v1"     # 15 bytes (matches the design's "16-byte" approximation;
                                       # actual length is 15 — verified via len() in tests)
_PRICE_SCALE = 1_000_000               # micro-IOTX, matches CORPUS-SNAPSHOT ratio_milli precedent

# CONSENT bitmask bits — must match Phase 237 ConsentCategory enum
_CONSENT_BIT_TOURNAMENT_GATE     = 1 << 0   # bit 0
_CONSENT_BIT_ANONYMIZED_RESEARCH = 1 << 1   # bit 1
_CONSENT_BIT_MANUFACTURER_CERT   = 1 << 2   # bit 2
_CONSENT_BIT_MARKETPLACE         = 1 << 3   # bit 3 — required for listings

_ZERO_HASH = b"\x00" * 32

# Phase 69 DATA_TAXONOMY (mirror — kept in sync with VAPIDataMarketplace.sol enum)
DATA_CLASS_SESSION     = 0
DATA_CLASS_CALIBRATION = 1
DATA_CLASS_PROOF       = 2
DATA_CLASS_RULING      = 3
DATA_CLASS_BIOMETRIC   = 4
DATA_CLASS_ORACLE      = 5
DATA_CLASS_REWARD      = 6
_DATA_CLASS_VALID_RANGE = range(0, 7)


def _validate_anchor_bytes(name: str, value: bytes) -> bytes:
    """Validate a 32-byte anchor field. None / empty -> zero bytes (absent)."""
    if value is None or value == b"":
        return _ZERO_HASH
    if not isinstance(value, (bytes, bytearray)):
        raise ValueError(f"{name} must be bytes, got {type(value).__name__}")
    if len(value) != 32:
        raise ValueError(f"{name} must be 32 bytes, got {len(value)}")
    return bytes(value)


def encode_price_micro(price_iotx: float) -> int:
    """Convert a price in IOTX units to uint64 micro-IOTX (price * 1e6).

    Matches CORPUS-SNAPSHOT-v1's `encode_ratio_milli` shape exactly.
    """
    if price_iotx is None:
        price_iotx = 0.0
    n = int(round(float(price_iotx) * _PRICE_SCALE))
    if n < 0:
        raise ValueError(f"price_micro_iotx must be >= 0, got {n}")
    if n > 0xFFFFFFFFFFFFFFFF:
        raise ValueError(f"price_micro_iotx overflow uint64: {n}")
    return n


def compute_ipfs_cid_hash(cid_string: str) -> bytes:
    """Hash a CIDv1 string to 32 bytes via SHA-256.

    The full CIDv1 string can be variable length; the LISTING-v1 commitment
    binds via SHA-256 hash to keep the canonical body fixed-length.  The
    actual CID is stored off-chain alongside the listing for buyer retrieval.
    """
    if cid_string is None:
        return _ZERO_HASH
    if not isinstance(cid_string, str):
        raise ValueError(
            f"cid_string must be str, got {type(cid_string).__name__}"
        )
    return hashlib.sha256(cid_string.encode("utf-8")).digest()


def compute_listing_commitment(
    sepproof_commitment: Optional[bytes],
    biometric_snapshot_hash: Optional[bytes],
    corpus_snapshot_hash: Optional[bytes],
    gic_hash: Optional[bytes],
    consent_bitmask: int,
    data_class: int,
    price_iotx: float,
    ipfs_cid: str,
    ts_ns: int,
) -> bytes:
    """Compute the LISTING-v1 commitment — FROZEN formula.

    Args:
        sepproof_commitment:     Phase 237 SEPPROOF anchor (32 bytes, or None / b"" for absent)
        biometric_snapshot_hash: Phase 237 BIOMETRIC-SNAPSHOT anchor (32 bytes, or None / b"")
        corpus_snapshot_hash:    Phase 237.5 CORPUS-SNAPSHOT anchor (32 bytes, or None / b"")
        gic_hash:                GIC chain link hash (32 bytes, or None / b"")
        consent_bitmask:         uint32 — bit 3 (MARKETPLACE) MUST be set
        data_class:              uint8 in [0, 6] (Phase 69 DATA_TAXONOMY enum)
        price_iotx:              non-negative float price in IOTX units
        ipfs_cid:                CIDv1 string for the off-chain listing metadata archive
        ts_ns:                   uint64 unix timestamp in nanoseconds

    Returns:
        32-byte SHA-256 digest of the canonical body.

    Raises:
        ValueError on any field violating its FROZEN-v1 contract.
    """
    # Defensive validations
    if not (0 <= int(consent_bitmask) <= 0xFFFFFFFF):
        raise ValueError(
            f"consent_bitmask out of uint32 range: {consent_bitmask}"
        )
    if not (int(consent_bitmask) & _CONSENT_BIT_MARKETPLACE):
        raise ValueError(
            "consent_bitmask must have MARKETPLACE bit (bit 3) set — "
            "listings require explicit marketplace consent grant"
        )
    if int(data_class) not in _DATA_CLASS_VALID_RANGE:
        raise ValueError(
            f"data_class must be in [0, 6] (Phase 69 DATA_TAXONOMY), "
            f"got {data_class}"
        )
    if not (0 <= int(ts_ns) <= 0xFFFFFFFFFFFFFFFF):
        raise ValueError(f"ts_ns out of uint64 range: {ts_ns}")

    # Normalise anchor fields (32-byte each; absent -> zero bytes)
    sep_bytes  = _validate_anchor_bytes("sepproof_commitment", sepproof_commitment)
    bio_bytes  = _validate_anchor_bytes("biometric_snapshot_hash", biometric_snapshot_hash)
    corp_bytes = _validate_anchor_bytes("corpus_snapshot_hash", corpus_snapshot_hash)
    gic_bytes  = _validate_anchor_bytes("gic_hash", gic_hash)

    # Compose canonical bytestream
    body = bytearray()
    body.extend(_LISTING_TAG)                                    # 15 bytes
    body.extend(sep_bytes)                                       # 32
    body.extend(bio_bytes)                                       # 32
    body.extend(corp_bytes)                                      # 32
    body.extend(gic_bytes)                                       # 32
    body.extend(struct.pack(">I", int(consent_bitmask)))         # 4
    body.append(int(data_class))                                 # 1
    body.extend(struct.pack(">Q", encode_price_micro(price_iotx)))  # 8
    body.extend(compute_ipfs_cid_hash(ipfs_cid))                 # 32
    body.extend(struct.pack(">Q", int(ts_ns)))                   # 8

    return hashlib.sha256(bytes(body)).digest()


def expected_body_length() -> int:
    """Return the canonical body length (FROZEN at v1) — for tests + validation.

    Layout: 15 (tag) + 32*4 (anchors) + 4 (consent_bitmask) + 1 (data_class)
            + 8 (price) + 32 (cid_hash) + 8 (ts_ns) = 196 bytes
    """
    return (
        len(_LISTING_TAG)   # 15
        + 32 * 4            # sepproof + biometric + corpus + gic
        + 4                 # consent_bitmask
        + 1                 # data_class
        + 8                 # price_micro_iotx
        + 32                # ipfs_cid_hash
        + 8                 # ts_ns
    )


def count_anchors_present(
    sepproof_commitment: Optional[bytes],
    biometric_snapshot_hash: Optional[bytes],
    corpus_snapshot_hash: Optional[bytes],
    gic_hash: Optional[bytes],
) -> int:
    """Count how many of the four anchor inputs are non-zero / non-None.

    Used by the on-chain extension contract to compute multiplier tier:
      - 0 anchors present (CONSENT only):  Tier Basic     (1.0x)
      - 1 anchor (CONSENT + GIC|CORPUS):   Tier Verified  (1.5x)
      - 3 anchors (SEPPROOF+BIO+CONSENT):  Tier Attested  (2.0x)
      - 4 anchors + tournament VHP:        Tier Premium   (3.0x)

    The bridge-side count is informational only (mirrors what the on-chain
    contract computes via IAdjudicationRegistry.isRecorded).  The contract
    verdict is authoritative; this helper exists for caller UX.
    """
    count = 0
    for anchor in (sepproof_commitment, biometric_snapshot_hash,
                   corpus_snapshot_hash, gic_hash):
        if anchor is not None and anchor != b"" and anchor != _ZERO_HASH:
            if isinstance(anchor, (bytes, bytearray)) and len(anchor) == 32:
                count += 1
    return count
