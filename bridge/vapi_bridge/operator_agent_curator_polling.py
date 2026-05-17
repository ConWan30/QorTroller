"""Phase O2-DRAFT-AUTOLOOP (Curator) -- 2026-05-10.

Wires Curator's three already-shipped draft methods
(operator_agent_curator_drafting.py: draft_marketplace_listing_review,
draft_kms_sign_review, draft_operator_notify) to a TESTABLE TRIGGER SURFACE.

Sibling of operator_agent_sentry_polling.py + operator_agent_guardian_polling.py.
Class shape LOCKED across A/B/C polling agents -- mirror Sentry's signature.

SCAFFOLD-ONLY trigger sources via callback injection. The polling loop does
NOT subscribe to bus channels, marketplace event streams, or schedule cron
jobs itself; it consumes from `get_pending_triggers()` injected at boot.
Live wiring (real listing-event subscriber, real anchor-freshness scanner,
real 6h periodic-compliance scheduler) ships in a follow-up phase.

TRIGGER DISPATCH MATRIX (Curator):

  trigger.kind             payload keys                draft methods
  ----------------------- --------------------------- -------------------------
  listing_event           listing_id, verdict (must   draft_marketplace_listing_
                          be one of _FROZEN_VERDICTS),   review THEN
                          review_payload (dict)         draft_kms_sign_review
                                                         (chained via
                                                         verdict_payload_hash)
  anchor_freshness_alert  notification_id, recommend  draft_operator_notify
                          ation, notify_payload         (severity=
                          (optional)                    "recommend_suspend")
  periodic_compliance     listings (list of dicts:    BATCH: for each listing,
                          listing_id, verdict,          draft_marketplace_listing_
                          review_payload)                review

RATE LIMITING: ONE trigger per cycle (queue head). The periodic_compliance
batch is ONE trigger even though it emits N draft rows. listing_event chains
2 methods (review + sig) but is also ONE trigger.

COUNTER UNIT (per-method-success, mirrors Guardian): _drafts_count
increments by the number of successfully persisted draft methods. So a
listing_event += 2 (review + sig); a periodic_compliance batch with N
listings += N; an anchor_freshness_alert += 1.

FAIL-OPEN: trigger handler exceptions caught + logged + skipped; loop continues.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Callable, List, Optional

from .curator_review import _FROZEN_VERDICTS
from .operator_agent_curator_drafting import CuratorDraftGenerator

log = logging.getLogger(__name__)

_POLL_INTERVAL_DEFAULT_S = 30

GetPendingTriggersFn = Callable[[], List[dict]]


def _no_op_triggers() -> List[dict]:
    return []


class CuratorPollingLoop:
    """Phase O2-DRAFT-AUTOLOOP polling loop for Curator. Class shape locked
    across A/B/C polling agents."""

    def __init__(
        self,
        *,
        cfg: Any,
        store: Any,
        draft_generator: CuratorDraftGenerator,
        get_pending_triggers: GetPendingTriggersFn,
        chain: Any = None,
        bus: Any = None,
    ) -> None:
        self._cfg = cfg
        self._store = store
        self._gen = draft_generator
        self._get_pending = get_pending_triggers
        self._task: Optional[asyncio.Task] = None
        self._stop_event = asyncio.Event()
        self._drafts_count = 0
        self._interval_s = int(
            getattr(cfg, "operator_agent_curator_polling_interval_s",
                    _POLL_INTERVAL_DEFAULT_S)
        )
        # Phase 235.x-STABILITY-9 stage 4e 2026-05-17: absorbed-agent ticker
        # invokes CorpusDataCuratorAgent's 7-task data-coherence cycle at
        # its original 30min cadence. Per agent_rationalization_v1.md §3.4
        # + Q4=YES (DataCuratorAgent rename deferred to follow-up).
        self._absorbed_ticker = None
        if getattr(cfg, "stewards_absorb_enabled", True):
            try:
                from .operator_steward_absorbed_agents import (
                    AbsorbedAgentTicker, CURATOR_ABSORBED,
                )
                self._absorbed_ticker = AbsorbedAgentTicker(
                    steward_name="Curator",
                    specs=CURATOR_ABSORBED,
                    cfg=cfg, store=store, chain=chain, bus=bus,
                )
            except Exception as _exc:  # noqa: BLE001
                log.warning(
                    "CuratorPollingLoop: absorbed ticker setup failed (%s); "
                    "absorbed agents will not run", _exc,
                )

    def _drafts_this_session(self) -> int:
        return self._drafts_count

    async def start(self) -> None:
        if self._task is not None and not self._task.done():
            return
        self._stop_event.clear()
        self._task = asyncio.create_task(self._run())
        try:
            self._task.set_name("CuratorPollingLoop._run")
        except AttributeError:
            pass

    async def stop(self) -> None:
        self._stop_event.set()
        if self._task is None:
            return
        if self._task.done():
            self._task = None
            return
        try:
            await asyncio.wait_for(self._task, timeout=5.0)
        except asyncio.TimeoutError:
            self._task.cancel()
            try:
                await self._task
            except (asyncio.CancelledError, Exception):  # noqa: BLE001
                pass
        except asyncio.CancelledError:
            pass
        except Exception as exc:  # noqa: BLE001
            log.warning("CuratorPollingLoop.stop: task await error: %s", exc)
        finally:
            self._task = None

    async def _run(self) -> None:
        log.info("CuratorPollingLoop: started interval=%ds", self._interval_s)
        while not self._stop_event.is_set():
            try:
                triggers = self._safe_get_triggers()
                if triggers:
                    self._dispatch_one(triggers[0])
                # Phase 235.x-STABILITY-9 stage 4e 2026-05-17: tick absorbed
                # CorpusDataCuratorAgent at its 30min cadence.
                if self._absorbed_ticker is not None:
                    try:
                        await self._absorbed_ticker.tick_all()
                    except Exception as _abs_exc:  # noqa: BLE001
                        log.warning(
                            "CuratorPollingLoop: absorbed tick failed (%s); "
                            "continuing main loop", _abs_exc,
                        )
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001
                log.exception("CuratorPollingLoop: outer loop error: %s", exc)
            try:
                await asyncio.wait_for(
                    self._stop_event.wait(), timeout=self._interval_s,
                )
            except asyncio.TimeoutError:
                pass
        log.info("CuratorPollingLoop: stopped")

    def _safe_get_triggers(self) -> List[dict]:
        try:
            res = self._get_pending() or []
        except Exception as exc:  # noqa: BLE001
            log.warning("CuratorPollingLoop: get_pending_triggers error: %s", exc)
            return []
        if not isinstance(res, list):
            log.warning(
                "CuratorPollingLoop: get_pending_triggers returned %s; expected list",
                type(res).__name__,
            )
            return []
        return res

    def _dispatch_one(self, trigger: dict) -> None:
        if not isinstance(trigger, dict):
            log.warning("CuratorPollingLoop: trigger not dict; skipping: %r", trigger)
            return
        kind = trigger.get("kind")
        payload = trigger.get("payload") or {}
        if not isinstance(payload, dict):
            log.warning(
                "CuratorPollingLoop: trigger payload not dict; kind=%r", kind,
            )
            return

        try:
            if kind == "listing_event":
                self._handle_listing_event(payload)
            elif kind == "anchor_freshness_alert":
                self._handle_anchor_freshness_alert(payload)
            elif kind == "periodic_compliance":
                self._handle_periodic_compliance(payload)
            else:
                log.warning("CuratorPollingLoop: unknown trigger kind=%r", kind)
        except Exception as exc:  # noqa: BLE001
            log.warning(
                "CuratorPollingLoop: handler error kind=%r: %s", kind, exc,
            )

    # ------------------------------------------------------------------
    # Trigger handlers
    # ------------------------------------------------------------------
    def _handle_listing_event(self, payload: dict) -> None:
        """listing_event -> marketplace-listing-review + kms-sign-review (chained)."""
        listing_id = str(payload.get("listing_id", "")).strip()
        verdict = str(payload.get("verdict", "")).strip()
        review_payload = payload.get("review_payload") or {}
        if not listing_id or verdict not in _FROZEN_VERDICTS:
            log.info(
                "CuratorPollingLoop: listing_event invalid (id=%r verdict=%r); "
                "delegating to draft_marketplace_listing_review for error reporting",
                listing_id, verdict,
            )
        # 1) marketplace-listing-review draft
        verdict_result = self._gen.draft_marketplace_listing_review(
            listing_id=listing_id,
            verdict=verdict,
            review_payload=review_payload if isinstance(review_payload, dict) else {},
        )
        self._record_result(verdict_result, "listing_event/verdict")
        # 2) kms-sign-review chained via payload_hash linkage (only if verdict
        # produced a real payload_hash; bad-input results have hash="")
        verdict_hash = getattr(verdict_result, "payload_hash", "") or ""
        if len(verdict_hash) == 64:
            sig_result = self._gen.draft_kms_sign_review(
                listing_id=listing_id,
                verdict_payload_hash=verdict_hash,
                signer_pubkey_hex="",
                signature_payload=None,
            )
            self._record_result(sig_result, "listing_event/sig")

    def _handle_anchor_freshness_alert(self, payload: dict) -> None:
        notification_id = str(payload.get("notification_id", "")).strip()
        recommendation = str(payload.get("recommendation", "")).strip()
        notify_payload = payload.get("notify_payload") or {}
        result = self._gen.draft_operator_notify(
            notification_id=notification_id,
            recommendation=recommendation,
            severity="recommend_suspend",
            notify_payload=notify_payload if isinstance(notify_payload, dict) else None,
        )
        self._record_result(result, "anchor_freshness_alert")

    def _handle_periodic_compliance(self, payload: dict) -> None:
        """Batch trigger: emit N marketplace-listing-review drafts (one per
        listing in the batch). Counts as ONE trigger but produces N method
        successes (counter increments by N)."""
        listings = payload.get("listings") or []
        if not isinstance(listings, list):
            log.warning(
                "CuratorPollingLoop: periodic_compliance.listings not list; got %s",
                type(listings).__name__,
            )
            return
        for entry in listings:
            if not isinstance(entry, dict):
                continue
            listing_id = str(entry.get("listing_id", "")).strip()
            verdict = str(entry.get("verdict", "")).strip()
            rp = entry.get("review_payload") or {}
            result = self._gen.draft_marketplace_listing_review(
                listing_id=listing_id,
                verdict=verdict,
                review_payload=rp if isinstance(rp, dict) else {},
            )
            self._record_result(result, "periodic_compliance")

    def _record_result(self, result: Any, label: str) -> None:
        try:
            err = getattr(result, "error", None)
            draft_id = int(getattr(result, "draft_id", 0) or 0)
        except Exception:  # noqa: BLE001
            err = "result-introspect-error"
            draft_id = 0
        if err:
            log.info("CuratorPollingLoop: %s draft error=%s", label, err)
            return
        if draft_id <= 0:
            return
        self._drafts_count += 1
        log.debug(
            "CuratorPollingLoop: %s draft persisted id=%d total=%d",
            label, draft_id, self._drafts_count,
        )


async def run_curator_polling_loop(
    *,
    cfg: Any,
    store: Any,
    draft_generator: Optional[CuratorDraftGenerator] = None,
    get_pending_triggers: Optional[GetPendingTriggersFn] = None,
    chain: Any = None,
    bus: Any = None,
) -> None:
    """Module-level entrypoint invoked from main.py.

    Short-circuits when cfg.operator_agent_curator_polling_enabled is False.
    Constructs CuratorDraftGenerator if draft_generator is None. Uses no-op
    trigger source if get_pending_triggers is None.
    """
    if not getattr(cfg, "operator_agent_curator_polling_enabled", False):
        log.info(
            "CuratorPollingLoop: disabled "
            "(operator_agent_curator_polling_enabled=False)"
        )
        return

    gen = draft_generator
    if gen is None:
        gen = CuratorDraftGenerator(cfg=cfg, store=store)

    triggers_fn = get_pending_triggers or _no_op_triggers

    loop = CuratorPollingLoop(
        cfg=cfg,
        store=store,
        draft_generator=gen,
        get_pending_triggers=triggers_fn,
        chain=chain,
        bus=bus,
    )
    await loop.start()
    try:
        if loop._task is not None:
            await loop._task
    except asyncio.CancelledError:
        await loop.stop()
        raise
