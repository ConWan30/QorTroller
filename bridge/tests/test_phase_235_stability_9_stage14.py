"""Phase 235.x-STABILITY-9 stage 14 (2026-05-18) — Sync get_logs path tests.

Closes the symmetric Stage 12 gap on event-filter get_logs reads:

  Stage 12: block_number routed through asyncio.to_thread(sync_w3.eth.block_number)
            via ChainReadGovernor._fetch_block_number sync_w3 path.
  Stage 14: get_logs routed through asyncio.to_thread(sync_get_logs)
            via ChainReadGovernor.run_read sync_fn parameter.

Stage 13 observation surfaced 15.86s peak STARVATION clustering at the
10s governor wait_for timeout + ~5.86s socket-cancellation residual =
exact Windows ProactorEventLoop signature.
ChainReconciler.get_phg_checkpoint_events was the surviving async path.
Stage 14 closes it.

Same shape as Stage 12 fix. Surgical:
  - chain.py: add get_phg_checkpoint_events_sync (uses self._sync_w3)
  - chain_read_governor.py: extend run_read with sync_fn parameter
  - chain_reconciler.py: pass sync_fn when chain has _sync_w3
"""
from __future__ import annotations

import asyncio
import time
from pathlib import Path
from types import SimpleNamespace

import pytest


_BRIDGE_DIR = Path(__file__).resolve().parents[1] / "vapi_bridge"


# ─── Source-pattern presence tests ─────────────────────────────────────────


def test_t_235_stab9_14_1_chain_has_sync_get_logs_method() -> None:
    """chain.py exposes get_phg_checkpoint_events_sync method."""
    src = (_BRIDGE_DIR / "chain.py").read_text(encoding="utf-8")
    assert "def get_phg_checkpoint_events_sync(" in src
    assert "self._sync_w3.eth.contract(" in src
    assert "event_filter.get_logs(" in src
    assert "stage 14" in src


def test_t_235_stab9_14_2_governor_accepts_sync_fn_param() -> None:
    """ChainReadGovernor.run_read accepts sync_fn kwarg."""
    src = (_BRIDGE_DIR / "chain_read_governor.py").read_text(encoding="utf-8")
    assert "sync_fn: Optional[Callable[[], T]] = None" in src
    assert "if sync_fn is not None:" in src
    assert "asyncio.to_thread(sync_fn)" in src
    assert "STAGE-14" in src


def test_t_235_stab9_14_3_reconciler_passes_sync_fn() -> None:
    """ChainReconciler passes sync_fn when chain has _sync_w3."""
    src = (_BRIDGE_DIR / "chain_reconciler.py").read_text(encoding="utf-8")
    assert "get_phg_checkpoint_events_sync" in src
    assert "sync_fn=_sync_fn" in src
    assert "stage 14" in src


# ─── Behavioral tests ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_t_235_stab9_14_4_run_read_with_sync_fn_offloads_to_thread() -> None:
    """run_read(sync_fn=...) routes through asyncio.to_thread — a 500ms
    blocking sync_fn does NOT block the event loop heartbeat."""
    from bridge.vapi_bridge.chain_read_governor import ChainReadGovernor

    def slow_sync_get_logs():
        time.sleep(0.5)
        return [{"transactionHash": "0xabc"}]

    async def unused_async_fn():
        return []

    cfg = SimpleNamespace(
        chain_read_block_cache_ttl_s=5.0,
        chain_read_max_concurrent=4,
        chain_read_timeout_s=10.0,
    )
    governor = ChainReadGovernor(w3=None, cfg=cfg)

    tick_completed_at: list[float] = []

    async def event_loop_tick():
        await asyncio.sleep(0.05)
        tick_completed_at.append(time.monotonic())

    t0 = time.monotonic()
    result, _ = await asyncio.gather(
        governor.run_read(
            unused_async_fn,
            label="test_get_logs",
            fallback=[],
            sync_fn=slow_sync_get_logs,
        ),
        event_loop_tick(),
    )
    tick_elapsed = tick_completed_at[0] - t0

    assert result == [{"transactionHash": "0xabc"}]
    assert tick_elapsed < 0.30, (
        f"Event loop blocked: tick {tick_elapsed:.3f}s (expected <0.30s "
        f"with sync_fn offloaded to worker thread)"
    )


@pytest.mark.asyncio
async def test_t_235_stab9_14_5_run_read_without_sync_fn_uses_async_path() -> None:
    """When sync_fn is None, original Stage 9 async path is used (preserves
    backward compat)."""
    from bridge.vapi_bridge.chain_read_governor import ChainReadGovernor

    async_called = {"n": 0}

    async def async_coro():
        async_called["n"] += 1
        return [{"event": "async_path"}]

    cfg = SimpleNamespace(
        chain_read_block_cache_ttl_s=5.0,
        chain_read_max_concurrent=4,
        chain_read_timeout_s=10.0,
    )
    governor = ChainReadGovernor(w3=None, cfg=cfg)
    result = await governor.run_read(async_coro, label="test_async", fallback=[])
    assert result == [{"event": "async_path"}]
    assert async_called["n"] == 1


@pytest.mark.asyncio
async def test_t_235_stab9_14_6_sync_fn_error_returns_fallback() -> None:
    """When sync_fn raises, governor returns fallback (fail-open)."""
    from bridge.vapi_bridge.chain_read_governor import ChainReadGovernor

    def raising_sync_fn():
        raise RuntimeError("synthetic IoTeX RPC error")

    async def unused_async_fn():
        return [{"unused": True}]

    cfg = SimpleNamespace(
        chain_read_block_cache_ttl_s=5.0,
        chain_read_max_concurrent=4,
        chain_read_timeout_s=10.0,
    )
    governor = ChainReadGovernor(w3=None, cfg=cfg)
    result = await governor.run_read(
        unused_async_fn,
        label="test_error",
        fallback=[{"fallback": True}],
        sync_fn=raising_sync_fn,
    )
    assert result == [{"fallback": True}]


# ─── Regression guards ─────────────────────────────────────────────────────


def test_t_235_stab9_14_7_stage12_block_number_sync_preserved() -> None:
    """Stage 12 sync_w3 block_number routing MUST remain."""
    src = (_BRIDGE_DIR / "chain_read_governor.py").read_text(encoding="utf-8")
    assert "if self._sync_w3 is not None:" in src
    assert "self._sync_w3.eth.block_number" in src


def test_t_235_stab9_14_8_stage13_proactive_monitor_to_thread_preserved() -> None:
    """Stage 13 ProactiveMonitor surveillance to_thread wraps MUST remain."""
    src = (_BRIDGE_DIR / "proactive_monitor.py").read_text(encoding="utf-8")
    assert "asyncio.to_thread(\n                self._network_detector.detect_clusters" in src
    assert "asyncio.to_thread(self._store.get_leaderboard, 100)" in src


def test_t_235_stab9_14_9_async_path_unchanged_in_governor() -> None:
    """The original Stage 9 wait_for + TimeoutError path remains intact
    (just becomes the else branch when sync_fn is None)."""
    src = (_BRIDGE_DIR / "chain_read_governor.py").read_text(encoding="utf-8")
    assert "await asyncio.wait_for(coro_fn(), timeout=eff_timeout)" in src
    assert "except asyncio.TimeoutError:" in src
    assert "STAGE-9 %s TIMEOUT" in src


def test_t_235_stab9_14_10_sync_method_returns_empty_when_no_sync_w3() -> None:
    """get_phg_checkpoint_events_sync returns [] when self._sync_w3 is None
    (fail-open + caller falls back to async path)."""
    # Verify in source — actual chain init test is heavyweight
    src = (_BRIDGE_DIR / "chain.py").read_text(encoding="utf-8")
    assert "if self._sync_w3 is None:" in src
    # The early-return for sync_w3 absence should appear in the sync method
    sync_method_block = src[src.index("def get_phg_checkpoint_events_sync"):]
    sync_method_block = sync_method_block[:sync_method_block.index("def ", 100)]
    assert "return []" in sync_method_block
    assert "sync_w3 unavailable" in sync_method_block
