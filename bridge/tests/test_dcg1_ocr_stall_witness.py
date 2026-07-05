"""D-CG-1 — OCR as an additional stall witness in CANDIDATE regime (operator-approved 2026-07-04).

The finding (F-CG-1, corpus-growth session): a WEAK BR cut was doubly stuck — its own sub-floor scores never
accumulated K=3, AND the stall-demote trigger keyed on feed_v1 raw >=0.66, precisely the marginal signal in
BR rendering. The fix lets an OCR killer-slot read count as `raw_killer_authored` so witnessed misses
accumulate and weak cuts demote-and-recut.

THE FP-INTERACTION RAIL (the condition HOLD'd on): the witness path is structurally DEMOTE-ONLY —
`raw_killer_authored` feeds observe_candidate's stall counter and nothing else. These tests pin that a
stream of OCR witnesses can never promote, never fold AUTHORED, and never touch R3's fp-fire path; the only
reachable outcome is `candidate_demoted_stall` -> BOOTSTRAP (self-healing recut). Cost/splice gates pinned
too: OCR fires only on a FRESH row with a SUB-floor candidate score and the bootstrap flag ON.
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


class _Res:
    def __init__(self, score, x, y):
        self.score, self.evidence = score, {"x_frac": x, "y_frac": y, "region": None, "slot": None}
        self.verdict = type("V", (), {"value": "UNVERIFIABLE"})()   # feed_v1 raw NEVER authored (BR shape)
        self.handle = "q0rtr01a30"


_READ = OcrRead(True, "Qortrola30", 100.0, 0.16, 0.30, "killer", match_kind="exact",
                engine="tesseract_row_v1")
_ABSTAIN = OcrRead(False, "", 0.0, None, None, None)


def _rgc(tmp_path):
    rgc = RetinaGameCapture.__new__(RetinaGameCapture)
    rgc._inline_monitor = InlineAuthorshipMonitor(match_floor=0.66, killer_max_frac=0.28,
                                                  feed_region_max_yfrac=0.42, anchor_id="feed_v1")
    rgc._session_anchor = SessionAnchorGenerator(session_id="t", killer_max_frac=0.28,
                                                 feed_region_max_yfrac=0.42)
    rgc._anchor = np.ones((10, 10), np.uint8)
    rgc._prev_killer_gray = None
    rgc._last_killer_fresh_ms = -1e18
    rgc._session_anchor_dir = str(tmp_path)
    rgc._ocr_bootstrap_enabled = True
    return rgc


def _fresh(rgc, value):
    def _f(bgr, now_ms):
        if value:
            rgc._last_killer_fresh_ms = now_ms
        return value
    return _f


def _to_candidate(rgc, monkeypatch, bgr):
    """Drive the generator BOOTSTRAP -> CANDIDATE via an OCR-verified catch (the wired path)."""
    monkeypatch.setattr(rgc, "_ocr_bootstrap_read", lambda b: _READ)
    monkeypatch.setattr(rgc, "_cut_session_anchor", lambda b, x, y: (np.ones((8, 40), np.uint8), "sha_w"))
    monkeypatch.setattr(rgc, "_killer_fresh_row", _fresh(rgc, True))
    rgc._session_anchor_fold(bgr, _Res(0.5, 0.22, 0.97), _Res(0.5, 0.22, 0.97).evidence, 1000.0)
    assert rgc._session_anchor.regime == "CANDIDATE"


def test_br_starvation_now_demotes_and_recuts(tmp_path, monkeypatch):
    # THE F-CG-1 scenario: candidate sub-floor on real kill rows, feed_v1 raw never authored (BR), OCR reads
    # each fresh row -> stalls accumulate -> candidate_demoted_stall at the limit (was: stuck forever).
    rgc = _rgc(tmp_path)
    bgr = np.zeros((100, 100, 3), np.uint8)
    monkeypatch.setattr(kc, "killer_slot_best", lambda *a, **k: (0.40, 0.18, 0.30))   # weak cut, sub-floor
    _to_candidate(rgc, monkeypatch, bgr)
    for t in (2000.0, 3000.0, 4000.0):                        # 3 fresh kill rows the candidate misses
        rgc._session_anchor_fold(bgr, _Res(0.5, 0.22, 0.97), _Res(0.5, 0.22, 0.97).evidence, t)
    st = rgc._session_anchor.status()
    assert rgc._session_anchor.regime == "BOOTSTRAP"          # demote-and-recut fired
    assert st["failures"] and st["failures"][-1]["kind"] == "candidate_stall"
    assert st["fp_fires"] == 0                                # R3's fp path untouched by the witness


def test_ocr_witness_can_never_promote_or_author(tmp_path, monkeypatch):
    # FP-interaction rail: an endless stream of OCR witnesses never promotes and never folds AUTHORED —
    # demote is the ONLY reachable transition from witness pressure.
    rgc = _rgc(tmp_path)
    rgc._session_anchor.stall_limit = 99                      # keep it in CANDIDATE under max pressure
    bgr = np.zeros((100, 100, 3), np.uint8)
    monkeypatch.setattr(kc, "killer_slot_best", lambda *a, **k: (0.40, 0.18, 0.30))
    _to_candidate(rgc, monkeypatch, bgr)
    mon = rgc._inline_monitor
    mon.mark_onset(1500.0)
    for t in range(2000, 12000, 1000):                        # 10 witnessed misses
        rgc._session_anchor_fold(bgr, _Res(0.5, 0.22, 0.97), _Res(0.5, 0.22, 0.97).evidence, float(t))
    assert rgc._session_anchor.regime == "CANDIDATE"          # never promoted
    assert rgc._session_anchor.status()["promotions"] == 0
    rec = mon.mark_onset(99000.0)
    assert rec is None or rec["verdict"] != "AUTHORED_PRESENT"   # no authorship from witnesses


def test_ocr_abstain_never_stalls(tmp_path, monkeypatch):
    # FAIL-OPEN: an abstaining read (matched=False) is NOT a witnessed miss — no stall accumulates.
    rgc = _rgc(tmp_path)
    bgr = np.zeros((100, 100, 3), np.uint8)
    monkeypatch.setattr(kc, "killer_slot_best", lambda *a, **k: (0.40, 0.18, 0.30))
    _to_candidate(rgc, monkeypatch, bgr)
    monkeypatch.setattr(rgc, "_ocr_bootstrap_read", lambda b: _ABSTAIN)
    for t in (2000.0, 3000.0, 4000.0, 5000.0):
        rgc._session_anchor_fold(bgr, _Res(0.5, 0.22, 0.97), _Res(0.5, 0.22, 0.97).evidence, t)
    assert rgc._session_anchor.regime == "CANDIDATE"          # no demote from abstentions
    assert not rgc._session_anchor.status()["failures"]


def test_witness_gates_cost_discipline(tmp_path, monkeypatch):
    # OCR runs ONLY on (fresh AND sub-floor AND enabled): a clearing candidate or a non-fresh frame or the
    # flag OFF must not invoke the OCR engine at all (bootstrap-moment cost discipline extended, not broken).
    rgc = _rgc(tmp_path)
    bgr = np.zeros((100, 100, 3), np.uint8)
    monkeypatch.setattr(kc, "killer_slot_best", lambda *a, **k: (0.40, 0.18, 0.30))
    _to_candidate(rgc, monkeypatch, bgr)
    calls = {"n": 0}

    def _counting_read(b):
        calls["n"] += 1
        return _READ
    monkeypatch.setattr(rgc, "_ocr_bootstrap_read", _counting_read)
    # (a) candidate CLEARS the floor -> no OCR
    monkeypatch.setattr(kc, "killer_slot_best", lambda *a, **k: (0.90, 0.18, 0.30))
    rgc._session_anchor_fold(bgr, _Res(0.5, 0.22, 0.97), _Res(0.5, 0.22, 0.97).evidence, 2000.0)
    assert calls["n"] == 0
    # (b) sub-floor but NOT fresh -> no OCR
    monkeypatch.setattr(kc, "killer_slot_best", lambda *a, **k: (0.40, 0.18, 0.30))
    monkeypatch.setattr(rgc, "_killer_fresh_row", _fresh(rgc, False))
    rgc._session_anchor_fold(bgr, _Res(0.5, 0.22, 0.97), _Res(0.5, 0.22, 0.97).evidence, 3000.0)
    assert calls["n"] == 0
    # (c) sub-floor + fresh but flag OFF -> no OCR
    rgc._ocr_bootstrap_enabled = False
    monkeypatch.setattr(rgc, "_killer_fresh_row", _fresh(rgc, True))
    rgc._session_anchor_fold(bgr, _Res(0.5, 0.22, 0.97), _Res(0.5, 0.22, 0.97).evidence, 4000.0)
    assert calls["n"] == 0
    # (d) all three gates open -> OCR fires exactly once for this crop
    rgc._ocr_bootstrap_enabled = True
    rgc._session_anchor_fold(bgr, _Res(0.5, 0.22, 0.97), _Res(0.5, 0.22, 0.97).evidence, 5000.0)
    assert calls["n"] == 1
