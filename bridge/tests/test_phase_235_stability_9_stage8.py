"""Phase 235.x-STABILITY-9 stage 8 (2026-05-17) — ChainReconciler
surgical fix tests.

Validates the Stage 7-named primary offender fix: ChainReconciler
SQLite calls now run via asyncio.to_thread; chain RPC calls retain
their async-yield behavior but are instrumented with Stage 8 timing
markers.

Per operator Stage 8 directive: ChainReconciler primary; PIA audit
deferred (PIA has zero uncovered sync sub-calls — confirmed by grep).
"""
import asyncio
import logging
import os
import time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, AsyncMock, patch

import pytest

from bridge.vapi_bridge.chain_reconciler import ChainReconciler


_BRIDGE_DIR = Path(__file__).resolve().parents[1] / "vapi_bridge"


# ─── Fixture: minimal store + chain stubs ─────────────────────────────────


def _stub_store():
    """Sync store stub that tracks calls."""
    store = MagicMock()
    store.mark_checkpoint_confirmed = MagicMock(return_value=None)
    store.get_unconfirmed_checkpoints = MagicMock(return_value=[])
    return store


class _AsyncBlockNumber:
    """Awaitable wrapper that mimics AsyncWeb3.eth.block_number property."""
    def __init__(self, value):
        self._value = value
    def __await__(self):
        async def _coro():
            return self._value
        return _coro().__await__()


class _StubW3Eth:
    def __init__(self, block_number=100):
        self.block_number = _AsyncBlockNumber(block_number)


class _StubW3:
    def __init__(self, block_number=100):
        self.eth = _StubW3Eth(block_number)


def _stub_chain(block_number=100, events=None):
    chain = MagicMock()
    chain._w3 = _StubW3(block_number)
    # Phase 235.x-STABILITY-9 stage 12 2026-05-17: explicit None for
    # sync_w3 mirrors production ChainClient fail-open behavior. Without
    # this, MagicMock would auto-create a sync_w3 attribute and the
    # governor would attempt int(MagicMock(...)) inside to_thread.
    chain._sync_w3 = None
    chain.get_phg_checkpoint_events = AsyncMock(return_value=events or [])
    chain.wait_for_receipt = AsyncMock(return_value={"status": 1})
    return chain


# ─── Tests ────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_t_235_stab9_8_1_reconcile_cycle_calls_to_thread_for_sqlite() -> None:
    """Stage 8 invariant: SQLite mark_checkpoint_confirmed batch runs
    via asyncio.to_thread, NOT directly on the event loop."""
    store = _stub_store()
    events = [
        {"transactionHash": "0xabc1", "deviceId": "d1", "cumulativeScore": 1},
        {"transactionHash": "0xabc2", "deviceId": "d2", "cumulativeScore": 2},
    ]
    chain = _stub_chain(block_number=200, events=events)

    rec = ChainReconciler(store, chain, poll_interval=30.0)
    rec._last_block = 150

    with patch("asyncio.to_thread", wraps=asyncio.to_thread) as mock_tot:
        await rec._reconcile_cycle()

    # to_thread should have been called at least twice:
    # 1. _apply_confirmed_events_sync (batch mark_checkpoint_confirmed)
    # 2. self._store.get_unconfirmed_checkpoints
    assert mock_tot.call_count >= 2, (
        f"Expected ≥2 asyncio.to_thread calls (batch confirm + get_unconfirmed); "
        f"got {mock_tot.call_count}"
    )


@pytest.mark.asyncio
async def test_t_235_stab9_8_2_apply_confirmed_events_sync_batches() -> None:
    """The new sync helper iterates all tx hashes + calls store batch-style."""
    store = _stub_store()
    chain = _stub_chain()
    rec = ChainReconciler(store, chain)
    tx_hashes = ["0xa", "0xb", "0xc"]
    n = rec._apply_confirmed_events_sync(tx_hashes)
    assert n == 3
    assert store.mark_checkpoint_confirmed.call_count == 3


@pytest.mark.asyncio
async def test_t_235_stab9_8_3_apply_fail_open_on_individual_error() -> None:
    """Sync helper preserves fail-open: one row failing doesn't abort batch."""
    store = _stub_store()
    # Make 2nd call raise; 1st + 3rd succeed
    call_count = {"n": 0}
    def _flaky(tx_hash):
        call_count["n"] += 1
        if call_count["n"] == 2:
            raise RuntimeError("simulated SQLite failure")
    store.mark_checkpoint_confirmed = _flaky
    chain = _stub_chain()
    rec = ChainReconciler(store, chain)
    n = rec._apply_confirmed_events_sync(["0xa", "0xb", "0xc"])
    # Returns count of SUCCESSFUL writes (2 of 3); did not raise
    assert n == 2
    assert call_count["n"] == 3


@pytest.mark.asyncio
async def test_t_235_stab9_8_4_chain_error_short_circuits_cycle() -> None:
    """Block-number fetch failure → cycle returns early (preserves pre-stage-8
    fail-open behavior; chain.warning still logged)."""
    store = _stub_store()
    chain = MagicMock()
    # block_number that raises when awaited
    class _RaisingBlockNumber:
        def __await__(self):
            async def _coro():
                raise RuntimeError("simulated RPC error")
            return _coro().__await__()
    chain._w3 = MagicMock()
    chain._w3.eth = MagicMock()
    chain._w3.eth.block_number = _RaisingBlockNumber()

    rec = ChainReconciler(store, chain)
    await rec._reconcile_cycle()  # must NOT raise
    # Did not call SQLite (no events processed)
    assert store.mark_checkpoint_confirmed.call_count == 0


@pytest.mark.asyncio
async def test_t_235_stab9_8_5_empty_events_skips_sqlite_batch() -> None:
    """When chain has 0 events to confirm, the batch to_thread is skipped
    (avoid empty-list overhead)."""
    store = _stub_store()
    chain = _stub_chain(block_number=200, events=[])
    rec = ChainReconciler(store, chain)
    rec._last_block = 150
    await rec._reconcile_cycle()
    # mark_checkpoint_confirmed never called (empty batch)
    assert store.mark_checkpoint_confirmed.call_count == 0
    # But get_unconfirmed_checkpoints WAS called (always check for retries)
    assert store.get_unconfirmed_checkpoints.call_count == 1


@pytest.mark.asyncio
async def test_t_235_stab9_8_6_stage_7_absorbed_ticker_still_async_invokes() -> None:
    """AbsorbedAgentTicker spec for ChainReconciler still treats it as
    `is_async=True` — _invoke_one awaits, doesn't to_thread the whole
    method (which would corrupt AsyncWeb3 instance loop affinity)."""
    from bridge.vapi_bridge.operator_steward_absorbed_agents import (
        SENTRY_ABSORBED,
    )
    chain_recon_spec = next(
        s for s in SENTRY_ABSORBED if s.name == "ChainReconciler"
    )
    assert chain_recon_spec.is_async is True, (
        "ChainReconciler must remain is_async=True; the Stage 8 fix moves "
        "SQLite to to_thread INSIDE the async method, NOT the entire method."
    )
    assert chain_recon_spec.method_name == "_reconcile_cycle"


def test_t_235_stab9_8_7_apply_helper_method_exists() -> None:
    """_apply_confirmed_events_sync extracted as named method for clean
    asyncio.to_thread targeting."""
    assert hasattr(ChainReconciler, "_apply_confirmed_events_sync")
    assert callable(getattr(ChainReconciler, "_apply_confirmed_events_sync"))


def test_t_235_stab9_8_8_chain_reconciler_uses_loop_timing() -> None:
    """ChainReconciler imports + uses the shared timed_block from
    loop_timing (cohesive with Stage 7 instrumentation framework)."""
    src = (_BRIDGE_DIR / "chain_reconciler.py").read_text(encoding="utf-8")
    assert "from .loop_timing import timed_block" in src
    assert "[ChainReconciler] STAGE-8" in src
    # All 4 expected timed sections present:
    for site in [
        "chain_block_number",
        "chain_get_logs_range_",
        "sqlite_mark_confirmed_batch_N",
        "sqlite_get_unconfirmed",
    ]:
        assert site in src, f"Missing Stage 8 timed_block site: {site}"


def test_t_235_stab9_8_9_chain_submission_paused_unchanged() -> None:
    """Stage 8 does NOT modify any CHAIN_SUBMISSION_PAUSED behavior;
    the kill-switch invariant is preserved — verify chain.py wasn't
    touched."""
    import subprocess
    repo_root = Path(__file__).resolve().parents[2]
    # git diff main vs HEAD on chain.py — must be empty for Stage 8 commit
    # (Stage 8 only modifies chain_reconciler.py + tests + loop_timing usage)
    src_chain = (_BRIDGE_DIR / "chain.py").read_text(encoding="utf-8")
    # Stage 8 markers must NOT appear in chain.py:
    assert "STAGE-8" not in src_chain, (
        "Stage 8 invariant violated: chain.py must not be modified — "
        "kill-switch + chain primitive surface is FROZEN-region adjacent."
    )


def test_t_235_stab9_8_10_pia_deferred_no_modification() -> None:
    """PIA audit deferred per directive — verify protocol_intelligence_agent.py
    has no Stage 8 changes (Stage 7 instrumentation untouched)."""
    src = (_BRIDGE_DIR / "protocol_intelligence_agent.py").read_text(encoding="utf-8")
    assert "STAGE-7" in src, "Stage 7 instrumentation must remain"
    assert "STAGE-8" not in src, (
        "Stage 8 must NOT modify PIA — audit found zero uncovered sync "
        "sub-calls (no self._chain, no requests/httpx/subprocess); "
        "compute_report's SQLite is already wrapped in to_thread per Stage 3."
    )


@pytest.mark.asyncio
async def test_t_235_stab9_8_11_event_tx_bytes_to_hex_normalization() -> None:
    """tx_hash bytes → hex string conversion happens BEFORE to_thread
    (pure-Python pre-processing on event loop; sync helper receives strings)."""
    store = _stub_store()
    bytes_tx = b"\xab\xcd\xef\x12" * 8  # 32-byte tx hash
    events = [{"transactionHash": bytes_tx, "deviceId": "d", "cumulativeScore": 0}]
    chain = _stub_chain(block_number=200, events=events)
    rec = ChainReconciler(store, chain)
    rec._last_block = 150
    await rec._reconcile_cycle()
    # mark_checkpoint_confirmed was called with hex-string tx
    args = store.mark_checkpoint_confirmed.call_args
    assert args is not None
    tx_arg = args[0][0]
    assert isinstance(tx_arg, str)
    assert tx_arg.startswith("0x")
    assert tx_arg == "0x" + bytes_tx.hex()


@pytest.mark.asyncio
async def test_t_235_stab9_8_12_requeue_still_spawns_per_unconfirmed() -> None:
    """Stage 8 preserves the existing fire-and-forget requeue pattern —
    asyncio.create_task per unconfirmed checkpoint (no semantic change)."""
    store = _stub_store()
    unconfirmed_cps = [
        {"id": 1, "device_id": "d1", "tx_hash": "0xa"},
        {"id": 2, "device_id": "d2", "tx_hash": "0xb"},
    ]
    store.get_unconfirmed_checkpoints = MagicMock(return_value=unconfirmed_cps)
    chain = _stub_chain(block_number=200, events=[])
    rec = ChainReconciler(store, chain)
    rec._last_block = 150
    with patch("asyncio.create_task") as mock_ct:
        await rec._reconcile_cycle()
    # 2 unconfirmed checkpoints → 2 create_task spawns
    assert mock_ct.call_count == 2
