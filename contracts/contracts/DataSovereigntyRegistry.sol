// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * @title DataSovereigntyRegistry — Phase 69 VAPI Data Sovereignty Layer
 * @notice Immutable on-chain pledge declaring VAPI's ownership and control
 *         over all data derived from VAPI-certified DualShock Edge devices.
 *
 * The pledge is timestamped at IoTeX block N and is irrevocable.
 * schemaHash = keccak256(228B wire format + SQLite DDL + all table schemas)
 *
 * Data Release Policy (Three-Tier):
 *   MANUFACTURER — hardware makers (controller OEMs, sensor vendors)
 *   DEVELOPER    — game developers, tournament operators
 *   GAMER        — verified DualShock Edge owners (device_id on-chain)
 *
 * Data may only be accessed by an address holding a valid DataLicense for
 * the requested data class. Licenses are granted by the operator and can be
 * revoked at any time.
 *
 * Data classes (mirrors DataCuratorAgent.DATA_TAXONOMY):
 *   0 SESSION_DATA   1 CALIBRATION_DATA  2 PROOF_DATA   3 RULING_DATA
 *   4 BIOMETRIC_DATA 5 ORACLE_DATA       6 REWARD_DATA
 */
contract DataSovereigntyRegistry {

    // -----------------------------------------------------------------------
    // Types
    // -----------------------------------------------------------------------

    enum LicenseTier { MANUFACTURER, DEVELOPER, GAMER }
    enum DataClass {
        SESSION_DATA,
        CALIBRATION_DATA,
        PROOF_DATA,
        RULING_DATA,
        BIOMETRIC_DATA,
        ORACLE_DATA,
        REWARD_DATA
    }

    struct SovereigntyPledge {
        bytes32 schemaHash;        // keccak256(all VAPI data schemas)
        address sovereignAddress;  // bridge wallet — controls all data
        uint256 pledgeBlock;       // IoTeX block number (immutable)
        uint64  pledgeTimestamp;   // unix seconds
        string  declaration;       // human-readable sovereignty text
    }

    struct DataLicense {
        address licensee;
        LicenseTier tier;
        DataClass   dataClass;
        uint256     expiresAt;     // unix seconds; 0 = non-expiring
        bool        active;
    }

    // -----------------------------------------------------------------------
    // State
    // -----------------------------------------------------------------------

    address public operator;
    SovereigntyPledge public pledge;
    bool public pledged;

    /// licenseId counter
    uint256 public licenseCount;

    /// licenseId => DataLicense
    mapping(uint256 => DataLicense) public licenses;

    /// licensee address => licenseId list
    mapping(address => uint256[]) public licensesByAddress;

    /// licensee => dataClass => active licenseId (0 = none)
    mapping(address => mapping(uint8 => uint256)) public activeLicenseId;

    // -----------------------------------------------------------------------
    // Events
    // -----------------------------------------------------------------------

    event SovereigntyPledged(
        bytes32 indexed schemaHash,
        address indexed sovereignAddress,
        uint256 pledgeBlock,
        string  declaration
    );

    event LicenseGranted(
        uint256 indexed licenseId,
        address indexed licensee,
        LicenseTier tier,
        DataClass   dataClass,
        uint256     expiresAt
    );

    event LicenseRevoked(uint256 indexed licenseId, address indexed licensee);

    event OperatorTransferred(address indexed oldOperator, address indexed newOperator);

    // -----------------------------------------------------------------------
    // Modifiers
    // -----------------------------------------------------------------------

    modifier onlyOperator() {
        require(msg.sender == operator, "DataSovereigntyRegistry: unauthorized");
        _;
    }

    // -----------------------------------------------------------------------
    // Constructor
    // -----------------------------------------------------------------------

    constructor(address _operator) {
        require(_operator != address(0), "DataSovereigntyRegistry: zero operator");
        operator = _operator;
    }

    // -----------------------------------------------------------------------
    // Sovereignty Pledge (called once — immutable after)
    // -----------------------------------------------------------------------

    /**
     * @notice Commit the immutable VAPI data sovereignty pledge on-chain.
     * @param schemaHash  keccak256 of all VAPI data schemas (228B wire format + SQLite DDL)
     * @param declaration Human-readable sovereignty declaration text
     */
    function pledge_(bytes32 schemaHash, string calldata declaration) external onlyOperator {
        require(!pledged, "DataSovereigntyRegistry: already pledged");
        require(schemaHash != bytes32(0), "DataSovereigntyRegistry: zero schema hash");
        pledge = SovereigntyPledge({
            schemaHash:       schemaHash,
            sovereignAddress: msg.sender,
            pledgeBlock:      block.number,
            pledgeTimestamp:  uint64(block.timestamp),
            declaration:      declaration
        });
        pledged = true;
        emit SovereigntyPledged(schemaHash, msg.sender, block.number, declaration);
    }

    /**
     * @notice Read the sovereignty pledge.
     */
    function getPledge() external view returns (SovereigntyPledge memory) {
        require(pledged, "DataSovereigntyRegistry: not yet pledged");
        return pledge;
    }

    // -----------------------------------------------------------------------
    // License Management
    // -----------------------------------------------------------------------

    /**
     * @notice Grant a data access license to a licensee.
     * @param licensee  Address to grant access to (manufacturer/developer/gamer wallet)
     * @param tier      LicenseTier — MANUFACTURER / DEVELOPER / GAMER
     * @param dataClass DataClass — which data taxonomy class is licensed
     * @param expiresAt Unix timestamp expiry (0 = perpetual)
     */
    function grantLicense(
        address     licensee,
        LicenseTier tier,
        DataClass   dataClass,
        uint256     expiresAt
    ) external onlyOperator returns (uint256 licenseId) {
        require(licensee != address(0), "DataSovereigntyRegistry: zero licensee");
        require(
            expiresAt == 0 || expiresAt > block.timestamp,
            "DataSovereigntyRegistry: expired timestamp"
        );
        licenseCount++;
        licenseId = licenseCount;
        licenses[licenseId] = DataLicense({
            licensee:  licensee,
            tier:      tier,
            dataClass: dataClass,
            expiresAt: expiresAt,
            active:    true
        });
        licensesByAddress[licensee].push(licenseId);
        activeLicenseId[licensee][uint8(dataClass)] = licenseId;
        emit LicenseGranted(licenseId, licensee, tier, dataClass, expiresAt);
    }

    /**
     * @notice Revoke a data license.
     * @param licenseId License to revoke
     */
    function revokeLicense(uint256 licenseId) external onlyOperator {
        DataLicense storage lic = licenses[licenseId];
        require(lic.licensee != address(0), "DataSovereigntyRegistry: unknown license");
        require(lic.active, "DataSovereigntyRegistry: already revoked");
        lic.active = false;
        activeLicenseId[lic.licensee][uint8(lic.dataClass)] = 0;
        emit LicenseRevoked(licenseId, lic.licensee);
    }

    /**
     * @notice Check if a licensee has valid (non-expired, non-revoked) access to a data class.
     * @param licensee  Address to check
     * @param dataClass DataClass to check
     */
    function hasAccess(address licensee, DataClass dataClass) external view returns (bool) {
        uint256 id = activeLicenseId[licensee][uint8(dataClass)];
        if (id == 0) return false;
        DataLicense storage lic = licenses[id];
        if (!lic.active) return false;
        if (lic.expiresAt != 0 && block.timestamp > lic.expiresAt) return false;
        return true;
    }

    /**
     * @notice Get all licenseIds for a licensee.
     */
    function getLicenseIds(address licensee) external view returns (uint256[] memory) {
        return licensesByAddress[licensee];
    }

    // -----------------------------------------------------------------------
    // Admin
    // -----------------------------------------------------------------------

    function setOperator(address _operator) external onlyOperator {
        require(_operator != address(0), "DataSovereigntyRegistry: zero operator");
        emit OperatorTransferred(operator, _operator);
        operator = _operator;
    }
}
