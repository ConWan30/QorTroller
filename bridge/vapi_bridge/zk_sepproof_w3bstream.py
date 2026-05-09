"""Phase 237-ZK-SEPPROOF Step H — W3bstream submission wire format encoder.

Bridge-side counterpart to scripts/w3bstream/validate_zk_sepproof.ts.

Encodes a 448-byte submission payload that the W3bstream applet decodes:

    [0:256]      Groth16 proof bytes (BN254 uncompressed)
    [256:288]    biometricSnapshotHashLo  (uint256 BE)
    [288:320]    biometricSnapshotHashHi  (uint256 BE)
    [320:352]    claimedPlayerId          (uint256 BE)
    [352:384]    featureCommitment        (uint256 BE)
    [384:416]    separationThresholdMilli (uint256 BE)
    [416:448]    inferenceCode            (uint256 BE)

Total: 448 bytes (256 proof + 6 × 32 public inputs).

The wire format is FROZEN at Step H v1.  Any future change requires v2 +
new W3bstream applet pipeline coordination.

Integration:
  1. Bridge generates SepProofResult via ZKSepProofProver.generate_proof
  2. Bridge calls encode_w3bstream_submission(result) → 448 bytes
  3. Bridge POSTs payload to W3bstream HTTP gateway
  4. W3bstream applet (validate_zk_sepproof.ts) decodes + verifies + anchors

This module ships no I/O — pure encoding.  HTTP submission is a separate
operator step (deferred until W3bstream applet pipeline phase + wallet
refill for the registry chain calls).
"""
from __future__ import annotations

import struct
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .zk_sepproof_prover import SepProofResult


# ── Wire format constants (FROZEN at Step H v1) ─────────────────────────────
SUBMISSION_TOTAL_LEN = 448
PROOF_LEN = 256
N_PUBLIC_INPUTS = 6
PUBLIC_INPUT_LEN = 32  # uint256 BE per input

OFF_PROOF                       = 0
OFF_SNAP_HASH_LO                = 256
OFF_SNAP_HASH_HI                = 288
OFF_CLAIMED_PLAYER_ID           = 320
OFF_FEATURE_COMMITMENT          = 352
OFF_SEPARATION_THRESHOLD_MILLI  = 384
OFF_INFERENCE_CODE              = 416


def _encode_uint256_be(value: int) -> bytes:
    """Encode a non-negative integer to 32-byte big-endian (uint256 ABI)."""
    n = int(value)
    if n < 0:
        raise ValueError(f"uint256 cannot be negative, got {n}")
    if n.bit_length() > 256:
        raise ValueError(f"value exceeds uint256 range: {n}")
    return n.to_bytes(32, "big")


def encode_w3bstream_submission(result: "SepProofResult") -> bytes:
    """Encode a SepProofResult to the FROZEN 448-byte W3bstream wire format.

    Args:
        result: SepProofResult from ZKSepProofProver.generate_proof.

    Returns:
        Exactly 448 bytes ready for W3bstream HTTP gateway POST.

    Raises:
        ValueError on shape mismatch or invalid result (proof_bytes wrong
        length, error field set, integer overflow).

    The encoder is strict: any input outside the FROZEN wire-format
    contract raises rather than silently truncating. This matches the
    Solidity verifier's strict deserialization on the receive side.
    """
    if result is None:
        raise ValueError("SepProofResult is None")
    if result.error:
        raise ValueError(
            f"cannot encode SepProofResult with error set: {result.error}"
        )
    if not isinstance(result.proof_bytes, (bytes, bytearray)):
        raise ValueError(
            f"proof_bytes must be bytes, got {type(result.proof_bytes).__name__}"
        )
    if len(result.proof_bytes) != PROOF_LEN:
        raise ValueError(
            f"proof_bytes must be {PROOF_LEN} bytes, got {len(result.proof_bytes)}"
        )

    out = bytearray(SUBMISSION_TOTAL_LEN)
    # Proof bytes
    out[OFF_PROOF:OFF_PROOF + PROOF_LEN] = result.proof_bytes
    # Public inputs (each as uint256 BE)
    out[OFF_SNAP_HASH_LO:OFF_SNAP_HASH_LO + PUBLIC_INPUT_LEN] = _encode_uint256_be(
        result.biometric_snapshot_hash_lo
    )
    out[OFF_SNAP_HASH_HI:OFF_SNAP_HASH_HI + PUBLIC_INPUT_LEN] = _encode_uint256_be(
        result.biometric_snapshot_hash_hi
    )
    out[OFF_CLAIMED_PLAYER_ID:OFF_CLAIMED_PLAYER_ID + PUBLIC_INPUT_LEN] = _encode_uint256_be(
        result.claimed_player_id
    )
    out[OFF_FEATURE_COMMITMENT:OFF_FEATURE_COMMITMENT + PUBLIC_INPUT_LEN] = _encode_uint256_be(
        result.feature_commitment
    )
    out[OFF_SEPARATION_THRESHOLD_MILLI:
        OFF_SEPARATION_THRESHOLD_MILLI + PUBLIC_INPUT_LEN] = _encode_uint256_be(
        result.separation_threshold_milli
    )
    out[OFF_INFERENCE_CODE:OFF_INFERENCE_CODE + PUBLIC_INPUT_LEN] = _encode_uint256_be(
        result.inference_code
    )
    return bytes(out)


def decode_w3bstream_submission(payload: bytes) -> dict:
    """Decode a 448-byte W3bstream submission back to its component fields.

    Inverse of encode_w3bstream_submission.  Useful for tests + diagnostic
    tooling.

    Returns dict with keys: proof_bytes, biometric_snapshot_hash_lo/hi,
    claimed_player_id, feature_commitment, separation_threshold_milli,
    inference_code.
    """
    if not isinstance(payload, (bytes, bytearray)):
        raise ValueError(
            f"payload must be bytes, got {type(payload).__name__}"
        )
    if len(payload) != SUBMISSION_TOTAL_LEN:
        raise ValueError(
            f"payload must be {SUBMISSION_TOTAL_LEN} bytes, "
            f"got {len(payload)}"
        )
    return {
        "proof_bytes": bytes(payload[OFF_PROOF:OFF_PROOF + PROOF_LEN]),
        "biometric_snapshot_hash_lo": int.from_bytes(
            payload[OFF_SNAP_HASH_LO:OFF_SNAP_HASH_LO + PUBLIC_INPUT_LEN], "big"
        ),
        "biometric_snapshot_hash_hi": int.from_bytes(
            payload[OFF_SNAP_HASH_HI:OFF_SNAP_HASH_HI + PUBLIC_INPUT_LEN], "big"
        ),
        "claimed_player_id": int.from_bytes(
            payload[OFF_CLAIMED_PLAYER_ID:
                    OFF_CLAIMED_PLAYER_ID + PUBLIC_INPUT_LEN], "big"
        ),
        "feature_commitment": int.from_bytes(
            payload[OFF_FEATURE_COMMITMENT:
                    OFF_FEATURE_COMMITMENT + PUBLIC_INPUT_LEN], "big"
        ),
        "separation_threshold_milli": int.from_bytes(
            payload[OFF_SEPARATION_THRESHOLD_MILLI:
                    OFF_SEPARATION_THRESHOLD_MILLI + PUBLIC_INPUT_LEN], "big"
        ),
        "inference_code": int.from_bytes(
            payload[OFF_INFERENCE_CODE:
                    OFF_INFERENCE_CODE + PUBLIC_INPUT_LEN], "big"
        ),
    }


def reconstruct_snapshot_hash(lo: int, hi: int) -> bytes:
    """Reconstruct the 32-byte snapshot hash from (lo, hi) 128-bit halves.

    Mirrors:
      - Solidity verifier:  bytes32((hi << 128) | lo)
      - W3bstream applet:   _reconstruct_snapshot_hash() helper
    """
    if lo < 0 or lo >= (1 << 128):
        raise ValueError(f"lo out of 128-bit range: {lo}")
    if hi < 0 or hi >= (1 << 128):
        raise ValueError(f"hi out of 128-bit range: {hi}")
    full_int = (hi << 128) | lo
    return full_int.to_bytes(32, "big")
