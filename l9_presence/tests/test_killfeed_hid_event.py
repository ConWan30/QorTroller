"""Tests for l9_presence.killfeed_hid_event — the HID-lobe schema + R2-onset detector (dual-lobe fusion).

Pins: the r2_onset event shape (device-clock t_ms + raw device_ts/wall_ms for anchor audit + input_caused
False); rising-edge detection on the device clock (one onset per crossing, sustained-hold no re-fire, no
spurious onset on a mid-hold start); session normalizer (span filter + malformed skip); and the coherence
round-trip (HID input matched to a screen outcome -> COHERENT with a measurable cross-lobe latency). Pure."""
from __future__ import annotations

from l9_presence import killfeed_hid_event as he


def test_onset_event_shape_carries_device_clock_and_anchor_audit():
    ev = he.hid_onset_event(t_ms=1010.0, device_ts=30000, wall_ms=1010.5, l2=200)
    assert ev["type"] == he.HID_EVENT_R2_ONSET
    assert ev["t_ms"] == 1010.0                 # device-clock wall-corrected ms = the alignment clock
    assert ev["device_ts"] == 30000 and ev["wall_ms"] == 1010.5 and ev["l2"] == 200   # anchor-audit fields
    assert ev["input_caused"] is False          # an r2_onset is the INPUT cause, not an outcome


def _feed(det, seq):
    # seq of (wall_ms, ts_u32, l2); ts at 3000 ticks/ms keeps wall_corrected == wall_ms (anchor identity)
    for wall, ts, l2 in seq:
        det.push(wall, ts, l2)


def test_rising_edge_fires_once_per_crossing_device_clock():
    det = he.HidOnsetDetector(threshold=40)
    _feed(det, [(1000.0, 0, 0),            # anchor, low
                (1010.0, 30000, 200),      # 0 -> 200 : RISING EDGE #1 @1010
                (1020.0, 60000, 200),      # sustained high : NO re-fire
                (1030.0, 90000, 0),        # release (falling ignored)
                (1040.0, 120000, 200)])    # 0 -> 200 : RISING EDGE #2 @1040
    evs = det.drain_events()
    assert [e["t_ms"] for e in evs] == [1010.0, 1040.0]     # device-precise, exactly two onsets
    assert evs[0]["device_ts"] == 30000 and evs[0]["l2"] == 200
    assert det.drain_events() == []                          # drain clears
    assert det.stats()["hid_onsets"] == 2


def test_no_spurious_onset_on_a_mid_hold_start():
    # a session that starts while L2 is ALREADY down must NOT fabricate an onset (we only catch edges we saw)
    det = he.HidOnsetDetector(threshold=40)
    _feed(det, [(1000.0, 0, 200),          # first sample already high -> prev unknown -> no edge
                (1010.0, 30000, 200)])     # still high -> no edge
    assert det.drain_events() == []


def test_push_is_fail_open_never_raises():
    det = he.HidOnsetDetector()
    det.push(None, None, None)             # malformed report -> swallowed, no onset, no raise
    det.push("x", "y", "z")
    assert det.drain_events() == []


def test_session_hid_events_span_filter_and_malformed_skip():
    raw = [{"type": "r2_onset", "t_ms": 900.0, "device_ts": 1, "wall_ms": 900.0, "l2": 200},   # before span
           {"type": "r2_onset", "t_ms": 1500.0, "device_ts": 2, "wall_ms": 1500.0, "l2": 200},  # in span
           {"type": "r2_onset", "t_ms": None},                                                   # malformed
           {"nonsense": True},                                                                   # malformed
           {"type": "r2_onset", "t_ms": 9000.0, "device_ts": 3, "wall_ms": 9000.0, "l2": 200}]  # after span
    evs = he.session_hid_events(raw, span_ms=(1000.0, 5000.0))
    assert len(evs) == 1 and evs[0]["t_ms"] == 1500.0 and evs[0]["device_ts"] == 2
    # no span -> all well-formed rows pass (2 valid of the 5)
    assert len(he.session_hid_events(raw)) == 3


def test_to_timed_event_is_an_input_for_the_coherence_engine():
    ev = he.hid_onset_event(t_ms=1500.0, device_ts=2, wall_ms=1500.0, l2=200)
    te = he.to_timed_event(ev)
    assert te == {"kind": "input", "type": "controller.trigger.onset", "t": 1.5, "input_caused": False}
    assert he.to_timed_event({"t_ms": None}) is None
    # the type is exactly what assess_coherence counts as a play action
    from vapi_bridge.retina_causal_coherence import INPUT_EVENT_TYPES
    assert te["type"] in INPUT_EVENT_TYPES


def test_hid_input_explains_a_screen_outcome_measurable_latency():
    # the payoff: an r2_onset (input) precedes a killfeed AUTHORED (outcome) -> COHERENT + nearest_input_dt is
    # the cross-lobe latency. Screen outcome via the screen lobe's to_timed_event, HID via ours.
    import pytest
    from vapi_bridge.retina_causal_coherence import (CoherenceConfig, TimedEvent, assess_coherence)
    from l9_presence.killfeed_screen_event import authored_screen_event, to_timed_event as screen_te
    hid = he.to_timed_event(he.hid_onset_event(t_ms=1000.0, device_ts=1, wall_ms=1000.0, l2=200))
    scr = screen_te(authored_screen_event({"verdict": "AUTHORED_PRESENT", "killer_first_ms": 1120.0,
                                            "ts_ms": 6000.0, "composite_score": 0.8}))
    rep = assess_coherence([TimedEvent(**hid), TimedEvent(**scr)])   # the outcome IS input-caused (required)
    assert rep.n_inputs == 1 and rep.n_outcomes_required == 1
    assert rep.matches[0].matched and rep.matches[0].nearest_input_dt == pytest.approx(0.12)  # 1120-1000 ms
    # default min_outcomes=3 -> INSUFFICIENT on one kill; lower the bar and the single match reads COHERENT
    rep2 = assess_coherence([TimedEvent(**hid), TimedEvent(**scr)], CoherenceConfig(min_outcomes=1))
    assert rep2.verdict.value == "COHERENT"
