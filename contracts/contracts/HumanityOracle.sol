// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * @title HumanityOracle — Phase 69 VAPI Native Oracle
 * @notice On-chain oracle publishing verified humanity verdicts per device.
 *
 * Written by DataCuratorAgent (bridge operator) after each PITL cognition cycle.
 * Readable by any tournament contract on IoTeX — no auth required for reads.
 *
 * humanityPct is scaled ×10 for precision (e.g. 875 = 87.5%).
 * l4DistanceX1000 is the Mahalanobis L4 distance ×1000 (e.g. 7009 = 7.009 threshold).
 * inferenceCode matches PITL inference code enum (0x20 NOMINAL, 0x30 BIOMETRIC_ANOMALY, etc).
 *
 * The operator (bridge wallet) is the only address allowed to update verdicts.
 * Anyone may read.
 */
contract HumanityOracle {

    struct HumanityVerdict {
        uint8  inferenceCode;      // PITL inference code (0x20 NOMINAL, etc.)
        uint16 humanityPct;        // 0–1000 (scaled ×10; 1000 = 100.0%)
        uint32 l4DistanceX1000;    // L4 Mahalanobis ×1000
        uint32 l5CvX1000;          // L5 CV ×1000 (coefficient of variation)
        uint32 lastUpdateBlock;    // IoTeX block of last update
        uint64 lastUpdateTime;     // unix seconds of last update
    }

    address public operator;

    /// deviceId (bytes32 = keccak256(pubkey)) => latest verdict
    mapping(bytes32 => HumanityVerdict) private verdicts;

    /// deviceId => total update count (audit trail)
    mapping(bytes32 => uint256) public updateCount;

    // -----------------------------------------------------------------------
    // Events
    // -----------------------------------------------------------------------

    event VerdictUpdated(
        bytes32 indexed deviceId,
        uint8   inferenceCode,
        uint16  humanityPct,
        uint32  l4DistanceX1000,
        uint32  lastUpdateBlock
    );

    event OperatorTransferred(address indexed oldOperator, address indexed newOperator);

    // -----------------------------------------------------------------------
    // Modifiers
    // -----------------------------------------------------------------------

    modifier onlyOperator() {
        require(msg.sender == operator, "HumanityOracle: unauthorized");
        _;
    }

    // -----------------------------------------------------------------------
    // Constructor
    // -----------------------------------------------------------------------

    constructor(address _operator) {
        require(_operator != address(0), "HumanityOracle: zero operator");
        operator = _operator;
    }

    // -----------------------------------------------------------------------
    // Write (operator only)
    // -----------------------------------------------------------------------

    /**
     * @notice Publish a humanity verdict for a device.
     * @param deviceId         keccak256(pubkey) padded to bytes32
     * @param inferenceCode    PITL inference code (0x20 = NOMINAL, 0x30 = BIOMETRIC_ANOMALY, etc.)
     * @param humanityPct      humanity_probability × 10 (0–1000)
     * @param l4DistanceX1000  L4 Mahalanobis distance × 1000
     * @param l5CvX1000        L5 coefficient of variation × 1000
     */
    function updateVerdict(
        bytes32 deviceId,
        uint8   inferenceCode,
        uint16  humanityPct,
        uint32  l4DistanceX1000,
        uint32  l5CvX1000
    ) external onlyOperator {
        require(deviceId != bytes32(0), "HumanityOracle: zero device");
        require(humanityPct <= 1000, "HumanityOracle: pct overflow");
        verdicts[deviceId] = HumanityVerdict({
            inferenceCode:     inferenceCode,
            humanityPct:       humanityPct,
            l4DistanceX1000:   l4DistanceX1000,
            l5CvX1000:         l5CvX1000,
            lastUpdateBlock:   uint32(block.number),
            lastUpdateTime:    uint64(block.timestamp)
        });
        updateCount[deviceId]++;
        emit VerdictUpdated(deviceId, inferenceCode, humanityPct, l4DistanceX1000, uint32(block.number));
    }

    // -----------------------------------------------------------------------
    // Read (public — any tournament contract may query)
    // -----------------------------------------------------------------------

    /**
     * @notice Get the latest humanity verdict for a device.
     * @param deviceId keccak256(pubkey) padded to bytes32
     * @return verdict HumanityVerdict struct
     */
    function getHumanityVerdict(bytes32 deviceId) external view returns (HumanityVerdict memory verdict) {
        return verdicts[deviceId];
    }

    /**
     * @notice Convenience: is this device NOMINAL (inferenceCode == 0x20)?
     * @param deviceId keccak256(pubkey) padded to bytes32
     */
    function isNominal(bytes32 deviceId) external view returns (bool) {
        return verdicts[deviceId].inferenceCode == 0x20;
    }

    /**
     * @notice Convenience: humanity score as a fraction (0–1000, scaled ×10).
     */
    function getHumanityPct(bytes32 deviceId) external view returns (uint16) {
        return verdicts[deviceId].humanityPct;
    }

    // -----------------------------------------------------------------------
    // Admin
    // -----------------------------------------------------------------------

    function setOperator(address _operator) external onlyOperator {
        require(_operator != address(0), "HumanityOracle: zero operator");
        emit OperatorTransferred(operator, _operator);
        operator = _operator;
    }
}
