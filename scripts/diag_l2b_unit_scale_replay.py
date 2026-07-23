"""Grok round-02 Ask 5 / Step A -- offline unit-path replay for the live L2B gyro
unit-scale finding (docs/a2a/live-l2b-unit-scale-investigation/round-02-grok-expand.md).

Zero hardware, zero bridge risk, zero production-constant edits: this script never
modifies controller/l2b_imu_press_correlation.py. Where a 0.03 threshold is needed
for the recovery pass, it patches the imported module's _IMU_SPIKE_THRESH attribute
in THIS process only (matches Ask 5 Step A point 6 -- "local copy... not by editing
the module constant").

For each hw_*.json session with >= _MIN_PRESS_EVENTS Cross presses:
  Pass 1 (raw)      -- session gyro as stored (raw int16 LSB) -> coupled_fraction_raw
  Pass 2 (live-sim) -- same snaps with gyro_* /= 1000.0 (matches the live
                       DualSenseReader convention) -> coupled_fraction_live_sim
  Pass 3 (recovery) -- live-sim snaps + _IMU_SPIKE_THRESH patched to 0.03
                       (= 30.0 / 1000.0) -> coupled_fraction_recovered

Expected pattern if the unit-scale hypothesis is correct: raw high (>= ~0.55),
live-sim collapsed toward 0, recovery back near raw.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "controller"))

import l2b_imu_press_correlation as l2b  # noqa: E402
from l2b_imu_press_correlation import ImuPressCorrelationOracle  # noqa: E402

SESSION_DIR = REPO_ROOT / "sessions" / "human"
RAW_THRESH = 30.0
LIVE_THRESH = RAW_THRESH / 1000.0  # 0.03 -- what the constant SHOULD be under live scale


def _load_session_snaps(filename: str, gyro_scale: float = 1.0, max_reports: int = 5000):
    """Same remap as bridge/tests/test_l2b_imu_press_correlation.py::_load_session_snaps,
    with an added gyro_scale multiplier so raw vs live-sim can share one loader."""
    path = SESSION_DIR / filename
    if not path.exists():
        return None
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    snaps = []
    for r in data["reports"][:max_reports]:
        f = r["features"]
        snap = type("_S", (), {
            "timestamp_ms": float(r["timestamp_ms"]),
            "gyro_x":       float(f.get("gyro_x", 0.0)) * gyro_scale,
            "gyro_y":       float(f.get("gyro_y", 0.0)) * gyro_scale,
            "gyro_z":       float(f.get("gyro_z", 0.0)) * gyro_scale,
            "r2_trigger":   int(f.get("r2_trigger", 0)),
            "buttons":      (int(f.get("buttons_0", 0)) >> 5) & 1,  # Cross: buttons_0 bit5 -> bit0
        })()
        snaps.append(snap)
    return snaps


def _run_oracle(snaps, thresh: float) -> dict:
    """2026-07-22: takes an EXPLICIT threshold rather than relying on whatever
    the module's current default happens to be. l2b._IMU_SPIKE_THRESH's own
    default flipped from 30.0 (raw-LSB) to 0.03 (live-scaled) once this
    investigation's fix shipped -- this script's three-pass narrative (raw vs
    raw-calibrated / live-scaled vs raw-calibrated / live-scaled vs
    live-calibrated) only makes sense if each pass pins its OWN threshold,
    independent of the module default at the time it happens to be run."""
    original_thresh = l2b._IMU_SPIKE_THRESH
    l2b._IMU_SPIKE_THRESH = thresh
    try:
        oracle = ImuPressCorrelationOracle()
        for s in snaps:
            oracle.push_snapshot(s)
        feats = oracle.extract_features()
        result = oracle.classify()
        n_press_events = len(oracle._press_events)
    finally:
        l2b._IMU_SPIKE_THRESH = original_thresh
    if feats is None:
        return {"n_press_events": n_press_events, "coupled_fraction": None,
                "anomaly": None, "fires_0x31": None,
                "reason": f"< _MIN_PRESS_EVENTS ({l2b._MIN_PRESS_EVENTS})"}
    return {
        "n_press_events": n_press_events,
        "coupled_fraction": round(feats.coupled_fraction, 4),
        "anomaly": feats.anomaly,
        "fires_0x31": result is not None,
        "humanity_score": round(oracle.humanity_score(), 4),
    }


def replay_session(filename: str) -> dict:
    raw_snaps = _load_session_snaps(filename, gyro_scale=1.0)
    if raw_snaps is None:
        return {"session": filename, "skipped": "file not found"}
    live_snaps = _load_session_snaps(filename, gyro_scale=1.0 / 1000.0)

    # Pass 1: raw-scale data against the raw-LSB-calibrated threshold (should recover).
    pass1_raw = _run_oracle(raw_snaps, RAW_THRESH)

    # Pass 2: live-scaled data against the raw-LSB-calibrated threshold -- reproduces
    # the ORIGINAL bug this investigation found (should fail), regardless of what the
    # module's current default is.
    pass2_live_sim = _run_oracle(live_snaps, RAW_THRESH)

    # Pass 3: live-scaled data against the live-calibrated threshold (should recover) --
    # this is what shipped as the module default; pinned explicitly here too so this
    # script stays self-contained and correct independent of the module's default.
    pass3_recovery = _run_oracle(live_snaps, LIVE_THRESH)

    return {
        "session": filename,
        "pass1_raw_asstored": pass1_raw,
        "pass2_live_sim_div1000": pass2_live_sim,
        "pass3_recovery_thresh_0_03": pass3_recovery,
    }


def main() -> None:
    # Full corpus scan, not a hand-picked subset: most hw_*.json sessions are
    # stick/tremor/touchpad calibration captures with zero Cross/R2 presses (the
    # oracle's precursor-detection logic needs >= _MIN_PRESS_EVENTS button presses
    # to produce a verdict at all), so which files actually qualify isn't knowable
    # without scanning all of them. This is I/O-bound (several session files are
    # 80-110MB) and takes a couple of minutes -- run in background if invoking live.
    sessions = sorted(p.name for p in SESSION_DIR.glob("hw_*.json"))
    results = []
    for fname in sessions:
        r = replay_session(fname)
        if r.get("skipped"):
            continue
        # Only report sessions that reach the _MIN_PRESS_EVENTS floor in at least one pass
        p1 = r["pass1_raw_asstored"]
        if p1.get("n_press_events", 0) < l2b._MIN_PRESS_EVENTS:
            continue
        results.append(r)

    print(json.dumps({
        "raw_thresh": RAW_THRESH,
        "live_thresh_recovery": LIVE_THRESH,
        "min_press_events": l2b._MIN_PRESS_EVENTS,
        "coupled_fraction_anomaly_floor": l2b._COUPLED_FRACTION,
        "n_sessions_with_enough_presses": len(results),
        "sessions": results,
    }, indent=2))

    # Honest pattern check (print-only, does not fail the script) -- confirms/refutes
    # the round-02 hypothesis without silently asserting past a surprising result.
    print("\n--- pattern check ---")
    for r in results:
        raw = r["pass1_raw_asstored"]
        live = r["pass2_live_sim_div1000"]
        rec = r["pass3_recovery_thresh_0_03"]
        raw_cf = raw.get("coupled_fraction")
        live_cf = live.get("coupled_fraction")
        rec_cf = rec.get("coupled_fraction")
        verdict = "MATCHES round-02 hypothesis" if (
            raw_cf is not None and live_cf is not None and raw_cf >= 0.30 and live_cf <= 0.10
        ) else "DOES NOT clearly match (see raw values)"
        print(f"{r['session']}: raw={raw_cf} live_sim={live_cf} recovered={rec_cf} -> {verdict}")


if __name__ == "__main__":
    main()
