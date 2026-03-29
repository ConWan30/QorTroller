"""
Phase 120 — BT Transport Foundation SDK Tests (4 tests)

test_1_bt_transport_result_slots_6_fields
test_2_vapi_bt_transport_init
test_3_get_transport_status_bad_url_error
test_4_error_entry_all_false_zero
"""

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

SDK_DIR = Path(__file__).parents[1]
sys.path.insert(0, str(SDK_DIR))

# Stub heavy deps before sdk import
for _mod in ["web3", "web3.exceptions", "eth_account", "eth_account.signers.local"]:
    if _mod not in sys.modules:
        sys.modules[_mod] = MagicMock()

from vapi_sdk import (  # noqa: E402
    SDK_VERSION,
    BTTransportResult,
    VAPIBTTransport,
)


# ---------------------------------------------------------------------------
# 1. BTTransportResult slots — 6 fields
# ---------------------------------------------------------------------------

class TestBTTransportResultSlots(unittest.TestCase):

    def test_1_bt_transport_result_slots_6_fields(self):
        """BTTransportResult has exactly 6 slots with all named fields present."""
        self.assertTrue(hasattr(BTTransportResult, "__slots__"))
        slots = set(BTTransportResult.__slots__)
        required = {
            "bt_transport_enabled", "device_address", "sampling_rate_hz",
            "frames_received", "frames_dropped", "error",
        }
        self.assertEqual(slots, required)

        # Default construction with all required fields
        r = BTTransportResult(
            bt_transport_enabled=False,
            device_address="",
            sampling_rate_hz=250,
            frames_received=0,
            frames_dropped=0,
        )
        self.assertFalse(r.bt_transport_enabled)
        self.assertEqual(r.sampling_rate_hz, 250)
        self.assertIsNone(r.error)


# ---------------------------------------------------------------------------
# 2. VAPIBTTransport initializes without raising
# ---------------------------------------------------------------------------

class TestVAPIBTTransportInit(unittest.TestCase):

    def test_2_vapi_bt_transport_init(self):
        """VAPIBTTransport("http://localhost:18080", "test-key") initializes without raising."""
        bt = VAPIBTTransport("http://localhost:18080", api_key="test-key")
        self.assertIsNotNone(bt)


# ---------------------------------------------------------------------------
# 3. Bad URL → error in result, never raises
# ---------------------------------------------------------------------------

class TestBTTransportBadURL(unittest.TestCase):

    def test_3_get_transport_status_bad_url_error(self):
        """get_transport_status() bad URL (port 1) → BTTransportResult with error != None."""
        bt = VAPIBTTransport("http://127.0.0.1:1", api_key="test-key")
        result = bt.get_transport_status()
        self.assertIsInstance(result, BTTransportResult)
        self.assertIsNotNone(result.error)
        self.assertFalse(result.bt_transport_enabled)


# ---------------------------------------------------------------------------
# 4. Error entry → eligible/counts all zero/False
# ---------------------------------------------------------------------------

class TestBTTransportErrorDefaults(unittest.TestCase):

    def test_4_error_entry_all_false_zero(self):
        """Error BTTransportResult has bt_transport_enabled=False and all counts=0."""
        bt = VAPIBTTransport("http://127.0.0.1:1", api_key="test-key")
        result = bt.get_transport_status()
        self.assertFalse(result.bt_transport_enabled)
        self.assertEqual(result.frames_received, 0)
        self.assertEqual(result.frames_dropped, 0)
        self.assertEqual(result.sampling_rate_hz, 250)
        self.assertIsNotNone(result.error)


if __name__ == "__main__":
    unittest.main()
