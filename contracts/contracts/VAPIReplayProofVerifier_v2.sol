// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * @title VAPIReplayProofVerifier_v2 — Arc 6 (PoSR) wrapper
 * @notice Additive v2 verifier wrapping the snarkjs-generated Groth16 verifier
 *         for VAPIReplayProofVerifier_v2.circom + recency check against
 *         VAPITemporalBeaconRegistry (FROZEN-v1 #14).
 *
 * COEXISTS with VAPIReplayProofVerifier (Arc 5 v1) at 0x5182372d…. The v1
 * verifier stays callable for existing Arc 5 proofs; v2 verifies new PoSR-
 * bound proofs. Marketplace listings can hold either type — recency is
 * opt-in until a tournament operator requires it (Decision T3).
 *
 * Public-input layout (FROZEN — must match
 * contracts/circuits/VAPIReplayProofVerifier_v2.circom `component main
 * {public [...]}` declaration order; pinned by PV-CI INV-POSR-CIRCUIT-001):
 *
 *   [0] replayProofToken     — output
 *   [1] sanitizedTraceRoot
 *   [2] poacChainRoot
 *   [3] consentPolicyHash
 *   [4] humanityThreshold
 *   [5] vhpCommitment
 *   [6] openBeaconBlock      — PoSR
 *   [7] closeBeaconBlock     — PoSR
 *   [8] openBeaconCommitment — PoSR
 *   [9] closeBeaconCommitment — PoSR
 *
 * PROOF_TYPE = keccak256("VAPI-REPLAY-PROOF-v2") — new discriminator, NOT
 * an overload of Arc 5's INV-VHR-003. Pinned by INV-VHR-V2-001.
 *
 * @dev DEPLOYMENT — gated on the v2 trusted-setup ceremony (Arc 6 Commit 5
 *      or whenever operator fires it) + the deployed
 *      Groth16VerifierVAPIReplayProof_v2.sol address.
 */

interface IVAPIReplayProofGroth16VerifierV2 {
    function verifyProof(
        uint256[2] memory a,
        uint256[2][2] memory b,
        uint256[2] memory c,
        uint256[10] memory input
    ) external view returns (bool);
}

interface IVAPITemporalBeaconRegistry {
    function verifyBeacon(uint256 blockNumber, bytes32 claimedHash, bytes32 pqCommitment)
        external view returns (bool);
}

contract VAPIReplayProofVerifier_v2 {
    /// @notice FROZEN proof-type discriminator for PoSR-bound VHR proofs.
    /// Distinct from Arc 5's keccak256("VAPI-REPLAY-PROOF-v1"); does NOT
    /// overload that invariant.
    bytes32 public constant PROOF_TYPE = keccak256("VAPI-REPLAY-PROOF-v2");

    /// @notice publicInputs index constants — pin snarkjs declaration order.
    uint256 public constant INPUT_REPLAY_PROOF_TOKEN     = 0;
    uint256 public constant INPUT_SANITIZED_TRACE_ROOT   = 1;
    uint256 public constant INPUT_POAC_CHAIN_ROOT        = 2;
    uint256 public constant INPUT_CONSENT_POLICY_HASH    = 3;
    uint256 public constant INPUT_HUMANITY_THRESHOLD     = 4;
    uint256 public constant INPUT_VHP_COMMITMENT         = 5;
    uint256 public constant INPUT_OPEN_BEACON_BLOCK      = 6;
    uint256 public constant INPUT_CLOSE_BEACON_BLOCK     = 7;
    uint256 public constant INPUT_OPEN_BEACON_COMMITMENT = 8;
    uint256 public constant INPUT_CLOSE_BEACON_COMMITMENT = 9;

    address public immutable groth16Verifier;
    address public immutable beaconRegistry;

    event ReplayProofVerifiedV2(
        bytes32 indexed replayProofToken,
        bytes32 indexed poacChainRoot,
        bytes32 indexed consentPolicyHash,
        uint256 humanityThreshold,
        uint256 openBeaconBlock,
        uint256 closeBeaconBlock,
        bytes32 sanitizedTraceRoot,
        bytes32 vhpCommitment
    );

    error ZeroGroth16Verifier();
    error ZeroBeaconRegistry();
    error InvalidGroth16Proof();
    error OpenBeaconUnverified();
    error CloseBeaconUnverified();
    error CloseNotAfterOpen();

    constructor(address _groth16Verifier, address _beaconRegistry) {
        if (_groth16Verifier == address(0)) revert ZeroGroth16Verifier();
        if (_beaconRegistry == address(0)) revert ZeroBeaconRegistry();
        groth16Verifier = _groth16Verifier;
        beaconRegistry  = _beaconRegistry;
    }

    /**
     * @notice Verify a PoSR-bound VHR proof + check beacon hashes against the
     * temporal-beacon registry. Returns (valid, openBlock, closeBlock).
     * Reverts on any beacon mismatch / temporal-ordering violation.
     */
    function verifyWithRecency(
        uint256[2] calldata a,
        uint256[2][2] calldata b,
        uint256[2] calldata c,
        uint256[10] calldata publicInputs,
        bytes32 openBeaconHashBytes32,
        bytes32 closeBeaconHashBytes32,
        bytes32 pqCommitment
    ) external returns (bool, uint256, uint256) {
        // 1. Groth16 proof valid (in-circuit constraints include open/close
        //    commitment integrity + temporal ordering)
        bool ok = IVAPIReplayProofGroth16VerifierV2(groth16Verifier)
            .verifyProof(a, b, c, publicInputs);
        if (!ok) revert InvalidGroth16Proof();

        uint256 openBlock  = publicInputs[INPUT_OPEN_BEACON_BLOCK];
        uint256 closeBlock = publicInputs[INPUT_CLOSE_BEACON_BLOCK];

        // 2. Strict temporal ordering (the circuit also enforces this, but
        //    we double-check on-chain — defense in depth + clearer error)
        if (closeBlock <= openBlock) revert CloseNotAfterOpen();

        // 3. Beacon hashes match the registry's durable anchor — closes the
        //    loop between in-circuit Poseidon commitment and on-chain truth
        IVAPITemporalBeaconRegistry reg = IVAPITemporalBeaconRegistry(beaconRegistry);
        if (!reg.verifyBeacon(openBlock,  openBeaconHashBytes32, pqCommitment))  revert OpenBeaconUnverified();
        if (!reg.verifyBeacon(closeBlock, closeBeaconHashBytes32, pqCommitment)) revert CloseBeaconUnverified();

        emit ReplayProofVerifiedV2(
            bytes32(publicInputs[INPUT_REPLAY_PROOF_TOKEN]),
            bytes32(publicInputs[INPUT_POAC_CHAIN_ROOT]),
            bytes32(publicInputs[INPUT_CONSENT_POLICY_HASH]),
            publicInputs[INPUT_HUMANITY_THRESHOLD],
            openBlock,
            closeBlock,
            bytes32(publicInputs[INPUT_SANITIZED_TRACE_ROOT]),
            bytes32(publicInputs[INPUT_VHP_COMMITMENT])
        );
        return (true, openBlock, closeBlock);
    }

    /// @notice Pure-view variant — same logic without state-changing event.
    function verifyWithRecencyView(
        uint256[2] calldata a,
        uint256[2][2] calldata b,
        uint256[2] calldata c,
        uint256[10] calldata publicInputs,
        bytes32 openBeaconHashBytes32,
        bytes32 closeBeaconHashBytes32,
        bytes32 pqCommitment
    ) external view returns (bool) {
        bool ok = IVAPIReplayProofGroth16VerifierV2(groth16Verifier)
            .verifyProof(a, b, c, publicInputs);
        if (!ok) return false;
        uint256 openBlock  = publicInputs[INPUT_OPEN_BEACON_BLOCK];
        uint256 closeBlock = publicInputs[INPUT_CLOSE_BEACON_BLOCK];
        if (closeBlock <= openBlock) return false;
        IVAPITemporalBeaconRegistry reg = IVAPITemporalBeaconRegistry(beaconRegistry);
        if (!reg.verifyBeacon(openBlock,  openBeaconHashBytes32, pqCommitment))  return false;
        if (!reg.verifyBeacon(closeBlock, closeBeaconHashBytes32, pqCommitment)) return false;
        return true;
    }
}
