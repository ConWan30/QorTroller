"""
Phase 124 — L4 Per-Battery Threshold Track Registry SDK Tests (4 tests)

test_1_l4_threshold_track_result_slots
test_2_vapi_l4_threshold_tracks_init
test_3_get_tracks_bad_url_returns_error
test_4_error_path_defaults
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from vapi_sdk import L4ThresholdTrackResult, VAPIL4ThresholdTracks


class TestL4ThresholdTrackResultSlots(unittest.TestCase):
    def test_1_l4_threshold_track_result_slots(self):
        expected = {
            "l4_battery_threshold_enabled",
            "track_count",
            "active_count",
            "battery_types_tracked",
            "error",
        }
        slots = set(L4ThresholdTrackResult.__slots__)
        self.assertEqual(slots, expected)


class TestVAPIL4ThresholdTracksInit(unittest.TestCase):
    def test_2_vapi_l4_threshold_tracks_init(self):
        obj = VAPIL4ThresholdTracks("http://localhost:18080", "test-key")
        self.assertEqual(obj._base, "http://localhost:18080")
        self.assertEqual(obj._key, "test-key")


class TestGetTracksBadUrlReturnsError(unittest.TestCase):
    def test_3_get_tracks_bad_url_returns_error(self):
        obj = VAPIL4ThresholdTracks("http://127.0.0.1:1", "k")
        result = obj.get_tracks()
        self.assertIsNotNone(result.error)


class TestErrorPathDefaults(unittest.TestCase):
    def test_4_error_path_defaults(self):
        obj = VAPIL4ThresholdTracks("http://127.0.0.1:1", "k")
        result = obj.get_tracks()
        self.assertFalse(result.l4_battery_threshold_enabled)
        self.assertEqual(result.track_count, 0)
        self.assertEqual(result.active_count, 0)
        self.assertEqual(result.battery_types_tracked, [])
        self.assertIsNotNone(result.error)


if __name__ == "__main__":
    unittest.main()
