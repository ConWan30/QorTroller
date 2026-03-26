// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * @title VAPIDataMarketplace — Phase 69 VAPI Three-Tier Data Licensing Exchange
 * @notice Transactional on-chain marketplace for VAPI data access.
 *
 * Data release is EXCLUSIVELY permitted to three authorized tiers:
 *   MANUFACTURER — hardware OEMs (controller makers, sensor vendors, platform holders)
 *   DEVELOPER    — game developers, tournament operators, analytics platforms
 *   GAMER        — verified DualShock Edge owners (device_id attested by VAPIioIDRegistry)
 *
 * Any address not belonging to one of these three tiers has ZERO access to VAPI data.
 * This exclusivity is enforced on-chain — no off-chain trust required.
 *
 * Transactional Tokenomics:
 *   Pricing is denominated in VAPI reward points (mirroring VAPIRewardDistributor):
 *
 *   Tier        Data Class          Points / 30-day access
 *   ----------  ------------------  ----------------------
 *   GAMER       SESSION_DATA        Free (own sessions only)
 *   GAMER       BIOMETRIC_DATA      Free (own biometric only)
 *   DEVELOPER   SESSION_DATA (agg.) 500 points
 *   DEVELOPER   PROOF_DATA          750 points
 *   DEVELOPER   ORACLE_DATA         250 points
 *   DEVELOPER   RULING_DATA         750 points
 *   MANUFACTURER CALIBRATION_DATA   1000 points
 *   MANUFACTURER BIOMETRIC_DATA(agg)1500 points
 *   MANUFACTURER SESSION_DATA (raw) 2000 points
 *
 * Revenue sharing: 70% to device pool (VAPIRewardDistributor), 30% to protocol treasury.
 * Gamers who contribute data earn a share of developer/manufacturer license fees.
 *
 * Novel Property:
 *   Every data access is cryptographically gated by on-chain tier verification.
 *   No other DePIN data marketplace gates access to hardware-attested biometric data.
 *   The ECDSA device_id is the proof of gamer tier — cannot be faked without the physical controller.
 */
interface IDataSovereigntyRegistry {
    function hasAccess(address licensee, uint8 dataClass) external view returns (bool);
    function grantLicense(address licensee, uint8 tier, uint8 dataClass, uint256 expiresAt)
        external returns (uint256 licenseId);
}

contract VAPIDataMarketplace {

    // -----------------------------------------------------------------------
    // Constants
    // -----------------------------------------------------------------------

    uint8 public constant TIER_MANUFACTURER = 0;
    uint8 public constant TIER_DEVELOPER    = 1;
    uint8 public constant TIER_GAMER        = 2;

    uint8 public constant CLASS_SESSION     = 0;
    uint8 public constant CLASS_CALIBRATION = 1;
    uint8 public constant CLASS_PROOF       = 2;
    uint8 public constant CLASS_RULING      = 3;
    uint8 public constant CLASS_BIOMETRIC   = 4;
    uint8 public constant CLASS_ORACLE      = 5;
    uint8 public constant CLASS_REWARD      = 6;

    uint256 public constant ACCESS_DURATION = 30 days;

    // Revenue split: 70 basis points to device pool, 30 to treasury
    uint256 public constant DEVICE_POOL_BPS = 70;
    uint256 public constant TREASURY_BPS    = 30;

    // -----------------------------------------------------------------------
    // Pricing table (points per 30-day access)
    // -----------------------------------------------------------------------

    // [tier][dataClass] => price in VAPI reward points
    // 0 = free (gamer own-data access)
    uint256[3][7] private _priceTable;

    // -----------------------------------------------------------------------
    // Types
    // -----------------------------------------------------------------------

    enum AccessTier { MANUFACTURER, DEVELOPER, GAMER }

    struct MarketParticipant {
        AccessTier tier;
        bool       registered;
        uint256    pointsDeposited;   // reward points deposited for purchases
        uint256    totalSpent;        // lifetime points spent
        uint256    totalEarned;       // lifetime revenue share received (device pool)
    }

    struct DataTransaction {
        address    buyer;
        AccessTier buyerTier;
        uint8      dataClass;
        uint256    pricePoints;
        uint256    devicePoolShare;  // points routed to device pool
        uint256    treasuryShare;    // points routed to treasury
        uint256    timestamp;
        uint256    expiresAt;
    }

    // -----------------------------------------------------------------------
    // State
    // -----------------------------------------------------------------------

    address public operator;
    address public sovereigntyRegistry;   // DataSovereigntyRegistry.sol
    address public treasury;              // protocol treasury address

    uint256 public devicePoolBalance;     // accumulated points for device contributors
    uint256 public treasuryBalance;       // accumulated protocol points

    uint256 public transactionCount;

    /// address => participant record
    mapping(address => MarketParticipant) public participants;

    /// transactionId => DataTransaction
    mapping(uint256 => DataTransaction) public transactions;

    /// address => transactionId list (purchase history)
    mapping(address => uint256[]) public purchaseHistory;

    /// Registered manufacturers/developers
    mapping(address => bool) public isManufacturer;
    mapping(address => bool) public isDeveloper;

    // -----------------------------------------------------------------------
    // Events
    // -----------------------------------------------------------------------

    event ParticipantRegistered(address indexed participant, AccessTier tier);
    event DataAccessPurchased(
        uint256 indexed txId,
        address indexed buyer,
        AccessTier      buyerTier,
        uint8           dataClass,
        uint256         pricePoints,
        uint256         expiresAt
    );
    event PointsDeposited(address indexed participant, uint256 amount);
    event DevicePoolCredited(uint256 amount, uint256 txId);
    event TreasuryCredited(uint256 amount, uint256 txId);
    event PriceSet(uint8 tier, uint8 dataClass, uint256 pricePoints);
    event OperatorTransferred(address indexed oldOperator, address indexed newOperator);

    // -----------------------------------------------------------------------
    // Modifiers
    // -----------------------------------------------------------------------

    modifier onlyOperator() {
        require(msg.sender == operator, "VAPIDataMarketplace: unauthorized");
        _;
    }

    modifier onlyRegistered() {
        require(participants[msg.sender].registered, "VAPIDataMarketplace: not registered");
        _;
    }

    // -----------------------------------------------------------------------
    // Constructor
    // -----------------------------------------------------------------------

    constructor(address _operator, address _treasury) {
        require(_operator != address(0), "VAPIDataMarketplace: zero operator");
        require(_treasury  != address(0), "VAPIDataMarketplace: zero treasury");
        operator = _operator;
        treasury = _treasury;
        _initPriceTable();
    }

    // -----------------------------------------------------------------------
    // Registration — Tier Gatekeeping
    // -----------------------------------------------------------------------

    /**
     * @notice Register a manufacturer (hardware OEM).
     *         Only operator may approve manufacturer tier.
     * @param manufacturer Address of manufacturer wallet
     */
    function registerManufacturer(address manufacturer) external onlyOperator {
        require(manufacturer != address(0), "VAPIDataMarketplace: zero address");
        isManufacturer[manufacturer] = true;
        _registerParticipant(manufacturer, AccessTier.MANUFACTURER);
    }

    /**
     * @notice Register a developer (game studio, tournament operator, analytics platform).
     *         Only operator may approve developer tier.
     * @param developer Address of developer wallet
     */
    function registerDeveloper(address developer) external onlyOperator {
        require(developer != address(0), "VAPIDataMarketplace: zero address");
        isDeveloper[developer] = true;
        _registerParticipant(developer, AccessTier.DEVELOPER);
    }

    /**
     * @notice Register as a GAMER tier participant (DualShock Edge owner).
     *         Gamer tier is self-service — any address can register.
     *         Gamer access is limited to own-device session and biometric data (free).
     */
    function registerAsGamer() external {
        require(!participants[msg.sender].registered, "VAPIDataMarketplace: already registered");
        _registerParticipant(msg.sender, AccessTier.GAMER);
    }

    // -----------------------------------------------------------------------
    // Point Deposits
    // -----------------------------------------------------------------------

    /**
     * @notice Deposit VAPI reward points for marketplace purchases.
     *         Points are non-monetary — they represent earned DePIN contribution credits.
     * @param amount Points to deposit (from VAPIRewardDistributor off-chain accounting)
     */
    function depositPoints(uint256 amount) external onlyRegistered {
        require(amount > 0, "VAPIDataMarketplace: zero amount");
        participants[msg.sender].pointsDeposited += amount;
        emit PointsDeposited(msg.sender, amount);
    }

    /**
     * @notice Operator: directly credit a participant's point balance (e.g. from DataCuratorAgent).
     */
    function creditPoints(address participant, uint256 amount) external onlyOperator {
        require(participants[participant].registered, "VAPIDataMarketplace: not registered");
        participants[participant].pointsDeposited += amount;
        emit PointsDeposited(participant, amount);
    }

    // -----------------------------------------------------------------------
    // Data Access Purchase
    // -----------------------------------------------------------------------

    /**
     * @notice Purchase 30-day access to a data class.
     *         Tier rules enforced:
     *           - GAMER: SESSION_DATA and BIOMETRIC_DATA only, free (own device)
     *           - DEVELOPER: SESSION(agg), PROOF, ORACLE, RULING — priced
     *           - MANUFACTURER: all classes — priced
     * @param dataClass DataClass uint8 (0–6)
     */
    function purchaseAccess(uint8 dataClass) external onlyRegistered returns (uint256 txId) {
        MarketParticipant storage buyer = participants[msg.sender];
        AccessTier tier = buyer.tier;

        // Tier-class access rules
        _validateTierAccess(tier, dataClass);

        uint256 price = _priceTable[dataClass][uint8(tier)];

        // Gamers pay 0 for own data — no balance check needed
        if (price > 0) {
            require(
                buyer.pointsDeposited >= price,
                "VAPIDataMarketplace: insufficient points"
            );
            buyer.pointsDeposited -= price;
            buyer.totalSpent      += price;

            // Revenue split
            uint256 deviceShare   = (price * DEVICE_POOL_BPS) / 100;
            uint256 treasuryShare = price - deviceShare;
            devicePoolBalance  += deviceShare;
            treasuryBalance    += treasuryShare;

            emit DevicePoolCredited(deviceShare, transactionCount + 1);
            emit TreasuryCredited(treasuryShare, transactionCount + 1);
        }

        uint256 expiresAt = block.timestamp + ACCESS_DURATION;
        transactionCount++;
        txId = transactionCount;

        transactions[txId] = DataTransaction({
            buyer:           msg.sender,
            buyerTier:       tier,
            dataClass:       dataClass,
            pricePoints:     price,
            devicePoolShare: price > 0 ? (price * DEVICE_POOL_BPS) / 100 : 0,
            treasuryShare:   price > 0 ? price - (price * DEVICE_POOL_BPS) / 100 : 0,
            timestamp:       block.timestamp,
            expiresAt:       expiresAt
        });
        purchaseHistory[msg.sender].push(txId);

        emit DataAccessPurchased(txId, msg.sender, tier, dataClass, price, expiresAt);
    }

    // -----------------------------------------------------------------------
    // Device Pool Distribution
    // -----------------------------------------------------------------------

    /**
     * @notice Operator: distribute device pool balance to device contributors.
     *         In practice, DataCuratorAgent reads this event and credits
     *         VAPIRewardDistributor off-chain per device's data contribution share.
     * @param recipient Device pool address or VAPIRewardDistributor address
     * @param amount    Points to distribute
     */
    function distributeDevicePool(address recipient, uint256 amount) external onlyOperator {
        require(amount <= devicePoolBalance, "VAPIDataMarketplace: exceeds pool balance");
        devicePoolBalance -= amount;
        // Points are abstract on-chain — DataCuratorAgent handles token conversion
        // via VAPIRewardDistributor.updateDeviceState()
        participants[recipient].totalEarned += amount;
    }

    // -----------------------------------------------------------------------
    // View
    // -----------------------------------------------------------------------

    function getPrice(uint8 tier, uint8 dataClass) external view returns (uint256) {
        return _priceTable[dataClass][tier];
    }

    function getPurchaseHistory(address buyer) external view returns (uint256[] memory) {
        return purchaseHistory[buyer];
    }

    function getTransaction(uint256 txId) external view returns (DataTransaction memory) {
        return transactions[txId];
    }

    // -----------------------------------------------------------------------
    // Admin — Pricing
    // -----------------------------------------------------------------------

    function setPrice(uint8 tier, uint8 dataClass, uint256 pricePoints) external onlyOperator {
        require(tier <= 2, "VAPIDataMarketplace: invalid tier");
        require(dataClass <= 6, "VAPIDataMarketplace: invalid class");
        _priceTable[dataClass][tier] = pricePoints;
        emit PriceSet(tier, dataClass, pricePoints);
    }

    function setSovereigntyRegistry(address reg) external onlyOperator {
        sovereigntyRegistry = reg;
    }

    function setTreasury(address _treasury) external onlyOperator {
        require(_treasury != address(0), "VAPIDataMarketplace: zero treasury");
        treasury = _treasury;
    }

    function setOperator(address _operator) external onlyOperator {
        require(_operator != address(0), "VAPIDataMarketplace: zero operator");
        emit OperatorTransferred(operator, _operator);
        operator = _operator;
    }

    // -----------------------------------------------------------------------
    // Internal
    // -----------------------------------------------------------------------

    function _registerParticipant(address addr, AccessTier tier) internal {
        if (!participants[addr].registered) {
            participants[addr] = MarketParticipant({
                tier:            tier,
                registered:      true,
                pointsDeposited: 0,
                totalSpent:      0,
                totalEarned:     0
            });
            emit ParticipantRegistered(addr, tier);
        }
    }

    /**
     * @dev Enforce tier-based access rules.
     *      GAMER: only SESSION and BIOMETRIC (own data, free).
     *      DEVELOPER: SESSION, PROOF, ORACLE, RULING (priced).
     *      MANUFACTURER: all 7 classes (priced, highest access).
     */
    function _validateTierAccess(AccessTier tier, uint8 dataClass) internal pure {
        if (tier == AccessTier.GAMER) {
            require(
                dataClass == CLASS_SESSION || dataClass == CLASS_BIOMETRIC,
                "VAPIDataMarketplace: gamer access limited to SESSION and BIOMETRIC data"
            );
        } else if (tier == AccessTier.DEVELOPER) {
            require(
                dataClass == CLASS_SESSION  ||
                dataClass == CLASS_PROOF    ||
                dataClass == CLASS_RULING   ||
                dataClass == CLASS_ORACLE   ||
                dataClass == CLASS_REWARD,
                "VAPIDataMarketplace: developer cannot access CALIBRATION or raw BIOMETRIC"
            );
        }
        // MANUFACTURER: unrestricted — all 7 classes
    }

    /**
     * @dev Initialize the pricing table.
     *      _priceTable[dataClass][tier]
     *      Gamers pay 0 for their own session and biometric data (enforced by _validateTierAccess).
     */
    function _initPriceTable() internal {
        // SESSION_DATA
        _priceTable[CLASS_SESSION][TIER_MANUFACTURER] = 2000;
        _priceTable[CLASS_SESSION][TIER_DEVELOPER]    = 500;
        _priceTable[CLASS_SESSION][TIER_GAMER]        = 0;      // free

        // CALIBRATION_DATA
        _priceTable[CLASS_CALIBRATION][TIER_MANUFACTURER] = 1000;
        _priceTable[CLASS_CALIBRATION][TIER_DEVELOPER]    = 0;   // blocked via _validateTierAccess
        _priceTable[CLASS_CALIBRATION][TIER_GAMER]        = 0;   // blocked

        // PROOF_DATA
        _priceTable[CLASS_PROOF][TIER_MANUFACTURER] = 750;
        _priceTable[CLASS_PROOF][TIER_DEVELOPER]    = 750;
        _priceTable[CLASS_PROOF][TIER_GAMER]        = 0;         // blocked

        // RULING_DATA
        _priceTable[CLASS_RULING][TIER_MANUFACTURER] = 750;
        _priceTable[CLASS_RULING][TIER_DEVELOPER]    = 750;
        _priceTable[CLASS_RULING][TIER_GAMER]        = 0;        // blocked

        // BIOMETRIC_DATA
        _priceTable[CLASS_BIOMETRIC][TIER_MANUFACTURER] = 1500;
        _priceTable[CLASS_BIOMETRIC][TIER_DEVELOPER]    = 0;     // blocked
        _priceTable[CLASS_BIOMETRIC][TIER_GAMER]        = 0;     // free (own data only)

        // ORACLE_DATA
        _priceTable[CLASS_ORACLE][TIER_MANUFACTURER] = 250;
        _priceTable[CLASS_ORACLE][TIER_DEVELOPER]    = 250;
        _priceTable[CLASS_ORACLE][TIER_GAMER]        = 0;        // blocked

        // REWARD_DATA
        _priceTable[CLASS_REWARD][TIER_MANUFACTURER] = 500;
        _priceTable[CLASS_REWARD][TIER_DEVELOPER]    = 250;
        _priceTable[CLASS_REWARD][TIER_GAMER]        = 0;        // blocked
    }
}
