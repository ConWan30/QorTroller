"""Phase 237-CONSENT — Per-category consent primitive. FROZEN FORMULA v1.

Fifth FROZEN-v1 cryptographic primitive in the VAPI chain stack
(after GIC / WEC / VAME / CORPUS-SNAPSHOT — see PATTERN-016 in VAPI_MEMORY.md).
Every member of the family follows the same shape: SHA-256, big-endian byte
order, explicit domain tag, deterministic int encoding for variable inputs,
v1 permanently frozen with a documented v2 migration path.

Why per-category: tournament-gate consent and marketplace consent are
fundamentally different privacy decisions — one is required for play, the
other is monetisation opt-in. A single binary "consent_given" can never model
this. This module encodes the four categories (matching VAPI's tokenomics
tier table and the Phase 236+ plan):

    TOURNAMENT_GATE       — required for VAPI tournament eligibility
    ANONYMIZED_RESEARCH   — opt-in for population-level research data
    MANUFACTURER_CERT     — opt-in for hardware OEM cert-evaluation pool
    MARKETPLACE           — opt-in for VAPIDataMarketplace listing

Categories are stored as a uint32 bitmask (`bit_n = 1` iff category(n)
granted) so a single signature can grant multiple categories atomically.
Zero bits → no consent → fail-closed for any category-gated operation.

CONSENT_v1 commitment formula:
    consent_hash = SHA-256(
        b"VAPI-CONSENT-v1"          (15 bytes)  — domain separation
        || device_id_bytes32        (32 bytes)  — keccak256(pubkey) device id
        || category_bitmask_be      (4 bytes)   — uint32 BE bitmask
        || expires_at_ts_be         (8 bytes)   — uint64 BE unix seconds (0 = no expiry)
        || ts_ns_be                 (8 bytes)   — uint64 BE ns at grant time
    )                                = 67 bytes → 32 bytes

The hash binds device + categories + expiry + grant-time into one commitment
that the bridge stores locally AND the gamer signs on-chain. Mismatch
between local and on-chain commitments = tampering (the audit signal).

Any change to byte order, domain tag, bitmask layout, or scaling factor
requires v2 + a new domain tag. v1 is permanently frozen.
"""
from __future__ import annotations

import enum
import hashlib
import struct


_CONSENT_TAG = b"VAPI-CONSENT-v1"  # 15 bytes


class ConsentCategory(enum.IntEnum):
    """Per-category consent enum. Values FROZEN — must match the on-chain
    `enum ConsentCategory` in VAPIConsentRegistry.sol position-for-position.
    """
    TOURNAMENT_GATE     = 0
    ANONYMIZED_RESEARCH = 1
    MANUFACTURER_CERT   = 2
    MARKETPLACE         = 3


# Stable string names for the bridge `consent_ledger.consent_type` column.
# These are the ON-DISK values the database reads/writes; never reorder.
CATEGORY_NAMES: dict[ConsentCategory, str] = {
    ConsentCategory.TOURNAMENT_GATE:     "TOURNAMENT_GATE",
    ConsentCategory.ANONYMIZED_RESEARCH: "ANONYMIZED_RESEARCH",
    ConsentCategory.MANUFACTURER_CERT:   "MANUFACTURER_CERT",
    ConsentCategory.MARKETPLACE:         "MARKETPLACE",
}

NAME_TO_CATEGORY: dict[str, ConsentCategory] = {
    v: k for k, v in CATEGORY_NAMES.items()
}

ALL_CATEGORIES: tuple[ConsentCategory, ...] = tuple(ConsentCategory)


def category_from_name(name: str) -> ConsentCategory:
    """Look up a ConsentCategory by its string name. Case-sensitive.

    Raises ValueError on unknown name. Use this at API boundaries — internal
    code should pass enum values directly.
    """
    if name not in NAME_TO_CATEGORY:
        raise ValueError(
            f"unknown consent category: {name!r}. "
            f"Valid names: {sorted(NAME_TO_CATEGORY.keys())}"
        )
    return NAME_TO_CATEGORY[name]


def categories_to_bitmask(categories: list[ConsentCategory] | tuple[ConsentCategory, ...]) -> int:
    """Encode a set of categories as a uint32 bitmask.

    bit_n = 1 iff ConsentCategory(n) is in the set. Bitmask is the canonical
    on-chain representation; ordering of `categories` is irrelevant.
    """
    mask = 0
    for cat in categories:
        if not isinstance(cat, ConsentCategory):
            raise TypeError(f"expected ConsentCategory, got {type(cat).__name__}")
        mask |= (1 << int(cat))
    if not (0 <= mask <= 0xFFFFFFFF):
        raise ValueError(f"bitmask overflow uint32: {mask}")
    return mask


def bitmask_to_categories(bitmask: int) -> list[ConsentCategory]:
    """Decode a uint32 bitmask back into a sorted list of categories."""
    if not (0 <= bitmask <= 0xFFFFFFFF):
        raise ValueError(f"bitmask out of uint32 range: {bitmask}")
    out = []
    for cat in ConsentCategory:
        if bitmask & (1 << int(cat)):
            out.append(cat)
    return out


def device_id_to_bytes32(device_id: str | bytes) -> bytes:
    """Normalise a device_id into 32 bytes for the commitment input.

    Accepts either:
      - 64-char hex string (with or without 0x prefix) — typical keccak256(pubkey) form
      - 32 raw bytes
      - any other string — hashed with SHA-256 to produce a 32-byte tag

    The third case lets `device_id_to_bytes32("test_dev_1")` work for tests
    without forcing callers to pre-hash. In production, the hex form is
    canonical (matches the on-chain `bytes32` argument).
    """
    if isinstance(device_id, bytes):
        if len(device_id) != 32:
            raise ValueError(f"raw device_id must be 32 bytes, got {len(device_id)}")
        return device_id
    if not isinstance(device_id, str):
        raise TypeError(f"device_id must be str or bytes, got {type(device_id).__name__}")
    s = device_id.strip()
    if s.startswith("0x") or s.startswith("0X"):
        s = s[2:]
    # Try hex parse first
    try:
        b = bytes.fromhex(s)
        if len(b) == 32:
            return b
    except ValueError:
        pass
    # Fallback: SHA-256 the raw string (deterministic, useful for tests)
    return hashlib.sha256(device_id.encode("utf-8")).digest()


def compute_consent_hash(
    device_id: str | bytes,
    categories: list[ConsentCategory] | tuple[ConsentCategory, ...] | int,
    expires_at_ts: int,
    ts_ns: int,
) -> bytes:
    """Compute the consent commitment v1 — FROZEN formula.

    Args:
        device_id:       Device identifier; normalised to 32 bytes via device_id_to_bytes32().
        categories:      List/tuple of ConsentCategory members, OR a pre-computed uint32 bitmask.
        expires_at_ts:   Unix seconds when the consent expires (uint64). 0 means no expiry.
        ts_ns:           Unix nanoseconds at grant time (uint64).

    Returns:
        32-byte SHA-256 digest.
    """
    if isinstance(categories, int):
        bitmask = categories
        if not (0 <= bitmask <= 0xFFFFFFFF):
            raise ValueError(f"bitmask out of uint32 range: {bitmask}")
    else:
        bitmask = categories_to_bitmask(categories)

    if not (0 <= int(expires_at_ts) <= 0xFFFFFFFFFFFFFFFF):
        raise ValueError(f"expires_at_ts out of uint64 range: {expires_at_ts}")
    if not (0 <= int(ts_ns) <= 0xFFFFFFFFFFFFFFFF):
        raise ValueError(f"ts_ns out of uint64 range: {ts_ns}")

    dev_b = device_id_to_bytes32(device_id)

    return hashlib.sha256(
        _CONSENT_TAG
        + dev_b
        + struct.pack(">I", bitmask)
        + struct.pack(">Q", int(expires_at_ts))
        + struct.pack(">Q", int(ts_ns))
    ).digest()
