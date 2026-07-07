"""Advisory Presence Confidence Model — C-4.2.

Pure-function module encoding the honest per-signal quality evidence as of the current
measurement campaign, so consumers have the calibration basis inline rather than
cross-referencing separate reports.

Evidence base:
  C-2.3  AIT holdout separation report (docs/phase-c-ait-separation-report-2026-07-05.md)
  C-3.3  Offline Instrument-A recall scan M13 (audits/c33_m13_recall_scan_report.md)
  Phase 57  L4/L5 calibration corpus (N=74)

Advisory only — never flips flags, never modifies presence_score or _PROVISIONAL_WEIGHTS.
cert_scope="developer_self" and population_certified=False throughout (3-player corpus).
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class SignalConfidence(str, Enum):
    CALIBRATED = "CALIBRATED"
    # Measured; CI strictly > 1.0 (separation-ratio signals) or precision = 1.0
    # (zero-false-read signals). Within-scope claim defensible as stated.
    LOW = "LOW"
    # Measured but: CI spans 1.0 (cannot reject null at 95%), recall < 50%, or classifier
    # collapsed (all subjects map to one centroid). The measurement exists; the claim is weak.
    UNCALIBRATED = "UNCALIBRATED"
    # No measurement yet, or flag is default-OFF (N=0). No operating-point claim possible.


class OverallAdvisoryLabel(str, Enum):
    OPERATING_CONSERVATIVE = "OPERATING_CONSERVATIVE"
    # L4/L5 and PoSP precision are CALIBRATED within developer_self scope.
    # AIT is LOW (holdout CI spans 1.0; classifier collapse at current N).
    # PoEP/L6B are UNCALIBRATED (N=0, default-OFF).
    # Suitable for developer-self demonstration only; NOT tournament-grade biometric separation.


# ── C-2.3 AIT holdout constants ──────────────────────────────────────────────────────────
AIT_HOLDOUT_RATIO: float = 1.037
AIT_CI_LOWER: float = 0.986      # 95% CI lower bound — spans 1.0 → cannot reject null
AIT_CI_UPPER: float = 1.119
AIT_N_ENROLLED: tuple = (9, 10, 8)   # P1, P2, P3 enrolled sessions in holdout
AIT_CLASSIFIER_COLLAPSED: bool = True
# FAR=0.317 / FRR=0.633 are collapse artifacts (all three players map to the P2 centroid).
# Named constant encodes the prohibition so consumers cannot use these as live thresholds.
AIT_FAR_FRR_USABLE_AS_OPERATING_POINTS: bool = False

# ── C-3.3 PoSP authored-kills recall scan (M13) ──────────────────────────────────────────
POSP_PRECISION: float = 1.0            # 0 false reads across 524 crops
POSP_RECALL_FLOOR_K3: float = 0.296   # K=3 operative floor (8/27 clusters)
POSP_RECALL_CEILING_K2: float = 0.556  # K=2 theoretical ceiling (15/27) — NOT the claim
POSP_TOTAL_CLUSTERS_M13: int = 27
POSP_KAS_AUTHORED_M13: int = 8

# ── Phase 57 L4/L5 calibration (N=74) ───────────────────────────────────────────────────
L4_CALIBRATION_N: int = 74
L4_ANOMALY_THRESHOLD: float = 7.009
L4_CONTINUITY_THRESHOLD: float = 5.367

# ── PoEP / L6B ───────────────────────────────────────────────────────────────────────────
POEP_L6B_N: int = 0


@dataclass(slots=True)
class SignalEntry:
    signal: str
    confidence: SignalConfidence
    basis: str
    note: str


@dataclass
class AdvisoryPresenceConfidenceReport:
    overall_label: OverallAdvisoryLabel
    cert_scope: str
    population_certified: bool
    signals: dict
    ait_holdout_ratio: float
    ait_ci: tuple
    ait_far_frr_usable: bool
    posp_precision: float
    posp_recall_floor: float
    posp_recall_ceiling: float
    advisory: bool = True


def build_advisory_report() -> AdvisoryPresenceConfidenceReport:
    """Build the advisory confidence report from the measured evidence base.

    All inputs are module-level constants from C-2.3, C-3.3, and Phase 57.
    No runtime measurement is performed.
    """
    signals = {e.signal: e for e in [
        SignalEntry(
            signal="ait",
            confidence=SignalConfidence.LOW,
            basis=(f"C-2.3 holdout ratio={AIT_HOLDOUT_RATIO}, "
                   f"CI=({AIT_CI_LOWER}, {AIT_CI_UPPER})"),
            note=("CI spans 1.0; classifier collapsed (all players map to P2 centroid); "
                  "FAR/FRR NOT usable as operating points"),
        ),
        SignalEntry(
            signal="l4l5",
            confidence=SignalConfidence.CALIBRATED,
            basis=(f"Phase 57, N={L4_CALIBRATION_N}, anomaly={L4_ANOMALY_THRESHOLD}, "
                   f"continuity={L4_CONTINUITY_THRESHOLD}"),
            note="developer_self scope (3-player corpus); population_certified=False",
        ),
        SignalEntry(
            signal="posp_precision",
            confidence=SignalConfidence.CALIBRATED,
            basis="C-3.3, 0 false reads across 524 crops (M13, K=3)",
            note="Precision 100%; K=3 conservative anchor; zero false authored kills",
        ),
        SignalEntry(
            signal="posp_recall",
            confidence=SignalConfidence.LOW,
            basis=(f"C-3.3, {POSP_KAS_AUTHORED_M13}/{POSP_TOTAL_CLUSTERS_M13} "
                   f"clusters at K=3 (M13)"),
            note=(f"{POSP_RECALL_FLOOR_K3 * 100:.1f}% operative floor; "
                  f"59% of misses are structurally un-promotable (brief kill rows)"),
        ),
        SignalEntry(
            signal="nqpv_fusion",
            confidence=SignalConfidence.CALIBRATED,
            basis="developer_self coupling measured M11/M12/M13 (COUPLED_CLEAN validated)",
            note="developer_self scope; verifier_independence=False (self-witnessed rig)",
        ),
        SignalEntry(
            signal="poep_l6b",
            confidence=SignalConfidence.UNCALIBRATED,
            basis=f"N={POEP_L6B_N}, flags default-OFF",
            note="L6B N≥50 required; PoEP enabled requires calibrated reflex band",
        ),
    ]}

    return AdvisoryPresenceConfidenceReport(
        overall_label=OverallAdvisoryLabel.OPERATING_CONSERVATIVE,
        cert_scope="developer_self",
        population_certified=False,
        signals=signals,
        ait_holdout_ratio=AIT_HOLDOUT_RATIO,
        ait_ci=(AIT_CI_LOWER, AIT_CI_UPPER),
        ait_far_frr_usable=AIT_FAR_FRR_USABLE_AS_OPERATING_POINTS,
        posp_precision=POSP_PRECISION,
        posp_recall_floor=POSP_RECALL_FLOOR_K3,
        posp_recall_ceiling=POSP_RECALL_CEILING_K2,
        advisory=True,
    )
