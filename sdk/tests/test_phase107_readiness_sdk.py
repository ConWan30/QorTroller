"""Phase 107 — Live Mode Readiness SDK tests.

Tests:
  test_1  LiveModeReadinessResult.__slots__ has all 8 fields
  test_2  VAPILiveModeValidator.__init__ sets _base_url (rstrip('/')) and _api_key
  test_3  run_validation() never raises on bad URL; returns LiveModeReadinessResult with error
  test_4  get_latest() never raises on bad URL; returns LiveModeReadinessResult with error

SDK count: 109 -> 113 (+4)
"""
import sys
import os
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from vapi_sdk import LiveModeReadinessResult, VAPILiveModeValidator


class TestPhase107ReadinessSDK(unittest.TestCase):

    def test_1_live_mode_readiness_result_slots(self):
        """LiveModeReadinessResult.__slots__ has all 8 required fields."""
        slots = set(LiveModeReadinessResult.__slots__)
        required = {
            "n_tested", "false_positive_count", "false_positive_rate",
            "activation_committed", "pmi", "dry_run_active",
            "ready_for_live", "error",
        }
        self.assertEqual(slots, required, f"Unexpected slots: {slots ^ required}")

    def test_2_validator_init(self):
        """VAPILiveModeValidator.__init__ sets _base_url with rstrip('/') and _api_key."""
        v = VAPILiveModeValidator("http://localhost:8080/", "mykey107")
        self.assertEqual(v._base_url, "http://localhost:8080")
        self.assertEqual(v._api_key, "mykey107")

    def test_3_run_validation_never_raises_bad_url(self):
        """run_validation() returns LiveModeReadinessResult with error!=None on bad URL."""
        v = VAPILiveModeValidator("http://127.0.0.1:19999", "badkey")
        result = v.run_validation(n=5)
        self.assertIsInstance(result, LiveModeReadinessResult)
        self.assertIsNotNone(result.error)
        self.assertEqual(result.n_tested, 0)
        self.assertFalse(result.ready_for_live)

    def test_4_get_latest_never_raises_bad_url(self):
        """get_latest() returns LiveModeReadinessResult with error!=None on bad URL."""
        v = VAPILiveModeValidator("http://127.0.0.1:19999", "badkey")
        result = v.get_latest()
        self.assertIsInstance(result, LiveModeReadinessResult)
        self.assertIsNotNone(result.error)
        self.assertFalse(result.ready_for_live)
