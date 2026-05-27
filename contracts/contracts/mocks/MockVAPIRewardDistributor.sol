// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/// @notice Test-only mock for IVAPIRewardDistributor (Path A Arc 1 C4 Hardhat suite).
///         VAPIProtocolLensV2 does NOT consult this in either Path A gate
///         (isFullyEligible / isFullyEligible_PathA / getDeviceTier) — it is
///         only consulted by getDeviceState which Commit 4 does not test.
///         Included so constructor validation passes (5 non-zero addresses).
contract MockVAPIRewardDistributor {
    function getRewardBreakdown(bytes32)
        external pure
        returns (uint256, uint256, uint256, uint256, uint32)
    {
        return (0, 0, 0, 100, 0);
    }
}
