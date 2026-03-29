"""
Phase 111 — PoAd Registry SDK tests (4 tests).
SDK 133 → 137 (+4).
"""
import sys
import os
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from vapi_sdk import PoAdRegistryResult, VAPIPoAdRegistry


class TestPhase111PoAdRegistrySDK(unittest.TestCase):

    def test_1_poad_registry_result_slots_and_fields(self):
        """PoAdRegistryResult has exactly 8 __slots__ and all required field names."""
        slots = PoAdRegistryResult.__dataclass_fields__
        expected_fields = {
            "poad_registry_enabled",
            "total_poad_count",
            "dual_veto_poad_count",
            "on_chain_anchor_count",
            "adjudication_registry_address",
            "task_spec_registered",
            "is_composable",
            "error",
        }
        self.assertEqual(set(slots.keys()), expected_fields)
        self.assertEqual(len(slots), 8)

    def test_2_vapi_poad_registry_initializes_without_raising(self):
        """VAPIPoAdRegistry(base_url, api_key) initializes without raising."""
        client = VAPIPoAdRegistry("http://localhost:18080", "test-key")
        self.assertIsNotNone(client)

    def test_3_get_poad_status_bad_url_returns_error(self):
        """get_poad_status() with unreachable URL (port 1) returns result with error != None."""
        client = VAPIPoAdRegistry("http://localhost:1", "test-key")
        result = client.get_poad_status()
        self.assertIsInstance(result, PoAdRegistryResult)
        self.assertIsNotNone(result.error)

    def test_4_error_result_has_correct_defaults(self):
        """Error result has poad_registry_enabled=False, is_composable=False, task_spec_registered=True."""
        client = VAPIPoAdRegistry("http://localhost:1", "test-key")
        result = client.get_poad_status()
        self.assertFalse(result.poad_registry_enabled)
        self.assertFalse(result.is_composable)
        self.assertTrue(result.task_spec_registered)
        self.assertEqual(result.total_poad_count, 0)
        self.assertEqual(result.dual_veto_poad_count, 0)
        self.assertEqual(result.on_chain_anchor_count, 0)
        self.assertEqual(result.adjudication_registry_address, "")


if __name__ == "__main__":
    unittest.main()
