"""Tests for l9_presence.killfeed_inline — trigger-gated inline authorship scheduling (pure state machine).

Covers the R2-only channel registry, the near-boundary flag + JSONL sink, the K-refreshed background-score
tracker (exact numpy.percentile), and the InlineAuthorshipMonitor window/single-flight/min-gap decision +
result folding. No cv2 / async / bridge — the monitor is a pure state machine.
"""
from __future__ import annotations

import json
import math

from l9_presence import killfeed_inline as ki


def _feed_until_close(m, start_ms, dur_ms, rx_fn, ry_fn, step=50.0):
    """Feed rx/ry samples from start_ms past the window end; return the record emitted on close."""
    rec, t = None, float(start_ms)
    while t <= start_ms + dur_ms:
        r = m.feed_stick(t, rx_fn(t - start_ms), ry_fn(t - start_ms))
        if r is not None:
            rec = r
        t += step
    return rec


# --- channel registry: R2 only enabled, three documented-not-built ---
def test_registry_only_r2_enabled():
    en = ki.enabled_channels()
    assert [c.name for c in en] == ["r2_onset"]                     # exactly one enabled
    names = {c.name for c in ki.CHANNEL_REGISTRY}
    assert {"l2_ads", "weapon_switch", "r2_release"} <= names       # the three documented entries exist
    for c in ki.CHANNEL_REGISTRY:
        if c.name != "r2_onset":
            assert c.enabled is False                               # documented, NOT built
    assert ki.CHANNEL_REGISTRY[0].window_ms == (50.0, 5000.0)       # widened to the loop cadence + feed persistence


# --- near-boundary flag ---
def test_near_boundary_band():
    assert ki.near_boundary(0.66, 0.66, 0.02) is True
    assert ki.near_boundary(0.65, 0.66, 0.02) is True              # within eps (the 0.65 bg-max / 0.662 kill zone)
    assert ki.near_boundary(0.662, 0.66, 0.02) is True
    assert ki.near_boundary(0.60, 0.66, 0.02) is False
    assert ki.near_boundary(0.80, 0.66, 0.02) is False


def test_append_near_boundary_jsonl(tmp_path):
    p = str(tmp_path / "near.jsonl")
    assert ki.append_near_boundary_jsonl(p, {"score": 0.665, "verdict": "UNVERIFIABLE"}) is True
    assert ki.append_near_boundary_jsonl(p, {"score": 0.655, "verdict": "OWN_KILL_UNBOUND"}) is True
    lines = [json.loads(x) for x in open(p, encoding="utf-8").read().splitlines()]
    assert len(lines) == 2 and lines[0]["score"] == 0.665
    # fail-open: an unserializable record returns False, never raises
    assert ki.append_near_boundary_jsonl(p, {"x": object()}) is False


# --- background-score tracker: exact percentile refreshed every K ---
def test_bg_tracker_refreshes_every_k():
    t = ki.BackgroundScoreTracker(refresh_k=5)
    assert t.percentile() is None                                  # nothing yet
    for s in [0.30, 0.35, 0.40, 0.45]:
        t.add(s)
    assert t.percentile() is None                                  # < K samples -> not refreshed
    t.add(0.50)                                                    # 5th -> refresh
    assert t.percentile() is not None and t.n == 5
    assert abs(t.max() - 0.50) < 1e-9


# --- monitor window / single-flight / min-gap decision ---
def test_monitor_window_gating():
    m = ki.InlineAuthorshipMonitor(window_ms=(50.0, 900.0), min_gap_ms=200.0)
    assert m.should_classify(1000.0) is False                      # no onset yet
    m.mark_onset(1000.0)                                           # window [1050, 1900]
    assert m.should_classify(1049.0) is False                      # before the lag_min gate
    assert m.should_classify(1050.0) is True                       # inside the window
    m.begin(1050.0)
    assert m.should_classify(1100.0) is False                      # single-flight (in-flight)
    m.end()
    assert m.should_classify(1100.0) is False                      # min-gap (1100-1050=50 < 200)
    assert m.should_classify(1300.0) is True                       # min-gap satisfied, still in window
    assert m.should_classify(2000.0) is False                      # past window end


def test_monitor_sustained_fire_extends_window():
    m = ki.InlineAuthorshipMonitor(window_ms=(50.0, 900.0), min_gap_ms=200.0)
    m.mark_onset(1000.0)                                           # end 1900
    m.mark_onset(1500.0)                                           # extends end to 2400
    assert m.should_classify(2300.0) is True                       # still open thanks to the re-fire


# --- monitor result folding: AUTHORED vs neutral field vs near-boundary ---
def test_monitor_record_result_folding():
    m = ki.InlineAuthorshipMonitor(match_floor=0.66, near_epsilon=0.02, refresh_k=1)
    # AUTHORED -> counts as authored, does NOT feed the background tracker (it's signal, not noise)
    assert m.record_result("AUTHORED_PRESENT", 0.80, "feed", "killer", 1200.0) is None
    assert m.status_dict()["inline_authored"] == 1
    assert m.status_dict()["inline_bg_n"] == 0
    # a death (feed-victim) -> neutral field + tracker; 0.67 is near the 0.66 floor -> returns an event
    ev = m.record_result("OWN_KILL_UNBOUND", 0.67, "feed", "victim", 1250.0)
    assert ev is not None and ev["verdict"] == "OWN_KILL_UNBOUND" and ev["region"] == "feed"
    assert m.status_dict()["inline_deaths"] == 1 and m.status_dict()["inline_bg_n"] == 1
    assert m.status_dict()["inline_near_boundary"] == 1
    # a clear background well below the floor -> tracker, no near-boundary event
    assert m.record_result("UNVERIFIABLE", 0.35, None, None, 1300.0) is None
    assert m.status_dict()["inline_bg_n"] == 2
    assert m.status_dict()["inline_classifications"] == 3
    assert m.status_dict()["inline_enabled"] is True

