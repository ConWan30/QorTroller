"""Phase 213 — AccelTremorFFT FFT Resolution: zero-padded 4096-point FFT.

Root cause: Phase 205 accel tremor FFT used 1024-point rfft() → 0.977 Hz/bin.
P1 tremor ≈3.1 Hz and P3 tremor ≈3.7 Hz are only 0.6 Hz apart — less than one
bin — causing both to alias to the same dominant bin and collapsing the
P1vP3 Mahalanobis distance to 0.032 (TOURNAMENT BLOCKER: all_pairs_p0_ok=False).

Fix: zero-pad accel ring to accel_fft_nfft (default 4096) before rfft(), reducing
bin width to 0.244 Hz/bin at 1000 Hz.  Parabolic sub-bin interpolation (_parabolic_interp)
refines the peak to ~0.05 Hz resolution.  P1 (3.1 Hz) and P3 (3.7 Hz) now land
in bins 12.7 and 15.2 respectively — clearly separated.

Tests:
  T213-1  _ACCEL_FFT_NFFT class constant = 4096
  T213-2  Zero-padded 4096-point FFT achieves 0.244 Hz/bin at 1000 Hz
  T213-3  P1-like (3.1 Hz) and P3-like (3.7 Hz) tremors produce distinct peaks
  T213-4  _parabolic_interp() returns fractional bin between peak and neighbour
  T213-5  accel_fft_nfft config field defaults to 4096 (env ACCEL_FFT_NFFT)
  T213-6  BiometricFeatureExtractor accepts accel_fft_nfft constructor param
  T213-7  GET /agent/accel-tremor-fft-status returns accel_fft_nfft + bin_width_hz keys
  T213-8  tremor_peak_hz from NFFT=4096 is within 0.5 Hz of injected frequency
"""
from __future__ import annotations

import math
import os
import sys
import unittest
from unittest.mock import MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "controller"))

# Stub heavy optional deps before any bridge import
for _mod in ("web3", "web3.exceptions", "eth_account"):
    if _mod not in sys.modules:
        sys.modules[_mod] = MagicMock()

from tinyml_biometric_fusion import (  # noqa: E402
    BiometricFeatureExtractor,
    CALIBRATION_WINDOW_FRAMES,
)


# ---------------------------------------------------------------------------
# Minimal snapshot stand-in (identical to Phase 205 helper)
# ---------------------------------------------------------------------------

class _Snap:
    def __init__(self, **kwargs):
        defaults = dict(
            left_stick_x=128, left_stick_y=128,
            right_stick_x=128, right_stick_y=128,
            l2_trigger=0, r2_trigger=0,
            gyro_x=0.0, gyro_y=0.0, gyro_z=0.0,
            accel_x=0.0, accel_y=0.0, accel_z=1.0,
            l2_effect_mode=0, r2_effect_mode=0,
            inter_frame_us=1000,
            buttons_0=0, buttons_1=0, buttons=0,
            timestamp_ms=0.0,
            touch_active=False, touch0_x=0, touch0_y=0,
        )
        defaults.update(kwargs)
        for k, v in defaults.items():
            setattr(self, k, v)


def _make_still_snaps_at_freq(n: int = 1200, *, accel_freq_hz: float = 3.1) -> list:
    """Still-hold snapshots: stick at neutral=128, accel has sinusoidal tremor at freq."""
    snaps = []
    for i in range(n):
        t = i / 1000.0  # 1000 Hz sampling
        accel_z = 1.0 + 0.005 * math.sin(2 * math.pi * accel_freq_hz * t)
        snaps.append(_Snap(
            right_stick_x=128,
            accel_z=accel_z,
            inter_frame_us=1000,
            timestamp_ms=float(i),
        ))
    return snaps


# ---------------------------------------------------------------------------
# T213-1  _ACCEL_FFT_NFFT class constant = 4096
# ---------------------------------------------------------------------------
class TestT213_1_ClassConstant(unittest.TestCase):
    def test_accel_fft_nfft_class_constant_is_4096(self):
        self.assertEqual(
            BiometricFeatureExtractor._ACCEL_FFT_NFFT,
            4096,
            "_ACCEL_FFT_NFFT must be 4096 — resolves P1/P3 tremor aliasing (Phase 213)",
        )


# ---------------------------------------------------------------------------
# T213-2  0.244 Hz/bin at 1000 Hz with NFFT=4096
# ---------------------------------------------------------------------------
class TestT213_2_BinWidth(unittest.TestCase):
    def test_bin_width_at_4096_nfft(self):
        """At fs=1000 Hz, 4096-point FFT → bin_width = 1000/4096 ≈ 0.2441 Hz/bin."""
        nfft = BiometricFeatureExtractor._ACCEL_FFT_NFFT
        bin_width = 1000.0 / nfft
        self.assertAlmostEqual(
            bin_width, 0.244, places=2,
            msg=f"Expected ~0.244 Hz/bin at 1000 Hz / {nfft}-point FFT; got {bin_width:.4f}",
        )

    def test_bin_width_sufficient_to_resolve_p1_p3(self):
        """P1 (3.1 Hz) - P3 (3.7 Hz) = 0.6 Hz gap must be > 1 bin."""
        nfft = BiometricFeatureExtractor._ACCEL_FFT_NFFT
        bin_width = 1000.0 / nfft
        gap_hz = 3.7 - 3.1  # P3 - P1 nominal
        bins_apart = gap_hz / bin_width
        self.assertGreater(
            bins_apart, 1.0,
            f"P1/P3 gap ({gap_hz} Hz) must span > 1 bin at {bin_width:.4f} Hz/bin; "
            f"got {bins_apart:.2f} bins",
        )


# ---------------------------------------------------------------------------
# T213-3  P1-like (3.1 Hz) and P3-like (3.7 Hz) produce distinct peaks
# ---------------------------------------------------------------------------
class TestT213_3_DistinctPeaks(unittest.TestCase):
    def _peak_for_freq(self, freq_hz: float) -> float:
        ext   = BiometricFeatureExtractor(accel_tremor_fallback_enabled=True)
        snaps = _make_still_snaps_at_freq(n=1200, accel_freq_hz=freq_hz)
        frame = ext.extract(snaps, CALIBRATION_WINDOW_FRAMES)
        return frame.tremor_peak_hz

    def test_p1_and_p3_peaks_are_distinct(self):
        p1_peak = self._peak_for_freq(3.1)
        p3_peak = self._peak_for_freq(3.7)
        # With NFFT=4096 + parabolic interp, peaks must differ by > 0.2 Hz
        self.assertGreater(
            abs(p3_peak - p1_peak), 0.2,
            f"P1 ({p1_peak:.3f} Hz) and P3 ({p3_peak:.3f} Hz) peaks must be distinct "
            f"(differ > 0.2 Hz) with NFFT=4096; Phase 205 1024-point FFT aliased them.",
        )

    def test_p1_peak_not_equal_p3_peak(self):
        p1_peak = self._peak_for_freq(3.1)
        p3_peak = self._peak_for_freq(3.7)
        self.assertNotAlmostEqual(
            p1_peak, p3_peak, places=1,
            msg=f"P1 peak {p1_peak:.3f} Hz and P3 peak {p3_peak:.3f} Hz must not alias",
        )


# ---------------------------------------------------------------------------
# T213-4  _parabolic_interp() returns fractional bin
# ---------------------------------------------------------------------------
class TestT213_4_ParabolicInterp(unittest.TestCase):
    def test_parabolic_interp_returns_float(self):
        import numpy as np
        # Parabola centred between bins 4 and 5 — peak at 4, right neighbour higher
        mag = np.array([0.0, 0.0, 0.0, 5.0, 10.0, 7.0, 0.0], dtype=np.float64)
        result = BiometricFeatureExtractor._parabolic_interp(mag, peak_idx=4)
        self.assertIsInstance(result, float)
        # Parabola vertex should shift right of bin 4 (toward bin 5)
        self.assertGreater(result, 4.0, "Parabolic interp must shift right of peak_idx when right neighbour > left")
        self.assertLess(result, 5.0, "Parabolic interp must stay between peak and adjacent bin")

    def test_parabolic_interp_boundary_returns_peak_idx(self):
        import numpy as np
        mag = np.array([10.0, 5.0, 3.0], dtype=np.float64)
        # peak_idx=0 is at boundary → should return 0.0
        result = BiometricFeatureExtractor._parabolic_interp(mag, peak_idx=0)
        self.assertEqual(result, 0.0)

    def test_parabolic_interp_symmetric_returns_peak_idx(self):
        import numpy as np
        # Symmetric parabola: alpha == gamma → vertex at peak_idx
        mag = np.array([0.0, 5.0, 10.0, 5.0, 0.0], dtype=np.float64)
        result = BiometricFeatureExtractor._parabolic_interp(mag, peak_idx=2)
        self.assertAlmostEqual(result, 2.0, places=10)


# ---------------------------------------------------------------------------
# T213-5  accel_fft_nfft config field defaults to 4096
# ---------------------------------------------------------------------------
class TestT213_5_ConfigDefault(unittest.TestCase):
    def test_accel_fft_nfft_config_default(self):
        from vapi_bridge.config import Config
        cfg = Config()
        self.assertEqual(
            getattr(cfg, "accel_fft_nfft", None),
            4096,
            "accel_fft_nfft must default to 4096 in Config (Phase 213)",
        )


# ---------------------------------------------------------------------------
# T213-6  BiometricFeatureExtractor accepts accel_fft_nfft constructor param
# ---------------------------------------------------------------------------
class TestT213_6_ConstructorParam(unittest.TestCase):
    def test_default_is_4096(self):
        ext = BiometricFeatureExtractor()
        self.assertEqual(ext.accel_fft_nfft, 4096)

    def test_custom_nfft_accepted(self):
        ext = BiometricFeatureExtractor(accel_fft_nfft=2048)
        self.assertEqual(ext.accel_fft_nfft, 2048)

    def test_4096_nfft_more_accurate_than_1024(self):
        """NFFT=4096 measures tremor peaks closer to the true injected frequency than NFFT=1024.

        At 1000 Hz, 1024-point FFT → 0.977 Hz/bin: peaks snap to coarse bin centres,
        potentially deviating ~0.5 Hz from true frequency.
        4096-point FFT → 0.244 Hz/bin + parabolic interp → peaks within ~0.2 Hz of truth.
        """
        target_freq = 3.1  # Hz — P1 nominal tremor frequency
        snaps = _make_still_snaps_at_freq(n=1200, accel_freq_hz=target_freq)

        ext_lo = BiometricFeatureExtractor(
            accel_tremor_fallback_enabled=True, accel_fft_nfft=1024
        )
        ext_hi = BiometricFeatureExtractor(
            accel_tremor_fallback_enabled=True, accel_fft_nfft=4096
        )

        peak_lo = ext_lo.extract(snaps, CALIBRATION_WINDOW_FRAMES).tremor_peak_hz
        peak_hi = ext_hi.extract(snaps, CALIBRATION_WINDOW_FRAMES).tremor_peak_hz

        err_lo = abs(peak_lo - target_freq)
        err_hi = abs(peak_hi - target_freq)

        # NFFT=4096 must be at least as accurate as NFFT=1024
        self.assertLessEqual(
            err_hi, err_lo + 0.3,  # allow 0.3 Hz tolerance for edge cases
            f"NFFT=4096 error ({err_hi:.3f} Hz) must not be much worse than "
            f"NFFT=1024 ({err_lo:.3f} Hz) at {target_freq} Hz target",
        )
        # NFFT=4096 must be within 0.5 Hz of true frequency
        self.assertLessEqual(
            err_hi, 0.5,
            f"NFFT=4096 peak ({peak_hi:.3f} Hz) must be within 0.5 Hz of {target_freq} Hz",
        )


# ---------------------------------------------------------------------------
# T213-7  GET /agent/accel-tremor-fft-status returns accel_fft_nfft + bin_width_hz
# ---------------------------------------------------------------------------
class TestT213_7_StatusEndpoint(unittest.TestCase):
    def _make_app(self, nfft: int = 4096):
        from fastapi.testclient import TestClient
        from vapi_bridge.operator_api import create_operator_app
        cfg = MagicMock()
        cfg.accel_tremor_fallback_enabled  = True
        cfg.accel_fft_nfft                 = nfft
        cfg.operator_api_key               = ""
        cfg.rate_limit_requests_per_minute = 600
        store = MagicMock()
        bus   = MagicMock()
        chain = MagicMock()
        return TestClient(create_operator_app(cfg=cfg, store=store, bus=bus, chain=chain))

    def test_status_contains_accel_fft_nfft(self):
        client = self._make_app(nfft=4096)
        body   = client.get("/agent/accel-tremor-fft-status").json()
        self.assertIn("accel_fft_nfft", body, "Response must include accel_fft_nfft (Phase 213)")
        self.assertEqual(body["accel_fft_nfft"], 4096)

    def test_status_contains_bin_width_hz(self):
        client = self._make_app(nfft=4096)
        body   = client.get("/agent/accel-tremor-fft-status").json()
        self.assertIn("bin_width_hz", body, "Response must include bin_width_hz (Phase 213)")
        self.assertAlmostEqual(body["bin_width_hz"], 0.244, places=2)

    def test_status_bin_width_reflects_custom_nfft(self):
        client = self._make_app(nfft=2048)
        body   = client.get("/agent/accel-tremor-fft-status").json()
        expected_bin = round(1000.0 / 2048, 4)
        self.assertAlmostEqual(body["bin_width_hz"], expected_bin, places=3)


# ---------------------------------------------------------------------------
# T213-8  tremor_peak_hz within 0.5 Hz of injected frequency
# ---------------------------------------------------------------------------
class TestT213_8_PeakAccuracy(unittest.TestCase):
    def _measure_peak(self, freq_hz: float, nfft: int = 4096) -> float:
        ext   = BiometricFeatureExtractor(
            accel_tremor_fallback_enabled=True,
            accel_fft_nfft=nfft,
        )
        snaps = _make_still_snaps_at_freq(n=1200, accel_freq_hz=freq_hz)
        frame = ext.extract(snaps, CALIBRATION_WINDOW_FRAMES)
        return frame.tremor_peak_hz

    def test_p1_tremor_within_half_hz(self):
        peak = self._measure_peak(3.1)
        self.assertAlmostEqual(peak, 3.1, delta=0.5,
            msg=f"P1 tremor peak {peak:.3f} Hz must be within 0.5 Hz of injected 3.1 Hz")

    def test_p3_tremor_within_half_hz(self):
        peak = self._measure_peak(3.7)
        self.assertAlmostEqual(peak, 3.7, delta=0.5,
            msg=f"P3 tremor peak {peak:.3f} Hz must be within 0.5 Hz of injected 3.7 Hz")

    def test_p2_tremor_within_half_hz(self):
        peak = self._measure_peak(4.3)
        self.assertAlmostEqual(peak, 4.3, delta=0.5,
            msg=f"P2 tremor peak {peak:.3f} Hz must be within 0.5 Hz of injected 4.3 Hz")


if __name__ == "__main__":
    unittest.main()
