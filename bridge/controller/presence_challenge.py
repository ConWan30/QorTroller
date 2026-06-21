"""Forceful, DISTINGUISHABLE presence-challenge stimulus + scheduler.

Phase 2 capture needs a presence challenge the operator can FEEL and unmistakably
tell apart from NCAA CFB 26's ambient haptics while playing. The default L6B probe
is deliberately sub-perceptual (force ~60/255) — the OPPOSITE of what we need here.
This builds a VOLUNTARY, high-amplitude, signature-cadence challenge:

  - HIGH force on BOTH adaptive triggers (default 230/255) — well above the
    sub-perceptual floor, so it is consciously felt.
  - A SIGNATURE TRIPLE-PULSE cadence (full-force kick / off / kick / off / kick)
    on BOTH triggers simultaneously. NCAA CFB drives mostly the main rumble motors
    (tackles) and a steady R2 sprint resistance — it does NOT produce a synchronized
    full-amplitude triple-kick on both triggers, so the pattern is recognisable.

HONESTY: "forceful enough" and "distinguishable" are PERCEPTUAL — they can only be
certified by the operator feeling it on the controller (scripts/presence_challenge_feeltest.py).
The invariants here (`is_forceful`, `is_signature`) are PROXIES that encode the
design intent in a testable way; the floor is a tunable guess, the feel-test is
authoritative. Reuses the real driver profile type (l6_challenge_profiles).
"""
from __future__ import annotations

from dataclasses import dataclass

from .l6_challenge_profiles import TRIGGER_PULSE, TriggerChallengeProfile

# Tunable proxy for "consciously felt." The feel-test, not this number, is the
# real arbiter. 230/255 ~ 90%; sub-perceptual L6B is 60/255 ~ 24%.
PERCEPTIBLE_FLOOR = 160
DEFAULT_FORCE = 230
DEFAULT_PULSES = 3
PRESENCE_CHALLENGE_PROFILE_ID = 901  # sentinel, outside the 0-7 calibrated set


def _pulse_pattern(force: int, pulses: int) -> tuple[int, ...]:
    """[force, 0, force, 0, ...] with `pulses` nonzero kicks, padded to 7 slots."""
    seq: list[int] = []
    for _ in range(pulses):
        seq.extend((force, 0))
    seq = seq[:7]
    seq += [0] * (7 - len(seq))
    return tuple(seq)


def forceful_signature_profile(force: int = DEFAULT_FORCE,
                               pulses: int = DEFAULT_PULSES) -> TriggerChallengeProfile:
    """A high-force triple-pulse on BOTH triggers — felt + recognisable in-game."""
    force = max(0, min(255, int(force)))
    pulses = max(1, min(3, int(pulses)))  # <=3 kicks fit in 7 slots as kick/off pairs
    pat = _pulse_pattern(force, pulses)
    return TriggerChallengeProfile(
        profile_id=PRESENCE_CHALLENGE_PROFILE_ID,
        name="PRESENCE_CHALLENGE_FORCEFUL",
        r2_mode=TRIGGER_PULSE, r2_forces=pat,
        l2_mode=TRIGGER_PULSE, l2_forces=pat,
        onset_threshold_ms=450.0,    # VOLUNTARY reaction band (conscious, not reflex)
        settle_threshold_ms=1200.0,
        description=f"Forceful presence challenge — {pulses}x{force}/255 dual-trigger signature pulse",
    )


def is_forceful(profile: TriggerChallengeProfile, floor: int = PERCEPTIBLE_FLOOR) -> bool:
    """Proxy: both triggers active AND peak force >= floor (consciously-felt design)."""
    r2_peak = max(profile.r2_forces) if profile.r2_forces else 0
    l2_peak = max(profile.l2_forces) if profile.l2_forces else 0
    return r2_peak >= floor and l2_peak >= floor


def is_signature(profile: TriggerChallengeProfile, min_pulses: int = 3) -> bool:
    """Proxy: a multi-kick PULSE cadence on both triggers (not a steady resistance
    the game could mimic)."""
    if profile.r2_mode != TRIGGER_PULSE or profile.l2_mode != TRIGGER_PULSE:
        return False
    r2_kicks = sum(1 for f in profile.r2_forces if f > 0)
    l2_kicks = sum(1 for f in profile.l2_forces if f > 0)
    return r2_kicks >= min_pulses and l2_kicks >= min_pulses


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
            # arm relative to now so the first challenge isn't instantaneous
            if rng is not None:
                self.schedule_next(now, rng)
            return False
        return now >= self._next_fire_at
