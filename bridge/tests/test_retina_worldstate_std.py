"""TRA-1 T2 - WorldState assembler + controller-sensor fusion tests.

Confirms QorTroller expresses its multi-modal fusion in Trio Retina's real WorldState schema:
video entities carry `bbox` + a model-tagged visual `vec`; the controller carries `locus`
(input-space) and NO latent; and the exportable state is held to two rails - the separation
law (no verdict) and the biometric floor (the anti-cheat moat never enters the WorldState).
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from bridge.vapi_bridge.retina_worldstate_std import (
    _FORBIDDEN_BIOMETRIC,
    make_vec, make_entity, controller_entity, make_worldstate, validate_worldstate,
)


# -- the model-tagged latent (vec) ------------------------------------------

def test_make_vec_inline_and_by_reference():
    inline = make_vec("osnet-reid", 2, dtype="fp32", values=[0.1, 0.2])
    assert inline == {"model": "osnet-reid", "dim": 2, "dtype": "fp32", "values": [0.1, 0.2]}
    ref = make_vec("v-jepa2-vitl", 1024, dtype="fp16", ref="vec://abc")
    assert ref["ref"] == "vec://abc" and "values" not in ref


def test_make_vec_requires_exactly_one_channel():
    with pytest.raises(ValueError):
        make_vec("m", 2)                                    # neither values nor ref
    with pytest.raises(ValueError):
        make_vec("m", 2, values=[1, 2], ref="vec://x")      # both


def test_make_vec_validates_dim_dtype_length():
    with pytest.raises(ValueError):
        make_vec("m", 3, values=[1, 2])                     # length != dim
    with pytest.raises(ValueError):
        make_vec("m", 2, dtype="bogus", values=[1, 2])      # bad dtype


# -- entities: bbox (vision) vs locus (field) -------------------------------

def test_make_entity_bbox_and_locus():
    assert make_entity("7", "person", bbox=[1, 2, 3, 4])["bbox"] == [1, 2, 3, 4]
    assert make_entity("rf", "rf_subject", locus=[2.41, 3.07])["locus"] == [2.41, 3.07]
    with pytest.raises(ValueError):
        make_entity("x", "y", bbox=[1, 2, 3])               # bbox must be 4 pixels


def test_controller_entity_is_locus_only_no_latent():
    pad = controller_entity("edge_pad", input_locus=[0.62, 0.05])
    assert pad["type"] == "controller" and pad["locus"] == [0.62, 0.05]
    assert "bbox" not in pad and "vec" not in pad           # input-space; moat never exports


# -- WorldState conformance -------------------------------------------------

def test_worldstate_minimal_and_requires_src_t():
    assert validate_worldstate(make_worldstate("cam", 1.0)) == []      # smallest valid = {src,t}
    assert "missing required field: src" in validate_worldstate({"t": 1.0})
    assert "missing required field: t" in validate_worldstate({"src": "cam"})


# -- the two honesty rails --------------------------------------------------

def test_separation_law_on_worldstate_entity():
    with pytest.raises(ValueError):
        make_worldstate("cam", 1.0, entities=[{"id": "9", "type": "player", "verdict": "SYNC"}])


def test_biometric_floor_rejects_forbidden_column():
    # a forbidden biometric column as a key is refused at entity + worldstate level
    with pytest.raises(ValueError):
        make_entity("p", "controller", l4_mahalanobis_distance=7.1)
    problems = validate_worldstate({"src": "cam", "t": 1.0, "ait_rms": 0.3})
    assert any("biometric floor" in p for p in problems)


# -- the centerpiece: video + controller fused in the real schema -----------

def test_multimodal_fusion_video_plus_controller():
    enemy = make_entity("e7", "person", bbox=[812, 430, 902, 640],
                        vec=make_vec("osnet-reid", 2, values=[0.1, 0.2]))
    pad = controller_entity("pad", input_locus=[0.62, 0.05])
    ws = make_worldstate(src="cam", t=1.0, frame=524, entities=[enemy, pad],
                         scene=make_vec("v-jepa2-vitl", 1024, dtype="fp16", ref="vec://s"))
    assert validate_worldstate(ws) == []
    ents = {e["id"]: e for e in ws["entities"]}
    assert "bbox" in ents["e7"] and "vec" in ents["e7"]      # video: pixel box + visual latent
    assert "locus" in ents["pad"] and "bbox" not in ents["pad"]   # controller: input-space, no box
    assert "vec" not in ents["pad"]                          # controller: no latent (moat absent)
    assert ws["scene"]["model"] == "v-jepa2-vitl"            # scene latent (vision, model-tagged)


# -- the biometric floor stays in sync with the source of truth -------------

def test_forbidden_biometric_mirrors_preprocessor():
    from bridge.vapi_bridge.replay_proof_pipeline.pre_processor import ReplayPreProcessor
    assert _FORBIDDEN_BIOMETRIC == ReplayPreProcessor.FORBIDDEN_COLUMNS
