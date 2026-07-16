"""A2A-STEWARD-EVOLVE B3 — Curator DPIG (Data-Product Integrity Gate).

Curator's O3 authority is marketplace-listing-suspend (a real IOTX spend). Curator already has BOTH a
drafting *pipe* (`operator_agent_curator_drafting.CuratorDraftGenerator.draft_marketplace_listing_review`
— produce+KMS-sign a chosen verdict) AND a *decision surface*
(`curator_review` / `curator_agent.compute_verdict_for_listing` — APPROVED / FLAGGED_TIER_MISMATCH /
FLAGGED_CONSENT_AMBIGUOUS over tier, anchor-freshness, IPFS, the MARKETPLACE consent bit).

HONEST DELTA (grok round-06): DPIG is NOT "the" missing decision logic — it is a SECOND decision surface
scoped to WMP data-PRODUCT integrity, checking the sale-soundness dimensions `curator_review` does NOT:
post-φ action-only (no `FORBIDDEN_COLUMNS` biometric leak), manifest PII-free, aggregate above the
fleet-telemetry de-anonymization floor, provenance join whole (ties to MPJA / PoSP), consent EXPIRY, and
consent CATEGORY-match — plus a suspend/relist RECOMMENDATION vocabulary disjoint from `curator_review`'s
FROZEN verdicts. The consent-revoked-active-listing rail OVERLAPS both `curator_review`'s consent check
and FSCA's `CONSENT_REVOKED_LISTING_ACTIVE` fleet-runtime rule — DPIG re-expresses that GDPR-Art.17 hazard
as a product-integrity DRAFT, it does not invent it. DPIG does NOT (yet) cover tier / anchor-freshness /
IPFS / commitment validity — those stay in `curator_review`; DPIG is not a marketplace-gate superset.

Its output is a DRAFT suspend/relist recommendation that would FEED the existing draft pipe (wiring
DPIG → CuratorDraftGenerator with an explicit rec→verdict mapping is v0.1) — not a hand-authored verdict.

The ACT — `VAPIDataMarketplaceListings.suspendListing()` — stays TWO-KEY + estimate-first via Curator's
existing live-write executor (real IOTX, executor still disabled). DPIG never suspends, never relists,
never spends. Gated by `cfg.dpig_enabled` (default False).
"""
from __future__ import annotations

RECOMMENDATIONS = ("PRODUCT_OK", "RECOMMEND_HOLD", "RECOMMEND_SUSPEND", "RECOMMEND_RELIST",
                   "STAY_SUSPENDED")
SCHEMA = "qortroller-dpig-v0"


def _canonical_forbidden_columns() -> frozenset:
    """The single source of truth for the Arc 5 biometric data-floor. Imported lazily (pulls numpy via
    the pipeline) so the pure evaluator + tests stay dependency-light; callers may inject explicitly."""
    try:
        from .replay_proof_pipeline.pre_processor import ReplayPreProcessor
        return ReplayPreProcessor.FORBIDDEN_COLUMNS
    except Exception:  # noqa: BLE001 - import unavailable -> caller gets an explicit "unverifiable" flag
        return frozenset()


def evaluate_product_integrity(
    *, listing_id: str, listing_active: bool,
    consent_granted: bool = False, consent_expiry_ts: int | None = None, now_ts: int = 0,
    listing_category=None, consented_categories=None,
    manifest_columns=None, manifest_pii_free: bool = True,
    join_verdict: str | None = None,
    is_aggregate: bool = False, device_count: int | None = None, min_device_floor: int = 5,
    forbidden_columns: frozenset | None = None,
    suspended_for_integrity: bool = False,
) -> dict:
    """Pure product-integrity evaluator over one listing's ground evidence. Draft only — no suspend, no
    relist, no IOTX. HARD violations (any -> suspend-class); SOFT flags (incomplete/unverifiable -> hold).

    `suspended_for_integrity` (grok round-06): DPIG only recommends RELIST when the CALLER asserts the
    listing was suspended for an integrity reason DPIG can see. DPIG cannot observe legal-hold / fraud /
    abuse / non-integrity suspends, so a clean-but-inactive listing defaults to STAY_SUSPENDED (relist is
    an operator decision) — never an unsafe auto-relist."""
    forb = forbidden_columns if forbidden_columns is not None else _canonical_forbidden_columns()
    cols = list(manifest_columns or [])
    cats = set(consented_categories or [])

    hard: list[str] = []      # data-floor / consent / provenance-contradiction -> selling-unsound
    soft: list[str] = []      # incomplete-or-unverifiable -> hold for evidence

    # 1. consent must be granted (GDPR / gamer-sovereignty: never sell without consent)
    if not consent_granted:
        hard.append("world-model/marketplace consent NOT granted")
    # 2. consent must not be expired
    elif consent_expiry_ts is not None and int(consent_expiry_ts) < int(now_ts):
        hard.append(f"consent expired (expiry={consent_expiry_ts} < now={now_ts})")
    # 3. the listing's category must be one the gamer consented to (unverifiable when we have a category
    #    but NO consented-category evidence -> SOFT, never a silent PRODUCT_OK)
    category_unverifiable = (listing_category is not None and not cats)
    if listing_category is not None and cats and listing_category not in cats:
        hard.append(f"listing category {listing_category!r} not in consented categories {sorted(cats)}")
    elif category_unverifiable:
        soft.append(f"listing category {listing_category!r} present but no consented-category evidence "
                    f"— category membership UNVERIFIABLE")

    # 4. post-φ action-only: NO FORBIDDEN_COLUMNS biometric feature may appear in the product manifest
    leaked = sorted(c for c in cols if c in forb)
    leak_check_ran = bool(forb) or not cols     # ran iff we have a forbidden set, or nothing to check
    if leaked:
        hard.append(f"biometric FORBIDDEN_COLUMNS leaked into product manifest: {leaked}")
    elif cols and not forb:
        soft.append("forbidden-column set unavailable (import failed) — biometric leak UNVERIFIABLE")

    # 5. manifest must be PII-free (T-WMP2-6 discipline elevated to product-integrity)
    if not manifest_pii_free:
        hard.append("corpus manifest is NOT PII-free")

    # 6. aggregate products must clear the fleet-telemetry de-anonymization floor
    if is_aggregate:
        if device_count is None:
            soft.append("aggregate product with unknown device_count — floor UNVERIFIABLE")
        elif int(device_count) < int(min_device_floor):
            hard.append(f"aggregate below device floor (n={device_count} < {min_device_floor})")

    # 7. provenance join: only a STRUCTURAL false-claim (BROKEN) is HARD; UNVERIFIABLE / PARTIAL / absent
    #    is incomplete-not-contradictory -> SOFT hold (grok round-06)
    jv = None if join_verdict is None else str(join_verdict).upper()
    if jv in ("JOIN_BROKEN", "BROKEN"):
        hard.append(f"provenance join is contradictory ({join_verdict})")
    elif jv in ("JOIN_COMPLETE", "SYNCHRONIZED"):
        pass
    else:
        soft.append(f"provenance join incomplete/absent/unverifiable ({join_verdict}) — needs a whole "
                    f"join before sale")

    if hard:
        recommendation = "RECOMMEND_SUSPEND" if listing_active else "STAY_SUSPENDED"
    elif soft:
        recommendation = "RECOMMEND_HOLD"
    elif not listing_active:
        # clean integrity evidence is NOT sufficient to relist — DPIG can't see non-integrity suspends
        if suspended_for_integrity:
            recommendation = "RECOMMEND_RELIST"
        else:
            recommendation = "STAY_SUSPENDED"
            soft.append("integrity clear but relist is an OPERATOR decision — non-integrity suspend "
                        "reasons (legal-hold/fraud/abuse) are invisible to DPIG")
    else:
        recommendation = "PRODUCT_OK"

    return {
        "schema": SCHEMA,
        "steward": "curator",
        "task": "DPIG",
        "listing_id": listing_id,
        "listing_active": bool(listing_active),
        "integrity_bitmap": {
            "consent_ok": (consent_granted and not (consent_expiry_ts is not None
                                                    and int(consent_expiry_ts) < int(now_ts))),
            # True only when the category check actually cleared; unverifiable (category present, no cats)
            # is NOT a clean pass.
            "category_ok": (listing_category is None
                            or (bool(cats) and listing_category in cats)),
            # honest: clean ONLY when the leak check actually ran and found nothing (grok round-06)
            "no_biometric_leak": (leak_check_ran and not leaked),
            "manifest_pii_free": bool(manifest_pii_free),
            "telemetry_floor_ok": (not is_aggregate) or (device_count is not None
                                                         and int(device_count) >= int(min_device_floor)),
            "provenance_join_whole": (jv in ("JOIN_COMPLETE", "SYNCHRONIZED")),
        },
        "recommendation": recommendation,
        "hard_violations": hard,
        "soft_flags": soft,
        "note": "DRAFT ONLY — Curator RECOMMENDS; the marketplace suspend/relist ACT stays TWO-KEY + "
                "estimate-first via the existing executor (real IOTX). DPIG never suspends, never relists, "
                "never spends. GDPR Art.17: a consent-revoked/expired ACTIVE listing is a SUSPEND "
                "recommendation. v0 = mechanical integrity DECISION logic; wiring it into the existing "
                "CuratorDraftGenerator draft pipe is v0.1.",
    }


def evaluate_products_from_store(store, cfg, *, listing_ids=None, limit: int = 200) -> dict:  # pragma: no cover - read-only adapter STUB
    """Read-only Store/marketplace adapter, gated by cfg.dpig_enabled (default False).

    HONEST SCOPE (mirrors B1 scan_repo / B2 attest_joins_from_store): this is a STUB. It does NOT yet pull
    the real evidence per listing (consent bitmask/expiry from the consent ledger, WMP manifest columns,
    PoSP/MPJA join verdict, fleet-telemetry device_count). Feeding it bare listing_ids would produce
    all-no-consent SUSPEND recommendations (a false 'working product-integrity gate'), so the stub REFUSES
    to invent recommendations and returns an explicit stub marker. The pure evaluate_product_integrity()
    evaluator is real and tested; this adapter is v0.1. Never suspends, never spends, never git/chain."""
    if not bool(getattr(cfg, "dpig_enabled", False)):
        return {"schema": SCHEMA, "enabled": False, "note": "dpig_enabled=False (opt-in capability)"}
    return {"schema": SCHEMA, "enabled": True, "steward": "curator", "task": "DPIG",
            "n_recommendations": 0, "recommendations": [],
            "adapter_scope": "STUB — listing_id list only; no consent/manifest/join/telemetry Store "
                             "extraction (v0.1). The pure evaluate_product_integrity() evaluator works; "
                             "this adapter does not yet.",
            "note": "STUB adapter — refuses to invent recommendations from unresolved evidence. Wire real "
                    "consent-ledger + WMP-manifest + join + telemetry extraction in v0.1. draft-only; "
                    "suspend/relist two-key; no IOTX; no git/chain write."}
