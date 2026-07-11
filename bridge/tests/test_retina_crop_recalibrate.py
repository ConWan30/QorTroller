"""TRL-1 R2 - retina OCR crop-recalibration tests.

Pins the pure ROI math against the daemon's _roi_px, proves the crops are
resolution-independent (the honest R2 finding), covers validate/remap, and runs
--report non-invasively. The cv2 overlay is tested only if opencv is present.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import pytest

import retina_crop_recalibrate as rc

_SCRIPT = REPO_ROOT / "scripts" / "retina_crop_recalibrate.py"
_KILLFEED = (0.62, 0.10, 0.36, 0.22)   # daemon default (top-right Warzone feed)
_PANEL = (0.0, 0.28, 0.32, 0.67)       # daemon default (left HUD panel)


# -- parse + pixel math (pinned to the daemon) -----------------------------

def test_parse_roi_valid_and_invalid():
    assert rc.parse_roi("0.62,0.10,0.36,0.22") == _KILLFEED
    assert rc.parse_roi("0.1,0.2,0.3") is None          # wrong arity
    assert rc.parse_roi("1.2,0,0.3,0.3") is None         # out of 0..1
    assert rc.parse_roi("junk") is None


def test_roi_px_matches_daemon_math():
    # _roi_px: x0=int(w*fx), x1=int(w*min(1,fx+fw)), same for y
    assert rc.roi_px(1920, 1080, _KILLFEED) == (1190, 108, 1881, 345)
    assert rc.roi_px(1920, 1080, _PANEL) == (0, 302, 614, 1026)


def test_crops_are_resolution_independent():
    """The honest R2 finding: a fractional ROI maps to the SAME relative region at
    any resolution (WGC window vs card 1080p) -> no resolution-driven shift."""
    for w, h in [(1920, 1080), (1280, 720), (1600, 900)]:
        x0, y0, _, _ = rc.roi_px(w, h, _KILLFEED)
        assert abs(x0 / w - _KILLFEED[0]) < 1e-3
        assert abs(y0 / h - _KILLFEED[1]) < 1e-3


# -- validation ------------------------------------------------------------

def test_validate_clean_and_overflow():
    assert rc.validate_roi(_KILLFEED) == []
    assert rc.validate_roi(_PANEL) == []
    assert rc.validate_roi((0.9, 0.0, 0.5, 0.2))         # 0.9+0.5 > 1 -> issue
    assert rc.validate_roi((0.1, 0.1, 0.0, 0.2))         # degenerate width
    assert rc.validate_roi(None)                         # unparseable


# -- content-framing remap -------------------------------------------------

def test_remap_identity_when_full_frame():
    out = rc.remap_content_box(_KILLFEED, (0, 0, 1, 1), (0, 0, 1, 1))
    assert all(abs(a - b) < 1e-9 for a, b in zip(out, _KILLFEED))


def test_remap_corrects_a_letterbox():
    # source content occupied the middle 88% vertically (top/bottom letterbox);
    # dest card is full-frame -> a crop at fy=0.10 should move.
    out = rc.remap_content_box(_KILLFEED, (0.0, 0.06, 1.0, 0.88), (0, 0, 1, 1))
    assert out[0] == pytest.approx(_KILLFEED[0])          # x unchanged (no h-letterbox)
    assert out[1] != pytest.approx(_KILLFEED[1])          # y remapped
    assert 0.0 <= out[1] <= 1.0


# -- overlay rects (pure) --------------------------------------------------

def test_overlay_rects_pure():
    rects = rc.overlay_rects(1920, 1080, [("killfeed", _KILLFEED), ("panel", _PANEL)])
    labels = {r[0] for r in rects}
    assert labels == {"killfeed", "panel"}
    assert rects[0][1] == (1190, 108, 1881, 345)


# -- portability + non-invasive run ----------------------------------------

def test_ascii_only_source():
    src = _SCRIPT.read_text(encoding="utf-8")
    non_ascii = sorted(set(c for c in src if ord(c) > 127))
    assert non_ascii == [], f"non-ASCII: {[hex(ord(c)) for c in non_ascii]}"


def test_report_runs_and_shows_rects():
    r = subprocess.run([sys.executable, str(_SCRIPT), "--report"],
                       capture_output=True, text=True, timeout=60)
    assert r.returncode == 0
    assert "x[1190..1881]" in r.stdout and "CONTENT-FRAMING" in r.stdout


# -- overlay draw (only if opencv is present) -------------------------------

def test_overlay_draw_if_cv2(tmp_path):
    cv2 = pytest.importorskip("cv2")
    np = pytest.importorskip("numpy")
    frame = tmp_path / "frame.png"
    cv2.imwrite(str(frame), np.zeros((1080, 1920, 3), dtype=np.uint8))
    out = tmp_path / "annotated.png"
    w, h = rc.draw_overlay(str(frame), str(out), [("killfeed", _KILLFEED), ("panel", _PANEL)])
    assert (w, h) == (1920, 1080)
    assert out.exists() and cv2.imread(str(out)) is not None
