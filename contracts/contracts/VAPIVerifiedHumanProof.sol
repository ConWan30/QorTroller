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

    /// @notice Phase O4-VPM-INT-B-PREP - Address of the cross-chain bridge
    ///         contract authorized to call bridgeMint(). Zero address until
    ///         setBridgeAddress is called by owner; bridgeMint reverts when
    ///         bridgeAddress is zero. Defensive prep for the eventual
    ///         VAPIVerifiedHumanProofBridge OApp refactor; full LayerZero
    ///         V2 inheritance is BLOCKED upstream by a peer-dep conflict
    ///         (lz-evm-oapp-v2 transitively requires ethers v5 via
    ///         eth-optimism contracts; Hardhat Toolbox 4 requires ethers
    ///         v6). Until the conflict resolves, bridgeMint provides the
    ///         receiver-side mint authority that the bridge _lzReceive
    ///         would call - exercisable today via MockLayerZeroEndpoint
    ///         simulateInbound at test time.
    address public bridgeAddress;

    event BridgeAddressSet(address indexed oldBridge, address indexed newBridge);
    event VHPBridgeMinted(
        uint256 indexed tokenId,
        address indexed to,
        bytes32 deviceIdHash,
        uint64  remoteNonce
    );

    modifier onlyBridge() {
        require(
            bridgeAddress != address(0),
            "VAPIVerifiedHumanProof: bridge not configured"
        );
        require(
            msg.sender == bridgeAddress,
            "VAPIVerifiedHumanProof: caller not bridge"
        );
        _;
    }

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

    // --- Phase O4-VPM-INT-B-PREP — Cross-chain bridge prep additions ---

    /**
     * @notice Set the authorized cross-chain bridge contract address.
     * @dev Zero address forbidden once set (no un-set path); subsequent
     *      changes emit BridgeAddressSet so the operator audit trail
     *      surfaces every authority rotation. ONLY this address may call
     *      bridgeMint() once configured.
     */
    function setBridgeAddress(address newBridge) external onlyOwner {
        require(newBridge != address(0), "VAPIVerifiedHumanProof: zero bridge");
        address old = bridgeAddress;
        bridgeAddress = newBridge;
        emit BridgeAddressSet(old, newBridge);
    }

    /**
     * @notice Bridge-initiated mint for cross-chain VHP arrivals.
     * @dev Called by the (future) VAPIVerifiedHumanProofBridge contract's
     *      `_lzReceive` when an inbound LayerZero message decodes to a
     *      mint request from another chain. Restrictions:
     *        - onlyBridge modifier (msg.sender == bridgeAddress; bridgeAddress != 0)
     *        - to != zero address
     *        - data.expiresAt must be in the future (bridge cannot
     *          mint already-expired tokens; receiver-side TTL check)
     *      Emits VHPMinted (compatible with existing minting analytics) +
     *      VHPBridgeMinted (Phase O4 receiver-side attribution).
     * @param to            Recipient address on this chain
     * @param data          Full VHPData payload bridged from source chain
     * @param remoteNonce   LayerZero message nonce — caller-supplied for
     *                      receiver-side replay guard inspection
     * @return tokenId      Newly-minted token's id
     */
    function bridgeMint(
        address to,
        VHPData calldata data,
        uint64  remoteNonce
    ) external onlyBridge returns (uint256) {
        require(to != address(0), "VAPIVerifiedHumanProof: zero address");
        require(
            data.expiresAt > block.timestamp,
            "VAPIVerifiedHumanProof: already expired"
        );

        _tokenIdCounter++;
        uint256 tokenId = _tokenIdCounter;

        vhpData[tokenId] = data;
        ownerOf[tokenId] = to;
        tokenOfAddress[to] = tokenId;

        emit VHPMinted(
            tokenId, to, data.deviceIdHash,
            data.certificationLevel, data.expiresAt
        );
        emit VHPBridgeMinted(tokenId, to, data.deviceIdHash, remoteNonce);
        return tokenId;
    }
}
