"""TPF-1 F4 - plane-splice adversarial matrix (forge-your-own, AH-1/A3 discipline).

We forge cross-plane mismatches against the fusion verifier and prove what it catches -
and, honestly, the one splice it CANNOT catch yet (the meaning-plane, F3-gated). The
forge-your-own rule (AH-1 A15 / PoSP A3) applied to the federation: attack your own
verifier, fix the gap you find, and pin the deferred ceiling instead of rounding it up.

The gap F4 closed: before the `session_consistency` rail, a manifest whose top-level
join key disagreed with its own assertion/observation planes was NOT caught when
verified WITHOUT the PoSP artifact (S1/S2). It is now.

The ceiling F4 pins: a MEANING splice (a bundle from a different session bound under
`attested_same_session=True`) still VERIFIES, because the WMP bundle carries no
session_id to cross-check - the manifest says so honestly (REFERENCE_ATTESTED, never
CRYPTOGRAPHIC), and F3 is what upgrades attestation to proof (S4).
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
    JOIN_CRYPTOGRAPHIC, JOIN_REFERENCE_ATTESTED,
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


# -- baseline: the real M17 manifest passes every rail (no regression) ------

def test_baseline_real_m17_passes():
    m = build_tri_plane_manifest(_posp(), _wmp(), attested_same_session=True)
    res = verify_tri_plane_manifest(m, posp=_posp(), wmp_bundle=_wmp())
    assert res["ok"] is True
    assert _check(res, "session_consistency") is True


# -- S1: internal assertion-session splice (CAUGHT without artifacts) -------
# The gap F4 closed: top-level join key from session A, assertion plane from session B.

def test_s1_assertion_session_splice_caught_no_artifacts():
    m = build_tri_plane_manifest(_posp(), _wmp(), attested_same_session=True)
    m["planes"]["assertion"]["session_id"] = "spliced_session_B"
    m["manifest_hash"] = _mhash(m)                      # forger rehashes to look internally clean
    res = verify_tri_plane_manifest(m)                  # NO posp artifact provided
    assert res["ok"] is False
    assert _check(res, "session_consistency") is False


# -- S2: internal observation-session splice (CAUGHT without artifacts) -----

def test_s2_observation_session_splice_caught_no_artifacts():
    m = build_tri_plane_manifest(_posp(), _wmp(), attested_same_session=True)
    m["planes"]["observation"]["session_id"] = "spliced_session_C"
    m["manifest_hash"] = _mhash(m)
    res = verify_tri_plane_manifest(m)
    assert res["ok"] is False
    assert _check(res, "session_consistency") is False


# -- S3: wrong-PoSP artifact splice (CAUGHT by binding) ---------------------

def test_s3_verify_against_wrong_posp_caught():
    m = build_tri_plane_manifest(_posp(), _wmp(), attested_same_session=True)
    other = _posp()
    other["session_id"] = "someone_elses_session"       # verify against a DIFFERENT session's PoSP
    res = verify_tri_plane_manifest(m, posp=other)
    assert res["ok"] is False
    assert _check(res, "assertion_binds_posp") is False


# -- S4: MEANING splice - the HONEST CEILING (verifier cannot catch; F3 does) --
# A bundle from a different session, bound attested=True. The WMP bundle carries no
# session_id, so no cross-check exists. The manifest VERIFIES - but never claims the
# meaning join is cryptographic; it says REFERENCE_ATTESTED, so no outsider is misled.

def test_s4_meaning_splice_is_the_documented_ceiling():
    bundle_B = copy.deepcopy(_wmp())
    bundle_B["action_trace_ticks"] = 111                # a structurally-valid DIFFERENT-session bundle
    m = build_tri_plane_manifest(_posp(), bundle_B, attested_same_session=True)
    res = verify_tri_plane_manifest(m, posp=_posp(), wmp_bundle=bundle_B)
    # The verifier accepts it - it has no cryptographic way to know bundle_B isn't M17's session.
    assert res["ok"] is True
    # ...but the honesty rail holds: meaning<->session is ATTESTED, never overclaimed CRYPTOGRAPHIC.
    assert m["join_status"]["meaning_session"] == JOIN_REFERENCE_ATTESTED
    assert m["join_status"]["meaning_session"] != JOIN_CRYPTOGRAPHIC


# -- S5: separation-law attack UNDER a rehash splice (CAUGHT) ----------------
# The operator's specific ask: test the separation-law machine-check while the forger
# rehashes to make the manifest internally consistent. The law still holds.

def test_s5_asserting_field_smuggled_into_meaning_caught():
    m = build_tri_plane_manifest(_posp(), _wmp(), attested_same_session=True)
    m["planes"]["meaning"]["claim"] = "SYNCHRONIZED_PRESENT"   # meaning trying to assert
    m["manifest_hash"] = _mhash(m)                             # rehashed - internally consistent
    res = verify_tri_plane_manifest(m, posp=_posp(), wmp_bundle=_wmp())
    assert res["ok"] is False
    assert _check(res, "separation_law") is False


# -- S6: manifest_hash tamper (CAUGHT by integrity) -------------------------

def test_s6_hash_tamper_caught():
    m = build_tri_plane_manifest(_posp(), _wmp(), attested_same_session=True)
    m["planes"]["assertion"]["verdict"] = "FORGED"            # mutate a field, do NOT rehash
    res = verify_tri_plane_manifest(m)
    assert res["ok"] is False
    assert _check(res, "manifest_hash") is False
