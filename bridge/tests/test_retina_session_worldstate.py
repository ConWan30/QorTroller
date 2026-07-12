"""TRA-1 T6.2 tests - session WorldState assembler from observation.

Verifies: the controller is a locus-only entity (no vec/bbox - the biometric-adjacent latent never
exports); honest omission when the HID is blind (input_locus=None); video entities pass through;
the nested scene is guarded against the biometric floor + separation law; and the assembled
WorldState is digestible for the T6.3 v3 commitment.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from bridge.vapi_bridge.retina_session_worldstate import (
    DEFAULT_SRC, PRESENCE_LOCUS, worldstate_from_observation,
)
from bridge.vapi_bridge.retina_worldstate_std import make_entity, validate_worldstate


def test_controller_added_as_locus_only_entity():
    ws = worldstate_from_observation(1000.0, controller_id="edge-01", input_locus=[0.1, -0.2])
    assert validate_worldstate(ws) == []
    ents = ws["entities"]
    assert len(ents) == 1
    c = ents[0]
    assert c["type"] == "controller" and c["locus"] == [0.1, -0.2]
    assert "vec" not in c and "bbox" not in c        # locus-only; no biometric-adjacent latent


def test_honest_omission_when_hid_blind():
    ws = worldstate_from_observation(1.0, controller_id="edge-01", input_locus=None)
    assert validate_worldstate(ws) == []
    assert not ws.get("entities")                    # no controller entity fabricated


def test_presence_locus_marks_present_without_live_reading():
    ws = worldstate_from_observation(1.0, controller_id="edge-01", input_locus=PRESENCE_LOCUS)
    assert ws["entities"][0]["locus"] == [0.0, 0.0]


def test_video_entities_passthrough():
    vid = make_entity("obj-1", "player", bbox=[10, 20, 30, 40])
    ws = worldstate_from_observation(1.0, video_entities=[vid])
    assert ws["entities"][0]["id"] == "obj-1"


def test_scene_biometric_floor_refused():
    with pytest.raises(ValueError):
        worldstate_from_observation(1.0, scene={"l4_vector": [1, 2, 3]})


def test_scene_separation_law_refused():
    with pytest.raises(ValueError):
        worldstate_from_observation(1.0, scene={"verdict": "AUTHORED"})


def test_smallest_valid_state():
    ws = worldstate_from_observation(1.0)
    assert validate_worldstate(ws) == []
    assert ws["src"] == DEFAULT_SRC and ws["t"] == 1.0


def test_worldstate_digestible_for_v3():
    from bridge.vapi_bridge.retina_state_commitment import compute_worldstate_digest
    ws = worldstate_from_observation(1000.0, controller_id="edge-01", input_locus=[0.1, 0.2])
    d = compute_worldstate_digest(ws)
    assert isinstance(d, (bytes, bytearray)) and len(d) == 32
