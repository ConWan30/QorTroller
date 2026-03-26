// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * @title MockRevertingRulingOracle — Phase 71 test helper
 * @notice Used in test_14 to verify that VAPIProtocolLens fails closed (M-1 fix).
 *         isSuspended() succeeds (returns false); isEligible() and getRulingState() revert.
 */
contract MockRevertingRulingOracle {
    function isSuspended(bytes32) external pure returns (bool) {
        return false;
    }

    function isEligible(bytes32) external pure returns (bool) {
        revert("MockRevertingRulingOracle: isEligible always reverts");
    }

    function getRulingState(bytes32) external pure returns (
        bool, uint32, uint32, uint32, uint64, bytes32
    ) {
        revert("MockRevertingRulingOracle: getRulingState always reverts");
    }
}
