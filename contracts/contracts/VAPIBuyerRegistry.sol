// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/access/Ownable.sol";
import "@openzeppelin/contracts/utils/ReentrancyGuard.sol";

/// @title VAPIBuyerRegistry — Buyer category credential registry
/// @notice Curator-attested registry of buyer credentials for the QorTroller
///         data marketplace. The Curator (vapi-curator agent, agentId
///         0xed6a2df5...) attests to a buyer's category — CATEGORY_ACADEMIC,
///         CATEGORY_GAME_DEV, CATEGORY_ESPORTS, or CATEGORY_BRAND — after
///         off-chain documentation review. Credentials expire after 365 days
///         and require re-attestation.
///
///         Trust model: CURATOR-ATTESTED. Structurally parallel to
///         VAPIManufacturerDeviceRegistry (manufacturer attests hardware
///         birth); same pattern, different subjects. Both registries share
///         the design where the attester is operator-bonded and the attestation
///         emits a public on-chain event.
///
///         Governance dependency: the Curator's scope-expansion governance
///         ceremony (BBG.proposeWithVHP proposalHash 0x59fb9996..., landed
///         2026-05-28 tx 0xba96f7cb...) is a load-bearing prerequisite for
///         this contract being useful. Phase 4a + 4b scope-update fires
///         (2026-05-28 txs 0x54a1cf31... + 0x21dcfab5...) flipped the
///         Curator's authorized scope to the manifest-committed hash
///         0xab874f62.... Without those, calling setCuratorWallet() with the
///         Curator's wallet would still authorize this contract, but
///         AgentAdjudicationRegistry.requireAgentScope would not pass the
///         Curator's broader actions.
///
///         FROZEN-v1 surface (pinned by PV-CI INV-BUY-001/002):
///           CATEGORY_ACADEMIC  = 1
///           CATEGORY_GAME_DEV  = 2
///           CATEGORY_ESPORTS   = 3
///           CATEGORY_BRAND     = 4
///         Category 5+ are reserved for future governance-approved categories
///         (new categories MUST extend this enum strictly upward; no reorder).
///
/// @dev    Only the contract owner (bridge wallet) may set the Curator
///         wallet. Only the Curator wallet may issue credentials. Both the
///         Curator wallet and the owner may revoke. View functions are
///         public for off-chain query and on-chain composability.
///
/// @dev    Anti-replay: issueCredential reverts if buyerDID is already
///         registered. Re-attestation after a credential expires or is
///         revoked is NOT permitted by this v1 (the buyerDID slot stays
///         consumed). A future v2 may add a re-attestation path with
///         explicit cycle counting; v1 chooses simple permanence per the
///         framework's "Operator decisions required before deploy" Q2 on
///         this contract.
contract VAPIBuyerRegistry is Ownable, ReentrancyGuard {

    /// @dev Academic researcher: universities, public research labs, etc.
    uint8 public constant CATEGORY_ACADEMIC = 1;
    /// @dev Game developer: studios, indie devs, engine teams shipping games.
    uint8 public constant CATEGORY_GAME_DEV = 2;
    /// @dev Esports organization: tournament operators, leagues, team orgs.
    uint8 public constant CATEGORY_ESPORTS  = 3;
    /// @dev Brand: advertisers, marketing partners. Subject to additional
    ///      off-chain operator confirmation per manifest CAP-001 constraint.
    uint8 public constant CATEGORY_BRAND    = 4;

    struct BuyerCredential {
        bytes32  buyerDID;       // ioID DID of buyer entity
        uint8    categoryId;     // CATEGORY_* constant
        bytes32  evidenceHash;   // sha256(off-chain documentation)
        address  attestedBy;     // Curator wallet address (msg.sender at issue)
        uint64   issuedAt;       // block.timestamp at issue
        uint64   expiresAt;      // issuedAt + 365 days
        bool     active;
    }

    /// @dev buyerDID => credential record. Slot stays consumed on revoke /
    ///      expiry; re-attestation under same buyerDID NOT permitted in v1.
    mapping(bytes32 => BuyerCredential) public credentials;

    /// @dev buyerDID => has-been-registered? Stays true on revoke / expiry.
    mapping(bytes32 => bool) public registered;

    /// @notice The wallet authorized to call issueCredential / revokeCredential.
    ///         Set by owner only, post-governance. address(0) until set (any
    ///         issuance call before set reverts).
    address public curatorWallet;

    event CredentialIssued(
        bytes32 indexed buyerDID,
        uint8 categoryId,
        address attestedBy,
        bytes32 evidenceHash,
        uint64 expiresAt
    );
    event CredentialRevoked(bytes32 indexed buyerDID, address revokedBy);
    event CuratorWalletSet(address indexed oldWallet, address indexed newWallet);

    constructor(address initialOwner) Ownable(initialOwner) {
        // Ownable's constructor reverts on zero-address.
    }

    /// @notice Set or update the Curator wallet authorized to attest buyers.
    /// @dev    Owner-only. Setting to address(0) effectively pauses issuance
    ///         (any issueCredential call will revert on "Curator wallet not
    ///         set"). This is the rollback path per the governance manifest.
    function setCuratorWallet(address wallet) external onlyOwner {
        address oldWallet = curatorWallet;
        curatorWallet = wallet;
        emit CuratorWalletSet(oldWallet, wallet);
    }

    /// @notice Issue a buyer credential. Curator-only.
    /// @param buyerDID     bytes32 ioID DID of the buyer entity
    /// @param categoryId   CATEGORY_* constant (1..4)
    /// @param evidenceHash sha256 of the off-chain documentation reviewed
    function issueCredential(
        bytes32 buyerDID,
        uint8   categoryId,
        bytes32 evidenceHash
    ) external nonReentrant {
        require(curatorWallet != address(0), "Curator wallet not set");
        require(msg.sender == curatorWallet, "only Curator");
        require(buyerDID != bytes32(0), "zero buyerDID");
        require(!registered[buyerDID], "already registered");
        require(
            categoryId >= CATEGORY_ACADEMIC && categoryId <= CATEGORY_BRAND,
            "invalid category"
        );

        uint64 nowTs = uint64(block.timestamp);
        credentials[buyerDID] = BuyerCredential({
            buyerDID:     buyerDID,
            categoryId:   categoryId,
            evidenceHash: evidenceHash,
            attestedBy:   msg.sender,
            issuedAt:     nowTs,
            expiresAt:    nowTs + 365 days,
            active:       true
        });
        registered[buyerDID] = true;

        emit CredentialIssued(
            buyerDID, categoryId, msg.sender, evidenceHash, nowTs + 365 days
        );
    }

    /// @notice Revoke a buyer credential. Curator or owner may revoke.
    /// @dev    Per framework Q3: revocation marks the credential inactive but
    ///         does NOT free the buyerDID slot (re-attestation under same DID
    ///         is not v1 behavior). A subsequent revoke on an already-inactive
    ///         credential is permitted (no-op effect, emits event for audit).
    function revokeCredential(bytes32 buyerDID) external {
        require(
            msg.sender == curatorWallet || msg.sender == owner(),
            "unauthorized"
        );
        require(registered[buyerDID], "not registered");
        credentials[buyerDID].active = false;
        emit CredentialRevoked(buyerDID, msg.sender);
    }

    /// @notice Predicate: is a buyer's credential valid for a given category?
    /// @dev    Used by composability points (off-chain marketplace gate,
    ///         on-chain purchase paths). Returns false for any of:
    ///         - buyerDID never registered
    ///         - credential revoked (active=false)
    ///         - credential expired (block.timestamp >= expiresAt)
    ///         - category mismatch
    function isValidCredential(bytes32 buyerDID, uint8 categoryId)
        external view returns (bool)
    {
        if (!registered[buyerDID]) return false;
        BuyerCredential memory c = credentials[buyerDID];
        return c.active
            && c.categoryId == categoryId
            && block.timestamp < c.expiresAt;
    }

    /// @notice Read the category of a buyer's credential. Returns 0 if not
    ///         registered (no valid category is 0).
    function getCategory(bytes32 buyerDID) external view returns (uint8) {
        return credentials[buyerDID].categoryId;
    }

    /// @notice Read the full credential struct for a buyer.
    /// @dev    Solidity's auto-generated getter for the `credentials` mapping
    ///         returns the 7-tuple positionally; this method exposes the same
    ///         data with named return values for readability + off-chain
    ///         ABI ergonomics (no field-position drift risk).
    function getCredential(bytes32 buyerDID)
        external view
        returns (
            bytes32 _buyerDID,
            uint8   _categoryId,
            bytes32 _evidenceHash,
            address _attestedBy,
            uint64  _issuedAt,
            uint64  _expiresAt,
            bool    _active
        )
    {
        BuyerCredential memory c = credentials[buyerDID];
        return (c.buyerDID, c.categoryId, c.evidenceHash, c.attestedBy,
                c.issuedAt, c.expiresAt, c.active);
    }
}
