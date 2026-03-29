"""
Phase 123 — L4 Calibration Staleness Monitor SDK Tests (4 tests)

test_1_calibration_status_result_slots
test_2_vapi_calibration_status_init
test_3_get_status_bad_url_returns_error
test_4_error_path_stale_true_defaults
"""

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock

SDK_DIR = Path(__file__).parents[1]
sys.path.insert(0, str(SDK_DIR))

for _mod in ["web3", "web3.exceptions", "eth_account", "eth_account.signers.local"]:
    if _mod not in sys.modules:
        sys.modules[_mod] = MagicMock()

from vapi_sdk import CalibrationStatusResult, VAPICalibrationStatus  # noqa: E402


class TestCalibrationStatusResultSlots(unittest.TestCase):

    def test_1_calibration_status_result_slots(self):
        """CalibrationStatusResult has exactly 6 fields."""
        expected = {
            "current_feature_dim",
            "calibration_feature_dim",
            "stale",
            "anomaly_threshold",
            "continuity_threshold",
            "error",
        }
        slots = set(CalibrationStatusResult.__slots__)
        self.assertEqual(slots, expected)

    def test_2_vapi_calibration_status_init(self):
        """VAPICalibrationStatus initializes without raising."""
        obj = VAPICalibrationStatus("http://localhost:18080", "test-key")
        self.assertEqual(obj._base, "http://localhost:18080")
        self.assertEqual(obj._key, "test-key")

    def test_3_get_status_bad_url_returns_error(self):
        """get_status() with unreachable URL returns error not None."""
        obj = VAPICalibrationStatus("http://127.0.0.1:1", "k")
        result = obj.get_status()
        self.assertIsNotNone(result.error)
        self.assertIsInstance(result, CalibrationStatusResult)

    def test_4_error_path_stale_true_defaults(self):
        """On error, stale=True, dims match safe defaults (13/12), thresholds non-zero."""
        obj = VAPICalibrationStatus("http://127.0.0.1:1", "k")
        result = obj.get_status()
        self.assertTrue(result.stale)
        self.assertEqual(result.current_feature_dim, 13)
        self.assertEqual(result.calibration_feature_dim, 12)
        self.assertGreater(result.anomaly_threshold, 0.0)
        self.assertGreater(result.continuity_threshold, 0.0)


if __name__ == "__main__":
    unittest.main()
