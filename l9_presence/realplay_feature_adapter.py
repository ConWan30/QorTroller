"""Real-data adapter: raw U3 capture HID rows -> realplay_liveness.WindowFeatures.

First time the committed `l9_presence/realplay_liveness.py` Composite-B evaluator is run against
anything but synthetic features (off-rig work, 2026-07-22). Pure extraction core
(`extract_window_features`) over a plain list of HID-row dicts + a window — no file I/O, no cv2 —
so it's unit-testable without a capture on disk. The runner (scripts/realplay_liveness_eval.py)
does the file reading and frame-derived fields (gameplay fraction via press activity; menu/capture
gates approximated — see runner docstring for exact caveats).

HONEST GAP THIS SURFACED (do not paper over): the run1_cfb27 capture predates the IMU/device-clock
fix in scripts/u3_raw_capture.py — its hid_events.jsonl rows have NO gyro/accel/sensor_ts_ticks
keys. So on run1: G3 (tremor) is unavailable (no accel), G4 (causal binding) is unavailable (no
gyro precursor to correlate), and the anti-replay rail layer-1 (device clock) is unavailable. The
extractor here does not fabricate these — missing keys map to None/0, which the evaluator's
existing fail-closed design (already committed, already tested) correctly turns into
UNVERIFIABLE. This is real, useful confirmation the fail-closed contract holds when fed a genuinely
incomplete real capture — it does not mean the evaluator is validated end-to-end (that needs a
capture from the FIXED recorder with real IMU data).
"""
from __future__ import annotations

from typing import Optional, Sequence

import numpy as np

from l9_presence.realplay_liveness import WindowFeatures

TREMOR_BAND_HZ: tuple[float, float] = (8.0, 12.0)

# Tremor FFT constants (A2A tremor-fft-real-data r02, grok-steered, CANDIDATE not FROZEN).
# Change-dedup capture (scripts/u3_raw_capture.py) is NOT continuous ~1kHz polling like the tested
# tinyml_biometric_fusion.py path assumes -- it has heavy-tailed gaps (run3_cfb27 measured: median
# gap 3.0ms, mean 8.8ms, p90 16.9ms, MAX 1824ms in one window). A naive fs=1/median(dt) + whole-window
# rfft would interpolate across multi-cycle silent gaps and fabricate spectral content. The fix is
# segment-first: split on any gap > GAP_VOID_MS, resample only the LONGEST contiguous clean segment,
# and refuse (None, None) if no segment clears the floor -- never invent a peak from a window that
# doesn't have one.
GAP_VOID_MS: float = 50.0          # never interpolate across a gap longer than this (~0.5x the
                                    # 10Hz tremor period of 100ms; derivation in grok r02 doc)
MIN_CLEAN_SEG_MS: float = 2000.0   # need >=2.0s of clean data (~16-24 cycles at 8-12Hz)
MIN_CLEAN_SEG_SAMPLES: int = 256   # raw samples in that segment (fail-closed floor)
RESAMPLE_HZ: float = 200.0         # uniform grid after segment accept (Nyquist 100Hz >> 12Hz)
TREMOR_SEARCH_HZ: tuple[float, float] = (8.0, 12.0)  # G3-facing peak MUST be band-limited to this
                                    # (grok r02: unconstrained global argmax finds low-freq postural
                                    # energy, not the 8-12Hz physiological band G3 actually gates on)
FFT_MIN_NFFT: int = 1024           # zero-pad floor, matches tinyml's tested FFT resolution

# G4 causal-binding constants — reused directly from the TESTED controller/l2b_imu_press_correlation.py
# (Layer 2B). Unlike tremor, this is a timestamp-windowed lookback check, not a frequency-domain
# method, so it does NOT need the segment/gap-void redesign: grounded empirically on run3 (median 14.5
# gyro samples in the 75ms lookback window per real press, 0/58 presses with zero samples) -- the
# change-dedup logging is dense exactly where it matters, because a real press moves stick/trigger/
# accel/gyro together, which is precisely what triggers a new dedup row.
L2B_PRECURSOR_WINDOW_MS: float = 80.0   # look-back window for IMU spike before button rising edge
L2B_PRECURSOR_MIN_MS: float = 5.0       # exclude same-frame coincidences
# controller/l2b_imu_press_correlation.py's _IMU_SPIKE_THRESH=30.0 is calibrated for RAW gyro
# LSB units (hw_* session corpus + L2B unit tests use raw int16; docstring: baseline ~20-40 LSB,
# micro-impulse 50-200 LSB). scripts/u3_raw_capture.py::parse_imu() applies GYRO_SCALE_DIVISOR
# (/1000.0) to match controller/dualshock_emulator.py — so THIS adapter's threshold must be the
# same raw constant divided by the same scale, or it can NEVER fire (empirically: run3 gyro_mag
# max ~18.5 in scaled units; raw thresh 30 is unreachable → false coupled_fraction=0.0).
# Single source of truth for the scale factor + raw thresh (prevents magic 30.0/1000.0 drift):
L2B_RAW_IMU_SPIKE_THRESH: float = 30.0   # mirrors controller/l2b _IMU_SPIKE_THRESH default
GYRO_SCALE_DIVISOR: float = 1000.0       # mirrors parse_imu / dualshock_emulator gyro scale
L2B_IMU_SPIKE_THRESH: float = L2B_RAW_IMU_SPIKE_THRESH / GYRO_SCALE_DIVISOR  # = 0.03 scaled
L2B_COUPLED_FRACTION_THR: float = 0.55  # matches controller/l2b_imu_press_correlation.py default
L2B_BASELINE_WINDOW_N: int = 200        # rolling median baseline window (samples, not ms — matches
                                        # the tested module's sample-count-based ring, not time-based)


def _stick_mag(row: dict, center: int = 128) -> int:
    return max(abs(row.get("lx", center) - center), abs(row.get("ly", center) - center),
              abs(row.get("rx", center) - center), abs(row.get("ry", center) - center))


def _row_t_ms(row: dict) -> float:
    """Window time base for HID rows.

    Prefer relative ``t_ms`` when present (scripts/realplay_liveness_eval.py normalizes capture
    start to 0). NEVER compare absolute wall-clock ``t_ns`` (epoch nanoseconds) to relative
    window bounds — that empties every window and silently zeros G2/press counts (F-COMPB-TNS-1).
    Absolute ``t_ns`` alone is only usable when it is already a small relative-origin value (tests
    that omit t_ms); real U3 rows always carry absolute t_ns and must also carry relative t_ms.
    """
    if "t_ms" in row:
        return float(row["t_ms"])
    if "t_ns" in row:
        return float(row["t_ns"]) / 1e6
    return -1e18


def trigger_active_fraction(rows: Sequence[dict], t_lo_ms: float, t_hi_ms: float,
                            trigger_thr: int = 20) -> Optional[float]:
    """G2 fractional gate (F17 discipline — fraction over window, never a binary any-press).
    Fraction of samples IN the window with l2 or r2 above threshold. None if the window has no rows
    at all (unknown, not zero — the evaluator must not invent credit from an empty window)."""
    in_window = [r for r in rows if t_lo_ms <= _row_t_ms(r) <= t_hi_ms]
    if not in_window:
        return None
    active = sum(1 for r in in_window if r.get("l2", 0) >= trigger_thr or r.get("r2", 0) >= trigger_thr)
    return active / len(in_window)


def press_event_count(rows: Sequence[dict], t_lo_ms: float, t_hi_ms: float,
                      trigger_thr: int = 20, stick_thr: int = 40) -> int:
    """Count of onset transitions (L2/R2 rising edge or stick burst) inside the window — feeds the
    G4 press-gate (L2B needs >=15 press events to even attempt causal binding); this only counts
    them, it does NOT compute coupling (that needs real IMU, absent on run1)."""
    ordered = sorted(rows, key=_row_t_ms)
    in_window = [r for r in ordered if t_lo_ms <= _row_t_ms(r) <= t_hi_ms]
    if len(in_window) < 2:
        return 0
    count = 0
    prev = in_window[0]
    for cur in in_window[1:]:
        onset = (prev.get("l2", 0) < trigger_thr <= cur.get("l2", 0)
                 or prev.get("r2", 0) < trigger_thr <= cur.get("r2", 0)
                 or (_stick_mag(prev) < stick_thr <= _stick_mag(cur)))
        if onset:
            count += 1
        prev = cur
    return count


def rhythm_is_macro_quantized(rows: Sequence[dict], t_lo_ms: float, t_hi_ms: float,
                              trigger_thr: int = 20, cv_floor: float = 0.15) -> Optional[bool]:
    """CANDIDATE proxy for G5 (L5 rhythm oracle is the real primitive; this is a coarse stand-in
    usable without IMU): coefficient-of-variation of inter-press-onset gaps. A human's press
    cadence has natural jitter (CV typically well above a fixed floor); a perfectly periodic macro
    has near-zero CV. Returns None if too few onsets to judge (< 3 gaps)."""
    ordered = sorted(rows, key=_row_t_ms)
    in_window = [r for r in ordered if t_lo_ms <= _row_t_ms(r) <= t_hi_ms]
    onsets: list[float] = []
    prev = None
    for r in in_window:
        active = r.get("l2", 0) >= trigger_thr or r.get("r2", 0) >= trigger_thr
        if active and prev is not None and not prev:
            onsets.append(_row_t_ms(r))
        prev = active
    if len(onsets) < 4:
        return None
    gaps = [onsets[i + 1] - onsets[i] for i in range(len(onsets) - 1)]
    mean = sum(gaps) / len(gaps)
    if mean <= 0:
        return None
    var = sum((g - mean) ** 2 for g in gaps) / len(gaps)
    cv = (var ** 0.5) / mean
    return cv < cv_floor  # True = suspiciously regular = "macro-quantized"


def device_ts_span(rows: Sequence[dict], t_lo_ms: float, t_hi_ms: float) -> tuple[Optional[int], Optional[float]]:
    """(span_ticks, wall_span_ms) from sensor_ts_ticks if present in the rows; (None, None) if the
    capture predates the IMU/clock fix (old-format rows have no 'sensor_ts_ticks' key at all —
    distinct from a genuinely-zero tick count, though the evaluator treats both as UNVERIFIABLE)."""
    ordered = sorted(rows, key=_row_t_ms)
    in_window = [r for r in ordered if t_lo_ms <= _row_t_ms(r) <= t_hi_ms and "sensor_ts_ticks" in r]
    if len(in_window) < 2:
        return None, None
    ticks = [r["sensor_ts_ticks"] for r in in_window]
    span_ticks = ticks[-1] - ticks[0]
    wall_span_ms = _row_t_ms(in_window[-1]) - _row_t_ms(in_window[0])
    if span_ticks <= 0 or wall_span_ms <= 0:
        return None, None
    return span_ticks, wall_span_ms


def inter_sample_gaps_ms(sorted_ts_ms: Sequence[float]) -> list[float]:
    """PURE: consecutive gaps (ms) in an already-time-sorted sequence. Empty/single -> []."""
    ts = list(sorted_ts_ms)
    if len(ts) < 2:
        return []
    return [ts[i + 1] - ts[i] for i in range(len(ts) - 1)]


def longest_clean_segment(
    rows: Sequence[dict], gap_void_ms: float = GAP_VOID_MS,
) -> list[dict]:
    """PURE: split `rows` (must already be time-sorted, each needs a time via _row_t_ms) on any
    inter-sample gap > gap_void_ms, and return the LONGEST contiguous run. This is the anti-
    fabrication rail (grok r02 A2A tremor-fft-real-data): never interpolate across a hole big
    enough to swallow multiple tremor cycles. Empty input -> [].

    "Longest" is by DURATION (ms), not sample count (grok r04 open-question #2 — matches the
    ">=2.0s clean data" floor's own semantics; a short but densely-sampled run should not beat a
    longer sparser one when both clear the floor, since the floor is a time-coverage requirement)."""
    if not rows:
        return []
    segments: list[list[dict]] = [[rows[0]]]
    for prev, cur in zip(rows, rows[1:]):
        gap = _row_t_ms(cur) - _row_t_ms(prev)
        if gap > gap_void_ms:
            segments.append([cur])
        else:
            segments[-1].append(cur)
    def _seg_duration_ms(seg: list[dict]) -> float:
        return _row_t_ms(seg[-1]) - _row_t_ms(seg[0]) if len(seg) > 1 else 0.0
    return max(segments, key=_seg_duration_ms)


def tremor_from_accel(
    rows: Sequence[dict], t_lo_ms: float, t_hi_ms: float,
    *,
    gap_void_ms: float = GAP_VOID_MS,
    min_clean_seg_ms: float = MIN_CLEAN_SEG_MS,
    min_clean_seg_samples: int = MIN_CLEAN_SEG_SAMPLES,
    resample_hz: float = RESAMPLE_HZ,
    search_hz: tuple[float, float] = TREMOR_SEARCH_HZ,
) -> tuple[Optional[float], Optional[float]]:
    """(tremor_peak_hz, tremor_band_power) from real accel data (grok-steered A2A
    tremor-fft-real-data r02 design; segment-first, NOT the naive whole-window FFT that
    controller/tinyml_biometric_fusion.py's continuous-poll assumption would require).

    Change-dedup capture data is NOT uniformly sampled -- it has heavy-tailed gaps (measured on a
    real capture: p90 gap 17ms but max gap 1824ms in one window). Procedure, honest at every step:
      1. Filter to accel rows in [t_lo_ms, t_hi_ms], sorted by time.
      2. Split on any gap > gap_void_ms; take the LONGEST clean segment only (never interpolate
         across a void -- that would fabricate spectral content in a hole the device never measured).
      3. If that segment doesn't clear min_clean_seg_ms AND min_clean_seg_samples -> (None, None).
         This is the fail-closed floor: a thin clean run isn't enough evidence, full stop.
      4. Compute accel magnitude ||a|| over the segment, resample onto a uniform `resample_hz` grid
         (linear interpolation -- valid now because gaps inside the segment are all <= gap_void_ms),
         DC-remove, zero-pad to >= FFT_MIN_NFFT, rfft.
      5. Peak + band power are BAND-LIMITED to `search_hz` (default 8-12Hz, matching G3's own gate)
         -- an unconstrained global argmax finds low-frequency postural/gravity-residual energy, not
         the physiological tremor band, and would make G3 fail even when real 8-12Hz content exists.
    """
    # grok r04 finding: filtering on "accel_x" alone risks KeyError if a row somehow has accel_x
    # but not accel_y/accel_z (run3 is 100% full-triple, but this must not crash on malformed data).
    accel_rows = [r for r in rows
                 if "accel_x" in r and "accel_y" in r and "accel_z" in r
                 and t_lo_ms <= _row_t_ms(r) <= t_hi_ms]
    if not accel_rows:
        return None, None
    accel_rows.sort(key=_row_t_ms)

    seg = longest_clean_segment(accel_rows, gap_void_ms)
    if not seg:
        return None, None
    seg_ms = _row_t_ms(seg[-1]) - _row_t_ms(seg[0])
    if seg_ms < min_clean_seg_ms or len(seg) < min_clean_seg_samples:
        return None, None

    t = np.array([_row_t_ms(r) / 1000.0 for r in seg], dtype=np.float64)   # seconds
    mag = np.array([
        (r["accel_x"] ** 2 + r["accel_y"] ** 2 + r["accel_z"] ** 2) ** 0.5 for r in seg
    ], dtype=np.float64)

    grid_dt = 1.0 / resample_hz
    grid = np.arange(t[0], t[-1], grid_dt)
    if len(grid) < 128:
        return None, None
    resampled = np.interp(grid, t, mag)

    dc = resampled - float(np.mean(resampled))
    nfft = max(FFT_MIN_NFFT, len(dc))
    fft_mag = np.abs(np.fft.rfft(dc, n=nfft))
    freqs = np.fft.rfftfreq(nfft, d=grid_dt)
    total_power = float(np.sum(fft_mag ** 2)) or 1e-9

    lo, hi = search_hz
    band_mask = (freqs >= lo) & (freqs <= hi)
    if not band_mask.any():
        return None, None
    band_indices = np.where(band_mask)[0]
    peak_in_band = int(np.argmax(fft_mag[band_mask]))
    peak_idx = int(band_indices[peak_in_band])
    tremor_peak_hz = float(freqs[peak_idx])
    tremor_band_power = float(np.sum(fft_mag[band_mask] ** 2) / total_power)
    return tremor_peak_hz, tremor_band_power


def l2b_coupled_fraction(
    rows: Sequence[dict], t_lo_ms: float, t_hi_ms: float,
    *,
    precursor_window_ms: float = L2B_PRECURSOR_WINDOW_MS,
    precursor_min_ms: float = L2B_PRECURSOR_MIN_MS,
    spike_thresh: float = L2B_IMU_SPIKE_THRESH,
    min_press_events: int = 15,
    baseline_window_n: int = L2B_BASELINE_WINDOW_N,
    trigger_thr: int = 20,
) -> Optional[float]:
    """G4 causal binding (real, not stubbed). Direct reuse of the TESTED methodology in
    controller/l2b_imu_press_correlation.py::_record_press -- a physical button press causes a
    wrist/hand micro-impulse the IMU records 5-80ms BEFORE the digital edge closes; software
    injection has zero precursor. For each R2 press (rising edge) in-window, look back
    [precursor_window_ms, precursor_min_ms] before it for a gyro_mag sample exceeding an adaptive
    threshold (median of prior gyro_mag + spike_thresh). coupled_fraction = fraction of presses
    with a precursor found. None if fewer than min_press_events presses, or no gyro data at all
    (honest unavailable, same discipline as tremor_from_accel -- never fabricate a fraction from
    nothing).

    Adaptation note (differs from the live continuous-ring module): baseline is computed from the
    most recent `baseline_window_n` gyro samples strictly BEFORE each press, not a fixed-duration
    time window -- the reference module's ring is sample-count-based (maxlen=200 @ ~1kHz assumed
    continuous poll), which is the same primitive this reuses, just without assuming a specific
    sample rate (this capture is change-dedup, not continuous)."""
    imu_rows = [r for r in rows
               if "gyro_x" in r and "gyro_y" in r and "gyro_z" in r
               and t_lo_ms <= _row_t_ms(r) <= t_hi_ms]
    if not imu_rows:
        return None
    imu_rows.sort(key=_row_t_ms)
    imu_history = [
        (_row_t_ms(r), (r["gyro_x"] ** 2 + r["gyro_y"] ** 2 + r["gyro_z"] ** 2) ** 0.5)
        for r in imu_rows
    ]

    press_rows = sorted(
        (r for r in rows if t_lo_ms <= _row_t_ms(r) <= t_hi_ms), key=_row_t_ms,
    )
    presses: list[float] = []
    above = False
    for r in press_rows:
        r2 = r.get("r2", 0)
        if not above and r2 >= trigger_thr * 3.2:   # ~64/255 rising, matches L2B _R2_PRESS_THRESH
            above = True
            presses.append(_row_t_ms(r))
        elif above and r2 < trigger_thr * 1.5:       # ~30/255 falling (hysteresis release)
            above = False
    if len(presses) < min_press_events:
        return None

    coupled = 0
    for pt in presses:
        lo_t, hi_t = pt - precursor_window_ms, pt - precursor_min_ms
        prior = [mag for t, mag in imu_history if t < pt - precursor_min_ms]
        baseline = float(np.median(prior[-baseline_window_n:])) if prior else 0.0
        thresh = baseline + spike_thresh
        has_precursor = any(lo_t <= t <= hi_t and mag > thresh for t, mag in imu_history)
        if has_precursor:
            coupled += 1
    return coupled / len(presses)


def extract_window_features(
    rows: Sequence[dict],
    window_start_ms: float,
    window_end_ms: float,
    *,
    capture_nominal: bool = True,
    host_exclusive_usb_or_unknown: bool = True,
    menu_detected: bool = False,
) -> WindowFeatures:
    """PURE core: HID rows (dicts with t_ns or t_ms, l2, r2, lx, ly, rx, ry, optionally
    accel_x/y/z, gyro_x/y/z, sensor_ts_ticks) + a window -> WindowFeatures.

    capture_nominal / host_exclusive_usb_or_unknown / menu_detected are injected (G1/G2 pre-gates
    this adapter cannot derive from HID alone without the live PCC/GAD machinery) — the runner
    supplies its best real approximation and documents it; this function does not guess."""
    window_s = (window_end_ms - window_start_ms) / 1000.0
    gaf = trigger_active_fraction(rows, window_start_ms, window_end_ms)
    presses = press_event_count(rows, window_start_ms, window_end_ms)
    quantized = rhythm_is_macro_quantized(rows, window_start_ms, window_end_ms)
    ticks, wall_ms = device_ts_span(rows, window_start_ms, window_end_ms)
    tremor_hz, tremor_power = tremor_from_accel(rows, window_start_ms, window_end_ms)
    l2b_coupled = l2b_coupled_fraction(rows, window_start_ms, window_end_ms)

    return WindowFeatures(
        capture_nominal=capture_nominal,
        host_exclusive_usb_or_unknown=host_exclusive_usb_or_unknown,
        gameplay_active_fraction=gaf,
        menu_detected=menu_detected,
        tremor_peak_hz=tremor_hz,
        tremor_band_power=tremor_power,
        l2b_coupled_fraction=l2b_coupled,   # real (grok-pending): reuses controller/l2b_imu_press_correlation.py methodology
        press_events=presses,
        l5_macro_quantized=quantized,
        device_ts_span_ticks=ticks,
        wall_span_ms=wall_ms,
        window_s=window_s,
        optical_consistent=None,
    )
