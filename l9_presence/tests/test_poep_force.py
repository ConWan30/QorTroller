"""Tests for PoEP P4a adaptive-trigger force-challenge logic (no hardware)."""
from l9_presence.poep_force import extract_force_features, force_auth_delta


def _ramp(rise_ms, hold_ms=300, dt=2):
    """R2 trajectory ramping 0->255 over rise_ms, then holding at 255."""
    traj = []
    t = 0
    while t <= rise_ms:
        traj.append({"t_ms": float(t), "r2": min(255.0, 255.0 * t / rise_ms)})
        t += dt
    while t <= rise_ms + hold_ms:
        traj.append({"t_ms": float(t), "r2": 255.0})
        t += dt
    return traj


def test_extract_force_features_basic():
    f = extract_force_features(_ramp(100))
    assert f["peak_r2"] == 255.0
    assert 90 <= f["rise_time_ms"] <= 110
    assert f["mean_slope"] > 0 and f["plateau_r2"] > 200


def test_force_delta_detects_resistance():
    on = extract_force_features(_ramp(300))    # resistance -> slow ramp
    off = extract_force_features(_ramp(100))   # no resistance -> fast ramp
    d = force_auth_delta(on, off)
    assert d["adaptive_response_detected"] is True
    assert d["slope_off"] > d["slope_on"]      # no-resistance ramps faster


def test_force_delta_none_when_identical():
    f = extract_force_features(_ramp(150))
    d = force_auth_delta(f, f)
    assert d["adaptive_response_detected"] is False   # emulator: ON==OFF


def test_force_delta_handles_flat_emulator():
    flat = extract_force_features([{"t_ms": float(t), "r2": 0.0} for t in range(0, 600, 2)])
    d = force_auth_delta(flat, flat)
    assert d["adaptive_response_detected"] is False


def test_force_delta_incomplete_press_not_misleading():
    # one phase has no real press (slope ~0) -> incomplete, delta 0 (NOT a misleading high value)
    on = extract_force_features([{"t_ms": float(t), "r2": 0.0} for t in range(0, 600, 2)])  # no press
    off = extract_force_features(_ramp(100))                                                  # real press
    d = force_auth_delta(on, off)
    assert d["incomplete"] is True
    assert d["delta"] == 0.0 and d["adaptive_response_detected"] is False
