"""Phase 108 — Tournament Readiness SDK tests.

Tests:
  test_1  TournamentReadinessResult.__slots__ has all 11 fields
  test_2  VAPITournamentReadiness.__init__ sets _base_url (rstrip('/')) and _api_key
  test_3  get_scorecard() never raises on bad URL; returns TournamentReadinessResult with error!=None
  test_4  get_scorecard() result has separation_ratio_current=0.362 and fully_ready=False on error

SDK count: 113 -> 117 (+4)
"""
import sys
import os
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from vapi_sdk import TournamentReadinessResult, VAPITournamentReadiness


class TestPhase108TournamentReadinessSDK(unittest.TestCase):

    def test_1_tournament_readiness_result_slots(self):
        """TournamentReadinessResult.__slots__ has all 11 required fields."""
        slots = set(TournamentReadinessResult.__slots__)
        required = {
            "software_conditions_met", "software_conditions_total",
            "hardware_conditions_met", "hardware_conditions_total",
            "separation_ratio_current", "separation_ratio_required",
            "fully_ready", "blocking_conditions",
            "ready_for_live", "pmi", "error",
        }
        self.assertEqual(slots, required, f"Unexpected slots: {slots ^ required}")

    def test_2_tournament_readiness_init(self):
        """VAPITournamentReadiness.__init__ sets _base_url with rstrip('/') and _api_key."""
        tr = VAPITournamentReadiness("http://localhost:8080/", "mykey108")
        self.assertEqual(tr._base_url, "http://localhost:8080")
        self.assertEqual(tr._api_key, "mykey108")

    def test_3_get_scorecard_never_raises_bad_url(self):
        """get_scorecard() returns TournamentReadinessResult with error!=None on bad URL."""
        tr = VAPITournamentReadiness("http://127.0.0.1:19998", "badkey")
        result = tr.get_scorecard()
        self.assertIsInstance(result, TournamentReadinessResult)
        self.assertIsNotNone(result.error)
        self.assertFalse(result.fully_ready)

    def test_4_get_scorecard_default_values_on_error(self):
        """get_scorecard() returns separation_ratio_current=0.362 and fully_ready=False on error."""
        tr = VAPITournamentReadiness("http://127.0.0.1:19998", "badkey")
        result = tr.get_scorecard()
        self.assertAlmostEqual(result.separation_ratio_current, 0.362, places=3)
        self.assertFalse(result.fully_ready)
        self.assertEqual(result.software_conditions_met, 0)
        self.assertEqual(result.hardware_conditions_met, 0)
        self.assertIsInstance(result.blocking_conditions, list)
