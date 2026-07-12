"""TRA-1 T6.3 tests - per-session VAPI-RETINA-STATE-v3 record builder + self-verify.

Confirms: the record binds the ordered event stream + WorldState into the FROZEN v3 commitment;
it is self-verifying (recompute from embedded data -> matches); tamper is caught; both rails refuse
an illegal state BEFORE a record is built; and the full T6.1 -> T6.2 -> T6.3 chain assembles.
Poseidon is mocked via the module hook (no node needed), mirroring the T3 forge tests.
"""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from bridge.vapi_bridge import retina_events_root as rer
from bridge.vapi_bridge.retina_event_std import make_event
from bridge.vapi_bridge.retina_worldstate_std import controller_entity, make_worldstate
from bridge.vapi_bridge.retina_state_v3_record import (
    SCHEMA, build_retina_state_v3_record, verify_retina_state_v3_record,
)

_DEV = "aa" * 32


def _mock_chain(elems):
    return hashlib.sha256(",".join(str(x) for x in elems).encode()).digest()


@pytest.fixture(autouse=True)
def _mock_poseidon():
    rer.set_poseidon_chain_fn(_mock_chain)
    yield
    rer.set_poseidon_chain_fn(None)


def _events():
    return [make_event("x_qortroller.kill", 1.0, "retina.killfeed", killer="Qortrola30", victim="A"),
            make_event("x_qortroller.kill", 2.0, "retina.killfeed", killer="rosa sparks", victim="B")]


def _ws():
    return make_worldstate("retina.session", 1.0, entities=[controller_entity("edge-01", input_locus=[0.1, 0.2])])


def test_record_shape():
    rec = build_retina_state_v3_record(_DEV, 111, _events(), _ws())
    assert rec["schema"] == SCHEMA
    assert rec["domain"] == "VAPI-RETINA-STATE-v3"
    assert rec["device_id"] == _DEV and rec["ts_ns"] == 111 and rec["n_events"] == 2
    assert len(rec["commitment"]) == 64
    assert len(rec["ordered_events_root"]) == 64 and len(rec["worldstate_digest"]) == 64


def test_record_self_verifies():
    assert verify_retina_state_v3_record(build_retina_state_v3_record(_DEV, 111, _events(), _ws()))


def test_tamper_is_caught():
    rec = build_retina_state_v3_record(_DEV, 111, _events(), _ws())
    rec["events"][0]["victim"] = "SOMEONE_ELSE"            # forge the embedded stream
    assert not verify_retina_state_v3_record(rec)


def test_embed_false_is_not_self_verifiable():
    rec = build_retina_state_v3_record(_DEV, 111, _events(), _ws(), embed=False)
    assert "events" not in rec
    assert not verify_retina_state_v3_record(rec)          # no embedded data to recompute from


def test_order_sensitive_commitment():
    a = build_retina_state_v3_record(_DEV, 111, _events(), _ws())["commitment"]
    b = build_retina_state_v3_record(_DEV, 111, list(reversed(_events())), _ws())["commitment"]
    assert a != b                                          # F-TRA0-1: replayable order committed


def test_asserting_event_refused_before_record():
    bad = [{"type": "x_qortroller.kill", "t": 1.0, "src": "cam", "verdict": "OWN_KILL"}]
    with pytest.raises(ValueError):
        build_retina_state_v3_record(_DEV, 111, bad, _ws())


def test_biometric_worldstate_refused_before_record():
    bad_ws = {"src": "cam", "t": 1.0, "l4_vector": [1, 2, 3]}   # biometric floor breach
    with pytest.raises(ValueError):
        build_retina_state_v3_record(_DEV, 111, _events(), bad_ws)


def test_end_to_end_t61_t62_t63_chain():
    from bridge.vapi_bridge.killfeed_retina_events import kill_events_from_rows
    from bridge.vapi_bridge.retina_session_worldstate import worldstate_from_observation
    rows = [["Qortrola30", "KING___2008"], ["rosa sparks", "Tee_Nugget"]]
    events = kill_events_from_rows(rows, 1000.0)
    ws = worldstate_from_observation(1000.0, controller_id="edge-01", input_locus=[0.1, 0.2])
    rec = build_retina_state_v3_record(_DEV, 1000, events, ws)
    assert rec["n_events"] == 2 and verify_retina_state_v3_record(rec)
