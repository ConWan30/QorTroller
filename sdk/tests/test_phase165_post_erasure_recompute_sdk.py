"""Phase 165 SDK tests — PostErasureRecomputeResult + VAPIPostErasureRecompute.

4 tests → SDK 297 → 301.
"""

import unittest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from sdk.vapi_sdk import (
    SDK_VERSION,
    PostErasureRecomputeResult,
    VAPIPostErasureRecompute,
)


class TestPhase165SDK(unittest.TestCase):

    def test_post_erasure_recompute_result_slots(self):
        """PostErasureRecomputeResult has 6 expected slots."""
        r = PostErasureRecomputeResult(
            consent_ledger_enabled = True,
            total_recomputes       = 2,
            pending_recomputes     = 1,
            latest_recompute_ts    = 1712345678.0,
            recompute_needed       = True,
            error                  = None,
        )
        self.assertTrue(r.consent_ledger_enabled)
        self.assertEqual(r.total_recomputes,    2)
        self.assertEqual(r.pending_recomputes,  1)
        self.assertEqual(r.latest_recompute_ts, 1712345678.0)
        self.assertTrue(r.recompute_needed)
        self.assertIsNone(r.error)

    def test_vapi_post_erasure_recompute_init(self):
        """VAPIPostErasureRecompute initialises without error."""
        client = VAPIPostErasureRecompute("http://localhost:8765", api_key="testkey165")
        self.assertIn("localhost", client._base)

    def test_get_status_bad_url_never_raises(self):
        """VAPIPostErasureRecompute.get_status() never raises — returns error default."""
        client = VAPIPostErasureRecompute("http://no-such-host-vapi-165.local")
        result = client.get_status()
        self.assertIsInstance(result, PostErasureRecomputeResult)
        self.assertIsNotNone(result.error)
        self.assertEqual(result.total_recomputes,   0)
        self.assertFalse(result.recompute_needed)

    def test_sdk_version_is_phase165(self):
        """SDK_VERSION reflects Phase 165."""
        self.assertEqual(SDK_VERSION, "3.0.0-phase166")


if __name__ == "__main__":
    unittest.main()
