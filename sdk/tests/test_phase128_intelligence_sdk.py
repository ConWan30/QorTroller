"""
Phase 128 — Protocol Intelligence Dashboard SDK (4 tests)

test_1_TournamentReadinessScore_slots_8_fields
test_2_VAPITournamentReadinessScore_init_no_raise
test_3_bad_url_returns_error_not_none
test_4_error_path_all_zero_scores
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from vapi_sdk import TournamentReadinessScore, VAPITournamentReadinessScore, SDK_VERSION


class TestPhase128IntelligenceSDK(unittest.TestCase):

    # ------------------------------------------------------------------
    # test_1: TournamentReadinessScore has exactly 8 slots
    # ------------------------------------------------------------------
    def test_1_TournamentReadinessScore_slots_8_fields(self):
        expected = {
            "score", "separation_score", "l4_score",
            "dual_gate_score", "epoch_score", "ioswarm_score",
            "dry_run_score", "error",
        }
        self.assertEqual(set(TournamentReadinessScore.__slots__), expected)

    # ------------------------------------------------------------------
    # test_2: VAPITournamentReadinessScore initialises without raising
    # ------------------------------------------------------------------
    def test_2_VAPITournamentReadinessScore_init_no_raise(self):
        client = VAPITournamentReadinessScore("http://localhost:18080", "k")
        self.assertIsNotNone(client)

    # ------------------------------------------------------------------
    # test_3: bad URL → get_score() returns error != None (never raises)
    # ------------------------------------------------------------------
    def test_3_bad_url_returns_error_not_none(self):
        client = VAPITournamentReadinessScore("http://localhost:0", "k", timeout=2)
        result = client.get_score()
        self.assertIsInstance(result, TournamentReadinessScore)
        self.assertIsNotNone(result.error)

    # ------------------------------------------------------------------
    # test_4: error path yields all-zero float scores
    # ------------------------------------------------------------------
    def test_4_error_path_all_zero_scores(self):
        client = VAPITournamentReadinessScore("http://localhost:0", "k", timeout=2)
        result = client.get_score()
        self.assertEqual(result.score, 0.0)
        self.assertEqual(result.separation_score, 0.0)
        self.assertEqual(result.l4_score, 0.0)
        self.assertEqual(result.dual_gate_score, 0.0)
        self.assertEqual(result.epoch_score, 0.0)
        self.assertEqual(result.ioswarm_score, 0.0)
        self.assertEqual(result.dry_run_score, 0.0)


if __name__ == "__main__":
    unittest.main()
