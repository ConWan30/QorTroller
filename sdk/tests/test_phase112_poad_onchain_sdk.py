"""
Phase 112 — PoAd On-Chain Anchor SDK tests (4 tests).
SDK 137 -> 141 (+4).
"""
import sys
import os
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class TestPoAdAnchorResultSlots(unittest.TestCase):
    """Test 1: PoAdAnchorResult.__slots__ has exactly 6 fields."""

    def test_slots_6_fields(self):
        from vapi_sdk import PoAdAnchorResult
        slots = PoAdAnchorResult.__slots__
        self.assertEqual(len(slots), 6)
        required = {
            "poad_on_chain_enabled", "anchored_count", "pending_count",
            "last_anchor_tx", "adjudication_registry_address", "error",
        }
        for field in required:
            self.assertIn(field, slots, f"Missing slot: {field}")


class TestVAPIPoAdAnchorInit(unittest.TestCase):
    """Test 2: VAPIPoAdAnchor("http://localhost:18080", "test-key") initializes without raising."""

    def test_init_no_raise(self):
        from vapi_sdk import VAPIPoAdAnchor
        anchor = VAPIPoAdAnchor("http://localhost:18080", "test-key")
        self.assertIsNotNone(anchor)


class TestVAPIPoAdAnchorBadUrl(unittest.TestCase):
    """Test 3: get_anchor_status() bad URL (port 1) -> result with error != None."""

    def test_bad_url_returns_error(self):
        from vapi_sdk import VAPIPoAdAnchor
        anchor = VAPIPoAdAnchor("http://127.0.0.1:1", "test-key")
        result = anchor.get_anchor_status()
        self.assertIsNotNone(result.error)


class TestVAPIPoAdAnchorErrorDefaults(unittest.TestCase):
    """Test 4: error result -> poad_on_chain_enabled=False, anchored_count=0, last_anchor_tx=None."""

    def test_error_defaults(self):
        from vapi_sdk import VAPIPoAdAnchor
        anchor = VAPIPoAdAnchor("http://127.0.0.1:1", "test-key")
        result = anchor.get_anchor_status()
        self.assertFalse(result.poad_on_chain_enabled)
        self.assertEqual(result.anchored_count, 0)
        self.assertIsNone(result.last_anchor_tx)


if __name__ == "__main__":
    unittest.main()
