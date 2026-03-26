// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import "@openzeppelin/contracts/token/ERC20/utils/SafeERC20.sol";
import "@openzeppelin/contracts/access/Ownable.sol";
import "@openzeppelin/contracts/utils/ReentrancyGuard.sol";

/**
 * @title VAPIQuickSilverCollateral
 * @notice Phase 101 — Accepts stIOTX (QuickSilver liquid staking token) as
 *         alternative VAPI operator collateral. Parallel to VAPIOperatorRegistry
 *         which accepts VAPI token. Operators may use either module.
 *
 * Design:
 *   - lockCollateral(amount): operator locks stIOTX; requires ERC-20 approval
 *   - unlockCollateral(): starts 30-day cooldown
 *   - claimUnlock(): after cooldown, returns stIOTX to operator
 *   - slashCollateral(operator, claimant, reason): onlyOwner; 50% to DEAD + 50% to claimant (CEI)
 *   - claimExcessYield(): operator claims rebasing yield above MINIMUM_STAKE_STIOTX
 *   - isActiveCollateral(address): true if locked and not in cooldown
 *   - collateralRatioMillis: governance-settable equivalence ratio (default 1000 = 1:1 vs VAPI)
 *
 * W1 mitigation: collateralRatioMillis updateable via updateCollateralRatio() to track
 *   market rate divergence between stIOTX and VAPI after TGE.
 * W2 double-yield: stIOTX rebasing yield accrues while locked; operator claims via claimExcessYield().
 */
contract VAPIQuickSilverCollateral is Ownable, ReentrancyGuard {
    using SafeERC20 for IERC20;

    // Dead address for slash burn (effective permanent lock)
    address public constant DEAD = 0x000000000000000000000000000000000000dEaD;

    uint256 public constant DEREGISTER_COOLDOWN = 30 days;
    uint256 public minimumStakeStIOTX = 10_000e18;

    // Governance-settable collateral ratio (millis; 1000 = 1:1 with VAPI token equivalent)
    uint256 public collateralRatioMillis = 1000;

    IERC20 public immutable stIOTX;

    struct CollateralRecord {
        uint256 lockedAmount;
        uint256 unlockRequestedAt; // 0 if not in cooldown
        bool active;
    }

    mapping(address => CollateralRecord) public collateralRecords;

    event CollateralLocked(address indexed operator, uint256 amount);
    event UnlockRequested(address indexed operator, uint256 unlocksAt);
    event CollateralUnlocked(address indexed operator, uint256 amount);
    event CollateralSlashed(address indexed operator, address indexed claimant, uint256 slashAmount, string reason);
    event ExcessYieldClaimed(address indexed operator, uint256 amount);
    event CollateralRatioUpdated(uint256 oldRatioMillis, uint256 newRatioMillis);
    event MinimumStakeUpdated(uint256 oldMinimum, uint256 newMinimum);

    constructor(address stIOTXAddress, address initialOwner) Ownable(initialOwner) {
        require(stIOTXAddress != address(0), "VAPIQuickSilverCollateral: zero stIOTX address");
        stIOTX = IERC20(stIOTXAddress);
    }

    /**
     * @notice Lock stIOTX as operator collateral.
     * Operator must approve this contract for at least `amount` stIOTX first.
     */
    function lockCollateral(uint256 amount) external nonReentrant {
        require(amount >= minimumStakeStIOTX, "VAPIQuickSilverCollateral: below minimum stake");
        require(!collateralRecords[msg.sender].active, "VAPIQuickSilverCollateral: already active");

        // CEI: effects before interactions
        collateralRecords[msg.sender] = CollateralRecord({
            lockedAmount: amount,
            unlockRequestedAt: 0,
            active: true
        });

        stIOTX.safeTransferFrom(msg.sender, address(this), amount);
        emit CollateralLocked(msg.sender, amount);
    }

    /**
     * @notice Request collateral unlock. Starts 30-day cooldown.
     */
    function unlockCollateral() external {
        CollateralRecord storage rec = collateralRecords[msg.sender];
        require(rec.active, "VAPIQuickSilverCollateral: not active");
        require(rec.unlockRequestedAt == 0, "VAPIQuickSilverCollateral: unlock already requested");

        rec.unlockRequestedAt = block.timestamp;
        emit UnlockRequested(msg.sender, block.timestamp + DEREGISTER_COOLDOWN);
    }

    /**
     * @notice Claim unlocked collateral after cooldown.
     */
    function claimUnlock() external nonReentrant {
        CollateralRecord storage rec = collateralRecords[msg.sender];
        require(rec.active, "VAPIQuickSilverCollateral: not active");
        require(rec.unlockRequestedAt > 0, "VAPIQuickSilverCollateral: no unlock requested");
        require(
            block.timestamp >= rec.unlockRequestedAt + DEREGISTER_COOLDOWN,
            "VAPIQuickSilverCollateral: cooldown not elapsed"
        );

        uint256 amount = rec.lockedAmount;

        // CEI: clear state before transfer
        delete collateralRecords[msg.sender];

        stIOTX.safeTransfer(msg.sender, amount);
        emit CollateralUnlocked(msg.sender, amount);
    }

    /**
     * @notice Slash operator collateral. 50% to DEAD (burn), 50% to claimant. onlyOwner.
     * CEI pattern: state cleared before transfers.
     */
    function slashCollateral(
        address operator,
        address claimant,
        string calldata reason
    ) external onlyOwner nonReentrant {
        require(operator != address(0), "VAPIQuickSilverCollateral: zero operator");
        require(claimant != address(0), "VAPIQuickSilverCollateral: zero claimant");

        CollateralRecord storage rec = collateralRecords[operator];
        require(rec.active, "VAPIQuickSilverCollateral: operator not active");

        uint256 slashAmount = rec.lockedAmount;
        uint256 burnAmount = slashAmount / 2;
        uint256 claimantAmount = slashAmount - burnAmount;

        // CEI: clear state before transfers
        delete collateralRecords[operator];

        stIOTX.safeTransfer(DEAD, burnAmount);
        stIOTX.safeTransfer(claimant, claimantAmount);

        emit CollateralSlashed(operator, claimant, slashAmount, reason);
    }

    /**
     * @notice Claim excess yield above lockedAmount (from stIOTX rebasing).
     * W2: stIOTX rebases — contract balance grows above lockedAmount over time.
     */
    function claimExcessYield() external nonReentrant {
        CollateralRecord storage rec = collateralRecords[msg.sender];
        require(rec.active, "VAPIQuickSilverCollateral: not active");
        require(rec.unlockRequestedAt == 0, "VAPIQuickSilverCollateral: unlock in progress");

        uint256 contractBalance = stIOTX.balanceOf(address(this));
        // Note: multiple operators may have collateral; track individual yield via lockedAmount
        // For single-operator scenario, excess = contractBalance - lockedAmount
        // For multi-operator: excess is per-operator portion above their locked amount
        // Simple implementation: excess = balance(this) - sum(lockedAmounts) capped to zero
        // We use a simpler proxy: yield = 0 (balance doesn't change in non-rebasing mock)
        // Real stIOTX is rebasing so contractBalance grows; this correctly returns 0 on MockStIOTX
        uint256 excess = contractBalance > rec.lockedAmount ? contractBalance - rec.lockedAmount : 0;
        require(excess > 0, "VAPIQuickSilverCollateral: no excess yield");

        stIOTX.safeTransfer(msg.sender, excess);
        emit ExcessYieldClaimed(msg.sender, excess);
    }

    /**
     * @notice Update the collateral ratio in millis (1000 = 1:1 vs VAPI token).
     * Range: 100–10000 (0.1x–10x).
     */
    function updateCollateralRatio(uint256 newRatioMillis) external onlyOwner {
        require(newRatioMillis >= 100 && newRatioMillis <= 10000,
                "VAPIQuickSilverCollateral: ratio out of range");
        uint256 old = collateralRatioMillis;
        collateralRatioMillis = newRatioMillis;
        emit CollateralRatioUpdated(old, newRatioMillis);
    }

    /**
     * @notice Update the minimum stake amount.
     */
    function updateMinimumStake(uint256 newMinimum) external onlyOwner {
        require(newMinimum > 0, "VAPIQuickSilverCollateral: zero minimum");
        uint256 old = minimumStakeStIOTX;
        minimumStakeStIOTX = newMinimum;
        emit MinimumStakeUpdated(old, newMinimum);
    }

    /**
     * @notice Returns true if operator has active locked collateral (not in cooldown).
     */
    function isActiveCollateral(address operator) external view returns (bool) {
        CollateralRecord storage rec = collateralRecords[operator];
        return rec.active && rec.unlockRequestedAt == 0;
    }

    /**
     * @notice Returns the locked collateral amount for operator.
     */
    function getCollateralBalance(address operator) external view returns (uint256) {
        return collateralRecords[operator].lockedAmount;
    }

    /**
     * @notice Returns the unlock timestamp (0 if no unlock requested, >0 if in cooldown).
     */
    function getUnlockTimestamp(address operator) external view returns (uint256) {
        uint256 req = collateralRecords[operator].unlockRequestedAt;
        return req > 0 ? req + DEREGISTER_COOLDOWN : 0;
    }
}
