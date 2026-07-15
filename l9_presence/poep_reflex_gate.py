"""A2A-POEP-P2 B1+B2 — the reflex-corpus quality gate (category-bleed guard + usable-reflex filter).

The L6B corpus mixes three classes under one table: real human-reflex probes, CCO device-PHYSICS
captures (force-fingerprint research -- NOT reflex), and a broken/unwired route that emitted
REFLEX_OBSERVED=1 rows with ZERO IMU corroboration. Counting REFLEX_OBSERVED alone over-counts the
usable corpus 189 -> the honest 76 (measured 2026-07-15). This module is the single source of truth
for "which rows are usable human-reflex calibration material":

  B2 (category-bleed guard): policy_ref MUST be in the allowlist; CCO_T0 device-physics + broken/null
     routes + the failed squeeze protocol are excluded BY CONSTRUCTION (grok round-06 Q7).
  B1 (usable filter): after the policy gate, a row still must be IMU-corroborated (peak > floor) AND
     in the human reflex band AND not a latency artifact. + a burst-dedup pass for independence.

No liveness verdict, no model -- a data-quality gate only. poep_enabled stays False.
"""
from __future__ import annotations

from typing import Iterable, Optional

# B2 (grok round-06 Q7, confirmed against bridge.db policy_ref values):
L6B_REFLEX_POLICY_ALLOWLIST: frozenset[str] = frozenset({
    "desk_operator_still",        # the only route that produced real IMU-corroborated reflexes
    "edge_operator_reflex_v1",    # FUTURE: the registered-Edge reflex campaign MUST stamp this
})
# Documented deny (excluded by construction; here for auditability, not consulted -- allowlist wins):
L6B_REFLEX_POLICY_DENYLIST: frozenset[str] = frozenset({
    "CCO_T0_POLICY_v1_OPTION_C",  # CCO device-PHYSICS (force fingerprint) -- device-auth, NOT reflex
    "desk_operator_squeeze",      # failed protocol (near-zero IMU -- a trigger squeeze barely moves the body)
    # None / missing policy_ref   # broken/unwired route (emitted 113 peak=0 REFLEX_OBSERVED junk)
})

# B1 defaults: the IMU noise-floor threshold (config l6b_accel_delta_threshold_lsb) + the reflex band.
DEFAULT_PEAK_FLOOR_LSB = 500.0
DEFAULT_BAND_MS = (80.0, 350.0)
DEFAULT_ARTIFACT_MAX_MS = 1000.0   # any "latency" above this is a wall-clock artifact (slow ENTER), not a reflex


def policy_is_reflex(policy_ref: Optional[str]) -> bool:
    """B2: only an explicit allowlisted L6B-reflex policy counts. null / CCO / squeeze -> False."""
    return policy_ref in L6B_REFLEX_POLICY_ALLOWLIST


def is_usable_reflex(*, policy_ref: Optional[str], reflex_verdict: Optional[str],
                     accel_delta_peak: Optional[float], latency_ms: Optional[float],
                     peak_floor: float = DEFAULT_PEAK_FLOOR_LSB,
                     band_ms: tuple[float, float] = DEFAULT_BAND_MS,
                     artifact_max_ms: float = DEFAULT_ARTIFACT_MAX_MS) -> bool:
    """B1+B2: True iff this row is usable human-reflex calibration material. Never trusts
    REFLEX_OBSERVED alone (grok round-06): policy allowlist AND observed AND IMU-corroborated AND
    in-band AND not a latency artifact."""
    if not policy_is_reflex(policy_ref):
        return False
    if reflex_verdict != "REFLEX_OBSERVED":
        return False
    if accel_delta_peak is None or accel_delta_peak <= peak_floor:
        return False                                   # peak=0 null-route junk excluded here
    if latency_ms is None or latency_ms > artifact_max_ms:
        return False                                   # wall-clock artifact (e.g. 39.7s slow ENTER)
    lo, hi = band_ms
    return lo <= latency_ms <= hi


def dedup_bursts(ts_ms_sorted: Iterable[float], min_gap_ms: float = 5000.0) -> int:
    """Independence pass (grok DQ-6): collapse probes fired <min_gap_ms apart into one effective
    sample. Returns the effective independent count. Input MUST be ascending probe timestamps."""
    ts = [t for t in ts_ms_sorted if t is not None]
    if not ts:
        return 0
    n = 1
    last = ts[0]
    for t in ts[1:]:
        if (t - last) >= min_gap_ms:
            n += 1
            last = t
    return n
