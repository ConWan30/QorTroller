"""Live L4 humanity p_L4 mapping (cycle-36).

The p_L4 component of the Bayesian humanity fusion maps the L4 Mahalanobis distance to a humanity
probability. The legacy mapping ``exp(-max(0, d-2))`` anchors at d=2.0 — far tighter than the measured
L4 NOMINAL scale (anomaly threshold ~7.009; corpus human-mean d~2.45) — so it UNDER-credits genuine
NOMINAL humans (p_L4~0.05 at d=5; ~0.007 at the threshold). The re-anchor ``0.5**(d/threshold)`` aligns
the 0.5 point with the anomaly threshold (d==threshold->0.5, d~2.45->~0.74) and was validated coherent on
the real N=10 1000 Hz corpus (9/10 sessions L4-NOMINAL).

DEFAULT-OFF + config-gated: this RAISES humanity, and humanity HARD-GATES passport issuance
(humanity_prob >= 0.60), so flipping it on is a security-relevant loosening of the sub-threshold scoring
(the L4 anomaly hard-gate itself is untouched). When the flag is OFF the result is BYTE-IDENTICAL to the
legacy formula. The operator validates on a real N>=50 corpus (humans pass-rate rises, adversary
pass-rate does NOT) before flipping ``l4_humanity_reanchor_enabled=true``.
"""
from __future__ import annotations

import math

_DEFAULT_ANOMALY_THRESHOLD = 7.009


def p_l4_from_distance(
    distance: float | None,
    warmed: bool,
    *,
    reanchor_enabled: bool = False,
    anomaly_threshold: float | None = _DEFAULT_ANOMALY_THRESHOLD,
) -> float:
    """L4 Mahalanobis distance -> p_L4 humanity component in [0,1].

    not warmed / distance None  -> 0.5 (neutral prior; unchanged from legacy).
    reanchor_enabled is False    -> legacy exp(-max(0, d-2))  (BYTE-IDENTICAL to pre-cycle-36).
    reanchor_enabled is True     -> 0.5 ** (d / anomaly_threshold), clamped [0,1] (corpus-validated).
    """
    if not warmed or distance is None:
        return 0.5
    d = max(0.0, float(distance))
    if reanchor_enabled:
        thr = anomaly_threshold if (anomaly_threshold and anomaly_threshold > 0) else _DEFAULT_ANOMALY_THRESHOLD
        return float(min(1.0, max(0.0, 0.5 ** (d / thr))))
    return float(math.exp(-max(0.0, d - 2.0)))
