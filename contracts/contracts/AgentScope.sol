// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/access/Ownable.sol";
import "@openzeppelin/contracts/utils/ReentrancyGuard.sol";

/// @dev Local interface declaration for AgentRegistry's registration predicate.
///      Pass 2C Section 3.2 dependency: AgentScope cross-validates against
///      AgentRegistry before storing scope for any agentId. Local declaration
///      preferred over a shared contracts/contracts/interfaces/IAgentRegistry.sol
///      because this is the first interface use in Phase O0 and a single-method
///      interface is small enough that decentralized declaration is cleaner
///      than introducing a new directory.
interface IAgentRegistry {
    function isRegistered(bytes32 agentId) external view returns (bool);
}

/// @title AgentScope — Operator series Phase O0 operational-scope storage
/// @notice Stores the Merkle root of the policy bundle (Cedar/Rego) the bridge
///         verifies against at request time. Sibling contract to AgentRegistry
///         (Phase O0 Stream 2 Session 1, commit b063718e); follows the same
///         Ownable + ReentrancyGuard pattern.
///
/// ─────────────────────────────────────────────────────────────────────
/// Two-layer scope enforcement (architectural reasoning, do not collapse)
/// ─────────────────────────────────────────────────────────────────────
///
/// VAPI's Phase O0 design separates an agent's scope into two storage layers
/// across two contracts. Both layers store a per-agent bytes32 Merkle root, and
/// they are deliberately allowed to differ. The two-layer pattern is not
/// duplication; it is intentional architectural separation.
///
///   AgentRegistry.scopeHash — governance commitment.
///     The scope the agent was approved with at registration. Updated only
///     through deliberate governance events. Represents WHAT THE AGENT IS
///     AUTHORIZED TO DO. Slow-moving, audit-traceable, change-controlled.
///
///   AgentScope.scopeRoot — operational state.
///     The scope the bridge currently enforces. Updated as operational policy
///     evolves within the governance-approved envelope. Represents WHAT SCOPE
///     IS ACTIVE AT THE MOMENT of any agent action. Faster-moving, may be
///     adjusted between governance reviews.
///
/// AgentScope.setAgentScopeRoot does NOT validate consistency with
/// AgentRegistry.scopeHash. The two are deliberately allowed to differ because
/// operational adjustment within the governance-approved envelope is the
/// architectural purpose of this second contract. Auditors compare the two
/// values to verify agents operated within governance-approved scope; the
/// contracts themselves do not enforce consistency.
///
/// AgentAdjudicationRegistry's requireAgentScope modifier (Phase O0 Stream 2
/// Session 5) reads from AgentScope.scopeRoot — operational truth at moment
/// of action — not from AgentRegistry.scopeHash.
///
/// ─────────────────────────────────────────────────────────────────────
/// Single-function design (Pass 2C Section 3.2)
/// ─────────────────────────────────────────────────────────────────────
///
/// One mutating function `setAgentScopeRoot` handles both initial set and
/// subsequent updates. The AgentScopeRootSet event carries oldRoot + newRoot
/// fields, with oldRoot=bytes32(0) on the first call (matching Pass 2C's
/// "default Phase O0 scopeRoot is bytes32(0)" specification). No separate
/// updateAgentScopeRoot function and no AgentScopeAlreadySet error — those
/// were drifts from Pass 2C in the operator's Session 2 prompt and the
/// implementation follows the design phase's locked specification.
///
/// ─────────────────────────────────────────────────────────────────────
/// Phase O0 status
/// ─────────────────────────────────────────────────────────────────────
///
/// This contract ships as Stream 2-prep Session 2 work. No agents have scope
/// set at deployment; first scope set occurs in Phase O0 Section 6.4 work or
/// later phases when policy bundles are authored. The default state for any
/// agentId is scopeRoot = bytes32(0) — empty bundle, no operational scope yet,
/// consistent with Phase O0 not granting agents operational authority.
///
/// @dev Only the owner (bridge wallet) may set scope roots. The view function
///      getScopeRoot is public for off-chain query.
/// @dev Pre-condition for setAgentScopeRoot: the agentId must be registered in
///      AgentRegistry. This cross-contract check ensures scope can only be
///      assigned to agents that exist in the registry.

contract AgentScope is Ownable, ReentrancyGuard {

    /// @notice The AgentRegistry contract this AgentScope cross-validates
    ///         against. Set at deployment and immutable for the lifetime of
    ///         this AgentScope.
    IAgentRegistry public immutable agentRegistry;

    /// @dev agentId => scopeRoot. Default value bytes32(0) for any unset
    ///      agent (Pass 2C Section 3.2 default).
    mapping(bytes32 => bytes32) private _scopeRoots;

    event AgentScopeRootSet(
        bytes32 indexed agentId,
        bytes32 oldRoot,
        bytes32 newRoot,
        uint256 timestamp
    );

    /// @notice Custom error emitted when setAgentScopeRoot is called for an
    ///         agentId that has not been registered in AgentRegistry.
    error AgentNotRegistered(bytes32 agentId);

    /// @notice Custom error emitted when setAgentScopeRoot is called with
    ///         agentId == bytes32(0).
    error InvalidAgentId();

    /// @notice Custom error emitted when the AgentRegistry address provided
    ///         to the constructor is the zero address.
    error InvalidAgentRegistry();

    constructor(address initialOwner, address _agentRegistry) Ownable(initialOwner) {
        if (_agentRegistry == address(0)) {
            revert InvalidAgentRegistry();
        }
        agentRegistry = IAgentRegistry(_agentRegistry);
    }

    /// @notice Set or update an agent's operational scope Merkle root.
    /// @dev Single-function design per Pass 2C Section 3.2. Multiple calls
    ///      allowed: the AgentScopeRootSet event carries oldRoot + newRoot,
    ///      with oldRoot=bytes32(0) on the first call.
    /// @param agentId   bytes32 agent identifier (must be registered in
    ///                  AgentRegistry; cross-validation reverts if not)
    /// @param scopeRoot Merkle root of the agent's policy bundle. Setting to
    ///                  bytes32(0) is allowed (default state can be set
    ///                  explicitly e.g. to revoke operational scope).
    function setAgentScopeRoot(bytes32 agentId, bytes32 scopeRoot) external onlyOwner {
        if (agentId == bytes32(0)) {
            revert InvalidAgentId();
        }
        if (!agentRegistry.isRegistered(agentId)) {
            revert AgentNotRegistered(agentId);
        }

        bytes32 oldRoot = _scopeRoots[agentId];
        _scopeRoots[agentId] = scopeRoot;

        emit AgentScopeRootSet(agentId, oldRoot, scopeRoot, block.timestamp);
    }

    /// @notice Read an agent's current operational scope Merkle root.
    /// @param agentId  bytes32 agent identifier
    /// @return scopeRoot  The Merkle root currently stored for this agent
    ///                    (bytes32(0) if never set).
    function getScopeRoot(bytes32 agentId) external view returns (bytes32) {
        return _scopeRoots[agentId];
    }
}
