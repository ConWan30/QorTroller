"""Population reaction-time band for the QorTroller anti-cheat detector — CANDIDATE, ADVISORY (ASM-Loop r02).

The shipped detector's GO band (320, 400] ms is a SINGLE-OPERATOR provisional band. grok F5 flagged that a
population human who reacts faster than 320 ms would false-positive as SUSPECTED_BOT. This module (a) sets a
population-SAFE hard sub-floor at the human anticipation boundary, (b) provides a data-driven estimator that
pools per-operator reaction samples into a population band + per-operator FRR, honestly PROVISIONAL until
enough operators are measured, and (c) recomputes the joint worst-case FAR for a (wider) population band
using the SAME grok-audited math (a wider band RAISES the single-shot FAR; the multi-challenge compounding
and a higher K compensate).

HONESTY: with N=1 operator this is a FRAMEWORK + a CONSERVATIVE PRIOR, not a measured population band. The
anticipation floor (~120 ms) is established general psychophysics — voluntary reactions below ~100-120 ms to
an unpredictable stimulus are anticipation / false-starts, not reaction — stated WITHOUT fabricated citations;
a measured floor across operators is rig-gated. Candidate/advisory: gates nothing; poep_enabled/L6B stay False.
"""
from __future__ import annotations

import math
import os
import sys
from typing import Any

# Flat absolute import (matches qortroller_anticheat.py's own style) so this module works both as a package
# member (l9_presence.population_band) and as a top-level module (the runner/tests add l9_presence to path).
_L9 = os.path.dirname(os.path.abspath(__file__))
if _L9 not in sys.path:
    sys.path.insert(0, _L9)
from qortroller_anticheat import worst_case_true_far, GO_LO_MS, GO_HI_MS, K_REQUIRED_DEFAULT  # noqa: E402

# Hard human-impossibility sub-floor: a voluntary reaction to an UNPREDICTABLE stimulus cannot beat this
# (below = anticipation / scripted). Conservative general psychophysics, NOT our measurement, NOT a cite.
ANTICIPATION_FLOOR_MS = 120.0
MIN_OPERATORS_FOR_POPULATION = 5     # below this the band is PROVISIONAL (not a population claim)
MIN_SAMPLES_PER_OPERATOR = 20


def population_safe_sub_floor_ms() -> float:
    """The population-safe anti-cheat sub-floor = the anticipation boundary, NOT the single-operator 320 ms.
    Using 320 ms as the sub-floor (as the shipped detector does) false-positives fast humans (F5)."""
    return ANTICIPATION_FLOOR_MS


def _percentile(xs: list[float], pct: float) -> float:
    xs = sorted(xs)
    if not xs:
        return 0.0
    k = (len(xs) - 1) * pct / 100.0
    lo, hi = math.floor(k), math.ceil(k)
    return xs[int(k)] if lo == hi else xs[lo] * (hi - k) + xs[hi] * (k - lo)


def frr_for_band(samples: list[float], band_lo: float, band_hi: float) -> float:
    """Fraction of an operator's reactions OUTSIDE [band_lo, band_hi] = the false-reject rate for that band."""
    if not samples:
        return 0.0
    return round(sum(1 for x in samples if not (band_lo <= x <= band_hi)) / len(samples), 3)


def estimate_population_band(operator_samples: dict[str, list[float]],
                             anticipation_floor_ms: float = ANTICIPATION_FLOOR_MS,
                             lo_pct: float = 1.0, hi_pct: float = 99.0, margin_ms: float = 20.0,
                             min_operators: int = MIN_OPERATORS_FOR_POPULATION,
                             min_samples_per_op: int = MIN_SAMPLES_PER_OPERATOR,
                             k_required: int = K_REQUIRED_DEFAULT) -> dict[str, Any]:
    """Pool per-operator reaction-time samples (ms) -> a population band + per-operator FRR. The band floor is
    max(anticipation_floor, lo_pct-percentile - margin) (never below the human anticipation boundary); the
    ceiling is hi_pct-percentile + margin. PROVISIONAL until >= min_operators each with >= min_samples_per_op.
    Also reports the joint worst-case FAR for the population band vs the single-operator default band."""
    ops = {op: [float(x) for x in s if x is not None] for op, s in operator_samples.items()}
    ops = {op: s for op, s in ops.items() if s}
    pooled = [x for s in ops.values() for x in s]
    n_ops, n_samp = len(ops), len(pooled)

    base: dict[str, Any] = {"schema": "qortroller-population-band-v0", "advisory": True,
                            "n_operators": n_ops, "n_samples": n_samp,
                            "anticipation_floor_ms": anticipation_floor_ms}
    if not pooled:
        base.update(provisional=True, band_lo_ms=None, band_hi_ms=None, per_operator_frr={},
                    confidence_note="no samples", gate_note=_GATE_NOTE)
        return base

    floor = max(anticipation_floor_ms, _percentile(pooled, lo_pct) - margin_ms)
    ceiling = _percentile(pooled, hi_pct) + margin_ms
    per_op_frr = {op: frr_for_band(s, floor, ceiling) for op, s in ops.items()}

    # BAND COHERENCE GUARD (grok r03 F1/F2): floor = max(anticipation, ...) can EXCEED ceiling when the whole
    # pool reacts faster than the anticipation floor (every sample is sub-human by our own definition). Such a
    # band is DEGENERATE (floor >= ceiling) -> it is NOT a coherent human band. A degenerate band MUST be
    # flagged provisional and MUST NOT report a misleadingly-low (0.0) FAR as if it were a tight, safe band.
    degenerate = ceiling <= floor
    provisional = (degenerate or n_ops < min_operators
                   or any(len(s) < min_samples_per_op for s in ops.values()))

    if degenerate:
        # No coherent band -> FAR is UNDEFINED (do not emit 0.0). Report both bounds honestly-flagged.
        pop_far = None
        default_far = worst_case_true_far(k_required=k_required)[2]
        far_note = ("DEGENERATE band (floor >= ceiling): the pooled samples are (almost) all below the "
                    "anticipation floor, so no coherent human band exists. FAR is UNDEFINED (not 0.0); this "
                    "pool is itself a red flag, not a safe low-FAR band. Recapture real human reactions.")
    else:
        # joint worst-case FAR for the ACTUAL population three-zone config: band (floor, ceiling] + the
        # anticipation floor as the FATAL sub-floor (soft zone in between). A wider band AND a lower sub-floor
        # both RAISE the FAR (F4) — surfaced, not hidden. Compared to the single-operator default (sub==go_lo).
        pop_far = worst_case_true_far(k_required=k_required, go_lo_ms=floor, go_hi_ms=ceiling,
                                      sub_floor_ms=anticipation_floor_ms)[2]
        default_far = worst_case_true_far(k_required=k_required)[2]
        far_note = ("a WIDER population band AND a lower (anticipation) sub-floor BOTH RAISE the joint "
                    "worst-case TRUE FAR (F4); raise K and/or rely on multi-challenge compounding to "
                    "compensate. FAR computed with sub_floor=anticipation at k_required=%d" % k_required)

    base.update(
        band_lo_ms=round(floor, 1), band_hi_ms=round(ceiling, 1),
        degenerate_band=degenerate,
        per_operator_frr=per_op_frr,
        provisional=provisional,
        operators_needed=max(0, min_operators - n_ops),
        worst_case_far_population_band=pop_far,
        worst_case_far_single_operator_band=default_far,
        far_note=far_note,
        confidence_note=(("DEGENERATE band — " if degenerate else "")
                         + (f"PROVISIONAL: {n_ops} operator(s); need >= {min_operators} operators each with "
                            f">= {min_samples_per_op} samples for a population band" if provisional
                            else f"{n_ops} operators / {n_samp} samples — met the minimum")),
        gate_note=_GATE_NOTE,
    )
    return base


_GATE_NOTE = ("candidate/advisory; the anti-cheat sub-floor should be the anticipation floor "
              f"({ANTICIPATION_FLOOR_MS:.0f}ms), NOT the single-operator 320ms (F5); "
              "poep_enabled/L6B/L6_CHALLENGES stay False; gates nothing")


def single_operator_floor_false_positive_rate(fast_operator_samples: list[float],
                                              single_op_floor_ms: float = GO_LO_MS) -> float:
    """F5 DEMONSTRATION: fraction of a FAST operator's reactions that the single-operator 320 ms floor would
    wrongly reject as sub-floor (SUSPECTED_BOT). A population-safe floor at the anticipation boundary fixes it."""
    if not fast_operator_samples:
        return 0.0
    return round(sum(1 for x in fast_operator_samples if x <= single_op_floor_ms) / len(fast_operator_samples), 3)
