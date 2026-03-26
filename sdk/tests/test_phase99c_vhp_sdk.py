"""Phase 99C — VAPIHumanProof SDK tests.

Tests:
  test_1  VHPData defaults — is_valid=False, error=None, all 11 fields present
  test_2  VAPIHumanProof.is_human() returns False on connection error (never raises)
  test_3  VAPIHumanProof.get_vhp_data() parses mocked response correctly
  test_4  VAPIHumanProof.request_vhp_mint() returns error dict on failure (never raises)
  test_5  VHPData.is_valid=True when mocked server returns is_valid=true + future expires_at
  test_6  VHPData.__slots__ — all 11 fields present

SDK count: 81 → 87 (+6)
"""
import time
import json
import unittest
from unittest.mock import patch, MagicMock
from io import BytesIO
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from vapi_sdk import VAPIHumanProof, VHPData


class TestVHPDataDefaults(unittest.TestCase):

    def test_1_vhpdata_defaults_and_fields(self):
        """VHPData with all required fields — defaults is_valid=False, error=None."""
        vhp = VHPData(
            device_id="",
            token_id=0,
            cert_level=0,
            consecutive_clean=0,
            confidence_score=0.0,
            issued_at=0.0,
            expires_at=0.0,
            is_valid=False,
        )
        self.assertFalse(vhp.is_valid)
        self.assertIsNone(vhp.error)
        self.assertEqual(vhp.token_id, 0)
        self.assertEqual(vhp.cert_level, 0)
        self.assertEqual(vhp.consecutive_clean, 0)
        self.assertEqual(vhp.confidence_score, 0.0)

    def test_6_vhpdata_slots_all_fields_present(self):
        """VHPData.__slots__ contains all 11 expected fields."""
        expected = {
            "device_id", "token_id", "cert_level", "consecutive_clean",
            "confidence_score", "issued_at", "expires_at", "is_valid",
            "to_address", "vhp_contract_address", "error",
        }
        actual = set(VHPData.__slots__)
        self.assertEqual(expected, actual)


class TestVAPIHumanProofClient(unittest.TestCase):

    def test_2_is_human_returns_false_on_connection_error(self):
        """VAPIHumanProof.is_human() returns False on bad URL (never raises)."""
        client = VAPIHumanProof("http://localhost:19999_bad_port", api_key="k")
        result = client.is_human("dev_test")
        self.assertFalse(result)

    def test_3_get_vhp_data_parses_mocked_response(self):
        """VAPIHumanProof.get_vhp_data() parses a valid API response correctly."""
        future_ts = time.time() + 90 * 86400
        mock_response_body = json.dumps({
            "device_id": "dev_abc",
            "found": True,
            "is_valid": True,
            "token_id": 42,
            "cert_level": 2,
            "consecutive_clean": 30,
            "confidence_score": 8500,  # basis points
            "created_at": time.time() - 100,
            "expires_at": future_ts,
            "to_address": "0xabcdef",
            "vhp_contract_address": "0x1234",
            "timestamp": time.time(),
        }).encode()

        mock_resp = MagicMock()
        mock_resp.read.return_value = mock_response_body
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_resp):
            client = VAPIHumanProof("http://localhost:8080", api_key="test")
            data = client.get_vhp_data("dev_abc")

        self.assertEqual(data.device_id, "dev_abc")
        self.assertEqual(data.token_id, 42)
        self.assertEqual(data.cert_level, 2)
        self.assertEqual(data.consecutive_clean, 30)
        self.assertAlmostEqual(data.confidence_score, 0.85, places=5)  # 8500/10000
        self.assertAlmostEqual(data.expires_at, future_ts, places=0)
        self.assertTrue(data.is_valid)
        self.assertIsNone(data.error)

    def test_4_request_vhp_mint_returns_error_on_failure(self):
        """VAPIHumanProof.request_vhp_mint() returns error dict on failure (never raises)."""
        client = VAPIHumanProof("http://localhost:19999_bad_port", api_key="k")
        result = client.request_vhp_mint("dev_test", "0xrecipient")
        self.assertIsInstance(result, dict)
        self.assertIn("error", result)

    def test_5_is_human_true_when_is_valid_true(self):
        """is_human() returns True when API response has is_valid=true."""
        future_ts = time.time() + 86400
        mock_response_body = json.dumps({
            "device_id": "dev_human",
            "found": True,
            "is_valid": True,
            "token_id": 1,
            "cert_level": 1,
            "consecutive_clean": 10,
            "confidence_score": 9000,
            "expires_at": future_ts,
            "to_address": "0x1234",
            "vhp_contract_address": "0xvhp",
            "timestamp": time.time(),
        }).encode()

        mock_resp = MagicMock()
        mock_resp.read.return_value = mock_response_body
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_resp):
            client = VAPIHumanProof("http://localhost:8080", api_key="test")
            result = client.is_human("dev_human")

        self.assertTrue(result)
