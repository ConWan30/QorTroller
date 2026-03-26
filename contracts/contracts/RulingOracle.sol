// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * @title RulingOracle — Phase 69 VAPI Native Oracle
 * @notice On-chain oracle wrapping RulingRegistry state for external consumption.
 *
 * Exposes current suspension status, ruling streak, and last commitment hash
 * for any device — queryable by any tournament contract on IoTeX.
 *
 * The DataCuratorAgent writes oracle state after each RulingEnforcementAgent cycle.
 * Anyone may read (no auth required).
 *
 * Ruling streaks mirror RulingEnforcementAgent escalation ladder:
 *   FLAG × 5  → HOLD
 *   HOLD × 2  → BLOCK (triggers PHGCredential suspension)
 */
contract RulingOracle {

    struct RulingState {
        bool    suspended;
        uint32  flagStreak;
        uint32  holdStreak;
        uint32  lastUpdateBlock;
        uint64  suspendedUntil;    // unix seconds; 0 = not suspended
        bytes32 lastCommitmentHash; // most recent ruling commitment
    }

    address public operator;

    /// deviceId => current ruling state
    mapping(bytes32 => RulingState) private states;

    /// deviceId => total ruling events written (audit count)
    mapping(bytes32 => uint256) public eventCount;

    // -----------------------------------------------------------------------
    // Events
    // -----------------------------------------------------------------------

    event RulingStateUpdated(
        bytes32 indexed deviceId,
        bool    suspended,
        uint32  flagStreak,
        uint32  holdStreak,
        uint64  suspendedUntil
    );

    event OperatorTransferred(address indexed oldOperator, address indexed newOperator);

    // -----------------------------------------------------------------------
    // Modifiers
    // -----------------------------------------------------------------------

    modifier onlyOperator() {
        require(msg.sender == operator, "RulingOracle: unauthorized");
        _;
    }

    // -----------------------------------------------------------------------
    // Constructor
    // -----------------------------------------------------------------------

    constructor(address _operator) {
        require(_operator != address(0), "RulingOracle: zero operator");
        operator = _operator;
    }

    // -----------------------------------------------------------------------
    // Write (operator only)
    // -----------------------------------------------------------------------

    /**
     * @notice Update the ruling state for a device.
     * @param deviceId          keccak256(pubkey) padded to bytes32
     * @param suspended         Is the device currently suspended?
     * @param flagStreak        Consecutive FLAG rulings since last CLEAR
     * @param holdStreak        Consecutive HOLD rulings since last CLEAR
     * @param suspendedUntil    Unix seconds expiry of suspension (0 if not suspended)
     * @param lastCommitmentHash Most recent ruling commitment_hash from RulingRegistry
     */
    function updateRulingState(
        bytes32 deviceId,
        bool    suspended,
        uint32  flagStreak,
        uint32  holdStreak,
        uint64  suspendedUntil,
        bytes32 lastCommitmentHash
    ) external onlyOperator {
        require(deviceId != bytes32(0), "RulingOracle: zero device");
        states[deviceId] = RulingState({
            suspended:          suspended,
            flagStreak:         flagStreak,
            holdStreak:         holdStreak,
            lastUpdateBlock:    uint32(block.number),
            suspendedUntil:     suspendedUntil,
            lastCommitmentHash: lastCommitmentHash
        });
        eventCount[deviceId]++;
        emit RulingStateUpdated(deviceId, suspended, flagStreak, holdStreak, suspendedUntil);
    }

    // -----------------------------------------------------------------------
    // Read (public)
    // -----------------------------------------------------------------------

    /**
     * @notice Get the full ruling state for a device.
     */
    function getRulingState(bytes32 deviceId) external view returns (RulingState memory) {
        return states[deviceId];
    }

    /**
     * @notice Is this device currently under a BLOCK suspension?
     */
    function isSuspended(bytes32 deviceId) external view returns (bool) {
        RulingState storage s = states[deviceId];
        if (!s.suspended) return false;
        if (s.suspendedUntil != 0 && block.timestamp > s.suspendedUntil) return false;
        return true;
    }

    /**
     * @notice Is this device currently eligible (not suspended, clean streak)?
     *         Clean = flagStreak < 5 AND holdStreak < 2.
     */
    function isEligible(bytes32 deviceId) external view returns (bool) {
        RulingState storage s = states[deviceId];
        if (s.suspended && (s.suspendedUntil == 0 || block.timestamp <= s.suspendedUntil)) {
            return false;
        }
        return s.flagStreak < 5 && s.holdStreak < 2;
    }

    // -----------------------------------------------------------------------
    // Admin
    // -----------------------------------------------------------------------

    function setOperator(address _operator) external onlyOperator {
        require(_operator != address(0), "RulingOracle: zero operator");
        emit OperatorTransferred(operator, _operator);
        operator = _operator;
    }
}
