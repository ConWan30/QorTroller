"""QorTroller L9 — background Remote Play window capture (DESIGN-ONLY).

Per the capture research (2026-05): PS Remote Play is NOT hard-DRM; black frames
come from per-window capture + GPU hardware-overlay decode. Known-good path:
  * dxcam (DXGI Desktop Duplication): full-screen monitor duplication + REGION CROP,
    fastest (~100-240fps). PRIMARY. Keep Remote Play MAXIMIZED.
  * if frames are black -> overlay-decode gotcha. Workarounds (operator-side):
      (a) disable Windows "Hardware-accelerated GPU scheduling" + reboot, OR
      (b) use a WGC backend (windows-capture / wincam) which handles overlays.
  * mss: cross-platform, ~30-60fps. LAST RESORT (too slow for 60fps real-time).

This module provides a uniform ScreenCapturer over whichever backend is available,
plus is_black_frame() for the decisive de-risk check.

STATUS: design-only probe scaffold. No FROZEN-v1 primitive, no chain.
"""
from __future__ import annotations

from typing import Optional, Tuple

import numpy as np

# ---- optional backends (import-guarded) ----
try:
    import dxcam  # type: ignore
    _DXCAM = True
except Exception:  # pragma: no cover
    _DXCAM = False

try:
    import mss  # type: ignore
    _MSS = True
except Exception:  # pragma: no cover
    _MSS = False


Region = Tuple[int, int, int, int]  # (left, top, right, bottom)


def available_backends() -> list[str]:
    out = []
    if _DXCAM:
        out.append("dxcam")
    if _MSS:
        out.append("mss")
    return out


def is_black_frame(frame: Optional["np.ndarray"], mean_thresh: float = 6.0,
                   active_frac_thresh: float = 0.02) -> bool:
    """True if the frame is (near) black — the protected-surface / overlay signature.

    Black if mean luminance < mean_thresh AND the fraction of non-trivial pixels
    (>16) is below active_frac_thresh. Two-part test avoids calling a dark-but-real
    scene 'black'.
    """
    if frame is None or frame.size == 0:
        return True
    f = frame
    if f.ndim == 3:
        f = f.mean(axis=2)
    if float(f.mean()) >= mean_thresh:
        return False
    active = float((f > 16).mean())
    return active < active_frac_thresh


class ScreenCapturer:
    """Uniform capture surface. Prefers dxcam (full-screen + crop), falls back to
    mss. Returns BGR uint8 ndarrays (OpenCV convention) or None on a missed grab.
    """

    def __init__(self, region: Optional[Region] = None, monitor_idx: int = 0,
                 backend: str = "auto") -> None:
        self.region = region
        self.monitor_idx = monitor_idx
        self._backend = backend
        self._cam = None
        self._sct = None
        self._init_backend()

    def _init_backend(self) -> None:
        want = self._backend
        if want in ("auto", "dxcam") and _DXCAM:
            self._cam = dxcam.create(output_idx=self.monitor_idx, output_color="BGR")
            self._backend = "dxcam"
            return
        if want in ("auto", "mss") and _MSS:
            self._sct = mss.mss()
            self._backend = "mss"
            return
        raise RuntimeError(
            "No screen-capture backend available. Install one of: "
            "`pip install dxcam` (recommended, Windows) or `pip install mss`."
        )

    @property
    def backend(self) -> str:
        return self._backend

    def grab(self) -> Optional["np.ndarray"]:
        if self._backend == "dxcam":
            frame = self._cam.grab(region=self.region) if self.region else self._cam.grab()
            return frame  # BGR ndarray or None if no new frame since last grab
        # mss path
        if self.region:
            l, t, r, b = self.region
            mon = {"left": l, "top": t, "width": r - l, "height": b - t}
        else:
            mon = self._sct.monitors[self.monitor_idx + 1]
        raw = self._sct.grab(mon)
        arr = np.asarray(raw)  # BGRA
        return arr[:, :, :3][:, :, ::-1].copy() if arr.shape[2] == 4 else arr  # -> BGR

    def close(self) -> None:
        try:
            if self._cam is not None and hasattr(self._cam, "release"):
                self._cam.release()
            if self._sct is not None:
                self._sct.close()
        except Exception:
            pass
