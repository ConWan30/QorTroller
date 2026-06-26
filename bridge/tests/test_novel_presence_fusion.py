"""Cycle-26/29 NQPV — NovelPresenceFusionOrchestrator.fuse() calibrated split-output model.

Pure unit test (no oracles, no HID). Covers the seam's sharpening (COUPLED_CLEAN = presence, no
screen lobe) AND the cycle-29 calibrated model: graded weighted score (single sub-grade oracle
OUTVOTED not fatal; missing oracle ABSTAINS) + the separate disagreement signal + injectable
threshold. The verdict is advisory (NOT defensibility-validated; the operating point is the
RETINA-EXCL-2 study's job).
"""
from __future__ import annotations

import types

from vapi_bridge.novel_presence_fusion import (
    NQPVVerdict,
    NovelPresenceFusionOrchestrator,
    cocapture_fields_from_pitl_meta,
)


def _f(**kw):
    return NovelPresenceFusionOrchestrator().fuse(**kw)


def _cco(tier):
    return types.SimpleNamespace(tier=tier, commitment="")


# --- hard gates + binding ---

def test_missing_binding_unverifiable():
    assert _f(device_id=None, record_hash="ab").verdict == NQPVVerdict.UNVERIFIABLE


def test_hardware_class_fail_hard_gate():
    r = _f(device_id="d", record_hash="r", cco_report=_cco("FAIL"),
           poep_present=True, retina_report="COUPLED_CLEAN")
    assert r.verdict == NQPVVerdict.HARDWARE_CLASS_FAIL


def test_consent_revoked_hard_gate():
    r = _f(device_id="d", record_hash="r", poep_present=True, retina_report="COUPLED_CLEAN",
           cco_report=_cco("P-T3"), consent_ok=False)
    assert r.verdict == NQPVVerdict.UNVERIFIABLE


# --- the seam's sharpening: COUPLED_CLEAN (no screen) is a valid presence input ---

def test_consistent_human_verified_hardware_via_coupled_clean():
    r = _f(device_id="d", record_hash="r", cco_report=_cco("P-T3"),
           poep_present=True, retina_report="COUPLED_CLEAN")
    assert r.verdict == NQPVVerdict.CONSISTENT_HUMAN_VERIFIED_HARDWARE
    assert r.presence_score >= 0.6


def test_consistent_human_no_cco():
    r = _f(device_id="d", record_hash="r", poep_present=True, retina_report="COUPLED_CLEAN")
    assert r.verdict == NQPVVerdict.CONSISTENT_HUMAN


# --- explicit disagreement patterns (the separate anti-cheat axis) ---

def test_presence_without_trajectory():
    r = _f(device_id="d", record_hash="r", poep_present=True, retina_report="IMPLAUSIBLE")
    assert r.verdict == NQPVVerdict.INCONSISTENT_PRESENCE_WITHOUT_TRAJECTORY


def test_trajectory_without_presence():
    r = _f(device_id="d", record_hash="r", poep_present=False, retina_report="PLAUSIBLE")
    assert r.verdict == NQPVVerdict.INCONSISTENT_TRAJECTORY_WITHOUT_PRESENCE


def test_live_coherent_without_presence_is_trajectory_without_presence():
    # (was the precedence-bug case) LIVE_COHERENT + poep False must NOT certify a human
    r = _f(device_id="d", record_hash="r", poep_present=False, retina_report="LIVE_COHERENT")
    assert r.verdict not in (NQPVVerdict.CONSISTENT_HUMAN, NQPVVerdict.CONSISTENT_HUMAN_VERIFIED_HARDWARE)
    assert r.verdict == NQPVVerdict.INCONSISTENT_TRAJECTORY_WITHOUT_PRESENCE


# --- anti-GCAP: graded votes, not conjunctive kill ---

def test_single_negative_oracle_is_outvoted_not_fatal():
    # l4_l5_l6=False (one sub-grade oracle says no) but everything else passes -> still HUMAN,
    # with the disagreement surfaced separately. (Conjunctive logic would have REJECTED here.)
    r = _f(device_id="d", record_hash="r", cco_report=_cco("P-T3"),
           poep_present=True, retina_report="COUPLED_CLEAN", l4_l5_l6_ok=False)
    assert r.verdict == NQPVVerdict.CONSISTENT_HUMAN_VERIFIED_HARDWARE
    assert r.disagreement_index > 0.0  # the disagreement is flagged, not used to reject


def test_missing_oracle_abstains_not_penalizes():
    # l4_l5_l6 not provided (None) -> abstains -> does not lower the verdict
    r = _f(device_id="d", record_hash="r", cco_report=_cco("P-T3"),
           poep_present=True, retina_report="COUPLED_CLEAN")  # no l4_l5_l6_ok
    assert r.verdict == NQPVVerdict.CONSISTENT_HUMAN_VERIFIED_HARDWARE


def test_injectable_threshold_gates_the_score():
    # same 0.80-score case, but a stricter injected threshold pushes it below the bar
    r = _f(device_id="d", record_hash="r", cco_report=_cco("P-T3"),
           poep_present=True, retina_report="COUPLED_CLEAN", l4_l5_l6_ok=False, threshold=0.99)
    assert r.verdict == NQPVVerdict.INDETERMINATE


# --- cycle-30 capture-time co-capture derivation ---

def test_cocapture_derives_live_oracles_and_abstains_honestly():
    f = cocapture_fields_from_pitl_meta({
        "cco_presence_ceiling_candidate": "P-T3", "humanity_prob": 0.82,
        "retina_enabled": True, "retina_alert": False,
    })
    assert f["nqpv_cocapture"] is True
    assert f["nqpv_cco_tier"] == "P-T3"
    assert f["nqpv_l4l5l6_ok"] is True                       # humanity 0.82 >= 0.5
    assert f["nqpv_retina_controller_signal"] == "CONTROLLER_CLEAN"
    assert f["nqpv_poep_present"] is None                    # abstain (not fabricated)


def test_cocapture_flags_anomaly_and_low_humanity():
    f = cocapture_fields_from_pitl_meta({"humanity_prob": 0.3, "retina_enabled": True, "retina_alert": True})
    assert f["nqpv_cco_tier"] is None                        # missing -> abstain
    assert f["nqpv_l4l5l6_ok"] is False                      # humanity 0.3 < 0.5
    assert f["nqpv_retina_controller_signal"] == "CONTROLLER_ANOMALY"


def test_cocapture_abstains_when_inputs_absent():
    f = cocapture_fields_from_pitl_meta({"cco_presence_ceiling_candidate": "P-T3"})  # no humanity/retina
    assert f["nqpv_l4l5l6_ok"] is None
    assert f["nqpv_retina_controller_signal"] is None
    assert f["nqpv_poep_present"] is None                    # abstain (no live PoEP)
    assert f["nqpv_retina_coupled_verdict"] is None          # abstain (no camera witness)


# --- cycle-33 (b) forward-compat plumbing: live presence oracles flow through when present ---

def test_cocapture_carries_live_poep_when_present():
    f = cocapture_fields_from_pitl_meta({"humanity_prob": 0.7, "poep_present": True})
    assert f["nqpv_poep_present"] is True                    # live PoEP signal carried, not hardcoded None


def test_cocapture_carries_live_coupled_retina_when_present():
    f = cocapture_fields_from_pitl_meta({
        "retina_enabled": True, "retina_alert": False,
        "retina_coupled_verdict": "COUPLED_CLEAN",          # camera witness landed
    })
    assert f["nqpv_retina_coupled_verdict"] == "COUPLED_CLEAN"
    assert f["nqpv_retina_controller_signal"] == "CONTROLLER_CLEAN"  # controller lobe still separate
