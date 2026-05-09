"""Phase 238 Step I-AUTOLOOP-1 — Curator autonomous review loop.

Wallet-free preconditions for the third Operator Initiative agent's
autonomous review pipeline.  Default-disabled via CURATOR_REVIEW_ENABLED;
activates only when operator opts in + restarts bridge after Step I-FINAL
on-chain registration.

What this module ships:
  - compute_verdict_for_listing()  : module-level reusable verdict helper
                                     (lifted from operator_api.py closure
                                     so the autonomous loop + operator
                                     endpoints can share one code path)
  - select_listings_due_for_review(): query helper — picks listings that
                                     have NOT been reviewed in the past
                                     `since_minutes` window (idempotency
                                     prevents review spam on every loop)
  - run_curator_review_loop()      : async loop registered from main.py
                                     when CURATOR_REVIEW_ENABLED=True

Defensive backoff invariant (Phase 235.x-STABILITY-6 pattern):
  - All per-iteration errors caught + logged at WARNING; loop continues
  - "no running event loop" / asyncio.CancelledError propagate (never
    swallowed) so the supervisor can shut down cleanly
  - Each iteration sleeps cfg.curator_review_interval_s (default 300s)
  - Per-listing failure does NOT abort the batch (fail-open)

Performance invariant (Phase 235.x-STABILITY-2/4 pattern):
  - Per-listing review uses asyncio.to_thread for SQLite reads/writes
  - chain.is_adjudication_recorded is a view call (zero gas, no kill-switch)
"""
from __future__ import annotations

import asyncio
import json as _j
import logging
import time as _t
from typing import Optional

log = logging.getLogger(__name__)


# ── Reusable per-listing verdict helper ─────────────────────────────────────

async def compute_verdict_for_listing(
    store,
    chain,
    cfg,
    commitment_hex_clean: str,
    listing: dict,
    trigger_reason: str,
    protocol_state_cache=None,
) -> dict:
    """Compute a Curator review verdict for one listing + persist it.

    This is the module-level reusable helper.  Both the operator endpoint
    `POST /operator/curator-review-listing` and the autonomous loop
    `run_curator_review_loop` call this to share one verdict-execution
    path, ensuring both surfaces produce identical 13-key output shapes.

    Args:
        store: Store instance (SQLite wrapper)
        chain: ChainClient instance (is_adjudication_recorded view call)
        cfg:   Config instance (for anchor_freshness_blocks)
        commitment_hex_clean: 64-char hex string, lowercase, no 0x prefix
        listing: dict from store.get_listing or marketplace.get_listing
        trigger_reason: operator audit string OR autonomous-loop tag

    Returns:
        13-key dict matching the FROZEN endpoint response shape.
        Never raises — graceful errors surface as REJECTED_INVALID_COMMITMENT.
    """
    from .curator_review import (
        AnchorStates, IpfsState, review_listing as _review_listing,
    )

    # Snapshot anchor isRecorded() state for each non-empty anchor.  View
    # calls bypass kill-switch (read-only) and tolerate RPC errors via
    # fail-open False return (Curator surfaces "anchor not present" rather
    # than blocking the review pipeline).
    async def _is_rec(commit_hex: str) -> bool:
        if not commit_hex or commit_hex == "0" * 64:
            return False
        try:
            return bool(await chain.is_adjudication_recorded(commit_hex))
        except Exception:
            return False

    states = AnchorStates(
        sepproof_recorded  = await _is_rec(listing.get("sepproof_commitment", "")),
        biometric_recorded = await _is_rec(listing.get("biometric_snapshot_hash", "")),
        corpus_recorded    = await _is_rec(listing.get("corpus_snapshot_hash", "")),
        gic_recorded       = await _is_rec(listing.get("gic_hash", "")),
    )

    # IPFS resolvability — None means not checked (fail-open).
    # Step I-FINAL agent process can extend this to a real Pinata HEAD;
    # current implementation skips the check to keep round-trip latency low.
    ipfs = IpfsState(resolvable=None)

    verdict = _review_listing(
        listing, states, ipfs,
        current_block_number=None,
        anchor_freshness_blocks=int(getattr(cfg, "curator_anchor_freshness_blocks", 1_000_000)),
    )
    ts_ns = int(_t.time_ns())
    breakdown_json = _j.dumps(verdict.anchors_recorded_breakdown)

    # Persist via worker thread (Phase 235.x-STABILITY-2 invariant)
    row_id = await asyncio.to_thread(
        store.insert_curator_review,
        commitment_hex_clean,
        verdict.verdict,
        verdict.severity,
        verdict.anchors_recorded_count,
        breakdown_json,
        verdict.consent_marketplace_bit_set,
        verdict.ipfs_resolvable,
        verdict.declared_tier,
        verdict.tier_at_review_time,
        verdict.tier_changed,
        verdict.shadow_mode,
        verdict.reason_detail,
        trigger_reason,
        ts_ns,
    )

    # Phase 238 Step I-AUTOLOOP-3 producer wiring: emit curator_verdict
    # event to the ProtocolStateCache so SSE Twin stream subscribers
    # (frontend Twin controller scene) animate the verdict in real time.
    # Cache argument is optional + fail-open per producer-must-never-break
    # invariant.
    if protocol_state_cache is not None:
        try:
            protocol_state_cache.update_curator_verdict(
                commitment16=commitment_hex_clean[:16],
                verdict=verdict.verdict,
                severity=verdict.severity,
                ts_ns=ts_ns,
            )
        except Exception:
            # Producer wiring must NEVER break the verdict pipeline
            pass

    return {
        "row_id":                       int(row_id),
        "commitment_hex":               commitment_hex_clean,
        "verdict":                      verdict.verdict,
        "severity":                     verdict.severity,
        "anchors_recorded_count":       verdict.anchors_recorded_count,
        "anchors_recorded_breakdown":   verdict.anchors_recorded_breakdown,
        "consent_marketplace_bit_set":  verdict.consent_marketplace_bit_set,
        "ipfs_resolvable":              verdict.ipfs_resolvable,
        "declared_tier":                verdict.declared_tier,
        "tier_at_review_time":          verdict.tier_at_review_time,
        "tier_changed":                 verdict.tier_changed,
        "shadow_mode":                  verdict.shadow_mode,
        "ts_ns":                        ts_ns,
    }


# ── Listing selection (idempotency + autonomous loop driver) ────────────────

def select_listings_due_for_review(
    store,
    since_minutes: int = 60,
    limit: int = 25,
) -> list[dict]:
    """Pick listings that have NOT been Curator-reviewed in the lookback
    window.  Returns full listing dicts ready for compute_verdict_for_listing.

    Idempotency invariant — a listing reviewed within the past
    `since_minutes` is excluded.  This prevents the autonomous loop from
    re-reviewing the same row every 5 minutes; without it, the
    curator_listing_review_log would grow at 12 rows/listing/hour
    indefinitely.

    Caller MUST already hold the asyncio.to_thread context if invoked
    from an async fn — this is a synchronous SQLite read.
    """
    cutoff_ns = int((_t.time() - max(1, since_minutes) * 60) * 1e9)
    limit = max(1, min(int(limit), 100))
    try:
        with store._conn() as conn:
            rows = conn.execute(
                "SELECT m.listing_commitment, m.seller_address, "
                "       m.sepproof_commitment, m.biometric_snapshot_hash, "
                "       m.corpus_snapshot_hash, m.gic_hash, m.consent_bitmask, "
                "       m.data_class, m.price_iotx, m.ipfs_cid, m.ipfs_cid_hash, "
                "       m.ts_ns, m.on_chain_confirmed, m.tx_hash, "
                "       m.anchors_present_count "
                "FROM marketplace_listing_log m "
                "WHERE NOT EXISTS ("
                "  SELECT 1 FROM curator_listing_review_log r "
                "  WHERE r.listing_commitment = m.listing_commitment "
                "    AND r.ts_ns >= ? "
                ") "
                "ORDER BY m.ts_ns DESC LIMIT ?",
                (cutoff_ns, limit),
            ).fetchall()
        return [dict(r) for r in rows]
    except Exception as exc:
        log.warning("select_listings_due_for_review: %s", exc)
        return []


# ── Autonomous review loop ──────────────────────────────────────────────────

async def run_curator_review_loop(store, chain, cfg, protocol_state_cache=None) -> None:
    """Phase 238 Step I-AUTOLOOP-1 — autonomous Curator review loop.

    Polls every cfg.curator_review_interval_s (default 300s = 5 min).
    Each iteration:
      1. select_listings_due_for_review() — pick up to 25 stale listings
      2. compute_verdict_for_listing() per row (writes to curator_listing_review_log)
      3. Sleep for cfg.curator_review_interval_s before next iteration

    Defensive guarantees:
      - Per-iteration errors caught + logged WARNING; loop continues
      - asyncio.CancelledError propagates for clean supervisor shutdown
      - Per-listing failure does NOT abort the batch
      - All SQLite ops on worker thread (Phase 235.x-STABILITY invariant)
      - Initial 30s grace period before first cycle so bridge can finish
        binding ports + agents can finish handshakes (matches FSCA pattern)
    """
    interval_s = float(getattr(cfg, "curator_review_interval_s", 300.0))
    batch_limit = int(getattr(cfg, "curator_review_batch_limit", 25))
    since_minutes = int(getattr(cfg, "curator_review_idempotency_window_minutes", 60))

    log.info(
        "Phase 238 Step I-AUTOLOOP-1 — Curator review loop starting "
        "(interval=%.0fs, batch_limit=%d, since_minutes=%d)",
        interval_s, batch_limit, since_minutes,
    )

    # Initial grace period — match FSCA + cedar_drift_sweeper startup pattern
    try:
        await asyncio.sleep(30.0)
    except asyncio.CancelledError:
        log.info("Curator loop cancelled during startup grace; exiting")
        raise

    iteration = 0
    while True:
        iteration += 1
        cycle_start = _t.monotonic()
        try:
            listings = await asyncio.to_thread(
                select_listings_due_for_review,
                store, since_minutes, batch_limit,
            )
            verdict_count = 0
            verdict_breakdown: dict[str, int] = {}
            for listing in listings:
                commit = str(listing.get("listing_commitment", ""))
                if not commit:
                    continue
                try:
                    res = await compute_verdict_for_listing(
                        store, chain, cfg,
                        commit, listing,
                        trigger_reason=f"autoloop_iter{iteration}",
                        protocol_state_cache=protocol_state_cache,
                    )
                    verdict_count += 1
                    v = res.get("verdict", "UNKNOWN")
                    verdict_breakdown[v] = verdict_breakdown.get(v, 0) + 1
                except asyncio.CancelledError:
                    raise
                except Exception as exc:
                    log.warning(
                        "Curator loop per-listing failure commitment=%s: %s",
                        commit[:16], exc,
                    )
            cycle_dur = _t.monotonic() - cycle_start
            if verdict_count > 0:
                log.info(
                    "Curator loop iter %d: reviewed %d listings in %.2fs — %s",
                    iteration, verdict_count, cycle_dur,
                    json_summary(verdict_breakdown),
                )
            else:
                log.debug(
                    "Curator loop iter %d: no listings due for review (%.2fs)",
                    iteration, cycle_dur,
                )
        except asyncio.CancelledError:
            log.info("Curator loop cancelled at iter %d; exiting cleanly", iteration)
            raise
        except Exception as exc:
            log.warning(
                "Curator loop iter %d outer exception (continuing): %s",
                iteration, exc,
            )

        # Defensive backoff per Phase 235.x-STABILITY-6 pattern
        try:
            await asyncio.sleep(max(1.0, interval_s))
        except asyncio.CancelledError:
            log.info("Curator loop cancelled during sleep; exiting")
            raise


def json_summary(breakdown: dict) -> str:
    """Compact verdict breakdown summary for log lines."""
    if not breakdown:
        return "{}"
    return ", ".join(f"{k}={v}" for k, v in sorted(breakdown.items()))
