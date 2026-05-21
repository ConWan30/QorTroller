"""QorTroller L9 — synthetic adversary generator (DEVELOPMENT / threshold-setting).

Builds labeled "scripted" sessions from REAL human recordings by replacing the
on-screen CAMERA track with aimbot-style motion that is NOT caused by the player's
stick. The player's real stick input is kept, so this models an aimbot operating
while a human still holds the controller — the camera moves on its own.

Three injection profiles:
  * "static" — bot barely aims manually; camera ~still + noise (lock-and-hold).
  * "snap"   — periodic snap-to-target impulses (the classic aimbot signature).
  * "track"  — camera smoothly tracks a synthetic target at a frequency unrelated
               to the stick (smooth-aim cheat).

It also runs an INJECTION SWEEP: camera = (1-b)*real_camera + b*injected, for b in
[0..1]. b=0 is the real human; b=1 is pure injection. The coupling score as b rises
shows where the detector starts catching partial injection — i.e. how to set a
threshold against the human baseline.

HONEST SCOPE: this tests the detector against a MODEL of a cheat (useful for
development + thresholds), NOT a real aimbot, and it does NOT model an input-masked
aimbot that also fakes matching stick input. Treat results as design evidence, not
a field-validated detection rate. The real negative condition is cheat-free decoupled
capture (killcam/spectator/replay) — see README.

STATUS: design-only. No FROZEN-v1 primitive, no chain, no PoAC change. Generates no
in-game effect — it only writes camera-motion arrays for offline detector testing.
"""
from __future__ import annotations

import numpy as np

from .session_recorder import SessionData, analyze_session_data, load_session

MODES = ("static", "snap", "track")


def injected_motion(ts_ms: np.ndarray, mode: str, seed: int = 0) -> tuple[np.ndarray, np.ndarray]:
    """Generate (yaw, pitch) aimbot-style camera motion uncoupled from any stick."""
    rng = np.random.default_rng(seed)
    n = ts_ms.size
    base_y = rng.normal(0.0, 0.5, n)
    base_p = rng.normal(0.0, 0.5, n)
    if mode == "static":
        return base_y, base_p
    if mode == "snap":
        n_snaps = max(1, n // 80)                 # ~ one lock-on per ~0.8s at 100Hz
        for _ in range(n_snaps):
            i = int(rng.integers(0, max(1, n - 3)))
            base_y[i:i + 2] += rng.normal(0.0, 25.0)   # fast large snap
            base_p[i:i + 2] += rng.normal(0.0, 12.0)
        return base_y, base_p
    if mode == "track":
        f = 0.13 + 0.05 * rng.random()            # target frequency unrelated to stick
        ph = rng.random() * 2 * np.pi
        yaw = 8.0 * np.sin(2 * np.pi * f * ts_ms / 1000.0 + ph) + base_y
        pitch = 3.0 * np.sin(2 * np.pi * (f * 0.5) * ts_ms / 1000.0) + base_p
        return yaw, pitch
    raise ValueError(f"unknown mode {mode!r}; pick one of {MODES}")


def synthesize(session: SessionData, injection: float = 1.0,
               mode: str = "snap", seed: int = 0) -> SessionData:
    """Return a 'scripted' SessionData: camera = (1-injection)*real + injection*injected.
    Real stick input is preserved. injection=1.0 -> pure aimbot; 0.0 -> unchanged human."""
    b = float(np.clip(injection, 0.0, 1.0))
    iy, ip = injected_motion(np.asarray(session.mo_ts, dtype=np.float64), mode, seed)
    yaw = (1.0 - b) * np.asarray(session.mo_yaw, float) + b * iy
    pitch = (1.0 - b) * np.asarray(session.mo_pitch, float) + b * ip
    return SessionData(session.in_ts, session.in_sx, session.in_sy,
                       session.mo_ts, yaw, pitch, "scripted", session.in_fire)


def _metrics_of(s: SessionData) -> tuple:
    """(coupling_score, decoupled_energy) for a session, or (None, None)."""
    r = analyze_session_data(s)
    return r.get("coupling_score"), r.get("decoupled_energy")


def _mean(xs):
    xs = [x for x in xs if x is not None]
    return float(np.mean(xs)) if xs else None


def evaluate(paths: list[str], modes=MODES, seed: int = 0) -> dict:
    """Score real human sessions vs pure-injection scripted versions per mode, on BOTH
    axes (coupling + decoupled_energy/residual), and run an injection sweep. Coupling
    catches full takeover; the residual axis is the tool for partial assist."""
    humans = [load_session(p) for p in paths]
    h_pairs = [_metrics_of(s) for s in humans]
    h_coup = _mean([c for c, _ in h_pairs])
    h_dec = _mean([d for _, d in h_pairs])
    out: dict = {
        "n_human": len(humans),
        "human_coupling_mean": h_coup,
        "human_decoupled_energy_mean": h_dec,
        "modes": {},
        "injection_sweep": {},
    }
    for mode in modes:
        pairs = [_metrics_of(synthesize(s, injection=1.0, mode=mode, seed=seed + i))
                 for i, s in enumerate(humans)]
        s_coup = _mean([c for c, _ in pairs])
        s_dec = _mean([d for _, d in pairs])
        out["modes"][mode] = {
            "scripted_coupling_mean": s_coup,
            "coupling_separation": (h_coup - s_coup) if (h_coup is not None and s_coup is not None) else None,
            "scripted_decoupled_energy_mean": s_dec,
            "decoupled_energy_rise": (s_dec - h_dec) if (h_dec is not None and s_dec is not None) else None,
        }
    for b in (0.0, 0.25, 0.5, 0.75, 1.0):
        pairs = [_metrics_of(synthesize(s, injection=b, mode="snap", seed=seed + i))
                 for i, s in enumerate(humans)]
        out["injection_sweep"][f"{b:.2f}"] = {
            "coupling": _mean([c for c, _ in pairs]),
            "decoupled_energy": _mean([d for _, d in pairs]),
        }
    return out


def _cli() -> int:
    import argparse
    import json
    ap = argparse.ArgumentParser(description="L9 synthetic adversary (dev/threshold tool)")
    ap.add_argument("paths", nargs="+", help="real human .npz sessions")
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args()
    print(json.dumps(evaluate(a.paths, seed=a.seed), indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
