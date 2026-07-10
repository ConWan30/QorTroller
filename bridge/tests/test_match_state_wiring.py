"""LUMEN-2b live match-state wiring (arc B) tests.

Pins: flag default-OFF + off = no tracker/feed/file · live==offline detector parity · kill-anchor ->
MATCH_STARTED emitted · close_session flushes final MATCH_ENDED · tick dedup · push_kill_span ONLY on
AUTHORED_PRESENT · mark_r2_onset -> push_onset · fail-open · NEVER-GATES (emit-only side channel).
"""
from __future__ import annotations

import json
import os

from bridge.vapi_bridge.qortroller_retina_capture import RetinaGameCapture, _match_state_enabled
from l9_presence.match_state_live import LiveMatchStateTracker


class _MockTracker:
    """Records feed calls; inert tick/state so feed-wiring tests don't depend on detect_match_state."""
    def __init__(self):
        self.onsets, self.windows, self.kills = [], [], []
        self.session_id, self.ticks = "sid", 0

    def push_onset(self, t): self.onsets.append(float(t))
    def push_window(self, g, e): self.windows.append((float(g), float(e)))
    def push_kill_span(self, s, e): self.kills.append((float(s), float(e)))
    def tick(self, now): self.ticks += 1; return []
    def state_now(self, now): return "LOBBY"
    def close_session(self, now): return []


def _cap(tracker, tmp_path):
    """A __new__ RetinaGameCapture with just the match-state wiring attrs (bypass the WGC __init__)."""
    cap = RetinaGameCapture.__new__(RetinaGameCapture)
    cap._match_state = tracker
    cap._match_state_log_path = str(tmp_path / "retina_match_state.jsonl")
    cap._match_state_last_event = None
    cap._match_state_last_ts_ms = None
    cap._match_state_n_started = 0
    cap._match_state_n_ended = 0
    cap._match_state_current = "LOBBY" if tracker is not None else "OFF"
    return cap


def _lines(path):
    if not os.path.isfile(path):
        return []
    return [json.loads(ln) for ln in open(path, encoding="utf-8") if ln.strip()]


# ---------------------------------------------------------------- T1 flag OFF / no tracker -> no-op
def test_t1_flag_default_off_and_no_tracker_noop(tmp_path):
    assert _match_state_enabled({}) is False
    assert _match_state_enabled({"RETINA_MATCH_STATE_ENABLED": "1"}) is True
    cap = _cap(None, tmp_path)                                  # flag-off => tracker None
    cap.tick_match_state(1000.0)                                 # clean no-op
    assert _lines(cap._match_state_log_path) == []              # nothing written


# ---------------------------------------------------------------- T2 live == offline detector
def test_t2_live_matches_offline_detector():
    from l9_presence.match_state import IN_MATCH, MATCH_STARTED, detect_match_state
    kills = [(1000.0, 2000.0)]
    t = LiveMatchStateTracker(session_start_ms=0.0, session_id="sid")
    t.push_kill_span(*kills[0])
    live = [x.event for x in t.tick(3000.0)]
    tl = detect_match_state(session_span_ms=(0.0, 3000.0), onsets_ms=[], windows_ms=[],
                            kill_spans_ms=kills, session_id="sid")
    assert MATCH_STARTED in live and any(s.state == IN_MATCH for s in tl.spans)   # same detector, same call


# ---------------------------------------------------------------- T3 kill anchor -> MATCH_STARTED emitted
def test_t3_kill_anchor_emits_match_started(tmp_path):
    t = LiveMatchStateTracker(session_start_ms=0.0, session_id="sid")
    cap = _cap(t, tmp_path)
    t.push_kill_span(1000.0, 2000.0)
    cap.tick_match_state(3000.0)
    ev = _lines(cap._match_state_log_path)
    assert ev and ev[0]["event"] == "MATCH_STARTED"
    assert ev[0]["schema"] == "qortroller-match-state-live-v0" and ev[0]["advisory"] is True
    assert cap._match_state_n_started == 1 and cap._match_state_last_event == "MATCH_STARTED"


# ---------------------------------------------------------------- T4 close_session flushes final ENDED
def test_t4_close_session_flushes_final_ended(tmp_path):
    t = LiveMatchStateTracker(session_start_ms=0.0, session_id="sid")
    cap = _cap(t, tmp_path)
    t.push_kill_span(1000.0, 2000.0)
    cap.tick_match_state(3000.0)                                 # MATCH_STARTED (match still open)
    cap._emit_match_state(t.close_session(4000.0))              # what RGC.stop() calls -- no 240s wait
    evs = [e["event"] for e in _lines(cap._match_state_log_path)]
    assert "MATCH_STARTED" in evs and "MATCH_ENDED" in evs and cap._match_state_n_ended == 1


# ---------------------------------------------------------------- T5 tick dedup (no double STARTED)
def test_t5_tick_dedup_no_double_started(tmp_path):
    t = LiveMatchStateTracker(session_start_ms=0.0, session_id="sid")
    cap = _cap(t, tmp_path)
    t.push_kill_span(1000.0, 2000.0)
    cap.tick_match_state(3000.0); cap.tick_match_state(3500.0); cap.tick_match_state(4000.0)
    started = [e for e in _lines(cap._match_state_log_path) if e["event"] == "MATCH_STARTED"]
    assert len(started) == 1


# ---------------------------------------------------------------- T6 kill span ONLY on AUTHORED_PRESENT
def test_t6_kill_span_only_on_authored(tmp_path):
    m = _MockTracker()
    cap = _cap(m, tmp_path)
    cap._event_bind_stamp, cap._current_record_hash = False, None      # _log_composite context
    cap._composite_log_path = str(tmp_path / "comp.jsonl")
    cap._death_monitor, cap._death_lock = None, None
    cap._log_composite({"verdict": "AUTHORED_PRESENT", "window_gate_ms": 1000.0, "window_end_ms": 4000.0})
    cap._log_composite({"verdict": "SPECTATED", "window_gate_ms": 5000.0, "window_end_ms": 8000.0})
    assert m.windows == [(1000.0, 4000.0), (5000.0, 8000.0)]           # window pushed for BOTH composites
    assert m.kills == [(1000.0, 4000.0)]                              # kill span ONLY for AUTHORED_PRESENT


# ---------------------------------------------------------------- T7 mark_r2_onset -> push_onset
def test_t7_mark_r2_onset_pushes_onset(tmp_path):
    m = _MockTracker()
    cap = _cap(m, tmp_path)
    cap._inline_monitor = None                                  # onset pushes BEFORE the inline early-return
    cap.mark_r2_onset(1234.0)
    assert m.onsets == [1234.0]


# ---------------------------------------------------------------- T8 fail-open: tick raise never propagates
def test_t8_fail_open_tick_never_raises(tmp_path):
    class _Boom(_MockTracker):
        def tick(self, now): raise RuntimeError("boom")
        def state_now(self, now): raise RuntimeError("boom")
    cap = _cap(_Boom(), tmp_path)
    cap.tick_match_state(1000.0)                                 # must swallow, not raise


# ---------------------------------------------------------------- never-gates: emit-only side channel
def test_never_gates_emit_only(tmp_path):
    """Rail 1: the wiring READS the composite, never mutates the authorship keys; tick returns nothing a
    verdict path could consume; match-state writes ONLY its own jsonl (never the composite/KAS path)."""
    m = _MockTracker()
    cap = _cap(m, tmp_path)
    cap._event_bind_stamp, cap._current_record_hash = False, None
    cap._composite_log_path = str(tmp_path / "comp.jsonl")
    cap._death_monitor, cap._death_lock = None, None
    composite = {"verdict": "AUTHORED_PRESENT", "window_gate_ms": 1000.0, "window_end_ms": 4000.0,
                 "composite_score": 0.9, "window_members": 3}
    before = dict(composite)
    cap._log_composite(composite)
    for k in ("verdict", "window_gate_ms", "window_end_ms", "composite_score", "window_members"):
        assert composite[k] == before[k]                        # authorship keys untouched
    assert cap.tick_match_state(3000.0) is None                 # no verdict returned -> nothing can gate on it
