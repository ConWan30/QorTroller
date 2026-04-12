"""Phase 204 SDK tests — IoSwarmAdjudicationPrimerResult + VAPIIoSwarmAdjudicationPrimer.

T204-SDK-1  IoSwarmAdjudicationPrimerResult is a dataclass with slots=True and 6 fields
T204-SDK-2  VAPIIoSwarmAdjudicationPrimer.prime() parses successful 200 response
T204-SDK-3  VAPIIoSwarmAdjudicationPrimer.prime() handles 409 (primer disabled) gracefully
T204-SDK-4  primer_enabled=False produces error field set, log_seeded=False
"""
from __future__ import annotations

import dataclasses
import json
import sys
import os
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from vapi_sdk import IoSwarmAdjudicationPrimerResult, VAPIIoSwarmAdjudicationPrimer  # noqa: E402


# ---------------------------------------------------------------------------
# T204-SDK-1  Dataclass structure
# ---------------------------------------------------------------------------
class TestT204SDK1_DataclassStructure(unittest.TestCase):
    def test_is_dataclass(self):
        self.assertTrue(dataclasses.is_dataclass(IoSwarmAdjudicationPrimerResult))

    def test_slots_true(self):
        self.assertTrue(
            hasattr(IoSwarmAdjudicationPrimerResult, "__slots__"),
            "IoSwarmAdjudicationPrimerResult must use slots=True for memory efficiency",
        )

    def test_field_names(self):
        fields = {f.name for f in dataclasses.fields(IoSwarmAdjudicationPrimerResult)}
        expected = {
            "primer_enabled",
            "devices_primed",
            "ioswarm_adjudication_log_seeded",
            "ioswarm_adjudication_log_total",
            "timestamp",
            "error",
        }
        self.assertEqual(fields, expected, f"Field mismatch: got {fields}")

    def test_default_values(self):
        r = IoSwarmAdjudicationPrimerResult(
            primer_enabled=False,
            devices_primed=0,
            ioswarm_adjudication_log_seeded=False,
        )
        self.assertEqual(r.ioswarm_adjudication_log_total, 0)
        self.assertEqual(r.timestamp, 0.0)
        self.assertIsNone(r.error)


# ---------------------------------------------------------------------------
# T204-SDK-2  Successful 200 response parsing
# ---------------------------------------------------------------------------
class TestT204SDK2_SuccessResponse(unittest.TestCase):
    def test_prime_parses_200_response(self):
        import urllib.response as _uresp
        import io

        body = json.dumps({
            "primer_enabled":                  True,
            "devices_primed":                  5,
            "ioswarm_adjudication_log_seeded": True,
            "ioswarm_adjudication_log_total":  5,
            "timestamp":                       1712000000.0,
            "results": [
                {"device_id": f"primer_device_{i:03d}",
                 "classj_verdict": "CLEAR",
                 "triage_verdict": "CLEAR",
                 "dual_veto": False}
                for i in range(5)
            ],
        }).encode()

        mock_resp = MagicMock()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__  = MagicMock(return_value=False)
        mock_resp.read      = lambda: body
        mock_resp.status    = 200

        primer = VAPIIoSwarmAdjudicationPrimer("http://localhost:8080", "testkey")
        with patch("urllib.request.urlopen", return_value=mock_resp):
            result = primer.prime()

        self.assertTrue(result.primer_enabled)
        self.assertEqual(result.devices_primed, 5)
        self.assertTrue(result.ioswarm_adjudication_log_seeded)
        self.assertEqual(result.ioswarm_adjudication_log_total, 5)
        self.assertEqual(result.timestamp, 1712000000.0)
        self.assertIsNone(result.error)


# ---------------------------------------------------------------------------
# T204-SDK-3  409 response (primer disabled) handled gracefully
# ---------------------------------------------------------------------------
class TestT204SDK3_DisabledResponse(unittest.TestCase):
    def test_prime_handles_409_gracefully(self):
        import urllib.error as _ue
        import io

        detail = json.dumps({
            "error":   "primer_disabled",
            "message": "ioswarm_adjudication_primer_enabled=False.",
        }).encode()

        err = _ue.HTTPError(
            url="http://localhost:8080/agent/prime-ioswarm-adjudication",
            code=409,
            msg="Conflict",
            hdrs=MagicMock(),
            fp=io.BytesIO(detail),
        )

        primer = VAPIIoSwarmAdjudicationPrimer("http://localhost:8080", "testkey")
        with patch("urllib.request.urlopen", side_effect=err):
            result = primer.prime()

        self.assertFalse(result.primer_enabled)
        self.assertEqual(result.devices_primed, 0)
        self.assertFalse(result.ioswarm_adjudication_log_seeded)
        self.assertIsNotNone(result.error)
        # Error message comes from the 409 response "message" field
        self.assertIn("primer_enabled", result.error)


# ---------------------------------------------------------------------------
# T204-SDK-4  primer_enabled=False: error field set, log_seeded=False
# ---------------------------------------------------------------------------
class TestT204SDK4_PrimerDisabledState(unittest.TestCase):
    def test_disabled_result_has_correct_state(self):
        r = IoSwarmAdjudicationPrimerResult(
            primer_enabled=False,
            devices_primed=0,
            ioswarm_adjudication_log_seeded=False,
            error="ioswarm_adjudication_primer_enabled=False",
        )
        self.assertFalse(r.primer_enabled)
        self.assertEqual(r.devices_primed, 0)
        self.assertFalse(r.ioswarm_adjudication_log_seeded)
        self.assertIsNotNone(r.error)
        self.assertIn("primer_enabled", r.error)

    def test_enabled_result_has_correct_state(self):
        r = IoSwarmAdjudicationPrimerResult(
            primer_enabled=True,
            devices_primed=5,
            ioswarm_adjudication_log_seeded=True,
            ioswarm_adjudication_log_total=5,
            timestamp=1712000000.0,
        )
        self.assertTrue(r.primer_enabled)
        self.assertEqual(r.devices_primed, 5)
        self.assertTrue(r.ioswarm_adjudication_log_seeded)
        self.assertIsNone(r.error)


if __name__ == "__main__":
    unittest.main()
