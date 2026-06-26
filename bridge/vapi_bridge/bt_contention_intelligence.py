"""BT-contention intelligence v1 (PCC-only) — cycle-39 scope `s-bt-contention-angle-scope`.

Treats Bluetooth-link contention as a FIRST-CLASS capture-integrity signal that GATES the presence proof
(never fabricates one), under the governing principle "capture integrity precedes presence."

v1 is PCC-only: it fuses the already-live capture-health signals (host_state + poll-rate CV + optional
module-flap count) into a `contention_state` + a benign/adversarial *lean*, and exposes whether the state
should GATE the proof (`contested`). The gate is consumed by agent #34 (PRESENCE_CONTESTED) and the
developer-self-cert NQPV proof.

HONESTY RAILS (from the scope note):
  - The adversarial direction is a measured-LEAN, never a hard verdict. Distinguishing a relay/cloud-bot
    contending the link (the BT-CALIB threat model) from benign streaming requires the BT-CALIB study
    (BlueShield FN floors: 5.84% CFO / 8.72% RSSI / 2.37% combined). v1 only LEANS.
  - bt_witness HCI evidence (Tpoll variance, AFH retransmission) and the hard adversarial verdict are v2
    (LAN-tower BlueZ hardware). v1 works in degraded mode on PCC alone.
  - No FROZEN-v1 / 228B PoAC / chain dependency — this is an integrity overlay, not a wire-format change.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class ContentionState(str, Enum):
    CLEAR = "CLEAR"                       # no contention; capture trustworthy
    CONTESTED_BENIGN = "CONTESTED-BENIGN"  # contention coincides with a known streaming source
    CONTESTED_SUSPECT = "CONTESTED-SUSPECT"  # unexplained contention — adversarial lean
    FLAPPING = "FLAPPING"                 # module repeatedly detaching/reattaching (hardware/tether)
    UNKNOWN = "UNKNOWN"                   # insufficient/indeterminate signal


class AdversaryLean(str, Enum):
    NONE = "NONE"        # no contention, or contention with no adversarial signal
    BENIGN = "BENIGN"    # contention explained by a known streaming source
    SUSPECT = "SUSPECT"  # contention unexplained — leans adversarial (NOT a verdict)


@dataclass(frozen=True)
class ContentionAssessment:
    """Result of a PCC-only contention assessment.

    `contested` is the load-bearing field consumed by the presence layer: True means the capture is
    contested and the presence proof MUST be gated (capture integrity precedes presence).
    """
    state: ContentionState
    lean: AdversaryLean
    evidence: str
    contested: bool

    def to_dict(self) -> dict:
        return {
            "state": self.state.value,
            "lean": self.lean.value,
            "evidence": self.evidence,
            "contested": self.contested,
        }


# Defaults are conservative: CV threshold matches PCC's CONTESTED inference (CV >= 0.40 per CLAUDE.md);
# flap threshold is "more than one detach in the window" (a single transient is tolerated).
_CV_CONTESTED_THRESHOLD = 0.40
_FLAP_THRESHOLD = 2

# host_state values that mean "capture path is healthy / uncontested"
_CLEAR_HOSTS = frozenset({"EXCLUSIVE_USB", "EXCLUSIVE_BT", "UNKNOWN", "NOMINAL"})


def assess_contention(
    *,
    host_state: Optional[str],
    poll_rate_cv: Optional[float] = None,
    flap_count_in_window: int = 0,
    streaming_source_active: bool = False,
    cv_contested_threshold: float = _CV_CONTESTED_THRESHOLD,
    flap_threshold: int = _FLAP_THRESHOLD,
) -> ContentionAssessment:
    """Assess BT-link contention from PCC-only signals. Pure -> testable.

    Precedence (most concrete failure first):
      1. FLAPPING — module detached >= flap_threshold times in the window (hardware/tether). contested.
      2. CONTESTED — PCC host_state==CONTESTED OR poll-rate CV >= threshold. Lean BENIGN if a known
         streaming source is active (Remote Play), else SUSPECT. contested.
      3. CLEAR — host_state in the healthy set with no CV breach. NOT contested.
      4. UNKNOWN — DEGRADED/DISCONNECTED/missing host_state. NOT contested (indeterminate, abstain — a
         disconnect is handled by PCC's own DISCONNECTED path, not by the contention gate).
    """
    host = (host_state or "").upper()

    if flap_count_in_window >= flap_threshold:
        return ContentionAssessment(
            ContentionState.FLAPPING, AdversaryLean.NONE,
            f"module detached {flap_count_in_window}x in window (>= {flap_threshold}) — hardware/tether issue",
            contested=True,
        )

    cv_high = poll_rate_cv is not None and poll_rate_cv >= cv_contested_threshold
    if host == "CONTESTED" or cv_high:
        _why_cv = f"CV={poll_rate_cv:.3f}>={cv_contested_threshold:.2f}" if cv_high else f"host_state={host}"
        if streaming_source_active:
            return ContentionAssessment(
                ContentionState.CONTESTED_BENIGN, AdversaryLean.BENIGN,
                f"contention ({_why_cv}) coincides with a known streaming source (e.g. Remote Play) — benign lean",
                contested=True,
            )
        return ContentionAssessment(
            ContentionState.CONTESTED_SUSPECT, AdversaryLean.SUSPECT,
            f"unexplained contention ({_why_cv}); no known streaming source — adversarial lean (measured-lean, not a verdict)",
            contested=True,
        )

    if host in _CLEAR_HOSTS:
        return ContentionAssessment(
            ContentionState.CLEAR, AdversaryLean.NONE, f"host_state={host}; no contention", contested=False,
        )

    return ContentionAssessment(
        ContentionState.UNKNOWN, AdversaryLean.NONE,
        f"host_state={host or 'missing'} — contention indeterminate (PCC owns disconnect/degraded path)",
        contested=False,
    )


def contention_to_presence_signal(assessment: ContentionAssessment) -> Optional[str]:
    """Map a contention assessment to an agent #34 presence-HUD signal_type, or None.

    Any contested state -> PRESENCE_CONTESTED (the binary HUD signal); the richer state/lean lives in the
    assessment's evidence for logging. CLEAR/UNKNOWN -> None (no contention signal).
    """
    return "PRESENCE_CONTESTED" if assessment.contested else None
