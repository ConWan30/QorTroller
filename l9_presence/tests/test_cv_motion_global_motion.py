"""phaseCorrelate global-pan estimator for cv_motion.frames_to_motion (replaces dense Farneback).

The coupling oracle only consumes the MEAN flow = a single global yaw/pitch pan, which phaseCorrelate computes
directly (the dense field was averaged away anyway). These tests pin the direction + axis-separation +
scale-linearity contract the coupling depends on, exercised on the small (downscaled) gray the slice-at-source
capture path produces. frames_to_motion was previously untested (the WGC callback is the live-validated I/O
boundary); this makes the estimator deterministically testable. Convention (empirically): phaseCorrelate(prev,
cur) returns the prev->cur global shift same-sign as the motion, and frames_to_motion negates it, so a +x scene
shift yields yaw_rate < 0 (camera-pan convention, identical to the old Farneback mean-flow sign)."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import numpy as np  # noqa: E402
import pytest  # noqa: E402

try:
    import cv2  # noqa: F401
    from l9_presence.cv_motion import frames_to_motion  # noqa: E402
    _CV2 = True
except Exception:
    _CV2 = False

pytestmark = pytest.mark.skipif(not _CV2, reason="opencv-python not installed")


def _textured(h: int = 270, w: int = 480, seed: int = 0) -> "np.ndarray":
    """A textured gray frame phaseCorrelate can lock onto (pure noise has no dominant spectral peak).
    Size defaults to 270x480 = the 1080p/4 gray the slice-at-source path produces at downscale=4."""
    rng = np.random.default_rng(seed)
    base = rng.random((h, w)).astype(np.float32)
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    base += 2.0 * np.sin(xx / 23.0) + 2.0 * np.cos(yy / 19.0)   # low-freq structure -> a detectable shift
    span = float(base.max() - base.min()) + 1e-6
    return (255.0 * (base - base.min()) / span).astype(np.uint8)


def _shift(img: "np.ndarray", dx: int, dy: int) -> "np.ndarray":
    """cur = prev shifted by (+dx, +dy) px. np.roll is circular, which is exactly phaseCorrelate's model."""
    return np.roll(np.roll(img, dy, axis=0), dx, axis=1)


def test_horizontal_pan_drives_yaw_not_pitch():
    prev = _textured()
    m = frames_to_motion(prev, _shift(prev, 6, 0), dt_s=0.1)
    assert abs(m.yaw_rate) > 1.0                         # detected the pan
    assert abs(m.pitch_rate) < 0.25 * abs(m.yaw_rate)    # x-shift -> yaw dominant, pitch ~0
    assert m.yaw_rate < 0                                # +x scene shift -> negative yaw (camera-pan convention)


def test_vertical_pan_drives_pitch_not_yaw():
    prev = _textured(seed=1)
    m = frames_to_motion(prev, _shift(prev, 0, 5), dt_s=0.1)
    assert abs(m.pitch_rate) > 1.0
    assert abs(m.yaw_rate) < 0.25 * abs(m.pitch_rate)
    assert m.pitch_rate < 0


def test_opposite_shifts_give_opposite_yaw():
    prev = _textured(seed=2)
    mp = frames_to_motion(prev, _shift(prev, 6, 0), dt_s=0.1)
    mn = frames_to_motion(prev, _shift(prev, -6, 0), dt_s=0.1)
    assert np.sign(mp.yaw_rate) == -np.sign(mn.yaw_rate)   # direction reverses with pan direction (Pearson r)


def test_rate_scales_inversely_with_dt():
    prev = _textured(seed=3)
    cur = _shift(prev, 8, 0)
    m_fast = frames_to_motion(prev, cur, dt_s=0.1)
    m_slow = frames_to_motion(prev, cur, dt_s=0.2)
    assert m_fast.yaw_rate == pytest.approx(2.0 * m_slow.yaw_rate, rel=0.15)   # rate = shift / dt


def test_no_motion_is_near_zero():
    prev = _textured(seed=4)
    m = frames_to_motion(prev, prev.copy(), dt_s=0.1)
    assert abs(m.yaw_rate) < 1.0 and abs(m.pitch_rate) < 1.0


def test_returns_framemotion_contract():
    prev = _textured(seed=5)
    m = frames_to_motion(prev, _shift(prev, 3, 2), dt_s=0.05)
    assert hasattr(m, "yaw_rate") and hasattr(m, "pitch_rate") and hasattr(m, "flow_energy")
    assert m.flow_energy >= 0.0                          # global-shift magnitude / dt, never negative
