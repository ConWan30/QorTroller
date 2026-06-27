"""QorTroller L9 — on-screen camera angular velocity from frames (DESIGN-ONLY).

Deterministic local computer vision (no cloud model). Estimates how much the
game view PANNED between consecutive frames via dense optical flow, yielding a
yaw_rate / pitch_rate proxy that feeds coupling.InputOutputCouplingOracle.

Method: mean global optical flow on a downscaled grayscale frame.
  mean horizontal flow / dt -> yaw_rate proxy
  mean vertical   flow / dt -> pitch_rate proxy
These are *proxies* (uncalibrated to degrees) — fine, because the coupling score
uses Pearson r, which is invariant to linear scale.

Requires opencv-python (import-guarded). Offline-first: validate extraction
against eyeball ground truth on a few clips before trusting the score
(see README "CV validation" gate). Real-time at 60fps may need the downscale
factor raised; that is a Step-3 (shadow) optimization, not a probe blocker.

STATUS: design-only probe scaffold. No FROZEN-v1 primitive, no chain.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

try:
    import cv2  # type: ignore
    _CV2 = True
except Exception:  # pragma: no cover - env without opencv
    _CV2 = False

import numpy as np

DOWNSCALE: int = 4          # process at 1/DOWNSCALE resolution for speed

# Cached Hanning windows for phaseCorrelate (keyed by (h, w)); the window size only changes when the
# Adaptive Capture Governor changes downscale, so recreating it per frame would be wasteful.
_HANNING_CACHE: dict = {}


def _hanning_for(shape) -> "np.ndarray":
    """Hanning window matching a grayscale frame's (h, w), cached. Reduces phaseCorrelate edge spectral
    leakage. Only called after the _CV2 guard in frames_to_motion."""
    key = (int(shape[0]), int(shape[1]))
    win = _HANNING_CACHE.get(key)
    if win is None:
        win = cv2.createHanningWindow((key[1], key[0]), cv2.CV_32F)   # cv2 size is (width, height)
        _HANNING_CACHE[key] = win
    return win


@dataclass
class FrameMotion:
    yaw_rate: float          # mean horizontal flow / dt  (camera pan proxy)
    pitch_rate: float        # mean vertical   flow / dt
    flow_energy: float       # mean |flow| — overall on-screen motion magnitude


def to_gray_small(frame_bgr: "np.ndarray", downscale: int = DOWNSCALE) -> "np.ndarray":
    """BGR/RGB frame -> downscaled grayscale (the CV working image).

    `downscale` is overridable so the Adaptive Capture Governor can trade flow resolution
    for frame rate in real time (higher downscale = cheaper frames = steadier fps)."""
    if not _CV2:
        raise RuntimeError("opencv-python not installed (pip install opencv-python)")
    if frame_bgr.ndim == 3:
        gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
    else:
        gray = frame_bgr
    d = max(1, int(downscale))
    if d > 1:
        gray = cv2.resize(gray, (gray.shape[1] // d, gray.shape[0] // d),
                          interpolation=cv2.INTER_AREA)
    return gray


def frames_to_motion(prev_gray: "np.ndarray", gray: "np.ndarray", dt_s: float) -> FrameMotion:
    """Global on-screen pan between two grayscale frames -> motion proxy.

    Uses phase correlation (a frequency-domain global-shift estimator) rather than dense optical flow: the
    coupling oracle consumes only the MEAN flow (a single global yaw/pitch pan), which cv2.phaseCorrelate
    computes DIRECTLY ~50x faster than calcOpticalFlowFarneback + np.mean -- the dense field was discarded
    after averaging anyway. Coupling scores via Pearson r (scale-invariant), so the proxy's absolute scale is
    irrelevant; only relative motion over time matters. Inputs must be the same size (the capture-loop shape
    guard guarantees it)."""
    if not _CV2:
        raise RuntimeError("opencv-python not installed (pip install opencv-python)")
    dt_s = max(float(dt_s), 1e-3)
    p = prev_gray.astype(np.float32)
    g = gray.astype(np.float32)
    (dx, dy), _response = cv2.phaseCorrelate(p, g, _hanning_for(p.shape))
    # phaseCorrelate(prev, cur) returns the prev->cur global shift (same direction as the old Farneback mean
    # flow); the scene shifts OPPOSITE the camera pan, so negate to keep yaw_rate tracking camera motion with
    # the same sign convention as before (absolute sign re-validated live via COUPLED_CLEAN).
    energy = float((dx * dx + dy * dy) ** 0.5)
    return FrameMotion(yaw_rate=-float(dx) / dt_s, pitch_rate=-float(dy) / dt_s, flow_energy=energy / dt_s)


class MotionExtractor:
    """Stateful per-frame motion extractor. Feed frames in order with timestamps;
    get a FrameMotion once a previous frame exists."""

    def __init__(self, downscale: Optional[int] = None) -> None:
        self._prev: Optional["np.ndarray"] = None
        self._prev_ts_ms: Optional[float] = None
        self._downscale: int = int(downscale) if downscale else DOWNSCALE

    def set_downscale(self, downscale: int) -> None:
        """Retune flow resolution live (Adaptive Capture Governor). Resets the prev frame so
        the next flow is computed at the new scale (mismatched-size frames can't be flowed)."""
        d = max(1, int(downscale))
        if d != self._downscale:
            self._downscale = d
            self._prev = None  # force re-seed at the new resolution

    def push_frame(self, frame_bgr: "np.ndarray", ts_ms: float) -> Optional[Tuple[float, FrameMotion]]:
        """Return (ts_ms, FrameMotion) for this frame, or None for the first frame."""
        gray = to_gray_small(frame_bgr, self._downscale)
        if self._prev is None:
            self._prev, self._prev_ts_ms = gray, ts_ms
            return None
        dt_s = (ts_ms - (self._prev_ts_ms or ts_ms)) / 1000.0
        m = frames_to_motion(self._prev, gray, dt_s)
        self._prev, self._prev_ts_ms = gray, ts_ms
        return ts_ms, m

    def reset(self) -> None:
        self._prev, self._prev_ts_ms = None, None


def opencv_available() -> bool:
    return _CV2
