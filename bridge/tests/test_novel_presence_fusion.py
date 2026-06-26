"""Cycle-26/29 NQPV — NovelPresenceFusionOrchestrator.fuse() calibrated split-output model.

Pure unit test (no oracles, no HID). Covers the seam's sharpening (COUPLED_CLEAN = presence, no
screen lobe) AND the cycle-29 calibrated model: graded weighted score (single sub-grade oracle
OUTVOTED not fatal; missing oracle ABSTAINS) + the separate disagreement signal + injectable
threshold. The verdict is advisory (NOT defensibility-validated; the operating point is the
RETINA-EXCL-2 study's job).
"""
from __future__ import annotations

import types

from vapi_bridge.novel_presence_fusion import NQPVVerdict, NovelPresenceFusionOrchestrator


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
