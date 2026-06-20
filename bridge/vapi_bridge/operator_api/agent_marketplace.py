"""Marketplace / curator / twin-stream routes (D-DECON-2 operator_api residue #16).

Register-function split per audits/decon-store-map.md agent_marketplace_curator domain.
"""
from __future__ import annotations

import asyncio
import json as _json
import logging
import time
from pathlib import Path
from typing import Callable

from fastapi import FastAPI, Header, HTTPException, Query

log = logging.getLogger(__name__)


def register_agent_marketplace_routes(
    app: FastAPI,
    *,
    cfg,
    store,
    chain,
    check_key: Callable[[str], None],
    check_rate: Callable[[str], None],
    check_read_key: Callable[[str], None],
    repo_root: Path,
    vapi_bridge_dir: Path,
) -> None:
    """Register PALL marketplace, Curator review, and twin-stream HTTP routes."""

    # --- Phase 69: Data Sovereignty + Curator endpoints ---

    @app.get("/curator/data-lineage/{device_id}")
    def get_data_lineage(
        device_id: str,
        limit: int = 50,
        api_key: str = Query(..., description="Shared operator API key"),
    ):
        """Return full data lineage graph for a device (Phase 69).

        Lineage graph: session → proof → ruling → token eligibility.
        Each entry has taxonomy_class, quality_index, curator_note.
        """
        check_key(api_key)
        check_rate(api_key)
        lineage = store.get_data_lineage(device_id.strip(), limit=limit)
        return {
            "device_id": device_id,
            "lineage_count": len(lineage),
            "lineage": lineage,
        }

    @app.get("/curator/token-eligibility/{device_id}")
    def get_token_eligibility(
        device_id: str,
        api_key: str = Query(..., description="Shared operator API key"),
    ):
        """Return token eligibility score + multiplier breakdown for a device (Phase 69).

        Reads from token_eligibility table (updated by DataCuratorAgent every 5 minutes).
        """
        check_key(api_key)
        check_rate(api_key)
        elig = store.get_token_eligibility(device_id.strip())
        if not elig:
            return {"device_id": device_id, "eligibility": None}
        return {"device_id": device_id, "eligibility": elig}

    @app.get("/curator/oracle-state/{oracle_type}")
    def get_oracle_state(
        oracle_type: str,
        limit: int = 50,
        api_key: str = Query(..., description="Shared operator API key"),
    ):
        """Return recent oracle publication log for a given oracle type (Phase 69).

        oracle_type: HUMANITY | RULING | PASSPORT
        """
        check_key(api_key)
        check_rate(api_key)
        oracle_type = oracle_type.upper().strip()
        if oracle_type not in ("HUMANITY", "RULING", "PASSPORT"):
            raise HTTPException(400, f"Unknown oracle_type '{oracle_type}'. Use HUMANITY|RULING|PASSPORT")
        pubs = store.get_oracle_publications(oracle_type=oracle_type, limit=limit)
        return {
            "oracle_type": oracle_type,
            "publication_count": len(pubs),
            "publications": pubs,
        }

    @app.post("/curator/publish-oracle")
    async def publish_oracle(
        device_id: str,
        oracle_type: str,
        api_key: str = Query(..., description="Shared operator API key"),
    ):
        """Force an immediate on-chain oracle update for a device (Phase 69).

        Operator-only. Triggers DataCuratorAgent._publish_oracles() for the device.
        oracle_type: HUMANITY | RULING | PASSPORT | ALL
        """
        check_key(api_key)
        check_rate(api_key)
        from ..data_curator_agent import DataCuratorAgent
        curator = DataCuratorAgent(cfg, store, chain=None)  # no live publish via REST
        oracle_type = oracle_type.upper().strip()
        result = {"device_id": device_id, "oracle_type": oracle_type, "status": "queued"}
        # Log intent — live publish requires chain client from main; REST returns queue status
        store.insert_oracle_publication(
            oracle_type=oracle_type,
            device_id=device_id,
            tx_hash=None,
            payload_json=_json.dumps({"trigger": "manual_rest", "queued_at": time.time()}),
        )
        return result

    # --- Data Economy Arc 3 Commit 3: autonomy-ladder approval endpoints ---
    # The approval_required / manual autonomy levels queue listing intents into
    # pending_listings; these endpoints are the gamer-facing (operator-proxied)
    # surface to review and act on that queue. Approving a listing only marks it
    # APPROVED — it does NOT broadcast. The actual marketplace tx remains the
    # dry-run-defaulted + kill-switch-gated + operator-fired CuratorListingBuilder
    # path. Rejecting removes the intent from the queue. No chain contact here.

    @app.get("/curator/pending-listings")
    def get_pending_listings(
        status: str = "pending",
        api_key: str = Query(..., description="Shared operator API key"),
    ):
        """List packaging intents awaiting the gamer's decision (Arc 3).

        These are sessions packaged under approval_required / manual autonomy.
        Read-only; no chain contact.
        """
        check_key(api_key)
        check_rate(api_key)
        rows = store.get_pending_listings(status=status.strip() or "pending")
        return {"status": status, "count": len(rows), "listings": rows}

    @app.get("/curator/pending-replay-proofs")
    def get_pending_replay_proofs(
        limit: int = 100,
        api_key: str = Query(..., description="Shared operator API key"),
    ):
        """List Arc 5 VHR packaging entries in a pending state.

        Outcomes returned:
          • vhr_proof_deferred           — witness assembled; ceremony absent so
                                           snarkjs cannot prove. Honest no-op.
          • vhr_proof_built_no_verifier  — proof generated; cfg.replay_proof_verifier
                                           _address is empty (no on-chain wire).
          • vhr_proof_built              — full success, awaiting operator-fired
                                           marketplace submission.

        Read-only; no chain contact. Reads from curator_packaging_log via
        store.get_pending_replay_proofs. Dormant pipeline → empty list.
        """
        check_key(api_key)
        check_rate(api_key)
        rows = store.get_pending_replay_proofs(limit=int(limit))
        return {"count": len(rows), "pending_replay_proofs": rows}

    @app.post("/curator/approve-listing/{listing_id}")
    def approve_listing(
        listing_id: int,
        api_key: str = Query(..., description="Shared operator API key"),
    ):
        """Approve a queued listing intent (Arc 3 autonomy ladder).

        Marks the intent APPROVED. Does NOT broadcast — the marketplace tx stays
        dry-run-defaulted + kill-switch-gated + operator-fired. Returns 404 if the
        listing id is unknown.
        """
        check_key(api_key)
        check_rate(api_key)
        ok = store.update_pending_listing_status(int(listing_id), "approved")
        if not ok:
            raise HTTPException(404, f"pending listing {listing_id} not found")
        return {"listing_id": listing_id, "status": "approved", "broadcast": False}

    @app.post("/curator/reject-listing/{listing_id}")
    def reject_listing(
        listing_id: int,
        api_key: str = Query(..., description="Shared operator API key"),
    ):
        """Reject a queued listing intent (Arc 3 autonomy ladder).

        Marks the intent REJECTED — it is never packaged or listed. Returns 404
        if the listing id is unknown.
        """
        check_key(api_key)
        check_rate(api_key)
        ok = store.update_pending_listing_status(int(listing_id), "rejected")
        if not ok:
            raise HTTPException(404, f"pending listing {listing_id} not found")
        return {"listing_id": listing_id, "status": "rejected"}

    # --- Phase 75: Validation gate status ---

    # Phase 238-MARKETPLACE Step F — Provenance-Anchored Listing Layer (PALL) endpoints
    # ------------------------------------------------------------------
    # Bridge-side orchestration for the per-listing cryptographic provenance
    # layer.  Sellers register listings via POST /operator/list-data-session;
    # buyers + auditors browse via GET /agent/marketplace-listings/* endpoints.
    # The actual on-chain extension contract VAPIDataMarketplaceListings.sol
    # (Step D) is deployed separately (Step H, wallet-gated); these endpoints
    # surface the bridge's local listing log and trigger AdjudicationRegistry
    # anchoring of LISTING-v1 commitments.
    @app.post("/operator/list-data-session")
    async def list_data_session_endpoint(
        api_key: str = Query(default=""),
        seller_address: str = Query(..., description="Seller wallet address (must be Phase 69 GAMER)"),
        sepproof_commitment_hex: str = Query(default=""),
        biometric_snapshot_hex: str = Query(default=""),
        corpus_snapshot_hex: str = Query(default=""),
        gic_hash_hex: str = Query(default=""),
        consent_bitmask: int = Query(..., description="uint32 — bit 3 (MARKETPLACE) required"),
        data_class: int = Query(..., description="uint8 in [0, 6] — Phase 69 DATA_TAXONOMY"),
        price_iotx: float = Query(..., description="Listing price in IOTX units"),
        listing_metadata_json: str = Query(default="{}", description="JSON dict, pinned to IPFS"),
        reason: str = Query(default=""),
    ):
        """Create a new PALL listing (operator-triggered).

        Args:
            api_key: cfg.operator_api_key (full operator auth)
            seller_address: must be registered as Phase 69 GAMER
            sepproof_commitment_hex / biometric_snapshot_hex / corpus_snapshot_hex /
                gic_hash_hex: 64-char hex strings of the 4 anchor commitments
                (or empty string if anchor absent — listing tier degrades)
            consent_bitmask: uint32; bit 3 (MARKETPLACE) MUST be set
            data_class: 0..6 per Phase 69 DATA_TAXONOMY
            price_iotx: listing price in full IOTX units
            listing_metadata_json: JSON-encoded dict, pinned to IPFS for buyer retrieval
            reason: operator audit string >= 10 chars

        Returns:
            Result dict with listing_commitment, ipfs_cid, tier preview,
            on_chain_confirmed, tx_hash, ts_ns.

        422: short reason, malformed JSON, missing MARKETPLACE consent,
        invalid data_class, anchor hex parse errors.
        """
        check_key(api_key)
        check_rate(api_key)
        _reason = (reason or "").strip()
        if len(_reason) < 10:
            raise HTTPException(
                422, "reason must be at least 10 characters (operator audit field)"
            )

        import json as _j238fl
        from ..data_marketplace import DataMarketplace

        # Parse listing_metadata_json
        try:
            metadata_dict = _j238fl.loads(listing_metadata_json) if listing_metadata_json else {}
            if not isinstance(metadata_dict, dict):
                raise ValueError("listing_metadata_json must decode to a JSON object")
        except Exception as exc:
            raise HTTPException(422, f"listing_metadata_json parse failed: {exc}")

        # Parse anchor hexes (empty -> None)
        def _hex_to_bytes_or_none(h: str):
            h = (h or "").strip().lower()
            if not h:
                return None
            if h.startswith("0x"):
                h = h[2:]
            try:
                b = bytes.fromhex(h)
                if len(b) != 32:
                    raise ValueError(f"expected 32 bytes, got {len(b)}")
                return b
            except Exception as exc:
                raise HTTPException(422, f"anchor hex parse failed: {exc}")

        sepproof_b   = _hex_to_bytes_or_none(sepproof_commitment_hex)
        biometric_b  = _hex_to_bytes_or_none(biometric_snapshot_hex)
        corpus_b     = _hex_to_bytes_or_none(corpus_snapshot_hex)
        gic_b        = _hex_to_bytes_or_none(gic_hash_hex)

        # Pinata client lookup — may be None if not configured (mock mode allowed)
        pinata_client = getattr(app, "_pinata_client", None)

        marketplace = DataMarketplace(
            store=store, chain=chain, cfg=cfg, pinata_client=pinata_client
        )
        result = await marketplace.create_listing(
            seller_address          = seller_address,
            sepproof_commitment     = sepproof_b,
            biometric_snapshot_hash = biometric_b,
            corpus_snapshot_hash    = corpus_b,
            gic_hash                = gic_b,
            consent_bitmask         = int(consent_bitmask),
            data_class              = int(data_class),
            price_iotx              = float(price_iotx),
            listing_metadata        = metadata_dict,
            trigger_reason          = _reason,
        )
        if result.get("error"):
            # Defensive: validation errors -> 422; other -> 500
            error_msg = result["error"]
            status = 422 if (
                "MARKETPLACE bit" in error_msg
                or "data_class" in error_msg
                or "consent_bitmask" in error_msg
                or "ts_ns out of" in error_msg
                or "32 bytes" in error_msg
            ) else 500
            raise HTTPException(status, detail=result)
        return result

    @app.get("/agent/marketplace-status")
    async def marketplace_status_endpoint(
        x_api_key: str = Header(default=""),
    ):
        """Read-only summary: total + anchored listing counts + latest summary.

        Returns 11 keys: total_listings, anchored_listings, latest_commitment,
        latest_seller, latest_data_class, latest_price_iotx,
        latest_anchors_present, latest_ts_ns, latest_on_chain,
        latest_tx_hash, timestamp.
        """
        check_read_key(x_api_key)
        return await asyncio.to_thread(store.get_marketplace_listing_status)

    @app.get("/agent/marketplace-listing/{commitment_hex}")
    async def marketplace_listing_by_commitment_endpoint(
        commitment_hex: str,
        x_api_key: str = Header(default=""),
    ):
        """Read-only: full listing record by commitment hex.

        Returns 16+ keys covering all stored fields + tier preview
        (tier, tier_name, multiplier_bps).  Returns 404 if not found.
        """
        check_read_key(x_api_key)
        from ..data_marketplace import DataMarketplace
        marketplace = DataMarketplace(store=store, chain=chain, cfg=cfg)

        # Sanitise commitment hex (strip 0x, lowercase)
        h = (commitment_hex or "").strip().lower()
        if h.startswith("0x"):
            h = h[2:]
        if len(h) != 64:
            raise HTTPException(422, "commitment_hex must be 64 hex characters")

        listing = await asyncio.to_thread(marketplace.get_listing, h)
        if not listing:
            raise HTTPException(404, f"listing not found for commitment={h[:16]}...")
        return listing

    @app.get("/agent/marketplace-listings-by-seller")
    async def marketplace_listings_by_seller_endpoint(
        seller_address: str = Query(...),
        limit: int = Query(default=20, le=100),
        x_api_key: str = Header(default=""),
    ):
        """Read-only: per-seller listings (DESC ts_ns).

        Returns list of listing dicts with tier preview.
        """
        check_read_key(x_api_key)
        from ..data_marketplace import DataMarketplace
        marketplace = DataMarketplace(store=store, chain=chain, cfg=cfg)
        rows = await asyncio.to_thread(
            marketplace.get_listings_by_seller, seller_address, int(limit)
        )
        return {"seller": seller_address, "count": len(rows), "listings": rows}

    # ─────────────────────────────────────────────────────────────────────
    # Phase 238 Step I — Curator Shadow Infrastructure (5 endpoints)
    # ─────────────────────────────────────────────────────────────────────
    # The Curator is the third Operator Initiative agent (post Sentry +
    # Guardian).  Cedar bundle authored at
    # bridge/vapi_bridge/cedar_bundles/curator_o1_shadow_v1.json
    # (Merkle 0xa104138a... — agentId placeholder until Step I-FINAL).
    #
    # Wire-contract LOCKED for the upcoming frontend dashboard revamp phase.
    # Do NOT iterate on JSON shapes after frontend integration begins.

    async def _curator_compute_verdict(
        commitment_hex_clean: str,
        listing: dict,
        trigger_reason: str,
    ) -> dict:
        """Phase 238 Step I-AUTOLOOP-1 — delegates to the module-level
        compute_verdict_for_listing in curator_agent.py so the operator
        endpoint + autonomous loop share one verdict-execution path.

        Passes the ProtocolStateCache (Phase 238 Step I-AUTOLOOP-3) so
        operator-triggered manual reviews ALSO emit curator_verdict
        events to SSE subscribers — frontend animates regardless of
        whether the verdict came from the autonomous loop or operator.
        """
        from ..curator_agent import compute_verdict_for_listing
        cache = getattr(app, "_protocol_state_cache", None)
        verdict_result = await compute_verdict_for_listing(
            store, chain, cfg,
            commitment_hex_clean, listing, trigger_reason,
            protocol_state_cache=cache,
        )

        # Phase O5-MLGA Stage 10: MARKET-LISTING-v1 autonomous emission.
        # Every Curator review (manual operator trigger OR autonomous
        # loop) auto-emits one MARKET-LISTING VPM artifact summarizing
        # the listing state at verdict time. Fail-open: any emission
        # failure logs internally + does NOT affect the verdict
        # response. Worker thread to keep the event loop free.
        try:
            from ..market_listing_emitter import emit_market_listing
            verdict_label = str(verdict_result.get("verdict") or "APPROVED")
            await asyncio.to_thread(
                emit_market_listing,
                store=store, cfg=cfg,
                commitment_hex=commitment_hex_clean,
                listing=listing,
                verdict=verdict_label,
            )
        except Exception as _ml_exc:  # noqa: BLE001
            log.warning(
                "MARKET-LISTING emit hook failed (non-fatal): %s", _ml_exc,
            )

        return verdict_result

    @app.post("/operator/curator-review-listing")
    async def curator_review_listing_endpoint(
        api_key: str = Query(default=""),
        commitment_hex: str = Query(..., description="LISTING-v1 commitment hex (64 chars)"),
        reason: str = Query(default="", description="Operator audit string >=10 chars"),
    ):
        """Phase 238 Step I — Manual Curator review trigger (operator action).

        Runs the deterministic review pipeline against the listing pointed
        to by commitment_hex.  Persists a verdict row in
        curator_listing_review_log.  Shadow-mode in O1 — verdict is advisory
        only and does NOT auto-suspend the listing.

        Returns 13-key dict (see curator_review.ReviewVerdict for shape).
        Frontend wire contract is FROZEN.
        """
        check_key(api_key)
        check_rate(api_key)
        _r = (reason or "").strip()
        if len(_r) < 10:
            raise HTTPException(422, "reason must be at least 10 characters")
        h = (commitment_hex or "").strip().lower()
        if h.startswith("0x"):
            h = h[2:]
        if len(h) != 64:
            raise HTTPException(422, "commitment_hex must be 64 hex characters")

        from ..data_marketplace import DataMarketplace
        marketplace = DataMarketplace(store=store, chain=chain, cfg=cfg)
        listing = await asyncio.to_thread(marketplace.get_listing, h)
        if not listing:
            raise HTTPException(404, f"listing not found for commitment={h[:16]}...")

        return await _curator_compute_verdict(h, listing, _r)

    @app.get("/agent/curator-status")
    async def curator_status_endpoint(
        x_api_key: str = Header(default=""),
    ):
        """Phase 238 Step I — Curator review summary (top-of-tab widget).

        Returns 10 keys: curator_review_enabled, total_reviews,
        approved_reviews, flagged_reviews, rejected_reviews, latest_verdict,
        latest_listing_commitment, latest_review_ts_ns, shadow_mode, timestamp.
        """
        check_read_key(x_api_key)
        agg = await asyncio.to_thread(store.get_curator_review_status)
        agg["curator_review_enabled"] = bool(getattr(cfg, "curator_review_enabled", False))
        return agg

    @app.get("/agent/curator-review/{commitment_hex}")
    async def curator_review_for_listing_endpoint(
        commitment_hex: str,
        limit: int = Query(default=50, le=200),
        x_api_key: str = Header(default=""),
    ):
        """Phase 238 Step I — Per-listing review timeline (drawer).

        Returns { listing_commitment, reviews: [...], total }.  Reviews
        sorted DESC by ts_ns so most recent appears first.
        """
        check_read_key(x_api_key)
        h = (commitment_hex or "").strip().lower()
        if h.startswith("0x"):
            h = h[2:]
        if len(h) != 64:
            raise HTTPException(422, "commitment_hex must be 64 hex characters")
        rows = await asyncio.to_thread(
            store.get_curator_reviews_for_listing, h, int(limit)
        )
        return {
            "listing_commitment": h,
            "reviews":            rows,
            "total":              len(rows),
        }

    @app.get("/agent/curator-flagged-listings")
    async def curator_flagged_listings_endpoint(
        since_minutes: int = Query(default=1440),
        limit: int = Query(default=50),
        x_api_key: str = Header(default=""),
    ):
        """Phase 238 Step I — Flagged listings hot-bar (operator audit).

        Returns { listings: [...], total, since_minutes, capped }.
        Caps: limit <= 100 (silently clamped); since_minutes <= 30d.
        """
        check_read_key(x_api_key)
        # Caps applied inside store helper too — defensive double-clamp here
        original_limit = int(limit)
        original_since = int(since_minutes)
        clamped_limit = max(1, min(original_limit, 100))
        clamped_since = max(1, min(original_since, 43200))
        rows = await asyncio.to_thread(
            store.get_curator_flagged_listings,
            clamped_since, clamped_limit
        )
        return {
            "listings":      rows,
            "total":         len(rows),
            "since_minutes": clamped_since,
            "capped":        (clamped_limit != original_limit) or (clamped_since != original_since),
        }

    @app.post("/operator/curator-bulk-review")
    async def curator_bulk_review_endpoint(
        api_key: str = Query(default=""),
        seller_address: str = Query(default=""),
        since_minutes: int = Query(default=1440),
        limit: int = Query(default=20, le=100),
        reason: str = Query(default=""),
    ):
        """Phase 238 Step I — Bulk re-review of recent listings (operator action).

        Re-runs the Curator review pipeline against currently-stored listings
        matching the filter.  Use case: anchor went stale → flag retroactively
        without waiting for autonomous Curator loop (Step I-FINAL).

        Returns { reviewed_count, verdicts_breakdown: {...}, reviews: [...], ts_ns }.
        """
        check_key(api_key)
        check_rate(api_key)
        _r = (reason or "").strip()
        if len(_r) < 10:
            raise HTTPException(422, "reason must be at least 10 characters")
        clamped_limit = max(1, min(int(limit), 100))

        # Gather candidate listings — by-seller filter narrows scope
        if seller_address:
            listings = await asyncio.to_thread(
                store.get_marketplace_listings_by_seller, seller_address, clamped_limit
            )
            # Re-fetch full listing fields for each (helper above only returns subset)
            from ..data_marketplace import DataMarketplace
            marketplace = DataMarketplace(store=store, chain=chain, cfg=cfg)
            full_listings = []
            for short_listing in listings:
                full = await asyncio.to_thread(
                    marketplace.get_listing, short_listing.get("listing_commitment", "")
                )
                if full:
                    full_listings.append(full)
            listings = full_listings
        else:
            # No seller filter — pull most recent listings up to limit
            with store._conn() as conn:
                rows = conn.execute(
                    "SELECT listing_commitment, seller_address, sepproof_commitment, "
                    "       biometric_snapshot_hash, corpus_snapshot_hash, gic_hash, "
                    "       consent_bitmask, data_class, price_iotx, ipfs_cid, "
                    "       ipfs_cid_hash, ts_ns, on_chain_confirmed, tx_hash, "
                    "       anchors_present_count "
                    "FROM marketplace_listing_log ORDER BY ts_ns DESC LIMIT ?",
                    (clamped_limit,)
                ).fetchall()
            listings = [dict(r) for r in rows]

        breakdown: dict = {}
        reviews_out: list = []
        for listing in listings:
            commit = str(listing.get("listing_commitment", ""))
            if not commit:
                continue
            try:
                review = await _curator_compute_verdict(commit, listing, _r)
                v = review["verdict"]
                breakdown[v] = breakdown.get(v, 0) + 1
                reviews_out.append(review)
            except Exception as e:
                log.warning("curator-bulk-review per-listing failure: %s", e)

        import time as _t238bulk
        return {
            "reviewed_count":      len(reviews_out),
            "verdicts_breakdown":  breakdown,
            "reviews":             reviews_out,
            "since_minutes":       int(since_minutes),
            "ts_ns":               int(_t238bulk.time_ns()),
        }

    # ─────────────────────────────────────────────────────────────────────
    # Phase 238 Step I-AUTOLOOP-3 — SSE Twin Stream
    # ─────────────────────────────────────────────────────────────────────
    # Real-time event hub for the frontend Twin controller scene + dashboard
    # pulse animations.  ProtocolStateCache holds bounded ring buffers for
    # 5 event categories; this SSE endpoint fans them out to EventSource
    # clients.  Heartbeat fires every 15s to keep idle connections alive.
    #
    # Wire contract LOCKED for the upcoming frontend revamp.  Adding a
    # new event type requires v2 of protocol_state_cache.py + frontend.

    @app.get("/agent/twin-stream")
    async def twin_stream_endpoint(
        x_api_key: str = Header(default=""),
        backfill: int = Query(
            default=0, ge=0, le=20,
            description="Optional: emit up to N most-recent events per category before live stream",
        ),
    ):
        """Phase 238 Step I-AUTOLOOP-3 — SSE event stream for Twin scene.

        Subscribes the client to ProtocolStateCache + emits typed events
        as they fire from bridge event sources.  Frontend EventSource
        consumes these to drive Twin controller animations + tier badge
        pulses + Operator-bar status updates.

        Event types (FROZEN):
            poac_chain_link    { hash16, ts_ns }
            gic_verdict        { verdict, severity, ts_ns }
            pcc_state_change   { capture_state, host_state, ts_ns }
            curator_verdict    { commitment16, verdict, severity, ts_ns }
            anchor_confirmed   { tx_hash, primitive_type, ts_ns }
            heartbeat          { ts_ns }   # every 15s, keepalive
        """
        check_read_key(x_api_key)
        cache = getattr(app, "_protocol_state_cache", None)
        if cache is None:
            # Bridge booted without cache wired (shouldn't happen post-Step I-AUTOLOOP-3)
            from ..protocol_state_cache import ProtocolStateCache
            cache = ProtocolStateCache()
            app._protocol_state_cache = cache

        async def _generate():
            queue = cache.subscribe()
            try:
                # Optional backfill of most-recent events before live stream
                if backfill > 0:
                    from ..protocol_state_cache import (
                        EVENT_POAC_CHAIN_LINK, EVENT_GIC_VERDICT,
                        EVENT_PCC_STATE_CHANGE, EVENT_CURATOR_VERDICT,
                        EVENT_ANCHOR_CONFIRMED,
                    )
                    for et in (
                        EVENT_POAC_CHAIN_LINK, EVENT_GIC_VERDICT,
                        EVENT_PCC_STATE_CHANGE, EVENT_CURATOR_VERDICT,
                        EVENT_ANCHOR_CONFIRMED,
                    ):
                        for evt in cache.recent(et, n=backfill):
                            yield f"event: {et}\ndata: {_json.dumps(evt)}\n\n"

                # Live stream
                while True:
                    event_type, payload = await queue.get()
                    yield f"event: {event_type}\ndata: {_json.dumps(payload)}\n\n"
            except asyncio.CancelledError:
                # Client disconnected — clean unsubscribe
                pass
            finally:
                cache.unsubscribe(queue)

        return StreamingResponse(
            _generate(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    @app.get("/agent/twin-stream-stats")
    async def twin_stream_stats_endpoint(
        x_api_key: str = Header(default=""),
    ):
        """Telemetry summary for ProtocolStateCache.  Read-only.

        Returns: { events_emitted, events_dropped, subscribers_active,
                   subscribers_registered, buffer_sizes }
        """
        check_read_key(x_api_key)
        cache = getattr(app, "_protocol_state_cache", None)
        if cache is None:
            return {
                "events_emitted":         0,
                "events_dropped":         0,
                "subscribers_active":     0,
                "subscribers_registered": 0,
                "buffer_sizes":           {},
                "cache_attached":         False,
            }
        stats = cache.stats()
        stats["cache_attached"] = True
        return stats

    # Phase 235-DASH-UPGRADE — GET /agent/auto-trigger-status
    # ------------------------------------------------------------------
    # Read-only telemetry for the SessionBoundaryDetectorAgent (Phase
    # 235-AUTO-TRIGGER, agent #38).  Exists so the gamer dashboard can
    # surface live agent state during the 5-min throttle windows where
    # chain_length appears static — without it, the user sees a frozen
    # dashboard for 5–15 minutes between every stamp and may push manual
    # triggers that trip the FSCA AUTO_TRIGGER_RATE_LIMIT_VIOLATION rule.
    #
    # The agent instance is attached to app._sbda from main.py.  Returns
    # `agent_alive: false` when the agent isn't wired (auto_trigger_enabled
    # =false at startup) so the dashboard can render a muted "OFF" chip.
    @app.get("/operator/curator-graduation-readiness")
    async def get_curator_graduation_readiness(
        x_api_key: str = Header(default=""),
    ):
        """Curator O2_SUGGEST -> O3_ACT consolidated graduation
        readiness — wallet-free.

        Exposes the same payload as scripts/curator_graduation_
        readiness_audit.py. Reduces 4 sub-audits (G7 + watcher + CFSS
        + on-chain) to a single READY/BLOCKED/FAIL/ERROR verdict.
        Frontend Operator Console reads this for the "Curator
        graduation cleared" dashboard tile.
        """
        check_read_key(x_api_key)
        try:
            import importlib.util
            import sys as _sys
            from pathlib import Path as _Path
            _proj = repo_root
            if str(_proj / "scripts") not in _sys.path:
                _sys.path.insert(0, str(_proj / "scripts"))
            _spec = importlib.util.spec_from_file_location(
                "curator_grad_ep",
                _proj / "scripts" / "curator_graduation_readiness_audit.py",
            )
            _mod = importlib.util.module_from_spec(_spec)
            _sys.modules["curator_grad_ep"] = _mod
            _spec.loader.exec_module(_mod)
        except Exception as exc:
            raise HTTPException(
                status_code=500,
                detail=f"curator_grad_audit import failed: {exc}",
            )
        db_path = _Path(getattr(cfg, "db_path", "bridge/vapi_store.db"))
        bundle_dir = vapi_bridge_dir / "cedar_bundles"
        report, exit_code = await asyncio.to_thread(
            _mod.run_audit, db_path, bundle_dir,
        )
        report["http_exit_code"] = exit_code
        report["timestamp"] = time.time()
        return report


