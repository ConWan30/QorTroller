"""Phase 103 -- SDK Activation Flow tests.

Tests:
  test_1  SimulationResult.__slots__ has all 10 fields
  test_2  VAPIActivationFlow.__init__ sets _base_url (rstrip("/")) and _api_key
  test_3  run_simulation never raises on bad URL; returns SimulationResult with error != None
  test_4  check_ready parses mocked activation-status response; result is dict with 'fully_activated'
  test_5  get_first_vhp parses mocked first-vhp-status response; result is dict with 'found'
  test_6  run_simulation returns SimulationResult.fully_activated=False on connection error

SDK count: 93 -> 99 (+6)
"""
import json
import os
import sys
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from sdk.vapi_sdk import SimulationResult, VAPIActivationFlow


class TestPhase103ActivationSDK(unittest.TestCase):

    def test_1_simulation_result_slots(self):
        """SimulationResult.__slots__ has all 10 fields."""
        slots = set(SimulationResult.__slots__)
        required = {
            "simulation_sessions", "gate_passed", "cert_created",
            "dry_run_toggled", "vhp_minted", "token_id", "tx_hash",
            "fully_activated", "elapsed_ms", "error",
        }
        for field in required:
            self.assertIn(field, slots, f"Missing slot: {field}")

    def test_2_vapi_activation_flow_init(self):
        """VAPIActivationFlow.__init__ sets _base_url (rstrip('/')) and _api_key."""
        flow = VAPIActivationFlow("http://localhost:8080/", api_key="mykey")
        self.assertEqual(flow._base_url, "http://localhost:8080")
        self.assertEqual(flow._api_key, "mykey")

    def test_3_run_simulation_never_raises_on_bad_url(self):
        """run_simulation never raises on bad URL; returns SimulationResult with error != None."""
        flow = VAPIActivationFlow("http://localhost:0", api_key="k")
        result = flow.run_simulation(n_sessions=10)
        self.assertIsInstance(result, SimulationResult)
        self.assertIsNotNone(result.error)
        self.assertFalse(result.fully_activated)

    def test_4_check_ready_parses_response(self):
        """check_ready parses mocked activation-status response; result is dict with 'fully_activated'."""
        flow = VAPIActivationFlow("http://localhost:8080", api_key="k")
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(
            {"fully_activated": True, "current_blocking_step": 6}
        ).encode()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_resp):
            result = flow.check_ready()

        self.assertIsInstance(result, dict)
        self.assertIn("fully_activated", result)
        self.assertTrue(result["fully_activated"])

    def test_5_get_first_vhp_parses_response(self):
        """get_first_vhp parses mocked first-vhp-status response; result is dict with 'found'."""
        flow = VAPIActivationFlow("http://localhost:8080", api_key="k")
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(
            {"found": True, "is_simulation": True, "tx_hash": "sim_mint_abc"}
        ).encode()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_resp):
            result = flow.get_first_vhp()

        self.assertIsInstance(result, dict)
        self.assertIn("found", result)
        self.assertTrue(result["found"])

    def test_6_run_simulation_fully_activated_false_on_connection_error(self):
        """run_simulation returns SimulationResult.fully_activated=False on connection error."""
        flow = VAPIActivationFlow("http://localhost:0", api_key="k")
        result = flow.run_simulation()
        self.assertFalse(result.fully_activated)
        self.assertIsNotNone(result.error)
