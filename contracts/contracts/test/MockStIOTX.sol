// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/token/ERC20/ERC20.sol";

/**
 * @title MockStIOTX
 * @notice Test helper — mintable ERC-20 simulating stIOTX for Phase 101 tests.
 */
contract MockStIOTX is ERC20 {
    constructor() ERC20("Mock stIOTX", "stIOTX") {}

    function mint(address to, uint256 amount) external {
        _mint(to, amount);
    }
}
