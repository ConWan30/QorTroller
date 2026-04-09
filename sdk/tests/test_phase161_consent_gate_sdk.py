"""Phase 161 SDK tests — ConsentGateResult + VAPIConsentGate.

4 tests → SDK 281 → 285.
"""

import unittest
from unittest.mock import patch, MagicMock
import sys, os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from sdk.vapi_sdk import (
    SDK_VERSION,
    ConsentGateResult,
    VAPIConsentGate,
)


class TestPhase161SDK(unittest.TestCase):

    def test_consent_gate_result_slots(self):
        """ConsentGateResult has 5 expected slots."""
        r = ConsentGateResult(
            consent_ledger_enabled = True,
            gate_active            = True,
            violations_total       = 3,
            last_violation_ts      = 1712250000.0,
            error                  = None,
        )
        self.assertTrue(r.consent_ledger_enabled)
        self.assertTrue(r.gate_active)
        self.assertEqual(r.violations_total, 3)
        self.assertAlmostEqual(r.last_violation_ts, 1712250000.0)
        self.assertIsNone(r.error)

    def test_vapi_consent_gate_init(self):
        """VAPIConsentGate initialises without error."""
        client = VAPIConsentGate("http://localhost:8765", api_key="testkey161")
        self.assertIn("localhost", client._base)

    def test_consent_gate_bad_url_never_raises(self):
        """VAPIConsentGate.get_gate_status() never raises — returns error default."""
        client = VAPIConsentGate("http://no-such-host-vapi-161.local")
        result = client.get_gate_status()
        self.assertIsInstance(result, ConsentGateResult)
        self.assertIsNotNone(result.error)
        self.assertEqual(result.violations_total, 0)
        self.assertFalse(result.gate_active)

    def test_sdk_version_is_phase162(self):
        """SDK_VERSION reflects Phase 162 (bumped from 161)."""
        self.assertEqual(SDK_VERSION, "3.0.0-phase166")


if __name__ == "__main__":
    unittest.main()
