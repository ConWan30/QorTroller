// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * @title FederatedThreatRegistry
 * @notice Phase 80 — On-chain threat signal registry for cross-bridge BLOCK ruling federation.
 *
 * Stores BLOCK ruling signals from the VAPI bridge fleet.
 * isThreatSignaled(deviceId) is a pure view callable by any tournament gate contract
 * without gas — same composability pattern as VAPIProtocolLens.isFullyEligible().
 *
 * Anti-replay: UNIQUE constraint on commitHash (require !active before insert).
 * Only the operator may add or revoke signals.
 *
 * Replaces Phase 34 cluster-hash reporting design with per-ruling, per-device signals
 * that align with the RulingRegistry commitment_hash format introduced in Phase 66.
 */
contract FederatedThreatRegistry {

    address public operator;

    struct ThreatSignal {
        address deviceId;       // keccak256(device_id) → address cast
        bytes32 commitHash;
        bytes32 circuitId;
        uint256 timestamp;
        bool active;
    }

    // commitHash → ThreatSignal
    mapping(bytes32 => ThreatSignal) public threatSignals;

    // deviceId (address) → count of active signals
    mapping(address => uint256) public deviceSignalCount;

    event ThreatSignalAdded(
        address indexed deviceId,
        bytes32 indexed commitHash,
        bytes32 circuitId,
        uint256 timestamp
    );

    event ThreatSignalRevoked(
        bytes32 indexed commitHash,
        address indexed deviceId
    );

    event OperatorTransferred(
        address indexed previousOperator,
        address indexed newOperator
    );

    modifier onlyOperator() {
        require(msg.sender == operator, "FederatedThreatRegistry: caller is not operator");
        _;
    }

    constructor(address _operator) {
        require(_operator != address(0), "FederatedThreatRegistry: zero operator");
        operator = _operator;
        emit OperatorTransferred(address(0), _operator);
    }

    /**
     * @notice Add a threat signal for a device.
     * @param deviceId   The device address (keccak256 of device_id string cast to address).
     * @param commitHash The commitment hash of the BLOCK ruling (unique per ruling).
     * @param circuitId  The ZK circuit identifier (SHA3-256 of circuit name).
     */
    function addThreatSignal(
        address deviceId,
        bytes32 commitHash,
        bytes32 circuitId
    ) external onlyOperator {
        require(deviceId != address(0), "FederatedThreatRegistry: zero deviceId");
        require(commitHash != bytes32(0), "FederatedThreatRegistry: zero commitHash");
        require(
            !threatSignals[commitHash].active,
            "FederatedThreatRegistry: commitHash already registered"
        );

        threatSignals[commitHash] = ThreatSignal({
            deviceId: deviceId,
            commitHash: commitHash,
            circuitId: circuitId,
            timestamp: block.timestamp,
            active: true
        });

        deviceSignalCount[deviceId] += 1;

        emit ThreatSignalAdded(deviceId, commitHash, circuitId, block.timestamp);
    }

    /**
     * @notice Revoke an existing threat signal (sets active=false).
     * @param commitHash The commitment hash to revoke.
     */
    function revokeThreatSignal(bytes32 commitHash) external onlyOperator {
        ThreatSignal storage sig = threatSignals[commitHash];
        require(sig.active, "FederatedThreatRegistry: signal not active");

        address deviceId = sig.deviceId;
        sig.active = false;

        if (deviceSignalCount[deviceId] > 0) {
            deviceSignalCount[deviceId] -= 1;
        }

        emit ThreatSignalRevoked(commitHash, deviceId);
    }

    /**
     * @notice Returns true if the device has at least one active threat signal.
     * @dev Pure view — callable by tournament gate contracts without gas cost.
     */
    function isThreatSignaled(address deviceId) external view returns (bool) {
        return deviceSignalCount[deviceId] > 0;
    }

    /**
     * @notice Returns the full ThreatSignal struct for a given commitHash.
     */
    function getThreatSignal(bytes32 commitHash)
        external
        view
        returns (ThreatSignal memory)
    {
        return threatSignals[commitHash];
    }

    /**
     * @notice Transfer operator role to a new address.
     */
    function transferOperator(address newOperator) external onlyOperator {
        require(newOperator != address(0), "FederatedThreatRegistry: zero newOperator");
        address prev = operator;
        operator = newOperator;
        emit OperatorTransferred(prev, newOperator);
    }
}
