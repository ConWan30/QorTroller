"""QorTroller PoEP P4a — adaptive-trigger force-challenge (device-auth strengthening).

P2/P3 device-auth was weak: the force-response was incidental (players flicked the stick,
not pressed R2). P4a adds a DELIBERATE force-challenge — set the adaptive trigger to a known
resistance, have the operator press R2 against it, and capture the R2 force trajectory. A real
Edge's force-response CHANGES measurably between resistance-ON and resistance-OFF presses (the
resistance reshapes the ramp); an emulator/Cronus/XIM (no adaptive-trigger physics) shows no
difference -> the ON-vs-OFF delta is the device-auth signal. De-risk: is that delta measurable?

ENROLLMENT mode (not in-game). poep_enabled stays False (P4-gated). The pure feature/delta
logic is unit-tested; the hardware capture is defensive (needs an on-rig run, like the buzz
de-risk). STATUS: design-only; no FROZEN-v1/PoAC/chain/contract touched.
"""
from __future__ import annotations

import sys
import time

import numpy as np

_R2_ONSET = 20            # R2 value (0-255) that marks press onset
_trapz = getattr(np, "trapezoid", getattr(np, "trapz"))


def extract_force_features(traj: list) -> dict:
    """From an R2 press trajectory (list of {t_ms, r2}) extract the force-response shape:
    peak, rise time, ramp slope (force vs the resistance), AUC, held plateau."""
    if len(traj) < 3:
        return {"n_samples": len(traj), "peak_r2": 0.0, "rise_time_ms": None,
                "mean_slope": 0.0, "auc": 0.0, "plateau_r2": 0.0}
    ts = [float(s["t_ms"]) for s in traj]
    r2 = [float(s["r2"]) for s in traj]
    peak = max(r2)
    peak_i = r2.index(peak)
    onset_i = next((i for i, v in enumerate(r2) if v > _R2_ONSET), None)
    rise = (ts[peak_i] - ts[onset_i]) if (onset_i is not None and peak_i > onset_i) else None
    slope = (peak / rise) if (rise and rise > 0) else 0.0
    tail = r2[int(len(r2) * 0.8):]
    return {"n_samples": len(traj), "peak_r2": float(peak),
            "rise_time_ms": (round(rise, 1) if rise is not None else None),
            "mean_slope": float(slope), "auc": float(_trapz(r2, ts)),
            "plateau_r2": float(np.mean(tail)) if tail else 0.0}


def force_auth_delta(on: dict, off: dict, min_delta: float = 0.15) -> dict:
    """Device-auth signal: how much the adaptive resistance reshapes the force ramp (slope).
    Real Edge -> resistance-ON slope differs from OFF (delta high); emulator -> identical
    (delta ~0). adaptive_response_detected when the relative slope delta >= min_delta."""
    so, sf = float(on.get("mean_slope", 0.0)), float(off.get("mean_slope", 0.0))
    base = max(so, sf, 1e-9)
    delta = abs(so - sf) / base
    return {"delta": round(delta, 3), "slope_on": round(so, 3), "slope_off": round(sf, 3),
            "adaptive_response_detected": bool(so > 1e-9 and sf > 1e-9 and delta >= min_delta)}


def _set_trigger(ds, resistance: bool) -> bool:
    try:
        from pydualsense import TriggerModes
        if resistance:
            ds.triggerR.setMode(TriggerModes.Rigid); ds.triggerR.setForce(1, 220)
        else:
            ds.triggerR.setMode(TriggerModes.Off)
        return True
    except Exception as exc:
        print(f"  adaptive-trigger set failed: {exc}")
        return False


def run_force_derisk(trials: int = 8, capture_s: float = 2.0) -> dict:
    try:
        from pydualsense import pydualsense
    except Exception as exc:
        return {"status": "no_pydualsense", "error": str(exc)}
    ds = pydualsense()
    try:
        ds.init()
    except Exception as exc:
        return {"status": "controller_unreachable", "error": str(exc)}
    on_feats, off_feats, write_ok = [], [], False
    try:
        for i in range(trials):
            resistance = (i % 2 == 0)
            write_ok = _set_trigger(ds, resistance) or write_ok
            print(f"  trial {i + 1}/{trials} [{'RESISTANCE' if resistance else 'no resistance'}]"
                  " — press R2 fully, then release")
            traj, t0 = [], time.time()
            while time.time() - t0 < capture_s:
                traj.append({"t_ms": (time.time() - t0) * 1000.0, "r2": getattr(ds.state, "R2", 0)})
                time.sleep(0.002)
            f = extract_force_features(traj)
            (on_feats if resistance else off_feats).append(f)
            print(f"    peak_r2={f['peak_r2']:.0f} rise={f['rise_time_ms']} slope={f['mean_slope']:.2f}")
            time.sleep(0.4)
    finally:
        _set_trigger(ds, False)
        try:
            ds.close()
        except Exception:
            pass

    def _agg(fs, k):
        vals = [f[k] for f in fs if f.get(k)]
        return float(np.mean(vals)) if vals else 0.0
    on = {"mean_slope": _agg(on_feats, "mean_slope")}
    off = {"mean_slope": _agg(off_feats, "mean_slope")}
    d = force_auth_delta(on, off)
    d["status"] = "ok"; d["write_ok"] = write_ok
    d["go"] = bool(write_ok and d["adaptive_response_detected"])
    return d


def main() -> int:
    print("=" * 64)
    print("QorTroller PoEP P4a — adaptive-trigger force-challenge de-risk")
    print("=" * 64)
    print("  Hold the controller (USB, NOT in a game). Press R2 fully then release each prompt;")
    print("  half the trials apply trigger RESISTANCE, half don't.\n")
    r = run_force_derisk()
    print("  " + "=" * 60)
    if r.get("status") != "ok":
        print(f"  ABORT: {r.get('status')} {r.get('error', '')}"); return 4
    print(f"  slope ON={r['slope_on']}  OFF={r['slope_off']}  delta={r['delta']}")
    if r["go"]:
        print("  RESULT: GO — adaptive resistance measurably reshapes the force-response "
              "(device-auth channel real). Strengthen device-auth in P4a.")
        return 0
    print("  RESULT: NO-GO — resistance ON vs OFF force-response not distinguishable; "
          "device-auth via force-curve is weak on this method (fall back to IMU/grip).")
    return 6


if __name__ == "__main__":
    sys.exit(main())
