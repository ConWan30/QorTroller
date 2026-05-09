// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * @title ZKSepProofVerifier — Phase 237-ZK-SEPPROOF wrapper
 * @notice On-chain verifier for VAPI ZK separation proofs.
 *
 * Wraps a snarkjs-generated Groth16 verifier (auto-generated from
 * ZKSepProof.circom + the trusted setup ceremony's .zkey) and adds
 * the load-bearing pre-condition that the BIOMETRIC-SNAPSHOT-v1
 * commitment referenced in the proof's public inputs is anchored
 * on AdjudicationRegistry.
 *
 * Why this wrapper exists (vs calling Groth16 verifier directly):
 *   The Groth16 verifier proves the witness (centroids, cov_inv,
 *   feature_vector) is internally consistent — the witness centroids
 *   produce the public-input feature_commitment, the witness vector
 *   is closer to centroids[claimed_id] than to other centroids per
 *   the separation threshold, etc.
 *
 *   But Groth16 alone does NOT prove the witness centroids match the
 *   AIT corpus that operators have committed to.  A malicious bridge
 *   could fabricate centroids that satisfy the inequality but
 *   represent no real player profile.
 *
 *   This wrapper closes that hole by requiring the snapshot_hash in
 *   the public inputs (lo, hi halves) is recorded on
 *   AdjudicationRegistry — meaning some bridge committed to those
 *   exact centroids on-chain via anchor_biometric_snapshot() and
 *   the commitment can be cryptographically verified against the
 *   centroid bytes off-chain.
 *
 * Public input order (FROZEN — must match ZKSepProof.circom main declaration):
 *   [0] biometricSnapshotHashLo  — uint256 holding low 128 bits of snapshot
 *   [1] biometricSnapshotHashHi  — uint256 holding high 128 bits
 *   [2] claimedPlayerId          — uint256 in [0, N_PLAYERS)
 *   [3] featureCommitment        — Poseidon(witness || claimedPlayerId)
 *   [4] separationThresholdMilli — uint256 (e.g. 1000 = ratio ≥ 1.0)
 *   [5] inferenceCode            — uint256 in [0, 255]
 *
 * Snapshot hash reconstruction:
 *   bytes32 snapshotHash = bytes32((hi << 128) | lo)
 *
 *   The split is a circuit-side accommodation: BN254 scalar field is
 *   ~254 bits, so a 256-bit SHA-256 digest cannot fit in one field
 *   element. Splitting into 128-bit halves preserves the hash bytes
 *   bit-for-bit while staying within field bounds.
 *
 * @dev DEPLOYMENT NOTE — Two-stage deploy:
 *   Stage 1 (post-ceremony): operator runs run-mpc-ceremony.js with
 *     circuit name "ZKSepProof" producing
 *     ZKSepProof_verification_key.json + ZKSepProof_final.zkey.
 *     snarkjs zkey export solidityverifier ./ZKSepProof_final.zkey
 *     ./Groth16VerifierZKSepProof.sol generates the inner verifier.
 *   Stage 2: deploy Groth16VerifierZKSepProof.sol → record address.
 *     Then deploy this contract with (groth16Address, adjudicationAddress).
 *
 *   Until Stage 1 completes, this contract cannot be deployed (the
 *   inner verifier address would be address(0) — explicitly rejected).
 */

interface IZKSepProofGroth16Verifier {
    function verifyProof(
        uint256[2] memory a,
        uint256[2][2] memory b,
        uint256[2] memory c,
        uint256[6] memory input
    ) external view returns (bool);
}

interface IAdjudicationRegistry {
    function isRecorded(bytes32 poadHash) external view returns (bool);
}

contract ZKSepProofVerifier {
    /// @notice Immutable Groth16 verifier (snarkjs-generated from ZKSepProof.circom + ceremony zkey)
    address public immutable groth16Verifier;

    /// @notice Immutable AdjudicationRegistry — pre-condition source for snapshot anchor
    address public immutable adjudicationRegistry;

    /// @notice Emitted on every successful verifyAndCheckSnapshot call.
    event SepProofAccepted(
        bytes32 indexed snapshotHash,
        uint256 indexed claimedPlayerId,
        uint256 separationThresholdMilli,
        uint256 inferenceCode
    );

    constructor(address _groth16Verifier, address _adjudicationRegistry) {
        require(_groth16Verifier != address(0), "ZKSepProof: groth16 verifier zero");
        require(_adjudicationRegistry != address(0), "ZKSepProof: adjudication registry zero");
        groth16Verifier = _groth16Verifier;
        adjudicationRegistry = _adjudicationRegistry;
    }

    /**
     * @notice Verify a ZK-SEPPROOF proof and check its snapshot is anchored.
     *
     * @param a              Groth16 proof element a
     * @param b              Groth16 proof element b
     * @param c              Groth16 proof element c
     * @param publicInputs   6 public inputs in the canonical order (see contract docstring)
     * @return verified      True if the proof is valid AND the snapshot is anchored
     *
     * Reverts:
     *   "snapshot not anchored" — biometricSnapshotHash is not in AdjudicationRegistry
     *   (Groth16 verification failure returns false rather than revert — matches
     *   snarkjs-generated verifier convention)
     */
    function verifyAndCheckSnapshot(
        uint256[2] calldata a,
        uint256[2][2] calldata b,
        uint256[2] calldata c,
        uint256[6] calldata publicInputs
    ) external returns (bool verified) {
        // Reconstruct the 256-bit snapshot hash from its 128-bit halves.
        // Circuit splits because BN254 scalar field is ~254 bits.
        bytes32 snapshotHash = bytes32(
            (publicInputs[1] << 128) | publicInputs[0]
        );

        // Load-bearing pre-condition: snapshot must be anchored on AdjudicationRegistry.
        // Without this check, the Groth16 verifier alone cannot prove the witness
        // centroids represent any real corpus state.
        require(
            IAdjudicationRegistry(adjudicationRegistry).isRecorded(snapshotHash),
            "ZKSepProof: snapshot not anchored"
        );

        // Forward to inner Groth16 verifier with the 6-element public input array.
        verified = IZKSepProofGroth16Verifier(groth16Verifier).verifyProof(a, b, c, publicInputs);

        if (verified) {
            emit SepProofAccepted(
                snapshotHash,
                publicInputs[2],   // claimedPlayerId
                publicInputs[4],   // separationThresholdMilli
                publicInputs[5]    // inferenceCode
            );
        }
    }

    /**
     * @notice Pure view variant — same logic as verifyAndCheckSnapshot but without
     *         emitting the SepProofAccepted event.  Useful for off-chain dry-run
     *         (eth_call against this method costs zero gas).
     */
    function verifyAndCheckSnapshotView(
        uint256[2] calldata a,
        uint256[2][2] calldata b,
        uint256[2] calldata c,
        uint256[6] calldata publicInputs
    ) external view returns (bool verified) {
        bytes32 snapshotHash = bytes32(
            (publicInputs[1] << 128) | publicInputs[0]
        );
        require(
            IAdjudicationRegistry(adjudicationRegistry).isRecorded(snapshotHash),
            "ZKSepProof: snapshot not anchored"
        );
        verified = IZKSepProofGroth16Verifier(groth16Verifier).verifyProof(a, b, c, publicInputs);
    }
}
