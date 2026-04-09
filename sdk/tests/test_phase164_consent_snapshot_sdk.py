"""Phase 164 SDK tests — ConsentSnapshotResult + VAPIConsentSnapshotDelta.

4 tests → SDK 293 → 297.
"""

import unittest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from sdk.vapi_sdk import (
    SDK_VERSION,
    ConsentSnapshotResult,
    VAPIConsentSnapshotDelta,
)


class TestPhase164SDK(unittest.TestCase):

    def test_consent_snapshot_result_slots(self):
        """ConsentSnapshotResult has 6 expected slots."""
        r = ConsentSnapshotResult(
            commit_hash           = "a" * 64,
            n_consented_at_commit = 3,
            n_consented_live      = 2,
            delta                 = 1,
            revoked_since_commit  = 1,
            error                 = None,
        )
        self.assertEqual(len(r.commit_hash), 64)
        self.assertEqual(r.n_consented_at_commit, 3)
        self.assertEqual(r.n_consented_live, 2)
        self.assertEqual(r.delta, 1)
        self.assertEqual(r.revoked_since_commit, 1)
        self.assertIsNone(r.error)

    def test_vapi_consent_snapshot_delta_init(self):
        """VAPIConsentSnapshotDelta initialises without error."""
        client = VAPIConsentSnapshotDelta("http://localhost:8765", api_key="testkey164")
        self.assertIn("localhost", client._base)

    def test_get_delta_bad_url_never_raises(self):
        """VAPIConsentSnapshotDelta.get_delta() never raises — returns error default."""
        client = VAPIConsentSnapshotDelta("http://no-such-host-vapi-164.local")
        result = client.get_delta()
        self.assertIsInstance(result, ConsentSnapshotResult)
        self.assertIsNotNone(result.error)
        self.assertIsNone(result.commit_hash)
        self.assertEqual(result.delta, 0)

    def test_sdk_version_is_phase164(self):
        """SDK_VERSION reflects Phase 164."""
        self.assertEqual(SDK_VERSION, "3.0.0-phase166")


if __name__ == "__main__":
    unittest.main()
