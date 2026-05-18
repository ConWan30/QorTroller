"""
Phase 25 — Chain Reconciler

Background coroutine that confirms PHG checkpoints via on-chain event polling.
Polls PHGCheckpointCommitted getLogs every poll_interval seconds.
Marks confirmed=True for matched SQLite checkpoints.
Re-queues confirmed=False checkpoints older than retry_age_s seconds.
"""

import asyncio
import logging

log = logging.getLogger(__name__)


class ChainReconciler:
    """
    Background coroutine: confirms PHG checkpoints via on-chain event polling.

    Polls PHGCheckpointCommitted getLogs every poll_interval seconds.
    Marks confirmed=True for matched SQLite checkpoints.
    Re-queues confirmed=False checkpoints older than retry_age_s (default 300s).

    Usage (from main.py):
        reconciler = ChainReconciler(store, chain, poll_interval=30.0)
        asyncio.create_task(reconciler.run())
    """

    def __init__(self, store, chain, poll_interval: float = 30.0, retry_age_s: float = 300.0,
                 cfg=None, governor=None):
        self._store = store
        self._chain = chain
        self._cfg = cfg
        self._poll_interval = poll_interval
        self._retry_age_s = retry_age_s
        self._running = False
        self._last_block: int = 0
        # Phase 235.x-STABILITY-9 stage 9 (2026-05-17): shared chain-read
        # governor. Optional injection so existing callers / tests work
        # unchanged. When None, lazily create one on first need (lazy
        # creation lets us defer asyncio.Semaphore init until the loop
        # exists). Cfg defaults: 5.0s block-cache TTL + max_concurrent=4
        # + 10.0s per-call timeout.
        self._governor = governor

    def _get_governor(self):
        """Lazy-init the chain-read governor. Returns None if cfg/chain
        is missing or governor construction fails (fail-open: caller falls
        back to direct chain calls)."""
        if self._governor is not None:
            return self._governor
        try:
            from .chain_read_governor import ChainReadGovernor
            # Phase 235.x-STABILITY-9 stage 12 2026-05-17: pass the sync
            # Web3 companion if available so block_number reads route
            # through asyncio.to_thread, closing the Windows
            # ProactorEventLoop cancellation gap (Stage 11 measured the
            # async path leak ~12s of uncancellable socket read after
            # asyncio.wait_for cancellation; total event-loop block was
            # 22s vs governor's 10s timeout).
            _sync_w3 = getattr(self._chain, "_sync_w3", None)
            self._governor = ChainReadGovernor(
                w3=self._chain._w3,
                cfg=self._cfg if self._cfg is not None else type("_", (), {})(),
                sync_w3=_sync_w3,
            )
            return self._governor
        except Exception as exc:  # noqa: BLE001 — fail-open
            log.warning(
                "ChainReconciler: governor lazy-init failed (%s); falling "
                "back to direct chain reads", exc,
            )
            self._governor = False  # sentinel: don't retry init
            return None

    async def run(self):
        """Run the reconciler loop until cancelled."""
        self._running = True
        log.info(
            "ChainReconciler started (poll_interval=%.0fs, retry_age=%.0fs)",
            self._poll_interval, self._retry_age_s,
        )
        # Initialize last_block
        # Phase 235.x-STABILITY-9 stage 9: route through governor when available
        try:
            gov = self._get_governor()
            if gov:
                self._last_block = await gov.get_block_number()
            else:
                self._last_block = await self._chain._w3.eth.block_number
        except Exception:
            self._last_block = 0

        while self._running:
            try:
                await asyncio.sleep(self._poll_interval)
                await self._reconcile_cycle()
            except asyncio.CancelledError:
                log.info("ChainReconciler shutting down")
                self._running = False
                return
            except Exception as exc:
                log.warning("ChainReconciler cycle error: %s", exc)
                # Phase 235.x-STABILITY-6: defensive backoff. If the next
                # iteration's `await asyncio.sleep` also raises (e.g.,
                # 'no running event loop' on a task that lost its loop
                # affinity — empirically observed 2026-05-09 when the bridge
                # event loop is otherwise idle), this inner sleep also
                # raises and we exit cleanly instead of tight-looping at
                # ~9000 errors/second.
                try:
                    await asyncio.sleep(min(self._poll_interval, 5.0))
                except asyncio.CancelledError:
                    self._running = False
                    return
                except Exception as backoff_exc:
                    log.error(
                        "ChainReconciler: backoff sleep failed (%s) — "
                        "exiting loop cleanly to prevent tight-loop spam",
                        backoff_exc,
                    )
                    self._running = False
                    return

    async def _reconcile_cycle(self):
        """Single reconciliation pass: fetch events and mark confirmed.

        Phase 235.x-STABILITY-9 stage 8 (2026-05-17): surgical fix for the
        primary loop-blocker named by Stage 7 instrumentation (10 SLOW SPEC
        events / peak 20.6s on event loop tid). Removes sync SQLite work
        from the event loop via asyncio.to_thread + adds per-section
        timing instrumentation so empirical comparison with the next
        observation window can confirm whether chain RPC or SQLite was
        the dominant contributor.

        Sections retained on event loop (async, yield-friendly):
          - chain block_number read
          - chain get_phg_checkpoint_events (AsyncWeb3 get_logs)
          - asyncio.create_task spawn for requeue (fire-and-forget)
        Sections moved to worker thread via asyncio.to_thread (sync work):
          - batch mark_checkpoint_confirmed(tx_hash) for all events
          - get_unconfirmed_checkpoints SQLite scan
        """
        # Lazy import to avoid cycle + keep helper optional in tests
        from .loop_timing import timed_block

        _chain_warn_s = 2.0
        _sqlite_warn_s = 0.5
        _outer_prefix = "[ChainReconciler] STAGE-8"

        # SECTION A — chain block_number (async; network; STAGE-9 governed)
        # Stage 9: route through governor for TTL cache + semaphore + timeout.
        # Reconciler polls every 30s; TTL is 5s — first call after each poll
        # interval misses cache + fetches; subsequent same-interval calls
        # from OTHER agents (when wired in future) hit cache.
        try:
            with timed_block(
                "chain_block_number",
                warn_s=_chain_warn_s,
                logger=log,
                prefix=_outer_prefix,
                always_info=False,
                slow_word="SLOW CHAIN",
                hint="IoTeX RPC block_number read — network latency or rate-limit "
                     "(STAGE-9 governed: TTL cache + semaphore + timeout)",
            ):
                gov = self._get_governor()
                if gov:
                    current_block = await gov.get_block_number()
                else:
                    current_block = await self._chain._w3.eth.block_number
        except Exception as exc:
            log.warning("ChainReconciler: could not fetch block number: %s", exc)
            return

        if current_block <= self._last_block:
            return

        # SECTION B — chain get_logs (async; network; range-sensitive)
        # Stage 9: route through governor for semaphore + timeout (NOT cached
        # — get_logs is range-specific and not safely cacheable).
        try:
            with timed_block(
                f"chain_get_logs_range_{current_block - self._last_block}",
                warn_s=_chain_warn_s,
                logger=log,
                prefix=_outer_prefix,
                always_info=False,
                slow_word="SLOW CHAIN",
                hint="IoTeX get_logs over block range — STAGE-9 governed "
                     "(semaphore + timeout); narrow range or event-filter "
                     "cursor if persistent",
            ):
                gov = self._get_governor()
                if gov:
                    _from = self._last_block + 1
                    _to = current_block
                    events = await gov.run_read(
                        lambda: self._chain.get_phg_checkpoint_events(_from, _to),
                        label=f"get_phg_checkpoint_events_range_{_to - _from + 1}",
                        fallback=[],
                    )
                else:
                    events = await self._chain.get_phg_checkpoint_events(
                        self._last_block + 1, current_block
                    )
        except Exception as exc:
            log.warning("ChainReconciler: getLogs error (non-fatal): %s", exc)
            events = []

        # SECTION C — batch SQLite writes (sync; off-loop via to_thread)
        # Pre-process tx hashes on event loop (fast pure-Python), then
        # hand a single batch to a worker thread for the SQLite writes.
        tx_hashes_to_confirm: list[str] = []
        for event in events:
            tx_hash = event["transactionHash"]
            if isinstance(tx_hash, bytes):
                tx_hash = tx_hash.hex()
            if not tx_hash.startswith("0x"):
                tx_hash = "0x" + tx_hash
            tx_hashes_to_confirm.append(tx_hash)

        if tx_hashes_to_confirm:
            try:
                with timed_block(
                    f"sqlite_mark_confirmed_batch_N{len(tx_hashes_to_confirm)}",
                    warn_s=_sqlite_warn_s,
                    logger=log,
                    prefix=_outer_prefix,
                    always_info=False,
                    slow_word="SLOW SQLITE",
                    hint="batch mark_checkpoint_confirmed via to_thread — "
                         "investigate WAL contention if persistent",
                ):
                    await asyncio.to_thread(
                        self._apply_confirmed_events_sync, tx_hashes_to_confirm
                    )
            except Exception as exc:
                log.warning(
                    "ChainReconciler: batch confirm error (non-fatal): %s", exc
                )

        self._last_block = current_block

        # SECTION D — SQLite read for unconfirmed retries (sync; off-loop)
        try:
            with timed_block(
                "sqlite_get_unconfirmed",
                warn_s=_sqlite_warn_s,
                logger=log,
                prefix=_outer_prefix,
                always_info=False,
                slow_word="SLOW SQLITE",
                hint="get_unconfirmed_checkpoints scan — investigate WAL contention",
            ):
                unconfirmed = await asyncio.to_thread(
                    self._store.get_unconfirmed_checkpoints,
                    self._retry_age_s,
                )
        except Exception as exc:
            log.warning("ChainReconciler: get_unconfirmed error (non-fatal): %s", exc)
            unconfirmed = []

        # SECTION E — fire-and-forget requeue tasks (async; spawn only, no await)
        for cp in unconfirmed:
            log.warning(
                "ChainReconciler: unconfirmed checkpoint id=%s device=%s tx=%s — scheduling retry",
                cp.get("id"), str(cp.get("device_id", ""))[:16], str(cp.get("tx_hash", ""))[:16],
            )
            asyncio.create_task(self._requeue_checkpoint(cp))

    def _apply_confirmed_events_sync(self, tx_hashes: list[str]) -> int:
        """Sync helper: batch-apply confirmed checkpoint markers.

        Phase 235.x-STABILITY-9 stage 8 (2026-05-17): extracted so the
        N×SQLite writes can run on a worker thread via asyncio.to_thread
        instead of fragmenting the event loop with per-row sync writes.
        Each mark_checkpoint_confirmed is fail-open at the store layer;
        wrapping aggregates the cost without changing per-row semantics.

        Returns the count of writes actually attempted (caller logs).
        """
        n = 0
        for tx_hash in tx_hashes:
            try:
                self._store.mark_checkpoint_confirmed(tx_hash)
                n += 1
                log.debug("ChainReconciler: confirmed checkpoint tx=%s", tx_hash[:16])
            except Exception as exc:  # noqa: BLE001 — fail-open per existing contract
                log.debug(
                    "ChainReconciler: mark_checkpoint_confirmed failed tx=%s: %s",
                    tx_hash[:16], exc,
                )
        return n

    async def _requeue_checkpoint(self, checkpoint: dict):
        """Attempt to re-confirm a stale unconfirmed checkpoint by tx hash lookup."""
        tx_hash = checkpoint.get("tx_hash", "")
        if not tx_hash:
            return
        try:
            receipt = await self._chain.wait_for_receipt(tx_hash, timeout=10)
            if receipt and receipt.get("status") == 1:
                self._store.mark_checkpoint_confirmed(tx_hash)
                log.info("ChainReconciler: requeued checkpoint confirmed: tx=%s", tx_hash[:16])
        except Exception as exc:
            log.debug("ChainReconciler: requeue failed for tx=%s: %s", tx_hash[:16], exc)
