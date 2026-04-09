"""Phase 158 SDK tests — GSRHMACValidationResult + PoHBGResult.

4 tests → SDK 269 → 273.
"""

import unittest
from unittest.mock import patch, MagicMock
import sys, os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from sdk.vapi_sdk import (
    SDK_VERSION,
    GSRHMACValidationResult,
    VAPIGSRHMACValidator,
    PoHBGResult,
    VAPIPoHBG,
)


class TestPhase158SDK(unittest.TestCase):

    def test_gsr_hmac_result_slots(self):
        """GSRHMACValidationResult has 6 expected slots."""
        r = GSRHMACValidationResult(
            gsr_hmac_enabled        = False,
            gsr_hmac_key_configured = False,
            total_validations       = 0,
            valid_count             = 0,
            rejected_count          = 0,
            error                   = None,
        )
        self.assertFalse(r.gsr_hmac_enabled)
        self.assertEqual(r.total_validations, 0)
        self.assertIsNone(r.error)

    def test_pohbg_result_slots(self):
        """PoHBGResult has 6 expected slots."""
        r = PoHBGResult(
            pohbg_enabled     = False,
            total_pohbg       = 7,
            latest_pohbg_hash = "c" * 64,
            latest_device_id  = "dev_abc",
            latest_ts_ns      = 1712270400_000_000_000,
            error             = None,
        )
        self.assertEqual(r.total_pohbg, 7)
        self.assertEqual(len(r.latest_pohbg_hash), 64)
        self.assertIsNone(r.error)

    def test_gsr_hmac_bad_url_never_raises(self):
        """VAPIGSRHMACValidator.get_validation_status() never raises — returns error default."""
        client = VAPIGSRHMACValidator("http://no-such-host-vapi-158.local")
        result = client.get_validation_status()
        self.assertIsInstance(result, GSRHMACValidationResult)
        self.assertIsNotNone(result.error)
        self.assertFalse(result.gsr_hmac_enabled)

    def test_pohbg_bad_url_never_raises(self):
        """VAPIPoHBG.get_pohbg_status() never raises — returns error default."""
        client = VAPIPoHBG("http://no-such-host-vapi-158.local")
        result = client.get_pohbg_status()
        self.assertIsInstance(result, PoHBGResult)
        self.assertIsNotNone(result.error)
        self.assertIsNone(result.latest_pohbg_hash)


if __name__ == "__main__":
    unittest.main()
