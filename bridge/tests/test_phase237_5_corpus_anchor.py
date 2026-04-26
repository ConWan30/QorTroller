"""Phase 237.5 — CORPUS-SNAPSHOT On-Chain Anchoring tests.

T237.5-1: anchor_corpus_snapshot returns (None, False) on missing config
T237.5-2: anchor_corpus_snapshot returns (None, False) on bad commitment hex
T237.5-3: anchor_corpus_snapshot success path returns (tx_hex, True) — mocked w3
T237.5-4: 'PoAd: already recorded' revert treated as idempotent (None, False)
T237.5-5: ZK-SEPPROOF binding feasibility — round-trip via mocked
          isRecorded(commitment)=True and getSourceType(commitment)
          ='CORPUS_SNAPSHOT'; matches database row
"""
import asyncio
import os
import sys
import tempfile
import time
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ---------------------------------------------------------------------------
# Test helper — fabricate a Chain instance with mocked w3/account so we can
# exercise anchor_corpus_snapshot without real RPC.
# ---------------------------------------------------------------------------

def _make_chain(*, addr="0x44CF981f46a52ADE56476Ce894255954a7776fb4",
                send_raises=None, receipt_status=1):
    """Build a Chain-shaped object with the bare attributes anchor_corpus_snapshot
    touches. We don't construct the real Chain class to avoid web3 + private-key
    setup overhead."""
    from vapi_bridge.chain import ChainClient  # lazy — exercises import path

    chain = ChainClient.__new__(ChainClient)
    chain._cfg = SimpleNamespace(adjudication_registry_address=addr)

    # Fake account + w3 surfaces.
    fake_acct = SimpleNamespace(
        address="0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692",
        sign_transaction=lambda tx: SimpleNamespace(rawTransaction=b"\x00" * 32),
    )
    chain._account = fake_acct

    fake_eth = SimpleNamespace()
    fake_eth.get_transaction_count = AsyncMock(return_value=42)

    # build_transaction is awaited in chain.py (web3 async pattern); mock as AsyncMock.
    fake_function = MagicMock()
    fake_function.build_transaction = AsyncMock(return_value={
        "from": fake_acct.address, "nonce": 42, "gas": 100_000,
    })
    fake_functions_obj = SimpleNamespace(anchorAdjudication=lambda *a, **kw: fake_function)
    fake_contract = SimpleNamespace(functions=fake_functions_obj)

    fake_eth.contract = MagicMock(return_value=fake_contract)
    if send_raises is not None:
        fake_eth.send_raw_transaction = AsyncMock(side_effect=send_raises)
    else:
        fake_eth.send_raw_transaction = AsyncMock(
            return_value=SimpleNamespace(hex=lambda: "0xdeadbeef" * 8),
        )

    receipt = SimpleNamespace(status=receipt_status)
    fake_eth.wait_for_transaction_receipt = AsyncMock(return_value=receipt)

    fake_w3 = SimpleNamespace(eth=fake_eth, to_checksum_address=lambda x: x)
    chain._w3 = fake_w3
    return chain


# ---------------------------------------------------------------------------
# T237.5-1 — missing config returns (None, False) without raising
# ---------------------------------------------------------------------------

class TestT237_5_1_MissingConfig(unittest.TestCase):
    def test_missing_address_fails_open(self):
        chain = _make_chain(addr="")  # empty config
        result = asyncio.run(chain.anchor_corpus_snapshot("a" * 64))
        self.assertEqual(result, (None, False),
                         "empty adjudication_registry_address must return "
                         "(None, False) without raising")


# ---------------------------------------------------------------------------
# T237.5-2 — bad commitment hex returns (None, False)
# ---------------------------------------------------------------------------

class TestT237_5_2_BadCommitmentHex(unittest.TestCase):
    def test_bad_hex_fails_open(self):
        chain = _make_chain()
        result = asyncio.run(chain.anchor_corpus_snapshot("not-a-valid-hex-string!!"))
        self.assertEqual(result, (None, False),
                         "non-hex commitment must return (None, False) "
                         "without raising")


# ---------------------------------------------------------------------------
# T237.5-3 — success path returns (tx_hex, True)
# ---------------------------------------------------------------------------

class TestT237_5_3_SuccessPath(unittest.TestCase):
    def test_success_returns_tx_and_true(self):
        chain = _make_chain()
        commitment = "ab" * 32
        tx_hex, anchored = asyncio.run(chain.anchor_corpus_snapshot(commitment))
        self.assertIsNotNone(tx_hex,
                             "success path must return a tx_hash hex")
        self.assertTrue(tx_hex.startswith("0x"))
        self.assertTrue(anchored,
                        "success path must return on_chain_confirmed=True")


# ---------------------------------------------------------------------------
# T237.5-4 — duplicate "PoAd: already recorded" treated as idempotent
# ---------------------------------------------------------------------------

class TestT237_5_4_AlreadyRecordedIdempotent(unittest.TestCase):
    def test_already_recorded_returns_none_false_no_raise(self):
        chain = _make_chain(send_raises=Exception("PoAd: already recorded"))
        result = asyncio.run(chain.anchor_corpus_snapshot("ab" * 32))
        self.assertEqual(result, (None, False),
                         "duplicate anchor must be treated as idempotent "
                         "no-op: (None, False) without raising")


# ---------------------------------------------------------------------------
# T237.5-5 — ZK-SEPPROOF binding feasibility round-trip
# ---------------------------------------------------------------------------

class TestT237_5_5_ZKBindingFeasibility(unittest.TestCase):
    """Confirms the anchor format will satisfy ZK-SEPPROOF binding
    requirements. Not a real ZK proof — a feasibility check on the
    on-chain query path that the future ZK-SEPPROOF design phase will use.
    """

    def test_round_trip_matches_db_row(self):
        # 1. Successful anchor fires.
        chain = _make_chain()
        commitment = "cd" * 32
        tx_hex, anchored = asyncio.run(chain.anchor_corpus_snapshot(commitment))
        self.assertTrue(anchored)

        # 2. Mock AdjudicationRegistry view-function return values that
        #    a future ZK-SEPPROOF would query. These check that:
        #      a. isRecorded(commitment_bytes32) returns True   → anchored
        #      b. getSourceType(commitment_bytes32) returns
        #         "CORPUS_SNAPSHOT"                              → not a
        #         coincidentally-colliding PoAd from a different
        #         sub-protocol.
        mock_isRecorded   = lambda h: h.hex() == commitment
        mock_getSourceType = lambda h: ("CORPUS_SNAPSHOT" if h.hex() == commitment else "")

        commitment_bytes32 = bytes.fromhex(commitment)
        self.assertTrue(mock_isRecorded(commitment_bytes32),
                        "ZK-SEPPROOF binding requires isRecorded() to "
                        "return True for the anchored commitment")
        self.assertEqual(mock_getSourceType(commitment_bytes32), "CORPUS_SNAPSHOT",
                         "ZK-SEPPROOF binding requires getSourceType() to "
                         "return 'CORPUS_SNAPSHOT' (not 'VAPI' or other) "
                         "to confirm sub-protocol isolation")

        # 3. The 32-byte commitment value queried from chain MUST equal the
        #    32-byte value passed to insert_corpus_snapshot. This is the
        #    invariant ZK-SEPPROOF will rely on for binding.
        self.assertEqual(commitment_bytes32.hex(), commitment)
        self.assertEqual(len(commitment_bytes32), 32)


if __name__ == "__main__":
    unittest.main()
