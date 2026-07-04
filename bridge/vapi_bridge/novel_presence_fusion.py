"""
Novel QorTroller Presence Verifier (NQPV) Fusion Orchestrator for Cycle 26.

This module provides the central, interoperable fusion of:
- CCO (hardware class verification)
- Retina / Screen-Retina (visual causal trajectory authenticity)
- PoEP / L9 Presence (embodied human + device auth)
- L4/L5/L6 (human physics input oracles)
- PoAC / GIC / PoSR (cryptographic binding, continuity, recency)
- Consent / VHP / PDA (sovereignty + attestation)
- PoVCA (Proof of Verified Causal Authorship — Cycle 42: input-grounded screen authorship per game-action; composes as oracle into NQPV)

Purpose: Create a single, seamless "gamer presence" proof that a verified human on certified hardware is generating real physics-based inputs that causally drive the game (not a bot or modified cheat hardware).

PoVCA enhancement (from cycle-42): per discrete on-screen game-action, prove authorship by verified controller input (provenance + L9 causal coupling + L4/L5 structure). Reuses existing primitives for interoperability. Honesty rails baked: "authorship + structure, NOT skill rank"; always advisory until study; abstain on emulated/non-live; compose into NQPV (not parallel).

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
    # ---- D-CERT-1 (a) INVARIANT — three orthogonal questions, three fields, none doing another's job:
    #     cert_scope            answers "WHO vouches" (the certification regime);
    #     verifier_independence answers "is the voucher INDEPENDENT of the subject";
    #     active_oracles        answers "WHAT evidence backed this verdict" (per-oracle outcome).
    #   Comparability (F-CERT-005) is solved by DECLARATION in active_oracles, NOT by multiplying
    #   cert_scope strings. When a new oracle joins the fusion it is declared in the manifest — do NOT
    #   mint a new scope string for it (that would reintroduce the uncoordinated-literal drift D-CERT-6
    #   closed, at the scope layer). Retina/authorship joining the fusion stays a D-CERT-5 question. ----
    # cycle-38 developer-self-cert (d-developer-self-cert): the CERTIFICATION SCOPE of this proof.
    # "advisory" (default) = uncertified signal; "developer_self" = certified for the developer's own
    # single-subject scope (NOT population/tournament). population_certified stays False until a
    # population corpus + real adversaries pass the study. The verdict is the result WITHIN the scope.
    cert_scope: str = "advisory"
    population_certified: bool = False
    # cycle-59 D-CERT-7: the verifier-independence rail, made EXPLICIT (was implicit in
    # population_certified=False). A structural fact of the cert scope, NOT enrollment data:
    #   None  -> no cert scope applies (advisory) -> the question is N/A;
    #   False -> self-certified (developer_self: verifier == subject) -> MUST NOT be laundered
    #            into independent/third-party trust;
    #   True  -> an independent verifier certified this (population/tournament) -> not reachable today.
    # Consumers read this directly instead of inferring independence from population_certified.
    verifier_independence: bool | None = None

    # Cycle-42 PoVCA (Proof of Verified Causal Authorship): input-grounded per-action authorship
    # (provenance + L9 causal + L4/L5 structure). Composes as oracle into NQPV (abstains if missing).
    # name chosen to avoid "skill" over-claim (authorship + structure_ok, not rank).
    # See posca_action_provenance.py for detector/binder (reuses ScreenEvent + assess_coherence + L4).
    # Rails: always advisory until measured study + live co-capture; hard gate emulated via CCO.
    posca_verdict: str = "UNVERIFIABLE"
    posca_commitment: str = ""
    posca_structure_ok: Optional[bool] = None
    posca_coupling_score: Optional[float] = None
    posca_action_count: int = 0

    # cycle-58 D-CERT-8 (d-cert8-emit-evidence-base): the calibration EVIDENCE BASE that
    # authorized this proof, emitted inline so the proof STREAM ALONE is self-describing
    # (closes F-CERT-008 — an auditor of the stream no longer needs poep_l9/ to reconstruct
    # the basis). All null-safe: None = no developer-self band governing this proof (advisory).
    # `calibration_band_commitment` is a BIOMETRIC-SNAPSHOT-v1 COMMITMENT (reflex_band_commitment),
    # NEVER raw band values — the raw (mu, sigma, salt) stays operator-held for audit disclosure
    # per VAPI_BIOMETRIC_PRIVACY.md. Self-describing != more-certified: population_certified stays
    # False; this closes an AUDITABILITY gap, not a certification gap. The commitment also pins the
    # authorizing band per proof, incidentally closing the F-CERT-007 band-drift anomaly.
    governing_model: str | None = None
    calibration_band_commitment: str | None = None
    calibration_n: int | None = None
    calibration_player_scope: str | None = None

    # cycle-59 D-CERT-1: the active-oracles manifest — per-oracle OUTCOME (contributed / abstained /
    # absent / abstained_or_absent) for THIS proof, so two verdicts resting on DIFFERENT evidence sets
    # are distinguishable (closes F-CERT-005 comparability, incl. the same-set-different-abstention
    # variant). Derived inside fuse() from the same oracle checks it scores -> cannot disagree with the
    # verdict. Null-safe: None on old records / the abstain path (NEVER inferred retroactively; the
    # honest answer for an unrecorded fusion is "unrecorded"). See _oracle_manifest for the honest
    # abstained-vs-absent conflation on the Optional[bool] oracles (poep / l4l5l6).
    active_oracles: dict[str, str] | None = None


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


def _oracle_manifest(
    retina_report, retina_contribution, cco_report, cco_tier, poep_present, l4_l5_l6_ok,
) -> dict[str, str]:
    """D-CERT-1 active-oracles manifest: per-oracle OUTCOME for THIS proof, derived from the SAME
    oracle inputs the fusion scores (so the manifest can NEVER disagree with the verdict). Closes
    F-CERT-005 comparability: two verdicts resting on different evidence sets become distinguishable.

    Outcomes:
      "contributed"         -> the oracle moved presence_score;
      "abstained"           -> consulted (input present) but produced no usable signal;
      "absent"              -> not wired (input missing);
      "abstained_or_absent" -> poep / l4l5l6 ONLY. They are passed as Optional[bool], so their
                               non-contributed state CANNOT distinguish consulted-and-abstained from
                               not-wired (the F-CERT-005 comparability gap surviving in miniature).
                               Distinguishing them would require passing those oracles as a richer
                               input type (a report object, or a (wired, value) pair) — a schema change
                               deferred; the manifest NAMES the conflation rather than papering over it.
    """
    manifest: dict[str, str] = {}
    # retina + cco are report-object inputs -> full 3-way (absent = report is None; abstained = report
    # present but no usable signal; contributed = a value that moved the score).
    manifest["retina"] = ("absent" if retina_report is None
                          else "abstained" if retina_contribution is None
                          else "contributed")
    manifest["cco"] = ("absent" if cco_report is None
                       else "abstained" if not cco_tier
                       else "contributed")
    # poep + l4l5l6 are Optional[bool] -> only contributed vs the honest conflation.
    manifest["poep"] = "contributed" if poep_present is not None else "abstained_or_absent"
    manifest["l4l5l6"] = "contributed" if l4_l5_l6_ok is not None else "abstained_or_absent"
    return manifest


def cocapture_fields_from_pitl_meta(meta: dict) -> dict:
    """Capture-time co-capture (cycle-30): derive the NQPV oracle inputs from the live per-record PITL
    meta sidecar, for the RETINA-EXCL-2 study corpus. HONEST about what is actually live in the session
    loop (USB capture only):
      - nqpv_cco_tier: cco_presence_ceiling_candidate (live, from the CCO capability report).
      - nqpv_l4l5l6_ok: humanity_prob >= 0.5 (PROXY — the humanity formula fuses L4/L5/L6/L2B/L2C).
      - nqpv_retina_controller_signal: the CONTROLLER-LOBE perception (CONTROLLER_CLEAN / _ANOMALY) --
        NOT the full L9/PoCP COUPLED_CLEAN nor screen LIVE_COHERENT (those need camera/screen, not live).
      - nqpv_poep_present / nqpv_retina_coupled_verdict (cycle-33 (b) forward-compat plumbing): carry a
        LIVE presence-oracle signal IF one was written into the meta, else None (ABSTAIN). Today both
        abstain -- PoEP is off-by-default behind its L6B N>=50 gate, and the coupled-retina screen
        verdict needs a camera witness (hardware-gated). When those go live they populate
        meta["poep_present"] / meta["retina_coupled_verdict"] and flow through here with NO code change
        (the "the harness re-runs cleanly once they land" promise). The controller-lobe signal is NEVER
        promoted to the coupled verdict -- different lobe, different vocabulary.
    Pure; the study reads these alongside device_id + record_hash to populate SessionArtifact. A missing
    input is None (abstain), never a fabricated value."""
    hp = meta.get("humanity_prob")
    if meta.get("retina_enabled"):
        retina_sig = "CONTROLLER_ANOMALY" if meta.get("retina_alert") else "CONTROLLER_CLEAN"
    else:
        retina_sig = None
    return {
        "nqpv_cocapture": True,
        # U1 (design doc §2.6): the shared session identifier passthrough — the join key correlating this
        # meta (and any proof built from it) with the session's KAS record + archive manifest. Null-safe:
        # None on pre-U1 records / non-daemon runs. NOT a fuse() input (that is U3's manifest question).
        "session_id": meta.get("session_id"),
        "session_display": meta.get("session_display"),
        "nqpv_cco_tier": meta.get("cco_presence_ceiling_candidate"),
        "nqpv_l4l5l6_ok": (hp >= 0.5) if isinstance(hp, (int, float)) else None,
        "nqpv_retina_controller_signal": retina_sig,
        "nqpv_poep_present": meta.get("poep_present"),                      # live if present, else abstain
        "nqpv_retina_coupled_verdict": meta.get("retina_coupled_verdict"),  # live (camera) if present, else abstain
        # PoVCA (Cycle 42): forward if attached in live co-capture (posca_action_provenance slice).
        # Absent -> NQPV fuse abstains (per design: only live oracles separate).
        "posca_verdict": meta.get("posca_verdict"),
        "posca_commitment": meta.get("posca_commitment"),
        "posca_structure_ok": meta.get("posca_structure_ok"),
        "posca_coupling_score": meta.get("posca_coupling_score"),
        "posca_action_count": meta.get("posca_action_count"),
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
        developer_self_cert: bool = False,
        # PoVCA (Cycle 42): optional ADVISORY oracle inputs from co-capture / action provenance.
        # Surfaced as posca_verdict on the proof; does NOT move presence_score (posca is absent from
        # _PROVISIONAL_WEIGHTS) until a measured RETINA-EXCL-2 study sets a calibrated weight under the
        # anti-GCAP rail. Absent/None structure -> abstain (UNVERIFIABLE); emulated device -> UNVERIFIABLE.
        posca_structure_ok: Optional[bool] = None,
        posca_coupling_score: Optional[float] = None,
        posca_action_count: int = 0,
        posca_commitment: str = "",
        # cycle-58 D-CERT-8: the calibration evidence base (from the live developer-self verdict),
        # carried onto the proof so the stream is self-describing. All None-default -> absent on
        # advisory proofs. `calibration_band_commitment` is a commitment (never raw band values).
        governing_model: str | None = None,
        calibration_band_commitment: str | None = None,
        calibration_n: int | None = None,
        calibration_player_scope: str | None = None,
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

        # D-CERT-1: hoist the retina contribution (both the score and the manifest use it) + build the
        # active-oracles manifest from the SAME oracle inputs the fusion scores, BEFORE the verdict
        # branching, so it is recorded on every path (hard-gate + scoring) and cannot disagree with the
        # verdict it accompanies.
        _rc = _retina_presence_contribution(retina_verdict)
        active_oracles = _oracle_manifest(retina_report, _rc, cco_report, cco_tier,
                                          poep_present, l4_l5_l6_ok)

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
            if _rc is not None:                       # _rc hoisted above (D-CERT-1 manifest reuse)
                contribs["retina"] = _rc
            if poep_present is not None:
                contribs["poep"] = 1.0 if poep_present else 0.0
            if l4_l5_l6_ok is not None:
                contribs["l4l5l6"] = 1.0 if l4_l5_l6_ok else 0.0
            if cco_tier:
                contribs["cco"] = 1.0  # present + not FAIL (FAIL hard-gated above)

            # PoVCA (cycle-42) is deliberately NOT a scoring contrib. It is an ADVISORY oracle FIELD
            # surfaced on the proof (posca_verdict below); it is absent from _PROVISIONAL_WEIGHTS and so
            # MUST NOT move presence_score until a measured RETINA-EXCL-2 study sets a calibrated weight
            # under the anti-GCAP rail (fused TAR >= best single oracle). Folding it into the score now —
            # on the uncalibrated, abstain-by-default structure signal — is exactly the overclaim the
            # cycle-42 honesty rails forbid.

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

        # cycle-38 developer-self-cert: cert_scope describes the certification REGIME (not the verdict).
        # developer_self when the operator's dev-cert mode is on; else advisory. population_certified
        # stays False until a population corpus + real adversaries pass the study (d-developer-self-cert).
        cert_scope = "developer_self" if developer_self_cert else "advisory"
        _scope_note = ("developer-self cert scope (single-subject; population_certified=False)"
                       if developer_self_cert
                       else "advisory; not certifying until RETINA-EXCL-2 study")
        # D-CERT-7: independence rail derived from the scope (structural fact, not enrollment data).
        # developer_self -> False (verifier == subject; do not launder); advisory -> None (N/A).
        verifier_independence = False if cert_scope == "developer_self" else None
        # PoVCA verdict (authorship + structure, NOT skill rank). Single source of truth honoring the
        # tri-state structure signal (None = abstain -> UNVERIFIABLE, never AUTHENTIC without L4 evidence)
        # and the emulated gate. The commitment is the recomputable one minted at action-detection time
        # (passed through here) — never a fabricated string.
        from .posca_action_provenance import posca_verdict_from
        posca_v = posca_verdict_from(posca_structure_ok, posca_coupling_score, cco_tier)
        posca_commit = posca_commitment or ""

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
            active_oracles=active_oracles,
            cert_scope=cert_scope,
            population_certified=False,
            verifier_independence=verifier_independence,
            posca_verdict=posca_v,
            posca_commitment=posca_commit,
            posca_structure_ok=posca_structure_ok,
            posca_coupling_score=posca_coupling_score,
            posca_action_count=posca_action_count,
            governing_model=governing_model,
            calibration_band_commitment=calibration_band_commitment,
            calibration_n=calibration_n,
            calibration_player_scope=calibration_player_scope,
            notes=(f"calibrated-v1; score={presence_score:.2f} "
                   f"disagreement={disagreement_index:.2f}; {_scope_note}; "
                   f"posca={posca_v} (advisory authorship field; NOT skill rank; not scored until study)")
        )

# --- Helper to wire into existing PoAC / GIC (stub for implementation) ---

def bind_fusion_to_poac(poac_record: Any, proof: FusedGamerPresenceProof) -> Any:
    """Planned: append fused verdict/commitment to PoAC body or sidecar. Do not alter 228B wire without ceremony."""
    # TODO: integrate with codec.PoACRecord
    return poac_record  # placeholder

# For now, the orchestrator is the core new interoperable piece.
# Call sites in dualshock_integration, retina fusion, and API will be extended in subsequent steps.