"""Phase O4-VPM-ANCHOR — chain.anchor_vpm() bridge-side client tests.

Validates the bridge-side helper that calls VPMAnchorRegistry.anchorVPM
on the deployed contract. Mirrors the test pattern from
test_phase237_5_corpus_anchor.py with mocked w3/account.

T-VPM-ANCHOR-1: kill-switch held -> (None, False); no RPC contact
T-VPM-ANCHOR-2: missing config (empty address) -> (None, False)
T-VPM-ANCHOR-3: missing account (no bridge key) -> (None, False)
T-VPM-ANCHOR-4: bad hex input -> (None, False)
T-VPM-ANCHOR-5: zero hashes rejected upfront -> (None, False)
T-VPM-ANCHOR-6: bad ts_ns type -> (None, False)
T-VPM-ANCHOR-7: success path -> (tx_hex, True)
T-VPM-ANCHOR-8: tx revert (status != 1) -> (None, False)
T-VPM-ANCHOR-9: 'VPM: already anchored' treated as idempotent -> (None, False)
T-VPM-ANCHOR-10: 'VPM: zkba not anchored' fail-open -> (None, False)
T-VPM-ANCHOR-11: ABI literal pinned (FROZEN regression guard)
"""
import os
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


VPM_ANCHOR_ADDR = "0xaabbccddeeff00112233445566778899aabbccdd"


def _make_chain(
    *,
    addr=VPM_ANCHOR_ADDR,
    kill_switch=False,
    account_present=True,
    send_raises=None,
    receipt_status=1,
):
    """Build a Chain-shaped object with mocked w3 + account so anchor_vpm
    can run without real RPC. Mirrors test_phase237_5_corpus_anchor
    pattern verbatim."""
    from vapi_bridge.chain import ChainClient

    chain = ChainClient.__new__(ChainClient)
    chain._cfg = SimpleNamespace(
        vpm_anchor_registry_address=addr,
        chain_submission_paused=kill_switch,
    )

    if account_present:
        chain._account = SimpleNamespace(
            address="0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692",
            sign_transaction=lambda tx: SimpleNamespace(
                raw_transaction=b"\x00" * 32
            ),
        )
    else:
        chain._account = None

    fake_eth = SimpleNamespace()
    fake_eth.get_transaction_count = AsyncMock(return_value=42)
    fake_eth.estimate_gas = AsyncMock(return_value=160_000)

    fake_function = MagicMock()
    fake_function.build_transaction = AsyncMock(return_value={
        "from": "0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692",
        "nonce": 42, "gas": 80_000,
    })
    fake_functions_obj = SimpleNamespace(
        anchorVPM=lambda *a, **kw: fake_function
    )
    fake_contract = SimpleNamespace(functions=fake_functions_obj)
    fake_eth.contract = MagicMock(return_value=fake_contract)

    if send_raises is not None:
        fake_eth.send_raw_transaction = AsyncMock(side_effect=send_raises)
    else:
        fake_eth.send_raw_transaction = AsyncMock(
            return_value=SimpleNamespace(hex=lambda: "0x" + "ab" * 32)
        )

    fake_eth.wait_for_transaction_receipt = AsyncMock(
        return_value={"status": receipt_status}
    )

    fake_w3 = SimpleNamespace()
    fake_w3.eth = fake_eth
    fake_w3.to_checksum_address = lambda a: a
    chain._w3 = fake_w3
    return chain


_GOOD_ZKBA = "1649f2803e0e3207f93fb1daac25d71d579ba3150d9d15317b97fe0e65a70d5f"
_GOOD_VPM  = "5b09a65e64f13026461ef5ea7aff701f8840f1c1e5202f60bb8f88a7474da5cb"
_GOOD_TS   = 1778900000000000000


class TestPhaseO4AnchorVPM(unittest.IsolatedAsyncioTestCase):

    async def test_t_vpm_anchor_1_kill_switch_held(self):
        """Kill-switch on -> (None, False); no contract construction."""
        chain = _make_chain(kill_switch=True)
        result = await chain.anchor_vpm(_GOOD_ZKBA, _GOOD_VPM, _GOOD_TS)
        self.assertEqual(result, (None, False))
        # No RPC contact — eth.get_transaction_count never called.
        chain._w3.eth.get_transaction_count.assert_not_called()

    async def test_t_vpm_anchor_2_missing_address(self):
        chain = _make_chain(addr="")
        result = await chain.anchor_vpm(_GOOD_ZKBA, _GOOD_VPM, _GOOD_TS)
        self.assertEqual(result, (None, False))

    async def test_t_vpm_anchor_3_missing_account(self):
        chain = _make_chain(account_present=False)
        result = await chain.anchor_vpm(_GOOD_ZKBA, _GOOD_VPM, _GOOD_TS)
        self.assertEqual(result, (None, False))

    async def test_t_vpm_anchor_4_bad_hex_input(self):
        chain = _make_chain()
        result = await chain.anchor_vpm("not-hex", _GOOD_VPM, _GOOD_TS)
        self.assertEqual(result, (None, False))

    async def test_t_vpm_anchor_5_zero_hashes_rejected(self):
        chain = _make_chain()
        zero_hash = "0" * 64

        # Zero zkba hash
        result1 = await chain.anchor_vpm(zero_hash, _GOOD_VPM, _GOOD_TS)
        self.assertEqual(result1, (None, False))

        # Zero vpm hash
        result2 = await chain.anchor_vpm(_GOOD_ZKBA, zero_hash, _GOOD_TS)
        self.assertEqual(result2, (None, False))

    async def test_t_vpm_anchor_6_bad_ts_ns(self):
        chain = _make_chain()
        # Negative
        result1 = await chain.anchor_vpm(_GOOD_ZKBA, _GOOD_VPM, -1)
        self.assertEqual(result1, (None, False))
        # Over uint64
        result2 = await chain.anchor_vpm(_GOOD_ZKBA, _GOOD_VPM, 2**64)
        self.assertEqual(result2, (None, False))
        # String
        result3 = await chain.anchor_vpm(_GOOD_ZKBA, _GOOD_VPM, "abc")
        self.assertEqual(result3, (None, False))

    async def test_t_vpm_anchor_7_success_path(self):
        chain = _make_chain()
        result = await chain.anchor_vpm(_GOOD_ZKBA, _GOOD_VPM, _GOOD_TS)
        tx_hex, ok = result
        self.assertTrue(ok)
        self.assertIsNotNone(tx_hex)
        self.assertTrue(tx_hex.startswith("0x"))
        # Gas estimate × 1.25 buffer applied (160_000 * 1.25 = 200_000)
        build_tx_kwargs = chain._w3.eth.contract.return_value.functions.anchorVPM.return_value if False else None  # not directly testable from mock

    async def test_t_vpm_anchor_8_tx_revert(self):
        chain = _make_chain(receipt_status=0)
        result = await chain.anchor_vpm(_GOOD_ZKBA, _GOOD_VPM, _GOOD_TS)
        self.assertEqual(result, (None, False))

    async def test_t_vpm_anchor_9_already_anchored_idempotent(self):
        chain = _make_chain(
            send_raises=Exception("execution reverted: VPM: already anchored"),
        )
        result = await chain.anchor_vpm(_GOOD_ZKBA, _GOOD_VPM, _GOOD_TS)
        self.assertEqual(result, (None, False))

    async def test_t_vpm_anchor_10_zkba_not_anchored_fail_open(self):
        chain = _make_chain(
            send_raises=Exception(
                "execution reverted: VPM: zkba not anchored"
            ),
        )
        result = await chain.anchor_vpm(_GOOD_ZKBA, _GOOD_VPM, _GOOD_TS)
        self.assertEqual(result, (None, False))


class TestPhaseO4AnchorVPMFrozen(unittest.TestCase):
    """FROZEN ABI pin — catches accidental selector / arg rename at PR time."""

    def test_t_vpm_anchor_11_abi_literal_frozen(self):
        from vapi_bridge.chain import ChainClient

        # The ABI must be a list of exactly one function descriptor.
        abi = ChainClient._VPM_ANCHOR_ABI
        self.assertEqual(len(abi), 1)
        entry = abi[0]

        # Function name pinned.
        self.assertEqual(entry["name"], "anchorVPM")
        self.assertEqual(entry["type"], "function")
        self.assertEqual(entry["stateMutability"], "nonpayable")

        # Inputs MUST be exactly 3 args in this order with these types.
        # Any reorder is a wire-format break against the deployed contract.
        inputs = entry["inputs"]
        self.assertEqual(len(inputs), 3)
        self.assertEqual(inputs[0]["name"], "zkbaManifestHash")
        self.assertEqual(inputs[0]["type"], "bytes32")
        self.assertEqual(inputs[1]["name"], "vpmManifestHash")
        self.assertEqual(inputs[1]["type"], "bytes32")
        self.assertEqual(inputs[2]["name"], "tsNs")
        self.assertEqual(inputs[2]["type"], "uint64")


if __name__ == "__main__":
    unittest.main()
