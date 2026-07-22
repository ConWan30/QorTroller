"""CFB snap-extractor pure-core tests. The event detector is a pure function over synthetic
(ts, present, signature) samples — no images, deterministic."""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import numpy as np
from l9_presence.cfb_snap_extractor import Sample, detect_play_events, signature_distance

def sig(v):  # a uniform NxM signature at value v
    return np.full((20, 120), v, dtype=np.uint8)

def test_single_change_one_event():
    s = [Sample(0.0, True, sig(0)), Sample(1.0, True, sig(0)),
         Sample(2.0, True, sig(200)), Sample(3.0, True, sig(200))]
    ev = detect_play_events(s, change_thr=25, debounce_s=3.0, min_present_run=2)
    assert len(ev) == 1 and abs(ev[0].ts_s - 2.0) < 1e-6

def test_no_change_no_event():
    s = [Sample(float(i), True, sig(50)) for i in range(6)]
    assert detect_play_events(s, change_thr=25) == []

def test_debounce_merges_flicker():
    # two big changes within debounce window -> only the first fires
    s = [Sample(0.0, True, sig(0)), Sample(1.0, True, sig(0)),
         Sample(2.0, True, sig(255)), Sample(3.0, True, sig(0))]  # 2.0 and 3.0 both big, <3s apart
    ev = detect_play_events(s, change_thr=25, debounce_s=3.0)
    assert len(ev) == 1

def test_absent_present_transition_does_not_fire():
    # HUD reappearing after a gap must NOT count as a play (cutscene/quarter-break guard)
    s = [Sample(0.0, True, sig(0)), Sample(1.0, True, sig(0)),
         Sample(2.0, False, None), Sample(3.0, False, None),
         Sample(4.0, True, sig(255)), Sample(5.0, True, sig(255))]
    ev = detect_play_events(s, change_thr=25, debounce_s=3.0, min_present_run=2)
    # the 255 at t=4 is the first present frame after the gap (run resets) -> no cross-gap event;
    # at t=5 the sig is unchanged from t=4 -> no event
    assert ev == []

def test_min_present_run_gate():
    # a change on the very first present frame after start doesn't fire until run>=min_present_run
    s = [Sample(0.0, True, sig(255)),               # run=1, no prev -> nothing
         Sample(1.0, True, sig(0))]                  # run=2, change vs prev -> fires
    ev = detect_play_events(s, change_thr=25, debounce_s=3.0, min_present_run=2)
    assert len(ev) == 1

def test_multiple_spaced_changes():
    s = []
    vals = [0, 0, 200, 200, 0, 0, 200, 200]   # changes at idx 2 and 4 and 6
    for i, v in enumerate(vals):
        s.append(Sample(float(i) * 4.0, True, sig(v)))   # 4s apart -> past debounce
    ev = detect_play_events(s, change_thr=25, debounce_s=3.0, min_present_run=2)
    assert len(ev) == 3

def test_signature_distance_basic():
    assert signature_distance(sig(0), sig(0)) == 0.0
    assert abs(signature_distance(sig(0), sig(100)) - 100.0) < 1e-6
    assert signature_distance(None, sig(0)) == 0.0        # None-safe


def test_continuous_present_hud_change_fires():
    """Quarter-break / penalty HUD text change with continuous scoreboard-present
    is NOT suppressed by the absent->present guard — that is the known false-fire
    class (run1 ~191.6s, change_score outlier). C4 honesty pin: present stays True
    across a large signature jump → event fires."""
    s = [Sample(0.0, True, sig(0)), Sample(1.0, True, sig(0)),
         Sample(5.0, True, sig(255)), Sample(6.0, True, sig(255))]
    ev = detect_play_events(s, change_thr=25, debounce_s=3.0, min_present_run=2)
    assert len(ev) == 1 and abs(ev[0].ts_s - 5.0) < 1e-6
    assert ev[0].change_score >= 25.0
