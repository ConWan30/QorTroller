// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;
import "@openzeppelin/contracts/access/Ownable.sol";
import "@openzeppelin/contracts/utils/ReentrancyGuard.sol";

/// @title VAPIConsentRegistry — Phase 237 Per-Category Gamer Consent
/// @notice On-chain consent state for biometric data routing.  Gamers (msg.sender)
///         grant or revoke per-category consent; the bridge READS this state via
///         view calls but never writes on the gamer's behalf (self-sovereignty).
///
///         Four categories (matching VAPIDataMarketplace tiers and the
///         Phase 236+ plan):
///           TOURNAMENT_GATE     (0) — required for tournament eligibility
///           ANONYMIZED_RESEARCH (1) — opt-in for population research data
///           MANUFACTURER_CERT   (2) — opt-in for hardware OEM cert pool
///           MARKETPLACE         (3) — opt-in for VAPIDataMarketplace listing
///
///         Pattern: Ownable + ReentrancyGuard (matches VAPIBiometricGovernance Phase 222).
///         Anti-replay: same consentHash cannot be submitted twice across all gamers.
///         Zero-hash guard: consentHash != bytes32(0).
///         Composes with VAPIioIDRegistry: optional reference for off-chain DID
///         resolution; setIoIDRegistry() does NOT block this contract from operating
///         standalone.
///
/// @dev Consent is per-(gamer, category): a gamer can grant TOURNAMENT_GATE
///      consent without granting MARKETPLACE.  Revocation is per-category too.
///      Re-grant on the same category overwrites the prior record (new
///      consentHash / new expiry); the prior consentHash remains in the
///      anti-replay set so it cannot be replayed by a different account.

contract VAPIConsentRegistry is Ownable, ReentrancyGuard {

    /// FROZEN enum — values must match consent_categories.ConsentCategory
    /// in the bridge.  Position-for-position correspondence is part of the
    /// FROZEN-v1 commitment formula domain.
    enum ConsentCategory {
        TOURNAMENT_GATE,        // 0
        ANONYMIZED_RESEARCH,    // 1
        MANUFACTURER_CERT,      // 2
        MARKETPLACE             // 3
    }

    struct ConsentRecord {
        bytes32 consentHash;    // SHA-256 commitment from bridge
                                //   compute_consent_hash() — FROZEN v1
        uint64  grantedAt;      // block.timestamp at grant
        uint64  expiresAt;      // 0 == no expiry
        bool    revoked;        // set true by revokeConsent
    }

    /// gamer → category → ConsentRecord
    mapping(address => mapping(uint8 => ConsentRecord)) private _consents;

    /// Anti-replay across all gamers / categories.  A consentHash, once
    /// submitted, cannot be reused.  This prevents a malicious actor who
    /// learns a hash off-chain from front-running it on someone else's behalf.
    mapping(bytes32 => bool) private _recordedHashes;

    /// Optional reference to VAPIioIDRegistry for off-chain DID resolution.
    /// Not required for grantConsent / revokeConsent / view calls to work.
    address public ioidRegistry;

    /// Total consents granted (lifetime; not decremented on revoke).
    uint256 public totalGrants;

    event ConsentGranted(
        address indexed gamer,
        uint8   indexed category,
        bytes32 indexed consentHash,
        uint64          expiresAt,
        uint256         blockNumber
    );

    event ConsentRevoked(
        address indexed gamer,
        uint8   indexed category,
        bytes32         priorConsentHash,
        uint256         blockNumber
    );

    event IoIDRegistrySet(
        address indexed oldRegistry,
        address indexed newRegistry
    );

    constructor(address initialOwner) Ownable(initialOwner) {
        // ioidRegistry is intentionally unset; setIoIDRegistry() is optional.
    }

    /// @notice Set or update the optional VAPIioIDRegistry reference.
    ///         Reverts on zero address.
    function setIoIDRegistry(address newRegistry) external onlyOwner {
        require(newRegistry != address(0), "VCR: zero ioidRegistry");
        emit IoIDRegistrySet(ioidRegistry, newRegistry);
        ioidRegistry = newRegistry;
    }

    /// @notice Grant consent for a specific category.  msg.sender is the gamer.
    ///         Reverts when:
    ///           - consentHash is bytes32(0)
    ///           - consentHash already submitted (anti-replay across all senders)
    ///           - category is out of the ConsentCategory enum range
    ///         Re-granting the same category by the same gamer overwrites the
    ///         prior record (new hash / new expiry); the prior hash remains
    ///         in the anti-replay set.
    function grantConsent(
        uint8 category,
        uint64 expiresAt,
        bytes32 consentHash
    ) external nonReentrant {
        require(consentHash != bytes32(0), "VCR: zero consentHash");
        require(!_recordedHashes[consentHash], "VCR: duplicate consentHash");
        require(category <= uint8(ConsentCategory.MARKETPLACE), "VCR: bad category");

        // CEI: state changes BEFORE the event emit (no external calls here)
        _recordedHashes[consentHash] = true;
        _consents[msg.sender][category] = ConsentRecord({
            consentHash: consentHash,
            grantedAt:   uint64(block.timestamp),
            expiresAt:   expiresAt,
            revoked:     false
        });
        totalGrants++;

        emit ConsentGranted(
            msg.sender, category, consentHash, expiresAt, block.number
        );
    }

    /// @notice Revoke consent for a specific category.  msg.sender is the gamer.
    ///         Reverts when:
    ///           - category is out of the ConsentCategory enum range
    ///           - no prior consent exists (cannot revoke what was never granted)
    function revokeConsent(uint8 category) external nonReentrant {
        require(category <= uint8(ConsentCategory.MARKETPLACE), "VCR: bad category");
        ConsentRecord storage rec = _consents[msg.sender][category];
        require(rec.consentHash != bytes32(0), "VCR: no consent to revoke");
        require(!rec.revoked, "VCR: already revoked");

        bytes32 prior = rec.consentHash;
        rec.revoked = true;
        emit ConsentRevoked(msg.sender, category, prior, block.number);
    }

    /// @notice Check whether a gamer's consent for a category is currently valid.
    ///         Valid iff: granted, not revoked, AND (expiresAt == 0 OR
    ///         block.timestamp < expiresAt).
    function isConsentValid(
        address gamer,
        uint8 category
    ) external view returns (bool) {
        if (category > uint8(ConsentCategory.MARKETPLACE)) return false;
        ConsentRecord storage rec = _consents[gamer][category];
        if (rec.consentHash == bytes32(0)) return false;
        if (rec.revoked) return false;
        if (rec.expiresAt != 0 && block.timestamp >= rec.expiresAt) return false;
        return true;
    }

    /// @notice Return the full consent record for a gamer / category.
    ///         Returns zero-record (consentHash == bytes32(0)) if no consent.
    function getConsentRecord(
        address gamer,
        uint8 category
    ) external view returns (ConsentRecord memory) {
        if (category > uint8(ConsentCategory.MARKETPLACE)) {
            return ConsentRecord(bytes32(0), 0, 0, false);
        }
        return _consents[gamer][category];
    }

    /// @notice Returns true when a consentHash has already been submitted
    ///         (anti-replay surface for off-chain duplicate-detection).
    function isRecorded(bytes32 consentHash) external view returns (bool) {
        return _recordedHashes[consentHash];
    }
}
