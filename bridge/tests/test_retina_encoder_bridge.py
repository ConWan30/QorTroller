"""TRA-1 T6.5 tests - trio-retina encoder bridge.

Skips cleanly when the optional trio-retina library is absent. Verifies: QorTroller's events pass
the REAL retina.validate() (the reimplementation is faithful); the ext-extension asserting guard;
and that a real trio-retina Event / WorldState routes through our boundary all the way to the FROZEN
v3 commitment. The HEAVY detectors/embedders are never imported here (card-gated).
"""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

retina = pytest.importorskip("retina")   # trio-retina is OPTIONAL; skip if not installed

from bridge.vapi_bridge import retina_events_root as rer
from bridge.vapi_bridge.killfeed_retina_events import kill_event
from bridge.vapi_bridge.retina_encoder_bridge import (
    cross_validate, event_from_trio, trio_retina_available, worldstate_from_trio,
)


def _mock_chain(elems):
    return hashlib.sha256(",".join(str(x) for x in elems).encode()).digest()


@pytest.fixture(autouse=True)
def _mock_poseidon():
    rer.set_poseidon_chain_fn(_mock_chain)
    yield
    rer.set_poseidon_chain_fn(None)


def test_library_available():
    assert trio_retina_available()


def test_our_events_pass_the_real_validator():
    # load-bearing interop: QorTroller's stdlib reimplementation is faithful to the real library
    assert cross_validate(kill_event("Qortrola30", "KING___2008", 1.0)) == []


def test_cross_validate_catches_toplevel_assertion():
    assert cross_validate({"type": "x_q.kill", "t": 1.0, "src": "cam", "verdict": "OWN"})


def test_cross_validate_catches_ext_assertion():
    # the ext guard: an asserting field hidden in the standard's ext extension is still refused
    assert cross_validate({"type": "x_q.kill", "t": 1.0, "src": "cam", "ext": {"verdict": "OWN"}})


def test_event_from_trio_roundtrips():
    ev = retina.Event(type="x_qortroller.kill", t=1.0, src="cam", ext={"killer": "Q", "victim": "V"})
    d = event_from_trio(ev)
    assert d["type"] == "x_qortroller.kill" and d["ext"] == {"killer": "Q", "victim": "V"}
    assert cross_validate(d) == []


def test_event_from_trio_refuses_asserting_ext():
    with pytest.raises(ValueError):
        event_from_trio(retina.Event(type="x_q.kill", t=1.0, src="cam", ext={"verdict": "OWN"}))


def test_worldstate_from_trio_routes_video_and_adds_controller():
    ws = retina.WorldState(src="cam", t=1.0,
                           entities=[retina.Entity(id="p1", type="player", bbox=[10, 20, 30, 40])])
    qt = worldstate_from_trio(ws, controller_id="edge-01", input_locus=[0.1, 0.2])
    types = [e["type"] for e in qt["entities"]]
    assert "player" in types and "controller" in types      # video routed through + controller fused


def test_encoder_output_commits_via_t63():
    from bridge.vapi_bridge.retina_state_v3_record import (
        build_retina_state_v3_record, verify_retina_state_v3_record,
    )
    events = [event_from_trio(retina.Event(type="x_qortroller.kill", t=1.0, src="cam",
                                           ext={"killer": "Qortrola30", "victim": "V"}))]
    ws = worldstate_from_trio(
        retina.WorldState(src="cam", t=1.0, entities=[retina.Entity(id="p1", type="player", bbox=[1, 2, 3, 4])]),
        controller_id="edge-01", input_locus=[0.1, 0.2])
    rec = build_retina_state_v3_record("aa" * 32, 111, events, ws)
    assert verify_retina_state_v3_record(rec)               # real encoder output -> FROZEN v3 commit
