// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * @title VAPIReplayProofVerifier — Data Economy Arc 5 wrapper
 * @notice On-chain verifier for VAPI Verified Human Replay (VHR) proofs.
 *
 * Wraps a snarkjs-generated Groth16 verifier (auto-generated from
 * contracts/circuits/VAPIReplayProofVerifier.circom + the trusted setup
 * ceremony's .zkey) and adds the FROZEN PROOF_TYPE discriminator that
 * distinguishes VHR proofs from the existing PitlSessionProof / ZKSepProof
 * lineage on the marketplace.
 *
 * What the inner Groth16 verifier proves:
 *   - Knowledge of (vhpTokenId, sessionNonce) opening of vhpCommitment.
 *   - humanityProbabilityWitness >= humanityThreshold (Num2Bits(10) range
 *     check after off-chain subtraction).
 *   - replayProofToken === Poseidon(sanitizedTraceRoot, poacChainRoot,
 *     consentPolicyHash, humanityThreshold).
 *
 * What this wrapper adds:
 *   - PROOF_TYPE discriminator (INV-VHR-003): keccak256("VAPI-REPLAY-PROOF-v1").
 *   - ReplayProofVerified event surfacing the public-input tuple for indexers.
 *   - Immutable Groth16 verifier address — no setter, no upgrade path.
 *
 * What this wrapper deliberately does NOT bind on-chain (Commit 3 scope):
 *
 *   1. AdjudicationRegistry snapshot anchoring of poacChainRoot.
 *      poacChainRoot is a BN254 field element (Poseidon root, ~254 bits) while
 *      AdjudicationRegistry stores SHA-256 32-byte hashes — the field↔bytes32
 *      binding decision is non-trivial and is deferred to Commit 4's
 *      orchestrator + the Arc 5 Step 4 anchor reconciliation.
 *
 *   2. Consent manifest binding of consentPolicyHash.
 *      Spec line 476 binds consentPolicyHash to
 *      `VAPIConsentRegistry.manifestHash(deviceId)` but Arc 4 shipped a
 *      SEPARATE `VAPIConsentManifestRegistry` keyed by gamer ADDRESS — drift
 *      D-2 per docs/data-economy-deploy-hold-and-arc5-readiness.md. The
 *      verifier has no address context to perform the lookup; binding is
 *      enforced at orchestration / listing time (Curator gate, Commit 4).
 *
 * Both deferrals are deliberate: deploying a wrapper that consults a not-yet-
 * deployed registry would either fail-closed (every proof rejected) or
 * fail-open (no enforcement) — neither honest. The wrapper exists purely to
 * lock the PROOF_TYPE and the public-input tuple shape; preconditions land
 * with the orchestrator once the Arc 4 manifest contract's deploy posture is
 * also reconciled.
 *
 * Public input array (FROZEN — must match VAPIReplayProofVerifier.circom):
 *
 *   snarkjs orders OUTPUT first, then PUBLIC inputs in declaration order, so
 *   the 6-element publicInputs array is:
 *
 *     [0] replayProofToken     — circuit output, Poseidon(4)(sanitizedTraceRoot,
 *                                  poacChainRoot, consentPolicyHash,
 *                                  humanityThreshold)
 *     [1] sanitizedTraceRoot   — Poseidon-sponge root of the matrix (off-circuit;
 *                                  recomputed off-chain by the verifier)
 *     [2] poacChainRoot        — Poseidon-8 Merkle root of session PoAC records
 *     [3] consentPolicyHash    — hash of the gamer's consent manifest at listing
 *     [4] humanityThreshold    — scaled ×1000 floor (e.g. 700 = 0.70 AIT default)
 *     [5] vhpCommitment        — Poseidon(2)(vhpTokenId, sessionNonce)
 *
 * @dev DEPLOYMENT — gated on the trusted-setup ceremony AND the Arc 5 ladder
 *      hold. Per docs/data-economy-deploy-hold-and-arc5-readiness.md: all
 *      remaining Data Economy on-chain deploys (Arc 2, Arc 4, Arc 5) are
 *      HELD until Arc 5 is built end-to-end and verified under explicit
 *      operator GO.
 *
 *      Two-stage deploy (post-hold-lift):
 *        Stage 1 — operator runs the trusted-setup ceremony for
 *          VAPIReplayProofVerifier.circom (reuses pot15_final.ptau,
 *          contributors per Phase 237 precedent), producing
 *          VAPIReplayProofVerifier_final.zkey +
 *          VAPIReplayProofVerifier_verification_key.json. snarkjs
 *          `zkey export solidityverifier` generates the inner
 *          Groth16VerifierVAPIReplayProof.sol — deploy it, record address.
 *        Stage 2 — deploy this wrapper with (groth16VerifierAddress) via
 *          scripts/deploy-vapi-replay-proof-verifier.js (estimate-only by
 *          default; broadcast on VAPI_REPLAY_PROOF_DEPLOY_CONFIRM=1).
 */

interface IVAPIReplayProofGroth16Verifier {
    function verifyProof(
        uint256[2] memory a,
        uint256[2][2] memory b,
        uint256[2] memory c,
        uint256[6] memory input
    ) external view returns (bool);
}

contract VAPIReplayProofVerifier {
    /// @notice FROZEN proof-type discriminator — distinguishes VHR proofs
    /// from PitlSessionProof / ZKSepProof on the marketplace. Pinned by
    /// PV-CI INV-VHR-003; any change breaks listing-type routing.
    bytes32 public constant PROOF_TYPE = keccak256("VAPI-REPLAY-PROOF-v1");

    /// @notice Indices into the snarkjs publicInputs array. Tied to the
    /// circuit's `component main {public [...]}` declaration order (pinned
    /// by PV-CI INV-VHR-005). snarkjs convention places the single circuit
    /// output (replayProofToken) at index 0, then public inputs in
    /// declaration order.
    uint256 public constant INPUT_REPLAY_PROOF_TOKEN   = 0;
    uint256 public constant INPUT_SANITIZED_TRACE_ROOT = 1;
    uint256 public constant INPUT_POAC_CHAIN_ROOT      = 2;
    uint256 public constant INPUT_CONSENT_POLICY_HASH  = 3;
    uint256 public constant INPUT_HUMANITY_THRESHOLD   = 4;
    uint256 public constant INPUT_VHP_COMMITMENT       = 5;

    /// @notice Immutable Groth16 verifier address (snarkjs-generated from
    /// the VAPIReplayProofVerifier circuit + ceremony zkey).
    address public immutable groth16Verifier;

    /// @notice Emitted on every accepted VHR proof. Indexers reconstruct the
    /// proof package from these fields + the off-chain matrix payload.
    event ReplayProofVerified(
        bytes32 indexed replayProofToken,
        bytes32 indexed poacChainRoot,
        bytes32 indexed consentPolicyHash,
        uint256 humanityThreshold,
        bytes32 sanitizedTraceRoot,
        bytes32 vhpCommitment
    );

    constructor(address _groth16Verifier) {
        require(_groth16Verifier != address(0), "VHR: groth16 verifier zero");
        groth16Verifier = _groth16Verifier;
    }

    /**
     * @notice Verify a VHR proof and emit ReplayProofVerified on acceptance.
     *
     * Forwards the proof to the inner Groth16 verifier with the FROZEN
     * 6-element public-input array. The circuit's tokenHasher constraint
     * ties publicInputs[0] (replayProofToken) to publicInputs[1..4]; the
     * caller has nothing to forge here without breaking the Groth16
     * soundness assumption.
     *
     * @param a              Groth16 proof element a
     * @param b              Groth16 proof element b
     * @param c              Groth16 proof element c
     * @param publicInputs   6 public inputs in snarkjs declaration order
     * @return verified      true if the Groth16 verifier accepts
     *
     * Matches the snarkjs-generated verifier convention of returning false on
     * a malformed proof rather than reverting — no revert here either, so
     * callers can branch on the boolean.
     */
    function verify(
        uint256[2] calldata a,
        uint256[2][2] calldata b,
        uint256[2] calldata c,
        uint256[6] calldata publicInputs
    ) external returns (bool verified) {
        verified = IVAPIReplayProofGroth16Verifier(groth16Verifier)
            .verifyProof(a, b, c, publicInputs);

        if (verified) {
            emit ReplayProofVerified(
                bytes32(publicInputs[INPUT_REPLAY_PROOF_TOKEN]),
                bytes32(publicInputs[INPUT_POAC_CHAIN_ROOT]),
                bytes32(publicInputs[INPUT_CONSENT_POLICY_HASH]),
                publicInputs[INPUT_HUMANITY_THRESHOLD],
                bytes32(publicInputs[INPUT_SANITIZED_TRACE_ROOT]),
                bytes32(publicInputs[INPUT_VHP_COMMITMENT])
            );
        }
    }

    /**
     * @notice Pure-view variant — same forwarding as `verify` without emitting
     * the event. Useful for buyer pre-purchase dry-runs (eth_call against
     * this method costs zero gas).
     */
    function verifyView(
        uint256[2] calldata a,
        uint256[2][2] calldata b,
        uint256[2] calldata c,
        uint256[6] calldata publicInputs
    ) external view returns (bool) {
        return IVAPIReplayProofGroth16Verifier(groth16Verifier)
            .verifyProof(a, b, c, publicInputs);
    }
}
