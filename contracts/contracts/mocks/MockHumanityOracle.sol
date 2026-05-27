// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/// @notice Test-only mock for IHumanityOracle (Path A Arc 1 C4 Hardhat suite).
///         Per-device settable boolean returns; ONLY the fields VAPIProtocolLensV2
///         actually reads. Production tests against this mock confirm the lens
///         composes correctly under each oracle's pass/fail axis.
contract MockHumanityOracle {
    mapping(bytes32 => bool) public isNominal;

    function setIsNominal(bytes32 deviceId, bool v) external { isNominal[deviceId] = v; }

    function getHumanityPct(bytes32) external pure returns (uint16) { return 0; }
    function getHumanityVerdict(bytes32)
        external pure
        returns (uint8, uint16, uint32, uint32, uint32, uint64)
    {
        return (0, 0, 0, 0, 0, 0);
    }
}
