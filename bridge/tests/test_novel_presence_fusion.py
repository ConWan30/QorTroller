"""Cycle-26 NQPV — NovelPresenceFusionOrchestrator.fuse() decision logic.

Pure unit test of the combining seam's verdict tree (no oracles, no HID). The seam's *sharpening* —
accepting COUPLED_CLEAN (L9/PoCP, no screen lobe) as a presence input — is exercised here. Includes
the incorporation bug-fix regression: LIVE_COHERENT WITHOUT presence must NOT read as CONSISTENT_HUMAN.
The verdict is advisory (NOT defensibility-validated; that's the cycle-29 calibrated-model target).
"""
from __future__ import annotations

import types

from vapi_bridge.novel_presence_fusion import NQPVVerdict, NovelPresenceFusionOrchestrator


def _f(**kw):
    return NovelPresenceFusionOrchestrator().fuse(**kw)


def _cco(tier):
    return types.SimpleNamespace(tier=tier, commitment="")


def test_missing_binding_unverifiable():
    assert _f(device_id=None, record_hash="ab").verdict == NQPVVerdict.UNVERIFIABLE


def test_hardware_class_fail():
    r = _f(device_id="d", record_hash="r", cco_report=_cco("FAIL"),
           poep_present=True, retina_report="COUPLED_CLEAN")
    assert r.verdict == NQPVVerdict.HARDWARE_CLASS_FAIL


def test_consistent_human_verified_hardware():
    # the seam's screen-lobe-free path: COUPLED_CLEAN (L9) + presence + hardware tier
    r = _f(device_id="d", record_hash="r", cco_report=_cco("P-T3"),
           poep_present=True, retina_report="COUPLED_CLEAN")
    assert r.verdict == NQPVVerdict.CONSISTENT_HUMAN_VERIFIED_HARDWARE


def test_consistent_human_no_cco():
    r = _f(device_id="d", record_hash="r", poep_present=True, retina_report="COUPLED_CLEAN")
    assert r.verdict == NQPVVerdict.CONSISTENT_HUMAN


def test_presence_without_trajectory():
    r = _f(device_id="d", record_hash="r", poep_present=True, retina_report="IMPLAUSIBLE")
    assert r.verdict == NQPVVerdict.INCONSISTENT_PRESENCE_WITHOUT_TRAJECTORY


def test_trajectory_without_presence():
    r = _f(device_id="d", record_hash="r", poep_present=False, retina_report="PLAUSIBLE")
    assert r.verdict == NQPVVerdict.INCONSISTENT_TRAJECTORY_WITHOUT_PRESENCE


def test_consent_revoked_unverifiable():
    r = _f(device_id="d", record_hash="r", poep_present=True, retina_report="COUPLED_CLEAN",
           cco_report=_cco("P-T3"), consent_ok=False)
    assert r.verdict == NQPVVerdict.UNVERIFIABLE


def test_bugfix_live_coherent_without_presence_not_human():
    # regression for the precedence fix: LIVE_COHERENT + poep_present=False must NOT certify a human
    r = _f(device_id="d", record_hash="r", poep_present=False, retina_report="LIVE_COHERENT")
    assert r.verdict not in (NQPVVerdict.CONSISTENT_HUMAN, NQPVVerdict.CONSISTENT_HUMAN_VERIFIED_HARDWARE)
    assert r.verdict == NQPVVerdict.INDETERMINATE
