"""Tests for scripts/killfeed_audit_lane.py — the dual-instrument read-only kill-feed audit lane.

The load-bearing logic is `adjudicate()` — the disagreement taxonomy that turns two independent instruments
into the G1' precision measurement. It is pure (two dicts in, a category out), so it is exhaustively pinned
here: the CONFLICT_* categories ARE the zero-false-read control (A read a kill B saw as a death/roster), and
A_KILL_B_GAP vs A_KILL_B_MISS is the coverage-annotation distinction that keeps a structural B-blindness from
reading as suspicion. Instrument fail-open (noise -> UNRESOLVED, never a fabricated OWN_KILL) is pinned too.
"""
from __future__ import annotations

import importlib.util
import os

import pytest

cv2 = pytest.importorskip("cv2")
import numpy as np  # noqa: E402

from l9_presence import killfeed_ocr_bootstrap as ob  # noqa: E402

_REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_LANE_PATH = os.path.join(_REPO, "scripts", "killfeed_audit_lane.py")
_spec = importlib.util.spec_from_file_location("killfeed_audit_lane", _LANE_PATH)
lane = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(lane)


def _a(tax):
    return {"labeler": lane.INSTR_A, "taxonomy": tax}


def _b(tax, is_r4=False):
    return {"labeler": lane.INSTR_B, "taxonomy": tax, "is_r4": is_r4}


def test_adjudicate_agree():
    assert lane.adjudicate(_a(ob.OWN_KILL), _b(ob.OWN_KILL)) == "AGREE"
    assert lane.adjudicate(_a(ob.UNRESOLVED), _b(ob.UNRESOLVED)) == "AGREE"


def test_adjudicate_conflict_is_the_false_read_control():
    # A read an own-kill where B scored the handle in the VICTIM slot -> candidate A false read (must be 0).
    # No geometry on either side -> FAIL-TOWARD-REVIEW: the CONFLICT label is kept, never silently downgraded.
    assert lane.adjudicate(_a(ob.OWN_KILL), _b(ob.OWN_DEATH)) == "CONFLICT_A_KILL_B_DEATH"
    assert lane.adjudicate(_a(ob.OWN_KILL), _b(ob.OTHER_ROW)) == "CONFLICT_A_KILL_B_ROSTER"


def _ay(tax, y):
    return {"labeler": lane.INSTR_A, "taxonomy": tax, "y_frac": y}


def _by(tax, y):
    return {"labeler": lane.INSTR_B, "taxonomy": tax, "is_r4": False, "y_frac": y}


def test_adjudicate_location_gate_same_row_is_conflict():
    # F-G1P-2: B contradicting A ON THE SAME ROW (|dy| <= half a pitch) stays a CONFLICT — the real control.
    assert lane.adjudicate(_ay(ob.OWN_KILL, 0.30), _by(ob.OWN_DEATH, 0.31)) == "CONFLICT_A_KILL_B_DEATH"
    assert lane.adjudicate(_ay(ob.OWN_KILL, 0.30), _by(ob.OTHER_ROW, 0.30)) == "CONFLICT_A_KILL_B_ROSTER"


def test_adjudicate_location_gate_different_row_is_elsewhere():
    # B's signal from a DIFFERENT row (roster at 0.97, or another feed row) = B-blindness, not suspicion.
    # All 7 archive conflicts (2026-07-04, adjudicated TRUE) were exactly this class.
    assert lane.adjudicate(_ay(ob.OWN_KILL, 0.30), _by(ob.OTHER_ROW, 0.97)) == "A_KILL_B_ELSEWHERE"
    assert lane.adjudicate(_ay(ob.OWN_KILL, 0.30), _by(ob.OWN_DEATH, 0.40)) == "A_KILL_B_ELSEWHERE"


def test_adjudicate_location_gate_double_kill_pitch_guard():
    # Two genuinely distinct rows sit >= ONE pitch apart; the same-row tolerance is HALF a pitch, so a
    # double-kill's adjacent rows are never bucketed as one row (operator rider on F-G1P-2).
    assert lane.SAME_ROW_MAX_DY == lane.ROW_PITCH_YFRAC / 2.0 and 0.0 < lane.ROW_PITCH_YFRAC < 0.1
    dy_one_pitch = lane.ROW_PITCH_YFRAC
    assert lane.adjudicate(_ay(ob.OWN_KILL, 0.30),
                           _by(ob.OWN_DEATH, 0.30 + dy_one_pitch)) == "A_KILL_B_ELSEWHERE"


def test_adjudicate_location_gate_missing_y_fails_toward_review():
    # y on only ONE side -> geometry unknown -> keep CONFLICT (a potential contradiction is never dropped).
    a_no_y = {"labeler": lane.INSTR_A, "taxonomy": ob.OWN_KILL}
    assert lane.adjudicate(a_no_y, _by(ob.OWN_DEATH, 0.97)) == "CONFLICT_A_KILL_B_DEATH"


def test_adjudicate_b_gap_vs_b_miss():
    # A=OWN_KILL, B=UNRESOLVED: EXPECTED B-coverage gap (no R4 anchor) vs a real B miss (had R4, missed).
    assert lane.adjudicate(_a(ob.OWN_KILL), _b(ob.UNRESOLVED, is_r4=False)) == "A_KILL_B_GAP"
    assert lane.adjudicate(_a(ob.OWN_KILL), _b(ob.UNRESOLVED, is_r4=True)) == "A_KILL_B_MISS"


def test_adjudicate_a_recall_gap():
    assert lane.adjudicate(_a(ob.UNRESOLVED), _b(ob.OWN_KILL)) == "B_KILL_A_MISS"


def test_adjudicate_benign_a_abstain():
    # A is a killer-slot reader; abstaining on a death/roster is CORRECT, not a missed kill.
    assert lane.adjudicate(_a(ob.UNRESOLVED), _b(ob.OWN_DEATH)) == "BENIGN_A_ABSTAIN"
    assert lane.adjudicate(_a(ob.UNRESOLVED), _b(ob.OTHER_ROW)) == "BENIGN_A_ABSTAIN"


def test_instrument_a_shape_and_fail_open():
    # instrument_a returns the labeler + a taxonomy in {OWN_KILL, UNRESOLVED} (killer-slot reader); a zeros
    # panel yields UNRESOLVED, never a fabricated OWN_KILL.
    out = lane.instrument_a(np.zeros((120, 120, 3), np.uint8))
    assert out["labeler"] == lane.INSTR_A
    assert out["taxonomy"] in (ob.OWN_KILL, ob.UNRESOLVED)
    assert out["taxonomy"] == ob.UNRESOLVED       # nothing to read on black


def test_load_ensemble_has_static_anchors():
    ens = lane.load_ensemble()
    assert "feed_v1" in ens and "roster_v1" in ens          # committed static assets always present


def test_instrument_b_fail_open_on_noise():
    # B on random noise must not fabricate OWN_KILL (sub-floor -> UNRESOLVED/other, never a kill).
    ens = lane.load_ensemble()
    rng = np.random.default_rng(1)
    out = lane.instrument_b(rng.integers(0, 255, (200, 200, 3), dtype=np.uint8), ens)
    assert out["labeler"] == lane.INSTR_B and out["taxonomy"] != ob.OWN_KILL
