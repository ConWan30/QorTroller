"""Phase B item ④ / D2 Phase 14b step 1a — SP1 ZK-SEPPROOF prover (mock-mode).

Dual-mode (mock / real-prewired) **SP1** prover MIRRORING `ZKSepProofProver`'s
interface for an apples-to-apples ZK-SEPPROOF comparison. PoAC-v2's ZK proving
layer = **SP1** per decision D1 (Path C) — see
`wiki/methodology/poac_v2_choice_pre_investigation.md` §10.

This module is the **code-GREEN evidence slice** for the D2 seamlessness gate:
14a (`wiki/methodology/d2_seamlessness_pre_validation.md`) found, by read-only
inspection, that the bridge is prover-additive (six coexisting prover modules)
and that SP1 plugs into the established subprocess convention. This module turns
that paper-GREEN into code-GREEN: a SECOND proving backend that coexists
*alongside* `zk_sepproof_prover.py` (Groth16) **without modifying it**, following
the same convention, default-off, CI-green.

  - **Mock mode (default here + in CI):** structural SHA-256 commitment, no SP1
    toolchain. Mirrors `ZKSepProofProver._mock_proof` so outputs are directly
    comparable. NO real cryptography.
  - **Real mode (PREWIRED, NOT active):** would shell out to the SP1 toolchain
    `cargo prove` — **target SP1 v6** (v5 was deprecated on the Succinct Prover
    Network 2026-05-19) — against a compiled SP1 guest ELF + proving key, OR
    call the Succinct Prover Network API. Activates only when SP1 artifacts +
    toolchain are present (absent here → mock). This is exactly the
    artifact-availability gating pattern `zk_sepproof_prover.py` uses for
    snarkjs.

SCOPE HONESTY (matches `d2_seamlessness_pre_validation.md`):
  - **The SP1 proof wire format is NOT frozen here.** The mock layout below is a
    PROVISIONAL structural stand-in for round-trip tests only — NOT a PATTERN-017
    frozen family, NOT a canonical wire format. No `b"VAPI-…-vN"` frozen tag is
    introduced. Freezing an SP1 proof format is downstream D2 step-2+ work, gated
    on a real guest + the D6 composite-sig gadget decision.
  - **On-chain verification (D4: app-layer STARK-verify reuse vs Groth16-wrap)
    is OUT OF SCOPE.** This module only PRODUCES + locally (structurally)
    verifies in mock mode.
  - **The 228-byte PoAC record and the 256-byte Groth16 proof format are
    UNTOUCHED** — this is a NEW format *alongside*, never a modification.

Apples-to-apples observation (a genuine finding from this slice): the Groth16
mock computes its feature_commitment via SHA-256 only because Poseidon would need
a Node.js subprocess — SHA-256 is a *stand-in* for the circuit's real Poseidon.
For SP1 the situation inverts: SP1 ships a **native SHA-256 precompile**, so a
real SP1 guest can use SHA-256 *directly* as the commitment hash (no Poseidon-vs-
SHA-256 R1CS-cost tradeoff). The mock therefore uses the identical SHA-256 body
as the Groth16 mock — so the two are byte-comparable in mock mode — while in real
mode the Groth16 (Poseidon) and SP1 (SHA-256-native) commitments would differ by
design, which is itself the benchmark-worthy distinction D2 step 2 will measure.

T-D2-SP1-1..13 (see bridge/tests/test_d2_sp1_prover.py).
"""
from __future__ import annotations

import hashlib
import logging
import os
import shutil
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Optional, Sequence

# Additive reuse — import the shared AIT shape + the validation contract from the
# Groth16 prover WITHOUT modifying it. Single source of truth for the corpus
# shape guarantees the SP1 path stays apples-to-apples with Groth16.
from .zk_sepproof_prover import (
    ZKSepProofProver,
    FEATURE_DIM,
    N_PLAYERS,
    WITNESS_SCALE,
)

log = logging.getLogger(__name__)

# ── SP1-specific constants ───────────────────────────────────────────────────

# Target SP1 major version. v5 was deprecated on the Succinct Prover Network
# 2026-05-19; any real-mode work must pin v6+. Informational here (mock mode).
SP1_TARGET_VERSION = "v6"

# Provisional mock proof size — deliberately DISTINCT from the Groth16 256-byte
# wire format (zk_sepproof_prover.PROOF_SIZE) to make explicit that an SP1 proof
# is a NEW format alongside, not a modification. NOT a frozen wire format.
SP1_MOCK_PROOF_SIZE = 192

_THIS_DIR        = Path(__file__).parent.parent
SP1_ARTIFACTS_DIR = _THIS_DIR / "sp1_artifacts"

_SP1_GUEST_ELF = os.getenv("VAPI_SP1_GUEST_ELF_PATH",
                           str(SP1_ARTIFACTS_DIR / "zksepproof_guest.elf"))
_SP1_PROVING_KEY = os.getenv("VAPI_SP1_PROVING_KEY_PATH",
                             str(SP1_ARTIFACTS_DIR / "zksepproof_pk.bin"))


def _sp1_artifacts_available(elf: str, pk: str) -> bool:
    """True when real-mode SP1 artifacts AND the toolchain are present.

    Mock mode is silently selected when False — no error raised. Same pattern
    `zk_sepproof_prover._artifacts_available` uses for snarkjs; lets the bridge
    boot cleanly before the SP1 guest is compiled + a prover is available.

    Three independent gates (ALL required for real mode):
      1. compiled SP1 guest ELF present + non-empty
      2. proving key present + non-empty
      3. an SP1 prover invocation surface on PATH (`cargo`/`sp1`) — the
         subprocess analog of snarkjs; absent here → mock.
    """
    for p in (elf, pk):
        if not p or not Path(p).is_file() or Path(p).stat().st_size == 0:
            return False
    # Toolchain presence: `cargo prove` (sp1 CLI installs a `cargo-prove`
    # subcommand) or a standalone `sp1` binary. Network-only proving would
    # instead check an API key; left for D2 step 2.
    if not (shutil.which("cargo") or shutil.which("sp1")):
        return False
    return True


# Module-level flag — importable by callers to branch real / mock (mirrors
# zk_sepproof_prover.ZKSEP_ARTIFACTS_AVAILABLE).
SP1_ARTIFACTS_AVAILABLE: bool = _sp1_artifacts_available(_SP1_GUEST_ELF, _SP1_PROVING_KEY)


# ── Result dataclass ─────────────────────────────────────────────────────────

@dataclass(slots=True)
class SP1SepProofResult:
    """Output of SP1SepProofProver.generate_proof.

    Mirrors SepProofResult (zk_sepproof_prover) field-for-field so the two
    backends are directly comparable, plus `prover_backend` to disambiguate.
    On failure, error is non-None and proof_bytes is SP1_MOCK_PROOF_SIZE zeros.
    """
    proof_bytes:                  bytes
    feature_commitment:           int
    claimed_player_id:            int
    biometric_snapshot_hash_lo:   int
    biometric_snapshot_hash_hi:   int
    separation_threshold_milli:   int
    inference_code:               int
    is_mock:                      bool
    prover_backend:               str = "sp1"
    error:                        Optional[str] = None


# ── SP1SepProofProver ────────────────────────────────────────────────────────

class SP1SepProofProver:
    """Dual-mode (mock / real-prewired) SP1 prover for ZK-SEPPROOF.

    Interface-compatible with ZKSepProofProver.generate_proof. Default mock mode
    requires no SP1 toolchain. See module docstring for the real-mode prewiring.
    """

    def __init__(
        self,
        guest_elf_path: str = _SP1_GUEST_ELF,
        proving_key_path: str = _SP1_PROVING_KEY,
    ) -> None:
        self._elf = guest_elf_path
        self._pk = proving_key_path
        self._available = _sp1_artifacts_available(guest_elf_path, proving_key_path)
        if not self._available:
            log.info(
                "SP1 ZK-SEPPROOF artifacts/toolchain unavailable — using mock "
                "proofs. Real mode (D2 step 2) requires a compiled SP1 %s guest "
                "ELF + proving key in bridge/sp1_artifacts/ and `cargo prove` on "
                "PATH.", SP1_TARGET_VERSION,
            )

    # ── Public API (signature mirrors ZKSepProofProver.generate_proof) ─────────

    def generate_proof(
        self,
        witness_vector: Sequence[float],
        claimed_player_id: int,
        centroids_by_player: Mapping[int, Sequence[float]],
        cov_inv: Sequence[Sequence[float]],
        biometric_snapshot_hash: bytes,
        separation_threshold_milli: int = 1000,
        inference_code: int = 0,
    ) -> SP1SepProofResult:
        """Generate an SP1 ZK-SEPPROOF proof. Never raises; mirrors the Groth16
        prover's validation contract (reuses ZKSepProofProver._validate_inputs).
        """
        try:
            # Additive reuse of the Groth16 prover's validation — identical
            # input contract, single source of truth, no modification.
            ZKSepProofProver._validate_inputs(
                witness_vector, claimed_player_id, centroids_by_player,
                cov_inv, biometric_snapshot_hash,
                separation_threshold_milli, inference_code,
            )
        except ValueError as exc:
            return SP1SepProofResult(
                proof_bytes=bytes(SP1_MOCK_PROOF_SIZE), feature_commitment=0,
                claimed_player_id=int(claimed_player_id),
                biometric_snapshot_hash_lo=0, biometric_snapshot_hash_hi=0,
                separation_threshold_milli=int(separation_threshold_milli),
                inference_code=int(inference_code),
                is_mock=not self._available, error=str(exc),
            )

        hash_int = int.from_bytes(biometric_snapshot_hash, "big")
        snapshot_hash_hi = (hash_int >> 128) & ((1 << 128) - 1)
        snapshot_hash_lo = hash_int & ((1 << 128) - 1)
        scaled_witness = self._scale_vector(witness_vector)

        if self._available:
            return self._real_proof_sp1(
                scaled_witness=scaled_witness,
                claimed_player_id=int(claimed_player_id),
                centroids_by_player=centroids_by_player,
                cov_inv=cov_inv,
                snapshot_hash_lo=snapshot_hash_lo,
                snapshot_hash_hi=snapshot_hash_hi,
                separation_threshold_milli=int(separation_threshold_milli),
                inference_code=int(inference_code),
            )
        return self._mock_proof(
            scaled_witness=scaled_witness,
            claimed_player_id=int(claimed_player_id),
            snapshot_hash_lo=snapshot_hash_lo,
            snapshot_hash_hi=snapshot_hash_hi,
            separation_threshold_milli=int(separation_threshold_milli),
            inference_code=int(inference_code),
        )

    # ── Helpers ────────────────────────────────────────────────────────────────

    @staticmethod
    def _scale_vector(vec: Sequence[float]) -> list[int]:
        """Scale floats to signed int64 via 1e9 (matches BIOMETRIC-SNAPSHOT-v1
        / the Groth16 prover, so commitments are apples-to-apples)."""
        return [int(round(float(v) * WITNESS_SCALE)) for v in vec]

    # ── Mock proof path ──────────────────────────────────────────────────────

    def _mock_proof(
        self,
        scaled_witness: Sequence[int],
        claimed_player_id: int,
        snapshot_hash_lo: int,
        snapshot_hash_hi: int,
        separation_threshold_milli: int,
        inference_code: int,
    ) -> SP1SepProofResult:
        """Structural mock — no SP1 toolchain.

        feature_commitment = SHA-256(packed scaled witness || claimed_player_id),
        byte-identical body to ZKSepProofProver._mock_proof so the two backends'
        mock commitments match exactly (apples-to-apples comparison harness). In
        real mode this SHA-256 is the SP1 guest's actual native-precompile hash
        (NOT a Poseidon stand-in), so real-mode commitments would diverge from
        Groth16 by design — the benchmark-worthy distinction.

        proof_bytes is a PROVISIONAL structural layout (SP1_MOCK_PROOF_SIZE, a
        DIFFERENT size from the 256-byte Groth16 wire format) — NOT frozen, NOT
        canonical, round-trip-test only.
        """
        body = struct.pack(">4q", *scaled_witness) + struct.pack(">B", claimed_player_id)
        commit_int = int.from_bytes(hashlib.sha256(body).digest(), "big")

        proof = bytearray(SP1_MOCK_PROOF_SIZE)
        proof[0:32]    = commit_int.to_bytes(32, "big")
        snapshot_hash_full = (snapshot_hash_hi << 128) | snapshot_hash_lo
        proof[32:64]   = snapshot_hash_full.to_bytes(32, "big")
        proof[64:96]   = int(claimed_player_id).to_bytes(32, "big")
        proof[96:128]  = int(separation_threshold_milli).to_bytes(32, "big")
        proof[128:160] = int(inference_code).to_bytes(32, "big")
        # [160:192] reserved/zeros — provisional, non-frozen

        return SP1SepProofResult(
            proof_bytes=bytes(proof),
            feature_commitment=commit_int,
            claimed_player_id=int(claimed_player_id),
            biometric_snapshot_hash_lo=snapshot_hash_lo,
            biometric_snapshot_hash_hi=snapshot_hash_hi,
            separation_threshold_milli=int(separation_threshold_milli),
            inference_code=int(inference_code),
            is_mock=True,
            prover_backend="sp1",
            error=None,
        )

    # ── Real proof path (PREWIRED — deferred to D2 step 2) ────────────────────

    def _real_proof_sp1(
        self,
        scaled_witness, claimed_player_id, centroids_by_player, cov_inv,
        snapshot_hash_lo, snapshot_hash_hi,
        separation_threshold_milli, inference_code,
    ) -> SP1SepProofResult:
        """Real SP1 proof — PREWIRED, not yet implemented (D2 step 2).

        Activation path (D2 step 2, target SP1 v6): compile the ZK-SEPPROOF
        Mahalanobis+threshold check as an SP1 Rust guest → `cargo prove` the
        execution against the proving key (subprocess, the snarkjs analog) OR
        submit to the Succinct Prover Network → parse the proof + public values.

        Until that lands, this path is unreachable in practice
        (`_sp1_artifacts_available` is False without the toolchain), and returns
        a clear error result if ever forced — never raises, matching the
        never-raise contract of the Groth16 prover.
        """
        return SP1SepProofResult(
            proof_bytes=bytes(SP1_MOCK_PROOF_SIZE), feature_commitment=0,
            claimed_player_id=int(claimed_player_id),
            biometric_snapshot_hash_lo=snapshot_hash_lo,
            biometric_snapshot_hash_hi=snapshot_hash_hi,
            separation_threshold_milli=int(separation_threshold_milli),
            inference_code=int(inference_code),
            is_mock=False,
            prover_backend="sp1",
            error=(
                "real SP1 proving is D2 step 2 (prewired only) — compile the "
                f"SP1 {SP1_TARGET_VERSION} guest + provide a proving key"
            ),
        )
