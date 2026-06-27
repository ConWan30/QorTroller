"""Tests for the forceful presence-challenge MOTOR signature + scheduler (pure logic).

Encodes design intent (forceful amplitude + multi-pulse signature cadence + idle-gated
jitter). Does NOT certify perceptual forcefulness — only the operator feel-test does.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from bridge.controller.presence_challenge import (  # noqa: E402
    PERCEPTIBLE_FLOOR,
    ChallengeScheduler,
    classify_gesture_response,
    forceful_motor_signature,
    is_forceful,
    is_signature,
)


def test_gesture_in_band_is_human():
    # gesture first active at 200ms -> within [120,450] -> HUMAN/REFLEX_OBSERVED
    samples = [(50, False), (200, True), (260, True)]
    r = classify_gesture_response(samples)
    assert r["classification"] == "HUMAN" and r["reflex_verdict"] == "REFLEX_OBSERVED"
    assert r["latency_ms"] == 200


def test_gesture_too_fast_is_flagged():
    # active at 60ms -> faster than human floor -> TOO_FAST / anticipation, NOT human
    r = classify_gesture_response([(60, True), (200, True)])
    assert r["classification"] == "TOO_FAST" and r["anticipation"] is True
    assert r["reflex_verdict"] is None


def test_no_gesture_is_no_response():
    r = classify_gesture_response([(t, False) for t in (50, 150, 300, 440)])
    assert r["classification"] == "NO_RESPONSE" and r["reflex_verdict"] is None


def test_gesture_too_late_is_no_response():
    # first active only at 600ms -> outside band -> NO_RESPONSE (records latency)
    r = classify_gesture_response([(600, True)])
    assert r["classification"] == "NO_RESPONSE" and r["latency_ms"] == 600


class _Rng:
    def __init__(self, v): self.v = v
    def uniform(self, a, b): return self.v


def test_default_signature_forceful_and_signature():
    s = forceful_motor_signature()
    assert is_forceful(s) is True and is_signature(s) is True
    assert s.amp == 255 and s.pulses == 3


def test_steps_both_motors():
    s = forceful_motor_signature(amp=255, pulses=3)
    steps = s.steps()
    assert len(steps) == 6                       # on/off per pulse
    assert steps[0] == (255, 255, s.on_ms / 1000.0)   # both motors on
    assert steps[1] == (0, 0, s.off_ms / 1000.0)      # gap


def test_steps_alternate_sweep():
    s = forceful_motor_signature(amp=255, pulses=3, alternate=True)
    on_steps = [st for st in s.steps() if st[:2] != (0, 0)]
    assert on_steps[0][:2] == (255, 0)           # left
    assert on_steps[1][:2] == (0, 255)           # right
    assert on_steps[2][:2] == (255, 0)           # left


def test_low_amp_not_forceful():
    s = forceful_motor_signature(amp=60, pulses=3)
    assert is_forceful(s) is False and 60 < PERCEPTIBLE_FLOOR


def test_amp_clamped():
    assert forceful_motor_signature(amp=999).amp == 255
    assert forceful_motor_signature(amp=-5).amp == 0


def test_scheduler_idle_gate_never_fires_when_idle():
    s = ChallengeScheduler()
    assert s.should_fire(now=10_000.0, recent_active=False, rng=_Rng(0.0)) is False


def test_scheduler_arms_lazily_then_fires_when_due():
    s = ChallengeScheduler(interval_s=30.0, jitter_s=10.0, min_interval_s=20.0)
    assert s.should_fire(now=100.0, recent_active=True, rng=_Rng(0.0)) is False
    assert s._next_fire_at == 130.0
    assert s.should_fire(now=125.0, recent_active=True) is False
    assert s.should_fire(now=130.0, recent_active=True) is True


def test_scheduler_clamps_jitter_to_min_interval():
    s = ChallengeScheduler(interval_s=30.0, jitter_s=20.0, min_interval_s=20.0)
    assert s.schedule_next(now=0.0, rng=_Rng(-20.0)) == 20.0
