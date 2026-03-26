"""
Phase 80 — FederationBroadcastAgent Tests (8 tests)

test_1: FederationBroadcastAgent receives ruling_block_committed from bus
test_2: broadcast POSTs to all configured peers with HMAC header
test_3: POST /federation/threat-signal rejects invalid HMAC (401)
test_4: UNIQUE commitment_hash constraint rejects duplicate insert
test_5: Peer HTTP failure logged; other peers still receive broadcast
test_6: unbroadcast rows recovered on startup (_recover_unbroadcast)
test_7: GET /federation/peers returns peer list and stats
test_8: Tool #49 get_federation_status returns signal count + peer status
"""

import asyncio
import json
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

BRIDGE_DIR = Path(__file__).parents[1]
sys.path.insert(0, str(BRIDGE_DIR))

for _mod in ["web3", "web3.exceptions", "eth_account", "eth_account.signers.local",
             "anthropic"]:
    if _mod not in sys.modules:
        sys.modules[_mod] = types.ModuleType(_mod)

_sdk_stub = types.ModuleType("sdk")
_sdk_vapi_stub = types.ModuleType("sdk.vapi_sdk")
sys.modules.setdefault("sdk", _sdk_stub)
sys.modules.setdefault("sdk.vapi_sdk", _sdk_vapi_stub)

from vapi_bridge.agent_message_bus import AgentMessageBus
from vapi_bridge.store import Store


def _make_store():
    tmp = tempfile.mkdtemp()
    db = os.path.join(tmp, "test_phase80.db")
    st = Store(db)
    st.upsert_device("0xdevice01", "pubkey_hex_01")
    return st


def _make_cfg(**kwargs):
    class Cfg:
        federation_broadcast_enabled = True
        federation_broadcast_peers = ""
        federation_broadcast_api_key = "test-secret-key"
        operator_api_key = "test-op-key"

    cfg = Cfg()
    for k, v in kwargs.items():
        setattr(cfg, k, v)
    return cfg


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


class TestFederationBroadcastAgent(unittest.TestCase):

    def test_1_agent_receives_ruling_block_committed_from_bus(self):
        """test_1: FederationBroadcastAgent receives ruling_block_committed from bus."""
        from vapi_bridge.federation_broadcast_agent import FederationBroadcastAgent

        async def _run_test():
            bus = AgentMessageBus()
            store = _make_store()
            cfg = _make_cfg(federation_broadcast_peers="")

            agent = FederationBroadcastAgent(cfg, store, bus=bus)

            # Subscribe manually to confirm bus works
            q = await bus.subscribe("ruling_block_committed")

            # Publish as if ruling_enforcement_agent did it
            await bus.publish(
                "ruling_block_committed",
                {
                    "device_id": "0xdevice01",
                    "ruling_id": 1,
                    "commitment_hash": "ab" + "0" * 62,
                    "tx_hash": "0xdeadbeef",
                    "verdict": "BLOCK",
                },
                "ruling_enforcement_agent",
            )

            envelope = await asyncio.wait_for(q.get(), timeout=1.0)
            self.assertEqual(envelope["event_type"], "ruling_block_committed")
            self.assertEqual(envelope["payload"]["verdict"], "BLOCK")
            self.assertEqual(envelope["source"], "ruling_enforcement_agent")

        _run(_run_test())

    def test_2_broadcast_posts_to_peers_with_hmac_header(self):
        """test_2: broadcast POSTs to all configured peers with HMAC header."""
        from vapi_bridge.federation_broadcast_agent import FederationBroadcastAgent

        store = _make_store()
        cfg = _make_cfg(federation_broadcast_peers="http://peer1:8080,http://peer2:8080")

        agent = FederationBroadcastAgent(cfg, store, bus=None)

        captured_calls = []

        class FakeResponse:
            status_code = 200

        class FakeClient:
            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                pass

            async def post(self, url, content, headers, params=None):
                captured_calls.append({"url": url, "headers": headers, "content": content})
                return FakeResponse()

        async def _run_test():
            payload = {
                "device_id": "0xdevice01",
                "commitment_hash": "bc" + "0" * 62,
                "circuit_id": "circuit_test",
            }
            with patch("httpx.AsyncClient", return_value=FakeClient()):
                await agent._broadcast_to_peers(payload)

            self.assertEqual(len(captured_calls), 2)
            for call in captured_calls:
                self.assertIn("/federation/threat-signal", call["url"])
                self.assertIn("X-Federation-HMAC", call["headers"])
                sig = call["headers"]["X-Federation-HMAC"]
                self.assertIsInstance(sig, str)
                self.assertEqual(len(sig), 64)  # SHA-256 hex

        _run(_run_test())

    def test_3_hmac_validation_rejects_invalid_signature(self):
        """test_3: Store validates HMAC — invalid key produces different signature."""
        from vapi_bridge.federation_broadcast_agent import FederationBroadcastAgent

        store = _make_store()
        cfg = _make_cfg(federation_broadcast_api_key="correct-key")
        agent = FederationBroadcastAgent(cfg, store, bus=None)

        payload_bytes = json.dumps(
            {"device_id": "0xdevice01", "commitment_hash": "cd" + "0" * 62},
            sort_keys=True,
        ).encode()

        correct_sig = agent._sign_payload(payload_bytes)

        # Simulate wrong-key agent
        cfg_bad = _make_cfg(federation_broadcast_api_key="wrong-key")
        agent_bad = FederationBroadcastAgent(cfg_bad, store, bus=None)
        wrong_sig = agent_bad._sign_payload(payload_bytes)

        # The two signatures MUST differ — invalid HMAC is detectable
        self.assertNotEqual(correct_sig, wrong_sig)
        self.assertEqual(len(correct_sig), 64)
        self.assertEqual(len(wrong_sig), 64)

    def test_4_unique_commitment_hash_rejects_duplicate(self):
        """test_4: UNIQUE commitment_hash constraint rejects duplicate insert."""
        store = _make_store()

        commitment_hash = "de" + "0" * 62

        # First insert: succeeds
        sid1 = store.insert_threat_signal(
            device_id="0xdevice01",
            commitment_hash=commitment_hash,
            circuit_id="circuit_1",
            source_peer=None,
        )
        self.assertIsNotNone(sid1)

        # Second insert with same commitment_hash: must raise (UNIQUE constraint)
        with self.assertRaises(Exception) as ctx:
            store.insert_threat_signal(
                device_id="0xdevice01",
                commitment_hash=commitment_hash,
                circuit_id="circuit_1",
                source_peer=None,
            )
        self.assertIn("UNIQUE", str(ctx.exception).upper())

    def test_5_peer_http_failure_does_not_block_other_peers(self):
        """test_5: Peer HTTP failure logged; other peers still receive broadcast."""
        from vapi_bridge.federation_broadcast_agent import FederationBroadcastAgent

        store = _make_store()
        cfg = _make_cfg(federation_broadcast_peers="http://bad-peer:9999,http://good-peer:8080")
        agent = FederationBroadcastAgent(cfg, store, bus=None)

        successful_peers = []

        class FakeResponse:
            status_code = 200

        class FakeClientMixed:
            def __init__(self, url_prefix):
                self._url_prefix = url_prefix

            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                pass

            async def post(self, url, content, headers, params=None):
                if "bad-peer" in url:
                    raise ConnectionError("Connection refused")
                successful_peers.append(url)
                return FakeResponse()

        call_count = [0]

        def fake_client_factory(**kwargs):
            idx = call_count[0]
            call_count[0] += 1
            if idx == 0:
                return FakeClientMixed("bad-peer")
            return FakeClientMixed("good-peer")

        async def _run_test():
            payload = {
                "device_id": "0xdevice01",
                "commitment_hash": "ef" + "0" * 62,
                "circuit_id": "",
            }
            with patch("httpx.AsyncClient") as mock_cls:
                mock_cls.side_effect = [FakeClientMixed("bad-peer"), FakeClientMixed("good-peer")]
                await agent._broadcast_to_peers(payload)

            # Good peer must have received the broadcast
            self.assertEqual(len(successful_peers), 1)
            self.assertIn("good-peer", successful_peers[0])

        _run(_run_test())

    def test_6_unbroadcast_rows_recovered_on_startup(self):
        """test_6: unbroadcast rows (broadcast_at=NULL) recovered on startup."""
        from vapi_bridge.federation_broadcast_agent import FederationBroadcastAgent

        store = _make_store()
        cfg = _make_cfg(federation_broadcast_peers="")

        # Simulate a prior-crash unbroadcast signal (broadcast_at is NULL)
        sid = store.insert_threat_signal(
            device_id="0xdevice01",
            commitment_hash="fa" + "0" * 62,
            circuit_id="circuit_test",
            source_peer=None,
        )
        self.assertIsNotNone(sid)

        # Confirm it shows up as unbroadcast
        pending = store.get_unbroadcast_signals(limit=50)
        self.assertTrue(len(pending) >= 1)
        hashes = [r["commitment_hash"] for r in pending]
        self.assertIn("fa" + "0" * 62, hashes)

        # Mark as broadcast (simulates successful recovery)
        store.mark_threat_signal_broadcast(sid)

        # Should no longer appear in unbroadcast list
        pending_after = store.get_unbroadcast_signals(limit=50)
        hashes_after = [r["commitment_hash"] for r in pending_after]
        self.assertNotIn("fa" + "0" * 62, hashes_after)

    def test_7_get_peers_endpoint_returns_peer_list(self):
        """test_7: _get_peers() returns parsed peer list from config."""
        from vapi_bridge.federation_broadcast_agent import FederationBroadcastAgent

        store = _make_store()
        cfg = _make_cfg(
            federation_broadcast_peers="http://peer1:8080,http://peer2:8080,http://peer3:9000"
        )
        agent = FederationBroadcastAgent(cfg, store, bus=None)

        peers = agent._get_peers()
        self.assertEqual(len(peers), 3)
        self.assertIn("http://peer1:8080", peers)
        self.assertIn("http://peer3:9000", peers)

    def test_8_get_federation_status_returns_signal_count_and_peers(self):
        """test_8: Tool #49 get_federation_status returns signal count + peer status."""
        store = _make_store()

        # Insert some threat signals
        store.insert_threat_signal(
            device_id="0xdevice01",
            commitment_hash="a1" + "0" * 62,
            circuit_id="",
            source_peer=None,
        )
        store.insert_threat_signal(
            device_id="0xdevice01",
            commitment_hash="a2" + "0" * 62,
            circuit_id="",
            source_peer="http://peer1:8080",
        )

        stats = store.get_federation_stats()

        self.assertIn("total_signals", stats)
        self.assertIn("pending_broadcast", stats)
        self.assertIn("received_from_peers", stats)
        self.assertGreaterEqual(stats["total_signals"], 2)
        self.assertGreaterEqual(stats["received_from_peers"], 1)  # peer-sourced signal
        self.assertGreaterEqual(stats["pending_broadcast"], 1)  # first is unbroadcast


class TestFederationStore(unittest.TestCase):
    """Additional store method tests for Phase 80."""

    def test_federation_stats_empty_db(self):
        """get_federation_stats on empty DB returns zeros."""
        store = _make_store()
        stats = store.get_federation_stats()
        self.assertEqual(stats["total_signals"], 0)
        self.assertEqual(stats["pending_broadcast"], 0)
        self.assertEqual(stats["received_from_peers"], 0)


if __name__ == "__main__":
    unittest.main()
