"""
Phase 82 — Reactive Adjudication Interrupt Tests (8 tests)

test_1_token_bucket_allows_calls_within_limit
test_2_token_bucket_denies_call_when_exhausted
test_3_token_bucket_resets_after_window
test_4_listen_class_j_bus_fires_interrupt_on_high_risk
test_5_listen_class_j_bus_defers_when_bucket_exhausted
test_6_adjudicate_device_directly_returns_verdict_and_ruling_id
test_7_reactive_adjudication_log_stored_and_retrievable
test_8_tool_51_get_reactive_adjudication_status_returns_entries
"""

import asyncio
import json
import sys
import tempfile
import time
import types
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

BRIDGE_DIR = Path(__file__).parents[1]
sys.path.insert(0, str(BRIDGE_DIR))

# Stub heavy optional dependencies before any bridge imports
for _mod in ["web3", "web3.exceptions", "eth_account", "eth_account.signers.local",
             "anthropic"]:
    if _mod not in sys.modules:
        sys.modules[_mod] = MagicMock()

from vapi_bridge.store import Store

_DEVICE_A = "aa" * 32


def _make_store() -> Store:
    td = tempfile.mkdtemp()
    return Store(str(Path(td) / "test_p82.db"))


def _make_cfg(**kwargs):
    cfg = MagicMock()
    cfg.operator_api_key = "testkey82"
    cfg.agent_dry_run_mode = True
    cfg.reactive_adjudication_rate_limit = kwargs.get("reactive_adjudication_rate_limit", 2)
    cfg.reactive_adjudication_window_seconds = kwargs.get("reactive_adjudication_window_seconds", 60)
    cfg.ceremony_registry_address = ""
    cfg.iotex_rpc_url = ""
    cfg.class_j_detection_enabled = True
    cfg.class_j_entropy_windows = 10
    return cfg


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


# ---------------------------------------------------------------------------
# Token bucket tests (synchronous — no asyncio)
# ---------------------------------------------------------------------------

class TestTokenBucket(unittest.TestCase):
    """Verify _ReactiveAdjudicationBucket rate-limiting behaviour."""

    def _make_bucket(self, max_calls=2, window_seconds=60.0):
        from vapi_bridge.session_adjudicator import _ReactiveAdjudicationBucket
        return _ReactiveAdjudicationBucket(max_calls, window_seconds)

    def test_1_token_bucket_allows_calls_within_limit(self):
        """Bucket should grant consume() for first N calls in window."""
        bucket = self._make_bucket(max_calls=3)
        self.assertTrue(bucket.consume())
        self.assertTrue(bucket.consume())
        self.assertTrue(bucket.consume())

    def test_2_token_bucket_denies_call_when_exhausted(self):
        """After N grants, the next consume() returns False (bucket empty)."""
        bucket = self._make_bucket(max_calls=2)
        bucket.consume()
        bucket.consume()
        # 3rd call must be denied
        self.assertFalse(bucket.consume())

    def test_3_token_bucket_resets_after_window(self):
        """After window_seconds elapses, bucket resets and allows calls again."""
        bucket = self._make_bucket(max_calls=1, window_seconds=0.05)
        self.assertTrue(bucket.consume())   # granted
        self.assertFalse(bucket.consume())  # exhausted
        time.sleep(0.06)                    # wait for window to expire
        self.assertTrue(bucket.consume())   # reset — granted again


# ---------------------------------------------------------------------------
# Bus integration tests (asyncio)
# ---------------------------------------------------------------------------

class TestReactiveAdjudicationBus(unittest.TestCase):
    """Verify the class_j bus listener fires and defers correctly."""

    def _make_adjudicator(self, store, bus=None, **cfg_kwargs):
        from vapi_bridge.session_adjudicator import SessionAdjudicator
        cfg = _make_cfg(**cfg_kwargs)
        return SessionAdjudicator(cfg, store, bus=bus)

    def _make_bus(self):
        from vapi_bridge.agent_message_bus import AgentMessageBus
        bus = AgentMessageBus()
        _run(bus._init_lock())
        return bus

    def test_4_listen_class_j_bus_fires_interrupt_on_high_risk(self):
        """_listen_class_j_bus() should call _reactive_interrupt on a HIGH event."""
        store = _make_store()
        bus = self._make_bus()
        adj = self._make_adjudicator(store, bus=bus)

        interrupted = []

        async def _fake_interrupt(device_id, entropy_variance):
            interrupted.append((device_id, entropy_variance))

        adj._reactive_interrupt = _fake_interrupt

        async def _run_test():
            listener = asyncio.ensure_future(adj._listen_class_j_bus())
            await asyncio.sleep(0.05)
            await bus.publish(
                "class_j_high_risk_detected",
                {"device_id": _DEVICE_A, "entropy_variance": 0.01},
                source="class_j_detector",
            )
            await asyncio.sleep(0.1)
            listener.cancel()
            try:
                await listener
            except asyncio.CancelledError:
                pass

        _run(_run_test())
        self.assertEqual(len(interrupted), 1)
        self.assertEqual(interrupted[0][0], _DEVICE_A)
        self.assertAlmostEqual(interrupted[0][1], 0.01, places=3)

    def test_5_listen_class_j_bus_defers_when_bucket_exhausted(self):
        """When bucket is exhausted, was_deferred=1 entry is written to store."""
        store = _make_store()
        bus = self._make_bus()
        # Bucket size 0 — every call deferred immediately
        adj = self._make_adjudicator(
            store, bus=bus,
            reactive_adjudication_rate_limit=0,
            reactive_adjudication_window_seconds=60,
        )

        async def _run_test():
            listener = asyncio.ensure_future(adj._listen_class_j_bus())
            await asyncio.sleep(0.05)
            await bus.publish(
                "class_j_high_risk_detected",
                {"device_id": _DEVICE_A, "entropy_variance": 0.02},
                source="class_j_detector",
            )
            await asyncio.sleep(0.1)
            listener.cancel()
            try:
                await listener
            except asyncio.CancelledError:
                pass

        _run(_run_test())
        entries = store.get_reactive_adjudication_log(device_id=_DEVICE_A)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["was_deferred"], 1)
        self.assertEqual(entries[0]["triggered_by"], "class_j_high_risk_detected")


# ---------------------------------------------------------------------------
# Core ruling path
# ---------------------------------------------------------------------------

class TestReactiveAdjudicationCore(unittest.TestCase):
    """Verify _adjudicate_device_directly produces rulings and stores them."""

    def _make_adjudicator(self, store):
        from vapi_bridge.session_adjudicator import SessionAdjudicator
        cfg = _make_cfg()
        adj = SessionAdjudicator(cfg, store)
        return adj

    def test_6_adjudicate_device_directly_returns_verdict_and_ruling_id(self):
        """_adjudicate_device_directly() must return (verdict_str, int ruling_id)."""
        store = _make_store()
        # agent_rulings has FK on device — seed it first
        store.upsert_device(_DEVICE_A, "00" * 33)
        adj = self._make_adjudicator(store)

        # Patch LLM to avoid real Anthropic call
        async def _fake_llm(evidence):
            return "FLAG", 0.4, "Reactive test ruling."

        adj._llm_ruling = _fake_llm

        async def _run_test():
            return await adj._adjudicate_device_directly(
                device_id=_DEVICE_A,
                entropy_variance=0.015,
                source="test_direct",
            )

        verdict, ruling_id = _run(_run_test())
        self.assertIn(verdict, ("FLAG", "HOLD", "BLOCK", "CERTIFY", "CLEAR"))
        self.assertIsInstance(ruling_id, int)
        self.assertGreater(ruling_id, 0)

    def test_7_reactive_adjudication_log_stored_and_retrievable(self):
        """insert/get_reactive_adjudication_log round-trips correctly."""
        store = _make_store()
        rid = store.insert_reactive_adjudication_log(
            device_id=_DEVICE_A,
            triggered_by="class_j_high_risk_detected",
            entropy_variance=0.013,
            verdict="HOLD",
            was_deferred=False,
        )
        self.assertIsInstance(rid, int)
        entries = store.get_reactive_adjudication_log(device_id=_DEVICE_A)
        self.assertEqual(len(entries), 1)
        e = entries[0]
        self.assertEqual(e["device_id"], _DEVICE_A)
        self.assertAlmostEqual(e["entropy_variance"], 0.013, places=3)
        self.assertEqual(e["verdict"], "HOLD")
        self.assertEqual(e["was_deferred"], 0)

    def test_8_tool_51_get_reactive_adjudication_status_returns_entries(self):
        """Tool #51 get_reactive_adjudication_status returns expected structure."""
        from vapi_bridge.bridge_agent import BridgeAgent
        store = _make_store()
        cfg = _make_cfg()
        agent = BridgeAgent(cfg, store)
        # Seed two entries — one deferred, one not
        store.insert_reactive_adjudication_log(
            _DEVICE_A, "class_j_high_risk_detected", 0.01, "FLAG", False
        )
        store.insert_reactive_adjudication_log(
            _DEVICE_A, "class_j_high_risk_detected", 0.01, None, True
        )
        result = agent._execute_tool("get_reactive_adjudication_status", {"device_id": _DEVICE_A})
        self.assertIn("entries", result)
        self.assertIn("total_returned", result)
        self.assertIn("deferred_count", result)
        self.assertEqual(result["total_returned"], 2)
        self.assertEqual(result["deferred_count"], 1)


if __name__ == "__main__":
    unittest.main()
