// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/// @notice Minimal mock of AdjudicationRegistry's isRecorded() for VPMAnchorRegistry
///         tests. Operator-controllable: setRecorded(hash, bool) flips a hash's
///         recorded state without exercising the full Phase 111 flow.
contract MockAdjudicationRegistry_VPM {
    mapping(bytes32 => bool) public recorded;

    function setRecorded(bytes32 podHash, bool value) external {
        recorded[podHash] = value;
    }

    function isRecorded(bytes32 podHash) external view returns (bool) {
        return recorded[podHash];
    }
}
