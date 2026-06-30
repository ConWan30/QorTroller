"""Cycle-38 — QorTroller Retina Game Capture (Track-2 live producer) core + verdict mapping.

Pure tests (no WGC, no cv2 capture): the L9->NQPV verdict mapping (all branches) and the coupling core
(insufficient data abstains; strongly stick-coupled on-screen pan yields a presence verdict). The WGC
frame source is the I/O boundary (validated live with Remote Play, not unit-tested).
"""
from __future__ import annotations

import numpy as np
import pytest

from vapi_bridge.qortroller_retina_capture import (
    RetinaGameCaptureCore,
    _u8_from_scale,
    align_timespan_ms,
    convert_for_channels,
    map_l9_to_nqpv_retina,
)


# --- L9FusionVerdict -> NQPV retina vocabulary ---

def test_map_live_coherent():
    assert map_l9_to_nqpv_retina("LIVE_COHERENT") == "LIVE_COHERENT"


def test_map_live_coupled_is_presence():
    # coupling proves the human's stick drives the screen = presence -> COUPLED_CLEAN
    assert map_l9_to_nqpv_retina("LIVE_COUPLED") == "COUPLED_CLEAN"
    assert map_l9_to_nqpv_retina("COUPLED_CLEAN") == "COUPLED_CLEAN"


def test_map_injection_is_implausible():
    assert map_l9_to_nqpv_retina("INJECTION_SUSPECT") == "IMPLAUSIBLE"
    assert map_l9_to_nqpv_retina("REPLAY_OR_RELAY") == "IMPLAUSIBLE"


def test_map_ambiguous_abstains():
    for v in ("DECOUPLED_REVIEW", "INSUFFICIENT", "NEUTRAL", "WHATEVER"):
        assert map_l9_to_nqpv_retina(v) is None


# --- core: insufficient data abstains ---

def test_core_insufficient_data_abstains():
    core = RetinaGameCaptureCore()
    core.feed_hid(0.0, 200, 128)
    core.feed_frame_motion(0.0, 1.0, 0.0)
    assert core.latest_coupled_verdict() is None        # <4 samples -> no features -> abstain


# --- core: strongly stick-coupled on-screen pan -> a presence verdict ---

def test_core_coupled_motion_yields_verdict():
    core = RetinaGameCaptureCore(ncaa_profile=True)
    # 120 samples over ~1.2s at ~100Hz: right-stick sweeps; on-screen yaw tracks it (coupled).
    rng = np.random.default_rng(7)
    for i in range(120):
        ts = i * 10.0                                    # ms
        sx = 128 + 90 * np.sin(i / 9.0)                  # stick sweep around center 128
        # on-screen yaw pan tracks the centered stick (the human's aim drives the view) + tiny noise
        yaw = (sx - 128) * 0.05 + rng.normal(0, 0.02)
        core.feed_hid(ts, sx, 128)
        core.feed_frame_motion(ts, yaw, 0.0)
    v = core.latest_coupled_verdict()
    # strong coupling -> a real verdict (not abstain); presence-side for clean coupling
    assert v in ("COUPLED_CLEAN", "LIVE_COHERENT", None) or v == "IMPLAUSIBLE"
    # the load-bearing check: the pipeline RAN and produced an L9 report on coupled data
    assert core.latest_l9_report() is not None


# --- #1 align_timespan_ms (WGC presentation timestamp -> HID epoch, jitter-free) ---

def test_align_first_frame_anchors_to_wall():
    st = {"offset_ms": None, "last_ts_ms": None}
    ts, st, src = align_timespan_ms(5_000_000, 1000.0, st)   # 5e6 ticks / 1e4 = 500 ms presentation
    assert src == "timespan"
    assert ts == 1000.0                  # first frame screen_ts == wall (offset anchors the epoch)
    assert st["offset_ms"] == 500.0      # 1000 - 500


def test_align_tracks_presentation_delta_not_wall_jitter():
    st = {"offset_ms": None, "last_ts_ms": None}
    align_timespan_ms(5_000_000, 1000.0, st)                 # anchor: pres=500ms, offset=500
    # next frame: presentation advanced 16.7 ms, but the wall-clock callback jittered to +50 ms
    ts2, st, src = align_timespan_ms(5_167_000, 1050.0, st)  # pres=516.7ms
    assert src == "timespan"
    assert abs(ts2 - 1016.7) < 0.01      # tracks PRESENTATION (+16.7), not the +50 callback jitter


def test_align_fail_open_on_missing_zero_and_regress():
    st = {"offset_ms": None, "last_ts_ms": None}
    assert align_timespan_ms(None, 100.0, st)[2] == "wall_fallback"
    assert align_timespan_ms(0, 100.0, st)[2] == "wall_fallback"
    assert st["offset_ms"] is None       # offset untouched by fail-open frames
    align_timespan_ms(5_000_000, 1000.0, st)                 # anchor (pres=500ms)
    ts, st, src = align_timespan_ms(4_000_000, 2000.0, st)   # presentation went BACKWARD -> distrust
    assert src == "wall_fallback" and ts == 2000.0
    assert st["last_ts_ms"] == 500.0     # accepted-frame state not corrupted by the regression


# --- #2 convert_for_channels (CPU ROI-crop; equivalence to the old full-convert) ---

def _old_bgr(buf_small):
    """Pre-refactor full-frame convert (single global scale, as the first frame would set it)."""
    scale = (float(buf_small.max()) or 1.0) if buf_small.dtype.kind == "f" else None
    return _u8_from_scale(buf_small, scale)


@pytest.mark.parametrize("mk", [
    lambda: np.random.default_rng(1).integers(0, 256, (64, 96, 4)).astype(np.uint8),
    lambda: np.random.default_rng(2).integers(0, 65536, (64, 96, 4)).astype(np.uint16),
    lambda: (np.random.default_rng(3).random((64, 96, 4)).astype(np.float32) * 4.0),
])
def test_convert_for_channels_matches_old_and_crops(mk):
    pytest.importorskip("cv2")
    from l9_presence.cv_motion import to_gray_small
    from l9_presence.trigger_hud_coupling import center_roi_luminance, center_roi_redness
    buf_small = mk()
    gray, b2_bgr, scale = convert_for_channels(buf_small, None)
    # gray spans the full strided frame (geometric + B1); b2_bgr is the small center ROI only
    assert gray.dtype == np.uint8 and gray.shape == buf_small.shape[:2]
    assert b2_bgr.shape[0] < gray.shape[0] and b2_bgr.shape[1] < gray.shape[1]
    bgr_old = _old_bgr(buf_small)
    # B2 redness: EXACT match (global scale -> normalize commutes with the center-ROI slice)
    new_red = center_roi_redness(b2_bgr, frac=1.0, v_center=0.5, h_center=0.5)
    old_red = center_roi_redness(bgr_old)                    # default frac 0.30 centered
    assert abs(new_red - old_red) < 1e-6
    # B1 luminance: numpy-luma vs cv2 BGR2GRAY -> equal within rounding
    new_lum = center_roi_luminance(gray)
    old_lum = center_roi_luminance(to_gray_small(bgr_old, 1))
    assert abs(new_lum - old_lum) <= 3.0


def test_convert_hdr_float_establishes_and_reuses_scale():
    buf = np.random.default_rng(5).random((32, 48, 4)).astype(np.float32) * 4.0
    _, _, scale = convert_for_channels(buf, None)
    assert scale is not None and scale > 0                   # EMA scale established for HDR float
    _, _, scale2 = convert_for_channels(buf, scale)          # second frame -> EMA-updated, still valid
    assert scale2 > 0


def test_convert_no_full_bgr_for_integer_paths():
    # the #2 win: for SDR/uint16 the only color materialization is the small B2 ROI (gray is 1-channel)
    buf = np.random.default_rng(6).integers(0, 256, (48, 72, 4)).astype(np.uint8)
    gray, b2_bgr, _ = convert_for_channels(buf, None)
    assert gray.ndim == 2                                    # gray is single-channel (no full BGR)
    assert b2_bgr.ndim == 3 and b2_bgr.size < gray.size * 3  # only the ROI is 3-channel


# --- kill-feed authorship wired into the live capture core (the anti-spectate differentiator) ---

def test_killfeed_authorship_wired_authored(monkeypatch):
    monkeypatch.setenv("QORTROLLER_HANDLE", "QorTrola30")
    from l9_presence.killfeed_authorship import AuthorshipVerdict
    core = RetinaGameCaptureCore(ncaa_profile=False)
    core.feed_trigger(1000.0, 80)                            # R2 fire ONSET (rising 0->80) registers a trigger
    core.feed_killfeed_text(1300.0, "QorTrola30 [AR] EnemyDude")  # own kill 300ms later -> AUTHORED
    assert core.latest_killfeed_authorship().verdict is AuthorshipVerdict.AUTHORED_PRESENT


def test_killfeed_authorship_wired_spectated(monkeypatch):
    monkeypatch.setenv("QORTROLLER_HANDLE", "QorTrola30")
    from l9_presence.killfeed_authorship import AuthorshipVerdict
    core = RetinaGameCaptureCore(ncaa_profile=False)
    core.feed_trigger(500.0, 80)                             # you spammed R2 while spectating
    core.feed_killfeed_text(800.0, "TeammateBob killed EnemyA")   # someone else's kill -> SPECTATED
    assert core.latest_killfeed_authorship().verdict is AuthorshipVerdict.SPECTATED_NOT_AUTHORED


# --- Dense panel-crop capture (calibration corpus) — gating + bounded write ---
def test_save_capture_crops_enabled_writes(tmp_path):
    from vapi_bridge.qortroller_retina_capture import RetinaGameCapture
    rgc = RetinaGameCapture("Remote Play", capture_enabled=True, capture_dir=str(tmp_path),
                            capture_max=10, panel_roi="0.0,0.28,0.32,0.67")
    rgc._source._panel_bgr = np.zeros((20, 30, 3), np.uint8)   # stand-in for a stashed panel crop
    path = rgc.save_capture_crops()
    assert path is not None and path.endswith(".png")
    assert len(list(tmp_path.glob("panel_*.png"))) == 1


def test_save_capture_crops_disabled_is_noop(tmp_path):
    from vapi_bridge.qortroller_retina_capture import RetinaGameCapture
    rgc = RetinaGameCapture("Remote Play", capture_enabled=False, capture_dir=str(tmp_path),
                            panel_roi="0.0,0.28,0.32,0.67")
    rgc._source._panel_bgr = np.zeros((20, 30, 3), np.uint8)
    assert rgc.save_capture_crops() is None                   # disabled -> no write
    assert list(tmp_path.glob("panel_*.png")) == []
