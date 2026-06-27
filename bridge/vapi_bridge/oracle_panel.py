"""QorTroller × L9 — replay-through-all-oracles panel (Fusion v2 Phase 3).

The calibration core: take ONE bound co-capture session artifact and run EVERY screen-bound
oracle on it, so labelled artifacts (real + self-adversarial) can be tabulated into a 5-class
× per-oracle confusion. This is where UNCALIBRATED becomes measured separation.

Lives in the bridge (the integrator that owns the retina fusion modules); imports
`l9_presence.coupling` (bridge -> l9_presence direction; l9_presence stays pure). Pure +
hardware-free: the artifact (npz streams + optional OCR text + label) is the input contract;
the runner does file I/O. Everything is stamped UNCALIBRATED. No FROZEN/PoAC/chain touch.

Oracles run per artifact:
  * continuous coupling  — InputOutputCouplingOracle (camera <- stick causal Pearson + lag +
    decoupled-energy + time-shuffle negative control).
  * discrete coherence   — OCR HUD deltas (parse_hud/diff_hud) vs derived controller input
    events -> assess_coherence.
  * tri-channel fusion   — fuse_screen_retina(continuous, discrete) -> L9FusionReport.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from l9_presence.coupling import InputOutputCouplingOracle  # bridge -> l9_presence (l9 stays pure)

from .retina_causal_coherence import (
    CoherenceVerdict,
    TimedEvent,
    assess_coherence,
    from_screen_events,
)
from .retina_screen_lobe import HudState, diff_hud, parse_hud
from .screen_retina_fusion import ContinuousConfig, L9FusionVerdict, fuse_screen_retina

# input-event derivation thresholds (HID-derived, no trio-retina dependency)
_TRIGGER_ONSET = 10.0       # in_fire rising past this = a trigger action
_STICK_JUMP_NORM = 0.25     # |stick delta|/255 above this = a deliberate stick move
EVT_TRIGGER_ONSET = "controller.trigger.onset"
EVT_STICK_RADIAL_JUMP = "controller.stick.radial_jump"


@dataclass(frozen=True)
class SessionArtifact:
    """A bound co-capture session (the panel's input contract). Streams are plain lists so the
    panel needs no numpy in its signature; the loader converts npz arrays. `hud_texts` is the
    per-frame OCR (t_ms, text); omit for coupling-only sessions. `class_label`/`provenance`
    carry the ground-truth label for the confusion."""
    in_ts: list[float]
    in_sx: list[float]
    in_sy: list[float]
    mo_ts: list[float]
    mo_yaw: list[float]
    mo_pitch: list[float]
    in_fire: list[float] = field(default_factory=list)
    hud_texts: list[tuple[float, str]] = field(default_factory=list)
    class_label: str = "UNLABELED"
    provenance: str = "real"
    record_hash: str = ""
    capture_telemetry: dict = field(default_factory=dict)
    # --- NQPV oracle co-capture (cycle-30 wiring) — populated at capture time; ""/None = ABSTAIN ---
    # The retina/L9 verdict is computed by the panel itself (fuse_screen_retina). These carry the
    # OTHER oracle outputs so the corpus session is a full co-capture; a missing field abstains in the
    # calibrated model (no fabrication). Populating them is the capture-time step (live session loop).
    device_id: str = ""
    cco_tier: str = ""                    # CCO hardware-class tier (e.g. "P-T3"); "FAIL" hard-gates
    poep_present: Optional[bool] = None
    l4_l5_l6_ok: Optional[bool] = None


@dataclass(frozen=True)
class PanelReport:
    class_label: str
    provenance: str
    coupling_score: Optional[float]
    coupling_lag_ms: Optional[float]
    decoupled_energy: Optional[float]
    negative_control: Optional[float]
    coherence: CoherenceVerdict
    coherence_ratio: float
    fusion_verdict: L9FusionVerdict
    n_input_events: int
    n_screen_events: int
    # NQPV fused presence (cycle-30) — for the defensibility study to read per session
    nqpv_verdict: str = "UNVERIFIABLE"
    nqpv_presence_score: float = 0.0
    nqpv_disagreement_index: float = 0.0

    def to_dict(self) -> dict:
        return {
            "schema": "vapi-oracle-panel-v1",
            "calibration": "UNCALIBRATED",
            "class_label": self.class_label,
            "provenance": self.provenance,
            "coupling_score": self.coupling_score,
            "coupling_lag_ms": self.coupling_lag_ms,
            "decoupled_energy": self.decoupled_energy,
            "negative_control": self.negative_control,
            "coherence": self.coherence.value,
            "coherence_ratio": round(self.coherence_ratio, 4),
            "fusion_verdict": self.fusion_verdict.value,
            "n_input_events": self.n_input_events,
            "n_screen_events": self.n_screen_events,
            "nqpv_verdict": self.nqpv_verdict,
            "nqpv_presence_score": round(self.nqpv_presence_score, 4),
            "nqpv_disagreement_index": round(self.nqpv_disagreement_index, 4),
        }


def derive_input_events(a: SessionArtifact) -> list[TimedEvent]:
    """Derive coherence input events from HID streams (no trio-retina needed): a trigger
    onset on each rising R2 edge, a stick radial-jump on each large stick delta."""
    # NOTE: coherence times are in SECONDS (diff_hud uses t in s), so input event times are
    # converted from the artifact's millisecond timestamps to seconds to share one time base.
    events: list[TimedEvent] = []
    fire = a.in_fire
    for i in range(1, len(fire)):
        if fire[i - 1] < _TRIGGER_ONSET <= fire[i]:
            events.append(TimedEvent(kind="input", type=EVT_TRIGGER_ONSET, t=float(a.in_ts[i]) / 1000.0))
    for i in range(1, len(a.in_sx)):
        dx = a.in_sx[i] - a.in_sx[i - 1]
        dy = a.in_sy[i] - a.in_sy[i - 1]
        if (dx * dx + dy * dy) ** 0.5 / 255.0 >= _STICK_JUMP_NORM:
            events.append(TimedEvent(kind="input", type=EVT_STICK_RADIAL_JUMP, t=float(a.in_ts[i]) / 1000.0))
    return events


def derive_screen_events(a: SessionArtifact) -> list:
    """OCR HUD texts -> ScreenEvents via consecutive diff_hud (t in ms -> s for the fusion grid)."""
    out: list = []
    prev: Optional[HudState] = None
    for t_ms, text in a.hud_texts:
        cur = parse_hud(text)
        if prev is not None:
            out.extend(diff_hud(prev, cur, t_ms / 1000.0))
        prev = cur
    return out


def evaluate_artifact(a: SessionArtifact,
                      cont_cfg: Optional[ContinuousConfig] = None) -> PanelReport:
    """Run every screen-bound oracle on one bound session. Pure + hardware-free.

    cont_cfg selects the continuous-axis profile (default FPS). Pass
    screen_retina_fusion.NCAA_CONTINUOUS_CONFIG to drop the injection/residual axis for
    auto-camera games."""
    cont_cfg = cont_cfg or ContinuousConfig()
    # ---- continuous coupling ----
    osc = InputOutputCouplingOracle()
    for t, x, y in zip(a.in_ts, a.in_sx, a.in_sy):
        osc.push_input(float(t), float(x), float(y))
    for t, yaw, pitch in zip(a.mo_ts, a.mo_yaw, a.mo_pitch):
        osc.push_frame_motion(float(t), float(yaw), float(pitch))
    feats = osc.extract_features()
    nc = osc.negative_control()
    cs = feats.coupling_score if feats else None
    lag = feats.lag_ms if feats else None
    dec = feats.decoupled_energy if feats else None

    # ---- discrete coherence ----
    screen_events = derive_screen_events(a)
    input_events = derive_input_events(a)
    coh = assess_coherence(input_events + from_screen_events(screen_events))

    # ---- tri-channel fusion ----
    fusion = fuse_screen_retina(cs, nc, dec, coh.verdict, coh.coherence_ratio(), cfg=cont_cfg)

    # Cycle 26/30 NQPV wiring — feed the co-captured oracle outputs into the central orchestrator.
    # retina/L9 verdict = `fusion` (incl. COUPLED_CLEAN, the screen-lobe-free presence input). The
    # CCO/PoEP/L4-L5-L6 come from the SessionArtifact co-capture fields; a missing field ABSTAINS in
    # the calibrated model (no fabrication). Advisory / fail-open; not certifying (RETINA-EXCL-2 study).
    import types as _types
    nqpv_proof = None
    try:
        from .novel_presence_fusion import NovelPresenceFusionOrchestrator
        _cco = _types.SimpleNamespace(tier=a.cco_tier) if getattr(a, "cco_tier", "") else None
        nqpv_proof = NovelPresenceFusionOrchestrator().fuse(
            retina_report=fusion,
            cco_report=_cco,
            poep_present=getattr(a, "poep_present", None),
            l4_l5_l6_ok=getattr(a, "l4_l5_l6_ok", None),
            device_id=getattr(a, "device_id", "") or "",
            record_hash=getattr(a, "record_hash", "") or "",
        )
    except Exception:
        nqpv_proof = None  # fail-open

    return PanelReport(
        class_label=a.class_label, provenance=a.provenance,
        coupling_score=cs, coupling_lag_ms=lag, decoupled_energy=dec, negative_control=nc,
        coherence=coh.verdict, coherence_ratio=coh.coherence_ratio(),
        fusion_verdict=fusion.verdict,
        n_input_events=len(input_events), n_screen_events=len(screen_events),
        nqpv_verdict=(nqpv_proof.verdict.value if nqpv_proof else "UNVERIFIABLE"),
        nqpv_presence_score=(nqpv_proof.presence_score if nqpv_proof else 0.0),
        nqpv_disagreement_index=(nqpv_proof.disagreement_index if nqpv_proof else 0.0),
    )
