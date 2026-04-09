"""Phase 162 SDK tests — ConsentAwareCorpusResult + VAPIConsentAwareCorpus.

4 tests → SDK 285 → 289.
"""

import unittest
from unittest.mock import patch, MagicMock
import sys, os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from sdk.vapi_sdk import (
    SDK_VERSION,
    ConsentAwareCorpusResult,
    VAPIConsentAwareCorpus,
)


class TestPhase162SDK(unittest.TestCase):

    def test_consent_aware_corpus_result_slots(self):
        """ConsentAwareCorpusResult has 6 expected slots."""
        r = ConsentAwareCorpusResult(
            consent_ledger_enabled    = True,
            active_consent_count      = 10,
            revoked_count             = 2,
            erasure_requested_count   = 1,
            consent_corpus_defensible = False,
            error                     = None,
        )
        self.assertTrue(r.consent_ledger_enabled)
        self.assertEqual(r.active_consent_count, 10)
        self.assertEqual(r.revoked_count, 2)
        self.assertEqual(r.erasure_requested_count, 1)
        self.assertFalse(r.consent_corpus_defensible)
        self.assertIsNone(r.error)

    def test_vapi_consent_aware_corpus_init(self):
        """VAPIConsentAwareCorpus initialises without error."""
        client = VAPIConsentAwareCorpus("http://localhost:8765", api_key="testkey162")
        self.assertIn("localhost", client._base)

    def test_corpus_bad_url_never_raises(self):
        """VAPIConsentAwareCorpus.get_corpus_status() never raises — returns error default."""
        client = VAPIConsentAwareCorpus("http://no-such-host-vapi-162.local")
        result = client.get_corpus_status()
        self.assertIsInstance(result, ConsentAwareCorpusResult)
        self.assertIsNotNone(result.error)
        self.assertEqual(result.active_consent_count, 0)
        self.assertFalse(result.consent_corpus_defensible)

    def test_sdk_version_is_phase162(self):
        """SDK_VERSION reflects Phase 162."""
        self.assertEqual(SDK_VERSION, "3.0.0-phase166")


if __name__ == "__main__":
    unittest.main()
