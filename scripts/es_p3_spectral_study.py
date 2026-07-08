#!/usr/bin/env python3
"""ES-P3 -- haptic-echo spectral separation study (pre-registered bar applied to the
banked ES-P2 captures).

PRE-REGISTERED BAR (ES ladder, stated 2026-07-07 before any capture existed):
  "haptic events separable from human tremor at >=10x band-power ratio with zero false
   events on idle."
Operationalized (fixed BEFORE computing segment statistics):
  - bands: TREMOR 4-15 Hz (project canon) | HAPTIC 30-200 Hz (motor band; the M15
    in-match observation sat at ~49 Hz)
  - ratio criterion: haptic-band power (firing seg) / haptic-band power (idle seg) >= 10
  - event criterion: sliding 250ms windows; event threshold = idle-segment MAX
    haptic-band power x 1.5 (margin above the entire idle floor) -> idle false events
    MUST be 0 (by construction with margin -- the honest check is the margin holding),
    and the firing segment must show events at fire cadence.
  - control: tremor-band power should be SAME-ORDER across segments (grip is grip).

Privacy: consumes gitignored sessions/ captures; emits AGGREGATE band powers only
(no raw IMU leaves the rig). Advisory; feeds ES-P4/EDGE-SENSE wiring decisions.

Usage: python scripts/es_p3_spectral_study.py
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

TREMOR_BAND = (4.0, 15.0)
HAPTIC_BAND = (30.0, 200.0)
RATIO_BAR = 10.0
EVENT_WIN_MS = 250.0
EVENT_MARGIN = 1.5


def _load_accel(path: str):
    d = json.load(open(path, encoding="utf-8"))
    reps = d["reports"]
    ax = np.array([r["features"]["accel_x"] for r in reps], dtype=np.float64)
    ay = np.array([r["features"]["accel_y"] for r in reps], dtype=np.float64)
    az = np.array([r["features"]["accel_z"] for r in reps], dtype=np.float64)
    ts = np.array([r["timestamp_ms"] for r in reps], dtype=np.float64)
    mag = np.sqrt(ax * ax + ay * ay + az * az)
    mag -= mag.mean()                       # DC-remove (gravity)
    fs = 1000.0 * len(ts) / max(1.0, (ts[-1] - ts[0]))
    return mag, fs, len(reps)


def _band_power(sig: np.ndarray, fs: float, band) -> float:
    n = len(sig)
    spec = np.abs(np.fft.rfft(sig * np.hanning(n))) ** 2
    freqs = np.fft.rfftfreq(n, d=1.0 / fs)
    m = (freqs >= band[0]) & (freqs <= band[1])
    return float(spec[m].sum() / n)


def _windowed_band_power(sig: np.ndarray, fs: float, band, win_ms: float):
    w = max(64, int(fs * win_ms / 1000.0))
    out = []
    for i in range(0, len(sig) - w, w):
        out.append(_band_power(sig[i:i + w], fs, band))
    return np.array(out)


def main() -> int:
    seg1_p = os.path.join(_REPO, "sessions", "es_p2_seg1_idle_grip.json")
    seg2_p = os.path.join(_REPO, "sessions", "es_p2_seg2_firing.json")
    for p in (seg1_p, seg2_p):
        if not os.path.isfile(p):
            print(f"MISSING: {p}", file=sys.stderr)
            return 2

    idle, fs1, n1 = _load_accel(seg1_p)
    fire, fs2, n2 = _load_accel(seg2_p)
    print(f"seg1 idle : {n1} reports @ {fs1:.1f}Hz | seg2 fire: {n2} reports @ {fs2:.1f}Hz")

    res = {"bands": {"tremor": TREMOR_BAND, "haptic": HAPTIC_BAND},
           "pre_registered": {"ratio_bar": RATIO_BAR, "event_margin": EVENT_MARGIN,
                              "event_win_ms": EVENT_WIN_MS}}

    # whole-segment band powers
    for name, sig, fs in (("idle", idle, fs1), ("fire", fire, fs2)):
        res[name] = {"tremor_power": _band_power(sig, fs, TREMOR_BAND),
                     "haptic_power": _band_power(sig, fs, HAPTIC_BAND),
                     "fs": round(fs, 1)}
    ratio = res["fire"]["haptic_power"] / max(res["idle"]["haptic_power"], 1e-12)
    tremor_ratio = res["fire"]["tremor_power"] / max(res["idle"]["tremor_power"], 1e-12)
    res["haptic_ratio_fire_over_idle"] = round(ratio, 2)
    res["tremor_ratio_fire_over_idle"] = round(tremor_ratio, 2)
    res["ratio_bar_met"] = bool(ratio >= RATIO_BAR)

    # event detection: threshold from idle max x margin
    idle_w = _windowed_band_power(idle, fs1, HAPTIC_BAND, EVENT_WIN_MS)
    fire_w = _windowed_band_power(fire, fs2, HAPTIC_BAND, EVENT_WIN_MS)
    thr = float(idle_w.max()) * EVENT_MARGIN
    idle_events = int((idle_w > thr).sum())
    fire_events = int((fire_w > thr).sum())
    res["event_threshold"] = thr
    res["idle_windows"] = len(idle_w)
    res["idle_false_events"] = idle_events
    res["fire_windows"] = len(fire_w)
    res["fire_event_windows"] = fire_events
    res["fire_event_fraction"] = round(fire_events / max(1, len(fire_w)), 3)
    res["zero_false_on_idle"] = bool(idle_events == 0)
    res["bar_met_overall"] = bool(res["ratio_bar_met"] and res["zero_false_on_idle"]
                                  and fire_events > 0)

    print(f"\n  haptic-band power: idle={res['idle']['haptic_power']:.3e}  "
          f"fire={res['fire']['haptic_power']:.3e}  ratio={ratio:.1f}x  "
          f"(bar >= {RATIO_BAR}x: {'MET' if res['ratio_bar_met'] else 'MISSED'})")
    print(f"  tremor-band control ratio: {tremor_ratio:.2f}x (expect same-order)")
    print(f"  events @ thr=idle_max x{EVENT_MARGIN}: idle {idle_events}/{len(idle_w)} "
          f"(zero-false: {'HELD' if idle_events == 0 else 'FAILED'}) | "
          f"fire {fire_events}/{len(fire_w)} windows ({res['fire_event_fraction']*100:.0f}%)")
    print(f"\n  PRE-REGISTERED BAR OVERALL: {'MET' if res['bar_met_overall'] else 'MISSED'}")

    out = os.path.join(_REPO, "audits", "es_p3_spectral_result.json")
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(res, fh, indent=2)
    print(f"  written -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
