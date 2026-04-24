"""Phase 205 SDK tests — AccelTremorFFTResult + VAPIAccelTremorFFT.

T205-SDK-1  AccelTremorFFTResult is a dataclass with slots=True and 6 fields
T205-SDK-2  VAPIAccelTremorFFT.status() parses successful 200 response
T205-SDK-3  VAPIAccelTremorFFT.status() handles network error gracefully
T205-SDK-4  fallback_source field reflects enabled/disabled state
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

from vapi_sdk import AccelTremorFFTResult, VAPIAccelTremorFFT  # noqa: E402


# ---------------------------------------------------------------------------
# T205-SDK-1  Dataclass structure
# ---------------------------------------------------------------------------
class TestT205SDK1_DataclassStructure(unittest.TestCase):
    def test_is_dataclass(self):
        self.assertTrue(dataclasses.is_dataclass(AccelTremorFFTResult))

    def test_slots_true(self):
        self.assertTrue(
            hasattr(AccelTremorFFTResult, "__slots__"),
            "AccelTremorFFTResult must use slots=True for memory efficiency",
        )

    def test_field_names(self):
        fields = {f.name for f in dataclasses.fields(AccelTremorFFTResult)}
        expected = {
            "accel_tremor_fallback_enabled",
            "still_hold_var_threshold",
            "fallback_source",
            "tremor_search_range_hz",
            "accel_fft_nfft",   # Phase 213
            "bin_width_hz",      # Phase 213
            "timestamp",
            "error",
        }
        self.assertEqual(fields, expected, f"Field mismatch: got {fields}")

    def test_default_values(self):
        r = AccelTremorFFTResult(
            accel_tremor_fallback_enabled=True,
            still_hold_var_threshold=4.0,
            fallback_source="accel_magnitude_fft",
            tremor_search_range_hz=[1.0, 15.0],
        )
        self.assertEqual(r.timestamp, 0.0)
        self.assertIsNone(r.error)


# ---------------------------------------------------------------------------
# T205-SDK-2  Successful 200 response parsing
# ---------------------------------------------------------------------------
class TestT205SDK2_SuccessResponse(unittest.TestCase):
    def test_status_parses_200_response(self):
        import urllib.response as _uresp
        import io

        body = json.dumps({
            "accel_tremor_fallback_enabled": True,
            "still_hold_var_threshold":      4.0,
            "fallback_source":               "accel_magnitude_fft",
            "tremor_search_range_hz":        [1.0, 15.0],
            "timestamp":                     1712100000.0,
        }).encode()

        mock_resp = MagicMock()
        mock_resp.read.return_value = body
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_resp):
            client = VAPIAccelTremorFFT("http://localhost:8080", "test-key")
            result = client.status()

        self.assertIsNone(result.error)
        self.assertTrue(result.accel_tremor_fallback_enabled)
        self.assertEqual(result.still_hold_var_threshold, 4.0)
        self.assertEqual(result.fallback_source, "accel_magnitude_fft")
        self.assertEqual(result.tremor_search_range_hz, [1.0, 15.0])
        self.assertEqual(result.timestamp, 1712100000.0)


# ---------------------------------------------------------------------------
# T205-SDK-3  Network error handled gracefully
# ---------------------------------------------------------------------------
class TestT205SDK3_ErrorHandling(unittest.TestCase):
    def test_status_handles_network_error(self):
        with patch("urllib.request.urlopen", side_effect=OSError("connection refused")):
            client = VAPIAccelTremorFFT("http://localhost:8080", "test-key")
            result = client.status()

        self.assertIsNotNone(result.error)
        self.assertIn("connection refused", result.error)
        self.assertFalse(result.accel_tremor_fallback_enabled)
        self.assertEqual(result.fallback_source, "unknown")
        self.assertEqual(result.tremor_search_range_hz, [])


# ---------------------------------------------------------------------------
# T205-SDK-4  fallback_source reflects enabled/disabled state
# ---------------------------------------------------------------------------
class TestT205SDK4_FallbackSourceField(unittest.TestCase):
    def _parse_response(self, enabled: bool) -> AccelTremorFFTResult:
        body = json.dumps({
            "accel_tremor_fallback_enabled": enabled,
            "still_hold_var_threshold":      4.0,
            "fallback_source":               "accel_magnitude_fft" if enabled else "stick_fft_only",
            "tremor_search_range_hz":        [1.0, 15.0] if enabled else [],
            "timestamp":                     1712000000.0,
        }).encode()

        mock_resp = MagicMock()
        mock_resp.read.return_value = body
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_resp):
            return VAPIAccelTremorFFT("http://localhost:8080").status()

    def test_fallback_source_accel_when_enabled(self):
        result = self._parse_response(enabled=True)
        self.assertEqual(result.fallback_source, "accel_magnitude_fft")
        self.assertTrue(result.accel_tremor_fallback_enabled)

    def test_fallback_source_stick_when_disabled(self):
        result = self._parse_response(enabled=False)
        self.assertEqual(result.fallback_source, "stick_fft_only")
        self.assertFalse(result.accel_tremor_fallback_enabled)


if __name__ == "__main__":
    unittest.main()
