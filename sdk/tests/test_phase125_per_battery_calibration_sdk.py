"""
Phase 125 — Per-Battery Calibration SDK Tests (4 tests)

test_1_calibration_apply_result_has_5_slots
test_2_vapi_calibration_apply_init_without_raise
test_3_bad_url_returns_error
test_4_error_path_defaults
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from vapi_sdk import CalibrationApplyResult, VAPICalibrationApply


class TestCalibrationApplyResultSlots(unittest.TestCase):
    def test_1_calibration_apply_result_has_5_slots(self):
        slots = CalibrationApplyResult.__dataclass_fields__
        self.assertEqual(len(slots), 5)
        expected = {"battery_type", "anomaly_threshold", "continuity_threshold", "n_sessions", "error"}
        self.assertEqual(set(slots.keys()), expected)


class TestVAPICalibrationApplyInit(unittest.TestCase):
    def test_2_vapi_calibration_apply_init_without_raise(self):
        client = VAPICalibrationApply("http://localhost:18080", "test-key")
        self.assertIsNotNone(client)


class TestBadUrlReturnsError(unittest.TestCase):
    def test_3_bad_url_returns_error(self):
        client = VAPICalibrationApply("http://127.0.0.1:1", "k")
        result = client.apply(
            battery_type="touchpad",
            anomaly_threshold=7.5,
            continuity_threshold=5.5,
            n_sessions=40,
        )
        self.assertIsInstance(result, CalibrationApplyResult)
        self.assertIsNotNone(result.error)


class TestErrorPathDefaults(unittest.TestCase):
    def test_4_error_path_defaults(self):
        client = VAPICalibrationApply("http://127.0.0.1:1", "k")
        result = client.apply(
            battery_type="trigger",
            anomaly_threshold=7.0,
            continuity_threshold=5.0,
        )
        self.assertEqual(result.battery_type, "")
        self.assertEqual(result.anomaly_threshold, 0.0)
        self.assertEqual(result.continuity_threshold, 0.0)
        self.assertEqual(result.n_sessions, 0)
        self.assertIsNotNone(result.error)


if __name__ == "__main__":
    unittest.main()
