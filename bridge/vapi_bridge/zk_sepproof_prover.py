"""Phase 237-ZK-SEPPROOF — Bridge prover (Step C).

Generates Groth16 ZK separation proofs from live AIT sessions.  Mirrors the
PITLProver (Phase 26) dual-mode (mock / real) architecture exactly:

  - Real mode:  snarkjs groth16 fullprove subprocess against the .wasm + .zkey
                produced by the trusted setup ceremony (deferred until wallet
                refill — see CLAUDE.md Phase 237-ZK-SEPPROOF Step E).
  - Mock mode:  structural commitment computation without the cryptographic
                circuit. Verifies wiring (bridge → SDK → verifier mock) in
                CI without needing ceremony artifacts.

Artifact env vars (real mode):
  VAPI_ZKSEP_WASM_PATH  — bridge/zk_artifacts/ZKSepProof.wasm
  VAPI_ZKSEP_ZKEY_PATH  — bridge/zk_artifacts/ZKSepProof_final.zkey
  VAPI_ZKSEP_VKEY_PATH  — bridge/zk_artifacts/ZKSepProof_verification_key.json

Setup (one-time, post-ceremony):
  cd contracts/circuits && circom ZKSepProof.circom --r1cs --wasm --sym
  bash run-mpc-ceremony.sh ZKSepProof   # produces _final.zkey + _verification_key.json
  cp ZKSepProof_js/ZKSepProof.wasm bridge/zk_artifacts/
  cp ZKSepProof_final.zkey         bridge/zk_artifacts/
  cp ZKSepProof_verification_key.json bridge/zk_artifacts/

Public input order (FROZEN — matches ZKSepProof.circom main declaration):
  [0] biometricSnapshotHashLo  — uint256: low 128 bits of BIOMETRIC-SNAPSHOT-v1
  [1] biometricSnapshotHashHi  — uint256: high 128 bits
  [2] claimedPlayerId          — uint256 in [0, N_PLAYERS)
  [3] featureCommitment        — Poseidon(5)(witness_vector || claimedPlayerId)
  [4] separationThresholdMilli — uint256 (1000 = ratio≥1.0)
  [5] inferenceCode            — uint256 in [0, 255]

Witness scaling (FROZEN — matches BIOMETRIC-SNAPSHOT-v1):
  All floats scaled by 1e9 to int64 BE before circuit input.
  Negative values supported (signed int64).

Proof wire format (256 bytes — same as Phase 26 PITLProver / Phase 18 ZKProver):
  [0:32]    pi_a[0]    G1 point
  [32:64]   pi_a[1]
  [64:96]   pi_b[0][0] G2 point
  [96:128]  pi_b[0][1]
  [128:160] pi_b[1][0]
  [160:192] pi_b[1][1]
  [192:224] pi_c[0]    G1 point
  [224:256] pi_c[1]

Mock proof wire format (deterministic structural encoding for round-trip tests):
  [0:32]    feature_commitment_int   (32B big-endian, matches public input #3)
  [32:64]   biometric_snapshot_hash  (32B big-endian, matches public inputs #0+#1)
  [64:96]   claimed_player_id        (32B big-endian, matches public input #2)
  [96:128]  separation_threshold_milli (32B big-endian, matches #4)
  [128:160] inference_code           (32B big-endian, matches #5)
  [160:256] zeros
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import struct
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Optional, Sequence, Tuple

log = logging.getLogger(__name__)

# ── Frozen scaling constants ─────────────────────────────────────────────────
WITNESS_SCALE = 1_000_000_000   # 1e9, matches BIOMETRIC-SNAPSHOT-v1
PROOF_SIZE    = 256             # Groth16 BN254 uncompressed (matches Phase 26)
N_PLAYERS     = 3               # FROZEN at v1 — AIT corpus shape
FEATURE_DIM   = 4               # FROZEN at v1 — AIT pipeline

_THIS_DIR        = Path(__file__).parent.parent
ZK_ARTIFACTS_DIR = _THIS_DIR / "zk_artifacts"

_ZKSEP_WASM = os.getenv("VAPI_ZKSEP_WASM_PATH",
                         str(ZK_ARTIFACTS_DIR / "ZKSepProof.wasm"))
_ZKSEP_ZKEY = os.getenv("VAPI_ZKSEP_ZKEY_PATH",
                         str(ZK_ARTIFACTS_DIR / "ZKSepProof_final.zkey"))
_ZKSEP_VKEY = os.getenv("VAPI_ZKSEP_VKEY_PATH",
                         str(ZK_ARTIFACTS_DIR / "ZKSepProof_verification_key.json"))

_COMPUTE_INPUTS_ZKSEP_JS = ZK_ARTIFACTS_DIR / "compute_inputs_zksepproof.js"


def _artifacts_available(wasm: str, zkey: str) -> bool:
    """True when all real-mode ZK artifacts exist and are non-empty.

    Mock mode is silently selected when False — no error raised.  This is
    the same pattern PITLProver uses; lets the bridge boot cleanly before
    the trusted setup ceremony runs.
    """
    js_ok = (
        _COMPUTE_INPUTS_ZKSEP_JS.is_file()
        and (ZK_ARTIFACTS_DIR / "node_modules" / "circomlibjs").is_dir()
    )
    for p in (wasm, zkey):
        if not p or not Path(p).is_file() or Path(p).stat().st_size == 0:
            return False
    return js_ok


# Module-level flag — importable by callers to branch between real / mock paths.
ZKSEP_ARTIFACTS_AVAILABLE: bool = _artifacts_available(_ZKSEP_WASM, _ZKSEP_ZKEY)


# ── Result dataclass ─────────────────────────────────────────────────────────

@dataclass(slots=True)
class SepProofResult:
    """Output of ZKSepProofProver.generate_proof.

    All fields are populated on success.  On failure, error is non-None and
    the other fields fall back to safe defaults (proof_bytes is 256 zeros).

    Slots-attached for memory + immutability (matches Phase 184 SDK pattern).
    """
    proof_bytes:                  bytes        # 256-byte Groth16 wire format
    feature_commitment:           int          # Poseidon(5)(witness || pid)
    claimed_player_id:            int          # uint8
    biometric_snapshot_hash_lo:   int          # low 128 bits
    biometric_snapshot_hash_hi:   int          # high 128 bits
    separation_threshold_milli:   int          # uint16
    inference_code:               int          # uint8
    is_mock:                      bool         # True when artifacts absent
    error:                        Optional[str] = None


# ── ZKSepProofProver ─────────────────────────────────────────────────────────

class ZKSepProofProver:
    """Dual-mode (mock / real) Groth16 prover for ZK-SEPPROOF.

    Usage:
        prover = ZKSepProofProver()
        result = prover.generate_proof(
            witness_vector       = [9.37, 0.85, 0.52, 0.71],   # AIT features
            claimed_player_id    = 1,
            centroids_by_player  = {0: [...], 1: [...], 2: [...]},
            cov_inv              = [[...], [...], [...], [...]],  # 4x4
            biometric_snapshot_hash = bytes.fromhex("..."),  # 32-byte from anchor
            separation_threshold_milli = 1000,
            inference_code       = 0,
        )
        if result.error:
            # logged; never raised — mock mode + missing artifacts both
            # produce a valid SepProofResult so the caller can inspect.
            ...
    """

    def __init__(
        self,
        wasm_path: str = _ZKSEP_WASM,
        zkey_path: str = _ZKSEP_ZKEY,
        vkey_path: str = _ZKSEP_VKEY,
    ) -> None:
        self._wasm = wasm_path
        self._zkey = zkey_path
        self._vkey = vkey_path
        self._available = _artifacts_available(wasm_path, zkey_path)
        if not self._available:
            log.info(
                "ZK-SEPPROOF artifacts unavailable — using mock proofs. "
                "Run trusted setup ceremony post-wallet-refill and copy "
                "ZKSepProof.wasm + .zkey + verification_key.json to "
                "bridge/zk_artifacts/."
            )

    # ── Public API ───────────────────────────────────────────────────────────

    def generate_proof(
        self,
        witness_vector: Sequence[float],
        claimed_player_id: int,
        centroids_by_player: Mapping[int, Sequence[float]],
        cov_inv: Sequence[Sequence[float]],
        biometric_snapshot_hash: bytes,
        separation_threshold_milli: int = 1000,
        inference_code: int = 0,
    ) -> SepProofResult:
        """Generate a 256-byte ZK-SEPPROOF proof for the given inputs.

        Args validation:
          - witness_vector must have FEATURE_DIM (4) elements
          - claimed_player_id must be in [0, N_PLAYERS)
          - centroids_by_player must contain exactly N_PLAYERS entries with
            FEATURE_DIM-sized vectors
          - cov_inv must be FEATURE_DIM x FEATURE_DIM
          - biometric_snapshot_hash must be exactly 32 bytes
          - separation_threshold_milli must fit uint16
          - inference_code must fit uint8

        On any validation failure: returns SepProofResult with error set and
        proof_bytes filled with zeros. Never raises.
        """
        # Defensive validation
        try:
            self._validate_inputs(
                witness_vector, claimed_player_id, centroids_by_player,
                cov_inv, biometric_snapshot_hash,
                separation_threshold_milli, inference_code,
            )
        except ValueError as exc:
            return SepProofResult(
                proof_bytes=bytes(PROOF_SIZE), feature_commitment=0,
                claimed_player_id=int(claimed_player_id),
                biometric_snapshot_hash_lo=0, biometric_snapshot_hash_hi=0,
                separation_threshold_milli=int(separation_threshold_milli),
                inference_code=int(inference_code),
                is_mock=not self._available, error=str(exc),
            )

        # Split 32-byte snapshot hash into (lo, hi) 128-bit halves.
        # Circuit splits because BN254 scalar field is ~254 bits.
        hash_int = int.from_bytes(biometric_snapshot_hash, "big")
        snapshot_hash_hi = (hash_int >> 128) & ((1 << 128) - 1)
        snapshot_hash_lo = hash_int & ((1 << 128) - 1)

        # Scale witness inputs (matches BIOMETRIC-SNAPSHOT-v1's int64 1e9 scale)
        scaled_witness = self._scale_vector(witness_vector)

        if self._available:
            return self._real_proof(
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

    # ── Validation ───────────────────────────────────────────────────────────

    @staticmethod
    def _validate_inputs(
        witness_vector, claimed_player_id, centroids_by_player,
        cov_inv, biometric_snapshot_hash,
        separation_threshold_milli, inference_code,
    ) -> None:
        if len(witness_vector) != FEATURE_DIM:
            raise ValueError(
                f"witness_vector must have {FEATURE_DIM} elements, "
                f"got {len(witness_vector)}"
            )
        cpid = int(claimed_player_id)
        if not (0 <= cpid < N_PLAYERS):
            raise ValueError(
                f"claimed_player_id must be in [0, {N_PLAYERS}), got {cpid}"
            )
        if len(centroids_by_player) != N_PLAYERS:
            raise ValueError(
                f"centroids_by_player must have {N_PLAYERS} entries, "
                f"got {len(centroids_by_player)}"
            )
        for pid in range(N_PLAYERS):
            if pid not in centroids_by_player:
                raise ValueError(f"missing centroid for player_id={pid}")
            if len(centroids_by_player[pid]) != FEATURE_DIM:
                raise ValueError(
                    f"centroid for player {pid} must have {FEATURE_DIM} "
                    f"elements, got {len(centroids_by_player[pid])}"
                )
        if len(cov_inv) != FEATURE_DIM:
            raise ValueError(
                f"cov_inv must be {FEATURE_DIM}x{FEATURE_DIM}, "
                f"got {len(cov_inv)} rows"
            )
        for i, row in enumerate(cov_inv):
            if len(row) != FEATURE_DIM:
                raise ValueError(
                    f"cov_inv row {i} must have {FEATURE_DIM} elements, "
                    f"got {len(row)}"
                )
        if not isinstance(biometric_snapshot_hash, (bytes, bytearray)):
            raise ValueError(
                f"biometric_snapshot_hash must be bytes, "
                f"got {type(biometric_snapshot_hash).__name__}"
            )
        if len(biometric_snapshot_hash) != 32:
            raise ValueError(
                f"biometric_snapshot_hash must be 32 bytes, "
                f"got {len(biometric_snapshot_hash)}"
            )
        if not (0 <= int(separation_threshold_milli) <= 0xFFFF):
            raise ValueError(
                f"separation_threshold_milli must fit uint16, "
                f"got {separation_threshold_milli}"
            )
        if not (0 <= int(inference_code) <= 0xFF):
            raise ValueError(
                f"inference_code must fit uint8, got {inference_code}"
            )

    @staticmethod
    def _scale_vector(vec: Sequence[float]) -> list[int]:
        """Scale a float vector to signed int64 via 1e9 (BIOMETRIC-SNAPSHOT-v1 scale).

        Negative values supported. Overflow check: int64 range
        [-9.2e18, +9.2e18] vs scaled values up to ~6e10 for AIT — comfortable.
        """
        out = []
        for v in vec:
            n = int(round(float(v) * WITNESS_SCALE))
            out.append(n)
        return out

    # ── Mock proof path ──────────────────────────────────────────────────────

    def _mock_proof(
        self,
        scaled_witness: Sequence[int],
        claimed_player_id: int,
        snapshot_hash_lo: int,
        snapshot_hash_hi: int,
        separation_threshold_milli: int,
        inference_code: int,
    ) -> SepProofResult:
        """Mock proof path — no real circuit, no ceremony required.

        feature_commitment is computed as SHA-256 of packed scaled witness
        + claimed_player_id (NOT Poseidon — would require Node.js subprocess).
        This is a STRUCTURAL stand-in: the value is deterministic and
        round-trippable, but does NOT match what the real circuit would
        produce.  When ceremony artifacts arrive, real mode produces the
        actual Poseidon commitment.

        Mock proof bytes encode the public inputs in a deterministic
        layout for round-trip tests. The verifier mock
        (MockZKSepProofGroth16Verifier.sol) ignores proof bytes entirely
        and returns the configured verifyResult, so test wiring works
        end-to-end without cryptographic correctness.
        """
        # Structural commitment via SHA-256
        body = struct.pack(">4q", *scaled_witness) + struct.pack(">B", claimed_player_id)
        commit_int = int.from_bytes(hashlib.sha256(body).digest(), "big")

        # Encode mock proof bytes
        proof = bytearray(PROOF_SIZE)
        proof[0:32]    = commit_int.to_bytes(32, "big")
        # snapshot_hash_lo + snapshot_hash_hi reconstructs the 32-byte hash
        snapshot_hash_full = (snapshot_hash_hi << 128) | snapshot_hash_lo
        proof[32:64]   = snapshot_hash_full.to_bytes(32, "big")
        proof[64:96]   = int(claimed_player_id).to_bytes(32, "big")
        proof[96:128]  = int(separation_threshold_milli).to_bytes(32, "big")
        proof[128:160] = int(inference_code).to_bytes(32, "big")
        # [160:256] zeros

        return SepProofResult(
            proof_bytes=bytes(proof),
            feature_commitment=commit_int,
            claimed_player_id=int(claimed_player_id),
            biometric_snapshot_hash_lo=snapshot_hash_lo,
            biometric_snapshot_hash_hi=snapshot_hash_hi,
            separation_threshold_milli=int(separation_threshold_milli),
            inference_code=int(inference_code),
            is_mock=True,
            error=None,
        )

    # ── Real proof path (deferred until ceremony) ────────────────────────────

    def _real_proof(
        self,
        scaled_witness, claimed_player_id, centroids_by_player, cov_inv,
        snapshot_hash_lo, snapshot_hash_hi,
        separation_threshold_milli, inference_code,
    ) -> SepProofResult:
        """Real Groth16 proof via snarkjs subprocess.

        Activates when ceremony artifacts are present in bridge/zk_artifacts/.
        Until then, _artifacts_available returns False and this code path
        is unreachable in production.

        Failure modes covered (return SepProofResult with error set):
          - Node.js helper failure (Poseidon compute fails)
          - snarkjs subprocess non-zero exit
          - Proof JSON parse failure
        """
        try:
            with tempfile.TemporaryDirectory() as _tmp:
                tmpdir = Path(_tmp)

                # Build sorted centroids list matching circuit's [N_PLAYERS][FEATURES] shape
                centroids_scaled = [
                    self._scale_vector(centroids_by_player[pid])
                    for pid in range(N_PLAYERS)
                ]
                cov_scaled = [self._scale_vector(row) for row in cov_inv]

                private_in = {
                    "witnessVector":              [str(v) for v in scaled_witness],
                    "centroids":                  [[str(v) for v in row] for row in centroids_scaled],
                    "covInv":                     [[str(v) for v in row] for row in cov_scaled],
                    "claimedPlayerId":            int(claimed_player_id),
                    "biometricSnapshotHashLo":    str(snapshot_hash_lo),
                    "biometricSnapshotHashHi":    str(snapshot_hash_hi),
                    "separationThresholdMilli":   int(separation_threshold_milli),
                    "inferenceCode":              int(inference_code),
                }
                priv_path = tmpdir / "private_inputs_zksep.json"
                priv_path.write_text(json.dumps(private_in))

                # Compute Poseidon-based featureCommitment via Node.js
                circuit_in_path = tmpdir / "circuit_input_zksep.json"
                _run_node(
                    str(_COMPUTE_INPUTS_ZKSEP_JS),
                    [str(priv_path)],
                    capture_to=circuit_in_path,
                    cwd=str(ZK_ARTIFACTS_DIR),
                )
                circuit_inputs = json.loads(circuit_in_path.read_text())
                feature_commitment_int = int(circuit_inputs["featureCommitment"])

                # snarkjs groth16 fullprove
                proof_path  = tmpdir / "proof_zksep.json"
                public_path = tmpdir / "public_zksep.json"
                _run_snarkjs([
                    "groth16", "fullprove",
                    str(circuit_in_path),
                    self._wasm,
                    self._zkey,
                    str(proof_path),
                    str(public_path),
                ])

                proof_json  = json.loads(proof_path.read_text())
                proof_bytes = _encode_proof(proof_json)

                log.info(
                    "ZK-SEPPROOF generated — claimed_pid=%d fc=%s size=%d",
                    int(claimed_player_id),
                    hex(feature_commitment_int)[:18], len(proof_bytes),
                )
                return SepProofResult(
                    proof_bytes=proof_bytes,
                    feature_commitment=feature_commitment_int,
                    claimed_player_id=int(claimed_player_id),
                    biometric_snapshot_hash_lo=snapshot_hash_lo,
                    biometric_snapshot_hash_hi=snapshot_hash_hi,
                    separation_threshold_milli=int(separation_threshold_milli),
                    inference_code=int(inference_code),
                    is_mock=False,
                    error=None,
                )
        except Exception as exc:
            return SepProofResult(
                proof_bytes=bytes(PROOF_SIZE), feature_commitment=0,
                claimed_player_id=int(claimed_player_id),
                biometric_snapshot_hash_lo=snapshot_hash_lo,
                biometric_snapshot_hash_hi=snapshot_hash_hi,
                separation_threshold_milli=int(separation_threshold_milli),
                inference_code=int(inference_code),
                is_mock=False,
                error=f"real proof failed: {type(exc).__name__}: {exc}"[:200],
            )


# ── Proof encoding (matches Phase 26 PITLProver wire format) ────────────────

def _encode_proof(proof_json: dict) -> bytes:
    """Encode snarkjs proof.json → 256-byte ABI wire format."""
    def to_bytes32(v) -> bytes:
        n = int(v, 16) if str(v).startswith(("0x", "0X")) else int(v)
        return n.to_bytes(32, "big")

    buf = bytearray(PROOF_SIZE)
    buf[0:32]    = to_bytes32(proof_json["pi_a"][0])
    buf[32:64]   = to_bytes32(proof_json["pi_a"][1])
    buf[64:96]   = to_bytes32(proof_json["pi_b"][0][0])
    buf[96:128]  = to_bytes32(proof_json["pi_b"][0][1])
    buf[128:160] = to_bytes32(proof_json["pi_b"][1][0])
    buf[160:192] = to_bytes32(proof_json["pi_b"][1][1])
    buf[192:224] = to_bytes32(proof_json["pi_c"][0])
    buf[224:256] = to_bytes32(proof_json["pi_c"][1])
    return bytes(buf)


# ── Subprocess helpers (mirror PITLProver pattern) ───────────────────────────

def _run_node(script: str, args: list, capture_to=None, cwd=None) -> None:
    """Run a Node.js script, optionally capturing stdout to a file."""
    cmd = ["node", script] + list(args)
    if capture_to:
        with Path(capture_to).open("w") as f:
            r = subprocess.run(cmd, stdout=f, stderr=subprocess.PIPE, cwd=cwd, check=False)
    else:
        r = subprocess.run(cmd, capture_output=True, cwd=cwd, check=False)
    if r.returncode != 0:
        stderr = r.stderr.decode(errors="replace") if r.stderr else ""
        raise RuntimeError(f"Node.js helper failed: {stderr[:600]}")


def _run_snarkjs(args: list, check: bool = True):
    """Run snarkjs via npx."""
    cmd = ["npx", "--yes", "snarkjs"] + args
    r = subprocess.run(cmd, capture_output=True, check=False)
    if check and r.returncode != 0:
        stderr = r.stderr.decode(errors="replace") if r.stderr else ""
        raise RuntimeError(f"snarkjs failed: {stderr[:600]}")
    return r
