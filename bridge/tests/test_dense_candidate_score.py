"""Option 3 — dense-candidate scoring (live-authorship promotion fix) tests.

Fix: docs/live-authorship-dense-candidate-fix-2026-07-10.md. The dense worker scores the dense panel
stash against the CANDIDATE template so the session anchor promotes (K=3) / stall-recuts even when R2
windows are sparse (the M18/rp4_rp live-0-authored failure), WITHOUT OCR, off the event loop, with the
K=3/0.66/FP/stall gate UNCHANGED. These tests drive `_dense_candidate_observe` directly (the pure
CANDIDATE-subset), mocking `killer_slot_best`, so no WGC/cv2 window is constructed.

Pins: flag default-OFF (T1) · dense K-progress promotes at K=3 (T2) · never calls OCR (T3) · feed_v1
stall-recut with no OCR (T5) · FP-demote preserved on background (T6) · no-op outside CANDIDATE (T8) ·
C3 dense-private fresh-row never touches the window path · generator mutation under _session_anchor_lock.
"""
from __future__ import annotations

import threading
from types import SimpleNamespace

import numpy as np
import pytest

from bridge.vapi_bridge.qortroller_retina_capture import RetinaGameCapture, _dense_score_enabled
from l9_presence.killfeed_session_anchor import BOOTSTRAP, CANDIDATE, PROMOTED, SessionAnchorGenerator

_BGR = np.zeros((50, 50, 3), dtype=np.uint8)   # sentinel crop; killer_slot_best is mocked in observe tests


def _cand_gen() -> SessionAnchorGenerator:
    gen = SessionAnchorGenerator(session_id="test")
    gen._regime = CANDIDATE
    gen._candidate_anchor = object()           # sentinel candidate template
    gen._candidate_sha = "sha16test"
    gen._consistent = 0
    gen._stalls = 0
    return gen


def _make_cap(gen: SessionAnchorGenerator) -> RetinaGameCapture:
    cap = RetinaGameCapture.__new__(RetinaGameCapture)   # bypass the WGC-bound __init__
    cap._session_anchor = gen
    cap._anchor = object()                     # feed_v1/bootstrap template sentinel
    cap._inline_monitor = SimpleNamespace(feed_region_max_yfrac=0.42, killer_max_frac=0.28)
    cap._session_anchor_lock = threading.Lock()
    cap._dense_prev_killer_gray = None
    cap._dense_last_killer_fresh_ms = -1e18
    return cap


def _patch_ksb(monkeypatch, gen, cap, *, cand_score: float, feed_score: float) -> None:
    """Mock killer_slot_best: candidate template -> cand_score, feed_v1 template -> feed_score.
    x/y frac = (0.1, 0.1) is inside the killer feed geometry (< 0.28 / < 0.42)."""
    cand, feed = gen._candidate_anchor, cap._anchor

    def fake(bgr, anchor):
        return (cand_score if anchor is cand else feed_score, 0.1, 0.1)

    monkeypatch.setattr("l9_presence.killfeed_cv.killer_slot_best", fake)


def _active_feed(cap: RetinaGameCapture) -> None:
    """is_bg=False: fresh-row marks the feed active at each observe (last_fresh := now)."""
    cap._dense_killer_fresh_row = lambda bgr, now: (setattr(cap, "_dense_last_killer_fresh_ms", now) or True)


def _background(cap: RetinaGameCapture) -> None:
    """is_bg=True: no fresh row; last_fresh stays far in the past."""
    cap._dense_killer_fresh_row = lambda bgr, now: False
    cap._dense_last_killer_fresh_ms = -1e18


# ------------------------------------------------------------------ T1: flag default-OFF + truthy set
def test_t1_flag_default_off_and_truthy_set():
    assert _dense_score_enabled({}) is False
    assert _dense_score_enabled({"RETINA_CANDIDATE_DENSE_SCORE": "0"}) is False
    assert _dense_score_enabled({"RETINA_CANDIDATE_DENSE_SCORE": "off"}) is False
    for v in ("1", "true", "TRUE", "Yes", "on"):
        assert _dense_score_enabled({"RETINA_CANDIDATE_DENSE_SCORE": v}) is True


# ------------------------------------------------------------------ T2: dense K-progress promotes at K=3
def test_t2_dense_kprogress_promotes_at_k3(monkeypatch):
    gen = _cand_gen()
    cap = _make_cap(gen)
    _patch_ksb(monkeypatch, gen, cap, cand_score=0.7, feed_score=0.0)   # candidate clears, no stall
    _active_feed(cap)
    evs = [cap._dense_candidate_observe(_BGR, 1000.0 + i) for i in range(3)]
    assert gen.regime == PROMOTED
    assert evs[-1]["event"] == "promoted"
    assert evs[0]["event"] == "candidate_progress"   # no classify window was needed


# ------------------------------------------------------------------ T3: dense path NEVER calls OCR
def test_t3_dense_never_calls_ocr(monkeypatch):
    import l9_presence.killfeed_ocr_bootstrap as ob
    calls = {"n": 0}
    monkeypatch.setattr(ob, "tight_row_ocr", lambda *a, **k: calls.__setitem__("n", calls["n"] + 1))
    gen = _cand_gen()
    cap = _make_cap(gen)
    _patch_ksb(monkeypatch, gen, cap, cand_score=0.3, feed_score=0.7)   # even the stall path uses no OCR
    _active_feed(cap)
    cap._dense_candidate_observe(_BGR, 1000.0)
    assert calls["n"] == 0


# ------------------------------------------------------------------ T5: weak cut -> feed_v1 stall-recut (no OCR)
def test_t5_dense_stall_recut_via_feed_v1(monkeypatch):
    gen = _cand_gen()
    cap = _make_cap(gen)
    _patch_ksb(monkeypatch, gen, cap, cand_score=0.3, feed_score=0.7)   # candidate sub-floor, feed authors
    _active_feed(cap)
    evs = [cap._dense_candidate_observe(_BGR, 1000.0 + i) for i in range(3)]   # stall_limit=3
    assert gen.regime == BOOTSTRAP                                       # demoted for recut
    assert evs[-1]["event"] == "candidate_demoted_stall"
    assert evs[0]["event"] == "candidate_stall"


# ------------------------------------------------------------------ T6: FP demote preserved on the dense path
def test_t6_dense_fp_demote_on_background(monkeypatch):
    gen = _cand_gen()
    cap = _make_cap(gen)
    _patch_ksb(monkeypatch, gen, cap, cand_score=0.7, feed_score=0.0)   # candidate clears but on background
    _background(cap)
    ev = cap._dense_candidate_observe(_BGR, 1000.0)
    assert gen.regime == BOOTSTRAP
    assert ev["event"] == "candidate_demoted_fp"


# ------------------------------------------------------------------ T8: no-op outside CANDIDATE
@pytest.mark.parametrize("regime", [BOOTSTRAP, PROMOTED])
def test_t8_dense_noop_outside_candidate(monkeypatch, regime):
    gen = _cand_gen()
    gen._regime = regime
    cap = _make_cap(gen)
    _patch_ksb(monkeypatch, gen, cap, cand_score=0.7, feed_score=0.7)
    _active_feed(cap)
    ev = cap._dense_candidate_observe(_BGR, 1000.0)
    assert ev is None
    assert gen.regime == regime            # unchanged


# ------------------------------------------------------------------ C3: dense fresh-row is private (real cv2)
def test_c3_dense_fresh_row_private_state():
    pytest.importorskip("cv2")
    cap = RetinaGameCapture.__new__(RetinaGameCapture)
    cap._inline_monitor = SimpleNamespace(feed_region_max_yfrac=0.42, killer_max_frac=0.28)
    cap._prev_killer_gray = "WINDOW_SENTINEL"   # the window-path fold's prior — must NOT be touched
    cap._last_killer_fresh_ms = -1e18
    cap._dense_prev_killer_gray = None
    cap._dense_last_killer_fresh_ms = -1e18
    cap._dense_killer_fresh_row(_BGR, 1000.0)
    assert cap._prev_killer_gray == "WINDOW_SENTINEL"   # C3: window path frame-diff untouched
    assert cap._dense_prev_killer_gray is not None       # dense-private prior was set


# ------------------------------------------------------------------ lock is held during generator mutation
def test_generator_mutation_under_lock(monkeypatch):
    gen = _cand_gen()
    cap = _make_cap(gen)
    _patch_ksb(monkeypatch, gen, cap, cand_score=0.7, feed_score=0.0)
    _active_feed(cap)
    orig = gen.observe_candidate
    seen = {"locked": None}

    def spy(**kw):
        seen["locked"] = cap._session_anchor_lock.locked()
        return orig(**kw)

    monkeypatch.setattr(gen, "observe_candidate", spy)
    cap._dense_candidate_observe(_BGR, 1000.0)
    assert seen["locked"] is True          # _session_anchor_lock held across observe_candidate (C1)
