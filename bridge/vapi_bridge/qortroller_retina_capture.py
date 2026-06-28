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


class WgcFrameSource:
    """Windows Graphics Capture source: captures a window in the background, runs cv_motion on each
    frame pair, and feeds on-screen pan into the core. Import-guarded; failure is non-fatal (the lobe
    just abstains). Captures DIGITAL frames of the Remote Play / game window (no camera)."""

    def __init__(self, core: RetinaGameCaptureCore, window_substr: str, *, downscale: int = 4,
                 monitor_index: int = 0, min_update_interval_ms: int = 0) -> None:
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
        self._ts_state: dict = {"offset_ms": None, "last_ts_ms": None}  # presentation-clock epoch align (#1)
        self._ts_source: str = "wall_fallback"          # last screen-ts source: 'timespan' / 'wall_fallback'
        self._ts_logged: bool = False                   # one-time units-verification log on first timespan frame

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
                 monitor_index: int = 0, min_update_interval_ms: int = 0) -> None:
        self.core = RetinaGameCaptureCore(ncaa_profile=ncaa_profile)
        self._source = WgcFrameSource(self.core, window_substr, downscale=downscale,
                                      monitor_index=monitor_index,
                                      min_update_interval_ms=min_update_interval_ms)
        self.started = False
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
            "th2_coupled": (th2[0].coupled if th2 else None),
        }

    def stop(self) -> None:
        self._source.stop()
