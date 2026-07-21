"""Composite-B Thesis C — optical co-presence checker (CANDIDATE, advisory). SESSION-BINDING, not
human-proof. Adversary-reviewed (grok optical r02: F1+F2 BLOCK adopted).

WHAT THIS ACTUALLY PROVES (grok F2 — do NOT over-claim past this):
  That the controller input stream is **coupled to the CURRENT live game session's events** — i.e.
  session co-presence. A dump replay of a *different* session's inputs fails (its inputs responded to
  a different game). This is the anti-replay signal that lets `realplay_liveness` reach the
  replay-resistant CONTINUOUS_PRESENT tier for dump-replay-of-another-session.

WHAT THIS DOES **NOT** PROVE (first-class residuals, grok F2/F3):
  * NOT humanity / NOT anti-macro. A "press on every snap" macro, or a vision→HID bot timed to the
    live feed, is event-coupled and passes BY DESIGN — this metric's positive class is session
    co-presence, not a live human. Anti-macro/anti-bot is L6b/PoEP/G3-G5 territory, not this function.
  * NOT identity.
  * A coordinated HID+video re-encode driving a matching live video (F19 class) is a higher-bar
    residual, out of v0.
  So the honest field name is `event_coupled` / session-bound, never "involuntary" or "live human".

THE NULL MODEL (grok F1 — analytic uniform chance was gameable by PERIODIC structure):
  Football events are quasi-periodic (snaps ~25-40s apart), so a periodic input pattern at a lucky
  phase beats a uniform-random chance baseline. Fixed: the baseline is now an EMPIRICAL circular-shift
  null — the observed responses are circularly shifted through many phases (preserving their internal
  spacing/structure), hit-rate recomputed at each phase; the real (unshifted) hit-rate must exceed a
  high quantile of that null. A periodic macro's real phase is not a significant outlier against its
  own shifted phases → correctly NOT flagged. A genuinely event-locked stream is.

SCOPE: pure, deterministic (systematic shifts, no RNG), no bridge/hardware imports, fail-closed.
Thresholds are CANDIDATE (U3 measurement-gated). Advisory — returns a bool + diagnostics, flips nothing.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional

# CANDIDATE thresholds (hypotheses — U3 measurement-gated, NOT calibrated)
REACTION_WINDOW_MS: tuple[float, float] = (150.0, 600.0)  # response band after a game event
MIN_EVENTS: int = 8            # below this the score is not defensible -> fail-closed (F4: may be a
                               #   multi-window / session-aggregate count in practice, not one 120s window)
MIN_ABS_HIT_RATE: float = 0.35  # observed hit-rate absolute floor
NULL_SHIFTS: int = 64          # number of systematic circular phases in the empirical null
NULL_QUANTILE: float = 0.95    # real hit-rate must beat this quantile of the shifted null
NULL_MIN_EXCESS: float = 0.15  # ...and beat the null MEDIAN by at least this absolute margin


@dataclass(frozen=True, slots=True)
class TimedEvent:
    ts_ms: float
    kind: str = ""


@dataclass(frozen=True, slots=True)
class OpticalCoPresenceResult:
    event_coupled: bool          # session co-presence (NOT humanity — see module docstring)
    reason: str
    n_events: int
    hit_rate: float
    null_q: float                # the NULL_QUANTILE-th quantile of the circular-shift null
    null_median: float
    def to_dict(self) -> dict:
        return {
            # NB: field is `event_coupled`, consumed as optical_consistent — session-bound, not human
            "event_coupled": self.event_coupled,
            "reason": self.reason,
            "n_events": self.n_events,
            "hit_rate": round(self.hit_rate, 4),
            "null_q": round(self.null_q, 4),
            "null_median": round(self.null_median, 4),
            "claim": "session_co_presence_not_humanity",
        }


def _hit_rate(event_ts: list[float], resp_ts: list[float], lo: float, hi: float) -> float:
    if not event_ts:
        return 0.0
    aligned = 0
    for e in event_ts:
        w0, w1 = e + lo, e + hi
        # resp_ts sorted; linear scan is fine at these sizes
        if any(w0 <= r <= w1 for r in resp_ts):
            aligned += 1
    return aligned / len(event_ts)


def _quantile(xs: list[float], q: float) -> float:
    if not xs:
        return 0.0
    s = sorted(xs)
    idx = min(len(s) - 1, max(0, int(round(q * (len(s) - 1)))))
    return s[idx]


def optical_copresence(
    game_events: Iterable[TimedEvent],
    input_responses: Iterable[TimedEvent],
    reaction_window_ms: tuple[float, float] = REACTION_WINDOW_MS,
    min_events: int = MIN_EVENTS,
    min_abs_hit_rate: float = MIN_ABS_HIT_RATE,
    n_shifts: int = NULL_SHIFTS,
    null_quantile: float = NULL_QUANTILE,
    null_min_excess: float = NULL_MIN_EXCESS,
) -> OpticalCoPresenceResult:
    """True iff the input responses are event-coupled to THIS session's events beyond an empirical
    circular-shift null (F1). Session co-presence only — not humanity (F2)."""
    events = sorted(e.ts_ms for e in game_events)
    responses = sorted(r.ts_ms for r in input_responses)
    lo, hi = reaction_window_ms

    if len(events) < min_events:
        return OpticalCoPresenceResult(False, f"too few game events ({len(events)}<{min_events})",
                                       len(events), 0.0, 0.0, 0.0)
    if not responses:
        return OpticalCoPresenceResult(False, "no input responses", len(events), 0.0, 0.0, 0.0)

    real = _hit_rate(events, responses, lo, hi)

    # F5: span from the response support only (an adversary can't pad it to shrink the baseline).
    r_span = responses[-1] - responses[0]
    if r_span <= 0:
        return OpticalCoPresenceResult(False, "degenerate response span", len(events), real, 0.0, 0.0)

    # F8 FIX (grok optical r04): wrap period must be r_span + one mean-gap, NOT r_span. Modulo by
    # r_span collapses the first/last point of a regular grid onto each other (n -> n-1 unique),
    # corrupting the null. period = n * mean_gap keeps all n points distinct through every phase.
    r0 = responses[0]
    n_resp = len(responses)
    mean_gap = r_span / (n_resp - 1) if n_resp > 1 else r_span
    period = r_span + mean_gap
    null: list[float] = []
    for k in range(1, n_shifts + 1):
        off = (k / (n_shifts + 1)) * period
        shifted = sorted(r0 + ((r - r0 + off) % period) for r in responses)
        null.append(_hit_rate(events, shifted, lo, hi))
    null_q = _quantile(null, null_quantile)
    null_med = _quantile(null, 0.5)

    coupled = (
        real >= min_abs_hit_rate
        and real > null_q
        and real >= null_med + null_min_excess
    )
    reason = (
        f"hit_rate={real:.2f} vs null_q{null_quantile:.2f}={null_q:.2f} null_med={null_med:.2f} "
        f"floor={min_abs_hit_rate} -> "
        f"{'session-coupled (not human-proof)' if coupled else 'at-null (dump-replay/uncoupled)'}"
    )
    return OpticalCoPresenceResult(coupled, reason, len(events), real, null_q, null_med)


# F6/F9/F10 (grok optical r04): the empirical null is a REAL test only once its thresholds are
# calibrated against measured NCAA snap-interval + reaction-lag distributions (U3). Until then the
# n~8-12 hit-rate lattice does not give an honest alpha-level p-value, and event spacing/thresholds
# are unvalidated. So the flag that can flip the replay-resistant CONTINUOUS tier is FAIL-CLOSED:
# it returns False unless `calibrated=True` is explicitly passed (which only happens post-U3).
OPTICAL_CALIBRATED_DEFAULT: bool = False


def optical_consistent_flag(
    game_events: Iterable[TimedEvent],
    input_responses: Iterable[TimedEvent],
    calibrated: bool = OPTICAL_CALIBRATED_DEFAULT,
    **kw,
) -> Optional[bool]:
    """The `optical_consistent` value fed to `realplay_liveness.WindowFeatures.optical_consistent`.
    Session co-presence, not humanity.

    FAIL-CLOSED CALIBRATION GATE: returns False unless `calibrated=True`. Rationale (grok optical
    r04 F6/F9/F10): the thresholds are CANDIDATE and statistically uncalibrated at the football
    event regime; until U3 measurement validates them at an honest alpha level, this must NOT flip
    the replay-resistant CONTINUOUS_PRESENT tier. So in production today CONTINUOUS stays unreachable
    and the composite caps at PARTIAL — the honest, fail-closed posture. The underlying
    `optical_copresence()` result is still available (advisory/diagnostic) for measurement + review."""
    if not calibrated:
        return False
    return optical_copresence(game_events, input_responses, **kw).event_coupled
