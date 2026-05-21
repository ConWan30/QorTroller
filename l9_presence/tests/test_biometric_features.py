"""Tests for the L9 render-loop biometric feature vector (numpy-only; no hardware)."""
import numpy as np

from l9_presence.biometric_features import (
    between_player_separation, extract_feature_vector, permutation_test,
    within_player_stability,
)
from l9_presence.session_recorder import SessionData, load_session


def _write_player(path, player, axis="yaw", n=500, rate_hz=100.0, lag_ms=40.0,
                  freq_hz=0.8, gain=1.5, seed=0):
    """Write a yaw- or pitch-driven session tagged with a player id."""
    rng = np.random.default_rng(seed)
    dt = 1000.0 / rate_hz
    ts = np.arange(n) * dt
    big, small = 60.0, 8.0
    lag = int(round(lag_ms / dt))
    yaw = rng.normal(0, 0.4, n)
    pitch = rng.normal(0, 0.4, n)
    if axis == "yaw":
        sx = 128 + big * np.sin(2 * np.pi * freq_hz * ts / 1000.0)
        sy = 128 + small * np.sin(2 * np.pi * (freq_hz * 0.4) * ts / 1000.0)
        yaw[lag:] += (sx[: n - lag] - 128) * gain
    else:
        sy = 128 + big * np.sin(2 * np.pi * freq_hz * ts / 1000.0)
        sx = 128 + small * np.sin(2 * np.pi * (freq_hz * 0.4) * ts / 1000.0)
        pitch[lag:] += (sy[: n - lag] - 128) * gain
    np.savez(path, in_ts=ts, in_sx=sx, in_sy=sy, mo_ts=ts, mo_yaw=yaw, mo_pitch=pitch,
             label="human", player=player)
    return str(path)


def _session(n=500, rate_hz=100.0, lag_ms=40.0, freq_hz=0.8, gain=1.5, seed=0, active=True):
    rng = np.random.default_rng(seed)
    dt = 1000.0 / rate_hz
    ts = np.arange(n) * dt
    amp = 60.0 if active else 0.5          # inactive = barely aiming
    sx = 128 + amp * np.sin(2 * np.pi * freq_hz * ts / 1000.0)
    sy = 128 + (amp * 0.15) * np.sin(2 * np.pi * (freq_hz * 0.4) * ts / 1000.0)
    lag = int(round(lag_ms / dt))
    yaw = rng.normal(0, 0.4, n)
    if active:
        yaw[lag:] += (sx[: n - lag] - 128) * gain
    pitch = rng.normal(0, 0.4, n)
    return SessionData(ts, sx, sy, ts, yaw, pitch, "human")


def test_feature_vector_keys_and_reliability():
    v = extract_feature_vector(_session(active=True))
    for k in ("yaw_coupling", "dominant_coupling", "dominant_lag_ms",
              "yaw_pitch_ratio", "aim_activity", "reliable"):
        assert k in v
    assert v["reliable"] is True
    assert v["yaw_coupling"] > v["pitch_coupling"]   # yaw-driven session
    assert v["yaw_pitch_ratio"] > 0.5


def test_inactive_session_is_unreliable():
    v = extract_feature_vector(_session(active=False))
    assert v["reliable"] is False


def test_within_player_stability_gates_and_scores(tmp_path):
    # 5 consistent active sessions + 1 inactive -> reliable subset = 5, low CV
    import numpy as _np
    paths = []
    for i in range(5):
        s = _session(lag_ms=40.0, freq_hz=0.8, seed=i, active=True)
        p = str(tmp_path / f"a{i}.npz")
        _np.savez(p, in_ts=s.in_ts, in_sx=s.in_sx, in_sy=s.in_sy,
                  mo_ts=s.mo_ts, mo_yaw=s.mo_yaw, mo_pitch=s.mo_pitch, label="human")
        paths.append(p)
    s = _session(seed=99, active=False)
    p = str(tmp_path / "inactive.npz")
    _np.savez(p, in_ts=s.in_ts, in_sx=s.in_sx, in_sy=s.in_sy,
              mo_ts=s.mo_ts, mo_yaw=s.mo_yaw, mo_pitch=s.mo_pitch, label="human")
    paths.append(p)

    rep = within_player_stability(paths)
    assert rep["n_total"] == 6
    assert rep["n_reliable"] == 5                       # inactive gated out
    assert rep["features"]["dominant_coupling"]["cv"] < 0.3   # consistent -> stable


def test_player_id_round_trips(tmp_path):
    p = _write_player(tmp_path / "p.npz", "P2")
    assert load_session(p).player == "P2"


def test_between_player_needs_two(tmp_path):
    paths = [_write_player(tmp_path / f"p1_{i}.npz", "P1", seed=i) for i in range(3)]
    assert between_player_separation(paths)["status"] == "need_>=2_players"


def test_between_player_separates_distinct_styles(tmp_path):
    paths = []
    for i in range(4):
        paths.append(_write_player(tmp_path / f"p1_{i}.npz", "P1", axis="yaw", seed=i))
        paths.append(_write_player(tmp_path / f"p2_{i}.npz", "P2", axis="pitch", seed=100 + i))
    rep = between_player_separation(paths)
    assert rep["n_players"] == 2
    assert rep["separation_ratio"] > 1.0     # distinct aim styles -> separable
    assert rep["separable"] is True
    assert rep["loo_accuracy"] > 0.7         # proper LOO classifies the two styles
    assert rep["loo_total"] == 8


def test_permutation_test_flags_real_separation(tmp_path):
    paths = []
    for i in range(4):
        paths.append(_write_player(tmp_path / f"p1_{i}.npz", "P1", axis="yaw", seed=i))
        paths.append(_write_player(tmp_path / f"p2_{i}.npz", "P2", axis="pitch", seed=100 + i))
    rep = permutation_test(paths, n_perm=500)
    assert rep["real_ratio"] > rep["null_p95"]   # real separation beats the null
    assert rep["significant"] is True
