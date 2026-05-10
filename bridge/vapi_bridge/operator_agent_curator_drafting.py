"""Phase O2-DRAFT-GENERATION (Curator) -- 2026-05-10.

Curator's three O2_SUGGEST drafting primitives. Third agent in the parallel-
fleet drafting trio (sibling of operator_agent_sentry_drafting.py +
operator_agent_guardian_drafting.py shipped same day).

PERMITTED RESOURCE PATHS at O2_SUGGEST per `curator_o2_suggest_v1.json`:
  tool:kms-sign                    -> draft://listing_reviews/*
  skill:marketplace-listing-review -> draft://listing_reviews/*
  skill:tier-compliance-check      -> lane://marketplace/**   (read-only at O2)
  skill:anchor-freshness-audit     -> lane://provenance/**    (read-only at O2)
  tool:ipfs-metadata-fetch         -> lane://marketplace/**   (read-only HTTP GET)
  tool:operator-notify             -> draft://operator_notifications/*

This module ships the three highest-leverage WRITE primitives:
  - skill:marketplace-listing-review (HEADLINE Curator skill)
  - tool:kms-sign on listing reviews (signs already-drafted verdicts)
  - tool:operator-notify (suspension RECOMMENDATION channel; soft-veto path)

The three READ-only skills (tier-compliance-check, anchor-freshness-audit,
ipfs-metadata-fetch) do NOT produce drafts -- they observe state. They will
be exercised by Curator's polling loop (deferred phase) but emit zero rows
in operator_agent_drafts.

CURATOR-EXCLUSIVE DECISION: overturn_curator
  When operator review of a marketplace-listing-review draft determines
  the verdict was wrong (e.g. Curator flagged a listing that operator
  re-checks and approves), the operator records decision='overturn_curator'.
  This feeds the watcher's PHASE_O3_FALSE_POSITIVE_RATE_MAX gate (Curator-
  only; default 0.0 = ZERO TOLERANCE for marketplace verdicts overturned
  by operator). Sentry+Guardian drafts never receive overturn_curator.

CONSENT GATE (Phase 237-CONSENT, MARKETPLACE bit 3): listing reviews
require the seller's MARKETPLACE consent bit set. The drafting primitive
itself does not enforce -- the upstream listing-creation pipeline already
gates via VAPIDataMarketplaceListings.sol. Drafts produced here may
reference listings whose consent state is later revoked; the FSCA
CONSENT_REVOKED_LISTING_ACTIVE rule (Phase 238 Step I-AUTOLOOP-2) detects
that drift on the next 15-min poll cycle.

INVARIANTS (mirror Sentry/Guardian):
  - draft_uri MUST start with "draft://" (Cedar VALID_SCHEMES gate)
  - payload_hash is SHA-256 lowercase hex of canonical-JSON body
  - agent_id passed to store is the Q9 hex when cfg fields populated;
    canonical name "curator" fallback for test stubs
  - Idempotent: same agent+payload_hash twice returns existing row id
  - Fail-open: store insertion failures return draft_id=0 with error populated
  - Verdict field validated against Phase 238 Step I FROZEN _FROZEN_VERDICTS
    set (7 codes; 6 operational + REJECTED_INVALID_COMMITMENT safety floor)
"""
from __future__ import annotations

import hashlib
import json
import logging
import time
from dataclasses import dataclass
from typing import Any, Optional

from .curator_review import _FROZEN_VERDICTS, _SEVERITY_BY_VERDICT
from .operator_agent_sentry_drafting import (
    DraftResult,
    _normalize_commit_hash,
    _sha256_canonical_json,
)
from .operator_agent_guardian_drafting import _safe_id_segment
from .operator_initiative_advancement import _resolve_agent_id_for_store

log = logging.getLogger(__name__)


# Curator's canonical name in INITIATIVE_AGENTS (matches watcher convention).
CURATOR_CANONICAL = "curator"

# Curator's permitted draft URI prefixes per curator_o2_suggest_v1.json.
# Re-asserted at module level so a future bundle edit lifting these paths
# does not silently change the draft URI scheme without a code update.
CURATOR_LISTING_REVIEW_DRAFT_PREFIX        = "draft://listing_reviews/"
CURATOR_OPERATOR_NOTIFICATION_DRAFT_PREFIX = "draft://operator_notifications/"

# Frozen severity ladder for operator notifications (mirrors Guardian's
# operational-diagnostic ladder; aligned with Phase 238 Step I severity
# codes but with the Curator-recommendation-specific 'recommend_suspend'
# value added at the high end for the suspension recommendation channel).
_NOTIFY_SEVERITIES = frozenset({"info", "warn", "error", "critical", "recommend_suspend"})


class CuratorDraftGenerator:
    """Phase O2-DRAFT-GENERATION primitive surface for Curator.

    All three methods are synchronous (pure-Python + sqlite3 writes).
    Higher-level call sites (e.g., the eventual Curator polling loop or
    the bridge listing-event subscriber) decide WHEN to invoke them.
    """

    def __init__(self, *, cfg: Any, store: Any) -> None:
        self._cfg = cfg
        self._store = store
        self._agent_id_used = _resolve_agent_id_for_store(CURATOR_CANONICAL, cfg)

    # ------------------------------------------------------------------
    # 1. skill:marketplace-listing-review on draft://listing_reviews/*
    # ------------------------------------------------------------------
    #
    # HEADLINE Curator skill. Verdict drafts attach to a specific listing
    # via listing_id; draft URI segments use sanitized listing_id +
    # '/verdict' to disambiguate from kms-sign-on-the-same-listing drafts
    # that use '/sig'.
    # ------------------------------------------------------------------
    def draft_marketplace_listing_review(
        self,
        *,
        listing_id: str,
        verdict: str,
        review_payload: Optional[dict] = None,
    ) -> DraftResult:
        """Produce a Curator marketplace-listing-review verdict draft.

        verdict MUST be one of the seven FROZEN codes per Phase 238
        Step I _FROZEN_VERDICTS (six operational + REJECTED_INVALID_COMMITMENT
        safety floor). Invalid verdict -> early-return with error.

        review_payload captures the verdict context (anchors_present,
        declared_tier, derived_tier, freshness_age_hours, etc.). Stored
        as canonical JSON; payload_hash = SHA-256 of canonical bytes.
        """
        if not listing_id or not isinstance(listing_id, str):
            return DraftResult(
                draft_id=0,
                draft_uri="",
                payload_hash="",
                payload_bytes=0,
                action_category="skill",
                action_name="marketplace-listing-review",
                agent_id_used=self._agent_id_used,
                error="listing_id must be non-empty string",
            )
        if verdict not in _FROZEN_VERDICTS:
            return DraftResult(
                draft_id=0,
                draft_uri="",
                payload_hash="",
                payload_bytes=0,
                action_category="skill",
                action_name="marketplace-listing-review",
                agent_id_used=self._agent_id_used,
                error=(
                    f"verdict must be one of FROZEN _FROZEN_VERDICTS "
                    f"(Phase 238 Step I); got {verdict!r}"
                ),
            )

        payload = dict(review_payload) if isinstance(review_payload, dict) else {}
        payload.setdefault("listing_id", listing_id)
        payload.setdefault("verdict", verdict)
        payload.setdefault("severity", _SEVERITY_BY_VERDICT.get(verdict, "INFO"))
        payload.setdefault("ts_ns", time.time_ns())

        payload_hash, payload_bytes = _sha256_canonical_json(payload)
        safe = _safe_id_segment(listing_id)
        # /verdict suffix disambiguates from kms-sign-on-the-same-listing
        draft_uri = f"{CURATOR_LISTING_REVIEW_DRAFT_PREFIX}{safe}/verdict"

        try:
            row_id = self._store.insert_operator_agent_draft(
                agent_id=self._agent_id_used,
                action_category="skill",
                action_name="marketplace-listing-review",
                draft_uri=draft_uri,
                payload_hash=payload_hash,
                payload_bytes=payload_bytes,
                kms_sig_present=False,
            )
        except Exception as exc:
            log.warning(
                "CuratorDraftGenerator.draft_marketplace_listing_review persist failed: %s",
                exc,
            )
            return DraftResult(
                draft_id=0,
                draft_uri=draft_uri,
                payload_hash=payload_hash,
                payload_bytes=payload_bytes,
                action_category="skill",
                action_name="marketplace-listing-review",
                agent_id_used=self._agent_id_used,
                error=f"{type(exc).__name__}: {exc}",
            )

        return DraftResult(
            draft_id=int(row_id),
            draft_uri=draft_uri,
            payload_hash=payload_hash,
            payload_bytes=payload_bytes,
            action_category="skill",
            action_name="marketplace-listing-review",
            agent_id_used=self._agent_id_used,
        )

    # ------------------------------------------------------------------
    # 2. tool:kms-sign on draft://listing_reviews/*
    # ------------------------------------------------------------------
    #
    # Curator-specific kms-sign: signs an already-drafted listing review.
    # URI segment uses listing_id + '/sig' so the signature draft is
    # distinguishable from the verdict draft at storage layer (different
    # payload_hash and different URI). Caller MUST pass the verdict
    # payload_hash so the signature is bound to a specific verdict.
    # ------------------------------------------------------------------
    def draft_kms_sign_review(
        self,
        *,
        listing_id: str,
        verdict_payload_hash: str,
        signer_pubkey_hex: str = "",
        signature_payload: Optional[dict] = None,
    ) -> DraftResult:
        """Produce a Curator kms-sign draft over an already-drafted
        listing review.

        verdict_payload_hash links this signature draft to a specific
        marketplace-listing-review draft (returned by
        draft_marketplace_listing_review). The signature draft does not
        re-validate the verdict; it presupposes the upstream draft is
        well-formed.

        kms_sig_present = True when signer_pubkey_hex is non-empty.
        """
        if not listing_id or not isinstance(listing_id, str):
            return DraftResult(
                draft_id=0,
                draft_uri="",
                payload_hash="",
                payload_bytes=0,
                action_category="tool",
                action_name="kms-sign",
                agent_id_used=self._agent_id_used,
                error="listing_id must be non-empty string",
            )
        if not verdict_payload_hash or len(verdict_payload_hash) != 64:
            return DraftResult(
                draft_id=0,
                draft_uri="",
                payload_hash="",
                payload_bytes=0,
                action_category="tool",
                action_name="kms-sign",
                agent_id_used=self._agent_id_used,
                error="verdict_payload_hash must be 64-char SHA-256 hex",
            )

        payload = dict(signature_payload) if isinstance(signature_payload, dict) else {}
        payload.setdefault("listing_id", listing_id)
        payload.setdefault("verdict_payload_hash", verdict_payload_hash)
        payload.setdefault("ts_ns", time.time_ns())
        if signer_pubkey_hex:
            payload["signer_pubkey_hex"] = str(signer_pubkey_hex)

        payload_hash, payload_bytes = _sha256_canonical_json(payload)
        safe = _safe_id_segment(listing_id)
        # /sig suffix disambiguates from /verdict draft
        draft_uri = f"{CURATOR_LISTING_REVIEW_DRAFT_PREFIX}{safe}/sig"

        try:
            row_id = self._store.insert_operator_agent_draft(
                agent_id=self._agent_id_used,
                action_category="tool",
                action_name="kms-sign",
                draft_uri=draft_uri,
                payload_hash=payload_hash,
                payload_bytes=payload_bytes,
                kms_sig_present=bool(signer_pubkey_hex),
            )
        except Exception as exc:
            log.warning(
                "CuratorDraftGenerator.draft_kms_sign_review persist failed: %s", exc
            )
            return DraftResult(
                draft_id=0,
                draft_uri=draft_uri,
                payload_hash=payload_hash,
                payload_bytes=payload_bytes,
                action_category="tool",
                action_name="kms-sign",
                agent_id_used=self._agent_id_used,
                error=f"{type(exc).__name__}: {exc}",
            )

        return DraftResult(
            draft_id=int(row_id),
            draft_uri=draft_uri,
            payload_hash=payload_hash,
            payload_bytes=payload_bytes,
            action_category="tool",
            action_name="kms-sign",
            agent_id_used=self._agent_id_used,
        )

    # ------------------------------------------------------------------
    # 3. tool:operator-notify on draft://operator_notifications/*
    # ------------------------------------------------------------------
    #
    # Suspension RECOMMENDATION channel. At O2 SUGGEST, Curator can
    # recommend operator-final action (e.g. listing suspension) but
    # cannot execute. At O3 ACTING, Curator gains direct
    # tool:marketplace-listing-suspend authority on chain://iotex-testnet
    # via the setCurator() role. operator-notify remains useful at O3
    # for cases where Curator sees a violation but operator-final review
    # is preferred over autonomous suspension.
    # ------------------------------------------------------------------
    def draft_operator_notify(
        self,
        *,
        notification_id: str,
        recommendation: str,
        severity: str = "info",
        notify_payload: Optional[dict] = None,
    ) -> DraftResult:
        """Produce a Curator operator-notify draft (suspension recommendation
        or other operator-attention signal).

        severity: 'info' | 'warn' | 'error' | 'critical' | 'recommend_suspend'
        ('recommend_suspend' is the Curator-specific high-stakes value
        signaling 'operator should suspend this listing'; promoted from
        Phase 238 Step I-AUTOLOOP recommendation primitive).
        """
        if not notification_id or not isinstance(notification_id, str):
            return DraftResult(
                draft_id=0,
                draft_uri="",
                payload_hash="",
                payload_bytes=0,
                action_category="tool",
                action_name="operator-notify",
                agent_id_used=self._agent_id_used,
                error="notification_id must be non-empty string",
            )
        if not recommendation or not isinstance(recommendation, str):
            return DraftResult(
                draft_id=0,
                draft_uri="",
                payload_hash="",
                payload_bytes=0,
                action_category="tool",
                action_name="operator-notify",
                agent_id_used=self._agent_id_used,
                error="recommendation must be non-empty string",
            )
        if severity not in _NOTIFY_SEVERITIES:
            return DraftResult(
                draft_id=0,
                draft_uri="",
                payload_hash="",
                payload_bytes=0,
                action_category="tool",
                action_name="operator-notify",
                agent_id_used=self._agent_id_used,
                error=(
                    f"severity must be one of "
                    f"{sorted(_NOTIFY_SEVERITIES)}; got {severity!r}"
                ),
            )

        payload = dict(notify_payload) if isinstance(notify_payload, dict) else {}
        payload.setdefault("notification_id", notification_id)
        payload.setdefault("recommendation", recommendation)
        payload.setdefault("severity", severity)
        payload.setdefault("ts_ns", time.time_ns())

        payload_hash, payload_bytes = _sha256_canonical_json(payload)
        safe = _safe_id_segment(notification_id)
        draft_uri = f"{CURATOR_OPERATOR_NOTIFICATION_DRAFT_PREFIX}{safe}"

        try:
            row_id = self._store.insert_operator_agent_draft(
                agent_id=self._agent_id_used,
                action_category="tool",
                action_name="operator-notify",
                draft_uri=draft_uri,
                payload_hash=payload_hash,
                payload_bytes=payload_bytes,
                kms_sig_present=False,
            )
        except Exception as exc:
            log.warning(
                "CuratorDraftGenerator.draft_operator_notify persist failed: %s", exc
            )
            return DraftResult(
                draft_id=0,
                draft_uri=draft_uri,
                payload_hash=payload_hash,
                payload_bytes=payload_bytes,
                action_category="tool",
                action_name="operator-notify",
                agent_id_used=self._agent_id_used,
                error=f"{type(exc).__name__}: {exc}",
            )

        return DraftResult(
            draft_id=int(row_id),
            draft_uri=draft_uri,
            payload_hash=payload_hash,
            payload_bytes=payload_bytes,
            action_category="tool",
            action_name="operator-notify",
            agent_id_used=self._agent_id_used,
        )
