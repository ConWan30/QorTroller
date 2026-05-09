"""Phase 238-MARKETPLACE — LISTING-v1 primitive tests.

Verifies the FROZEN-v1 formula is byte-identical for canonical inputs,
deterministic across reruns, sensitive to every input field, properly
bounds-checks, and enforces the MARKETPLACE consent requirement.

This is the 7th member of the PATTERN-016 FROZEN-v1 family.  Any change
to byte order, scale, or domain tag invalidates every prior anchored
listing — these tests are the regression guard.

T-238-MKT-LP-1..12.
"""
from __future__ import annotations

import hashlib
import struct
import sys
import types as _types
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
BRIDGE_DIR = Path(__file__).parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(BRIDGE_DIR) not in sys.path:
    sys.path.insert(0, str(BRIDGE_DIR))

# Stub heavy-import modules
for _mod in ["web3", "web3.exceptions", "eth_account", "anthropic"]:
    if _mod not in sys.modules:
        sys.modules[_mod] = _types.ModuleType(_mod)
if "dotenv" not in sys.modules:
    _dotenv = _types.ModuleType("dotenv")
    _dotenv.load_dotenv = lambda *a, **kw: None  # type: ignore[attr-defined]
    sys.modules["dotenv"] = _dotenv

from vapi_bridge.listing_primitive import (  # noqa: E402
    compute_listing_commitment,
    compute_ipfs_cid_hash,
    encode_price_micro,
    expected_body_length,
    count_anchors_present,
    _LISTING_TAG,
    _PRICE_SCALE,
    _CONSENT_BIT_MARKETPLACE,
    _CONSENT_BIT_TOURNAMENT_GATE,
    _CONSENT_BIT_ANONYMIZED_RESEARCH,
    DATA_CLASS_BIOMETRIC,
    DATA_CLASS_SESSION,
    DATA_CLASS_PROOF,
)


# ── Canonical inputs (Phase 238 Premium-tier shape) ─────────────────────────

CANONICAL_SEPPROOF       = bytes.fromhex("aa" * 32)
CANONICAL_BIOMETRIC_SNAP = bytes.fromhex("bb" * 32)
CANONICAL_CORPUS_SNAP    = bytes.fromhex("cc" * 32)
CANONICAL_GIC            = bytes.fromhex("dd" * 32)
CANONICAL_CONSENT_BITMASK = (
    _CONSENT_BIT_MARKETPLACE        # required
    | _CONSENT_BIT_ANONYMIZED_RESEARCH
)
CANONICAL_DATA_CLASS = DATA_CLASS_BIOMETRIC   # uint8 = 4
CANONICAL_PRICE_IOTX = 5.0                     # 5 IOTX
CANONICAL_CID = "bafybeigdyrzt5sfp7udm7hu76uh7y26nf3efuylqabf3oclgtqy55fbzdi"
CANONICAL_TS_NS = 1_778_400_000_000_000_000


# ─────────────────────────────────────────────────────────────────────────────
# T-238-MKT-LP-1: domain tag is "VAPI-LISTING-v1" (15 bytes literal)
# ─────────────────────────────────────────────────────────────────────────────

def test_t_238_mkt_lp_1_domain_tag_frozen():
    """FROZEN: domain tag must be exactly b'VAPI-LISTING-v1' (15 bytes).
    Any change is a v2 break and invalidates all prior anchors."""
    assert _LISTING_TAG == b"VAPI-LISTING-v1"
    assert len(_LISTING_TAG) == 15


# ─────────────────────────────────────────────────────────────────────────────
# T-238-MKT-LP-2: price scale factor is 1e6 literal (matches CORPUS-SNAPSHOT)
# ─────────────────────────────────────────────────────────────────────────────

def test_t_238_mkt_lp_2_scale_frozen():
    """FROZEN: scale factor must be exactly 1_000_000.  Matches
    CORPUS-SNAPSHOT-v1's ratio_milli precedent for OS-deterministic
    int encoding of float values."""
    assert _PRICE_SCALE == 1_000_000


# ─────────────────────────────────────────────────────────────────────────────
# T-238-MKT-LP-3: body length is exactly 196 bytes
# ─────────────────────────────────────────────────────────────────────────────

def test_t_238_mkt_lp_3_body_length():
    """FROZEN body layout: 15 (tag) + 32*4 (anchors) + 4 (consent) + 1 (data_class)
    + 8 (price) + 32 (cid_hash) + 8 (ts_ns) = 196 bytes."""
    assert expected_body_length() == 196


# ─────────────────────────────────────────────────────────────────────────────
# T-238-MKT-LP-4: commitment is deterministic (same inputs -> same digest)
# ─────────────────────────────────────────────────────────────────────────────

def test_t_238_mkt_lp_4_deterministic():
    c1 = compute_listing_commitment(
        sepproof_commitment     = CANONICAL_SEPPROOF,
        biometric_snapshot_hash = CANONICAL_BIOMETRIC_SNAP,
        corpus_snapshot_hash    = CANONICAL_CORPUS_SNAP,
        gic_hash                = CANONICAL_GIC,
        consent_bitmask         = CANONICAL_CONSENT_BITMASK,
        data_class              = CANONICAL_DATA_CLASS,
        price_iotx              = CANONICAL_PRICE_IOTX,
        ipfs_cid                = CANONICAL_CID,
        ts_ns                   = CANONICAL_TS_NS,
    )
    c2 = compute_listing_commitment(
        sepproof_commitment     = CANONICAL_SEPPROOF,
        biometric_snapshot_hash = CANONICAL_BIOMETRIC_SNAP,
        corpus_snapshot_hash    = CANONICAL_CORPUS_SNAP,
        gic_hash                = CANONICAL_GIC,
        consent_bitmask         = CANONICAL_CONSENT_BITMASK,
        data_class              = CANONICAL_DATA_CLASS,
        price_iotx              = CANONICAL_PRICE_IOTX,
        ipfs_cid                = CANONICAL_CID,
        ts_ns                   = CANONICAL_TS_NS,
    )
    assert c1 == c2
    assert len(c1) == 32  # SHA-256 output


# ─────────────────────────────────────────────────────────────────────────────
# T-238-MKT-LP-5: manual SHA-256 reconstruction matches commitment
# ─────────────────────────────────────────────────────────────────────────────

def test_t_238_mkt_lp_5_manual_recompute_matches():
    """Verify the canonical body layout by reconstructing the digest manually.
    This is the regression guard against silent layout changes."""
    expected_body = bytearray()
    expected_body.extend(_LISTING_TAG)                                # 15
    expected_body.extend(CANONICAL_SEPPROOF)                          # 32
    expected_body.extend(CANONICAL_BIOMETRIC_SNAP)                    # 32
    expected_body.extend(CANONICAL_CORPUS_SNAP)                       # 32
    expected_body.extend(CANONICAL_GIC)                               # 32
    expected_body.extend(struct.pack(">I", CANONICAL_CONSENT_BITMASK)) # 4
    expected_body.append(CANONICAL_DATA_CLASS)                        # 1
    expected_body.extend(struct.pack(">Q", int(round(CANONICAL_PRICE_IOTX * 1_000_000))))  # 8
    expected_body.extend(hashlib.sha256(CANONICAL_CID.encode("utf-8")).digest())            # 32
    expected_body.extend(struct.pack(">Q", CANONICAL_TS_NS))           # 8

    expected_digest = hashlib.sha256(bytes(expected_body)).digest()
    actual_digest = compute_listing_commitment(
        sepproof_commitment     = CANONICAL_SEPPROOF,
        biometric_snapshot_hash = CANONICAL_BIOMETRIC_SNAP,
        corpus_snapshot_hash    = CANONICAL_CORPUS_SNAP,
        gic_hash                = CANONICAL_GIC,
        consent_bitmask         = CANONICAL_CONSENT_BITMASK,
        data_class              = CANONICAL_DATA_CLASS,
        price_iotx              = CANONICAL_PRICE_IOTX,
        ipfs_cid                = CANONICAL_CID,
        ts_ns                   = CANONICAL_TS_NS,
    )
    assert actual_digest == expected_digest
    assert len(expected_body) == expected_body_length() == 196


# ─────────────────────────────────────────────────────────────────────────────
# T-238-MKT-LP-6: every input field is sensitive (changing one changes digest)
# ─────────────────────────────────────────────────────────────────────────────

def test_t_238_mkt_lp_6_per_input_sensitivity():
    """Changing ANY field must change the digest. Partial sensitivity is a
    bug — a malicious seller could find equivalent inputs with same digest."""
    base_kwargs = dict(
        sepproof_commitment     = CANONICAL_SEPPROOF,
        biometric_snapshot_hash = CANONICAL_BIOMETRIC_SNAP,
        corpus_snapshot_hash    = CANONICAL_CORPUS_SNAP,
        gic_hash                = CANONICAL_GIC,
        consent_bitmask         = CANONICAL_CONSENT_BITMASK,
        data_class              = CANONICAL_DATA_CLASS,
        price_iotx              = CANONICAL_PRICE_IOTX,
        ipfs_cid                = CANONICAL_CID,
        ts_ns                   = CANONICAL_TS_NS,
    )
    base = compute_listing_commitment(**base_kwargs)

    # Each tweaked field must produce a different digest
    field_changes = [
        ("sepproof_commitment",     bytes.fromhex("11" * 32)),
        ("biometric_snapshot_hash", bytes.fromhex("22" * 32)),
        ("corpus_snapshot_hash",    bytes.fromhex("33" * 32)),
        ("gic_hash",                bytes.fromhex("44" * 32)),
        ("consent_bitmask",         CANONICAL_CONSENT_BITMASK | _CONSENT_BIT_TOURNAMENT_GATE),
        ("data_class",              DATA_CLASS_PROOF),    # different class
        ("price_iotx",              CANONICAL_PRICE_IOTX + 0.001),
        ("ipfs_cid",                "bafkreialtdifferentcidvaluexxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"),
        ("ts_ns",                   CANONICAL_TS_NS + 1),
    ]
    for field, new_value in field_changes:
        modified = dict(base_kwargs)
        modified[field] = new_value
        new_digest = compute_listing_commitment(**modified)
        assert new_digest != base, (
            f"sensitivity broken: changing '{field}' produced same digest"
        )


# ─────────────────────────────────────────────────────────────────────────────
# T-238-MKT-LP-7: optional anchors (None / b"") -> zero-bytes (absent)
# ─────────────────────────────────────────────────────────────────────────────

def test_t_238_mkt_lp_7_optional_anchors_handled():
    """Tier-1 Basic listings have no SEPPROOF/BIOMETRIC/CORPUS/GIC anchors.
    Caller passes None or b''; canonical body uses 32 zero bytes for each."""
    # All four anchors absent (Tier 1 Basic shape)
    basic = compute_listing_commitment(
        sepproof_commitment     = None,
        biometric_snapshot_hash = None,
        corpus_snapshot_hash    = b"",
        gic_hash                = None,
        consent_bitmask         = _CONSENT_BIT_MARKETPLACE,  # MARKETPLACE only
        data_class              = DATA_CLASS_SESSION,
        price_iotx              = 0.5,
        ipfs_cid                = CANONICAL_CID,
        ts_ns                   = CANONICAL_TS_NS,
    )
    # Same call but with explicit zero-bytes for absent anchors
    explicit_zeros = compute_listing_commitment(
        sepproof_commitment     = b"\x00" * 32,
        biometric_snapshot_hash = b"\x00" * 32,
        corpus_snapshot_hash    = b"\x00" * 32,
        gic_hash                = b"\x00" * 32,
        consent_bitmask         = _CONSENT_BIT_MARKETPLACE,
        data_class              = DATA_CLASS_SESSION,
        price_iotx              = 0.5,
        ipfs_cid                = CANONICAL_CID,
        ts_ns                   = CANONICAL_TS_NS,
    )
    assert basic == explicit_zeros, (
        "None / b'' anchor inputs must collapse to zero bytes (absent) — "
        "callers can use either form for Basic-tier listings"
    )


# ─────────────────────────────────────────────────────────────────────────────
# T-238-MKT-LP-8: MARKETPLACE consent bit is required
# ─────────────────────────────────────────────────────────────────────────────

def test_t_238_mkt_lp_8_marketplace_consent_required():
    """A listing without MARKETPLACE consent (bit 3) is cryptographically
    invalid. compute_listing_commitment raises ValueError rather than
    silently encoding a non-marketplace-authorized listing."""
    # All other consent bits set, but NOT MARKETPLACE
    no_marketplace_mask = (
        _CONSENT_BIT_TOURNAMENT_GATE
        | _CONSENT_BIT_ANONYMIZED_RESEARCH
    )
    with pytest.raises(ValueError, match="MARKETPLACE bit"):
        compute_listing_commitment(
            sepproof_commitment     = CANONICAL_SEPPROOF,
            biometric_snapshot_hash = CANONICAL_BIOMETRIC_SNAP,
            corpus_snapshot_hash    = CANONICAL_CORPUS_SNAP,
            gic_hash                = CANONICAL_GIC,
            consent_bitmask         = no_marketplace_mask,
            data_class              = CANONICAL_DATA_CLASS,
            price_iotx              = CANONICAL_PRICE_IOTX,
            ipfs_cid                = CANONICAL_CID,
            ts_ns                   = CANONICAL_TS_NS,
        )


# ─────────────────────────────────────────────────────────────────────────────
# T-238-MKT-LP-9: data_class out-of-range raises
# ─────────────────────────────────────────────────────────────────────────────

def test_t_238_mkt_lp_9_invalid_data_class():
    """data_class must be in [0, 6] matching Phase 69 DATA_TAXONOMY enum."""
    for bad in (-1, 7, 8, 255):
        with pytest.raises(ValueError, match="data_class must be in"):
            compute_listing_commitment(
                sepproof_commitment     = None,
                biometric_snapshot_hash = None,
                corpus_snapshot_hash    = None,
                gic_hash                = None,
                consent_bitmask         = _CONSENT_BIT_MARKETPLACE,
                data_class              = bad,
                price_iotx              = 1.0,
                ipfs_cid                = CANONICAL_CID,
                ts_ns                   = CANONICAL_TS_NS,
            )


# ─────────────────────────────────────────────────────────────────────────────
# T-238-MKT-LP-10: price overflow + negative raises
# ─────────────────────────────────────────────────────────────────────────────

def test_t_238_mkt_lp_10_price_bounds():
    """encode_price_micro raises on negative or uint64 overflow."""
    with pytest.raises(ValueError, match=">= 0"):
        encode_price_micro(-1.0)
    with pytest.raises(ValueError, match="overflow uint64"):
        # 1e13 IOTX * 1e6 = 1e19 — overflows uint64 (max ~1.8e19)
        encode_price_micro(2e13)
    # Edge cases that should pass
    assert encode_price_micro(0) == 0
    assert encode_price_micro(1.0) == 1_000_000
    assert encode_price_micro(0.000001) == 1   # 1 micro-IOTX
    assert encode_price_micro(None) == 0       # None -> 0


# ─────────────────────────────────────────────────────────────────────────────
# T-238-MKT-LP-11: ts_ns + consent_bitmask uint range boundary
# ─────────────────────────────────────────────────────────────────────────────

def test_t_238_mkt_lp_11_uint_boundaries():
    common_kwargs = dict(
        sepproof_commitment     = None,
        biometric_snapshot_hash = None,
        corpus_snapshot_hash    = None,
        gic_hash                = None,
        data_class              = DATA_CLASS_SESSION,
        price_iotx              = 1.0,
        ipfs_cid                = CANONICAL_CID,
    )
    # ts_ns out of uint64
    with pytest.raises(ValueError, match="ts_ns out of uint64 range"):
        compute_listing_commitment(
            consent_bitmask = _CONSENT_BIT_MARKETPLACE,
            ts_ns           = -1,
            **common_kwargs,
        )
    with pytest.raises(ValueError, match="ts_ns out of uint64 range"):
        compute_listing_commitment(
            consent_bitmask = _CONSENT_BIT_MARKETPLACE,
            ts_ns           = 2**64,
            **common_kwargs,
        )
    # consent_bitmask out of uint32
    with pytest.raises(ValueError, match="consent_bitmask out of uint32 range"):
        compute_listing_commitment(
            consent_bitmask = 2**32,
            ts_ns           = CANONICAL_TS_NS,
            **common_kwargs,
        )
    with pytest.raises(ValueError, match="consent_bitmask out of uint32 range"):
        compute_listing_commitment(
            consent_bitmask = -1,
            ts_ns           = CANONICAL_TS_NS,
            **common_kwargs,
        )


# ─────────────────────────────────────────────────────────────────────────────
# T-238-MKT-LP-12: count_anchors_present helper for tier computation
# ─────────────────────────────────────────────────────────────────────────────

def test_t_238_mkt_lp_12_count_anchors():
    """count_anchors_present mirrors what the on-chain extension contract
    will compute via IAdjudicationRegistry.isRecorded() per anchor."""
    # 0 anchors (Basic tier)
    assert count_anchors_present(None, None, None, None) == 0
    assert count_anchors_present(b"", b"", b"", b"") == 0
    assert count_anchors_present(
        b"\x00" * 32, b"\x00" * 32, b"\x00" * 32, b"\x00" * 32
    ) == 0
    # 1 anchor (Verified tier)
    assert count_anchors_present(None, None, CANONICAL_CORPUS_SNAP, None) == 1
    assert count_anchors_present(None, None, None, CANONICAL_GIC) == 1
    # 3 anchors (Attested tier)
    assert count_anchors_present(
        CANONICAL_SEPPROOF, CANONICAL_BIOMETRIC_SNAP, None, None
    ) == 2
    # 4 anchors (Premium tier basis)
    assert count_anchors_present(
        CANONICAL_SEPPROOF, CANONICAL_BIOMETRIC_SNAP,
        CANONICAL_CORPUS_SNAP, CANONICAL_GIC
    ) == 4
    # Wrong-length input is not counted
    assert count_anchors_present(b"\x01\x02", None, None, None) == 0
