"""A2A-STEWARD-EVOLVE B3 — Curator DPIG tests. Pins the product-integrity decision logic: the HARD
violations that make a data-product unsound for sale -> suspend-class recommendation, the SOFT
provenance-incomplete -> hold, and the draft-only rails (Curator recommends; the suspend ACT is two-key).
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from bridge.vapi_bridge.steward_dpig import (
    SCHEMA,
    _canonical_forbidden_columns,
    evaluate_product_integrity,
)

_FORB = frozenset({"l4_mahalanobis_distance", "l5_cv", "ait_rms"})


def _ok(**over):
    base = dict(listing_id="L1", listing_active=True, consent_granted=True, consent_expiry_ts=2000,
                now_ts=1000, listing_category=3, consented_categories={3},
                manifest_columns=["kills", "clean_streak"], manifest_pii_free=True,
                join_verdict="JOIN_COMPLETE", is_aggregate=False, forbidden_columns=_FORB)
    base.update(over)
    return evaluate_product_integrity(**base)


def test_clean_active_product_is_ok():
    r = _ok()
    assert r["recommendation"] == "PRODUCT_OK"
    assert r["hard_violations"] == [] and r["soft_flags"] == []
    assert all(r["integrity_bitmap"].values())


def test_no_consent_recommends_suspend():
    r = _ok(consent_granted=False)
    assert r["recommendation"] == "RECOMMEND_SUSPEND"
    assert any("consent NOT granted" in x for x in r["hard_violations"])
    assert r["integrity_bitmap"]["consent_ok"] is False


def test_expired_consent_recommends_suspend():
    r = _ok(consent_expiry_ts=500, now_ts=1000)   # expired
    assert r["recommendation"] == "RECOMMEND_SUSPEND"
    assert any("expired" in x for x in r["hard_violations"])


def test_category_not_consented_recommends_suspend():
    r = _ok(listing_category=2, consented_categories={3})   # sells cat 2, only consented cat 3
    assert r["recommendation"] == "RECOMMEND_SUSPEND"
    assert any("not in consented" in x for x in r["hard_violations"])


def test_biometric_forbidden_column_leak_recommends_suspend():
    # the strongest data-floor rail: a post-φ product must never carry a FORBIDDEN_COLUMNS feature
    r = _ok(manifest_columns=["kills", "l4_mahalanobis_distance", "clean_streak"])
    assert r["recommendation"] == "RECOMMEND_SUSPEND"
    assert any("FORBIDDEN_COLUMNS leaked" in x for x in r["hard_violations"])
    assert r["integrity_bitmap"]["no_biometric_leak"] is False


def test_manifest_not_pii_free_recommends_suspend():
    r = _ok(manifest_pii_free=False)
    assert r["recommendation"] == "RECOMMEND_SUSPEND"
    assert any("PII-free" in x for x in r["hard_violations"])


def test_aggregate_below_device_floor_recommends_suspend():
    r = _ok(is_aggregate=True, device_count=3, min_device_floor=5)
    assert r["recommendation"] == "RECOMMEND_SUSPEND"
    assert any("below device floor" in x for x in r["hard_violations"])


def test_broken_provenance_join_recommends_suspend():
    r = _ok(join_verdict="JOIN_BROKEN")
    assert r["recommendation"] == "RECOMMEND_SUSPEND"
    assert any("contradictory" in x for x in r["hard_violations"])


def test_incomplete_provenance_join_is_hold_not_suspend():
    # incomplete-but-not-contradictory is a SOFT hold, never a suspend
    r = _ok(join_verdict="JOIN_PARTIAL")
    assert r["recommendation"] == "RECOMMEND_HOLD"
    assert r["hard_violations"] == []
    assert any("incomplete" in x for x in r["soft_flags"])


def test_unverifiable_provenance_join_is_hold_not_suspend():
    # grok round-06: UNVERIFIABLE is incomplete, NOT a structural false-claim -> SOFT hold, not hard
    r = _ok(join_verdict="UNVERIFIABLE")
    assert r["recommendation"] == "RECOMMEND_HOLD"
    assert r["hard_violations"] == []
    assert not any("contradictory" in x for x in r["soft_flags"])


def test_hard_violation_on_inactive_listing_stays_suspended():
    r = _ok(consent_granted=False, listing_active=False)
    assert r["recommendation"] == "STAY_SUSPENDED"


def test_clean_inactive_defaults_to_stay_suspended():
    # grok round-06 RELIST footgun: DPIG can't see non-integrity suspends -> never auto-relist
    r = _ok(listing_active=False)
    assert r["recommendation"] == "STAY_SUSPENDED"
    assert r["hard_violations"] == []
    assert any("relist is an OPERATOR decision" in x for x in r["soft_flags"])


def test_clean_inactive_relists_only_when_integrity_suspend_asserted():
    r = _ok(listing_active=False, suspended_for_integrity=True)
    assert r["recommendation"] == "RECOMMEND_RELIST"
    assert r["hard_violations"] == [] and r["soft_flags"] == []


def test_category_unverifiable_is_hold_not_ok():
    # grok round-06 fail-open: category present but no consented-category evidence -> SOFT, not PRODUCT_OK
    r = _ok(listing_category=3, consented_categories=set())
    assert r["recommendation"] == "RECOMMEND_HOLD"
    assert r["hard_violations"] == []
    assert any("UNVERIFIABLE" in x for x in r["soft_flags"])
    assert r["integrity_bitmap"]["category_ok"] is False


def test_bitmap_no_leak_false_when_forbidden_set_unavailable():
    # grok round-06 bitmap lie: check couldn't run (empty forb, cols present) -> not a clean True
    r = _ok(manifest_columns=["kills"], forbidden_columns=frozenset())
    assert r["integrity_bitmap"]["no_biometric_leak"] is False
    assert any("UNVERIFIABLE" in x for x in r["soft_flags"])


def test_draft_only_rail_and_schema():
    r = _ok()
    assert r["schema"] == SCHEMA and r["steward"] == "curator" and r["task"] == "DPIG"
    assert "DRAFT ONLY" in r["note"] and "TWO-KEY" in r["note"] and "never spends" in r["note"]
    assert "v0.1" in r["note"]


def test_canonical_forbidden_default_is_loadable():
    # DPIG reuses the Arc 5 canonical data-floor rather than forking a copy that could drift
    forb = _canonical_forbidden_columns()
    assert "l4_mahalanobis_distance" in forb and "l5_cv" in forb
