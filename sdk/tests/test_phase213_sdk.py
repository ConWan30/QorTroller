"""Phase 213 SDK tests — AccelTremorFFTResult Phase 213 fields.

T213-SDK-1  AccelTremorFFTResult has accel_fft_nfft field with default 4096
T213-SDK-2  AccelTremorFFTResult has bin_width_hz field with default 0.244
T213-SDK-3  VAPIAccelTremorFFT.status() parses accel_fft_nfft from response body
T213-SDK-4  VAPIAccelTremorFFT.status() parses bin_width_hz from response body
"""
from __future__ import annotations

import dataclasses
import io
import json
import os
import sys
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from vapi_sdk import AccelTremorFFTResult, VAPIAccelTremorFFT  # noqa: E402


def _make_mock_response(body: dict):
    mock_resp = MagicMock()
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = MagicMock(return_value=False)
    mock_resp.read.return_value = json.dumps(body).encode()
    return mock_resp


# ---------------------------------------------------------------------------
# T213-SDK-1  accel_fft_nfft field present with default 4096
# ---------------------------------------------------------------------------
class TestT213SDK1_AccelFftNfft(unittest.TestCase):
    def test_field_exists(self):
        fields = {f.name for f in dataclasses.fields(AccelTremorFFTResult)}
        self.assertIn("accel_fft_nfft", fields,
            "AccelTremorFFTResult must have accel_fft_nfft field (Phase 213)")

    def test_default_is_4096(self):
        r = AccelTremorFFTResult(
            accel_tremor_fallback_enabled=True,
            still_hold_var_threshold=4.0,
            fallback_source="accel_magnitude_fft",
            tremor_search_range_hz=[1.0, 15.0],
        )
        self.assertEqual(r.accel_fft_nfft, 4096,
            "accel_fft_nfft default must be 4096")

    def test_field_type_is_int(self):
        r = AccelTremorFFTResult(
            accel_tremor_fallback_enabled=True,
            still_hold_var_threshold=4.0,
            fallback_source="accel_magnitude_fft",
            tremor_search_range_hz=[1.0, 15.0],
        )
        self.assertIsInstance(r.accel_fft_nfft, int)


# ---------------------------------------------------------------------------
# T213-SDK-2  bin_width_hz field present with default 0.244
# ---------------------------------------------------------------------------
class TestT213SDK2_BinWidthHz(unittest.TestCase):
    def test_field_exists(self):
        fields = {f.name for f in dataclasses.fields(AccelTremorFFTResult)}
        self.assertIn("bin_width_hz", fields,
            "AccelTremorFFTResult must have bin_width_hz field (Phase 213)")

    def test_default_is_0_244(self):
        r = AccelTremorFFTResult(
            accel_tremor_fallback_enabled=True,
            still_hold_var_threshold=4.0,
            fallback_source="accel_magnitude_fft",
            tremor_search_range_hz=[1.0, 15.0],
        )
        self.assertAlmostEqual(r.bin_width_hz, 0.244, places=3,
            msg="bin_width_hz default must be ~0.244 (1000 Hz / 4096)")

    def test_field_type_is_float(self):
        r = AccelTremorFFTResult(
            accel_tremor_fallback_enabled=True,
            still_hold_var_threshold=4.0,
            fallback_source="accel_magnitude_fft",
            tremor_search_range_hz=[1.0, 15.0],
        )
        self.assertIsInstance(r.bin_width_hz, float)


# ---------------------------------------------------------------------------
# T213-SDK-3  VAPIAccelTremorFFT.status() parses accel_fft_nfft
# ---------------------------------------------------------------------------
class TestT213SDK3_ParseAccelFftNfft(unittest.TestCase):
    def _status_from_body(self, body: dict) -> AccelTremorFFTResult:
        mock_resp = _make_mock_response(body)
        with patch("urllib.request.urlopen", return_value=mock_resp):
            client = VAPIAccelTremorFFT("http://localhost:8080", "test-key")
            return client.status()

    def test_parses_accel_fft_nfft_4096(self):
        body = {
            "accel_tremor_fallback_enabled": True,
            "still_hold_var_threshold": 4.0,
            "fallback_source": "accel_magnitude_fft",
            "tremor_search_range_hz": [1.0, 15.0],
            "accel_fft_nfft": 4096,
            "bin_width_hz": 0.244,
            "timestamp": 1.0,
        }
        result = self._status_from_body(body)
        self.assertEqual(result.accel_fft_nfft, 4096)

    def test_parses_custom_nfft(self):
        body = {
            "accel_tremor_fallback_enabled": True,
            "still_hold_var_threshold": 4.0,
            "fallback_source": "accel_magnitude_fft",
            "tremor_search_range_hz": [1.0, 15.0],
            "accel_fft_nfft": 2048,
            "bin_width_hz": 0.488,
            "timestamp": 1.0,
        }
        result = self._status_from_body(body)
        self.assertEqual(result.accel_fft_nfft, 2048)

    def test_defaults_to_4096_when_absent(self):
        body = {
            "accel_tremor_fallback_enabled": True,
            "still_hold_var_threshold": 4.0,
            "fallback_source": "accel_magnitude_fft",
            "tremor_search_range_hz": [1.0, 15.0],
            "timestamp": 1.0,
        }
        result = self._status_from_body(body)
        self.assertEqual(result.accel_fft_nfft, 4096,
            "accel_fft_nfft must default to 4096 when absent from response")


# ---------------------------------------------------------------------------
# T213-SDK-4  VAPIAccelTremorFFT.status() parses bin_width_hz
# ---------------------------------------------------------------------------
class TestT213SDK4_ParseBinWidthHz(unittest.TestCase):
    def _status_from_body(self, body: dict) -> AccelTremorFFTResult:
        mock_resp = _make_mock_response(body)
        with patch("urllib.request.urlopen", return_value=mock_resp):
            return VAPIAccelTremorFFT("http://localhost:8080").status()

    def test_parses_bin_width_hz(self):
        body = {
            "accel_tremor_fallback_enabled": True,
            "still_hold_var_threshold": 4.0,
            "fallback_source": "accel_magnitude_fft",
            "tremor_search_range_hz": [1.0, 15.0],
            "accel_fft_nfft": 4096,
            "bin_width_hz": 0.2441,
            "timestamp": 1.0,
        }
        result = self._status_from_body(body)
        self.assertAlmostEqual(result.bin_width_hz, 0.2441, places=4)

    def test_defaults_to_0_244_when_absent(self):
        body = {
            "accel_tremor_fallback_enabled": True,
            "still_hold_var_threshold": 4.0,
            "fallback_source": "accel_magnitude_fft",
            "tremor_search_range_hz": [1.0, 15.0],
            "timestamp": 1.0,
        }
        result = self._status_from_body(body)
        self.assertAlmostEqual(result.bin_width_hz, 0.244, places=3,
            msg="bin_width_hz must default to 0.244 when absent from response")


if __name__ == "__main__":
    unittest.main()
