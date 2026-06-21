"""QorTroller L9 — Adaptive Capture Governor (real-time lag/FPS self-tuning, pure logic).

Closes a feedback loop the same lag signal that proves presence also uses to keep VIDEO
OUTPUT STEADY and keep the coupling oracle (coupling.py) in its valid regime. Driven entirely
by telemetry derived from the capture stream the witness agent already reads.

HONEST SCOPE: this CANNOT reduce external Remote-Play network/stream lag (that is upstream of
the capture). What it does:
  * stabilize the CAPTURE PIPELINE — hold a steady frame cadence (low frame-interval jitter)
    by trading optical-flow resolution (downscale) and region size for frame rate, and
  * ADAPT THE ESTIMATOR — widen the coupling lag-search window when the measured input->output
    lag approaches the search ceiling (else the coupling estimate truncates), and lengthen /
    raise the resample grid when there are too few samples for a valid score.

Pure + I/O-free: `decide()` is a deterministic control law over telemetry; the stateful
`AdaptiveCaptureGovernor` adds EMA smoothing + a cooldown so single-frame spikes don't thrash
the controls. The capture loop (cocapture / witness agent) feeds it frame timestamps + the
coupling lag and applies the returned controls. No FROZEN/PoAC/chain touch.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Optional

# coupling.py regime constants this governor keeps valid (kept in sync; not imported to stay pure)
COUPLING_LAG_MAX_MS_DEFAULT = 500.0
COUPLING_COMMON_RATE_HZ_DEFAULT = 120.0
COUPLING_MIN_GRID_SAMPLES_DEFAULT = 120


@dataclass(frozen=True)
class CaptureTelemetry:
    measured_fps: float = 0.0
    fps_cv: float = 0.0              # frame-interval std/mean (jitter; lower = steadier)
    stale_ms: float = 0.0           # time since the last fresh frame (capture-pipeline lag)
    coupling_lag_ms: Optional[float] = None  # measured input->output lag from coupling.py
    grid_samples: int = 0           # resampled samples available to the coupling oracle
    dropped: int = 0
    n_frames: int = 0


@dataclass(frozen=True)
class CaptureControls:
    target_fps: float = 60.0
    downscale: int = 4              # cv_motion DOWNSCALE (higher = cheaper frames = faster)
    region_scale: float = 1.0       # 1.0 = full configured region; <1 crops for speed
    lag_window_ms: float = COUPLING_LAG_MAX_MS_DEFAULT      # feeds coupling.LAG_MAX_MS
    resample_hz: float = COUPLING_COMMON_RATE_HZ_DEFAULT    # feeds coupling.COMMON_RATE_HZ


@dataclass(frozen=True)
class GovernorConfig:
    min_fps: float = 30.0
    target_margin: float = 0.15     # "high fps" = measured_fps > target_fps*(1+margin)
    fps_cv_ceiling: float = 0.25    # above this jitter, recover steadiness first
    downscale_bounds: tuple[int, int] = (2, 8)
    region_scale_bounds: tuple[float, float] = (0.5, 1.0)
    downscale_step: int = 1
    region_step: float = 0.1
    lag_headroom_ms: float = 80.0   # widen window when lag within this of the ceiling
    lag_window_step_ms: float = 150.0
    lag_window_max_ms: float = 1200.0
    resample_step_hz: float = 30.0
    resample_max_hz: float = 240.0
    min_grid_samples: int = COUPLING_MIN_GRID_SAMPLES_DEFAULT
    cooldown_frames: int = 30       # observations to wait between applied changes
    ema_alpha: float = 0.3          # smoothing for measured_fps / fps_cv


@dataclass(frozen=True)
class AdjustmentDecision:
    changed: bool
    reason: str
    before: CaptureControls
    after: CaptureControls
    flags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "changed": self.changed,
            "reason": self.reason,
            "flags": list(self.flags),
            "before": vars(self.before),
            "after": vars(self.after),
        }


def _mean(xs: list[float]) -> float:
    return sum(xs) / len(xs) if xs else 0.0


def _std(xs: list[float]) -> float:
    n = len(xs)
    if n < 2:
        return 0.0
    m = _mean(xs)
    return (sum((x - m) ** 2 for x in xs) / n) ** 0.5


def compute_telemetry(frame_ts_ms: list[float], *, coupling_lag_ms: Optional[float] = None,
                      grid_samples: int = 0, dropped: int = 0,
                      now_ms: Optional[float] = None) -> CaptureTelemetry:
    """Derive capture telemetry from frame arrival timestamps (ms). Pure."""
    intervals = [b - a for a, b in zip(frame_ts_ms, frame_ts_ms[1:]) if b > a]
    mean_int = _mean(intervals)
    fps = 1000.0 / mean_int if mean_int > 0 else 0.0
    cv = (_std(intervals) / mean_int) if mean_int > 0 else 0.0
    stale = 0.0
    if now_ms is not None and frame_ts_ms:
        stale = max(0.0, now_ms - frame_ts_ms[-1])
    return CaptureTelemetry(
        measured_fps=fps, fps_cv=cv, stale_ms=stale,
        coupling_lag_ms=coupling_lag_ms, grid_samples=int(grid_samples),
        dropped=int(dropped), n_frames=len(frame_ts_ms),
    )


def _clamp_int(v: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, v))


def _clamp_float(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def decide(t: CaptureTelemetry, c: CaptureControls,
           cfg: GovernorConfig = GovernorConfig()) -> AdjustmentDecision:
    """One control decision from telemetry. Priority: steady video FIRST, then estimator
    validity (lag window, grid), then opportunistic sharpening. At most one control changes
    per call; observational flags may still accumulate. Deterministic + pure."""
    flags: list[str] = []
    ds_lo, ds_hi = cfg.downscale_bounds
    rs_lo, rs_hi = cfg.region_scale_bounds

    # ---- priority 1: STEADY VIDEO OUTPUT (jitter high or fps too low) ----
    fps_low = t.measured_fps > 0 and t.measured_fps < max(cfg.min_fps, c.target_fps * (1 - cfg.target_margin))
    if t.fps_cv > cfg.fps_cv_ceiling or fps_low:
        flags.append("unsteady_fps")
        if c.downscale < ds_hi:
            after = replace(c, downscale=_clamp_int(c.downscale + cfg.downscale_step, ds_lo, ds_hi))
            return AdjustmentDecision(True, "recover_fps:downscale_up", c, after, flags)
        if c.region_scale > rs_lo + 1e-9:
            after = replace(c, region_scale=_clamp_float(c.region_scale - cfg.region_step, rs_lo, rs_hi))
            return AdjustmentDecision(True, "recover_fps:region_shrink", c, after, flags)
        flags.append("fps_floor_reached")  # can't recover further; report it
        return AdjustmentDecision(False, "recover_fps:at_floor", c, c, flags)

    # ---- priority 2: ESTIMATOR VALIDITY — lag near the search ceiling ----
    if t.coupling_lag_ms is not None and t.coupling_lag_ms >= (c.lag_window_ms - cfg.lag_headroom_ms):
        flags.append("lag_near_ceiling")
        if c.lag_window_ms < cfg.lag_window_max_ms:
            after = replace(c, lag_window_ms=_clamp_float(
                c.lag_window_ms + cfg.lag_window_step_ms, 0.0, cfg.lag_window_max_ms))
            return AdjustmentDecision(True, "widen_lag_window", c, after, flags)
        flags.append("lag_window_maxed")
        return AdjustmentDecision(False, "widen_lag_window:maxed", c, c, flags)

    # ---- priority 3: ESTIMATOR VALIDITY — too few grid samples ----
    if 0 < t.grid_samples < cfg.min_grid_samples:
        flags.append("grid_short")
        if c.resample_hz < cfg.resample_max_hz:
            after = replace(c, resample_hz=_clamp_float(
                c.resample_hz + cfg.resample_step_hz, 0.0, cfg.resample_max_hz))
            return AdjustmentDecision(True, "raise_resample", c, after, flags)
        flags.append("extend_capture")  # resample maxed; only more time helps
        return AdjustmentDecision(False, "raise_resample:maxed", c, c, flags)

    # ---- priority 4: OPPORTUNISTIC — steady & fast -> sharpen optical flow ----
    fps_high = t.measured_fps > c.target_fps * (1 + cfg.target_margin)
    if fps_high and t.fps_cv <= cfg.fps_cv_ceiling and c.downscale > ds_lo:
        after = replace(c, downscale=_clamp_int(c.downscale - cfg.downscale_step, ds_lo, ds_hi))
        return AdjustmentDecision(True, "sharpen_flow:downscale_down", c, after, flags)

    return AdjustmentDecision(False, "steady", c, c, flags)


class AdaptiveCaptureGovernor:
    """Stateful wrapper: EMA-smooths telemetry + enforces a cooldown between applied changes
    so the controls don't oscillate. The capture loop calls observe(...) periodically and
    applies the returned controls; every decision is recorded for the session artifact."""

    def __init__(self, controls: Optional[CaptureControls] = None,
                 cfg: GovernorConfig = GovernorConfig()) -> None:
        self.controls = controls or CaptureControls()
        self.cfg = cfg
        self._ema_fps: Optional[float] = None
        self._ema_cv: Optional[float] = None
        self._cooldown = 0
        self.log: list[AdjustmentDecision] = []

    def _smooth(self, t: CaptureTelemetry) -> CaptureTelemetry:
        a = self.cfg.ema_alpha
        self._ema_fps = t.measured_fps if self._ema_fps is None else (1 - a) * self._ema_fps + a * t.measured_fps
        self._ema_cv = t.fps_cv if self._ema_cv is None else (1 - a) * self._ema_cv + a * t.fps_cv
        return replace(t, measured_fps=self._ema_fps, fps_cv=self._ema_cv)

    def observe(self, frame_ts_ms: list[float], *, coupling_lag_ms: Optional[float] = None,
                grid_samples: int = 0, dropped: int = 0,
                now_ms: Optional[float] = None) -> AdjustmentDecision:
        t = compute_telemetry(frame_ts_ms, coupling_lag_ms=coupling_lag_ms,
                              grid_samples=grid_samples, dropped=dropped, now_ms=now_ms)
        t = self._smooth(t)
        if self._cooldown > 0:
            self._cooldown -= 1
            d = AdjustmentDecision(False, "cooldown", self.controls, self.controls, [])
            self.log.append(d)
            return d
        d = decide(t, self.controls, self.cfg)
        if d.changed:
            self.controls = d.after
            self._cooldown = self.cfg.cooldown_frames
        self.log.append(d)
        return d

    def telemetry_summary(self) -> dict:
        """The optimizable dataset surfaced to the witness manifest."""
        changes = [d for d in self.log if d.changed]
        return {
            "observations": len(self.log),
            "changes": len(changes),
            "ema_fps": round(self._ema_fps, 2) if self._ema_fps is not None else None,
            "ema_fps_cv": round(self._ema_cv, 4) if self._ema_cv is not None else None,
            "final_controls": vars(self.controls),
            "reasons": [d.reason for d in changes],
            "flags": sorted({f for d in self.log for f in d.flags}),
        }
