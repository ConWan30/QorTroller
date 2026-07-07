"""C1 (narrow, Tesseract-era) — the REAL `_killer_fresh_row` on the dynamic->freeze transition seam.

The wiring tests (test_session_anchor_wiring) pin the R2 gate with a MOCKED fresh-row; the genuinely
untested seam is the real frame-diff's behavior when a STATIC freeze-frame (pause / kill-cam still / spliced
still) appears AFTER dynamic content:

  - cold-start freeze: prev is None then diff=0 -> fresh=False on every frame — the gate holds TRIVIALLY
    (pinned here as a regression, proved by code analysis before this test existed);
  - dynamic->freeze TRANSITION: |freeze - prior dynamic| can exceed _SESSION_ANCHOR_FRESH_DIFF (6.0) ->
    fresh=True for EXACTLY ONE frame. That one-frame window is REAL: an OCR-matching kill row inside the
    freeze CAN bootstrap-cut on the transition frame (honest finding, pinned — not hidden);
  - what contains it: the freeze then STOPS being fresh, `_last_killer_fresh_ms` ages past
    _SESSION_ANCHOR_ROW_PERSIST_MS (5 s), the frozen content flips to is_background=True, and the candidate
    (cut from that very freeze) scores >=0.66 on it -> R3 `candidate_demoted_fp` -> back to BOOTSTRAP.
    A freeze can SEED a candidate for at most one persist window; it cannot HOLD one.

Out of scope (architectural, not unit-testable here): the fold only runs inside R2-gated classification
calls, so a freeze with NO live R2 input never reaches this code at all (R2 ∧ B2 invariant). Normal-motion
replay is A2/A4's coverage, not C1's.

TWO-LAYER SHAPE (do not flatten to "pass"): the exposure (one-frame fresh transition CAN seed a candidate)
is real and structural; the containment is the DEMOTE-PERSIST TIMER, not fresh-row differencing. The
security guarantee rests on _SESSION_ANCHOR_ROW_PERSIST_MS — the 3rd instance of an operational timing
parameter turning out load-bearing for security (after R2 window width -> splice FAR, and the escape-hatch
witness signal -> BR stall deadlock). Changing that constant is a security decision, not tuning.
"""
from __future__ import annotations

import numpy as np
import pytest

pytest.importorskip("cv2")

from l9_presence import killfeed_cv as kc
from l9_presence.killfeed_inline import InlineAuthorshipMonitor
from l9_presence.killfeed_ocr_bootstrap import OcrRead
from l9_presence.killfeed_session_anchor import SessionAnchorGenerator
from bridge.vapi_bridge.qortroller_retina_capture import RetinaGameCapture


class _Res:                                          # classify_panel result stand-in (victim path only)
    def __init__(self, score, x, y):
        self.score, self.evidence = score, {"x_frac": x, "y_frac": y, "region": None, "slot": None}
        self.verdict = type("V", (), {"value": "UNVERIFIABLE"})()
        self.handle = "q0rtr01a30"


def _bare_rgc(tmp_path, k=3):
    rgc = RetinaGameCapture.__new__(RetinaGameCapture)     # bypass WGC-attaching __init__
    rgc._inline_monitor = InlineAuthorshipMonitor(match_floor=0.66, killer_max_frac=0.28,
                                                  feed_region_max_yfrac=0.42, anchor_id="feed_v1")
    rgc._session_anchor = SessionAnchorGenerator(session_id="t", killer_max_frac=0.28,
                                                 feed_region_max_yfrac=0.42, k_consistency=k)
    rgc._anchor = np.ones((10, 10), np.uint8)
    rgc._prev_killer_gray = None                          # REAL fresh-row state (not mocked in this file)
    rgc._last_killer_fresh_ms = -1e18
    rgc._session_anchor_dir = str(tmp_path)
    rgc._ocr_bootstrap_enabled = False
    return rgc


def _dynamic_frame(seed=7):
    rng = np.random.default_rng(seed)
    return rng.integers(0, 255, (100, 100, 3), dtype=np.uint8)


_FREEZE = np.full((100, 100, 3), 180, np.uint8)           # the still that persists after the transition


def test_cold_start_freeze_is_never_fresh(tmp_path):
    # prev=None on frame 1, identical frames after -> diff 0 -> the gate holds trivially forever.
    rgc = _bare_rgc(tmp_path)
    assert rgc._killer_fresh_row(_FREEZE, 1000.0) is False        # no prior region yet
    assert rgc._killer_fresh_row(_FREEZE, 1100.0) is False        # diff == 0
    assert rgc._killer_fresh_row(_FREEZE.copy(), 1200.0) is False
    assert rgc._last_killer_fresh_ms == -1e18                     # never marked fresh


def test_transition_is_fresh_for_exactly_one_frame(tmp_path):
    # dynamic -> freeze: the FIRST freeze frame diffs against the prior dynamic region -> fresh=True once;
    # every subsequent identical freeze frame -> False. This is the one-frame window, pinned.
    rgc = _bare_rgc(tmp_path)
    rgc._killer_fresh_row(_dynamic_frame(), 1000.0)               # prime prev with dynamic content
    assert rgc._killer_fresh_row(_FREEZE, 1100.0) is True         # the transition frame
    assert rgc._last_killer_fresh_ms == 1100.0
    for t in (1200.0, 1300.0, 1400.0):
        assert rgc._killer_fresh_row(_FREEZE, t) is False         # frozen -> never fresh again
    assert rgc._last_killer_fresh_ms == 1100.0                    # last-fresh pinned at the transition


def test_transition_frame_can_seed_a_candidate_honest_finding(tmp_path, monkeypatch):
    # HONEST FINDING (not a defect fix): on the ONE transition frame, an OCR-verified killer-slot read inside
    # the freeze passes the real fresh-row gate and cuts -> CANDIDATE. C1 documents the window, then T4 pins
    # what contains it.
    rgc = _bare_rgc(tmp_path)
    rgc._ocr_bootstrap_enabled = True
    monkeypatch.setattr(kc, "killer_slot_best", lambda *a, **k: (0.50, 0.16, 0.30))   # sub-floor template
    monkeypatch.setattr(rgc, "_ocr_bootstrap_read",
                        lambda b: OcrRead(True, "Qortrola30", 100.0, 0.16, 0.30, "killer",
                                          match_kind="exact", engine="tesseract_row_v1"))
    monkeypatch.setattr(rgc, "_cut_session_anchor", lambda b, x, y: (np.ones((8, 40), np.uint8), "sha_frz"))
    rgc._killer_fresh_row(_dynamic_frame(), 1000.0)               # real gate, primed with dynamic content
    rgc._inline_monitor.mark_onset(1050.0)
    rgc._session_anchor_fold(_FREEZE, _Res(0.5, 0.22, 0.97), _Res(0.5, 0.22, 0.97).evidence, 1100.0)
    assert rgc._session_anchor.regime == "CANDIDATE"              # the one-frame window is real
    # and the SAME freeze one frame later can no longer bootstrap anything (regime aside, fresh is gone)
    assert rgc._killer_fresh_row(_FREEZE, 1200.0) is False


def test_frozen_candidate_self_demotes_after_persist_window(tmp_path, monkeypatch):
    # Containment: the candidate cut FROM the freeze keeps scoring >=0.66 on the same frozen content; once
    # _last_killer_fresh_ms ages past 5 s the content is is_background=True -> R3 candidate_demoted_fp ->
    # BOOTSTRAP. No AUTHORED composite is emitted (promoted-only fold) and the machine logs the FP.
    rgc = _bare_rgc(tmp_path)
    rgc._ocr_bootstrap_enabled = True
    scores = iter([(0.50, 0.16, 0.30),                            # transition: sub-floor, OCR carries the cut
                   (0.90, 0.16, 0.30), (0.90, 0.16, 0.30),        # frozen frames inside the persist window
                   (0.90, 0.16, 0.30)])                           # frozen frame PAST the window -> FP fire
    monkeypatch.setattr(kc, "killer_slot_best", lambda *a, **k: next(scores))
    monkeypatch.setattr(rgc, "_ocr_bootstrap_read",
                        lambda b: OcrRead(True, "Qortrola30", 100.0, 0.16, 0.30, "killer",
                                          match_kind="exact", engine="tesseract_row_v1"))
    monkeypatch.setattr(rgc, "_cut_session_anchor", lambda b, x, y: (np.ones((8, 40), np.uint8), "sha_frz"))
    mon = rgc._inline_monitor
    rgc._killer_fresh_row(_dynamic_frame(), 1000.0)
    mon.mark_onset(1050.0)
    rgc._session_anchor_fold(_FREEZE, _Res(0.5, 0.22, 0.97), _Res(0.5, 0.22, 0.97).evidence, 1100.0)
    assert rgc._session_anchor.regime == "CANDIDATE"
    # two frozen observations inside the 5 s persist window: K=3 unmet, still CANDIDATE
    rgc._session_anchor_fold(_FREEZE, _Res(0.5, 0.22, 0.97), _Res(0.5, 0.22, 0.97).evidence, 2000.0)
    rgc._session_anchor_fold(_FREEZE, _Res(0.5, 0.22, 0.97), _Res(0.5, 0.22, 0.97).evidence, 3000.0)
    assert rgc._session_anchor.regime == "CANDIDATE"
    # past the persist window (1100 + 5000): frozen content is background; the 0.90 self-fire -> demote
    rgc._session_anchor_fold(_FREEZE, _Res(0.5, 0.22, 0.97), _Res(0.5, 0.22, 0.97).evidence, 6200.0)
    st = rgc._session_anchor.status()
    assert rgc._session_anchor.regime == "BOOTSTRAP" and st["fp_fires"] == 1
    assert st["failures"] and st["failures"][-1]["kind"] == "candidate_fp"
    rec = mon.mark_onset(9000.0)                                  # resolve the window
    assert rec is None or rec["verdict"] != "AUTHORED_PRESENT"    # never promoted -> nothing AUTHORED
