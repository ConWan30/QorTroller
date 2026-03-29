"""
Phase 130A — VAPISwarmOperatorGate SDK (4 tests)

test_1_SwarmOperatorGateResult_slots_5_fields
test_2_VAPISwarmOperatorGate_init_no_raise
test_3_bad_url_returns_error_not_none
test_4_error_path_all_zero_defaults
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from vapi_sdk import SwarmOperatorGateResult, VAPISwarmOperatorGate, SDK_VERSION


class TestPhase130SwarmOperatorGateSDK(unittest.TestCase):

    # ------------------------------------------------------------------
    # test_1: SwarmOperatorGateResult has exactly 5 slots
    # ------------------------------------------------------------------
    def test_1_SwarmOperatorGateResult_slots_5_fields(self):
        expected = {"gate_configured", "valid", "node_count", "timestamp", "error"}
        self.assertEqual(set(SwarmOperatorGateResult.__slots__), expected)

    # ------------------------------------------------------------------
    # test_2: VAPISwarmOperatorGate initialises without raising
    # ------------------------------------------------------------------
    def test_2_VAPISwarmOperatorGate_init_no_raise(self):
        client = VAPISwarmOperatorGate("http://localhost:18080", "k")
        self.assertIsNotNone(client)

    # ------------------------------------------------------------------
    # test_3: bad URL → get_gate_status() returns error != None (never raises)
    # ------------------------------------------------------------------
    def test_3_bad_url_returns_error_not_none(self):
        client = VAPISwarmOperatorGate("http://localhost:0", "k", timeout=2)
        result = client.get_gate_status()
        self.assertIsInstance(result, SwarmOperatorGateResult)
        self.assertIsNotNone(result.error)

    # ------------------------------------------------------------------
    # test_4: error path → gate_configured=False, valid=False, node_count=0, timestamp=0.0
    # ------------------------------------------------------------------
    def test_4_error_path_all_zero_defaults(self):
        client = VAPISwarmOperatorGate("http://localhost:0", "k", timeout=2)
        result = client.get_gate_status()
        self.assertFalse(result.gate_configured)
        self.assertFalse(result.valid)
        self.assertEqual(result.node_count, 0)
        self.assertEqual(result.timestamp, 0.0)


if __name__ == "__main__":
    unittest.main()
