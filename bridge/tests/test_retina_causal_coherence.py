"""Tests for the dual-lobe screen parser + input<->outcome causal-coherence fusion (pure)."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from bridge.vapi_bridge.retina_screen_lobe import (  # noqa: E402
    EVT_DOWN_ADVANCED,
    EVT_FIRST_DOWN,
    EVT_PLAYCLOCK_RESET,
    EVT_QUARTER_CHANGED,
    EVT_SCORE_CHANGED,
    HudState,
    ScreenEvent,
    diff_hud,
    is_input_caused,
    parse_hud,
)
from bridge.vapi_bridge.retina_causal_coherence import (  # noqa: E402
    CoherenceConfig,
    CoherenceVerdict,
    TimedEvent,
    assess_coherence,
    from_controller_events,
    from_screen_events,
)


# ---- screen lobe: parse_hud ----

def test_parse_down_distance():
    h = parse_hud("3RD & 7   PLAY CLOCK 21")
    assert h.down == 3 and h.distance == 7 and h.play_clock == 21


def test_parse_goal_to_go_and_quarter():
    h = parse_hud("1st & GOAL   2nd QTR")
    assert h.down == 1 and h.distance == 0 and h.quarter == 2


def test_parse_score_pair_provisional():
    h = parse_hud("HOME 21 - 14 AWAY")
    assert h.score_a == 21 and h.score_b == 14


def test_parse_empty_is_all_none():
    h = parse_hud(None)
    assert h == HudState()
    assert parse_hud("garbage with no hud").down is None


# ---- screen lobe: diff_hud ----

def test_diff_down_advanced():
    evs = diff_hud(HudState(down=1, distance=10), HudState(down=2, distance=6), t=5.0)
    assert [e.type for e in evs] == [EVT_DOWN_ADVANCED]
    assert evs[0].input_caused is True


def test_diff_first_down_on_reset():
    evs = diff_hud(HudState(down=3, distance=2), HudState(down=1, distance=10), t=5.0)
    assert evs[0].type == EVT_FIRST_DOWN and evs[0].input_caused is True


def test_diff_score_change_provisional():
    evs = diff_hud(HudState(down=1, score_a=0, score_b=0),
                   HudState(down=1, score_a=7, score_b=0), t=9.0)
    assert any(e.type == EVT_SCORE_CHANGED and e.input_caused for e in evs)


def test_diff_playclock_reset_is_marker():
    evs = diff_hud(HudState(play_clock=3), HudState(play_clock=40), t=1.0)
    assert evs[0].type == EVT_PLAYCLOCK_RESET and evs[0].input_caused is False


def test_diff_quarter_change_is_marker():
    evs = diff_hud(HudState(quarter=1), HudState(quarter=2), t=1.0)
    assert evs[0].type == EVT_QUARTER_CHANGED and evs[0].input_caused is False


def test_diff_ocr_dropout_never_fabricates():
    # a field going to None (OCR dropout) must not emit a transition
    assert diff_hud(HudState(down=2, distance=5), HudState(down=None), t=1.0) == []


def test_is_input_caused_map():
    assert is_input_caused(EVT_DOWN_ADVANCED) is True
    assert is_input_caused(EVT_QUARTER_CHANGED) is False


# ---- fusion: adapters ----

def test_from_controller_events_filters_to_input_types():
    raw = [
        {"type": "controller.trigger.onset", "t": 1.0},
        {"type": "controller.tremor.anomalous", "t": 1.1},  # not a play action -> dropped
        {"type": "controller.stick.radial_jump", "t": 2.0},
    ]
    te = from_controller_events(raw)
    assert [e.type for e in te] == ["controller.trigger.onset", "controller.stick.radial_jump"]
    assert all(e.kind == "input" for e in te)


def test_from_screen_events_carries_input_caused():
    se = [ScreenEvent(EVT_DOWN_ADVANCED, 5.0, True), ScreenEvent(EVT_QUARTER_CHANGED, 6.0, False)]
    te = from_screen_events(se)
    assert te[0].input_caused is True and te[1].input_caused is False


# ---- fusion: assess_coherence ----

def _inputs(ts):
    return [TimedEvent("input", "controller.trigger.onset", t) for t in ts]


def _outcomes(ts, caused=True):
    return [TimedEvent("outcome", EVT_DOWN_ADVANCED, t, input_caused=caused) for t in ts]


def test_coherent_when_every_outcome_has_preceding_input():
    ev = _inputs([1.0, 11.0, 21.0]) + _outcomes([3.0, 13.0, 23.0])
    rep = assess_coherence(ev)
    assert rep.verdict is CoherenceVerdict.COHERENT
    assert rep.coherence_ratio() == 1.0 and rep.n_matched == 3


def test_orphan_outcome_when_screen_advances_without_input():
    # outcomes at 3/13/23 but NO inputs at all -> relay/replay/spectator
    rep = assess_coherence(_outcomes([3.0, 13.0, 23.0]))
    assert rep.verdict is CoherenceVerdict.ORPHAN_OUTCOME
    assert rep.n_matched == 0 and rep.coherence_ratio() == 0.0


def test_input_outside_window_does_not_match():
    # input 20 s before the outcome, window is 10 s -> orphan
    ev = _inputs([0.0]) + _outcomes([15.0, 30.0, 45.0])
    rep = assess_coherence(ev)
    assert rep.n_matched == 0 and rep.verdict is CoherenceVerdict.ORPHAN_OUTCOME


def test_partial_coherence_below_threshold_is_orphan():
    # 1 of 3 matched (ratio 0.33 < 0.7) -> ORPHAN_OUTCOME
    ev = _inputs([1.0]) + _outcomes([3.0, 50.0, 90.0])
    rep = assess_coherence(ev)
    assert rep.n_matched == 1 and rep.verdict is CoherenceVerdict.ORPHAN_OUTCOME


def test_markers_are_ignored_for_causality():
    # only markers (input_caused=False) -> no required outcomes -> not flagged
    markers = [TimedEvent("outcome", EVT_QUARTER_CHANGED, 5.0, input_caused=False)]
    rep = assess_coherence(markers)
    assert rep.n_outcomes_required == 0 and rep.verdict is CoherenceVerdict.INSUFFICIENT


def test_insufficient_when_too_few_outcomes():
    rep = assess_coherence(_inputs([1.0]) + _outcomes([2.0]))
    assert rep.verdict is CoherenceVerdict.INSUFFICIENT


def test_orphan_input_when_heavy_input_zero_outcomes():
    rep = assess_coherence(_inputs([1, 2, 3, 4, 5, 6]))
    assert rep.verdict is CoherenceVerdict.ORPHAN_INPUT


def test_report_dict_is_uncalibrated():
    rep = assess_coherence(_inputs([1.0, 11.0, 21.0]) + _outcomes([3.0, 13.0, 23.0]))
    d = rep.to_dict()
    assert d["calibration"] == "UNCALIBRATED" and d["verdict"] == "COHERENT"
    assert d["n_orphan_outcomes"] == 0


def test_end_to_end_screen_to_fusion():
    # full pipe: HUD diffs -> screen events -> fusion, with matching inputs
    se = diff_hud(HudState(down=1, distance=10), HudState(down=2, distance=4), t=5.0)
    se += diff_hud(HudState(down=2, distance=4), HudState(down=3, distance=1), t=18.0)
    se += diff_hud(HudState(down=3, distance=1), HudState(down=1, distance=10), t=30.0)
    ctrl = [{"type": "controller.trigger.onset", "t": tt} for tt in (3.0, 16.0, 28.0)]
    ev = from_controller_events(ctrl) + from_screen_events(se)
    rep = assess_coherence(ev)
    assert rep.verdict is CoherenceVerdict.COHERENT and rep.n_outcomes_required == 3
