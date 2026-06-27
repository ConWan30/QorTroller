"""Coupling-threshold calibration — calibrate the UNCALIBRATED L9 COUPLING_THRESHOLD (0.20) against real
capture data. PURE module (no bridge/network imports); the capture lives in the bridge, this only DECIDES.

The L9 oracle exposes, per active-aim window, TWO numbers:
  * coupling_score  = real |causal Pearson r| between the right-stick and the on-screen pan.
  * negative_control = the SAME window with the input TIME-SHUFFLED = the chance/null baseline
    ("MUST be << coupling_score", coupling.py). This is the built-in false-accept oracle.

HONEST METHOD (the rails — never lower a threshold just to make COUPLED_CLEAN fire):
  * the adopted threshold MUST sit strictly above the null (shuffle/decoupled) distribution's upper tail,
    so the false-accept rate (FAR = fraction of null that passes) is MEASURED and bounded, not assumed.
  * verdict ADOPTABLE only if real coupling separates from the null with TPR >= floor at FAR <= cap. If
    real coupling overlaps the null, NO threshold is FAR-safe in this capture regime -> INSEPARABLE = the
    honest "Remote-Play coupling is genuinely sub-grade; use native-PC for the lag pillar" (cycle-44)
    outcome, NOT a lowered bar.
  * per-REGIME: a Remote-Play threshold is not a native-PC threshold (latency/jitter differ) -> label the
    corpus by regime and calibrate per regime.
  * the shuffle null is the WEAKEST honest null; structured decoupled motion (auto-camera / replay / another
    player's POV) can beat shuffle, so a shuffle-only ADOPTABLE is PROVISIONAL until structured negatives are
    added (the anti-GCAP rail, mirroring the NQPV defensibility study).

The bridge LOGS coupling_score + negative_control per session (RGC status/diag); a runner harvests labelled
samples by regime and calls calibrate(). This module is import-light + deterministic for unit testing.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Sequence

import numpy as np

CURRENT_THRESHOLD: float = 0.20   # L9_COUPLING_THRESHOLD default (coupling.py) — the hypothesis under test
FAR_CAP: float = 0.05             # max tolerated false-accept (null passing) for an adoptable threshold
TPR_FLOOR: float = 0.50           # min real-coupling pass-rate at that FAR to call a threshold useful
N_FLOOR: int = 10                 # min per-class samples for ANY verdict
N_PRODUCTION: int = 30            # per-class samples for production confidence (below = feasibility only)


@dataclass(frozen=True)
class CalibrationResult:
    verdict: str                          # ADOPTABLE | INSEPARABLE | INSUFFICIENT_DATA
    n_coupled: int
    n_null: int
    recommended_threshold: Optional[float]   # FAR-controlled; None unless ADOPTABLE
    far_at_threshold: Optional[float]
    tpr_at_threshold: Optional[float]
    separation: Optional[float]              # median(coupled) - p95(null); > 0 = separable
    current_threshold: float = CURRENT_THRESHOLD
    structured_null: bool = False            # True once non-shuffle decoupled negatives are included
    caveats: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "verdict": self.verdict, "n_coupled": self.n_coupled, "n_null": self.n_null,
            "recommended_threshold": self.recommended_threshold,
            "far_at_threshold": self.far_at_threshold, "tpr_at_threshold": self.tpr_at_threshold,
            "separation": self.separation, "current_threshold": self.current_threshold,
            "structured_null": self.structured_null, "caveats": list(self.caveats),
        }


def _clean(xs: Sequence[Optional[float]]) -> "np.ndarray":
    return np.asarray([float(x) for x in xs if x is not None], dtype=np.float64)


def calibrate(coupled: Sequence[Optional[float]], null: Sequence[Optional[float]], *,
              structured_null: bool = False, far_cap: float = FAR_CAP,
              tpr_floor: float = TPR_FLOOR, n_floor: int = N_FLOOR) -> CalibrationResult:
    """coupled = coupling_score from active-aim windows; null = negative_control (shuffle) [+ structured
    decoupled samples when available]. Returns a FAR-controlled threshold verdict. Deterministic."""
    c = _clean(coupled)
    n = _clean(null)
    sep = (float(np.median(c) - np.quantile(n, 0.95)) if c.size and n.size else None)
    caveats: list = []
    if not structured_null:
        caveats.append("null = SHUFFLE only (weakest honest null); add structured decoupled "
                       "(auto-camera/replay) negatives before production adoption — anti-GCAP rail")
    if c.size < n_floor or n.size < n_floor:
        caveats.append(f"INSUFFICIENT: need >={n_floor}/class (>={N_PRODUCTION} for production); "
                       f"have coupled={c.size} null={n.size}")
        return CalibrationResult("INSUFFICIENT_DATA", c.size, n.size, None, None, None,
                                 sep, structured_null=structured_null, caveats=caveats)
    if c.size < N_PRODUCTION or n.size < N_PRODUCTION:
        caveats.append(f"feasibility N (coupled={c.size} null={n.size}); re-confirm at N>={N_PRODUCTION}")
    # FAR-controlled candidate: the (1 - far_cap) quantile of the null -> by construction FAR ~= far_cap
    thr = float(np.quantile(n, 1.0 - far_cap))
    far = float(np.mean(n >= thr))
    tpr = float(np.mean(c >= thr))
    if sep is None or sep <= 0.0 or tpr < tpr_floor:
        caveats.append("real coupling overlaps the null upper tail -> no FAR-safe threshold in this "
                       "regime (sub-grade capture; native-PC for the lag pillar, cycle-44)")
        return CalibrationResult("INSEPARABLE", c.size, n.size, None, round(far, 4), round(tpr, 4),
                                 sep, structured_null=structured_null, caveats=caveats)
    return CalibrationResult("ADOPTABLE", c.size, n.size, round(thr, 4), round(far, 4), round(tpr, 4),
                             round(sep, 4), structured_null=structured_null, caveats=caveats)
