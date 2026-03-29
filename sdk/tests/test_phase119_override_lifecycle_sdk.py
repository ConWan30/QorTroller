"""
Phase 119 — SDK EpochWindowOverrideStatus + VAPIEpochWindowOverrideManager (4 tests)
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
    EpochWindowOverrideStatus,
    VAPIEpochWindowOverrideManager,
)


class TestEpochWindowOverrideLifecycleSDK(unittest.TestCase):

    def test_1_sdk_version_is_phase119(self):
        """SDK_VERSION must be at least phase119 (forward-compatible integer comparison)."""
        self.assertGreaterEqual(int(SDK_VERSION.split("-phase")[1]), 119)

    def test_2_epoch_window_override_status_slots(self):
        """EpochWindowOverrideStatus has exactly 6 slots."""
        expected = {
            "override_count", "overrides_with_max_uses", "overrides",
            "epoch_window_enabled", "timestamp", "error",
        }
        self.assertEqual(set(EpochWindowOverrideStatus.__slots__), expected)

    def test_3_get_override_status_bad_url_no_raise(self):
        """get_override_status() never raises — returns error in result.error on bad URL."""
        client = VAPIEpochWindowOverrideManager("http://127.0.0.1:19995", api_key="k119")
        result = client.get_override_status()
        self.assertIsNotNone(result.error)
        self.assertEqual(result.override_count, 0)
        self.assertEqual(result.overrides_with_max_uses, 0)
        self.assertIsInstance(result.overrides, list)
        self.assertFalse(result.epoch_window_enabled)

    def test_4_get_override_status_parses_response(self):
        """get_override_status() maps bridge response fields correctly."""
        import json
        import urllib.request

        fake_body = json.dumps({
            "override_count": 2,
            "overrides_with_max_uses": 1,
            "overrides": [
                {
                    "device_id": "dev_cold",
                    "override_window_seconds": 172800.0,
                    "reason": "cold start",
                    "max_uses": 3,
                    "use_count": 1,
                    "expires_at": None,
                    "created_at": 1711200000.0,
                },
                {
                    "device_id": "dev_perm",
                    "override_window_seconds": 604800.0,
                    "reason": "slow adjudicator",
                    "max_uses": None,
                    "use_count": 0,
                    "expires_at": None,
                    "created_at": 1711100000.0,
                },
            ],
            "epoch_window_enabled": True,
            "timestamp": 1711300000.0,
        }).encode()

        class _FakeResp:
            def read(self):
                return fake_body
            def __enter__(self):
                return self
            def __exit__(self, *_):
                pass

        client = VAPIEpochWindowOverrideManager("http://bridge.test", api_key="op-key")
        with patch.object(urllib.request, "urlopen", return_value=_FakeResp()):
            result = client.get_override_status()

        self.assertEqual(result.override_count, 2)
        self.assertEqual(result.overrides_with_max_uses, 1)
        self.assertEqual(len(result.overrides), 2)
        self.assertEqual(result.overrides[0]["device_id"], "dev_cold")
        self.assertEqual(result.overrides[0]["max_uses"], 3)
        self.assertTrue(result.epoch_window_enabled)
        self.assertIsNone(result.error)


if __name__ == "__main__":
    unittest.main()
