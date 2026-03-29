"""
Phase 116 — SDK EpochWindowAnalyticsResult + VAPIEpochWindowAnalytics (4 tests)
"""
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

SDK_DIR = Path(__file__).parents[1]
sys.path.insert(0, str(SDK_DIR))

for _mod in ["web3", "web3.exceptions", "eth_account", "eth_account.signers.local"]:
    if _mod not in sys.modules:
        sys.modules[_mod] = MagicMock()

from vapi_sdk import (  # noqa: E402
    SDK_VERSION,
    EpochWindowAnalyticsResult,
    VAPIEpochWindowAnalytics,
)


class TestEpochWindowAnalyticsSDK(unittest.TestCase):

    def test_1_sdk_version_is_phase116(self):
        """SDK_VERSION must be at least phase116 (may be newer after subsequent phases)."""
        self.assertGreaterEqual(int(SDK_VERSION.split("-phase")[1]), 116)

    def test_2_epoch_window_analytics_result_slots(self):
        """EpochWindowAnalyticsResult has exactly 8 slots."""
        expected = {
            "epoch_window_enabled", "epoch_window_seconds",
            "total_gate5_checks", "staleness_blocked_count",
            "p50_age_seconds", "p95_age_seconds",
            "recommended_window_seconds", "error",
        }
        self.assertEqual(set(EpochWindowAnalyticsResult.__slots__), expected)

    def test_3_get_analytics_bad_url_no_raise(self):
        """get_analytics() never raises — returns error in result.error on bad URL."""
        client = VAPIEpochWindowAnalytics("http://127.0.0.1:19998", api_key="k116")
        result = client.get_analytics()
        self.assertIsNotNone(result.error)
        self.assertFalse(result.epoch_window_enabled)
        self.assertEqual(result.total_gate5_checks, 0)

    def test_4_get_analytics_parses_response(self):
        """get_analytics() maps bridge response fields correctly."""
        import json
        import urllib.request

        fake_body = json.dumps({
            "epoch_window_enabled": True,
            "epoch_window_seconds": 43200.0,
            "total_gate5_checks": 50,
            "staleness_blocked_count": 3,
            "checked_count": 47,
            "p50_age_seconds": 3600.0,
            "p95_age_seconds": 40000.0,
            "recommended_window_seconds": 80000.0,
            "timestamp": 1711100000.0,
        }).encode()

        class _FakeResp:
            def read(self):
                return fake_body
            def __enter__(self):
                return self
            def __exit__(self, *_):
                pass

        client = VAPIEpochWindowAnalytics("http://bridge.test", api_key="op-key")
        with patch.object(urllib.request, "urlopen", return_value=_FakeResp()):
            result = client.get_analytics()

        self.assertTrue(result.epoch_window_enabled)
        self.assertAlmostEqual(result.epoch_window_seconds, 43200.0)
        self.assertEqual(result.total_gate5_checks, 50)
        self.assertEqual(result.staleness_blocked_count, 3)
        self.assertAlmostEqual(result.p50_age_seconds, 3600.0)
        self.assertAlmostEqual(result.p95_age_seconds, 40000.0)
        self.assertAlmostEqual(result.recommended_window_seconds, 80000.0)
        self.assertIsNone(result.error)


if __name__ == "__main__":
    unittest.main()
