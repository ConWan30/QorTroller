"""
Phase 87 — GateAttestationAnchor On-Chain Publication Tests (4 tests)

test_1_compute_gate_attestation_hash_deterministic
test_2_record_gate_attestation_on_chain_millis_conversion
test_3_anchor_skipped_when_no_address_configured
test_4_anchor_publishes_and_stores_on_chain_tx
"""

import asyncio
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

BRIDGE_DIR = Path(__file__).parents[1]
sys.path.insert(0, str(BRIDGE_DIR))

for _mod in ["web3", "web3.exceptions", "eth_account", "eth_account.signers.local",
             "anthropic"]:
    if _mod not in sys.modules:
        sys.modules[_mod] = MagicMock()

from vapi_bridge.adjudication_warm_up import (
    AdjudicationWarmUpRunner,
    compute_gate_attestation_hash,
)
from vapi_bridge.store import Store


def _make_store() -> Store:
    td = tempfile.mkdtemp()
    return Store(str(Path(td) / "test_p87.db"))


def _make_cfg(anchor_addr="0xDeAdBeEf" * 5, gate_n=100, max_dr=1.0):
    cfg = MagicMock()
    cfg.gate_attestation_anchor_address = anchor_addr
    cfg.validation_gate_n = gate_n
    cfg.validation_max_divergence_rate = max_dr
    cfg.warm_up_batch_size = 1
    cfg.chain_submission_paused = False
    return cfg


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


# ---------------------------------------------------------------------------
# 1. compute_gate_attestation_hash — deterministic + format
# ---------------------------------------------------------------------------

class TestComputeGateAttestationHash(unittest.TestCase):

    def test_1_compute_gate_attestation_hash_deterministic(self):
        """Same inputs produce identical 64-char lowercase hex; different inputs differ."""
        ts_ns = 1_700_000_000_123_456_789
        h1 = compute_gate_attestation_hash(50, 100, 0.05, ts_ns)
        h2 = compute_gate_attestation_hash(50, 100, 0.05, ts_ns)
        self.assertEqual(h1, h2, "Identical inputs must produce identical hash")
        self.assertEqual(len(h1), 64, "SHA-256 hex must be 64 chars")
        self.assertTrue(all(c in "0123456789abcdef" for c in h1), "Must be lowercase hex")

        # Different consecutive_clean → different hash
        h3 = compute_gate_attestation_hash(51, 100, 0.05, ts_ns)
        self.assertNotEqual(h1, h3, "Different consecutive_clean must yield different hash")

        # Different divergence_rate → different hash
        h4 = compute_gate_attestation_hash(50, 100, 0.10, ts_ns)
        self.assertNotEqual(h1, h4, "Different divergence_rate must yield different hash")


# ---------------------------------------------------------------------------
# 2. record_gate_attestation_on_chain — millis conversion
# ---------------------------------------------------------------------------

class TestRecordGateAttestationOnChain(unittest.TestCase):

    def test_2_record_gate_attestation_on_chain_millis_conversion(self):
        """divergence_rate 0.123 is encoded as millis=123 in the on-chain call."""
        # Build a minimal fake chain client
        mock_receipt = MagicMock()
        mock_receipt.status = 1

        mock_tx_hash = MagicMock()
        mock_tx_hash.hex.return_value = "0xdeadbeef" + "00" * 28

        mock_fn = MagicMock()
        mock_fn.build_transaction = AsyncMock(return_value={"gas": 100_000})
        mock_contract_fns = MagicMock()
        mock_contract_fns.recordGateAttestation.return_value = mock_fn

        mock_contract = MagicMock()
        mock_contract.functions = mock_contract_fns

        mock_w3 = MagicMock()
        mock_w3.eth.contract.return_value = mock_contract
        mock_w3.eth.get_transaction_count = AsyncMock(return_value=1)
        mock_w3.eth.send_raw_transaction = AsyncMock(return_value=mock_tx_hash)
        mock_w3.eth.wait_for_transaction_receipt = AsyncMock(return_value=mock_receipt)
        mock_w3.to_checksum_address = lambda x: x

        mock_account = MagicMock()
        mock_account.address = "0x1234"
        # web3.py 7.x: signed_transaction.raw_transaction (snake_case)
        mock_account.sign_transaction = MagicMock(return_value=MagicMock(raw_transaction=b"signed"))

        cfg = _make_cfg(anchor_addr="0xAnchor")
        from vapi_bridge import chain as chain_mod
        client = object.__new__(chain_mod.ChainClient)
        client._cfg = cfg
        client._w3 = mock_w3
        client._account = mock_account

        ts_ns = 1_700_000_000_000_000_000
        attestation_hash_hex = compute_gate_attestation_hash(50, 100, 0.123, ts_ns)

        tx = _run(client.record_gate_attestation_on_chain(
            attestation_hash_hex=attestation_hash_hex,
            consecutive_clean=50,
            gate_n=100,
            divergence_rate=0.123,
            timestamp_ns=ts_ns,
        ))
        self.assertTrue(tx.startswith("0xdeadbeef"))

        # Verify recordGateAttestation was called with divergenceRateMillis=123
        call_args = mock_contract_fns.recordGateAttestation.call_args
        self.assertIsNotNone(call_args, "recordGateAttestation must have been called")
        positional = call_args[0]
        # positional[0]=hash_bytes, [1]=consecutive_clean, [2]=gate_n, [3]=millis, [4]=ts_s
        self.assertEqual(positional[3], 123,
                         f"divergenceRateMillis should be 123, got {positional[3]}")
        self.assertEqual(positional[1], 50,
                         f"consecutiveClean should be 50, got {positional[1]}")
        self.assertEqual(positional[2], 100,
                         f"gateN should be 100, got {positional[2]}")


# ---------------------------------------------------------------------------
# 3. _anchor_gate_on_chain skipped when no address
# ---------------------------------------------------------------------------

class TestAnchorSkippedWhenNoAddress(unittest.TestCase):

    def test_3_anchor_skipped_when_no_address_configured(self):
        """run_warm_up on_chain_published=False when anchor address is empty."""
        store = _make_store()
        cfg = _make_cfg(anchor_addr=None)
        # Override cfg.gate_attestation_anchor_address to None
        cfg.gate_attestation_anchor_address = None

        runner = AdjudicationWarmUpRunner(cfg, store)
        mock_chain = MagicMock()

        report = _run(runner.run_warm_up(device_ids=[], chain=mock_chain))

        self.assertFalse(report["on_chain_published"],
                         "on_chain_published must be False when anchor address not set")
        self.assertIsNone(report["on_chain_tx"])
        # chain.record_gate_attestation_on_chain must NOT have been called
        mock_chain.record_gate_attestation_on_chain.assert_not_called()


# ---------------------------------------------------------------------------
# 4. _anchor_gate_on_chain publishes + inserts SQLite row
# ---------------------------------------------------------------------------

class TestAnchorPublishesAndStores(unittest.TestCase):

    def test_4_anchor_publishes_and_stores_on_chain_tx(self):
        """run_warm_up calls chain + stores gate attestation when address configured."""
        store = _make_store()
        cfg = _make_cfg(anchor_addr="0xAnchorAddress")

        runner = AdjudicationWarmUpRunner(cfg, store)

        fake_tx = "0xfeedcafe" + "00" * 28
        mock_chain = MagicMock()
        mock_chain.record_gate_attestation_on_chain = AsyncMock(return_value=fake_tx)

        report = _run(runner.run_warm_up(device_ids=[], chain=mock_chain))

        self.assertTrue(report["on_chain_published"],
                        "on_chain_published must be True when anchor address set")
        self.assertEqual(report["on_chain_tx"], fake_tx)

        # Verify chain was called with the correct types
        call_kwargs = mock_chain.record_gate_attestation_on_chain.call_args
        self.assertIsNotNone(call_kwargs, "chain method must have been called")
        kwargs = call_kwargs[1] if call_kwargs[1] else {}
        args = call_kwargs[0] if call_kwargs[0] else ()
        # Accept either positional or keyword args
        attestation_hash_hex = kwargs.get("attestation_hash_hex", args[0] if args else None)
        self.assertIsNotNone(attestation_hash_hex)
        self.assertEqual(len(attestation_hash_hex), 64,
                         "attestation_hash_hex must be 64 chars")

        # Verify SQLite row inserted
        rows = store.get_gate_attestations(limit=5)
        self.assertEqual(len(rows), 1, "Exactly one gate attestation row expected in SQLite")
        self.assertEqual(rows[0]["on_chain_tx"], fake_tx)
        self.assertEqual(len(rows[0]["attestation_hash"]), 64)


if __name__ == "__main__":
    unittest.main()
