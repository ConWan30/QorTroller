"""
Phase 127 — Tournament Preflight SDK Tests (4 tests)

test_1_tournament_preflight_result_has_8_slots
test_2_vapi_tournament_preflight_init_without_raise
test_3_bad_url_returns_error
test_4_error_path_defaults
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from vapi_sdk import TournamentPreflightResult, VAPITournamentPreflight


class TestTournamentPreflightResultSlots(unittest.TestCase):
    def test_1_tournament_preflight_result_has_8_slots(self):
        slots = TournamentPreflightResult.__dataclass_fields__
        self.assertEqual(len(slots), 8)
        expected = {
            "separation_ok", "l4_ok", "gate_ok", "cert_ok", "audit_ok",
            "overall_pass", "conditions_detail", "error",
        }
        self.assertEqual(set(slots.keys()), expected)


class TestVAPITournamentPreflightInit(unittest.TestCase):
    def test_2_vapi_tournament_preflight_init_without_raise(self):
        client = VAPITournamentPreflight("http://localhost:18080", "test-key")
        self.assertIsNotNone(client)


class TestBadUrlReturnsError(unittest.TestCase):
    def test_3_bad_url_returns_error(self):
        client = VAPITournamentPreflight("http://127.0.0.1:1", "k")
        result = client.run_preflight()
        self.assertIsInstance(result, TournamentPreflightResult)
        self.assertIsNotNone(result.error)


class TestErrorPathDefaults(unittest.TestCase):
    def test_4_error_path_defaults(self):
        client = VAPITournamentPreflight("http://127.0.0.1:1", "k")
        result = client.run_preflight()
        self.assertFalse(result.separation_ok)
        self.assertFalse(result.l4_ok)
        self.assertFalse(result.gate_ok)
        self.assertFalse(result.cert_ok)
        self.assertFalse(result.audit_ok)
        self.assertFalse(result.overall_pass)
        self.assertIsInstance(result.conditions_detail, dict)
        self.assertIsNotNone(result.error)


if __name__ == "__main__":
    unittest.main()
