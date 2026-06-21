"""Forceful, DISTINGUISHABLE presence-challenge stimulus (MAIN-MOTOR signature) + scheduler.

Design history / honest correction: the first version used adaptive-TRIGGER resistance.
On real hardware that is only felt when you PULL the trigger — useless as a stimulus you
must passively react to mid-play. Confirmed 2026-06-21 on a real Edge: the MAIN RUMBLE
MOTORS are felt strongly in the palms regardless of trigger/finger position. So the
challenge is a main-motor SIGNATURE CADENCE:

  - HIGH amplitude (default 255/255) — unmistakably felt.
  - A SIGNATURE multi-pulse cadence (default 3 sharp equal pulses with crisp gaps), so it
    reads as "that specific bzz-bzz-bzz challenge," distinct from NCAA CFB's irregular,
    contextual tackle rumble. Optional `alternate` does a left/right sweep for an even more
    distinct, non-gameplay pattern.

HONESTY: "forceful enough" and "distinguishable" are PERCEPTUAL — certified only by the
operator feeling it (scripts/presence_challenge_feeltest.py). `is_forceful`/`is_signature`
are testable proxies for the design intent; the operator's feel-test is authoritative.
"""
from __future__ import annotations

from dataclasses import dataclass

# Tunable proxy for "consciously felt." The feel-test, not this number, is the arbiter.
PERCEPTIBLE_FLOOR = 160
DEFAULT_AMP = 255
DEFAULT_PULSES = 3
DEFAULT_ON_MS = 200
DEFAULT_OFF_MS = 180


@dataclass(frozen=True)
class MotorSignature:
    """A main-motor rumble challenge cadence. amp 0-255 on left/right motors."""
    amp: int = DEFAULT_AMP
    pulses: int = DEFAULT_PULSES
    on_ms: int = DEFAULT_ON_MS
    off_ms: int = DEFAULT_OFF_MS
    alternate: bool = False  # left/right sweep instead of both-motors-together

    def steps(self) -> list[tuple[int, int, float]]:
        """Expand to [(left_amp, right_amp, duration_s), ...] for delivery."""
        out: list[tuple[int, int, float]] = []
        for i in range(self.pulses):
            if self.alternate:
                left = self.amp if i % 2 == 0 else 0
                right = self.amp if i % 2 == 1 else 0
            else:
                left = right = self.amp
            out.append((left, right, self.on_ms / 1000.0))
            out.append((0, 0, self.off_ms / 1000.0))
        return out

    def duration_s(self) -> float:
        return self.pulses * (self.on_ms + self.off_ms) / 1000.0


def forceful_motor_signature(amp: int = DEFAULT_AMP, pulses: int = DEFAULT_PULSES,
                             alternate: bool = False) -> MotorSignature:
    amp = max(0, min(255, int(amp)))
    pulses = max(1, int(pulses))
    return MotorSignature(amp=amp, pulses=pulses, alternate=alternate)


def is_forceful(sig: MotorSignature, floor: int = PERCEPTIBLE_FLOOR) -> bool:
    """Proxy: amplitude at/above the consciously-felt floor."""
    return sig.amp >= floor


def is_signature(sig: MotorSignature, min_pulses: int = 3) -> bool:
    """Proxy: a multi-pulse cadence (not a single rumble the game could mimic)."""
    return sig.pulses >= min_pulses


@dataclass
class ChallengeScheduler:
    """Jittered periodic firing with an idle-gate (never challenge an idle player,
    mirroring L6TriggerDriver's 'never when idle' rule). Pure + injectable."""
    interval_s: float = 30.0
    jitter_s: float = 10.0
    min_interval_s: float = 20.0
    _next_fire_at: float | None = None

    def schedule_next(self, now: float, rng) -> float:
        delta = self.interval_s + rng.uniform(-self.jitter_s, self.jitter_s)
        delta = max(self.min_interval_s, delta)
        self._next_fire_at = now + delta
        return self._next_fire_at

    def should_fire(self, now: float, recent_active: bool, rng=None) -> bool:
        """True iff the player is active AND we are due. Arms the first window lazily."""
        if not recent_active:
            return False                      # idle-gate: never challenge an idle player
        if self._next_fire_at is None:
            if rng is not None:
                self.schedule_next(now, rng)
            return False
        return now >= self._next_fire_at
