// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/// @title MockVHP222 — Minimal VHP mock for Phase 222 BBG Hardhat tests.
/// @notice Implements the IVHP interface used by VAPIBiometricGovernance.
///         NOT for production use — test mock only.
contract MockVHP222 {

    struct MockToken {
        address owner;
        uint256 expiresAt;
        bool    valid;
    }

    mapping(uint256 => MockToken) public tokens;

    function mint(uint256 tokenId, address owner_, uint256 expiresAt_) external {
        tokens[tokenId] = MockToken({
            owner:     owner_,
            expiresAt: expiresAt_,
            valid:     true
        });
    }

    function invalidate(uint256 tokenId) external {
        tokens[tokenId].valid = false;
    }

    function isValid(uint256 tokenId) external view returns (bool) {
        return tokens[tokenId].valid;
    }

    function expiresAt(uint256 tokenId) external view returns (uint256) {
        return tokens[tokenId].expiresAt;
    }

    function ownerOf(uint256 tokenId) external view returns (address) {
        address o = tokens[tokenId].owner;
        require(o != address(0), "MockVHP222: token not minted");
        return o;
    }
}
