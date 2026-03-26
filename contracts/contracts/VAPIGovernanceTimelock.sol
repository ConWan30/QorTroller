// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * @title VAPIGovernanceTimelock — Phase 70 Operator Transition Safety
 * @notice Interposes a mandatory 48-hour queue before any operator address change
 *         takes effect on any of the 6 Phase 69 VAPI contracts.
 *
 * Security model:
 *   - Only the current operator can queue or execute transitions.
 *   - A designated co-signer (cancel-only) can block a queued transition
 *     without being able to queue or execute one.
 *   - This prevents a compromised operator key from instantly transferring
 *     all oracle control — the co-signer has 48 hours to cancel.
 *   - PHGCredential is explicitly excluded: its bridge address is immutable
 *     by contract design and cannot be covered by this timelock.
 *
 * Supported target contracts (Phase 69):
 *   DataSovereigntyRegistry, HumanityOracle, RulingOracle, PassportOracle,
 *   VAPIRewardDistributor, VAPIDataMarketplace.
 *
 * Target contracts must expose: function setOperator(address) external
 */
contract VAPIGovernanceTimelock {

    // -----------------------------------------------------------------------
    // Constants
    // -----------------------------------------------------------------------

    uint256 public constant TIMELOCK_DELAY = 48 hours;

    // -----------------------------------------------------------------------
    // Types
    // -----------------------------------------------------------------------

    struct QueuedTransition {
        address target;       // Phase 69 contract address
        address newOperator;  // proposed new operator
        uint256 eta;          // block.timestamp + TIMELOCK_DELAY — earliest execution time
        bool    executed;
        bool    cancelled;
    }

    // -----------------------------------------------------------------------
    // State
    // -----------------------------------------------------------------------

    address public operator;
    address public coSigner;   // cancel-only — cannot queue or execute

    /// Auto-incrementing queue counter
    uint256 public nextQueueId;

    /// queueId => QueuedTransition
    mapping(uint256 => QueuedTransition) public transitions;

    // -----------------------------------------------------------------------
    // Events
    // -----------------------------------------------------------------------

    event TransitionQueued(
        uint256 indexed queueId,
        address indexed target,
        address indexed newOperator,
        uint256 eta
    );

    event TransitionExecuted(
        uint256 indexed queueId,
        address indexed target,
        address indexed newOperator
    );

    event TransitionCancelled(
        uint256 indexed queueId,
        address indexed cancelledBy
    );

    event CoSignerSet(address indexed oldCoSigner, address indexed newCoSigner);
    event OperatorTransferred(address indexed oldOperator, address indexed newOperator);

    // -----------------------------------------------------------------------
    // Modifiers
    // -----------------------------------------------------------------------

    modifier onlyOperator() {
        require(msg.sender == operator, "VAPIGovernanceTimelock: unauthorized");
        _;
    }

    modifier onlyOperatorOrCoSigner() {
        require(
            msg.sender == operator || msg.sender == coSigner,
            "VAPIGovernanceTimelock: not operator or co-signer"
        );
        _;
    }

    // -----------------------------------------------------------------------
    // Constructor
    // -----------------------------------------------------------------------

    constructor(address _operator, address _coSigner) {
        require(_operator != address(0), "VAPIGovernanceTimelock: zero operator");
        operator = _operator;
        coSigner = _coSigner;
        emit CoSignerSet(address(0), _coSigner);
    }

    // -----------------------------------------------------------------------
    // Queue
    // -----------------------------------------------------------------------

    /**
     * @notice Queue an operator transition for a target contract.
     *         The transition becomes executable after TIMELOCK_DELAY (48h).
     * @param target      The Phase 69 contract to update.
     * @param newOperator The proposed new operator address.
     * @return queueId    The ID of this queued transition.
     */
    function queueTransition(address target, address newOperator)
        external
        onlyOperator
        returns (uint256 queueId)
    {
        require(target != address(0), "VAPIGovernanceTimelock: zero target");
        require(newOperator != address(0), "VAPIGovernanceTimelock: zero newOperator");

        queueId = nextQueueId++;
        uint256 eta = block.timestamp + TIMELOCK_DELAY;

        transitions[queueId] = QueuedTransition({
            target:      target,
            newOperator: newOperator,
            eta:         eta,
            executed:    false,
            cancelled:   false
        });

        emit TransitionQueued(queueId, target, newOperator, eta);
    }

    // -----------------------------------------------------------------------
    // Execute
    // -----------------------------------------------------------------------

    /**
     * @notice Execute a queued transition after its eta has elapsed.
     *         Calls setOperator(newOperator) on the target contract.
     *         Security: sets executed=true BEFORE the external call (CEI pattern).
     * @param queueId The transition to execute.
     */
    function executeTransition(uint256 queueId) external onlyOperator {
        QueuedTransition storage t = transitions[queueId];
        require(t.target != address(0), "VAPIGovernanceTimelock: unknown queueId");
        require(!t.executed, "VAPIGovernanceTimelock: already executed");
        require(!t.cancelled, "VAPIGovernanceTimelock: cancelled");
        require(block.timestamp >= t.eta, "VAPIGovernanceTimelock: timelock not elapsed");

        // CEI: set state before external call
        t.executed = true;

        // Call setOperator on the target
        (bool ok, ) = t.target.call(
            abi.encodeWithSignature("setOperator(address)", t.newOperator)
        );
        require(ok, "VAPIGovernanceTimelock: setOperator call failed");

        emit TransitionExecuted(queueId, t.target, t.newOperator);
    }

    // -----------------------------------------------------------------------
    // Cancel
    // -----------------------------------------------------------------------

    /**
     * @notice Cancel a queued transition before it is executed.
     *         Both the operator and the co-signer may cancel.
     * @param queueId The transition to cancel.
     */
    function cancelTransition(uint256 queueId) external onlyOperatorOrCoSigner {
        QueuedTransition storage t = transitions[queueId];
        require(t.target != address(0), "VAPIGovernanceTimelock: unknown queueId");
        require(!t.executed, "VAPIGovernanceTimelock: already executed");
        require(!t.cancelled, "VAPIGovernanceTimelock: already cancelled");

        t.cancelled = true;
        emit TransitionCancelled(queueId, msg.sender);
    }

    // -----------------------------------------------------------------------
    // Admin
    // -----------------------------------------------------------------------

    /**
     * @notice Replace the co-signer address.
     *         NOTE: This change is NOT subject to the timelock — it takes
     *         effect immediately so the operator can quickly update the
     *         co-signer key if it is lost or compromised.
     */
    function setCoSigner(address _coSigner) external onlyOperator {
        require(_coSigner != address(0), "VAPIGovernanceTimelock: zero co-signer"); // L-1 fix
        emit CoSignerSet(coSigner, _coSigner);
        coSigner = _coSigner;
    }

    /**
     * @notice Transfer the timelock's own operator address immediately.
     *         Use only to bootstrap governance; in production prefer queueing
     *         this via a separate safe mechanism.
     */
    function transferOperator(address _newOperator) external onlyOperator {
        require(_newOperator != address(0), "VAPIGovernanceTimelock: zero operator");
        emit OperatorTransferred(operator, _newOperator);
        operator = _newOperator;
    }

    // -----------------------------------------------------------------------
    // View helpers
    // -----------------------------------------------------------------------

    /**
     * @notice Get the full state of a queued transition.
     */
    function getTransition(uint256 queueId)
        external
        view
        returns (QueuedTransition memory)
    {
        return transitions[queueId];
    }

    /**
     * @notice Check whether a transition is ready to execute
     *         (eta elapsed, not yet executed, not cancelled).
     */
    function isReady(uint256 queueId) external view returns (bool) {
        QueuedTransition storage t = transitions[queueId];
        return (
            t.target != address(0) &&
            !t.executed &&
            !t.cancelled &&
            block.timestamp >= t.eta
        );
    }
}
