"""Integration test for the WIRED session-anchor path — drives the real `_session_anchor_fold` worker
method end-to-end (not the replay harness that mirrors it), so the wiring is regression-locked before the
live match. Constructs a bare RetinaGameCapture (bypassing WGC __init__) with the real InlineAuthorshipMonitor
and SessionAnchorGenerator, scripts killer_slot_best + fresh-row, and asserts: bootstrap-catch -> K=3
promote -> AUTHORED composite carrying the SESSION regime tag (CF1 through the real fold), with NO AUTHORED
before promotion (R1 coverage gap)."""
from __future__ import annotations

import numpy as np
import pytest

pytest.importorskip("cv2")

from l9_presence import killfeed_cv as kc
from l9_presence.killfeed_inline import InlineAuthorshipMonitor
from l9_presence.killfeed_session_anchor import SessionAnchorGenerator
from vapi_bridge.qortroller_retina_capture import RetinaGameCapture


class _Res:                                          # stand-in for the classify_panel result (victim path)
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
    rgc._anchor = np.ones((10, 10), np.uint8)             # opaque; killer_slot_best is scripted
    rgc._prev_killer_gray = None
    rgc._last_killer_fresh_ms = -1e18
    rgc._session_anchor_dir = str(tmp_path)
    return rgc


def _fresh_mock(rgc, value):
    """Faithful _killer_fresh_row stand-in: mirrors the real method's side effect of setting
    _last_killer_fresh_ms on a fresh row (is_background reads that field — the coupling this locks in)."""
    def _f(bgr, now_ms):
        if value:
            rgc._last_killer_fresh_ms = now_ms
        return value
    return _f


def test_wired_fold_bootstrap_to_promote_to_authored_with_session_tag(tmp_path, monkeypatch):
    rgc = _bare_rgc(tmp_path)
    bgr = np.zeros((100, 100, 3), np.uint8)
    # scripted killer_slot_best sequence: catch (0.60) -> 3x candidate (0.70) -> promoted crop (0.75)
    seq = iter([(0.60, 0.18, 0.30), (0.70, 0.18, 0.30), (0.70, 0.18, 0.30),
                (0.72, 0.18, 0.30), (0.75, 0.18, 0.30)])
    monkeypatch.setattr(kc, "killer_slot_best", lambda *a, **k: next(seq))
    monkeypatch.setattr(rgc, "_killer_fresh_row", _fresh_mock(rgc, True))           # every crop a fresh row
    monkeypatch.setattr(rgc, "_cut_session_anchor", lambda b, x, y: (np.ones((8, 40), np.uint8), "sha_t"))

    mon = rgc._inline_monitor
    mon.mark_onset(1000.0)
    ev_roster = _Res(0.5, 0.22, 0.97).evidence          # feed_v1 res at roster -> victim path skips it
    # crop 1: bootstrap catch (0.60, fresh) -> CANDIDATE
    rgc._session_anchor_fold(bgr, _Res(0.5, 0.22, 0.97), ev_roster, 1100.0)
    assert rgc._session_anchor.regime == "CANDIDATE"
    # crops 2-4: candidate matches -> after the 3rd, PROMOTED
    rgc._session_anchor_fold(bgr, _Res(0.5, 0.22, 0.97), ev_roster, 1200.0)
    rgc._session_anchor_fold(bgr, _Res(0.5, 0.22, 0.97), ev_roster, 1300.0)
    assert rgc._session_anchor.regime == "CANDIDATE"     # 2/3 so far, no AUTHORED folded yet (R1 gap)
    rgc._session_anchor_fold(bgr, _Res(0.5, 0.22, 0.97), ev_roster, 1400.0)
    assert rgc._session_anchor.is_promoted()
    # crop 5: PROMOTED -> killer 0.75 folds AUTHORED with the session tag
    rgc._session_anchor_fold(bgr, _Res(0.5, 0.22, 0.97), ev_roster, 1500.0)
    rec = mon.mark_onset(9000.0)                          # resolve the window
    assert rec is not None and rec["verdict"] == "AUTHORED_PRESENT"
    assert rec["anchor"] == "session_t@0.66"             # CF1: the session tag flows through the REAL fold


def test_wired_fold_no_authored_before_promotion(tmp_path, monkeypatch):
    # R1: a strong killer score while still in CANDIDATE must NOT emit AUTHORED (kills-before-promotion gap).
    rgc = _bare_rgc(tmp_path, k=99)                       # never promotes within the test
    bgr = np.zeros((100, 100, 3), np.uint8)
    monkeypatch.setattr(kc, "killer_slot_best", lambda *a, **k: (0.90, 0.18, 0.30))   # very strong killer
    monkeypatch.setattr(rgc, "_killer_fresh_row", _fresh_mock(rgc, True))
    monkeypatch.setattr(rgc, "_cut_session_anchor", lambda b, x, y: (np.ones((8, 40), np.uint8), "sha_t"))
    mon = rgc._inline_monitor
    mon.mark_onset(1000.0)
    for t in (1100.0, 1200.0, 1300.0):                   # catch then candidate; 0.90 each but K=99 unmet
        rgc._session_anchor_fold(bgr, _Res(0.5, 0.22, 0.97), _Res(0.5, 0.22, 0.97).evidence, t)
    assert rgc._session_anchor.regime == "CANDIDATE" and not rgc._session_anchor.is_promoted()
    rec = mon.mark_onset(9000.0)
    # no killer folded to the composite (promoted-only) -> not AUTHORED
    assert rec is None or rec["verdict"] != "AUTHORED_PRESENT"


def test_wired_fold_victim_path_stays_static_feed_v1(tmp_path, monkeypatch):
    # Scope: a feed_v1 VICTIM match folds OWN_DEATH tagged static feed_v1, independent of the killer generator.
    rgc = _bare_rgc(tmp_path)
    bgr = np.zeros((100, 100, 3), np.uint8)
    monkeypatch.setattr(kc, "killer_slot_best", lambda *a, **k: (0.10, None, None))    # no killer signal
    monkeypatch.setattr(rgc, "_killer_fresh_row", _fresh_mock(rgc, False))
    mon = rgc._inline_monitor
    mon.mark_onset(1000.0)
    res = _Res(0.73, 0.40, 0.30)                          # feed_v1 global-best at VICTIM position
    rgc._session_anchor_fold(bgr, res, res.evidence, 1100.0)
    rec = mon.mark_onset(9000.0)
    assert rec is not None and rec["verdict"] == "OWN_DEATH" and rec["anchor"] == "feed_v1"
