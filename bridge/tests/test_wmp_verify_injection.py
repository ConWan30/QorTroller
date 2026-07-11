"""WMP Phase-2 verifier-injection tests (INC-1).

Pins the promoted paths WITHOUT touching the v1 suite: each injected callable's pass / fail /
exception behavior, the deferred paths' immunity to injection, and the all-None default's
byte-identical stub markers. Pure — fake callables only, no snarkjs, no network.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from sdk.wmp_verify import (check_consent, check_humanity, check_matrix_root_rehash,
                            check_recency, verify_bundle)

_ROOT = "2001282384424057750069554473104889511003144158405398629700461784410503414425"


def _bundle(**over):
    b = {
        "schema": "vapi-wmp-provenance-bundle-v1",
        "scope_channel": "ACTION_ONLY",
        "scope_observation_channel": "ABSENT_BY_DESIGN_DATA_FLOOR",
        "scope_fidelity": "MACRO_INTENT_POST_PHI_NOT_BIOMECHANICAL",
        "scope_synthetic": True,
        "scope_is_full_pomdp_tuple": False,
        "action_trace_ticks": 4,
        "action_trace_channels": ["stick_L_sector", "stick_R_sector"],
        "action_trace_matrix_hex": {"stick_L_sector": "00000000", "stick_R_sector": "01010101"},
        "sanitized_trace_root_ref": _ROOT,
        "humanity_proof_bytes_hex": "ab" * 256,
        "humanity_proof_public_inputs": {"sanitizedTraceRoot": _ROOT, "replayProofToken": "1",
                                         "poacChainRoot": "2", "consentPolicyHash": "0",
                                         "humanityThreshold": "700", "vhpCommitment": "3"},
        "humanity_deferred": False,
        "recency_registry_address": "0x" + "96" * 20,
        "recency_open_block": 100, "recency_close_block": 164,
        "recency_open_block_hash": "0x" + "aa" * 32,
        "recency_close_block_hash": "0x" + "bb" * 32,
        "world_model_consent_dimension": "GRANTED",
        "consent_gamer_address": "0x" + "0c" * 20,
    }
    b.update(over)
    return b


# ── rehash (poseidon_root) ─────────────────────────────────────────────────
def test_rehash_promoted_pass_and_algorithm():
    r = check_matrix_root_rehash(_bundle(), poseidon_root=lambda m: _ROOT)
    assert r["passed"] and r["algorithm"] == "POSEIDON_BN254" and r["stubbed"] is False


def test_rehash_promoted_mismatch_fails():
    r = check_matrix_root_rehash(_bundle(), poseidon_root=lambda m: "999")
    assert not r["passed"] and "mismatch" in r["issues"][0]


def test_rehash_callable_exception_is_fail_never_silent():
    def _boom(m):
        raise RuntimeError("helper died")
    r = check_matrix_root_rehash(_bundle(), poseidon_root=_boom)
    assert not r["passed"] and "failed" in r["issues"][0]


# ── humanity (groth16_verify) ──────────────────────────────────────────────
def test_humanity_promoted_pass_fail_and_unstubbed():
    ok = check_humanity(_bundle(), groth16_verify=lambda pub, hexs: True)
    bad = check_humanity(_bundle(), groth16_verify=lambda pub, hexs: False)
    assert ok["passed"] and ok["stubbed"] is False
    assert not bad["passed"] and "did NOT verify" in bad["issues"][0]


def test_humanity_deferred_ignores_injection():
    b = _bundle(humanity_deferred=True, humanity_deferred_reason="vhr_proof_deferred")
    r = check_humanity(b, groth16_verify=lambda pub, hexs: False)   # would fail if consulted
    assert r["passed"] and r["deferred"] and r["stubbed"]           # honest deferral wins


# ── recency (beacon_lookup) ────────────────────────────────────────────────
def test_recency_promoted_match_and_mismatch():
    hashes = {100: "0x" + "aa" * 32, 164: "0x" + "bb" * 32}
    ok = check_recency(_bundle(), beacon_lookup=lambda blk: hashes.get(blk))
    assert ok["passed"] and ok["stubbed"] is False
    bad = check_recency(_bundle(), beacon_lookup=lambda blk: "0x" + "ff" * 32)
    assert not bad["passed"] and any("mismatch" in i for i in bad["issues"])


def test_recency_no_anchor_fails_and_empty_registry_still_deferred():
    r = check_recency(_bundle(), beacon_lookup=lambda blk: None)
    assert not r["passed"] and any("no beacon anchored" in i for i in r["issues"])
    d = check_recency(_bundle(recency_registry_address=""), beacon_lookup=lambda blk: "0x00")
    assert d["passed"] and d["deferred"]                            # dormant-registry honesty wins


# ── consent (consent_lookup) ───────────────────────────────────────────────
def test_consent_promoted_grant_and_refusal():
    ok = check_consent(_bundle(), consent_lookup=lambda g: True)
    assert ok["passed"] and ok["stubbed"] is False
    bad = check_consent(_bundle(), consent_lookup=lambda g: False)
    assert not bad["passed"] and "NOT granted" in bad["issues"][0]


def test_consent_deferred_dimension_ignores_injection():
    b = _bundle(world_model_consent_dimension="DEFERRED")
    r = check_consent(b, consent_lookup=lambda g: False)            # would fail if consulted
    assert r["passed"] and r["deferred"]
    assert r["deferred_reason"] == "CONSENT_GATE_DEFERRED"


# ── the default-regression pin ─────────────────────────────────────────────
def test_all_none_defaults_keep_v1_stub_markers():
    res = verify_bundle(_bundle(world_model_consent_dimension="DEFERRED"), allow_synthetic=True)
    assert res.overall == "VERIFIED"
    assert res.checks["humanity"]["stubbed"] is True                # v1 stub preserved
    assert res.checks["recency"]["stubbed"] is True
    assert "consent" in res.deferred                                # W1-D deferral preserved


def test_orchestrator_threads_all_four_callables():
    hashes = {100: "0x" + "aa" * 32, 164: "0x" + "bb" * 32}
    res = verify_bundle(_bundle(), allow_synthetic=True,
                        groth16_verify=lambda pub, hexs: True,
                        poseidon_root=lambda m: _ROOT,
                        beacon_lookup=lambda blk: hashes.get(blk),
                        consent_lookup=lambda g: True)
    assert res.overall == "VERIFIED"
    assert not any(c.get("stubbed") for c in res.checks.values())   # 5/5 zero-stub
    assert res.deferred == []
