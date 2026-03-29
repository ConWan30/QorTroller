"""
Phase 122 — VHP Confidence Score Multiplier SDK tests (4 tests).

1. ConfidenceMultiplierResult.__slots__ has exactly 6 fields; all named fields present
2. VAPIConfidenceMultiplier("http://localhost:18080", "test-key") initializes without raising
3. get_status() bad URL (port 1) → ConfidenceMultiplierResult with error != None
4. error entry → multiplier_enabled=False, effective_multiplier=1.0, log_count=0
"""
from __future__ import annotations

import sys
import os
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from sdk.vapi_sdk import ConfidenceMultiplierResult, VAPIConfidenceMultiplier, SDK_VERSION


class TestConfidenceMultiplierSDK(unittest.TestCase):

    def test_result_slots_and_fields(self):
        slots = ConfidenceMultiplierResult.__slots__
        self.assertEqual(len(slots), 6)
        required = {
            "multiplier_enabled", "current_bt_strat_ratio",
            "effective_multiplier", "floor", "log_count", "error",
        }
        for f in required:
            self.assertIn(f, slots, f"Missing slot: {f}")

    def test_init_no_raise(self):
        cm = VAPIConfidenceMultiplier("http://localhost:18080", "test-key")
        self.assertIsNotNone(cm)

    def test_bad_url_returns_error_result(self):
        cm = VAPIConfidenceMultiplier("http://localhost:1", "test-key")
        result = cm.get_status()
        self.assertIsInstance(result, ConfidenceMultiplierResult)
        self.assertIsNotNone(result.error)

    def test_error_result_safe_defaults(self):
        cm = VAPIConfidenceMultiplier("http://localhost:1", "test-key")
        result = cm.get_status()
        self.assertFalse(result.multiplier_enabled)
        self.assertAlmostEqual(result.effective_multiplier, 1.0)
        self.assertEqual(result.log_count, 0)
        self.assertAlmostEqual(result.current_bt_strat_ratio, -1.0)
        self.assertAlmostEqual(result.floor, 0.0)


if __name__ == "__main__":
    unittest.main()
