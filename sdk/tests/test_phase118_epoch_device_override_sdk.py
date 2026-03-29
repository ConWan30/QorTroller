"""
Phase 118 — SDK EpochWindowAutoTuneResult + VAPIEpochWindowAutoTune (4 tests)
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
    EpochWindowAutoTuneResult,
    VAPIEpochWindowAutoTune,
)


class TestEpochWindowAutoTuneSDK(unittest.TestCase):

    def test_1_sdk_version_is_phase118(self):
        """SDK_VERSION must be at least phase118 (forward-compatible integer comparison)."""
        self.assertGreaterEqual(int(SDK_VERSION.split("-phase")[1]), 118)

    def test_2_epoch_window_auto_tune_result_slots(self):
        """EpochWindowAutoTuneResult has exactly 7 slots."""
        expected = {
            "epoch_window_enabled", "current_window_seconds",
            "recommended_window_seconds", "fleet_p95_age_seconds",
            "override_count", "override_candidates", "error",
        }
        self.assertEqual(set(EpochWindowAutoTuneResult.__slots__), expected)

    def test_3_get_auto_tune_bad_url_no_raise(self):
        """get_auto_tune() never raises — returns error in result.error on bad URL."""
        client = VAPIEpochWindowAutoTune("http://127.0.0.1:19996", api_key="k118")
        result = client.get_auto_tune()
        self.assertIsNotNone(result.error)
        self.assertFalse(result.epoch_window_enabled)
        self.assertEqual(result.override_count, 0)
        self.assertIsInstance(result.override_candidates, list)

    def test_4_get_auto_tune_parses_response(self):
        """get_auto_tune() maps bridge response fields correctly."""
        import json
        import urllib.request

        fake_body = json.dumps({
            "epoch_window_enabled": True,
            "current_window_seconds": 86400.0,
            "recommended_window_seconds": 172800.0,
            "fleet_p95_age_seconds": 80000.0,
            "override_count": 2,
            "override_candidates": [
                {"device_id": "dev_cold", "p95_age_seconds": 90000.0},
            ],
            "timestamp": 1711300000.0,
        }).encode()

        class _FakeResp:
            def read(self):
                return fake_body
            def __enter__(self):
                return self
            def __exit__(self, *_):
                pass

        client = VAPIEpochWindowAutoTune("http://bridge.test", api_key="op-key")
        with patch.object(urllib.request, "urlopen", return_value=_FakeResp()):
            result = client.get_auto_tune()

        self.assertTrue(result.epoch_window_enabled)
        self.assertAlmostEqual(result.current_window_seconds, 86400.0)
        self.assertAlmostEqual(result.recommended_window_seconds, 172800.0)
        self.assertAlmostEqual(result.fleet_p95_age_seconds, 80000.0)
        self.assertEqual(result.override_count, 2)
        self.assertEqual(len(result.override_candidates), 1)
        self.assertEqual(result.override_candidates[0]["device_id"], "dev_cold")
        self.assertIsNone(result.error)


if __name__ == "__main__":
    unittest.main()
