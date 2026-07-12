"""Tests for l9_presence.killfeed_raw_reader — the left-middle RAW-OCR bridge to authorship.

Deterministic: the OCR fn is INJECTED (synthetic tokens), the frame is a numpy placeholder, and the
REAL KillfeedAuthorshipOracle judges the produced lines. Reproduces the live kill1 result shape
(1 own kill + 2 teammate kills -> author only yours) and the short-killer death edge the token-based
classifier handles but the oracle's string-offset heuristic does not.
"""
import numpy as np

from l9_presence import killfeed_raw_reader as kr
from l9_presence.killfeed_authorship import KillfeedAuthorshipOracle
from l9_presence.killfeed_ocr_bootstrap import OTHER_ROW, OWN_DEATH, OWN_KILL

HANDLE = "QorTrola30"


def _frame(h=1080, w=1920):
    return np.zeros((h, w, 3), dtype=np.uint8)


def _ocr(tokens):
    """An injected OCR fn returning fixed (x, y, text) tokens regardless of the crop."""
    return lambda crop: tokens


# --- crop_roi -------------------------------------------------------------
def test_crop_roi_left_middle_pixels():
    crop = kr.crop_roi(_frame(), kr.DEFAULT_KILLFEED_ROI)   # 0.0,0.45,0.26,0.19 on 1920x1080
    assert crop is not None
    assert crop.shape[:2] == (691 - 486, 499 - 0)           # y[486:691], x[0:499]


def test_crop_roi_degenerate_none():
    assert kr.crop_roi(_frame(), (0.0, 0.0, 0.0, 0.0)) is None


# --- grouping / lines -----------------------------------------------------
def test_group_rows_clusters_by_y_and_orders_killer_left():
    toks = [(200, 10, "victimA"), (10, 10, "Qortrola30"),
            (210, 40, "victimB"), (12, 40, "rosa sparks")]
    assert kr.group_rows(toks) == [["Qortrola30", "victimA"], ["rosa sparks", "victimB"]]


def test_rows_to_lines_joins_and_drops_empty():
    assert kr.rows_to_lines([["Qortrola30", "AWOLNoob"], [], ["  "]]) == ["Qortrola30 AWOLNoob"]


# --- token-based classification (the robust, proven rule) -----------------
def test_classify_own_kill_killer_slot():
    rows = [["Qortrola30", "KING___2008"]]
    assert kr.classify_rows(rows, HANDLE)[0][0] == OWN_KILL


def test_classify_teammate_is_other():
    rows = [["rosa sparks", "Tee_Nugget"]]
    assert kr.classify_rows(rows, HANDLE)[0][0] == OTHER_ROW


def test_classify_own_death_short_killer_is_not_a_kill():
    # `Efram1 -> Qortrola30`: you DIED. The oracle's string-offset heuristic (6/16 < 0.5) would misread
    # this as a kill; the token-based classifier sees your handle is NOT the leftmost token -> OWN_DEATH.
    rows = [["Efram1", "Qortrola30"]]
    assert kr.classify_rows(rows, HANDLE)[0][0] == OWN_DEATH


def test_classify_ocr_noise_still_own_kill():
    rows = [["Q0rtro1a3O", "AWOLNoob"]]        # tesseract-style o/0, l/1, O confusions
    assert kr.classify_rows(rows, HANDLE)[0][0] == OWN_KILL


# --- end-to-end read (injected OCR) --------------------------------------
def test_read_feed_lines_end_to_end():
    toks = [(10, 12, "Qortrola30"), (240, 12, "KING___2008")]
    assert kr.read_feed_lines(_frame(), ocr_fn=_ocr(toks)) == ["Qortrola30 KING___2008"]


def test_own_kill_count_reproduces_kill1_shape():
    # one frame's rows: your kill + two teammate kills (the live kill1 differentiation)
    toks = [(10, 12, "Qortrola30"), (240, 12, "KING___2008"),
            (12, 44, "rosa sparks"), (250, 44, "Tee_Nugget"),
            (11, 76, "Deslayer295"), (245, 76, "OxOLover")]
    verdicts = [v for v, _, _ in kr.classify_rows(kr.read_rows(_frame(), ocr_fn=_ocr(toks)), HANDLE)]
    assert verdicts.count(OWN_KILL) == 1
    assert verdicts.count(OTHER_ROW) == 2
    assert kr.own_kill_count(_frame(), own_handle=HANDLE, ocr_fn=_ocr(toks)) == 1


def test_read_failopen_on_ocr_error():
    def boom(crop):
        raise RuntimeError("ocr blew up")
    assert kr.read_rows(_frame(), ocr_fn=boom) == []
    assert kr.read_feed_lines(_frame(), ocr_fn=lambda crop: []) == []


# --- integration with the REAL oracle (the existing feed_killfeed_text path) --
def test_lines_feed_the_real_oracle_common_case():
    toks = [(10, 12, "Qortrola30"), (240, 12, "KING___2008"),
            (12, 44, "rosa sparks"), (250, 44, "Tee_Nugget")]
    text = kr.read_feed_text(_frame(), ocr_fn=_ocr(toks))
    orc = KillfeedAuthorshipOracle(HANDLE)
    for line in text.splitlines():
        orc.push_killfeed_line(1000.0, line)
    res = orc.verdict()
    assert res.own_kills == 1
    assert res.other_kills == 1
