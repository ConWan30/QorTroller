// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/access/Ownable.sol";

/**
 * @title VAPIVerifiedHumanProofBridge
 * @notice Phase 99C — LayerZero V2 OApp cross-chain sender for VHP tokens.
 *
 * Sends a VHP token's data to a peer contract on another chain via LayerZero messaging.
 * The receiving chain mints a mirror token or updates state via lzReceive().
 *
 * Anti-replay: each (tokenId, dstEid) pair is tracked via sentNonces to prevent
 * duplicate sends. A higher nonce can be sent to update the remote state.
 *
 * Setup: setPeer(dstEid, peerAddress) must be called before first send to any chain.
 *
 * NOTE: This is an AssemblyScript stub — lzSend is mocked for testnet use.
 *       Production: inherit from OApp and implement _lzSend + lzReceive via
 *       LayerZero V2 endpoint contract (EndpointV2 at the configured address).
 */
contract VAPIVerifiedHumanProofBridge is Ownable {

    // LayerZero endpoint address (set at deploy, immutable)
    address public immutable lzEndpoint;

    // dstEid → peer address (bytes32 for cross-chain address encoding)
    mapping(uint32 => bytes32) public peers;

    // tokenId → dstEid → nonce (anti-replay counter)
    mapping(uint256 => mapping(uint32 => uint64)) public sentNonces;

    // VHPData struct mirrored from VAPIVerifiedHumanProof.sol
    struct VHPData {
        bytes32 deviceIdHash;
        uint8   certificationLevel;
        uint32  consecutiveClean;
        uint32  confidenceScore;
        uint256 issuedAt;
        uint256 expiresAt;
        bytes32 mpcCeremonyHash;
    }

    event VHPSent(
        uint256 indexed tokenId,
        uint32  indexed dstEid,
        address recipient,
        uint64  nonce,
        bytes32 peerAddress
    );
    event PeerSet(uint32 indexed dstEid, bytes32 peerAddress);

    constructor(address _lzEndpoint, address initialOwner) Ownable(initialOwner) {
        require(_lzEndpoint != address(0), "VAPIVerifiedHumanProofBridge: zero endpoint");
        lzEndpoint = _lzEndpoint;
    }

    /**
     * @notice Configure the peer contract address on a destination chain.
     * @param dstEid LayerZero destination endpoint ID (e.g., 30101 for Ethereum mainnet)
     * @param peerAddress Peer contract address encoded as bytes32 (right-padded if 20-byte addr)
     */
    function setPeer(uint32 dstEid, bytes32 peerAddress) external onlyOwner {
        require(peerAddress != bytes32(0), "VAPIVerifiedHumanProofBridge: zero peer");
        peers[dstEid] = peerAddress;
        emit PeerSet(dstEid, peerAddress);
    }

    /**
     * @notice Send a VHP token's data to a peer chain.
     * @dev In production: calls lzEndpoint.send() with encoded VHPData.
     *      Stub: emits event only, does not call LayerZero endpoint.
     * @param tokenId VHP token ID on this chain
     * @param dstEid Destination LayerZero endpoint ID
     * @param recipient Recipient address on the destination chain
     * @param data VHPData struct to encode and send
     */
    function send(
        uint256 tokenId,
        uint32  dstEid,
        address recipient,
        VHPData calldata data
    ) external payable onlyOwner {
        require(peers[dstEid] != bytes32(0), "VAPIVerifiedHumanProofBridge: peer not set");
        require(recipient != address(0), "VAPIVerifiedHumanProofBridge: zero recipient");
        require(data.expiresAt > block.timestamp, "VAPIVerifiedHumanProofBridge: token expired");

        uint64 nonce = sentNonces[tokenId][dstEid] + 1;
        sentNonces[tokenId][dstEid] = nonce;

        // Production: bytes memory payload = abi.encode(tokenId, recipient, data);
        // lzEndpoint.send{value: msg.value}(...);
        // Stub: emit event only (testnet mode)
        emit VHPSent(tokenId, dstEid, recipient, nonce, peers[dstEid]);
    }

    /**
     * @notice Returns the latest nonce sent for a (tokenId, dstEid) pair.
     */
    function getSentNonce(uint256 tokenId, uint32 dstEid) external view returns (uint64) {
        return sentNonces[tokenId][dstEid];
    }

    /**
     * @notice Recover any ETH/IOTX sent accidentally to this contract.
     */
    function withdrawNative() external onlyOwner {
        payable(owner()).transfer(address(this).balance);
    }
}
