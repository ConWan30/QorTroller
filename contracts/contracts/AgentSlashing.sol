// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/access/Ownable.sol";
import "@openzeppelin/contracts/utils/ReentrancyGuard.sol";

/// @dev Local interface declaration for AgentRegistry's registration predicate.
///      Pass 2C Section 3.3 dependency: AgentSlashing cross-validates against
///      AgentRegistry before accepting bonds or slash proposals against an
///      agent. Local declaration matches AgentScope's pattern from Session 2
///      per Decision X resolution (no shared interfaces directory introduced
///      to avoid disrupting AgentScope which already shipped with a local
///      declaration). The single-method interface declaration is duplicated
///      across AgentScope, AgentSlashing, and AgentAdjudicationRegistry
///      (Session 5) — accepted cost for not refactoring AgentScope.
interface IAgentRegistry {
    function isRegistered(bytes32 agentId) external view returns (bool);
}

/// @title AgentSlashing — Operator series Phase O0 economic accountability
/// @notice VetoSlasher-pattern slashing for agent misbehavior, adapted from
///         Symbiotic's reference design per Pass 2C Section 3.3. The
///         architecture is bond → propose → 24h veto window → execute (burn).
///
/// ─────────────────────────────────────────────────────────────────────
/// Decision Z-A — pure burn (Session 4 resolution)
/// ─────────────────────────────────────────────────────────────────────
///
/// Slashed amounts transfer to address(0xdead) at execution time. No
/// recipient governance question; no redistribute pathway. The
/// SlashExecuted event still carries both burnedAmount and distributedAmount
/// fields per Pass 2C Section 3.3's specified signature, with
/// distributedAmount=0 in the Phase O0 pure-burn implementation. Preserving
/// the event ABI keeps future phase flexibility if a redistribute model
/// becomes warranted, without committing the Phase O0 contract to that
/// complexity.
///
/// Z-A reasoning recorded in the commit message:
///   - Matches Pass 2C Section 3.3 purpose statement ("Bond → slash →
///     24h veto window → burn").
///   - Avoids recipient governance question entirely (no treasury
///     address to manage, no redistribute-target governance event).
///   - Continues the architectural posture from Pass 2A V10 and Pass 2B
///     Path 3 of preferring simpler commitments over flexible ones that
///     introduce future governance surfaces.
///
/// ─────────────────────────────────────────────────────────────────────
/// Decision W-A — partial slashing (Session 4 resolution)
/// ─────────────────────────────────────────────────────────────────────
///
/// proposeSlash accepts a slashAmount parameter; the proposer specifies
/// how much of the bond to slash. Bond persists with reduced balance after
/// partial slash; multiple proposals against the same agent can target
/// different amounts. Matches Symbiotic's VetoSlasher reference pattern
/// that Pass 2C Section 3.3 cited as template. Stronger incentive
/// alignment through proportional consequences than all-or-nothing.
///
/// Double-spend guard: at executeSlash time, slashAmount must still be
/// <= current bond. Multiple in-flight proposals against the same agent
/// could each pass proposeSlash but later fail at execute time if earlier
/// proposals already drained the bond. The guard reverts InsufficientBond
/// at execute time, not just at propose time.
///
/// ─────────────────────────────────────────────────────────────────────
/// Veto window semantics
/// ─────────────────────────────────────────────────────────────────────
///
/// vetoWindowSeconds (default 86400 = 24 hours) is the temporal boundary
/// between veto-eligibility and execute-eligibility:
///
///   block.timestamp < proposedAt + vetoWindowSeconds  → veto allowed
///                                                       executeSlash reverts
///                                                       (VetoWindowNotElapsed)
///
///   block.timestamp >= proposedAt + vetoWindowSeconds → veto reverts
///                                                       (VetoWindowElapsed)
///                                                       executeSlash allowed
///
/// veto and executeSlash are temporally exclusive AND status-exclusive.
/// Either operation transitions a Proposed proposal to a terminal state
/// (Vetoed or Executed); the other operation reverts thereafter.
///
/// ─────────────────────────────────────────────────────────────────────
/// Phase O0 status
/// ─────────────────────────────────────────────────────────────────────
///
/// This contract ships as Stream 2-prep Session 4 work. No agents are
/// registered with bonds at deployment per Pass 2C Section 3.3 ("Bond
/// deposits are permissionless during P0 but no agent is yet active so
/// no actual bonds will be deposited at Phase O0 exit"). The contract
/// is deployment-ready; bond posting and slashing become operationally
/// meaningful in P1+ when agents are active.
///
/// @dev Pattern: Ownable + ReentrancyGuard. Owner-only for proposeSlash,
///      veto, executeSlash. Public payable for postBond. Public views
///      for getters.

contract AgentSlashing is Ownable, ReentrancyGuard {

    /// @notice Burn destination for slashed funds (Z-A pure burn).
    address public constant BURN_ADDRESS = 0x000000000000000000000000000000000000dEaD;

    /// @notice The AgentRegistry contract this AgentSlashing cross-validates
    ///         against. Set at deployment and immutable for the contract's
    ///         lifetime.
    IAgentRegistry public immutable agentRegistry;

    /// @notice Veto window duration in seconds. Default 86400 (24 hours)
    ///         per Pass 2C Section 3.3. Immutable for the contract's lifetime.
    uint256 public immutable vetoWindowSeconds;

    /// @dev Proposal lifecycle status.
    enum ProposalStatus {
        Proposed,   // 0 — awaiting veto window expiry or veto action
        Vetoed,     // 1 — terminal: veto by owner during the window
        Executed    // 2 — terminal: slashAmount burned after window expiry
    }

    struct Proposal {
        bytes32 agentId;
        uint256 slashAmount;
        bytes32 evidenceHash;
        uint256 proposedAt;
        ProposalStatus status;
        string reason;
    }

    /// @dev agentId => bond amount in wei. Posted via permissionless postBond,
    ///      drained per partial slash via executeSlash.
    mapping(bytes32 => uint256) private _bonds;

    /// @dev Append-only array of proposals. Indexed by proposalId (array index).
    Proposal[] private _proposals;

    event BondDeposited(bytes32 indexed agentId, uint256 amount);

    event SlashProposed(
        uint256 indexed proposalId,
        bytes32 indexed agentId,
        uint256 slashAmount,
        bytes32 evidenceHash,
        string reason
    );

    event SlashVetoed(uint256 indexed proposalId, address indexed cosigner);

    event SlashExecuted(
        uint256 indexed proposalId,
        uint256 burnedAmount,
        uint256 distributedAmount
    );

    error InvalidAgentRegistry();
    error InvalidBondAmount();
    error InvalidSlashAmount();
    error InvalidEvidenceHash();
    error AgentNotRegistered(bytes32 agentId);
    error InsufficientBond(uint256 slashAmount, uint256 bond);
    error ProposalNotFound(uint256 proposalId);
    error ProposalNotProposed(uint256 proposalId, ProposalStatus status);
    error VetoWindowElapsed(uint256 proposedAt, uint256 currentTime);
    error VetoWindowNotElapsed(uint256 proposedAt, uint256 currentTime);
    error BurnTransferFailed();

    constructor(
        address initialOwner,
        address _agentRegistry,
        uint256 _vetoWindowSeconds
    ) Ownable(initialOwner) {
        if (_agentRegistry == address(0)) {
            revert InvalidAgentRegistry();
        }
        agentRegistry = IAgentRegistry(_agentRegistry);
        vetoWindowSeconds = _vetoWindowSeconds;
    }

    /// @notice Deposit bond for a registered agent. Permissionless: anyone
    ///         can post bond for any registered agent (typically the agent
    ///         themselves, but operationally not enforced).
    /// @param agentId  Agent to bond. Must be registered in AgentRegistry.
    function postBond(bytes32 agentId) external payable nonReentrant {
        if (msg.value == 0) {
            revert InvalidBondAmount();
        }
        if (!agentRegistry.isRegistered(agentId)) {
            revert AgentNotRegistered(agentId);
        }

        unchecked {
            // Bond accumulation cannot overflow in practice; uint256 max is
            // ~10^77 and IOTX supply is bounded. unchecked saves gas.
            _bonds[agentId] += msg.value;
        }

        emit BondDeposited(agentId, msg.value);
    }

    /// @notice Propose a slash against a registered agent. Owner-only.
    /// @param agentId       Target agent (must be registered)
    /// @param reason        Human-readable rationale for the slash (stored
    ///                      on-chain; carried in event)
    /// @param slashAmount   Amount of bond to slash (must be > 0 and <= current
    ///                      bond at proposeSlash time; re-checked at executeSlash)
    /// @param evidenceHash  Cryptographic commitment to off-chain evidence
    ///                      (must be non-zero; provides audit trail anchor)
    /// @return proposalId   Index into _proposals; the proposalId for veto/execute
    function proposeSlash(
        bytes32 agentId,
        string calldata reason,
        uint256 slashAmount,
        bytes32 evidenceHash
    ) external onlyOwner returns (uint256 proposalId) {
        if (slashAmount == 0) {
            revert InvalidSlashAmount();
        }
        if (evidenceHash == bytes32(0)) {
            revert InvalidEvidenceHash();
        }
        if (!agentRegistry.isRegistered(agentId)) {
            revert AgentNotRegistered(agentId);
        }
        uint256 bond = _bonds[agentId];
        if (slashAmount > bond) {
            revert InsufficientBond(slashAmount, bond);
        }

        proposalId = _proposals.length;
        _proposals.push(Proposal({
            agentId: agentId,
            slashAmount: slashAmount,
            evidenceHash: evidenceHash,
            proposedAt: block.timestamp,
            status: ProposalStatus.Proposed,
            reason: reason
        }));

        emit SlashProposed(proposalId, agentId, slashAmount, evidenceHash, reason);
    }

    /// @notice Veto a slash proposal during its veto window. Owner-only.
    /// @param proposalId  The proposal to veto
    function veto(uint256 proposalId) external onlyOwner {
        if (proposalId >= _proposals.length) {
            revert ProposalNotFound(proposalId);
        }
        Proposal storage p = _proposals[proposalId];
        if (p.status != ProposalStatus.Proposed) {
            revert ProposalNotProposed(proposalId, p.status);
        }
        if (block.timestamp >= p.proposedAt + vetoWindowSeconds) {
            revert VetoWindowElapsed(p.proposedAt, block.timestamp);
        }

        p.status = ProposalStatus.Vetoed;
        emit SlashVetoed(proposalId, msg.sender);
    }

    /// @notice Execute a slash proposal after its veto window has elapsed.
    ///         Burns slashAmount by transferring to address(0xdead). Owner-only.
    /// @param proposalId  The proposal to execute
    function executeSlash(uint256 proposalId) external onlyOwner nonReentrant {
        if (proposalId >= _proposals.length) {
            revert ProposalNotFound(proposalId);
        }
        Proposal storage p = _proposals[proposalId];
        if (p.status != ProposalStatus.Proposed) {
            revert ProposalNotProposed(proposalId, p.status);
        }
        if (block.timestamp < p.proposedAt + vetoWindowSeconds) {
            revert VetoWindowNotElapsed(p.proposedAt, block.timestamp);
        }

        // Double-spend guard: re-check bond at execute time. Multiple
        // proposals against the same agent could each pass propose-time
        // bond check but conflict at execute time if earlier executions
        // already drained the bond.
        uint256 bond = _bonds[p.agentId];
        uint256 slashAmount = p.slashAmount;
        if (slashAmount > bond) {
            revert InsufficientBond(slashAmount, bond);
        }

        // CEI: status update before external call, then bond debit, then
        // burn transfer. nonReentrant adds defense-in-depth.
        p.status = ProposalStatus.Executed;
        unchecked {
            // Safe by the guard above.
            _bonds[p.agentId] = bond - slashAmount;
        }

        (bool ok, ) = BURN_ADDRESS.call{value: slashAmount}("");
        if (!ok) {
            revert BurnTransferFailed();
        }

        emit SlashExecuted(proposalId, slashAmount, 0);
    }

    /// @notice Read an agent's current bond amount.
    function getBond(bytes32 agentId) external view returns (uint256) {
        return _bonds[agentId];
    }

    /// @notice Read a proposal's full record.
    /// @dev Reverts ProposalNotFound on out-of-bounds proposalId.
    function getProposal(uint256 proposalId)
        external
        view
        returns (
            bytes32 agentId,
            uint256 slashAmount,
            bytes32 evidenceHash,
            uint256 proposedAt,
            ProposalStatus status,
            string memory reason
        )
    {
        if (proposalId >= _proposals.length) {
            revert ProposalNotFound(proposalId);
        }
        Proposal memory p = _proposals[proposalId];
        return (p.agentId, p.slashAmount, p.evidenceHash, p.proposedAt, p.status, p.reason);
    }

    /// @notice Total number of proposals (any status). Convenience for off-chain
    ///         pagination.
    function totalProposals() external view returns (uint256) {
        return _proposals.length;
    }

    /// @notice Predicate: is this proposal in Proposed status (not yet Vetoed
    ///         or Executed)?
    function isProposed(uint256 proposalId) external view returns (bool) {
        if (proposalId >= _proposals.length) {
            return false;
        }
        return _proposals[proposalId].status == ProposalStatus.Proposed;
    }
}
