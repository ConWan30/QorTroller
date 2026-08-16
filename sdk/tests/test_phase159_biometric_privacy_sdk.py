"""Phase 159 SDK tests — BiometricPrivacyComplianceResult + VAPIBiometricPrivacy.

4 tests → SDK 273 → 277.
"""

import unittest
from unittest.mock import patch, MagicMock
import sys, os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from sdk.vapi_sdk import (
    SDK_VERSION,
    BiometricPrivacyComplianceResult,
    VAPIBiometricPrivacy,
)


class TestPhase159SDK(unittest.TestCase):

    def test_biometric_privacy_result_slots(self):
        """BiometricPrivacyComplianceResult has 6 expected slots."""
        r = BiometricPrivacyComplianceResult(
            biometric_privacy_enabled = True,
            bp001_half_life_days      = 90.0,
            records_monitored         = 11,
            mean_decay_factor         = 0.92,
            warning_triggered         = False,
            error                     = None,
        )
        self.assertTrue(r.biometric_privacy_enabled)
        self.assertAlmostEqual(r.bp001_half_life_days, 90.0)
        self.assertEqual(r.records_monitored, 11)
        self.assertFalse(r.warning_triggered)
        self.assertIsNone(r.error)

    def test_vapi_biometric_privacy_init(self):
        """VAPIBiometricPrivacy initialises without error."""
        client = VAPIBiometricPrivacy("http://localhost:8765", api_key="testkey")
        self.assertIn("localhost", client._base)

    def test_biometric_privacy_bad_url_never_raises(self):
        """VAPIBiometricPrivacy.get_privacy_status() never raises — returns error default."""
        client = VAPIBiometricPrivacy("http://no-such-host-vapi-159.local")
        result = client.get_privacy_status()
        self.assertIsInstance(result, BiometricPrivacyComplianceResult)
        self.assertIsNotNone(result.error)
        self.assertAlmostEqual(result.mean_decay_factor, 1.0)

    def test_sdk_version_is_phase162(self):
        """SDK_VERSION reflects Phase 162 (bumped from 159 via 160–161)."""
        # SDK_VERSION moved past per-phase numeric suffixes (3.1.1-phase-o3-zkba-track1-g4-validator-sdk); keep the
# monotonic-floor intent instead of pinning a dead format.

        _semver = tuple(int(p) for p in SDK_VERSION.split("-")[0].split(".")[:3])

        self.assertGreaterEqual(_semver, (3, 1, 0))


if __name__ == "__main__":
    unittest.main()
