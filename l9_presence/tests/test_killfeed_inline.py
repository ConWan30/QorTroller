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

# ============================================================================================
# LOOP 2 — DeathWindowMonitor (post-death stick-activity; corpus-only, NO verdict)
# ============================================================================================

def test_death_window_settle_detected():
    m = ki.DeathWindowMonitor(window_ms=3000.0, noise_floor=2.5)
    m.mark_death(1000.0, "crop_a")
    # active (big stick swings) for the first ~1000ms, then idle (stick at 128) for the remainder
    rec = _feed_until_close(m, 1000.0, 3100.0,
                            rx_fn=lambda rel: 128.0 + (30.0 * math.sin(rel / 60.0) if rel < 1000 else 0.0),
                            ry_fn=lambda rel: 128.0)
    assert rec is not None
    assert rec["truncated"] is False
    assert rec["settle_ts_ms"] is not None and 0.0 < rec["settle_ts_ms"] < 3000.0   # settled mid-window
    assert rec["rx_var"] is not None and rec["rx_range"] is not None                 # raw fields present
    assert "verdict" not in rec                                                       # NO verdict field


def test_death_window_never_settles_is_null():
    m = ki.DeathWindowMonitor(window_ms=2000.0, noise_floor=2.5)
    m.mark_death(0.0, "crop_b")
    rec = _feed_until_close(m, 0.0, 2100.0,
                            rx_fn=lambda rel: 128.0 + 30.0 * math.sin(rel / 50.0),   # active throughout
                            ry_fn=lambda rel: 128.0 + 30.0 * math.cos(rel / 50.0))
    assert rec is not None
    assert rec["settle_ts_ms"] is None            # NEVER settled -> null (distinct from settling at end)


def test_death_window_restart_truncates_first():
    m = ki.DeathWindowMonitor(window_ms=4000.0, noise_floor=2.5)
    assert m.mark_death(1000.0, "crop1") is None      # first death -> nothing to close
    m.feed_stick(1100.0, 140.0, 120.0)
    m.feed_stick(1200.0, 130.0, 128.0)
    trunc = m.mark_death(2000.0, "crop2")             # second death INSIDE the window -> truncate the first
    assert trunc is not None
    assert trunc["truncated"] is True
    assert trunc["window_ms"] < 4000.0                # truncated shorter than the nominal window
    assert trunc["source_crop_ref"] == "crop1"
    assert m.status_dict()["death_events"] == 1       # exactly one window closed
    assert m.status_dict()["death_window_active"] is True   # a fresh window is open (not dropped)


def test_death_window_records_raw_anchor_and_lag_is_derivable():
    """The window opens at CONFIRMATION (win_start=ts_ms); death_anchor_ms carries the earlier death-row
    appearance. Both raw in the record -> confirmation lag = ts_ms - death_anchor_ms recoverable offline."""
    m = ki.DeathWindowMonitor(window_ms=1000.0, noise_floor=2.5)
    m.mark_death(5000.0, "c", death_anchor_ms=4200.0)          # confirmed at 5000, row first seen at 4200
    rec = _feed_until_close(m, 5000.0, 6100.0, rx_fn=lambda rel: 128.0, ry_fn=lambda rel: 128.0)
    assert rec["death_anchor_ms"] == 4200.0
    assert rec["ts_ms"] == 5000.0
    assert rec["ts_ms"] - rec["death_anchor_ms"] == 800.0      # the confirmation lag, offline-derivable


def test_death_window_anchor_survives_restart_per_window():
    """On restart the truncated prior record must keep ITS OWN anchor (set before the new one overwrites)."""
    m = ki.DeathWindowMonitor(window_ms=4000.0, noise_floor=2.5)
    m.mark_death(1000.0, "crop1", death_anchor_ms=700.0)
    trunc = m.mark_death(2000.0, "crop2", death_anchor_ms=1800.0)   # restart -> closes window 1
    assert trunc["death_anchor_ms"] == 700.0                   # window 1 kept its own anchor
    assert m._death_anchor_ms == 1800.0                        # window 2 holds the new anchor


def test_death_window_anchor_defaults_none():
    m = ki.DeathWindowMonitor(window_ms=1000.0, noise_floor=2.5)
    m.mark_death(0.0, "c")                                     # legacy 2-arg call -> anchor unknown
    rec = _feed_until_close(m, 0.0, 1100.0, rx_fn=lambda rel: 128.0, ry_fn=lambda rel: 128.0)
    assert rec["death_anchor_ms"] is None


def test_death_window_no_verdict_anywhere():
    m = ki.DeathWindowMonitor(window_ms=1000.0, noise_floor=2.5)
    m.mark_death(0.0, "c")
    rec = _feed_until_close(m, 0.0, 1100.0, rx_fn=lambda rel: 128.0, ry_fn=lambda rel: 128.0)
    # corpus record carries only raw measurements — never a PRESENT/ABSENT/AUTHORED verdict
    for banned in ("verdict", "present", "absent", "authored"):
        assert not any(banned in k.lower() for k in rec)


# ============================================================================================
# PHASE 1 — max-over-window composite (floor-transfer diagnostic fix, D-FLOOR-1=branch-b)
# ============================================================================================

def _mk_composite_monitor(**kw):
    kw.setdefault("window_ms", (50.0, 900.0))
    kw.setdefault("min_gap_ms", 200.0)
    kw.setdefault("match_floor", 0.66)
    kw.setdefault("killer_max_frac", 0.28)
    kw.setdefault("feed_region_max_yfrac", 0.42)
    return ki.InlineAuthorshipMonitor(**kw)


def test_composite_below_floor_single_sample_but_window_max_authors():
    # THE archive-confirmed bug this fixes: no single sample clears the floor, but the window's MAX does.
    m = _mk_composite_monitor()
    m.mark_onset(1000.0)                                            # window [1050, 1900]
    m.observe_window(0.50, 0.18, 0.35, 1100.0)                      # killer-position, below floor
    m.observe_window(0.702, 0.18, 0.35, 1300.0)                     # killer-position, CLEARS floor
    m.observe_window(0.45, 0.18, 0.35, 1500.0)                      # killer-position, below floor again
    rec = m.mark_onset(3000.0)                                      # a NEW window (past the old end) resolves the old one
    assert rec is not None
    assert rec["verdict"] == "AUTHORED_PRESENT"
    assert abs(rec["composite_score"] - 0.702) < 1e-6               # the MAX, not the last/first sample
    assert rec["window_members"] == 3
    assert m.status_dict()["inline_composite_authored"] == 1


def test_anchor_provenance_stamped_on_records():
    # Rider 3 (2026-07-02 anchor swap): score semantics are anchor-specific, so every composite AND
    # near-boundary record carries which anchor produced it -> a corpus spanning the roster->feed swap
    # stays interpretable (same lesson as ts_source). Default roster_v1; the live caller passes feed_v1.
    assert ki.InlineAuthorshipMonitor().anchor_id == "roster_v1"
    m = _mk_composite_monitor(anchor_id="feed_v1", refresh_k=1, near_epsilon=0.02)
    # composite record carries the anchor id
    m.mark_onset(1000.0)
    m.observe_window(0.702, 0.18, 0.35, 1300.0)
    rec = m.mark_onset(3000.0)
    assert rec is not None and rec["anchor"] == "feed_v1"
    # near-boundary record carries it too
    ev = m.record_result("UNVERIFIABLE", 0.665, "feed", "killer", 3100.0)
    assert ev is not None and ev["anchor"] == "feed_v1"


def test_composite_authored_carries_fold_time_anchor_tag():
    # Carry-forward 1 (session-anchor wiring): the AUTHORED record's anchor = the tag of the WINNING killer
    # fold, captured at fold time — NOT the last fold's tag and NOT a lagging session variable. A later,
    # LOWER-score fold with a different regime tag must NOT override the max's tag (unfakeable by ordering).
    m = _mk_composite_monitor(anchor_id="feed_v1")
    m.mark_onset(1000.0)
    m.observe_window(0.70, 0.18, 0.35, 1100.0, anchor_tag="session_s2@0.66")          # WINS (highest)
    m.observe_window(0.68, 0.18, 0.35, 1200.0, anchor_tag="bootstrap_feed_v1@0.55")   # later + lower
    rec = m.mark_onset(3000.0)
    assert rec["verdict"] == "AUTHORED_PRESENT" and abs(rec["composite_score"] - 0.70) < 1e-6
    assert rec["anchor"] == "session_s2@0.66"          # the winning fold's tag, not the last fold's
    # OWN_DEATH never carries a session tag (victim path is static feed_v1 by scope)
    m2 = _mk_composite_monitor(anchor_id="feed_v1")
    m2.mark_onset(1000.0)
    m2.observe_window(0.73, 0.40, 0.35, 1100.0)        # victim position, no tag
    rec2 = m2.mark_onset(3000.0)
    assert rec2["verdict"] == "OWN_DEATH" and rec2["anchor"] == "feed_v1"


def test_composite_works_on_below_floor_evidence_without_region_slot():
    # classify_panel omits region/slot from evidence when score<floor -- observe_window must still work
    # from x_frac/y_frac alone (the one thing always present), which is exactly what it's designed for.
    m = _mk_composite_monitor()
    m.mark_onset(0.0)
    m.observe_window(0.30, 0.18, 0.35, 100.0)     # would-be killer, below floor -- no region/slot needed
    rec = m.mark_onset(5000.0)
    assert rec is not None and rec["verdict"] == "UNVERIFIABLE"      # never cleared the floor -> honest abstain


def test_composite_victim_resolves_own_death_not_authored():
    m = _mk_composite_monitor()
    m.mark_onset(0.0)
    m.observe_window(0.80, 0.40, 0.35, 100.0)      # victim position (xf>=killer_max_frac), clears floor
    rec = m.mark_onset(5000.0)
    assert rec is not None
    assert rec["verdict"] == "OWN_DEATH"                             # own handle at victim = your death, NEVER authored
    assert m.status_dict()["inline_composite_authored"] == 0


def test_composite_records_victim_first_seen_anchor():
    """The death-row appearance anchor is the FIRST victim obs, not the peak — so a confirmation-gated
    settle_ts_ms is normalizable to the death instant offline (lag = resolve ts - victim_first_ms)."""
    m = _mk_composite_monitor()
    m.mark_onset(0.0)
    m.observe_window(0.55, 0.40, 0.35, 120.0)      # first victim obs (below floor) -> anchors appearance
    m.observe_window(0.82, 0.40, 0.35, 900.0)      # later, stronger victim obs -> raises the max, NOT the anchor
    rec = m.mark_onset(5000.0)
    assert rec["verdict"] == "OWN_DEATH"                             # window-max 0.82 cleared floor
    assert rec["victim_first_ms"] == 120.0                          # anchor = FIRST appearance, not the 900ms peak
    assert rec["ts_ms"] > rec["victim_first_ms"]                    # confirmation lag is positive + recoverable


def test_composite_no_victim_anchor_is_none():
    m = _mk_composite_monitor()
    m.mark_onset(0.0)
    m.observe_window(0.90, 0.18, 0.35, 100.0)      # killer only, no victim obs
    rec = m.mark_onset(5000.0)
    assert rec["victim_first_ms"] is None                           # no death row seen -> anchor is None


def test_composite_below_floor_victim_never_resolves_own_death():
    """Loop-2 detection rail: a victim-position sample that never clears the floor must NOT resolve OWN_DEATH
    (would fire a phantom mark_death). Only the window-MAX clearing the floor counts."""
    m = _mk_composite_monitor()
    m.mark_onset(0.0)
    m.observe_window(0.50, 0.40, 0.35, 100.0)      # victim position but below floor
    m.observe_window(0.61, 0.40, 0.35, 200.0)      # still below floor; window-max victim = 0.61 < 0.66
    rec = m.mark_onset(5000.0)
    assert rec["verdict"] == "UNVERIFIABLE"                          # no OWN_DEATH -> no death trigger


def test_composite_killer_wins_over_victim_when_both_present():
    m = _mk_composite_monitor()
    m.mark_onset(0.0)
    m.observe_window(0.90, 0.40, 0.35, 100.0)      # victim, high
    m.observe_window(0.70, 0.18, 0.35, 200.0)      # killer, also clears floor
    rec = m.mark_onset(5000.0)
    assert rec["verdict"] == "AUTHORED_PRESENT"                      # killer-clearing wins the resolution


def test_composite_roster_position_never_authors():
    m = _mk_composite_monitor()
    m.mark_onset(0.0)
    m.observe_window(0.95, 0.18, 0.80, 100.0)      # roster region (yf>=0.42) even though xf looks killer-ish
    rec = m.mark_onset(5000.0)
    assert rec["verdict"] == "UNVERIFIABLE"                          # roster is persistent presence, not a kill


def test_composite_empty_window_resolves_to_none():
    m = _mk_composite_monitor()
    m.mark_onset(0.0)                              # window opens, but nothing ever observed in it
    rec = m.mark_onset(5000.0)
    assert rec is None                                                # nothing to resolve -> no spurious record


def test_flush_stale_window_resolves_without_a_new_onset():
    # combat stops firing entirely -- no NEW onset ever comes; flush_if_expired must still resolve it.
    m = _mk_composite_monitor()
    m.mark_onset(1000.0)                            # window [1050, 1900]
    m.observe_window(0.843, 0.18, 0.35, 1200.0)      # clears floor
    assert m.flush_if_expired(1500.0) is None        # still inside the window -> not expired yet
    rec = m.flush_if_expired(2000.0)                 # past window end, no further onset -> resolves now
    assert rec is not None and rec["verdict"] == "AUTHORED_PRESENT"
    assert m.flush_if_expired(2500.0) is None         # already resolved -> no double-emit


def test_sustained_fire_composites_across_the_whole_extended_window():
    # re-onset within an OPEN window extends it and must NOT reset the running max (a real combat burst
    # composites across the whole engagement, not just the segment since the last re-press).
    m = _mk_composite_monitor()
    m.mark_onset(0.0)                                # window [50, 900]
    m.observe_window(0.70, 0.18, 0.35, 100.0)         # clears floor early in the burst
    assert m.mark_onset(500.0) is None                # re-onset INSIDE the window -> extends, does NOT resolve
    m.observe_window(0.30, 0.18, 0.35, 600.0)         # a later, lower sample in the SAME extended window
    rec = m.mark_onset(3000.0)                        # now past the extended end -> resolves
    assert rec is not None and rec["verdict"] == "AUTHORED_PRESENT"
    assert abs(rec["composite_score"] - 0.70) < 1e-6  # the max survives the extension, isn't reset by re-onset


def test_composite_never_touches_frozen_thresholds():
    # the composite mirror fields must equal killfeed_cv's frozen constants when constructed by the real path
    from l9_presence import killfeed_cv as kc
    m = ki.InlineAuthorshipMonitor(match_floor=kc.DEFAULT_MATCH_FLOOR,
                                   killer_max_frac=kc.KILLER_MAX_FRAC_PANEL,
                                   feed_region_max_yfrac=kc.FEED_REGION_MAX_YFRAC)
    assert m.match_floor == 0.66 and m.killer_max_frac == 0.28 and m.feed_region_max_yfrac == 0.42
