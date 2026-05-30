// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/// @title MockVAPIReplayProofGroth16VerifierV2 — Arc 6 Commit 4 test mock
contract MockVAPIReplayProofGroth16VerifierV2 {
    bool public verifyResult = true;
    function setVerifyResult(bool r) external { verifyResult = r; }
    function verifyProof(
        uint256[2] memory, uint256[2][2] memory, uint256[2] memory, uint256[10] memory
    ) external view returns (bool) { return verifyResult; }
}

/// @title MockVAPITemporalBeaconRegistry — Arc 6 Commit 4 test mock
contract MockVAPITemporalBeaconRegistry {
    mapping(uint256 => bytes32) public anchoredHash;
    function setAnchored(uint256 blk, bytes32 h) external { anchoredHash[blk] = h; }
    function verifyBeacon(uint256 blk, bytes32 claimed) external view returns (bool) {
        return anchoredHash[blk] != bytes32(0) && anchoredHash[blk] == claimed;
    }
}
