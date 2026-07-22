"""Football event<->response coupling tests — grok A2A football-coupling r02 BUILD-NOW.

Pure-function rails: fixed-window D1/D3, multi-input onsets, matched adaptive D2 null.
No capture I/O required. No flag flips.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from l9_presence.football_event_coupling import (  # noqa: E402
    MotionSample,
    HidSample,
    detect_field_motion_onsets,
    extract_multi_input_onsets,
    extract_r2_onsets,
    football_fixed_window_coupling,
    football_adaptive_lag_coupling,
    events_from_ts_s,
    suggest_energy_threshold,
)
from l9_presence.optical_copresence import TimedEvent  # noqa: E402


# ---- field-motion onset detector ----

def test_motion_onsets_require_threshold_and_debounce():
    samples = [
        MotionSample(0.0, 1.0),
        MotionSample(0.2, 50.0),   # peak
        MotionSample(0.4, 10.0),
        MotionSample(0.6, 48.0),   # within debounce of first — suppressed
        MotionSample(3.0, 55.0),   # second peak after debounce
        MotionSample(3.2, 20.0),
    ]
    onsets = detect_field_motion_onsets(samples, energy_threshold=40.0, debounce_s=2.0)
    assert len(onsets) == 2
    assert abs(onsets[0].ts_ms - 200.0) < 1.0
    assert abs(onsets[1].ts_ms - 3000.0) < 1.0
    assert all(o.kind == "field_motion_onset" for o in onsets)


def test_motion_onset_local_max_not_shoulder():
    # shoulder at 0.2 (45) then true peak at 0.4 (60) within radius — only peak fires
    samples = [
        MotionSample(0.0, 5.0),
        MotionSample(0.2, 45.0),
        MotionSample(0.4, 60.0),
        MotionSample(0.6, 10.0),
    ]
    onsets = detect_field_motion_onsets(
        samples, energy_threshold=40.0, debounce_s=0.5, local_max_radius_s=0.5,
    )
    assert len(onsets) == 1
    assert abs(onsets[0].ts_ms - 400.0) < 1.0


def test_suggest_threshold_percentile_is_monotonic():
    samples = [MotionSample(float(i), float(i)) for i in range(11)]  # 0..10
    lo = suggest_energy_threshold(samples, percentile=10)
    hi = suggest_energy_threshold(samples, percentile=90)
    assert lo < hi


# ---- multi-input onset extraction ----

def test_r2_onset_rising_edge():
    rows = [
        HidSample(0.0, r2=0),
        HidSample(10.0, r2=0),
        HidSample(20.0, r2=50),   # onset
        HidSample(30.0, r2=80),
        HidSample(100.0, r2=0),
        HidSample(200.0, r2=60),  # second onset (gap > min_gap_ms=50)
    ]
    onsets = extract_r2_onsets(rows)
    assert len(onsets) == 2
    assert onsets[0].ts_ms == 20.0
    assert onsets[1].ts_ms == 200.0


def test_multi_input_includes_stick_burst_and_l2():
    rows = [
        HidSample(0.0, l2=0, r2=0, lx=128, ly=128, rx=128, ry=128),
        HidSample(10.0, l2=40, r2=0),                 # L2 onset
        HidSample(100.0, l2=0, r2=0, lx=128, ly=128),
        HidSample(200.0, lx=128 + 50, ly=128),        # stick burst
        HidSample(300.0, lx=128, ly=128),
        HidSample(400.0, r2=30),                      # R2 onset
    ]
    onsets = extract_multi_input_onsets(rows)
    kinds = {o.kind for o in onsets}
    assert "l2_onset" in kinds
    assert "stick_burst" in kinds
    assert "r2_onset" in kinds
    assert len(onsets) == 3


# ---- fixed-window D1/D3 coupling ----

SNAP_S = 30.0  # football-realistic spacing (matches optical_copresence F10 tests)


def test_fixed_window_locked_stream_is_coupled():
    # ~30s snap spacing; response locked +300ms — default optical window (150, 600) discriminates
    ev = events_from_ts_s([i * SNAP_S for i in range(16)], kind="field")
    resp = [TimedEvent(e.ts_ms + 300.0, "in") for e in ev]
    r = football_fixed_window_coupling(ev, resp)  # default REACTION_WINDOW on optical path via kw
    # football module default is (100, 1500); still fine at 30s spacing
    assert r.event_coupled is True
    assert r.hit_rate > r.null_q


def test_fixed_window_dense_uncoupled_fails():
    # dense responses every 2s, events every 30s — high hit but at-null (density saturation)
    ev = events_from_ts_s([i * SNAP_S for i in range(16)], kind="field")
    resp = [TimedEvent(float(t), "in") for t in range(0, 500_000, 2000)]
    r = football_fixed_window_coupling(ev, resp, reaction_window_ms=(500.0, 8000.0))
    if r.hit_rate <= r.null_q:
        assert r.event_coupled is False


def test_fixed_window_too_few_events_fail_closed():
    ev = events_from_ts_s([1.0, 2.0, 3.0])
    resp = [TimedEvent(1100.0, "in")]
    r = football_fixed_window_coupling(ev, resp, min_events=8)
    assert r.event_coupled is False
    assert "too few" in r.reason


# ---- D2 matched adaptive lag (look-ahead guard) ----

def test_adaptive_matched_null_locked_stream_coupled():
    """Locked +2.2s responses with IRREGULAR event spacing so circular shifts cannot
    recover a single common lag (equal-period grids make adaptive dens=1 for every phase)."""
    # irregular inter-event gaps (s): 18, 25, 22, 30, 19, 27, 21, 24, 28, 20, 26, 23
    gaps = [18, 25, 22, 30, 19, 27, 21, 24, 28, 20, 26, 23, 19, 25, 22]
    ts = [0.0]
    for g in gaps:
        ts.append(ts[-1] + g)
    ev = events_from_ts_s(ts, kind="dd")
    resp = [TimedEvent(e.ts_ms + 2200.0, "in") for e in ev]
    r = football_adaptive_lag_coupling(
        ev, resp,
        lag_search_ms=(0.0, 5000.0),
        bin_width_ms=500.0,
    )
    assert r.event_coupled is True
    assert 1500.0 <= r.peak_lag_ms <= 3000.0
    assert "matched_search=True" in r.reason
    d = r.to_dict()
    assert d["null_procedure"] == "matched_adaptive_lag_search_per_shift"


def test_adaptive_dense_periodic_not_spuriously_coupled():
    """A dense periodic stream will find SOME lag under adaptive search; matched null
    must keep it from false-passing (the look-ahead risk D2 exists to close)."""
    ev = events_from_ts_s([i * 15.0 for i in range(16)], kind="dd")
    # periodic inputs every 1.5s — adaptive search always finds a bin with hits
    resp = [TimedEvent(float(t), "in") for t in range(0, 250_000, 1500)]
    r = football_adaptive_lag_coupling(
        ev, resp,
        lag_search_ms=(0.0, 8000.0),
        bin_width_ms=500.0,
    )
    # real peak density will be high; null peaks under the SAME search should also be high
    assert r.real_peak_density >= 0.5
    # critical: must not claim coupled when null_q is also high
    if r.real_peak_density <= r.null_q or r.real_peak_density < r.null_median + 0.15:
        assert r.event_coupled is False
    # even if somehow excess is large, document — but for this construction expect fail
    assert r.event_coupled is False


def test_adaptive_empty_responses_fail_closed():
    ev = events_from_ts_s([i * 10.0 for i in range(10)])
    r = football_adaptive_lag_coupling(ev, [])
    assert r.event_coupled is False
    assert "no input" in r.reason
