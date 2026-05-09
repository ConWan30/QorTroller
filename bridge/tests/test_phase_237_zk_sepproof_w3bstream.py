"""Phase 237-ZK-SEPPROOF Step H — W3bstream applet + wire format tests.

Two complementary test surfaces:

  Bridge encoder tests (T-237-SEP-W3-1..8):
    Verify the 448-byte wire format encoder/decoder round-trips,
    rejects malformed inputs, and reconstructs the snapshot hash
    correctly from the (lo, hi) split.

  Applet shape tests (T-237-SEP-W3-9..14):
    Static checks on validate_zk_sepproof.ts source — locks the FROZEN
    wire format constants, the load-bearing pre-condition (snapshot
    anchored check), the verification anchor anchoring path, and the
    PLACEHOLDER selector documentation. AssemblyScript can't execute in
    pytest; static analysis is the appropriate verification surface.
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

from vapi_bridge.zk_sepproof_w3bstream import (  # noqa: E402
    encode_w3bstream_submission,
    decode_w3bstream_submission,
    reconstruct_snapshot_hash,
    SUBMISSION_TOTAL_LEN,
    PROOF_LEN,
    PUBLIC_INPUT_LEN,
    N_PUBLIC_INPUTS,
)
from vapi_bridge.zk_sepproof_prover import ZKSepProofProver  # noqa: E402

APPLET_PATH = PROJECT_ROOT / "scripts" / "w3bstream" / "validate_zk_sepproof.ts"


# ── Canonical inputs ────────────────────────────────────────────────────────

CANONICAL_WITNESS = [9.37, 0.85, 0.52, 0.71]
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
# Bridge encoder tests
# ─────────────────────────────────────────────────────────────────────────────

def test_t_237_sep_w3_1_constants_frozen():
    """FROZEN: the wire-format constants must match exactly. Any change
    requires v2 + new applet pipeline coordination."""
    assert SUBMISSION_TOTAL_LEN == 448
    assert PROOF_LEN == 256
    assert N_PUBLIC_INPUTS == 6
    assert PUBLIC_INPUT_LEN == 32
    # 256 + 6 × 32 = 448
    assert PROOF_LEN + N_PUBLIC_INPUTS * PUBLIC_INPUT_LEN == SUBMISSION_TOTAL_LEN


def test_t_237_sep_w3_2_round_trip_via_prover():
    """Generate a SepProofResult via the prover, encode, decode, verify
    the round-trip preserves all fields byte-for-byte."""
    prover = ZKSepProofProver()
    result = prover.generate_proof(
        witness_vector=CANONICAL_WITNESS, claimed_player_id=1,
        centroids_by_player=CANONICAL_CENTROIDS, cov_inv=CANONICAL_COV_INV,
        biometric_snapshot_hash=CANONICAL_SNAPSHOT,
        separation_threshold_milli=1000, inference_code=0,
    )
    payload = encode_w3bstream_submission(result)
    assert len(payload) == SUBMISSION_TOTAL_LEN

    decoded = decode_w3bstream_submission(payload)
    assert decoded["proof_bytes"] == result.proof_bytes
    assert decoded["biometric_snapshot_hash_lo"] == result.biometric_snapshot_hash_lo
    assert decoded["biometric_snapshot_hash_hi"] == result.biometric_snapshot_hash_hi
    assert decoded["claimed_player_id"] == result.claimed_player_id
    assert decoded["feature_commitment"] == result.feature_commitment
    assert decoded["separation_threshold_milli"] == result.separation_threshold_milli
    assert decoded["inference_code"] == result.inference_code


def test_t_237_sep_w3_3_reconstruct_snapshot_hash():
    """Verify reconstruct_snapshot_hash matches Solidity verifier's
    `bytes32((hi << 128) | lo)` and the W3bstream applet's
    _reconstruct_snapshot_hash helper."""
    prover = ZKSepProofProver()
    result = prover.generate_proof(
        witness_vector=CANONICAL_WITNESS, claimed_player_id=1,
        centroids_by_player=CANONICAL_CENTROIDS, cov_inv=CANONICAL_COV_INV,
        biometric_snapshot_hash=CANONICAL_SNAPSHOT,
    )
    reconstructed = reconstruct_snapshot_hash(
        result.biometric_snapshot_hash_lo,
        result.biometric_snapshot_hash_hi,
    )
    assert reconstructed == CANONICAL_SNAPSHOT


def test_t_237_sep_w3_4_encode_rejects_error_result():
    """SepProofResult with error set must not be encoded — would silently
    propagate the error downstream as 'valid' submission."""
    prover = ZKSepProofProver()
    bad_result = prover.generate_proof(
        witness_vector=[1.0, 2.0],   # too few features → error
        claimed_player_id=1,
        centroids_by_player=CANONICAL_CENTROIDS, cov_inv=CANONICAL_COV_INV,
        biometric_snapshot_hash=CANONICAL_SNAPSHOT,
    )
    assert bad_result.error is not None
    with pytest.raises(ValueError, match="error set"):
        encode_w3bstream_submission(bad_result)


def test_t_237_sep_w3_5_encode_rejects_wrong_proof_length():
    """proof_bytes must be exactly 256 bytes. Truncated/extended → reject."""
    prover = ZKSepProofProver()
    result = prover.generate_proof(
        witness_vector=CANONICAL_WITNESS, claimed_player_id=1,
        centroids_by_player=CANONICAL_CENTROIDS, cov_inv=CANONICAL_COV_INV,
        biometric_snapshot_hash=CANONICAL_SNAPSHOT,
    )
    # Mutate proof_bytes to wrong length via dataclass-direct write
    object.__setattr__(result, "proof_bytes", b"\x00" * 100)
    with pytest.raises(ValueError, match="must be 256 bytes"):
        encode_w3bstream_submission(result)


def test_t_237_sep_w3_6_decode_rejects_wrong_length():
    with pytest.raises(ValueError, match="must be 448 bytes"):
        decode_w3bstream_submission(b"\x00" * 447)
    with pytest.raises(ValueError, match="must be 448 bytes"):
        decode_w3bstream_submission(b"")


def test_t_237_sep_w3_7_reconstruct_snapshot_rejects_oversized():
    """lo/hi must each fit in 128 bits (uint128)."""
    with pytest.raises(ValueError, match="128-bit"):
        reconstruct_snapshot_hash(1 << 128, 0)
    with pytest.raises(ValueError, match="128-bit"):
        reconstruct_snapshot_hash(0, 1 << 128)
    with pytest.raises(ValueError, match="128-bit"):
        reconstruct_snapshot_hash(-1, 0)


def test_t_237_sep_w3_8_round_trip_zero_threshold():
    """Boundary case: separation_threshold_milli=0 + inference_code=0 + zero hash."""
    prover = ZKSepProofProver()
    result = prover.generate_proof(
        witness_vector=CANONICAL_WITNESS, claimed_player_id=0,
        centroids_by_player=CANONICAL_CENTROIDS, cov_inv=CANONICAL_COV_INV,
        biometric_snapshot_hash=b"\x00" * 32,
        separation_threshold_milli=0, inference_code=0,
    )
    payload = encode_w3bstream_submission(result)
    decoded = decode_w3bstream_submission(payload)
    assert decoded["biometric_snapshot_hash_lo"] == 0
    assert decoded["biometric_snapshot_hash_hi"] == 0
    assert decoded["separation_threshold_milli"] == 0
    assert decoded["inference_code"] == 0
    assert decoded["claimed_player_id"] == 0


# ─────────────────────────────────────────────────────────────────────────────
# Applet shape tests (static checks on validate_zk_sepproof.ts source)
# ─────────────────────────────────────────────────────────────────────────────

def _read_applet() -> str:
    return APPLET_PATH.read_text(encoding="utf-8")


def test_t_237_sep_w3_9_applet_exists_at_canonical_path():
    """validate_zk_sepproof.ts must live at scripts/w3bstream/.  The
    applet pipeline phase looks for applets under that directory."""
    assert APPLET_PATH.exists(), (
        f"validate_zk_sepproof.ts must live at {APPLET_PATH}"
    )
    src = _read_applet()
    assert "export function handle_zk_sepproof_message()" in src, (
        "FROZEN: entry point name must be handle_zk_sepproof_message"
    )


def test_t_237_sep_w3_10_applet_constants_match_bridge():
    """Wire-format constants in the applet must match bridge encoder
    exactly. Drift → silent decoder corruption.

    SUBMISSION_TOTAL_LEN, PROOF_LEN, N_PUBLIC_INPUTS, PUBLIC_INPUT_LEN
    """
    src = _read_applet()
    assert "SUBMISSION_TOTAL_LEN: i32 = 448" in src
    assert "PROOF_LEN: i32           = 256" in src
    assert "N_PUBLIC_INPUTS: i32     = 6" in src
    assert "PUBLIC_INPUT_LEN: i32    = 32" in src


def test_t_237_sep_w3_11_applet_offsets_match_bridge():
    """Offset constants in the applet must match bridge encoder."""
    src = _read_applet()
    assert "OFF_PROOF: i32                   = 0" in src
    assert "OFF_SNAP_HASH_LO: i32            = 256" in src
    assert "OFF_SNAP_HASH_HI: i32            = 288" in src
    assert "OFF_CLAIMED_PLAYER_ID: i32       = 320" in src
    assert "OFF_FEATURE_COMMITMENT: i32      = 352" in src
    assert "OFF_SEPARATION_THRESHOLD_MILLI: i32 = 384" in src
    assert "OFF_INFERENCE_CODE: i32          = 416" in src


def test_t_237_sep_w3_12_applet_has_load_bearing_anchor_check():
    """Pre-condition check (snapshot must be anchored on AdjudicationRegistry)
    is the load-bearing security property — without it, the W1 attack
    succeeds. Regression guard against a future contributor removing it."""
    src = _read_applet()
    assert "_check_snapshot_anchored" in src, (
        "applet must call _check_snapshot_anchored before verifying the "
        "Groth16 proof — load-bearing W1 attack closure"
    )
    # The function must be wired to the chain_call_view path against
    # AdjudicationRegistry.isRecorded
    assert "isRecorded" in src or "0xC0FFEE07" in src, (
        "applet must reference AdjudicationRegistry.isRecorded selector or "
        "name (PLACEHOLDER 0xC0FFEE07 → keccak256('isRecorded(bytes32)')[:4])"
    )
    # Return code 2 reserved for this failure
    assert "return 2;" in src


def test_t_237_sep_w3_13_applet_anchors_verification_record():
    """On verified=true, the applet anchors a unique-per-verification record
    via AdjudicationRegistry.recordAdjudication. This is the audit trail
    that lets third parties verify 'this proof was accepted at this time'.
    """
    src = _read_applet()
    # Verification anchor domain tag
    assert "VAPI-SEPPROOF-VERIFIED-v1" in src, (
        "FROZEN: verification anchor domain tag must be exactly "
        "'VAPI-SEPPROOF-VERIFIED-v1' (25 bytes)"
    )
    # Selector matches deployed legacy 3-arg recordAdjudication ABI
    # (Phase 237.5 Path X discovered anchorAdjudication 2-arg not deployed)
    assert "0x5FA83F4B" in src, (
        "applet must use legacy 3-arg recordAdjudication selector "
        "(matches deployed bytecode per Phase 237.5 Path X)"
    )


def test_t_237_sep_w3_14_applet_documents_three_zone_compartmentalization():
    """The novelty claim of Step H — three-zone privacy compartmentalization
    — must be documented in the applet header. Future contributors reading
    the applet need to understand WHY this is wired through W3bstream
    rather than calling the verifier directly from the bridge."""
    src = _read_applet()
    assert "Three-zone privacy compartmentalization" in src, (
        "applet header must document the three-zone compartmentalization "
        "novelty (bridge=biometrics; W3bstream=proof; chain=anchor)"
    )
    # All three zones explicitly named
    assert "ZONE 1" in src
    assert "ZONE 2" in src
    assert "ZONE 3" in src
