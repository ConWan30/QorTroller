"""Tests for the synthetic adversary generator (numpy-only; no hardware)."""
import numpy as np

from l9_presence.session_recorder import SessionData, analyze_session_data
from l9_presence.synth_adversary import evaluate, injected_motion, synthesize


def _coupled_session(n=400, rate_hz=100.0, lag_ms=40.0, freq_hz=0.8, seed=0):
    rng = np.random.default_rng(seed)
    dt = 1000.0 / rate_hz
    ts = np.arange(n) * dt
    sx = 128 + 60.0 * np.sin(2 * np.pi * freq_hz * ts / 1000.0)
    sy = 128 + 10.0 * np.sin(2 * np.pi * (freq_hz * 0.4) * ts / 1000.0)
    lag = int(round(lag_ms / dt))
    yaw = rng.normal(0, 0.4, n)
    yaw[lag:] += (sx[: n - lag] - 128) * 1.5
    pitch = rng.normal(0, 0.4, n)
    return SessionData(ts, sx, sy, ts, yaw, pitch, "human")


def test_injected_motion_shape_and_determinism():
    ts = np.arange(300) * 10.0
    y1, p1 = injected_motion(ts, "snap", seed=7)
    y2, p2 = injected_motion(ts, "snap", seed=7)
    assert y1.shape == p1.shape == (300,)
    assert np.allclose(y1, y2)  # deterministic for a fixed seed


def test_injection_zero_is_unchanged():
    s = _coupled_session()
    out = synthesize(s, injection=0.0, mode="snap")
    assert np.allclose(out.mo_yaw, s.mo_yaw)
    assert out.label == "scripted"


def test_pure_injection_collapses_coupling():
    s = _coupled_session()
    human = analyze_session_data(s)["coupling_score"]
    # every injection profile reduces coupling below the human's
    for mode in ("static", "snap", "track"):
        scripted = analyze_session_data(synthesize(s, injection=1.0, mode=mode))["coupling_score"]
        assert scripted < human
    # the hard-decoupling profiles collapse toward the noise floor; smooth "track"
    # is deliberately the harder case (a coherent camera track partially correlates)
    for mode in ("static", "snap"):
        scripted = analyze_session_data(synthesize(s, injection=1.0, mode=mode))["coupling_score"]
        assert scripted < 0.3


def test_evaluate_separates_and_sweeps(tmp_path):
    paths = []
    for i in range(3):
        s = _coupled_session(freq_hz=0.5 + 0.3 * i, seed=i)
        p = str(tmp_path / f"h{i}.npz")
        np.savez(p, in_ts=s.in_ts, in_sx=s.in_sx, in_sy=s.in_sy,
                 mo_ts=s.mo_ts, mo_yaw=s.mo_yaw, mo_pitch=s.mo_pitch, label="human")
        paths.append(p)
    rep = evaluate(paths, seed=0)
    assert rep["human_coupling_mean"] > rep["modes"]["snap"]["scripted_coupling_mean"]
    sweep = rep["injection_sweep"]
    assert sweep["0.00"]["coupling"] > sweep["1.00"]["coupling"]  # more injection -> less coupling
    # the residual axis should not be lower under full injection than under none
    assert sweep["1.00"]["decoupled_energy"] >= sweep["0.00"]["decoupled_energy"] - 0.05
