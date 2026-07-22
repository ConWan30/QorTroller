"""Unit tests for the U3 recorder's IMU byte-parsing (pure, no hardware/capture I/O).
Offsets verified against controller/dualshock_emulator.py's tested pydualsense parse."""
from __future__ import annotations
import struct, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from u3_raw_capture import (parse_imu, OFF_ACCEL_X, OFF_ACCEL_Y, OFF_ACCEL_Z, OFF_GYRO_X, OFF_GYRO_Y,
                            OFF_GYRO_Z, ACCEL_SCALE, OFF_SENSOR_TS)

def test_short_buffer_returns_zeros_never_raises():
    r = parse_imu(b"\x00" * 10)
    assert r == {"accel_x": 0.0, "accel_y": 0.0, "accel_z": 0.0,
                 "gyro_x": 0.0, "gyro_y": 0.0, "gyro_z": 0.0, "sensor_ts_ticks": 0}

def test_accel_scale_conversion():
    b = bytearray(64)
    struct.pack_into("<h", b, OFF_ACCEL_X, 8192)  # +1g on X
    r = parse_imu(bytes(b))
    assert abs(r["accel_x"] - 1.0) < 1e-9

def test_negative_accel_and_gyro():
    b = bytearray(64)
    struct.pack_into("<h", b, OFF_ACCEL_Z, -8192)   # -1g on Z (gravity when face-down-ish)
    struct.pack_into("<h", b, OFF_GYRO_Y, -500)
    r = parse_imu(bytes(b))
    assert abs(r["accel_z"] - (-1.0)) < 1e-9
    assert abs(r["gyro_y"] - (-0.5)) < 1e-9   # -500 raw / 1000.0 (grok r03: matches emulator scaling)

def test_all_six_axes_independent():
    b = bytearray(64)
    vals = {OFF_ACCEL_X: 100, OFF_ACCEL_Y: 200, OFF_ACCEL_Z: 300,
            OFF_GYRO_X: 10, OFF_GYRO_Y: 20, OFF_GYRO_Z: 30}
    for off, v in vals.items():
        struct.pack_into("<h", b, off, v)
    r = parse_imu(bytes(b))
    assert abs(r["accel_x"] - 100/ACCEL_SCALE) < 1e-9
    assert abs(r["accel_y"] - 200/ACCEL_SCALE) < 1e-9
    assert abs(r["accel_z"] - 300/ACCEL_SCALE) < 1e-9
    assert abs(r["gyro_x"] - 0.01) < 1e-9
    assert abs(r["gyro_y"] - 0.02) < 1e-9
    assert abs(r["gyro_z"] - 0.03) < 1e-9

def test_exactly_28_bytes_is_the_floor():
    b = bytearray(28)
    struct.pack_into("<h", b, OFF_GYRO_Z, 4200)
    r = parse_imu(bytes(b))
    assert abs(r["gyro_z"] - 4.2) < 1e-9

def test_sensor_ts_ticks_needs_32_bytes():
    b27 = bytearray(27)
    assert parse_imu(bytes(b27))["sensor_ts_ticks"] == 0
    b31 = bytearray(31)  # len<32 -> ticks never read even though a fake write COULD sit at [28:31]
    assert parse_imu(bytes(b31))["sensor_ts_ticks"] == 0
    b32 = bytearray(32)
    struct.pack_into("<I", b32, OFF_SENSOR_TS, 123456789)
    assert parse_imu(bytes(b32))["sensor_ts_ticks"] == 123456789
