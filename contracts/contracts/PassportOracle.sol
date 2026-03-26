// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * @title PassportOracle — Phase 69 VAPI Native Oracle
 * @notice On-chain oracle wrapping PITLTournamentPassport state for external consumption.
 *
 * Exposes passport issuance status, session count, and on-chain validation flag
 * per device — queryable by any tournament contract on IoTeX.
 *
 * The DataCuratorAgent writes after each EnrollmentManager cycle.
 * Anyone may read (no auth required).
 *
 * Passport issuance requires ≥10 NOMINAL sessions (enrollment_min_sessions).
 * onChain = true means the ZK proof has been verified by TournamentPassportVerifier.sol.
 */
contract PassportOracle {

    struct PassportState {
        bool    issued;           // has a passport been generated?
        bool    onChain;          // is it verified on-chain (ZK proof accepted)?
        bytes32 passportHash;     // keccak256(passport payload) — matches PITLTournamentPassport
        uint32  sessionCount;     // total NOMINAL sessions contributing to this passport
        uint32  lastUpdateBlock;  // IoTeX block of last update
        uint64  issuedAt;         // unix seconds of passport issuance
    }

    address public operator;

    /// deviceId => passport state
    mapping(bytes32 => PassportState) private passports;

    /// deviceId => update count (audit)
    mapping(bytes32 => uint256) public updateCount;

    // -----------------------------------------------------------------------
    // Events
    // -----------------------------------------------------------------------

    event PassportStateUpdated(
        bytes32 indexed deviceId,
        bool    issued,
        bool    onChain,
        bytes32 passportHash,
        uint32  sessionCount
    );

    event OperatorTransferred(address indexed oldOperator, address indexed newOperator);

    // -----------------------------------------------------------------------
    // Modifiers
    // -----------------------------------------------------------------------

    modifier onlyOperator() {
        require(msg.sender == operator, "PassportOracle: unauthorized");
        _;
    }

    // -----------------------------------------------------------------------
    // Constructor
    // -----------------------------------------------------------------------

    constructor(address _operator) {
        require(_operator != address(0), "PassportOracle: zero operator");
        operator = _operator;
    }

    // -----------------------------------------------------------------------
    // Write (operator only)
    // -----------------------------------------------------------------------

    /**
     * @notice Update passport state for a device.
     * @param deviceId     keccak256(pubkey) padded to bytes32
     * @param issued       Has a passport been generated?
     * @param onChain      Has the ZK proof been accepted on-chain?
     * @param passportHash keccak256(passport payload)
     * @param sessionCount Total NOMINAL sessions used for this passport
     */
    function updatePassportState(
        bytes32 deviceId,
        bool    issued,
        bool    onChain,
        bytes32 passportHash,
        uint32  sessionCount
    ) external onlyOperator {
        require(deviceId != bytes32(0), "PassportOracle: zero device");
        uint64 issuedAt = passports[deviceId].issuedAt;
        if (issued && issuedAt == 0) {
            issuedAt = uint64(block.timestamp);
        }
        passports[deviceId] = PassportState({
            issued:          issued,
            onChain:         onChain,
            passportHash:    passportHash,
            sessionCount:    sessionCount,
            lastUpdateBlock: uint32(block.number),
            issuedAt:        issuedAt
        });
        updateCount[deviceId]++;
        emit PassportStateUpdated(deviceId, issued, onChain, passportHash, sessionCount);
    }

    // -----------------------------------------------------------------------
    // Read (public)
    // -----------------------------------------------------------------------

    /**
     * @notice Get the full passport state for a device.
     */
    function getPassportState(bytes32 deviceId) external view returns (PassportState memory) {
        return passports[deviceId];
    }

    /**
     * @notice Is this device's ZK tournament passport verified on-chain?
     */
    function hasVerifiedPassport(bytes32 deviceId) external view returns (bool) {
        return passports[deviceId].issued && passports[deviceId].onChain;
    }

    /**
     * @notice How many NOMINAL sessions has this device accumulated?
     */
    function getSessionCount(bytes32 deviceId) external view returns (uint32) {
        return passports[deviceId].sessionCount;
    }

    // -----------------------------------------------------------------------
    // Admin
    // -----------------------------------------------------------------------

    function setOperator(address _operator) external onlyOperator {
        require(_operator != address(0), "PassportOracle: zero operator");
        emit OperatorTransferred(operator, _operator);
        operator = _operator;
    }
}
