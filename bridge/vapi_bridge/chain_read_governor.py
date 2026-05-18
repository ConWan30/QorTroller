"""Phase 235.x-STABILITY-9 stage 9 (2026-05-17) — Shared chain-read governor.

Stage 8 observation cleared SQLite as the dominant blocker (0 SLOW SQLITE
markers). Remaining starvation source: chain-RPC pressure across the boot
cohort (15 STAGE-8 SLOW CHAIN markers; chain_block_number takes 5-8s,
get_logs takes 5-17s). Multiple agents calling AsyncWeb3 read methods
concurrently during the boot cohort can saturate the httpx connection
pool + delay the asyncio scheduler.

This module ships a tiny shared governor that:

  1. TTL-CACHES the latest block_number (default 5s) — multiple agents
     within a single 5s window share one fetch. ChainReconciler calls
     this every 30s; if added agents start sharing it, cache amortizes.

  2. BOUNDS concurrent read RPCs via asyncio.Semaphore (default 4)
     so the cohort cannot flood the underlying httpx pool.

  3. ENFORCES a per-call TIMEOUT (default 10s) so a single slow RPC
     cannot block its caller indefinitely. Fail-open returns the cached
     value (or 0 if no cache yet); never raises out.

  4. Instruments cache hit/miss + slow RPC with STAGE-9 markers for
     grep-based observation.

Design discipline:
  - Stdlib + asyncio only (no new deps).
  - Lazy-init asyncio primitives (Semaphore/Lock) on first call so
     the module can be imported before an event loop exists.
  - Does NOT cache writes (this is read-only governance).
  - Does NOT cache anything beyond the short configurable TTL —
     finality / liveness semantics preserved for security-sensitive
     callers (ChainReconciler tolerates 5-10s stale block_number
     because its 30s poll cycle means cache is always fresh enough).
  - get_logs is NOT cached (range-specific, not safely cacheable).
     Instead it routes through the semaphore + timeout only.
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Awaitable, Callable, Optional, TypeVar

log = logging.getLogger(__name__)

T = TypeVar("T")


class ChainReadGovernor:
    """Shared governor for read-side AsyncWeb3 RPCs.

    Construct one per bridge process. Pass the AsyncWeb3 instance.
    Callers use `await governor.get_block_number()` and
    `await governor.run_read(coro_fn, label="...")` for arbitrary reads.

    All methods are async + fail-open: timeouts/errors return cached
    or zero values; never raise out.
    """

    def __init__(
        self,
        *,
        w3: Any,
        cfg: Any,
        sync_w3: Any = None,
    ) -> None:
        self._w3 = w3
        self._cfg = cfg
        # Phase 235.x-STABILITY-9 stage 12 2026-05-17: optional sync Web3
        # companion. When set, get_block_number routes through
        # asyncio.to_thread(sync_w3.eth.block_number) so the blocking socket
        # read lives on a worker thread instead of the event loop. This
        # closes the Windows ProactorEventLoop cancellation gap empirically
        # observed at Stage 11 (governor wait_for fires at 10s but outer
        # measurement shows 22s — 12s of uncancellable socket read on the
        # event loop after asyncio cancellation). Optional: when None, the
        # original AsyncWeb3 path is used (pre-stage-12 behavior preserved
        # for tests + non-Windows deployments).
        self._sync_w3 = sync_w3
        # Read once + cache (read on every call; allow operator
        # to retune without restart if they later want).
        self._block_cache_ttl_s_default = float(getattr(
            cfg, "chain_read_block_cache_ttl_s", 5.0
        ))
        self._max_concurrent_default = int(getattr(
            cfg, "chain_read_max_concurrent", 4
        ))
        self._timeout_s_default = float(getattr(
            cfg, "chain_read_timeout_s", 10.0
        ))
        # State (lazy-init for async primitives)
        self._block_cache_value: int = 0
        self._block_cache_at: float = 0.0
        self._semaphore: Optional[asyncio.Semaphore] = None
        self._block_cache_lock: Optional[asyncio.Lock] = None
        # Observability counters
        self._block_cache_hits: int = 0
        self._block_cache_misses: int = 0
        self._block_cache_fail_open_returns: int = 0
        self._read_timeouts: int = 0
        self._reads_total: int = 0
        log.info(
            "[ChainReadGovernor] STAGE-9 initialized "
            "(block_cache_ttl=%.1fs, max_concurrent=%d, timeout=%.1fs)",
            self._block_cache_ttl_s_default,
            self._max_concurrent_default,
            self._timeout_s_default,
        )

    def _ensure_async_primitives(self) -> None:
        """Lazy-init Semaphore + Lock once an event loop exists."""
        if self._semaphore is None:
            self._semaphore = asyncio.Semaphore(self._max_concurrent_default)
        if self._block_cache_lock is None:
            self._block_cache_lock = asyncio.Lock()

    async def get_block_number(self) -> int:
        """Return latest block_number with TTL cache + semaphore + timeout.

        Cache TTL window means up to `1/ttl` chain-RPC calls per agent per
        second instead of unbounded. Multiple concurrent agents in the
        same TTL window share one fetched value.

        Returns 0 only if no successful fetch has ever occurred AND the
        current fetch fails. Otherwise returns the most-recent successful
        value (stale-but-safe).
        """
        self._ensure_async_primitives()
        self._reads_total += 1
        now = time.monotonic()

        # Fast path: cache hit (no lock needed for read-only check;
        # racy but the worst case is one extra fetch).
        if (
            self._block_cache_value > 0
            and (now - self._block_cache_at) < self._block_cache_ttl_s_default
        ):
            self._block_cache_hits += 1
            log.debug(
                "[ChainReadGovernor] STAGE-9 block_number CACHE HIT "
                "(age=%.3fs, value=%d)",
                now - self._block_cache_at, self._block_cache_value,
            )
            return self._block_cache_value

        # Cache miss — coalesce concurrent waiters via lock.
        async with self._block_cache_lock:
            # Re-check inside lock: another coroutine may have refreshed
            # while we awaited.
            now = time.monotonic()
            if (
                self._block_cache_value > 0
                and (now - self._block_cache_at) < self._block_cache_ttl_s_default
            ):
                self._block_cache_hits += 1
                return self._block_cache_value

            self._block_cache_misses += 1
            # Fetch under semaphore + timeout
            try:
                async with self._semaphore:
                    value = await asyncio.wait_for(
                        self._fetch_block_number(),
                        timeout=self._timeout_s_default,
                    )
                self._block_cache_value = int(value)
                self._block_cache_at = time.monotonic()
                log.debug(
                    "[ChainReadGovernor] STAGE-9 block_number REFRESH "
                    "(new_value=%d, prev_value=%d)",
                    self._block_cache_value, self._block_cache_value,
                )
                return self._block_cache_value
            except asyncio.TimeoutError:
                self._read_timeouts += 1
                self._block_cache_fail_open_returns += 1
                log.warning(
                    "[ChainReadGovernor] STAGE-9 block_number TIMEOUT "
                    "(after %.1fs; returning stale value=%d)",
                    self._timeout_s_default, self._block_cache_value,
                )
                return self._block_cache_value
            except Exception as exc:  # noqa: BLE001 — fail-open
                self._block_cache_fail_open_returns += 1
                log.warning(
                    "[ChainReadGovernor] STAGE-9 block_number ERROR "
                    "(%s; returning stale value=%d)",
                    exc, self._block_cache_value,
                )
                return self._block_cache_value

    async def _fetch_block_number(self) -> int:
        """Inner uncached fetch — separated for testability + monkey-patching.

        Phase 235.x-STABILITY-9 stage 12 2026-05-17: when sync_w3 is
        injected, route through asyncio.to_thread so the blocking socket
        read lives on a worker thread (Windows ProactorEventLoop cancellation
        gap closure). Otherwise fall back to the AsyncWeb3 awaitable
        (pre-stage-12 behavior).
        """
        if self._sync_w3 is not None:
            # Worker-thread blocking read; event loop heartbeat unaffected
            # even if IoTeX RPC stalls for the full OS socket timeout.
            return await asyncio.to_thread(
                lambda: int(self._sync_w3.eth.block_number)
            )
        # AsyncWeb3.eth.block_number is awaitable property
        return await self._w3.eth.block_number

    async def run_read(
        self,
        coro_fn: Callable[[], Awaitable[T]],
        *,
        label: str,
        timeout_s: Optional[float] = None,
        fallback: Optional[T] = None,
        sync_fn: Optional[Callable[[], T]] = None,
    ) -> T:
        """Run an arbitrary read coroutine under governor (semaphore + timeout).

        Use for non-cached reads like get_logs that need concurrency
        bounds but not TTL caching.

        Args:
          coro_fn:   nullary callable returning the read coroutine
                     (e.g. `lambda: chain.get_phg_checkpoint_events(a, b)`)
          label:     site name for STAGE-9 timing logs
          timeout_s: per-call timeout (default cfg.chain_read_timeout_s)
          fallback:  returned on timeout/error (default None)
          sync_fn:   Phase 235.x-STABILITY-9 stage 14 2026-05-18 — optional
                     sync callable that performs the same read via
                     blocking I/O. When provided, governor routes through
                     `asyncio.to_thread(sync_fn)` instead of
                     `asyncio.wait_for(coro_fn())`. Same pattern as Stage
                     12 `_fetch_block_number` sync_w3 offload. Use this
                     for AsyncWeb3 event-filter get_logs reads on Windows
                     ProactorEventLoop where async cancellation does not
                     propagate to the underlying socket. Stage 13
                     observation showed 15.86s peak STARVATION clustering
                     at the 10s governor timeout + ~5.86s socket-stall
                     residual — exact signature of the ProactorEventLoop
                     cancellation gap.

        Returns the coroutine's result OR `fallback` on timeout/error.
        Never raises out.
        """
        self._ensure_async_primitives()
        self._reads_total += 1
        eff_timeout = timeout_s if timeout_s is not None else self._timeout_s_default
        # Stage 14 path — sync_fn via to_thread, no async cancellation gap
        if sync_fn is not None:
            try:
                async with self._semaphore:
                    return await asyncio.to_thread(sync_fn)
            except Exception as exc:  # noqa: BLE001 — fail-open
                log.warning(
                    "[ChainReadGovernor] STAGE-14 %s sync_fn ERROR (%s; "
                    "returning fallback)",
                    label, exc,
                )
                return fallback  # type: ignore[return-value]
        # Original Stage 9 async path with wait_for
        try:
            async with self._semaphore:
                return await asyncio.wait_for(coro_fn(), timeout=eff_timeout)
        except asyncio.TimeoutError:
            self._read_timeouts += 1
            log.warning(
                "[ChainReadGovernor] STAGE-9 %s TIMEOUT (after %.1fs; "
                "returning fallback)",
                label, eff_timeout,
            )
            return fallback  # type: ignore[return-value]
        except Exception as exc:  # noqa: BLE001 — fail-open
            log.warning(
                "[ChainReadGovernor] STAGE-9 %s ERROR (%s; returning fallback)",
                label, exc,
            )
            return fallback  # type: ignore[return-value]

    def get_stats(self) -> dict:
        """Read-only snapshot for /operator/* endpoints."""
        return {
            "block_cache_hits":             self._block_cache_hits,
            "block_cache_misses":           self._block_cache_misses,
            "block_cache_fail_open_returns": self._block_cache_fail_open_returns,
            "read_timeouts":                self._read_timeouts,
            "reads_total":                  self._reads_total,
            "block_cache_value":            self._block_cache_value,
            "block_cache_age_s":            (
                time.monotonic() - self._block_cache_at
                if self._block_cache_at > 0 else None
            ),
            "block_cache_ttl_s":            self._block_cache_ttl_s_default,
            "max_concurrent":               self._max_concurrent_default,
            "timeout_s":                    self._timeout_s_default,
        }
