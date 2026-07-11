"""LUMEN-2 match-state detector tests.

Pins: fail-open UNKNOWN (no signals -> never a guessed match); kill-anchor confirms
alone; unconfirmed blips stay LOBBY; in-match no-fire gaps below exit_gap don't split
(the M14 183s rotation case); span snapping (trailing quiet = LOBBY, not match);
transition events; containment evaluation; timeline contiguity; state_at lookup.
"""
from __future__ import annotations

from l9_presence.match_state import (
    IN_MATCH,
    LOBBY,
    MATCH_ENDED,
    MATCH_STARTED,
    UNKNOWN,
    detect_match_state,
    evaluate_containment,
)

_S = 1_000_000.0                     # session start (ms)
_E = _S + 900_000.0                  # 15-min session


def _detect(**kw):
    kw.setdefault("session_span_ms", (_S, _E))
    return detect_match_state(**kw)


def test_no_signals_is_unknown_never_guessed():
    tl = _detect()
    assert [s.state for s in tl.spans] == [UNKNOWN]
    assert tl.n_matches == 0
    assert any("never guessing" in n for n in tl.notes)


def test_kill_anchor_confirms_alone():
    """One kill cluster, zero onsets/windows -> still a confirmed match (definitive)."""
    tl = _detect(kill_spans_ms=[(_S + 100_000, _S + 105_000)])
    assert tl.n_matches == 1
    assert tl.state_at(_S + 102_000) == IN_MATCH


def test_single_onset_blip_stays_lobby():
    """A lone active bucket (< enter_consecutive, no anchor) is NOT a match."""
    tl = _detect(onsets_ms=[_S + 100_000])
    assert tl.n_matches == 0
    assert tl.state_at(_S + 100_000) == LOBBY
    assert any("unconfirmed" in n for n in tl.notes)


def test_m14_shape_one_match_with_183s_gap():
    """The measured M14 reality: onset groups separated by a 183s no-fire rotation must
    remain ONE match (exit_gap 240s), with the trailing quiet reading LOBBY."""
    onsets = [_S + 20_000 + i * 5_000 for i in range(10)]          # 20s..65s burst
    onsets += [_S + 65_000 + 183_000 + i * 5_000 for i in range(10)]  # after 183s gap
    tl = _detect(onsets_ms=onsets)
    assert tl.n_matches == 1
    assert tl.state_at(_S + 150_000) == IN_MATCH        # inside the rotation gap
    assert tl.state_at(_E - 10_000) == LOBBY            # trailing quiet snapped out


def test_gap_beyond_exit_splits_two_matches():
    onsets = [_S + 20_000, _S + 30_000]
    onsets += [_S + 20_000 + 400_000, _S + 30_000 + 400_000]        # 400s later
    tl = _detect(onsets_ms=onsets)
    assert tl.n_matches == 2
    assert [e["event"] for e in tl.events] == [MATCH_STARTED, MATCH_ENDED,
                                               MATCH_STARTED, MATCH_ENDED]


def test_span_snapping_lobby_before_and_after():
    tl = _detect(windows_ms=[(_S + 300_000, _S + 310_000), (_S + 350_000, _S + 360_000)])
    states = [s.state for s in tl.spans]
    assert states == [LOBBY, IN_MATCH, LOBBY]
    m = tl.spans[1]
    assert m.start_ms <= _S + 300_000 and m.end_ms >= _S + 360_000
    assert m.start_ms >= _S + 290_000                    # snapped near first activity


def test_timeline_contiguous():
    tl = _detect(onsets_ms=[_S + 100_000, _S + 110_000, _S + 500_000, _S + 510_000])
    for a, b in zip(tl.spans, tl.spans[1:]):
        assert a.end_ms == b.start_ms
    assert tl.spans[0].start_ms == _S and tl.spans[-1].end_ms == _E


def test_containment_evaluation_pass_and_miss():
    kills = [(_S + 100_000, _S + 104_000)]
    tl = _detect(onsets_ms=[_S + 98_000, _S + 108_000], kill_spans_ms=kills)
    ev = evaluate_containment(tl, kill_spans_ms=kills,
                              windows_ms=[(_S + 99_000, _S + 105_000)])
    assert ev["ok"] and ev["kills_contained"] == "1/1"
    # a kill OUTSIDE any detected match must surface as a miss, never absorbed
    ev2 = evaluate_containment(tl, kill_spans_ms=[(_S + 800_000, _S + 801_000)])
    assert not ev2["ok"] and ev2["missed_kills"]


def test_invalid_session_span():
    tl = detect_match_state(session_span_ms=(_E, _S))
    assert tl.spans == [] and tl.n_matches == 0


def test_advisory_and_schema():
    tl = _detect(onsets_ms=[_S + 10_000, _S + 20_000])
    d = tl.to_dict()
    assert d["schema"] == "qortroller-match-state-v0" and d["advisory"] is True
