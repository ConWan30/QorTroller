"""POEP rung-2 analyzer tests. The analyzer's whole job is to answer P-WAVE-0 caveat 2 on REAL data:
do reflexes settle-to-plateau or return-to-baseline? These tests pin that verdict on synthetic captures
of each shape + the waveform-integrity check. poep_enabled stays False (analysis, not a flip).
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from l9_presence.poep_live_verify import waveform_commitment, waveform_digest
from scripts.poep_waveform_analyze import analyze_waveform_capture

T0 = 1_000_000_000_000


def _settling_curve():
    # early peak (peak_frac < 0.75) then HOLD near a raised plateau (tail ~flat) over a long window
    return [0.0, 400.0, 1200.0, 2000.0, 1750.0, 1650.0, 1620.0, 1615.0, 1610.0, 1612.0,
            1611.0, 1610.0, 1609.0, 1610.0, 1611.0, 1610.0]


def _descending_curve():
    # early peak then RAMP back toward baseline over a long window (tail strongly negative)
    return [0.0, 700.0, 1400.0, 2000.0, 1850.0, 1650.0, 1450.0, 1250.0, 1050.0, 850.0,
            650.0, 450.0, 300.0, 180.0, 90.0, 20.0]


def _record(idx, nonce, curve):
    wd = waveform_digest(curve)
    return {
        "challenge_index": idx, "nonce": nonce, "t_challenge_ns": T0,
        "waveform": curve, "waveform_digest": wd,
        "waveform_commitment": waveform_commitment(nonce=nonce, wave_digest=wd, t_challenge_ns=T0),
    }


def test_reports_distribution_not_a_gate_keyed_boolean():
    # grok round-23: the analyzer must NOT emit a settle boolean keyed to the shape-gate constant
    rep = analyze_waveform_capture({"records": [_record(i, f"n{i}", _settling_curve()) for i in range(6)]})
    assert "real_reflexes_settle_to_plateau" not in rep     # the circular boolean is GONE
    assert set(rep["tail_slope_distribution"]) >= {"mean", "median", "p10", "p90", "min", "max"}
    assert "NOT the shape-gate TAIL_SLOPE_MIN" in rep["physical_settle_criteria"]["note"]


def test_settling_curves_classify_as_settled():
    rep = analyze_waveform_capture({"records": [_record(i, f"n{i}", _settling_curve()) for i in range(6)]})
    assert rep["tail_class_counts"]["settled"] == 6
    assert rep["tail_class_counts"]["returning"] == 0
    assert rep["waveform_integrity_ok"] is True


def test_descending_curves_classify_as_returning():
    rep = analyze_waveform_capture({"records": [_record(i, f"d{i}", _descending_curve()) for i in range(6)]})
    assert rep["tail_class_counts"]["returning"] == 6
    assert rep["tail_class_counts"]["settled"] == 0
    assert rep["tail_slope_distribution"]["median"] < 0


def test_still_rising_curve_is_indeterminate_not_settled():
    # peak in the last quarter -> no settled tail observed -> must NOT be read as "settled" (grok round-23 bug)
    rising = [0.0, 100.0, 200.0, 300.0, 400.0, 500.0, 600.0, 700.0, 800.0, 900.0,
              1000.0, 1200.0, 1500.0, 1900.0, 2400.0, 3000.0]     # peak at the very end
    rep = analyze_waveform_capture({"records": [_record(1, "r1", rising)]})
    assert rep["tail_class_counts"]["indeterminate"] == 1
    assert rep["tail_class_counts"]["settled"] == 0


def test_integrity_detects_swapped_waveform():
    rec = _record(1, "n1", _settling_curve())
    rec["waveform"] = _descending_curve()          # swap the curve, leave the old digest/commitment
    rep = analyze_waveform_capture({"records": [rec]})
    assert rep["waveform_integrity_ok"] is False


def test_empty_capture_is_handled():
    rep = analyze_waveform_capture({"records": []})
    assert rep["n_waveforms"] == 0
    assert "no waveforms" in rep["verdict"]


def test_analyzer_never_flips_poep():
    rep = analyze_waveform_capture({"records": [_record(1, "n1", _settling_curve())]})
    assert "poep_enabled stays False" in rep["note"]
