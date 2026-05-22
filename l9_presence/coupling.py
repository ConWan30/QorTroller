"""QorTroller L9 — Input-Output Causal Presence: coupling core (DESIGN-ONLY).

Deterministic, numpy-only. This is the load-bearing math the whole GO/NO-GO rests
on, and it is deliberately free of any cloud model so it can become part of a
cryptographic determination.

Where controller/l2c_stick_imu_correlation.py asks "does the controller TWIST
(gyro_z) match the right-stick?" (input <-> IMU), L9 asks two questions about the
RENDERED game output:

  1. COUPLING  — does the on-screen camera angular velocity match the human's
     aim-stick input, at a causal lag? (input -> output causality)
     -> high for a human; collapses for injected/upstream-synthesized motion.

  2. RESIDUAL  — how much on-screen aim motion CANNOT be explained by the stick?
     (the aimbot / injection signature: the crosshair moves on its own)
     -> small for a human; large + engagement-locked for an aimbot.

Method (mirrors L2C's rolling-buffer causal-lag Pearson search, extended):
  * Input is ~1 kHz, video motion ~60 fps -> both are resampled onto a common
    uniform time grid (np.interp) over their overlap before correlation.
  * predicted aim-velocity = signed response curve of the (auto-centered) stick.
  * COUPLING = max |Pearson r| between predicted and measured over causal lags
    [0, LAG_MAX] (Remote Play latency window, much wider than L2C's grip window).
  * RESIDUAL = at the best lag, regress measured onto predicted (best-fit gain),
    residual = measured - gain*predicted_shifted; decoupled_energy_fraction =
    var(residual) / var(measured) in [0, 1].

NEGATIVE CONTROL (the honesty guard): recompute coupling with time-SHUFFLED
input. It MUST collapse toward 0. If it doesn't, the coupling is a latency-search
artifact, not real causality.

HONEST LIMIT: legitimate console AIM-ASSIST also adds residual motion. The probe
measures the SEPARATION between the human-with-aim-assist residual BASELINE and
the aimbot residual, NOT absolute residual. Characterize the human baseline
before trusting any threshold.

STATUS: design-only probe. No FROZEN-v1 primitive, no PoAC change, no chain.
"""
from __future__ import annotations

import os as _os
from collections import deque
from dataclasses import dataclass
from typing import Optional, Tuple

import numpy as np

# ---------------------------------------------------------------------------
# Constants (probe defaults; env-overridable, like L2C)
# ---------------------------------------------------------------------------

COMMON_RATE_HZ: float = float(_os.getenv("L9_COMMON_RATE_HZ", "120.0"))
"""Uniform grid both signals are resampled onto before correlation."""

LAG_MIN_MS: float = float(_os.getenv("L9_LAG_MIN_MS", "0.0"))
LAG_MAX_MS: float = float(_os.getenv("L9_LAG_MAX_MS", "500.0"))
"""Causal-lag search window in ms. Wide vs L2C's 10-60ms grip window because
Remote Play adds variable network+codec delay. Default raised 260->500ms after P4
(2026-05-21) showed a genuine high-latency stream: clean coupling (up to 0.955, neg
control 0.09) at ~400-500ms lag, 10x the ~40-80ms of a low-latency rig. 260ms
truncated it. Input precedes on-screen motion, so only NON-NEGATIVE lags are physical.
A per-session adaptive window (widen until the peak is interior, guarded by the negative
control) is the better long-term fix; 500ms covers realistic cloud-stream variation."""

MIN_GRID_SAMPLES: int = int(_os.getenv("L9_MIN_GRID_SAMPLES", "120"))
"""Minimum resampled samples (>= ~1s at 120Hz) before a score is returned."""

MIN_STICK_STD: float = float(_os.getenv("L9_MIN_STICK_STD", "0.01"))
"""If aim-stick activity is below this (player not aiming), coupling is undefined
-> return None (neutral), exactly as L2C returns None in the dead zone."""

COUPLING_THRESHOLD: float = float(_os.getenv("L9_COUPLING_THRESHOLD", "0.20"))
"""Below this max-causal-coupling, on-screen motion is not explained by input."""

HUMAN_COUPLING_BASELINE: float = float(_os.getenv("L9_HUMAN_COUPLING_BASELINE", "0.55"))
"""Expected human input->camera coupling, for humanity-score normalization.
PROVISIONAL — must be measured by the probe, not assumed."""

RESPONSE_EXPONENT: float = float(_os.getenv("L9_RESPONSE_EXPONENT", "1.0"))
"""Aim response curve: predicted = sign(s) * |s|**exponent. 1.0 = linear.
Pearson r is invariant to linear scale, so exact look-sensitivity is irrelevant;
the exponent only matters if the game uses a strong non-linear response curve."""

_BUFFER_MAXLEN: int = 4096


# ---------------------------------------------------------------------------
# Pure functions (fully unit-testable, no I/O)
# ---------------------------------------------------------------------------

def resample_uniform(ts_ms: np.ndarray, vals: np.ndarray, grid_ms: np.ndarray) -> np.ndarray:
    """Linear-interpolate irregular (ts, vals) onto a uniform grid."""
    if ts_ms.size < 2:
        return np.zeros_like(grid_ms)
    return np.interp(grid_ms, ts_ms, vals)


def aim_response(stick_centered: np.ndarray, exponent: float = RESPONSE_EXPONENT) -> np.ndarray:
    """Map auto-centered stick deflection to predicted aim velocity (signed)."""
    s = stick_centered
    if exponent == 1.0:
        return s
    return np.sign(s) * np.abs(s) ** exponent


def lagged_xcorr(pred: np.ndarray, meas: np.ndarray, lag_min: int, lag_max: int) -> Tuple[float, int]:
    """Max |Pearson r| between pred[:-lag] and meas[lag:] over causal lags.

    Returns (signed_r_at_best_abs, best_lag_samples). Mirrors L2C's scan; only
    non-negative lags (input precedes output) are physical. Returns (0.0, lag_min)
    when undefined (constant arrays / too short).
    """
    n = pred.size
    best_r, best_lag = 0.0, max(lag_min, 0)
    for lag in range(max(lag_min, 0), lag_max + 1):
        if lag >= n - 2:
            break
        a = pred[: n - lag] if lag > 0 else pred
        b = meas[lag:] if lag > 0 else meas
        m = min(a.size, b.size)
        a, b = a[:m], b[:m]
        if a.std() < 1e-9 or b.std() < 1e-9:
            continue
        r = float(np.corrcoef(a, b)[0, 1])
        if np.isnan(r):
            continue
        if abs(r) > abs(best_r):
            best_r, best_lag = r, lag
    return best_r, best_lag


def decoupled_energy_fraction(pred: np.ndarray, meas: np.ndarray, lag: int) -> float:
    """Fraction of measured-motion variance NOT explained by lag-aligned input.

    Best-fit gain g minimizes ||meas - g*pred_shifted||; residual energy fraction
    = var(meas - g*pred_shifted) / var(meas), clamped to [0, 1]. Large = on-screen
    motion the stick can't account for = aimbot/injection signature (but see the
    aim-assist baseline caveat in the module docstring).
    """
    n = pred.size
    if n - lag < 8:
        return 1.0
    a = pred[: n - lag] if lag > 0 else pred
    b = meas[lag:] if lag > 0 else meas
    m = min(a.size, b.size)
    a, b = a[:m], b[:m]
    vb = float(b.var())
    if vb < 1e-12:
        return 0.0
    va = float(a.var())
    if va < 1e-12:
        return 1.0
    g = float(np.cov(a, b)[0, 1] / va)
    resid = b - g * a
    return float(np.clip(resid.var() / vb, 0.0, 1.0))


def residual_series(pred: np.ndarray, meas: np.ndarray, lag: int) -> Tuple[np.ndarray, np.ndarray]:
    """Lag-aligned (residual, measured) arrays after removing the best-fit linear
    response: residual = meas_shifted - g*pred_shifted. Element k of the result
    corresponds to input time-index k (the camera it predicts is at k+lag), so an
    external per-sample signal sampled on the SAME input grid (e.g. the fire button)
    aligns by simple slicing [:residual.size]. Powers engagement-locked analysis."""
    n = pred.size
    lag = max(int(lag), 0)
    a = pred[: n - lag] if lag > 0 else pred
    b = meas[lag:] if lag > 0 else meas
    m = min(a.size, b.size)
    a, b = a[:m], b[:m]
    va = float(a.var())
    g = float(np.cov(a, b)[0, 1] / va) if va > 1e-12 else 0.0
    return b - g * a, b


# ---------------------------------------------------------------------------
# Feature dataclass
# ---------------------------------------------------------------------------

@dataclass
class CouplingFeatures:
    coupling_score: float          # max |causal Pearson r|, input -> camera
    coupling_signed: float         # signed r at the best |r| lag
    lag_ms: float                  # best causal lag (ms)
    decoupled_energy: float        # residual variance fraction [0,1]
    dominant_axis: str             # "yaw" | "pitch"
    grid_samples: int
    coupled: bool                  # coupling_score >= COUPLING_THRESHOLD


# ---------------------------------------------------------------------------
# Oracle (same shape as L2C's StickImuCorrelationOracle)
# ---------------------------------------------------------------------------

class InputOutputCouplingOracle:
    """L9 oracle. Buffers human aim-stick input (push_input) and measured
    on-screen camera angular velocity from CV (push_frame_motion), then scores
    input->output coupling + the unexplained-motion residual.

    Usage:
        for sx, sy, ts in input_frames:   oracle.push_input(ts, sx, sy)
        for yaw, pitch, ts in cv_frames:  oracle.push_frame_motion(ts, yaw, pitch)
        feats = oracle.extract_features()
        nc    = oracle.negative_control()  # must collapse vs feats.coupling_score
    """

    def __init__(self) -> None:
        self._in_ts: deque = deque(maxlen=_BUFFER_MAXLEN)
        self._in_sx: deque = deque(maxlen=_BUFFER_MAXLEN)
        self._in_sy: deque = deque(maxlen=_BUFFER_MAXLEN)
        self._mo_ts: deque = deque(maxlen=_BUFFER_MAXLEN)
        self._mo_yaw: deque = deque(maxlen=_BUFFER_MAXLEN)
        self._mo_pitch: deque = deque(maxlen=_BUFFER_MAXLEN)

    def push_input(self, ts_ms: float, right_stick_x: float, right_stick_y: float) -> None:
        self._in_ts.append(float(ts_ms))
        self._in_sx.append(float(right_stick_x))
        self._in_sy.append(float(right_stick_y))

    def push_frame_motion(self, ts_ms: float, yaw_rate: float, pitch_rate: float) -> None:
        """yaw_rate/pitch_rate = on-screen camera angular velocity from cv_motion."""
        self._mo_ts.append(float(ts_ms))
        self._mo_yaw.append(float(yaw_rate))
        self._mo_pitch.append(float(pitch_rate))

    def _grid(self) -> Optional[np.ndarray]:
        if len(self._in_ts) < 4 or len(self._mo_ts) < 4:
            return None
        t0 = max(self._in_ts[0], self._mo_ts[0])
        t1 = min(self._in_ts[-1], self._mo_ts[-1])
        if t1 - t0 < (MIN_GRID_SAMPLES / COMMON_RATE_HZ) * 1000.0:
            return None
        step = 1000.0 / COMMON_RATE_HZ
        return np.arange(t0, t1, step)

    def _axis(self, grid: np.ndarray, sx_arr, mo_arr, shuffle: bool) -> Tuple[float, float, int, float]:
        """Return (|r|, signed_r, best_lag_samples, decoupled_energy) for one axis."""
        in_ts = np.asarray(self._in_ts, dtype=np.float64)
        stick = np.asarray(sx_arr, dtype=np.float64)
        stick = stick - np.median(stick)            # auto-center (8-bit 128 or 16-bit 0)
        pred = aim_response(stick)
        pred_g = resample_uniform(in_ts, pred, grid)
        meas_g = resample_uniform(np.asarray(self._mo_ts, dtype=np.float64),
                                  np.asarray(mo_arr, dtype=np.float64), grid)
        if shuffle:
            rng = np.random.default_rng(1729)
            pred_g = pred_g.copy()
            rng.shuffle(pred_g)                     # destroy temporal alignment
        lag_min = int(round(LAG_MIN_MS / 1000.0 * COMMON_RATE_HZ))
        lag_max = int(round(LAG_MAX_MS / 1000.0 * COMMON_RATE_HZ))
        r, lag = lagged_xcorr(pred_g, meas_g, lag_min, lag_max)
        dec = decoupled_energy_fraction(pred_g, meas_g, lag)
        return abs(r), r, lag, dec

    def extract_features(self) -> Optional[CouplingFeatures]:
        grid = self._grid()
        if grid is None or grid.size < MIN_GRID_SAMPLES:
            return None
        # activity gate: require the player to actually be aiming on some axis
        sx = np.asarray(self._in_sx, dtype=np.float64); sx -= np.median(sx)
        sy = np.asarray(self._in_sy, dtype=np.float64); sy -= np.median(sy)
        if max(sx.std(), sy.std()) < MIN_STICK_STD * 255.0:  # scale-tolerant gate
            return None
        ay = self._axis(grid, self._in_sx, self._mo_yaw, shuffle=False)
        ap = self._axis(grid, self._in_sy, self._mo_pitch, shuffle=False)
        # dominant axis = whichever the player is driving harder (higher coupling)
        if ay[0] >= ap[0]:
            absr, r, lag, dec, axis = (*ay, "yaw")
        else:
            absr, r, lag, dec, axis = (*ap, "pitch")
        return CouplingFeatures(
            coupling_score=absr,
            coupling_signed=r,
            lag_ms=lag * 1000.0 / COMMON_RATE_HZ,
            decoupled_energy=dec,
            dominant_axis=axis,
            grid_samples=int(grid.size),
            coupled=absr >= COUPLING_THRESHOLD,
        )

    def negative_control(self) -> Optional[float]:
        """Coupling with time-shuffled input. MUST be << extract_features().coupling_score.
        Returns the shuffled coupling score, or None if insufficient data."""
        grid = self._grid()
        if grid is None or grid.size < MIN_GRID_SAMPLES:
            return None
        ay = self._axis(grid, self._in_sx, self._mo_yaw, shuffle=True)
        ap = self._axis(grid, self._in_sy, self._mo_pitch, shuffle=True)
        return max(ay[0], ap[0])

    def humanity_score(self) -> float:
        """Positive presence signal in [0,1]; 0.5 (neutral) if insufficient data."""
        f = self.extract_features()
        if f is None:
            return 0.5
        return float(min(1.0, f.coupling_score / HUMAN_COUPLING_BASELINE))

    def reset(self) -> None:
        for d in (self._in_ts, self._in_sx, self._in_sy,
                  self._mo_ts, self._mo_yaw, self._mo_pitch):
            d.clear()
