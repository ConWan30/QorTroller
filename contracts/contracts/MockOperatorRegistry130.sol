// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * @title MockOperatorRegistry130
 * @notice Test helper for Phase130.test.js — mocks IVAPIOperatorRegistry.getStake().
 */
contract MockOperatorRegistry130 {
    mapping(address => uint256) private _stakes;

    function setStake(address operator, uint256 amount) external {
        _stakes[operator] = amount;
    }

    function getStake(address operator) external view returns (uint256) {
        return _stakes[operator];
    }
}
