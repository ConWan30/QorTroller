"""QorTroller L9 — render-loop biometric feature vector + within-player stability.

Enhancement #1: the first biometric derived from the RENDERED output loop rather than
the controller alone. Per session it extracts {per-axis causal coupling, causal lag,
yaw/pitch dominance ratio, decoupled energy}. These are candidate features for the
inter-person separation that gates tournaments — but a biometric must be TIGHT within
one person before it can separate people, so within_player_stability() reports the
coefficient of variation (CV) across a single player's sessions, gated to sessions
with real aim activity (low-aim sessions carry no usable signal and only add noise).

STATUS: design-only probe. No FROZEN-v1 primitive, no chain, no PoAC change.
"""
from __future__ import annotations

from typing import Optional

import numpy as np

from . import coupling as C
from .session_recorder import load_session

_EPS = 1e-9
_LAG_MIN = int(round(C.LAG_MIN_MS / 1000.0 * C.COMMON_RATE_HZ))
_LAG_MAX = int(round(C.LAG_MAX_MS / 1000.0 * C.COMMON_RATE_HZ))


def _axis_features(in_ts, stick, mo_ts, cam, grid):
    """(|coupling|, lag_ms, decoupled_energy) for one input/camera axis."""
    s = np.asarray(stick, float)
    s = s - np.median(s)
    pred = C.resample_uniform(np.asarray(in_ts, float), C.aim_response(s), grid)
    meas = C.resample_uniform(np.asarray(mo_ts, float), np.asarray(cam, float), grid)
    r, lag = C.lagged_xcorr(pred, meas, _LAG_MIN, _LAG_MAX)
    dec = C.decoupled_energy_fraction(pred, meas, lag)
    return abs(r), lag * 1000.0 / C.COMMON_RATE_HZ, dec


def extract_feature_vector(s, coupling_floor: float = 0.2) -> Optional[dict]:
    """Per-session L9 biometric feature vector, or None if too short to grid."""
    in_ts, mo_ts = np.asarray(s.in_ts, float), np.asarray(s.mo_ts, float)
    if in_ts.size < 4 or mo_ts.size < 4:
        return None
    t0, t1 = max(in_ts[0], mo_ts[0]), min(in_ts[-1], mo_ts[-1])
    if t1 - t0 < (C.MIN_GRID_SAMPLES / C.COMMON_RATE_HZ) * 1000.0:
        return None
    grid = np.arange(t0, t1, 1000.0 / C.COMMON_RATE_HZ)
    yc, yl, yd = _axis_features(in_ts, s.in_sx, mo_ts, s.mo_yaw, grid)
    pc, pl, pd = _axis_features(in_ts, s.in_sy, mo_ts, s.mo_pitch, grid)
    sx = np.asarray(s.in_sx, float); sx -= np.median(sx)
    sy = np.asarray(s.in_sy, float); sy -= np.median(sy)
    dom_yaw = yc >= pc
    return {
        "yaw_coupling": yc, "pitch_coupling": pc,
        "yaw_lag_ms": yl, "pitch_lag_ms": pl,
        "yaw_decoupled": yd, "pitch_decoupled": pd,
        "dominant_coupling": max(yc, pc),
        "dominant_lag_ms": yl if dom_yaw else pl,
        "yaw_pitch_ratio": yc / (yc + pc + _EPS),   # 1.0 = pure yaw aimer, 0.5 = balanced
        "aim_activity": float(max(sx.std(), sy.std())),
        "reliable": bool(max(yc, pc) >= coupling_floor),
    }


def _stats(xs) -> dict:
    xs = np.asarray(xs, float)
    m, sd = float(xs.mean()), float(xs.std())
    return {"mean": round(m, 4), "std": round(sd, 4),
            "cv": round(sd / abs(m), 4) if abs(m) > _EPS else None, "n": int(xs.size)}


# features that are candidate biometrics; report stability on each
_FEATURE_KEYS = ("dominant_coupling", "dominant_lag_ms", "yaw_coupling",
                 "yaw_lag_ms", "yaw_pitch_ratio", "yaw_decoupled")


def within_player_stability(paths: list[str], coupling_floor: float = 0.2) -> dict:
    """CV of each candidate feature across one player's sessions (reliable subset).
    Low CV (< ~0.3) = stable enough to be a biometric; high CV = needs finer capture
    or better gating before it can help separation."""
    vecs = [extract_feature_vector(load_session(p), coupling_floor) for p in paths]
    vecs = [v for v in vecs if v is not None]
    reliable = [v for v in vecs if v["reliable"]]
    src = reliable if reliable else vecs
    out = {
        "n_total": len(vecs),
        "n_reliable": len(reliable),
        "coupling_floor": coupling_floor,
        "features": {k: _stats([v[k] for v in src]) for k in _FEATURE_KEYS},
        "verdict": {},
    }
    for k in _FEATURE_KEYS:
        cv = out["features"][k]["cv"]
        out["verdict"][k] = ("stable" if (cv is not None and cv < 0.3)
                             else "noisy" if cv is not None else "undefined")
    return out


def _cli() -> int:
    import argparse
    import json
    ap = argparse.ArgumentParser(description="L9 render-loop biometric stability")
    ap.add_argument("paths", nargs="+")
    ap.add_argument("--coupling-floor", type=float, default=0.2)
    a = ap.parse_args()
    print(json.dumps(within_player_stability(a.paths, a.coupling_floor), indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
