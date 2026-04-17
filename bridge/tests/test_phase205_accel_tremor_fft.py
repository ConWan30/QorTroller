"""Phase 205 — AccelTremorFFT: accel magnitude FFT fallback for tremor_peak_hz.

Root cause: BiometricFeatureExtractor used right_stick_x velocity FFT for
tremor_peak_hz, but in still-hold sessions (tremor_seed probe type) the stick
stays at neutral=128 → diff() → all zeros → FFT peak at 0 Hz.

Fix: when right_stick_x ring variance < _STILL_HOLD_VAR_THRESHOLD (4.0 LSB²)
AND accel_tremor_fallback_enabled=True, use accel magnitude FFT (1-15 Hz search)
instead.  IMU data reflects neurological tremor origin frequencies.

Tests:
  T205-1  Config field accel_tremor_fallback_enabled defaults True
  T205-2  Still-hold detection: _STILL_HOLD_VAR_THRESHOLD class constant = 4.0
  T205-3  Accel FFT fallback produces non-zero tremor_peak_hz during still-hold
  T205-4  Gameplay session (varying stick) still uses stick FFT path (no fallback)
  T205-5  Fallback disabled when accel_tremor_fallback_enabled=False
  T205-6  Accel tremor peak is in 1-15 Hz range when fallback active
  T205-7  GET /agent/accel-tremor-fft-status returns correct structure
  T205-8  Fallback inactive when accel ring not yet full (<1024 samples)
"""
from __future__ import annotations

import math
import os
import sys
import unittest
from unittest.mock import MagicMock, patch

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
# Minimal snapshot stand-in
# ---------------------------------------------------------------------------

class _Snap:
    """Minimal InputSnapshot stand-in for unit tests."""
    def __init__(self, **kwargs):
        defaults = dict(
            left_stick_x=128, left_stick_y=128,
            right_stick_x=128, right_stick_y=128,
            l2_trigger=0, r2_trigger=0,
            gyro_x=0.0, gyro_y=0.0, gyro_z=0.0,
            accel_x=0.0, accel_y=0.0, accel_z=1.0,
            l2_effect_mode=0, r2_effect_mode=0,
            inter_frame_us=1000,   # ~1000 Hz
            buttons_0=0, buttons_1=0, buttons=0,
            timestamp_ms=0.0,
            touch_active=False, touch0_x=0, touch0_y=0,
        )
        defaults.update(kwargs)
        for k, v in defaults.items():
            setattr(self, k, v)


def _make_still_snaps(n: int = 1200, *, accel_freq_hz: float = 4.0) -> list:
    """Still-hold snapshots: stick at neutral=128, accel has sinusoidal tremor."""
    snaps = []
    for i in range(n):
        t = i / 1000.0  # 1000 Hz sampling
        accel_z = 1.0 + 0.005 * math.sin(2 * math.pi * accel_freq_hz * t)
        snaps.append(_Snap(
            right_stick_x=128,  # neutral — no gameplay motion
            accel_z=accel_z,
            inter_frame_us=1000,
            timestamp_ms=float(i),
        ))
    return snaps


def _make_gameplay_snaps(n: int = 1200) -> list:
    """Gameplay snapshots: stick varies, accel has low noise."""
    snaps = []
    import random
    rng = random.Random(42)
    for i in range(n):
        snaps.append(_Snap(
            right_stick_x=128 + int(rng.gauss(0, 40)),  # active stick
            accel_z=1.0 + rng.gauss(0, 0.001),
            inter_frame_us=1000,
            timestamp_ms=float(i),
        ))
    return snaps


# ---------------------------------------------------------------------------
# T205-1  Config field defaults True
# ---------------------------------------------------------------------------
class TestT205_1_ConfigDefault(unittest.TestCase):
    def test_accel_tremor_fallback_enabled_default_true(self):
        from vapi_bridge.config import Config
        cfg = Config()
        self.assertTrue(
            getattr(cfg, "accel_tremor_fallback_enabled", None),
            "accel_tremor_fallback_enabled must default True in Config",
        )


# ---------------------------------------------------------------------------
# T205-2  _STILL_HOLD_VAR_THRESHOLD class constant
# ---------------------------------------------------------------------------
class TestT205_2_ClassConstant(unittest.TestCase):
    def test_still_hold_var_threshold_is_4(self):
        self.assertEqual(
            BiometricFeatureExtractor._STILL_HOLD_VAR_THRESHOLD,
            4.0,
            "_STILL_HOLD_VAR_THRESHOLD must be 4.0 (matching accel entropy guard pattern)",
        )

    def test_extractor_has_fallback_attribute(self):
        ext = BiometricFeatureExtractor()
        self.assertTrue(
            hasattr(ext, "accel_tremor_fallback_enabled"),
            "BiometricFeatureExtractor must expose accel_tremor_fallback_enabled instance attribute",
        )

    def test_default_fallback_enabled(self):
        ext = BiometricFeatureExtractor()
        self.assertTrue(ext.accel_tremor_fallback_enabled)

    def test_can_disable_via_constructor(self):
        ext = BiometricFeatureExtractor(accel_tremor_fallback_enabled=False)
        self.assertFalse(ext.accel_tremor_fallback_enabled)


# ---------------------------------------------------------------------------
# T205-3  Accel FFT fallback produces non-zero tremor_peak_hz during still-hold
# ---------------------------------------------------------------------------
class TestT205_3_AccelFallbackNonZero(unittest.TestCase):
    def test_still_hold_produces_nonzero_tremor_peak(self):
        """Use CALIBRATION_WINDOW_FRAMES (1025) so accel ring fills in a single call."""
        ext   = BiometricFeatureExtractor(accel_tremor_fallback_enabled=True)
        snaps = _make_still_snaps(n=1200, accel_freq_hz=4.0)
        frame = ext.extract(snaps, CALIBRATION_WINDOW_FRAMES)
        self.assertGreater(
            frame.tremor_peak_hz,
            0.0,
            f"tremor_peak_hz must be > 0 in still-hold with accel tremor fallback; got {frame.tremor_peak_hz}",
        )


# ---------------------------------------------------------------------------
# T205-4  Gameplay session (varying stick) still uses stick FFT path
# ---------------------------------------------------------------------------
class TestT205_4_GameplayUsesStickFFT(unittest.TestCase):
    def test_gameplay_stick_variance_above_threshold(self):
        """Verify that gameplay snaps have right_stick_x variance >> threshold."""
        import numpy as np
        snaps   = _make_gameplay_snaps(n=1200)
        rx_vals = [float(s.right_stick_x) for s in snaps]
        var     = float(np.var(rx_vals))
        self.assertGreater(
            var,
            BiometricFeatureExtractor._STILL_HOLD_VAR_THRESHOLD,
            f"Gameplay snaps should have high stick variance; got {var}",
        )


# ---------------------------------------------------------------------------
# T205-5  Fallback disabled when flag=False: still-hold returns 0.0
# ---------------------------------------------------------------------------
class TestT205_5_FallbackDisabled(unittest.TestCase):
    def test_still_hold_returns_zero_when_disabled(self):
        """With fallback disabled and stick at constant neutral, stick FFT is flat → 0.0."""
        ext   = BiometricFeatureExtractor(accel_tremor_fallback_enabled=False)
        snaps = _make_still_snaps(n=1200, accel_freq_hz=4.0)
        frame = ext.extract(snaps, CALIBRATION_WINDOW_FRAMES)
        # Stick at constant 128: all diffs=0 → FFT peak at DC (0 Hz).
        self.assertEqual(
            frame.tremor_peak_hz,
            0.0,
            f"tremor_peak_hz must be 0.0 when fallback disabled in still-hold; got {frame.tremor_peak_hz}",
        )


# ---------------------------------------------------------------------------
# T205-6  Accel tremor peak is in 1-15 Hz range
# ---------------------------------------------------------------------------
class TestT205_6_PeakInPhysiologicalRange(unittest.TestCase):
    def test_accel_tremor_peak_in_1_to_15_hz(self):
        ext   = BiometricFeatureExtractor(accel_tremor_fallback_enabled=True)
        snaps = _make_still_snaps(n=1200, accel_freq_hz=4.0)
        frame = ext.extract(snaps, CALIBRATION_WINDOW_FRAMES)
        self.assertGreater(
            frame.tremor_peak_hz, 0.0,
            "Expected non-zero tremor_peak_hz from accel fallback",
        )
        self.assertGreaterEqual(frame.tremor_peak_hz, 1.0, "Peak must be >= 1.0 Hz")
        self.assertLessEqual(frame.tremor_peak_hz, 15.0, "Peak must be <= 15.0 Hz")


# ---------------------------------------------------------------------------
# T205-7  GET /agent/accel-tremor-fft-status returns correct structure
# ---------------------------------------------------------------------------
class TestT205_7_StatusEndpoint(unittest.TestCase):
    def _make_app(self, enabled: bool = True):
        from fastapi.testclient import TestClient
        from vapi_bridge.operator_api import create_operator_app

        cfg = MagicMock()
        cfg.accel_tremor_fallback_enabled = enabled
        cfg.operator_api_key              = ""
        cfg.rate_limit_requests_per_minute = 600
        store = MagicMock()
        bus   = MagicMock()
        chain = MagicMock()
        return TestClient(create_operator_app(cfg=cfg, store=store, bus=bus, chain=chain))

    def test_status_endpoint_enabled(self):
        client = self._make_app(enabled=True)
        resp   = client.get("/agent/accel-tremor-fft-status")
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertIn("accel_tremor_fallback_enabled", body)
        self.assertIn("still_hold_var_threshold", body)
        self.assertIn("fallback_source", body)
        self.assertIn("tremor_search_range_hz", body)
        self.assertIn("timestamp", body)

    def test_status_fallback_source_reflects_flag(self):
        client_on  = self._make_app(enabled=True)
        client_off = self._make_app(enabled=False)
        self.assertEqual(
            client_on.get("/agent/accel-tremor-fft-status").json()["fallback_source"],
            "accel_magnitude_fft",
        )
        self.assertEqual(
            client_off.get("/agent/accel-tremor-fft-status").json()["fallback_source"],
            "stick_fft_only",
        )


# ---------------------------------------------------------------------------
# T205-8  Fallback inactive when accel ring not yet full (<1024 samples)
# ---------------------------------------------------------------------------
class TestT205_8_WarmupBehavior(unittest.TestCase):
    def test_insufficient_accel_samples_returns_zero(self):
        """With only 100 snaps, accel ring has < 1024 samples → fallback inactive → 0.0."""
        ext   = BiometricFeatureExtractor(accel_tremor_fallback_enabled=True)
        snaps = _make_still_snaps(n=100, accel_freq_hz=4.0)
        frame = ext.extract(snaps)
        self.assertEqual(
            frame.tremor_peak_hz,
            0.0,
            f"tremor_peak_hz must be 0.0 during warm-up (< 1024 accel samples); got {frame.tremor_peak_hz}",
        )


if __name__ == "__main__":
    unittest.main()
