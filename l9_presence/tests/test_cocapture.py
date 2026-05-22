"""Tests for F1 co-capture schema, L4 adapter, and autonomous F3-readiness (no hardware)."""
import numpy as np

from l9_presence.cocapture import (
    CoCaptureSession, compute_l4_features, fusion_readiness, load_cocapture,
    raw_reports_to_snapshots, save_cocapture,
)


def _report(rx=128, ry=128, l2=0, r2=0):
    b = bytearray(64)
    b[0] = 0x01
    b[3] = rx; b[4] = ry; b[5] = l2; b[6] = r2
    return bytes(b)


def _synthetic_stream(n=1100, seed=0):
    rng = np.random.default_rng(seed)
    reports, ts = [], []
    for k in range(n):
        rx = int(128 + 50 * np.sin(k / 30.0))
        reports.append(_report(rx=rx, r2=int(rng.integers(0, 255))))
        ts.append(k * 1000)   # 1 kHz -> 1000 us apart
    return reports, ts


def test_raw_to_snapshots_maps_validated_bytes():
    reports, ts = [_report(rx=200, ry=40, l2=10, r2=250)], [0]
    snaps = raw_reports_to_snapshots(reports, ts)
    assert snaps[0].right_stick_x == 200 and snaps[0].right_stick_y == 40
    assert snaps[0].l2_trigger == 10 and snaps[0].r2_trigger == 250


def test_compute_l4_returns_13_vector():
    reports, ts = _synthetic_stream()
    vec = compute_l4_features(reports, ts)
    # extractor is in-repo (numpy-only) so it should import and return 13 features
    assert vec is not None and vec.shape == (13,)


def test_cocapture_roundtrip(tmp_path):
    s = CoCaptureSession(player="P2", l9_vec=[0.4, 0.6, 0.84], l4_vec=[0.1] * 13,
                         l9_reliable=True, l9_coupling=0.4, l4_provisional=True,
                         n_hid=60000, n_frames=1800)
    p = str(tmp_path / "P2_01.npz")
    save_cocapture(p, s)
    r = load_cocapture(p)
    assert r.player == "P2" and r.l9_reliable and len(r.l4_vec) == 13


def _write(tmp, player, n, reliable=True, l4=True):
    for i in range(n):
        s = CoCaptureSession(player=player, l9_vec=[0.4, 0.6, 0.84],
                             l4_vec=([0.1] * 13 if l4 else None),
                             l9_reliable=reliable, l9_coupling=0.4, l4_provisional=True)
        save_cocapture(str(tmp / f"{player}_{i:02d}.npz"), s)


def test_readiness_ready_with_three_players(tmp_path):
    for pl in ("P1", "P2", "P3"):
        _write(tmp_path, pl, 6)
    rep = fusion_readiness(str(tmp_path), min_per_player=5)
    assert rep["f3_runnable"] is True
    assert rep["tournament_grade_possible"] is True
    assert rep["needs_capture"] is False


def test_readiness_needs_more_players(tmp_path):
    for pl in ("P1", "P2"):
        _write(tmp_path, pl, 6)
    rep = fusion_readiness(str(tmp_path), min_per_player=5)
    assert rep["f3_runnable"] is True            # 2 players is runnable
    assert rep["tournament_grade_possible"] is False
    assert rep["needs_capture"] is True
    assert any("more player" in g for g in rep["gaps"])


def test_readiness_needs_more_sessions(tmp_path):
    _write(tmp_path, "P1", 6)
    _write(tmp_path, "P2", 6)
    _write(tmp_path, "P3", 2)                     # P3 short
    rep = fusion_readiness(str(tmp_path), min_per_player=5)
    assert rep["f3_runnable"] is False
    assert any("P3 needs" in g for g in rep["gaps"])


def test_recompute_l9_from_stored_streams(tmp_path):
    from l9_presence.cocapture import recompute_l9_from_file
    # synthetic coupled streams (camera = lagged stick), stored alongside the session
    n, dt = 500, 10.0
    ts = np.arange(n) * dt
    sx = 128 + 60 * np.sin(2 * np.pi * 0.8 * ts / 1000.0)
    sy = 128 + 8 * np.sin(2 * np.pi * 0.3 * ts / 1000.0)
    yaw = np.zeros(n); yaw[4:] = (sx[:-4] - 128) * 1.5
    streams = {"in_ts": ts, "in_sx": sx, "in_sy": sy,
               "mo_ts": ts, "mo_yaw": yaw, "mo_pitch": np.zeros(n)}
    s = CoCaptureSession(player="P1", l9_vec=[0.4, 0.6, 0.84], l4_vec=[0.1] * 13,
                         l9_reliable=True, l9_coupling=0.4, l4_provisional=False)
    p = str(tmp_path / "P1_01.npz")
    save_cocapture(p, s, l9_streams=streams)
    r = recompute_l9_from_file(p)
    assert r["coupling_score"] > 0.3          # aligned streams -> real coupling
    assert r["stick_x_std"] > 2.0             # stick actually varied


def test_readiness_ignores_l4_missing(tmp_path):
    _write(tmp_path, "P1", 6, l4=False)           # no L4 view -> not usable
    rep = fusion_readiness(str(tmp_path), min_per_player=5)
    assert rep["usable_sessions"] == 0
