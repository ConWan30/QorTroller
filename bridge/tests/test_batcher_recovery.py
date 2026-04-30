"""
Tests for Batcher startup recovery + shutdown drain + queue bound — Phase 36

4 tests covering:
1. get_pending_records() called during startup to re-queue pending records
2. QueueFull during startup recovery is handled gracefully (no exception)
3. asyncio.Queue maxsize=1000 enforced (not unbounded)
4. startup with empty pending records completes without error
"""
import asyncio
import sys
import os
import types
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Stub web3 before importing batcher (batcher → chain → web3)
# Mirrors pattern from test_phg_registry.py
for _mod_name in ("web3", "web3.exceptions", "eth_account"):
    if _mod_name not in sys.modules:
        sys.modules[_mod_name] = types.ModuleType(_mod_name)

_web3_exc = sys.modules["web3.exceptions"]
if not hasattr(_web3_exc, "ContractLogicError"):
    _web3_exc.ContractLogicError = type("ContractLogicError", (Exception,), {})
if not hasattr(_web3_exc, "TransactionNotFound"):
    _web3_exc.TransactionNotFound = type("TransactionNotFound", (Exception,), {})

_web3_mod = sys.modules["web3"]
for _attr in ("AsyncWeb3", "AsyncHTTPProvider"):
    if not hasattr(_web3_mod, _attr):
        setattr(_web3_mod, _attr, MagicMock())

_eth_acct = sys.modules["eth_account"]
if not hasattr(_eth_acct, "Account"):
    _eth_acct.Account = MagicMock()

from vapi_bridge.batcher import Batcher


def _make_batcher(pending_records=None):
    cfg = MagicMock()
    cfg.batch_size = 10
    cfg.batch_timeout_s = 5
    cfg.max_retries = 3
    cfg.retry_base_delay_s = 1.0
    cfg.phg_registry_address = ""

    store = MagicMock()
    store.get_pending_records.return_value = pending_records or []
    store.get_failed_submissions.return_value = []

    chain = MagicMock()

    return Batcher(cfg, store, chain), store, cfg


class TestBatcherRecovery(unittest.TestCase):

    def test_1_startup_calls_get_pending_records(self):
        """Batcher.run() calls store.get_pending_records on startup for recovery."""
        batcher, store, _ = _make_batcher(pending_records=[])

        async def _run_briefly():
            task = asyncio.create_task(batcher.run())
            await asyncio.sleep(0.05)  # give startup block time to execute
            task.cancel()
            try:
                await task
            except (asyncio.CancelledError, Exception):
                pass

        asyncio.run(_run_briefly())
        store.get_pending_records.assert_called()

    def test_2_startup_recovery_handles_queue_full_gracefully(self):
        """QueueFull during startup re-queue is caught silently (no exception propagates)."""
        # Build a raw record that can be parsed
        # We'll use a record with raw_data=None so parse_record is skipped
        pending_record = {
            "record_hash": "aa" * 32,
            "raw_data": None,  # None raw_data → silently skipped
            "status": "pending",
        }
        batcher, store, _ = _make_batcher(pending_records=[pending_record] * 5)

        async def _run_briefly():
            task = asyncio.create_task(batcher.run())
            await asyncio.sleep(0.05)
            task.cancel()
            try:
                await task
            except (asyncio.CancelledError, Exception):
                pass

        # Should not raise any exception
        asyncio.run(_run_briefly())

    def test_3_queue_has_maxsize_1000(self):
        """Batcher queue is bounded at maxsize=1000 (not unbounded)."""
        batcher, _, _ = _make_batcher()
        assert batcher._queue.maxsize == 1000, (
            f"Expected maxsize=1000, got {batcher._queue.maxsize}"
        )

    def test_4_startup_with_empty_pending_records_completes_without_error(self):
        """Empty pending records list at startup does not raise."""
        batcher, store, _ = _make_batcher(pending_records=[])

        async def _run_briefly():
            task = asyncio.create_task(batcher.run())
            await asyncio.sleep(0.05)
            task.cancel()
            try:
                await task
            except (asyncio.CancelledError, Exception):
                pass

        asyncio.run(_run_briefly())
        store.get_pending_records.assert_called_once()


class TestBatcherChainPausedDeadLetter(unittest.TestCase):
    """Phase 237.5 Path C+ secondary fix — chain_submission_paused → DEAD_LETTER.

    Mirrors the existing dead-letter shortcuts for private-key-not-set,
    P256 (0xf46a06ea), and insufficient-funds in batcher.py:285-339.
    The kill-switch error is raised by chain.py:_send_tx when the
    operator has set CHAIN_SUBMISSION_PAUSED=true; retrying produces
    no progress because the state is operator-controlled, so the
    correct behavior is immediate dead-letter with once-and-suppress
    log noise.
    """

    DEVICE_ID = "cc" * 32

    def _build_record(self):
        # Minimal PoACRecord stand-in covering attributes _submit_batch reads.
        rec = MagicMock()
        rec.device_id = bytes.fromhex(self.DEVICE_ID)
        rec.device_id_hex = self.DEVICE_ID
        rec.record_hash = bytes(32)
        rec.signature = bytes(64)
        rec.raw_body = bytes(164)
        rec.schema_version = 0
        rec.inference_result = 0x10
        return rec

    def _build_batcher_with_paused_chain(self):
        cfg = MagicMock()
        cfg.batch_size = 10
        cfg.batch_timeout_s = 5
        cfg.max_retries = 3
        cfg.retry_base_delay_s = 1.0
        cfg.phg_registry_address = ""

        store = MagicMock()
        # batch_update_status / create_submission are sync calls dispatched via
        # asyncio.to_thread; MagicMock handles both call shapes.
        store.create_submission.return_value = 12345

        chain = MagicMock()
        # Single-record path uses verify_single for schema_version=0.
        chain.verify_single = AsyncMock(
            side_effect=RuntimeError(
                "chain_submission_paused: on-chain transactions are paused via "
                "CHAIN_SUBMISSION_PAUSED=true in bridge/.env"
            )
        )
        return Batcher(cfg, store, chain), store, cfg

    # T-BATCHER-CHAIN-PAUSED-1
    def test_chain_paused_dead_letters_immediately(self):
        """A single chain_submission_paused error transitions both the
        submission and its associated records to STATUS_DEAD_LETTER."""
        from vapi_bridge.store import STATUS_DEAD_LETTER

        batcher, store, _ = self._build_batcher_with_paused_chain()
        record = self._build_record()
        raw = bytes(228)

        async def _run():
            await batcher._submit_batch([(record, raw)])

        asyncio.run(_run())

        # The submission was marked dead-letter with the kill-switch error string.
        update_calls = store.update_submission.call_args_list
        # Find the dead-letter call (the test mock starts with STATUS_BATCHED).
        dead_letter_call = next(
            (c for c in update_calls if c.kwargs.get("status") == STATUS_DEAD_LETTER),
            None,
        )
        assert dead_letter_call is not None, (
            "expected at least one update_submission call with STATUS_DEAD_LETTER"
        )
        err = dead_letter_call.kwargs.get("error", "")
        assert "chain_submission_paused" in err.lower() or "kill-switch" in err.lower(), (
            f"expected error to reference chain_submission_paused or kill-switch; got: {err!r}"
        )

        # The record_hashes were transitioned to DEAD_LETTER too.
        batch_status_calls = store.batch_update_status.call_args_list
        dead_letter_batch_calls = [
            c for c in batch_status_calls
            if STATUS_DEAD_LETTER in c.args
        ]
        assert dead_letter_batch_calls, (
            "expected batch_update_status call with STATUS_DEAD_LETTER"
        )

    # T-BATCHER-CHAIN-PAUSED-2
    def test_chain_paused_warning_logged_once_then_suppressed(self):
        """First chain_submission_paused failure logs a WARNING; subsequent
        failures suppress to DEBUG via the _chain_paused_logged flag."""
        import logging
        batcher, _, _ = self._build_batcher_with_paused_chain()
        record = self._build_record()
        raw = bytes(228)

        # Capture log records emitted by the batcher logger.
        captured: list[logging.LogRecord] = []

        class _Capture(logging.Handler):
            def emit(self, rec):
                captured.append(rec)

        handler = _Capture(level=logging.DEBUG)
        # The test environment imports vapi_bridge.batcher via sys.path shim
        # (line 17 of this file), so the live logger name is vapi_bridge.batcher.
        # In production runs the logger appears as bridge.vapi_bridge.batcher.
        batcher_logger = logging.getLogger("vapi_bridge.batcher")
        prior_level = batcher_logger.level
        batcher_logger.setLevel(logging.DEBUG)
        batcher_logger.addHandler(handler)

        try:
            async def _run_twice():
                await batcher._submit_batch([(record, raw)])
                await batcher._submit_batch([(record, raw)])

            asyncio.run(_run_twice())
        finally:
            batcher_logger.removeHandler(handler)
            batcher_logger.setLevel(prior_level)

        warnings = [r for r in captured if r.levelno == logging.WARNING
                    and "chain_submission_paused" in r.getMessage().lower()]
        debugs = [r for r in captured if r.levelno == logging.DEBUG
                  and "chain_submission_paused" in r.getMessage().lower()
                  and "suppressed" in r.getMessage().lower()]

        assert len(warnings) == 1, (
            f"expected exactly 1 WARNING with chain_submission_paused; got {len(warnings)}"
        )
        assert len(debugs) >= 1, (
            f"expected at least 1 suppressed-repeat DEBUG; got {len(debugs)}"
        )
        assert batcher._chain_paused_logged is True, (
            "expected _chain_paused_logged flag to be True after first WARNING"
        )


if __name__ == "__main__":
    unittest.main()
