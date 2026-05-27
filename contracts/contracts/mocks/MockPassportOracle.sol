// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/// @notice Test-only mock for IPassportOracle (Path A Arc 1 C4 Hardhat suite).
contract MockPassportOracle {
    mapping(bytes32 => bool) public hasVerifiedPassport;

    function setHasVerifiedPassport(bytes32 deviceId, bool v) external {
        hasVerifiedPassport[deviceId] = v;
    }

    function getPassportState(bytes32)
        external pure
        returns (bool, bool, bytes32, uint32, uint32, uint64)
    {
        return (false, false, bytes32(0), 0, 0, 0);
    }
}
