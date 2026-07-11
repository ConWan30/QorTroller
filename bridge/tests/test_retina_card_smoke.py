"""TRL-1 R1 - card-arrival UVC smoke tests.

The verdict logic is pure (injected probes), so it tests without cv2 or a camera.
A non-invasive subprocess run (--max-index -1 probes nothing) exercises main()'s
print path + ASCII output without opening the operator's webcam.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import retina_card_smoke as rcs

_SCRIPT = REPO_ROOT / "scripts" / "retina_card_smoke.py"


def _dev(index, opened=True, grabbed=True, w=1920, h=1080, fps=60.0):
    return rcs.DeviceReport(index=index, opened=opened, grabbed=grabbed, width=w, height=h, fps=fps)


# -- verdict logic (pure) --------------------------------------------------

def test_go_when_target_meets_bar():
    st, _ = rcs.verdict([_dev(0)], 0)
    assert st == rcs.GO


def test_no_device_when_nothing_grabs():
    st, _ = rcs.verdict([_dev(0, opened=False, grabbed=False, w=0, h=0, fps=0.0)], 0)
    assert st == rcs.NO_DEVICE


def test_no_go_below_bar():
    st, _ = rcs.verdict([_dev(0, w=640, h=480, fps=30.0)], 0)     # a webcam, below 1280px
    assert st == rcs.NO_GO


def test_points_to_other_index_when_card_elsewhere():
    reports = [_dev(0, w=640, h=480, fps=30.0), _dev(1, w=1920, h=1080, fps=60.0)]
    st, reason = rcs.verdict(reports, 0)
    assert st == rcs.NO_GO and "RETINA_UVC_INDEX=1" in reason


def test_go_below_ideal_still_go():
    st, reason = rcs.verdict([_dev(0, w=1280, h=720, fps=30.0)], 0)
    assert st == rcs.GO and "below ideal" in reason


# -- enumerate (injected probe, no cv2/camera) -----------------------------

def test_enumerate_handles_no_cv2():
    reports, present = rcs.enumerate_devices(3, 1920, 1080, 60, "MJPG", probe=lambda *a: None)
    assert present is False and reports == []


def test_enumerate_with_injected_probe():
    def fake(i, *a):
        hit = (i == 1)
        return {"opened": hit, "grabbed": hit, "width": 1920 if hit else 0,
                "height": 1080 if hit else 0, "fps": 60.0 if hit else 0.0}
    reports, present = rcs.enumerate_devices(2, 1920, 1080, 60, "MJPG", probe=fake)
    assert present and len(reports) == 3
    assert rcs.verdict(reports, 1)[0] == rcs.GO


# -- portability + non-invasive run ----------------------------------------

def test_ascii_only_source():
    src = _SCRIPT.read_text(encoding="utf-8")
    non_ascii = sorted(set(c for c in src if ord(c) > 127))
    assert non_ascii == [], f"non-ASCII in smoke: {[hex(ord(c)) for c in non_ascii]}"


def test_runs_without_opening_a_camera():
    """--max-index -1 probes nothing -> NO-DEVICE -> exit 1, exercising the full
    print path (ASCII, table, verdict) without touching any capture device."""
    r = subprocess.run([sys.executable, str(_SCRIPT), "--max-index", "-1"],
                       capture_output=True, text=True, timeout=60)
    assert r.returncode == 1
    assert "NO-DEVICE" in r.stdout and "TRL-1 R1" in r.stdout
