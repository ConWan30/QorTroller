"""Phase 166 SDK tests — MixedProbeGateResult + VAPIMixedProbeGate.

4 tests -> SDK 301 -> 305.
"""

import unittest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from sdk.vapi_sdk import (
    SDK_VERSION,
    MixedProbeGateResult,
    VAPIMixedProbeGate,
)


class TestPhase166SDK(unittest.TestCase):

    def test_mixed_probe_gate_result_slots(self):
        """MixedProbeGateResult has 5 expected slots."""
        r = MixedProbeGateResult(
            min_separation_ratio  = 0.70,
            sessions_needed_total = 12,
            overall_ready         = False,
            mixed_probe_in_types  = True,
            error                 = None,
        )
        self.assertAlmostEqual(r.min_separation_ratio, 0.70, places=2)
        self.assertEqual(r.sessions_needed_total, 12)
        self.assertFalse(r.overall_ready)
        self.assertTrue(r.mixed_probe_in_types)
        self.assertIsNone(r.error)

    def test_vapi_mixed_probe_gate_init(self):
        """VAPIMixedProbeGate initialises without error."""
        client = VAPIMixedProbeGate("http://localhost:8765", api_key="testkey166")
        self.assertIn("localhost", client._base)

    def test_get_status_bad_url_never_raises(self):
        """VAPIMixedProbeGate.get_status() never raises — returns error default."""
        client = VAPIMixedProbeGate("http://no-such-host-vapi-166.local")
        result = client.get_status()
        self.assertIsInstance(result, MixedProbeGateResult)
        self.assertIsNotNone(result.error)
        self.assertAlmostEqual(result.min_separation_ratio, 0.70, places=2)
        self.assertFalse(result.overall_ready)

    def test_sdk_version_is_phase166(self):
        """SDK_VERSION reflects Phase 166."""
        self.assertEqual(SDK_VERSION, "3.0.0-phase166")


if __name__ == "__main__":
    unittest.main()
