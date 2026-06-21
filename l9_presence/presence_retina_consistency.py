"""
L9 x Trio-Retina Presence-Consistency Fusion (RESEARCH / ADVISORY -- default-OFF)
================================================================================

Fuses two ORTHOGONAL axes of "humanness" into a cross-oracle CONSISTENCY signal:

  - PoEP / presence (EMBODIMENT): a live human is in the loop NOW -- challenge-
    response liveness + device-auth + nonce freshness. Sparse, event-driven.
    Source: ``l9_presence.poep_calibration.poep_verify()`` ({verdict, liveness_pass,
    device_auth_pass, ...}).

  - Trio-Retina (TRAJECTORY AUTHENTICITY): the CONTINUOUS output trajectory is
    physically plausible for human neuromotor control. Dense, per cognition cycle.
    Source: bridge retina_perception (``retina_event_log.anomaly_count`` / residual,
    bound to a PoAC ``record_hash``).

The SECURITY SIGNAL is their DISAGREEMENT, not either oracle's verdict.

Why disagreement and not classification (the load-bearing design claim)
-----------------------------------------------------------------------
Single-classifier biometric fusion at gamepad signal quality hits an ROC ceiling
-- see the GCAP honest negative, where tightening one classifier to catch more
adversaries collapsed genuine-human TAR 0.806 -> 0.581. This module deliberately
does NOT add features to one classifier. It treats two INDEPENDENT oracles (which
SHOULD agree for a genuine human) and emits their INCONSISTENCY. Inconsistency
detection between independent axes can have a better operating point than human-
vs-bot classification on one noisy axis, because an adversary must now satisfy two
independent models AND forge their agreement under a cryptographic binding.

What this closes (and what it does NOT)
---------------------------------------
CLOSES (in principle): machine-assisted cheating -- a present, reflexive human
(passes PoEP) whose CONTINUOUS output trajectory is machine-corrected downstream
of the controller (aim-assist / aimbot) trips IMPLAUSIBLE retina while presence
holds => INCONSISTENT. Partially closes human-relay (human passes the sparse
challenge while a bot plays between challenges) IFF the binding is tight enough
that the dense retina stream cannot be desynchronised from the presence proof.
DOES NOT CLOSE: account-sharing / smurfing / carrying -- a present, skilled,
legitimate-trajectory human who is not the account owner passes BOTH oracles.
That is an identity problem; neither presence nor trajectory authenticity is
identity. This module makes no identity claim.

HONESTY RAILS (load-bearing -- do not remove)
---------------------------------------------
1. ADVISORY ONLY. Never a tournament P0 gate, never an input to
   humanity_probability, never touches the 228-byte PoAC wire. Activation is a
   config concern in a future runner; this pure module gates nothing.
2. FAIL-OPEN. Missing / unbound / insufficient oracles => UNVERIFIABLE, NEVER a
   cheat verdict. A desynchronised or partial signal must never accuse.
3. UNCALIBRATED. Emits a CATEGORICAL consistency verdict + the contributing
   oracle states. It deliberately does NOT emit a calibrated probability: the
   separation power of the disagreement signal is [UNVALIDATED] until an
   adversarial capture (aim-assist / bot-in-loop / relay) proves the disagreement
   ROC beats either standalone ROC. ``calibration_status`` is always
   ``UNCALIBRATED_SYNTHETIC`` until that experiment lands.
4. BINDING IS THE SECURITY. Oracles are fused ONLY when bound to the same
   device_id, an overlapping time window, and (where present) the same PoAC
   record_hash. ``check_binding`` fails closed-to-UNVERIFIABLE on any gap --
   a loose binding reopens the human-relay attack.

No bridge imports (l9_presence stays standalone). Inputs are injected dataclasses
adapted from the live oracles by a future runner; the core is a pure function.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

CALIBRATION_STATUS = "UNCALIBRATED_SYNTHETIC"  # honesty rail #3 -- never claims a score


class PresenceState(str, Enum):
    PRESENT = "PRESENT"          # PoEP verdict PRESENT (liveness AND device-auth pass)
    REJECT = "REJECT"            # PoEP verdict REJECT (a challenge was run and failed)
    UNKNOWN = "UNKNOWN"          # no proof in window / calibration_incomplete / disabled


class TrajectoryState(str, Enum):
    PLAUSIBLE = "PLAUSIBLE"      # retina saw the window, no trajectory anomaly
    IMPLAUSIBLE = "IMPLAUSIBLE"  # retina flagged trajectory anomaly (anomaly_count > 0)
    UNKNOWN = "UNKNOWN"          # retina disabled / buffer-short / no bound row


class L4State(str, Enum):
    NOMINAL = "NOMINAL"          # Mahalanobis distance below continuity threshold
    ANOMALOUS = "ANOMALOUS"      # distance above anomaly threshold
    UNKNOWN = "UNKNOWN"          # no L4 distance persisted for the record


class ConsistencyVerdict(str, Enum):
    CONSISTENT_HUMAN = "CONSISTENT_HUMAN"
    CONSISTENT_INACTIVE = "CONSISTENT_INACTIVE"
    INCONSISTENT_PRESENCE_WITHOUT_AUTHENTIC_TRAJECTORY = "INCONSISTENT_PRESENCE_WITHOUT_AUTHENTIC_TRAJECTORY"
    INCONSISTENT_AUTHENTIC_TRAJECTORY_WITHOUT_PRESENCE = "INCONSISTENT_AUTHENTIC_TRAJECTORY_WITHOUT_PRESENCE"
    INDETERMINATE = "INDETERMINATE"
    UNVERIFIABLE = "UNVERIFIABLE"


# Advisory severity. Only the two INCONSISTENT (disagreement) states carry weight.
# These are NOT gate thresholds -- they rank advisory findings for operator review.
_SEVERITY = {
    ConsistencyVerdict.INCONSISTENT_PRESENCE_WITHOUT_AUTHENTIC_TRAJECTORY: "HIGH",
    ConsistencyVerdict.INCONSISTENT_AUTHENTIC_TRAJECTORY_WITHOUT_PRESENCE: "MEDIUM",
    ConsistencyVerdict.CONSISTENT_HUMAN: "NONE",
    ConsistencyVerdict.CONSISTENT_INACTIVE: "NONE",
    ConsistencyVerdict.INDETERMINATE: "INFO",
    ConsistencyVerdict.UNVERIFIABLE: "INFO",
}

# A genuine human's two oracles should agree. The disagreement states are the
# security signal; security_flag marks them for the FSCA consistency lattice.
_SECURITY_FLAG = {
    ConsistencyVerdict.INCONSISTENT_PRESENCE_WITHOUT_AUTHENTIC_TRAJECTORY,
    ConsistencyVerdict.INCONSISTENT_AUTHENTIC_TRAJECTORY_WITHOUT_PRESENCE,
}

# Default fusion time window: a presence proof and a retina trajectory window are
# considered co-temporal if their timestamps fall within this many nanoseconds.
# Conservative default; the real value is a calibration question, not a constant.
DEFAULT_WINDOW_NS = 2_000_000_000  # 2.0 s


@dataclass(frozen=True)
class PresenceSignal:
    device_id: str
    ts_ns: int
    state: PresenceState
    liveness_pass: Optional[bool] = None
    device_auth_pass: Optional[bool] = None
    nonce: Optional[str] = None


@dataclass(frozen=True)
class TrajectorySignal:
    device_id: str
    record_hash: str
    ts_ns: int
    state: TrajectoryState
    anomaly_count: int = 0
    residual: Optional[float] = None


@dataclass(frozen=True)
class L4Signal:
    state: L4State = L4State.UNKNOWN
    distance: Optional[float] = None


@dataclass(frozen=True)
class BindingResult:
    bound: bool
    reason: str


@dataclass(frozen=True)
class ConsistencyResult:
    verdict: ConsistencyVerdict
    severity: str
    security_flag: bool
    presence_state: PresenceState
    trajectory_state: TrajectoryState
    l4_state: L4State
    binding: BindingResult
    calibration_status: str
    evidence: dict = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "verdict": self.verdict.value,
            "severity": self.severity,
            "security_flag": self.security_flag,
            "presence_state": self.presence_state.value,
            "trajectory_state": self.trajectory_state.value,
            "l4_state": self.l4_state.value,
            "binding": {"bound": self.binding.bound, "reason": self.binding.reason},
            "calibration_status": self.calibration_status,
            "evidence": self.evidence,
        }


# --------------------------------------------------------------------------
# Adapters -- map live oracle outputs to the typed signal states
# --------------------------------------------------------------------------

def classify_presence(poep_result: Optional[dict]) -> PresenceState:
    """Map ``poep_verify()`` output to a PresenceState. Fail-safe to UNKNOWN."""
    if not poep_result:
        return PresenceState.UNKNOWN
    # calibration_incomplete (N<50) or any non-verdict status -> UNKNOWN (no claim)
    if poep_result.get("status") == "calibration_incomplete":
        return PresenceState.UNKNOWN
    verdict = poep_result.get("verdict")
    if verdict == "PRESENT":
        return PresenceState.PRESENT
    if verdict == "REJECT":
        return PresenceState.REJECT
    return PresenceState.UNKNOWN


def classify_trajectory(
    *,
    enabled: bool,
    buffer_filled: bool,
    anomaly_count: Optional[int],
) -> TrajectoryState:
    """Map retina perception state to a TrajectoryState. Fail-safe to UNKNOWN.

    UNKNOWN (not IMPLAUSIBLE) when retina is disabled or the window is buffer-short
    -- absence of a verdict is NOT evidence of an anomaly (honesty rail #2).
    """
    if not enabled or not buffer_filled or anomaly_count is None:
        return TrajectoryState.UNKNOWN
    return TrajectoryState.IMPLAUSIBLE if anomaly_count > 0 else TrajectoryState.PLAUSIBLE


# --------------------------------------------------------------------------
# Binding -- the security boundary (fail-closed-to-UNVERIFIABLE)
# --------------------------------------------------------------------------

def check_binding(
    presence: PresenceSignal,
    trajectory: TrajectorySignal,
    *,
    window_ns: int = DEFAULT_WINDOW_NS,
) -> BindingResult:
    """Oracles may be fused ONLY when bound to the same device and time window.

    A loose binding reopens the human-relay attack (pass presence on device A while
    a bot drives device B, or splice an old trajectory beside a fresh presence
    proof). Any gap => not bound => caller fails open to UNVERIFIABLE.
    """
    if not presence.device_id or not trajectory.device_id:
        return BindingResult(False, "missing device_id on a signal")
    if presence.device_id != trajectory.device_id:
        return BindingResult(
            False, f"device_id mismatch ({presence.device_id[:8]}.. != {trajectory.device_id[:8]}..)"
        )
    if not trajectory.record_hash:
        return BindingResult(False, "trajectory missing record_hash anchor")
    try:
        delta = abs(int(presence.ts_ns) - int(trajectory.ts_ns))
    except (TypeError, ValueError):
        return BindingResult(False, "non-integer timestamp on a signal")
    if delta > window_ns:
        return BindingResult(False, f"timestamps outside fusion window (|delta|={delta}ns > {window_ns}ns)")
    return BindingResult(True, "bound: same device_id, record_hash present, within window")


# --------------------------------------------------------------------------
# The consistency lattice -- disagreement IS the security signal
# --------------------------------------------------------------------------

def assemble_consistency(
    presence: PresenceSignal,
    trajectory: TrajectorySignal,
    l4: Optional[L4Signal] = None,
    *,
    window_ns: int = DEFAULT_WINDOW_NS,
) -> ConsistencyResult:
    """Fuse presence x trajectory (x optional L4) into a categorical consistency
    verdict. Disagreement between the two independent oracles is the security
    signal. Fail-open to UNVERIFIABLE on any binding gap or total absence of
    signal. NEVER emits a calibrated score (honesty rail #3)."""
    l4 = l4 or L4Signal()
    p, t = presence.state, trajectory.state

    def _result(v: ConsistencyVerdict, note: str) -> ConsistencyResult:
        return ConsistencyResult(
            verdict=v,
            severity=_SEVERITY[v],
            security_flag=v in _SECURITY_FLAG,
            presence_state=p,
            trajectory_state=t,
            l4_state=l4.state,
            binding=binding,
            calibration_status=CALIBRATION_STATUS,
            evidence={
                "note": note,
                "record_hash": trajectory.record_hash,
                "device_id": presence.device_id,
                "anomaly_count": trajectory.anomaly_count,
                "residual": trajectory.residual,
                "l4_distance": l4.distance,
                "liveness_pass": presence.liveness_pass,
                "device_auth_pass": presence.device_auth_pass,
            },
        )

    # Rail #4: binding first. No fusion across an unverified boundary.
    binding = check_binding(presence, trajectory, window_ns=window_ns)
    if not binding.bound:
        return _result(ConsistencyVerdict.UNVERIFIABLE, f"unbound -- {binding.reason}")

    # Rail #2: no signal at all -> cannot accuse, cannot clear.
    if p is PresenceState.UNKNOWN and t is TrajectoryState.UNKNOWN:
        return _result(ConsistencyVerdict.UNVERIFIABLE, "both oracles UNKNOWN -- no signal")

    # Only one oracle reporting -> not enough to call (dis)agreement.
    if p is PresenceState.UNKNOWN or t is TrajectoryState.UNKNOWN:
        return _result(ConsistencyVerdict.INDETERMINATE, "single-oracle window -- no consistency call")

    # Both oracles reporting -> the consistency lattice.
    if p is PresenceState.PRESENT and t is TrajectoryState.PLAUSIBLE:
        # Agreement on "human" -- unless the optional third oracle (L4) strongly
        # disagrees, in which case the two-vs-one split is itself a finding.
        if l4.state is L4State.ANOMALOUS:
            return _result(
                ConsistencyVerdict.INCONSISTENT_PRESENCE_WITHOUT_AUTHENTIC_TRAJECTORY,
                "presence+trajectory say human but L4 Mahalanobis anomalous -- 2v1 split",
            )
        return _result(ConsistencyVerdict.CONSISTENT_HUMAN, "presence + plausible trajectory agree")

    if p is PresenceState.PRESENT and t is TrajectoryState.IMPLAUSIBLE:
        # THE machine-assist / relay catch: a live human is present, but the
        # continuous output trajectory is not human-generated.
        return _result(
            ConsistencyVerdict.INCONSISTENT_PRESENCE_WITHOUT_AUTHENTIC_TRAJECTORY,
            "live presence but implausible continuous trajectory (machine-assist/relay candidate)",
        )

    if p is PresenceState.REJECT and t is TrajectoryState.PLAUSIBLE:
        # Human-plausible trajectory with no live presence: replay / synthetic
        # humanisation, OR presence simply was not genuinely exercised this window.
        return _result(
            ConsistencyVerdict.INCONSISTENT_AUTHENTIC_TRAJECTORY_WITHOUT_PRESENCE,
            "plausible trajectory but presence REJECT (replay/synthetic or presence not exercised)",
        )

    # p REJECT and t IMPLAUSIBLE -> both agree there is no genuine human activity.
    return _result(ConsistencyVerdict.CONSISTENT_INACTIVE, "no presence + implausible trajectory agree")
