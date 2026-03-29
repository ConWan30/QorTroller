"""
Phase 131 — IoSwarm Live Node Registry SDK Tests (4 tests)

test_1_IoSwarmNodeRegistryResult_6_slots
test_2_init_no_raise
test_3_bad_url_returns_error_not_none
test_4_error_path_emulator_mode_true
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

from vapi_sdk import IoSwarmNodeRegistryResult, VAPIIoSwarmNodeRegistry  # noqa: E402


class TestIoSwarmNodeRegistryResult(unittest.TestCase):

    def test_1_IoSwarmNodeRegistryResult_6_slots(self):
        """IoSwarmNodeRegistryResult must have exactly 6 slots."""
        r = IoSwarmNodeRegistryResult()
        expected_slots = {
            "live_nodes", "emulator_mode", "registry_count",
            "node_timeout_s", "last_quorum_ts", "error",
        }
        actual = set(r.__dataclass_fields__.keys())
        self.assertEqual(actual, expected_slots)

    def test_2_init_no_raise(self):
        """VAPIIoSwarmNodeRegistry.__init__ must not raise."""
        try:
            reg = VAPIIoSwarmNodeRegistry("http://bridge.test", api_key="k")
            self.assertIsNotNone(reg)
        except Exception as exc:
            self.fail(f"VAPIIoSwarmNodeRegistry init raised: {exc}")

    def test_3_bad_url_returns_error_not_none(self):
        """get_registry_status() on unreachable URL returns error != None."""
        reg = VAPIIoSwarmNodeRegistry("http://127.0.0.1:19999", api_key="x")
        result = reg.get_registry_status()
        self.assertIsNotNone(result.error)
        self.assertIsInstance(result.error, str)

    def test_4_error_path_emulator_mode_true(self):
        """On failure, emulator_mode defaults to True (safe fallback)."""
        reg = VAPIIoSwarmNodeRegistry("http://127.0.0.1:19999", api_key="x")
        result = reg.get_registry_status()
        self.assertTrue(result.emulator_mode)
        self.assertEqual(result.live_nodes, 0)
        self.assertEqual(result.registry_count, 0)
        self.assertAlmostEqual(result.node_timeout_s, 5.0)
        self.assertAlmostEqual(result.last_quorum_ts, 0.0)


if __name__ == "__main__":
    unittest.main()
