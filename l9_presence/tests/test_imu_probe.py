"""Tests for the IMU offset validator (numpy-only; no hardware).

Synthesizes a DualSense-like report stream with a KNOWN IMU layout (gyro then accel)
and confirms the detector recovers the offsets, labels accel as the conserved-magnitude
triple, and that cocapture picks up the validated mapping (l4 no longer provisional).
"""
import json

import numpy as np

from l9_presence.imu_probe import detect_imu_offsets


def _put_i16(b, i, v):
    b[i:i + 2] = int(np.clip(v, -32768, 32767)).to_bytes(2, "little", signed=True)


def _make_streams(gyro_off=(16, 18, 20), accel_off=(22, 24, 26), g=8000, seed=0):
    rng = np.random.default_rng(seed)
    rest, rot = [], []
    # REST: gyro ~0, accel = gravity on z (one axis), small noise
    for _ in range(120):
        b = bytearray(64); b[0] = 0x01
        for o in gyro_off:
            _put_i16(b, o, rng.normal(0, 5))
        gx, gy, gz = rng.normal(0, 5), rng.normal(0, 5), g + rng.normal(0, 5)
        _put_i16(b, accel_off[0], gx); _put_i16(b, accel_off[1], gy); _put_i16(b, accel_off[2], gz)
        rest.append(bytes(b))
    # ROTATION: gyro spikes (zero-mean, high var), accel = gravity rotating (magnitude conserved)
    for k in range(240):
        b = bytearray(64); b[0] = 0x01
        for o in gyro_off:
            _put_i16(b, o, rng.normal(0, 4000))
        th, ph = k * 0.15, k * 0.07
        ax = g * np.sin(th) * np.cos(ph); ay = g * np.sin(th) * np.sin(ph); az = g * np.cos(th)
        _put_i16(b, accel_off[0], ax); _put_i16(b, accel_off[1], ay); _put_i16(b, accel_off[2], az)
        rot.append(bytes(b))
    return rest, rot


def test_detects_known_gyro_accel_layout():
    rest, rot = _make_streams(gyro_off=(16, 18, 20), accel_off=(22, 24, 26))
    res = detect_imu_offsets(rest, rot)
    assert (res["gyro_x"], res["gyro_y"], res["gyro_z"]) == (16, 18, 20)
    assert (res["accel_x"], res["accel_y"], res["accel_z"]) == (22, 24, 26)
    assert res["accel_mag_cv"] < 0.2          # gravity magnitude conserved
    assert res["confidence"] in ("high", "medium")


def test_scale_normalizes_gravity_to_one():
    rest, rot = _make_streams(g=8000)
    res = detect_imu_offsets(rest, rot)
    assert abs(8000 * res["scale"] - 1.0) < 0.1   # rest accel magnitude -> ~1.0 g


def test_inconclusive_on_structureless():
    rng = np.random.default_rng(0)
    flat = [bytes(bytearray([0x01]) + bytes(rng.integers(0, 256, 63).tolist())) for _ in range(50)]
    res = detect_imu_offsets(flat, flat)
    assert "gyro_x" not in res                  # no still/rotate structure -> no false lock


def test_cocapture_uses_validated_offsets(tmp_path):
    from l9_presence import cocapture
    p = tmp_path / "imu_offsets.json"
    p.write_text(json.dumps({"gyro_x": 16, "gyro_y": 18, "gyro_z": 20,
                             "accel_x": 22, "accel_y": 24, "accel_z": 26, "scale": 1.25e-4}))
    loaded = cocapture.load_validated_offsets(str(p))
    assert loaded is not None
    offs, scale = loaded
    assert offs["accel_z"] == 26 and abs(scale - 1.25e-4) < 1e-9
