// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * @title RulingRegistry — Phase 66 VAPI Ruling Enforcement Pipeline
 * @notice Stores autonomous agent ruling commitment_hashes on-chain.
 *
 * commitment_hash = SHA-256(verdict + sorted(evidence_hashes) + attestation_hash + ts_ns)
 * This is the same hash produced by sdk/vapi_agent.py and bridge/vapi_bridge/session_adjudicator.py.
 * SDKAttestation is included as trust anchor — no ruling can be forged or replayed.
 *
 * Anti-replay: each commitment_hash may only be recorded once (revert on duplicate).
 * Per-device history: deviceRulings[deviceId] holds all commitment_hashes in order.
 * Only the authorized operator (bridge wallet) may call recordRuling.
 */
contract RulingRegistry {

    enum Verdict { FLAG, HOLD, BLOCK, CERTIFY, CLEAR }

    struct Ruling {
        bytes32 commitmentHash;
        Verdict verdict;
        uint16  confidence1000;    // confidence * 1000 (0–1000)
        uint64  timestamp;         // unix seconds
        address submittedBy;
    }

    /// commitment_hash => Ruling (anti-replay: each hash stored at most once)
    mapping(bytes32 => Ruling) public rulings;

    /// device_id (bytes32) => ordered list of commitment_hashes
    mapping(bytes32 => bytes32[]) public deviceRulings;

    address public operator;

    event RulingRecorded(
        bytes32 indexed commitmentHash,
        bytes32 indexed deviceId,
        Verdict verdict,
        uint16 confidence1000,
        uint64 timestamp
    );

    event OperatorTransferred(address indexed oldOperator, address indexed newOperator);

    modifier onlyOperator() {
        require(msg.sender == operator, "RulingRegistry: unauthorized");
        _;
    }

    constructor(address _operator) {
        require(_operator != address(0), "RulingRegistry: zero operator");
        operator = _operator;
    }

    /**
     * @notice Record an autonomous agent ruling commitment on-chain.
     * @param commitmentHash SHA-256(verdict+evidence+attestation+ts_ns) from bridge
     * @param deviceId       keccak256(pubkey) padded to bytes32
     * @param verdict        Verdict enum value
     * @param confidence1000 confidence * 1000 (0–1000)
     * @param timestamp      unix seconds at ruling time
     */
    function recordRuling(
        bytes32 commitmentHash,
        bytes32 deviceId,
        Verdict verdict,
        uint16  confidence1000,
        uint64  timestamp
    ) external onlyOperator {
        require(rulings[commitmentHash].timestamp == 0, "RulingRegistry: already recorded");
        rulings[commitmentHash] = Ruling({
            commitmentHash: commitmentHash,
            verdict:        verdict,
            confidence1000: confidence1000,
            timestamp:      timestamp,
            submittedBy:    msg.sender
        });
        deviceRulings[deviceId].push(commitmentHash);
        emit RulingRecorded(commitmentHash, deviceId, verdict, confidence1000, timestamp);
    }

    /**
     * @notice Get the most recent ruling for a device.
     * @param deviceId bytes32 device identifier
     */
    function getLatestRuling(bytes32 deviceId) external view returns (Ruling memory) {
        bytes32[] storage hashes = deviceRulings[deviceId];
        require(hashes.length > 0, "RulingRegistry: no rulings for device");
        return rulings[hashes[hashes.length - 1]];
    }

    /**
     * @notice Get the total number of rulings recorded for a device.
     * @param deviceId bytes32 device identifier
     */
    function getRulingCount(bytes32 deviceId) external view returns (uint256) {
        return deviceRulings[deviceId].length;
    }

    /**
     * @notice Transfer operator role to a new address.
     * @param _operator New operator address
     */
    function setOperator(address _operator) external onlyOperator {
        require(_operator != address(0), "RulingRegistry: zero operator");
        emit OperatorTransferred(operator, _operator);
        operator = _operator;
    }
}
