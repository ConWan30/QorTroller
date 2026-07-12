"""TRA-1 T6.1 tests - kill-feed rows -> conformant retina.event/0.1 events.

Verifies the events are standard-conformant (retina.event/0.1), namespaced (x_qortroller.kill),
ORDER-preserving (F-TRA0-1), status/singleton rows are skipped, and - critically - that they carry
NO authorship/asserting field (the separation law, T4): the encoder emits state, never a verdict.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from bridge.vapi_bridge.killfeed_retina_events import (
    KILL_EVENT_TYPE, kill_event, kill_events_from_rows,
)
from bridge.vapi_bridge.retina_event_std import (
    is_namespaced_type, make_event, separation_law_problems, to_jsonl, validate_event, validate_stream,
)


def test_kill_event_is_conformant_and_namespaced():
    ev = kill_event("Qortrola30", "KING___2008", 1000.0)
    assert validate_event(ev) == []
    assert separation_law_problems(ev) == []
    assert ev["type"] == KILL_EVENT_TYPE == "x_qortroller.kill"
    assert is_namespaced_type(ev["type"])
    assert ev["killer"] == "Qortrola30" and ev["victim"] == "KING___2008"
    assert ev["t"] == 1000.0 and ev["src"] == "retina.killfeed"


def test_event_carries_no_authorship_field():
    ev = kill_event("Qortrola30", "X", 1.0)
    for forbidden in ("authored", "authored_kills", "verdict", "own", "presence_score", "humanity"):
        assert forbidden not in ev


def test_asserting_event_is_refused_by_the_rail():
    # an event that ASSERTS cannot be constructed on the OBSERVATION plane (separation law)
    with pytest.raises(ValueError):
        make_event(KILL_EVENT_TYPE, 1.0, "retina.killfeed", verdict="OWN_KILL")


def test_rows_to_events_kill1_shape_order_preserved():
    rows = [["Qortrola30", "KING___2008"],
            ["rosa sparks", "Tee_Nugget"],
            ["Deslayer295", "OxOLover"]]
    evs = kill_events_from_rows(rows, 1000.0)
    assert len(evs) == 3
    assert [e["killer"] for e in evs] == ["Qortrola30", "rosa sparks", "Deslayer295"]
    assert all(e["type"] == "x_qortroller.kill" for e in evs)
    assert validate_stream(evs) == []


def test_status_lines_and_singletons_skipped():
    rows = [["[B2A]Tee_Nugget", "Connected"], ["Qortrola30", "AWOLNoob"], ["loneToken"], []]
    evs = kill_events_from_rows(rows, 1.0)
    assert len(evs) == 1
    assert evs[0]["killer"] == "Qortrola30" and evs[0]["victim"] == "AWOLNoob"


def test_multi_token_victim_joined():
    evs = kill_events_from_rows([["Qortrola30", "Big", "Boss"]], 1.0)
    assert evs[0]["victim"] == "Big Boss"


def test_stream_serializes_ordered_jsonl():
    evs = kill_events_from_rows([["Qortrola30", "A"], ["rosa sparks", "B"]], 5.0)
    jsonl = to_jsonl(evs)                       # validates conformance + separation law, ordered
    assert jsonl.count("\n") == 1              # 2 events -> 1 newline
    assert jsonl.index("Qortrola30") < jsonl.index("rosa sparks")   # emission order preserved


def test_frame_optional_omitted_when_absent():
    assert kill_event("Q", "V", 1.0, frame=42)["frame"] == 42
    assert "frame" not in kill_event("Q", "V", 1.0)
