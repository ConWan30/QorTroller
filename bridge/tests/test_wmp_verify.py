"""WMP-3 consumer verifier tests.

T-WMP3-1   valid fixture bundle VERIFIED (allow_synthetic=True)
T-WMP3-2   fixture bundle REJECTED when allow_synthetic=False
T-WMP3-3   tampered scope_disclosure REJECTED (channel != ACTION_ONLY)
T-WMP3-4   missing observation_channel disclosure REJECTED
T-WMP3-5   scope_is_full_pomdp_tuple=True REJECTED (overclaim)
T-WMP3-6   matrix-swap attack: changed action_trace_matrix_hex flips
           the structural rehash; verifier surfaces it (digest changes)
T-WMP3-7   empty Arc 6 registry → DEFERRED with reason
           BEACON_REGISTRY_NOT_DEPLOYED, overall still VERIFIED
T-WMP3-8   v1 consent dimension DEFERRED → CONSENT_GATE_DEFERRED
T-WMP3-9   bad recency: close_block <= open_block REJECTED
T-WMP3-10  unknown schema REJECTED
"""

import json
import os
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "bridge"))
sys.path.insert(0, str(REPO_ROOT / "sdk"))

from vapi_bridge.wmp import BundleAssembler  # noqa: E402
from vapi_bridge.replay_proof_pipeline.pre_processor import SanitizedReplayMatrix  # noqa: E402
from wmp_verify import (  # noqa: E402
    verify_bundle,
    OUTCOME_VERIFIED,
    OUTCOME_REJECTED,
    CHECK_SCOPE,
    CHECK_REHASH,
    CHECK_HUMANITY,
    CHECK_RECENCY,
    CHECK_CONSENT,
)


def _matrix(ticks=4):
    return SanitizedReplayMatrix(
        session_id="sid", ticks=ticks,
        stick_L_sector=bytes(ticks), stick_R_sector=bytes(ticks),
        trigger_L_state=bytes(ticks), trigger_R_state=bytes(ticks),
        button_mask=bytes(ticks * 2), imu_gravity_sector=bytes(ticks),
        poac_chain_root=bytes(32), vhp_token_id=2,
        humanity_prob_floor=0.71, session_verdict="HUMAN",
    )


def _hp():
    return {
        "proof_type":          "VAPI-REPLAY-PROOF-v1",
        # 256-byte snarkjs Groth16 proof → 512 hex chars, clean hex.
        "proof_bytes_hex":     "0x" + "ab" * 256,
        "public_inputs":       {"sanitizedTraceRoot": "143000"},
        "verifier_address":    "0x5182372d1D033db0c9230843DFDE606733D5F91B",
        "sanitized_trace_root": "143000",
    }


def _rec(registry=""):
    return {
        "open_block": 1, "open_block_hash": "0x" + "11" * 32,
        "close_block": 2, "close_block_hash": "0x" + "22" * 32,
        "registry_address": registry,
    }


def _cons():
    return {
        "registry_address": "0x5F7c8068D0e61818FCD613D47e68a9Ea906a2743",
        "gamer_address":    "0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692",
        "manifest_hash":    "0x" + "ab" * 32,
    }


def _bundle(synthetic=True, **overrides):
    asm = BundleAssembler(); asm.__post_init__()
    b = asm.assemble(
        sanitized_matrix=_matrix(),
        humanity_proof=_hp(),
        recency=_rec(),
        consent=_cons(),
        synthetic=synthetic,
    )
    d = b.to_dict()
    d.update(overrides)
    return d


def test_wmp3_1_valid_fixture_verified():
    r = verify_bundle(_bundle(), allow_synthetic=True)
    assert r.overall == OUTCOME_VERIFIED, r.reasons


def test_wmp3_2_synthetic_rejected_without_allow():
    r = verify_bundle(_bundle(synthetic=True), allow_synthetic=False)
    assert r.overall == OUTCOME_REJECTED
    assert any("scope_synthetic" in s for s in r.reasons)


def test_wmp3_3_tampered_scope_channel_rejected():
    d = _bundle()
    d["scope_channel"] = "ACTION_AND_OBSERVATION"  # an overclaim
    r = verify_bundle(d, allow_synthetic=True)
    assert r.overall == OUTCOME_REJECTED
    assert not r.checks[CHECK_SCOPE]["passed"]


def test_wmp3_4_missing_observation_disclosure_rejected():
    d = _bundle()
    d["scope_observation_channel"] = "AVAILABLE_OUT_OF_BAND"  # tampered
    r = verify_bundle(d, allow_synthetic=True)
    assert r.overall == OUTCOME_REJECTED
    assert not r.checks[CHECK_SCOPE]["passed"]


def test_wmp3_5_is_full_pomdp_tuple_overclaim_rejected():
    d = _bundle()
    d["scope_is_full_pomdp_tuple"] = True  # the prohibited overclaim
    r = verify_bundle(d, allow_synthetic=True)
    assert r.overall == OUTCOME_REJECTED


def test_wmp3_6_matrix_swap_changes_structural_rehash():
    """The structural rehash CATCHES matrix-swap attacks: a different
    matrix produces a different digest. This is the v1 implementation
    of the §5.4 canonical-home check (Phase-2 promotes the digest
    algorithm to Poseidon-over-BN254)."""
    d_a = _bundle()
    d_b = _bundle()
    # Swap the matrix bytes on bundle B — flip a single byte in the
    # button_mask channel:
    d_b["action_trace_matrix_hex"]["button_mask"] = "ff" + d_b["action_trace_matrix_hex"]["button_mask"][2:]
    r_a = verify_bundle(d_a, allow_synthetic=True)
    r_b = verify_bundle(d_b, allow_synthetic=True)
    # Different structural rehash digests — the canonical home detects
    # the swap independently of the Groth16 proof.
    assert r_a.checks[CHECK_REHASH]["actual"] != r_b.checks[CHECK_REHASH]["actual"]


def test_wmp3_7_empty_arc6_registry_deferred_honest():
    d = _bundle()
    d["recency_registry_address"] = ""  # Arc 6 dormant in this fixture
    r = verify_bundle(d, allow_synthetic=True)
    assert r.overall == OUTCOME_VERIFIED  # deferral is NOT a failure
    assert CHECK_RECENCY in r.deferred
    assert r.checks[CHECK_RECENCY]["deferred_reason"] == "BEACON_REGISTRY_NOT_DEPLOYED"


def test_wmp3_8_consent_v1_deferred():
    """W1-D v1 behavior: world-model consent dimension is DEFERRED. The
    verifier surfaces that as honest deferral, not a failure."""
    r = verify_bundle(_bundle(), allow_synthetic=True)
    assert CHECK_CONSENT in r.deferred
    assert r.checks[CHECK_CONSENT]["deferred_reason"] == "CONSENT_GATE_DEFERRED"


def test_wmp3_9_bad_recency_temporal_order_rejected():
    d = _bundle()
    d["recency_registry_address"] = "0x962440312a995b21d4E203bE6d93021CC22bA051"
    d["recency_open_block"] = 100
    d["recency_close_block"] = 99  # close < open — temporal-order violation
    r = verify_bundle(d, allow_synthetic=True)
    assert r.overall == OUTCOME_REJECTED
    assert any("temporal ordering" in s for s in r.reasons)


def test_wmp3_10_unknown_schema_rejected():
    d = _bundle()
    d["schema"] = "vapi-wmp-provenance-bundle-v999-attacker-spoof"
    r = verify_bundle(d, allow_synthetic=True)
    assert r.overall == OUTCOME_REJECTED
    assert any("schema" in s for s in r.reasons)
