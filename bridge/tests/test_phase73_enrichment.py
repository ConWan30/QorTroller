"""
Phase 73 — SessionAdjudicator Ceremony Enrichment Tests (4 tests)

Tests the ceremony integrity enrichment in SessionAdjudicator._process_ruling_request:
  test_1: adjudication evidence includes ceremony_on_chain_match field
  test_2: ceremony registry unreachable → evidence has error field, ruling proceeds normally
  test_3: on_chain_match=False → evidence flags ceremony_integrity_failed=True
  test_4: agent_rulings table accepts ceremony_integrity JSON column

NOTE: These tests mock the ceremony registry call — real on-chain verification
requires a live IoTeX testnet node (test is CI-safe).
"""

import asyncio
import json
import sys
import tempfile
import os
import types
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

BRIDGE_DIR = Path(__file__).parents[1]
sys.path.insert(0, str(BRIDGE_DIR))

# Stub heavy optional dependencies
for _mod in ["web3", "web3.exceptions", "eth_account", "eth_account.signers.local",
             "anthropic"]:
    if _mod not in sys.modules:
        sys.modules[_mod] = types.ModuleType(_mod)

# Stub SDK module to avoid SDK path issues in bridge test context
_sdk_stub = types.ModuleType("sdk")
_sdk_vapi_stub = types.ModuleType("sdk.vapi_sdk")
sys.modules.setdefault("sdk", _sdk_stub)
sys.modules.setdefault("sdk.vapi_sdk", _sdk_vapi_stub)

from vapi_bridge.store import Store


def _make_store():
    tmp = tempfile.mkdtemp()
    db = os.path.join(tmp, "test_phase73.db")
    st = Store(db)
    # Insert a device so FK constraints pass
    st.upsert_device("0xdevice01", "pubkey_hex_01")
    return st


def _run(coro):
    """Run a coroutine in a new event loop (test helper)."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


class TestCeremonyEnrichmentStore(unittest.TestCase):
    """test_4: agent_rulings table accepts ceremony_integrity JSON column."""

    def test_4_agent_rulings_accepts_ceremony_integrity_column(self):
        """test_4: insert_agent_ruling stores ceremony_integrity JSON."""
        store = _make_store()
        ceremony_data = {
            "on_chain_match": True,
            "contributor_count": 3,
            "beacon_block_number": 41723255,
            "error": None,
        }
        ruling_id = store.insert_agent_ruling(
            device_id="0xdevice01",
            verdict="FLAG",
            confidence=0.45,
            reasoning="Test ruling with ceremony enrichment",
            evidence_json='{"test": true}',
            commitment_hash="0x" + "ab" * 32,
            ceremony_integrity=json.dumps(ceremony_data),
        )
        self.assertGreater(ruling_id, 0)

        row = store.get_agent_ruling_by_id(ruling_id)
        self.assertIsNotNone(row)
        stored = json.loads(row["ceremony_integrity"])
        self.assertTrue(stored["on_chain_match"])
        self.assertEqual(stored["contributor_count"], 3)
        self.assertEqual(stored["beacon_block_number"], 41723255)


class TestCeremonyEnrichmentAdjudicator(unittest.TestCase):
    """Tests 1–3: SessionAdjudicator ceremony call behaviour."""

    def _make_adjudicator(self, cfg_overrides=None):
        from vapi_bridge.session_adjudicator import SessionAdjudicator
        store = _make_store()
        cfg = MagicMock()
        cfg.ceremony_registry_address = "0xCeremonyRegistry"
        cfg.iotex_rpc_url = "https://babel-api.testnet.iotex.io"
        cfg.agent_dry_run_mode = True
        if cfg_overrides:
            for k, v in cfg_overrides.items():
                setattr(cfg, k, v)
        adj = SessionAdjudicator(cfg, store)
        return adj, store

    def test_1_evidence_includes_ceremony_on_chain_match(self):
        """test_1: When ceremony matches, evidence does NOT flag integrity_failed."""
        adj, store = self._make_adjudicator()

        # Mock _get_ceremony_integrity to return success
        ceremony_ok = {
            "on_chain_match": True,
            "contributor_count": 3,
            "beacon_block_number": 41723255,
            "error": None,
        }

        # Build a fake ruling_request event
        import time as _time
        event = {
            "id": 1,
            "event_type": "ruling_request",
            "payload_json": json.dumps({
                "device_id": "0xdevice01",
                "attestation_hash": "0x" + "aa" * 32,
            }),
        }

        # Stub store methods to return minimal data
        store.read_unconsumed_events = MagicMock(return_value=[event])
        store.get_enrollment = MagicMock(return_value={"status": "pending", "avg_humanity": 0.7})
        store.get_device_risk_label = MagicMock(return_value={"risk_label": "stable"})
        store.get_recent_records = MagicMock(return_value=[])
        store.get_l6b_baseline = MagicMock(return_value={"probe_count": 0})
        store.write_agent_event = MagicMock()
        store.mark_event_consumed = MagicMock()

        # Mock LLM ruling
        adj._llm_ruling = AsyncMock(return_value=("FLAG", 0.05, "No anomalies"))
        adj._get_ceremony_integrity = AsyncMock(return_value=ceremony_ok)

        _run(adj._process_ruling_request(event))

        # ceremony_integrity_failed should NOT be in evidence_summary
        # Verify by checking what was stored
        rulings = store.get_agent_rulings("0xdevice01")
        self.assertEqual(len(rulings), 1)
        evidence = json.loads(rulings[0]["evidence_json"])
        self.assertNotIn("ceremony_integrity_failed", evidence)

        # ceremony_integrity should be stored
        stored_ceremony = json.loads(rulings[0]["ceremony_integrity"])
        self.assertTrue(stored_ceremony["on_chain_match"])

    def test_2_ceremony_unreachable_proceeds_normally(self):
        """test_2: Unreachable registry → evidence has error field, ruling still proceeds."""
        adj, store = self._make_adjudicator()

        ceremony_error = {
            "on_chain_match": False,
            "contributor_count": 0,
            "beacon_block_number": 0,
            "error": "Connection refused: ceremony registry unreachable",
        }

        event = {
            "id": 2,
            "event_type": "ruling_request",
            "payload_json": json.dumps({
                "device_id": "0xdevice01",
                "attestation_hash": "0x" + "bb" * 32,
            }),
        }

        store.get_enrollment = MagicMock(return_value={})
        store.get_device_risk_label = MagicMock(return_value={})
        store.get_recent_records = MagicMock(return_value=[])
        store.get_l6b_baseline = MagicMock(return_value={})
        store.write_agent_event = MagicMock()
        store.mark_event_consumed = MagicMock()

        adj._llm_ruling = AsyncMock(return_value=("FLAG", 0.05, "No anomalies"))
        adj._get_ceremony_integrity = AsyncMock(return_value=ceremony_error)

        # Should NOT raise — failure is graceful
        _run(adj._process_ruling_request(event))

        rulings = store.get_agent_rulings("0xdevice01")
        self.assertEqual(len(rulings), 1)

        stored_ceremony = json.loads(rulings[0]["ceremony_integrity"])
        self.assertIsNotNone(stored_ceremony.get("error"))
        self.assertFalse(stored_ceremony["on_chain_match"])

        # Ruling should be stored normally (error in ceremony doesn't block ruling)
        self.assertEqual(rulings[0]["verdict"], "FLAG")

    def test_3_on_chain_mismatch_flags_ceremony_integrity_failed(self):
        """test_3: on_chain_match=False without error → evidence gets ceremony_integrity_failed=True."""
        adj, store = self._make_adjudicator()

        # Mismatch (no error, but match=False — ceremony key tampered)
        ceremony_mismatch = {
            "on_chain_match": False,
            "contributor_count": 3,
            "beacon_block_number": 41723255,
            "error": None,
        }

        event = {
            "id": 3,
            "event_type": "ruling_request",
            "payload_json": json.dumps({
                "device_id": "0xdevice01",
                "attestation_hash": "0x" + "cc" * 32,
            }),
        }

        store.get_enrollment = MagicMock(return_value={})
        store.get_device_risk_label = MagicMock(return_value={})
        store.get_recent_records = MagicMock(return_value=[])
        store.get_l6b_baseline = MagicMock(return_value={})
        store.write_agent_event = MagicMock()
        store.mark_event_consumed = MagicMock()

        adj._llm_ruling = AsyncMock(return_value=("FLAG", 0.05, "Ceremony mismatch"))
        adj._get_ceremony_integrity = AsyncMock(return_value=ceremony_mismatch)

        _run(adj._process_ruling_request(event))

        rulings = store.get_agent_rulings("0xdevice01")
        self.assertEqual(len(rulings), 1)

        evidence = json.loads(rulings[0]["evidence_json"])
        # ceremony_integrity_failed must be set in evidence when mismatch without error
        self.assertTrue(evidence.get("ceremony_integrity_failed", False))


if __name__ == "__main__":
    unittest.main()
