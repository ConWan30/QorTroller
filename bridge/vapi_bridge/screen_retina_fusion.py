"""QorTroller × Trio-Retina — tri-channel L9 screen-retina fusion (pure logic).

Revives the WGC screen-capture as the SHARED sensor of two screen channels that both
bind to the certified controller input lobe, at two timescales:

  * CONTINUOUS coupling (L9/PoCP, ~60 Hz): cv_motion optical flow -> coupling.py. Does the
    on-screen camera move BECAUSE the aim-stick moved, at human lag? (coupling_score), and
    how much motion is UNEXPLAINED by the stick? (decoupled_energy = injection/aimbot proxy).
    Honesty rail: a time-SHUFFLED negative control MUST collapse; if it doesn't, the coupling
    is a latency-search artifact, not causality.
  * DISCRETE outcome coherence (dual-lobe OCR, event-rate): retina_causal_coherence over OCR
    HUD outcomes vs controller input events. Do down/score advances follow input?

This module fuses the two ORTHOGONAL axes into one L9 verdict. It is pure over primitives +
the CoherenceVerdict (no l9_presence import, no I/O), so it is fully testable; the runner
feeds it `coupling.InputOutputCouplingOracle.extract_features()` + `negative_control()` and a
`retina_causal_coherence.CoherenceReport`.

Why exclusive: both axes bind to the SAME certified controller stream. An attacker must
satisfy independent causal bindings at two timescales simultaneously -- a video replay fakes
discrete OCR outcomes but the continuous coupling to the live stick collapses; an aimbot
keeps coupling but spikes decoupled_energy. UNCALIBRATED: thresholds are hypotheses until a
labelled co-capture experiment. Default-off; no FROZEN/PoAC/chain touch.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional

from .retina_causal_coherence import CoherenceVerdict

# coupling.py defaults (kept in sync; overridable per-call)
DEFAULT_COUPLING_THRESHOLD = 0.20   # min |causal r| for "camera tracks stick"
DEFAULT_NEG_CONTROL_GAP = 0.15      # coupling_score - negative_control must exceed this
DEFAULT_RESIDUAL_THRESHOLD = 0.60   # decoupled_energy at/above this = injection candidate


class ContinuousAxis(str, Enum):
    COUPLED_CLEAN = "COUPLED_CLEAN"    # camera tracks stick, neg-control collapsed, low residual
    COUPLED_INJECTION = "COUPLED_INJECTION"  # tracks stick BUT high unexplained residual (aimbot)
    DECOUPLED = "DECOUPLED"            # activity present but camera does NOT track stick / neg-control failed
    NEUTRAL = "NEUTRAL"                # not enough aim activity to judge (player not aiming)


class L9FusionVerdict(str, Enum):
    LIVE_COHERENT = "LIVE_COHERENT"          # coupling clean AND outcomes input-caused (strongest live)
    LIVE_COUPLED = "LIVE_COUPLED"            # coupling clean; outcome evidence insufficient
    INJECTION_SUSPECT = "INJECTION_SUSPECT"  # coupling clean-ish but high residual (aimbot candidate; provisional)
    REPLAY_OR_RELAY = "REPLAY_OR_RELAY"      # screen not driven by this controller (both axes say so)
    DECOUPLED_REVIEW = "DECOUPLED_REVIEW"    # axes contradict -> manual review
    INSUFFICIENT = "INSUFFICIENT"            # not enough evidence on either axis


@dataclass(frozen=True)
class ContinuousConfig:
    coupling_threshold: float = DEFAULT_COUPLING_THRESHOLD
    neg_control_gap: float = DEFAULT_NEG_CONTROL_GAP
    residual_threshold: float = DEFAULT_RESIDUAL_THRESHOLD


@dataclass(frozen=True)
class L9FusionReport:
    verdict: L9FusionVerdict
    continuous: ContinuousAxis
    coherence: CoherenceVerdict
    coupling_score: Optional[float]
    negative_control: Optional[float]
    decoupled_energy: Optional[float]
    coherence_ratio: float

    def to_dict(self) -> dict:
        return {
            "schema": "vapi-l9-screen-retina-fusion-v1",
            "calibration": "UNCALIBRATED",
            "verdict": self.verdict.value,
            "continuous_axis": self.continuous.value,
            "coherence_axis": self.coherence.value,
            "coupling_score": self.coupling_score,
            "negative_control": self.negative_control,
            "neg_control_gap": (None if self.coupling_score is None or self.negative_control is None
                                else round(self.coupling_score - self.negative_control, 4)),
            "decoupled_energy": self.decoupled_energy,
            "coherence_ratio": round(self.coherence_ratio, 4),
        }


def classify_continuous(coupling_score: Optional[float],
                        negative_control: Optional[float],
                        decoupled_energy: Optional[float],
                        cfg: ContinuousConfig = ContinuousConfig()) -> ContinuousAxis:
    """Continuous coupling axis. coupling_score None == oracle returned no features
    (player not aiming) -> NEUTRAL. The negative control MUST collapse (gap) or the
    coupling is treated as a latency-search artifact -> DECOUPLED."""
    if coupling_score is None:
        return ContinuousAxis.NEUTRAL
    neg = negative_control if negative_control is not None else 0.0
    collapsed = (coupling_score - neg) >= cfg.neg_control_gap
    if coupling_score >= cfg.coupling_threshold and collapsed:
        if decoupled_energy is not None and decoupled_energy >= cfg.residual_threshold:
            return ContinuousAxis.COUPLED_INJECTION
        return ContinuousAxis.COUPLED_CLEAN
    return ContinuousAxis.DECOUPLED  # activity but no clean causal tracking


def fuse_screen_retina(coupling_score: Optional[float],
                       negative_control: Optional[float],
                       decoupled_energy: Optional[float],
                       coherence: CoherenceVerdict,
                       coherence_ratio: float = 0.0,
                       cfg: ContinuousConfig = ContinuousConfig()) -> L9FusionReport:
    """Fuse the continuous coupling axis with the discrete outcome-coherence axis."""
    cont = classify_continuous(coupling_score, negative_control, decoupled_energy, cfg)

    if cont is ContinuousAxis.COUPLED_INJECTION:
        verdict = L9FusionVerdict.INJECTION_SUSPECT  # human drives camera + extra motion (aim-assist caveat)
    elif cont is ContinuousAxis.COUPLED_CLEAN:
        if coherence is CoherenceVerdict.COHERENT:
            verdict = L9FusionVerdict.LIVE_COHERENT
        elif coherence is CoherenceVerdict.ORPHAN_OUTCOME:
            verdict = L9FusionVerdict.DECOUPLED_REVIEW  # camera tracks stick yet HUD advances without input
        else:
            verdict = L9FusionVerdict.LIVE_COUPLED      # continuous proves presence; outcomes thin
    elif cont is ContinuousAxis.DECOUPLED:
        # activity present but camera does not causally track the stick
        if coherence is CoherenceVerdict.ORPHAN_OUTCOME:
            verdict = L9FusionVerdict.REPLAY_OR_RELAY   # both axes: screen not driven by this controller
        elif coherence is CoherenceVerdict.COHERENT:
            verdict = L9FusionVerdict.DECOUPLED_REVIEW  # contradiction -> review
        else:
            verdict = L9FusionVerdict.REPLAY_OR_RELAY   # decoupled camera + no input-caused outcomes
    else:  # NEUTRAL continuous (not aiming) -> rest on the discrete axis
        if coherence is CoherenceVerdict.COHERENT:
            verdict = L9FusionVerdict.LIVE_COHERENT
        elif coherence is CoherenceVerdict.ORPHAN_OUTCOME:
            verdict = L9FusionVerdict.REPLAY_OR_RELAY
        else:
            verdict = L9FusionVerdict.INSUFFICIENT

    return L9FusionReport(
        verdict=verdict, continuous=cont, coherence=coherence,
        coupling_score=coupling_score, negative_control=negative_control,
        decoupled_energy=decoupled_energy, coherence_ratio=coherence_ratio,
    )
