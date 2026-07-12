"""A2A-CDM Round 07 - forge execution of grok's Round-06 adversarial predictions (T1/T2).

Each test forges the exact attack grok described and asserts the verifier's response. Two
were CONFIRMED REAL GAPS on first run and fixed in this same commit:
  * T1-A2 - forking artifacts + stripped plane roots verified GREEN (D-CDM-1 bypass under
    "full verify with artifacts"). Fixed: artifact-derived roots are authoritative.
  * (companion) plane-root-lie - a plane declaring a root that disagrees with its artifact.
The rest confirm rails hold or pin a documented ceiling (T1-A1 pure-manifest, T1-A4 splice).
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from l9_presence.tri_plane_manifest import (
    build_tri_plane_manifest, verify_tri_plane_manifest, _mhash, consumer_status,
    JOIN_CRYPTOGRAPHIC, JOIN_REFERENCE_ATTESTED, JOIN_CONTENT_FORK,
)

_POSP = REPO_ROOT / "audits" / "posp_record_match17_rp_fixb3_2026-07-08.json"
_WMP = REPO_ROOT / "wmp_corpus_real" / "wmp_corpus.jsonl"


def _posp():
    return json.loads(_POSP.read_text(encoding="utf-8"))


def _wmp():
    return json.loads(_WMP.read_text(encoding="utf-8").splitlines()[0])


def _wroot(wmp):
    return wmp["humanity_proof_public_inputs"]["poacChainRoot"]


def _check(res, name):
    for c in res["checks"]:
        if c["name"] == name:
            return c["ok"]
    return None


# -- T1-A2: forking artifacts + STRIPPED plane roots (was a real D-CDM-1 bypass) --------

def test_t1_a2_stripped_planes_with_forking_artifacts_caught():
    posp, wmp = _posp(), _wmp()
    posp["poac_chain_root"] = str(int(_wroot(wmp)) + 999)          # real PoSP root A != bundle B
    m = build_tri_plane_manifest(posp, wmp, attested_same_session=True)
    m["planes"]["assertion"]["poac_chain_root"] = None             # launder: strip both
    m["planes"]["meaning"]["poac_chain_root"] = None
    m["manifest_hash"] = _mhash(m)
    res = verify_tri_plane_manifest(m, posp=posp, wmp_bundle=wmp)  # artifacts still fork
    assert res["ok"] is False
    assert _check(res, "content_fork") is False                    # artifact-derived roots authoritative


def test_t1_a2b_plane_declares_root_disagreeing_with_artifact_caught():
    posp, wmp = _posp(), _wmp()
    posp["poac_chain_root"] = _wroot(wmp)                          # artifacts AGREE
    m = build_tri_plane_manifest(posp, wmp, attested_same_session=True)
    m["planes"]["assertion"]["poac_chain_root"] = str(int(_wroot(wmp)) + 5)  # plane LIES
    m["manifest_hash"] = _mhash(m)
    res = verify_tri_plane_manifest(m, posp=posp, wmp_bundle=wmp)
    assert res["ok"] is False
    assert _check(res, "assertion_root_matches_posp") is False


# -- T1-A1: pure-manifest downgrade-to-ABSENT is the DOCUMENTED CEILING (no artifacts) --

def test_t1_a1_pure_manifest_downgrade_is_attested_ceiling_not_verified():
    """WITHOUT artifacts, a stripped manifest can only ever claim ATTESTED - never VERIFIED.
    This is grok's accepted ceiling (a): ABSENT = evidence-not-in-hand. The moment artifacts
    are supplied (test above) the fork is caught, so a consumer demands artifacts for > ATTESTED."""
    posp, wmp = _posp(), _wmp()
    posp["poac_chain_root"] = str(int(_wroot(wmp)) + 999)
    m = build_tri_plane_manifest(posp, wmp, attested_same_session=True)   # meaning=CONTENT_FORK
    m["planes"]["assertion"]["poac_chain_root"] = None                    # strip one side
    m["join_status"]["meaning_session"] = JOIN_REFERENCE_ATTESTED         # relabel down
    m["join_status"]["poac_chain_join"] = "ABSENT"
    m["manifest_hash"] = _mhash(m)
    res = verify_tri_plane_manifest(m)                                    # NO artifacts
    assert res["ok"] is True                                              # ceiling: not caught bare
    assert consumer_status(m, res)["joined_status"] == "JOINED_ATTESTED"  # never JOINED_VERIFIED


def test_t1_a5_one_sided_root_never_verified():
    posp, wmp = _posp(), _wmp()                                           # M17: PoSP has no root
    m = build_tri_plane_manifest(posp, wmp, attested_same_session=True)   # meaning root present only
    cs = consumer_status(m, verify_tri_plane_manifest(m, posp=posp, wmp_bundle=wmp))
    assert cs["joined_status"] == "JOINED_ATTESTED"                       # one-sided -> attested, not verified


# -- T2-A1: consumer_status must see a fork from plane fields even with NO verify_result --

def test_t2_a1_consumer_status_recomputes_fork_without_verify_result():
    posp, wmp = _posp(), _wmp()
    posp["poac_chain_root"] = str(int(_wroot(wmp)) + 7)
    m = build_tri_plane_manifest(posp, wmp, attested_same_session=True)   # both plane roots present, fork
    m["join_status"]["meaning_session"] = JOIN_REFERENCE_ATTESTED         # producer lies "attested"
    m["manifest_hash"] = _mhash(m)
    cs = consumer_status(m)                                               # NO verify_result passed
    assert cs["joined_status"] == "CONTENT_FORK"                          # recomputed from plane roots


def test_t2_a1b_bare_cryptographic_label_without_matching_roots_not_verified():
    posp, wmp = _posp(), _wmp()
    m = build_tri_plane_manifest(posp, wmp, attested_same_session=True)   # M17: roots ABSENT
    m["join_status"]["meaning_session"] = JOIN_CRYPTOGRAPHIC              # unearned label
    m["manifest_hash"] = _mhash(m)
    assert consumer_status(m)["joined_status"] == "UNVERIFIABLE"          # label alone never verifies


# -- regression: the real M17 still verifies + reads JOINED_ATTESTED --------------------

def test_real_m17_unaffected_by_r07_hardening():
    posp, wmp = _posp(), _wmp()
    m = build_tri_plane_manifest(posp, wmp, attested_same_session=True)
    res = verify_tri_plane_manifest(m, posp=posp, wmp_bundle=wmp)
    assert res["ok"] is True
    assert consumer_status(m, res)["joined_status"] == "JOINED_ATTESTED"
