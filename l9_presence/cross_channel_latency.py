"""
L9 Cross-Channel Render-Latency Invariant (RESEARCH / ADVISORY -- default-OFF)
=============================================================================

Implements the forgery-resistant core of the Retina-Presence product thesis: the
gate's verdict is NOT "is channel X coupled" but "do the coupled channels share ONE
render+stream latency". See the synthesis notes:
  - s-cross-channel-latency-invariant   (the primitive)
  - s-retina-presence-product-thesis     (why it is the moat)
  - s-multi-channel-presence-gate         (the fusion gate this sharpens)

THE CLAIM (load-bearing)
------------------------
Each coupling oracle (B1 muzzle-flash, B2 kill-marker, geometric stick->pan,
recoil-compensation, ADS->FOV) independently estimates the input->screen lag and
its own time-shuffled null. In a GENUINE session every channel traverses ONE
physical pipeline (wire -> GPU -> encode -> network -> decode), so their measured
lags CLUSTER (L +/- jitter). A forger can fabricate ONE channel's coupling SCORE
(e.g. firing along to spectated combat -- the active-spectate hot-negative the B2
calibration audit measured at 0.261 vs a 0.282 kill-floor, a ~0.02 margin), but it
cannot make that channel's LAG agree with the others', because the spectated/replayed
screen runs on a clock the forger's trigger does not drive. Cross-channel lag
agreement is the property only co-located physical authorship produces.

So the gate measures the DISPERSION of the coupled channels' lags. Low spread =>
one shared clock => PRESENT_COHERENT. Coupled-but-scattered => no shared clock =>
INCOHERENT (a subset was fabricated). Too few coupled channels => INSUFFICIENT
(a single channel is exactly what was too thin -- the gate refuses to certify on it).

HONESTY RAILS (do not remove)
-----------------------------
1. ADVISORY ONLY. Never a tournament P0 gate, never an input to humanity_probability,
   never touches the 228-byte PoAC wire. This pure module gates nothing by itself.
2. FAIL-OPEN. No channels / all abstained / a single channel => UNVERIFIABLE or
   INSUFFICIENT, NEVER a PRESENT verdict. Absence of agreement is not a cheat call.
3. UNCALIBRATED. ``TAU_LAG_MS`` (the agreement threshold) is a PLACEHOLDER. The real
   value is a calibration question, not a constant -- ``calibrate_tau_lag`` fits it
   against labeled genuine/forged sessions and returns INSUFFICIENT_DATA until the
   live campaign reaches N_FLOOR (mirrors the B2 audit's n_null<10 verdict).
   ``CALIBRATION_STATUS`` stays ``UNCALIBRATED_SYNTHETIC`` until that experiment lands.
4. NULL-COLLAPSE GUARD. A channel only counts toward agreement if its causal coupling
   beats its time-shuffled null by ``null_margin`` -- a channel whose null did NOT
   collapse is spurious and is excluded (and surfaced in evidence), never trusted.

No bridge imports (l9_presence stays standalone). numpy-only; inputs are injected
dataclasses a future runner adapts from the live oracles. The core is a pure function.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

import numpy as np

CALIBRATION_STATUS = "UNCALIBRATED_SYNTHETIC"  # honesty rail #3 -- never claims a live score

# --- placeholder constants (the calibration campaign replaces TAU_LAG_MS) -------------------
TAU_LAG_MS: float = 80.0
"""Max robust dispersion (MAD, ms) of coupled-channel lags for PRESENT_COHERENT. PLACEHOLDER --
a plausible render+stream jitter band, NOT a measured threshold. Fit it with calibrate_tau_lag."""

MIN_COUPLED_CHANNELS: int = 2
"""Agreement is undefined below 2 coupled channels -- a single channel is exactly what the B2 audit
found too thin, so the gate refuses to certify on it (returns INSUFFICIENT_CHANNELS, not PRESENT)."""

NULL_MARGIN: float = 0.05
"""A channel counts as coupled only if coupling - null >= this (the shuffled null collapsed). Below
it the channel's score is not distinguishable from chance and is excluded from the agreement set."""

N_FLOOR: int = 10          # < this many labeled sessions per class => INSUFFICIENT_DATA
N_PRODUCTION: int = 30     # >= this => a CALIBRATED (not _PROVISIONAL) verdict is eligible
FAR_TARGET: float = 0.0    # FAR-safe: prefer a tau that admits zero forged sessions
FRR_CEILING: float = 0.5   # a FAR-safe tau that rejects >half the genuine set is useless, not "calibrated"


class LatencyVerdict(str, Enum):
    PRESENT_COHERENT = "PRESENT_COHERENT"                  # >=MIN coupled channels share one lag
    INCOHERENT_NO_SHARED_CLOCK = "INCOHERENT_NO_SHARED_CLOCK"  # coupled but lags disagree (forgery sig)
    INSUFFICIENT_CHANNELS = "INSUFFICIENT_CHANNELS"        # <MIN coupled -- cannot assess agreement
    UNVERIFIABLE = "UNVERIFIABLE"                          # no channels / all abstained / bad input


@dataclass(frozen=True)
class ChannelLag:
    """One coupling oracle's per-window output. ``coupling``/``null`` are |Pearson r| for the
    causal and the time-shuffled scan; ``lag_ms`` is the lag at the best causal |r|."""
    channel: str
    coupling: float
    null: float
    lag_ms: float

    def is_coupled(self, null_margin: float = NULL_MARGIN) -> bool:
        """Counts toward agreement iff the causal coupling beat the shuffled null by the margin."""
        try:
            return (float(self.coupling) - float(self.null)) >= float(null_margin)
        except (TypeError, ValueError):
            return False


@dataclass(frozen=True)
class LatencyAgreementResult:
    verdict: LatencyVerdict
    n_coupled: int
    lag_center_ms: Optional[float]   # median lag of the coupled channels
    lag_spread_ms: Optional[float]   # robust dispersion (MAD) of the coupled lags
    tau_lag_ms: float
    coupled_channels: list           # names that cleared the null-collapse guard
    calibration_status: str
    evidence: dict = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "verdict": self.verdict.value,
            "n_coupled": self.n_coupled,
            "lag_center_ms": self.lag_center_ms,
            "lag_spread_ms": self.lag_spread_ms,
            "tau_lag_ms": self.tau_lag_ms,
            "coupled_channels": list(self.coupled_channels),
            "calibration_status": self.calibration_status,
            "evidence": self.evidence,
        }


def _mad(x: np.ndarray) -> float:
    """Median absolute deviation about the median -- robust to one outlier channel (a single
    fabricated lag cannot inflate the spread the way std would)."""
    med = float(np.median(x))
    return float(np.median(np.abs(x - med)))


def assess_latency_agreement(
    channels: list[ChannelLag],
    *,
    tau_lag_ms: float = TAU_LAG_MS,
    min_channels: int = MIN_COUPLED_CHANNELS,
    null_margin: float = NULL_MARGIN,
) -> LatencyAgreementResult:
    """Cross-channel render-latency invariant. Pure. Fail-open (honesty rail #2): never returns
    PRESENT_COHERENT unless >= ``min_channels`` channels each cleared the null-collapse guard AND
    their lags cluster within ``tau_lag_ms`` (MAD). A single coupled channel, or coupled-but-
    scattered lags, NEVER certifies."""
    suspect = [c.channel for c in channels if (not c.is_coupled(null_margin))
               and _finite(c.coupling) and _finite(c.null) and (c.coupling >= null_margin)]
    coupled = [c for c in channels if c.is_coupled(null_margin) and _finite(c.lag_ms)]

    def _result(v: LatencyVerdict, center, spread, note: str) -> LatencyAgreementResult:
        return LatencyAgreementResult(
            verdict=v, n_coupled=len(coupled),
            lag_center_ms=center, lag_spread_ms=spread, tau_lag_ms=float(tau_lag_ms),
            coupled_channels=[c.channel for c in coupled],
            calibration_status=CALIBRATION_STATUS,
            evidence={
                "note": note,
                "null_collapsed_channels": [c.channel for c in coupled],
                "null_suspect_channels": suspect,   # coupled-looking but null did NOT collapse
                "per_channel_lag_ms": {c.channel: round(float(c.lag_ms), 2) for c in coupled},
                "min_channels": int(min_channels),
                "null_margin": float(null_margin),
            },
        )

    if not coupled:
        return _result(LatencyVerdict.UNVERIFIABLE, None, None,
                       "no channel cleared the null-collapse guard -- no agreement to assess")
    lags = np.array([float(c.lag_ms) for c in coupled], dtype=np.float64)
    center, spread = float(np.median(lags)), _mad(lags)
    if len(coupled) < min_channels:
        return _result(LatencyVerdict.INSUFFICIENT_CHANNELS, center, spread,
                       f"only {len(coupled)} coupled channel(s) < {min_channels} -- a single channel "
                       "is too thin to certify (B2 audit); refusing PRESENT")
    if spread <= tau_lag_ms:
        return _result(LatencyVerdict.PRESENT_COHERENT, center, spread,
                       f"{len(coupled)} channels share one lag (MAD {spread:.1f}ms <= {tau_lag_ms:.1f}ms)")
    return _result(LatencyVerdict.INCOHERENT_NO_SHARED_CLOCK, center, spread,
                   f"{len(coupled)} channels coupled but lags disagree (MAD {spread:.1f}ms > "
                   f"{tau_lag_ms:.1f}ms) -- no shared clock (fabricated-subset signature)")


# --------------------------------------------------------------------------
# Calibration harness -- fit TAU_LAG_MS against labeled sessions (the follow-up
# the cycle-51 product thesis is gated on). Mirrors the B2 audit's verdict
# discipline: INSUFFICIENT_DATA below N_FLOOR, PROVISIONAL below N_PRODUCTION.
# --------------------------------------------------------------------------

class CalibrationVerdict(str, Enum):
    CALIBRATED = "CALIBRATED"                      # >=N_PRODUCTION/class AND a FAR-safe tau exists
    CALIBRATED_PROVISIONAL = "CALIBRATED_PROVISIONAL"  # N_FLOOR<=n<N_PRODUCTION; directional only
    NO_SAFE_THRESHOLD = "NO_SAFE_THRESHOLD"        # enough data but no tau hits FAR_TARGET
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"        # < N_FLOOR labeled sessions in either class


@dataclass(frozen=True)
class CalibrationResult:
    verdict: CalibrationVerdict
    tau_lag_ms: Optional[float]
    far: Optional[float]            # fraction of forged sessions admitted as PRESENT_COHERENT
    frr: Optional[float]            # fraction of genuine sessions NOT admitted
    n_genuine: int
    n_forged: int
    calibration_status: str
    evidence: dict = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "verdict": self.verdict.value, "tau_lag_ms": self.tau_lag_ms,
            "far": self.far, "frr": self.frr,
            "n_genuine": self.n_genuine, "n_forged": self.n_forged,
            "calibration_status": self.calibration_status, "evidence": self.evidence,
        }


def calibrate_tau_lag(
    genuine_sessions: list[list[ChannelLag]],
    forged_sessions: list[list[ChannelLag]],
    *,
    candidates_ms: Optional[list[float]] = None,
    min_channels: int = MIN_COUPLED_CHANNELS,
    null_margin: float = NULL_MARGIN,
    far_target: float = FAR_TARGET,
    frr_ceiling: float = FRR_CEILING,
) -> CalibrationResult:
    """Fit the agreement threshold from labeled sessions. Sweep ``candidates_ms`` and pick the tau
    that holds FAR <= ``far_target`` (FAR-safe) AND FRR <= ``frr_ceiling`` (a threshold that rejects
    most genuine sessions is useless, not "calibrated"), minimizing FRR with a tighter-tau tiebreak.
    Honest verdict: INSUFFICIENT_DATA below N_FLOOR, PROVISIONAL below N_PRODUCTION, NO_SAFE_THRESHOLD
    if no tau separates the classes. Live forged set = the active-spectate/replay negatives (B2 audit)."""
    ng, nf = len(genuine_sessions), len(forged_sessions)
    if min(ng, nf) < N_FLOOR:
        return CalibrationResult(
            CalibrationVerdict.INSUFFICIENT_DATA, None, None, None, ng, nf, CALIBRATION_STATUS,
            {"note": f"need >= {N_FLOOR} sessions/class; have genuine={ng} forged={nf}",
             "n_production_target": N_PRODUCTION})
    cand = candidates_ms if candidates_ms is not None else [float(t) for t in range(5, 205, 5)]

    def _coherent(session: list[ChannelLag], tau: float) -> bool:
        return assess_latency_agreement(
            session, tau_lag_ms=tau, min_channels=min_channels, null_margin=null_margin
        ).verdict is LatencyVerdict.PRESENT_COHERENT

    best = None  # (far, frr, tau)
    sweep = []
    for tau in cand:
        far = sum(_coherent(s, tau) for s in forged_sessions) / nf
        frr = sum(not _coherent(s, tau) for s in genuine_sessions) / ng
        sweep.append({"tau_ms": tau, "far": round(far, 4), "frr": round(frr, 4)})
        if far <= far_target and frr <= frr_ceiling:
            key = (far, frr, tau)
            if best is None or key < best:
                best = key
    if best is None:
        # no FAR-safe tau; report the operating point with the lowest FAR for triage
        lo = min(sweep, key=lambda r: (r["far"], r["frr"]))
        return CalibrationResult(
            CalibrationVerdict.NO_SAFE_THRESHOLD, lo["tau_ms"], lo["far"], lo["frr"], ng, nf,
            CALIBRATION_STATUS, {"note": "no tau achieves FAR target", "far_target": far_target,
                                 "best_effort": lo, "sweep": sweep})
    far, frr, tau = best
    verdict = (CalibrationVerdict.CALIBRATED if min(ng, nf) >= N_PRODUCTION
               else CalibrationVerdict.CALIBRATED_PROVISIONAL)
    return CalibrationResult(
        verdict, float(tau), float(far), float(frr), ng, nf, CALIBRATION_STATUS,
        {"note": "FAR-safe tau selected (min FRR, tighter-tau tiebreak)",
         "far_target": far_target, "n_production_target": N_PRODUCTION, "sweep": sweep})


def _finite(x) -> bool:
    try:
        return np.isfinite(float(x))
    except (TypeError, ValueError):
        return False
