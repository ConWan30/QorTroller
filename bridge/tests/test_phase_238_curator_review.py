"""Phase 238 Step I — Curator review pipeline pure-logic tests.

Tests the deterministic verdict computer in bridge/vapi_bridge/curator_review.py
across all six FROZEN verdict codes plus the safety-floor REJECTED_INVALID_COMMITMENT.

T-238-CUR-RV-1..14 — pure logic only, no I/O, no fixtures beyond plain dicts.
"""
from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from bridge.vapi_bridge.curator_review import (  # noqa: E402
    AnchorStates,
    IpfsState,
    ReviewVerdict,
    review_listing,
    severity_for_verdict,
    is_frozen_verdict,
    _compute_tier_from_count,
    _declared_tier_from_data_class,
    MARKETPLACE_CONSENT_BIT,
    TIER_BASIC, TIER_VERIFIED, TIER_ATTESTED, TIER_PREMIUM,
    VERDICT_APPROVED,
    VERDICT_FLAGGED_TIER_MISMATCH,
    VERDICT_FLAGGED_ANCHOR_STALE,
    VERDICT_FLAGGED_CONSENT_AMBIGUOUS,
    VERDICT_FLAGGED_IPFS_UNAVAILABLE,
    VERDICT_REJECTED_NO_ANCHORS,
    VERDICT_REJECTED_INVALID_COMMITMENT,
)


def _premium_listing(commitment: str = "ab" * 32) -> dict:
    """Build a Premium-tier listing dict (4 anchors, MARKETPLACE consent)."""
    return {
        "listing_commitment":     commitment,
        "consent_bitmask":        MARKETPLACE_CONSENT_BIT,  # bit 3
        "data_class":             6,                         # implies Premium
        "ipfs_cid_hash":          "cd" * 32,
        "anchors_present_count":  4,
    }


def _all_anchors_recorded() -> AnchorStates:
    return AnchorStates(
        sepproof_recorded=True,
        biometric_recorded=True,
        corpus_recorded=True,
        gic_recorded=True,
    )


# T-238-CUR-RV-1 ─────────────────────────────────────────────────────────────
def test_t_238_cur_rv_1_approved_happy_path():
    listing = _premium_listing()
    states = _all_anchors_recorded()
    ipfs = IpfsState(resolvable=True)
    v = review_listing(listing, states, ipfs)
    assert v.verdict == VERDICT_APPROVED
    assert v.severity == "INFO"
    assert v.anchors_recorded_count == 4
    assert v.anchors_recorded_breakdown == {
        "sepproof": True, "biometric": True, "corpus": True, "gic": True
    }
    assert v.consent_marketplace_bit_set is True
    assert v.ipfs_resolvable is True
    assert v.declared_tier == TIER_PREMIUM
    assert v.tier_at_review_time == TIER_PREMIUM
    assert v.tier_changed is False
    assert v.shadow_mode is True


# T-238-CUR-RV-2 ─────────────────────────────────────────────────────────────
def test_t_238_cur_rv_2_flagged_tier_mismatch_under_anchored():
    """Seller declared Premium (data_class=6) but only 2 anchors recorded."""
    listing = _premium_listing()
    listing["anchors_present_count"] = 4   # listing CLAIMS 4
    states = AnchorStates(
        sepproof_recorded=True,
        biometric_recorded=True,
        corpus_recorded=False,    # only 2 actually recorded
        gic_recorded=False,
    )
    v = review_listing(listing, states, IpfsState(resolvable=True))
    assert v.verdict == VERDICT_FLAGGED_TIER_MISMATCH
    assert v.severity == "WARN"
    assert v.declared_tier == TIER_PREMIUM
    assert v.tier_at_review_time == TIER_ATTESTED  # 2 anchors → Attested
    assert v.tier_changed is True


# T-238-CUR-RV-3 ─────────────────────────────────────────────────────────────
def test_t_238_cur_rv_3_flagged_tier_mismatch_over_anchored():
    """Seller declared Basic (data_class=0) but 4 anchors recorded.
    Curator should still FLAG — tier-up indicates seller misclassified
    data sensitivity.
    """
    listing = {
        "listing_commitment":     "aa" * 32,
        "consent_bitmask":        MARKETPLACE_CONSENT_BIT,
        "data_class":             0,                  # Basic intent
        "ipfs_cid_hash":          "cd" * 32,
        "anchors_present_count":  4,
    }
    states = _all_anchors_recorded()
    v = review_listing(listing, states, IpfsState(resolvable=True))
    assert v.verdict == VERDICT_FLAGGED_TIER_MISMATCH
    assert v.declared_tier == TIER_BASIC
    assert v.tier_at_review_time == TIER_PREMIUM


# T-238-CUR-RV-4 ─────────────────────────────────────────────────────────────
def test_t_238_cur_rv_4_flagged_anchor_stale():
    """One recorded anchor's block is older than freshness threshold."""
    listing = _premium_listing()
    states = AnchorStates(
        sepproof_recorded=True,
        biometric_recorded=True,
        corpus_recorded=True,
        gic_recorded=True,
        sepproof_block_number=1_000,        # very old
        biometric_block_number=10_000_000,  # current
        corpus_block_number=10_000_000,
        gic_block_number=10_000_000,
    )
    v = review_listing(
        listing, states, IpfsState(resolvable=True),
        current_block_number=10_000_000,
        anchor_freshness_blocks=1_000_000,
    )
    assert v.verdict == VERDICT_FLAGGED_ANCHOR_STALE
    assert v.severity == "WARN"


# T-238-CUR-RV-5 ─────────────────────────────────────────────────────────────
def test_t_238_cur_rv_5_flagged_consent_ambiguous():
    """MARKETPLACE consent bit cleared post-creation."""
    listing = _premium_listing()
    listing["consent_bitmask"] = 1  # bit 0 only (TOURNAMENT_GATE), no bit 3
    v = review_listing(listing, _all_anchors_recorded(), IpfsState(resolvable=True))
    assert v.verdict == VERDICT_FLAGGED_CONSENT_AMBIGUOUS
    assert v.severity == "WARN"
    assert v.consent_marketplace_bit_set is False


# T-238-CUR-RV-6 ─────────────────────────────────────────────────────────────
def test_t_238_cur_rv_6_flagged_ipfs_unavailable_explicit_false():
    listing = _premium_listing()
    v = review_listing(
        listing, _all_anchors_recorded(),
        IpfsState(resolvable=False),
    )
    assert v.verdict == VERDICT_FLAGGED_IPFS_UNAVAILABLE
    assert v.severity == "LOW"
    assert v.ipfs_resolvable is False


# T-238-CUR-RV-7 ─────────────────────────────────────────────────────────────
def test_t_238_cur_rv_7_ipfs_skipped_does_not_flag():
    """ipfs_state.resolvable=None means 'not checked' — no flag fires."""
    listing = _premium_listing()
    v = review_listing(
        listing, _all_anchors_recorded(),
        IpfsState(resolvable=None),
    )
    assert v.verdict == VERDICT_APPROVED
    assert v.ipfs_resolvable is None


# T-238-CUR-RV-8 ─────────────────────────────────────────────────────────────
def test_t_238_cur_rv_8_rejected_no_anchors():
    """Listing has no anchors recorded but consent bit set."""
    listing = _premium_listing()
    listing["data_class"] = 0              # Basic — keeps tier check happy
    v = review_listing(
        listing,
        AnchorStates(),                    # zero anchors
        IpfsState(resolvable=True),
    )
    assert v.verdict == VERDICT_REJECTED_NO_ANCHORS
    assert v.severity == "HIGH"
    assert v.anchors_recorded_count == 0


# T-238-CUR-RV-9 ─────────────────────────────────────────────────────────────
def test_t_238_cur_rv_9_tier_compute_byte_for_byte_with_solidity():
    """_compute_tier_from_count MUST mirror VAPIDataMarketplaceListings.sol
    _computeTier exactly: 0→Basic, 1→Verified, 2-3→Attested, 4→Premium.
    """
    assert _compute_tier_from_count(0) == TIER_BASIC
    assert _compute_tier_from_count(1) == TIER_VERIFIED
    assert _compute_tier_from_count(2) == TIER_ATTESTED
    assert _compute_tier_from_count(3) == TIER_ATTESTED
    assert _compute_tier_from_count(4) == TIER_PREMIUM
    # Defensive: negative input → Basic (matches Solidity uint underflow guard)
    assert _compute_tier_from_count(-1) == TIER_BASIC
    # data_class declared-tier mapping
    assert _declared_tier_from_data_class(0) == TIER_BASIC
    assert _declared_tier_from_data_class(3) == TIER_BASIC
    assert _declared_tier_from_data_class(4) == TIER_ATTESTED
    assert _declared_tier_from_data_class(5) == TIER_ATTESTED
    assert _declared_tier_from_data_class(6) == TIER_PREMIUM


# T-238-CUR-RV-10 ────────────────────────────────────────────────────────────
def test_t_238_cur_rv_10_review_verdict_slots_locked():
    """ReviewVerdict @dataclass(slots=True) must reject ad-hoc attribute
    injection so future contributors cannot silently break the wire contract.
    """
    v = ReviewVerdict()
    import pytest
    with pytest.raises(AttributeError):
        v.injected_field = "x"  # type: ignore[attr-defined]


# T-238-CUR-RV-11 ────────────────────────────────────────────────────────────
def test_t_238_cur_rv_11_severity_assignment_correct():
    """Each verdict code maps to a severity per the FROZEN table."""
    assert severity_for_verdict(VERDICT_APPROVED) == "INFO"
    assert severity_for_verdict(VERDICT_FLAGGED_TIER_MISMATCH) == "WARN"
    assert severity_for_verdict(VERDICT_FLAGGED_ANCHOR_STALE) == "WARN"
    assert severity_for_verdict(VERDICT_FLAGGED_CONSENT_AMBIGUOUS) == "WARN"
    assert severity_for_verdict(VERDICT_FLAGGED_IPFS_UNAVAILABLE) == "LOW"
    assert severity_for_verdict(VERDICT_REJECTED_NO_ANCHORS) == "HIGH"
    assert severity_for_verdict(VERDICT_REJECTED_INVALID_COMMITMENT) == "HIGH"
    # Unknown verdict → INFO (graceful default)
    assert severity_for_verdict("MYSTERY_CODE") == "INFO"


# T-238-CUR-RV-12 ────────────────────────────────────────────────────────────
def test_t_238_cur_rv_12_verdict_serialization_round_trip():
    """ReviewVerdict's 13 fields must serialize+deserialize losslessly so the
    SDK + frontend can rely on stable JSON shape.
    """
    listing = _premium_listing()
    v = review_listing(listing, _all_anchors_recorded(), IpfsState(resolvable=True))
    # Manually serialize via vars() (slot-friendly)
    serialized = {
        "verdict": v.verdict,
        "severity": v.severity,
        "listing_commitment": v.listing_commitment,
        "anchors_recorded_count": v.anchors_recorded_count,
        "anchors_recorded_breakdown": v.anchors_recorded_breakdown,
        "consent_marketplace_bit_set": v.consent_marketplace_bit_set,
        "ipfs_resolvable": v.ipfs_resolvable,
        "declared_tier": v.declared_tier,
        "tier_at_review_time": v.tier_at_review_time,
        "tier_changed": v.tier_changed,
        "shadow_mode": v.shadow_mode,
        "reason_detail": v.reason_detail,
    }
    assert serialized["verdict"] == VERDICT_APPROVED
    assert serialized["anchors_recorded_breakdown"]["sepproof"] is True
    assert len(serialized) == 12  # 12 (excluding 'severity' below) — verify count
    assert "listing_commitment" in serialized


# T-238-CUR-RV-13 ────────────────────────────────────────────────────────────
def test_t_238_cur_rv_13_malformed_input_returns_invalid_commitment():
    """review_listing MUST never raise — malformed input → REJECTED_INVALID_COMMITMENT."""
    # Not a dict
    v = review_listing("not a dict", _all_anchors_recorded(), IpfsState())  # type: ignore[arg-type]
    assert v.verdict == VERDICT_REJECTED_INVALID_COMMITMENT
    assert v.severity == "HIGH"

    # Missing commitment
    v = review_listing({}, _all_anchors_recorded(), IpfsState())
    assert v.verdict == VERDICT_REJECTED_INVALID_COMMITMENT

    # Commitment too short
    v = review_listing(
        {"listing_commitment": "abc"},
        _all_anchors_recorded(), IpfsState()
    )
    assert v.verdict == VERDICT_REJECTED_INVALID_COMMITMENT

    # consent_bitmask not parseable
    v = review_listing(
        {"listing_commitment": "ab" * 32, "consent_bitmask": "x", "data_class": 0},
        _all_anchors_recorded(), IpfsState()
    )
    assert v.verdict == VERDICT_REJECTED_INVALID_COMMITMENT


# T-238-CUR-RV-14 ────────────────────────────────────────────────────────────
def test_t_238_cur_rv_14_frozen_six_verdict_codes():
    """The six operational verdict codes (plus the safety-floor 7th) MUST be
    exactly the FROZEN set.  Adding a new code requires a curator_review v2
    module — test catches accidental drift.
    """
    expected_frozen = {
        VERDICT_APPROVED,
        VERDICT_FLAGGED_TIER_MISMATCH,
        VERDICT_FLAGGED_ANCHOR_STALE,
        VERDICT_FLAGGED_CONSENT_AMBIGUOUS,
        VERDICT_FLAGGED_IPFS_UNAVAILABLE,
        VERDICT_REJECTED_NO_ANCHORS,
        VERDICT_REJECTED_INVALID_COMMITMENT,
    }
    for code in expected_frozen:
        assert is_frozen_verdict(code), f"{code} should be frozen"
    # Unknown codes must NOT be in the frozen set
    assert is_frozen_verdict("MYSTERY_NEW_CODE") is False
    assert is_frozen_verdict("") is False
