"""Phase O2-DRAFT-AUTOLOOP (Sentry) -- 2026-05-10.

Wires Sentry's three already-shipped draft methods (kms-sign,
provenance-recording, pda-attestation-anchor) to a TESTABLE TRIGGER SURFACE.

This is SCAFFOLD-ONLY at this phase: the loop accepts a `get_pending_triggers`
callable injected at construction. Tests inject deterministic stubs returning
[{kind, payload}, ...] dicts. Live event wiring (real git commit hooks, real
PoAC chain-head emissions, real PoAd-hash producers) is a follow-up phase.

The class shape is locked across A/B/C polling agents (Sentry/Guardian/Curator)
for cross-fleet symmetry: same constructor kwargs, same start()/stop()/
_drafts_this_session() surface, same dispatch matrix idiom.

TRIGGER DISPATCH MATRIX (Sentry):

  trigger.kind          payload keys                  draft methods (sequential)
  --------------------- ----------------------------- -------------------------
  commit                commit_hash, repo, branch     draft_kms_sign +
                                                      draft_provenance_record
  poac_chain_head       chain_head_hex, ts_ns         draft_provenance_record
  poad_hash             device_id_hash_hex,           draft_pda_anchor
                        poad_hash_hex

RATE-LIMIT INVARIANT: at most ONE trigger dispatched per cycle (queue head).
The "trigger" is the unit, not the draft row -- a `commit` trigger produces
two draft rows (kms-sign + provenance) but counts as one trigger toward the
per-cycle ceiling. This bounds queue drain to one trigger per
operator_agent_sentry_polling_interval_s.

FAIL-OPEN: trigger handler exceptions (bad payload shape, generator method
raises) are caught + logged + skipped; the loop continues. Matches the
cedar_drift_sweeper observability-loop contract.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Callable, Optional

log = logging.getLogger(__name__)

# Default poll interval if cfg.operator_agent_sentry_polling_interval_s
# is not set. Pre-Wave 0 ships this field in config.py with default=30s.
_POLL_INTERVAL_DEFAULT_S = 30

# Trigger kinds Sentry knows how to dispatch. Unknown kinds are logged + skipped.
_TRIGGER_KIND_COMMIT = "commit"
_TRIGGER_KIND_POAC_CHAIN_HEAD = "poac_chain_head"
_TRIGGER_KIND_POAD_HASH = "poad_hash"


def _noop_get_pending_triggers() -> list[dict]:
    """Default stub when no trigger source is wired. Returns empty list so
    the loop runs cleanly with zero dispatches per cycle. Live event wiring
    is deferred to a follow-up phase."""
    return []


class SentryPollingLoop:
    """Phase O2-DRAFT-AUTOLOOP polling loop for Sentry.

    Construction:
      cfg                   -- vapi_bridge.config.Config (or test stub)
      store                 -- vapi_bridge.store.Store
      draft_generator       -- SentryDraftGenerator instance (or test stub
                               with the same three method signatures)
      get_pending_triggers  -- callable returning a list of trigger dicts.
                               Each dict: {"kind": <str>, "payload": <dict>}.
                               Tests inject deterministic stubs.
    """

    def __init__(
        self,
        *,
        cfg: Any,
        store: Any,
        draft_generator: Any,
        get_pending_triggers: Callable[[], list[dict]],
        chain: Any = None,
        bus: Any = None,
    ) -> None:
        self._cfg = cfg
        self._store = store
        self._gen = draft_generator
        self._get_triggers = get_pending_triggers
        self._task: Optional[asyncio.Task] = None
        self._stop_event = asyncio.Event()
        self._drafts_count = 0
        self._interval_s = int(
            getattr(cfg, "operator_agent_sentry_polling_interval_s",
                    _POLL_INTERVAL_DEFAULT_S)
        )
        # Phase 235.x-STABILITY-9 stage 4d 2026-05-17: absorbed-agent ticker
        # invokes 4 provenance/chain-anchor agents at their original cadences
        # instead of running 4 standalone background asyncio tasks. Per
        # agent_rationalization_v1.md §3.3 + Q2 (steward cadence: agents fire
        # when their original interval has elapsed relative to last tick).
        self._absorbed_ticker = None
        if getattr(cfg, "stewards_absorb_enabled", True):
            try:
                from .operator_steward_absorbed_agents import (
                    AbsorbedAgentTicker, SENTRY_ABSORBED,
                )
                self._absorbed_ticker = AbsorbedAgentTicker(
                    steward_name="Sentry",
                    specs=SENTRY_ABSORBED,
                    cfg=cfg, store=store, chain=chain, bus=bus,
                )
            except Exception as _exc:  # noqa: BLE001
                log.warning(
                    "SentryPollingLoop: absorbed ticker setup failed (%s); "
                    "absorbed agents will not run", _exc,
                )

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    async def start(self) -> None:
        """Begin the background loop. Idempotent: a second call while already
        running is a no-op + warning."""
        if self._task is not None and not self._task.done():
            log.warning("SentryPollingLoop.start: already running; ignoring")
            return
        self._stop_event.clear()
        self._task = asyncio.ensure_future(self._run_loop())
        self._task.set_name("SentryPollingLoop")

    async def stop(self) -> None:
        """Cancel the background task gracefully."""
        self._stop_event.set()
        if self._task is None:
            return
        if not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            except Exception as exc:  # noqa: BLE001
                log.warning("SentryPollingLoop.stop: task raised: %s", exc)
        self._task = None

    def _drafts_this_session(self) -> int:
        """Count of triggers successfully dispatched this session.
        Each trigger counts as one regardless of how many draft rows it
        produces (commit trigger produces 2 rows but counts as 1)."""
        return self._drafts_count

    # ------------------------------------------------------------------
    # Loop body
    # ------------------------------------------------------------------
    async def _run_loop(self) -> None:
        """Long-lived loop. Wakes on _interval_s; pulls pending triggers;
        dispatches at most one (queue head); sleeps until next cycle."""
        log.info(
            "SentryPollingLoop: started interval=%ds",
            self._interval_s,
        )
        while not self._stop_event.is_set():
            try:
                await self._dispatch_one_cycle()
                # Phase 235.x-STABILITY-9 stage 4d 2026-05-17: tick absorbed
                # provenance/chain-anchor agents. Each fires at its own cadence
                # via per-agent elapsed-since-last-invoked tracking.
                if self._absorbed_ticker is not None:
                    try:
                        await self._absorbed_ticker.tick_all()
                    except Exception as _abs_exc:  # noqa: BLE001
                        log.warning(
                            "SentryPollingLoop: absorbed tick failed (%s); "
                            "continuing main loop", _abs_exc,
                        )
            except asyncio.CancelledError:
                log.info("SentryPollingLoop: cancelled, exiting cleanly")
                raise
            except Exception as exc:  # noqa: BLE001 — observability loop must not die
                log.exception("SentryPollingLoop: outer loop error: %s", exc)
            # Sleep until next cycle, but wake early if stop_event fires.
            try:
                await asyncio.wait_for(
                    self._stop_event.wait(), timeout=self._interval_s,
                )
            except asyncio.TimeoutError:
                pass

    async def _dispatch_one_cycle(self) -> None:
        """Pull pending triggers; dispatch the head of the queue (one trigger).
        Remaining triggers wait for the next cycle (rate-limit invariant)."""
        try:
            triggers = self._get_triggers()
        except Exception as exc:  # noqa: BLE001 — fail-open
            log.warning("SentryPollingLoop: get_pending_triggers raised: %s", exc)
            return
        if not triggers:
            return
        head = triggers[0]
        try:
            self._dispatch_trigger(head)
            self._drafts_count += 1
        except Exception as exc:  # noqa: BLE001 — fail-open per phase contract
            log.warning(
                "SentryPollingLoop: trigger dispatch failed kind=%s err=%s",
                head.get("kind") if isinstance(head, dict) else "?", exc,
            )

    # ------------------------------------------------------------------
    # Trigger dispatch matrix
    # ------------------------------------------------------------------
    def _dispatch_trigger(self, trigger: dict) -> None:
        """Route trigger -> appropriate draft method(s). See TRIGGER DISPATCH
        MATRIX in module docstring."""
        if not isinstance(trigger, dict):
            log.warning("SentryPollingLoop: trigger not a dict; skipping: %r", trigger)
            return
        kind = trigger.get("kind")
        payload = trigger.get("payload") or {}
        if not isinstance(payload, dict):
            log.warning("SentryPollingLoop: trigger payload not a dict; skipping kind=%s", kind)
            return

        if kind == _TRIGGER_KIND_COMMIT:
            self._dispatch_commit(payload)
        elif kind == _TRIGGER_KIND_POAC_CHAIN_HEAD:
            self._dispatch_poac_chain_head(payload)
        elif kind == _TRIGGER_KIND_POAD_HASH:
            self._dispatch_poad_hash(payload)
        else:
            log.warning("SentryPollingLoop: unknown trigger kind=%r; skipping", kind)

    def _dispatch_commit(self, payload: dict) -> None:
        """commit trigger -> kms-sign + provenance-recording (sequential)."""
        commit_hash = payload.get("commit_hash", "")
        repo = payload.get("repo", "")
        branch = payload.get("branch", "")
        # 1. kms-sign
        self._gen.draft_kms_sign(
            commit_hash=commit_hash,
            signer_pubkey_hex="",
            signature_payload={"repo": repo, "branch": branch},
        )
        # 2. provenance-recording
        # Truncate commit hash to 16 chars for record_id suffix readability.
        ch_short = (commit_hash or "")[:16]
        self._gen.draft_provenance_record(
            record_id=f"commit:{ch_short}",
            attestation_payload={
                "event_type": "GIT_COMMIT",
                "subject": commit_hash,
                "repo": repo,
                "branch": branch,
            },
        )

    def _dispatch_poac_chain_head(self, payload: dict) -> None:
        """poac_chain_head trigger -> provenance-recording only."""
        chain_head_hex = payload.get("chain_head_hex", "")
        ts_ns = payload.get("ts_ns", 0)
        ch_short = (chain_head_hex or "")[:16]
        self._gen.draft_provenance_record(
            record_id=f"poac:{ch_short}",
            attestation_payload={
                "event_type": "POAC_CHAIN_HEAD",
                "chain_head": chain_head_hex,
                "ts_ns": ts_ns,
            },
        )

    def _dispatch_poad_hash(self, payload: dict) -> None:
        """poad_hash trigger -> pda-attestation-anchor only."""
        device_id_hash_hex = payload.get("device_id_hash_hex", "")
        poad_hash_hex = payload.get("poad_hash_hex", "")
        self._gen.draft_pda_anchor(
            device_id_hash_hex=device_id_hash_hex,
            poad_hash_hex=poad_hash_hex,
            dual_veto=False,
        )


# ----------------------------------------------------------------------
# Module-level entrypoint (matches cedar_drift_sweeper pattern)
# ----------------------------------------------------------------------
async def run_sentry_polling_loop(
    *,
    cfg: Any,
    store: Any,
    draft_generator: Any = None,
    get_pending_triggers: Optional[Callable[[], list[dict]]] = None,
    chain: Any = None,
    bus: Any = None,
) -> None:
    """Module-level entrypoint invoked from main.py.

    Short-circuits + returns immediately if
    cfg.operator_agent_sentry_polling_enabled is False (opt-in default).

    If draft_generator is None, constructs a SentryDraftGenerator from
    cfg + store. If get_pending_triggers is None, uses a no-op stub that
    returns []; live event wiring is deferred to a follow-up phase.
    """
    if not getattr(cfg, "operator_agent_sentry_polling_enabled", False):
        log.info(
            "SentryPollingLoop: disabled "
            "(operator_agent_sentry_polling_enabled=False)"
        )
        return

    if draft_generator is None:
        # Late import to keep module-load surface light + match the
        # operator_agent_sentry_drafting.py contract.
        from .operator_agent_sentry_drafting import SentryDraftGenerator
        draft_generator = SentryDraftGenerator(cfg=cfg, store=store)

    if get_pending_triggers is None:
        get_pending_triggers = _noop_get_pending_triggers

    loop = SentryPollingLoop(
        cfg=cfg,
        store=store,
        draft_generator=draft_generator,
        get_pending_triggers=get_pending_triggers,
        chain=chain,
        bus=bus,
    )
    await loop.start()
    # Block until the inner task completes (graceful cancellation by main.py
    # task supervisor). Mirrors cedar_drift_sweeper's run_drift_sweep_loop
    # outer-loop semantics.
    if loop._task is not None:
        try:
            await loop._task
        except asyncio.CancelledError:
            log.info("SentryPollingLoop: outer cancelled")
            raise
