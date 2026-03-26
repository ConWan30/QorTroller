"""
Phase 72 — PHGCredential Bridge-Layer Multi-Sig Tests (8 tests)

Tests the pending_suspensions multi-sig flow:
  test_1: propose_suspension inserts to pending_suspensions
  test_2: confirm_suspension increments confirmation count
  test_3: execute requires threshold met (threshold=2 fails at confirmations=1)
  test_4: execute calls chain.suspend when threshold met (threshold=1 via REST mock)
  test_5: execute rejects expired proposals
  test_6: threshold=1 (default) allows immediate execution
  test_7: GET suspension proposal returns correct state
  test_8: confirm on already-executed proposal raises ValueError

NOTE: PHGCredential.bridge is immutable post-deploy — the multi-sig is a software
safeguard at the bridge (Python) layer, not cryptographic enforcement.
"""

import asyncio
import sys
import time
import tempfile
import os
import types
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

BRIDGE_DIR = Path(__file__).parents[1]
sys.path.insert(0, str(BRIDGE_DIR))

# Stub heavy optional dependencies (same pattern as other bridge tests)
for _mod in ["web3", "web3.exceptions", "eth_account", "eth_account.signers.local",
             "anthropic"]:
    if _mod not in sys.modules:
        sys.modules[_mod] = types.ModuleType(_mod)

from vapi_bridge.store import Store


def _make_store():
    tmp = tempfile.mkdtemp()
    db = os.path.join(tmp, "test_phase72.db")
    return Store(db)


class TestPendingSuspensionsStore(unittest.TestCase):
    """Tests 1–2, 7–8: store.py propose/confirm/get store methods."""

    def setUp(self):
        self.store = _make_store()

    def test_1_propose_suspension_inserts(self):
        """test_1: propose_suspension inserts a row, returns auto-increment id."""
        proposal_id = self.store.propose_suspension(
            device_id="0xdeadbeef",
            evidence_hash="abc123",
            duration_s=86400,
            proposed_by="key_a",
        )
        self.assertIsInstance(proposal_id, int)
        self.assertGreater(proposal_id, 0)

        row = self.store.get_suspension_proposal(proposal_id)
        self.assertIsNotNone(row)
        self.assertEqual(row["device_id"], "0xdeadbeef")
        self.assertEqual(row["evidence_hash"], "abc123")
        self.assertEqual(row["duration_s"], 86400)
        self.assertEqual(row["confirmations"], 0)
        self.assertEqual(row["executed"], 0)

    def test_2_confirm_suspension_increments(self):
        """test_2: confirm_suspension increments confirmation count, returns new count."""
        proposal_id = self.store.propose_suspension(
            device_id="0xdeadbeef",
            evidence_hash="abc123",
            duration_s=86400,
        )
        count1 = self.store.confirm_suspension(proposal_id)
        self.assertEqual(count1, 1)
        count2 = self.store.confirm_suspension(proposal_id)
        self.assertEqual(count2, 2)

        row = self.store.get_suspension_proposal(proposal_id)
        self.assertEqual(row["confirmations"], 2)

    def test_7_get_suspension_proposal_returns_state(self):
        """test_7: get_suspension_proposal returns all fields including expires_at."""
        now = time.time()
        proposal_id = self.store.propose_suspension(
            device_id="0xfeedface",
            evidence_hash="hash_xyz",
            duration_s=3600,
            proposed_by="operator_1",
            expires_in_s=86400.0,
        )
        row = self.store.get_suspension_proposal(proposal_id)
        self.assertEqual(row["device_id"], "0xfeedface")
        self.assertEqual(row["evidence_hash"], "hash_xyz")
        self.assertEqual(row["proposed_by"], "operator_1")
        self.assertAlmostEqual(row["expires_at"], now + 86400.0, delta=5.0)
        self.assertFalse(row["executed"])

    def test_8_confirm_on_executed_raises_value_error(self):
        """test_8: confirm on already-executed proposal raises ValueError."""
        proposal_id = self.store.propose_suspension(
            device_id="0xdeadbeef",
            evidence_hash="abc",
            duration_s=1000,
        )
        self.store.mark_suspension_executed(proposal_id, tx_hash="0xabc")
        with self.assertRaises(ValueError) as ctx:
            self.store.confirm_suspension(proposal_id)
        self.assertIn("already executed", str(ctx.exception))


class TestMultiSigRestEndpoints(unittest.TestCase):
    """Tests 3–6: operator_api.py suspension endpoints via TestClient."""

    def _make_app(self, threshold: int = 1, with_chain: bool = False):
        from vapi_bridge.config import Config
        from vapi_bridge.operator_api import create_operator_app

        cfg = MagicMock(spec=Config)
        cfg.operator_api_key = "test-api-key"
        cfg.rate_limit_per_minute = 9999
        cfg.suspension_multisig_threshold = threshold

        store = _make_store()

        chain = None
        if with_chain:
            chain = MagicMock()
            chain.suspend_phg_credential = AsyncMock(return_value="0xtxhash123")

        app = create_operator_app(cfg, store, chain=chain)
        return app, store

    def _client(self, app):
        from fastapi.testclient import TestClient
        return TestClient(app)

    def test_3_execute_requires_threshold_met(self):
        """test_3: execute returns 400 when confirmations < threshold (threshold=2)."""
        app, store = self._make_app(threshold=2, with_chain=True)
        client = self._client(app)

        # Propose
        resp = client.post(
            "/operator/suspension/propose",
            params={
                "device_id": "0xabc",
                "evidence_hash": "deadbeef" * 8,
                "duration_s": 86400,
                "api_key": "test-api-key",
            },
        )
        self.assertEqual(resp.status_code, 200)
        proposal_id = resp.json()["proposal_id"]
        self.assertEqual(resp.json()["threshold"], 2)

        # Execute without confirming — should fail (confirmations=0 < threshold=2)
        resp = client.post(
            f"/operator/suspension/execute/{proposal_id}",
            params={"api_key": "test-api-key"},
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn("Insufficient confirmations", resp.json()["detail"])

    def test_4_execute_calls_chain_when_threshold_met(self):
        """test_4: execute calls chain.suspend_phg_credential when threshold met."""
        app, store = self._make_app(threshold=1, with_chain=True)
        client = self._client(app)

        # Propose — threshold=1 means 0 confirms needed for execute
        resp = client.post(
            "/operator/suspension/propose",
            params={
                "device_id": "0xbeef",
                "evidence_hash": "00" * 32,
                "duration_s": 7200,
                "api_key": "test-api-key",
            },
        )
        self.assertEqual(resp.status_code, 200)
        proposal_id = resp.json()["proposal_id"]

        # Execute — threshold=1 and confirmations=0 means NOT ready yet unless
        # threshold means "at least 1 confirmation". Let's confirm first.
        resp = client.post(
            f"/operator/suspension/confirm/{proposal_id}",
            params={"api_key": "test-api-key"},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()["ready_to_execute"])

        # Execute
        resp = client.post(
            f"/operator/suspension/execute/{proposal_id}",
            params={"api_key": "test-api-key"},
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], "executed")
        self.assertEqual(data["tx_hash"], "0xtxhash123")

    def test_5_execute_rejects_expired_proposal(self):
        """test_5: execute returns 400 for expired proposals."""
        app, store = self._make_app(threshold=1, with_chain=True)
        client = self._client(app)

        # Propose a valid proposal (not expired yet)
        proposal_id = store.propose_suspension(
            device_id="0xcafe",
            evidence_hash="ff" * 32,
            duration_s=3600,
            expires_in_s=3600.0,  # valid for 1 hour
        )
        # Confirm to reach threshold=1
        store.confirm_suspension(proposal_id)

        # Now patch time in store to make the proposal look expired at execute time.
        # We directly update expires_at to the past via a raw SQL update.
        import sqlite3
        conn = sqlite3.connect(store._db_path)
        conn.execute("UPDATE pending_suspensions SET expires_at=? WHERE id=?",
                     (time.time() - 1.0, proposal_id))
        conn.commit()
        conn.close()

        resp = client.post(
            f"/operator/suspension/execute/{proposal_id}",
            params={"api_key": "test-api-key"},
        )
        # Expired proposals cannot be executed
        self.assertEqual(resp.status_code, 400)
        self.assertIn("expired", resp.json()["detail"].lower())

    def test_6_threshold_1_allows_single_confirm_execute(self):
        """test_6: With threshold=1, one confirmation → execute succeeds."""
        app, store = self._make_app(threshold=1, with_chain=True)
        client = self._client(app)

        # Propose
        resp = client.post(
            "/operator/suspension/propose",
            params={
                "device_id": "0x1234",
                "evidence_hash": "ab" * 32,
                "duration_s": 3600,
                "api_key": "test-api-key",
            },
        )
        self.assertEqual(resp.status_code, 200)
        proposal_id = resp.json()["proposal_id"]

        # One confirmation
        resp = client.post(
            f"/operator/suspension/confirm/{proposal_id}",
            params={"api_key": "test-api-key"},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()["ready_to_execute"])

        # Execute — single confirmation satisfies threshold=1
        resp = client.post(
            f"/operator/suspension/execute/{proposal_id}",
            params={"api_key": "test-api-key"},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["status"], "executed")


if __name__ == "__main__":
    unittest.main()
