"""
Phase 67 — SDK Ceremony Integrity Tests (4 tests)

TestSDKVerifyCeremonyIntegrity (4 tests):
  test_1_verify_ceremony_matching_key_returns_true_on_chain_match
  test_2_verify_ceremony_mismatched_key_returns_false_on_chain_match
  test_3_verify_ceremony_missing_address_returns_error_dict_no_raise
  test_4_verify_ceremony_returns_correct_contributor_count
"""

import hashlib
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

SDK_DIR = Path(__file__).parents[1]
sys.path.insert(0, str(SDK_DIR))

from vapi_sdk import VAPIZKProof


def _make_vkey_dict():
    return {"protocol": "groth16", "curve": "bn128", "nPublic": 5, "vk_alpha_1": []}


class _MockResponse:
    """Minimal urllib response mock."""
    def __init__(self, data: dict):
        self._data = json.dumps(data).encode()
    def read(self):
        return self._data
    def __enter__(self):
        return self
    def __exit__(self, *args):
        pass


class TestSDKVerifyCeremonyIntegrity(unittest.TestCase):
    """Phase 67 — VAPIZKProof.verify_ceremony_integrity() static method."""

    def setUp(self):
        self.vkey_dict = _make_vkey_dict()
        self.registry_addr = "0x" + "cc" * 20
        self.rpc_url = "http://localhost:8545"

    def test_1_verify_ceremony_matching_key_returns_true_on_chain_match(self):
        """verify_ceremony_integrity returns on_chain_match=True when eth_call returns True."""
        import urllib.request as _req
        # eth_call returns 0x...1 (True from Solidity bool)
        mock_resp = _MockResponse({"jsonrpc": "2.0", "result": "0x" + "0" * 63 + "1", "id": 1})
        with patch.object(_req, "urlopen", return_value=mock_resp):
            result = VAPIZKProof.verify_ceremony_integrity(
                self.vkey_dict,
                self.registry_addr,
                self.rpc_url,
                "PitlSessionProof",
            )
        self.assertTrue(result["on_chain_match"])
        self.assertIsNone(result["error"])
        self.assertEqual(result["circuit_name"], "PitlSessionProof")
        # local_hash must be a non-empty hex string starting with "0x"
        self.assertTrue(result["local_hash"].startswith("0x"))
        self.assertGreater(len(result["local_hash"]), 2)

    def test_2_verify_ceremony_mismatched_key_returns_false_on_chain_match(self):
        """verify_ceremony_integrity returns on_chain_match=False when eth_call returns False."""
        import urllib.request as _req
        # eth_call returns 0x...0 (False from Solidity bool — hash mismatch)
        mock_resp = _MockResponse({"jsonrpc": "2.0", "result": "0x" + "0" * 64, "id": 1})
        with patch.object(_req, "urlopen", return_value=mock_resp):
            result = VAPIZKProof.verify_ceremony_integrity(
                self.vkey_dict,
                self.registry_addr,
                self.rpc_url,
                "PitlSessionProof",
            )
        self.assertFalse(result["on_chain_match"])
        self.assertIsNone(result["error"])

    def test_3_verify_ceremony_missing_address_returns_error_dict_no_raise(self):
        """verify_ceremony_integrity returns error in dict when address is empty — never raises."""
        result = VAPIZKProof.verify_ceremony_integrity(
            self.vkey_dict,
            "",               # empty address
            self.rpc_url,
            "PitlSessionProof",
        )
        self.assertFalse(result["on_chain_match"])
        self.assertIsNotNone(result["error"])
        self.assertIn("not provided", result["error"])

    def test_4_verify_ceremony_returns_correct_contributor_count(self):
        """verify_ceremony_integrity returns contributor_count from getContributorCount call."""
        import urllib.request as _req

        call_count = [0]

        def mock_urlopen(req, timeout=None):
            call_count[0] += 1
            if call_count[0] == 1:
                # First call: verifyCeremony → True
                return _MockResponse({"jsonrpc": "2.0", "result": "0x" + "0" * 63 + "1", "id": 1})
            else:
                # Second call: getContributorCount → 3
                return _MockResponse({"jsonrpc": "2.0", "result": "0x03", "id": 2})

        with patch.object(_req, "urlopen", side_effect=mock_urlopen):
            result = VAPIZKProof.verify_ceremony_integrity(
                self.vkey_dict,
                self.registry_addr,
                self.rpc_url,
                "PitlSessionProof",
            )
        self.assertTrue(result["on_chain_match"])
        self.assertEqual(result["contributor_count"], 3)
        self.assertIsNone(result["error"])


if __name__ == "__main__":
    unittest.main()
