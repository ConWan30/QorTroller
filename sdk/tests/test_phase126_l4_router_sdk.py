"""
Phase 126 — L4 Router Status SDK Tests (4 tests)

test_1_l4_router_status_result_has_6_slots
test_2_vapil4_router_status_init_without_raise
test_3_bad_url_returns_error
test_4_error_path_defaults
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from vapi_sdk import L4RouterStatusResult, VAPIL4RouterStatus


class TestL4RouterStatusResultSlots(unittest.TestCase):
    def test_1_l4_router_status_result_has_6_slots(self):
        slots = L4RouterStatusResult.__dataclass_fields__
        self.assertEqual(len(slots), 6)
        expected = {
            "l4_battery_threshold_enabled", "total_lookups", "per_battery_lookups",
            "global_fallback_count", "last_battery_type", "error",
        }
        self.assertEqual(set(slots.keys()), expected)


class TestVAPIL4RouterStatusInit(unittest.TestCase):
    def test_2_vapil4_router_status_init_without_raise(self):
        client = VAPIL4RouterStatus("http://localhost:18080", "test-key")
        self.assertIsNotNone(client)


class TestBadUrlReturnsError(unittest.TestCase):
    def test_3_bad_url_returns_error(self):
        client = VAPIL4RouterStatus("http://127.0.0.1:1", "k")
        result = client.get_status()
        self.assertIsInstance(result, L4RouterStatusResult)
        self.assertIsNotNone(result.error)


class TestErrorPathDefaults(unittest.TestCase):
    def test_4_error_path_defaults(self):
        client = VAPIL4RouterStatus("http://127.0.0.1:1", "k")
        result = client.get_status()
        self.assertFalse(result.l4_battery_threshold_enabled)
        self.assertEqual(result.total_lookups, 0)
        self.assertEqual(result.per_battery_lookups, 0)
        self.assertEqual(result.global_fallback_count, 0)
        self.assertEqual(result.last_battery_type, "")
        self.assertIsNotNone(result.error)


if __name__ == "__main__":
    unittest.main()
