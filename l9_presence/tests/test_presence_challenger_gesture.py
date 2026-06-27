"""Tests for the challenger's dual-gesture acceptance (pure; no controller/pydualsense)."""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from scripts.presence_challenger import (  # noqa: E402
    format_selftest_line,
    gesture_active_from_state,
    parse_accepted,
    run_selftest,
)
from bridge.controller.probe_gate import GateConfig, GateSample  # noqa: E402


def _state(*, l5=False, r5=False, l4=False, r4=False, touch=False):
    return SimpleNamespace(
        L5=l5, R5=r5, L4=l4, R4=r4,
        trackPadTouch0=SimpleNamespace(isActive=touch),
    )


# ---- parse_accepted ----

def test_parse_single():
    assert parse_accepted("l5") == ["l5"]


def test_parse_dual_plus():
    assert parse_accepted("l5+touch") == ["l5", "touch"]


def test_parse_comma_and_swipe_alias():
    assert parse_accepted("r5,swipe") == ["r5", "touch"]
    assert parse_accepted("touchpad") == ["touch"]


def test_parse_dedupes_and_defaults():
    assert parse_accepted("l5+l5") == ["l5"]
    assert parse_accepted("") == ["l5"]      # back-compat default
    assert parse_accepted("  ") == ["l5"]


def test_parse_rejects_unknown():
    with pytest.raises(ValueError):
        parse_accepted("cross")
    with pytest.raises(ValueError):
        parse_accepted("l5+square")


# ---- gesture_active_from_state (the dual OR) ----

def test_l5_only_accepts_l5_not_touch():
    acc = ["l5"]
    assert gesture_active_from_state(_state(l5=True), acc) is True
    assert gesture_active_from_state(_state(touch=True), acc) is False
    assert gesture_active_from_state(_state(), acc) is False


def test_dual_accepts_either():
    acc = ["l5", "touch"]
    assert gesture_active_from_state(_state(l5=True), acc) is True     # paddle
    assert gesture_active_from_state(_state(touch=True), acc) is True  # touchpad
    assert gesture_active_from_state(_state(l5=True, touch=True), acc) is True
    assert gesture_active_from_state(_state(), acc) is False           # neither


def test_dual_does_not_accept_unlisted_button():
    # r5 not in the accepted set -> pressing R5 is NOT a response
    assert gesture_active_from_state(_state(r5=True), ["l5", "touch"]) is False


def test_missing_touch_attr_is_safe():
    bare = SimpleNamespace(L5=False)  # no trackPadTouch0 attribute at all
    assert gesture_active_from_state(bare, ["l5", "touch"]) is False


# ---- --selftest diagnostic ----

CFG = GateConfig()


def test_selftest_line_lull_when_still():
    still = [GateSample(lx=128, ly=128, l2=0, r2=0, accel_mag=1.0) for _ in range(8)]
    line = format_selftest_line(still[-1], still, baseline_var=1.0, gate_cfg=CFG)
    assert "LULL" in line and "CLEAR-to-fire" in line


def test_selftest_line_active_when_trigger():
    win = [GateSample(lx=128, ly=128, l2=0, r2=0, accel_mag=1.0) for _ in range(8)]
    win[4] = GateSample(lx=128, ly=128, r2=200, accel_mag=1.0)
    line = format_selftest_line(win[-1], win, baseline_var=1.0, gate_cfg=CFG)
    assert "ACTIVE" in line and "defer" in line


class _FakeDS:
    """Minimal pydualsense-shaped controller for the read-only selftest loop."""
    def __init__(self, accel=(0.1, 0.0, 0.98)):
        self._a = accel

    @property
    def state(self):
        return SimpleNamespace(
            LX=128, LY=128, L2_value=0, R2_value=0,
            accelerometer=SimpleNamespace(X=self._a[0], Y=self._a[1], Z=self._a[2]),
            trackPadTouch0=SimpleNamespace(isActive=False),
        )


def test_run_selftest_imu_ok_returns_zero():
    rc = run_selftest(_FakeDS(accel=(0.1, 0.0, 0.98)), 0.3, CFG, hz=200.0, print_hz=20.0)
    assert rc == 0  # non-zero accel exposed


def test_run_selftest_imu_absent_returns_one():
    rc = run_selftest(_FakeDS(accel=(0.0, 0.0, 0.0)), 0.3, CFG, hz=200.0, print_hz=20.0)
    assert rc == 1  # IMU not exposed -> warning + nonzero exit
