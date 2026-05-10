"""Phase O2-DRAFT-GENERATION (Curator) -- end-to-end primitive tests.

Third agent in the parallel-fleet trio. Mirrors test_phase_o2_draft_generation_*.py
patterns from Sentry+Guardian, plus Curator-specific verdict-enum + overturn_curator
+ false_positive_rate semantics.

  T-O2-DRAFT-CURATOR-1: marketplace-listing-review verdict draft persists with
                         FROZEN verdict enum + /verdict URI suffix
  T-O2-DRAFT-CURATOR-2: invalid verdict (not in _FROZEN_VERDICTS) early-returns
  T-O2-DRAFT-CURATOR-3: kms-sign-review draft uses /sig URI suffix; binds to
                         verdict_payload_hash (different URI than /verdict)
  T-O2-DRAFT-CURATOR-4: operator-notify with recommend_suspend severity
                         (Curator-specific high-stakes value)
  T-O2-DRAFT-CURATOR-5: count_drafts(curator) returns N=50 after 50 inserts
  T-O2-DRAFT-CURATOR-6: invalid input early-returns (empty listing_id, bad
                         verdict_payload_hash, bad severity, empty recommendation)
  T-O2-DRAFT-CURATOR-7: end-to-end watcher gate clears for Curator
                         (50 verdict drafts -> _count_drafts_safe(curator) == 50)
  T-O2-DRAFT-CURATOR-8: Curator overturn_curator decision feeds
                         compute_false_positive_rate; ZERO TOLERANCE invariant
                         (PHASE_O3_FALSE_POSITIVE_RATE_MAX=0.0 fires on ANY
                          positive rate)
  T-O2-DRAFT-CURATOR-9: parallel-fleet trio independence -- Sentry/Guardian/
                         Curator counts are isolated per agent
  T-O2-DRAFT-CURATOR-10: idempotent insert -- same verdict drafted twice
                          returns same row_id (count remains 1)
"""

from __future__ import annotations

import sys
import time
import types
from pathlib import Path

import pytest

BRIDGE_DIR = Path(__file__).resolve().parents[1]
if str(BRIDGE_DIR) not in sys.path:
    sys.path.insert(0, str(BRIDGE_DIR))

# Stub web3 + eth_account modules so any indirect import doesn't trip.
for _mod in ["web3", "web3.exceptions", "eth_account"]:
    if _mod not in sys.modules:
        sys.modules[_mod] = types.ModuleType(_mod)


def _make_store(tmp_path):
    from vapi_bridge.store import Store
    db_path = tmp_path / "curator_drafts_test.db"
    return Store(str(db_path))


def _make_cfg(**overrides):
    cfg = types.SimpleNamespace()
    for k, v in overrides.items():
        setattr(cfg, k, v)
    return cfg


# --------------------------------------------------------------------------
# T-O2-DRAFT-CURATOR-1: verdict draft + FROZEN enum + /verdict suffix
# --------------------------------------------------------------------------
def test_T_O2_DRAFT_CURATOR_1_verdict_draft_persists(tmp_path):
    from vapi_bridge.operator_agent_curator_drafting import (
        CuratorDraftGenerator,
        CURATOR_LISTING_REVIEW_DRAFT_PREFIX,
    )
    from vapi_bridge.curator_review import (
        VERDICT_APPROVED,
        VERDICT_FLAGGED_TIER_MISMATCH,
        _FROZEN_VERDICTS,
    )

    store = _make_store(tmp_path)
    gen = CuratorDraftGenerator(cfg=_make_cfg(), store=store)

    result = gen.draft_marketplace_listing_review(
        listing_id="listing-0xabc123",
        verdict=VERDICT_APPROVED,
        review_payload={
            "anchors_present": 4,
            "declared_tier": 3,    # PREMIUM intent
            "derived_tier": 3,     # PREMIUM derived
            "freshness_age_hours": 12.5,
        },
    )
    assert result.error is None
    assert result.draft_id > 0
    assert result.action_category == "skill"
    assert result.action_name == "marketplace-listing-review"
    assert result.agent_id_used == "curator"
    # /verdict suffix disambiguates from kms-sign on same listing
    assert result.draft_uri == f"{CURATOR_LISTING_REVIEW_DRAFT_PREFIX}listing-0xabc123/verdict"

    rows = store.get_operator_agent_drafts(agent_id="curator", limit=10)
    assert len(rows) == 1
    assert rows[0]["operator_decision"] is None  # unreviewed

    # Sanity: another valid verdict produces a distinct draft
    result2 = gen.draft_marketplace_listing_review(
        listing_id="listing-0xdef456",
        verdict=VERDICT_FLAGGED_TIER_MISMATCH,
        review_payload={"reason": "anchors=4 but declared tier=BASIC"},
    )
    assert result2.error is None
    assert result2.draft_id > 0
    assert result2.payload_hash != result.payload_hash

    # All 7 frozen verdicts are accepted
    assert len(_FROZEN_VERDICTS) == 7


# --------------------------------------------------------------------------
# T-O2-DRAFT-CURATOR-2: invalid verdict early-returns
# --------------------------------------------------------------------------
def test_T_O2_DRAFT_CURATOR_2_invalid_verdict_rejected(tmp_path):
    from vapi_bridge.operator_agent_curator_drafting import CuratorDraftGenerator

    store = _make_store(tmp_path)
    gen = CuratorDraftGenerator(cfg=_make_cfg(), store=store)

    for bad in ("APPROVE", "approved", "RANDOM_VERDICT", "", "FLAGGED"):
        r = gen.draft_marketplace_listing_review(
            listing_id="listing-x",
            verdict=bad,
            review_payload={"k": "v"},
        )
        assert r.error is not None, f"verdict {bad!r} must be rejected"
        assert r.draft_id == 0
        assert "_FROZEN_VERDICTS" in r.error or "verdict" in r.error.lower()

    # No rows persisted
    assert store.count_operator_agent_drafts(
        agent_id="curator", since_seconds=86400,
    ) == 0


# --------------------------------------------------------------------------
# T-O2-DRAFT-CURATOR-3: kms-sign-review uses /sig suffix
# --------------------------------------------------------------------------
def test_T_O2_DRAFT_CURATOR_3_kms_sign_uses_sig_suffix(tmp_path):
    from vapi_bridge.operator_agent_curator_drafting import (
        CuratorDraftGenerator,
        CURATOR_LISTING_REVIEW_DRAFT_PREFIX,
    )
    from vapi_bridge.curator_review import VERDICT_APPROVED

    store = _make_store(tmp_path)
    gen = CuratorDraftGenerator(cfg=_make_cfg(), store=store)

    listing = "listing-xyz"
    verdict = gen.draft_marketplace_listing_review(
        listing_id=listing,
        verdict=VERDICT_APPROVED,
        review_payload={"k": "v"},
    )
    assert verdict.error is None

    sig = gen.draft_kms_sign_review(
        listing_id=listing,
        verdict_payload_hash=verdict.payload_hash,
        signer_pubkey_hex="0xfeedface",
        signature_payload={"alg": "ECDSA-P256"},
    )
    assert sig.error is None
    assert sig.draft_id > 0
    # /sig URI distinct from /verdict
    assert sig.draft_uri == f"{CURATOR_LISTING_REVIEW_DRAFT_PREFIX}{listing}/sig"
    assert sig.draft_uri != verdict.draft_uri
    assert sig.payload_hash != verdict.payload_hash

    rows = store.get_operator_agent_drafts(agent_id="curator", limit=10)
    assert len(rows) == 2
    sig_row = next(r for r in rows if "/sig" in r["draft_uri"])
    assert sig_row["kms_sig_present"] == 1


# --------------------------------------------------------------------------
# T-O2-DRAFT-CURATOR-4: operator-notify with recommend_suspend severity
# --------------------------------------------------------------------------
def test_T_O2_DRAFT_CURATOR_4_operator_notify_recommend_suspend(tmp_path):
    from vapi_bridge.operator_agent_curator_drafting import (
        CuratorDraftGenerator,
        CURATOR_OPERATOR_NOTIFICATION_DRAFT_PREFIX,
    )

    store = _make_store(tmp_path)
    gen = CuratorDraftGenerator(cfg=_make_cfg(), store=store)

    result = gen.draft_operator_notify(
        notification_id="notify-listing-abc-2026-05-10T22:00",
        recommendation="suspend listing 0xabc -- anchor stale >30d AND tier mismatch",
        severity="recommend_suspend",
        notify_payload={"listing_id": "0xabc", "anchor_age_hours": 750},
    )
    assert result.error is None
    assert result.draft_id > 0
    assert result.draft_uri.startswith(CURATOR_OPERATOR_NOTIFICATION_DRAFT_PREFIX)
    # / and : sanitized to _
    assert "notify-listing-abc-2026-05-10T22_00" in result.draft_uri
    assert result.action_category == "tool"
    assert result.action_name == "operator-notify"

    # All 5 valid severities accepted
    for sev in ("info", "warn", "error", "critical", "recommend_suspend"):
        r = gen.draft_operator_notify(
            notification_id=f"notify-{sev}",
            recommendation="check this",
            severity=sev,
        )
        assert r.error is None, f"severity {sev!r} must be accepted"


# --------------------------------------------------------------------------
# T-O2-DRAFT-CURATOR-5: count_drafts(curator) returns N=50 after 50 inserts
# --------------------------------------------------------------------------
def test_T_O2_DRAFT_CURATOR_5_count_returns_true_count(tmp_path):
    from vapi_bridge.operator_agent_curator_drafting import CuratorDraftGenerator
    from vapi_bridge.curator_review import VERDICT_APPROVED

    store = _make_store(tmp_path)
    gen = CuratorDraftGenerator(cfg=_make_cfg(), store=store)

    for i in range(50):
        r = gen.draft_marketplace_listing_review(
            listing_id=f"listing-{i:04d}",
            verdict=VERDICT_APPROVED,
            review_payload={"i": i},
        )
        assert r.error is None
        assert r.draft_id > 0

    n = store.count_operator_agent_drafts(
        agent_id="curator", since_seconds=86400,
    )
    assert n == 50


# --------------------------------------------------------------------------
# T-O2-DRAFT-CURATOR-6: invalid input early-returns
# --------------------------------------------------------------------------
def test_T_O2_DRAFT_CURATOR_6_invalid_input(tmp_path):
    from vapi_bridge.operator_agent_curator_drafting import CuratorDraftGenerator
    from vapi_bridge.curator_review import VERDICT_APPROVED

    store = _make_store(tmp_path)
    gen = CuratorDraftGenerator(cfg=_make_cfg(), store=store)

    # Empty listing_id (review)
    r1 = gen.draft_marketplace_listing_review(
        listing_id="", verdict=VERDICT_APPROVED, review_payload={},
    )
    assert r1.error is not None
    assert r1.draft_id == 0

    # Empty listing_id (kms-sign)
    r2 = gen.draft_kms_sign_review(
        listing_id="", verdict_payload_hash="a" * 64,
    )
    assert r2.error is not None
    assert r2.draft_id == 0

    # Bad verdict_payload_hash (not 64 chars)
    r3 = gen.draft_kms_sign_review(
        listing_id="x", verdict_payload_hash="short",
    )
    assert r3.error is not None
    assert "64-char" in r3.error
    assert r3.draft_id == 0

    # Empty recommendation
    r4 = gen.draft_operator_notify(
        notification_id="x", recommendation="",
    )
    assert r4.error is not None
    assert r4.draft_id == 0

    # Bad severity (recommend_suspend is OK; URGENT is not)
    r5 = gen.draft_operator_notify(
        notification_id="x", recommendation="check", severity="URGENT",
    )
    assert r5.error is not None
    assert r5.draft_id == 0

    # Empty notification_id
    r6 = gen.draft_operator_notify(
        notification_id="", recommendation="check",
    )
    assert r6.error is not None
    assert r6.draft_id == 0

    # No rows persisted
    assert store.count_operator_agent_drafts(
        agent_id="curator", since_seconds=86400,
    ) == 0


# --------------------------------------------------------------------------
# T-O2-DRAFT-CURATOR-7: end-to-end watcher gate clears for Curator
# --------------------------------------------------------------------------
def test_T_O2_DRAFT_CURATOR_7_watcher_gate_clears(tmp_path):
    from vapi_bridge.operator_agent_curator_drafting import CuratorDraftGenerator
    from vapi_bridge.curator_review import VERDICT_APPROVED
    from vapi_bridge.operator_initiative_advancement import (
        PHASE_O3_DRAFT_PAYLOAD_MIN,
        _count_drafts_safe,
    )

    store = _make_store(tmp_path)
    gen = CuratorDraftGenerator(cfg=_make_cfg(), store=store)

    # Below threshold
    for i in range(10):
        gen.draft_marketplace_listing_review(
            listing_id=f"listing-{i:04d}",
            verdict=VERDICT_APPROVED,
            review_payload={"i": i},
        )
    assert _count_drafts_safe(store, "curator") == 10
    assert _count_drafts_safe(store, "curator") < PHASE_O3_DRAFT_PAYLOAD_MIN

    # At threshold
    for i in range(10, PHASE_O3_DRAFT_PAYLOAD_MIN):
        gen.draft_marketplace_listing_review(
            listing_id=f"listing-{i:04d}",
            verdict=VERDICT_APPROVED,
            review_payload={"i": i},
        )
    assert _count_drafts_safe(store, "curator") == PHASE_O3_DRAFT_PAYLOAD_MIN


# --------------------------------------------------------------------------
# T-O2-DRAFT-CURATOR-8: overturn_curator -> false_positive_rate ZERO TOLERANCE
# --------------------------------------------------------------------------
def test_T_O2_DRAFT_CURATOR_8_overturn_curator_zero_tolerance(tmp_path):
    """The headline Curator-specific gate: false_positive_rate_30d_max = 0.0
    (zero tolerance per *_o3_acting_v1.json _o3_gates field). ANY
    overturn_curator decision against a Curator draft fires the watcher's
    PHASE_O3_FALSE_POSITIVE_RATE_MAX gate."""
    from vapi_bridge.operator_agent_curator_drafting import CuratorDraftGenerator
    from vapi_bridge.curator_review import VERDICT_FLAGGED_ANCHOR_STALE
    from vapi_bridge.operator_initiative_advancement import (
        PHASE_O3_FALSE_POSITIVE_RATE_MAX,
        _false_positive_rate_safe,
    )

    store = _make_store(tmp_path)
    gen = CuratorDraftGenerator(cfg=_make_cfg(), store=store)

    # Empty -> 0.0
    assert _false_positive_rate_safe(store, "curator") == 0.0
    assert PHASE_O3_FALSE_POSITIVE_RATE_MAX == 0.0  # FROZEN: zero tolerance

    # 10 verdict drafts; 9 accept + 1 overturn_curator -> 1/10 = 10% FP rate
    drafts = []
    for i in range(10):
        drafts.append(
            gen.draft_marketplace_listing_review(
                listing_id=f"listing-{i:04d}",
                verdict=VERDICT_FLAGGED_ANCHOR_STALE,
                review_payload={"i": i},
            )
        )
    for i in range(9):
        store.record_operator_decision(draft_id=drafts[i].draft_id, decision="accept")
    store.record_operator_decision(
        draft_id=drafts[9].draft_id,
        decision="overturn_curator",
        reason="operator re-checked anchor freshness; was actually within window",
    )

    fp_rate = _false_positive_rate_safe(store, "curator")
    assert fp_rate == pytest.approx(0.1, abs=1e-9)
    # ZERO TOLERANCE: any positive rate > MAX(0.0) fires the blocker
    assert fp_rate > PHASE_O3_FALSE_POSITIVE_RATE_MAX

    # And: disagreement_rate is independent (operator accept/reject only;
    # overturn_curator does NOT count toward disagreement denominator)
    dis_rate = store.compute_operator_agent_disagreement_rate(
        agent_id="curator", since_seconds=86400,
    )
    # 9 accepts, 0 rejects, 1 overturn -> denominator only counts
    # accept+reject = 9; numerator (rejects) = 0 -> 0.0
    assert dis_rate == 0.0


# --------------------------------------------------------------------------
# T-O2-DRAFT-CURATOR-9: parallel-fleet trio independence
# --------------------------------------------------------------------------
def test_T_O2_DRAFT_CURATOR_9_trio_independence(tmp_path):
    """Sentry / Guardian / Curator each accumulate independent draft counts.
    Cross-counts MUST NOT pollute any agent's gate. Verifies the parallel-
    fleet per-agent isolation invariant across all three primitive
    surfaces shipped this session."""
    from vapi_bridge.operator_agent_sentry_drafting import SentryDraftGenerator
    from vapi_bridge.operator_agent_guardian_drafting import GuardianDraftGenerator
    from vapi_bridge.operator_agent_curator_drafting import CuratorDraftGenerator
    from vapi_bridge.curator_review import VERDICT_APPROVED

    store = _make_store(tmp_path)
    sentry = SentryDraftGenerator(cfg=_make_cfg(), store=store)
    guardian = GuardianDraftGenerator(cfg=_make_cfg(), store=store)
    curator = CuratorDraftGenerator(cfg=_make_cfg(), store=store)

    for i in range(7):
        sentry.draft_kms_sign(commit_hash=f"{i:040x}")
    for i in range(11):
        guardian.draft_audit_entry(
            audit_id=f"audit-{i}", audit_payload={"i": i},
        )
    for i in range(13):
        curator.draft_marketplace_listing_review(
            listing_id=f"listing-{i}",
            verdict=VERDICT_APPROVED,
            review_payload={"i": i},
        )

    n_sentry = store.count_operator_agent_drafts(
        agent_id="anchor_sentry", since_seconds=86400,
    )
    n_guardian = store.count_operator_agent_drafts(
        agent_id="guardian", since_seconds=86400,
    )
    n_curator = store.count_operator_agent_drafts(
        agent_id="curator", since_seconds=86400,
    )
    assert n_sentry == 7
    assert n_guardian == 11
    assert n_curator == 13
    assert n_sentry + n_guardian + n_curator == 31


# --------------------------------------------------------------------------
# T-O2-DRAFT-CURATOR-10: idempotent insert
# --------------------------------------------------------------------------
def test_T_O2_DRAFT_CURATOR_10_idempotent_insert(tmp_path):
    from vapi_bridge.operator_agent_curator_drafting import CuratorDraftGenerator
    from vapi_bridge.curator_review import VERDICT_APPROVED

    store = _make_store(tmp_path)
    gen = CuratorDraftGenerator(cfg=_make_cfg(), store=store)

    # Same listing_id + verdict + payload (locked ts_ns) -> same hash -> same row
    payload = {"anchors_present": 4, "ts_ns": 1234567890}
    r1 = gen.draft_marketplace_listing_review(
        listing_id="listing-stable",
        verdict=VERDICT_APPROVED,
        review_payload=payload,
    )
    r2 = gen.draft_marketplace_listing_review(
        listing_id="listing-stable",
        verdict=VERDICT_APPROVED,
        review_payload=payload,
    )

    assert r1.payload_hash == r2.payload_hash
    assert r1.draft_id == r2.draft_id
    assert store.count_operator_agent_drafts(
        agent_id="curator", since_seconds=86400,
    ) == 1
