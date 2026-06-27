"""QorTroller × Trio-Retina — INPUT<->OUTCOME causal-coherence fusion (pure logic).

The novel, QorTroller-exclusive fusion: bind the controller lobe (INPUT world model, the
cryptographically-anchored 1 kHz HID retina) to the screen lobe (OUTCOME world model, OCR
of the HUD) and check CAUSALITY -- every on-screen outcome (down advanced, first down,
score change) must be preceded, within a play-length window, by a controller-input event
sequence from THIS device that plausibly produces it.

Why exclusive: screen-OCR alone is ordinary vision anti-cheat. The moat is binding the
outcome stream to a CERTIFIED input world-model. The fusion catches:
  * replay-to-headless -> inputs but no screen outcomes (ORPHAN_INPUT, informational)
  * relay / spectator   -> screen outcomes with no explaining input -> ORPHAN_OUTCOME (flag)
  * a live human        -> outcomes matched to preceding inputs    -> COHERENT

This generalizes L9/PoCP (stick->camera coupling) to input-trajectory -> game-outcome
semantics. Pure over a normalized TimedEvent stream so it is fully testable without the
retina library or any controller. UNCALIBRATED: the causal map + window are a HYPOTHESIS;
real co-capture is needed before any calibrated score (mirrors the consistency engine's
UNCALIBRATED_SYNTHETIC posture). Default-off; no FROZEN/PoAC/chain touch.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

from .retina_screen_lobe import ScreenEvent, is_input_caused

# Controller (input) event types that count as "a plausible play action".
INPUT_EVENT_TYPES = frozenset({
    "controller.trigger.onset",     # R2 sprint / L2 — a snap/pass/kick action
    "controller.stick.radial_jump", # a deliberate stick move (juke, aim, throw)
})

DEFAULT_CAUSAL_WINDOW_S = 10.0  # play + whistle + HUD settle; an outcome must be input-caused within this


class CoherenceVerdict(str, Enum):
    COHERENT = "COHERENT"               # outcomes explained by preceding input
    ORPHAN_OUTCOME = "ORPHAN_OUTCOME"   # screen advanced with no explaining input -> relay/replay/spectator
    ORPHAN_INPUT = "ORPHAN_INPUT"       # input present but ~no outcomes (informational; not a cheat by itself)
    INSUFFICIENT = "INSUFFICIENT"       # too little evidence to judge


@dataclass(frozen=True)
class TimedEvent:
    kind: str   # "input" | "outcome"
    type: str
    t: float
    input_caused: bool = True  # for outcomes: whether causality is required (markers -> False)


@dataclass(frozen=True)
class OutcomeMatch:
    outcome: TimedEvent
    matched: bool
    nearest_input_dt: Optional[float]  # seconds between matching input and the outcome (None if orphan)


@dataclass(frozen=True)
class CoherenceReport:
    verdict: CoherenceVerdict
    matches: list[OutcomeMatch] = field(default_factory=list)
    n_outcomes_required: int = 0      # outcomes that require an input cause
    n_matched: int = 0
    n_inputs: int = 0

    def coherence_ratio(self) -> float:
        return self.n_matched / self.n_outcomes_required if self.n_outcomes_required else 0.0

    def to_dict(self) -> dict:
        return {
            "schema": "vapi-retina-causal-coherence-v1",
            "calibration": "UNCALIBRATED",  # causal map + window are a hypothesis until co-capture
            "verdict": self.verdict.value,
            "coherence_ratio": round(self.coherence_ratio(), 4),
            "n_outcomes_required": self.n_outcomes_required,
            "n_matched": self.n_matched,
            "n_orphan_outcomes": self.n_outcomes_required - self.n_matched,
            "n_inputs": self.n_inputs,
        }


def from_controller_events(events: list[Any]) -> list[TimedEvent]:
    """Normalize retina controller Events (or dicts) -> input TimedEvents."""
    out: list[TimedEvent] = []
    for e in events:
        etype = e.get("type") if isinstance(e, dict) else getattr(e, "type", "")
        t = e.get("t") if isinstance(e, dict) else getattr(e, "t", None)
        if etype in INPUT_EVENT_TYPES and t is not None:
            out.append(TimedEvent(kind="input", type=etype, t=float(t)))
    return out


def from_screen_events(events: list[ScreenEvent]) -> list[TimedEvent]:
    """Normalize ScreenEvents -> outcome TimedEvents (carry the input_caused flag)."""
    return [TimedEvent(kind="outcome", type=e.type, t=float(e.t),
                       input_caused=e.input_caused) for e in events]


@dataclass(frozen=True)
class CoherenceConfig:
    window_s: float = DEFAULT_CAUSAL_WINDOW_S
    min_outcomes: int = 3          # below this -> INSUFFICIENT
    coherent_ratio: float = 0.7    # >= this matched fraction -> COHERENT
    orphan_input_floor: int = 5    # inputs >= this with 0 required-outcomes -> ORPHAN_INPUT


def assess_coherence(events: list[TimedEvent],
                     cfg: CoherenceConfig = CoherenceConfig()) -> CoherenceReport:
    """Match each input-caused outcome to a controller input within [t-window, t].

    An outcome is COHERENT if at least one qualifying input precedes it inside the causal
    window. Markers (input_caused=False, e.g. quarter change) are ignored for causality."""
    inputs = sorted((e.t for e in events if e.kind == "input"))
    required = [e for e in events if e.kind == "outcome" and e.input_caused]
    n_inputs = len(inputs)

    matches: list[OutcomeMatch] = []
    n_matched = 0
    for oc in required:
        nearest_dt: Optional[float] = None
        for it in inputs:
            if oc.t - cfg.window_s <= it <= oc.t:
                dt = oc.t - it
                if nearest_dt is None or dt < nearest_dt:
                    nearest_dt = dt
        matched = nearest_dt is not None
        n_matched += int(matched)
        matches.append(OutcomeMatch(outcome=oc, matched=matched, nearest_input_dt=nearest_dt))

    n_req = len(required)
    if n_req < cfg.min_outcomes:
        # not enough outcomes to judge causality; flag ORPHAN_INPUT only if input is heavy
        if n_inputs >= cfg.orphan_input_floor and n_req == 0:
            verdict = CoherenceVerdict.ORPHAN_INPUT
        else:
            verdict = CoherenceVerdict.INSUFFICIENT
        return CoherenceReport(verdict, matches, n_req, n_matched, n_inputs)

    ratio = n_matched / n_req
    if ratio >= cfg.coherent_ratio:
        verdict = CoherenceVerdict.COHERENT
    else:
        verdict = CoherenceVerdict.ORPHAN_OUTCOME  # outcomes the certified device didn't drive
    return CoherenceReport(verdict, matches, n_req, n_matched, n_inputs)
