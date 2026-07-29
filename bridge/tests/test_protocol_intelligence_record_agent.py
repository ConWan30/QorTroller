"""
Phase 189 — ProtocolIntelligenceRecordAgent (agent #33) tests.

Covers genesis PIR-0010 bootstrap (including the idempotent and duplicate
paths), the chain-status report with its pir_chain_broken bus event, and the
poll loop's bootstrap-then-poll ordering.
"""
import asyncio
import hashlib
import os
import sys
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from vapi_bridge import protocol_intelligence_record_agent as pir_mod
from vapi_bridge.protocol_intelligence_record_agent import (
    _GENESIS_PIR,
    ProtocolIntelligenceRecordAgent,
)


def _agent(total_pirs=0, chain_intact=True, bus=None):
    store = MagicMock()
    store.get_pir_chain_status.return_value = {
        "total_pirs":      total_pirs,
        "chain_intact":    chain_intact,
        "latest_pir_hash": "ab" * 32,
        "latest_cycle":    10,
    }
    store.insert_pir.return_value = (1, "cd" * 32)
    cfg = MagicMock()
    cfg.pir_anchor_interval = 10
    return ProtocolIntelligenceRecordAgent(store, cfg, bus), store


class TestGenesisBootstrap(unittest.TestCase):

    def test_inserts_genesis_when_chain_empty(self):
        agent, store = _agent(total_pirs=0)
        self.assertTrue(agent._bootstrap_genesis_pir())
        kwargs = store.insert_pir.call_args.kwargs
        self.assertEqual(kwargs["cycle_number"], 10)
        self.assertEqual(kwargs["phase_produced"], "187")
        self.assertEqual(kwargs["threat_forecast"], "pir_chain_integrity_attack")
        self.assertEqual(kwargs["harness_score"], 0.78)
        self.assertEqual(
            kwargs["wif_hash"],
            hashlib.sha256(_GENESIS_PIR["wif_content"].encode()).hexdigest(),
        )
        self.assertGreater(kwargs["eval_timestamp"], 0)

    def test_skips_when_chain_already_populated(self):
        agent, store = _agent(total_pirs=3)
        self.assertFalse(agent._bootstrap_genesis_pir())
        store.insert_pir.assert_not_called()

    def test_duplicate_insert_is_not_an_error(self):
        agent, store = _agent(total_pirs=0)
        store.insert_pir.side_effect = ValueError("UNIQUE constraint failed")
        self.assertFalse(agent._bootstrap_genesis_pir())

    def test_store_failure_fails_open(self):
        agent, store = _agent(total_pirs=0)
        store.get_pir_chain_status.side_effect = RuntimeError("db gone")
        self.assertFalse(agent._bootstrap_genesis_pir())

    def test_anchor_interval_read_from_cfg(self):
        store = MagicMock()
        cfg = MagicMock()
        cfg.pir_anchor_interval = 25
        self.assertEqual(
            ProtocolIntelligenceRecordAgent(store, cfg)._anchor_interval, 25
        )


class TestStatusReport(unittest.TestCase):

    def test_intact_chain_publishes_nothing(self):
        bus = MagicMock()
        agent, _ = _agent(total_pirs=4, chain_intact=True, bus=bus)
        agent._report_status()
        bus.publish_sync.assert_not_called()

    def test_broken_chain_publishes_event(self):
        bus = MagicMock()
        agent, _ = _agent(total_pirs=4, chain_intact=False, bus=bus)
        agent._report_status()
        bus.publish_sync.assert_called_once()
        topic, payload = bus.publish_sync.call_args[0]
        self.assertEqual(topic, "pir_chain_broken")
        self.assertEqual(payload["total_pirs"], 4)
        self.assertEqual(payload["latest_cycle"], 10)

    def test_broken_chain_without_bus_does_not_raise(self):
        agent, _ = _agent(total_pirs=4, chain_intact=False, bus=None)
        agent._report_status()

    def test_bus_publish_error_is_swallowed(self):
        bus = MagicMock()
        bus.publish_sync.side_effect = RuntimeError("bus down")
        agent, _ = _agent(total_pirs=4, chain_intact=False, bus=bus)
        agent._report_status()

    def test_store_error_is_swallowed(self):
        agent, store = _agent()
        store.get_pir_chain_status.side_effect = RuntimeError("db gone")
        agent._report_status()


class TestPollLoop(unittest.TestCase):

    def test_bootstraps_then_reports_each_cycle(self):
        agent, _ = _agent(total_pirs=0)
        agent._bootstrap_genesis_pir = MagicMock(return_value=True)
        agent._report_status = MagicMock()

        calls = []

        async def _fake_sleep(delay):
            calls.append(delay)
            if len(calls) == 2:
                raise asyncio.CancelledError

        with patch.object(pir_mod.asyncio, "sleep", _fake_sleep), \
                self.assertRaises(asyncio.CancelledError):
            asyncio.run(agent.run_poll_loop())

        agent._bootstrap_genesis_pir.assert_called_once()
        self.assertEqual(agent._report_status.call_count, 1)
        self.assertEqual(calls, [pir_mod._POLL_INTERVAL_S] * 2)


if __name__ == "__main__":
    unittest.main()
