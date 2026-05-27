// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/// @notice Test-only mock for IRulingOracle (Path A Arc 1 C4 Hardhat suite).
contract MockRulingOracle {
    mapping(bytes32 => bool) public isSuspended;
    mapping(bytes32 => bool) public isEligible;

    function setIsSuspended(bytes32 deviceId, bool v) external { isSuspended[deviceId] = v; }
    function setIsEligible(bytes32 deviceId, bool v)  external { isEligible[deviceId]  = v; }

    function getRulingState(bytes32)
        external pure
        returns (bool, uint32, uint32, uint32, uint64, bytes32)
    {
        return (false, 0, 0, 0, 0, bytes32(0));
    }
}
