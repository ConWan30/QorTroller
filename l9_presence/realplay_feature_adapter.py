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

from l9_presence.realplay_liveness import WindowFeatures

TREMOR_BAND_HZ: tuple[float, float] = (8.0, 12.0)


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


def tremor_from_accel(rows: Sequence[dict], t_lo_ms: float, t_hi_ms: float) -> tuple[Optional[float], Optional[float]]:
    """(tremor_peak_hz, tremor_band_power) placeholder over accel magnitude in-window. Requires
    'accel_x'/'accel_y'/'accel_z' keys (absent on run1 — returns (None, None) honestly, no FFT
    fabricated from nothing). A real implementation needs a proper FFT (>=1024 samples per the
    existing tinyml_biometric_fusion.py discipline) — deferred until a capture has enough
    real accel samples to make that meaningful; this stub exists so the adapter's shape is complete
    and future work has an obvious single place to land the real computation."""
    accel_rows = [r for r in rows if "accel_x" in r]
    if not accel_rows:
        return None, None
    # Deliberately NOT implemented further here — see docstring. Real accel present but FFT
    # deferred to a follow-up once a real-IMU capture exists to validate against.
    return None, None


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

    return WindowFeatures(
        capture_nominal=capture_nominal,
        host_exclusive_usb_or_unknown=host_exclusive_usb_or_unknown,
        gameplay_active_fraction=gaf,
        menu_detected=menu_detected,
        tremor_peak_hz=tremor_hz,
        tremor_band_power=tremor_power,
        l2b_coupled_fraction=None,   # requires real IMU precursor correlation — not computed here
        press_events=presses,
        l5_macro_quantized=quantized,
        device_ts_span_ticks=ticks,
        wall_span_ms=wall_ms,
        window_s=window_s,
        optical_consistent=None,
    )
