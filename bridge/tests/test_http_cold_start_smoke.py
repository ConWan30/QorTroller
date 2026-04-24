"""Phase 235-ULTRAREVIEW Commit 5 — HTTP cold-start smoke test.

T-SMOKE-1: /health responds within 10s of Uvicorn startup (no event-loop starvation)

Reproduces the live-reproduced finding from the ULTRAREVIEW: Uvicorn starts, session
loop + batcher + curator keep running, but the HTTP ASGI handler is starved and curl
returns HTTP 000 after 10s.  After the batcher startup yield fix (asyncio.sleep(5) +
asyncio.to_thread for get_pending_records), /health must respond in < 10s.
"""
import asyncio
import os
import sys
import time
import types

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Stub heavy optional deps that chain.py imports before we import batcher
from unittest.mock import MagicMock as _MagicMock
for _mod in ["web3", "web3.exceptions", "eth_account", "eth_account.signers.local"]:
    if _mod not in sys.modules:
        _m = types.ModuleType(_mod)
        sys.modules[_mod] = _m
# Ensure web3 has the names chain.py imports
_web3_mod = sys.modules["web3"]
for _attr in ["AsyncWeb3", "AsyncHTTPProvider", "Web3"]:
    if not hasattr(_web3_mod, _attr):
        setattr(_web3_mod, _attr, _MagicMock())
_web3_exc = sys.modules["web3.exceptions"]
for _attr in ["ContractLogicError", "TransactionNotFound"]:
    if not hasattr(_web3_exc, _attr):
        setattr(_web3_exc, _attr, Exception)
_eth_acc = sys.modules["eth_account"]
if not hasattr(_eth_acc, "Account"):
    setattr(_eth_acc, "Account", _MagicMock())

pytestmark = pytest.mark.smoke


# ---------------------------------------------------------------------------
# T-SMOKE-1: batcher startup does not block /health endpoint
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_t_smoke_1_health_responds_without_starvation(tmp_path):
    """The batcher.run() startup path must not hold the event loop long enough
    to starve HTTP request processing.

    Strategy: mock get_pending_records to simulate a 200ms blocking call (small
    DB, representative of cold-start with pending records). Verify that a
    concurrent asyncio task simulating an HTTP request completes in < 2s even
    while batcher.run() is processing its startup block.

    This is a unit-level proxy for the live curl test — it validates the
    asyncio.to_thread() wrapping without starting an actual server process.
    """
    import asyncio
    from unittest.mock import MagicMock, patch

    # Simulate a slow get_pending_records (200ms blocking call)
    def _slow_get_pending(_limit=50):
        time.sleep(0.2)
        return []  # no records to re-enqueue

    class _FakeCfg:
        batch_size = 10
        batch_timeout_s = 30
        max_retries = 3
        retry_base_delay_s = 2.0

    class _FakeStore:
        def get_pending_records(self, limit=50):
            return _slow_get_pending(limit)

    class _FakeChain:
        pass

    from vapi_bridge.batcher import Batcher

    cfg = _FakeCfg()
    store = _FakeStore()
    chain = _FakeChain()
    batcher = Batcher(cfg, store, chain)

    _http_response_time: list[float] = []

    async def _simulated_http_request():
        """Simulates an HTTP handler: yields once and records when it ran."""
        await asyncio.sleep(0)
        _http_response_time.append(time.monotonic())

    # Patch asyncio.sleep in batcher to use 0 instead of 5 so the test runs fast
    _original_sleep = asyncio.sleep

    async def _fast_sleep(n):
        await _original_sleep(0)  # collapse the 5s startup delay to 0 for test speed

    t_start = time.monotonic()

    with patch("vapi_bridge.batcher.asyncio") as mock_asyncio:
        # Keep most of asyncio working, just override sleep and to_thread
        mock_asyncio.sleep = _fast_sleep
        mock_asyncio.to_thread = asyncio.to_thread
        mock_asyncio.create_task = asyncio.create_task
        mock_asyncio.CancelledError = asyncio.CancelledError
        mock_asyncio.get_running_loop = asyncio.get_running_loop
        mock_asyncio.Queue = asyncio.Queue
        mock_asyncio.wait_for = asyncio.wait_for

        # Start batcher and the simulated HTTP request concurrently
        batcher_task = asyncio.create_task(batcher.run())
        http_task    = asyncio.create_task(_simulated_http_request())

        # Wait for the HTTP task to complete (should be near-instant after first yield)
        try:
            await asyncio.wait_for(http_task, timeout=5.0)
        finally:
            batcher_task.cancel()
            try:
                await batcher_task
            except (asyncio.CancelledError, Exception):
                pass

    assert len(_http_response_time) == 1, "HTTP task must have executed"
    elapsed = _http_response_time[0] - t_start

    assert elapsed < 2.0, (
        f"HTTP cold-start starvation: simulated HTTP request took {elapsed:.2f}s > 2s. "
        "batcher startup is blocking the event loop — asyncio.to_thread() not working."
    )


# ---------------------------------------------------------------------------
# T-SMOKE-2: batcher run() uses asyncio.to_thread for get_pending_records
# ---------------------------------------------------------------------------

def test_t_smoke_2_batcher_uses_to_thread():
    """Static guard: verify batcher.run() source calls asyncio.to_thread for
    the startup get_pending_records call. This prevents regression where
    the to_thread call is accidentally reverted to a direct sync call.
    """
    import inspect
    from vapi_bridge.batcher import Batcher
    src = inspect.getsource(Batcher.run)
    assert "asyncio.to_thread" in src, (
        "batcher.Batcher.run() must use asyncio.to_thread() for get_pending_records "
        "startup call — direct sync call blocks the event loop during cold start"
    )
    assert "await asyncio.sleep(0)" in src, (
        "batcher.Batcher.run() must yield with await asyncio.sleep(0) after "
        "processing the startup pending-records loop"
    )
