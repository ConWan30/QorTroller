"""OA-RP-1 UVC capture-card source (delivery swap) tests.

Pins: RETINA_CAPTURE_SOURCE default 'wgc' selects WgcFrameSource (byte-identical) · 'uvc' selects
UvcFrameSource with env-tuned device params · the extracted _process_frame drives the SHARED pipeline
identically for HxWx4 BGRA (WGC shape) and HxWx3 BGR (cv2 shape) — motion counted, kf/panel stashed,
timespan=None honestly reports 'wall_fallback' · garbage frames bump frame_err_n and never raise ·
UVC stop() is safe when never started. No cv2 device / no WGC session is opened by any test.
"""
from __future__ import annotations

import numpy as np

from bridge.vapi_bridge.qortroller_retina_capture import (RetinaGameCapture, UvcFrameSource,
                                                          WgcFrameSource)


class _CoreStub:
    def __init__(self):
        self.roi, self.red, self.motion = [], [], []

    def feed_roi(self, ts, v):
        self.roi.append((ts, v))

    def feed_roi_red(self, ts, v):
        self.red.append((ts, v))

    def feed_frame_motion(self, ts, yaw, pitch):
        self.motion.append((ts, yaw, pitch))


def _frames(shape, n=3):
    """Deterministic frame sequence with real pixel motion (a moving bright block)."""
    out = []
    for i in range(n):
        f = np.zeros(shape, dtype=np.uint8)
        f[20 + 10 * i:40 + 10 * i, 20:60] = 200
        out.append(f)
    return out


def test_default_env_selects_wgc(monkeypatch):
    monkeypatch.delenv("RETINA_CAPTURE_SOURCE", raising=False)
    rgc = RetinaGameCapture("Remote Play")
    assert type(rgc._source) is WgcFrameSource            # byte-identical default path


def test_uvc_env_selects_uvc_source(monkeypatch):
    monkeypatch.setenv("RETINA_CAPTURE_SOURCE", "uvc")
    monkeypatch.setenv("RETINA_UVC_INDEX", "2")
    monkeypatch.setenv("RETINA_UVC_FPS", "30")
    rgc = RetinaGameCapture("Remote Play")
    assert type(rgc._source) is UvcFrameSource
    assert rgc._source._uvc_index == 2 and rgc._source._uvc_fps == 30
    assert "UVC capture device #2" in rgc._source._target_desc


def test_process_frame_bgr3_drives_shared_pipeline():
    """cv2-shape HxWx3 BGR frames: motion counted after a shape-stable pair; B1/B2 fed;
    timespan=None -> honest 'wall_fallback' (no fabricated presentation clock)."""
    core = _CoreStub()
    src = WgcFrameSource(core, "w", downscale=1)
    for i, f in enumerate(_frames((120, 160, 3))):
        src._process_frame(f, 1_000.0 + 33.0 * i, None)
    assert src.frames_seen >= 1                           # optical flow ran on the 3-channel path
    assert len(core.roi) == 3 and len(core.red) == 3      # B1 + B2 fed every frame
    assert src._ts_source == "wall_fallback"              # UVC has no QPC timespan — honest
    assert src._frame_err_n == 0


def test_process_frame_bgra4_same_pipeline():
    """WGC-shape HxWx4 BGRA through the SAME extracted method — the extraction regression guard."""
    core = _CoreStub()
    src = WgcFrameSource(core, "w", downscale=1)
    for i, f in enumerate(_frames((120, 160, 4))):
        src._process_frame(f, 2_000.0 + 33.0 * i, None)
    assert src.frames_seen >= 1 and src._frame_err_n == 0
    assert len(core.motion) == src.frames_seen


def test_kf_and_panel_stash_on_bgr3():
    """Killfeed + panel ROI stash works from 3-channel frames (the card path feeds OCR/authorship)."""
    core = _CoreStub()
    src = WgcFrameSource(core, "w", downscale=1, killfeed_roi="0.5,0.0,0.5,0.5",
                         killfeed_every=1, panel_roi="0.0,0.0,0.5,1.0")
    src._process_frame(_frames((120, 160, 3), 1)[0], 3_000.0, None)
    assert src._kf_bgr is not None and src._kf_bgr.shape[2] == 3
    assert src._panel_bgr is not None and src._panel_bgr.shape[2] == 3
    assert src._kf_ts == 3_000.0 and src._panel_ts == 3_000.0


def test_garbage_frame_never_raises():
    core = _CoreStub()
    src = WgcFrameSource(core, "w")
    src._process_frame(object(), 4_000.0, None)           # not an array at all
    assert src._frame_err_n == 1                          # counted, swallowed — thread survives


def test_uvc_stop_safe_when_never_started():
    src = UvcFrameSource(_CoreStub(), uvc_index=0)
    src.stop()                                            # no cap/thread -> no-op, no raise
    assert src._uvc_cap is None and src._uvc_thread is None
