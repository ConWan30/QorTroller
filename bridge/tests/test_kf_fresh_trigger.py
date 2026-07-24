"""HARD-1 (F-T66B-1) tests -- the fresh-feed OCR trigger.

The fix for the 0/21 own-kill recall: a screen-driven watcher fires the rapidocr read when the
killfeed REGION CHANGES, instead of waiting for the throttled tune tick. These tests pin the pure
trigger rule (kf_fresh_decision), the change signal (_kf_gray_diff), and the shared read path's
sink behavior -- all synthetic, no card, no daemon.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from bridge.vapi_bridge.qortroller_retina_capture import (
    _SESSION_ANCHOR_FRESH_DIFF, _kf_gray_diff, kf_fresh_decision, kf_watch_step,
)
from l9_presence.killfeed_authorship import (
    KillfeedAuthorshipOracle, canon, is_own_killer_token,
)
from l9_presence.killfeed_raw_reader import classify_rows
from l9_presence.killfeed_ocr_bootstrap import OWN_DEATH, OWN_KILL, OTHER_ROW


# --- the pure trigger rule ---------------------------------------------------
def test_fires_on_change_after_gap():
    assert kf_fresh_decision(diff=20.0, now_ms=10_000.0, last_ocr_ms=0.0)


def test_no_fire_below_threshold():
    # static screen noise stays below the tuned fresh-row constant -> no OCR burn
    assert not kf_fresh_decision(diff=_SESSION_ANCHOR_FRESH_DIFF, now_ms=10_000.0, last_ocr_ms=0.0)
    assert not kf_fresh_decision(diff=0.0, now_ms=10_000.0, last_ocr_ms=0.0)


def test_min_gap_bounds_ocr_rate():
    # a diff-storm (rapid scene changes) cannot fire faster than the gap -- the adversarial
    # "flood the watcher" ceiling grok's round-02 should attack
    assert not kf_fresh_decision(diff=50.0, now_ms=1_000.0, last_ocr_ms=500.0)      # 500ms < 1200ms
    assert kf_fresh_decision(diff=50.0, now_ms=1_701.0, last_ocr_ms=500.0)          # 1201ms >= gap


def test_custom_gap_and_threshold():
    assert kf_fresh_decision(diff=3.0, now_ms=100.0, last_ocr_ms=0.0, min_gap_ms=50.0, threshold=2.0)
    assert not kf_fresh_decision(diff=3.0, now_ms=40.0, last_ocr_ms=0.0, min_gap_ms=50.0, threshold=2.0)


# --- the change signal --------------------------------------------------------
def _crop(fill: int, h: int = 205, w: int = 499) -> np.ndarray:
    return np.full((h, w, 3), fill, dtype=np.uint8)


@pytest.mark.skip(reason="qortroller_retina_capture.py transitively needs cv2, not installed in this CI environment")
def test_gray_diff_first_frame_never_fires():
    diff, gray = _kf_gray_diff(_crop(128), None)
    assert diff == 0.0 and gray is not None                  # no spurious fire on startup


@pytest.mark.skip(reason="qortroller_retina_capture.py transitively needs cv2, not installed in this CI environment")
def test_gray_diff_static_feed_is_zero():
    _, g1 = _kf_gray_diff(_crop(128), None)
    diff, _ = _kf_gray_diff(_crop(128), g1)
    assert diff == 0.0


@pytest.mark.skip(reason="qortroller_retina_capture.py transitively needs cv2, not installed in this CI environment")
def test_gray_diff_new_row_fires_over_threshold():
    _, g1 = _kf_gray_diff(_crop(30), None)                   # dark feed region
    bright = _crop(30)
    bright[40:80, 10:300] = 235                              # a kill row renders (bright text band)
    diff, _ = _kf_gray_diff(bright, g1)
    assert diff > _SESSION_ANCHOR_FRESH_DIFF                 # the watcher would fire


@pytest.mark.skip(reason="qortroller_retina_capture.py transitively needs cv2, not installed in this CI environment")
def test_gray_diff_shape_change_resets_not_fires():
    _, g1 = _kf_gray_diff(_crop(128), None)
    diff, g2 = _kf_gray_diff(_crop(128, h=100, w=250), g1)   # governor downscale changed the crop
    assert diff == 0.0 and g2.shape != g1.shape              # reset, never a spurious fire


# --- H1-A1: gap-consumed high-diff must NOT be absorbed silently -------------
def test_watch_step_high_diff_gap_blocked_latches_not_absorbs():
    # a kill lands (diff=20) inside the 1.2s refractory after a prior fire at t=500ms
    action, advance, latch = kf_watch_step(20.0, 800.0, 500.0, False)
    assert action == "none" and advance is False and latch is True   # latch it, do NOT absorb


def test_watch_step_below_threshold_advances_baseline():
    action, advance, latch = kf_watch_step(0.0, 800.0, 500.0, False)
    assert action == "none" and advance is True and latch is False    # static, nothing pending


def test_watch_step_gap_then_static_sequence_eventually_fires():
    # THE H1-A1 regression: kill appears during refractory, stays visible; fires once gap opens.
    a1 = kf_watch_step(20.0, 800.0, 500.0, False)           # kill during gap -> latch
    assert a1 == ("none", False, True)
    a2 = kf_watch_step(20.0, 1000.0, 500.0, True)           # held (has_pending), gap still closed
    assert a2 == ("none", False, False)
    a3 = kf_watch_step(20.0, 1750.0, 500.0, True)           # gap open -> fire the latched crop
    assert a3[0] == "fire_pending" and a3[1] is True


# --- H1-A6: fade-before-gap must still fire the FROZEN crop -------------------
def test_watch_step_fade_before_gap_still_fires_pending():
    # kill appears in refractory (latch), then FADES to static before the gap opens; the frozen
    # crop must still fire once the gap opens (old rule absorbed the empty frame -> permanent miss).
    a1 = kf_watch_step(20.0, 800.0, 500.0, False)           # kill -> latch
    assert a1[2] is True
    a2 = kf_watch_step(0.0, 1100.0, 500.0, True)            # faded, gap closed -> HOLD, no absorb
    assert a2 == ("none", False, False)
    a3 = kf_watch_step(0.0, 1750.0, 500.0, True)            # gap open -> fire the frozen kill crop
    assert a3[0] == "fire_pending" and a3[1] is True


def test_watch_step_continuous_change_gap_open_fires_current():
    # no pending, change present, gap already open -> latch + fire immediately (fire the fresh crop)
    action, advance, latch = kf_watch_step(20.0, 2000.0, 500.0, False)
    assert action == "fire_pending" and latch is True and advance is True


# --- H1-A2: substring / OCR-poison killer must NOT author --------------------
def test_own_killer_boundary_equality():
    own = canon("QorTrola30")
    assert is_own_killer_token("QorTrola30", own)            # exact
    assert is_own_killer_token("QorTroIa3O", own)            # OCR confusables fold to the same canon
    assert not is_own_killer_token("QorTro1a300", own)       # A2 poison: contains-but-not-equals
    assert not is_own_killer_token("QorTrola300", own)
    assert not is_own_killer_token("xxQorTrola30", own)


def test_oracle_poison_handle_not_authored():
    orc = KillfeedAuthorshipOracle("QorTrola30")
    orc.push_trigger(1000.0)
    orc.push_killfeed_line(1300.0, "QorTro1a300 somevictim")  # extension-name poison
    res = orc.verdict()
    assert res.own_kills == 0 and res.bound_kills == 0        # zero-false-read holds


def test_classify_rows_poison_is_other_not_own():
    rows = [["QorTro1a300", "victim"]]
    out = classify_rows(rows, "QorTrola30")
    assert out[0][0] == OTHER_ROW                            # not OWN_KILL


# --- H1-A3: short-killer death must NOT count as a kill ----------------------
def test_oracle_short_killer_death_not_authored():
    orc = KillfeedAuthorshipOracle("QorTrola30")
    orc.push_trigger(1000.0)
    orc.push_killfeed_line(1300.0, "Efram1 QorTrola30")      # killer left, YOU are the victim
    res = orc.verdict()
    assert res.own_kills == 0                                # your death is never your kill


def test_oracle_real_own_kill_still_authors():
    orc = KillfeedAuthorshipOracle("QorTrola30")
    orc.push_trigger(1000.0)
    orc.push_killfeed_line(1300.0, "QorTrola30 Efram1")      # YOU killed Efram1
    res = orc.verdict()
    assert res.own_kills == 1 and res.bound_kills == 1       # true positive preserved


def test_classify_rows_death_vs_kill():
    assert classify_rows([["Efram1", "QorTrola30"]], "QorTrola30")[0][0] == OWN_DEATH
    assert classify_rows([["QorTrola30", "Efram1"]], "QorTrola30")[0][0] == OWN_KILL
