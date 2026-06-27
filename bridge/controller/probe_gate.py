"""Probe firing gate + haptic self-echo (pure logic; I/O lives in the challenger).

The challenger cannot see the PS5's OUTGOING haptic commands -- those are output reports
(PS5 -> controller). The only live signal that "a haptic is happening now" is the
controller's IMU registering the physical vibration. So the whole gate is built from the
INPUT stream the challenger already reads:

  1. LULL detection -- sustained still sticks + no trigger + quiet IMU = between-plays /
     pre-snap, the natural quiet window in NCAA CFB. Fire HERE, not mid-scramble.
  2. Pre-fire VETO -- if the IMU is loud (a rumble or violent motion is in progress),
     don't fire; reschedule. Scale-independent: window variance vs a rolling baseline,
     because the DualSense IMU scale is device-specific (see cocapture.py provisional note).
  3. HAPTIC SELF-ECHO (QorTroller-exclusive) -- after firing OUR motor signature, the IMU
     should show variance well above baseline DURING our pulses. `echo_confirmed` is the
     closed-loop proof the buzz physically fired on THIS device -- a presence-binding
     hardening against the relay attack (buzz device A, human reacts on device B).

Pure + injectable: every function operates on sampled features; no pydualsense, no I/O.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class GateState(str, Enum):
    LULL = "LULL"            # quiet between-plays / pre-snap -> clear to fire
    ACTIVE = "ACTIVE"        # live play (trigger or big stick motion) -> defer
    UNSETTLED = "UNSETTLED"  # loud IMU w/o input (residual rumble / handling) -> defer


@dataclass(frozen=True)
class GateSample:
    """One controller input frame, reduced to the gate-relevant fields."""
    lx: int = 128
    ly: int = 128
    l2: int = 0
    r2: int = 0
    accel_mag: float = 0.0   # |accel| (raw units; only RELATIVE magnitude matters here)


@dataclass(frozen=True)
class GateConfig:
    haptic_ratio: float = 3.0      # window accel var > baseline*ratio => haptic/motion => not quiet
    lull_stick_span: float = 8.0   # max stick travel (max-min) under this => sticks still
    trigger_floor: int = 12        # L2/R2 above this => a trigger is engaged
    min_samples: int = 4           # fewer than this => not enough info => fail-safe to UNSETTLED
    min_baseline_var: float = 1e-9 # floor so a zero/near-zero baseline can't divide-explode
    echo_ratio: float = 2.0        # during-challenge var > baseline*ratio => echo confirmed


def _variance(xs: list[float]) -> float:
    n = len(xs)
    if n < 2:
        return 0.0
    m = sum(xs) / n
    return sum((x - m) ** 2 for x in xs) / n


def accel_variance(window: list[GateSample]) -> float:
    return _variance([s.accel_mag for s in window])


def stick_span(window: list[GateSample]) -> float:
    """The larger of the lx-range and ly-range over the window (0 if still)."""
    if not window:
        return 0.0
    lxs = [s.lx for s in window]
    lys = [s.ly for s in window]
    return float(max(max(lxs) - min(lxs), max(lys) - min(lys)))


def any_trigger(window: list[GateSample], floor: int) -> bool:
    return any(s.l2 > floor or s.r2 > floor for s in window)


def is_input_quiet(window: list[GateSample], cfg: GateConfig = GateConfig()) -> bool:
    """True when the controller is not being actively USED (no trigger + sticks still),
    regardless of the IMU. Consumers feed the accel baseline from input-quiet windows so it
    tracks the resting accel-noise FLOOR — independent of whether a haptic is firing right
    now. This avoids the deadlock where the baseline only updates on LULL but an under-seeded
    baseline makes LULL unreachable, so the gate would defer forever."""
    if len(window) < cfg.min_samples:
        return False
    return not any_trigger(window, cfg.trigger_floor) and stick_span(window) <= cfg.lull_stick_span


def classify(window: list[GateSample], baseline_var: float,
             cfg: GateConfig = GateConfig()) -> GateState:
    """LULL / ACTIVE / UNSETTLED for a pre-fire window. Fail-safe: too little data or a
    loud IMU -> not LULL (defer), so we never fire blindly."""
    if len(window) < cfg.min_samples:
        return GateState.UNSETTLED
    if any_trigger(window, cfg.trigger_floor) or stick_span(window) > cfg.lull_stick_span:
        return GateState.ACTIVE
    base = max(baseline_var, cfg.min_baseline_var)
    if accel_variance(window) > base * cfg.haptic_ratio:
        return GateState.UNSETTLED  # rumble or violent motion in progress
    return GateState.LULL


def clear_to_fire(window: list[GateSample], baseline_var: float,
                  cfg: GateConfig = GateConfig()) -> tuple[bool, GateState]:
    """True only in a LULL. Returns (clear, state) so the caller can log WHY it deferred."""
    state = classify(window, baseline_var, cfg)
    return (state is GateState.LULL, state)


def echo_confirmed(during_var: float, baseline_var: float,
                   cfg: GateConfig = GateConfig()) -> bool:
    """HAPTIC SELF-ECHO: did the IMU physically witness our own buzz on THIS device?

    True iff accel variance measured DURING our motor signature exceeds the rolling
    baseline by `echo_ratio`. A failed echo means the commanded buzz did not register as
    physical vibration on the device we are reading -- the stimulus and the response
    channel are not the same physical controller (relay / spoof / dead motor)."""
    base = max(baseline_var, cfg.min_baseline_var)
    return during_var > base * cfg.echo_ratio


def update_baseline(baseline_var: float | None, window_var: float, alpha: float = 0.2) -> float:
    """EMA of accel variance over quiet windows -> the rolling 'quiet' reference. Seed on
    first observation. Only the caller decides which windows are quiet enough to feed in."""
    if baseline_var is None:
        return window_var
    return (1.0 - alpha) * baseline_var + alpha * window_var
