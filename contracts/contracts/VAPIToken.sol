// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/token/ERC20/extensions/ERC20Pausable.sol";
import "@openzeppelin/contracts/access/Ownable.sol";

/**
 * @title VAPIToken — Phase 99A VAPI Utility Token
 * @notice ERC-20 utility token for the VAPI DePIN ecosystem.
 *
 * Max supply: 1,000,000,000 VAPI (1B, 18 decimals)
 *
 * Token launch (TGE) is gated by the bridge operator until:
 *   - Inter-person separation ratio > 1.0 confirmed (currently 0.362)
 *   - N≥100 live adjudications with zero confirmed false positives
 *   - Verified Human Proof (VHP) end-to-end demonstrated
 *
 * completeTGE() is IRREVERSIBLE — permanently seals mint() and pauses transfers.
 * Test isolation invariant: never call completeTGE() in shared fixtures;
 * always use fresh deploys in Hardhat beforeEach blocks.
 *
 * Use cases:
 *   - Operator staking collateral (VAPIOperatorRegistry — 10,000 VAPI minimum)
 *   - Hardware certification fee (VAPIHardwareCertRegistry)
 *   - DePIN reward distribution (VAPIRewardDistributor)
 *
 * Deployed to IoTeX testnet only in Phase 99. No mainnet TGE in Phase 99.
 */
contract VAPIToken is ERC20Pausable, Ownable {
    uint256 public constant MAX_SUPPLY = 1_000_000_000 * 1e18; // 1B VAPI

    bool public tgeComplete;

    event TGECompleted(uint256 totalSupply, uint256 timestamp);

    constructor(address initialOwner)
        ERC20("VAPI Token", "VAPI")
        Ownable(initialOwner)
    {}

    /**
     * @notice Mint VAPI tokens. Only callable by owner before TGE.
     * @dev Reverts if tgeComplete=true or totalSupply+amount > MAX_SUPPLY.
     */
    function mint(address to, uint256 amount) external onlyOwner {
        require(!tgeComplete, "VAPIToken: TGE complete, no further minting");
        require(
            totalSupply() + amount <= MAX_SUPPLY,
            "VAPIToken: exceeds max supply"
        );
        _mint(to, amount);
    }

    /**
     * @notice Permanently seal minting and pause token transfers.
     * IRREVERSIBLE — cannot be undone. See test isolation invariant above.
     */
    function completeTGE() external onlyOwner {
        require(!tgeComplete, "VAPIToken: already complete");
        tgeComplete = true;
        _pause();
        emit TGECompleted(totalSupply(), block.timestamp);
    }

    /**
     * @notice Unpause transfers. Only callable by owner after emergency pause.
     * Note: completeTGE() pauses permanently — this cannot undo TGE.
     */
    function unpause() external onlyOwner {
        _unpause();
    }

    /**
     * @notice Burn caller's own tokens (e.g. for slashing mechanics).
     */
    function burn(uint256 amount) external {
        _burn(msg.sender, amount);
    }
}
