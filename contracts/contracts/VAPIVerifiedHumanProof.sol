// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/access/Ownable.sol";

/**
 * @title VAPIVerifiedHumanProof
 * @notice Phase 99C — ERC-4671 soulbound Verified Human Proof token.
 *
 * Non-transferable. Expires after ttlDays (default 90 days). Renewable while valid.
 *
 * Mint gate (enforced off-chain by operator_api.py):
 *   audit_valid=True AND gate_passed=True AND dry_run=False
 *
 * Composability: isValid(tokenId) + VAPIProtocolLens.isFullyEligible() = single-call tournament gate.
 *
 * Soulbound invariant: ALL transfer functions unconditionally revert.
 * OZ v5: no Counters library — uses plain uint256 _tokenIdCounter.
 * W1 (Phase 99 plan): TGE gate — no mint after completeTGE() on VAPIToken.
 */
contract VAPIVerifiedHumanProof is Ownable {

    struct VHPData {
        bytes32 deviceIdHash;
        uint8   certificationLevel;   // 1=controller, 2=controller+GSR
        uint32  consecutiveClean;
        uint32  confidenceScore;      // 0–10000 (basis points, 10000 = 100%)
        uint256 issuedAt;
        uint256 expiresAt;
        bytes32 mpcCeremonyHash;
    }

    uint256 private _tokenIdCounter;
    mapping(uint256 => VHPData) public vhpData;
    mapping(uint256 => address) public ownerOf;
    mapping(address => uint256) public tokenOfAddress;  // latest token per address
    uint256 public defaultTTLDays = 90;

    event VHPMinted(
        uint256 indexed tokenId,
        address indexed to,
        bytes32 deviceIdHash,
        uint8   certLevel,
        uint256 expiresAt
    );
    event VHPRenewed(uint256 indexed tokenId, uint256 newExpiresAt);

    constructor(address initialOwner) Ownable(initialOwner) {}

    /**
     * @notice Mint a soulbound VHP token.
     * @dev onlyOwner — called by bridge operator key after 3-condition gate passes.
     *      data.expiresAt must be in the future.
     */
    function mint(address to, VHPData calldata data) external onlyOwner returns (uint256) {
        require(to != address(0), "VAPIVerifiedHumanProof: zero address");
        require(data.expiresAt > block.timestamp, "VAPIVerifiedHumanProof: already expired");

        _tokenIdCounter++;
        uint256 tokenId = _tokenIdCounter;

        vhpData[tokenId] = data;
        ownerOf[tokenId] = to;
        tokenOfAddress[to] = tokenId;

        emit VHPMinted(tokenId, to, data.deviceIdHash, data.certificationLevel, data.expiresAt);
        return tokenId;
    }

    /**
     * @notice Returns true if the token exists and has not expired.
     */
    function isValid(uint256 tokenId) public view returns (bool) {
        return ownerOf[tokenId] != address(0) && block.timestamp < vhpData[tokenId].expiresAt;
    }

    /**
     * @notice Extend token expiry by defaultTTLDays from now. Token must currently be valid.
     */
    function renew(uint256 tokenId) external onlyOwner {
        require(isValid(tokenId), "VAPIVerifiedHumanProof: token not valid");
        uint256 newExpiry = block.timestamp + defaultTTLDays * 1 days;
        vhpData[tokenId].expiresAt = newExpiry;
        emit VHPRenewed(tokenId, newExpiry);
    }

    /**
     * @notice Total tokens ever minted (not accounting for expired).
     */
    function totalSupply() external view returns (uint256) {
        return _tokenIdCounter;
    }

    // --- Soulbound invariants: ALL transfer/approval functions unconditionally revert ---

    function transferFrom(address, address, uint256) external pure {
        revert("VAPIVerifiedHumanProof: soulbound");
    }

    function safeTransferFrom(address, address, uint256) external pure {
        revert("VAPIVerifiedHumanProof: soulbound");
    }

    function safeTransferFrom(address, address, uint256, bytes calldata) external pure {
        revert("VAPIVerifiedHumanProof: soulbound");
    }

    function approve(address, uint256) external pure {
        revert("VAPIVerifiedHumanProof: soulbound");
    }

    function setApprovalForAll(address, bool) external pure {
        revert("VAPIVerifiedHumanProof: soulbound");
    }
}
