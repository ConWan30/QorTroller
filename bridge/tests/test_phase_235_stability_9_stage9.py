"""Phase 235.x-STABILITY-9 stage 9 (2026-05-17) — Shared chain-read
governor tests.

Validates TTL block_number cache + concurrency semaphore + per-call
timeout + fail-open behavior. Also verifies ChainReconciler now routes
read-side RPC through the governor + write methods are NOT touched.
"""
import asyncio
import logging
import os
import time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, AsyncMock

import pytest

from bridge.vapi_bridge.chain_read_governor import ChainReadGovernor


_BRIDGE_DIR = Path(__file__).resolve().parents[1] / "vapi_bridge"


def _stub_cfg(**overrides):
    base = {
        "chain_read_block_cache_ttl_s": 5.0,
        "chain_read_max_concurrent": 4,
        "chain_read_timeout_s": 10.0,
    }
    base.update(overrides)
    return SimpleNamespace(**base)


class _AsyncBlockNumber:
    """AsyncWeb3.eth.block_number is an awaitable property — mimic that shape."""
    def __init__(self, value):
        self._value = value
    def __await__(self):
        async def _coro():
            return self._value
        return _coro().__await__()


def _stub_w3(block_number=42):
    w3 = MagicMock()
    w3.eth = MagicMock()
    w3.eth.block_number = _AsyncBlockNumber(block_number)
    return w3


# ─── Cfg tests ────────────────────────────────────────────────────────────

def test_t_235_stab9_9_1_cfg_defaults() -> None:
    """Stage 9 cfg fields ship with correct defaults."""
    for v in ["CHAIN_READ_BLOCK_CACHE_TTL_S", "CHAIN_READ_MAX_CONCURRENT", "CHAIN_READ_TIMEOUT_S"]:
        os.environ.pop(v, None)
    from bridge.vapi_bridge.config import Config
    cfg = Config()
    assert cfg.chain_read_block_cache_ttl_s == 5.0
    assert cfg.chain_read_max_concurrent == 4
    assert cfg.chain_read_timeout_s == 10.0


# ─── Block-number cache tests ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_t_235_stab9_9_2_block_number_cache_hit_within_ttl() -> None:
    """Second call within TTL returns cached value (no second fetch)."""
    cfg = _stub_cfg(chain_read_block_cache_ttl_s=10.0)
    w3 = _stub_w3(block_number=100)
    gov = ChainReadGovernor(w3=w3, cfg=cfg)
    fetch_count = {"n": 0}
    original = gov._fetch_block_number
    async def counting_fetch():
        fetch_count["n"] += 1
        return await original()
    gov._fetch_block_number = counting_fetch
    a = await gov.get_block_number()
    b = await gov.get_block_number()
    assert a == 100
    assert b == 100
    assert fetch_count["n"] == 1, "second call must hit cache"


@pytest.mark.asyncio
async def test_t_235_stab9_9_3_block_number_refresh_after_ttl() -> None:
    """After TTL expires, next call refreshes from chain."""
    cfg = _stub_cfg(chain_read_block_cache_ttl_s=0.05)  # 50ms TTL
    w3 = _stub_w3(block_number=200)
    gov = ChainReadGovernor(w3=w3, cfg=cfg)
    fetch_count = {"n": 0}
    original = gov._fetch_block_number
    async def counting_fetch():
        fetch_count["n"] += 1
        return await original()
    gov._fetch_block_number = counting_fetch
    await gov.get_block_number()
    await asyncio.sleep(0.10)  # exceed TTL
    await gov.get_block_number()
    assert fetch_count["n"] == 2, "second call after TTL must re-fetch"


@pytest.mark.asyncio
async def test_t_235_stab9_9_4_block_number_concurrent_callers_coalesce() -> None:
    """20 concurrent callers within TTL produce at most a few fetches
    (not 20). Cache + lock coalesces."""
    cfg = _stub_cfg(chain_read_block_cache_ttl_s=10.0)
    w3 = _stub_w3(block_number=300)
    gov = ChainReadGovernor(w3=w3, cfg=cfg)
    fetch_count = {"n": 0}
    original = gov._fetch_block_number
    async def counting_fetch():
        fetch_count["n"] += 1
        await asyncio.sleep(0.01)  # simulate latency to encourage races
        return await original()
    gov._fetch_block_number = counting_fetch
    results = await asyncio.gather(*[gov.get_block_number() for _ in range(20)])
    assert all(r == 300 for r in results)
    # With lock coalescing, expect 1 fetch for the cohort
    assert fetch_count["n"] <= 2, (
        f"Expected <=2 fetches for 20 concurrent callers (coalesced); "
        f"got {fetch_count['n']}"
    )


@pytest.mark.asyncio
async def test_t_235_stab9_9_5_block_number_timeout_fail_open() -> None:
    """If underlying fetch times out, return stale cached value (fail-open)."""
    cfg = _stub_cfg(chain_read_timeout_s=0.05)  # 50ms timeout
    w3 = _stub_w3(block_number=400)
    gov = ChainReadGovernor(w3=w3, cfg=cfg)
    # Prime cache with a real fetch
    primed = await gov.get_block_number()
    assert primed == 400
    # Now patch fetch to hang
    async def hanging_fetch():
        await asyncio.sleep(10)
        return 999
    gov._fetch_block_number = hanging_fetch
    # Force cache miss by waiting past TTL
    cfg2 = _stub_cfg(chain_read_block_cache_ttl_s=0.01, chain_read_timeout_s=0.05)
    gov._block_cache_ttl_s_default = 0.01
    await asyncio.sleep(0.02)
    # Should timeout + return cached 400
    result = await gov.get_block_number()
    assert result == 400, "fail-open must return stale cached value on timeout"


@pytest.mark.asyncio
async def test_t_235_stab9_9_6_block_number_error_fail_open() -> None:
    """If underlying fetch raises, return stale cached value (fail-open).
    Governor never raises out."""
    cfg = _stub_cfg()
    w3 = _stub_w3(block_number=500)
    gov = ChainReadGovernor(w3=w3, cfg=cfg)
    await gov.get_block_number()  # prime
    async def raising_fetch():
        raise RuntimeError("simulated RPC error")
    gov._fetch_block_number = raising_fetch
    # Force cache miss
    gov._block_cache_at = 0.0
    result = await gov.get_block_number()
    assert result == 500, "fail-open must return cached value on chain error"


# ─── run_read (generic governed read) tests ───────────────────────────────

@pytest.mark.asyncio
async def test_t_235_stab9_9_7_run_read_returns_value() -> None:
    """run_read returns the coroutine result on success."""
    cfg = _stub_cfg()
    gov = ChainReadGovernor(w3=_stub_w3(), cfg=cfg)
    result = await gov.run_read(
        lambda: asyncio.sleep(0, result=[{"event": "x"}]),
        label="test_read",
    )
    assert result == [{"event": "x"}]


@pytest.mark.asyncio
async def test_t_235_stab9_9_8_run_read_timeout_returns_fallback() -> None:
    """run_read returns `fallback` on timeout (never raises)."""
    cfg = _stub_cfg(chain_read_timeout_s=0.05)
    gov = ChainReadGovernor(w3=_stub_w3(), cfg=cfg)
    async def slow():
        await asyncio.sleep(10)
        return "should-not-arrive"
    result = await gov.run_read(slow, label="slow_read", fallback=[])
    assert result == []


@pytest.mark.asyncio
async def test_t_235_stab9_9_9_run_read_error_returns_fallback() -> None:
    """run_read returns `fallback` on inner exception (never raises)."""
    cfg = _stub_cfg()
    gov = ChainReadGovernor(w3=_stub_w3(), cfg=cfg)
    async def boom():
        raise RuntimeError("simulated")
    result = await gov.run_read(boom, label="boom_read", fallback="fb")
    assert result == "fb"


# ─── Concurrency semaphore test ───────────────────────────────────────────

@pytest.mark.asyncio
async def test_t_235_stab9_9_10_semaphore_bounds_concurrent_reads() -> None:
    """N concurrent run_read calls cannot exceed max_concurrent active."""
    cfg = _stub_cfg(chain_read_max_concurrent=2)
    gov = ChainReadGovernor(w3=_stub_w3(), cfg=cfg)
    active = {"current": 0, "peak": 0}
    async def tracker():
        active["current"] += 1
        active["peak"] = max(active["peak"], active["current"])
        await asyncio.sleep(0.05)
        active["current"] -= 1
        return "ok"
    results = await asyncio.gather(*[
        gov.run_read(tracker, label=f"r{i}") for i in range(10)
    ])
    assert all(r == "ok" for r in results)
    assert active["peak"] <= 2, (
        f"max_concurrent=2 must bound active reads; observed peak={active['peak']}"
    )


# ─── ChainReconciler wiring tests ─────────────────────────────────────────

@pytest.mark.asyncio
async def test_t_235_stab9_9_11_chain_reconciler_uses_governor() -> None:
    """ChainReconciler.run() routes block_number init through governor."""
    from bridge.vapi_bridge.chain_reconciler import ChainReconciler
    store = MagicMock()
    chain = MagicMock()
    chain._w3 = _stub_w3(block_number=42)
    chain.get_phg_checkpoint_events = AsyncMock(return_value=[])
    cfg = _stub_cfg()
    gov = ChainReadGovernor(w3=chain._w3, cfg=cfg)
    rec = ChainReconciler(store, chain, cfg=cfg, governor=gov)
    # First _reconcile_cycle: should route through governor for block_number
    rec._last_block = 30
    chain._w3.eth.block_number = _AsyncBlockNumber(50)  # block 50, advance
    await rec._reconcile_cycle()
    # After call, governor's block cache should hold 50
    assert gov._block_cache_value == 50


@pytest.mark.asyncio
async def test_t_235_stab9_9_12_chain_reconciler_falls_back_when_no_governor() -> None:
    """Pre-stage-9 callers (no cfg, no governor) still work — fallback path."""
    from bridge.vapi_bridge.chain_reconciler import ChainReconciler
    store = MagicMock()
    chain = MagicMock()
    chain._w3 = _stub_w3(block_number=99)
    chain.get_phg_checkpoint_events = AsyncMock(return_value=[])
    # No cfg, no governor — must not crash
    rec = ChainReconciler(store, chain)
    rec._last_block = 50
    await rec._reconcile_cycle()
    # Existing AbsorbedAgentTicker calls ChainReconciler with no cfg —
    # this construction path must still work.


# ─── Write-path safety tests ──────────────────────────────────────────────

def test_t_235_stab9_9_13_governor_has_no_write_routes() -> None:
    """ChainReadGovernor MUST NOT expose any write methods; verify
    governor surface is read-only."""
    src = (_BRIDGE_DIR / "chain_read_governor.py").read_text(encoding="utf-8")
    # Negative assertions: no write-side primitives
    for forbidden in ["_send_tx", "verify_poac", "anchor_", "submit_", "mint_",
                      "transfer", "send_raw_transaction"]:
        assert forbidden not in src, (
            f"Read governor must not reference write primitive: {forbidden}"
        )
    # Positive assertions: read-only ops only
    assert "get_block_number" in src
    assert "run_read" in src


def test_t_235_stab9_9_14_chain_submission_paused_untouched() -> None:
    """Stage 9 does NOT modify chain.py — CHAIN_SUBMISSION_PAUSED
    invariant preserved per FROZEN-region adjacency."""
    src = (_BRIDGE_DIR / "chain.py").read_text(encoding="utf-8")
    assert "STAGE-9" not in src, (
        "Stage 9 must NOT modify chain.py — kill-switch + write surface "
        "is FROZEN-region adjacent."
    )


def test_t_235_stab9_9_15_pia_deferred_no_modification() -> None:
    """PIA audit (Stage 9 directive) confirmed PIA has no chain reads;
    file must remain untouched."""
    src = (_BRIDGE_DIR / "protocol_intelligence_agent.py").read_text(encoding="utf-8")
    assert "STAGE-9" not in src, (
        "Stage 9 must NOT modify PIA — audit found zero chain reads in "
        "compute_report (line 132 _chain is a local dict, not chain RPC). "
        "PIA's 5-11s SLOW COMPUTE is worker/WAL contention, not "
        "chain-RPC related."
    )


def test_t_235_stab9_9_16_governor_stats_shape() -> None:
    """get_stats returns observable dict for /operator/* endpoints."""
    cfg = _stub_cfg()
    gov = ChainReadGovernor(w3=_stub_w3(), cfg=cfg)
    stats = gov.get_stats()
    for key in ["block_cache_hits", "block_cache_misses",
                "block_cache_fail_open_returns", "read_timeouts",
                "reads_total", "block_cache_value", "block_cache_ttl_s",
                "max_concurrent", "timeout_s"]:
        assert key in stats, f"missing stats key: {key}"
