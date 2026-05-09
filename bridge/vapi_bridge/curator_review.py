"""Phase 238 Step I — Curator review pipeline (pure functions).

This module is the deterministic, I/O-free verdict computer for the
Curator Operator Initiative agent (third agent after Sentry + Guardian).
The Curator's job is to review marketplace listings (Phase 238 PALL)
and produce a shadow-mode review verdict that an operator can audit
before promoting Curator from O1 (observe-only) to O2 (suspension
authority).

Design constraints:
  - Pure functions only — no SQLite, no network, no chain calls.
    Callers fetch all required state and pass it in.  This makes the
    verdict computer fully unit-testable and forbids accidental I/O
    that would break determinism.
  - Verdict codes are FROZEN at six (matches the plan + Cedar bundle
    skill description).  Adding a new code requires a v2 of this module.
  - Tier computation MUST byte-for-byte mirror VAPIDataMarketplaceListings.sol
    `_computeTier()` and bridge-side `data_marketplace._compute_tier_from_count`.

Verdict codes (FROZEN):
    APPROVED                    — INFO  — all checks pass
    FLAGGED_TIER_MISMATCH       — WARN  — declared tier disagrees with
                                          live anchor count
    FLAGGED_ANCHOR_STALE        — WARN  — referenced anchor block.number
                                          older than freshness threshold
    FLAGGED_CONSENT_AMBIGUOUS   — WARN  — MARKETPLACE consent bit cleared
    FLAGGED_IPFS_UNAVAILABLE    — LOW   — IPFS gateway non-200 / timeout
    REJECTED_NO_ANCHORS         — HIGH  — no anchors anchored at all
    REJECTED_INVALID_COMMITMENT — HIGH  — listing dict is malformed /
                                          missing required fields (graceful
                                          handling for store row corruption)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

# ── FROZEN constants ────────────────────────────────────────────────────────

# Verdict code literals — strings (not enums) so JSON serialization is direct
# and operator-facing dashboards can match against string equality without
# requiring an enum import.
VERDICT_APPROVED                    = "APPROVED"
VERDICT_FLAGGED_TIER_MISMATCH       = "FLAGGED_TIER_MISMATCH"
VERDICT_FLAGGED_ANCHOR_STALE        = "FLAGGED_ANCHOR_STALE"
VERDICT_FLAGGED_CONSENT_AMBIGUOUS   = "FLAGGED_CONSENT_AMBIGUOUS"
VERDICT_FLAGGED_IPFS_UNAVAILABLE    = "FLAGGED_IPFS_UNAVAILABLE"
VERDICT_REJECTED_NO_ANCHORS         = "REJECTED_NO_ANCHORS"
VERDICT_REJECTED_INVALID_COMMITMENT = "REJECTED_INVALID_COMMITMENT"

# Frozen six (plus 1 graceful-error code; total 7 — but the plan freezes the
# six operational codes; REJECTED_INVALID_COMMITMENT is the safety floor).
_FROZEN_VERDICTS = frozenset({
    VERDICT_APPROVED,
    VERDICT_FLAGGED_TIER_MISMATCH,
    VERDICT_FLAGGED_ANCHOR_STALE,
    VERDICT_FLAGGED_CONSENT_AMBIGUOUS,
    VERDICT_FLAGGED_IPFS_UNAVAILABLE,
    VERDICT_REJECTED_NO_ANCHORS,
    VERDICT_REJECTED_INVALID_COMMITMENT,
})

_SEVERITY_BY_VERDICT = {
    VERDICT_APPROVED:                    "INFO",
    VERDICT_FLAGGED_TIER_MISMATCH:       "WARN",
    VERDICT_FLAGGED_ANCHOR_STALE:        "WARN",
    VERDICT_FLAGGED_CONSENT_AMBIGUOUS:   "WARN",
    VERDICT_FLAGGED_IPFS_UNAVAILABLE:    "LOW",
    VERDICT_REJECTED_NO_ANCHORS:         "HIGH",
    VERDICT_REJECTED_INVALID_COMMITMENT: "HIGH",
}

# Phase 237-CONSENT bit positions — MARKETPLACE is bit 3 (0-indexed).
MARKETPLACE_CONSENT_BIT = 1 << 3

# Phase 238 Step D Tier enum mirror.  Order matches Solidity contract
# enum and bridge data_marketplace._compute_tier_from_count.
TIER_BASIC    = 0
TIER_VERIFIED = 1
TIER_ATTESTED = 2
TIER_PREMIUM  = 3

# data_class -> implied minimum tier mapping.  This is the seller's
# DECLARED tier intent.  We compare against the ANCHOR-COUNT-DERIVED
# tier to detect mismatches.  data_class enum mirrors Phase 69
# DataTaxonomy + Curator's listing_review FROZEN expectation that
# higher data classes (4+) imply Premium-grade anchoring.
#
# 0..3 → Basic intent  | 4..5 → Attested intent  | 6+ → Premium intent.
def _declared_tier_from_data_class(data_class: int) -> int:
    if data_class <= 3:
        return TIER_BASIC
    if data_class <= 5:
        return TIER_ATTESTED
    return TIER_PREMIUM


def _compute_tier_from_count(anchors_present: int) -> int:
    """Mirror VAPIDataMarketplaceListings.sol _computeTier byte-for-byte.

    Must match data_marketplace._compute_tier_from_count exactly — the
    PALL invariant is that bridge tier preview + on-chain tier compute +
    Curator review tier all agree.
    """
    n = int(anchors_present)
    if n <= 0:
        return TIER_BASIC
    if n == 1:
        return TIER_VERIFIED
    if n <= 3:
        return TIER_ATTESTED
    return TIER_PREMIUM


# ── Inputs (caller-supplied snapshots) ──────────────────────────────────────

@dataclass(slots=True)
class AnchorStates:
    """Per-anchor on-chain isRecorded() snapshot.

    Caller (operator endpoint or future Curator agent loop) populates
    this by calling chain.is_adjudication_recorded(commitment_hex) for
    each non-empty anchor field on the listing.

    block_number_at_record may be None when the registry contract does
    not expose per-record block number; in that case anchor_freshness
    check is best-effort (current_block_number - 0 = freshness inferred
    from listing ts_ns instead).
    """
    sepproof_recorded:  bool = False
    biometric_recorded: bool = False
    corpus_recorded:    bool = False
    gic_recorded:       bool = False
    # Optional staleness inputs — if unavailable, anchor freshness defaults
    # to "fresh" (skip the check) per fail-open principle.
    sepproof_block_number:  Optional[int] = None
    biometric_block_number: Optional[int] = None
    corpus_block_number:    Optional[int] = None
    gic_block_number:       Optional[int] = None

    def total_recorded(self) -> int:
        return sum([
            int(self.sepproof_recorded),
            int(self.biometric_recorded),
            int(self.corpus_recorded),
            int(self.gic_recorded),
        ])

    def to_breakdown_dict(self) -> dict:
        return {
            "sepproof":  bool(self.sepproof_recorded),
            "biometric": bool(self.biometric_recorded),
            "corpus":    bool(self.corpus_recorded),
            "gic":       bool(self.gic_recorded),
        }


@dataclass(slots=True)
class IpfsState:
    """IPFS metadata reachability snapshot.

    Caller fetches the listing's ipfs_cid via Pinata gateway (or any
    IPFS HTTP gateway) and reports the result here.  None means
    "not checked / timeout" — Curator treats that as fail-open
    (no FLAGGED_IPFS_UNAVAILABLE fired) since Pinata transient outage
    should not over-flag legitimate listings.
    """
    resolvable: Optional[bool] = None  # True/False/None(skipped)


# ── Output ──────────────────────────────────────────────────────────────────

@dataclass(slots=True)
class ReviewVerdict:
    """Curator review output — shadow-mode advisory only.

    Field-locked via slots=True so a future contributor can't silently
    add a field that breaks the wire contract with VAPICurator SDK +
    frontend dashboard.  All 13 fields are part of the FROZEN endpoint
    response shape per the plan.
    """
    verdict: str = ""
    severity: str = ""
    listing_commitment: str = ""
    anchors_recorded_count: int = 0
    anchors_recorded_breakdown: dict = field(default_factory=dict)
    consent_marketplace_bit_set: bool = False
    ipfs_resolvable: Optional[bool] = None
    declared_tier: int = 0
    tier_at_review_time: int = 0
    tier_changed: bool = False
    shadow_mode: bool = True
    reason_detail: str = ""


# ── Pure-function review pipeline ───────────────────────────────────────────

def review_listing(
    listing: dict,
    anchor_states: AnchorStates,
    ipfs_state: IpfsState,
    *,
    current_block_number: Optional[int] = None,
    anchor_freshness_blocks: int = 1_000_000,
) -> ReviewVerdict:
    """Compute a shadow-mode Curator verdict.

    Args:
        listing: dict with the marketplace_listing_log row fields.
            Required: listing_commitment, consent_bitmask, data_class,
            ipfs_cid_hash, anchors_present_count.  Missing required
            fields → REJECTED_INVALID_COMMITMENT.
        anchor_states: per-anchor on-chain recorded state + block.number
        ipfs_state: IPFS gateway resolvability state
        current_block_number: caller's most recent IoTeX block number
            (for anchor freshness check).  None disables freshness check.
        anchor_freshness_blocks: anchor older than current - N is stale

    Returns:
        ReviewVerdict — never raises (graceful REJECTED_INVALID_COMMITMENT
        for malformed input).
    """
    # ── Step 1: validate required fields ──────────────────────────────
    if not isinstance(listing, dict):
        return _make_verdict(
            VERDICT_REJECTED_INVALID_COMMITMENT,
            "",
            anchor_states,
            ipfs_state,
            declared_tier=0,
            tier_at_review_time=0,
            consent_set=False,
            reason_detail="listing input is not a dict",
        )

    commitment = str(listing.get("listing_commitment", "") or "")
    if not commitment or len(commitment) < 32:
        return _make_verdict(
            VERDICT_REJECTED_INVALID_COMMITMENT,
            commitment,
            anchor_states,
            ipfs_state,
            declared_tier=0,
            tier_at_review_time=0,
            consent_set=False,
            reason_detail="listing_commitment missing or too short",
        )

    try:
        consent_bitmask = int(listing.get("consent_bitmask", 0))
        data_class = int(listing.get("data_class", 0))
    except (TypeError, ValueError):
        return _make_verdict(
            VERDICT_REJECTED_INVALID_COMMITMENT,
            commitment,
            anchor_states,
            ipfs_state,
            declared_tier=0,
            tier_at_review_time=0,
            consent_set=False,
            reason_detail="consent_bitmask or data_class not parseable as int",
        )

    consent_set = bool(consent_bitmask & MARKETPLACE_CONSENT_BIT)
    declared_tier = _declared_tier_from_data_class(data_class)
    anchors_recorded = anchor_states.total_recorded()
    tier_at_review = _compute_tier_from_count(anchors_recorded)
    tier_changed = (tier_at_review != _compute_tier_from_count(
        int(listing.get("anchors_present_count", 0))
    ))

    # ── Step 2: highest-severity verdicts first (REJECTED before FLAGGED) ──

    # REJECTED_NO_ANCHORS — listing claims to exist but no anchors recorded
    # AND consent bit set (non-anchor sellers should still anchor CONSENT).
    if anchors_recorded == 0 and consent_set:
        return _make_verdict(
            VERDICT_REJECTED_NO_ANCHORS,
            commitment,
            anchor_states,
            ipfs_state,
            declared_tier=declared_tier,
            tier_at_review_time=tier_at_review,
            consent_set=consent_set,
            tier_changed=tier_changed,
            reason_detail="listing has zero anchors recorded on AdjudicationRegistry",
        )

    # ── Step 3: FLAGGED_CONSENT_AMBIGUOUS (consent revoked post-creation) ──
    if not consent_set:
        return _make_verdict(
            VERDICT_FLAGGED_CONSENT_AMBIGUOUS,
            commitment,
            anchor_states,
            ipfs_state,
            declared_tier=declared_tier,
            tier_at_review_time=tier_at_review,
            consent_set=consent_set,
            tier_changed=tier_changed,
            reason_detail="MARKETPLACE consent bit (bit 3) cleared in consent_bitmask",
        )

    # ── Step 4: FLAGGED_TIER_MISMATCH ──
    # Declared tier (from data_class) vs anchor-derived tier disagree.
    if declared_tier != tier_at_review:
        return _make_verdict(
            VERDICT_FLAGGED_TIER_MISMATCH,
            commitment,
            anchor_states,
            ipfs_state,
            declared_tier=declared_tier,
            tier_at_review_time=tier_at_review,
            consent_set=consent_set,
            tier_changed=tier_changed,
            reason_detail=(
                f"declared_tier={declared_tier} (from data_class={data_class}) "
                f"!= tier_at_review_time={tier_at_review} "
                f"(from {anchors_recorded} anchors recorded)"
            ),
        )

    # ── Step 5: FLAGGED_ANCHOR_STALE ──
    # Any recorded anchor whose block.number is older than current_block - N.
    if current_block_number is not None and anchor_freshness_blocks > 0:
        stalest_age = _stalest_anchor_age(anchor_states, current_block_number)
        if stalest_age is not None and stalest_age > anchor_freshness_blocks:
            return _make_verdict(
                VERDICT_FLAGGED_ANCHOR_STALE,
                commitment,
                anchor_states,
                ipfs_state,
                declared_tier=declared_tier,
                tier_at_review_time=tier_at_review,
                consent_set=consent_set,
                tier_changed=tier_changed,
                reason_detail=(
                    f"oldest anchor is {stalest_age} blocks behind current "
                    f"block (threshold {anchor_freshness_blocks})"
                ),
            )

    # ── Step 6: FLAGGED_IPFS_UNAVAILABLE ──
    # Only fires when ipfs_state.resolvable is explicitly False (None = skipped).
    if ipfs_state.resolvable is False:
        return _make_verdict(
            VERDICT_FLAGGED_IPFS_UNAVAILABLE,
            commitment,
            anchor_states,
            ipfs_state,
            declared_tier=declared_tier,
            tier_at_review_time=tier_at_review,
            consent_set=consent_set,
            tier_changed=tier_changed,
            reason_detail="IPFS gateway returned non-200 or timed out",
        )

    # ── Step 7: APPROVED ──
    return _make_verdict(
        VERDICT_APPROVED,
        commitment,
        anchor_states,
        ipfs_state,
        declared_tier=declared_tier,
        tier_at_review_time=tier_at_review,
        consent_set=consent_set,
        tier_changed=tier_changed,
        reason_detail="all checks pass",
    )


# ── Helpers ─────────────────────────────────────────────────────────────────

def _stalest_anchor_age(states: AnchorStates, current_block: int) -> Optional[int]:
    """Return the largest (current_block - anchor_block) for any recorded anchor.

    Anchors with no block_number_at_record (None) are skipped — caller did
    not provide block numbers, freshness check is fail-open.

    Returns None if no recorded anchor has a block number.
    """
    blocks = []
    if states.sepproof_recorded and states.sepproof_block_number is not None:
        blocks.append(int(states.sepproof_block_number))
    if states.biometric_recorded and states.biometric_block_number is not None:
        blocks.append(int(states.biometric_block_number))
    if states.corpus_recorded and states.corpus_block_number is not None:
        blocks.append(int(states.corpus_block_number))
    if states.gic_recorded and states.gic_block_number is not None:
        blocks.append(int(states.gic_block_number))
    if not blocks:
        return None
    oldest = min(blocks)
    return max(0, int(current_block) - oldest)


def _make_verdict(
    verdict: str,
    commitment: str,
    anchor_states: AnchorStates,
    ipfs_state: IpfsState,
    *,
    declared_tier: int,
    tier_at_review_time: int,
    consent_set: bool,
    tier_changed: bool = False,
    reason_detail: str = "",
) -> ReviewVerdict:
    """Build a ReviewVerdict with severity assignment + breakdown population."""
    if verdict not in _FROZEN_VERDICTS:
        # Should never happen — guard against typos in caller.
        verdict = VERDICT_REJECTED_INVALID_COMMITMENT
        reason_detail = f"unknown verdict code: {verdict}"

    return ReviewVerdict(
        verdict=verdict,
        severity=_SEVERITY_BY_VERDICT[verdict],
        listing_commitment=commitment,
        anchors_recorded_count=anchor_states.total_recorded(),
        anchors_recorded_breakdown=anchor_states.to_breakdown_dict(),
        consent_marketplace_bit_set=bool(consent_set),
        ipfs_resolvable=ipfs_state.resolvable,
        declared_tier=int(declared_tier),
        tier_at_review_time=int(tier_at_review_time),
        tier_changed=bool(tier_changed),
        shadow_mode=True,  # FROZEN True in O1
        reason_detail=str(reason_detail)[:256],
    )


def severity_for_verdict(verdict: str) -> str:
    """Public helper for callers that need severity without computing a verdict."""
    return _SEVERITY_BY_VERDICT.get(verdict, "INFO")


def is_frozen_verdict(verdict: str) -> bool:
    """Public helper — verdict ∈ frozen set (used by test_t_238_cur_rv_14)."""
    return verdict in _FROZEN_VERDICTS
