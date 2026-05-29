// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;
import "@openzeppelin/contracts/access/Ownable.sol";
import "@openzeppelin/contracts/utils/ReentrancyGuard.sol";

/// @title VAPIConsentManifestRegistry — Data Economy Arc 4 Structured Consent Manifest
/// @notice Additive upgrade of the gamer consent surface from the coarse
///         per-category bitmask (VAPIConsentRegistry, Phase 237, deployed and
///         UNCHANGED) to a structured 7-dimension policy manifest the Curator
///         packaging loop reads before listing data.
///
///         DELIBERATE ADDITIVE DEPLOY (not an in-place upgrade): VAPIConsentRegistry
///         is a fixed Ownable+ReentrancyGuard contract with no proxy, so per the
///         SeparationRatioRegistry redeploy precedent this is a SEPARATE contract.
///         The deployed VAPIConsentRegistry.isConsentValid / getConsentRecord
///         bitmask surface stays fully callable; nothing about the FROZEN
///         VAPI-CONSENT-v1 commitment formula or its ConsentCategory enum changes.
///
///         SELF-SOVEREIGNTY (unchanged from Phase 237): msg.sender is the gamer.
///         The bridge READS manifests via view calls and NEVER writes one on a
///         gamer's behalf. setManifest can only be called by the gamer for their
///         own address.
///
///         PROTOCOL FLOORS (on-chain, non-bypassable — framework §9.4):
///           minSessionsPerPackage >= 10   (aggregation floor)
///           coolingPeriodHours    >= 72   (temporal cooling floor)
///         A manifest that violates either floor reverts. No consent
///         configuration can lower them.
///
/// @dev The "competing player team" buyer category (§9.4, never allowed) is not
///      representable in the manifest at all — the buyer-category booleans are
///      academic / gamedev / esports / brand / anonymous only — so it is
///      structurally impossible to consent to, requiring no runtime guard.
contract VAPIConsentManifestRegistry is Ownable, ReentrancyGuard {

    /// Protocol floors — non-bypassable (framework §9.4).
    uint16 public constant MIN_SESSIONS_FLOOR = 10;
    uint32 public constant COOLING_HOURS_FLOOR = 72;

    /// Autonomy levels (framework §8 Dimension 7). A new manifest is never
    /// initialised at full autonomy by default — the gamer must opt in.
    ///   0 = manual, 1 = approval, 2 = notify, 3 = full
    uint8 public constant AUTONOMY_MAX = 3;

    struct ConsentManifest {
        // Dimension 1 — Data categories (above the immutable data floor)
        bool allowAggregateStats;
        bool allowSkillRankingProof;        // Tier 1 (default-ON intent)
        bool allowTrajectoryProof;          // Tier 2 (default-ON intent)
        bool allowContextPerformanceProof;  // Tier 3 (explicit opt-in)
        bool allowFullSessionProof;         // Tier 4 (explicit opt-in)

        // Dimension 2 — Buyer categories
        bool allowAcademic;
        bool allowGameDev;
        bool allowEsports;
        bool allowBrand;                    // explicit opt-in only
        bool allowAnonymous;                // explicit opt-in only

        // Dimension 3 — Aggregation floor (>= MIN_SESSIONS_FLOOR)
        uint16 minSessionsPerPackage;

        // Dimension 4 — Temporal cooling (>= COOLING_HOURS_FLOOR)
        uint32 coolingPeriodHours;

        // Dimension 5 — Pricing
        uint256 minPriceVapi;               // in VAPI token units
        uint8   listingType;                // 0=fixed, 1=auction

        // Dimension 6 — ZK proof depth: covered by the Tier bools above.

        // Dimension 7 — Autonomy level (0=manual,1=approval,2=notify,3=full)
        uint8   autonomyLevel;

        // Manifest versioning (set by the contract on store)
        uint64  updatedAt;
        bytes32 manifestHash;               // keccak256(abi.encode(policy fields))
    }

    /// gamer => manifest. A zero updatedAt means "no manifest set".
    mapping(address => ConsentManifest) private _manifests;

    /// Lifetime count of manifest writes (not decremented).
    uint256 public totalManifests;

    event ManifestUpdated(
        address indexed gamer,
        bytes32 indexed manifestHash,
        uint8           autonomyLevel,
        uint16          minSessionsPerPackage,
        uint32          coolingPeriodHours,
        uint256         blockNumber
    );

    constructor(address initialOwner) Ownable(initialOwner) {}

    /// @notice Set or replace the caller's consent manifest. msg.sender is the
    ///         gamer (self-sovereign — the bridge can never call this).
    ///         Reverts when a protocol floor is violated or autonomyLevel is
    ///         out of range. The contract stamps updatedAt + manifestHash; any
    ///         caller-supplied values for those two fields are ignored.
    function setManifest(ConsentManifest calldata m) external nonReentrant {
        require(m.minSessionsPerPackage >= MIN_SESSIONS_FLOOR,
                "VCMR: aggregation floor (min 10 sessions)");
        require(m.coolingPeriodHours >= COOLING_HOURS_FLOOR,
                "VCMR: cooling floor (min 72 hours)");
        require(m.autonomyLevel <= AUTONOMY_MAX, "VCMR: bad autonomyLevel");
        require(m.listingType <= 1, "VCMR: bad listingType");

        bytes32 h = _computeManifestHash(m);
        ConsentManifest memory stored = m;
        stored.updatedAt = uint64(block.timestamp);
        stored.manifestHash = h;
        _manifests[msg.sender] = stored;
        totalManifests++;

        emit ManifestUpdated(
            msg.sender, h, m.autonomyLevel,
            m.minSessionsPerPackage, m.coolingPeriodHours, block.number
        );
    }

    /// @notice Return a gamer's stored manifest. updatedAt == 0 means none set.
    function getManifest(address gamer) external view returns (ConsentManifest memory) {
        return _manifests[gamer];
    }

    /// @notice True iff the gamer has a manifest stored.
    function hasManifest(address gamer) external view returns (bool) {
        return _manifests[gamer].updatedAt != 0;
    }

    /// @notice Deterministic digest over the POLICY fields of a manifest
    ///         (excludes updatedAt + manifestHash, which are contract-stamped).
    ///         Pure — usable off-chain by the bridge to bind a listing to the
    ///         exact policy that authorised it.
    function computeManifestHash(ConsentManifest calldata m)
        external pure returns (bytes32)
    {
        return _computeManifestHash(m);
    }

    function _computeManifestHash(ConsentManifest memory m)
        internal pure returns (bytes32)
    {
        return keccak256(abi.encode(
            m.allowAggregateStats,
            m.allowSkillRankingProof,
            m.allowTrajectoryProof,
            m.allowContextPerformanceProof,
            m.allowFullSessionProof,
            m.allowAcademic,
            m.allowGameDev,
            m.allowEsports,
            m.allowBrand,
            m.allowAnonymous,
            m.minSessionsPerPackage,
            m.coolingPeriodHours,
            m.minPriceVapi,
            m.listingType,
            m.autonomyLevel
        ));
    }
}
