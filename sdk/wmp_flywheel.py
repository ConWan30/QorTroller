"""WMP Two-Engines Flywheel (FLY-1) — the certified-human corpus feeds back to the
protocol. The data engine (verified play) grows a baseline of what real human play
looks like; that baseline is the raw material for sharpening the anti-cheat engine.
The two engines reinforce: better data → better detector → more valuable data.

STRICTLY BREADTH-GATED + READ-ONLY (safety, non-negotiable):
  * At N < MIN_BREADTH the advisory DEFERS and returns nothing.
  * It NEVER writes a threshold, never touches calibration. (Hard rule: per-player
    L4 thresholds only tighten, via min(), operator + measurement gated.)
  * v0 emits a corpus BASELINE (distribution of the VDC fingerprint scalars across
    N certified sessions) as INFORMATION and makes NO anti-cheat recommendation.
    Wiring the baseline into a detector is a separate, explicitly-deferred operator
    + calibration step.

Ceiling: v0 computes a read-only certified-human baseline, gated on breadth. It
makes NO recommendation and writes NO threshold. At N=1 (today) it defers.
"""
from __future__ import annotations

# Provisional, DECLARED breadth floor (changing it is a schema-minor bump, never silent).
MIN_BREADTH = 30

# The scalar fingerprint features the baseline aggregates (clearly-scalar VDC dims).
_SCALAR_FEATURES = (
    ("trigger_fraction", "TRIGGER_ENGAGEMENT_FRACTION_v1", "fraction"),
    ("stick_fraction", "STICK_ENGAGEMENT_FRACTION_v1", "fraction"),
    ("button_press_events", "BUTTON_PRESS_COUNT_v1", "press_events"),
)

STATUS_DEFERRED = "DEFERRED"
STATUS_BASELINE = "BASELINE"


def _profile(claims: list) -> dict:
    """Extract the scalar fingerprint of one session from its VDC claim-set."""
    by = {c.get("derivation_id"): (c.get("value") or {}) for c in claims}
    prof = {}
    for feat, deriv, field in _SCALAR_FEATURES:
        v = by.get(deriv)
        if v is not None and field in v and v[field] is not None:
            prof[feat] = v[field]
    return prof


def corpus_baseline(sessions: list) -> dict:
    """`sessions` = list of VDC claim-sets (one list of claims per certified
    session). Returns a read-only certified-human baseline, or DEFERRED below the
    breadth floor. NEVER a recommendation, NEVER a threshold."""
    n = len(sessions)
    if n < MIN_BREADTH:
        return {
            "status": STATUS_DEFERRED,
            "n": n,
            "min_breadth": MIN_BREADTH,
            "reason": f"insufficient breadth N={n} < {MIN_BREADTH}",
            "baseline": None,
            "recommendation": None,          # never — v0 makes no anti-cheat recommendation
            "note": ("flywheel computes a certified-human baseline only at breadth; it makes "
                     "no anti-cheat recommendation and writes no threshold, ever, from here"),
        }
    profiles = [_profile(s) for s in sessions]
    baseline = {}
    for feat, _deriv, _field in _SCALAR_FEATURES:
        vals = [p[feat] for p in profiles if feat in p]
        if vals:
            baseline[feat] = {
                "n": len(vals),
                "min": min(vals),
                "max": max(vals),
                "mean": round(sum(vals) / len(vals), 6),
            }
    return {
        "status": STATUS_BASELINE,
        "n": n,
        "baseline": baseline,
        "recommendation": None,              # v0: baseline is INFORMATION only
        "note": ("read-only certified-human baseline; wiring into a detector is a separate "
                 "operator + calibration step (thresholds only tighten via min(), gated)"),
    }
