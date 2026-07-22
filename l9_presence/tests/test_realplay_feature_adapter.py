"""Unit tests for the real-data -> WindowFeatures adapter. Pure, synthetic HID rows, no capture I/O."""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from l9_presence.realplay_feature_adapter import (
    trigger_active_fraction, press_event_count, rhythm_is_macro_quantized, device_ts_span,
    tremor_from_accel, extract_window_features,
)

def _row(t_ms, l2=0, r2=0, lx=128, ly=128, rx=128, ry=128, **extra):
    return {"t_ms": t_ms, "l2": l2, "r2": r2, "lx": lx, "ly": ly, "rx": rx, "ry": ry, **extra}

def test_trigger_active_fraction_basic():
    rows = [_row(0, r2=0), _row(100, r2=255), _row(200, r2=255), _row(300, r2=0)]
    f = trigger_active_fraction(rows, 0, 300)
    assert abs(f - 0.5) < 1e-9   # 2 of 4 rows active

def test_trigger_active_fraction_empty_window_is_none():
    rows = [_row(0, r2=255)]
    assert trigger_active_fraction(rows, 1000, 2000) is None

def test_press_event_count_counts_onsets_not_levels():
    rows = [_row(0, r2=0), _row(50, r2=255), _row(100, r2=255), _row(150, r2=0), _row(200, r2=255)]
    n = press_event_count(rows, 0, 200)
    assert n == 2   # two rising edges

def test_press_event_count_stick_burst_counts():
    rows = [_row(0, lx=128), _row(50, lx=200), _row(100, lx=128)]
    n = press_event_count(rows, 0, 100)
    assert n >= 1

def test_rhythm_regular_press_flagged_quantized():
    rows = []
    for i in range(10):
        rows.append(_row(i * 1000, r2=0))
        rows.append(_row(i * 1000 + 10, r2=255))  # onset every exactly 1000ms
    q = rhythm_is_macro_quantized(rows, 0, 10000)
    assert q is True

def test_rhythm_irregular_press_not_quantized():
    import random
    random.seed(3)
    rows = []
    t = 0.0
    for i in range(10):
        t += random.uniform(400, 2200)
        rows.append(_row(t - 20, r2=0))
        rows.append(_row(t, r2=255))
    q = rhythm_is_macro_quantized(rows, 0, t + 100)
    assert q is False

def test_rhythm_too_few_onsets_is_none():
    rows = [_row(0, r2=255)]
    assert rhythm_is_macro_quantized(rows, 0, 100) is None

def test_device_ts_span_absent_key_returns_none():
    rows = [_row(0), _row(1000)]   # no sensor_ts_ticks key at all (run1-shape data)
    ticks, wall = device_ts_span(rows, 0, 1000)
    assert ticks is None and wall is None

def test_device_ts_span_present_computes_real_values():
    rows = [_row(0, sensor_ts_ticks=1000), _row(1000, sensor_ts_ticks=1000 + 3000 * 1000)]
    ticks, wall = device_ts_span(rows, 0, 1000)
    assert ticks == 3000 * 1000
    assert abs(wall - 1000) < 1e-6

def test_tremor_from_accel_absent_is_honestly_none():
    rows = [_row(0), _row(100)]
    hz, power = tremor_from_accel(rows, 0, 100)
    assert hz is None and power is None

def test_extract_window_features_run1_shape_fails_closed_on_ticks_and_tremor():
    """The exact run1_cfb27 scenario: rows have no accel/gyro/sensor_ts_ticks keys at all."""
    rows = [_row(i * 100, r2=(255 if i % 5 == 0 else 0)) for i in range(50)]
    f = extract_window_features(rows, 0, 5000)
    assert f.tremor_peak_hz is None
    assert f.device_ts_span_ticks is None
    assert f.gameplay_active_fraction is not None   # this one IS computable from run1-shape data

def test_extract_window_features_with_full_fixed_recorder_shape():
    """A window with sensor_ts_ticks present (the FIXED recorder's shape) at least gets past the
    device-clock gate — still None tremor since the accel-FFT stub is deliberately unimplemented."""
    rows = [_row(i * 100, r2=(255 if i % 5 == 0 else 0),
                sensor_ts_ticks=i * 100 * 3000, accel_x=0.01) for i in range(50)]
    f = extract_window_features(rows, 0, 4900)
    assert f.device_ts_span_ticks is not None
    assert f.wall_span_ms is not None


def test_f_compb_tns1_absolute_t_ns_plus_relative_t_ms_prefers_t_ms():
    """F-COMPB-TNS-1 regression: real U3 rows have absolute epoch t_ns AND runner-normalized
    relative t_ms. Preferring absolute t_ns/1e6 against relative window bounds empties every
    window (G2=None, presses=0) while tests that only supply t_ms stay green — silent false
    confidence. Prefer t_ms when present."""
    t0_ns = 1_700_000_000_000_000_000  # wall-clock epoch ns (real U3 shape)
    rows = []
    for i in range(10):
        rows.append({
            "t_ns": t0_ns + i * 100_000_000,  # absolute
            "t_ms": float(i * 100),           # relative (runner path)
            "l2": 0, "r2": 255 if i % 2 else 0,
            "lx": 128, "ly": 128, "rx": 128, "ry": 128,
        })
    f = trigger_active_fraction(rows, 0, 900)
    n = press_event_count(rows, 0, 900)
    assert f is not None and abs(f - 0.5) < 1e-9
    assert n == 5
    feat = extract_window_features(rows, 0, 900)
    assert feat.gameplay_active_fraction is not None
    assert feat.press_events == 5


# ---- tremor FFT (grok-steered A2A tremor-fft-real-data r02: segment-first, gap-void, band-limited) ----

def _sine_accel_rows(freq_hz, duration_s, sample_hz=300.0, amp=0.05, t0_ms=0.0, gap_at_s=None, gap_ms=0.0):
    """Synthetic accel rows: a sine on accel_x at `freq_hz`, sampled at `sample_hz`, with gravity on Z.
    If gap_at_s given, skip samples in [gap_at_s, gap_at_s + gap_ms/1000] to inject a real gap."""
    import math
    rows = []
    dt = 1.0 / sample_hz
    t = 0.0
    while t < duration_s:
        if gap_at_s is not None and gap_at_s <= t < gap_at_s + gap_ms / 1000.0:
            t += dt
            continue
        ax = amp * math.sin(2 * math.pi * freq_hz * t)
        rows.append({"t_ms": t0_ms + t * 1000.0, "accel_x": ax, "accel_y": 0.0, "accel_z": 1.0})
        t += dt
    return rows

def test_inter_sample_gaps_ms_basic():
    from l9_presence.realplay_feature_adapter import inter_sample_gaps_ms
    assert inter_sample_gaps_ms([]) == []
    assert inter_sample_gaps_ms([100.0]) == []
    gaps = inter_sample_gaps_ms([0.0, 10.0, 25.0])
    assert gaps == [10.0, 15.0]

def test_longest_clean_segment_splits_on_void_gap():
    from l9_presence.realplay_feature_adapter import longest_clean_segment
    rows = [{"t_ms": 0}, {"t_ms": 10}, {"t_ms": 20},       # clean run of 3, gap to next = 2000ms
            {"t_ms": 2020}, {"t_ms": 2030}, {"t_ms": 2040}, {"t_ms": 2050}]  # clean run of 4
    seg = longest_clean_segment(rows, gap_void_ms=50.0)
    assert len(seg) == 4
    assert seg[0]["t_ms"] == 2020

def test_longest_clean_segment_empty_input():
    from l9_presence.realplay_feature_adapter import longest_clean_segment
    assert longest_clean_segment([]) == []

def test_tremor_absent_accel_is_none():
    from l9_presence.realplay_feature_adapter import tremor_from_accel
    rows = [{"t_ms": 0}, {"t_ms": 100}]
    assert tremor_from_accel(rows, 0, 100) == (None, None)

def test_tremor_uniform_10hz_sine_finds_peak_in_band():
    from l9_presence.realplay_feature_adapter import tremor_from_accel
    rows = _sine_accel_rows(freq_hz=10.0, duration_s=3.0, sample_hz=300.0)
    hz, power = tremor_from_accel(rows, 0, 3000)
    assert hz is not None
    assert 8.0 <= hz <= 12.0
    assert power is not None and power > 1e-6

def test_tremor_out_of_band_signal_reports_in_band_peak_not_global():
    """A strong 3Hz signal (postural, out of the 8-12 band) must NOT make tremor_peak_hz report 3Hz
    -- the search must stay band-limited even when in-band power is comparatively weak."""
    from l9_presence.realplay_feature_adapter import tremor_from_accel
    rows = _sine_accel_rows(freq_hz=3.0, duration_s=3.0, sample_hz=300.0, amp=0.5)
    hz, power = tremor_from_accel(rows, 0, 3000)
    assert hz is not None
    assert 8.0 <= hz <= 12.0   # band-limited search always returns a value inside the band

def test_tremor_big_gap_forces_segment_not_whole_window():
    """A single 1.8s gap splits the window; only the longer clean side should be used, not an
    interpolation across the void (which would still often produce band-limited noise as a
    false positive -- the real regression this protects is USING BOTH SIDES naively)."""
    from l9_presence.realplay_feature_adapter import tremor_from_accel, longest_clean_segment
    rows = _sine_accel_rows(freq_hz=10.0, duration_s=1.0, sample_hz=300.0, amp=0.05) + \
           _sine_accel_rows(freq_hz=10.0, duration_s=2.5, sample_hz=300.0, amp=0.05, t0_ms=2800.0)
    seg = longest_clean_segment(rows, gap_void_ms=50.0)
    # the longer segment (2.5s @ 300Hz) must win, not the 1.0s one, and the gap must have split them
    assert len(seg) < len(rows)
    hz, power = tremor_from_accel(rows, 0, 5000)
    assert hz is not None and 8.0 <= hz <= 12.0

def test_tremor_segment_too_short_is_none():
    from l9_presence.realplay_feature_adapter import tremor_from_accel
    rows = _sine_accel_rows(freq_hz=10.0, duration_s=0.5, sample_hz=300.0)  # 0.5s < 2.0s floor
    hz, power = tremor_from_accel(rows, 0, 500)
    assert (hz, power) == (None, None)

def test_tremor_too_few_samples_is_none_even_if_duration_ok():
    from l9_presence.realplay_feature_adapter import tremor_from_accel
    # 2.5s duration but very sparse (20Hz -> 50 samples), below MIN_CLEAN_SEG_SAMPLES=256
    rows = _sine_accel_rows(freq_hz=10.0, duration_s=2.5, sample_hz=20.0)
    hz, power = tremor_from_accel(rows, 0, 2500)
    assert (hz, power) == (None, None)

def test_extract_window_features_tremor_now_wired_through():
    """extract_window_features must actually call the real tremor_from_accel, not a hardcoded None."""
    from l9_presence.realplay_feature_adapter import extract_window_features
    accel_rows = _sine_accel_rows(freq_hz=10.0, duration_s=3.0, sample_hz=300.0)
    r2_rows = [_row(i * 10, r2=(255 if i % 20 == 0 else 0)) for i in range(300)]
    rows = accel_rows + r2_rows
    f = extract_window_features(rows, 0, 3000)
    assert f.tremor_peak_hz is not None
    assert 8.0 <= f.tremor_peak_hz <= 12.0
