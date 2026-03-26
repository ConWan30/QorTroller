"""Phase 104 — ProtocolMaturityResult + VAPIProtocolMaturity SDK tests.

Tests:
  test_1  ProtocolMaturityResult.__slots__ has all 9 fields
  test_2  VAPIProtocolMaturity.__init__ sets _base_url and _api_key
  test_3  get_maturity() never raises bad URL; returns ProtocolMaturityResult with error
  test_4  commit_activation() returns dict with 'committed' key; never raises bad URL

SDK count: 99 -> 103 (+4)
"""
import sys
import os
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from vapi_sdk import ProtocolMaturityResult, VAPIProtocolMaturity


class TestProtocolMaturitySDK(unittest.TestCase):

    def test_1_protocol_maturity_result_slots(self):
        """ProtocolMaturityResult.__slots__ has all 9 required fields."""
        slots = set(ProtocolMaturityResult.__slots__)
        required = {
            "pmi", "pmi_label", "activation_committed", "committed_at",
            "dry_run_active", "is_simulation", "days_until_vhp_expiry",
            "vhp_found", "error",
        }
        for field in required:
            self.assertIn(field, slots, f"Missing slot: {field}")

    def test_2_vapi_protocol_maturity_init(self):
        """VAPIProtocolMaturity.__init__ sets _base_url (rstrip('/')) and _api_key."""
        client = VAPIProtocolMaturity("http://localhost:8080/", "mykey")
        self.assertEqual(client._base_url, "http://localhost:8080")
        self.assertEqual(client._api_key, "mykey")

    def test_3_get_maturity_never_raises_bad_url(self):
        """get_maturity() never raises on bad URL; returns ProtocolMaturityResult with error."""
        client = VAPIProtocolMaturity("http://localhost:19999", "badkey")
        result = client.get_maturity()
        self.assertIsInstance(result, ProtocolMaturityResult)
        self.assertIsNotNone(result.error)
        self.assertEqual(result.pmi, 0)

    def test_4_commit_activation_never_raises_bad_url(self):
        """commit_activation() returns dict with 'committed' key; never raises on bad URL."""
        client = VAPIProtocolMaturity("http://localhost:19999", "badkey")
        result = client.commit_activation()
        self.assertIsInstance(result, dict)
        self.assertIn("committed", result)
        self.assertFalse(result["committed"])
