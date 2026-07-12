"""TPF-1 F1 - tri-plane session manifest tests.

The real M17 session federates into one object (assertion + observation CRYPTOGRAPHIC,
meaning REFERENCE_ATTESTED). The load-bearing rails: the manifest can NEVER overclaim
the meaning join as CRYPTOGRAPHIC (F3-gated), and the separation law is machine-checked
(observation/meaning may not carry an asserting field).
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from l9_presence.tri_plane_manifest import (
    build_tri_plane_manifest, verify_tri_plane_manifest, _mhash,
    JOIN_CRYPTOGRAPHIC, JOIN_REFERENCE_ATTESTED, JOIN_UNATTESTED,
)

_POSP = REPO_ROOT / "audits" / "posp_record_match17_rp_fixb3_2026-07-08.json"
_WMP = REPO_ROOT / "wmp_corpus_real" / "wmp_corpus.jsonl"


def _posp():
    return json.loads(_POSP.read_text(encoding="utf-8"))


def _wmp():
    return json.loads(_WMP.read_text(encoding="utf-8").splitlines()[0])


def _check(res, name):
    for c in res["checks"]:
        if c["name"] == name:
            return c["ok"]
    return None


# -- real M17 federates + verifies -----------------------------------------

def test_real_m17_federates_and_verifies():
    m = build_tri_plane_manifest(_posp(), _wmp(), attested_same_session=True)
    res = verify_tri_plane_manifest(m, posp=_posp(), wmp_bundle=_wmp())
    assert res["ok"] is True
    assert m["join_status"]["assertion_observation"] == JOIN_CRYPTOGRAPHIC
    assert m["join_status"]["meaning_session"] == JOIN_REFERENCE_ATTESTED


def test_unattested_meaning_is_honestly_unattested():
    m = build_tri_plane_manifest(_posp(), _wmp(), attested_same_session=False)
    assert m["join_status"]["meaning_session"] == JOIN_UNATTESTED


def test_all_three_planes_present():
    p = build_tri_plane_manifest(_posp(), _wmp())["planes"]
    assert p["assertion"]["kas_session_root"] and p["observation"]["retina_perception_root"]
    assert p["meaning"]["bundle_hash"] and p["meaning"]["consent_gamer_address"]


# -- the honesty rail: meaning join can never be overclaimed CRYPTOGRAPHIC --

def test_overclaimed_meaning_join_fails():
    m = build_tri_plane_manifest(_posp(), _wmp(), attested_same_session=True)
    m["join_status"]["meaning_session"] = JOIN_CRYPTOGRAPHIC   # the lie F3 hasn't earned
    m["manifest_hash"] = _mhash(m)
    res = verify_tri_plane_manifest(m)
    assert res["ok"] is False
    assert _check(res, "meaning_join_honest") is False


# -- the separation law (machine-checked) ----------------------------------

def test_separation_law_observation_cannot_assert():
    m = build_tri_plane_manifest(_posp(), _wmp())
    m["planes"]["observation"]["verdict"] = "SYNCHRONIZED"     # observation asserting -> illegal
    m["manifest_hash"] = _mhash(m)
    res = verify_tri_plane_manifest(m)
    assert res["ok"] is False
    assert _check(res, "separation_law") is False


def test_separation_law_meaning_cannot_assert():
    m = build_tri_plane_manifest(_posp(), _wmp())
    m["planes"]["meaning"]["presence_score"] = 0.9            # meaning feeding presence -> illegal
    m["manifest_hash"] = _mhash(m)
    assert verify_tri_plane_manifest(m)["ok"] is False


# -- binding + integrity ----------------------------------------------------

def test_manifest_hash_tamper_fails():
    m = build_tri_plane_manifest(_posp(), _wmp())
    m["session_id"] = "different"
    assert _check(verify_tri_plane_manifest(m), "manifest_hash") is False


def test_binding_to_wrong_bundle_fails():
    m = build_tri_plane_manifest(_posp(), _wmp())
    other = copy.deepcopy(_wmp())
    other["action_trace_ticks"] = 999                        # a different bundle -> different hash
    res = verify_tri_plane_manifest(m, wmp_bundle=other)
    assert res["ok"] is False
    assert _check(res, "meaning_binds_bundle") is False


def test_incomplete_ao_join_when_root_missing():
    posp = _posp()
    posp["events_roots"] = {"kas_session_root": posp["events_roots"]["kas_session_root"]}  # drop retina
    m = build_tri_plane_manifest(posp, _wmp())
    assert m["join_status"]["assertion_observation"] != JOIN_CRYPTOGRAPHIC
