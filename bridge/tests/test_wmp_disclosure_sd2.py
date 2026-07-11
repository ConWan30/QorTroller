"""WMP Selective Disclosure SD-2 — Merkle-tree upgrade pinning tests.

SD-1 revealed all leaf hashes; SD-2 commits via a Merkle tree, so the disclosure
carries only the root + per-revealed log-N inclusion proofs, and hidden claims'
leaf hashes never appear.
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

import pytest

from sdk.wmp_derived import build_claim, DERIVATIONS, _claim_hash
from sdk.wmp_disclosure import (build_merkle_disclosure, verify_merkle_disclosure,
                                _merkle_leaf, SCHEMA_V2)

_UC1 = REPO_ROOT / "wmp_corpus_real" / "wmp_corpus.jsonl"


def _claims() -> list:
    b = json.loads(_UC1.read_text(encoding="utf-8").splitlines()[0])
    return [build_claim(b, d) for d in DERIVATIONS]


def _check(res: dict, name: str):
    for c in res["checks"]:
        if c["name"] == name:
            return c["ok"]
    return None


# ── happy path ─────────────────────────────────────────────────────────────

def test_full_merkle_disclosure_verifies():
    d = build_merkle_disclosure(_claims())
    res = verify_merkle_disclosure(d)
    assert res["ok"] is True
    assert all(c["ok"] for c in res["checks"])
    assert d["schema"] == SCHEMA_V2
    assert d["set_size"] == 5
    assert len(d["revealed"]) == 5


def test_selective_reveal_proof_is_logn():
    claims = _claims()
    d = build_merkle_disclosure(claims, reveal_ids=["ACTION_ENTROPY_v1"])
    assert verify_merkle_disclosure(d)["ok"] is True
    assert len(d["revealed"]) == 1
    # 5 leaves -> tree depth ceil(log2(5)) = 3 -> proof length 3
    assert len(d["revealed"][0]["inclusion_proof"]) == 3


def test_hidden_values_absent_and_most_leaf_hashes_hidden():
    """SD-2: hidden VALUES are ALWAYS absent; and revealing 1 of 5 leaks at most
    the ONE leaf-level Merkle sibling's hash (inherent to Merkle inclusion) —
    never all N hidden leaf hashes, unlike SD-1's flat envelope."""
    claims = _claims()
    d = build_merkle_disclosure(claims, reveal_ids=["TRIGGER_ENGAGEMENT_FRACTION_v1"])
    blob = json.dumps(d)
    revealed_ids = {i["claim"]["derivation_id"] for i in d["revealed"]}
    hidden = [c for c in claims if c["derivation_id"] not in revealed_ids]
    leaked = 0
    for c in hidden:
        assert json.dumps(c["value"]) not in blob            # value ALWAYS hidden
        if _merkle_leaf(_claim_hash(c)) in blob:
            leaked += 1
    assert leaked < len(hidden)                              # strictly better than SD-1 (all N)
    assert leaked <= 1                                        # only the leaf-level sibling can leak


def test_deterministic_root():
    a = build_merkle_disclosure(_claims())
    b = build_merkle_disclosure(_claims())
    assert a["merkle_root"] == b["merkle_root"]
    assert a["commitment_root"] == b["commitment_root"]


def test_reveal_nothing_still_commits():
    d = build_merkle_disclosure(_claims(), reveal_ids=[])
    assert verify_merkle_disclosure(d)["ok"] is True
    assert d["revealed"] == []
    assert d["set_size"] == 5


# ── tamper rails ─────────────────────────────────────────────────────────────

def test_tampered_revealed_value_fails_membership():
    d = build_merkle_disclosure(_claims(), reveal_ids=["INPUT_TEMPO_v1"])
    d["revealed"][0]["claim"]["value"]["total_transitions"] = 0
    res = verify_merkle_disclosure(d)
    assert res["ok"] is False
    assert _check(res, "revealed_integrity") is False or _check(res, "revealed_membership") is False


def test_tampered_merkle_root_fails_commitment():
    d = build_merkle_disclosure(_claims(), reveal_ids=["ACTION_ENTROPY_v1"])
    d["merkle_root"] = "0" * 64
    res = verify_merkle_disclosure(d)
    assert res["ok"] is False
    # header commitment binds the root, and the proof no longer reaches it
    assert _check(res, "commitment_root") is False
    assert _check(res, "revealed_membership") is False


def test_forged_inclusion_proof_fails():
    d = build_merkle_disclosure(_claims(), reveal_ids=["ACTION_ENTROPY_v1"])
    d["revealed"][0]["inclusion_proof"] = [{"hash": "ab" * 32, "sibling_left": False}]
    res = verify_merkle_disclosure(d)
    assert res["ok"] is False
    assert _check(res, "revealed_membership") is False


def test_foreign_claim_fails_membership():
    d = build_merkle_disclosure(_claims(), reveal_ids=["ACTION_ENTROPY_v1"])
    b = json.loads(_UC1.read_text(encoding="utf-8").splitlines()[0])
    foreign = build_claim(b, "BUTTON_PRESS_COUNT_v1")
    foreign["value"]["press_events"] = 4242
    import sdk.wmp_derived as wd
    foreign["claim_hash"] = wd._claim_hash(foreign)
    # attach the real claim's (valid) proof to the foreign claim — must still fail
    d["revealed"].append({"claim": foreign, "inclusion_proof": d["revealed"][0]["inclusion_proof"]})
    res = verify_merkle_disclosure(d)
    assert res["ok"] is False
    assert _check(res, "revealed_membership") is False


def test_cross_bundle_refused():
    claims = _claims()
    claims[2] = copy.deepcopy(claims[2])
    claims[2]["parent_bundle_hash"] = "f" * 64
    with pytest.raises(ValueError, match="same parent bundle"):
        build_merkle_disclosure(claims)
