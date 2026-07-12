"""TRA-1 T1 - retina.event/0.1 emitter + validator tests.

Confirms QorTroller emits + validates the real MachineFi Trio Retina standard: the closed
0.1 vocabulary matches the spec, gaming events ride the namespaced-custom-type extension
(F-TRA0-2), and the commitment preserves the replayable ORDER (F-TRA0-1) - a reordered
stream yields a DIFFERENT ordered root, where the legacy sorted root collides.
"""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from bridge.vapi_bridge.retina_event_std import (
    KNOWN_TYPES, RETINA_EVENT_VERSION,
    make_event, validate_event, is_valid, validate_stream, to_jsonl,
    is_namespaced_type, ordered_events_root,
)
from bridge.vapi_bridge.retina_events_root import compute_events_root_poseidon


def _mock_chain(elems):
    """Deterministic, ORDER-SENSITIVE stand-in for the node Poseidon chain."""
    return hashlib.sha256(",".join(str(x) for x in elems).encode()).digest()


# -- the standard's vocabulary ----------------------------------------------

def test_known_types_match_spec():
    assert KNOWN_TYPES == {"zone.enter", "zone.exit", "zone.dwell", "line.cross", "count.threshold"}
    assert RETINA_EVENT_VERSION == "retina.event/0.1"


def test_primitive_event_is_conformant():
    e = make_event("zone.dwell", 1718254799.8, "cam_01", id=42, label="person", zone="dock", dur=31.0, conf=0.91)
    assert is_valid(e)
    assert validate_event(e) == []


# -- F-TRA0-2: gaming events ride the namespaced-custom-type extension -------

def test_namespaced_gaming_type_accepted():
    assert is_namespaced_type("x_qortroller.kill")
    assert is_namespaced_type("qortroller.kill")
    assert is_valid(make_event("x_qortroller.kill", 1.0, "retina_01", label="headshot"))
    assert is_valid(make_event("qortroller.presence", 2.0, "retina_01"))


def test_bare_unknown_type_rejected():
    problems = validate_event({"type": "kill", "t": 1.0, "src": "x"})
    assert any("unknown bare type" in p for p in problems)


def test_reserved_primitive_domain_squat_rejected():
    # 'zone.foo' squats the reserved 'zone' primitive domain -> not a legal custom type
    assert not is_namespaced_type("zone.foo")
    assert not is_valid({"type": "zone.foo", "t": 1.0, "src": "x"})


# -- required fields + optional types ---------------------------------------

def test_missing_required_field_rejected():
    assert "missing required field: src" in validate_event({"type": "line.cross", "t": 1.0})
    with pytest.raises(ValueError):
        make_event("line.cross", 1.0, "")            # empty src


def test_optional_field_type_checked():
    assert any("conf" in p for p in validate_event({"type": "line.cross", "t": 1.0, "src": "x", "conf": "high"}))
    assert any("n" in p for p in validate_event({"type": "count.threshold", "t": 1.0, "src": "x", "n": True}))  # bool != int


# -- ordered JSON-Lines serialization ---------------------------------------

def test_to_jsonl_ordered_omit_empty():
    evs = [make_event("x_q.a", 1.0, "cam"), make_event("x_q.b", 2.0, "cam", label="")]
    out = to_jsonl(evs).splitlines()
    assert len(out) == 2                               # one event per line, emission order
    assert '"type":"x_q.a"' in out[0] and '"type":"x_q.b"' in out[1]
    assert "label" not in out[1]                       # empty field omitted


def test_to_jsonl_rejects_nonconformant():
    with pytest.raises(ValueError):
        to_jsonl([{"type": "kill", "t": 1.0, "src": "x"}])   # bare unknown type


# -- F-TRA0-1: the ordered root is ORDER-SENSITIVE; the sorted root collides -

def test_ordered_root_is_order_sensitive():
    a = make_event("x_q.kill", 1.0, "cam")
    b = make_event("x_q.kill", 2.0, "cam")            # distinct (different t)
    r_ab = ordered_events_root([a, b], chain_fn=_mock_chain)
    r_ba = ordered_events_root([b, a], chain_fn=_mock_chain)
    assert r_ab != r_ba                               # order preserved (replayable) - the fix
    assert len(r_ab) == 32


def test_legacy_sorted_root_collides_on_reorder():
    """The finding the fix addresses: the legacy sorted root is order-INDEPENDENT, so a
    reordered replayable stream collides. ordered_events_root above does not."""
    a = make_event("x_q.kill", 1.0, "cam")
    b = make_event("x_q.kill", 2.0, "cam")
    assert compute_events_root_poseidon([a, b], chain_fn=_mock_chain) == \
           compute_events_root_poseidon([b, a], chain_fn=_mock_chain)


# -- F-TRA0-3: conformant events feed the existing commitment (additive) -----

def test_conformant_events_feed_existing_root():
    evs = [make_event("x_q.kill", 1.0, "cam"), make_event("zone.enter", 2.0, "cam", zone="mid")]
    assert validate_stream(evs) == []
    root = ordered_events_root(evs, chain_fn=_mock_chain)
    assert isinstance(root, bytes) and len(root) == 32
