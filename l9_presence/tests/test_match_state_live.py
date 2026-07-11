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


# --- F-ARCB-1: force MATCH_ENDED on session close when detect returns nothing --------------
def test_close_session_forces_ended_when_detect_empty(monkeypatch):
    """F-ARCB-1 live repro: STARTED fired + match stayed open, but detect returns NO IN_MATCH
    span at close (the n_ended=0 seen live 2026-07-10 while match_state=IN_MATCH) -> close_session
    MUST still seal one MATCH_ENDED off the open-match flag. Fails on the pre-fix path-(A)-only."""
    import l9_presence.match_state_live as msl
    tr = _tracker()
    tr.push_kill_span(_S + 60_000, _S + 64_000)
    assert _drain(tr, _S + 70_000) == [MATCH_STARTED]          # open flag set
    monkeypatch.setattr(msl, "detect_match_state",
                        lambda **kw: type("TL", (), {"spans": []})())  # detect returns nothing
    ev = tr.close_session(_S + 80_000)
    assert [e.event for e in ev] == [MATCH_ENDED]
    assert ev[0].ts_ms == _S + 64_000                          # last activity (truth), not now
    assert ev[0].detected_at_ms == _S + 80_000                 # confident at stop
    assert tr._open_match_start_ms is None


def test_close_session_force_is_single_shot(monkeypatch):
    """Double close after a forced seal returns [] (dedup: the session_close key is once-only)."""
    import l9_presence.match_state_live as msl
    tr = _tracker()
    tr.push_kill_span(_S + 60_000, _S + 64_000)
    tr.tick(_S + 70_000)
    monkeypatch.setattr(msl, "detect_match_state",
                        lambda **kw: type("TL", (), {"spans": []})())
    assert [e.event for e in tr.close_session(_S + 80_000)] == [MATCH_ENDED]
    assert tr.close_session(_S + 90_000) == []                 # already sealed


def test_close_session_detect_path_no_double_seal():
    """Healthy path: detect DOES find the open match's span at close -> (A) emits exactly one
    ENDED and (B) does not double-fire (guards test_close_session_flushes_without_hysteresis)."""
    tr = _tracker()
    tr.push_onset(_S + 20_000)
    tr.push_onset(_S + 30_000)
    tr.tick(_S + 40_000)                                       # STARTED, open flag set
    ev = tr.close_session(_S + 60_000)                         # detect finds the span
    assert [e.event for e in ev] == [MATCH_ENDED]             # exactly one, no force double
    assert tr._open_match_start_ms is None


# --- F-ARCB-1b: daemon-side seal (close_session never runs — the daemon force-kills the bridge) ---
def test_seal_open_match_from_jsonl(tmp_path):
    """An unmatched MATCH_STARTED for a session_id -> the daemon seal returns ONE MATCH_ENDED
    scoped to that session (a fully-sealed OTHER session is ignored)."""
    import json
    from l9_presence.match_state_live import seal_open_match_from_jsonl
    p = tmp_path / "ms.jsonl"
    sid = "sess_abc"
    p.write_text(
        json.dumps({"event": "MATCH_STARTED", "ts_ms": 1000, "session_id": sid}) + "\n"
        + json.dumps({"event": "MATCH_STARTED", "ts_ms": 500, "session_id": "other"}) + "\n"
        + json.dumps({"event": "MATCH_ENDED", "ts_ms": 900, "session_id": "other"}) + "\n",
        encoding="utf-8")
    seal = seal_open_match_from_jsonl(str(p), sid, now_ms=2000.0)
    assert seal is not None
    assert seal["event"] == "MATCH_ENDED" and seal["session_id"] == sid
    assert seal["ts_ms"] == 2000.0 and seal["detected_at_ms"] == 2000.0
    assert seal["reason"] == "daemon_session_close" and seal["advisory"] is True


def test_seal_none_when_balanced_absent_or_never_started(tmp_path):
    """Idempotent + honest: absent file / already-balanced / never-started -> None (no double-seal)."""
    import json
    from l9_presence.match_state_live import seal_open_match_from_jsonl
    assert seal_open_match_from_jsonl(str(tmp_path / "nope.jsonl"), "s", 1.0) is None  # absent
    p = tmp_path / "ms.jsonl"
    p.write_text(
        json.dumps({"event": "MATCH_STARTED", "ts_ms": 1, "session_id": "s"}) + "\n"
        + json.dumps({"event": "MATCH_ENDED", "ts_ms": 2, "session_id": "s"}) + "\n",
        encoding="utf-8")
    assert seal_open_match_from_jsonl(str(p), "s", 3.0) is None                        # balanced
    assert seal_open_match_from_jsonl(str(p), "unseen_sid", 3.0) is None               # never started
