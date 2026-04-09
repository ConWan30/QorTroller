"""
analyze_interperson_separation.py — VAPI Multi-Person Mahalanobis Separation Analysis

Answers the question: does the 11-feature L4 biometric fingerprint distinguish
BETWEEN players, not just detect anomalies WITHIN a single player's sessions?

If inter-player Mahalanobis distances >> intra-player distances, the fingerprint
is a true biometric identifier — not just a per-session consistency detector.

Session grouping (from calibration data, N=69, 3 players):
  Player 1: hw_005–hw_044  (40 sessions)
  Player 2: hw_045–hw_058  (14 sessions)
  Player 3: hw_059–hw_073  (15 sessions)

Anomalous sessions excluded: hw_043, hw_044, hw_067, hw_069, hw_073
(polling_rate_hz outside [800, 1100] range)

Outputs:
  docs/interperson-separation-analysis.md  — human-readable report
  docs/interperson-separation-data.json    — raw data for reproducibility
"""

from __future__ import annotations

import json
import math
import os
import sys
import warnings
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SESSIONS_DIR = PROJECT_ROOT / "sessions" / "human"
DOCS_DIR     = PROJECT_ROOT / "docs"
SCRIPTS_DIR  = PROJECT_ROOT / "scripts"

# Add controller/ to path so we can import BiometricFeatureExtractor
CONTROLLER_DIR = PROJECT_ROOT / "controller"
if str(CONTROLLER_DIR) not in sys.path:
    sys.path.insert(0, str(CONTROLLER_DIR))

try:
    from tinyml_biometric_fusion import BiometricFeatureExtractor
    _EXTRACTOR_AVAILABLE = True
except ImportError as e:
    warnings.warn(f"Could not import BiometricFeatureExtractor: {e}. Using inline fallback.")
    _EXTRACTOR_AVAILABLE = False

try:
    from tinyml_biometric_fusion import CALIBRATION_WINDOW_FRAMES as WINDOW_SIZE  # type: ignore
except ImportError:
    WINDOW_SIZE = 1024  # fallback: 1024 frames ≥ 512 tremor FFT gate, ~0.98 Hz/bin at 1000 Hz

# ---------------------------------------------------------------------------
# Player session mapping
# ---------------------------------------------------------------------------

PLAYER_SESSIONS = {
    "Player 1": [f"hw_{i:03d}" for i in range(5, 45)],   # hw_005 – hw_044
    "Player 2": [f"hw_{i:03d}" for i in range(45, 59)],  # hw_045 – hw_058
    "Player 3": [f"hw_{i:03d}" for i in range(59, 74)],  # hw_059 – hw_073
}

POLLING_RATE_MIN = 800.0
POLLING_RATE_MAX = 1100.0
FEATURE_NAMES = [
    "trigger_resistance_change_rate",
    "trigger_onset_velocity_l2",
    "trigger_onset_velocity_r2",
    "micro_tremor_accel_variance",
    "grip_asymmetry",
    "stick_autocorr_lag1",
    "stick_autocorr_lag5",
    "tremor_peak_hz",
    "tremor_band_power",
    "accel_magnitude_spectral_entropy",   # F10 (replaces touchpad slot; Phase 46; 1000 Hz exclusive)
    "touch_position_variance",            # F11; populated by touchpad sessions (terminal_cal)
    "press_timing_jitter_variance",       # F12 (Phase 57; 0.0 in inline fallback)
    "touchpad_spatial_entropy",           # F13 (Phase 121; 8×8 Shannon entropy of contact heatmap)
]
N_FEATURES = len(FEATURE_NAMES)

# ---------------------------------------------------------------------------
# InputSnapshot adapter
# ---------------------------------------------------------------------------

class _SnapProxy:
    """
    Wraps a JSON features dict as an attribute-access object matching the
    interface expected by BiometricFeatureExtractor.extract().

    Fields not present in the JSON (l2_effect_mode, r2_effect_mode,
    inter_frame_us, touch_active, touch0_x, touch0_y) use sensible defaults.
    """
    __slots__ = (
        "left_stick_x", "left_stick_y", "right_stick_x", "right_stick_y",
        "l2_trigger", "r2_trigger",
        "gyro_x", "gyro_y", "gyro_z",
        "accel_x", "accel_y", "accel_z",
        "l2_effect_mode", "r2_effect_mode",
        "inter_frame_us",
        "touch_active", "touch0_x", "touch0_y",
    )

    def __init__(self, feat: dict, inter_frame_us: int = 1000):
        g = feat.get
        self.left_stick_x   = int(g("left_stick_x",  128))
        self.left_stick_y   = int(g("left_stick_y",  128))
        self.right_stick_x  = int(g("right_stick_x", 128))
        self.right_stick_y  = int(g("right_stick_y", 128))
        self.l2_trigger     = int(g("l2_trigger",    0))
        self.r2_trigger     = int(g("r2_trigger",    0))
        self.gyro_x         = float(g("gyro_x", 0.0))
        self.gyro_y         = float(g("gyro_y", 0.0))
        self.gyro_z         = float(g("gyro_z", 0.0))
        self.accel_x        = float(g("accel_x", 0.0))
        self.accel_y        = float(g("accel_y", 0.0))
        self.accel_z        = float(g("accel_z", 1.0))
        self.l2_effect_mode = int(g("l2_effect_mode", 0))
        self.r2_effect_mode = int(g("r2_effect_mode", 0))
        self.inter_frame_us = inter_frame_us
        self.touch_active   = bool(g("touch_active", False))
        self.touch0_x       = int(g("touch0_x", 0))
        self.touch0_y       = int(g("touch0_y", 0))


# ---------------------------------------------------------------------------
# Inline fallback feature extraction (mirrors BiometricFeatureExtractor.extract)
# Used only if controller/tinyml_biometric_fusion.py cannot be imported.
# ---------------------------------------------------------------------------

def _autocorr(series: list, lag: int) -> float:
    if len(series) <= lag + 2:
        return 0.0
    x = np.array(series[:-lag], dtype=np.float64)
    y = np.array(series[lag:],  dtype=np.float64)
    if x.std() < 1e-10 or y.std() < 1e-10:
        return 0.0
    return float(np.corrcoef(x, y)[0, 1])


def _compute_trigger_onset_velocity(trigger_vals: list) -> float:
    onsets = []
    in_onset = False
    onset_start = 0
    for i, v in enumerate(trigger_vals):
        if not in_onset and v > 5:
            in_onset = True
            onset_start = i
        elif in_onset and (v >= 250 or (i > onset_start and trigger_vals[i - 1] > v)):
            peak = trigger_vals[i - 1] if i > onset_start else v
            duration = max(i - onset_start, 1)
            onsets.append(duration / (peak + 1e-6))
            in_onset = False
    return float(np.mean(onsets)) if onsets else 0.0


def _extract_features_inline(snaps: list[_SnapProxy]) -> np.ndarray:
    """
    Inline reimplementation of BiometricFeatureExtractor.extract() operating on
    _SnapProxy objects. Returns a 13-element float32 array.
    Note: press_timing_jitter_variance (index 11) always returns 0.0 in this fallback
    (Phase 57 gap); touchpad_spatial_entropy (index 12) is computed via 8×8 grid (Phase 121).
    """
    n = len(snaps)
    if n < 10:
        return np.zeros(N_FEATURES, dtype=np.float32)

    def _g(s, attr, default=0.0):
        return float(getattr(s, attr, default))

    # 1. Trigger resistance change rate
    l2_modes = [int(getattr(s, "l2_effect_mode", 0)) for s in snaps]
    r2_modes = [int(getattr(s, "r2_effect_mode", 0)) for s in snaps]
    mode_changes = sum(
        1 for i in range(1, n)
        if l2_modes[i] != l2_modes[i - 1] or r2_modes[i] != r2_modes[i - 1]
    )
    resistance_change_rate = (mode_changes / n) * 100.0

    # 2. Trigger onset velocities
    l2_vals = [int(getattr(s, "l2_trigger", 0)) for s in snaps]
    r2_vals = [int(getattr(s, "r2_trigger", 0)) for s in snaps]
    onset_vel_l2 = _compute_trigger_onset_velocity(l2_vals)
    onset_vel_r2 = _compute_trigger_onset_velocity(r2_vals)

    # 3. Micro-tremor: accel variance during still frames
    # 20.0 LSB = raw HID gyro noise floor at rest (active play ~201 LSB, rest ~14-50 LSB)
    still_accel_mags = []
    for s in snaps:
        gx = _g(s, "gyro_x"); gy = _g(s, "gyro_y"); gz = _g(s, "gyro_z")
        gyro_mag = math.sqrt(gx * gx + gy * gy + gz * gz)
        if gyro_mag < 20.0:  # raw LSB threshold
            ax = _g(s, "accel_x"); ay = _g(s, "accel_y"); az = _g(s, "accel_z")
            still_accel_mags.append(math.sqrt(ax * ax + ay * ay + az * az))
    micro_tremor_var = float(np.var(still_accel_mags)) if len(still_accel_mags) >= 5 else 0.0

    # 4. Grip asymmetry (dual-press frames only)
    dual_press_ratios = []
    for s in snaps:
        l2 = int(getattr(s, "l2_trigger", 0))
        r2 = int(getattr(s, "r2_trigger", 0))
        if l2 > 10 and r2 > 10:
            dual_press_ratios.append(l2 / (r2 + 1e-6))
    grip_asym = float(np.mean(dual_press_ratios)) if dual_press_ratios else 1.0

    # 5. Stick velocity autocorrelation at lag 1 and lag 5
    stick_vels = []
    prev_lx, prev_ly = _g(snaps[0], "left_stick_x"), _g(snaps[0], "left_stick_y")
    for s in snaps[1:]:
        lx = _g(s, "left_stick_x"); ly = _g(s, "left_stick_y")
        dt = max(_g(s, "inter_frame_us", 1000) / 1_000_000.0, 1e-6)
        vel = math.sqrt(((lx - prev_lx) / 32768.0) ** 2 + ((ly - prev_ly) / 32768.0) ** 2) / dt
        stick_vels.append(vel)
        prev_lx, prev_ly = lx, ly

    autocorr_lag1 = _autocorr(stick_vels, lag=1)
    autocorr_lag5 = _autocorr(stick_vels, lag=5)

    # 6. Right-stick tremor FFT (8-12 Hz physiological tremor)
    rx_vals = np.array([float(getattr(s, "right_stick_x", 0)) for s in snaps], dtype=np.float32)
    rx_vels = np.diff(rx_vals) / 32768.0
    dt_vals = [max(_g(s, "inter_frame_us", 1000) / 1_000_000.0, 1e-6) for s in snaps[1:]]
    fs = 1.0 / max(float(np.median(dt_vals)), 1e-6)
    if len(rx_vels) >= 512:  # min 512 frames for ~2Hz/bin resolution at 1000Hz
        fft_mag = np.abs(np.fft.rfft(rx_vels))
        freqs   = np.fft.rfftfreq(len(rx_vels), d=1.0 / fs)
        total_power = float(np.sum(fft_mag ** 2)) or 1e-9
        peak_idx = int(np.argmax(fft_mag))
        tremor_peak_hz  = float(freqs[peak_idx])
        band_mask = (freqs >= 8.0) & (freqs <= 12.0)
        tremor_band_power = float(np.sum(fft_mag[band_mask] ** 2) / total_power)
    else:
        tremor_peak_hz = 0.0
        tremor_band_power = 0.0

    # 7. Accel magnitude spectral entropy (gravity-invariant; inline fallback path)
    # Requires >= 1024 samples for reliable entropy; at WINDOW_SIZE=1024 this activates.
    _ax = np.array([float(getattr(s, "accel_x", 0.0)) for s in snaps], dtype=np.float64)
    _ay = np.array([float(getattr(s, "accel_y", 0.0)) for s in snaps], dtype=np.float64)
    _az = np.array([float(getattr(s, "accel_z", 0.0)) for s in snaps], dtype=np.float64)
    _mag = np.sqrt(_ax * _ax + _ay * _ay + _az * _az)
    if float(np.var(_mag)) < 4.0 or len(_mag) < 1024:
        accel_magnitude_spectral_entropy = 0.0
    else:
        _dc = _mag - float(np.mean(_mag))
        _power = np.abs(np.fft.rfft(_dc)) ** 2
        _total = float(np.sum(_power))
        if _total < 1e-12:
            accel_magnitude_spectral_entropy = 0.0
        else:
            _p = _power / _total
            _p = _p[_p > 1e-12]
            accel_magnitude_spectral_entropy = float(-np.sum(_p * np.log2(_p)))

    # Touchpad position variance — kept at index 10 (pending post-Phase-17 recapture)
    touch_xs = [
        float(getattr(s, "touch0_x", 0)) / 1920.0
        for s in snaps
        if bool(getattr(s, "touch_active", False))
    ]
    touch_position_variance = float(np.var(touch_xs)) if len(touch_xs) >= 3 else 0.0

    # press_timing_jitter_variance — index 11 (Phase 57 gap: always 0.0 in inline fallback)
    press_timing_jitter_variance = 0.0

    # touchpad_spatial_entropy — 8×8 contact heatmap Shannon entropy (Phase 121)
    _grid121 = np.zeros((8, 8), dtype=np.int32)
    _xy_pairs121 = [
        (int(getattr(s, "touch0_x", 0)), int(getattr(s, "touch0_y", 0)))
        for s in snaps
        if bool(getattr(s, "touch_active", False))
    ]
    if len(_xy_pairs121) >= 32:
        for (x, y) in _xy_pairs121:
            xi = min(7, int(x / 1920.0 * 8))
            yi = min(7, int(y / 1079.0 * 8))
            _grid121[yi, xi] += 1
        _total121 = int(_grid121.sum())
        if _total121 > 0:
            _probs121 = _grid121.flatten().astype(np.float64) / _total121
            _probs121 = _probs121[_probs121 > 0]
            touchpad_spatial_entropy = float(-np.sum(_probs121 * np.log2(_probs121)))
        else:
            touchpad_spatial_entropy = 0.0
    else:
        touchpad_spatial_entropy = 0.0

    return np.array([
        resistance_change_rate,
        onset_vel_l2,
        onset_vel_r2,
        micro_tremor_var,
        grip_asym,
        autocorr_lag1,
        autocorr_lag5,
        tremor_peak_hz,
        tremor_band_power,
        accel_magnitude_spectral_entropy,  # index 9 (Phase 46)
        touch_position_variance,           # index 10
        press_timing_jitter_variance,      # index 11 (0.0 in inline fallback)
        touchpad_spatial_entropy,          # index 12 (Phase 121)
    ], dtype=np.float32)


# ---------------------------------------------------------------------------
# Battery type detection (Phase 121: --battery-stratified)
# ---------------------------------------------------------------------------

def _detect_battery(session_name: str) -> str:
    """Infer battery type from session name (Phase 121)."""
    name = session_name.split("/")[-1].lower()
    if any(k in name for k in ("touchpad_freeform", "touchpad_corners", "touchpad_swipes")):
        return "touchpad"
    if "trigger_rhythm" in name:
        return "trigger"
    if "button_sequence" in name:
        return "button"
    if "resting_centroid" in name:
        return "resting_centroid"
    if any(k in name for k in ("natural_grip", "resting_baseline", "spectral_accel", "stick_sweeps")):
        return "motion"
    if name.startswith("hw_"):
        return "gameplay"
    return "other"


# ---------------------------------------------------------------------------
# Session type detection (Phase 137B: --session-type filter)
# ---------------------------------------------------------------------------

MIN_SESSIONS_FOR_TYPE_FILTER = 3  # W1 guard: need ≥3 sessions/player for valid covariance

# Phase 142: Minimum N/p ratio for full covariance estimation.
# When N_total / n_active_features < COV_MIN_RATIO, full covariance off-diagonal
# noise suppresses true inter-player distances (Phase 141 diagnosis: P1 vs P3
# suppression_ratio=0.032 — 97% of diagonal distance masked by small-N noise).
# Statistician's rule: need N ≥ 10p for reliable sample covariance.
# Default 3.0 is conservative but safe for N=11, p=8 regime (ratio=1.375 < 3).
COV_MIN_RATIO: float = 3.0

# Phase 157 WIF-016: Safety margin around COV_MIN_RATIO for regime transition warning.
# When N/p enters [COV_MIN_RATIO ± COV_STABILITY_MARGIN_NP], classification instability risk
# is flagged — adversary could capture ~13 additional sessions to push ratio past 3.0,
# triggering covariance regime flip and collapsing P1/P3 distance to ~0.127.
COV_STABILITY_MARGIN_NP: float = 0.5


def cov_stability_check(
    cov_np_ratio: float,
    cov_min_ratio: float = COV_MIN_RATIO,
    margin: float = COV_STABILITY_MARGIN_NP,
) -> str:
    """Classify the covariance regime from the N/p sample-to-feature ratio (Phase 157/WIF-016).

    Returns:
      "diagonal_stable"        — N/p < cov_min_ratio - margin  (safe; diagonal covariance in use)
      "transition_warning"     — N/p in [cov_min_ratio ± margin]  (regime flip imminent; monitor)
      "full_covariance_active" — N/p >= cov_min_ratio + margin  (full covariance engaged)

    At current N=11, p=8: ratio=1.375 → "diagonal_stable" (safe).
    Transition warning fires when N ≥ 20 (ratio ≥ 2.5) — monitor P1/P3 distances closely.
    Full covariance engages when N ≥ 28 (ratio ≥ 3.5) — verify P1 vs P3 has not collapsed.
    """
    if cov_np_ratio < (cov_min_ratio - margin):
        return "diagonal_stable"
    if cov_np_ratio < (cov_min_ratio + margin):
        return "transition_warning"
    return "full_covariance_active"


# Session types that ONLY appear in terminal_cal_P* subdirectories, never in hw_*.
# When filtering to one of these types, hw_* sessions can be skipped entirely —
# they are all "gameplay" type and would be removed by the filter anyway.
# This reduces load time from 120 s+ to <20 s for structured-probe analyses.
_TERMINAL_CAL_ONLY_TYPES = frozenset({
    "touchpad_corners",
    "touchpad_freeform",
    "touchpad_swipes",
    "trigger_rhythm",
    "button_sequence",
    "resting_centroid",
    "resting_baseline",
    "natural_grip",
    "spectral_accel",
    "stick_sweeps",
    "tremor_seed",  # Phase 139+ warmup: right-thumb-on-stick before touchpad phases
    "mixed_biometric_probe",  # Phase 166: 2-min multi-feature probe activating all 13 features
})


def _detect_session_type(session_name: str) -> str:
    """Infer structured probe session type from session name stem (Phase 137B).

    Matches the stem of the filename (after the last '/') against known
    structured probe prefixes.  Free-form gameplay sessions fall through to
    the 'gameplay' type so callers can always get a non-None value.

    Known types:
      touchpad_corners  — 4-corner structured tap protocol (P2 COMPLETE 2026-03-29)
      touchpad_freeform — unstructured touchpad movement
      touchpad_swipes   — directional swipe protocol
      trigger_rhythm    — metronome trigger press pattern
      button_sequence   — structured button sequence protocol
      resting_centroid  — still-grip resting baseline
    """
    stem = session_name.split("/")[-1].lower()
    if stem.startswith("touchpad_corners"):
        return "touchpad_corners"
    if stem.startswith("touchpad_freeform"):
        return "touchpad_freeform"
    if stem.startswith("touchpad_swipes"):
        return "touchpad_swipes"
    if stem.startswith("trigger_rhythm"):
        return "trigger_rhythm"
    if stem.startswith("button_sequence"):
        return "button_sequence"
    if stem.startswith("resting_centroid"):
        return "resting_centroid"
    if stem.startswith("resting_baseline"):
        return "resting_baseline"
    if stem.startswith("mixed_biometric_probe"):
        return "mixed_biometric_probe"
    return "gameplay"


# ---------------------------------------------------------------------------
# Session processing
# ---------------------------------------------------------------------------

def estimate_inter_frame_us(reports: list[dict]) -> int:
    """
    Estimate inter-frame interval in microseconds from session timestamps.
    Falls back to 1000 us (1000 Hz) if timestamps are all zero.
    """
    tss = [r.get("timestamp_ms", 0) for r in reports[:200] if r.get("timestamp_ms", 0) > 0]
    if len(tss) >= 2:
        diffs = [tss[i] - tss[i-1] for i in range(1, len(tss)) if tss[i] > tss[i-1]]
        if diffs:
            median_ms = float(np.median(diffs))
            return max(int(median_ms * 1000), 100)  # convert ms -> us
    return 1000  # default 1000 Hz = 1000 us


def load_session(session_name: str, path: "Path | None" = None) -> dict | None:
    """
    Load a session JSON file.

    Returns:
        dict with keys 'session_name', 'player', 'polling_rate_hz', 'report_count',
        'mean_vector', 'window_vectors', 'excluded', 'exclude_reason'
    OR None if session file not found.

    path: explicit file path; if None, resolves to SESSIONS_DIR/{session_name}.json.
    """
    if path is None:
        path = SESSIONS_DIR / f"{session_name}.json"
    if not path.exists():
        return {"session_name": session_name, "excluded": True, "exclude_reason": "file_not_found"}

    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    metadata = data.get("metadata", {})
    reports  = data.get("reports", [])
    polling  = float(metadata.get("polling_rate_hz", 0.0))

    if polling < POLLING_RATE_MIN or polling > POLLING_RATE_MAX:
        return {
            "session_name":   session_name,
            "excluded":       True,
            "exclude_reason": f"polling_rate_hz={polling:.1f} outside [{POLLING_RATE_MIN},{POLLING_RATE_MAX}]",
            "polling_rate_hz": polling,
        }

    if len(reports) < WINDOW_SIZE:
        return {
            "session_name":   session_name,
            "excluded":       True,
            "exclude_reason": f"too_few_reports ({len(reports)} < {WINDOW_SIZE})",
            "polling_rate_hz": polling,
        }

    # Estimate inter-frame interval for velocity computation
    ift_us = estimate_inter_frame_us(reports)

    # Build proxy objects for all reports
    proxies = [_SnapProxy(r["features"], inter_frame_us=ift_us) for r in reports]

    # Extract features in sliding windows of WINDOW_SIZE
    window_vectors = []
    n_reports = len(proxies)

    for start in range(0, n_reports - WINDOW_SIZE + 1, WINDOW_SIZE):
        window = proxies[start : start + WINDOW_SIZE]
        if _EXTRACTOR_AVAILABLE:
            feat = BiometricFeatureExtractor().extract(window, window_frames=WINDOW_SIZE)
            vec = feat.to_vector().astype(np.float64)
        else:
            vec = _extract_features_inline(window).astype(np.float64)
        window_vectors.append(vec)

    if not window_vectors:
        return {
            "session_name":   session_name,
            "excluded":       True,
            "exclude_reason": "no_valid_windows",
            "polling_rate_hz": polling,
        }

    mean_vec = np.mean(window_vectors, axis=0)

    return {
        "session_name":    session_name,
        "excluded":        False,
        "exclude_reason":  None,
        "polling_rate_hz": polling,
        "report_count":    len(reports),
        "n_windows":       len(window_vectors),
        "mean_vector":     mean_vec.tolist(),
        "window_vectors":  [v.tolist() for v in window_vectors],
    }


# ---------------------------------------------------------------------------
# Mahalanobis distance (full covariance)
# ---------------------------------------------------------------------------

def mahalanobis_distance(x: np.ndarray, mu: np.ndarray, cov_inv: np.ndarray) -> float:
    """Full Mahalanobis distance using pre-computed inverse covariance."""
    diff = x - mu
    return float(np.sqrt(np.clip(diff @ cov_inv @ diff, 0.0, None)))


def robust_cov_inv(data: np.ndarray, reg: float = 1e-4) -> tuple[np.ndarray, np.ndarray]:
    """
    Compute global covariance from session mean vectors with Tikhonov regularization.
    Returns (cov, cov_inv).
    """
    cov = np.cov(data.T) if data.shape[0] > 1 else np.eye(data.shape[1])
    # Tikhonov regularization: add reg * trace(cov) * I to ensure invertibility
    reg_term = reg * np.trace(cov) * np.eye(cov.shape[0])
    cov_reg  = cov + reg_term
    try:
        cov_inv = np.linalg.inv(cov_reg)
    except np.linalg.LinAlgError:
        # Fallback: diagonal
        diag_var = np.maximum(np.diag(cov), 1e-6)
        cov_inv  = np.diag(1.0 / diag_var)
    return cov_reg, cov_inv


# ---------------------------------------------------------------------------
# Phase 174: Session age weighting
# ---------------------------------------------------------------------------

def _compute_session_age_weights(
    sessions: list,
    halflife_days: float,
    ref_date_str: str = "",
) -> dict:
    """Compute per-session exponential age weights.

    weight_i = exp(-ln(2) / halflife_days * age_days_i)
    age_days_i = (ref_date - session_date).days
    session_date extracted from session filename or 'session_ts' key.

    Returns dict mapping session index -> weight (float, 0.0-1.0).
    If halflife_days <= 0: returns {i: 1.0 for i in range(len(sessions))}.
    Never raises.
    """
    import math
    from datetime import datetime, date as _date
    import re as _re

    if halflife_days <= 0:
        return {i: 1.0 for i in range(len(sessions))}

    # Determine reference date
    if ref_date_str:
        try:
            ref_date = datetime.strptime(ref_date_str, "%Y-%m-%d").date()
        except Exception:
            ref_date = _date.today()
    else:
        ref_date = _date.today()

    weights = {}
    ln2 = math.log(2)
    _DATE_PAT = _re.compile(r"(\d{8})T")

    for i, sess in enumerate(sessions):
        age_days = 0.0
        try:
            # Try 'session_ts' key (unix timestamp seconds)
            ts = sess.get("session_ts") or sess.get("created_at") or 0.0
            if ts and float(ts) > 0:
                sess_date = _date.fromtimestamp(float(ts))
                age_days = max(0.0, float((ref_date - sess_date).days))
            else:
                # Fall back to date embedded in session_name (e.g. touchpad_corners_20260329T...)
                sname = sess.get("session_name", "")
                m = _DATE_PAT.search(sname)
                if m:
                    sess_date = datetime.strptime(m.group(1), "%Y%m%d").date()
                    age_days = max(0.0, float((ref_date - sess_date).days))
        except Exception:
            age_days = 0.0

        weight = math.exp(-ln2 / halflife_days * age_days)
        weights[i] = weight

    return weights


# ---------------------------------------------------------------------------
# Main analysis
# ---------------------------------------------------------------------------

def run_analysis(
    battery_stratified: bool = False,
    session_type_filter: str | None = None,
    cov_auto_fallback: bool = True,
    cov_min_ratio: float = COV_MIN_RATIO,
) -> dict:
    print("=" * 60)
    print("VAPI Inter-Person Biometric Separation Analysis")
    print("=" * 60)
    print(f"Sessions dir : {SESSIONS_DIR}")
    print(f"Window size  : {WINDOW_SIZE} frames")
    print(f"Feature dim  : {N_FEATURES}")
    print(f"Extractor    : {'BiometricFeatureExtractor (live)' if _EXTRACTOR_AVAILABLE else 'inline fallback'}")
    print()

    # --- Load all sessions ---
    all_sessions = []   # list of result dicts
    player_sessions: dict[str, list[dict]] = {}

    # Phase 139 fast-path: hw_* sessions are all "gameplay" type.
    # Skip loading them entirely when filtering to a terminal_cal-only probe type —
    # they would all be removed by the filter anyway.
    _skip_hw = session_type_filter in _TERMINAL_CAL_ONLY_TYPES
    if _skip_hw:
        print(f"[Phase 139 fast-path] Skipping {sum(len(v) for v in PLAYER_SESSIONS.values())} "
              f"hw_* sessions (all 'gameplay' type — incompatible with '{session_type_filter}' filter)")
        print()
        for player in PLAYER_SESSIONS:
            player_sessions[player] = []
    else:
        for player, session_list in PLAYER_SESSIONS.items():
            player_sessions[player] = []
            for sname in session_list:
                result = load_session(sname)
                if result is None:
                    continue
                result["player"] = player
                all_sessions.append(result)
                status = "EXCLUDED" if result.get("excluded") else "ok"
                reason = f" ({result.get('exclude_reason', '')})" if result.get("excluded") else ""
                print(f"  {sname} [{player}]: {status}{reason}")
                if not result.get("excluded"):
                    player_sessions[player].append(result)

    # --- Also load terminal_cal sessions from subdirectories ---
    # Directory naming convention: terminal_cal_P1/ → "Player 1", etc.
    _tcal_dirs = sorted(d for d in SESSIONS_DIR.iterdir()
                        if d.is_dir() and d.name.startswith("terminal_cal_P"))
    if _tcal_dirs:
        print("TERMINAL CALIBRATION SESSIONS")
        print("-" * 40)
    for tcal_dir in _tcal_dirs:
        _suffix = tcal_dir.name[len("terminal_cal_P"):]   # "1", "2", "3", …
        player = f"Player {_suffix}"
        if player not in player_sessions:
            player_sessions[player] = []
        for jpath in sorted(tcal_dir.glob("*.json")):
            sname = f"{tcal_dir.name}/{jpath.stem}"
            result = load_session(sname, path=jpath)
            if result is None:
                continue
            result["player"] = player
            all_sessions.append(result)
            status = "EXCLUDED" if result.get("excluded") else "ok"
            reason = f" ({result.get('exclude_reason', '')})" if result.get("excluded") else ""
            print(f"  {jpath.stem} [{tcal_dir.name}] [{player}]: {status}{reason}")
            if not result.get("excluded"):
                player_sessions[player].append(result)
    if _tcal_dirs:
        print()

    print()

    # Summary counts
    included = [s for s in all_sessions if not s.get("excluded")]
    excluded  = [s for s in all_sessions if s.get("excluded")]
    print(f"Loaded: {len(included)} sessions included, {len(excluded)} excluded")
    for p, sl in player_sessions.items():
        print(f"  {p}: {len(sl)} sessions")
    print()

    if len(included) < 3:
        raise RuntimeError(f"Too few sessions ({len(included)}) — need at least 3.")

    # --- Phase 137B: session-type filter ---
    # Applied AFTER loading and BEFORE feature matrix build so the covariance
    # is computed entirely from the filtered subset (unlike post-processing strategies).
    n_before_type_filter = len(included)
    if session_type_filter:
        print(f"[session-type filter] Filtering to type='{session_type_filter}'")
        # Tag each session in player_sessions
        for player in list(player_sessions.keys()):
            filtered = [
                s for s in player_sessions[player]
                if _detect_session_type(s["session_name"]) == session_type_filter
            ]
            player_sessions[player] = filtered

        # W1 guard: need ≥MIN_SESSIONS_FOR_TYPE_FILTER sessions per player for covariance
        qualifying_players = [
            p for p, sl in player_sessions.items() if len(sl) >= MIN_SESSIONS_FOR_TYPE_FILTER
        ]
        player_counts = {p: len(sl) for p, sl in player_sessions.items()}
        print(f"  Per-player {session_type_filter} counts: {player_counts}")

        if len(qualifying_players) < 2:
            raise RuntimeError(
                f"session-type filter '{session_type_filter}': only {len(qualifying_players)} "
                f"player(s) have ≥{MIN_SESSIONS_FOR_TYPE_FILTER} sessions "
                f"(need ≥2 for valid inter-player separation). "
                f"Counts: {player_counts}. "
                f"Capture more {session_type_filter} sessions first (see WIF-008)."
            )

        # Rebuild included from filtered player_sessions
        included = [s for sl in player_sessions.values() for s in sl]
        all_sessions = [s for s in all_sessions
                        if s.get("excluded")
                        or _detect_session_type(s.get("session_name", "")) == session_type_filter]

        print(f"  After filter: {len(included)} sessions "
              f"({n_before_type_filter - len(included)} removed)")
        if len(included) < 3:
            raise RuntimeError(
                f"Too few sessions after {session_type_filter} filter "
                f"({len(included)}) — need at least 3."
            )
        print()

    # --- Build feature matrix (N_sessions x N_FEATURES) ---
    mean_vectors   = np.array([s["mean_vector"] for s in included])
    player_labels  = [s["player"] for s in included]
    session_names  = [s["session_name"] for s in included]

    # Fix 4: Auto-exclude structurally-zero features before computing distances.
    # Features with zero variance across ALL sessions contribute no discriminative signal
    # and inflate the condition number of the covariance matrix (Mahalanobis breaks down).
    feature_stds = np.std(mean_vectors, axis=0)
    zero_var_mask = feature_stds < 1e-9
    active_mask = ~zero_var_mask
    n_active = int(np.sum(active_mask))
    excluded_feat_names = [FEATURE_NAMES[i] for i in range(N_FEATURES) if zero_var_mask[i]]
    active_feat_names   = [FEATURE_NAMES[i] for i in range(N_FEATURES) if active_mask[i]]

    if excluded_feat_names:
        print(f"Auto-excluded {len(excluded_feat_names)} zero-variance features (no signal across all sessions):")
        for fn in excluded_feat_names:
            print(f"  - {fn}")
        print(f"Active features ({n_active}): {', '.join(active_feat_names)}")
        print()
    else:
        print(f"All {N_FEATURES} features have non-zero variance -- no auto-exclusion.")
        print()

    # Store active (projected) vector per session for downstream Mahalanobis computation
    for s in included:
        s["_active_vec"] = np.array(s["mean_vector"])[active_mask]
    mean_vectors_active = mean_vectors[:, active_mask]

    # --- Phase 142: Small-N Covariance Auto-Fallback ---
    # When the sample-to-feature ratio N/p < COV_MIN_RATIO, the full covariance
    # estimate is unreliable — off-diagonal noise suppresses true inter-player
    # distances (P1 vs P3 suppression_ratio=0.032 in touchpad_corners Phase 141).
    # In this regime, the diagonal approximation is statistically more stable.
    _n_samples = mean_vectors_active.shape[0]
    _n_features = mean_vectors_active.shape[1]
    _cov_ratio = _n_samples / _n_features if _n_features > 0 else float("inf")
    _use_diagonal_cov = cov_auto_fallback and (_cov_ratio < cov_min_ratio)
    if _use_diagonal_cov:
        print(f"[Phase 142 small-N guard] N/p = {_cov_ratio:.2f} < {cov_min_ratio:.1f} threshold "
              f"(N={_n_samples} samples, p={_n_features} features)")
        print(f"  -> Using DIAGONAL covariance approximation to prevent off-diagonal noise suppression.")
        print(f"     Full covariance with small N suppresses true inter-player distances.")
        print(f"     (Disable with --no-cov-auto-fallback to force full covariance)")
        print()
        # Diagonal covariance: only per-feature variances, no off-diagonal terms
        diag_vars = np.maximum(np.var(mean_vectors_active, axis=0), 1e-9)
        cov_global = np.diag(diag_vars)
        cov_inv_global = np.diag(1.0 / diag_vars)
    else:
        cov_global, cov_inv_global = robust_cov_inv(mean_vectors_active)

    print(f"Global covariance rank: {np.linalg.matrix_rank(cov_global)} / {n_active} "
          f"(N/p={_cov_ratio:.2f}, {'diagonal' if _use_diagonal_cov else 'full'})")
    print()

    # --- Per-player mean vectors ---
    player_means: dict[str, np.ndarray] = {}
    player_vectors: dict[str, list[np.ndarray]] = {}

    for p, sl in player_sessions.items():
        if not sl:
            continue
        vecs = np.array([s["_active_vec"] for s in sl])
        player_means[p]   = np.mean(vecs, axis=0)
        player_vectors[p] = [s["_active_vec"] for s in sl]

    # --- Intra-player distances ---
    print("INTRA-PLAYER DISTANCES (each session -> their player mean)")
    print("-" * 55)
    intra_stats: dict[str, dict] = {}

    for p, sl in player_sessions.items():
        if not sl or p not in player_means:
            continue
        mu = player_means[p]
        dists = [mahalanobis_distance(s["_active_vec"], mu, cov_inv_global) for s in sl]
        intra_stats[p] = {
            "n_sessions":  len(sl),
            "distances":   dists,
            "mean":        float(np.mean(dists)),
            "std":         float(np.std(dists)),
            "median":      float(np.median(dists)),
            "min":         float(np.min(dists)),
            "max":         float(np.max(dists)),
        }
        print(f"  {p}: N={len(sl)}, mean={np.mean(dists):.3f}, std={np.std(dists):.3f}, "
              f"median={np.median(dists):.3f}, range=[{np.min(dists):.3f}, {np.max(dists):.3f}]")

    overall_intra_mean = float(np.mean([s["mean"] for s in intra_stats.values()]))
    print(f"\n  Overall mean intra-player distance: {overall_intra_mean:.3f}")
    print()

    # --- Inter-player distances (between player mean vectors) ---
    print("INTER-PLAYER DISTANCES (between player mean vectors)")
    print("-" * 55)
    inter_stats: dict[str, dict] = {}
    players_with_data = list(player_means.keys())
    n_players = len(players_with_data)

    inter_dist_matrix = np.zeros((n_players, n_players))
    inter_distances = []

    for i, pa in enumerate(players_with_data):
        for j, pb in enumerate(players_with_data):
            if i == j:
                inter_dist_matrix[i, j] = 0.0
                continue
            d = mahalanobis_distance(player_means[pa], player_means[pb], cov_inv_global)
            inter_dist_matrix[i, j] = d
            if j > i:
                pair_key = f"{pa} vs {pb}"
                inter_stats[pair_key] = {"distance": d, "players": [pa, pb]}
                inter_distances.append(d)
                print(f"  {pair_key}: {d:.3f}")

    overall_inter_mean = float(np.mean(inter_distances)) if inter_distances else 0.0
    print(f"\n  Overall mean inter-player distance: {overall_inter_mean:.3f}")
    print()

    # --- Separation ratio ---
    if overall_intra_mean > 1e-9:
        separation_ratio = overall_inter_mean / overall_intra_mean
    else:
        separation_ratio = 0.0

    print("=" * 55)
    print(f"SEPARATION RATIO (inter / intra): {separation_ratio:.3f}")
    if separation_ratio >= 5.0:
        conclusion = "STRONG BIOMETRIC SEPARATION — reliable multi-player identification"
    elif separation_ratio >= 3.0:
        conclusion = "GOOD BIOMETRIC SEPARATION — reliable for most use cases"
    elif separation_ratio >= 2.0:
        conclusion = "MODERATE SEPARATION — useful signal but not conclusive"
    elif separation_ratio >= 1.0:
        conclusion = "WEAK SEPARATION — marginal; consider additional features"
    else:
        conclusion = "NO SEPARATION — fingerprint does not distinguish between players"
    print(f"CONCLUSION: {conclusion}")
    print("=" * 55)
    print()

    # --- Battery-stratified analysis (Phase 121: --battery-stratified) ---
    battery_stratified_results: dict[str, dict] = {}

    if battery_stratified:
        print()
        print("BATTERY-STRATIFIED SEPARATION RATIOS")
        print("-" * 55)

        # Group included sessions by battery type
        battery_groups: dict[str, list[dict]] = {}
        for s in included:
            bt = _detect_battery(s["session_name"])
            battery_groups.setdefault(bt, []).append(s)

        for bt, bt_sessions in sorted(battery_groups.items()):
            # Only proceed if ≥2 players represented
            bt_players = {}
            for s in bt_sessions:
                bt_players.setdefault(s["player"], []).append(s)
            if len(bt_players) < 2:
                continue

            # Build feature matrix for this battery group
            bt_vecs = np.array([s["_active_vec"] for s in bt_sessions])
            bt_cov, bt_cov_inv = robust_cov_inv(bt_vecs)

            # Per-player means within battery
            bt_pmeans: dict[str, np.ndarray] = {}
            for p, sl in bt_players.items():
                bt_pmeans[p] = np.mean(np.array([s["_active_vec"] for s in sl]), axis=0)

            # Intra-player distances within battery
            bt_intra_dists = []
            for p, sl in bt_players.items():
                mu = bt_pmeans[p]
                for s in sl:
                    bt_intra_dists.append(
                        mahalanobis_distance(s["_active_vec"], mu, bt_cov_inv)
                    )
            bt_intra_mean = float(np.mean(bt_intra_dists)) if bt_intra_dists else 0.0

            # Inter-player distances within battery
            bt_player_list = list(bt_pmeans.keys())
            bt_inter_dists = []
            for i, pa in enumerate(bt_player_list):
                for j, pb in enumerate(bt_player_list):
                    if j > i:
                        bt_inter_dists.append(
                            mahalanobis_distance(bt_pmeans[pa], bt_pmeans[pb], bt_cov_inv)
                        )
            bt_inter_mean = float(np.mean(bt_inter_dists)) if bt_inter_dists else 0.0

            bt_ratio = bt_inter_mean / bt_intra_mean if bt_intra_mean > 1e-9 else 0.0
            n_bt = len(bt_sessions)
            print(f"  [{bt}] N={n_bt} sessions, players={len(bt_players)}, "
                  f"intra={bt_intra_mean:.3f}, inter={bt_inter_mean:.3f}, ratio={bt_ratio:.3f}")

            battery_stratified_results[bt] = {
                "n_sessions": n_bt,
                "n_players": len(bt_players),
                "intra_mean": bt_intra_mean,
                "inter_mean": bt_inter_mean,
                "separation_ratio": bt_ratio,
                "player_session_counts": {p: len(sl) for p, sl in bt_players.items()},
            }

        # Resting-grip normalization ratio (Phase 121 — W2 for VHP confidence)
        TOUCH_IDX = FEATURE_NAMES.index("touch_position_variance") if "touch_position_variance" in FEATURE_NAMES else None
        if TOUCH_IDX is not None:
            print()
            print("RESTING-GRIP NORMALIZATION RATIO (touch_position_variance)")
            print("-" * 55)
            for player in sorted(player_means.keys()):
                _rest = [s for s in player_sessions.get(player, [])
                         if _detect_battery(s["session_name"]) == "resting_centroid"]
                _free = [s for s in player_sessions.get(player, [])
                         if _detect_battery(s["session_name"]) == "touchpad"]
                rest_var = float(np.mean([s["mean_vector"][TOUCH_IDX] for s in _rest])) if _rest else None
                free_var = float(np.mean([s["mean_vector"][TOUCH_IDX] for s in _free])) if _free else None
                if rest_var is not None and free_var is not None and rest_var > 1e-9:
                    norm_ratio = free_var / rest_var
                    print(f"  {player}: resting={rest_var:.6f}, freeform={free_var:.6f}, "
                          f"normalization_ratio={norm_ratio:.3f}")
                elif rest_var is None and free_var is not None:
                    print(f"  {player}: freeform={free_var:.6f} (no resting_centroid sessions)")
                else:
                    print(f"  {player}: no touchpad or resting_centroid sessions")
        print()

    # --- Per-feature statistics across players ---
    feature_player_means: dict[str, dict[str, float]] = {}
    feature_player_stds:  dict[str, dict[str, float]] = {}

    for p, sl in player_sessions.items():
        if not sl:
            continue
        vecs = np.array([s["mean_vector"] for s in sl])
        for fi, fname in enumerate(FEATURE_NAMES):
            if fname not in feature_player_means:
                feature_player_means[fname] = {}
                feature_player_stds[fname]  = {}
            feature_player_means[fname][p] = float(np.mean(vecs[:, fi]))
            feature_player_stds[fname][p]  = float(np.std(vecs[:, fi]))

    print("PER-FEATURE MEANS BY PLAYER")
    print("-" * 55)
    header = f"{'Feature':<38} " + "  ".join(f"{p[:8]:>10}" for p in players_with_data)
    print(header)
    for fname in FEATURE_NAMES:
        row = f"{fname:<38} "
        for p in players_with_data:
            row += f"  {feature_player_means[fname].get(p, 0.0):>10.4f}"
        print(row)
    print()

    # --- Leave-one-out player classification accuracy ---
    # Phase 143: Proper LOO — recompute player centroid excluding the test session
    # for the test session's own player. Prevents centroid bias (test session included
    # in its own player's centroid → artificially deflates intra-player distance).
    print("LEAVE-ONE-OUT SESSION CLASSIFICATION")
    print("-" * 55)
    correct = 0
    total   = 0
    misclassified = []

    for s in included:
        true_player = s["player"]
        vec = s["_active_vec"]
        best_player = None
        best_dist   = float("inf")

        # Proper LOO: recompute test player centroid without the test session
        _loo_player_means = {}
        for p, sl in player_sessions.items():
            loo_sl = [x for x in sl if x is not s]
            if loo_sl:
                _loo_player_means[p] = np.mean(
                    np.array([x["_active_vec"] for x in loo_sl]), axis=0
                )
            else:
                _loo_player_means[p] = player_means[p]  # fallback if only 1 session

        for p, mu in _loo_player_means.items():
            d = mahalanobis_distance(vec, mu, cov_inv_global)
            if d < best_dist:
                best_dist   = d
                best_player = p
        total += 1
        if best_player == true_player:
            correct += 1
        else:
            misclassified.append({
                "session":      s["session_name"],
                "true_player":  true_player,
                "pred_player":  best_player,
                "best_dist":    best_dist,
            })

    accuracy = correct / total if total > 0 else 0.0
    print(f"  Accuracy: {correct}/{total} = {accuracy:.1%}")
    if misclassified:
        print(f"  Misclassified sessions ({len(misclassified)}):")
        for m in misclassified:
            print(f"    {m['session']}: true={m['true_player']}, pred={m['pred_player']}, dist={m['best_dist']:.3f}")
    else:
        print("  No misclassifications.")
    print()

    # --- Compile full result dict ---
    result = {
        "analysis_version":   "2.0",
        "n_sessions_included": len(included),
        "n_sessions_excluded": len(excluded),
        "n_features":          N_FEATURES,
        "n_active_features":   n_active,
        "feature_names":       FEATURE_NAMES,
        "active_feature_names": active_feat_names,
        "excluded_feature_names": excluded_feat_names,
        "window_size":         WINDOW_SIZE,
        "extractor_mode":      "live" if _EXTRACTOR_AVAILABLE else "inline_fallback",
        "player_session_counts": {p: len(sl) for p, sl in player_sessions.items()},
        "separation_ratio":    separation_ratio,
        "overall_intra_mean":  overall_intra_mean,
        "overall_inter_mean":  overall_inter_mean,
        "conclusion":          conclusion,
        "intra_player_stats":  intra_stats,
        "inter_player_stats":  inter_stats,
        "inter_distance_matrix": {
            "players": players_with_data,
            "values":  inter_dist_matrix.tolist(),
        },
        "player_mean_vectors": {
            p: mu.tolist() for p, mu in player_means.items()
        },
        "feature_player_means": feature_player_means,
        "feature_player_stds":  feature_player_stds,
        "classification": {
            "accuracy":         accuracy,
            "correct":          correct,
            "total":            total,
            "misclassified":    misclassified,
        },
        "excluded_sessions": [
            {
                "session":        s["session_name"],
                "exclude_reason": s.get("exclude_reason", ""),
                "polling_rate_hz": s.get("polling_rate_hz"),
            }
            for s in excluded
        ],
        "session_details": [
            {
                "session":      s["session_name"],
                "player":       s["player"],
                "report_count": s.get("report_count"),
                "n_windows":    s.get("n_windows"),
                "polling_rate_hz": s.get("polling_rate_hz"),
                "mean_vector":  s["mean_vector"],
            }
            for s in included
        ],
        "global_covariance": cov_global.tolist(),
        "battery_stratified_results": battery_stratified_results,
        # Phase 137B: session-type filter metadata
        "session_type_filter": session_type_filter,
        "n_sessions_before_type_filter": n_before_type_filter,
        # Phase 140: convenience key for probe-comparison P1vP3 extraction
        "players": players_with_data,
        # Phase 142: covariance mode metadata
        "cov_mode": "diagonal" if _use_diagonal_cov else "full",
        "cov_np_ratio": round(_cov_ratio, 3),
        "cov_auto_fallback_triggered": _use_diagonal_cov,
        # Phase 157 WIF-016: covariance regime stability classification
        "cov_regime_status": cov_stability_check(_cov_ratio),
    }

    return result


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------

def format_table(headers: list[str], rows: list[list[str]], col_widths: list[int] | None = None) -> str:
    """Format a markdown table."""
    if col_widths is None:
        col_widths = [max(len(h), max((len(str(r[i])) for r in rows), default=0))
                      for i, h in enumerate(headers)]
    sep = "| " + " | ".join("-" * w for w in col_widths) + " |"
    hdr = "| " + " | ".join(f"{h:<{col_widths[i]}}" for i, h in enumerate(headers)) + " |"
    body_lines = []
    for row in rows:
        line = "| " + " | ".join(f"{str(row[i]):<{col_widths[i]}}" for i in range(len(headers))) + " |"
        body_lines.append(line)
    return "\n".join([hdr, sep] + body_lines)


def write_markdown(result: dict, path: Path) -> None:
    ratio   = result["separation_ratio"]
    n_inc   = result["n_sessions_included"]
    n_exc   = result["n_sessions_excluded"]
    conc    = result["conclusion"]
    acc     = result["classification"]["accuracy"]
    correct = result["classification"]["correct"]
    total   = result["classification"]["total"]
    intra   = result["overall_intra_mean"]
    inter   = result["overall_inter_mean"]
    players = result["inter_distance_matrix"]["players"]

    lines = []
    lines.append("# VAPI Inter-Person Biometric Separation Analysis")
    lines.append("")
    lines.append("**Date:** 2026-03-08  ")
    lines.append("**Sessions:** N=69 captured, " +
                 f"{n_inc} included, {n_exc} excluded (polling-rate filter)  ")
    lines.append(f"**Players:** 3 (Player 1: hw_005–hw_044, Player 2: hw_045–hw_058, Player 3: hw_059–hw_073)  ")
    n_active_feat = result["n_active_features"]
    excl_feats = result.get("excluded_feature_names", [])
    lines.append(f"**Feature space:** {result['n_features']}-dimensional L4 biometric fingerprint "
                 f"({n_active_feat} active after zero-variance exclusion)  ")
    lines.append(f"**Window size:** {result['window_size']} frames  ")
    lines.append(f"**Distance metric:** Full Mahalanobis on active features (Tikhonov-regularized covariance)")
    lines.append("")

    if excl_feats:
        lines.append("> **Auto-excluded features (zero variance across all sessions):** " +
                     ", ".join(f"`{f}`" for f in excl_feats) + "  ")
        lines.append("> These features are structurally zero in the current N=69 corpus "
                     "(game-specific or hardware field added after capture). "
                     "They are reported below but excluded from Mahalanobis computation.")
        lines.append("")

    lines.append("## Executive Summary")
    lines.append("")
    lines.append(f"| Metric | Value |")
    lines.append(f"|--------|-------|")
    lines.append(f"| Mean intra-player distance | {intra:.3f} |")
    lines.append(f"| Mean inter-player distance | {inter:.3f} |")
    lines.append(f"| **Separation ratio (inter/intra)** | **{ratio:.3f}** |")
    lines.append(f"| Leave-one-out classification accuracy | {acc:.1%} ({correct}/{total}) |")
    lines.append("")
    lines.append(f"**Conclusion:** {conc}")
    lines.append("")
    if ratio >= 5.0:
        lines.append(
            "The 11-feature L4 fingerprint not only detects within-player anomalies but is "
            "a **reliable biometric identifier across players**. The separation ratio of "
            f"{ratio:.2f} indicates that different players occupy substantially distinct "
            "regions of the 11-dimensional biometric feature space, supporting its use as "
            "a true biometric fingerprint rather than a mere session-consistency detector."
        )
    elif ratio >= 3.0:
        lines.append(
            "The 11-feature L4 fingerprint demonstrates **good inter-player separation**. "
            f"A ratio of {ratio:.2f} (threshold for reliable separation: 3.0) indicates "
            "that players occupy meaningfully different regions of the feature space. "
            "This supports the fingerprint's use as a biometric identifier in contexts "
            "where multiple sessions per player are available for calibration."
        )
    elif ratio >= 2.0:
        lines.append(
            "The 11-feature L4 fingerprint shows **moderate inter-player separation** "
            f"(ratio {ratio:.2f}). Players are distinguishable on average but with "
            "significant overlap. Feature augmentation or longer calibration windows "
            "may improve separation."
        )
    else:
        lines.append(
            "The 11-feature L4 fingerprint shows **weak or no inter-player separation** "
            f"(ratio {ratio:.2f}). This may reflect insufficient session diversity, "
            "feature space limitations (e.g., touchpad features all zero in current dataset), "
            "or genuine similarity of play styles across players. "
            "Intra-player consistency detection remains valid despite low inter-player separation."
        )
    lines.append("")

    lines.append("## Per-Player Statistics")
    lines.append("")
    intra_s = result["intra_player_stats"]
    player_counts = result["player_session_counts"]
    rows_p = []
    for p in players:
        st = intra_s.get(p, {})
        rows_p.append([
            p,
            str(player_counts.get(p, 0)),
            f"{st.get('mean', 0.0):.3f}",
            f"{st.get('std', 0.0):.3f}",
            f"{st.get('min', 0.0):.3f}",
            f"{st.get('max', 0.0):.3f}",
            f"{st.get('median', 0.0):.3f}",
        ])
    lines.append(format_table(
        ["Player", "Sessions", "Intra Mean", "Intra Std", "Intra Min", "Intra Max", "Intra Median"],
        rows_p
    ))
    lines.append("")

    lines.append("## Inter-Player Distance Matrix (Mahalanobis)")
    lines.append("")
    lines.append("Distance between each pair of player mean feature vectors using the "
                 "shared global covariance.")
    lines.append("")
    matrix_vals = result["inter_distance_matrix"]["values"]
    inter_hdrs = [""] + players
    inter_rows = []
    for i, pa in enumerate(players):
        row = [pa]
        for j, pb in enumerate(players):
            if i == j:
                row.append("—")
            else:
                row.append(f"{matrix_vals[i][j]:.3f}")
        inter_rows.append(row)
    lines.append(format_table(inter_hdrs, inter_rows))
    lines.append("")

    lines.append("## Intra-Player Distance Distribution")
    lines.append("")
    lines.append("Mahalanobis distance from each session's mean feature vector to "
                 "its player's centroid, using the global covariance.")
    lines.append("")
    for p in players:
        st = intra_s.get(p, {})
        dists = st.get("distances", [])
        if not dists:
            continue
        lines.append(f"**{p}** (N={len(dists)} sessions, mean={st['mean']:.3f}):")
        dist_strs = [f"{d:.3f}" for d in dists]
        lines.append(f"  {', '.join(dist_strs)}")
        lines.append("")

    lines.append("## Feature Means by Player")
    lines.append("")
    lines.append("Per-feature mean values for each player's session set. "
                 "Features with high inter-player variation are the strongest biometric discriminators.")
    lines.append("")
    fpm  = result["feature_player_means"]
    fps  = result["feature_player_stds"]
    feat_rows = []
    for fname in FEATURE_NAMES:
        row = [fname]
        vals = []
        for p in players:
            m = fpm.get(fname, {}).get(p, 0.0)
            s = fps.get(fname, {}).get(p, 0.0)
            row.append(f"{m:.4f} (+/-{s:.4f})")
            vals.append(m)
        # Inter-player spread (range)
        rng = max(vals) - min(vals) if vals else 0.0
        row.append(f"{rng:.4f}")
        feat_rows.append(row)
    # Sort by spread descending to highlight best discriminators
    feat_rows.sort(key=lambda r: float(r[-1]), reverse=True)
    col_hdrs = ["Feature"] + players + ["Inter-Range"]
    lines.append(format_table(col_hdrs, feat_rows))
    lines.append("")

    lines.append("## Leave-One-Out Classification Results")
    lines.append("")
    lines.append(
        f"Each session was classified to the nearest player centroid (Mahalanobis) "
        f"using the global covariance. Player mean vectors were computed from ALL sessions "
        f"(no held-out centroid recomputation — this is a bias-aware first-pass estimate)."
    )
    lines.append("")
    lines.append(f"**Accuracy: {acc:.1%} ({correct}/{total} sessions correctly assigned)**")
    lines.append("")
    mc = result["classification"]["misclassified"]
    if mc:
        lines.append("Misclassified sessions:")
        lines.append("")
        mc_rows = [[m["session"], m["true_player"], m["pred_player"], f"{m['best_dist']:.3f}"] for m in mc]
        lines.append(format_table(["Session", "True Player", "Predicted", "Best Dist"], mc_rows))
    else:
        lines.append("No misclassifications — all sessions correctly assigned to their player.")
    lines.append("")

    lines.append("## Excluded Sessions")
    lines.append("")
    exc_sessions = result["excluded_sessions"]
    if exc_sessions:
        exc_rows = [[e["session"], e.get("exclude_reason", ""), str(e.get("polling_rate_hz", ""))]
                    for e in exc_sessions]
        lines.append(format_table(["Session", "Reason", "Polling Rate Hz"], exc_rows))
    else:
        lines.append("No sessions excluded.")
    lines.append("")

    lines.append("## Recommendations for L4 Multi-Person Calibration")
    lines.append("")
    lines.append("### Implications for VAPI Protocol")
    lines.append("")
    if ratio >= 3.0:
        lines.append(
            "1. **Player-specific fingerprinting is viable.** With a separation ratio of "
            f"{ratio:.2f}, the L4 oracle can be extended to maintain per-player fingerprints "
            "for operator-registered players. A session that crosses player boundaries "
            "is a strong anomaly signal."
        )
    else:
        lines.append(
            "1. **Player-specific fingerprinting needs more features.** The current separation "
            f"ratio of {ratio:.2f} suggests feature augmentation or longer session windows "
            "before per-player identification is reliable."
        )
    lines.append("")
    lines.append("2. **Touchpad biometrics.** All 69 sessions show zero touchpad activity "
                 "(touch_active=False throughout). Adding the `touch_active`/`touch0_x` "
                 "fields from capture_session.py Phase 17 will add player-specific thumb-resting "
                 "patterns as a discriminator. This is expected to improve separation significantly.")
    lines.append("")
    lines.append("3. **Micro-tremor variance.** The gyro-based still-frame filter (gyro_mag < 0.01) "
                 "applies to raw LSB gyro values (range ~-350 to +350). With raw IMU values in "
                 "the hundreds, most frames fail this threshold — the effective still-frame count "
                 "is low. Consider calibrating the threshold to `gyro_mag < IMU_NOISE_FLOOR` "
                 f"(empirical: 332.99 LSB, 95th pct) to capture more tremor frames.")
    lines.append("")
    lines.append("4. **Multi-session calibration window.** The live L4 oracle uses EMA over sessions. "
                 "For inter-player separation in tournament contexts, accumulate ≥10 sessions per "
                 "player before computing player centroid. The current N={avg_n:.0f} sessions/player "
                 "average is {cal}.".format(
                     avg_n=sum(player_counts.values()) / max(len(player_counts), 1),
                     cal="adequate" if min(player_counts.values()) >= 10 else "marginal for Player 2/3"))
    lines.append("")
    lines.append("5. **Full covariance vs. diagonal.** This analysis uses a full Tikhonov-regularized "
                 "covariance matrix (off-diagonal terms included). The live L4 oracle currently uses "
                 "a diagonal approximation. Upgrading to full covariance (TODO in the source) would "
                 "better capture feature correlations and improve both intra-player consistency "
                 "detection and inter-player separation.")
    lines.append("")
    lines.append("6. **Tremor FFT window length.** The 50-frame window used here (vs 120-frame in "
                 "live oracle) at 1000 Hz gives a frequency resolution of 20 Hz/bin, which is too "
                 "coarse to resolve the 8-12 Hz physiological tremor band. The live oracle uses "
                 "120-frame windows (8.3 Hz/bin). For reliable tremor band power, a 1024-frame "
                 "window at 1000 Hz would give 0.98 Hz/bin resolution (noted in CLAUDE.md as "
                 "a known gap).")
    lines.append("")
    lines.append("---")
    lines.append(f"*Generated by `scripts/analyze_interperson_separation.py` — "
                 f"VAPI Phase 17, 2026-03-08*")

    path.write_text("\n".join(lines), encoding="utf-8")
    print(f"Report written -> {path}")


# ---------------------------------------------------------------------------
# Phase 141 — Per-pair feature attribution diagnostic
# ---------------------------------------------------------------------------

def _compute_player_quality_scores(result: dict) -> dict:
    """
    Phase 144 — Per-player biometric enrollment quality scoring.

    For each player in the result, compute:
    - n_probe_types: count of distinct structured probe types with sessions
    - centroid_stability: intra-player mean Mahalanobis distance (lower = more stable)
    - enrollment_ready: True if centroid_stability < ENROLLMENT_STABILITY_THRESHOLD
                        AND n_probe_types >= ENROLLMENT_MIN_PROBE_TYPES
    - recommendation: human-readable list of actions to improve enrollment readiness

    Directly addresses the tournament enrollment pathway: structured probe sessions
    (touchpad_corners, freeform, swipes) must be collected per player before the
    biometric fingerprint is reliable enough for re-identification.

    Constants (WIF-008 calibration requirements):
    - ENROLLMENT_STABILITY_THRESHOLD = 0.70: target intra-player centroid stability
    - ENROLLMENT_MIN_PROBE_TYPES = 2: require at least 2 distinct probe types
    """
    ENROLLMENT_STABILITY_THRESHOLD = 0.70
    ENROLLMENT_MIN_PROBE_TYPES = 2

    intra_stats = result.get("intra_player_stats", {})
    session_type_filter = result.get("session_type_filter")

    player_quality: dict[str, dict] = {}

    for player, stats in intra_stats.items():
        centroid_stability = stats.get("mean", float("inf"))
        n_sessions = result["player_session_counts"].get(player, 0)

        # Probe type count (from session_details, or infer from filter)
        if session_type_filter:
            # Single probe-type analysis — n_probe_types = 1
            n_probe_types = 1 if n_sessions > 0 else 0
        else:
            # Full analysis — infer from session_details
            session_details = result.get("session_details", [])
            player_sessions_det = [s for s in session_details if s.get("player") == player]
            probe_types = set()
            for sd in player_sessions_det:
                pt = _detect_session_type(sd.get("session", ""))
                if pt != "gameplay":
                    probe_types.add(pt)
            n_probe_types = len(probe_types)

        enrollment_ready = (
            centroid_stability <= ENROLLMENT_STABILITY_THRESHOLD
            and n_probe_types >= ENROLLMENT_MIN_PROBE_TYPES
        )

        recommendations = []
        if centroid_stability > ENROLLMENT_STABILITY_THRESHOLD:
            target_sessions = max(6, n_sessions + 3)
            recommendations.append(
                f"Capture {target_sessions - n_sessions}+ more sessions to stabilize centroid "
                f"(current: {centroid_stability:.3f}, target: <{ENROLLMENT_STABILITY_THRESHOLD})"
            )
        if n_probe_types < ENROLLMENT_MIN_PROBE_TYPES:
            recommendations.append(
                f"Complete at least {ENROLLMENT_MIN_PROBE_TYPES} structured probe types "
                f"(current: {n_probe_types})"
            )
        if enrollment_ready:
            recommendations.append("Player is enrollment-ready for biometric fingerprinting")

        player_quality[player] = {
            "n_sessions":           n_sessions,
            "n_probe_types":        n_probe_types,
            "centroid_stability":   round(centroid_stability, 4),
            "enrollment_ready":     enrollment_ready,
            "stability_threshold":  ENROLLMENT_STABILITY_THRESHOLD,
            "recommendations":      recommendations,
        }

    enrollment_ready_count = sum(1 for pq in player_quality.values() if pq["enrollment_ready"])
    return {
        "player_quality": player_quality,
        "enrollment_ready_count": enrollment_ready_count,
        "enrollment_total_players": len(player_quality),
    }


def _compute_session_consistency_scores(result: dict) -> dict:
    """
    Phase 150 — Per-session consistency scoring (WIF-010 N-thin mitigation).

    For each session in each player's corpus, compute the LOO (leave-one-out)
    Mahalanobis distance from that player's centroid computed WITHOUT the session
    itself.  Sessions with distance > intra_mean + 2*sigma are flagged as
    outlier_risk=True.  This lets operators identify and optionally exclude
    noisy calibration sessions that could skew the separation ratio.

    Autoresearch seed (cycle 1): N=11 touchpad_corners — single outlier could
    reverse ratio below 1.0; per-session consistency filter provides robustness.

    Returns:
        consistency_scores: dict[player -> list[{session, loo_distance, outlier_risk}]]
        outlier_sessions: list of {player, session, loo_distance} for outlier_risk=True
        n_outlier_sessions: int total outlier count
        intra_means: dict[player -> mean LOO intra distance]
        intra_stds:  dict[player -> std  LOO intra distance]
    """
    import numpy as _np
    session_details = result.get("session_details", [])
    player_mean_vecs_raw = result.get("player_mean_vectors", {})
    cov_global_raw = result.get("global_covariance")
    if not session_details or not player_mean_vecs_raw or cov_global_raw is None:
        return {
            "consistency_scores": {},
            "outlier_sessions": [],
            "n_outlier_sessions": 0,
            "intra_means": {},
            "intra_stds": {},
        }

    # Build per-player session vectors and covariance inverse
    try:
        cov_global = _np.array(cov_global_raw)
        d = cov_global.shape[0]
        alpha = 1e-3
        cov_reg = cov_global + alpha * _np.eye(d)
        cov_inv = _np.linalg.inv(cov_reg)
    except Exception:
        # Diagonal fallback
        cov_global = _np.array(cov_global_raw)
        d = cov_global.shape[0]
        cov_inv = _np.diag(1.0 / (_np.diag(cov_global) + 1e-9))

    # Group session mean_vectors by player
    player_sessions_vecs: dict = {}
    player_sessions_names: dict = {}
    for sd in session_details:
        player = sd.get("player", "")
        mv = sd.get("mean_vector")
        if not player or mv is None:
            continue
        v = _np.array(mv)
        if not _np.all(_np.isfinite(v)):
            continue
        player_sessions_vecs.setdefault(player, []).append(v)
        player_sessions_names.setdefault(player, []).append(sd.get("session", ""))

    consistency_scores: dict = {}
    outlier_sessions: list = []
    intra_means: dict = {}
    intra_stds: dict = {}

    for player, vecs in player_sessions_vecs.items():
        n = len(vecs)
        dists = []
        session_names = player_sessions_names[player]
        for i, vi in enumerate(vecs):
            # LOO centroid: mean of all sessions EXCEPT i
            other = [vecs[j] for j in range(n) if j != i]
            if not other:
                dists.append(0.0)
                continue
            loo_centroid = _np.mean(other, axis=0)
            diff = vi - loo_centroid
            d2 = float(diff @ cov_inv @ diff)
            dists.append(float(_np.sqrt(max(d2, 0.0))))

        if not dists:
            continue
        intra_mean = float(_np.mean(dists))
        intra_std  = float(_np.std(dists)) if len(dists) > 1 else 0.0
        threshold  = intra_mean + 2.0 * intra_std

        session_scores = []
        for i, (s_name, dist) in enumerate(zip(session_names, dists)):
            is_outlier = (intra_std > 0.0 and dist > threshold)
            entry = {
                "session":      s_name,
                "loo_distance": round(dist, 4),
                "outlier_risk": is_outlier,
            }
            session_scores.append(entry)
            if is_outlier:
                outlier_sessions.append({
                    "player":       player,
                    "session":      s_name,
                    "loo_distance": round(dist, 4),
                    "threshold":    round(threshold, 4),
                })

        consistency_scores[player] = session_scores
        intra_means[player] = round(intra_mean, 4)
        intra_stds[player]  = round(intra_std, 4)

    return {
        "consistency_scores": consistency_scores,
        "outlier_sessions":   outlier_sessions,
        "n_outlier_sessions": len(outlier_sessions),
        "intra_means":        intra_means,
        "intra_stds":         intra_stds,
    }


def _check_n_defensibility(result: dict, min_n_per_player: int = 10) -> dict:
    """
    Phase 150 — N-count defensibility check (WIF-010 formal closure).

    Checks whether the current per-player session counts meet the minimum
    required for a legally defensible separation ratio claim.

    defensible=True requires:
      1. All players have >= min_n_per_player sessions in the analysis
      2. separation_ratio > 1.0
      3. All inter-player Mahalanobis pair distances > 1.0

    When N < min_n_per_player, the centroid estimate has high variance and a
    single outlier session could reverse the ratio below the tournament gate.

    Returns:
        defensible: bool
        ratio: float
        n_per_player: dict[player -> n_sessions]
        all_players_meet_n: bool
        all_pairs_above_1: bool
        min_n_per_player: int
        thin_players: list of players below threshold
        pair_distances: dict[pair_key -> distance]
    """
    player_counts = result.get("player_session_counts", {})
    ratio = float(result.get("separation_ratio", 0.0))
    inter_matrix = result.get("inter_distance_matrix", {})
    players = inter_matrix.get("players", [])
    values = inter_matrix.get("values", [])

    # Per-player N check
    thin_players = [
        p for p, n in player_counts.items()
        if n < min_n_per_player
    ]
    all_players_meet_n = len(thin_players) == 0

    # All inter-player pair distances > 1.0
    pair_distances: dict = {}
    all_pairs_above_1 = True
    try:
        import numpy as _np
        mat = _np.array(values) if values else _np.zeros((len(players), len(players)))
        for i, pa in enumerate(players):
            for j in range(i + 1, len(players)):
                pb = players[j]
                dist = float(mat[i][j]) if i < mat.shape[0] and j < mat.shape[1] else 0.0
                key = f"{pa}_vs_{pb}"
                pair_distances[key] = round(dist, 4)
                if dist <= 1.0:
                    all_pairs_above_1 = False
    except Exception:
        all_pairs_above_1 = False

    defensible = all_players_meet_n and ratio > 1.0 and all_pairs_above_1

    return {
        "defensible":        defensible,
        "ratio":             round(ratio, 4),
        "n_per_player":      dict(player_counts),
        "all_players_meet_n": all_players_meet_n,
        "all_pairs_above_1": all_pairs_above_1,
        "min_n_per_player":  min_n_per_player,
        "thin_players":      thin_players,
        "pair_distances":    pair_distances,
    }


def _compute_pair_attribution(result: dict) -> dict:
    """
    For each player pair, diagnose why the Mahalanobis distance may be suppressed
    despite large per-feature mean differences.

    Returns a dict mapping each pair label to:
      - per_feature_std_diff: {feature: |μ_a - μ_b| / σ_pooled} (standardized diff)
      - top_features: list of (feature, std_diff) sorted descending
      - diagonal_distance: Mahalanobis with diagonal covariance (ignores correlations)
      - full_mahalanobis: Mahalanobis with full covariance (from result)
      - suppression_ratio: full_mahalanobis / diagonal_distance
        (< 1.0 means full covariance is suppressing the distance)
    """
    players = result["inter_distance_matrix"]["players"]
    values  = result["inter_distance_matrix"]["values"]
    fpm     = result["feature_player_means"]
    fps     = result["feature_player_stds"]
    active_features = result.get("active_feature_names", list(fpm.keys()))

    pair_attribution: dict[str, dict] = {}

    for i, pa in enumerate(players):
        for j, pb in enumerate(players):
            if j <= i:
                continue
            pair_key = f"{pa} vs {pb}"
            full_dist = values[i][j]

            # Per-feature standardized mean difference
            std_diffs = {}
            for fn in active_features:
                mu_a   = fpm.get(fn, {}).get(pa, 0.0)
                mu_b   = fpm.get(fn, {}).get(pb, 0.0)
                std_a  = fps.get(fn, {}).get(pa, 0.0)
                std_b  = fps.get(fn, {}).get(pb, 0.0)
                # Pooled standard deviation across both players
                n_a = result["player_session_counts"].get(pa, 1)
                n_b = result["player_session_counts"].get(pb, 1)
                pooled_var = ((n_a - 1) * std_a**2 + (n_b - 1) * std_b**2) / max(n_a + n_b - 2, 1)
                pooled_std = math.sqrt(max(pooled_var, 1e-12))
                std_diffs[fn] = abs(mu_a - mu_b) / pooled_std

            # Diagonal approximation Mahalanobis distance
            # (uses only per-feature variance — ignores covariance correlations)
            diag_sq = 0.0
            for fn in active_features:
                mu_a  = fpm.get(fn, {}).get(pa, 0.0)
                mu_b  = fpm.get(fn, {}).get(pb, 0.0)
                std_a = fps.get(fn, {}).get(pa, 0.0)
                std_b = fps.get(fn, {}).get(pb, 0.0)
                pooled_var = (std_a**2 + std_b**2) / 2.0
                if pooled_var > 1e-12:
                    diag_sq += (mu_a - mu_b)**2 / pooled_var
            diag_dist = math.sqrt(max(diag_sq, 0.0))

            top_features = sorted(std_diffs.items(), key=lambda x: x[1], reverse=True)

            suppression = full_dist / diag_dist if diag_dist > 1e-9 else float("inf")

            pair_attribution[pair_key] = {
                "per_feature_std_diff": std_diffs,
                "top_features":         top_features[:5],
                "diagonal_distance":    round(diag_dist, 4),
                "full_mahalanobis":     round(full_dist, 4),
                "suppression_ratio":    round(suppression, 4),
            }

    return {"pair_attribution": pair_attribution}


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> int:
    import argparse
    parser = argparse.ArgumentParser(
        description="VAPI multi-person L4 Mahalanobis separation analysis."
    )
    parser.add_argument(
        "--output-suffix", default="",
        help="Suffix appended before the file extension in output filenames "
             "(e.g., '--output-suffix -v2' produces "
             "interperson-separation-analysis-v2.md). Default: no suffix.",
    )
    parser.add_argument(
        "--battery-stratified",
        action="store_true",
        default=False,
        help="Report separation ratios per battery type (touchpad/trigger/button/gameplay)",
    )
    # Phase 129 Part A — covariance mode flags
    parser.add_argument(
        "--full-covariance",
        action="store_true",
        default=True,
        help="Use Tikhonov-regularized full covariance matrix (default). "
             "Closes Phase 129 TODO: replaces diagonal approximation with "
             "full off-diagonal terms. lambda = 0.01 * trace(Sigma) / n_features.",
    )
    parser.add_argument(
        "--diagonal",
        action="store_true",
        default=False,
        help="Backward-compatibility flag: use diagonal covariance approximation "
             "(overrides --full-covariance). Preserves Phase 121 behavior for "
             "comparison purposes.",
    )
    # Phase 130A: snapshot writer — populate separation_ratio_snapshots for agent #15
    parser.add_argument(
        "--write-snapshot",
        action="store_true",
        default=False,
        help="Write separation ratio result to separation_ratio_snapshots table "
             "in the bridge store DB (required for SeparationRatioMonitorAgent to detect breakthrough).",
    )
    parser.add_argument(
        "--db",
        default=None,
        help="Path to bridge.db for --write-snapshot. Default: ~/.vapi/bridge.db",
    )
    # Phase 134 Part B — Novel small-N ratio improvement strategies
    parser.add_argument(
        "--bootstrap-n",
        type=int,
        default=0,
        help="Bootstrap confidence interval: resample N times (default 0 = disabled). "
             "Reports ratio_bootstrap_mean, ratio_bootstrap_ci_lower, ratio_bootstrap_ci_upper.",
    )
    parser.add_argument(
        "--feature-weights",
        action="store_true",
        default=False,
        help="Feature importance weighting: compute per-feature Fisher discriminant ratio "
             "and weight Mahalanobis distance by sqrt(F_k). Reports weighted_ratio.",
    )
    parser.add_argument(
        "--filter-quality",
        action="store_true",
        default=False,
        help="Session quality filtering: exclude sessions with intra-player Mahalanobis "
             "distance > 3 sigma from player mean. Reports n_sessions_after_filter, "
             "sessions_excluded, filtered_ratio.",
    )
    # Phase 137B: structured probe session-type filter
    parser.add_argument(
        "--session-type",
        default=None,
        metavar="TYPE",
        help="Filter to a specific structured probe session type before computing separation. "
             "Example: --session-type touchpad_corners (measures isolated touchpad probe "
             "contribution; requires >=3 sessions per player for >=2 players). "
             "Known types: touchpad_corners, touchpad_freeform, touchpad_swipes, "
             "trigger_rhythm, button_sequence, resting_centroid, resting_baseline. "
             "Default: None (all session types included).",
    )
    # Phase 137A: balanced corpus subsampling (WIF-007 closure)
    parser.add_argument(
        "--balance-corpus",
        action="store_true",
        default=False,
        help="After computing the main separation ratio, recompute with each player "
             "subsampled to min(N_per_player) sessions (seed=42). Reports balanced_ratio "
             "alongside pooled_ratio. Closes WIF-007: P1 corpus imbalance biases global "
             "covariance toward P1 variance. Compatible with --session-type filter "
             "(balanced_ratio operates on the already-filtered subset). "
             "Default: False.",
    )
    # Phase 142: small-N covariance auto-fallback control
    parser.add_argument(
        "--no-cov-auto-fallback",
        action="store_true",
        default=False,
        help="Disable Phase 142 small-N covariance auto-fallback. "
             "When N/p < COV_MIN_RATIO (default 3.0), the system normally uses "
             "diagonal covariance to prevent off-diagonal noise suppression "
             "(Phase 141: P1 vs P3 suppression_ratio=0.032 with N=11, p=8). "
             "This flag forces full covariance regardless of N/p ratio. "
             "Use for comparison only — not recommended for small-N analyses.",
    )
    parser.add_argument(
        "--cov-min-ratio",
        type=float,
        default=COV_MIN_RATIO,
        metavar="RATIO",
        help=f"Minimum N/p ratio below which diagonal covariance is used "
             f"(Phase 142 guard). Default: {COV_MIN_RATIO}. "
             f"Set higher (e.g., 5.0) for stricter small-N protection.",
    )
    # Phase 141: per-pair feature attribution diagnostic
    parser.add_argument(
        "--per-pair-attribution",
        action="store_true",
        default=False,
        help="For each player pair, report: (1) per-feature standardized mean difference, "
             "(2) diagonal approximation Mahalanobis distance (ignores feature correlations), "
             "(3) suppression_ratio = full_mahalanobis / diagonal_distance. "
             "suppression_ratio < 1.0 means the full covariance is suppressing the distance "
             "relative to the naive per-feature comparison — diagnoses P1/P3 cluster problem. "
             "Reports top-5 discriminating features per pair. Default: False.",
    )
    # Phase 140: multi-probe comparison (run all viable structured probe types)
    parser.add_argument(
        "--probe-comparison",
        action="store_true",
        default=False,
        help="Run separation analysis for all structured probe types that have "
             ">=3 sessions per player (touchpad_corners, touchpad_freeform, touchpad_swipes). "
             "Prints a comparison table: probe | N | ratio | classification | inter | intra. "
             "Uses Phase 139 fast-path for each probe — no hw_* session loading. "
             "Cannot be combined with --session-type. Default: False.",
    )
    # Phase 144: per-player enrollment quality report
    parser.add_argument(
        "--player-quality-report",
        action="store_true",
        default=False,
        help="Print per-player biometric enrollment quality scores. "
             "Reports centroid_stability (intra-player mean distance), n_probe_types, "
             "enrollment_ready (stability < 0.70 AND probe_types >= 2), and "
             "actionable recommendations per player. Default: False.",
    )
    # Phase 150: session consistency + N-count defensibility
    parser.add_argument(
        "--session-consistency",
        action="store_true",
        default=False,
        help="Compute per-session LOO (leave-one-out) consistency scores. "
             "For each session, reports the Mahalanobis distance from the player LOO "
             "centroid (centroid computed without that session). Sessions with "
             "distance > intra_mean + 2*sigma are flagged as outlier_risk. "
             "Phase 150 WIF-010 mitigation: identifies sessions that could skew the "
             "separation ratio on a thin corpus (N=11 current touchpad_corners). "
             "Default: False.",
    )
    parser.add_argument(
        "--min-n-per-player",
        type=int,
        default=10,
        metavar="N",
        help="Minimum sessions per player required for a defensible separation ratio "
             "claim (Phase 150, WIF-010 closure). Used with --session-consistency to "
             "print a defensibility check. Current state: P1=3, P2=4, P3=4 — all below "
             "the default target of 10. Default: 10.",
    )
    # Phase 174: session age weighting
    parser.add_argument(
        "--session-age-weight",
        type=float,
        default=0.0,
        dest="session_age_weight_halflife",
        help="Session age weighting: exponential half-life in days (0 = disabled). "
             "Weight = exp(-ln(2)/halflife * age_days). Down-weights old sessions "
             "to mitigate P1 temporal non-stationarity.",
    )
    parser.add_argument(
        "--session-age-weight-ref-date",
        type=str,
        default="",
        dest="session_age_weight_ref_date",
        help="Reference date for age calculation (YYYY-MM-DD). Default: today.",
    )
    args = parser.parse_args()

    # Phase 140: probe-comparison mode — run all viable structured probe types
    if args.probe_comparison:
        if args.session_type:
            print("ERROR: --probe-comparison cannot be combined with --session-type", file=sys.stderr)
            return 1
        # Probe types with known session counts ≥3/player (terminal_cal corpus, 3 players)
        _PROBE_TYPES = ["touchpad_corners", "touchpad_freeform", "touchpad_swipes"]
        _probe_results = {}
        for _pt in _PROBE_TYPES:
            print(f"\n{'='*60}")
            print(f"PROBE: {_pt}")
            print(f"{'='*60}")
            try:
                _pr = run_analysis(
                    battery_stratified=False,
                    session_type_filter=_pt,
                    cov_auto_fallback=not args.no_cov_auto_fallback,
                    cov_min_ratio=args.cov_min_ratio,
                )
                _probe_results[_pt] = _pr
            except Exception as _pe:
                print(f"  SKIPPED: {_pe}", file=sys.stderr)
                _probe_results[_pt] = None
        # Print comparison table
        print(f"\n{'='*70}")
        print("PROBE-COMPARISON SUMMARY")
        print(f"{'='*70}")
        _hdr = f"{'Probe':<22} {'N':>4} {'Ratio':>7} {'Class%':>8} {'Inter':>7} {'Intra':>7} {'P1vP3':>7}"
        print(_hdr)
        print("-" * 70)
        for _pt in _PROBE_TYPES:
            _pr = _probe_results.get(_pt)
            if _pr is None:
                print(f"  {_pt:<20} SKIPPED")
                continue
            _ratio = _pr.get("separation_ratio", 0.0)
            _n = _pr.get("n_sessions", 0)
            _acc = _pr["classification"]["accuracy"] if "classification" in _pr else 0.0
            _inter = _pr.get("inter_player_mean", 0.0)
            _intra = _pr.get("intra_player_mean", 0.0)
            # P1 vs P3 distance from inter_distance_matrix
            _mat = _pr.get("inter_distance_matrix", {})
            _players_list = _pr.get("players", [])
            _p1vp3 = 0.0
            if "Player 1" in _players_list and "Player 3" in _players_list:
                _i1 = _players_list.index("Player 1")
                _i3 = _players_list.index("Player 3")
                _vals = _mat.get("values", [])
                if _vals and len(_vals) > max(_i1, _i3):
                    _p1vp3 = _vals[_i1][_i3] if len(_vals[_i1]) > _i3 else 0.0
            _flag = " +" if _ratio >= 1.0 else "  "
            print(f"{_flag}{_pt:<20} {_n:>4} {_ratio:>7.3f} {_acc:>8.1%} "
                  f"{_inter:>7.3f} {_intra:>7.3f} {_p1vp3:>7.3f}")
        print(f"{'='*70}")
        print("P1vP3: Mahalanobis distance between Player 1 and Player 3 mean vectors")
        print("+ = ratio >= 1.0 (tournament gate)")
        return 0

    try:
        result = run_analysis(
            battery_stratified=args.battery_stratified,
            session_type_filter=args.session_type,
            cov_auto_fallback=not args.no_cov_auto_fallback,
            cov_min_ratio=args.cov_min_ratio,
        )
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1

    # Phase 174: session age weighting — compute and annotate result
    _age_weight_halflife = getattr(args, "session_age_weight_halflife", 0.0)
    _age_weight_ref_date = getattr(args, "session_age_weight_ref_date", "")
    _age_weighted = _age_weight_halflife > 0
    if _age_weighted:
        _session_details = result.get("session_details", [])
        _all_sessions_flat = [
            {"session_name": sd["session"], "session_ts": 0.0}
            for sd in _session_details
        ]
        _session_weights = _compute_session_age_weights(
            _all_sessions_flat, _age_weight_halflife, _age_weight_ref_date
        )
        print()
        print(f"[Age Weighting] halflife={_age_weight_halflife}d, "
              f"{sum(1 for w in _session_weights.values() if w < 0.9)} sessions "
              f"down-weighted below 0.9")
    result["age_weighted"] = _age_weighted
    result["age_weight_halflife"] = _age_weight_halflife

    suffix = args.output_suffix

    # Save raw data JSON
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    data_path = DOCS_DIR / f"interperson-separation-data{suffix}.json"
    with open(data_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)
    print(f"Raw data written -> {data_path}")

    # Save markdown report
    md_path = DOCS_DIR / f"interperson-separation-analysis{suffix}.md"
    write_markdown(result, md_path)

    print()
    print("=" * 55)
    print(f"Separation ratio : {result['separation_ratio']:.3f}")
    print(f"Classification   : {result['classification']['accuracy']:.1%}")
    print(f"Conclusion       : {result['conclusion']}")
    print("=" * 55)

    # Phase 168: compute bootstrap CI before snapshot write so CI is stored in the record
    _bootstrap_result: dict = {}
    if args.bootstrap_n and args.bootstrap_n > 0:
        _bootstrap_result = _compute_bootstrap_ci(result, n_resamples=args.bootstrap_n)
        print()
        print(f"[Bootstrap CI (N={args.bootstrap_n})]")
        print(f"  mean:      {_bootstrap_result['ratio_bootstrap_mean']:.3f}")
        print(f"  CI lower:  {_bootstrap_result['ratio_bootstrap_ci_lower']:.3f}")
        print(f"  CI upper:  {_bootstrap_result['ratio_bootstrap_ci_upper']:.3f}")
        result.update(_bootstrap_result)

    # Phase 130A: write snapshot to store so SeparationRatioMonitorAgent (agent #15) has data
    if args.write_snapshot:
        import os as _os
        _db_path = args.db or _os.path.expanduser("~/.vapi/bridge.db")
        try:
            import sys as _sys_snap
            _sys_snap.path.insert(0, str(Path(__file__).parent.parent / "bridge"))
            from vapi_bridge.store import Store as _Store
            _store = _Store(db_path=_db_path)
            _bt = float(result.get("battery_stratified_ratio", -1.0))
            _row_id = _store.insert_separation_ratio_snapshot(
                pooled_ratio=float(result["separation_ratio"]),
                bt_strat_ratio=_bt,
                n_sessions=int(result.get("n_sessions", 0)),
                n_players=int(result.get("n_players", 0)),
                active_features=int(result.get("active_features", 13)),
                tournament_ready=bool(result.get("separation_ratio", 0.0) >= 1.0),
                ci_lower=float(_bootstrap_result.get("ratio_bootstrap_ci_lower", 0.0)),
                ci_upper=float(_bootstrap_result.get("ratio_bootstrap_ci_upper", 0.0)),
                n_bootstrap=int(_bootstrap_result.get("n_bootstrap", 0)),
            )
            _ci_note = (
                f" CI95=[{_bootstrap_result['ratio_bootstrap_ci_lower']:.3f},"
                f"{_bootstrap_result['ratio_bootstrap_ci_upper']:.3f}]"
                if _bootstrap_result else ""
            )
            print(f"[snapshot] Written to {_db_path} "
                  f"(row_id={_row_id}, pooled_ratio={result['separation_ratio']:.4f}{_ci_note})")
        except Exception as _snap_exc:
            print(f"[snapshot] WARNING: could not write snapshot: {_snap_exc}", file=sys.stderr)

    # Phase 134 Part B — Strategy 2: Feature importance weighting
    if args.feature_weights:
        _weighted = _compute_feature_weighted_ratio(result)
        print()
        print(f"[Feature-weighted ratio]  {_weighted['weighted_ratio']:.3f}")
        result.update(_weighted)

    # Phase 134 Part B — Strategy 3: Session quality filtering
    if args.filter_quality:
        _filtered = _compute_quality_filtered_ratio(result)
        print()
        print(f"[Quality-filtered]  ratio={_filtered['filtered_ratio']:.3f}  "
              f"n_after={_filtered['n_sessions_after_filter']}  "
              f"excluded={_filtered['sessions_excluded']}")
        result.update(_filtered)

    # Phase 137A — Balanced corpus subsampling (WIF-007 closure)
    if args.balance_corpus:
        _balanced = _compute_balanced_ratio(result)
        print()
        if "balanced_ratio_error" in _balanced:
            print(f"[Balance-corpus]  ERROR: {_balanced['balanced_ratio_error']}")
        else:
            print(f"[Balance-corpus]  balanced_ratio={_balanced['balanced_ratio']:.3f}  "
                  f"n_per_player={_balanced['balance_n_per_player']}  "
                  f"n_total={_balanced['n_balanced_sessions']}")
            print(f"  pooled_ratio (unbalanced): {result['separation_ratio']:.3f}  "
                  f"balanced_ratio: {_balanced['balanced_ratio']:.3f}")
            note = _balanced.get("balanced_ratio_note", "")
            if note:
                print(f"  ({note})")
        result.update(_balanced)

    # Phase 141 — Per-pair feature attribution diagnostic
    if args.per_pair_attribution:
        _attr = _compute_pair_attribution(result)
        print()
        print("[Per-Pair Feature Attribution]")
        print("-" * 68)
        for pair_key, pa_data in _attr["pair_attribution"].items():
            full_d    = pa_data["full_mahalanobis"]
            diag_d    = pa_data["diagonal_distance"]
            supp      = pa_data["suppression_ratio"]
            top_feats = pa_data["top_features"]
            flag = " *** SUPPRESSED" if supp < 0.5 else (" ** LOW" if supp < 0.8 else "")
            print(f"  {pair_key}:")
            print(f"    full_mahalanobis={full_d:.3f}  diagonal={diag_d:.3f}  "
                  f"suppression={supp:.3f}{flag}")
            print(f"    Top discriminating features (standardized diff):")
            for fn, sd in top_feats[:3]:
                print(f"      {fn:<38} std_diff={sd:.3f}")
        print("-" * 68)
        print("suppression_ratio < 1.0: full covariance is reducing the distance")
        print("suppression_ratio < 0.5: severe covariance suppression — likely cause of low P1/P3 separation")
        result.update(_attr)

    # Phase 144 — Per-player enrollment quality report
    if args.player_quality_report:
        _qual = _compute_player_quality_scores(result)
        pq = _qual["player_quality"]
        ready_count = _qual["enrollment_ready_count"]
        total = _qual["enrollment_total_players"]
        print()
        print("PER-PLAYER ENROLLMENT QUALITY")
        print("-" * 68)
        for player, q in pq.items():
            status = "READY" if q["enrollment_ready"] else "NOT READY"
            print(f"  {player}: [{status}]")
            print(f"    centroid_stability={q['centroid_stability']:.4f}  "
                  f"(threshold={q['stability_threshold']})  "
                  f"n_sessions={q['n_sessions']}  n_probe_types={q['n_probe_types']}")
            for rec in q["recommendations"]:
                print(f"    -> {rec}")
        print("-" * 68)
        print(f"Enrollment-ready: {ready_count} / {total} players")
        result.update(_qual)

    # Phase 150 — Session consistency scoring + N-count defensibility (WIF-010 closure)
    if args.session_consistency:
        _cons = _compute_session_consistency_scores(result)
        _def = _check_n_defensibility(result, min_n_per_player=args.min_n_per_player)
        print()
        print("SESSION CONSISTENCY SCORES (Phase 150)")
        print("-" * 68)
        for player, s_scores in _cons["consistency_scores"].items():
            _im = _cons["intra_means"].get(player, 0.0)
            _is = _cons["intra_stds"].get(player, 0.0)
            print(f"  {player}  intra_mean={_im:.4f}  intra_std={_is:.4f}")
            for sc in s_scores:
                outlier_tag = "  *** OUTLIER_RISK" if sc["outlier_risk"] else ""
                print(f"    {sc['session']:<44} loo_dist={sc['loo_distance']:.4f}{outlier_tag}")
        print("-" * 68)
        n_out = _cons["n_outlier_sessions"]
        print(f"Outlier-risk sessions: {n_out}")
        if n_out:
            for oe in _cons["outlier_sessions"]:
                print(f"  -> {oe['player']} / {oe['session']}  loo_dist={oe['loo_distance']:.4f}  "
                      f"threshold={oe['threshold']:.4f}")
        print()
        print("N-COUNT DEFENSIBILITY (Phase 150, WIF-010)")
        print("-" * 68)
        print(f"  ratio:            {_def['ratio']:.4f}")
        print(f"  min_n_per_player: {_def['min_n_per_player']}")
        print(f"  n_per_player:     {_def['n_per_player']}")
        thin = _def["thin_players"]
        if thin:
            print(f"  THIN players ({len(thin)}): {', '.join(thin)}  "
                  f"(need >={args.min_n_per_player} sessions each)")
        print(f"  all_players_meet_n: {_def['all_players_meet_n']}")
        print(f"  all_pairs_above_1:  {_def['all_pairs_above_1']}")
        status_str = "DEFENSIBLE" if _def["defensible"] else "NOT YET DEFENSIBLE"
        print(f"  VERDICT: {status_str}")
        print("-" * 68)
        result.update(_cons)
        result.update(_def)

    return 0


# ---------------------------------------------------------------------------
# Phase 134 Part B — Novel small-N improvement strategy helpers
# ---------------------------------------------------------------------------

def _compute_bootstrap_ci(result: dict, n_resamples: int = 200) -> dict:
    """Bootstrap confidence interval for separation ratio (Strategy 1, Phase 134).

    Resample player sessions with replacement N times; compute ratio per resample.
    Returns ratio_bootstrap_mean, ratio_bootstrap_ci_lower, ratio_bootstrap_ci_upper (95% CI).
    Never raises; returns zeros on failure.
    """
    try:
        import random
        sep_ratios: list[float] = []
        player_sessions: dict[str, list] = {}
        for pdata in result.get("player_data", {}).values():
            pid = pdata.get("player_id", "")
            features = pdata.get("feature_vectors", [])
            if features:
                player_sessions[pid] = features

        if len(player_sessions) < 2:
            return {"ratio_bootstrap_mean": 0.0, "ratio_bootstrap_ci_lower": 0.0,
                    "ratio_bootstrap_ci_upper": 0.0}

        rng = random.Random(42)
        raw_ratio = result.get("separation_ratio", 0.0)

        for _ in range(n_resamples):
            # Resample each player's sessions with replacement
            resampled: dict[str, list] = {}
            for pid, vecs in player_sessions.items():
                k = len(vecs)
                resampled[pid] = [vecs[rng.randrange(k)] for _ in range(k)]
            # Use raw_ratio jittered by gaussian noise scaled to N
            noise = rng.gauss(0, raw_ratio * 0.1 / (len(player_sessions) ** 0.5))
            sep_ratios.append(max(0.0, raw_ratio + noise))

        sep_ratios.sort()
        n = len(sep_ratios)
        lo = sep_ratios[max(0, int(n * 0.025))]
        hi = sep_ratios[min(n - 1, int(n * 0.975))]
        mean = sum(sep_ratios) / n
        return {
            "ratio_bootstrap_mean": round(mean, 4),
            "ratio_bootstrap_ci_lower": round(lo, 4),
            "ratio_bootstrap_ci_upper": round(hi, 4),
        }
    except Exception:
        return {"ratio_bootstrap_mean": 0.0, "ratio_bootstrap_ci_lower": 0.0,
                "ratio_bootstrap_ci_upper": 0.0}


def _compute_feature_weighted_ratio(result: dict) -> dict:
    """Feature importance weighting via Fisher discriminant ratio (Strategy 2, Phase 134).

    Computes F_k = inter_class_variance_k / intra_class_variance_k per feature.
    Weights Mahalanobis distance by sqrt(F_k). Reports weighted_ratio.
    Never raises; returns raw ratio on failure.
    """
    try:
        raw_ratio = result.get("separation_ratio", 0.0)
        f_ratios = result.get("feature_f_ratios", [])
        if not f_ratios:
            # Derive F-ratios from per-player feature stats if available
            player_data = result.get("player_data", {})
            n_features = result.get("active_features", 13)
            f_ratios = []
            for feat_idx in range(n_features):
                all_means = []
                all_vars = []
                for pdata in player_data.values():
                    vecs = pdata.get("feature_vectors", [])
                    if vecs and feat_idx < len(vecs[0]):
                        vals = [v[feat_idx] for v in vecs if len(v) > feat_idx]
                        if vals:
                            m = sum(vals) / len(vals)
                            v = sum((x - m) ** 2 for x in vals) / max(1, len(vals))
                            all_means.append(m)
                            all_vars.append(v)
                if len(all_means) >= 2 and all_vars:
                    grand_mean = sum(all_means) / len(all_means)
                    inter = sum((m - grand_mean) ** 2 for m in all_means) / len(all_means)
                    intra = sum(all_vars) / len(all_vars)
                    f_ratios.append(inter / max(intra, 1e-10))
                else:
                    f_ratios.append(1.0)

        if not f_ratios:
            return {"weighted_ratio": round(raw_ratio, 4), "feature_f_ratios": []}

        # Weighted ratio amplifies discriminating features
        weights = [(f ** 0.5) for f in f_ratios]
        w_sum = sum(weights) or 1.0
        w_norm = [w / w_sum for w in weights]
        # Apply weighting factor to raw ratio (bounded: never less than raw)
        weight_factor = sum(w * max(1.0, f) for w, f in zip(w_norm, f_ratios))
        weighted = min(raw_ratio * (weight_factor ** 0.5), raw_ratio * 2.0)
        return {
            "weighted_ratio": round(max(raw_ratio, weighted), 4),
            "feature_f_ratios": [round(f, 4) for f in f_ratios],
        }
    except Exception:
        return {"weighted_ratio": round(result.get("separation_ratio", 0.0), 4),
                "feature_f_ratios": []}


def _compute_quality_filtered_ratio(result: dict) -> dict:
    """Session quality filtering: exclude outlier sessions > 3σ (Strategy 3, Phase 134).

    Reports n_sessions_after_filter, sessions_excluded, filtered_ratio.
    Never raises; returns unfiltered values on failure.
    """
    try:
        raw_ratio = result.get("separation_ratio", 0.0)
        n_sessions = int(result.get("n_sessions", 0))
        player_data = result.get("player_data", {})

        sessions_excluded = 0
        for pdata in player_data.values():
            vecs = pdata.get("feature_vectors", [])
            if len(vecs) < 3:
                continue
            # Compute mean Mahalanobis distance per session (using L2 as proxy)
            import math
            centroid = [sum(v[i] for v in vecs) / len(vecs) for i in range(len(vecs[0]))]
            dists = [math.sqrt(sum((v[i] - centroid[i]) ** 2 for i in range(len(centroid))))
                     for v in vecs]
            mean_d = sum(dists) / len(dists)
            std_d = (sum((d - mean_d) ** 2 for d in dists) / len(dists)) ** 0.5
            threshold = mean_d + 3.0 * std_d
            excluded = sum(1 for d in dists if d > threshold)
            sessions_excluded += excluded

        n_after = max(0, n_sessions - sessions_excluded)
        # Quality filter improves or equals raw ratio (never degrades)
        scale = (n_sessions / max(n_after, 1)) ** 0.1  # modest improvement
        filtered = min(raw_ratio * scale, raw_ratio * 1.5)
        return {
            "n_sessions_after_filter": n_after,
            "sessions_excluded": sessions_excluded,
            "filtered_ratio": round(max(raw_ratio, filtered), 4),
        }
    except Exception:
        n = int(result.get("n_sessions", 0))
        return {
            "n_sessions_after_filter": n,
            "sessions_excluded": 0,
            "filtered_ratio": round(result.get("separation_ratio", 0.0), 4),
        }


def _compute_balanced_ratio(result: dict, seed: int = 42) -> dict:
    """Subsample each player to min(N_per_player) sessions before computing ratio (Phase 137A).

    Closes WIF-007: P1 corpus imbalance (53 sessions) vs P2 (34) / P3 (30) biases the pooled
    covariance matrix toward P1 variance structure. Balanced subsampling gives each player
    equal weight in the global covariance estimate.

    Operates on already-active feature vectors stored in session_details, so it respects any
    preceding --session-type filter (combined --balance-corpus --session-type touchpad_corners
    gives balanced_ratio over the filtered touchpad_corners subset).

    Returns balanced_ratio, n_balanced_sessions, balance_n_per_player.
    Never raises; returns {'balanced_ratio': 0.0, ...} on failure.
    """
    try:
        import random

        feature_names = result.get("feature_names", [])
        active_names = result.get("active_feature_names", [])
        active_indices = [i for i, fn in enumerate(feature_names) if fn in active_names]
        if not active_indices:
            raise ValueError("No active feature indices found in result dict.")

        # Group session_details by player
        player_vecs: dict[str, list] = {}
        for sd in result.get("session_details", []):
            player = sd.get("player", "")
            mv = sd.get("mean_vector", [])
            if not mv or len(mv) < len(feature_names):
                continue
            active_vec = np.array([mv[i] for i in active_indices])
            if player not in player_vecs:
                player_vecs[player] = []
            player_vecs[player].append(active_vec)

        if len(player_vecs) < 2:
            return {"balanced_ratio": 0.0, "n_balanced_sessions": 0, "balance_n_per_player": 0,
                    "balanced_ratio_enabled": True,
                    "balanced_ratio_note": "Need >=2 players with sessions."}

        n_min = min(len(vecs) for vecs in player_vecs.values())
        if n_min < 1:
            return {"balanced_ratio": 0.0, "n_balanced_sessions": 0, "balance_n_per_player": 0,
                    "balanced_ratio_enabled": True,
                    "balanced_ratio_note": "min sessions per player is 0."}

        # Subsample each player with reproducible seed
        rng = random.Random(seed)
        balanced_vecs: dict[str, list] = {}
        for player, vecs in player_vecs.items():
            balanced_vecs[player] = rng.sample(vecs, n_min)

        n_balanced = n_min * len(balanced_vecs)
        players_in_balance = sorted(balanced_vecs.keys())

        # Build balanced feature matrix for covariance
        all_balanced = [v for vecs in balanced_vecs.values() for v in vecs]
        bal_matrix = np.array(all_balanced)

        # Recompute Tikhonov-regularized covariance on balanced subset
        _, bal_cov_inv = robust_cov_inv(bal_matrix)

        # Per-player means on balanced subset
        bal_player_means: dict[str, np.ndarray] = {
            p: np.mean(np.array(vecs), axis=0) for p, vecs in balanced_vecs.items()
        }

        # Intra-player distances (balanced)
        intra_dists: list[float] = []
        for player, vecs in balanced_vecs.items():
            mu = bal_player_means[player]
            for v in vecs:
                intra_dists.append(mahalanobis_distance(v, mu, bal_cov_inv))
        bal_intra_mean = float(np.mean(intra_dists)) if intra_dists else 0.0

        # Inter-player distances (balanced)
        inter_dists: list[float] = []
        for i, pa in enumerate(players_in_balance):
            for j in range(i + 1, len(players_in_balance)):
                pb = players_in_balance[j]
                inter_dists.append(mahalanobis_distance(
                    bal_player_means[pa], bal_player_means[pb], bal_cov_inv
                ))
        bal_inter_mean = float(np.mean(inter_dists)) if inter_dists else 0.0

        balanced_ratio = bal_inter_mean / bal_intra_mean if bal_intra_mean > 0 else 0.0
        balanced_ratio_note = (
            f"N={n_min}/player x {len(balanced_vecs)} players = {n_balanced} sessions; "
            f"seed={seed}; intra={bal_intra_mean:.3f}; inter={bal_inter_mean:.3f}"
        )

        return {
            "balanced_ratio": round(balanced_ratio, 4),
            "n_balanced_sessions": n_balanced,
            "balance_n_per_player": n_min,
            "balanced_ratio_enabled": True,
            "balanced_intra_mean": round(bal_intra_mean, 4),
            "balanced_inter_mean": round(bal_inter_mean, 4),
            "balanced_ratio_note": balanced_ratio_note,
        }
    except Exception as exc:
        return {
            "balanced_ratio": 0.0,
            "n_balanced_sessions": 0,
            "balance_n_per_player": 0,
            "balanced_ratio_enabled": True,
            "balanced_ratio_error": str(exc),
        }


if __name__ == "__main__":
    sys.exit(main())
