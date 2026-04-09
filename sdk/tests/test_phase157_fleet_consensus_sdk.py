"""Phase 157 SDK tests — FleetConsensusSnapshotResult + VAPIFleetConsensus.

4 tests → SDK 265 → 269.
"""

import unittest
from unittest.mock import patch, MagicMock
import sys, os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from sdk.vapi_sdk import (
    SDK_VERSION,
    FleetConsensusSnapshotResult,
    VAPIFleetConsensus,
    EnrollmentAutoGuidanceResult,
)


class TestPhase157SDK(unittest.TestCase):

    def test_fleet_consensus_result_slots(self):
        """FleetConsensusSnapshotResult has 6 expected slots."""
        r = FleetConsensusSnapshotResult(
            fleet_consensus_enabled  = True,
            total_snapshots          = 3,
            latest_pofc_hash         = "a" * 64,
            latest_agent_count       = 5,
            latest_separation_ratio  = 1.261,
            error                    = None,
        )
        self.assertTrue(r.fleet_consensus_enabled)
        self.assertEqual(r.total_snapshots, 3)
        self.assertEqual(len(r.latest_pofc_hash), 64)
        self.assertIsNone(r.error)

    def test_fleet_consensus_init(self):
        """VAPIFleetConsensus initialises without error."""
        client = VAPIFleetConsensus("http://localhost:8765", api_key="testkey")
        self.assertIn("localhost", client._base)

    def test_fleet_consensus_bad_url_never_raises(self):
        """VAPIFleetConsensus.get_snapshot() never raises — returns error default."""
        client = VAPIFleetConsensus("http://no-such-host-vapi-157.local")
        result = client.get_snapshot()
        self.assertIsInstance(result, FleetConsensusSnapshotResult)
        self.assertIsNotNone(result.error)
        self.assertIsNone(result.latest_pofc_hash)

    def test_enrollment_guidance_result_cov_regime_status_slot(self):
        """Phase 157: EnrollmentAutoGuidanceResult has cov_regime_status slot."""
        r = EnrollmentAutoGuidanceResult(
            sessions_needed_total = 7,
            overall_ready         = False,
            recommended_action    = "capture more sessions",
            urgency_level         = "HIGH",
            estimated_days        = 14.0,
            cov_regime_status     = "diagonal_stable",
            error                 = None,
        )
        self.assertEqual(r.cov_regime_status, "diagonal_stable")
        self.assertFalse(r.overall_ready)


if __name__ == "__main__":
    unittest.main()
