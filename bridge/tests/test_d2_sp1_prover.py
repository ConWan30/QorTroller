"""Phase B ④ / D2 Phase 14b step 1a — SP1 ZK-SEPPROOF prover (mock) tests.

Code-GREEN evidence for the 14a seamlessness gate: a SECOND proving backend
(SP1) coexists alongside the Groth16 ZKSepProofProver WITHOUT modifying it,
mock-mode by default, CI-green. Mirrors test_phase_237_zk_sepproof_prover.py and
adds COEXISTENCE + APPLES-TO-APPLES + DISTINCT-FORMAT assertions.

T-D2-SP1-1..13.
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

# Stub heavy-import modules (same pattern as the Groth16 prover test)
for _mod in ["web3", "web3.exceptions", "eth_account", "anthropic"]:
    if _mod not in sys.modules:
        sys.modules[_mod] = _types.ModuleType(_mod)
if "dotenv" not in sys.modules:
    _dotenv = _types.ModuleType("dotenv")
    _dotenv.load_dotenv = lambda *a, **kw: None  # type: ignore[attr-defined]
    sys.modules["dotenv"] = _dotenv

from vapi_bridge.zk_sp1_prover import (  # noqa: E402
    SP1SepProofProver,
    SP1SepProofResult,
    SP1_MOCK_PROOF_SIZE,
    SP1_TARGET_VERSION,
)
from vapi_bridge.zk_sepproof_prover import (  # noqa: E402
    ZKSepProofProver,
    SepProofResult,
    PROOF_SIZE as GROTH16_PROOF_SIZE,
)


# ── Canonical inputs (Phase 229 AIT-shaped — identical to the Groth16 test) ──

CANONICAL_WITNESS = [9.37, 0.85, 0.52, 0.71]
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


def _gen(prover, **over):
    kw = dict(
        witness_vector=CANONICAL_WITNESS,
        claimed_player_id=CANONICAL_CLAIMED_PID,
        centroids_by_player=CANONICAL_CENTROIDS,
        cov_inv=CANONICAL_COV_INV,
        biometric_snapshot_hash=CANONICAL_SNAPSHOT,
    )
    kw.update(over)
    return prover.generate_proof(**kw)


# T-D2-SP1-1: defaults to mock mode (no SP1 toolchain/artifacts)
def test_t_d2_sp1_1_default_mock_mode():
    prover = SP1SepProofProver()
    assert prover._available is False, (
        "test environment must not have SP1 guest ELF + proving key + toolchain"
    )
    assert SP1_TARGET_VERSION == "v6"  # v5 deprecated 2026-05-19


# T-D2-SP1-2: generate_proof returns SP1SepProofResult, is_mock True, backend tag
def test_t_d2_sp1_2_mock_proof_basic_shape():
    result = _gen(SP1SepProofProver())
    assert isinstance(result, SP1SepProofResult)
    assert result.is_mock is True
    assert result.error is None
    assert result.prover_backend == "sp1"
    assert len(result.proof_bytes) == SP1_MOCK_PROOF_SIZE
    assert result.claimed_player_id == 1
    assert result.separation_threshold_milli == 1000
    assert result.inference_code == 0


# T-D2-SP1-3: snapshot hash splits into (lo, hi) 128-bit halves; reconstructs
def test_t_d2_sp1_3_snapshot_hash_split():
    result = _gen(SP1SepProofProver())
    expected_int = int.from_bytes(CANONICAL_SNAPSHOT, "big")
    assert result.biometric_snapshot_hash_hi == (expected_int >> 128) & ((1 << 128) - 1)
    assert result.biometric_snapshot_hash_lo == expected_int & ((1 << 128) - 1)
    reconstructed = (result.biometric_snapshot_hash_hi << 128) | result.biometric_snapshot_hash_lo
    assert reconstructed == expected_int


# T-D2-SP1-4: deterministic
def test_t_d2_sp1_4_mock_deterministic():
    p = SP1SepProofProver()
    r1, r2 = _gen(p), _gen(p)
    assert r1.proof_bytes == r2.proof_bytes
    assert r1.feature_commitment == r2.feature_commitment


# T-D2-SP1-5: claimed_player_id binds into feature_commitment (W1 closure carries)
def test_t_d2_sp1_5_pid_binds_commitment():
    p = SP1SepProofProver()
    r0 = _gen(p, claimed_player_id=0)
    r1 = _gen(p, claimed_player_id=1)
    assert r0.feature_commitment != r1.feature_commitment


# T-D2-SP1-6: invalid witness length → error result (never raises)
def test_t_d2_sp1_6_invalid_witness_length():
    result = _gen(SP1SepProofProver(), witness_vector=[1.0, 2.0, 3.0])
    assert result.error is not None
    assert "witness_vector" in result.error
    assert result.proof_bytes == bytes(SP1_MOCK_PROOF_SIZE)


# T-D2-SP1-7: out-of-range claimed_player_id → error
def test_t_d2_sp1_7_invalid_claimed_pid():
    result = _gen(SP1SepProofProver(), claimed_player_id=42)
    assert result.error is not None
    assert "claimed_player_id" in result.error


# T-D2-SP1-8: bad snapshot hash length → error
def test_t_d2_sp1_8_invalid_snapshot_hash_length():
    result = _gen(SP1SepProofProver(), biometric_snapshot_hash=b"too_short")
    assert result.error is not None
    assert "32 bytes" in result.error


# T-D2-SP1-9: threshold + inference code propagate
def test_t_d2_sp1_9_threshold_and_inference_propagate():
    result = _gen(SP1SepProofProver(), separation_threshold_milli=1500, inference_code=0x20)
    assert result.error is None
    assert result.separation_threshold_milli == 1500
    assert result.inference_code == 0x20


# T-D2-SP1-10: result dataclass is slots-attached (immutability invariant)
def test_t_d2_sp1_10_result_dataclass_slots():
    result = _gen(SP1SepProofProver())
    with pytest.raises(AttributeError):
        result.injected_field = "should_fail"  # type: ignore[attr-defined]


# T-D2-SP1-11: COEXISTENCE — SP1 prover does not alter ZKSepProofProver behavior
def test_t_d2_sp1_11_coexistence_with_groth16_prover():
    """Both backends instantiate + run in the same process, independently, both
    in mock mode. This is the 14a 'additive, does not modify the existing prover'
    claim as code-GREEN evidence."""
    sp1 = SP1SepProofProver()
    groth16 = ZKSepProofProver()
    sp1_r = _gen(sp1)
    g_r = groth16.generate_proof(
        witness_vector=CANONICAL_WITNESS, claimed_player_id=CANONICAL_CLAIMED_PID,
        centroids_by_player=CANONICAL_CENTROIDS, cov_inv=CANONICAL_COV_INV,
        biometric_snapshot_hash=CANONICAL_SNAPSHOT,
    )
    assert sp1_r.is_mock is True and sp1_r.error is None
    assert g_r.is_mock is True and g_r.error is None
    assert isinstance(sp1_r, SP1SepProofResult)
    assert isinstance(g_r, SepProofResult)
    assert sp1_r.prover_backend == "sp1"


# T-D2-SP1-12: APPLES-TO-APPLES — mock commitments match across backends
def test_t_d2_sp1_12_apples_to_apples_commitment_parity():
    """In MOCK mode both backends compute SHA-256 over the identical scaled-body,
    so feature_commitment matches exactly — confirming the comparison harness is
    valid. (In REAL mode they would differ by design: Groth16 Poseidon vs SP1
    SHA-256-native — the benchmark D2 step 2 measures.)"""
    sp1_r = _gen(SP1SepProofProver())
    g_r = ZKSepProofProver().generate_proof(
        witness_vector=CANONICAL_WITNESS, claimed_player_id=CANONICAL_CLAIMED_PID,
        centroids_by_player=CANONICAL_CENTROIDS, cov_inv=CANONICAL_COV_INV,
        biometric_snapshot_hash=CANONICAL_SNAPSHOT,
    )
    assert sp1_r.feature_commitment == g_r.feature_commitment


# T-D2-SP1-13: DISTINCT FORMAT — SP1 proof size != Groth16 256-byte wire format
def test_t_d2_sp1_13_distinct_proof_format():
    """An SP1 proof is a NEW format ALONGSIDE the frozen 256-byte Groth16 one,
    never a modification. Distinct size makes this unambiguous."""
    assert SP1_MOCK_PROOF_SIZE != GROTH16_PROOF_SIZE
    assert GROTH16_PROOF_SIZE == 256
    result = _gen(SP1SepProofProver())
    assert len(result.proof_bytes) == SP1_MOCK_PROOF_SIZE
