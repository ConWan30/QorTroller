"""WMP Selective Disclosure (SD-1) — C1 pinning tests.

Commit to the 5-claim VDC fingerprint of the real UC-1 bundle, reveal a chosen
subset, and prove the rails: immutable commitment, membership, binding, and that
hidden claims' VALUES are never in the envelope.
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

import pytest

from sdk.wmp_derived import build_claim, DERIVATIONS
from sdk.wmp_disclosure import build_disclosure, verify_disclosure, _commitment_root, SCHEMA

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

def test_full_disclosure_verifies():
    d = build_disclosure(_claims())
    res = verify_disclosure(d)
    assert res["ok"] is True
    assert all(c["ok"] for c in res["checks"])
    assert d["schema"] == SCHEMA
    assert d["set_size"] == len(DERIVATIONS) == 5
    assert len(d["revealed"]) == 5


def test_selective_reveal_hides_the_rest():
    claims = _claims()
    reveal = ["TRIGGER_ENGAGEMENT_FRACTION_v1", "STICK_ENGAGEMENT_FRACTION_v1"]
    d = build_disclosure(claims, reveal_ids=reveal)
    res = verify_disclosure(d)
    assert res["ok"] is True
    # only the chosen 2 carry full values; the set still commits to all 5
    assert sorted(c["derivation_id"] for c in d["revealed"]) == sorted(reveal)
    assert d["set_size"] == 5
    assert len(d["leaf_hashes"]) == 5
    assert d["derivation_inventory"] == sorted(DERIVATIONS)   # inventory shows all types exist


def test_hidden_values_are_absent_from_envelope():
    """The hidden claims' VALUES never appear — only their hashes are in leaves."""
    claims = _claims()
    d = build_disclosure(claims, reveal_ids=["ACTION_ENTROPY_v1"])
    revealed_ids = {c["derivation_id"] for c in d["revealed"]}
    assert revealed_ids == {"ACTION_ENTROPY_v1"}
    # no hidden claim's value dict is serialized anywhere in the disclosure
    blob = json.dumps(d)
    for c in claims:
        if c["derivation_id"] not in revealed_ids:
            assert json.dumps(c["value"]) not in blob        # value hidden
            assert c["claim_hash"] in d["leaf_hashes"]        # but membership committed


def test_reveal_nothing_still_commits():
    """Max privacy: prove a committed set of N claims exists, reveal zero values."""
    d = build_disclosure(_claims(), reveal_ids=[])
    res = verify_disclosure(d)
    assert res["ok"] is True
    assert d["revealed"] == []
    assert d["set_size"] == 5


# ── immutability / tamper rails (fail-closed) ──────────────────────────────

def test_tampered_root_fails():
    d = build_disclosure(_claims())
    d["commitment_root"] = "0" * 64
    assert _check(verify_disclosure(d), "commitment_root") is False


def test_tampered_set_size_fails():
    d = build_disclosure(_claims())
    d["set_size"] = 99
    assert _check(verify_disclosure(d), "set_size") is False


def test_tampered_inventory_breaks_root():
    """Inventory is committed — misstating claim types breaks the root."""
    d = build_disclosure(_claims())
    d["derivation_inventory"] = d["derivation_inventory"][:-1] + ["FAKE_v1"]
    assert _check(verify_disclosure(d), "commitment_root") is False


def test_tampered_revealed_value_fails_membership():
    d = build_disclosure(_claims(), reveal_ids=["INPUT_TEMPO_v1"])
    d["revealed"][0]["value"]["total_transitions"] = 0        # lie about a revealed value
    res = verify_disclosure(d)
    assert res["ok"] is False
    # its recomputed hash no longer matches the committed leaf
    assert _check(res, "revealed_integrity") is False or _check(res, "revealed_membership") is False


def test_foreign_claim_injected_into_revealed_fails():
    """A claim not in the committed set cannot be smuggled into `revealed`."""
    d = build_disclosure(_claims(), reveal_ids=["ACTION_ENTROPY_v1"])
    b = json.loads(_UC1.read_text(encoding="utf-8").splitlines()[0])
    foreign = build_claim(b, "BUTTON_PRESS_COUNT_v1")
    foreign["value"]["press_events"] = 4242                    # a fabricated, uncommitted claim
    import sdk.wmp_derived as wd
    foreign["claim_hash"] = wd._claim_hash(foreign)
    d["revealed"].append(foreign)
    res = verify_disclosure(d)
    assert res["ok"] is False
    assert _check(res, "revealed_membership") is False


# ── build-time guards ───────────────────────────────────────────────────────

def test_cross_bundle_claims_refused():
    claims = _claims()
    claims[1] = copy.deepcopy(claims[1])
    claims[1]["parent_bundle_hash"] = "f" * 64                 # a different bundle
    with pytest.raises(ValueError, match="same parent bundle"):
        build_disclosure(claims)


def test_empty_refused():
    with pytest.raises(ValueError, match="no claims"):
        build_disclosure([])
