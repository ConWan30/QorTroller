"""TPF-1 F3 - meaning-plane HARD cryptographic join (earned, never asserted).

F3 grounding CORRECTED the optimistic F1 assumption: the PoSP's KAS commitment is a
SHA-256 over KAS-domain data, NOT the Arc-5 Poseidon PoAC-chain root - different domain,
cannot byte-match. So the hard join REQUIRES the PoSP to carry the SAME Arc-5
poac_chain_root the WMP replay pipeline computes. When it does, the meaning join EARNS
CRYPTOGRAPHIC via a byte-equal root match; absent (the committed M17) it stays honestly
REFERENCE_ATTESTED, and an unearned CRYPTOGRAPHIC claim is REJECTED.

This is the DeferredProver shape: the mechanism is real + tested here; M17's real join is
gated (its PoSP predates the field), so no fake join ships. The moment a PoSP carries the
matching root, the join is cryptographic and machine-verified - and the S4 meaning splice
is defeated for that session.
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from l9_presence.tri_plane_manifest import (
    build_tri_plane_manifest, verify_tri_plane_manifest, _mhash, poac_chain_join,
    JOIN_CRYPTOGRAPHIC, JOIN_REFERENCE_ATTESTED,
    POAC_VERIFIED_MATCH, POAC_MISMATCH, POAC_ABSENT,
)

_POSP = REPO_ROOT / "audits" / "posp_record_match17_rp_fixb3_2026-07-08.json"
_WMP = REPO_ROOT / "wmp_corpus_real" / "wmp_corpus.jsonl"


def _posp():
    return json.loads(_POSP.read_text(encoding="utf-8"))


def _wmp():
    return json.loads(_WMP.read_text(encoding="utf-8").splitlines()[0])


def _wmp_root(wmp):
    return wmp["humanity_proof_public_inputs"]["poacChainRoot"]


def _check(res, name):
    for c in res["checks"]:
        if c["name"] == name:
            return c["ok"]
    return None


# -- the pure helper --------------------------------------------------------

def test_poac_chain_join_helper():
    assert poac_chain_join("5", "5") == POAC_VERIFIED_MATCH
    assert poac_chain_join(5, "5") == POAC_VERIFIED_MATCH          # int vs decimal str
    assert poac_chain_join("0x05", "5") == POAC_VERIFIED_MATCH     # 0x-hex vs decimal
    assert poac_chain_join("5", "6") == POAC_MISMATCH
    assert poac_chain_join(None, "5") == POAC_ABSENT
    assert poac_chain_join("5", None) == POAC_ABSENT
    assert poac_chain_join("garbage", "5") == POAC_ABSENT          # unparseable -> absent, never a match


# -- the F3 win: a matching root EARNS the cryptographic meaning join -------

def test_matching_root_earns_cryptographic():
    posp, wmp = _posp(), _wmp()
    posp["poac_chain_root"] = _wmp_root(wmp)                       # PoSP carries the SAME PoAC-chain root
    m = build_tri_plane_manifest(posp, wmp, attested_same_session=True)
    assert m["join_status"]["poac_chain_join"] == POAC_VERIFIED_MATCH
    assert m["join_status"]["meaning_session"] == JOIN_CRYPTOGRAPHIC
    res = verify_tri_plane_manifest(m, posp=posp, wmp_bundle=wmp)
    assert res["ok"] is True
    assert _check(res, "meaning_join_honest") is True


def test_root_representation_robust():
    posp, wmp = _posp(), _wmp()
    posp["poac_chain_root"] = int(_wmp_root(wmp))                  # stored as INT vs bundle's form
    m = build_tri_plane_manifest(posp, wmp, attested_same_session=True)
    assert m["join_status"]["poac_chain_join"] == POAC_VERIFIED_MATCH


# -- a mismatched root stays honestly attested (never rounded up) -----------

def test_mismatched_root_stays_attested():
    posp, wmp = _posp(), _wmp()
    posp["poac_chain_root"] = str(int(_wmp_root(wmp)) + 1)         # a DIFFERENT PoAC chain
    m = build_tri_plane_manifest(posp, wmp, attested_same_session=True)
    assert m["join_status"]["poac_chain_join"] == POAC_MISMATCH
    assert m["join_status"]["meaning_session"] == JOIN_REFERENCE_ATTESTED   # NOT cryptographic
    assert verify_tri_plane_manifest(m, posp=posp, wmp_bundle=wmp)["ok"] is True


# -- F3 DEFEATS the S4 meaning splice when the PoSP carries a root ----------

def test_f3_defeats_meaning_splice_when_root_present():
    posp, wmp = _posp(), _wmp()
    posp["poac_chain_root"] = _wmp_root(wmp)
    bundle_B = copy.deepcopy(wmp)                                  # forger splices a different-session bundle
    bundle_B["humanity_proof_public_inputs"]["poacChainRoot"] = str(int(_wmp_root(wmp)) + 7)
    m = build_tri_plane_manifest(posp, bundle_B, attested_same_session=True)
    # the builder refuses the cryptographic label - the roots disagree
    assert m["join_status"]["poac_chain_join"] == POAC_MISMATCH
    assert m["join_status"]["meaning_session"] != JOIN_CRYPTOGRAPHIC
    # a forger who forces the label + rehashes is REJECTED by verify
    m["join_status"]["meaning_session"] = JOIN_CRYPTOGRAPHIC
    m["manifest_hash"] = _mhash(m)
    res = verify_tri_plane_manifest(m, posp=posp, wmp_bundle=bundle_B)
    assert res["ok"] is False
    assert _check(res, "meaning_join_honest") is False


# -- honest defer: the committed M17 (no root) is byte-identical to before --

def test_absent_root_real_m17_unchanged():
    m = build_tri_plane_manifest(_posp(), _wmp(), attested_same_session=True)   # M17 PoSP has no poac_chain_root
    assert m["join_status"]["poac_chain_join"] == POAC_ABSENT
    assert m["join_status"]["meaning_session"] == JOIN_REFERENCE_ATTESTED
    assert verify_tri_plane_manifest(m, posp=_posp(), wmp_bundle=_wmp())["ok"] is True


def test_unearned_cryptographic_claim_rejected():
    m = build_tri_plane_manifest(_posp(), _wmp(), attested_same_session=True)   # ABSENT root
    m["join_status"]["meaning_session"] = JOIN_CRYPTOGRAPHIC                    # the lie F3 hasn't earned
    m["manifest_hash"] = _mhash(m)
    res = verify_tri_plane_manifest(m)
    assert res["ok"] is False
    assert _check(res, "meaning_join_honest") is False
