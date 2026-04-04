"""Phase 160 SDK tests — ConsentLedgerResult + VAPIConsentLedger (BP-002).

4 tests → SDK 277 → 281.
"""

import unittest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from sdk.vapi_sdk import (
    SDK_VERSION,
    ConsentLedgerResult,
    VAPIConsentLedger,
)


class TestPhase160SDK(unittest.TestCase):

    def test_consent_ledger_result_slots(self):
        """ConsentLedgerResult has 6 expected slots."""
        r = ConsentLedgerResult(
            consent_ledger_enabled = True,
            consent_given          = True,
            consent_ts             = 1743800000.0,
            revoked                = False,
            erasure_requested      = False,
            error                  = None,
        )
        self.assertTrue(r.consent_ledger_enabled)
        self.assertTrue(r.consent_given)
        self.assertAlmostEqual(r.consent_ts, 1743800000.0)
        self.assertFalse(r.revoked)
        self.assertFalse(r.erasure_requested)
        self.assertIsNone(r.error)

    def test_vapi_consent_ledger_init(self):
        """VAPIConsentLedger initialises without error."""
        client = VAPIConsentLedger("http://localhost:8765", api_key="testkey")
        self.assertIn("localhost", client._base)

    def test_consent_ledger_bad_url_never_raises(self):
        """VAPIConsentLedger.get_consent_status() never raises — returns error default."""
        client = VAPIConsentLedger("http://no-such-host-vapi-160.local")
        result = client.get_consent_status("test_device")
        self.assertIsInstance(result, ConsentLedgerResult)
        self.assertIsNotNone(result.error)
        self.assertFalse(result.consent_given)
        self.assertFalse(result.revoked)

    def test_sdk_version_is_phase160(self):
        """SDK_VERSION reflects Phase 160."""
        self.assertEqual(SDK_VERSION, "3.0.0-phase160")


if __name__ == "__main__":
    unittest.main()
