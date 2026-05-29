"""Data Economy Arc 2 — ZK buyer-category proof verification (bridge read path).

The bridge verifies a buyer's private category proof against the on-chain
VAPIBuyerCategoryVerifier (Groth16, BN254) WITHOUT learning the buyerDID. A
buyer proves "I hold an unexpired Curator-issued credential for category C"
while keeping their identity private; the bridge learns only the category and
the anti-replay nullifier.

DESIGN (mirrors the Arc 1 fail-open read posture, deliberately NOT the
fail-loud Curator write path):
  - The verifier address defaults EMPTY (config.buyer_category_verifier_address)
    until the operator deploys the verifier on-chain. While empty, every call
    fails open False — a missing verifier must never validate a proof.
  - No writer. This module only staticcalls verifyProof; it cannot mutate state.
  - INV-BUY-001 (FROZEN category enum 1..4) is checked locally BEFORE any chain
    contact, so a malformed claimed_category is rejected without an RPC round-trip
    and the contract's own catMin/catMax circuit constraint is mirrored bridge-side.

Proof wire format (deterministic, 320 bytes = 10 × 32-byte big-endian words):
  [0..1]  pA.x, pA.y
  [2..5]  pB[0][0], pB[0][1], pB[1][0], pB[1][1]
  [6..7]  pC.x, pC.y
  [8]     credentialCommitment   (public input #3)
  [9]     nullifierHash          (public input #4)
claimed_category and current_timestamp are passed as function args (public
inputs #1, #2); pubSignals[0] (the circuit `valid` output) is always 1.

pubSignals layout passed to verifyProof — snarkjs orders outputs first, then
public inputs in declaration order:
  [0]=valid(=1) [1]=claimedCategory [2]=currentTimestamp
  [3]=credentialCommitment [4]=nullifierHash
"""
from __future__ import annotations

import logging

log = logging.getLogger("vapi.zk_buyer_verifier")

_PROOF_WORDS = 10
_PROOF_BYTES = _PROOF_WORDS * 32

# INV-BUY-001 FROZEN enum domain: ACADEMIC=1 / GAME_DEV=2 / ESPORTS=3 / BRAND=4
_CATEGORY_MIN = 1
_CATEGORY_MAX = 4


def _decode_proof(proof: bytes):
    """Split the 320-byte proof payload into (pA, pB, pC, commitment, nullifier).
    Raises ValueError on any length/format fault — callers fail open."""
    if not isinstance(proof, (bytes, bytearray)):
        raise ValueError("proof must be bytes")
    if len(proof) != _PROOF_BYTES:
        raise ValueError(f"proof must be {_PROOF_BYTES} bytes, got {len(proof)}")
    words = [
        int.from_bytes(proof[i * 32:(i + 1) * 32], "big")
        for i in range(_PROOF_WORDS)
    ]
    pA = (words[0], words[1])
    pB = ((words[2], words[3]), (words[4], words[5]))
    pC = (words[6], words[7])
    commitment = words[8]
    nullifier = words[9]
    return pA, pB, pC, commitment, nullifier


def verify_buyer_category_proof(
    chain,
    proof: bytes,
    claimed_category: int,
    current_timestamp: int,
) -> bool:
    """Verify a private buyer-category Groth16 proof on-chain.

    Returns True iff the verifier confirms the proof. Fail-open False on any
    fault: verifier undeployed, malformed proof, out-of-range category, or RPC
    error. The bridge never grants category access on an unverifiable proof.

    Args:
        chain:            ChainClient (provides verify_buyer_category_proof_onchain).
        proof:            320-byte wire payload (see module docstring).
        claimed_category: revealed category 1..4 (INV-BUY-001).
        current_timestamp: verifier "now" (unix seconds) for the expiry check.
    """
    # Local INV-BUY-001 guard — reject before any chain contact.
    try:
        cat = int(claimed_category)
    except (TypeError, ValueError):
        log.warning("verify_buyer_category_proof: non-int claimed_category (fail-open False)")
        return False
    if cat < _CATEGORY_MIN or cat > _CATEGORY_MAX:
        log.warning(
            "verify_buyer_category_proof: claimed_category %s outside FROZEN 1..4 (fail-open False)",
            cat,
        )
        return False

    try:
        ts = int(current_timestamp)
    except (TypeError, ValueError):
        log.warning("verify_buyer_category_proof: non-int current_timestamp (fail-open False)")
        return False

    try:
        pA, pB, pC, commitment, nullifier = _decode_proof(proof)
    except ValueError as exc:
        log.warning("verify_buyer_category_proof: %s (fail-open False)", exc)
        return False

    pub_signals = [1, cat, ts, commitment, nullifier]
    return chain.verify_buyer_category_proof_onchain(pA, pB, pC, pub_signals)
