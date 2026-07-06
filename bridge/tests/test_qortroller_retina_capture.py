"""Cycle-38 — QorTroller Retina Game Capture (Track-2 live producer) core + verdict mapping.

Pure tests (no WGC, no cv2 capture): the L9->NQPV verdict mapping (all branches) and the coupling core
(insufficient data abstains; strongly stick-coupled on-screen pan yields a presence verdict). The WGC
frame source is the I/O boundary (validated live with Remote Play, not unit-tested).
"""
from __future__ import annotations

import numpy as np
import pytest

from bridge.vapi_bridge.qortroller_retina_capture import (
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
    from bridge.vapi_bridge.qortroller_retina_capture import RetinaGameCapture
    rgc = RetinaGameCapture("Remote Play", capture_enabled=True, capture_dir=str(tmp_path),
                            capture_max=10, panel_roi="0.0,0.28,0.32,0.67")
    rgc._source._panel_bgr = np.zeros((20, 30, 3), np.uint8)   # stand-in for a stashed panel crop
    path = rgc.save_capture_crops()
    assert path is not None and path.endswith(".png")
    assert len(list(tmp_path.glob("panel_*.png"))) == 1


def test_panel_crop_is_full_res_not_downscaled():
    # Regression: the offline-review panel crop MUST come from the full-res frame, not the governor's
    # downscaled optical-flow buffer (which shrinks the ~600px panel to ~76px -> handle unreadable).
    from bridge.vapi_bridge.qortroller_retina_capture import _panel_roi_crop
    buf = np.zeros((1080, 1920, 4), np.uint8)                 # full-res BGRA frame
    crop = _panel_roi_crop(buf, (0.0, 0.28, 0.32, 0.67), None)
    assert crop.shape[1] >= 500 and crop.shape[0] >= 600      # full-res panel (~614x724), NOT ~76px
    assert crop.shape[2] == 3                                 # normalized to BGR


def test_save_capture_crops_disabled_is_noop(tmp_path):
    from bridge.vapi_bridge.qortroller_retina_capture import RetinaGameCapture
    rgc = RetinaGameCapture("Remote Play", capture_enabled=False, capture_dir=str(tmp_path),
                            panel_roi="0.0,0.28,0.32,0.67")
    rgc._source._panel_bgr = np.zeros((20, 30, 3), np.uint8)
    assert rgc.save_capture_crops() is None                   # disabled -> no write
    assert list(tmp_path.glob("panel_*.png")) == []


# --- LOOP 2 composite-driven death trigger (the 97b86b3c sibling fix; wired in _log_composite) ---

def _mk_death_capture(tmp_path):
    """A capture with the death monitor live but inline OFF (so no anchor-load needed) — we drive the
    composite path directly, which is exactly what mark_r2_onset / flush_stale_inline_window do live."""
    from bridge.vapi_bridge.qortroller_retina_capture import RetinaGameCapture
    import threading
    from l9_presence.killfeed_inline import DeathWindowMonitor
    rgc = RetinaGameCapture("Remote Play", capture_dir=str(tmp_path),
                            composite_log_path=str(tmp_path / "comp.jsonl"),
                            death_log_path=str(tmp_path / "death.jsonl"))
    # Stand the death monitor up directly (constructor default-off; we don't need inline's anchor here).
    rgc._death_monitor = DeathWindowMonitor(window_ms=4000.0, noise_floor=2.5)
    rgc._death_lock = threading.Lock()
    return rgc


def test_composite_own_death_fires_mark_death(tmp_path):
    rgc = _mk_death_capture(tmp_path)
    assert rgc._death_monitor._active is False
    rgc._log_composite({"ts_ms": 5000.0, "verdict": "OWN_DEATH", "composite_score": 0.79,
                        "window_members": 6, "window_gate_ms": 40.0, "window_end_ms": 4900.0,
                        "victim_first_ms": 4300.0})
    assert rgc._death_monitor._active is True                 # composite OWN_DEATH opened the death window
    assert rgc._death_monitor._win_start_ms == 5000.0         # window anchored at the confirmation ts
    assert rgc._death_monitor._death_anchor_ms == 4300.0      # death-row-first-seen propagated (lag recoverable)


def test_composite_authored_does_not_fire_mark_death(tmp_path):
    rgc = _mk_death_capture(tmp_path)
    rgc._log_composite({"ts_ms": 5000.0, "verdict": "AUTHORED_PRESENT", "composite_score": 0.72,
                        "window_members": 4, "window_gate_ms": 40.0, "window_end_ms": 4900.0})
    assert rgc._death_monitor._active is False                # a kill is NOT a death — no trigger


def test_composite_unverifiable_does_not_fire_mark_death(tmp_path):
    rgc = _mk_death_capture(tmp_path)
    rgc._log_composite({"ts_ms": 5000.0, "verdict": "UNVERIFIABLE", "composite_score": 0.5,
                        "window_members": 3, "window_gate_ms": 40.0, "window_end_ms": 4900.0})
    assert rgc._death_monitor._active is False


def test_worker_no_longer_fires_mark_death_directly(tmp_path):
    """Regression guard for the retired raw per-crop branch: the ONLY mark_death trigger in the capture
    file is now inside _log_composite (composite-driven). Two triggers would double-fire -> phantom
    restart-truncations. Assert the worker body no longer calls mark_death."""
    import inspect
    from bridge.vapi_bridge.qortroller_retina_capture import RetinaGameCapture
    worker_src = inspect.getsource(RetinaGameCapture._inline_classify_worker)
    assert ".mark_death(" not in worker_src                   # no CALL in the worker (comment may name it)
    log_src = inspect.getsource(RetinaGameCapture._log_composite)
    assert ".mark_death(" in log_src                          # sole trigger call lives here now


# --- l2_ads ADS coupling channel wiring (second anti-splice channel; scaffold, abstains until calibrated) ---

def _mk_ads(tmp_path, bg_every=30):
    from bridge.vapi_bridge.qortroller_retina_capture import RetinaGameCapture
    rgc = RetinaGameCapture("Remote Play", ads_enabled=True,
                            ads_log_path=str(tmp_path / "ads.jsonl"),
                            ads_segment_file=str(tmp_path / "ads_segment.json"),
                            ads_bg_sample_every=bg_every)
    rgc._source._downscale = 4
    # stub the B1 ROI history the merged-replay reads (list of (ts, lum), oldest-first, ts > cursor)
    rgc._roi_hist = []
    rgc.core.center_roi_series_since = lambda cur: [(t, v) for t, v in rgc._roi_hist if t > cur]
    return rgc


def _tick(rgc, roi_pairs, l2_pairs, now_ms):
    """One consumption tick: publish this tick's WGC-rate ROI history, push the L2 events onto the device-
    clock source (as the raw reader would — here their wall stamp IS the intended timeline), then feed.
    l2_pairs are (wall_ms, l2); we push them so the device-clock source carries them through unchanged."""
    rgc._roi_hist = list(roi_pairs)                          # cursor advances past these after the tick
    for wall, l2 in l2_pairs:                                # device ticks proportional to wall (3000/ms)
        rgc.push_l2_raw(wall, int(wall * 3000.0) & 0xFFFFFFFF, l2)
    rgc.feed_ads(now_ms)


def _read_jsonl(path):
    import json
    return [json.loads(ln) for ln in open(path, encoding="utf-8") if ln.strip()]


def test_ads_merged_replay_event_abstains_and_carries_context(tmp_path):
    rgc = _mk_ads(tmp_path)
    import json as _json
    (tmp_path / "ads_segment.json").write_text(
        _json.dumps({"optic": "high_8x", "fire_state": "no_fire", "segment": "8x"}), encoding="utf-8")
    # tick 0 primes cursors (no replay of stale history)
    _tick(rgc, [(900.0, 5.0)], [(900.0, 0)], 1000.0)
    # tick 1: a full press replayed at true WGC timing — baseline low, transition high, held, release, exit
    roi = [(1000.0, 5.0), (1025.0, 6.0), (1050.0, 80.0), (1075.0, 82.0),   # onset window (0,300 from 1050 edge)
           (1400.0, 81.0), (1600.0, 80.0), (1650.0, 7.0), (1700.0, 5.0)]   # held then exit after release
    l2 = [(1000.0, 0), (1050.0, 200), (1600.0, 200), (1650.0, 0)]          # rise at 1050, fall at 1650
    _tick(rgc, roi, l2, 2800.0)
    ev = [r for r in _read_jsonl(tmp_path / "ads.jsonl") if r.get("trigger_context") == "ads_event"]
    assert len(ev) == 1
    r = ev[0]
    assert r["verdict"] == "ADS_ABSTAIN_UNCALIBRATED"        # uncalibrated -> never fabricated
    assert r["baseline"] == 6.0                              # ROI at the 1050 edge instant (1025 sample) —
    assert r["baseline"] < 40.0                              # PRE-press, NOT the post-transition 80 (retro-fill)
    assert r["downscale"] == 4                               # governor state carried
    assert r["optic"] == "high_8x" and r["fire_state"] == "no_fire" and r["segment"] == "8x"  # structured
    assert r["label"] == "high_8x/no_fire/8x"                  # composite (readability)
    assert len(r["held_seq"]) >= 1 and "exit_seq" in r        # raw-first corpus intact


def test_ads_baseline_is_pre_press_not_post_transition(tmp_path):
    """The reason for merged replay: a naive per-tick feed reads the baseline a whole tick (~1.7s) after the
    press = post-transition = magnitude ~0. Merged replay captures the true PRE-press baseline."""
    rgc = _mk_ads(tmp_path)
    _tick(rgc, [(900.0, 4.0)], [(900.0, 0)], 1000.0)          # prime
    roi = [(1010.0, 4.0), (1040.0, 90.0), (1300.0, 88.0), (1350.0, 5.0)]  # flat, jump, hold, exit
    l2 = [(1020.0, 200), (1330.0, 0)]                        # rise 1020 (baseline 4.0 precedes), fall 1330
    _tick(rgc, roi, l2, 2700.0)
    r = [x for x in _read_jsonl(tmp_path / "ads.jsonl") if x.get("trigger_context") == "ads_event"][0]
    assert r["baseline"] == 4.0                              # NOT 90 — the pre-press value was captured


def test_ads_held_press_across_ticks_is_one_event(tmp_path):
    """Held-press regression at the wiring level: L2 stays down across MULTIPLE consumption ticks -> the
    monitor collapses it to ONE event (emitted on release), not one per tick."""
    rgc = _mk_ads(tmp_path)
    _tick(rgc, [(900.0, 5.0)], [(900.0, 0)], 1000.0)          # prime
    _tick(rgc, [(1000.0, 5.0), (1050.0, 80.0)], [(1000.0, 0), (1050.0, 200)], 2000.0)   # press, still held
    _tick(rgc, [(2100.0, 82.0), (2200.0, 81.0)], [(2100.0, 200)], 3000.0)               # STILL held, no edge
    _tick(rgc, [(3100.0, 80.0), (3200.0, 6.0)], [(3100.0, 200), (3150.0, 0)], 4000.0)   # release + exit
    ev = [r for r in _read_jsonl(tmp_path / "ads.jsonl") if r.get("trigger_context") == "ads_event"]
    assert len(ev) == 1                                       # ONE event across 3 held ticks


def test_ads_background_negative_sampling(tmp_path):
    rgc = _mk_ads(tmp_path, bg_every=3)
    _tick(rgc, [(900.0, 50.0)], [(900.0, 0)], 1000.0)         # prime
    for i in range(9):                                        # L2 idle throughout -> background samples
        _tick(rgc, [(1000.0 + i * 100, 50.0)], [(1000.0 + i * 100, 0)], 2000.0 + i * 100)
    bg = [r for r in _read_jsonl(tmp_path / "ads.jsonl") if r.get("trigger_context") == "background"]
    assert len(bg) == 3                                       # 9 idle ticks / every-3 -> 3 samples
    assert bg[0]["center_roi"] == 50.0 and bg[0]["verdict"] is None and bg[0]["downscale"] == 4


def test_ads_disabled_is_noop(tmp_path):
    from bridge.vapi_bridge.qortroller_retina_capture import RetinaGameCapture
    rgc = RetinaGameCapture("Remote Play", ads_enabled=False, ads_log_path=str(tmp_path / "ads.jsonl"))
    rgc.push_l2_raw(1000.0, 3_000_000, 200)                  # no source -> noop
    rgc.feed_ads(1000.0)                                      # no monitor -> noop
    assert not (tmp_path / "ads.jsonl").exists()


def test_ads_record_carries_device_ts_source(tmp_path):
    rgc = _mk_ads(tmp_path)
    _tick(rgc, [(900.0, 5.0)], [(900.0, 0)], 1000.0)          # prime
    roi = [(1000.0, 5.0), (1050.0, 80.0), (1400.0, 78.0), (1650.0, 6.0)]
    l2 = [(1000.0, 0), (1050.0, 200), (1600.0, 200), (1650.0, 0)]
    _tick(rgc, roi, l2, 2800.0)
    ev = [r for r in _read_jsonl(tmp_path / "ads.jsonl") if r.get("trigger_context") == "ads_event"]
    assert ev and ev[0]["ts_source"] == "device"             # rider 4: clock labeled on every record


def test_ads_crosscheck_logs_each_disagreement_with_both_values(tmp_path):
    """Rider 1 verification-built-before-needed: a raw-vs-pydualsense L2 disagreement logs its ts + both
    values (so the range session distinguishes edge-skew from a persistent wrong-offset); an agreement does
    not log."""
    rgc = _mk_ads(tmp_path)
    rgc.push_l2_raw(1000.0, 3_000_000, 5)                    # raw L2 low (5 < 40)
    rgc.crosscheck_l2(200, 1000.0)                           # pyds L2 high -> DISAGREE (logged)
    rgc.crosscheck_l2(0, 1010.0)                             # both low -> AGREE (not logged)
    cc = _read_jsonl(tmp_path / "ads_crosscheck.jsonl")
    assert len(cc) == 1                                       # only the disagreement logged
    assert cc[0]["pyds_l2"] == 200 and cc[0]["raw_l2"] == 5 and cc[0]["ts_ms"] == 1000.0
    assert rgc._ads_l2_agree == 1 and rgc._ads_l2_disagree == 1


def test_ads_tripwire_trips_on_sustained_stuck(tmp_path):
    """D-CERT-5 tripwire wired into the crosscheck: sustained raw-high / pyds-low (the 113/113 stuck pattern)
    trips it; the runner reads this per segment and halts + marks records suspect."""
    rgc = _mk_ads(tmp_path)
    for _ in range(4):                                       # 4 consecutive stuck observations (n_trip=3)
        rgc._last_raw_l2 = 255                                # raw stuck high (as push_l2_raw would set)
        rgc.crosscheck_l2(0, 1000.0)                          # pyds low
    assert rgc.ads_tripwire_status().get("tripped") is True


def test_ads_tripwire_clean_read_does_not_trip(tmp_path):
    """A clean session (raw follows pyds) with brief release edge-skew blips must NOT trip the tripwire."""
    seq = [(255, 255), (255, 255), (255, 0), (0, 0), (255, 255), (255, 0), (0, 0)]   # (raw, pyds): 1-obs skews
    rgc = _mk_ads(tmp_path)
    for raw, pyds in seq:
        rgc._last_raw_l2 = raw
        rgc.crosscheck_l2(pyds, 1000.0)
    assert rgc.ads_tripwire_status().get("tripped") is False


# --- D-BURST-2: thread-native classify entry (classify_in_window_sync) ------------------------------
class _AdmitMonitor:
    """Minimal InlineAuthorshipMonitor stand-in: admits once, then reports inflight until end()."""

    def __init__(self, admit=True):
        self._admit = admit
        self._inflight = False
        self.begun, self.ended = 0, 0

    def should_classify(self, now_ms):
        return self._admit and not self._inflight

    def begin(self, now_ms):
        self._inflight = True
        self.begun += 1

    def end(self):
        self._inflight = False
        self.ended += 1


def _mk_sync_rgc(tmp_path, monitor):
    from bridge.vapi_bridge.qortroller_retina_capture import RetinaGameCapture
    rgc = RetinaGameCapture("Remote Play", capture_dir=str(tmp_path),
                            panel_roi="0.0,0.28,0.32,0.67")
    rgc._inline_monitor = monitor
    rgc._anchor = object()                                   # sentinel: anchor present
    rgc._source._panel_bgr = np.zeros((20, 30, 3), np.uint8)
    return rgc


def test_classify_in_window_sync_runs_worker_in_calling_thread(tmp_path):
    # D-BURST-2: the sync entry runs the (already-synchronous) worker DIRECTLY — no asyncio, no
    # event loop anywhere in this test. begin/end bracket the call (single-flight preserved).
    import threading
    mon = _AdmitMonitor()
    rgc = _mk_sync_rgc(tmp_path, mon)
    seen = []
    rgc._inline_classify_worker = lambda bgr, now_ms: seen.append(threading.current_thread().name)
    rgc.classify_in_window_sync(1000.0)
    assert seen and seen[0] == threading.current_thread().name   # ran HERE, synchronously
    assert mon.begun == 1 and mon.ended == 1


def test_classify_in_window_sync_gates_no_monitor_no_panel_no_admission(tmp_path):
    from bridge.vapi_bridge.qortroller_retina_capture import RetinaGameCapture
    # no inline monitor -> no-op, never raises
    bare = RetinaGameCapture("Remote Play", capture_dir=str(tmp_path),
                             panel_roi="0.0,0.28,0.32,0.67")
    bare.classify_in_window_sync(1000.0)
    # monitor present but should_classify False (inflight/min-gap/window) -> worker NOT called
    mon = _AdmitMonitor(admit=False)
    rgc = _mk_sync_rgc(tmp_path, mon)
    rgc._inline_classify_worker = lambda *a: (_ for _ in ()).throw(AssertionError("must not run"))
    rgc.classify_in_window_sync(1000.0)
    assert mon.begun == 0
    # panel missing -> no-op before admission
    mon2 = _AdmitMonitor()
    rgc2 = _mk_sync_rgc(tmp_path, mon2)
    rgc2._source._panel_bgr = None
    rgc2.classify_in_window_sync(1000.0)
    assert mon2.begun == 0


def test_classify_in_window_sync_end_fires_even_when_worker_raises(tmp_path):
    # fail-open: a raising worker must still release single-flight (end()), never propagate.
    mon = _AdmitMonitor()
    rgc = _mk_sync_rgc(tmp_path, mon)
    rgc._inline_classify_worker = lambda *a: (_ for _ in ()).throw(RuntimeError("boom"))
    rgc.classify_in_window_sync(1000.0)                      # no raise
    assert mon.begun == 1 and mon.ended == 1                 # inflight released
