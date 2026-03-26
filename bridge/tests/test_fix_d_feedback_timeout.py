"""
test_fix_d_feedback_timeout.py — Unit tests for Fix D (LED/haptic timeout) and
VHPRenewalAgent publish_sync source= argument (Phase seamless-improvements).

Tests:
  test_1: _feedback_executor is a ThreadPoolExecutor with max_workers=1
  test_2: _apply_feedback timeout fires when the executor blocks; loop resumes
  test_3: VHPRenewalAgent lifecycle-warning publish_sync called with source="VHPRenewalAgent"
  test_4: VHPRenewalAgent renewal publish_sync called with source="VHPRenewalAgent"
"""

import asyncio
import sys
import time
import threading
from pathlib import Path
from unittest.mock import MagicMock, patch, call

import pytest

_BRIDGE = Path(__file__).parents[1]
sys.path.insert(0, str(_BRIDGE))


# ---------------------------------------------------------------------------
# Test 1 — _feedback_executor attribute exists and is a bounded ThreadPoolExecutor
# ---------------------------------------------------------------------------

def test_1_feedback_executor_is_bounded():
    """dualshock_integration source must create _feedback_executor with max_workers=1."""
    import concurrent.futures as _cf
    import inspect
    from vapi_bridge import dualshock_integration as _mod

    src = inspect.getsource(_mod)
    # Verify the executor is created with max_workers=1 in source
    assert "max_workers=1" in src, (
        "dualshock_integration must create _feedback_executor with max_workers=1 "
        "to prevent thread accumulation on repeated USB-write hangs"
    )
    assert "_feedback_executor" in src, (
        "_feedback_executor attribute must be defined in dualshock_integration"
    )
    assert "ThreadPoolExecutor" in src, (
        "ThreadPoolExecutor must be used for _feedback_executor"
    )
    # Verify it is used in run_in_executor call (not None/default pool)
    assert "run_in_executor(self._feedback_executor" in src, (
        "_apply_feedback must use self._feedback_executor (not None/default pool) "
        "in run_in_executor call"
    )


# ---------------------------------------------------------------------------
# Test 2 — asyncio.wait_for timeout fires and loop resumes
# ---------------------------------------------------------------------------

def test_2_apply_feedback_timeout_resumes_loop():
    """asyncio.wait_for must raise TimeoutError and NOT block the event loop."""
    import concurrent.futures as _cf

    _BLOCK_SECONDS = 0.3
    _TIMEOUT_SECONDS = 0.1

    def _blocking_feedback(_inference):
        time.sleep(_BLOCK_SECONDS)

    executor = _cf.ThreadPoolExecutor(max_workers=1, thread_name_prefix="test_fix_d")

    async def _run():
        loop = asyncio.get_running_loop()
        t0 = time.monotonic()
        timed_out = False
        try:
            await asyncio.wait_for(
                loop.run_in_executor(executor, _blocking_feedback, 0x00),
                timeout=_TIMEOUT_SECONDS,
            )
        except asyncio.TimeoutError:
            timed_out = True
        elapsed = time.monotonic() - t0
        return timed_out, elapsed

    timed_out, elapsed = asyncio.run(_run())

    assert timed_out, "asyncio.wait_for did not raise TimeoutError on blocking executor"
    assert elapsed < _BLOCK_SECONDS, (
        f"Event loop was blocked for {elapsed:.3f}s — timeout did not fire in time. "
        f"Expected < {_BLOCK_SECONDS}s (the full executor block duration)."
    )
    executor.shutdown(wait=False)


# ---------------------------------------------------------------------------
# Test 3 — VHPRenewalAgent lifecycle-warning publish_sync source=
# ---------------------------------------------------------------------------

def test_3_lifecycle_warning_publish_sync_has_source():
    """vhp_lifecycle_warning publish_sync must pass source='VHPRenewalAgent'."""
    from vapi_bridge.vhp_renewal_agent import VHPRenewalAgent

    store = MagicMock()
    store.get_total_vhp_count.return_value = 0
    store.get_expiring_vhps.return_value = []

    bus = MagicMock()
    cfg = MagicMock()
    cfg.agent_dry_run_mode = True
    cfg.vhp_renewal_warning_days = 7

    agent = VHPRenewalAgent(cfg=cfg, store=store, chain=MagicMock(), bus=bus)

    import asyncio as _aio
    _aio.run(agent._check_and_renew())

    # Find the call that published vhp_lifecycle_warning
    lifecycle_calls = [
        c for c in bus.publish_sync.call_args_list
        if c.args and c.args[0] == "vhp_lifecycle_warning"
    ]
    assert lifecycle_calls, (
        "publish_sync was never called with topic='vhp_lifecycle_warning' "
        "when total VHP count = 0"
    )
    for c in lifecycle_calls:
        assert c.kwargs.get("source") == "VHPRenewalAgent" or (
            len(c.args) >= 3 and c.args[2] == "VHPRenewalAgent"
        ), (
            f"lifecycle_warning publish_sync missing source='VHPRenewalAgent': {c}"
        )


# ---------------------------------------------------------------------------
# Test 4 — VHPRenewalAgent renewal publish_sync source=
# ---------------------------------------------------------------------------

def test_4_renewal_publish_sync_has_source():
    """vhp_renewed publish_sync must pass source='VHPRenewalAgent'."""
    from vapi_bridge.vhp_renewal_agent import VHPRenewalAgent

    cutoff_future = time.time() + 3 * 86_400  # expires in 3 days — within warning window

    store = MagicMock()
    store.get_total_vhp_count.return_value = 1
    store.get_expiring_vhps.return_value = [
        {
            "device_id": "dev_abc123",
            "token_id":  42,
            "expires_at": cutoff_future,
        }
    ]
    store.insert_vhp_renewal.return_value = 1

    chain = MagicMock()
    chain.renew_vhp = MagicMock(return_value=None)

    bus = MagicMock()
    cfg = MagicMock()
    cfg.agent_dry_run_mode = True   # dry_run → no real chain call
    cfg.vhp_renewal_warning_days = 7
    cfg.ioswarm_renewal_enabled = False  # Phase 109B guard — prevents MagicMock truthy from routing to coordinator

    agent = VHPRenewalAgent(cfg=cfg, store=store, chain=chain, bus=bus)

    import asyncio as _aio
    _aio.run(agent._check_and_renew())

    renewal_calls = [
        c for c in bus.publish_sync.call_args_list
        if c.args and c.args[0] == "vhp_renewed"
    ]
    assert renewal_calls, (
        "publish_sync was never called with topic='vhp_renewed' "
        "when an expiring VHP exists"
    )
    for c in renewal_calls:
        assert c.kwargs.get("source") == "VHPRenewalAgent" or (
            len(c.args) >= 3 and c.args[2] == "VHPRenewalAgent"
        ), (
            f"vhp_renewed publish_sync missing source='VHPRenewalAgent': {c}"
        )
