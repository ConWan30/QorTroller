"""
Phase 129 — Separation Ratio Breakthrough Monitor SDK (4 tests)

test_1_SeparationBreakthroughResult_slots_5_fields
test_2_VAPISeparationBreakthrough_init_no_raise
test_3_bad_url_returns_error_not_none
test_4_error_path_all_zero_defaults
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from vapi_sdk import SeparationBreakthroughResult, VAPISeparationBreakthrough, SDK_VERSION


class TestPhase129SeparationBreakthroughSDK(unittest.TestCase):

    # ------------------------------------------------------------------
    # test_1: SeparationBreakthroughResult has exactly 5 slots
    # ------------------------------------------------------------------
    def test_1_SeparationBreakthroughResult_slots_5_fields(self):
        expected = {
            "breakthrough_detected", "breakthrough_ratio",
            "breakthrough_ts", "n_players", "error",
        }
        self.assertEqual(set(SeparationBreakthroughResult.__slots__), expected)

    # ------------------------------------------------------------------
    # test_2: VAPISeparationBreakthrough initialises without raising
    # ------------------------------------------------------------------
    def test_2_VAPISeparationBreakthrough_init_no_raise(self):
        client = VAPISeparationBreakthrough("http://localhost:18080", "k")
        self.assertIsNotNone(client)

    # ------------------------------------------------------------------
    # test_3: bad URL → get_breakthrough() returns error != None (never raises)
    # ------------------------------------------------------------------
    def test_3_bad_url_returns_error_not_none(self):
        client = VAPISeparationBreakthrough("http://localhost:0", "k", timeout=2)
        result = client.get_breakthrough()
        self.assertIsInstance(result, SeparationBreakthroughResult)
        self.assertIsNotNone(result.error)

    # ------------------------------------------------------------------
    # test_4: error path → all-zero defaults
    # ------------------------------------------------------------------
    def test_4_error_path_all_zero_defaults(self):
        client = VAPISeparationBreakthrough("http://localhost:0", "k", timeout=2)
        result = client.get_breakthrough()
        self.assertFalse(result.breakthrough_detected)
        self.assertEqual(result.breakthrough_ratio, 0.0)
        self.assertEqual(result.breakthrough_ts, 0.0)
        self.assertEqual(result.n_players, 0)


if __name__ == "__main__":
    unittest.main()
