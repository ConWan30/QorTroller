// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * @title VAPIDataMarketplaceListings — Phase 238-MARKETPLACE Provenance-Anchored Listing Layer (PALL)
 * @notice Per-listing cryptographic provenance extension on top of Phase 69 VAPIDataMarketplace.
 *
 * Where Phase 69 VAPIDataMarketplace ships tier-class data licensing (MANUFACTURER/DEVELOPER/GAMER
 * across 7 data classes with 30-day blanket access), this extension contract adds:
 *
 *   1. Per-listing storage keyed by 32-byte LISTING-v1 commitment (Phase 238 FROZEN-v1 primitive)
 *   2. On-chain tier computation by reading IAdjudicationRegistry.isRecorded() for each component
 *      anchor (SEPPROOF + BIOMETRIC-SNAPSHOT + CORPUS-SNAPSHOT + GIC) — tier is cryptographic
 *      property, not seller-attested
 *   3. Multiplier table (1.0x / 1.5x / 2.0x / 3.0x) computed from anchor count
 *   4. Forward-compat curator hook (Phase 238 Step I) — allows a designated agent address
 *      (e.g., the Operator Initiative's "Curator" agent) to suspend listings beyond operator
 *
 * Composition NOT modification: this contract REFERENCES Phase 69 + AdjudicationRegistry but
 * does NOT modify either.  All Phase 69 tier registration / 70-30 split / 30-day access logic
 * is preserved unchanged.  PALL operates as a parallel provenance layer.
 *
 * Payment plumbing is bridge-side (Phase 238 Steps E+F).  This contract emits events that
 * the bridge consumes for VAPI reward point accounting in the Phase 69 ledger.  No on-chain
 * token transfers in this contract — V1 stays in Phase 69 reward-points accounting per
 * operator decision Q2 (see plan file).
 *
 * Public input order for listings (FROZEN — must match LISTING-v1 commitment formula in
 * bridge/vapi_bridge/listing_primitive.py):
 *
 *   listing_commitment = SHA-256(
 *       b"VAPI-LISTING-v1"          (15 bytes)
 *       || sepproof_commitment      (32 bytes; zeros if absent)
 *       || biometric_snapshot_hash  (32 bytes; zeros if absent)
 *       || corpus_snapshot_hash     (32 bytes; zeros if absent)
 *       || gic_hash                 (32 bytes; zeros if absent)
 *       || consent_bitmask_be       (4 bytes; bit 3 = MARKETPLACE required)
 *       || data_class_be            (1 byte; 0..6 Phase 69 enum)
 *       || price_micro_iotx_be      (8 bytes; uint64 = price * 1e6 IOTX)
 *       || ipfs_cid_hash            (32 bytes; SHA-256 of CIDv1 string)
 *       || ts_ns_be                 (8 bytes; uint64 ns timestamp)
 *   ) = 196 bytes -> SHA-256 -> 32 bytes
 *
 * @dev DEPLOYMENT NOTE — Two-stage:
 *   Stage 1: Phase 69 VAPIDataMarketplace already deployed (LIVE).
 *   Stage 2: Deploy this extension contract with constructor args
 *            (phase69MarketplaceAddress, adjudicationRegistryAddress).
 *            Both addresses immutable + zero-address rejected.
 *
 *   Curator role (Step I): post-deploy, operator calls setCurator(curatorAddress)
 *   to enable the Operator Initiative's third agent.  Default zero = no curator
 *   (operator-only admin).  Forward-compat ensures this contract works without
 *   Curator existence at deploy time.
 */

interface IAdjudicationRegistryListings {
    function isRecorded(bytes32 poadHash) external view returns (bool);
}

interface IVAPIDataMarketplaceListings {
    enum Tier { Basic, Verified, Attested, Premium }
}

interface IPhase69Marketplace {
    function participants(address) external view returns (
        uint8 tier,
        bool registered,
        uint256 pointsDeposited,
        uint256 totalSpent,
        uint256 totalEarned
    );
}

contract VAPIDataMarketplaceListings is IVAPIDataMarketplaceListings {

    // -----------------------------------------------------------------------
    // Constants — Tier multipliers in basis points (10000 = 1.0×)
    // -----------------------------------------------------------------------

    uint256 public constant TIER_BASIC_MULTIPLIER_BPS    = 10000;  // 1.0×
    uint256 public constant TIER_VERIFIED_MULTIPLIER_BPS = 15000;  // 1.5×
    uint256 public constant TIER_ATTESTED_MULTIPLIER_BPS = 20000;  // 2.0×
    uint256 public constant TIER_PREMIUM_MULTIPLIER_BPS  = 30000;  // 3.0×
    uint256 public constant BPS_DENOMINATOR              = 10000;

    // CONSENT bitmask bits — match Phase 237 ConsentCategory enum
    uint32 public constant CONSENT_BIT_TOURNAMENT_GATE     = 1 << 0;
    uint32 public constant CONSENT_BIT_ANONYMIZED_RESEARCH = 1 << 1;
    uint32 public constant CONSENT_BIT_MANUFACTURER_CERT   = 1 << 2;
    uint32 public constant CONSENT_BIT_MARKETPLACE         = 1 << 3;

    // Phase 69 GAMER tier value (matches AccessTier enum index 2)
    uint8 public constant PHASE69_TIER_GAMER = 2;

    // -----------------------------------------------------------------------
    // Storage
    // -----------------------------------------------------------------------

    /// @notice Phase 69 marketplace — tier auth delegated here
    address public immutable phase69Marketplace;

    /// @notice AdjudicationRegistry — anchor verification source
    address public immutable adjudicationRegistry;

    /// @notice Operator (admin) — set at deploy; transferable via setOperator
    address public operator;

    /// @notice Curator — Phase 238 Step I forward-compat. Zero = no curator.
    address public curator;

    /// @notice Listing record
    struct Listing {
        address seller;
        bytes32 sepproofCommitment;
        bytes32 biometricSnapshotHash;
        bytes32 corpusSnapshotHash;
        bytes32 gicHash;
        uint32  consentBitmask;
        uint8   dataClass;
        uint64  priceMicroIotx;
        bytes32 ipfsCidHash;
        uint64  tsNs;
        bool    suspended;
        bool    exists;
    }

    /// @notice Listing storage keyed by LISTING-v1 commitment
    mapping(bytes32 => Listing) public listings;

    /// @notice All listing commitments in creation order (paginated reads)
    bytes32[] public listingCommitments;

    /// @notice Per-seller listing index for fast querying
    mapping(address => bytes32[]) public listingsBySeller;

    // -----------------------------------------------------------------------
    // Events
    // -----------------------------------------------------------------------

    event ListingCreated(
        bytes32 indexed listingCommitment,
        address indexed seller,
        uint8   tier,
        uint8   dataClass,
        uint64  priceMicroIotx,
        bytes32 ipfsCidHash
    );

    event ListingSuspended(
        bytes32 indexed listingCommitment,
        address indexed by,
        string  reason
    );

    event CuratorTransferred(
        address indexed oldCurator,
        address indexed newCurator
    );

    event OperatorTransferred(
        address indexed oldOperator,
        address indexed newOperator
    );

    // -----------------------------------------------------------------------
    // Modifiers
    // -----------------------------------------------------------------------

    modifier onlyOperator() {
        require(msg.sender == operator, "PALL: not operator");
        _;
    }

    modifier onlyOperatorOrCurator() {
        require(
            msg.sender == operator
            || (curator != address(0) && msg.sender == curator),
            "PALL: not operator or curator"
        );
        _;
    }

    // -----------------------------------------------------------------------
    // Constructor
    // -----------------------------------------------------------------------

    constructor(address _phase69Marketplace, address _adjudicationRegistry) {
        require(_phase69Marketplace != address(0), "PALL: phase69 zero");
        require(_adjudicationRegistry != address(0), "PALL: adjReg zero");
        phase69Marketplace = _phase69Marketplace;
        adjudicationRegistry = _adjudicationRegistry;
        operator = msg.sender;
    }

    // -----------------------------------------------------------------------
    // Listing creation
    // -----------------------------------------------------------------------

    /**
     * @notice Create a new listing.
     * @param listingCommitment 32-byte LISTING-v1 commitment (computed off-chain per
     *                          bridge/vapi_bridge/listing_primitive.py FROZEN formula)
     * @param sepproofCommitment Phase 237 SEPPROOF anchor (zero if absent)
     * @param biometricSnapshotHash Phase 237 BIOMETRIC-SNAPSHOT anchor (zero if absent)
     * @param corpusSnapshotHash Phase 237.5 CORPUS-SNAPSHOT anchor (zero if absent)
     * @param gicHash GIC chain link hash (zero if absent)
     * @param consentBitmask uint32 — bit 3 (MARKETPLACE) MUST be set
     * @param dataClass uint8 in [0, 6] — Phase 69 DATA_TAXONOMY enum
     * @param priceMicroIotx uint64 — price * 1e6 IOTX (matches CORPUS-SNAPSHOT precedent)
     * @param ipfsCidHash 32-byte SHA-256 of the CIDv1 string for off-chain metadata archive
     * @param tsNs uint64 — listing creation time in nanoseconds
     *
     * Reverts:
     *   - listingCommitment is zero
     *   - listingCommitment already exists
     *   - caller is not registered as Phase 69 GAMER
     *   - consentBitmask missing MARKETPLACE bit
     *   - dataClass out of range
     *
     * Tier is computed at creation time by reading anchor presence via
     * IAdjudicationRegistry.isRecorded() — sellers cannot self-attest tier.
     */
    function createListing(
        bytes32 listingCommitment,
        bytes32 sepproofCommitment,
        bytes32 biometricSnapshotHash,
        bytes32 corpusSnapshotHash,
        bytes32 gicHash,
        uint32  consentBitmask,
        uint8   dataClass,
        uint64  priceMicroIotx,
        bytes32 ipfsCidHash,
        uint64  tsNs
    ) external returns (uint8 tierIndex) {
        require(listingCommitment != bytes32(0), "PALL: zero commitment");
        require(!listings[listingCommitment].exists, "PALL: listing exists");
        require(
            (consentBitmask & CONSENT_BIT_MARKETPLACE) != 0,
            "PALL: MARKETPLACE consent bit required"
        );
        require(dataClass <= 6, "PALL: data_class out of range");

        // Phase 69 GAMER auth — caller must be registered as a gamer
        (uint8 callerTier, bool callerRegistered, , , ) =
            IPhase69Marketplace(phase69Marketplace).participants(msg.sender);
        require(callerRegistered, "PALL: not registered in Phase 69");
        require(callerTier == PHASE69_TIER_GAMER, "PALL: not GAMER tier");

        // Compute tier from anchor presence (read-only, gas-cheap view calls)
        Tier tier = _computeTier(
            sepproofCommitment, biometricSnapshotHash,
            corpusSnapshotHash, gicHash
        );

        // Store
        listings[listingCommitment] = Listing({
            seller:                 msg.sender,
            sepproofCommitment:     sepproofCommitment,
            biometricSnapshotHash:  biometricSnapshotHash,
            corpusSnapshotHash:     corpusSnapshotHash,
            gicHash:                gicHash,
            consentBitmask:         consentBitmask,
            dataClass:              dataClass,
            priceMicroIotx:         priceMicroIotx,
            ipfsCidHash:            ipfsCidHash,
            tsNs:                   tsNs,
            suspended:              false,
            exists:                 true
        });
        listingCommitments.push(listingCommitment);
        listingsBySeller[msg.sender].push(listingCommitment);

        emit ListingCreated(
            listingCommitment, msg.sender, uint8(tier),
            dataClass, priceMicroIotx, ipfsCidHash
        );
        return uint8(tier);
    }

    // -----------------------------------------------------------------------
    // Tier computation (view) — reads AdjudicationRegistry.isRecorded()
    // -----------------------------------------------------------------------

    /**
     * @notice Compute tier from anchor presence count.
     * @dev Anchors counted as present iff non-zero AND IAdjudicationRegistry.isRecorded()=true.
     *      Pure on-chain computation — sellers cannot self-attest tier.
     *      Tier table:
     *        0 anchors → Basic    (1.0×)
     *        1 anchor  → Verified (1.5×)
     *        2-3 anchors → Attested (2.0×)
     *        4 anchors → Premium  (3.0×) — note: tournament-grade VHP check is bridge-side
     */
    function _computeTier(
        bytes32 sepproofCommitment,
        bytes32 biometricSnapshotHash,
        bytes32 corpusSnapshotHash,
        bytes32 gicHash
    ) internal view returns (Tier) {
        IAdjudicationRegistryListings reg =
            IAdjudicationRegistryListings(adjudicationRegistry);
        uint8 count = 0;
        if (sepproofCommitment != bytes32(0)
            && reg.isRecorded(sepproofCommitment)) {
            count++;
        }
        if (biometricSnapshotHash != bytes32(0)
            && reg.isRecorded(biometricSnapshotHash)) {
            count++;
        }
        if (corpusSnapshotHash != bytes32(0)
            && reg.isRecorded(corpusSnapshotHash)) {
            count++;
        }
        if (gicHash != bytes32(0) && reg.isRecorded(gicHash)) {
            count++;
        }
        if (count == 0) return Tier.Basic;
        if (count == 1) return Tier.Verified;
        if (count <= 3) return Tier.Attested;
        return Tier.Premium;
    }

    /// @notice External tier query for a stored listing.
    function getListingTier(bytes32 listingCommitment)
        external view returns (Tier)
    {
        Listing memory l = listings[listingCommitment];
        require(l.exists, "PALL: listing not found");
        return _computeTier(
            l.sepproofCommitment, l.biometricSnapshotHash,
            l.corpusSnapshotHash, l.gicHash
        );
    }

    /// @notice External multiplier query (basis points; 10000 = 1.0×).
    function getListingMultiplierBps(bytes32 listingCommitment)
        external view returns (uint256)
    {
        Listing memory l = listings[listingCommitment];
        require(l.exists, "PALL: listing not found");
        Tier t = _computeTier(
            l.sepproofCommitment, l.biometricSnapshotHash,
            l.corpusSnapshotHash, l.gicHash
        );
        if (t == Tier.Basic)    return TIER_BASIC_MULTIPLIER_BPS;
        if (t == Tier.Verified) return TIER_VERIFIED_MULTIPLIER_BPS;
        if (t == Tier.Attested) return TIER_ATTESTED_MULTIPLIER_BPS;
        return TIER_PREMIUM_MULTIPLIER_BPS;
    }

    /// @notice Listing existence check (cheaper than full read for buyers).
    function listingExists(bytes32 listingCommitment)
        external view returns (bool)
    {
        return listings[listingCommitment].exists;
    }

    /// @notice Listing count (for paginated reads).
    function getListingCount() external view returns (uint256) {
        return listingCommitments.length;
    }

    /// @notice Per-seller listing count.
    function getSellerListingCount(address seller)
        external view returns (uint256)
    {
        return listingsBySeller[seller].length;
    }

    // -----------------------------------------------------------------------
    // Suspension (operator or curator)
    // -----------------------------------------------------------------------

    /**
     * @notice Suspend a listing — fraud, consent revocation, or curation flag.
     *         Suspended listings remain in storage for audit trail but are
     *         marked suspended=true; bridge-side endpoints filter them out
     *         of buyer-facing browse results.
     * @dev Callable by operator OR curator (when curator is set).  Curator
     *      role exists for Phase 238 Step I (Operator Initiative third agent).
     */
    function suspendListing(bytes32 listingCommitment, string calldata reason)
        external onlyOperatorOrCurator
    {
        Listing storage l = listings[listingCommitment];
        require(l.exists, "PALL: listing not found");
        require(!l.suspended, "PALL: already suspended");
        l.suspended = true;
        emit ListingSuspended(listingCommitment, msg.sender, reason);
    }

    // -----------------------------------------------------------------------
    // Admin (operator-only)
    // -----------------------------------------------------------------------

    /**
     * @notice Set curator address — Phase 238 Step I forward-compat hook.
     *         Default zero = no curator (operator-only admin).
     *         Curator can suspend listings (cross-validation with operator)
     *         but cannot modify operator state.  Step I will define the
     *         Curator agent's full skill matrix in its Cedar bundle.
     */
    function setCurator(address newCurator) external onlyOperator {
        address old = curator;
        curator = newCurator;
        emit CuratorTransferred(old, newCurator);
    }

    /// @notice Transfer operator role.
    function setOperator(address newOperator) external onlyOperator {
        require(newOperator != address(0), "PALL: operator zero");
        address old = operator;
        operator = newOperator;
        emit OperatorTransferred(old, newOperator);
    }
}
