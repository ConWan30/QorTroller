"""Tests for the forceful presence-challenge stimulus + scheduler (pure logic).

These encode the DESIGN intent (forceful + signature cadence + idle-gated jitter).
They do NOT certify perceptual forcefulness — only the operator feel-test does.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from bridge.controller.presence_challenge import (  # noqa: E402
    PERCEPTIBLE_FLOOR,
    ChallengeScheduler,
    _pulse_pattern,
    forceful_signature_profile,
    is_forceful,
    is_signature,
)


class _Rng:
    def __init__(self, v): self.v = v
    def uniform(self, a, b): return self.v


def test_pulse_pattern_shape():
    assert _pulse_pattern(230, 3) == (230, 0, 230, 0, 230, 0, 0)
    assert _pulse_pattern(200, 1) == (200, 0, 0, 0, 0, 0, 0)
    assert len(_pulse_pattern(255, 3)) == 7


def test_default_profile_is_forceful_and_signature():
    p = forceful_signature_profile()
    assert is_forceful(p) is True
    assert is_signature(p) is True
    assert max(p.r2_forces) == 230 and max(p.l2_forces) == 230
    # both triggers carry the triple-kick (gameplay can't sync this)
    assert sum(1 for f in p.r2_forces if f > 0) == 3
    assert sum(1 for f in p.l2_forces if f > 0) == 3


def test_subperceptual_force_is_not_forceful():
    # the default L6B level (~60) must NOT pass the forceful proxy
    p = forceful_signature_profile(force=60, pulses=3)
    assert max(p.r2_forces) == 60
    assert is_forceful(p) is False        # 60 < PERCEPTIBLE_FLOOR
    assert 60 < PERCEPTIBLE_FLOOR


def test_force_clamped_and_bounded():
    assert max(forceful_signature_profile(force=999).r2_forces) == 255
    assert max(forceful_signature_profile(force=-5).r2_forces) == 0


def test_scheduler_idle_gate_never_fires_when_idle():
    s = ChallengeScheduler()
    # idle -> never fire, regardless of timing
    assert s.should_fire(now=10_000.0, recent_active=False, rng=_Rng(0.0)) is False


def test_scheduler_arms_lazily_then_fires_when_due():
    s = ChallengeScheduler(interval_s=30.0, jitter_s=10.0, min_interval_s=20.0)
    # first active call arms the window (no instant challenge)
    assert s.should_fire(now=100.0, recent_active=True, rng=_Rng(0.0)) is False
    assert s._next_fire_at == 130.0        # 100 + (30 + uniform=0)
    assert s.should_fire(now=125.0, recent_active=True) is False   # not due
    assert s.should_fire(now=130.0, recent_active=True) is True    # due


def test_scheduler_clamps_jitter_to_min_interval():
    s = ChallengeScheduler(interval_s=30.0, jitter_s=20.0, min_interval_s=20.0)
    # jitter -20 -> 10s, clamped up to the 20s min
    assert s.schedule_next(now=0.0, rng=_Rng(-20.0)) == 20.0
