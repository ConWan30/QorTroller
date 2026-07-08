"""LUMEN-2b live tracker tests.

Pins: STARTED emits once when confirmed (retroactive ts, later detected_at); ENDED for
the newest match is WITHHELD until forward exit-gap confidence (no flap through the
measured 183s in-match no-fire gap); an older match's end emits as soon as the split is
detected; close_session flushes without hysteresis; dedup across ticks; no signals ->
no events; state_now advisory view.
"""
from __future__ import annotations

from l9_presence.match_state import MATCH_ENDED, MATCH_STARTED
from l9_presence.match_state_live import LiveMatchStateTracker

_S = 1_000_000.0


def _tracker(**kw):
    kw.setdefault("session_start_ms", _S)
    return LiveMatchStateTracker(**kw)


def _drain(tracker, now):
    return [t.event for t in tracker.tick(now)]


def test_started_emits_once_with_retroactive_ts():
    tr = _tracker()
    tr.push_onset(_S + 20_000)
    assert _drain(tr, _S + 25_000) == []                 # one active bucket: unconfirmed
    tr.push_onset(_S + 32_000)                           # second bucket -> confirmed
    ev = tr.tick(_S + 40_000)
    assert [e.event for e in ev] == [MATCH_STARTED]
    assert ev[0].ts_ms <= _S + 20_000 + 10_000           # snapped near first activity
    assert ev[0].detected_at_ms == _S + 40_000           # honesty: detection is late
    assert _drain(tr, _S + 50_000) == []                 # dedup on later ticks


def test_kill_anchor_confirms_immediately():
    tr = _tracker()
    tr.push_kill_span(_S + 60_000, _S + 64_000)
    assert _drain(tr, _S + 70_000) == [MATCH_STARTED]


def test_ended_withheld_until_exit_gap_confidence():
    """KC-2b-1: the 183s no-fire rotation must NOT emit an end."""
    tr = _tracker()
    tr.push_onset(_S + 20_000)
    tr.push_onset(_S + 30_000)
    tr.tick(_S + 40_000)                                  # STARTED
    # 183s of silence (the measured M14 rotation) -> still no ENDED
    assert _drain(tr, _S + 30_000 + 183_000) == []
    tr.push_onset(_S + 220_000)                           # activity resumes, same match
    assert _drain(tr, _S + 230_000) == []
    # now real silence beyond the 240s gap -> ENDED, timestamped at last activity
    ev = tr.tick(_S + 220_000 + 250_000)
    assert [e.event for e in ev] == [MATCH_ENDED]
    assert ev[0].ts_ms <= _S + 220_000 + 10_000           # snapped to last active bucket
    assert ev[0].detected_at_ms == _S + 220_000 + 250_000


def test_two_matches_older_end_emits_on_split():
    tr = _tracker()
    tr.push_onset(_S + 20_000)
    tr.push_onset(_S + 30_000)
    tr.tick(_S + 40_000)                                  # match 1 STARTED
    # match 2 starts 400s later (beyond exit gap) -> the split makes match 1's end confident
    tr.push_onset(_S + 430_000)
    tr.push_onset(_S + 440_000)
    ev = tr.tick(_S + 450_000)
    kinds = [e.event for e in ev]
    assert kinds == [MATCH_STARTED, MATCH_ENDED] or kinds == [MATCH_ENDED, MATCH_STARTED]
    started = next(e for e in ev if e.event == MATCH_STARTED)
    ended = next(e for e in ev if e.event == MATCH_ENDED)
    assert ended.ts_ms < started.ts_ms                    # match 1 ended before match 2 began


def test_close_session_flushes_without_hysteresis():
    tr = _tracker()
    tr.push_onset(_S + 20_000)
    tr.push_onset(_S + 30_000)
    tr.tick(_S + 40_000)
    ev = tr.close_session(_S + 60_000)                    # stop 20s after last activity
    assert [e.event for e in ev] == [MATCH_ENDED]
    assert tr.state_now(_S + 61_000) == "LOBBY"


def test_no_signals_no_events():
    tr = _tracker()
    assert _drain(tr, _S + 300_000) == []
    assert tr.close_session(_S + 400_000) == []


def test_state_now_advisory():
    tr = _tracker()
    assert tr.state_now(_S + 10_000) == "LOBBY"
    tr.push_onset(_S + 20_000)
    tr.push_onset(_S + 30_000)
    tr.tick(_S + 40_000)
    assert tr.state_now(_S + 50_000) == "IN_MATCH"
    assert tr.state_now(_S + 30_000 + 300_000) == "LOBBY"  # activity stale beyond gap
