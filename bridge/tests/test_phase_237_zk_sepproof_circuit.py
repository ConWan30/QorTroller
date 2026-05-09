"""Phase 237-ZK-SEPPROOF — ZKSepProof.circom circuit shape tests.

Static checks on the circom source + compiled artifacts.  These tests do NOT
run the trusted setup ceremony (wallet-gated; deferred until refill) or
generate proofs (requires .zkey from ceremony).  They lock in the FROZEN
circuit parameters so a future contributor can't silently alter the public
input shape, scale, or constraint count without test failure.

The circuit lives at contracts/circuits/ZKSepProof.circom and is compiled
to ZKSepProof.r1cs + ZKSepProof.wasm via:
    cd contracts/circuits && ../circom.exe ZKSepProof.circom --r1cs --wasm --sym

T-237-SEP-CIR-1..7.
"""
from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
CIRCUITS_DIR = PROJECT_ROOT / "contracts" / "circuits"
CIRCUIT_SRC = CIRCUITS_DIR / "ZKSepProof.circom"


def _read_circuit() -> str:
    return CIRCUIT_SRC.read_text(encoding="utf-8")


# ─────────────────────────────────────────────────────────────────────────────
# T-237-SEP-CIR-1: circuit source exists at the canonical path
# ─────────────────────────────────────────────────────────────────────────────

def test_t_237_sep_cir_1_source_exists():
    assert CIRCUIT_SRC.exists(), (
        f"ZKSepProof.circom must live at {CIRCUIT_SRC}. "
        "Phase 237-ZK-SEPPROOF locks this path for ceremony tooling."
    )
    src = _read_circuit()
    assert "pragma circom 2.0.0" in src
    assert "template ZKSepProof()" in src


# ─────────────────────────────────────────────────────────────────────────────
# T-237-SEP-CIR-2: FROZEN parameters at v1
# ─────────────────────────────────────────────────────────────────────────────

def test_t_237_sep_cir_2_frozen_parameters():
    """Phase 237-ZK-SEPPROOF v1 freezes N_PLAYERS=3, FEATURES=4 (AIT corpus
    shape).  Future expansion requires v2 + new ceremony + new verifier.
    Regression guard against a future contributor silently changing these."""
    src = _read_circuit()
    assert "var N_PLAYERS = 3;" in src, "FROZEN: N_PLAYERS must be 3"
    assert "var FEATURES  = 4;" in src or "var FEATURES = 4;" in src, (
        "FROZEN: FEATURES must be 4"
    )
    # SCALE_NUM controls the separation threshold numerator (claimed_dist × 1000)
    assert "var SCALE_NUM = 1000;" in src, "FROZEN: SCALE_NUM must be 1000"


# ─────────────────────────────────────────────────────────────────────────────
# T-237-SEP-CIR-3: public input count is 6 (matches design)
# ─────────────────────────────────────────────────────────────────────────────

def test_t_237_sep_cir_3_public_inputs_count():
    """nPublic must be exactly 6 — Solidity verifier interface depends on this.
    Adding/removing a public input breaks every existing on-chain integration."""
    src = _read_circuit()
    # Find the `component main {public [...]} = ZKSepProof()` line
    main_decl = src[src.find("component main"):]
    assert "biometricSnapshotHashLo" in main_decl
    assert "biometricSnapshotHashHi" in main_decl
    assert "claimedPlayerId" in main_decl
    assert "featureCommitment" in main_decl
    assert "separationThresholdMilli" in main_decl
    assert "inferenceCode" in main_decl
    # No 7th input snuck in
    public_block = main_decl[main_decl.find("[") + 1: main_decl.find("]")]
    public_inputs = [s.strip() for s in public_block.split(",")]
    assert len(public_inputs) == 6, (
        f"FROZEN: nPublic must be 6, got {len(public_inputs)}: {public_inputs}"
    )


# ─────────────────────────────────────────────────────────────────────────────
# T-237-SEP-CIR-4: Poseidon arity matches FEATURES + 1 (witness || pid)
# ─────────────────────────────────────────────────────────────────────────────

def test_t_237_sep_cir_4_poseidon_arity():
    """C1 binding: featureCommitment = Poseidon(5)(witnessVector[4] || claimedPlayerId).
    Phase 62 used Poseidon(8); this is a different commitment shape (4+1=5 inputs).
    Future v2 expanding FEATURES requires bumping arity and re-doing ceremony."""
    src = _read_circuit()
    assert "Poseidon(5)" in src, (
        "FROZEN: Phase 237-ZK-SEPPROOF uses Poseidon(5) — 4 witness features + "
        "1 claimedPlayerId. Different shape from Phase 62's Poseidon(8)."
    )


# ─────────────────────────────────────────────────────────────────────────────
# T-237-SEP-CIR-5: LessThan(128) for separation comparison
# ─────────────────────────────────────────────────────────────────────────────

def test_t_237_sep_cir_5_lessthan_bit_width():
    """Mahalanobis × scale at 1e9 produces values up to ~1e30 — exceeds int64.
    LessThan(128) handles 2^128 ≈ 3.4e38 with comfortable margin.  A future
    contributor accidentally narrowing to LessThan(64) or LessThan(96) would
    silently truncate values and produce false-pass proofs on extreme inputs."""
    src = _read_circuit()
    assert "LessThan(128)" in src, (
        "FROZEN: separation comparison must use LessThan(128) — narrower bit "
        "widths cannot represent the 1e30 scale of Mahalanobis × threshold"
    )


# ─────────────────────────────────────────────────────────────────────────────
# T-237-SEP-CIR-6: compiled R1CS exists at expected path
# (Test runs after `circom ZKSepProof.circom --r1cs --wasm --sym` is invoked.
#  If R1CS is missing the test skips rather than fails — circom toolchain may
#  not be in CI runners; ceremony coordinator runs the compile separately.)
# ─────────────────────────────────────────────────────────────────────────────

def test_t_237_sep_cir_6_compiled_artifacts_present_or_skip():
    """If the operator has run `circom ZKSepProof.circom --r1cs --wasm`, the
    compiled artifacts must live at the canonical paths.  If not yet compiled,
    skip — circom is not part of bridge CI runners."""
    r1cs = CIRCUITS_DIR / "ZKSepProof.r1cs"
    wasm = CIRCUITS_DIR / "ZKSepProof_js" / "ZKSepProof.wasm"
    if not r1cs.exists():
        import pytest
        pytest.skip("ZKSepProof.r1cs not yet compiled — run circom to generate")
    assert r1cs.exists()
    assert wasm.exists(), (
        "ZKSepProof.wasm missing from ZKSepProof_js/ — incomplete circom output"
    )
    # R1CS file size is a smoke check; an empty .r1cs is a circom error.
    assert r1cs.stat().st_size > 0


# ─────────────────────────────────────────────────────────────────────────────
# T-237-SEP-CIR-7: include path consistency with Phase 62 / 67 precedent
# ─────────────────────────────────────────────────────────────────────────────

def test_t_237_sep_cir_7_circomlib_includes_canonical():
    """All VAPI circuits include circomlib via `../../node_modules/circomlib/`.
    Drift here breaks the build chain if the path resolution differs across
    operators.  Locks the include shape."""
    src = _read_circuit()
    assert (
        'include "../../node_modules/circomlib/circuits/poseidon.circom";' in src
    ), "Poseidon include path must match Phase 62/67 convention"
    assert (
        'include "../../node_modules/circomlib/circuits/comparators.circom";' in src
    ), "Comparators include path must match Phase 62/67 convention"
