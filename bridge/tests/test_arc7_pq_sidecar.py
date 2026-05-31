"""Arc 7 Decoupled Cryptographic Sidecar Pointer Test Suite.

Verifies the out-of-band ML-DSA-65 signing process, deterministic SHA-256 pointer
generation, mock DePIN DA layer persistence, and that the Layer 1 primitive
remains unaltered (strictly 228 bytes).
"""

import asyncio
import hashlib
import json
import pytest

from bridge.vapi_bridge.replay_proof_pipeline.da_layer import da_router
from bridge.vapi_bridge.replay_proof_pipeline.pipeline import (
    _run_mldsa_signing,
    VHRProofPackage,
    SanitizedReplayMatrix,
)
from bridge.vapi_bridge.codec import POAC_RECORD_SIZE


def test_poac_record_size_unaltered():
    """Asserts that the L1 primitive POAC_RECORD_SIZE strictly equals 228 bytes."""
    assert POAC_RECORD_SIZE == 228


def test_mldsa_signing_and_da_upload():
    """Verifies that _run_mldsa_signing computes a valid 32-byte pointer and stores the 3,309-byte payload in the DA layer."""
    # 1. Setup a mock SanitizedReplayMatrix
    matrix = SanitizedReplayMatrix(
        session_id="session-pqc-1",
        ticks=10,
        stick_L_sector=b"\x01" * 10,
        stick_R_sector=b"\x02" * 10,
        trigger_L_state=b"\x03" * 10,
        trigger_R_state=b"\x04" * 10,
        button_mask=b"\x05" * 20,
        imu_gravity_sector=b"\x06" * 10,
        poac_chain_root=b"\x07" * 32,
        vhp_token_id=123,
        humanity_prob_floor=0.95,
        session_verdict="HUMAN",
    )

    # Clear DA storage to isolate test
    da_router.clear()

    # 2. Run signing process (which also performs the DA upload)
    commitment_hex, signature = _run_mldsa_signing(matrix)

    # 3. Assert pointer properties (hex format, 32 bytes)
    assert commitment_hex.startswith("0x")
    commitment_bytes = bytes.fromhex(commitment_hex[2:])
    assert len(commitment_bytes) == 32

    # 4. Assert signature length is exactly 3309 bytes
    assert len(signature) == 3309

    # 5. Assert DA layer successfully downloaded payload matches signature
    downloaded = da_router.download_signature(commitment_bytes)
    assert downloaded is not None
    assert len(downloaded) == 3309
    assert downloaded == signature


@pytest.mark.asyncio
async def test_thread_c_async_signing():
    """Verifies that the Thread C engine can sign matrix out-of-band without blocking the loop."""
    matrix = SanitizedReplayMatrix(
        session_id="session-pqc-async",
        ticks=5,
        stick_L_sector=b"\x01" * 5,
        stick_R_sector=b"\x02" * 5,
        trigger_L_state=b"\x03" * 5,
        trigger_R_state=b"\x04" * 5,
        button_mask=b"\x05" * 10,
        imu_gravity_sector=b"\x06" * 5,
        poac_chain_root=b"\x07" * 32,
        vhp_token_id=123,
        humanity_prob_floor=0.95,
        session_verdict="HUMAN",
    )

    da_router.clear()

    # Run in asyncio thread-pool executor (representing Thread C behavior)
    commitment_hex, signature = await asyncio.to_thread(_run_mldsa_signing, matrix)

    assert commitment_hex.startswith("0x")
    commitment_bytes = bytes.fromhex(commitment_hex[2:])
    assert len(commitment_bytes) == 32
    assert len(signature) == 3309

    downloaded = da_router.download_signature(commitment_bytes)
    assert downloaded == signature
