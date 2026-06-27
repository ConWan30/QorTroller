"""Cycle-39 — HDR-aware WGC frame normalization + re-acquire-on-stall for the Retina Game Capture.

HDR (live in Remote Play) makes WGC deliver a wider buffer than 8-bit BGRA; the normalizer must hand
cv_motion an 8-bit 3-channel array regardless. Re-acquire handles Remote Play recreating its window.
"""
from __future__ import annotations

import time

import numpy as np

from vapi_bridge.qortroller_retina_capture import RetinaGameCaptureCore, WgcFrameSource


def _src():
    return WgcFrameSource(RetinaGameCaptureCore(ncaa_profile=False), "no-such-window")


def test_normalizer_sdr_uint8_passthrough():
    out = _src()._to_u8_bgr((np.random.rand(8, 8, 4) * 255).astype(np.uint8))
    assert out.dtype == np.uint8 and out.shape == (8, 8, 3)


def test_normalizer_hdr_uint16():
    out = _src()._to_u8_bgr((np.random.rand(8, 8, 4) * 65535).astype(np.uint16))
    assert out.dtype == np.uint8 and out.shape == (8, 8, 3)
    assert out.max() <= 255


def test_normalizer_hdr_scrgb_float():
    # scRGB: 1.0 = SDR white, HDR highlights exceed 1.0
    out = _src()._to_u8_bgr((np.random.rand(8, 8, 3).astype(np.float32) * 4.0))
    assert out.dtype == np.uint8 and out.shape == (8, 8, 3)
    assert 0 <= int(out.min()) and int(out.max()) <= 255


def test_restart_not_running_or_fresh_is_noop():
    s = _src()
    assert s.restart_if_stalled() is False          # not running
    s._running = True
    s._last_frame_wall = time.time()
    assert s.restart_if_stalled(stall_s=4.0) is False  # fresh frame


def test_restart_stalled_past_cooldown_attempts_reacquire():
    s = _src()
    s._running = True
    s._last_frame_wall = time.time() - 10.0   # stalled
    s._last_reacquire_wall = 0.0              # cooldown elapsed
    before = s._reacquires
    s.restart_if_stalled(stall_s=4.0, cooldown_s=8.0)  # start() returns False (no real window) but counts
    assert s._reacquires == before + 1


def test_restart_within_cooldown_suppressed():
    s = _src()
    s._running = True
    s._last_frame_wall = time.time() - 10.0   # stalled
    s._last_reacquire_wall = time.time()      # just re-acquired -> cooldown active
    before = s._reacquires
    assert s.restart_if_stalled(stall_s=4.0, cooldown_s=8.0) is False
    assert s._reacquires == before


def test_monitor_mode_targets_display():
    s = WgcFrameSource(RetinaGameCaptureCore(ncaa_profile=False), "Remote Play", monitor_index=1)
    assert s._monitor_index == 1
    assert "monitor #1" in s._target_desc


def test_window_mode_is_default():
    s = WgcFrameSource(RetinaGameCaptureCore(ncaa_profile=False), "Remote Play")
    assert s._monitor_index == 0
    assert "Remote Play" in s._target_desc


def test_retina_game_capture_passes_monitor_through():
    from vapi_bridge.qortroller_retina_capture import RetinaGameCapture
    rgc = RetinaGameCapture("Remote Play", monitor_index=2)
    assert rgc._source._monitor_index == 2
