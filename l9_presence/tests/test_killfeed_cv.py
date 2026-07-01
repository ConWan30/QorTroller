"""Tests for l9_presence.killfeed_cv — color-agnostic, fail-closed kill-feed authorship CV scaffold.

Covers the deterministic, verified parts: the bounded crop-ring (corpus capture), color-agnostic glyph
binarization, the killer-LEFT/victim-RIGHT position gate (VERIFIED from real frames), and the FAIL-CLOSED
discipline (no anchor / below floor -> UNVERIFIABLE, never a guessed AUTHORED). T-KFCV-7 documents the
honest N=2 ground-truth result (the scaffold abstains until a dense corpus calibrates the floor).
"""
from __future__ import annotations

import os

import pytest

from l9_presence import killfeed_cv as kc
from l9_presence.killfeed_authorship import AuthorshipVerdict

cv2 = pytest.importorskip("cv2")
import numpy as np  # noqa: E402

_REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _glyph_pattern(h=24, w=70):
    """A distinctive binary 'handle' pattern (white on black) standing in for the own-handle glyphs."""
    a = np.zeros((h, w), np.uint8)
    a[4:8, 5:65] = 255
    a[10:14, 5:40] = 255
    a[16:20, 5:60] = 255
    a[4:20, 5:9] = 255
    return a


def _feed_with_pattern_at(pattern, feed_w=300, feed_h=34, x=10):
    """A BGR feed crop (black) with the pattern pasted (white) at x — left=killer, right=victim."""
    feed = np.zeros((feed_h, feed_w, 3), np.uint8)
    ph, pw = pattern.shape
    y = (feed_h - ph) // 2
    feed[y:y + ph, x:x + pw, :] = pattern[:, :, None]
    return feed


# T-KFCV-1 — bounded crop ring (the dense-capture corpus saver keeps newest N, prunes the rest)
def test_save_crop_bounded_rings(tmp_path):
    img = np.zeros((10, 10, 3), np.uint8)
    paths = []
    for i in range(8):
        p = kc.save_crop_bounded(str(tmp_path), "panel", img, ts_ns=1000 + i, max_files=5)
        assert p is not None
        paths.append(p)
    remaining = sorted(tmp_path.glob("panel_*.png"))
    assert len(remaining) == 5                       # bounded to max_files
    assert (tmp_path / "panel_1007.png").exists()    # newest kept
    assert not (tmp_path / "panel_1000.png").exists()  # oldest pruned
    # max_files <= 0 disables; None image is a no-op
    assert kc.save_crop_bounded(str(tmp_path), "panel", img, max_files=0) is None
    assert kc.save_crop_bounded(str(tmp_path), "panel", None) is None


# T-KFCV-2 — color-agnostic binarization: the SAME glyph shape in different colours binarizes identically
def test_binarize_is_color_agnostic():
    pat = _glyph_pattern()
    shapes = []
    for color in ((0, 255, 255), (0, 0, 255), (0, 255, 0), (255, 0, 0)):  # yellow/red/green/blue BGR
        bgr = np.zeros((*pat.shape, 3), np.uint8)
        bgr[pat > 0] = color
        bw = kc.binarize_glyphs(bgr)
        assert bw is not None
        shapes.append((bw > 0))
    for s in shapes[1:]:
        assert np.array_equal(shapes[0], s)          # identical shape regardless of colour


# T-KFCV-3 — fail-closed: no anchor -> UNVERIFIABLE (never guesses)
def test_classify_no_anchor_unverifiable():
    feed = _feed_with_pattern_at(_glyph_pattern(), x=10)
    r = kc.classify_feed(feed, None)
    assert r.verdict == AuthorshipVerdict.UNVERIFIABLE
    assert "no anchor" in r.note


# T-KFCV-4 — confident match in the LEFT/killer slot -> AUTHORED_PRESENT (convention verified from frames)
def test_classify_killer_left_authored():
    pat = _glyph_pattern()
    feed = _feed_with_pattern_at(pat, feed_w=300, x=12)       # left third
    r = kc.classify_feed(feed, pat, match_floor=0.5)
    assert r.verdict == AuthorshipVerdict.AUTHORED_PRESENT
    assert r.killer_slot is True and r.x_frac < 0.5
    assert r.score >= 0.5


# T-KFCV-5 — confident match in the RIGHT/victim slot -> neutral (your death), NOT authored
def test_classify_victim_right_not_authored():
    pat = _glyph_pattern()
    feed = _feed_with_pattern_at(pat, feed_w=300, x=230)      # right side
    r = kc.classify_feed(feed, pat, match_floor=0.5)
    assert r.verdict != AuthorshipVerdict.AUTHORED_PRESENT
    assert r.killer_slot is False and r.x_frac >= 0.5


# T-KFCV-6 — below the match floor -> UNVERIFIABLE (abstain, never SPECTATED-by-guess)
def test_classify_below_floor_unverifiable():
    pat = _glyph_pattern()
    noise = np.random.RandomState(0).randint(0, 60, (34, 300, 3), np.uint8)  # no handle present
    r = kc.classify_feed(noise, pat, match_floor=0.95)
    assert r.verdict == AuthorshipVerdict.UNVERIFIABLE
    assert r.score < 0.95


def _panel_with_pattern(pattern, W=614, H=724, x=0, y=0):
    """A BGR left-panel crop (black) with the handle pattern pasted at (x, y)."""
    panel = np.zeros((H, W, 3), np.uint8)
    ph, pw = pattern.shape
    panel[y:y + ph, x:x + pw, :] = pattern[:, :, None]
    return panel


# T-KFCV-P1 — calibrated panel classifier: feed KILLER slot -> AUTHORED (thresholds from the 243-crop corpus)
def test_classify_panel_killer_feed_authored():
    pat = _glyph_pattern()
    panel = _panel_with_pattern(pat, x=int(614 * 0.15), y=int(724 * 0.31))   # feed region, killer-left
    r = kc.classify_panel(panel, pat)
    assert r.verdict == AuthorshipVerdict.AUTHORED_PRESENT
    assert r.evidence.get("region") == "feed" and r.evidence.get("slot") == "killer"


# T-KFCV-P2 — feed VICTIM slot (your death) -> NOT authored (the 0.5-vs-0.28 boundary fix)
def test_classify_panel_victim_feed_not_authored():
    pat = _glyph_pattern()
    panel = _panel_with_pattern(pat, x=int(614 * 0.42), y=int(724 * 0.35))   # feed region, victim-right
    r = kc.classify_panel(panel, pat)
    assert r.verdict != AuthorshipVerdict.AUTHORED_PRESENT
    assert r.evidence.get("slot") == "victim"


# T-KFCV-P3 — ROSTER region (persistent presence) -> not a kill, even in the killer x-band
def test_classify_panel_roster_not_a_kill():
    pat = _glyph_pattern()
    panel = _panel_with_pattern(pat, x=int(614 * 0.20), y=int(724 * 0.96))   # roster region (bottom)
    r = kc.classify_panel(panel, pat)
    assert r.verdict == AuthorshipVerdict.UNVERIFIABLE
    assert r.evidence.get("region") == "roster"


# T-KFCV-P4 — panel classifier is fail-closed without an anchor
def test_classify_panel_no_anchor_fail_closed():
    r = kc.classify_panel(_panel_with_pattern(_glyph_pattern(), x=90, y=220), None)
    assert r.verdict == AuthorshipVerdict.UNVERIFIABLE


# T-KFCV-7 — HONEST N=2 ground-truth result (documents the calibration gap). Skips if the operator's local
# frames / committed anchor asset are absent (CI has no Warzone frames). At the default (uncalibrated) floor
# the scaffold ABSTAINS on both the positive (kf_kill1) and negative (kf_kill2) frames — fail-closed-correct,
# never a false AUTHORED. Resolving this to a true-positive on kf_kill1 needs the dense corpus.
def test_ground_truth_n2_abstains_until_calibrated():
    anchor_path = os.path.join(_REPO, "l9_presence", "assets", "own_handle_anchor.png")
    k1 = os.path.join(_REPO, "kf_kill1.png")
    k2 = os.path.join(_REPO, "kf_kill2.png")
    if not (os.path.exists(anchor_path) and os.path.exists(k1) and os.path.exists(k2)):
        pytest.skip("ground-truth Warzone frames / anchor asset not present (operator-local)")
    anchor = kc.load_anchor(anchor_path)
    assert anchor is not None
    im1, im2 = cv2.imread(k1), cv2.imread(k2)
    W = im1.shape[1]
    # left-panel feed band (best non-roster match band located during the build): abstains at default floor
    for im in (im1, im2):
        feed = im[330:900, 0:int(W * 0.30)]
        r = kc.classify_feed(feed, anchor)           # default floor (0.62) — uncalibrated
        assert r.verdict != AuthorshipVerdict.AUTHORED_PRESENT   # never a false/uncalibrated AUTHORED
