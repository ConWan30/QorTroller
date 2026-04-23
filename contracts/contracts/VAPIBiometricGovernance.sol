// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;
import "@openzeppelin/contracts/access/Ownable.sol";
import "@openzeppelin/contracts/utils/ReentrancyGuard.sol";

/// @title VAPIBiometricGovernance — Phase 222 Biometric-Bound Governance (BBG)
/// @notice Gates governance proposals on the proposer's live Verified Human Proof (VHP).
///
///         Three attacks blocked:
///           STOLEN_KEY:  Attacker has the private key but not the soulbound VHP.
///                        VHP is non-transferable; ownerOf check enforces binding.
///           VHP_EXPIRY:  VHP must remain valid for at least bbgMaxAgeSec beyond the
///                        proposal time. Expired/near-expired VHPs are rejected.
///           FLASH_LOAN:  VHP is soulbound (non-transferable); ownership cannot be
///                        flash-borrowed unlike fungible governance tokens.
///
///         Pattern: Ownable + ReentrancyGuard (follows CeremonyAuditRegistry Phase 179).
///         Anti-replay: same proposalHash cannot be submitted twice.
///         Zero-root guard: proposalHash != bytes32(0).
///
/// @dev VHP interface: isValid(tokenId), expiresAt(tokenId), ownerOf(tokenId).
///      VHP contract must be set via constructor or setVHPContract() before proposals.

interface IVHP222 {
    function isValid(uint256 tokenId) external view returns (bool);
    function expiresAt(uint256 tokenId) external view returns (uint256);
    function ownerOf(uint256 tokenId) external view returns (address);
}

contract VAPIBiometricGovernance is Ownable, ReentrancyGuard {

    struct BBGProposal {
        bytes32 proposalHash;   // SHA-256 of the proposal content (off-chain)
        address proposer;       // msg.sender at proposal time
        uint256 vhpTokenId;     // Soulbound VHP token ID held by proposer
        uint256 proposedAt;     // block.timestamp
        uint256 vhpExpiresAt;   // VHP expiresAt at proposal time
    }

    IVHP222 public vhpContract;
    uint256 public bbgMaxAgeSec;   // Minimum VHP freshness window (seconds)
    uint256 public totalProposals;

    BBGProposal[] private _proposals;

    // Anti-replay: proposalHash => submitted
    mapping(bytes32 => bool) private _proposed;

    event ProposalSubmitted(
        bytes32 indexed proposalHash,
        address indexed proposer,
        uint256 vhpTokenId,
        uint256 blockNumber
    );

    event VHPContractSet(
        address indexed oldVHP,
        address indexed newVHP
    );

    constructor(
        address initialOwner,
        address vhpAddr,
        uint256 maxAgeSec
    ) Ownable(initialOwner) {
        require(vhpAddr != address(0), "BBG: zero vhpAddr");
        vhpContract  = IVHP222(vhpAddr);
        bbgMaxAgeSec = maxAgeSec > 0 ? maxAgeSec : 3600;
    }

    /// @notice Update the VHP contract address (onlyOwner).
    ///         Reverts on zero address.
    function setVHPContract(address newVHP) external onlyOwner {
        require(newVHP != address(0), "BBG: zero newVHP");
        emit VHPContractSet(address(vhpContract), newVHP);
        vhpContract = IVHP222(newVHP);
    }

    /// @notice Submit a governance proposal gated on caller's live VHP.
    ///         Reverts when:
    ///           - proposalHash is bytes32(0)
    ///           - proposalHash already submitted (anti-replay)
    ///           - VHP tokenId is not valid (expired or revoked)
    ///           - VHP ownerOf(tokenId) != msg.sender (STOLEN_KEY guard)
    ///           - VHP expires within bbgMaxAgeSec from now (VHP_EXPIRY guard)
    function proposeWithVHP(
        bytes32 proposalHash,
        uint256 vhpTokenId
    ) external nonReentrant {
        require(proposalHash != bytes32(0), "BBG: zero proposalHash");
        require(!_proposed[proposalHash], "BBG: duplicate proposalHash");
        require(vhpContract.isValid(vhpTokenId), "BBG: VHP not valid");
        require(
            vhpContract.ownerOf(vhpTokenId) == msg.sender,
            "BBG: not VHP owner"
        );
        uint256 vhpExp = vhpContract.expiresAt(vhpTokenId);
        require(
            vhpExp >= block.timestamp + bbgMaxAgeSec,
            "BBG: VHP expires too soon"
        );

        _proposed[proposalHash] = true;
        _proposals.push(BBGProposal({
            proposalHash: proposalHash,
            proposer:     msg.sender,
            vhpTokenId:   vhpTokenId,
            proposedAt:   block.timestamp,
            vhpExpiresAt: vhpExp
        }));
        totalProposals++;

        emit ProposalSubmitted(proposalHash, msg.sender, vhpTokenId, block.number);
    }

    /// @notice Returns true when proposalHash has already been submitted.
    function isProposed(bytes32 proposalHash) external view returns (bool) {
        return _proposed[proposalHash];
    }

    /// @notice Return the proposal at a specific index.
    ///         Reverts when index >= totalProposals.
    function getProposal(uint256 index) external view returns (BBGProposal memory) {
        require(index < _proposals.length, "BBG: index out of range");
        return _proposals[index];
    }
}
