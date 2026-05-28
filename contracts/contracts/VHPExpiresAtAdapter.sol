// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/// @title VHPExpiresAtAdapter — IVHP222 shim over VAPIVerifiedHumanProof
/// @notice ABI adapter exposing the IVHP222 interface that VAPIBiometricGovernance
///         (Phase 222 BBG) expects. The canonical VAPIVerifiedHumanProof
///         (Phase 99C, 0xD3B2E259A4B69EF08e263e3A57B2507B7eac3dcF) implements
///         `isValid(uint256)` + `ownerOf(uint256)` directly but exposes `expiresAt`
///         only as a field inside the auto-generated `vhpData(uint256)` struct
///         getter (7-tuple). This adapter wraps the canonical contract and
///         exposes `expiresAt(uint256) -> uint256` as a standalone view so
///         BBG's `proposeWithVHP(proposalHash, vhpTokenId)` can read the VHP
///         freshness window per the Phase 222 BBG_MAX_AGE_SEC gate.
///
/// @dev Discovered 2026-05-28 during Curator scope-expansion governance ceremony
///      pre-broadcast sanity check: BBG.proposeWithVHP() at line 97 calls
///      `vhpContract.expiresAt(vhpTokenId)` which reverts against the deployed
///      VAPIVerifiedHumanProof. The IVHP222 interface in BBG.sol predates the
///      actual VHP shipped in Phase 99C. This adapter bridges the gap.
///
///      The adapter is IMMUTABLE — `vhp` is set in constructor + never changes.
///      If VAPIVerifiedHumanProof is ever redeployed, this adapter must be
///      re-deployed and `BBG.setVHPContract(newAdapter)` re-called.
///
///      Zero-state contract; no storage beyond the immutable VHP reference.
///      All three IVHP222 methods are pure pass-throughs (delegation reads;
///      no state mutation, no value transfer, no event emission).

interface IVAPIVerifiedHumanProof {
    function ownerOf(uint256 tokenId) external view returns (address);
    function isValid(uint256 tokenId) external view returns (bool);
    /// @notice Auto-generated struct getter for the public `vhpData` mapping.
    ///         Returns the 7 VHPData fields as positional return values.
    function vhpData(uint256 tokenId) external view returns (
        bytes32 deviceIdHash,
        uint8   certificationLevel,
        uint32  consecutiveClean,
        uint32  confidenceScore,
        uint256 issuedAt,
        uint256 expiresAt,
        bytes32 mpcCeremonyHash
    );
}

contract VHPExpiresAtAdapter {

    /// @notice The wrapped VAPIVerifiedHumanProof contract (immutable).
    ///         Set at construction; cannot be changed. To point the adapter
    ///         at a different VHP, re-deploy the adapter.
    IVAPIVerifiedHumanProof public immutable vhp;

    constructor(address vhpAddr) {
        require(vhpAddr != address(0), "VHPAdapter: zero vhpAddr");
        vhp = IVAPIVerifiedHumanProof(vhpAddr);
    }

    /// @notice Returns the VHP expiry timestamp for tokenId — the standalone
    ///         getter IVHP222 expects. Reads the `expiresAt` field (index 5)
    ///         from the wrapped contract's `vhpData(tokenId)` struct getter.
    ///         Returns 0 for unminted tokenIds (default uint256 from a
    ///         zero-initialized struct).
    function expiresAt(uint256 tokenId) external view returns (uint256) {
        ( , , , , , uint256 _expiresAt, ) = vhp.vhpData(tokenId);
        return _expiresAt;
    }

    /// @notice Pass-through to VAPIVerifiedHumanProof.isValid(). Returns true
    ///         iff the token exists AND block.timestamp < its expiresAt.
    function isValid(uint256 tokenId) external view returns (bool) {
        return vhp.isValid(tokenId);
    }

    /// @notice Pass-through to VAPIVerifiedHumanProof.ownerOf(). Returns the
    ///         soulbound token's holder (zero address if unminted).
    function ownerOf(uint256 tokenId) external view returns (address) {
        return vhp.ownerOf(tokenId);
    }
}
