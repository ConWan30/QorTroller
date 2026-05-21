"""Deterministic tests for the L9 coupling core (numpy-only; no I/O, no hardware).

These validate the load-bearing claim: a human (input causally drives the screen)
scores HIGH coupling with a COLLAPSING negative control, while an aimbot (screen
moves without/independent of input) scores LOW coupling + HIGH decoupled energy.
"""
import numpy as np
import pytest

from l9_presence import coupling as C


# ---------------------------------------------------------------------------
# synthetic session builders
# ---------------------------------------------------------------------------

def _human_session(lag_ms=50.0, dur_ms=3000.0, freq=0.8, noise=0.05, seed=0):
    """Input 1kHz sine; on-screen yaw = centered stick delayed by lag + noise."""
    in_ts = np.arange(0.0, dur_ms, dur_ms / 3000.0)
    stick = 128.0 + 40.0 * np.sin(2 * np.pi * freq * in_ts / 1000.0)   # 8-bit, 128 neutral
    vid_ts = np.arange(0.0, dur_ms, 1000.0 / 60.0)                      # 60fps
    rng = np.random.default_rng(seed)
    meas_yaw = 40.0 * np.sin(2 * np.pi * freq * (vid_ts - lag_ms) / 1000.0)
    meas_yaw = meas_yaw + noise * 40.0 * rng.standard_normal(vid_ts.size)
    return in_ts, stick, vid_ts, meas_yaw


def _aimbot_session(dur_ms=3000.0, seed=1):
    """Stick still moves (player appears to aim) but on-screen yaw is an
    INDEPENDENT signal — the crosshair moves on its own."""
    in_ts = np.arange(0.0, dur_ms, dur_ms / 3000.0)
    stick = 128.0 + 40.0 * np.sin(2 * np.pi * 0.8 * in_ts / 1000.0)
    vid_ts = np.arange(0.0, dur_ms, 1000.0 / 60.0)
    rng = np.random.default_rng(seed)
    # independent on-screen motion (different freq + noise) — not from the stick
    meas_yaw = 40.0 * np.sin(2 * np.pi * 1.7 * vid_ts / 1000.0 + 1.1) \
        + 20.0 * rng.standard_normal(vid_ts.size)
    return in_ts, stick, vid_ts, meas_yaw


def _fill(oracle, in_ts, stick, vid_ts, meas_yaw):
    for t, s in zip(in_ts, stick):
        oracle.push_input(t, s, 128.0)              # pitch stick static
    for t, y in zip(vid_ts, meas_yaw):
        oracle.push_frame_motion(t, y, 0.0)


# ---------------------------------------------------------------------------
# pure-function tests
# ---------------------------------------------------------------------------

def test_lagged_xcorr_recovers_known_lag():
    rng = np.random.default_rng(7)
    pred = rng.standard_normal(400)
    k = 9
    meas = np.empty_like(pred)
    meas[k:] = pred[:-k]
    meas[:k] = 0.0
    meas += 0.02 * rng.standard_normal(pred.size)
    r, lag = C.lagged_xcorr(pred, meas, 0, 30)
    assert lag == pytest.approx(k, abs=1)
    assert abs(r) > 0.9


def test_decoupled_energy_low_when_coupled_high_when_noise():
    rng = np.random.default_rng(3)
    pred = rng.standard_normal(400)
    meas_coupled = 2.5 * pred                       # fully explained at lag 0
    assert C.decoupled_energy_fraction(pred, meas_coupled, 0) < 0.05
    meas_noise = rng.standard_normal(400)           # unrelated
    assert C.decoupled_energy_fraction(pred, meas_noise, 0) > 0.7


def test_resample_uniform_basic():
    ts = np.array([0.0, 10.0, 20.0])
    vals = np.array([0.0, 10.0, 0.0])
    grid = np.array([5.0, 15.0])
    out = C.resample_uniform(ts, vals, grid)
    assert out[0] == pytest.approx(5.0)
    assert out[1] == pytest.approx(5.0)


# ---------------------------------------------------------------------------
# oracle / end-to-end synthetic tests
# ---------------------------------------------------------------------------

def test_human_session_high_coupling_low_residual():
    o = C.InputOutputCouplingOracle()
    _fill(o, *_human_session())
    f = o.extract_features()
    assert f is not None
    assert f.dominant_axis == "yaw"
    assert f.coupling_score > 0.8           # input explains the screen
    assert f.coupled is True
    assert f.decoupled_energy < 0.35        # little unexplained motion
    assert 0.0 <= f.lag_ms <= C.LAG_MAX_MS


def test_human_negative_control_collapses():
    o = C.InputOutputCouplingOracle()
    _fill(o, *_human_session())
    f = o.extract_features()
    nc = o.negative_control()
    assert f is not None and nc is not None
    # time-shuffled input must lose almost all coupling
    assert nc < 0.3
    assert f.coupling_score - nc > 0.4      # clear, honest margin


def test_aimbot_session_low_coupling_high_residual():
    o = C.InputOutputCouplingOracle()
    _fill(o, *_aimbot_session())
    f = o.extract_features()
    assert f is not None
    assert f.coupling_score < 0.30          # screen motion not from the stick
    assert f.coupled is False
    assert f.decoupled_energy > 0.6         # large unexplained (aimbot) energy


def test_static_stick_returns_none():
    o = C.InputOutputCouplingOracle()
    in_ts = np.arange(0.0, 3000.0, 1.0)
    stick = np.full(in_ts.size, 128.0)      # player not aiming
    vid_ts = np.arange(0.0, 3000.0, 1000.0 / 60.0)
    meas = 10.0 * np.sin(2 * np.pi * 1.0 * vid_ts / 1000.0)
    _fill(o, in_ts, stick, vid_ts, meas)
    assert o.extract_features() is None     # undefined when no aim activity
    assert o.humanity_score() == 0.5        # neutral, not a false accusation


def test_separation_human_vs_aimbot():
    """The GO/NO-GO in miniature: human coupling clearly exceeds aimbot coupling."""
    h = C.InputOutputCouplingOracle(); _fill(h, *_human_session())
    a = C.InputOutputCouplingOracle(); _fill(a, *_aimbot_session())
    hf, af = h.extract_features(), a.extract_features()
    assert hf is not None and af is not None
    assert hf.coupling_score > af.coupling_score + 0.4
    assert af.decoupled_energy > hf.decoupled_energy + 0.3
