"""Tests for the L9 render-loop biometric feature vector (numpy-only; no hardware)."""
import numpy as np

from l9_presence.biometric_features import extract_feature_vector, within_player_stability
from l9_presence.session_recorder import SessionData


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
