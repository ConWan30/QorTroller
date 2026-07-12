"""TRA-1 T6.4 tests - PoSP retina_perception_root join (standard, ordered).

Verifies: the standard perception root is the ordered conformant Poseidon root (order-sensitive,
honest-null on empty, rail-guarded); the join carries only OBSERVATION fields (no assertion root);
and, wired through build_posp, the observation root and the assertion (kas) root sit as TWO NAMED
PARALLEL roots, never conflated (§2.3). Poseidon mocked via the module hook.
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
from bridge.vapi_bridge.retina_posp_join import (
    PERCEPTION_ROOT_SCHEME, posp_retina_join, standard_perception_root,
)
from l9_presence.posp import build_posp


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


def test_standard_root_is_ordered_hex():
    r = standard_perception_root(_events())
    assert isinstance(r, str) and len(r) == 64


def test_empty_stream_honest_null():
    assert standard_perception_root([]) is None


def test_order_sensitive():
    assert standard_perception_root(_events()) != standard_perception_root(list(reversed(_events())))


def test_asserting_event_refused():
    with pytest.raises(ValueError):
        standard_perception_root([{"type": "x_q.kill", "t": 1.0, "src": "cam", "verdict": "OWN"}])


def test_join_is_observation_only():
    j = posp_retina_join("sess-1", _events(), v3_commitment="dead" * 16)
    assert j["session_id"] == "sess-1"
    assert len(j["retina_perception_root"]) == 64
    assert j["retina_perception_root_scheme"] == PERCEPTION_ROOT_SCHEME
    assert j["retina_state_v3_commitment"] == "dead" * 16
    assert "kas_session_root" not in j          # §2.3: observation side only, never the assertion root


def test_join_honest_null_on_empty():
    assert posp_retina_join("sess-1", [])["retina_perception_root"] is None


def test_build_posp_places_root_as_named_parallel():
    root = standard_perception_root(_events())
    kas = {"session_id": "sess-1", "events_root": "kas" + "0" * 61,
           "commitment": "c", "verdict": "AUTHORED_SESSION"}
    posp = build_posp(session_id="sess-1", kas_record=kas, retina_perception_root=root)
    er = posp.events_roots
    assert er["retina_perception_root"] == root                    # OBSERVATION side
    assert er["kas_session_root"] == "kas" + "0" * 61              # ASSERTION side
    assert er["retina_perception_root"] != er["kas_session_root"]  # named + parallel, never conflated
