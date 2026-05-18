"""Phase 235.x-STABILITY-9 stage 12 (2026-05-17) — Sync-Web3 chain-read
offload tests.

Validates the structural fix that closes the Windows ProactorEventLoop
cancellation gap empirically observed at Stage 11 (governor wait_for
cancelled at 10s but outer wrap measured 22.48s — 12s of uncancellable
socket read continued blocking the event loop after asyncio cancellation).

Stage 12 introduces a sync Web3 companion on ChainClient and routes
ChainReadGovernor.get_block_number through asyncio.to_thread when the
sync companion is available. The blocking socket lives on a worker
thread where it cannot block the event loop heartbeat regardless of
how badly the IoTeX RPC stalls.
"""
from __future__ import annotations

import asyncio
import time
from pathlib import Path
from types import SimpleNamespace

import pytest


_BRIDGE_DIR = Path(__file__).resolve().parents[1] / "vapi_bridge"


# ─── Source-pattern presence tests ─────────────────────────────────────────


def test_t_235_stab9_12_1_chain_client_sync_companion_present() -> None:
    """ChainClient.__init__ creates a sync Web3 companion (self._sync_w3)."""
    src = (_BRIDGE_DIR / "chain.py").read_text(encoding="utf-8")
    assert "self._sync_w3 = Web3(_SyncHTTPProvider(cfg.iotex_rpc_url))" in src, (
        "ChainClient must construct a sync Web3 companion alongside the "
        "async client (Stage 12 closure of Windows ProactorEventLoop "
        "cancellation gap)"
    )
    # Fail-open path
    assert "self._sync_w3 = None" in src
    assert "stage 12" in src


def test_t_235_stab9_12_2_governor_accepts_sync_w3() -> None:
    """ChainReadGovernor.__init__ accepts sync_w3 kwarg."""
    src = (_BRIDGE_DIR / "chain_read_governor.py").read_text(encoding="utf-8")
    assert "sync_w3: Any = None" in src
    assert "self._sync_w3 = sync_w3" in src
    assert "stage 12" in src


def test_t_235_stab9_12_3_fetch_routes_through_to_thread() -> None:
    """_fetch_block_number uses asyncio.to_thread when sync_w3 is present."""
    src = (_BRIDGE_DIR / "chain_read_governor.py").read_text(encoding="utf-8")
    assert "if self._sync_w3 is not None:" in src
    assert "asyncio.to_thread" in src
    assert "self._sync_w3.eth.block_number" in src


def test_t_235_stab9_12_4_reconciler_passes_sync_w3_to_governor() -> None:
    """ChainReconciler._get_governor passes self._chain._sync_w3."""
    src = (_BRIDGE_DIR / "chain_reconciler.py").read_text(encoding="utf-8")
    assert 'getattr(self._chain, "_sync_w3", None)' in src
    assert "sync_w3=_sync_w3" in src
    assert "stage 12" in src


# ─── Behavioral tests ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_t_235_stab9_12_5_sync_path_offloads_blocking_read(tmp_path) -> None:
    """When sync_w3 is injected, _fetch_block_number runs on a worker
    thread — a 500ms blocking sync read does NOT block the event loop.
    A concurrent 50ms tick still completes well before the blocking
    read finishes.
    """
    from bridge.vapi_bridge.chain_read_governor import ChainReadGovernor

    class _SyncEth:
        @property
        def block_number(self):
            # Simulate Windows-style uncancellable socket stall
            time.sleep(0.5)
            return 12345

    class _SyncW3:
        eth = _SyncEth()

    cfg = SimpleNamespace(
        chain_read_block_cache_ttl_s=5.0,
        chain_read_max_concurrent=4,
        chain_read_timeout_s=10.0,
    )
    governor = ChainReadGovernor(w3=None, cfg=cfg, sync_w3=_SyncW3())

    tick_completed_at: list[float] = []

    async def event_loop_tick():
        await asyncio.sleep(0.05)
        tick_completed_at.append(time.monotonic())

    t0 = time.monotonic()
    block, _ = await asyncio.gather(
        governor.get_block_number(),
        event_loop_tick(),
    )
    block_completed_at = time.monotonic() - t0
    tick_elapsed = tick_completed_at[0] - t0

    assert block == 12345, f"Expected 12345 from sync_w3, got {block}"
    assert tick_elapsed < 0.30, (
        f"Event loop was blocked: tick took {tick_elapsed:.3f}s "
        f"(expected <0.30s if to_thread is offloading the sync read)"
    )
    assert block_completed_at >= 0.45, (
        f"Block fetch returned in {block_completed_at:.3f}s — expected "
        f">=0.45s because sync_w3.eth.block_number sleeps 500ms"
    )


@pytest.mark.asyncio
async def test_t_235_stab9_12_6_async_path_preserved_when_no_sync_w3() -> None:
    """When sync_w3 is None, the original AsyncWeb3 path is used
    (pre-stage-12 behavior preserved for tests + non-Windows deployments)."""
    from bridge.vapi_bridge.chain_read_governor import ChainReadGovernor

    fetch_calls = {"async_path": 0, "sync_path": 0}

    class _AsyncEth:
        @property
        def block_number(self):
            # AsyncWeb3 awaitable property — return an awaitable
            async def _fetch():
                fetch_calls["async_path"] += 1
                return 99999
            return _fetch()

    class _AsyncW3:
        eth = _AsyncEth()

    cfg = SimpleNamespace(
        chain_read_block_cache_ttl_s=5.0,
        chain_read_max_concurrent=4,
        chain_read_timeout_s=10.0,
    )
    # No sync_w3 — old async path must be used
    governor = ChainReadGovernor(w3=_AsyncW3(), cfg=cfg)
    block = await governor.get_block_number()
    assert block == 99999
    assert fetch_calls["async_path"] == 1
    assert fetch_calls["sync_path"] == 0


@pytest.mark.asyncio
async def test_t_235_stab9_12_7_sync_path_timeout_governance_still_works(tmp_path) -> None:
    """When sync_w3 blocks longer than timeout_s, the governor's
    asyncio.wait_for STILL fires the TIMEOUT path — but the underlying
    sync work continues on the worker thread (won't block the event loop).
    Caller gets the stale value.
    """
    from bridge.vapi_bridge.chain_read_governor import ChainReadGovernor

    class _SyncEth:
        @property
        def block_number(self):
            time.sleep(2.0)  # Blocks longer than timeout
            return 55555

    class _SyncW3:
        eth = _SyncEth()

    cfg = SimpleNamespace(
        chain_read_block_cache_ttl_s=5.0,
        chain_read_max_concurrent=4,
        chain_read_timeout_s=0.3,  # Tight timeout for fast test
    )
    governor = ChainReadGovernor(w3=None, cfg=cfg, sync_w3=_SyncW3())

    t0 = time.monotonic()
    result = await governor.get_block_number()
    elapsed = time.monotonic() - t0

    # Timeout should fire; stale value (0) returned since cache empty
    assert result == 0, f"Expected stale 0 from timeout, got {result}"
    # Async-side returns near the timeout (worker thread keeps running)
    assert elapsed < 1.0, f"Governor should return at timeout (~0.3s), got {elapsed:.3f}s"
    # Governor stats: timeout was recorded
    stats = governor.get_stats()
    assert stats["read_timeouts"] >= 1


# ─── Integration test — ChainReconciler wires sync_w3 through ─────────────


def test_t_235_stab9_12_8_reconciler_wires_sync_w3_through_governor() -> None:
    """ChainReconciler lazy-init governor pulls sync_w3 from chain client."""
    from bridge.vapi_bridge.chain_reconciler import ChainReconciler

    class _FakeAsyncW3: pass
    class _FakeSyncW3: pass

    class _FakeChain:
        _w3 = _FakeAsyncW3()
        _sync_w3 = _FakeSyncW3()

    cfg = SimpleNamespace(
        chain_read_block_cache_ttl_s=5.0,
        chain_read_max_concurrent=4,
        chain_read_timeout_s=10.0,
    )
    reconciler = ChainReconciler(
        store=None, chain=_FakeChain(), poll_interval=30.0, cfg=cfg,
    )
    governor = reconciler._get_governor()
    assert governor is not None
    assert governor._sync_w3 is _FakeChain._sync_w3, (
        "Governor should receive the sync_w3 companion from chain client"
    )
    assert governor._w3 is _FakeChain._w3


def test_t_235_stab9_12_9_reconciler_handles_missing_sync_w3() -> None:
    """When chain client lacks _sync_w3 (e.g. test stub), governor still
    works — falls back to async path internally."""
    from bridge.vapi_bridge.chain_reconciler import ChainReconciler

    class _FakeAsyncW3: pass

    class _FakeChain:
        _w3 = _FakeAsyncW3()
        # No _sync_w3 attr

    cfg = SimpleNamespace(
        chain_read_block_cache_ttl_s=5.0,
        chain_read_max_concurrent=4,
        chain_read_timeout_s=10.0,
    )
    reconciler = ChainReconciler(
        store=None, chain=_FakeChain(), poll_interval=30.0, cfg=cfg,
    )
    governor = reconciler._get_governor()
    assert governor is not None
    assert governor._sync_w3 is None
    assert governor._w3 is _FakeChain._w3


# ─── Regression guard ─────────────────────────────────────────────────────


def test_t_235_stab9_12_10_stage9_governor_existing_behavior_preserved() -> None:
    """Stage 9 governor cfg field names + defaults preserved."""
    from bridge.vapi_bridge.chain_read_governor import ChainReadGovernor
    cfg = SimpleNamespace(
        chain_read_block_cache_ttl_s=5.0,
        chain_read_max_concurrent=4,
        chain_read_timeout_s=10.0,
    )
    g = ChainReadGovernor(w3=None, cfg=cfg)
    stats = g.get_stats()
    assert stats["block_cache_ttl_s"] == 5.0
    assert stats["max_concurrent"] == 4
    assert stats["timeout_s"] == 10.0
    assert stats["block_cache_hits"] == 0
    assert stats["read_timeouts"] == 0
