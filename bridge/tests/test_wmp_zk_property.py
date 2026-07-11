"""WMP ZK Property Proof (ZKP-1) — scaffold + honest-deferral tests.

The load-bearing honesty: with no ceremony, a property-proof is DEFERRED — never
reported as proven OR failed. The request carries the statement (claim + field +
predicate + public threshold) but NEVER the secret value. A mock prover/verifier
exercises the PROVEN/REJECTED flip structurally (NOT real zero-knowledge).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

import pytest

from sdk.wmp_derived import build_claim, DERIVATIONS
from sdk.wmp_zk_property import (build_property_request, build_property_proof,
                                 verify_property_proof, DeferredProver, PREDICATES,
                                 OUTCOME_PROVEN, OUTCOME_DEFERRED, OUTCOME_REJECTED)

_UC1 = REPO_ROOT / "wmp_corpus_real" / "wmp_corpus.jsonl"


def _claim(deriv="TRIGGER_ENGAGEMENT_FRACTION_v1") -> dict:
    b = json.loads(_UC1.read_text(encoding="utf-8").splitlines()[0])
    return build_claim(b, deriv)


class _MockProver:
    """STRUCTURAL ONLY — returns fake bytes to exercise the non-deferred path.
    NOT a real zero-knowledge prover."""
    reason = "mock"

    def prove(self, request, claim):
        return "deadbeef"


# ── request: statement without the secret value ────────────────────────────

def test_request_does_not_leak_value():
    claim = _claim()
    req = build_property_request(claim, "fraction", "GTE", 0.05)
    assert req["predicate"] == "GTE" and req["threshold"] == 0.05
    assert req["claim_hash"] == claim["claim_hash"]
    # the secret value (0.1) must NOT appear anywhere in the public request
    assert "0.1" not in json.dumps(req)
    assert "fraction" == req["field_path"]


def test_request_rejects_unknown_predicate():
    with pytest.raises(ValueError, match="predicate"):
        build_property_request(_claim(), "fraction", "NEQ", 0.05)


def test_request_rejects_missing_field():
    with pytest.raises(KeyError):
        build_property_request(_claim(), "no_such_field", "GTE", 1)


def test_request_rejects_non_vdc_claim():
    bad = {"schema": "not-vdc", "value": {"fraction": 0.1}}
    with pytest.raises(ValueError, match="not a VDC claim"):
        build_property_request(bad, "fraction", "GTE", 0.05)


# ── the honest deferral (no ceremony) ──────────────────────────────────────

def test_default_prover_defers_honestly():
    rec = build_property_proof(_claim(), "fraction", "GTE", 0.05)
    assert rec["deferred"] is True
    assert rec["proof_hex"] is None
    assert rec["prover"] == "DeferredProver"
    assert rec["deferred_reason"]


def test_deferred_record_verifies_as_DEFERRED_not_pass_or_fail():
    """A deferral must NEVER read as PROVEN or REJECTED."""
    rec = build_property_proof(_claim(), "fraction", "GTE", 0.05)
    res = verify_property_proof(rec)
    assert res["outcome"] == OUTCOME_DEFERRED
    assert res["outcome"] not in (OUTCOME_PROVEN, OUTCOME_REJECTED)


def test_proof_present_but_no_verifier_is_DEFERRED():
    rec = build_property_proof(_claim(), "fraction", "GTE", 0.05, prover=_MockProver())
    assert rec["deferred"] is False and rec["proof_hex"] == "deadbeef"
    res = verify_property_proof(rec, zk_verify=None)
    assert res["outcome"] == OUTCOME_DEFERRED       # can't confirm without the ceremony verifier


# ── structural flip via mock verifier (NOT real ZK) ────────────────────────

def test_mock_verifier_true_is_PROVEN():
    rec = build_property_proof(_claim(), "fraction", "GTE", 0.05, prover=_MockProver())
    res = verify_property_proof(rec, zk_verify=lambda req, p: True)
    assert res["outcome"] == OUTCOME_PROVEN


def test_mock_verifier_false_is_REJECTED():
    rec = build_property_proof(_claim(), "fraction", "GTE", 0.05, prover=_MockProver())
    res = verify_property_proof(rec, zk_verify=lambda req, p: False)
    assert res["outcome"] == OUTCOME_REJECTED


def test_verifier_exception_is_REJECTED_not_silent_pass():
    rec = build_property_proof(_claim(), "fraction", "GTE", 0.05, prover=_MockProver())

    def _boom(req, p):
        raise RuntimeError("verifier down")

    res = verify_property_proof(rec, zk_verify=_boom)
    assert res["outcome"] == OUTCOME_REJECTED


def test_wrong_schema_rejected():
    res = verify_property_proof({"schema": "nope", "request": {}}, zk_verify=lambda r, p: True)
    assert res["outcome"] == OUTCOME_REJECTED


def test_predicates_frozen():
    assert PREDICATES == ("GTE", "LTE", "EQ")
