// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/utils/ReentrancyGuard.sol";
import "@openzeppelin/contracts/access/Ownable.sol";

/// @dev Minimal token interface — avoids full IERC20 import; matches VAPIToken.sol
interface IVAPIToken {
    function transferFrom(address from, address to, uint256 amount) external returns (bool);
    function transfer(address to, uint256 amount) external returns (bool);
    function burn(uint256 amount) external;
    function balanceOf(address account) external view returns (uint256);
}

/**
 * @title VAPIOperatorRegistry — Phase 99A Operator Staking & Slashing
 * @notice Bridge operators stake VAPI tokens to earn the right to run the
 *         13-agent VAPI enforcement fleet. Slashing creates cryptographic
 *         accountability for false-positive enforcement actions.
 *
 * Economics:
 *   - MINIMUM_STAKE: 10,000 VAPI (~$X at TGE)
 *   - SLASH: 50% burned / 50% sent to slash caller (claimant)
 *   - DEREGISTER: 30-day cooldown after requestDeregister()
 *
 * Security:
 *   - All state-mutating functions follow CEI (Checks → Effects → Interactions)
 *   - ReentrancyGuard on stake/slash/deregister
 *   - onlyOwner for slash (bridge operator key, covered by VAPIGovernanceTimelock)
 *
 * Token interface is minimal (transferFrom/transfer/burn) — no IERC20 import
 * to avoid circular dependency concerns. Token is VAPIToken.sol.
 */
contract VAPIOperatorRegistry is ReentrancyGuard, Ownable {
    uint256 public constant MINIMUM_STAKE = 10_000 * 1e18;     // 10,000 VAPI
    uint256 public constant DEREGISTER_COOLDOWN = 30 days;
    uint256 public constant SLASH_BURN_PCT = 50;                // 50% burned

    struct OperatorStake {
        uint256 amount;
        uint256 stakedAt;
        uint256 deregisterRequestedAt; // 0 = no pending deregister request
        bool active;
    }

    IVAPIToken public immutable vapiToken;
    mapping(address => OperatorStake) public stakes;

    event OperatorRegistered(address indexed operator, uint256 amount, uint256 timestamp);
    event OperatorSlashed(
        address indexed operator,
        uint256 burnAmount,
        uint256 claimAmount,
        string reason
    );
    event DeregisterRequested(address indexed operator, uint256 unlockAt);
    event OperatorDeregistered(address indexed operator, uint256 amount);

    constructor(address tokenAddress, address initialOwner)
        Ownable(initialOwner)
    {
        require(tokenAddress != address(0), "VAPIOperatorRegistry: zero token address");
        vapiToken = IVAPIToken(tokenAddress);
    }

    /**
     * @notice Register as a VAPI bridge operator by staking MINIMUM_STAKE VAPI.
     * @dev Caller must first approve this contract for MINIMUM_STAKE on VAPIToken.
     *      CEI: checks first, state update, then external call.
     */
    function registerOperator() external nonReentrant {
        require(!stakes[msg.sender].active, "VAPIOperatorRegistry: already registered");

        // Effects before interactions (CEI)
        stakes[msg.sender] = OperatorStake({
            amount: MINIMUM_STAKE,
            stakedAt: block.timestamp,
            deregisterRequestedAt: 0,
            active: true
        });

        // Interaction last
        vapiToken.transferFrom(msg.sender, address(this), MINIMUM_STAKE);

        emit OperatorRegistered(msg.sender, MINIMUM_STAKE, block.timestamp);
    }

    /**
     * @notice Slash an operator for enforcement misconduct.
     * @dev Burns 50% of stake; sends 50% to caller (claimant = owner/DAO).
     *      CEI: state deleted before external token calls.
     */
    function slash(address operator, string calldata reason)
        external
        onlyOwner
        nonReentrant
    {
        require(stakes[operator].active, "VAPIOperatorRegistry: operator not active");

        uint256 stakeAmount = stakes[operator].amount;
        uint256 burnAmt = (stakeAmount * SLASH_BURN_PCT) / 100;
        uint256 claimAmt = stakeAmount - burnAmt;

        // Effects: clear state before external calls (CEI)
        delete stakes[operator];

        // Interactions: external token calls after state cleared
        vapiToken.transfer(address(this), burnAmt); // move to self, then burn
        vapiToken.burn(burnAmt);                    // burn caller's own balance
        vapiToken.transfer(msg.sender, claimAmt);

        emit OperatorSlashed(operator, burnAmt, claimAmt, reason);
    }

    /**
     * @notice Initiate the 30-day deregister cooldown window.
     */
    function requestDeregister() external {
        require(stakes[msg.sender].active, "VAPIOperatorRegistry: not registered");
        require(
            stakes[msg.sender].deregisterRequestedAt == 0,
            "VAPIOperatorRegistry: deregister already requested"
        );
        stakes[msg.sender].deregisterRequestedAt = block.timestamp;
        emit DeregisterRequested(
            msg.sender,
            block.timestamp + DEREGISTER_COOLDOWN
        );
    }

    /**
     * @notice Complete deregistration after 30-day cooldown elapses.
     */
    function executeDeregister() external nonReentrant {
        OperatorStake memory s = stakes[msg.sender];
        require(s.active, "VAPIOperatorRegistry: not registered");
        require(
            s.deregisterRequestedAt > 0,
            "VAPIOperatorRegistry: no deregister request"
        );
        require(
            block.timestamp >= s.deregisterRequestedAt + DEREGISTER_COOLDOWN,
            "VAPIOperatorRegistry: cooldown not elapsed"
        );

        uint256 amount = s.amount;

        // CEI: clear state before transfer
        delete stakes[msg.sender];

        vapiToken.transfer(msg.sender, amount);

        emit OperatorDeregistered(msg.sender, amount);
    }

    /**
     * @notice Returns true if the address is an active registered operator.
     */
    function isOperator(address operator) external view returns (bool) {
        return stakes[operator].active;
    }
}
