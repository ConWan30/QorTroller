// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/access/Ownable.sol";
import "@openzeppelin/contracts/utils/ReentrancyGuard.sol";

/// @title AgentRegistry — Operator series Phase O0 agent identity registry
/// @notice Registers each Operator Agent with (agentId → publicKey, scopeHash, status).
///         Sibling contract to VAPIBiometricGovernance (Phase 222 LIVE at
///         0x06782293F1CFC1AA30C0Baee0437c2B336796A00); follows the same
///         Ownable + ReentrancyGuard + indexed-events pattern.
///
///         agentId is bytes32 representing the hash of the agent's ioID DID +
///         ERC-6551 TBA address binding per Pass 2C Q9 resolution:
///         keccak256(abi.encode(ioID_DID_address, ERC6551_TBA_address)).
///         Specific encoding is computed off-chain in Phase O0 Section 6.4;
///         this contract stores whatever bytes32 is provided.
///
///         Status enum values (per Pass 2C Section 3.1) are represented as
///         uint8 with named constants because the value space is non-contiguous
///         (0-6 plus 255). Solidity native enums auto-assign sequential values
///         and cannot express the SUSPENDED=255 sentinel without RESERVED gaps.
///
///         Phase O0 status: this contract ships as Stream 2-prep work. No
///         agents are registered at deployment; first registration occurs in
///         Phase O0 Section 6.4 after GitHub Apps registration completes for
///         vapi-anchor-sentry and vapi-guardian.
///
/// @dev    Only the owner (bridge wallet) may register agents or update status
///         and scope. View functions are public for off-chain query.
/// @dev    Anti-replay: registerAgent reverts if agentId is already registered.
///         updateAgentStatus and updateAgentScope require pre-existing
///         registration.

contract AgentRegistry is Ownable, ReentrancyGuard {

    struct Agent {
        address publicKey;     // Agent's ECDSA secp256k1 public key (TBA address)
        bytes32 scopeHash;     // Merkle root of the agent's policy bundle (Cedar)
        uint8 status;          // Lifecycle status (see STATUS_* constants)
    }

    /// @dev Phase O0 exit state — agent registered but inactive.
    uint8 public constant STATUS_DEFINED = 0;
    /// @dev P1 — Shadow / Read-Only mode.
    uint8 public constant STATUS_SHADOW = 1;
    /// @dev P2 — Suggestion mode (drafts PRs, requires human approval).
    uint8 public constant STATUS_SUGGESTING = 2;
    /// @dev P3 — Write authority for tournament gate.
    uint8 public constant STATUS_WRITE_TOURNAMENT = 3;
    /// @dev P4 — Invariant change authorization.
    uint8 public constant STATUS_INVARIANT_AUTH = 4;
    /// @dev P5 — Provenance write authority.
    uint8 public constant STATUS_PROVENANCE_WRITE = 5;
    /// @dev P6 — Full Operator authority.
    uint8 public constant STATUS_FULL_OPERATOR = 6;
    /// @dev Sentinel — agent suspended pending governance review or slashing.
    uint8 public constant STATUS_SUSPENDED = 255;

    /// @dev agentId => Agent record. publicKey == address(0) sentinel means
    ///      "not registered" since address(0) is never a valid agent key.
    mapping(bytes32 => Agent) private _agents;

    /// @dev Monotonically increasing counter of registered agents.
    uint256 public totalAgents;

    event AgentRegistered(
        bytes32 indexed agentId,
        address indexed publicKey,
        bytes32 scopeHash,
        uint8 status
    );

    event AgentStatusUpdated(
        bytes32 indexed agentId,
        uint8 oldStatus,
        uint8 newStatus
    );

    event AgentScopeUpdated(
        bytes32 indexed agentId,
        bytes32 oldScope,
        bytes32 newScope
    );

    constructor(address initialOwner) Ownable(initialOwner) {
        // Ownable's constructor reverts on zero-address; no further check needed.
    }

    /// @notice Register a new Operator Agent. Owner-only; anti-replay guarded.
    /// @param agentId    bytes32 agent identifier (keccak256 of DID + TBA off-chain)
    /// @param publicKey  Agent's ECDSA secp256k1 public key address
    /// @param scopeHash  Merkle root of agent's policy bundle (zero hash at P0 entry)
    /// @param status     Lifecycle status (must be a recognized STATUS_* value)
    function registerAgent(
        bytes32 agentId,
        address publicKey,
        bytes32 scopeHash,
        uint8 status
    ) external onlyOwner {
        require(agentId != bytes32(0), "AgentRegistry: zero agentId");
        require(publicKey != address(0), "AgentRegistry: zero publicKey");
        require(_isValidStatus(status), "AgentRegistry: invalid status");
        require(
            _agents[agentId].publicKey == address(0),
            "AgentRegistry: agent already registered"
        );

        _agents[agentId] = Agent({
            publicKey: publicKey,
            scopeHash: scopeHash,
            status: status
        });
        unchecked {
            totalAgents += 1;
        }

        emit AgentRegistered(agentId, publicKey, scopeHash, status);
    }

    /// @notice Update an existing agent's lifecycle status. Owner-only.
    /// @param agentId    bytes32 agent identifier (must be pre-registered)
    /// @param newStatus  New lifecycle status (must be a recognized STATUS_* value)
    function updateAgentStatus(bytes32 agentId, uint8 newStatus) external onlyOwner {
        require(
            _agents[agentId].publicKey != address(0),
            "AgentRegistry: agent not registered"
        );
        require(_isValidStatus(newStatus), "AgentRegistry: invalid status");

        uint8 oldStatus = _agents[agentId].status;
        _agents[agentId].status = newStatus;

        emit AgentStatusUpdated(agentId, oldStatus, newStatus);
    }

    /// @notice Update an existing agent's scope hash. Owner-only.
    /// @param agentId   bytes32 agent identifier (must be pre-registered)
    /// @param newScope  New scope Merkle root
    function updateAgentScope(bytes32 agentId, bytes32 newScope) external onlyOwner {
        require(
            _agents[agentId].publicKey != address(0),
            "AgentRegistry: agent not registered"
        );

        bytes32 oldScope = _agents[agentId].scopeHash;
        _agents[agentId].scopeHash = newScope;

        emit AgentScopeUpdated(agentId, oldScope, newScope);
    }

    /// @notice Read an agent's full record.
    /// @param agentId  bytes32 agent identifier
    /// @return publicKey  Agent's public key (address(0) if not registered)
    /// @return scopeHash  Agent's scope Merkle root
    /// @return status     Agent's lifecycle status
    function getAgent(bytes32 agentId)
        external
        view
        returns (address publicKey, bytes32 scopeHash, uint8 status)
    {
        Agent memory a = _agents[agentId];
        return (a.publicKey, a.scopeHash, a.status);
    }

    /// @notice Convenience predicate: is this agentId registered?
    function isRegistered(bytes32 agentId) external view returns (bool) {
        return _agents[agentId].publicKey != address(0);
    }

    /// @dev Validate a status value against the recognized STATUS_* set.
    ///      Recognized values: 0..6 (lifecycle progression) and 255 (suspended).
    function _isValidStatus(uint8 s) internal pure returns (bool) {
        return s <= 6 || s == 255;
    }
}
