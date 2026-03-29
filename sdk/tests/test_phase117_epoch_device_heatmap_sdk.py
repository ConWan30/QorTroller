"""
Phase 117 — SDK EpochWindowDeviceEntry + VAPIEpochWindowHeatmap (4 tests)
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
    EpochWindowDeviceEntry,
    VAPIEpochWindowHeatmap,
)


class TestEpochWindowHeatmapSDK(unittest.TestCase):

    def test_1_sdk_version_is_phase117(self):
        """SDK_VERSION must be 3.0.0-phase117 after Phase 117 bump."""
        self.assertGreaterEqual(int(SDK_VERSION.split("-phase")[1]), 117)

    def test_2_epoch_window_device_entry_slots(self):
        """EpochWindowDeviceEntry has exactly 6 slots."""
        expected = {
            "device_id", "check_count", "blocked_count",
            "p50_age_seconds", "p95_age_seconds", "last_check_ts",
        }
        self.assertEqual(set(EpochWindowDeviceEntry.__slots__), expected)

    def test_3_get_heatmap_bad_url_no_raise(self):
        """get_heatmap() never raises — returns safe list on bad URL."""
        client = VAPIEpochWindowHeatmap("http://127.0.0.1:19997", api_key="k117")
        result = client.get_heatmap()
        self.assertIsInstance(result, list)
        # Error path returns 1 entry with safe defaults
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].p95_age_seconds, -1.0)

    def test_4_get_heatmap_parses_response(self):
        """get_heatmap() maps bridge response devices list correctly."""
        import json
        import urllib.request

        fake_body = json.dumps({
            "epoch_window_enabled": False,
            "epoch_window_seconds": 86400.0,
            "total_devices": 2,
            "devices": [
                {
                    "device_id": "dev_stale",
                    "check_count": 10,
                    "blocked_count": 3,
                    "p50_age_seconds": 70000.0,
                    "p95_age_seconds": 80000.0,
                    "last_check_ts": 1711200000.0,
                },
                {
                    "device_id": "dev_fresh",
                    "check_count": 5,
                    "blocked_count": 0,
                    "p50_age_seconds": 1000.0,
                    "p95_age_seconds": 2000.0,
                    "last_check_ts": 1711200100.0,
                },
            ],
            "timestamp": 1711200200.0,
        }).encode()

        class _FakeResp:
            def read(self):
                return fake_body
            def __enter__(self):
                return self
            def __exit__(self, *_):
                pass

        client = VAPIEpochWindowHeatmap("http://bridge.test", api_key="op-key")
        with patch.object(urllib.request, "urlopen", return_value=_FakeResp()):
            result = client.get_heatmap()

        self.assertEqual(len(result), 2)
        self.assertEqual(result[0].device_id, "dev_stale")
        self.assertEqual(result[0].check_count, 10)
        self.assertEqual(result[0].blocked_count, 3)
        self.assertAlmostEqual(result[0].p95_age_seconds, 80000.0)
        self.assertEqual(result[1].device_id, "dev_fresh")
        self.assertEqual(result[1].blocked_count, 0)
        self.assertAlmostEqual(result[1].p95_age_seconds, 2000.0)


if __name__ == "__main__":
    unittest.main()
