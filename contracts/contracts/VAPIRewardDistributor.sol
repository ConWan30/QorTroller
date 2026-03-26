// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * @title VAPIRewardDistributor — Phase 69 VAPI DePIN Token Distribution
 * @notice Device-gated DePIN token distributor for verified DualShock Edge owners.
 *
 * DePIN model:
 *   Physical node:       DualShock Edge CFI-ZCP1
 *   Proof of work:       PoAC 228B record with NOMINAL inference (0x20)
 *   Reward eligibility:  On-chain oracle state (HumanityOracle + RulingOracle + PassportOracle)
 *   Token:               ERC20 — injected via setRewardToken (token-agnostic)
 *
 * Device-gated (NOT player-gated) until inter-person separation ratio > 1.0.
 * Current ratio: 0.362 — documented §8.6. Hardware recapture required to upgrade.
 *
 * Reward multipliers (stacking):
 *   Base NOMINAL session:         1.0× (10 points per session)
 *   ZK passport on-chain:         1.5× boost
 *   Enrollment complete (≥10):    2.0× boost
 *   Clean streak (5× NOMINAL):    2.5× boost
 *   MPC ceremony device:          1.25× boost
 *   Tournament gate cleared:      3.0× boost
 *
 * Anti-gaming:
 *   - No farming: only NOMINAL (0x20) sessions count
 *   - No replay: RulingRegistry anti-replay prevents double-counting
 *   - No Sybil: device_id = keccak256(hardware ECDSA pubkey)
 *   - No soft wallets: cannot generate device_id without physical controller
 *
 * The operator (bridge wallet) updates device state via updateDeviceState().
 * Claim is pull-model: device owner calls claimReward(device_id, wallet).
 */
interface IERC20 {
    function transfer(address to, uint256 amount) external returns (bool);
    function balanceOf(address account) external view returns (uint256);
}

contract VAPIRewardDistributor {

    // -----------------------------------------------------------------------
    // Constants
    // -----------------------------------------------------------------------

    uint256 public constant BASE_POINTS_PER_SESSION = 10;   // 10 reward points per NOMINAL session
    uint256 public constant POINTS_PER_TOKEN        = 100;  // 100 points = 1 token unit (adjustable)

    // Multiplier denominators (stored as ×100 for integer math)
    // e.g. 150 = 1.5×, 200 = 2.0×
    uint16 public constant MULT_PASSPORT    = 150;   // 1.5×
    uint16 public constant MULT_ENROLLMENT  = 200;   // 2.0×
    uint16 public constant MULT_CLEAN_STREAK= 250;   // 2.5×
    uint16 public constant MULT_MPC_VERIFIED= 125;   // 1.25×
    uint16 public constant MULT_GATE_CLEARED= 300;   // 3.0×

    // -----------------------------------------------------------------------
    // Types
    // -----------------------------------------------------------------------

    struct DeviceRewardState {
        uint256 totalNominalSessions;   // lifetime NOMINAL sessions (0x20)
        uint256 accumulatedPoints;      // unclaimed reward points
        uint256 lastRewardBlock;        // block of last state update
        uint64  lastRewardTime;         // unix seconds of last state update
        bool    passportHeld;           // ZK passport verified on-chain
        bool    enrollmentComplete;     // ≥10 NOMINAL sessions reached
        bool    mpcVerified;            // device used MPC-ceremony-verified circuit
        bool    gatePassed;             // TournamentGate cleared
        uint32  cleanStreak;            // consecutive NOMINAL sessions without flags
        address rewardAddress;          // wallet to receive tokens (set by operator per device)
    }

    // -----------------------------------------------------------------------
    // State
    // -----------------------------------------------------------------------

    address public operator;
    address public rewardToken;         // ERC20 token address (set after deploy)

    /// deviceId => reward state
    mapping(bytes32 => DeviceRewardState) public deviceState;

    /// deviceId => total tokens claimed (lifetime)
    mapping(bytes32 => uint256) public totalClaimed;

    // -----------------------------------------------------------------------
    // Events
    // -----------------------------------------------------------------------

    event DeviceStateUpdated(
        bytes32 indexed deviceId,
        uint256 totalNominalSessions,
        uint256 accumulatedPoints,
        uint32  cleanStreak
    );

    event RewardClaimed(
        bytes32 indexed deviceId,
        address indexed rewardAddress,
        uint256 tokenAmount,
        uint256 pointsConsumed
    );

    event RewardTokenSet(address indexed token);
    event RewardAddressSet(bytes32 indexed deviceId, address indexed rewardAddress);
    event OperatorTransferred(address indexed oldOperator, address indexed newOperator);

    // -----------------------------------------------------------------------
    // Modifiers
    // -----------------------------------------------------------------------

    modifier onlyOperator() {
        require(msg.sender == operator, "VAPIRewardDistributor: unauthorized");
        _;
    }

    // -----------------------------------------------------------------------
    // Constructor
    // -----------------------------------------------------------------------

    constructor(address _operator) {
        require(_operator != address(0), "VAPIRewardDistributor: zero operator");
        operator = _operator;
    }

    // -----------------------------------------------------------------------
    // Operator — State Updates
    // -----------------------------------------------------------------------

    /**
     * @notice Update a device's reward-eligibility state after a NOMINAL session.
     *         Called by DataCuratorAgent via bridge operator wallet.
     * @param deviceId             keccak256(pubkey) padded to bytes32
     * @param nominalSessionsDelta Additional NOMINAL sessions in this update batch
     * @param passportHeld         Does the device hold a ZK passport?
     * @param enrollmentComplete   Has the device completed enrollment (≥10 NOMINAL)?
     * @param mpcVerified          Was this session produced under an MPC-verified circuit?
     * @param gatePassed           Has the device cleared TournamentGate?
     * @param cleanStreakNow       Current clean streak count
     */
    function updateDeviceState(
        bytes32 deviceId,
        uint256 nominalSessionsDelta,
        bool    passportHeld,
        bool    enrollmentComplete,
        bool    mpcVerified,
        bool    gatePassed,
        uint32  cleanStreakNow
    ) external onlyOperator {
        require(deviceId != bytes32(0), "VAPIRewardDistributor: zero device");
        DeviceRewardState storage s = deviceState[deviceId];

        s.totalNominalSessions += nominalSessionsDelta;
        s.passportHeld          = passportHeld;
        s.enrollmentComplete    = enrollmentComplete;
        s.mpcVerified           = mpcVerified;
        s.gatePassed            = gatePassed;
        s.cleanStreak           = cleanStreakNow;
        s.lastRewardBlock       = block.number;
        s.lastRewardTime        = uint64(block.timestamp);

        // Compute points earned for this update
        if (nominalSessionsDelta > 0) {
            uint256 rawPoints  = nominalSessionsDelta * BASE_POINTS_PER_SESSION;
            uint256 multiplier = _computeMultiplier(s);
            uint256 earned     = (rawPoints * multiplier) / 100;
            s.accumulatedPoints += earned;
        }

        emit DeviceStateUpdated(deviceId, s.totalNominalSessions, s.accumulatedPoints, cleanStreakNow);
    }

    /**
     * @notice Set the wallet address that receives rewards for a specific device.
     *         Must be called by operator (bridge verifies device ownership via PoAC chain).
     */
    function setRewardAddress(bytes32 deviceId, address rewardAddress) external onlyOperator {
        require(rewardAddress != address(0), "VAPIRewardDistributor: zero address");
        deviceState[deviceId].rewardAddress = rewardAddress;
        emit RewardAddressSet(deviceId, rewardAddress);
    }

    // -----------------------------------------------------------------------
    // Claim (pull model)
    // -----------------------------------------------------------------------

    /**
     * @notice Claim accumulated reward tokens for a device.
     *         Sends to the registered rewardAddress for this device.
     * @param deviceId Device to claim for
     */
    function claimReward(bytes32 deviceId) external {
        require(rewardToken != address(0), "VAPIRewardDistributor: token not set");
        DeviceRewardState storage s = deviceState[deviceId];
        require(s.rewardAddress != address(0), "VAPIRewardDistributor: no reward address");
        require(msg.sender == s.rewardAddress || msg.sender == operator,
                "VAPIRewardDistributor: unauthorized claim");
        require(s.accumulatedPoints >= POINTS_PER_TOKEN, "VAPIRewardDistributor: insufficient points");

        uint256 tokens  = s.accumulatedPoints / POINTS_PER_TOKEN;
        uint256 consumed = tokens * POINTS_PER_TOKEN;
        s.accumulatedPoints -= consumed;
        totalClaimed[deviceId] += tokens;

        require(
            IERC20(rewardToken).transfer(s.rewardAddress, tokens),
            "VAPIRewardDistributor: transfer failed"
        );
        emit RewardClaimed(deviceId, s.rewardAddress, tokens, consumed);
    }

    // -----------------------------------------------------------------------
    // View — Reward Calculation
    // -----------------------------------------------------------------------

    /**
     * @notice Preview the current multiplier for a device (×100 integer, 100 = 1.0×).
     */
    function getMultiplier(bytes32 deviceId) external view returns (uint256) {
        return _computeMultiplier(deviceState[deviceId]);
    }

    /**
     * @notice Full reward breakdown for a device.
     * @return totalSessions   Lifetime NOMINAL sessions
     * @return accPoints       Accumulated unclaimed points
     * @return claimableTokens Tokens immediately claimable
     * @return multiplierX100  Current combined multiplier (×100)
     * @return cleanStreak     Current clean-streak count
     */
    function getRewardBreakdown(bytes32 deviceId) external view returns (
        uint256 totalSessions,
        uint256 accPoints,
        uint256 claimableTokens,
        uint256 multiplierX100,
        uint32  cleanStreak
    ) {
        DeviceRewardState storage s = deviceState[deviceId];
        return (
            s.totalNominalSessions,
            s.accumulatedPoints,
            s.accumulatedPoints / POINTS_PER_TOKEN,
            _computeMultiplier(s),
            s.cleanStreak
        );
    }

    // -----------------------------------------------------------------------
    // Admin
    // -----------------------------------------------------------------------

    function setRewardToken(address token) external onlyOperator {
        require(token != address(0), "VAPIRewardDistributor: zero token");
        rewardToken = token;
        emit RewardTokenSet(token);
    }

    function setOperator(address _operator) external onlyOperator {
        require(_operator != address(0), "VAPIRewardDistributor: zero operator");
        emit OperatorTransferred(operator, _operator);
        operator = _operator;
    }

    // -----------------------------------------------------------------------
    // Internal
    // -----------------------------------------------------------------------

    /**
     * @dev Compute combined multiplier (×100 integer) from device state flags.
     *      Multipliers stack multiplicatively.
     *      Base = 100 (1.0×).
     */
    function _computeMultiplier(DeviceRewardState storage s) internal view returns (uint256) {
        uint256 m = 100; // 1.0× base
        if (s.passportHeld)       m = (m * MULT_PASSPORT)     / 100;  // ×1.5
        if (s.enrollmentComplete) m = (m * MULT_ENROLLMENT)   / 100;  // ×2.0
        if (s.cleanStreak >= 5)   m = (m * MULT_CLEAN_STREAK) / 100;  // ×2.5
        if (s.mpcVerified)        m = (m * MULT_MPC_VERIFIED)  / 100; // ×1.25
        if (s.gatePassed)         m = (m * MULT_GATE_CLEARED)  / 100; // ×3.0
        return m;
    }
}
