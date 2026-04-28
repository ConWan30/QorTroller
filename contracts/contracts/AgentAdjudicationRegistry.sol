// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/access/Ownable.sol";
import "@openzeppelin/contracts/utils/ReentrancyGuard.sol";

/// @dev Local interface declaration for AgentRegistry's registration predicate.
///      Pass 2C Section 3.5 dependency: AgentAdjudicationRegistry verifies
///      agent existence before anchoring any action. Local declaration
///      matches the pattern established in Sessions 2 (AgentScope) and 4
///      (AgentSlashing) per Decision X resolution. The single-method
///      interface is duplicated across AgentScope, AgentSlashing, and this
///      contract — accepted cost for not refactoring AgentScope.
interface IAgentRegistry {
    function isRegistered(bytes32 agentId) external view returns (bool);
}

/// @dev Local interface declaration for AgentScope's operational-scope read.
///      Pass 2C Section 3.5 dependency: AgentAdjudicationRegistry reads
///      AgentScope.scopeRoot per Decision C from Session 2 (Interpretation 1
///      two-layer scope enforcement). AgentScope.scopeRoot is the
///      OPERATIONAL truth at moment of action; AgentRegistry.scopeHash is
///      the GOVERNANCE COMMITMENT at registration time. The two are
///      deliberately allowed to differ. This contract reads operational
///      truth.
interface IAgentScope {
    function getScopeRoot(bytes32 agentId) external view returns (bytes32);
}

/// @title AgentAdjudicationRegistry — Operator series Phase O0 attestation surface
/// @notice Agent-scoped on-chain action anchor. Per Design Pass 1 Conflict 1
///         Option A and Pass 2C Section 3.5. Hosts AGENT_COMMIT v1 (sixth
///         FROZEN-v1 primitive, per Pass 2A V10) and PHYSICAL_DATA_ATTESTATION
///         v1 (seventh FROZEN-v1 primitive, per Pass 2B Path 3) via the
///         actionType discriminator. Two reserved actionTypes
///         (AUDIT_LOG_CHECKPOINT, BOUNDARY_UPDATE) commit Phase O0 to the
///         FROZEN four-entry vocabulary while leaving future activation
///         pathways available.
///
///         Architectural significance: this contract is the architectural
///         climax of Stream 2-prep because it brings together agent
///         identity (AgentRegistry, Session 1), operational scope
///         (AgentScope, Session 2), and the on-chain attestation surface
///         where the two FROZEN-v1 primitives committed during the design
///         phase land at the contract layer.
///
/// ─────────────────────────────────────────────────────────────────────
/// Decision U-Enum (Session 5 resolution)
/// ─────────────────────────────────────────────────────────────────────
///
/// actionType is implemented as a Solidity enum rather than a string per
/// Pass 2C Section 3.5/4.3's literal specification. Three reasons confirmed
/// U-Enum:
///   - Stronger structural enforcement of Pass 2C's "vocabulary FROZEN at
///     four entries" commitment (adding entries requires contract redeploy)
///   - Gas-efficient at scale (uint8 vs string storage and comparison)
///   - Type-safe validation (Solidity bounds-checks the enum cast
///     automatically, panic 0x21 on invalid value)
///
/// The off-chain readability concern is mitigated by the canonical string
/// equivalents documented in this NatSpec for off-chain tooling. The
/// divergence from Pass 2C's string spec is documented in this commit's
/// message. Pass 2C's intent (FROZEN four-entry vocabulary) is preserved
/// MORE strongly under U-Enum than under the literal string interpretation.
///
/// Canonical actionType vocabulary (FROZEN per Pass 2C Section 4.3):
///   AGENT_COMMIT (0)               — "AGENT_COMMIT"
///                                    Anchors a git commit attestation
///                                    (AGENT_COMMIT v1, Pass 2A V10).
///                                    ACTIVE in Phase O0.
///   PHYSICAL_DATA_ATTESTATION (1)  — "PHYSICAL_DATA_ATTESTATION"
///                                    Anchors a physical-data binding
///                                    (PHYSICAL_DATA_ATTESTATION v1,
///                                    Pass 2B Path 3).
///                                    ACTIVE in Phase O0.
///   AUDIT_LOG_CHECKPOINT (2)       — "AUDIT_LOG_CHECKPOINT"
///                                    Anchors a Tessera signed-tree-head
///                                    via this contract instead of AuditLog.
///                                    RESERVED — passes validation under
///                                    Decision V-A but not exercised by
///                                    agents in Phase O0.
///   BOUNDARY_UPDATE (3)            — "BOUNDARY_UPDATE"
///                                    Anchors a scope/policy bundle update.
///                                    RESERVED — passes validation under
///                                    Decision V-A but not exercised by
///                                    agents in Phase O0.
///
/// ─────────────────────────────────────────────────────────────────────
/// Decision V-A (Session 5 resolution) — reserved as documentation
/// ─────────────────────────────────────────────────────────────────────
///
/// The two reserved actionType values pass validation in Phase O0 (any
/// uint8 in range 0..3 cast cleanly to ActionType per Solidity enum
/// semantics). "Reserved" status is documentation of operator policy, not
/// contract enforcement. Future phase agent capability updates activate
/// the reserved actionTypes by allowing agents to call with them; no
/// contract change is required because the validation already accepts
/// them.
///
/// Practical effect of V-A vs V-B in Phase O0: zero. The requireAgentScope
/// check below rejects all anchor calls in Phase O0 because no agents
/// have scope set (Pass 2C Section 3.2 Phase O0 default scopeRoot is
/// bytes32(0)). V-A keeps the contract immutable from Phase O0 forward;
/// V-B would have introduced a future governance event to activate
/// reserved types, which contradicts Pass 2C's "FROZEN at four entries"
/// commitment.
///
/// ─────────────────────────────────────────────────────────────────────
/// UNION storage design (Session 5 resolution)
/// ─────────────────────────────────────────────────────────────────────
///
/// Storage combines operator's anchorId-keyed primary structure with Pass
/// 2C's actionHash-keyed anti-replay tracker:
///   _anchors             — Anchor[] array, anchorId = array index
///                          (operator: per-anchor record + monotonic id)
///   _agentAnchors        — mapping(agentId => anchorIds[]) per-agent index
///                          (operator: efficient per-agent lookup)
///   _anchorIdByHash      — mapping(actionHash => anchorId+1)
///                          (Pass 2C: anti-replay; +1 sentinel because
///                           uint256(0) is a valid anchorId — store
///                           anchorId+1 so 0 means "unseen")
///
/// Anti-replay (Pass 2C's load-bearing security property): each actionHash
/// is globally unique across the contract's lifetime. Attempting to anchor
/// the same actionHash twice (regardless of agent or actionType) reverts
/// with DuplicateActionHash. Critical for AGENT_COMMIT v1 (no commit
/// anchored twice) and PHYSICAL_DATA_ATTESTATION v1 (no physical-data
/// hash anchored twice).
///
/// Per-agent indexing (operator's load-bearing operational property):
/// auditors can efficiently retrieve all anchors for a given agent
/// without scanning the global array. Useful for compliance audits
/// (Pass 2A audience: businesses and institutions).
///
/// ─────────────────────────────────────────────────────────────────────
/// Pass 2C Q9 — agentId encoding (FROZEN at first AgentRegistry registration)
/// ─────────────────────────────────────────────────────────────────────
///
/// agentId is bytes32 representing keccak256(abi.encode(ioID_DID_address,
/// ERC6551_TBA_address)) per Pass 2C Q9 (operator-confirmed 2026-04-27).
/// This contract stores whatever bytes32 is provided by the caller; the
/// canonical encoding is enforced by AgentRegistry.registerAgent at
/// agent registration time (Phase O0 Section 6.4). The encoding becomes
/// FROZEN at first agent registration in AgentRegistry — any later change
/// to the encoding would break agentId lookups across all five Phase O0
/// contracts.
///
/// ─────────────────────────────────────────────────────────────────────
/// Phase O0 status
/// ─────────────────────────────────────────────────────────────────────
///
/// This contract ships as Stream 2-prep Session 5 work — the final
/// Phase O0 contract. No anchors land at deployment. The
/// requireAgentScope modifier rejects all anchor calls in Phase O0
/// because no agents have scope set (Pass 2C Section 3.2 Phase O0
/// default). First anchor activation requires Phase O1+ agent capability
/// authoring; AGENT_COMMIT v1 and PHYSICAL_DATA_ATTESTATION v1 bridge
/// modules that produce the actionHashes ship as Stream 3-prep work.
///
/// @dev Pattern: Ownable + ReentrancyGuard. Owner-only for anchorAgentAction.
///      Public views for off-chain audit query.
/// @dev External calls in anchorAgentAction are read-only (isRegistered,
///      getScopeRoot view functions on owner-controlled contracts), so
///      nonReentrant is omitted per Sessions 1-2 pattern.

contract AgentAdjudicationRegistry is Ownable, ReentrancyGuard {

    /// @notice FROZEN four-entry actionType vocabulary per Pass 2C Section
    ///         4.3. Adding entries requires contract redeploy under U-Enum
    ///         (governance-grade weight matching Pass 2C's commitment).
    enum ActionType {
        AGENT_COMMIT,                  // 0 — active in Phase O0
        PHYSICAL_DATA_ATTESTATION,     // 1 — active in Phase O0
        AUDIT_LOG_CHECKPOINT,          // 2 — reserved (V-A: passes validation)
        BOUNDARY_UPDATE                // 3 — reserved (V-A: passes validation)
    }

    struct Anchor {
        bytes32 agentId;       // Per Pass 2C Q9 encoding (FROZEN)
        bytes32 actionHash;    // Cryptographic commitment to off-chain action
        uint256 timestamp;     // block.timestamp at anchor time
        uint256 blockNumber;   // block.number at anchor time
        ActionType actionType; // Discriminator for the FROZEN-v1 primitive class
    }

    /// @notice The AgentRegistry contract this AgentAdjudicationRegistry
    ///         cross-validates against. Set at deployment and immutable.
    IAgentRegistry public immutable agentRegistry;

    /// @notice The AgentScope contract this AgentAdjudicationRegistry reads
    ///         operational scope from. Set at deployment and immutable.
    IAgentScope public immutable agentScope;

    /// @dev Append-only array of anchor records. Indexed by anchorId
    ///      (the array index, also emitted in AgentActionAnchored events).
    Anchor[] private _anchors;

    /// @dev Per-agent index of anchorIds. Enables efficient retrieval of
    ///      all anchors for a given agentId without scanning the global
    ///      _anchors array.
    mapping(bytes32 => uint256[]) private _agentAnchors;

    /// @dev Anti-replay tracker: actionHash => (anchorId + 1). Zero means
    ///      "unseen". Storing anchorId+1 disambiguates anchorId=0 from
    ///      "not anchored".
    mapping(bytes32 => uint256) private _anchorIdByHash;

    event AgentActionAnchored(
        uint256 indexed anchorId,
        bytes32 indexed agentId,
        ActionType actionType,
        bytes32 actionHash,
        uint256 timestamp,
        uint256 blockNumber
    );

    error InvalidAgentRegistry();
    error InvalidAgentScopeContract();
    error AgentNotRegistered(bytes32 agentId);
    error InvalidAgentScope(bytes32 agentId);
    error InvalidActionHash();
    error DuplicateActionHash(bytes32 actionHash);
    error ActionHashNotFound(bytes32 actionHash);
    error AnchorNotFound(uint256 anchorId);

    /// @notice Modifier enforcing the agent has registered identity.
    /// @dev Pass 2C Section 3.5 names this concept; implementation is a
    ///      modifier so the ordering (registration → scope → body) is
    ///      explicit and declarative.
    modifier requireAgentRegistered(bytes32 agentId) {
        if (!agentRegistry.isRegistered(agentId)) {
            revert AgentNotRegistered(agentId);
        }
        _;
    }

    /// @notice Modifier enforcing the agent has non-zero operational scope.
    /// @dev Pass 2C Section 3.5 + Decision C from Session 2: reads
    ///      AgentScope.scopeRoot (operational truth), not
    ///      AgentRegistry.scopeHash (governance commitment). At Phase O0
    ///      exit, no agents have operational scope set, so this modifier
    ///      rejects all anchor calls until Phase O1+ scope-bundle authoring.
    modifier requireAgentScope(bytes32 agentId) {
        if (agentScope.getScopeRoot(agentId) == bytes32(0)) {
            revert InvalidAgentScope(agentId);
        }
        _;
    }

    constructor(
        address initialOwner,
        address _agentRegistry,
        address _agentScope
    ) Ownable(initialOwner) {
        if (_agentRegistry == address(0)) {
            revert InvalidAgentRegistry();
        }
        if (_agentScope == address(0)) {
            revert InvalidAgentScopeContract();
        }
        agentRegistry = IAgentRegistry(_agentRegistry);
        agentScope = IAgentScope(_agentScope);
    }

    /// @notice Anchor a per-agent action attestation. Owner-only.
    /// @dev Modifier ordering enforces Pass 2C-specified check sequence:
    ///      onlyOwner → requireAgentRegistered → requireAgentScope → body
    ///      (actionHash + anti-replay + append + emit).
    /// @param agentId      bytes32 agent identifier (must be registered in
    ///                     AgentRegistry; must have non-zero scopeRoot in
    ///                     AgentScope)
    /// @param actionType   FROZEN four-entry vocabulary discriminator
    ///                     (AGENT_COMMIT, PHYSICAL_DATA_ATTESTATION,
    ///                     AUDIT_LOG_CHECKPOINT, BOUNDARY_UPDATE).
    ///                     Solidity enum bounds check rejects uint8 >= 4
    ///                     with Panic(0x21).
    /// @param actionHash   Cryptographic commitment to the off-chain action.
    ///                     Must be non-zero. Globally unique (anti-replay).
    /// @return anchorId    The new anchor's id (array index).
    function anchorAgentAction(
        bytes32 agentId,
        ActionType actionType,
        bytes32 actionHash
    )
        external
        onlyOwner
        requireAgentRegistered(agentId)
        requireAgentScope(agentId)
        returns (uint256 anchorId)
    {
        if (actionHash == bytes32(0)) {
            revert InvalidActionHash();
        }
        if (_anchorIdByHash[actionHash] != 0) {
            revert DuplicateActionHash(actionHash);
        }

        anchorId = _anchors.length;
        _anchors.push(Anchor({
            agentId: agentId,
            actionHash: actionHash,
            timestamp: block.timestamp,
            blockNumber: block.number,
            actionType: actionType
        }));
        _agentAnchors[agentId].push(anchorId);
        _anchorIdByHash[actionHash] = anchorId + 1;  // sentinel: 0 = unseen

        emit AgentActionAnchored(
            anchorId,
            agentId,
            actionType,
            actionHash,
            block.timestamp,
            block.number
        );
    }

    /// @notice Read an anchor record by anchorId (array index).
    /// @dev Reverts AnchorNotFound on out-of-bounds.
    function getAnchor(uint256 anchorId)
        external
        view
        returns (
            bytes32 agentId,
            ActionType actionType,
            bytes32 actionHash,
            uint256 timestamp,
            uint256 blockNumber
        )
    {
        if (anchorId >= _anchors.length) {
            revert AnchorNotFound(anchorId);
        }
        Anchor memory a = _anchors[anchorId];
        return (a.agentId, a.actionType, a.actionHash, a.timestamp, a.blockNumber);
    }

    /// @notice Total number of anchors. Convenience for off-chain pagination.
    function getAnchorCount() external view returns (uint256) {
        return _anchors.length;
    }

    /// @notice Read all anchorIds for a given agent.
    /// @dev Returns empty array if the agent has no anchors. For very-large
    ///      agent histories, off-chain callers may need to paginate via
    ///      getAnchor index-by-index instead of fetching the full array.
    function getAgentAnchors(bytes32 agentId) external view returns (uint256[] memory) {
        return _agentAnchors[agentId];
    }

    /// @notice Predicate: has this actionHash been anchored?
    /// @dev Pass 2C anti-replay query. Used by off-chain bridge to
    ///      pre-check before submitting a re-anchor attempt.
    function isRecorded(bytes32 actionHash) external view returns (bool) {
        return _anchorIdByHash[actionHash] != 0;
    }

    /// @notice Look up anchorId for a given actionHash.
    /// @dev Reverts ActionHashNotFound if the hash has not been anchored.
    function getAnchorByHash(bytes32 actionHash) external view returns (uint256) {
        uint256 stored = _anchorIdByHash[actionHash];
        if (stored == 0) {
            revert ActionHashNotFound(actionHash);
        }
        return stored - 1;  // un-shift the +1 sentinel
    }
}
