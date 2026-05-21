"""Synthetic tests for L9 session-analysis helpers (numpy-only; no hardware).

Builds in-memory .npz sessions where the camera motion is a lagged copy of the
stick (coupled) and verifies: the parser reads explicit offsets, a coupled session
scores high with a collapsing negative control, and the cross-session decoupled
control separates true pairs from mismatched pairs.
"""
import numpy as np

from l9_presence.coupling import residual_series
from l9_presence.session_recorder import (
    SessionData, analyze_session, compare_sessions, decoupled_control,
    engagement_locked_residual, make_stick_parser,
)


def _eng_session(n=900, rate_hz=100.0, lag_ms=40.0, freq_hz=0.8, seed=0, aimbot=False):
    """Coupled session with firing in the second half; if aimbot, inject unexplained
    snaps only while firing (the engagement-locked signature)."""
    rng = np.random.default_rng(seed)
    dt = 1000.0 / rate_hz
    ts = np.arange(n) * dt
    sx = 128 + 60.0 * np.sin(2 * np.pi * freq_hz * ts / 1000.0)
    sy = 128 + 10.0 * np.sin(2 * np.pi * (freq_hz * 0.4) * ts / 1000.0)
    lag = int(round(lag_ms / dt))
    yaw = rng.normal(0, 0.4, n)
    yaw[lag:] += (sx[: n - lag] - 128) * 1.5
    fire = np.zeros(n)
    fire[n // 2:] = 200.0                       # trigger held through the second half
    if aimbot:
        for i in range(n // 2, n, 18):          # unexplained snaps only while firing
            yaw[i:i + 5] += rng.normal(0, 30)
    pitch = rng.normal(0, 0.4, n)
    return SessionData(ts, sx, sy, ts, yaw, pitch, "x", fire)


def _write_session(path, n=400, rate_hz=100.0, lag_ms=40.0, coupled=True,
                   freq_hz=0.8, seed=0, label="human"):
    rng = np.random.default_rng(seed)
    dt = 1000.0 / rate_hz
    ts = np.arange(n) * dt
    sx = 128 + 60.0 * np.sin(2 * np.pi * freq_hz * ts / 1000.0)
    sy = 128 + 10.0 * np.sin(2 * np.pi * (freq_hz * 0.4) * ts / 1000.0)
    # camera yaw rate is proportional to (lagged) stick deflection, + noise
    lag = int(round(lag_ms / dt))
    yaw = rng.normal(0, 0.4, n)
    if coupled and lag < n:
        yaw[lag:] += (sx[: n - lag] - 128) * 1.5
    pitch = rng.normal(0, 0.4, n)
    np.savez(path, in_ts=ts, in_sx=sx, in_sy=sy,
             mo_ts=ts, mo_yaw=yaw, mo_pitch=pitch, label=label)


def test_make_stick_parser_reads_offsets():
    parse = make_stick_parser(3, 4)
    assert parse(bytes([0x01, 10, 20, 200, 50, 0, 0])) == (200.0, 50.0)


def test_make_stick_parser_short_report_is_safe():
    assert make_stick_parser(3, 4)(b"\x01\x02") == (128.0, 128.0)


def test_coupled_session_scores_high_with_collapsing_control(tmp_path):
    p = str(tmp_path / "human.npz")
    _write_session(p, coupled=True)
    r = analyze_session(p)
    assert r["coupling_score"] > 0.3
    assert r["negative_control"] < 0.2          # shuffle control collapses
    assert r["neg_control_margin"] > 0.1


def test_decoupled_session_scores_low(tmp_path):
    p = str(tmp_path / "decoupled.npz")
    _write_session(p, coupled=False)
    r = analyze_session(p)
    # camera unrelated to input -> coupling near the noise floor
    assert r.get("coupling_score", 1.0) < 0.3


def test_decoupled_control_separates_true_from_mismatched(tmp_path):
    paths = []
    for i in range(3):
        p = str(tmp_path / f"h{i}.npz")
        _write_session(p, coupled=True, freq_hz=0.5 + 0.35 * i, seed=i)  # distinct patterns
        paths.append(p)
    res = decoupled_control(paths)
    assert res["true_coupling_mean"] > res["decoupled_coupling_mean"]
    assert res["separation"] > 0.1


def test_residual_series_removes_linear_response():
    pred = np.sin(np.linspace(0, 12, 300))
    meas = 2.3 * pred                       # perfectly explained by a linear gain
    resid, b = residual_series(pred, meas, 0)
    assert resid.var() < 1e-3 * meas.var()   # linear response removed (tiny ddof bias remains)
    assert b.size == pred.size


def test_engagement_locked_no_fire_data():
    s = _eng_session(aimbot=False)
    s.in_fire = None
    assert engagement_locked_residual(s)["status"] == "no_fire_data"


def test_engagement_locked_flags_fire_correlated_injection():
    human = engagement_locked_residual(_eng_session(aimbot=False))
    bot = engagement_locked_residual(_eng_session(aimbot=True))
    # human: firing adds no unexplained aim -> fire ~ rest
    assert abs(human["fire_minus_rest"]) < 0.2
    # aimbot: unexplained snaps cluster at the trigger -> fire residual >> rest
    assert bot["fire_minus_rest"] > human["fire_minus_rest"]
    assert bot["residual_energy_fire"] > bot["residual_energy_rest"]


def test_compare_groups_by_label(tmp_path):
    h = str(tmp_path / "h.npz"); _write_session(h, coupled=True, label="human")
    s = str(tmp_path / "s.npz"); _write_session(s, coupled=False, label="scripted")
    out = compare_sessions([h, s])
    assert out["labels"]["human"]["n"] == 1
    assert out["labels"]["scripted"]["n"] == 1
