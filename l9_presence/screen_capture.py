"""QorTroller L9 — background Remote Play window capture (DESIGN-ONLY).

Per the capture research (2026-05): PS Remote Play is NOT hard-DRM; black frames
come from per-window capture + GPU hardware-overlay decode. Known-good path:
  * bettercam (DXGI Desktop Duplication): full-screen monitor duplication + REGION
    CROP, fastest (~100-240fps). PRIMARY — maintained successor to dxcam, fixes the
    comtypes COM-release access-violation crash on Python 3.12/3.13. Keep Remote
    Play MAXIMIZED.
  * dxcam: same DXGI path, older + unmaintained (2022). FALLBACK only — known to
    double-free a COM pointer under comtypes>=1.4 + Python 3.13 (access violation).
  * if frames are black -> overlay-decode gotcha. Workarounds (operator-side):
      (a) disable Windows "Hardware-accelerated GPU scheduling" + reboot, OR
      (b) use a WGC backend (windows-capture / wincam) which handles overlays.
  * mss: cross-platform GDI BitBlt, ~30-60fps. LAST RESORT — slow AND frequently
    returns black on hardware-overlay surfaces (it is NOT DXGI), so a black result
    on mss is inconclusive; confirm with a DXGI backend before declaring NO-GO.

This module provides a uniform ScreenCapturer over whichever backend is available,
plus is_black_frame() for the decisive de-risk check.

STATUS: design-only probe scaffold. No FROZEN-v1 primitive, no chain.
"""
from __future__ import annotations

from typing import Optional, Tuple

import numpy as np

# ---- optional backends (import-guarded) ----
# bettercam is the maintained drop-in for dxcam (same .create()/.grab() API); it is
# preferred because dxcam 0.3.0 crashes on Python 3.13 during COM Release.
try:
    import bettercam  # type: ignore
    _BETTERCAM = True
except Exception:  # pragma: no cover
    _BETTERCAM = False

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

# WGC (Windows.Graphics.Capture) via the Rust-backed `windows-capture` package: 60fps,
# overlay-capable (correct for Remote Play), and NO comtypes (so no DXGI access-violation
# crash). Event-driven, so it runs in a background thread and grab() returns the latest
# new frame. Preferred when present — sharpens the L9 lag feature (16ms vs ~33ms bins).
try:
    from windows_capture import WindowsCapture  # type: ignore
    _WGC = True
except Exception:  # pragma: no cover
    _WGC = False


Region = Tuple[int, int, int, int]  # (left, top, right, bottom)

# DXGI backends share the bettercam/dxcam API surface (.create / .grab / .release).
_DXGI_MODULES = {}
if _BETTERCAM:
    _DXGI_MODULES["bettercam"] = bettercam
if _DXCAM:
    _DXGI_MODULES["dxcam"] = dxcam


def available_backends() -> list[str]:
    """Backends in PREFERENCE order (most reliable/capable first)."""
    out = []
    if _WGC:
        out.append("wgc")
    if _BETTERCAM:
        out.append("bettercam")
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
    """Uniform capture surface. Prefers a DXGI backend (bettercam, then dxcam) with
    full-screen duplication + region crop, falls back to mss. Returns BGR uint8
    ndarrays (OpenCV convention) or None on a missed grab. grab() never raises — a
    backend error returns None so the de-risk loop can record it as a missed frame
    rather than crashing.
    """

    def __init__(self, region: Optional[Region] = None, monitor_idx: int = 0,
                 backend: str = "auto") -> None:
        self.region = region
        self.monitor_idx = monitor_idx
        self._backend = backend
        self._dxgi_module = None  # the bettercam/dxcam module actually in use
        self._cam = None
        self._sct = None
        self._wgc_control = None   # windows-capture background capture control
        self._wgc_latest = None    # latest BGR frame from the WGC thread
        self._wgc_id = 0           # increments per delivered frame
        self._wgc_last_id = -1     # last id returned by grab() (dedup)
        self._init_backend()

    def _wgc_setup(self) -> None:
        """Start a background WGC capture; on_frame_arrived stores the latest cropped
        BGR frame. grab() then returns each new frame once (None if unchanged)."""
        cap = WindowsCapture(cursor_capture=False, draw_border=False,
                             monitor_index=self.monitor_idx + 1, window_name=None)
        region = self.region

        @cap.event
        def on_frame_arrived(frame, capture_control):  # runs in WGC's thread
            try:
                buf = frame.frame_buffer  # (h, w, 4) BGRA uint8
                if region:
                    l, t, r, b = region
                    bgr = buf[t:b, l:r, :3]
                else:
                    bgr = buf[:, :, :3]
                self._wgc_latest = np.ascontiguousarray(bgr)
                self._wgc_id += 1
            except Exception:
                pass

        @cap.event
        def on_closed():
            pass

        self._wgc_control = cap.start_free_threaded()

    def _init_backend(self) -> None:
        want = self._backend
        # WGC first when available (60fps, overlay-capable, crash-free)
        if want in ("auto", "wgc") and _WGC:
            self._wgc_setup()
            self._backend = "wgc"
            return
        # explicit or auto DXGI selection, in preference order
        for name in ("bettercam", "dxcam"):
            if want in ("auto", name) and name in _DXGI_MODULES:
                mod = _DXGI_MODULES[name]
                self._cam = mod.create(output_idx=self.monitor_idx, output_color="BGR")
                self._dxgi_module = mod
                self._backend = name
                return
        if want in ("auto", "mss") and _MSS:
            self._sct = mss.mss()
            self._backend = "mss"
            return
        raise RuntimeError(
            f"No screen-capture backend available for backend={want!r}. Install one of: "
            "`pip install windows-capture` (WGC, 60fps + overlay-capable, recommended), "
            "`pip install bettercam` (DXGI), or `pip install mss`. (dxcam is supported but "
            "unmaintained and crashes on Python 3.13.)"
        )

    @property
    def backend(self) -> str:
        return self._backend

    def grab(self) -> Optional["np.ndarray"]:
        try:
            if self._wgc_control is not None:  # WGC: return each new frame once
                if self._wgc_id == self._wgc_last_id or self._wgc_latest is None:
                    return None
                self._wgc_last_id = self._wgc_id
                return self._wgc_latest
            if self._cam is not None:  # DXGI backend (bettercam / dxcam)
                return (self._cam.grab(region=self.region) if self.region
                        else self._cam.grab())  # BGR ndarray or None if no new frame
            # mss path
            if self.region:
                l, t, r, b = self.region
                mon = {"left": l, "top": t, "width": r - l, "height": b - t}
            else:
                mon = self._sct.monitors[self.monitor_idx + 1]
            raw = self._sct.grab(mon)
            arr = np.asarray(raw)  # BGRA
            return arr[:, :, :3][:, :, ::-1].copy() if arr.shape[2] == 4 else arr  # -> BGR
        except Exception:
            return None

    def close(self) -> None:
        try:
            if self._wgc_control is not None and hasattr(self._wgc_control, "stop"):
                self._wgc_control.stop()
        except Exception:
            pass
        self._wgc_control = None
        self._wgc_latest = None
        try:
            if self._cam is not None and hasattr(self._cam, "release"):
                self._cam.release()
        except Exception:
            pass
        self._cam = None
        # release the module-level DXGI device/output COM objects so the interpreter
        # does not double-free them at GC (the dxcam access-violation signature).
        try:
            if self._dxgi_module is not None and hasattr(self._dxgi_module, "clean_up"):
                self._dxgi_module.clean_up()
        except Exception:
            pass
        self._dxgi_module = None
        try:
            if self._sct is not None:
                self._sct.close()
        except Exception:
            pass
        self._sct = None
