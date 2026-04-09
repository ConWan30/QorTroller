"""Phase 163 SDK tests — SeparationRatioCommitResult + VAPISeparationRatioCommit.

4 tests → SDK 289 → 293.
"""

import unittest
import sys, os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from sdk.vapi_sdk import (
    SDK_VERSION,
    SeparationRatioCommitResult,
    VAPISeparationRatioCommit,
)


class TestPhase163SDK(unittest.TestCase):

    def test_separation_ratio_commit_result_slots(self):
        """SeparationRatioCommitResult has 7 expected slots."""
        r = SeparationRatioCommitResult(
            committed   = False,
            commit_hash = "a" * 64,
            n_consented = 10,
            n_sessions  = 11,
            n_players   = 3,
            dry_run     = True,
            error       = None,
        )
        self.assertFalse(r.committed)
        self.assertEqual(len(r.commit_hash), 64)
        self.assertEqual(r.n_consented, 10)
        self.assertEqual(r.n_sessions, 11)
        self.assertEqual(r.n_players, 3)
        self.assertTrue(r.dry_run)
        self.assertIsNone(r.error)

    def test_vapi_separation_ratio_commit_init(self):
        """VAPISeparationRatioCommit initialises without error."""
        client = VAPISeparationRatioCommit("http://localhost:8765", api_key="testkey163")
        self.assertIn("localhost", client._base)

    def test_commit_bad_url_never_raises(self):
        """VAPISeparationRatioCommit.commit() never raises — returns error default."""
        client = VAPISeparationRatioCommit("http://no-such-host-vapi-163.local")
        result = client.commit(ratio=1.261, n_sessions=11, n_players=3, players_sorted="P1,P2,P3")
        self.assertIsInstance(result, SeparationRatioCommitResult)
        self.assertIsNotNone(result.error)
        self.assertFalse(result.committed)
        self.assertTrue(result.dry_run)

    def test_sdk_version_is_phase163(self):
        """SDK_VERSION reflects Phase 163."""
        self.assertEqual(SDK_VERSION, "3.0.0-phase166")


if __name__ == "__main__":
    unittest.main()
