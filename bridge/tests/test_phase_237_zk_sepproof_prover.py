"""Phase 237-ZK-SEPPROOF — Bridge prover (Step C) tests.

Tests cover the mock-mode prover end-to-end (real mode requires the trusted
setup ceremony, deferred until wallet refill).  Mock mode is the operational
default until artifacts arrive in bridge/zk_artifacts/, so all tests focus
on it.

T-237-SEP-PR-1..10.
"""
from __future__ import annotations

import sys
import types as _types
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
BRIDGE_DIR = Path(__file__).parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(BRIDGE_DIR) not in sys.path:
    sys.path.insert(0, str(BRIDGE_DIR))

# Stub heavy-import modules
for _mod in ["web3", "web3.exceptions", "eth_account", "anthropic"]:
    if _mod not in sys.modules:
        sys.modules[_mod] = _types.ModuleType(_mod)
if "dotenv" not in sys.modules:
    _dotenv = _types.ModuleType("dotenv")
    _dotenv.load_dotenv = lambda *a, **kw: None  # type: ignore[attr-defined]
    sys.modules["dotenv"] = _dotenv

from vapi_bridge.zk_sepproof_prover import (  # noqa: E402
    ZKSepProofProver,
    SepProofResult,
    PROOF_SIZE,
    N_PLAYERS,
    FEATURE_DIM,
    WITNESS_SCALE,
)


# ── Canonical inputs (Phase 229 AIT-shaped) ─────────────────────────────────

CANONICAL_WITNESS = [9.37, 0.85, 0.52, 0.71]   # P1 tremor + gravity angles
CANONICAL_CLAIMED_PID = 1
CANONICAL_CENTROIDS = {
    0: [9.37, 0.85, 0.52, 0.71],
    1: [1.71, 0.92, 0.39, 0.67],
    2: [3.85, 0.78, 0.61, 0.82],
}
CANONICAL_COV_INV = [
    [ 0.045, -0.012,  0.003,  0.001],
    [-0.012,  2.310, -0.085,  0.122],
    [ 0.003, -0.085,  3.040, -0.218],
    [ 0.001,  0.122, -0.218,  2.760],
]
CANONICAL_SNAPSHOT = bytes.fromhex(
    "deadbeefdeadbeefdeadbeefdeadbeefcafebabecafebabecafebabecafebabe"
)


# ─────────────────────────────────────────────────────────────────────────────
# T-237-SEP-PR-1: prover defaults to mock mode (no ceremony artifacts)
# ─────────────────────────────────────────────────────────────────────────────

def test_t_237_sep_pr_1_default_mock_mode():
    """Without ceremony artifacts, ZKSEP_ARTIFACTS_AVAILABLE is False —
    prover automatically uses mock mode. No error, no warning that fails
    the test."""
    prover = ZKSepProofProver()
    # The prover's _available flag mirrors module-level ZKSEP_ARTIFACTS_AVAILABLE
    # which is False in the test environment (no .zkey).
    assert prover._available is False, (
        "test environment must not have ZK ceremony artifacts present"
    )


# ─────────────────────────────────────────────────────────────────────────────
# T-237-SEP-PR-2: generate_proof returns SepProofResult with is_mock=True
# ─────────────────────────────────────────────────────────────────────────────

def test_t_237_sep_pr_2_mock_proof_basic_shape():
    prover = ZKSepProofProver()
    result = prover.generate_proof(
        witness_vector=CANONICAL_WITNESS,
        claimed_player_id=CANONICAL_CLAIMED_PID,
        centroids_by_player=CANONICAL_CENTROIDS,
        cov_inv=CANONICAL_COV_INV,
        biometric_snapshot_hash=CANONICAL_SNAPSHOT,
    )
    assert isinstance(result, SepProofResult)
    assert result.is_mock is True
    assert result.error is None
    assert len(result.proof_bytes) == PROOF_SIZE
    assert result.claimed_player_id == 1
    assert result.separation_threshold_milli == 1000  # default
    assert result.inference_code == 0  # default


# ─────────────────────────────────────────────────────────────────────────────
# T-237-SEP-PR-3: snapshot hash splits into (lo, hi) 128-bit halves
# ─────────────────────────────────────────────────────────────────────────────

def test_t_237_sep_pr_3_snapshot_hash_split():
    """The 32-byte snapshot hash must split into low/high 128-bit halves
    matching the circuit's public input split.  Reconstruction:
        hash_full = (hi << 128) | lo
    """
    prover = ZKSepProofProver()
    result = prover.generate_proof(
        witness_vector=CANONICAL_WITNESS,
        claimed_player_id=CANONICAL_CLAIMED_PID,
        centroids_by_player=CANONICAL_CENTROIDS,
        cov_inv=CANONICAL_COV_INV,
        biometric_snapshot_hash=CANONICAL_SNAPSHOT,
    )
    expected_int = int.from_bytes(CANONICAL_SNAPSHOT, "big")
    expected_hi = (expected_int >> 128) & ((1 << 128) - 1)
    expected_lo = expected_int & ((1 << 128) - 1)
    assert result.biometric_snapshot_hash_hi == expected_hi
    assert result.biometric_snapshot_hash_lo == expected_lo
    # Reconstructed full hash matches input
    reconstructed = (
        result.biometric_snapshot_hash_hi << 128
    ) | result.biometric_snapshot_hash_lo
    assert reconstructed == expected_int


# ─────────────────────────────────────────────────────────────────────────────
# T-237-SEP-PR-4: deterministic — same inputs produce same proof
# ─────────────────────────────────────────────────────────────────────────────

def test_t_237_sep_pr_4_mock_deterministic():
    """Mock proofs are structural SHA-256 over scaled inputs — must be
    deterministic across calls. Real mode is also deterministic (snarkjs
    Groth16 is deterministic given same private inputs + ceremony randomness)."""
    prover = ZKSepProofProver()
    r1 = prover.generate_proof(
        witness_vector=CANONICAL_WITNESS,
        claimed_player_id=CANONICAL_CLAIMED_PID,
        centroids_by_player=CANONICAL_CENTROIDS,
        cov_inv=CANONICAL_COV_INV,
        biometric_snapshot_hash=CANONICAL_SNAPSHOT,
    )
    r2 = prover.generate_proof(
        witness_vector=CANONICAL_WITNESS,
        claimed_player_id=CANONICAL_CLAIMED_PID,
        centroids_by_player=CANONICAL_CENTROIDS,
        cov_inv=CANONICAL_COV_INV,
        biometric_snapshot_hash=CANONICAL_SNAPSHOT,
    )
    assert r1.proof_bytes == r2.proof_bytes
    assert r1.feature_commitment == r2.feature_commitment


# ─────────────────────────────────────────────────────────────────────────────
# T-237-SEP-PR-5: changing claimed_player_id changes feature_commitment
# (W1 attack closure verification)
# ─────────────────────────────────────────────────────────────────────────────

def test_t_237_sep_pr_5_pid_change_invalidates_commitment():
    """Phase 237-ZK-SEPPROOF W1 attack: prover can claim any player_id with
    same vector. Closure: feature_commitment binds (witness, claimed_id),
    so changing pid produces different commitment. This test verifies the
    binding holds in mock mode (real mode binds via Poseidon)."""
    prover = ZKSepProofProver()
    r0 = prover.generate_proof(
        witness_vector=CANONICAL_WITNESS, claimed_player_id=0,
        centroids_by_player=CANONICAL_CENTROIDS, cov_inv=CANONICAL_COV_INV,
        biometric_snapshot_hash=CANONICAL_SNAPSHOT,
    )
    r1 = prover.generate_proof(
        witness_vector=CANONICAL_WITNESS, claimed_player_id=1,
        centroids_by_player=CANONICAL_CENTROIDS, cov_inv=CANONICAL_COV_INV,
        biometric_snapshot_hash=CANONICAL_SNAPSHOT,
    )
    assert r0.feature_commitment != r1.feature_commitment, (
        "claimed_player_id must bind into feature_commitment — "
        "W1 attack closure broken"
    )


# ─────────────────────────────────────────────────────────────────────────────
# T-237-SEP-PR-6: input validation — bad witness length
# ─────────────────────────────────────────────────────────────────────────────

def test_t_237_sep_pr_6_invalid_witness_length():
    prover = ZKSepProofProver()
    result = prover.generate_proof(
        witness_vector=[1.0, 2.0, 3.0],   # only 3 features (need 4)
        claimed_player_id=1,
        centroids_by_player=CANONICAL_CENTROIDS, cov_inv=CANONICAL_COV_INV,
        biometric_snapshot_hash=CANONICAL_SNAPSHOT,
    )
    assert result.error is not None
    assert "witness_vector" in result.error
    assert result.proof_bytes == bytes(PROOF_SIZE)  # zeros on error


# ─────────────────────────────────────────────────────────────────────────────
# T-237-SEP-PR-7: input validation — out-of-range claimed_player_id
# ─────────────────────────────────────────────────────────────────────────────

def test_t_237_sep_pr_7_invalid_claimed_pid():
    prover = ZKSepProofProver()
    result = prover.generate_proof(
        witness_vector=CANONICAL_WITNESS, claimed_player_id=42,
        centroids_by_player=CANONICAL_CENTROIDS, cov_inv=CANONICAL_COV_INV,
        biometric_snapshot_hash=CANONICAL_SNAPSHOT,
    )
    assert result.error is not None
    assert "claimed_player_id" in result.error


# ─────────────────────────────────────────────────────────────────────────────
# T-237-SEP-PR-8: input validation — bad snapshot hash length
# ─────────────────────────────────────────────────────────────────────────────

def test_t_237_sep_pr_8_invalid_snapshot_hash_length():
    prover = ZKSepProofProver()
    result = prover.generate_proof(
        witness_vector=CANONICAL_WITNESS, claimed_player_id=1,
        centroids_by_player=CANONICAL_CENTROIDS, cov_inv=CANONICAL_COV_INV,
        biometric_snapshot_hash=b"too_short",   # wrong length
    )
    assert result.error is not None
    assert "32 bytes" in result.error


# ─────────────────────────────────────────────────────────────────────────────
# T-237-SEP-PR-9: separation threshold + inference code parameterization
# ─────────────────────────────────────────────────────────────────────────────

def test_t_237_sep_pr_9_threshold_and_inference_propagate():
    """Custom separation_threshold_milli and inference_code propagate
    through to the result (and into the encoded proof bytes — circuit
    consumes them as public inputs)."""
    prover = ZKSepProofProver()
    result = prover.generate_proof(
        witness_vector=CANONICAL_WITNESS, claimed_player_id=1,
        centroids_by_player=CANONICAL_CENTROIDS, cov_inv=CANONICAL_COV_INV,
        biometric_snapshot_hash=CANONICAL_SNAPSHOT,
        separation_threshold_milli=1500,   # ratio ≥ 1.5
        inference_code=0x20,                # NOMINAL
    )
    assert result.error is None
    assert result.separation_threshold_milli == 1500
    assert result.inference_code == 0x20


# ─────────────────────────────────────────────────────────────────────────────
# T-237-SEP-PR-10: result is slots-attached dataclass (immutability invariant)
# ─────────────────────────────────────────────────────────────────────────────

def test_t_237_sep_pr_10_result_dataclass_slots():
    """SepProofResult uses @dataclass(slots=True) per Phase 184+ SDK pattern.
    Setting an unknown attribute must raise AttributeError."""
    prover = ZKSepProofProver()
    result = prover.generate_proof(
        witness_vector=CANONICAL_WITNESS, claimed_player_id=1,
        centroids_by_player=CANONICAL_CENTROIDS, cov_inv=CANONICAL_COV_INV,
        biometric_snapshot_hash=CANONICAL_SNAPSHOT,
    )
    with pytest.raises(AttributeError):
        result.injected_field = "should_fail"  # type: ignore[attr-defined]
