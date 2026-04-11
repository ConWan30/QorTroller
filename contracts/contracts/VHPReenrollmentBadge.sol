// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/access/Ownable.sol";
import "@openzeppelin/contracts/utils/ReentrancyGuard.sol";

/**
 * @title VHPReenrollmentBadge
 * @notice Phase 187 — WIF-033 W2 closure: ERC-4671-style soulbound credential
 *         issued when a biometric re-enrollment attestation validates on IoTeX L1.
 *
 * @dev Soulbound: all transfer operations are permanently disabled.
 *      Each badge records:
 *        - playerIdHash: keccak256(player_id) — privacy-preserving identity anchor
 *        - attestationHash: HMAC-SHA256 token from ReEnrollmentAttestationAgent (Phase 185)
 *        - mintedAt: block.timestamp at mint
 *        - expiresAt: mintedAt + ttlDays * 1 days (default 90 days)
 *        - valid: true until revoked or expired
 *
 *      Composability:
 *        - isValid(tokenId) — checks block.timestamp < expiresAt
 *        - playerBadgeCount[playerIdHash] — total re-enrollment events (biometric stability score)
 *        - latestBadgeId[playerIdHash] — latest token for a player
 *
 *      Tournament operators can query playerBadgeCount to score biometric stability:
 *        count=0: never drifted (most stable)
 *        count>2: high temporal non-stationarity (re-enrollment required multiple times)
 *
 *      VAPI Exclusivity:
 *        VHPReenrollmentBadge requires:
 *          Phase 182: PersonaBreakDetectorAgent (LOO accuracy trend detection)
 *          Phase 185: ReEnrollmentAttestationAgent (HMAC-SHA256 attestation token)
 *          Phase 186: AttestationBoundRenewalAgent (on-chain binding via SeparationRatioRegistry)
 *          Phase 187: VHPReenrollmentBadge (soulbound identity recovery credential)
 *        This 4-layer stack is non-replicable without VAPI's full biometric infrastructure.
 *
 * @dev Gas estimate: ~90k per mintBadge (struct write + 3 mapping updates + event)
 * @dev Deploy: deploy-phase187.js (IoTeX testnet, deferred — ~0.08 IOTX est.)
 * @dev Security: onlyOwner mint; ReentrancyGuard; zero-bytes32 guards on all inputs;
 *                anti-replay: same attestationHash rejected (UNIQUE semantic via require)
 */
contract VHPReenrollmentBadge is Ownable, ReentrancyGuard {
    // -------------------------------------------------------------------
    // Types
    // -------------------------------------------------------------------

    struct Badge {
        bytes32 playerIdHash;     // keccak256(player_id) — privacy-preserving
        bytes32 attestationHash;  // HMAC-SHA256 from ReEnrollmentAttestationAgent
        uint256 mintedAt;         // block.timestamp at mint
        uint256 expiresAt;        // mintedAt + ttlDays * 1 days
        bool    valid;            // false when revoked by owner
    }

    // -------------------------------------------------------------------
    // State
    // -------------------------------------------------------------------

    uint256 public totalBadges;

    /// @notice tokenId → Badge
    mapping(uint256 => Badge) public badges;

    /// @notice playerIdHash → total badge count (re-enrollment counter)
    mapping(bytes32 => uint256) public playerBadgeCount;

    /// @notice playerIdHash → latest tokenId
    mapping(bytes32 => uint256) public latestBadgeId;

    /// @notice attestationHash → already used (anti-replay: one badge per attestation)
    mapping(bytes32 => bool) public attestationUsed;

    // -------------------------------------------------------------------
    // Events
    // -------------------------------------------------------------------

    event BadgeMinted(
        uint256 indexed tokenId,
        bytes32 indexed playerIdHash,
        bytes32 indexed attestationHash,
        uint256 expiresAt,
        uint256 blockNumber
    );

    event BadgeRevoked(
        uint256 indexed tokenId,
        bytes32 indexed playerIdHash
    );

    // -------------------------------------------------------------------
    // Constructor
    // -------------------------------------------------------------------

    constructor(address initialOwner) Ownable(initialOwner) {}

    // -------------------------------------------------------------------
    // Mint
    // -------------------------------------------------------------------

    /**
     * @notice Mint a soulbound re-enrollment badge for a player.
     * @param playerIdHash    keccak256(player_id) — privacy-preserving identity anchor.
     * @param attestationHash HMAC-SHA256 attestation from ReEnrollmentAttestationAgent.
     * @param ttlDays         Badge validity in days (must be > 0; typical: 90).
     * @return tokenId        Immutable on-chain token ID.
     *
     * Requirements:
     *   - onlyOwner (bridge operator)
     *   - playerIdHash != bytes32(0)
     *   - attestationHash != bytes32(0)
     *   - ttlDays > 0
     *   - attestationHash not previously used (anti-replay)
     */
    function mintBadge(
        bytes32 playerIdHash,
        bytes32 attestationHash,
        uint256 ttlDays
    )
        external
        onlyOwner
        nonReentrant
        returns (uint256 tokenId)
    {
        // Checks
        require(playerIdHash    != bytes32(0), "VHPReenrollmentBadge: zero player hash");
        require(attestationHash != bytes32(0), "VHPReenrollmentBadge: zero attestation hash");
        require(ttlDays > 0,                   "VHPReenrollmentBadge: ttl must be positive");
        require(
            !attestationUsed[attestationHash],
            "VHPReenrollmentBadge: attestation already used"
        );

        // Effects
        tokenId = ++totalBadges;
        uint256 exp = block.timestamp + ttlDays * 1 days;

        badges[tokenId] = Badge({
            playerIdHash:    playerIdHash,
            attestationHash: attestationHash,
            mintedAt:        block.timestamp,
            expiresAt:       exp,
            valid:           true
        });

        playerBadgeCount[playerIdHash]++;
        latestBadgeId[playerIdHash]      = tokenId;
        attestationUsed[attestationHash] = true;

        // Interactions (none — soulbound, no external calls)
        emit BadgeMinted(tokenId, playerIdHash, attestationHash, exp, block.number);
    }

    // -------------------------------------------------------------------
    // Read
    // -------------------------------------------------------------------

    /**
     * @notice Check if a badge is valid (not expired, not revoked).
     * @param tokenId Badge token ID.
     * @return bool True if badge.valid == true AND block.timestamp < badge.expiresAt.
     */
    function isValid(uint256 tokenId) external view returns (bool) {
        Badge storage b = badges[tokenId];
        return b.valid && block.timestamp < b.expiresAt;
    }

    /**
     * @notice Get the latest badge token ID for a player.
     * @param playerIdHash keccak256(player_id).
     * @return tokenId Latest badge token ID (0 if none minted).
     */
    function getLatestBadge(bytes32 playerIdHash) external view returns (uint256) {
        return latestBadgeId[playerIdHash];
    }

    // -------------------------------------------------------------------
    // Revoke (owner only — emergency use)
    // -------------------------------------------------------------------

    /**
     * @notice Revoke a badge (set valid=false). Irreversible.
     * @param tokenId Badge token ID to revoke.
     */
    function revokeBadge(uint256 tokenId) external onlyOwner {
        require(tokenId > 0 && tokenId <= totalBadges, "VHPReenrollmentBadge: token not found");
        Badge storage b = badges[tokenId];
        require(b.valid, "VHPReenrollmentBadge: already revoked");
        b.valid = false;
        emit BadgeRevoked(tokenId, b.playerIdHash);
    }

    // -------------------------------------------------------------------
    // Soulbound: no transfers
    // -------------------------------------------------------------------

    /**
     * @notice Soulbound — all transfers permanently disabled.
     * @dev ERC-4671 pattern: transfer functions are blocked at the contract level.
     *      This contract does not inherit ERC-721 — it is a pure soulbound implementation.
     *      Any attempt to transfer ownership of a badge is impossible by design.
     */
    function _rejectTransfer() internal pure {
        revert("VHPReenrollmentBadge: soulbound - transfers disabled");
    }
}
