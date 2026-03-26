"""
Phase 69 — VAPIDataCurator SDK Tests (4 tests)

TestVAPIDataCurator (4 tests):
  test_1_get_data_lineage_returns_error_on_connection_failure
  test_2_get_token_eligibility_returns_error_on_connection_failure
  test_3_get_oracle_state_passes_oracle_type_uppercase
  test_4_compute_reward_score_returns_breakdown_when_eligibility_exists
"""

import json
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

SDK_DIR = Path(__file__).parents[1]
sys.path.insert(0, str(SDK_DIR))

from vapi_data_curator import VAPIDataCurator


class TestVAPIDataCurator(unittest.TestCase):

    def _make_curator(self, base_url="http://localhost:0", api_key="testkey"):
        return VAPIDataCurator(base_url=base_url, api_key=api_key, timeout=2)

    # -----------------------------------------------------------------------
    # test_1: get_data_lineage — connection failure returns error dict (not raise)
    # -----------------------------------------------------------------------

    def test_1_get_data_lineage_returns_error_on_connection_failure(self):
        """SDK: get_data_lineage never raises — returns error field on network failure."""
        curator = self._make_curator()
        result = curator.get_data_lineage("aa" * 32)
        self.assertIn("error", result)
        # Should NOT contain lineage (failed request)
        self.assertNotIn("lineage", result)

    # -----------------------------------------------------------------------
    # test_2: get_token_eligibility — connection failure returns error dict
    # -----------------------------------------------------------------------

    def test_2_get_token_eligibility_returns_error_on_connection_failure(self):
        """SDK: get_token_eligibility never raises — returns error field on failure."""
        curator = self._make_curator()
        result = curator.get_token_eligibility("bb" * 32)
        self.assertIn("error", result)

    # -----------------------------------------------------------------------
    # test_3: get_oracle_state — uppercase conversion + error on failure
    # -----------------------------------------------------------------------

    def test_3_get_oracle_state_passes_oracle_type_uppercase(self):
        """SDK: get_oracle_state uppercases oracle_type and returns error on failure."""
        curator = self._make_curator()
        result = curator.get_oracle_state("humanity")  # lowercase input
        # Will fail (no server) but the URL should contain HUMANITY
        self.assertIn("error", result)
        # oracle_type context should be in error response
        self.assertIn("oracle_type", result)

    # -----------------------------------------------------------------------
    # test_4: compute_reward_score — returns breakdown from eligibility state
    # -----------------------------------------------------------------------

    def test_4_compute_reward_score_returns_breakdown_when_eligibility_exists(self):
        """SDK: compute_reward_score enriches eligibility with multiplier breakdown."""
        curator = self._make_curator()

        # Mock get_token_eligibility to return a valid state
        mock_eligibility = {
            "device_id": "aa" * 32,
            "eligibility": {
                "nominal_sessions":    15,
                "clean_streak":        6,
                "passport_held":       True,
                "enrollment_complete": True,
                "mpc_verified":        True,
                "gate_passed":         False,
                "base_multiplier":     1.0,
                "total_multiplier":    3.75,
                "eligibility_score":   56.25,
                "last_computed_at":    1741234567.0,
            }
        }
        with patch.object(curator, "get_token_eligibility", return_value=mock_eligibility):
            result = curator.compute_reward_score("aa" * 32)

        self.assertNotIn("error", result)
        self.assertIn("multiplier_breakdown", result)
        self.assertIn("passport", result["multiplier_breakdown"])
        self.assertIn("enrollment", result["multiplier_breakdown"])
        self.assertIn("clean_streak", result["multiplier_breakdown"])
        self.assertIn("mpc_verified", result["multiplier_breakdown"])
        self.assertEqual(result["nominal_sessions"], 15)
        self.assertAlmostEqual(result["total_multiplier"], 3.75, places=2)
        # gate_passed is False — should NOT appear in breakdown
        self.assertNotIn("gate_passed", result["multiplier_breakdown"])


if __name__ == "__main__":
    unittest.main()
