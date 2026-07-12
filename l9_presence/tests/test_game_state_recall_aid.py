"""TRL-1 A2 - game-state buffer OCR-recall aid tests.

recall_priority raises WHERE TO LOOK (SCENE_CHANGE density, KILL_ROW_CLUSTER boost,
non-max-suppressed). The load-bearing rail: authorship_recall_priority returns []
until the zero-false-read + C1 re-gate re-passes (consumption_regated), so the aid
cannot influence the certificate path at the desk.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from l9_presence.game_state_buffer import (
    SceneEvent, SceneEventStream, SCENE_SCHEMA, SCENE_CHANGE, KILL_ROW_CLUSTER,
    recall_priority, authorship_recall_priority, RECALL_CLUSTER_WINDOW_MS,
)


def _change(ts_ms):
    return SceneEvent(ts_ns=int(ts_ms * 1e6), kind=SCENE_CHANGE, span_ms=None,
                      crop_shas=[], confidence=10.0, source="t")


def _cluster(start_ms, end_ms):
    return SceneEvent(ts_ns=int(start_ms * 1e6), kind=KILL_ROW_CLUSTER,
                      span_ms=[start_ms, end_ms], crop_shas=["s"], confidence=0.9, source="t")


def _stream(events):
    return SceneEventStream(schema=SCENE_SCHEMA, session_id="s", session_display="d",
                            events=sorted(events, key=lambda e: e.ts_ns))


# -- the advisory recall aid -----------------------------------------------

def test_dense_burst_ranks_above_isolated():
    burst = [_change(t) for t in (990, 995, 1000, 1005, 1010)]
    st = _stream(burst + [_change(5000)])
    hints = recall_priority(st)
    assert hints[0]["priority"] > hints[-1]["priority"]
    assert hints[0]["ts_ns"] < int(2000 * 1e6)          # the burst window, not the isolated one


def test_nms_yields_distinct_windows():
    st = _stream([_change(t) for t in (990, 995, 1000, 1005, 1010)] + [_change(5000)])
    hints = recall_priority(st)
    assert len(hints) == 2                              # the burst collapses to ONE window
    ts = sorted(h["ts_ns"] for h in hints)
    assert (ts[1] - ts[0]) > RECALL_CLUSTER_WINDOW_MS * 1e6


def test_kill_row_cluster_boosts_priority():
    st = _stream([_change(1000), _change(3000), _cluster(900, 1100)])  # cluster overlaps 1000
    hints = recall_priority(st)
    assert hints[0]["ts_ns"] == int(1000 * 1e6)         # boosted x2, ranks first


def test_empty_stream_no_hints():
    assert recall_priority(_stream([])) == []
    assert recall_priority(_stream([_cluster(0, 100)])) == []   # no SCENE_CHANGE


# -- the consumption gate (the load-bearing certificate-path rail) ----------

def test_authorship_gate_closed_by_default():
    st = _stream([_change(t) for t in (1000, 1005, 1010)])
    assert recall_priority(st)                          # advisory hints EXIST
    assert authorship_recall_priority(st) == []          # but the certificate path sees NONE
    assert authorship_recall_priority(st, consumption_regated=False) == []


def test_authorship_gate_open_only_after_regate():
    st = _stream([_change(t) for t in (1000, 1005, 1010)])
    hints = authorship_recall_priority(st, consumption_regated=True)
    assert hints == recall_priority(st)                  # once re-gated, it matches the aid
    assert len(hints) >= 1


def test_advisory_shape_is_hints_not_a_verdict():
    st = _stream([_change(1000)])
    h = recall_priority(st)
    assert isinstance(h, list) and set(h[0].keys()) == {"ts_ns", "priority"}
