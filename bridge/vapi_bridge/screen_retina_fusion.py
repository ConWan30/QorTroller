"""QorTroller x Trio-Retina — tri-channel L9 screen-retina fusion (pure logic).

Revives the WGC screen-capture as the SHARED sensor of two screen channels that both
bind to the certified controller input lobe, at two timescales:

  * CONTINUOUS coupling (L9/PoCP, ~60 Hz): cv_motion optical flow -> coupling.py. Does the
    on-screen camera move BECAUSE the aim-stick moved, at human lag? (coupling_score), and
    how much motion is UNEXPLAINED by the stick? (decoupled_energy = injection/aimbot proxy).
    Honesty rail: a time-SHUFFLED negative control MUST collapse; if it doesn't, the coupling
    is a latency-search artifact, not causality.
  * DISCRETE outcome coherence (dual-lobe OCR, event-rate): retina_causal_coherence over OCR
    HUD outcomes vs controller input events. Do down/score advances follow input?

  * VISUAL oracle coherence (NVIDIA Nemotron VLM): third lobe added 2026-07-27. Uses a vision-
    language model to classify the on-screen state (menu/lobby/gameplay/loading) and cross-verify
    it against the continuous coupling and discrete outcome axes. A player in "menu" cannot produce
    "gameplay coupling" (football: play-running; shooter: combat engagement) — this catches
    replay/relay attacks that the first two axes alone miss.

This module fuses the three ORTHOGONAL axes into one L9 verdict.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional

from .retina_causal_coherence import CoherenceVerdict

# Third lobe: Visual Oracle (NVIDIA Nemotron VLM) — optional import
try:
    from .retina_visual_oracle import (
        VisualOracle, VisualContext, CrossModalVerdict,
        GameState as VisualGameState,
    )
    _HAS_VISUAL_ORACLE = True
except ImportError:
    _HAS_VISUAL_ORACLE = False
    class VisualOracle:
        enabled = False
        async def analyze_frame(self, frame): return None
        def verify(self, *a, **kw):
            class V:
                match = True; anomaly = False; anomaly_type = ""
                def to_dict(s): return {"available": False}
            return V()
        def enhance_poac(self, base_record=None, **kw):
            return base_record or {}
    class VisualContext:
        game_state = None; confidence = 0.0; frame_hash = ""
        def to_dict(self): return {}
    class CrossModalVerdict:
        match = True; anomaly = False; anomaly_type = ""
        def to_dict(self): return {"available": False}
    class VisualGameState:
        UNKNOWN = "unknown"


# coupling.py defaults (kept in sync; overridable per-call)
DEFAULT_COUPLING_THRESHOLD = 0.20   # min |causal r| for "camera tracks stick"
DEFAULT_NEG_CONTROL_GAP = 0.15      # coupling_score - negative_control must exceed this
DEFAULT_RESIDUAL_THRESHOLD = 0.60   # decoupled_energy at/above this = injection candidate


class ContinuousAxis(str, Enum):
    COUPLED_CLEAN = "COUPLED_CLEAN"
    COUPLED_INJECTION = "COUPLED_INJECTION"
    DECOUPLED = "DECOUPLED"
    NEUTRAL = "NEUTRAL"


class L9FusionVerdict(str, Enum):
    # Pre-existing verdicts (first two axes)
    LIVE_COHERENT = "LIVE_COHERENT"
    LIVE_COUPLED = "LIVE_COUPLED"
    INJECTION_SUSPECT = "INJECTION_SUSPECT"
    REPLAY_OR_RELAY = "REPLAY_OR_RELAY"
    DECOUPLED_REVIEW = "DECOUPLED_REVIEW"
    INSUFFICIENT = "INSUFFICIENT"

    # Visual Oracle verdicts (third axis — NVIDIA Nemotron VLM)
    VISUALLY_CONFIRMED = "VISUALLY_CONFIRMED"
    VISUALLY_DECOUPLED = "VISUALLY_DECOUPLED"
    VISUALLY_BLOCKED = "VISUALLY_BLOCKED"
    VISUAL_INSUFFICIENT = "VISUAL_INSUFFICIENT"


@dataclass(frozen=True)
class ContinuousConfig:
    coupling_threshold: float = DEFAULT_COUPLING_THRESHOLD
    neg_control_gap: float = DEFAULT_NEG_CONTROL_GAP
    residual_threshold: float = DEFAULT_RESIDUAL_THRESHOLD
    injection_axis_enabled: bool = True


NCAA_CONTINUOUS_CONFIG = ContinuousConfig(injection_axis_enabled=False)


@dataclass(frozen=True)
class L9FusionReport:
    verdict: L9FusionVerdict
    continuous: ContinuousAxis
    coherence: CoherenceVerdict
    coupling_score: Optional[float]
    negative_control: Optional[float]
    decoupled_energy: Optional[float]
    coherence_ratio: float
    # Third axis
    visual_oracle: Optional[dict] = None

    def to_dict(self) -> dict:
        d = {
            "schema": "vapi-l9-screen-retina-fusion-v2",
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
        if self.visual_oracle is not None:
            d["visual_oracle"] = self.visual_oracle
        return d


def classify_continuous(coupling_score: Optional[float],
                        negative_control: Optional[float],
                        decoupled_energy: Optional[float],
                        cfg: ContinuousConfig = ContinuousConfig()) -> ContinuousAxis:
    if coupling_score is None:
        return ContinuousAxis.NEUTRAL
    neg = negative_control if negative_control is not None else 0.0
    collapsed = (coupling_score - neg) >= cfg.neg_control_gap
    if coupling_score >= cfg.coupling_threshold and collapsed:
        if (cfg.injection_axis_enabled and decoupled_energy is not None
                and decoupled_energy >= cfg.residual_threshold):
            return ContinuousAxis.COUPLED_INJECTION
        return ContinuousAxis.COUPLED_CLEAN
    return ContinuousAxis.DECOUPLED


# ── Visual Oracle Adjudication ────────────────────────────────────────────

def _adjudicate_visual(verdict: L9FusionVerdict, visual_context: Optional[VisualContext],
                       cross_modal: Optional[CrossModalVerdict]) -> L9FusionVerdict:
    """Apply the third axis (visual oracle) to override or confirm the base verdict.

    Higher priority than the first two axes: if Nemotron VLM sees a menu/loading screen,
    there is no gameplay to verify, regardless of what the coupling/coherence axes say.
    """
    if visual_context is None or visual_context.confidence < 0.1:
        return verdict  # No visual data — keep base verdict

    # Blocking states: menu, lobby, loading — no gameplay possible
    if visual_context.game_state in (VisualGameState.MENU, VisualGameState.LOBBY,
                                     VisualGameState.LOADING, VisualGameState.RESULTS,
                                     VisualGameState.CUTSCENE):
        return L9FusionVerdict.VISUALLY_BLOCKED

    # Anomaly: cross-modal mismatch
    if cross_modal and cross_modal.anomaly:
        if cross_modal.confidence >= 0.7:
            return L9FusionVerdict.VISUALLY_DECOUPLED
        return verdict  # Low confidence mismatch — keep base verdict

    # Confirmation: visual context matches motion/input
    if cross_modal and cross_modal.match:
        return L9FusionVerdict.VISUALLY_CONFIRMED

    return L9FusionVerdict.VISUAL_INSUFFICIENT


def fuse_screen_retina(coupling_score: Optional[float],
                       negative_control: Optional[float],
                       decoupled_energy: Optional[float],
                       coherence: CoherenceVerdict,
                       coherence_ratio: float = 0.0,
                       cfg: ContinuousConfig = ContinuousConfig(),
                       visual_context: Optional[VisualContext] = None,
                       cross_modal: Optional[CrossModalVerdict] = None) -> L9FusionReport:
    """Fuse three axes: continuous coupling + discrete outcome coherence + visual oracle.

    Args:
        coupling_score:    Camera-stick coupling (from InputOutputCouplingOracle)
        negative_control:  Time-shuffled negative control
        decoupled_energy:  Unexplained motion residual
        coherence:         Outcome coherence verdict (from CoherenceVerdict)
        coherence_ratio:   Ratio of coherent outcomes
        cfg:               Continuous coupling config
        visual_context:    Visual scene understanding (from NVIDIA Nemotron VisualOracle)
        cross_modal:       Cross-modal verification result (from CrossModalVerifier)

    Returns:
        L9FusionReport with verdict from all three axes
    """
    # Axis 1: Continuous coupling
    cont = classify_continuous(coupling_score, negative_control, decoupled_energy, cfg)

    # Axis 2: Discrete outcome coherence
    if cont is ContinuousAxis.COUPLED_INJECTION:
        base_verdict = L9FusionVerdict.INJECTION_SUSPECT
    elif cont is ContinuousAxis.COUPLED_CLEAN:
        if coherence is CoherenceVerdict.COHERENT:
            base_verdict = L9FusionVerdict.LIVE_COHERENT
        elif coherence is CoherenceVerdict.ORPHAN_OUTCOME:
            base_verdict = L9FusionVerdict.DECOUPLED_REVIEW
        else:
            base_verdict = L9FusionVerdict.LIVE_COUPLED
    elif cont is ContinuousAxis.DECOUPLED:
        if coherence is CoherenceVerdict.ORPHAN_OUTCOME:
            base_verdict = L9FusionVerdict.REPLAY_OR_RELAY
        elif coherence is CoherenceVerdict.COHERENT:
            base_verdict = L9FusionVerdict.DECOUPLED_REVIEW
        else:
            base_verdict = L9FusionVerdict.REPLAY_OR_RELAY
    else:  # NEUTRAL
        if coherence is CoherenceVerdict.COHERENT:
            base_verdict = L9FusionVerdict.LIVE_COHERENT
        elif coherence is CoherenceVerdict.ORPHAN_OUTCOME:
            base_verdict = L9FusionVerdict.REPLAY_OR_RELAY
        else:
            base_verdict = L9FusionVerdict.INSUFFICIENT

    # Axis 3: Visual oracle (overrides base verdict if visual data available)
    final_verdict = _adjudicate_visual(base_verdict, visual_context, cross_modal)

    # Build visual oracle data for the report
    vis_data = None
    if visual_context and visual_context.confidence > 0.1:
        vis_data = {
            "visual_context": visual_context.to_dict() if hasattr(visual_context, 'to_dict') else {},
            "cross_modal": cross_modal.to_dict() if cross_modal and hasattr(cross_modal, 'to_dict') else {},
        }

    return L9FusionReport(
        verdict=final_verdict, continuous=cont, coherence=coherence,
        coupling_score=coupling_score, negative_control=negative_control,
        decoupled_energy=decoupled_energy, coherence_ratio=coherence_ratio,
        visual_oracle=vis_data,
    )
