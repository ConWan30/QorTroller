"""C-4.2 Advisory Presence Confidence Model — test suite.

Pins: AIT=LOW (CI spans 1.0 + classifier collapse); FAR/FRR not usable; L4/L5=CALIBRATED;
PoSP precision=CALIBRATED, recall=LOW; PoEP/L6B=UNCALIBRATED; overall=OPERATING_CONSERVATIVE;
advisory=True always; cert_scope=developer_self; population_certified=False.
"""
from __future__ import annotations

from l9_presence.advisory_presence_confidence import (
    AIT_CI_LOWER,
    AIT_CI_UPPER,
    AIT_FAR_FRR_USABLE_AS_OPERATING_POINTS,
    AIT_HOLDOUT_RATIO,
    SignalConfidence,
    OverallAdvisoryLabel,
    build_advisory_report,
)


def test_ait_confidence_is_low():
    """C-2.3: CI spans 1.0 + classifier collapsed → LOW, never CALIBRATED."""
    r = build_advisory_report()
    assert r.signals["ait"].confidence == SignalConfidence.LOW


def test_ait_ci_spans_one():
    """AIT CI lower < 1.0 < upper — the structural reason for LOW (cannot reject null)."""
    assert AIT_CI_LOWER < 1.0 < AIT_CI_UPPER


def test_ait_far_frr_not_usable():
    """Collapse-artifact FAR/FRR must never be used as operating-point thresholds."""
    r = build_advisory_report()
    assert r.ait_far_frr_usable is False
    assert AIT_FAR_FRR_USABLE_AS_OPERATING_POINTS is False


def test_l4l5_calibrated():
    """L4/L5: N=74, thresholds anchored → CALIBRATED within developer_self scope."""
    r = build_advisory_report()
    assert r.signals["l4l5"].confidence == SignalConfidence.CALIBRATED


def test_posp_precision_calibrated_recall_low():
    """PoSP: precision=1.0 (CALIBRATED), recall=29.6% K=3 floor (LOW)."""
    r = build_advisory_report()
    assert r.signals["posp_precision"].confidence == SignalConfidence.CALIBRATED
    assert r.signals["posp_recall"].confidence == SignalConfidence.LOW
    assert r.posp_precision == 1.0
    assert abs(r.posp_recall_floor - 0.296) < 0.001


def test_poep_l6b_uncalibrated():
    """PoEP/L6B: N=0, default-OFF → UNCALIBRATED."""
    r = build_advisory_report()
    assert r.signals["poep_l6b"].confidence == SignalConfidence.UNCALIBRATED


def test_overall_label_operating_conservative():
    r = build_advisory_report()
    assert r.overall_label == OverallAdvisoryLabel.OPERATING_CONSERVATIVE


def test_advisory_invariants():
    """advisory=True always; cert_scope=developer_self; population_certified=False."""
    r = build_advisory_report()
    assert r.advisory is True
    assert r.cert_scope == "developer_self"
    assert r.population_certified is False


def test_nqpv_calibrated_within_developer_scope():
    r = build_advisory_report()
    assert r.signals["nqpv_fusion"].confidence == SignalConfidence.CALIBRATED


def test_ait_holdout_ratio_matches_c23_report():
    """C-2.3 exact measurement: holdout_ratio=1.037, CI spans 1.0."""
    r = build_advisory_report()
    assert abs(r.ait_holdout_ratio - 1.037) < 0.001
    lo, hi = r.ait_ci
    assert lo < 1.0 < hi
