"""QorTroller L9 — Channel B1: Trigger→HUD event coupling (DESIGN-ONLY core).

The geometric channel (l9_presence/coupling.py) binds the right STICK to on-screen PAN. This channel
binds the certified controller's **R2 trigger** (1000 Hz, ground-truth telemetry off the vaulted
device) to the **on-screen center-ROI response** (muzzle flash + reticle bloom at the crosshair).

Why this channel exists — the anti-GCAP property the geometric channel lacks (campaign 2026-06-27):
  * Geometric coupling (stick→pan) is SOFT: a spectated replay / auto-camera pan can spuriously
    correlate with stick motion well enough to clear a low threshold. Measured live, real spectate
    footage produced stick→pan coupling up to ~0.10, overlapping genuine aim → thin separation margin.
  * Trigger→HUD is HARD: a replay you are merely watching cannot emit muzzle flashes synced to a
    trigger *you* pulled. Pull R2 into a spectated POV and the on-screen flashes are someone else's,
    at someone else's timing → no causal lag aligns your R2 to the screen → coupling collapses, and
    the time-shuffled null collapses with it. The adversary can fabricate plausible screen motion,
    but not screen events causally bound to your live trigger.

Method — identical causal-lag Pearson machinery as the geometric oracle (reused, not reimplemented):
  * predictor  = the (auto-centered) R2 trigger-position signal (high while pulling).
  * measured   = center-ROI luminance/motion (spikes on flash/bloom).
  * COUPLING   = max |Pearson r| between predictor and measured over a causal render+stream lag window.
  * NULL       = the same with the trigger time-SHUFFLED; MUST collapse (honesty guard).

The lag window is wider than stick→pan: the HUD response (flash render + encode + network + decode)
can lag more than a camera pan. Pure, numpy-only, deterministic. No FROZEN-v1 / PoAC / chain.
"""
from __future__ import annotations

import os as _os
from collections import deque
from dataclasses import dataclass
from typing import Optional, Tuple

import numpy as np

# Reuse the geometric oracle's resampling + causal-lag Pearson scan — one shared machinery.
from l9_presence.coupling import (
    COMMON_RATE_HZ,
    MIN_GRID_SAMPLES,
    lagged_xcorr,
    resample_uniform,
)

# Render+stream latency window for trigger→screen. Wider than stick→pan's because the HUD response
# (muzzle flash render + codec + network + decode) accumulates more delay than a camera pan.
TH_LAG_MIN_MS: float = float(_os.getenv("L9_TH_LAG_MIN_MS", "30.0"))
TH_LAG_MAX_MS: float = float(_os.getenv("L9_TH_LAG_MAX_MS", "400.0"))

TH_COUPLING_THRESHOLD: float = float(_os.getenv("L9_TH_COUPLING_THRESHOLD", "0.20"))
"""Below this max-causal-coupling, on-screen flashes are not explained by the trigger (uncalibrated;
the geometric campaign showed 0.20 is a placeholder — Channel B1 needs its own structured-negative
calibration, but its separation is expected to be far cleaner than the geometric channel)."""

MIN_FIRE_STD: float = float(_os.getenv("L9_MIN_FIRE_STD", "0.02"))
"""If R2 trigger activity is below this (player not firing), coupling is undefined → return None
(neutral), exactly as the geometric oracle abstains in the dead-zone."""

_BUFFER_MAXLEN: int = 4096


@dataclass
class TriggerHudFeatures:
    coupling_score: float          # max |causal Pearson r|, R2 trigger -> center-ROI response
    coupling_signed: float         # signed r at the best |r| lag
    lag_ms: float                  # best causal lag (ms) — the render+stream delay
    grid_samples: int
    fire_events: int               # number of distinct R2 onset pulses observed
    coupled: bool                  # coupling_score >= TH_COUPLING_THRESHOLD


class TriggerHudCouplingOracle:
    """L9 Channel B1 oracle. Buffers R2 trigger position (push_trigger) and center-ROI luminance/motion
    from the retina (push_roi), then scores trigger->HUD causal coupling + a shuffled null.

    Usage mirrors InputOutputCouplingOracle:
        for ts, r2 in trigger_frames: oracle.push_trigger(ts, r2)   # R2 0..255
        for ts, roi in roi_frames:    oracle.push_roi(ts, roi)      # center-ROI luminance/motion
        feats = oracle.extract_features()
        nc    = oracle.negative_control()   # must collapse vs feats.coupling_score
    """

    def __init__(self, *, lag_min_ms=None, lag_max_ms=None,
                 common_rate_hz=None, min_grid_samples=None) -> None:
        self.lag_min_ms: float = TH_LAG_MIN_MS if lag_min_ms is None else float(lag_min_ms)
        self.lag_max_ms: float = TH_LAG_MAX_MS if lag_max_ms is None else float(lag_max_ms)
        self.common_rate_hz: float = COMMON_RATE_HZ if common_rate_hz is None else float(common_rate_hz)
        self.min_grid_samples: int = MIN_GRID_SAMPLES if min_grid_samples is None else int(min_grid_samples)
        self._tr_ts: deque = deque(maxlen=_BUFFER_MAXLEN)
        self._tr_v: deque = deque(maxlen=_BUFFER_MAXLEN)
        self._roi_ts: deque = deque(maxlen=_BUFFER_MAXLEN)
        self._roi_v: deque = deque(maxlen=_BUFFER_MAXLEN)

    def push_trigger(self, ts_ms: float, r2_value: float) -> None:
        """R2 trigger position (0..255 raw, or any scale — auto-centered before correlation)."""
        self._tr_ts.append(float(ts_ms))
        self._tr_v.append(float(r2_value))

    def push_roi(self, ts_ms: float, roi_value: float) -> None:
        """Center-ROI luminance/motion from the retina (spikes on muzzle flash / reticle bloom)."""
        self._roi_ts.append(float(ts_ms))
        self._roi_v.append(float(roi_value))

    def _grid(self) -> Optional[np.ndarray]:
        if len(self._tr_ts) < 4 or len(self._roi_ts) < 4:
            return None
        t0 = max(self._tr_ts[0], self._roi_ts[0])
        t1 = min(self._tr_ts[-1], self._roi_ts[-1])
        if t1 - t0 < (self.min_grid_samples / self.common_rate_hz) * 1000.0:
            return None
        step = 1000.0 / self.common_rate_hz
        return np.arange(t0, t1, step)

    def _fire_count(self) -> int:
        """Distinct R2 onset pulses: rising edges above half the observed R2 range."""
        v = np.asarray(self._tr_v, dtype=np.float64)
        if v.size < 2:
            return 0
        lo, hi = float(v.min()), float(v.max())
        if hi - lo < MIN_FIRE_STD * 255.0:
            return 0
        thr = lo + 0.5 * (hi - lo)
        above = v >= thr
        return int(np.count_nonzero(above[1:] & ~above[:-1]))   # rising edges

    def _score(self, grid: np.ndarray, shuffle: bool) -> Tuple[float, float, int]:
        tr = np.asarray(self._tr_v, dtype=np.float64)
        tr = tr - np.median(tr)                       # auto-center the trigger
        tr_g = resample_uniform(np.asarray(self._tr_ts, dtype=np.float64), tr, grid)
        roi = np.asarray(self._roi_v, dtype=np.float64)
        roi_g = resample_uniform(np.asarray(self._roi_ts, dtype=np.float64), roi, grid)
        if shuffle:
            rng = np.random.default_rng(1729)
            tr_g = tr_g.copy()
            rng.shuffle(tr_g)                         # destroy temporal alignment (the null)
        lag_min = int(round(self.lag_min_ms / 1000.0 * self.common_rate_hz))
        lag_max = int(round(self.lag_max_ms / 1000.0 * self.common_rate_hz))
        r, lag = lagged_xcorr(tr_g, roi_g, lag_min, lag_max)
        return abs(r), r, lag

    def extract_features(self) -> Optional[TriggerHudFeatures]:
        grid = self._grid()
        if grid is None or grid.size < self.min_grid_samples:
            return None
        # activity gate: require the player to actually be firing
        tr = np.asarray(self._tr_v, dtype=np.float64)
        if (tr.max() - tr.min()) < MIN_FIRE_STD * 255.0:
            return None
        absr, r, lag = self._score(grid, shuffle=False)
        return TriggerHudFeatures(
            coupling_score=absr,
            coupling_signed=r,
            lag_ms=lag * 1000.0 / self.common_rate_hz,
            grid_samples=int(grid.size),
            fire_events=self._fire_count(),
            coupled=absr >= TH_COUPLING_THRESHOLD,
        )

    def negative_control(self) -> Optional[float]:
        """Coupling with the trigger time-SHUFFLED. MUST be << extract_features().coupling_score."""
        grid = self._grid()
        if grid is None or grid.size < self.min_grid_samples:
            return None
        absr, _, _ = self._score(grid, shuffle=True)
        return absr

    def reset(self) -> None:
        for d in (self._tr_ts, self._tr_v, self._roi_ts, self._roi_v):
            d.clear()


# ---------------------------------------------------------------------------
# Center-ROI signal extractors (the per-frame scalars the channels correlate against the trigger)
# ---------------------------------------------------------------------------

def center_roi_luminance(gray, frac: float = 0.30) -> float:
    """B1 signal — mean luminance of the central `frac` box. A muzzle flash / reticle bloom spikes it.
    `gray` = HxW grayscale frame. Returns 0.0 on an empty ROI."""
    h, w = gray.shape[:2]
    m = frac / 2.0
    roi = gray[int(h * (0.5 - m)):int(h * (0.5 + m)), int(w * (0.5 - m)):int(w * (0.5 + m))]
    return float(roi.mean()) if roi.size else 0.0


def center_roi_redness(bgr, frac: float = 0.30) -> float:
    """B2 signal — red-DOMINANCE of the central box: mean of clamp(R - max(G, B), 0). `bgr` = HxWx3(+)
    in OpenCV B,G,R order. A RED hitmarker / enemy-lock reticle spikes it; a WHITE muzzle flash
    (R≈G≈B) does NOT — that separation is exactly why B2 is hit-specific and B1 is flash-generic.
    Returns 0.0 on an empty / non-color ROI."""
    h, w = bgr.shape[:2]
    m = frac / 2.0
    roi = bgr[int(h * (0.5 - m)):int(h * (0.5 + m)), int(w * (0.5 - m)):int(w * (0.5 + m))]
    if roi.size == 0 or roi.shape[-1] < 3:
        return 0.0
    r = roi[..., 2].astype(np.float64)
    g = roi[..., 1].astype(np.float64)
    b = roi[..., 0].astype(np.float64)
    return float(np.clip(r - np.maximum(g, b), 0.0, None).mean())
