"""PoEP Track-1 activation layer (presence-oracle liveness, cycle-37 scope).

Bridges the l9_presence PoEP verdict (poep_calibration.poep_verify / liveness_score) to the NQPV
co-capture's poep_present contract (Optional[bool]: True / False / None=ABSTAIN), behind the TWO-KEY
hard-rule gate. PURE — operates on the verdict dict + the operator flag; no l9 import, no HID, no I/O.

THE TWO-KEY GATE (both required, else ABSTAIN):
  1. DATA gate  — the calibration model has N>=50 in-band reactions (the verdict is NOT
     "calibration_incomplete"). Enforced upstream by liveness_score/poep_verify (L6B hard rule).
  2. OPERATOR gate — poep_enabled flipped True (cfg.poep_liveness_enabled), a deliberate operator
     two-key action, NEVER auto-derived from the data gate.
Until BOTH are true, poep_present is None (ABSTAIN) — exactly what the co-capture/fusion treat as
"oracle not live", so a not-yet-activated PoEP never penalizes a real human nor fabricates a verdict.

This is why PoEP is enrollment-mode and SESSION-level: the reflex challenge needs a still controller
(gameplay confounds it; SHAM=1.0 in-game is proven), so poep_present is a per-SESSION verdict carried
into the per-record co-capture meta, never a mid-game per-record challenge.
"""
from __future__ import annotations

from typing import Optional


def poep_present_signal(poep_verdict: Optional[dict], *, poep_enabled: bool) -> Optional[bool]:
    """Map a poep_verify()/liveness_score() result -> the co-capture poep_present (Optional[bool]).

    Returns None (ABSTAIN) unless BOTH keys pass: operator (poep_enabled) AND data (model has N>=50,
    i.e. the verdict is not "calibration_incomplete"). Then True iff PRESENT/liveness_pass, else False.
    """
    if not poep_enabled:
        return None                                   # operator two-key not flipped -> abstain
    if not poep_verdict:
        return None
    if poep_verdict.get("status") == "calibration_incomplete":
        return None                                   # data gate (N>=50) not satisfied -> abstain
    verdict = poep_verdict.get("verdict")
    if verdict == "PRESENT":
        return True
    if verdict == "REJECT":
        return False
    # liveness_score-shaped result (no combined PRESENT/REJECT) -> fall back to the liveness flag
    if "liveness_pass" in poep_verdict:
        return bool(poep_verdict["liveness_pass"])
    return None                                       # unrecognized shape -> abstain (never fabricate)


def poep_activation_status(readiness: Optional[dict], *, poep_enabled: bool) -> dict:
    """Combine poep_readiness() + the operator two-key into a single clear activation status.

    status: ACTIVATED (both keys) / READY_TO_ACTIVATE_OPERATOR_GATE (data ready, operator hasn't
    flipped) / CALIBRATION_INCOMPLETE (need more in-band reactions).
    """
    readiness = readiness or {}
    data_ready = bool(readiness.get("calibration_complete"))
    op = bool(poep_enabled)
    if data_ready and op:
        status = "ACTIVATED"
    elif data_ready:
        status = "READY_TO_ACTIVATE_OPERATOR_GATE"
    else:
        status = "CALIBRATION_INCOMPLETE"
    return {
        "status": status,
        "activated": data_ready and op,
        "data_gate_n_ready": data_ready,
        "operator_two_key_enabled": op,
        "total_in_band_reactions": readiness.get("total_in_band_reactions", 0),
        "min_n": readiness.get("min_n"),
        "reactions_needed": readiness.get("reactions_needed"),
    }
