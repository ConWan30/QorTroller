"""Phase O2-CURATOR-TRIGGERS — Live trigger sources for the Curator polling loop.

Sibling of operator_agent_git_trigger_source.py. Ships THREE callable trigger
sources matching the CuratorPollingLoop trigger contract (operator_agent_curator_polling.py):

  1. CuratorMarketplaceListingTriggerSource
       Subscribes to marketplace_listing_log new rows by id high-water mark.
       Emits {kind:'listing_event',
              payload:{listing_id, verdict, review_payload}}

  2. CuratorAnchorFreshnessTriggerSource
       Cron-style: when called past the configured interval, queries the
       most recent N listings, checks each anchor's recorded state via
       chain.is_adjudication_recorded(), and emits
       {kind:'anchor_freshness_alert',
        payload:{notification_id, recommendation, notify_payload}}
       for any listing whose anchor has aged past FRESHNESS_THRESHOLD_HOURS.

  3. CuratorPeriodicComplianceTriggerSource
       Cron-style: at each configured interval boundary, emits ONE batch
       trigger {kind:'periodic_compliance', payload:{listings:[...]}} where
       each listing is {listing_id, verdict, review_payload}.

DRIFT FINDINGS (verified against HEAD 73e70838 source-of-truth):
  - curator_review.review_listing(listing, anchor_states, ipfs_state, ...)
    is NOT a single-arg function — it requires ALSO AnchorStates +
    IpfsState snapshots. Building those requires async chain RPC calls.
    A SYNC trigger source (per spec __call__ -> list[dict]) cannot
    cleanly invoke that pipeline without forcing an event-loop run on
    every poll. The pragmatic, safety-first contract chosen here:
    we DO NOT call review_listing inside trigger sources. Verdict
    emitted is VERDICT_REJECTED_INVALID_COMMITMENT (the safety floor).
    The CuratorPollingLoop's _handle_listing_event then calls
    draft_marketplace_listing_review which validates verdict ∈
    _FROZEN_VERDICTS and persists the draft. The AGENT'S autonomous loop
    (curator_agent.py) is the layer that performs the full review_listing
    pipeline — the trigger source's job is just to surface "this listing
    needs a review fired" with the safest-possible verdict tag.

  - chain.is_adjudication_recorded is async. The freshness source
    detects asyncio.iscoroutine on the result and runs it via
    asyncio.run() if no loop is running, falling back to [] on any
    failure (fail-open).

  - marketplace_listing_log columns verified at store.py:3401-3420:
    id, listing_commitment, seller_address, sepproof_commitment,
    biometric_snapshot_hash, corpus_snapshot_hash, gic_hash,
    consent_bitmask, data_class, price_iotx, ipfs_cid, ipfs_cid_hash,
    ts_ns, on_chain_confirmed, tx_hash, anchors_present_count,
    trigger_reason, created_at. No "listing_id" column — the surfaced
    "listing_id" in payloads is the listing_commitment string.

INVARIANTS (per phase contract):
  * cfg flag False  -> __call__ returns [] (and factory returns None)
  * NEVER raises    -> all exceptions caught, logged at debug/warning, [] returned
  * Source state    -> in-memory only (last-seen-id / last-fired-ts);
                       not persisted; restart resets baseline
  * Baseline rule   -> first call after init seeds last-seen-id from
                       current MAX(id) and returns [] (matches
                       GitTriggerSource baseline pattern documented
                       in T-O2-GIT-TRIG-1)

CONSTANTS (frozen here — not cfg-overridable):
  FRESHNESS_THRESHOLD_HOURS = 720      # 30 days
  LISTING_BATCH_LIMIT       = 50       # max listings inspected per cron fire
  PERIODIC_COMPLIANCE_LIMIT = 50       # max listings per batch trigger
"""
from __future__ import annotations

import asyncio
import logging
import sqlite3
import time
from typing import Any, Optional

log = logging.getLogger(__name__)


# ── Frozen constants ─────────────────────────────────────────────────────────
FRESHNESS_THRESHOLD_HOURS = 720          # 30 days
LISTING_BATCH_LIMIT       = 50
PERIODIC_COMPLIANCE_LIMIT = 50

# Lazy import sentinel; populated on first use to avoid circular imports.
_VERDICT_REJECTED_INVALID_COMMITMENT = "REJECTED_INVALID_COMMITMENT"


def _safety_floor_verdict() -> str:
    """Return the verdict-safety-floor string. Tries to use curator_review's
    canonical constant; falls back to the literal if curator_review is
    unavailable or its constant has been renamed (defensive)."""
    try:
        from .curator_review import VERDICT_REJECTED_INVALID_COMMITMENT
        return VERDICT_REJECTED_INVALID_COMMITMENT
    except Exception:
        return _VERDICT_REJECTED_INVALID_COMMITMENT


# ── Helpers ──────────────────────────────────────────────────────────────────
def _get_db_path(store: Any) -> Optional[str]:
    """Best-effort discovery of the Store's underlying SQLite path. Returns
    None when store object lacks the attribute (test stubs, alt impls)."""
    for attr in ("_db_path", "db_path", "_path", "path"):
        p = getattr(store, attr, None)
        if p:
            return str(p)
    return None


def _fetch_listing_rows(store: Any, *, since_id: int = 0,
                        limit: int = LISTING_BATCH_LIMIT) -> list[dict]:
    """Fetch marketplace_listing_log rows newer than since_id, ordered by
    id ASC. Returns empty list on any error (missing table, missing
    columns, locked DB, etc.). Resilient to schema drift via try/except."""
    db = _get_db_path(store)
    if not db:
        return []
    try:
        conn = sqlite3.connect(db, timeout=2.0)
        conn.row_factory = sqlite3.Row
        try:
            cur = conn.execute(
                "SELECT id, listing_commitment, seller_address, "
                "sepproof_commitment, biometric_snapshot_hash, "
                "corpus_snapshot_hash, gic_hash, consent_bitmask, "
                "data_class, ipfs_cid, ts_ns, anchors_present_count "
                "FROM marketplace_listing_log "
                "WHERE id > ? "
                "ORDER BY id ASC LIMIT ?",
                (int(since_id), int(limit)),
            )
            rows = [dict(r) for r in cur.fetchall()]
            return rows
        finally:
            conn.close()
    except sqlite3.OperationalError as exc:
        log.debug("Curator trigger: marketplace_listing_log query failed (op): %s", exc)
        return []
    except Exception as exc:
        log.debug("Curator trigger: marketplace_listing_log query failed: %s", exc)
        return []


def _fetch_max_listing_id(store: Any) -> int:
    """Return MAX(id) from marketplace_listing_log, or 0 on error/empty."""
    db = _get_db_path(store)
    if not db:
        return 0
    try:
        conn = sqlite3.connect(db, timeout=2.0)
        try:
            row = conn.execute(
                "SELECT MAX(id) FROM marketplace_listing_log"
            ).fetchone()
            if row and row[0] is not None:
                return int(row[0])
            return 0
        finally:
            conn.close()
    except Exception as exc:
        log.debug("Curator trigger: MAX(id) query failed: %s", exc)
        return 0


def _fetch_recent_listing_rows(store: Any, *,
                               limit: int = LISTING_BATCH_LIMIT) -> list[dict]:
    """Fetch the most recent N rows ordered by ts_ns DESC. Used by both
    AnchorFreshness (audit recent listings) and PeriodicCompliance (batch)."""
    db = _get_db_path(store)
    if not db:
        return []
    try:
        conn = sqlite3.connect(db, timeout=2.0)
        conn.row_factory = sqlite3.Row
        try:
            cur = conn.execute(
                "SELECT id, listing_commitment, seller_address, "
                "sepproof_commitment, biometric_snapshot_hash, "
                "corpus_snapshot_hash, gic_hash, consent_bitmask, "
                "data_class, ipfs_cid, ts_ns, anchors_present_count "
                "FROM marketplace_listing_log "
                "ORDER BY ts_ns DESC LIMIT ?",
                (int(limit),),
            )
            return [dict(r) for r in cur.fetchall()]
        finally:
            conn.close()
    except Exception as exc:
        log.debug("Curator trigger: recent listings query failed: %s", exc)
        return []


def _build_review_payload(row: dict) -> dict:
    """Distill a marketplace_listing_log row into the trigger's
    review_payload field. The CuratorPollingLoop's
    draft_marketplace_listing_review consumer treats this as opaque dict
    and just persists it; the agent's autonomous loop reads it."""
    return {
        "anchor_count":       int(row.get("anchors_present_count", 0) or 0),
        "declared_tier":      int(row.get("data_class", 0) or 0),
        "consent_bitmask":    int(row.get("consent_bitmask", 0) or 0),
        "ipfs_cid":           str(row.get("ipfs_cid", "") or ""),
        "ts_ns":              int(row.get("ts_ns", 0) or 0),
        "listing_commitment": str(row.get("listing_commitment", "") or ""),
    }


def _row_to_listing_trigger_dict(row: dict) -> dict:
    """Render a row as the inner {listing_id, verdict, review_payload}
    dict used by both 'listing_event' and 'periodic_compliance' batches."""
    commitment = str(row.get("listing_commitment", "") or "")
    return {
        "listing_id":     commitment,
        "verdict":        _safety_floor_verdict(),
        "review_payload": _build_review_payload(row),
    }


def _maybe_run_coroutine(maybe_coro: Any) -> Any:
    """If the value is a coroutine, run it via asyncio.run; otherwise
    return as-is. Catches all errors and returns None (fail-open)."""
    if not asyncio.iscoroutine(maybe_coro):
        return maybe_coro
    try:
        # If a loop is already running in this thread, asyncio.run will
        # raise RuntimeError; use new_event_loop fallback.
        try:
            return asyncio.run(maybe_coro)
        except RuntimeError:
            loop = asyncio.new_event_loop()
            try:
                return loop.run_until_complete(maybe_coro)
            finally:
                loop.close()
    except Exception as exc:
        log.debug("Curator trigger: coroutine drive failed: %s", exc)
        return None


# ── Source 1: marketplace_listing_log new-row trigger ────────────────────────
class CuratorMarketplaceListingTriggerSource:
    """Subscribes to marketplace_listing_log new rows by id high-water mark.

    Emits one trigger per new listing row (forward chronological order
    by row id) shaped:
        {
            "kind": "listing_event",
            "payload": {
                "listing_id":     <listing_commitment hex>,
                "verdict":        "REJECTED_INVALID_COMMITMENT" (safety floor),
                "review_payload": {anchor_count, declared_tier,
                                   consent_bitmask, ipfs_cid, ts_ns,
                                   listing_commitment},
            },
        }

    First call after init seeds last-seen-id from current MAX(id) and
    returns []. Subsequent calls diff against it.

    See module docstring DRIFT FINDINGS for the rationale behind the
    safety-floor verdict (review_listing is async + multi-arg; sync
    trigger source cannot cleanly compute the full verdict).
    """

    def __init__(self, *, cfg: Any, store: Any) -> None:
        self._cfg = cfg
        self._store = store
        self._last_seen_id: Optional[int] = None
        self._initialized = False

    def __call__(self) -> list[dict]:
        if self._cfg is not None and not getattr(
            self._cfg, "operator_agent_curator_marketplace_trigger_enabled", False
        ):
            return []

        try:
            if not self._initialized:
                # Baseline: seed last-seen-id from current MAX(id), no
                # triggers emitted on first call.
                self._last_seen_id = _fetch_max_listing_id(self._store)
                self._initialized = True
                return []

            since = int(self._last_seen_id or 0)
            rows = _fetch_listing_rows(self._store, since_id=since,
                                       limit=LISTING_BATCH_LIMIT)
            if not rows:
                return []

            triggers: list[dict] = []
            max_id = since
            for row in rows:
                rid = int(row.get("id", 0) or 0)
                if rid > max_id:
                    max_id = rid
                triggers.append({
                    "kind": "listing_event",
                    "payload": _row_to_listing_trigger_dict(row),
                })
            self._last_seen_id = max_id
            return triggers
        except Exception as exc:  # noqa: BLE001 — fail-open contract
            log.warning(
                "CuratorMarketplaceListingTriggerSource: __call__ failed: %s",
                exc,
            )
            return []


# ── Source 2: anchor freshness cron ──────────────────────────────────────────
class CuratorAnchorFreshnessTriggerSource:
    """Cron-style anchor-freshness detector.

    On each call the source first checks an internal last-fired
    timestamp against
    cfg.operator_agent_curator_anchor_freshness_interval_s (default
    3600s). If the interval has not elapsed, returns []. Otherwise:
      1) loads the most recent N marketplace_listing_log rows
      2) for each listing, picks a non-empty anchor commitment field
         (sepproof_commitment / biometric_snapshot_hash /
         corpus_snapshot_hash / gic_hash) and asks
         chain.is_adjudication_recorded(commitment) — async, run via
         asyncio.run when needed
      3) if the listing's age (now - ts_ns/1e9) exceeds
         FRESHNESS_THRESHOLD_HOURS (720h = 30d), emits an
         anchor_freshness_alert trigger recommending operator review

    The age check is intentionally listing-ts-based rather than
    block-number-based: the AdjudicationRegistry doesn't expose
    block.number per record (see curator_review.AnchorStates docstring).
    Listing ts_ns is a strict over-approximation (anchor ≤ listing) so
    flagging by listing age is conservative.

    chain may be None — the source then skips RPC checks and emits
    triggers based purely on listing age (fail-open).
    """

    def __init__(self, *, cfg: Any, store: Any, chain: Any = None) -> None:
        self._cfg = cfg
        self._store = store
        self._chain = chain
        self._last_fired_ts: float = 0.0

    def _interval_s(self) -> float:
        return float(getattr(
            self._cfg,
            "operator_agent_curator_anchor_freshness_interval_s",
            3600,
        ) or 3600)

    def __call__(self) -> list[dict]:
        if self._cfg is not None and not getattr(
            self._cfg,
            "operator_agent_curator_anchor_freshness_trigger_enabled",
            False,
        ):
            return []

        now = time.time()
        if (now - self._last_fired_ts) < self._interval_s():
            return []

        # Even on internal errors, advance the fired-ts so we don't
        # hammer SQLite/RPC on every poll.
        self._last_fired_ts = now

        try:
            rows = _fetch_recent_listing_rows(
                self._store, limit=LISTING_BATCH_LIMIT,
            )
            if not rows:
                return []

            threshold_s = FRESHNESS_THRESHOLD_HOURS * 3600.0
            triggers: list[dict] = []

            for row in rows:
                try:
                    commitment = str(row.get("listing_commitment", "") or "")
                    if not commitment:
                        continue

                    # Listing age (seconds) — ts_ns is nanoseconds.
                    ts_ns = int(row.get("ts_ns", 0) or 0)
                    age_s = max(0.0, now - (ts_ns / 1e9)) if ts_ns > 0 else 0.0

                    if age_s < threshold_s:
                        # Within freshness window; don't flag.
                        continue

                    # Optional chain probe — fail-open. We pick the first
                    # non-empty anchor commitment to verify recorded state.
                    anchor_present: Optional[bool] = None
                    if self._chain is not None:
                        anchor_hex = ""
                        for fld in (
                            "sepproof_commitment",
                            "biometric_snapshot_hash",
                            "corpus_snapshot_hash",
                            "gic_hash",
                        ):
                            v = str(row.get(fld, "") or "")
                            if v and v != "0" * 64:
                                anchor_hex = v
                                break
                        if anchor_hex:
                            try:
                                fn = getattr(
                                    self._chain,
                                    "is_adjudication_recorded",
                                    None,
                                )
                                if fn is not None:
                                    result = fn(anchor_hex)
                                    anchor_present = bool(
                                        _maybe_run_coroutine(result)
                                    )
                            except Exception as exc:
                                log.debug(
                                    "Curator freshness: chain probe failed: %s",
                                    exc,
                                )
                                anchor_present = None

                    age_hours = age_s / 3600.0
                    notify_payload = {
                        "listing_commitment": commitment,
                        "freshness_age_hours": age_hours,
                        "anchor_present": anchor_present,
                        "ts_ns": ts_ns,
                    }
                    triggers.append({
                        "kind": "anchor_freshness_alert",
                        "payload": {
                            "notification_id": (
                                f"anchor-stale-{commitment[:16]}-{int(now)}"
                            ),
                            "recommendation": "recommend_suspend",
                            "notify_payload": notify_payload,
                        },
                    })
                except Exception as exc:
                    # Per-listing failure must not break the batch.
                    log.debug(
                        "Curator freshness: per-listing eval failed: %s",
                        exc,
                    )
                    continue

            return triggers
        except Exception as exc:  # noqa: BLE001
            log.warning(
                "CuratorAnchorFreshnessTriggerSource: __call__ failed: %s",
                exc,
            )
            return []


# ── Source 3: 6h periodic compliance batch ───────────────────────────────────
class CuratorPeriodicComplianceTriggerSource:
    """Cron emitting a single BATCH trigger of recent listings for re-review.

    On each call, checks if cron interval (default 21600s = 6h) has
    elapsed since the last fire. If yes: loads most recent N listing
    rows, packages them into ONE 'periodic_compliance' batch trigger
    where payload.listings is a list of {listing_id, verdict,
    review_payload} dicts (same shape as the 'listing_event' inner
    payload). Verdicts are the safety-floor REJECTED_INVALID_COMMITMENT
    (see module DRIFT FINDINGS).

    The CuratorPollingLoop's _handle_periodic_compliance treats the
    batch as ONE trigger but produces N draft rows — matching the
    rate-limit invariant in the polling-loop docstring.
    """

    def __init__(self, *, cfg: Any, store: Any) -> None:
        self._cfg = cfg
        self._store = store
        self._last_fired_ts: float = 0.0

    def _interval_s(self) -> float:
        return float(getattr(
            self._cfg,
            "operator_agent_curator_periodic_compliance_interval_s",
            21600,
        ) or 21600)

    def __call__(self) -> list[dict]:
        if self._cfg is not None and not getattr(
            self._cfg,
            "operator_agent_curator_periodic_compliance_trigger_enabled",
            False,
        ):
            return []

        now = time.time()
        if (now - self._last_fired_ts) < self._interval_s():
            return []

        # Advance fired-ts even on internal failure (prevents tight
        # retry loops on persistent SQLite errors).
        self._last_fired_ts = now

        try:
            rows = _fetch_recent_listing_rows(
                self._store, limit=PERIODIC_COMPLIANCE_LIMIT,
            )
            if not rows:
                return []

            listings: list[dict] = []
            for row in rows:
                try:
                    listings.append(_row_to_listing_trigger_dict(row))
                except Exception as exc:
                    log.debug(
                        "Curator compliance: row render failed: %s", exc,
                    )
                    continue

            if not listings:
                return []

            return [{
                "kind": "periodic_compliance",
                "payload": {"listings": listings},
            }]
        except Exception as exc:  # noqa: BLE001
            log.warning(
                "CuratorPeriodicComplianceTriggerSource: __call__ failed: %s",
                exc,
            )
            return []


# ── Factories (module-level, mirror make_git_trigger_source) ─────────────────
def make_curator_marketplace_listing_trigger_source(
    *, cfg: Any, store: Any,
) -> Optional[CuratorMarketplaceListingTriggerSource]:
    """Return a configured source, or None when its cfg flag is False."""
    if cfg is not None and not getattr(
        cfg, "operator_agent_curator_marketplace_trigger_enabled", False,
    ):
        log.info(
            "CuratorMarketplaceListingTriggerSource: disabled "
            "(operator_agent_curator_marketplace_trigger_enabled=False)"
        )
        return None
    return CuratorMarketplaceListingTriggerSource(cfg=cfg, store=store)


def make_curator_anchor_freshness_trigger_source(
    *, cfg: Any, store: Any, chain: Any = None,
) -> Optional[CuratorAnchorFreshnessTriggerSource]:
    """Return a configured source, or None when its cfg flag is False."""
    if cfg is not None and not getattr(
        cfg,
        "operator_agent_curator_anchor_freshness_trigger_enabled",
        False,
    ):
        log.info(
            "CuratorAnchorFreshnessTriggerSource: disabled "
            "(operator_agent_curator_anchor_freshness_trigger_enabled=False)"
        )
        return None
    return CuratorAnchorFreshnessTriggerSource(
        cfg=cfg, store=store, chain=chain,
    )


def make_curator_periodic_compliance_trigger_source(
    *, cfg: Any, store: Any,
) -> Optional[CuratorPeriodicComplianceTriggerSource]:
    """Return a configured source, or None when its cfg flag is False."""
    if cfg is not None and not getattr(
        cfg,
        "operator_agent_curator_periodic_compliance_trigger_enabled",
        False,
    ):
        log.info(
            "CuratorPeriodicComplianceTriggerSource: disabled "
            "(operator_agent_curator_periodic_compliance_trigger_enabled=False)"
        )
        return None
    return CuratorPeriodicComplianceTriggerSource(cfg=cfg, store=store)
