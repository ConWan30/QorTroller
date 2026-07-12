"""TRA-1 T3 - VAPI-RETINA-STATE-v3 verify-rung forge tests.

Confirms the v3 commitment is the correct verify rung over the CANONICAL Trio Retina standard:
it is deterministic, ORDER-sensitive (F-TRA0-1 - a reordered replayable stream commits
differently), binds the WorldState frame (a tampered WorldState changes the commitment), and is
rail-guarded (an asserting event or a biometric WorldState column is refused BEFORE commit).
Poseidon is mocked via the module hook so no node is needed.
"""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from bridge.vapi_bridge.retina_event_std import make_event
from bridge.vapi_bridge.retina_worldstate_std import make_worldstate, make_entity, controller_entity
from bridge.vapi_bridge import retina_events_root as rer
from bridge.vapi_bridge.retina_state_commitment import (
    compute_retina_state_commitment_v3, compute_retina_state_commitment_v2, DOMAIN_TAG_V3,
)

_DEV = "aa" * 32


def _mock_chain(elems):
    """Deterministic, ORDER-SENSITIVE stand-in for the node Poseidon chain."""
    return hashlib.sha256(",".join(str(x) for x in elems).encode()).digest()


@pytest.fixture(autouse=True)
def _mock_poseidon():
    rer.set_poseidon_chain_fn(_mock_chain)
    yield
    rer.set_poseidon_chain_fn(None)


def _stream():
    return [make_event("x_q.kill", 1.0, "cam"), make_event("x_q.kill", 2.0, "cam")]


def _ws():
    return make_worldstate("cam", 1.0, entities=[
        make_entity("e7", "person", bbox=[1, 2, 3, 4]),
        controller_entity("pad", input_locus=[0.6, 0.05]),
    ])


def test_v3_deterministic():
    a = compute_retina_state_commitment_v3(_DEV, 111, _stream(), worldstate=_ws())
    b = compute_retina_state_commitment_v3(_DEV, 111, _stream(), worldstate=_ws())
    assert a == b and len(a) == 64


def test_v3_is_order_sensitive():
    s = _stream()
    fwd = compute_retina_state_commitment_v3(_DEV, 111, s)
    rev = compute_retina_state_commitment_v3(_DEV, 111, list(reversed(s)))
    assert fwd != rev                                     # F-TRA0-1: replayable order is committed


def test_v3_binds_worldstate_frame():
    base = compute_retina_state_commitment_v3(_DEV, 111, _stream(), worldstate=_ws())
    tampered = make_worldstate("cam", 1.0, entities=[
        make_entity("e7", "person", bbox=[9, 9, 9, 9]),   # moved box -> different frame
        controller_entity("pad", input_locus=[0.6, 0.05]),
    ])
    assert compute_retina_state_commitment_v3(_DEV, 111, _stream(), worldstate=tampered) != base


def test_v3_rejects_asserting_event():
    bad = _stream() + [{"type": "x_q.kill", "t": 3.0, "src": "cam", "verdict": "SYNC"}]
    with pytest.raises(ValueError):
        compute_retina_state_commitment_v3(_DEV, 111, bad)


def test_v3_rejects_biometric_worldstate():
    bad_ws = {"src": "cam", "t": 1.0, "ait_rms": 0.3}     # biometric floor violation
    with pytest.raises(ValueError):
        compute_retina_state_commitment_v3(_DEV, 111, _stream(), worldstate=bad_ws)


def test_v3_distinct_from_v2():
    # different domain + ordered root + bound WorldState -> never collides with v2
    v3 = compute_retina_state_commitment_v3(_DEV, 111, _stream(), worldstate=_ws())
    v2 = compute_retina_state_commitment_v2(_DEV, 111, _stream())
    assert v3 != v2
    assert DOMAIN_TAG_V3 == b"VAPI-RETINA-STATE-v3"
