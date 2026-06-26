"""
Novel QorTroller Presence Verifier (NQPV) Fusion Orchestrator for Cycle 26.

This module provides the central, interoperable fusion of:
- CCO (hardware class verification)
- Retina / Screen-Retina (visual causal trajectory authenticity)
- PoEP / L9 Presence (embodied human + device auth)
- L4/L5/L6 (human physics input oracles)
- PoAC / GIC / PoSR (cryptographic binding, continuity, recency)
- Consent / VHP / PDA (sovereignty + attestation)

Purpose: Create a single, seamless "gamer presence" proof that a verified human on certified hardware is generating real physics-based inputs that causally drive the game (not a bot or modified cheat hardware).

Basis: All components are designed as orthogonal (different axes, timescales, physics vs crypto). Their fusion on disagreement + cryptographic binding is the evolutionary anti-cheat + presence verifier.

If a component lacks direct wiring, this module + planned extensions close the loop.

Output: FusedGamerPresenceProof (verdict + bindings + commitments) that can be bound to PoAC, stamped in GIC, exported via WMP, or surfaced in API/on-chain.

Default-off, research surface; no FROZEN PoAC touch without ceremony.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Any

# --- Enums (extend existing Retina L9FusionVerdict and CCO tiers) ---

class NQPVVerdict(str, Enum):
    CONSISTENT_HUMAN_VERIFIED_HARDWARE = "CONSISTENT_HUMAN_VERIFIED_HARDWARE"  # strongest: all oracles agree + hardware class ok
    CONSISTENT_HUMAN = "CONSISTENT_HUMAN"  # human presence + trajectory, hardware context pending/lower tier
    INCONSISTENT_PRESENCE_WITHOUT_TRAJECTORY = "INCONSISTENT_PRESENCE_WITHOUT_TRAJECTORY"  # live human but output not causal (relay/aim-assist)
    INCONSISTENT_TRAJECTORY_WITHOUT_PRESENCE = "INCONSISTENT_TRAJECTORY_WITHOUT_PRESENCE"  # plausible output but no live human (replay)
    CONSISTENT_INACTIVE = "CONSISTENT_INACTIVE"  # no activity, all agree
    HARDWARE_CLASS_FAIL = "HARDWARE_CLASS_FAIL"  # CCO tier fail (modified/cheat hardware)
    UNVERIFIABLE = "UNVERIFIABLE"  # binding gap or partial data (fail-open)
    INDETERMINATE = "INDETERMINATE"

@dataclass(frozen=True, slots=True)
class FusedGamerPresenceProof:
    verdict: NQPVVerdict
    device_id: str
    record_hash: str
    cco_tier: str | None = None
    retina_verdict: str | None = None
    poep_present: bool | None = None
    l4_l5_l6_consistent: bool | None = None
    presence_score: float = 0.0          # cycle-29 calibrated weighted score in [0,1]
    disagreement_index: float = 0.0      # cycle-29 SEPARATE anti-cheat signal (oracle spread)
    binding_ok: bool = False
    timestamp_ns: int = 0
    commitments: dict[str, str] = field(default_factory=dict)  # e.g. {"retina": "...", "pda": "..."}
    notes: str = ""


# --- Calibrated model (cycle-29) — PROVISIONAL operating point ---
# These weights + threshold are ADVISORY placeholders so the seam runs; the QUALIFYING operating point
# comes from the RETINA-EXCL-2 study (measured human-TAR/adversary-FAR ROC + the anti-GCAP rail).
# fuse() accepts overrides so the study can inject calibrated values without a code change.
_PROVISIONAL_WEIGHTS: dict[str, float] = {"retina": 0.35, "poep": 0.30, "l4l5l6": 0.20, "cco": 0.15}
_PROVISIONAL_THRESHOLD: float = 0.60


def _retina_presence_contribution(retina_verdict: str | None) -> float | None:
    """Retina verdict -> presence contribution in [0,1], or None to ABSTAIN (absent/inactive/unknown).
    Abstain (not 0.0) is the anti-GCAP rule: a missing/inactive oracle must NOT penalize a real human.
    IMPLAUSIBLE is matched before PLAUSIBLE (it is a superstring)."""
    if not retina_verdict:
        return None
    v = str(retina_verdict).upper()
    if "COUPLED_CLEAN" in v or "LIVE_COHERENT" in v:
        return 1.0
    if "IMPLAUSIBLE" in v or "INJECTION" in v:
        return 0.0
    if "PLAUSIBLE" in v:
        return 0.5
    return None  # INACTIVE / unknown -> abstain


def cocapture_fields_from_pitl_meta(meta: dict) -> dict:
    """Capture-time co-capture (cycle-30): derive the NQPV oracle inputs from the live per-record PITL
    meta sidecar, for the RETINA-EXCL-2 study corpus. HONEST about what is actually live in the session
    loop (USB capture only):
      - nqpv_cco_tier: cco_presence_ceiling_candidate (live, from the CCO capability report).
      - nqpv_l4l5l6_ok: humanity_prob >= 0.5 (PROXY — the humanity formula fuses L4/L5/L6/L2B/L2C).
      - nqpv_retina_controller_signal: the CONTROLLER-LOBE perception (CONTROLLER_CLEAN / _ANOMALY) --
        NOT the full L9/PoCP COUPLED_CLEAN nor screen LIVE_COHERENT (those need camera/screen, not live).
      - nqpv_poep_present: None (ABSTAIN — PoEP is off-by-default; do not fabricate).
    Pure; the study reads these alongside device_id + record_hash to populate SessionArtifact. A missing
    input is None (abstain), never a fabricated value."""
    hp = meta.get("humanity_prob")
    if meta.get("retina_enabled"):
        retina_sig = "CONTROLLER_ANOMALY" if meta.get("retina_alert") else "CONTROLLER_CLEAN"
    else:
        retina_sig = None
    return {
        "nqpv_cocapture": True,
        "nqpv_cco_tier": meta.get("cco_presence_ceiling_candidate"),
        "nqpv_l4l5l6_ok": (hp >= 0.5) if isinstance(hp, (int, float)) else None,
        "nqpv_retina_controller_signal": retina_sig,
        "nqpv_poep_present": None,  # abstain: PoEP off-by-default; full L9/screen coupling not live here
    }


# --- Core Orchestrator ---

class NovelPresenceFusionOrchestrator:
    """
    Central fusion engine.

    Usage (planned wiring):
    orchestrator = NovelPresenceFusionOrchestrator()
    proof = orchestrator.fuse(
        cco_report=cco_report,
        retina_report=retina_fusion_report,
        poep_present=poep_present,
        l4_l5_l6_ok=l4_l5_l6_ok,
        device_id=device_id,
        record_hash=record_hash,
        consent_ok=consent_ok
    )
    # Then bind to PoAC, GIC, store, etc.
    """

    def __init__(self) -> None:
        pass

    def fuse(
        self,
        *,
        cco_report: Any | None = None,
        retina_report: Any | None = None,
        poep_present: bool | None = None,
        l4_l5_l6_ok: bool | None = None,
        device_id: str | None = None,
        record_hash: str | None = None,
        consent_ok: bool | None = None,
        timestamp_ns: int = 0,
        weights: dict[str, float] | None = None,
        threshold: float | None = None,
    ) -> FusedGamerPresenceProof:
        """
        Perform the fusion.

        All inputs are optional for graceful degradation (UNVERIFIABLE on missing binding data).
        """
        if not device_id or not record_hash:
            return FusedGamerPresenceProof(
                verdict=NQPVVerdict.UNVERIFIABLE,
                device_id=device_id or "",
                record_hash=record_hash or "",
                binding_ok=False,
                timestamp_ns=timestamp_ns,
                notes="Missing device_id or record_hash binding"
            )

        # Extract CCO tier
        cco_tier = None
        if cco_report is not None:
            cco_tier = getattr(cco_report, "tier", None) or getattr(cco_report, "research_tier", None)

        # Extract Retina verdict (from existing L9FusionVerdict)
        retina_verdict = None
        if retina_report is not None:
            retina_verdict = getattr(retina_report, "verdict", None) or str(retina_report)

        # Basic binding check (device + record + time assumed by caller)
        binding_ok = bool(device_id and record_hash)

        # --- Calibrated split-output model (cycle-29; replaces the conjunctive string-match tree) ---
        # SHARPENING KEPT: COUPLED_CLEAN (L9/PoCP, no screen) is still an accepted presence input, so
        # RETINA-EXCL-1 stays dissolved. CHANGED: presence is a GRADED weighted score (a single
        # sub-grade oracle's miss is OUTVOTED, not fatal; a missing oracle ABSTAINS) -> defuses the
        # GCAP human-reject trap. Disagreement is a SEPARATE signal. ADVISORY / default-off until the
        # RETINA-EXCL-2 study sets the certified weights+threshold (the literals here are provisional).
        _w = weights or _PROVISIONAL_WEIGHTS
        _thr = threshold if threshold is not None else _PROVISIONAL_THRESHOLD
        _ru = str(retina_verdict).upper() if retina_verdict else ""

        if cco_tier and "FAIL" in str(cco_tier).upper():
            # HARD GATE — categorical integrity, not graded presence evidence
            verdict, presence_score, disagreement_index = NQPVVerdict.HARDWARE_CLASS_FAIL, 0.0, 0.0
        elif consent_ok is False:
            # HARD GATE — sovereignty: no valid proof without consent
            verdict, presence_score, disagreement_index = NQPVVerdict.UNVERIFIABLE, 0.0, 0.0
        else:
            # Per-oracle presence contributions in [0,1]; an ABSENT oracle is OMITTED (abstains).
            contribs: dict[str, float] = {}
            _rc = _retina_presence_contribution(retina_verdict)
            if _rc is not None:
                contribs["retina"] = _rc
            if poep_present is not None:
                contribs["poep"] = 1.0 if poep_present else 0.0
            if l4_l5_l6_ok is not None:
                contribs["l4l5l6"] = 1.0 if l4_l5_l6_ok else 0.0
            if cco_tier:
                contribs["cco"] = 1.0  # present + not FAIL (FAIL hard-gated above)

            if contribs:
                _wsum = sum(_w.get(k, 0.0) for k in contribs) or 1.0
                presence_score = sum(_w.get(k, 0.0) * v for k, v in contribs.items()) / _wsum
                _vals = list(contribs.values())
                disagreement_index = (max(_vals) - min(_vals)) if len(_vals) > 1 else 0.0
            else:
                presence_score, disagreement_index = 0.0, 0.0

            if poep_present is False and "INACTIVE" in _ru:
                verdict = NQPVVerdict.CONSISTENT_INACTIVE
            elif poep_present and ("IMPLAUSIBLE" in _ru or "INJECTION" in _ru):
                # explicit disagreement pattern: live human, output not causal (relay/aim-assist)
                verdict = NQPVVerdict.INCONSISTENT_PRESENCE_WITHOUT_TRAJECTORY
            elif poep_present is False and _rc is not None and _rc >= 0.5:
                # explicit disagreement pattern: plausible output, no live human (replay)
                verdict = NQPVVerdict.INCONSISTENT_TRAJECTORY_WITHOUT_PRESENCE
            elif presence_score >= _thr:
                verdict = NQPVVerdict.CONSISTENT_HUMAN_VERIFIED_HARDWARE if cco_tier else NQPVVerdict.CONSISTENT_HUMAN
            else:
                verdict = NQPVVerdict.INDETERMINATE

        commitments = {}
        if retina_report:
            commitments["retina"] = getattr(retina_report, "commitment", "") or ""
        if cco_report:
            commitments["cco"] = getattr(cco_report, "commitment", "") or ""

        return FusedGamerPresenceProof(
            verdict=verdict,
            device_id=device_id,
            record_hash=record_hash,
            cco_tier=cco_tier,
            retina_verdict=retina_verdict,
            poep_present=poep_present,
            l4_l5_l6_consistent=l4_l5_l6_ok,
            presence_score=round(presence_score, 4),
            disagreement_index=round(disagreement_index, 4),
            binding_ok=binding_ok,
            timestamp_ns=timestamp_ns,
            commitments=commitments,
            notes=(f"calibrated-v1 (PROVISIONAL, advisory); score={presence_score:.2f} "
                   f"disagreement={disagreement_index:.2f}; not certifying until RETINA-EXCL-2 study")
        )

# --- Helper to wire into existing PoAC / GIC (stub for implementation) ---

def bind_fusion_to_poac(poac_record: Any, proof: FusedGamerPresenceProof) -> Any:
    """Planned: append fused verdict/commitment to PoAC body or sidecar. Do not alter 228B wire without ceremony."""
    # TODO: integrate with codec.PoACRecord
    return poac_record  # placeholder

# For now, the orchestrator is the core new interoperable piece.
# Call sites in dualshock_integration, retina fusion, and API will be extended in subsequent steps.