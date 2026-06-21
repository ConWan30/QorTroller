"""Tests for the probe firing gate + haptic self-echo (pure logic)."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from bridge.controller.probe_gate import (  # noqa: E402
    GateConfig,
    GateSample,
    GateState,
    accel_variance,
    any_trigger,
    classify,
    clear_to_fire,
    echo_confirmed,
    stick_span,
    update_baseline,
)

CFG = GateConfig()


def _still(n=8, accel=1.0):
    """A quiet window: centred sticks, no trigger, flat accel."""
    return [GateSample(lx=128, ly=128, l2=0, r2=0, accel_mag=accel) for _ in range(n)]


# ---- primitives ----

def test_stick_span_still_vs_moving():
    assert stick_span(_still()) == 0.0
    win = [GateSample(lx=128), GateSample(lx=200), GateSample(lx=120)]
    assert stick_span(win) == 80.0


def test_any_trigger():
    assert any_trigger(_still(), CFG.trigger_floor) is False
    assert any_trigger(_still() + [GateSample(r2=200)], CFG.trigger_floor) is True


def test_accel_variance_flat_is_zero():
    assert accel_variance(_still()) == 0.0


# ---- classify ----

def test_lull_when_still_and_quiet():
    # flat accel == baseline -> within ratio -> LULL
    assert classify(_still(accel=1.0), baseline_var=0.0, cfg=CFG) is GateState.LULL


def test_active_when_trigger_engaged():
    win = _still()
    win[3] = GateSample(lx=128, ly=128, r2=200, accel_mag=1.0)  # R2 snap
    assert classify(win, baseline_var=1.0, cfg=CFG) is GateState.ACTIVE


def test_active_when_sticks_moving():
    win = [GateSample(lx=128 + (40 if i % 2 else -40), ly=128, accel_mag=1.0) for i in range(8)]
    assert classify(win, baseline_var=1.0, cfg=CFG) is GateState.ACTIVE


def test_unsettled_when_imu_loud_without_input():
    # sticks still, no trigger, but accel variance >> baseline -> residual rumble -> defer
    loud = [GateSample(lx=128, ly=128, accel_mag=(50.0 if i % 2 else -50.0)) for i in range(8)]
    assert classify(loud, baseline_var=1.0, cfg=CFG) is GateState.UNSETTLED


def test_unsettled_when_too_few_samples():
    assert classify(_still(n=2), baseline_var=1.0, cfg=CFG) is GateState.UNSETTLED


# ---- clear_to_fire ----

def test_clear_to_fire_only_in_lull():
    clear, state = clear_to_fire(_still(accel=1.0), baseline_var=1.0, cfg=CFG)
    assert clear is True and state is GateState.LULL
    win = _still(); win[2] = GateSample(r2=200)
    clear2, state2 = clear_to_fire(win, baseline_var=1.0, cfg=CFG)
    assert clear2 is False and state2 is GateState.ACTIVE


# ---- haptic self-echo ----

def test_echo_confirmed_when_buzz_registers():
    # during-challenge variance way above baseline -> the IMU saw our buzz
    assert echo_confirmed(during_var=100.0, baseline_var=1.0, cfg=CFG) is True


def test_echo_fails_when_no_physical_vibration():
    # commanded a buzz but IMU stayed at baseline -> relay/spoof/dead motor
    assert echo_confirmed(during_var=1.0, baseline_var=1.0, cfg=CFG) is False


def test_echo_handles_zero_baseline():
    # zero baseline must not divide-explode; any real vibration still confirms
    assert echo_confirmed(during_var=5.0, baseline_var=0.0, cfg=CFG) is True
    assert echo_confirmed(during_var=0.0, baseline_var=0.0, cfg=CFG) is False


# ---- baseline EMA ----

def test_update_baseline_seeds_then_smooths():
    b = update_baseline(None, 10.0)
    assert b == 10.0                       # seeds on first obs
    b2 = update_baseline(b, 20.0, alpha=0.5)
    assert b2 == 15.0                      # EMA toward new obs
