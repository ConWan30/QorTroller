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
                try:
                    buf = frame.frame_buffer               # HxWx4; 8-bit BGRA (SDR) or wider under HDR
                    if self.frame_format == "unknown":
                        self.frame_format = f"{getattr(buf, 'dtype', '?')}{tuple(getattr(buf, 'shape', ()))}"
                        log.info("RetinaGameCapture: first WGC frame format=%s (HDR-aware normalization active)",
                                 self.frame_format)
                    # Downscale AT SOURCE: stride-slice the raw HxWx4 view by the live downscale BEFORE the
                    # expensive convert, so _to_u8_bgr (the 6 MB ascontiguousarray / HDR float-normalize) +
                    # grayscale run on ~1/d**2 the pixels instead of full 1080p (the 39fps-raw -> 7fps-processed
                    # gap was this wasted work on 16x more pixels than we use). Read _downscale ONCE — tune()
                    # mutates it on the bridge thread; splitting it mid-frame would desync the shape guard. The
                    # stride already applies the downscale, so to_gray_small gets downscale=1 (no double-down).
                    d = max(1, int(self._downscale))
                    buf_small = buf[::d, ::d]              # strided view (cheap); ceil(H/d) x ceil(W/d) x 4
                    bgr = self._to_u8_bgr(buf_small)       # HDR-aware: uint16 / scRGB-float -> 8-bit BGR
                    gray = to_gray_small(bgr, 1)           # cvtColor only — stride already downscaled
                    now = time.time() * 1000.0
                    # Channels B1 (center-ROI flash luminance) + B2 (center-ROI RED hitmarker) signals ->
                    # the trigger->HUD oracles. Best-effort; a bad ROI never kills the capture thread.
                    try:
                        from l9_presence.trigger_hud_coupling import center_roi_luminance, center_roi_redness
                        self._core.feed_roi(now, center_roi_luminance(gray))     # B1: flash
                        self._core.feed_roi_red(now, center_roi_redness(bgr))    # B2: red hitmarker
                    except Exception:  # noqa: BLE001
                        pass
                    # Shape guard: the governor changes downscale live, which changes the gray image size.
                    # Optical flow REQUIRES prev.size()==next.size(); a mismatch must SKIP motion (re-baseline),
                    # never throw — else prev_gray never updates and every later frame fails forever.
                    if (self._prev_gray is not None and self._prev_ts is not None
                            and self._prev_gray.shape == gray.shape):
                        dt = (now - self._prev_ts) / 1000.0
                        if dt > 0:
                            fm = frames_to_motion(self._prev_gray, gray, dt)
                            self._core.feed_frame_motion(now, fm.yaw_rate, fm.pitch_rate)
                            self.frames_seen += 1
                            self._frame_ts.append(now)
                    self._prev_gray, self._prev_ts = gray, now   # ALWAYS update -> re-baseline on size change
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
        """HDR-aware normalize. WGC delivers 8-bit BGRA under SDR, but a WIDER buffer under HDR (uint16, or
        scRGB float16/32 where 1.0 = SDR white and highlights exceed 1.0). Return an 8-bit 3-channel array so
        cv_motion (optical flow) works regardless of HDR state. uint16 -> deterministic >>8; float ->
        EMA-smoothed scale (per-frame max alone would flicker brightness and inject false optical flow)."""
        import numpy as np
        a = buf
        if getattr(a, "ndim", 0) == 3 and a.shape[2] >= 3:
            a = a[:, :, :3]
        if a.dtype == np.uint8:
            return np.ascontiguousarray(a)
        if a.dtype == np.uint16:
            return np.ascontiguousarray((a >> 8).astype(np.uint8))
        a = a.astype(np.float32)
        m = float(a.max()) if a.size else 1.0
        if m <= 0:
            m = 1.0
        self._lum_scale = m if self._lum_scale is None else 0.9 * self._lum_scale + 0.1 * m
        return np.ascontiguousarray(np.clip(a / self._lum_scale * 255.0, 0, 255).astype(np.uint8))

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
