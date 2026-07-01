"""QorTroller Retina Game Capture (Track-2 live producer) — NOVEL.

Brings the coupled-retina screen lobe LIVE without a camera. With PS Remote Play the PS5 game renders on
the laptop, so Windows Graphics Capture (WGC) grabs it DIGITALLY -> cv_motion optical flow (on-screen view
pan) -> InputOutputCouplingOracle (couples the screen pan to the controller's HID right-stick) ->
fuse_screen_retina -> the coupled-retina verdict the developer-self-cert NQPV fusion consumes as
meta["retina_coupled_verdict"].

WHY NOVEL / why this beats a camera: the screen lobe was camera-rig-gated. Remote Play + WGC makes it a
digital screen-grab (no camera, no TV angle/lighting/noise) and the same WGC feed is the OUTCOME world the
controller (1 kHz HID retina) is coupled to. NCAA's auto-camera caps it at COUPLED_CLEAN (the
residual/injection axis is dropped via NCAA_CONTINUOUS_CONFIG); a manual-camera game can reach
LIVE_COHERENT once HUD-OCR coherence is added (v0 here is coupling-only, coherence deferred).

Layers (testable): a PURE core (RetinaGameCaptureCore -> verdict from injected motion+HID) + a WGC frame
source (windows_capture, import-guarded, background thread) + the tie (RetinaGameCapture). DEFAULT-OFF.
No FROZEN-v1 / 228B PoAC / chain / IOTX. cert_scope stays developer_self; this only adds a presence lobe.
"""
from __future__ import annotations

import logging
import time
from collections import deque
from typing import Optional

from .screen_retina_fusion import (
    CoherenceVerdict,
    ContinuousConfig,
    L9FusionVerdict,
    NCAA_CONTINUOUS_CONFIG,
    fuse_screen_retina,
)

log = logging.getLogger(__name__)

# "no coherence info" — v0 is coupling-only (no HUD OCR). Pick the insufficient/unknown member
# defensively so a COUPLED_CLEAN continuous axis fuses to LIVE_COUPLED (presence; outcomes thin),
# never spuriously LIVE_COHERENT.
_NO_COHERENCE = (getattr(CoherenceVerdict, "INSUFFICIENT", None)
                 or getattr(CoherenceVerdict, "UNKNOWN", None)
                 or list(CoherenceVerdict)[-1])


def map_l9_to_nqpv_retina(verdict) -> Optional[str]:
    """L9FusionVerdict -> the NQPV retina_coupled_verdict vocabulary that _retina_presence_contribution
    understands (COUPLED_CLEAN/LIVE_COHERENT -> presence 1.0; IMPLAUSIBLE -> 0.0; None -> abstain).
    LIVE_COUPLED (coupling proves presence, outcomes thin) maps to COUPLED_CLEAN (it IS presence)."""
    name = verdict.value if hasattr(verdict, "value") else str(verdict)
    if name == "LIVE_COHERENT":
        return "LIVE_COHERENT"
    if name in ("LIVE_COUPLED", "COUPLED_CLEAN"):
        return "COUPLED_CLEAN"           # coupling proves the human's stick drives the screen = presence
    if name in ("INJECTION_SUSPECT", "REPLAY_OR_RELAY"):
        return "IMPLAUSIBLE"             # aimbot / not-this-controller -> presence-negative
    return None                          # DECOUPLED_REVIEW / INSUFFICIENT / NEUTRAL -> abstain


class RetinaGameCaptureCore:
    """PURE coupling->verdict core (no WGC, no cv2). Inject on-screen motion (feed_frame_motion) + HID
    right-stick (feed_hid); latest_coupled_verdict() scores the InputOutputCouplingOracle + fuses."""

    def __init__(self, *, ncaa_profile: bool = True) -> None:
        # lazy import so the module loads even if l9_presence/opencv are absent in some envs
        from l9_presence.coupling import InputOutputCouplingOracle
        self._oracle = InputOutputCouplingOracle()
        self._cfg: ContinuousConfig = NCAA_CONTINUOUS_CONFIG if ncaa_profile else ContinuousConfig()
        self._last_feats = None   # last CouplingFeatures (exposes coupling_score + best-lag_ms for diag)
        self._feats_history = []  # (coupling_score, decoupled_energy) per computed window, for the P1 burst gate
        # Channel B1 (trigger->HUD): R2 trigger (from feed_hid loop) vs center-ROI flash response (from frames).
        # Fail-open: if the channel module can't load, the geometric channel still works.
        try:
            from l9_presence.trigger_hud_coupling import TriggerHudCouplingOracle
            self._th_oracle = TriggerHudCouplingOracle()     # B1: trigger vs center luminance (flash)
            self._th2_oracle = TriggerHudCouplingOracle()    # B2: trigger vs center redness (RED hitmarker)
        except Exception:  # noqa: BLE001
            self._th_oracle = None
            self._th2_oracle = None
        self._last_th = None       # last B1 TriggerHudFeatures, for diag
        self._last_th2 = None      # last B2 TriggerHudFeatures, for diag
        # Kill-feed authorship (anti-spectate differentiator; fail-open). Own-handle kill bound to YOUR R2
        # onset -> AUTHORED; others' kills -> SPECTATED. Correlation can't separate these (cycle-56); this can.
        self._kf_oracle = None
        self._kf_prev_r2 = 0
        try:
            from l9_presence.killfeed_authorship import KillfeedAuthorshipOracle
            self._kf_oracle = KillfeedAuthorshipOracle()   # handle from env QORTROLLER_HANDLE (QorTrola30)
        except Exception:  # noqa: BLE001
            self._kf_oracle = None

    def feed_hid(self, ts_ms: float, right_stick_x: float, right_stick_y: float) -> None:
        self._oracle.push_input(ts_ms, right_stick_x, right_stick_y)

    def feed_frame_motion(self, ts_ms: float, yaw_rate: float, pitch_rate: float) -> None:
        self._oracle.push_frame_motion(ts_ms, yaw_rate, pitch_rate)

    def latest_l9_report(self):
        feats = self._oracle.extract_features()
        self._last_feats = feats         # stash for diagnostics (coupling_score + best causal lag_ms)
        if feats is None:                # not enough aim activity / data -> no verdict
            return None
        # P1 burst gate: record this computed window so a burst can rank by decoupled_energy at proof time
        self._feats_history.append((feats.coupling_score, feats.decoupled_energy))
        if len(self._feats_history) > 256:
            self._feats_history = self._feats_history[-256:]
        nc = self._oracle.negative_control()
        return fuse_screen_retina(feats.coupling_score, nc, feats.decoupled_energy,
                                  coherence=_NO_COHERENCE, cfg=self._cfg)

    def latest_coupled_verdict(self) -> Optional[str]:
        """The NQPV-vocabulary coupled-retina verdict (or None=abstain) for meta['retina_coupled_verdict']."""
        rep = self.latest_l9_report()
        return None if rep is None else map_l9_to_nqpv_retina(rep.verdict)

    def reset_burst_history(self) -> None:
        """Clear the per-burst window history (call at burst start so the gate scopes to THIS burst)."""
        self._feats_history = []

    def burst_gated_summary(self, keep_quantile: float = 0.5):
        """Apply the P1 decoupled-energy gate over the accumulated burst windows -> GatedBurstSummary
        (median coupling of the lowest-DE genuine-aim windows vs COUPLING_THRESHOLD). Pure delegate."""
        from l9_presence.coupling import gate_features_by_decoupled_energy
        return gate_features_by_decoupled_energy(list(self._feats_history), keep_quantile=keep_quantile)

    # --- Channel B1: trigger->HUD (R2 trigger vs center-ROI flash response) -----------------------------
    def feed_trigger(self, ts_ms: float, r2_value: float) -> None:
        """R2 trigger position (0..255) from the HID loop into BOTH trigger->HUD oracles (B1 + B2)."""
        if self._th_oracle is not None:
            self._th_oracle.push_trigger(ts_ms, r2_value)
        if self._th2_oracle is not None:
            self._th2_oracle.push_trigger(ts_ms, r2_value)
        # Kill-feed authorship: register the R2 fire ONSET (rising edge over ~40/255) as a trigger event the
        # own-handle kill must causally follow within the render+OCR window.
        if self._kf_oracle is not None:
            _r2 = int(r2_value)
            if _r2 >= 40 and self._kf_prev_r2 < 40:
                self._kf_oracle.push_trigger(ts_ms)
            self._kf_prev_r2 = _r2

    def feed_killfeed_text(self, ts_ms: float, text: Optional[str]) -> None:
        """OCR'd kill-feed text (one or more lines) -> the authorship oracle, one row per line."""
        if self._kf_oracle is None or not text:
            return
        for line in str(text).splitlines():
            line = line.strip()
            if line:
                self._kf_oracle.push_killfeed_line(ts_ms, line)

    def latest_killfeed_authorship(self):
        """AuthorshipResult or None (oracle absent)."""
        return self._kf_oracle.verdict() if self._kf_oracle is not None else None

    def feed_roi(self, ts_ms: float, roi_value: float) -> None:
        """B1: center-ROI luminance (muzzle flash / reticle bloom spikes it) from the retina frames."""
        if self._th_oracle is not None:
            self._th_oracle.push_roi(ts_ms, roi_value)

    def feed_roi_red(self, ts_ms: float, red_value: float) -> None:
        """B2: center-ROI redness (RED hitmarker / enemy-lock reticle spikes it) from the retina frames."""
        if self._th2_oracle is not None:
            self._th2_oracle.push_roi(ts_ms, red_value)

    def latest_trigger_hud(self):
        """Channel B1 report -> (TriggerHudFeatures, negative_control) or None (abstain: not firing / no data)."""
        if self._th_oracle is None:
            return None
        f = self._th_oracle.extract_features()
        self._last_th = f
        if f is None:
            return None
        return f, self._th_oracle.negative_control()

    def latest_hit_hud(self):
        """Channel B2 report -> (TriggerHudFeatures, negative_control) or None. Couples R2 fire to the
        RED hitmarker response: high only when your trigger produces real on-screen hits (game-state
        driven — the strongest anti-spoof, since a spectated replay shows no red synced to YOUR trigger)."""
        if self._th2_oracle is None:
            return None
        f = self._th2_oracle.extract_features()
        self._last_th2 = f
        if f is None:
            return None
        return f, self._th2_oracle.negative_control()


# --- Frame timestamp + ROI-crop helpers (pure; unit-tested without WGC) -------------------------------
# WGC Direct3D11CaptureFrame.SystemRelativeTime is a QPC TimeSpan in 100 ns ticks; windows_capture passes
# it through as frame.timespan. /1e4 -> ms. BUILD-TIME VERIFY: log raw frame.timespan deltas vs wall-clock
# deltas on the first live frames and confirm this scale before trusting absolute lag.
_TIMESPAN_TICKS_PER_MS: float = 10_000.0


def align_timespan_ms(timespan_raw, wall_ms: float, state: dict):
    """Map a WGC frame.timespan to the HID wall-clock EPOCH with QPC presentation precision — removes
    callback-scheduling jitter from the screen-side coupling timestamps (-> tighter lag_ms -> sharper
    cross-channel latency invariant). Pure: threads `state` ({'offset_ms','last_ts_ms'}). FAIL-OPEN:
    missing / zero / non-monotonic timespan -> wall_ms with offset untouched. Returns
    (screen_ts_ms, state, source) with source in {'timespan','wall_fallback'}."""
    if timespan_raw is None:
        return wall_ms, state, "wall_fallback"
    try:
        ts_ms = float(timespan_raw) / _TIMESPAN_TICKS_PER_MS
    except (TypeError, ValueError):
        return wall_ms, state, "wall_fallback"
    if not (ts_ms > 0.0):
        return wall_ms, state, "wall_fallback"
    last = state.get("last_ts_ms")
    if last is not None and ts_ms < last:           # presentation time must be monotonic
        return wall_ms, state, "wall_fallback"
    if state.get("offset_ms") is None:
        state["offset_ms"] = wall_ms - ts_ms        # one-time epoch anchor to the HID clock
    state["last_ts_ms"] = ts_ms
    return ts_ms + state["offset_ms"], state, "timespan"


def _u8_from_scale(a, lum_scale):
    """Normalize a raw WGC (sub-)array (BGRA/BGR; uint8/uint16/float) to contiguous uint8 BGR using a
    PRECOMPUTED float lum_scale (ignored for integer dtypes). Pure."""
    import numpy as np
    if getattr(a, "ndim", 0) == 3 and a.shape[2] >= 3:
        a = a[:, :, :3]
    if a.dtype == np.uint8:
        return np.ascontiguousarray(a)
    if a.dtype == np.uint16:
        return np.ascontiguousarray((a >> 8).astype(np.uint8))
    a = a.astype(np.float32)
    s = lum_scale if (lum_scale and lum_scale > 0) else 1.0
    return np.ascontiguousarray(np.clip(a / s * 255.0, 0, 255).astype(np.uint8))


def convert_for_channels(buf_small, lum_scale, *, b2_frac: float = 0.30,
                         b2_vc: float = 0.5, b2_hc: float = 0.5):
    """CPU ROI-crop convert -> (gray_full, b2_roi_bgr, lum_scale) WITHOUT materializing a full-frame BGR
    image. gray_full is a direct numpy luma (cv2 BGR2GRAY weights) of the strided buffer — it feeds the
    geometric channel + B1 luminance (which crops it for free); only the small B2 center-ROI is converted
    to BGR for redness. The HDR float lum_scale is updated ONCE over the full frame and reused for both
    outputs (recomputing it from the small ROI would inject false optical-flow / redness drift). Pure."""
    import numpy as np
    from l9_presence.trigger_hud_coupling import _roi_box
    a = buf_small
    if a.dtype.kind == "f":                          # HDR float: update shared EMA scale once
        m = float(a.max()) if a.size else 1.0
        if m <= 0:
            m = 1.0
        lum_scale = m if lum_scale is None else 0.9 * lum_scale + 0.1 * m
    # gray via direct luma — no full-frame BGR allocation (the #2 win)
    b = a[:, :, 0].astype(np.float32)
    g = a[:, :, 1].astype(np.float32)
    r = a[:, :, 2].astype(np.float32)
    luma = 0.114 * b + 0.587 * g + 0.299 * r
    if a.dtype == np.uint16:
        luma = luma / 256.0
    elif a.dtype.kind == "f":
        s = lum_scale if (lum_scale and lum_scale > 0) else 1.0
        luma = luma / s * 255.0
    gray_full = np.ascontiguousarray(np.clip(luma + 0.5, 0, 255).astype(np.uint8))
    # B2 center ROI -> BGR only (small); _roi_box returns the sub-array slice
    roi_bgr = _u8_from_scale(_roi_box(a, b2_frac, b2_vc, b2_hc), lum_scale)
    return gray_full, roi_bgr, lum_scale


def _parse_roi(s: str):
    """Parse 'fx,fy,fw,fh' (0..1 fractions) -> tuple or None (kill-feed ROI; Warzone feed is top-right)."""
    try:
        parts = [float(x) for x in str(s).split(",")]
        if len(parts) == 4 and all(0.0 <= p <= 1.0 for p in parts):
            return tuple(parts)
    except (TypeError, ValueError):
        pass
    return None


def _roi_px(shape, roi):
    """Fractional (fx,fy,fw,fh) -> integer (y0,y1,x0,x1) pixel box on an HxW[xC] array."""
    h, w = shape[:2]
    fx, fy, fw, fh = roi
    x0 = int(w * fx); x1 = int(w * min(1.0, fx + fw))
    y0 = int(h * fy); y1 = int(h * min(1.0, fy + fh))
    return y0, y1, x0, x1


def _panel_roi_crop(buf, roi, lum_scale):
    """Crop the HUD panel ROI from the FULL-RES frame buffer + normalize to uint8 BGR. MUST take the raw
    `buf` (full frame), NOT `buf_small` — the governor downscales buf_small up to 8x under Remote Play GPU
    pressure, which crushes the ~600px panel to ~76px (unreadable for the offline handle detector). The
    offline-review corpus crop stays full resolution regardless of the live coupling downscale. Pure."""
    y0, y1, x0, x1 = _roi_px(buf.shape, roi)
    return _u8_from_scale(buf[y0:y1, x0:x1], lum_scale)


class WgcFrameSource:
    """Windows Graphics Capture source: captures a window in the background, runs cv_motion on each
    frame pair, and feeds on-screen pan into the core. Import-guarded; failure is non-fatal (the lobe
    just abstains). Captures DIGITAL frames of the Remote Play / game window (no camera)."""

    def __init__(self, core: RetinaGameCaptureCore, window_substr: str, *, downscale: int = 4,
                 monitor_index: int = 0, min_update_interval_ms: int = 0,
                 killfeed_roi: str = "", killfeed_every: int = 20, panel_roi: str = "") -> None:
        self._core = core
        self._window = window_substr
        self._monitor_index = int(monitor_index)   # >=1 -> capture that monitor instead of the window
        self._min_update_interval_ms = max(0, int(min_update_interval_ms))  # WGC/DWM-level rate cap (GPU relief)
        self._target_desc = (f"monitor #{monitor_index}" if int(monitor_index) >= 1
                             else f"window ~'{window_substr}'")
        self._downscale = downscale
        self._cap = None
        self._control = None        # CaptureControl from start_free_threaded() — the REAL stop() handle (GPU release)
        self._prev_gray = None
        self._prev_ts: Optional[float] = None
        self._running = False
        self.frames_seen = 0
        self._frame_ts: deque = deque(maxlen=240)   # recent WGC frame arrival times (ms) for the governor
        self._last_frame_wall: Optional[float] = None   # wall-clock (s) of last frame -> stall detection
        self._last_reacquire_wall: float = 0.0          # cooldown gate for re-acquire
        self._reacquires: int = 0
        self._frame_err_n: int = 0
        self._lum_scale: Optional[float] = None         # EMA luminance scale for HDR-float normalization
        self.frame_format: str = "unknown"              # observed WGC buffer format (SDR uint8 vs HDR wider)
        self._ts_state: dict = {"offset_ms": None, "last_ts_ms": None}  # presence-clock epoch align (#1)
        self._ts_source: str = "wall_fallback"          # last screen-ts source: 'timespan' / 'wall_fallback'
        self._ts_logged: bool = False                   # one-time units-verification log on first timespan frame
        self._kf_roi = _parse_roi(killfeed_roi)         # kill-feed ROI (fractions) or None — authorship OCR
        self._kf_every = max(1, int(killfeed_every))    # stash the feed ROI every N frames (OCR is throttled)
        self._kf_bgr = None                             # latest kill-feed ROI (contiguous BGR) for the OCR tick
        self._kf_ts = None
        self._kf_frame_n = 0
        self._panel_roi = _parse_roi(panel_roi)         # left HUD panel (feed+roster) for dense corpus capture
        self._panel_bgr = None                          # latest panel ROI (contiguous BGR) for the crop saver

    def start(self) -> bool:
        try:
            from windows_capture import WindowsCapture
            from l9_presence.cv_motion import frames_to_motion, to_gray_small
        except Exception as exc:  # noqa: BLE001
            log.warning("RetinaGameCapture: WGC/cv_motion unavailable (lobe abstains): %s", exc)
            return False
        try:
            # GPU-competition relief: minimum_update_interval throttles WGC at the DWM level (fewer GPU
            # frame-copies + readbacks) so screen capture doesn't starve the Remote Play decoder. 0 = uncapped.
            _wc_kwargs = ({"minimum_update_interval": self._min_update_interval_ms}
                          if self._min_update_interval_ms > 0 else {})
            if self._monitor_index >= 1:
                cap = WindowsCapture(monitor_index=self._monitor_index, **_wc_kwargs)
                self._target_desc = f"monitor #{self._monitor_index}"
            else:
                cap = WindowsCapture(window_name=self._window, **_wc_kwargs)
                self._target_desc = f"window ~'{self._window}'"

            @cap.event
            def on_frame_arrived(frame, capture_control):  # noqa: ANN001
                self._last_frame_wall = time.time()        # mark arrival even if processing fails (stall clock)
                wall_ms = self._last_frame_wall * 1000.0
                try:
                    buf = frame.frame_buffer               # HxWx4; 8-bit BGRA (SDR) or wider under HDR
                    if self.frame_format == "unknown":
                        self.frame_format = f"{getattr(buf, 'dtype', '?')}{tuple(getattr(buf, 'shape', ()))}"
                        log.info("RetinaGameCapture: first WGC frame format=%s (HDR-aware normalization active)",
                                 self.frame_format)
                    # #1 Presentation timestamp: use the WGC frame's own presentation time (frame.timespan),
                    # epoch-aligned to the HID wall-clock, for the coupling feeds — removes callback jitter
                    # so HID<->screen lag_ms is tighter. Fail-open to wall_ms if timespan is absent/zero.
                    screen_ts, self._ts_state, self._ts_source = align_timespan_ms(
                        getattr(frame, "timespan", None), wall_ms, self._ts_state)
                    if self._ts_source == "timespan" and not self._ts_logged:
                        self._ts_logged = True            # BUILD-TIME VERIFY: raw->ms scale + epoch offset
                        log.info("RetinaGameCapture: WGC presentation timestamp ACTIVE — raw timespan=%s "
                                 "-> %.1f ms; epoch offset=%.1f ms. Verify /%g scale: subsequent timespan "
                                 "deltas should track frame cadence, not callback jitter.",
                                 getattr(frame, "timespan", None),
                                 float(getattr(frame, "timespan", 0)) / _TIMESPAN_TICKS_PER_MS,
                                 self._ts_state.get("offset_ms") or 0.0, _TIMESPAN_TICKS_PER_MS)
                    # Downscale AT SOURCE: stride-slice the raw HxWx4 view by the live downscale BEFORE the
                    # expensive convert. Read _downscale ONCE — tune() mutates it on the bridge thread;
                    # splitting it mid-frame would desync the shape guard.
                    d = max(1, int(self._downscale))
                    buf_small = buf[::d, ::d]              # strided view (cheap); ceil(H/d) x ceil(W/d) x 4
                    # #2 CPU ROI-crop convert: full-frame GRAY (geometric + B1) + B2 center-ROI BGR only —
                    # no full-frame BGR materialization. Shares the HDR lum_scale across both outputs.
                    gray, b2_bgr, self._lum_scale = convert_for_channels(buf_small, self._lum_scale)
                    # Channels B1 (center-ROI flash luminance, on full gray) + B2 (RED hitmarker, on its ROI)
                    # -> the trigger->HUD oracles. Best-effort; a bad ROI never kills the capture thread.
                    try:
                        from l9_presence.trigger_hud_coupling import center_roi_luminance, center_roi_redness
                        self._core.feed_roi(screen_ts, center_roi_luminance(gray))     # B1: flash (full gray)
                        self._core.feed_roi_red(                                       # B2: red (pre-cropped ROI)
                            screen_ts, center_roi_redness(b2_bgr, frac=1.0, v_center=0.5, h_center=0.5))
                    except Exception:  # noqa: BLE001
                        pass
                    # Kill-feed authorship ROI: stash a contiguous BGR crop of the feed region every N frames
                    # (cheap); the OCR itself runs on the throttled tune() tick, never on this frame callback.
                    if self._kf_roi is not None or self._panel_roi is not None:
                        self._kf_frame_n += 1
                        if self._kf_frame_n % self._kf_every == 0:
                            try:
                                if self._kf_roi is not None:
                                    _y0, _y1, _x0, _x1 = _roi_px(buf_small.shape, self._kf_roi)
                                    self._kf_bgr = _u8_from_scale(buf_small[_y0:_y1, _x0:_x1], self._lum_scale)
                                    self._kf_ts = screen_ts
                                # Dense corpus: stash the left HUD panel (feed+roster) crop for the saver
                                # tick — from the FULL-RES buf (see _panel_roi_crop; buf_small would be
                                # ~76px under GPU-pressure downscale = unreadable for the handle detector).
                                if self._panel_roi is not None:
                                    self._panel_bgr = _panel_roi_crop(buf, self._panel_roi, self._lum_scale)
                            except Exception:  # noqa: BLE001
                                pass
                    # Shape guard: the governor changes downscale live, which changes the gray image size.
                    # Optical flow REQUIRES prev.size()==next.size(); a mismatch must SKIP motion (re-baseline),
                    # never throw — else prev_gray never updates and every later frame fails forever.
                    if (self._prev_gray is not None and self._prev_ts is not None
                            and self._prev_gray.shape == gray.shape):
                        dt = (screen_ts - self._prev_ts) / 1000.0
                        if dt > 0:
                            fm = frames_to_motion(self._prev_gray, gray, dt)
                            self._core.feed_frame_motion(screen_ts, fm.yaw_rate, fm.pitch_rate)
                            self.frames_seen += 1
                            self._frame_ts.append(wall_ms)   # governor fps/stall stays on wall-clock arrival
                    self._prev_gray, self._prev_ts = gray, screen_ts  # ALWAYS update -> re-baseline on size change
                except Exception as _fx:  # noqa: BLE001 — a bad frame must never kill the capture thread
                    if self._frame_err_n == 0:
                        log.warning("RetinaGameCapture: frame processing error (HDR format?): %s", _fx)
                    self._frame_err_n += 1

            @cap.event
            def on_closed():  # noqa: ANN202
                self._running = False

            self._cap = cap
            self._control = cap.start_free_threaded()   # store the CaptureControl (WindowsCapture has no stop())
            self._running = True
            self._last_frame_wall = time.time()        # fresh clock so stall detection waits for real frames
            log.info("RetinaGameCapture: WGC capturing %s (digital screen-grab, no camera)",
                     self._target_desc)
            return True
        except Exception as exc:  # noqa: BLE001
            log.warning("RetinaGameCapture: WGC start failed (lobe abstains): %s", exc)
            return False

    def recent_frame_ts(self) -> list:
        """Recent WGC frame arrival times (ms, wall-clock) for the adaptive governor's fps telemetry."""
        return list(self._frame_ts)

    def _to_u8_bgr(self, buf):
        """HDR-aware normalize to 8-bit 3-channel BGR (kept for direct callers / tests; on_frame_arrived
        now uses convert_for_channels). WGC delivers 8-bit BGRA under SDR, a WIDER buffer under HDR
        (uint16, or scRGB float where 1.0 = SDR white). uint16 -> deterministic >>8; float -> EMA-smoothed
        scale (per-frame max alone would flicker brightness and inject false optical flow). Updates the
        shared float EMA scale, then delegates the pixel work to _u8_from_scale."""
        import numpy as np
        a = buf
        if getattr(a, "ndim", 0) == 3 and a.shape[2] >= 3:
            a = a[:, :, :3]
        if a.dtype.kind == "f":
            a32 = a.astype(np.float32)
            m = float(a32.max()) if a32.size else 1.0
            if m <= 0:
                m = 1.0
            self._lum_scale = m if self._lum_scale is None else 0.9 * self._lum_scale + 0.1 * m
        return _u8_from_scale(buf, self._lum_scale)

    def restart_if_stalled(self, stall_s: float = 4.0, cooldown_s: float = 8.0) -> bool:
        """Re-acquire the window if frames stopped arriving. Remote Play recreates/fullscreens its window when
        a game stream starts, invalidating the WGC handle captured at start() (frames freeze). Cooldown-gated
        to avoid thrash. Returns True if a re-acquire happened."""
        if not self._running or self._last_frame_wall is None:
            return False
        now = time.time()
        if (now - self._last_frame_wall) <= stall_s or (now - self._last_reacquire_wall) <= cooldown_s:
            return False
        log.warning("RetinaGameCapture: WGC stalled %.1fs (frames_seen=%d, fmt=%s) — re-acquiring %s",
                    now - self._last_frame_wall, self.frames_seen, self.frame_format, self._target_desc)
        self._last_reacquire_wall = now
        self._reacquires += 1
        self.stop()
        self._prev_gray = None
        self._prev_ts = None
        return self.start()

    def stop(self) -> None:
        self._running = False
        try:
            # WindowsCapture has no stop(); only the CaptureControl from start_free_threaded() does. The prior
            # self._cap.stop() was a silent no-op (hasattr False) -> the WGC session never actually halted, so
            # the GPU was never released until the process died. Use the control so stop() truly stops capture.
            if self._control is not None:
                self._control.stop()
        except Exception:  # noqa: BLE001
            pass
        finally:
            self._control = None


class RetinaGameCapture:
    """Tie: WGC frame source -> core. feed_hid() from the bridge loop (right-stick);
    latest_coupled_verdict() read by the co-capture hook -> meta['retina_coupled_verdict']."""

    def __init__(self, window_substr: str, *, ncaa_profile: bool = True, downscale: int = 4,
                 monitor_index: int = 0, min_update_interval_ms: int = 0,
                 killfeed_enabled: bool = False, killfeed_roi: str = "", killfeed_every: int = 20,
                 capture_enabled: bool = False, capture_dir: str = "retina_kf_crops",
                 capture_max: int = 600, panel_roi: str = "",
                 inline_enabled: bool = False, anchor_path: str = "", near_log_path: str = "",
                 r2_threshold: int = 40) -> None:
        self.core = RetinaGameCaptureCore(ncaa_profile=ncaa_profile)
        self._capture_enabled = bool(capture_enabled)
        self._inline_enabled = bool(inline_enabled)
        # Inline authorship classification needs the panel crop stashed even if crop-saving is off.
        _need_panel = self._capture_enabled or self._inline_enabled
        self._source = WgcFrameSource(self.core, window_substr, downscale=downscale,
                                      monitor_index=monitor_index,
                                      min_update_interval_ms=min_update_interval_ms,
                                      killfeed_roi=(killfeed_roi if killfeed_enabled else ""),
                                      killfeed_every=killfeed_every,
                                      panel_roi=(panel_roi if _need_panel else ""))
        self._killfeed_enabled = bool(killfeed_enabled)
        self._kf_logged = False
        self._capture_dir = str(capture_dir)
        self._capture_max = int(capture_max)
        self._capture_n = 0
        self._capture_logged = False
        self.started = False
        # Trigger-gated INLINE authorship (advisory; default-off). PURE monitor holds the R2-window +
        # single-flight decision; the anchor + classify + persist happen off the event loop (see
        # maybe_classify_in_window). Fail-open: no anchor -> inline abstains, capture is unaffected.
        self._inline_monitor = None
        self._anchor = None
        self._near_log_path = str(near_log_path or "retina_kf_near_boundary.jsonl")
        self._r2_threshold = int(r2_threshold)
        self._inline_logged = False
        if self._inline_enabled:
            try:
                from l9_presence.killfeed_cv import DEFAULT_MATCH_FLOOR, load_anchor
                from l9_presence.killfeed_inline import InlineAuthorshipMonitor
                self._anchor = load_anchor(anchor_path or "l9_presence/assets/own_handle_anchor.png")
                self._inline_monitor = InlineAuthorshipMonitor(match_floor=DEFAULT_MATCH_FLOOR)
            except Exception:  # noqa: BLE001 — inline is advisory; never block capture on its setup
                self._inline_monitor = None
                self._anchor = None
        # Adaptive lag/FPS governor — meticulously widens the oracle's causal-lag search window to track
        # the live Remote Play latency (and tunes resample-rate/downscale for estimator validity).
        from l9_presence.adaptive_capture import AdaptiveCaptureGovernor, CaptureControls
        self._governor = AdaptiveCaptureGovernor(CaptureControls(downscale=downscale))

    def start(self) -> bool:
        self.started = self._source.start()
        return self.started

    def feed_hid(self, ts_ms: float, right_stick_x: float, right_stick_y: float) -> None:
        self.core.feed_hid(ts_ms, right_stick_x, right_stick_y)

    def feed_trigger(self, ts_ms: float, r2_value: float) -> None:
        """Channel B1: R2 trigger (from the HID loop) into the trigger->HUD oracle."""
        self.core.feed_trigger(ts_ms, r2_value)

    def ocr_killfeed_tick(self) -> None:
        """If kill-feed authorship is enabled + tesseract resolves, OCR the latest stashed feed ROI and feed
        the lines to the authorship oracle. Fail-open: absent tesseract / ROI / frame -> no-op (oracle stays
        UNVERIFIABLE). Called from the throttled tune() loop, never the per-frame WGC callback."""
        if not getattr(self, "_killfeed_enabled", False):
            return
        bgr = getattr(self._source, "_kf_bgr", None)
        if bgr is None:
            return
        try:
            from l9_presence import hud_ocr
            if not getattr(self, "_kf_logged", False):
                self._kf_logged = True
                log.info("RetinaGameCapture: kill-feed authorship ON (tesseract=%s, roi=%s, handle=%s)",
                         hud_ocr.ocr_available(), getattr(self._source, "_kf_roi", None),
                         getattr(self.core._kf_oracle, "own_canon", None))
            if not hud_ocr.ocr_available():
                return
            text = hud_ocr.ocr_frame(bgr)
            if text:
                log.info("kf OCR: %r", text.replace("\n", " | ")[:200])   # diagnostic: what the ROI reads
                self.core.feed_killfeed_text(getattr(self._source, "_kf_ts", None) or 0.0, text)
        except Exception:  # noqa: BLE001 — OCR must never break capture
            pass

    def save_capture_crops(self) -> Optional[str]:
        """Dense corpus capture: if enabled, write the latest stashed left-panel crop (kill-feed + roster)
        to a bounded ring of PNGs for offline review/anchor-extraction. Called from the throttled tune()
        tick (file I/O off the WGC frame callback). Fail-open: cv2/dir issues -> no-op. Returns the path
        written, or None. This produces the corpus the killfeed authorship detector must be calibrated on."""
        if not self._capture_enabled:
            return None
        bgr = getattr(self._source, "_panel_bgr", None)
        if bgr is None:
            return None
        try:
            from l9_presence.killfeed_cv import save_crop_bounded
            path = save_crop_bounded(self._capture_dir, "panel", bgr, max_files=self._capture_max)
            self._capture_n += 1 if path else 0
            if path and not self._capture_logged:
                self._capture_logged = True
                log.info("RetinaGameCapture: dense panel-crop capture ON -> %s (ring max=%d)",
                         self._capture_dir, self._capture_max)
            return path
        except Exception:  # noqa: BLE001 — capture must never break the loop
            return None

    # --- Trigger-gated INLINE authorship classification (consumption side; off the event loop) ----------
    def mark_r2_onset(self, now_ms: float) -> None:
        """R2 fire onset from the per-record consumption loop: open/extend the classification window. Cheap
        (no classify here) — safe to call inline. No-op if inline is not active."""
        if self._inline_monitor is not None:
            self._inline_monitor.mark_onset(float(now_ms))

    def maybe_classify_in_window(self, now_ms: float) -> None:
        """If inside an active R2 window and not already classifying, schedule ONE off-thread classify of the
        latest panel crop. Non-blocking: the ~100ms classify_panel runs via asyncio.to_thread, single-flight
        + min-gap bounded. Called per consumption cycle. No work is added to the WGC frame callback."""
        if self._inline_monitor is None or self._anchor is None:
            return
        if not self._inline_monitor.should_classify(float(now_ms)):
            return
        bgr = getattr(self._source, "_panel_bgr", None)
        if bgr is None:
            return
        try:
            import asyncio
            self._inline_monitor.begin(float(now_ms))
            asyncio.create_task(self._inline_classify(bgr, float(now_ms)))
        except RuntimeError:                       # no running loop (non-async caller) -> abstain, unblock
            self._inline_monitor.end()

    async def _inline_classify(self, bgr, now_ms: float) -> None:
        import asyncio
        try:
            await asyncio.to_thread(self._inline_classify_worker, bgr, now_ms)
        except Exception:  # noqa: BLE001 — inline classify must never break the loop
            pass
        finally:
            if self._inline_monitor is not None:
                self._inline_monitor.end()

    def _inline_classify_worker(self, bgr, now_ms: float) -> None:
        """Off-event-loop worker: classify the panel crop, fold into live telemetry, log near-boundary, and
        persist the classified crop via the SAME bounded-ring saver (reuse, no second storage path)."""
        from l9_presence.killfeed_cv import classify_panel, save_crop_bounded
        from l9_presence.killfeed_inline import append_near_boundary_jsonl
        res = classify_panel(bgr, self._anchor)
        ev = res.evidence or {}
        near = self._inline_monitor.record_result(
            res.verdict.value, res.score, ev.get("region"), ev.get("slot"), now_ms)
        if not self._inline_logged:
            self._inline_logged = True
            log.info("RetinaGameCapture: inline authorship ON (floor=%.2f, handle=%s) — first classify %s",
                     self._inline_monitor.match_floor, res.handle, res.verdict.value)
        if res.verdict.value == "AUTHORED_PRESENT":
            log.info("inline authorship: AUTHORED_PRESENT score=%.3f x_frac=%s", res.score, ev.get("x_frac"))
        if near is not None:
            append_near_boundary_jsonl(self._near_log_path, near)
        # Persist the classified crop via the existing saver (grows the SAME corpus; bounded ring).
        save_crop_bounded(self._capture_dir, "panel", bgr, max_files=self._capture_max)

    def latest_coupled_verdict(self) -> Optional[str]:
        return self.core.latest_coupled_verdict()

    def reset_burst_history(self) -> None:
        """P1 burst gate: clear per-burst window history (call at burst start)."""
        self.core.reset_burst_history()

    def burst_gated_summary(self, keep_quantile: float = 0.5):
        """P1 burst gate: decoupled-energy-gated burst verdict over the accumulated windows."""
        return self.core.burst_gated_summary(keep_quantile)

    def tune(self) -> Optional[dict]:
        """Observe capture telemetry + APPLY the governor's controls live. The meticulous lag adjustment:
        widens the oracle's causal-lag search window (lag_max_ms) when the measured Remote Play lag nears
        the ceiling, and tunes resample-rate/downscale for estimator validity + steady frames. Returns the
        decision dict, or None if too few WGC frames yet. The governor is EMA-smoothed + cooldown-gated."""
        self._source.restart_if_stalled()   # HDR/Remote-Play: re-acquire if the window handle went stale
        self.ocr_killfeed_tick()             # throttled kill-feed OCR -> authorship (off the frame callback)
        self.save_capture_crops()            # throttled dense panel-crop capture -> offline calibration corpus
        fts = self._source.recent_frame_ts()
        if len(fts) < 4:
            return None
        feats = self.core._last_feats
        lag = feats.lag_ms if feats is not None else None
        grid = feats.grid_samples if feats is not None else 0
        d = self._governor.observe(fts, coupling_lag_ms=lag, grid_samples=grid, now_ms=time.time() * 1000.0)
        if d.changed:
            ctl = self._governor.controls
            self.core._oracle.lag_max_ms = float(ctl.lag_window_ms)     # widen/shrink causal-lag search
            self.core._oracle.common_rate_hz = float(ctl.resample_hz)   # estimator resample rate
            self._source._downscale = int(ctl.downscale)               # optical-flow cost (applied live)
        return d.to_dict()

    @property
    def frames_seen(self) -> int:
        """How many WGC frame-pairs have been processed (0 => capture not producing frames = a bug;
        >0 with a None verdict => honest abstain, e.g. dead-zone right stick in NCAA CFB)."""
        return self._source.frames_seen

    def status(self) -> dict:
        """Diagnostic snapshot for 'is every datapoint functioning' checks. Also surfaces the
        coupling-threshold CALIBRATION features (coupling_score = real |causal r|, negative_control =
        time-shuffled chance null, decoupled_energy, grid_samples) so every session logs the data a
        calibration run separates with a measured FAR (s-coupling-threshold-calibration)."""
        rep = self.core.latest_l9_report()
        feats = self.core._last_feats
        nc = self.core._oracle.negative_control()    # shuffle null (chance coupling) — the FAR baseline
        th = self.core.latest_trigger_hud()          # Channel B1 (trigger->flash): (features, null) or None
        th2 = self.core.latest_hit_hud()             # Channel B2 (trigger->RED hitmarker): (features, null) or None
        kf = self.core.latest_killfeed_authorship()  # Kill-feed authorship (anti-spectate differentiator) or None
        return {
            "started": self.started,
            "frames_seen": self._source.frames_seen,
            "l9_verdict": (rep.verdict.value if rep is not None else None),
            "nqpv_verdict": (map_l9_to_nqpv_retina(rep.verdict) if rep is not None else None),
            "coupling_score": (round(feats.coupling_score, 3) if feats is not None else None),
            "negative_control": (round(nc, 3) if nc is not None else None),   # time-shuffled = chance null (FAR)
            "decoupled_energy": (round(feats.decoupled_energy, 3) if feats is not None else None),
            "grid_samples": (feats.grid_samples if feats is not None else 0),
            "lag_ms": (round(feats.lag_ms, 1) if feats is not None else None),   # meticulously-adjusted causal lag
            "lag_window_ms": round(self.core._oracle.lag_max_ms, 1),             # current adaptive search ceiling
            "resample_hz": round(self.core._oracle.common_rate_hz, 1),
            "frame_format": self._source.frame_format,       # SDR uint8 vs HDR (uint16/float) — HDR-aware
            "ts_source": self._source._ts_source,             # 'timespan' (WGC presentation) / 'wall_fallback'
            "ts_offset_ms": (round(self._source._ts_state.get("offset_ms"), 1)
                             if self._source._ts_state.get("offset_ms") is not None else None),
            "frame_errs": self._source._frame_err_n,
            "reacquires": self._source._reacquires,
            "frame_stall_s": (round(time.time() - self._source._last_frame_wall, 1)
                              if self._source._last_frame_wall else None),
            "governor": self._governor.telemetry_summary(),
            "abstain_reason": (None if rep is not None else
                               "extract_features None (right-stick aim activity < MIN_STICK_STD or < MIN_GRID_SAMPLES)"),
            # Channel B1 (trigger->HUD; live-wired P2) — R2 trigger vs center-ROI flash coupling + shuffle null
            "th_coupling": (round(th[0].coupling_score, 3) if th else None),
            "th_null": (round(th[1], 3) if (th and th[1] is not None) else None),
            "th_lag_ms": (round(th[0].lag_ms, 1) if th else None),
            "th_coupled": (th[0].coupled if th else None),
            "th_fires": (th[0].fire_events if th else None),
            # Channel B2 (trigger->RED hitmarker; live-wired) — strongest anti-spoof (game-state-driven red)
            "th2_coupling": (round(th2[0].coupling_score, 3) if th2 else None),
            "th2_null": (round(th2[1], 3) if (th2 and th2[1] is not None) else None),
            "th2_lag_ms": (round(th2[0].lag_ms, 1) if th2 else None),   # B2 lag — 3rd channel for the latency invariant
            "th2_coupled": (th2[0].coupled if th2 else None),
            # Kill-feed authorship — the anti-spectate differentiator converging alongside the coupling channels
            "kf_verdict": (kf.verdict.value if kf else None),
            "kf_own_kills": (kf.own_kills if kf else None),
            "kf_other_kills": (kf.other_kills if kf else None),
            "kf_bound_kills": (kf.bound_kills if kf else None),
            # Trigger-gated INLINE authorship telemetry (read-only; NOT a threshold input)
            **(self._inline_monitor.status_dict() if self._inline_monitor is not None
               else {"inline_enabled": False}),
        }

    def stop(self) -> None:
        self._source.stop()
