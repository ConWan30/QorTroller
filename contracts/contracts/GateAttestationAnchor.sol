// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * @title GateAttestationAnchor — Phase 84 VAPI Live Mode Gate Completion
 * @notice On-chain registry for autonomous AI fleet self-calibration proofs.
 *
 * attestation_hash = SHA-256(
 *     consecutive_clean_bytes || gate_n_bytes || divergence_rate_bytes || timestamp_ns_bytes
 * )
 * Binding formula matches bridge/vapi_bridge/adjudication_warm_up.py:compute_gate_attestation_hash()
 *
 * This is the first cryptographic proof that an AI enforcement fleet achieved
 * autonomous self-calibration — anchored to IoTeX L1.
 *
 * Anti-replay: each attestationHash may only be recorded once (revert on duplicate).
 * Only the authorized operator (bridge wallet) may call recordGateAttestation.
 */
contract GateAttestationAnchor {

    struct GateAttestation {
        bytes32 attestationHash;
        uint32  consecutiveClean;
        uint32  gateN;
        uint32  divergenceRateMillis;  // divergence_rate * 1000 (no floats on-chain)
        uint64  timestamp;             // unix seconds
        address submittedBy;
    }

    /// attestationHash => GateAttestation (anti-replay: each hash stored at most once)
    mapping(bytes32 => GateAttestation) public attestations;

    /// Ordered history of attestation hashes for getLatestAttestation()
    bytes32[] public attestationHistory;

    address public operator;

    event GateAttestationRecorded(
        bytes32 indexed attestationHash,
        uint32  consecutiveClean,
        uint32  gateN,
        uint64  timestamp
    );

    event OperatorTransferred(address indexed oldOperator, address indexed newOperator);

    modifier onlyOperator() {
        require(msg.sender == operator, "GateAttestationAnchor: unauthorized");
        _;
    }

    constructor(address _operator) {
        require(_operator != address(0), "GateAttestationAnchor: zero operator");
        operator = _operator;
    }

    /**
     * @notice Record an AI fleet gate attestation on-chain.
     * @param attestationHash  SHA-256(consecutive_clean||gate_n||divergence_rate||ts_ns) from bridge
     * @param consecutiveClean Number of consecutive clean validations at gate pass
     * @param gateN            Gate threshold (validation_gate_n config value)
     * @param divergenceRateMillis divergence_rate * 1000 (rounded, no floating point)
     * @param timestamp        Unix seconds at attestation time
     */
    function recordGateAttestation(
        bytes32 attestationHash,
        uint32  consecutiveClean,
        uint32  gateN,
        uint32  divergenceRateMillis,
        uint64  timestamp
    ) external onlyOperator {
        require(
            attestations[attestationHash].timestamp == 0,
            "GateAttestationAnchor: already recorded"
        );
        attestations[attestationHash] = GateAttestation({
            attestationHash:      attestationHash,
            consecutiveClean:     consecutiveClean,
            gateN:                gateN,
            divergenceRateMillis: divergenceRateMillis,
            timestamp:            timestamp,
            submittedBy:          msg.sender
        });
        attestationHistory.push(attestationHash);
        emit GateAttestationRecorded(attestationHash, consecutiveClean, gateN, timestamp);
    }

    /**
     * @notice Get attestation by hash.
     * @param attestationHash The attestation hash to look up
     */
    function getAttestation(bytes32 attestationHash) external view returns (GateAttestation memory) {
        return attestations[attestationHash];
    }

    /**
     * @notice Get the most recent gate attestation recorded.
     */
    function getLatestAttestation() external view returns (GateAttestation memory) {
        require(attestationHistory.length > 0, "GateAttestationAnchor: no attestations");
        return attestations[attestationHistory[attestationHistory.length - 1]];
    }

    /**
     * @notice Return total number of gate attestations recorded.
     */
    function getAttestationCount() external view returns (uint256) {
        return attestationHistory.length;
    }

    /**
     * @notice Transfer operator role to a new address.
     * @param _operator New operator address
     */
    function setOperator(address _operator) external onlyOperator {
        require(_operator != address(0), "GateAttestationAnchor: zero operator");
        emit OperatorTransferred(operator, _operator);
        operator = _operator;
    }
}
