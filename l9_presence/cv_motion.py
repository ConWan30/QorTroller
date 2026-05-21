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
_FARNEBACK = dict(pyr_scale=0.5, levels=3, winsize=15, iterations=3,
                  poly_n=5, poly_sigma=1.2, flags=0)


@dataclass
class FrameMotion:
    yaw_rate: float          # mean horizontal flow / dt  (camera pan proxy)
    pitch_rate: float        # mean vertical   flow / dt
    flow_energy: float       # mean |flow| — overall on-screen motion magnitude


def to_gray_small(frame_bgr: "np.ndarray") -> "np.ndarray":
    """BGR/RGB frame -> downscaled grayscale (the CV working image)."""
    if not _CV2:
        raise RuntimeError("opencv-python not installed (pip install opencv-python)")
    if frame_bgr.ndim == 3:
        gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
    else:
        gray = frame_bgr
    if DOWNSCALE > 1:
        gray = cv2.resize(gray, (gray.shape[1] // DOWNSCALE, gray.shape[0] // DOWNSCALE),
                          interpolation=cv2.INTER_AREA)
    return gray


def frames_to_motion(prev_gray: "np.ndarray", gray: "np.ndarray", dt_s: float) -> FrameMotion:
    """Dense optical flow between two grayscale frames -> motion proxy."""
    if not _CV2:
        raise RuntimeError("opencv-python not installed (pip install opencv-python)")
    dt_s = max(float(dt_s), 1e-3)
    flow = cv2.calcOpticalFlowFarneback(prev_gray, gray, None, **_FARNEBACK)
    fx = float(np.mean(flow[..., 0]))
    fy = float(np.mean(flow[..., 1]))
    energy = float(np.mean(np.hypot(flow[..., 0], flow[..., 1])))
    # scene flows OPPOSITE the camera pan -> negate so yaw_rate tracks camera motion
    return FrameMotion(yaw_rate=-fx / dt_s, pitch_rate=-fy / dt_s, flow_energy=energy / dt_s)


class MotionExtractor:
    """Stateful per-frame motion extractor. Feed frames in order with timestamps;
    get a FrameMotion once a previous frame exists."""

    def __init__(self) -> None:
        self._prev: Optional["np.ndarray"] = None
        self._prev_ts_ms: Optional[float] = None

    def push_frame(self, frame_bgr: "np.ndarray", ts_ms: float) -> Optional[Tuple[float, FrameMotion]]:
        """Return (ts_ms, FrameMotion) for this frame, or None for the first frame."""
        gray = to_gray_small(frame_bgr)
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
