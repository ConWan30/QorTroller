// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/access/Ownable.sol";
import "@openzeppelin/contracts/utils/ReentrancyGuard.sol";

/// @title AuditLog — Operator series Phase O0 system-level Tessera anchor
/// @notice Append-only Merkle root anchor for nightly Tessera signed-tree-head
///         (SSH) checkpoints. Phase O0 ships the contract; the Tessera upstream
///         feed is deferred to P1+. Until activation, the contract holds zero
///         checkpoints — the "ships empty, activates later" pattern that
///         matches Stream 1's path-scope gate (declaratively in place but
///         producing zero enforcement actions until agent identities exist).
///
/// ─────────────────────────────────────────────────────────────────────
/// Architectural distinction (system-level vs per-agent)
/// ─────────────────────────────────────────────────────────────────────
///
/// AuditLog is a SYSTEM-LEVEL audit anchor for the entire protocol's signed
/// audit tree. One global checkpoint sequence shared across all agents and
/// all activity, indexed by checkpointId (uint256). It does NOT track
/// per-agent records.
///
/// Per-agent action attestation lives in AgentAdjudicationRegistry (Phase O0
/// Stream 2 Session 5), which anchors AGENT_COMMIT v1 and
/// PHYSICAL_DATA_ATTESTATION v1 records keyed by agentId. The two contracts
/// have distinct architectural purposes:
///
///   AuditLog                         → protocol-wide audit checkpoint
///   AgentAdjudicationRegistry        → per-agent action attestation
///
/// AuditLog has NO dependency on AgentRegistry. The contract accepts only a
/// bridge wallet as initialOwner; checkpoint anchoring is a pure protocol
/// operation that does not require agent existence checks.
///
/// ─────────────────────────────────────────────────────────────────────
/// Anti-replay, monotonic, and freshness guards
/// ─────────────────────────────────────────────────────────────────────
///
/// appendCheckpoint enforces three integrity properties (Pass 2C Section 3.4):
///
///   Anti-replay  — each merkleRoot must be globally unique across the
///                  contract's lifetime. Replaying a previously-anchored
///                  root reverts with DuplicateMerkleRoot. Tracked via
///                  mapping(bytes32 => bool) _seenRoots.
///
///   Monotonic    — each append must have treeSize > previousTreeSize.
///                  The Merkle tree only grows; it never shrinks or stays
///                  the same. Reverts with NonMonotonicTreeSize.
///
///   Freshness    — each append must have timestamp >= block.timestamp - 3600.
///                  Prevents backdating attacks where a stale signed-tree-head
///                  is anchored long after it was produced. Reverts with
///                  StaleTimestamp.
///
/// Future timestamps (timestamp > block.timestamp) are allowed within reason
/// to accommodate clock skew between Tessera and the on-chain block clock.
/// No explicit upper bound is enforced; operator wallet ownership is the
/// trust anchor for whether the timestamp is genuine.
///
/// ─────────────────────────────────────────────────────────────────────
/// Phase O0 status
/// ─────────────────────────────────────────────────────────────────────
///
/// This contract ships as Stream 2-prep Session 3 work. No checkpoints exist
/// at deployment; first checkpoint occurs in P1+ when the Tessera upstream
/// feed is wired up. getLatestCheckpoint() returns sentinel zero values
/// (bytes32(0), 0, 0, 0) on empty state rather than reverting — initial
/// queries should not fail.
///
/// @dev Only the owner (bridge wallet) may append checkpoints. View functions
///      are public for off-chain audit query.
/// @dev MAX_TIMESTAMP_AGE constant (3600 seconds = 1 hour) per Pass 2C
///      Section 3.4 freshness guard specification.

contract AuditLog is Ownable, ReentrancyGuard {

    /// @notice Maximum age in seconds for a checkpoint timestamp at append
    ///         time. Pass 2C Section 3.4 freshness guard.
    uint256 public constant MAX_TIMESTAMP_AGE = 3600;

    struct Checkpoint {
        bytes32 merkleRoot;
        uint256 treeSize;
        uint256 timestamp;     // Tessera signed-tree-head timestamp (operator-provided)
        uint256 blockNumber;   // On-chain block at append time (automatic)
    }

    /// @dev Append-only array of checkpoint records. Indexed by checkpointId
    ///      (the array index, also emitted in CheckpointAppended events).
    Checkpoint[] private _checkpoints;

    /// @dev Anti-replay tracker. mapping(merkleRoot => seen) prevents the same
    ///      Merkle root from being anchored twice.
    mapping(bytes32 => bool) private _seenRoots;

    event CheckpointAppended(
        uint256 indexed checkpointId,
        bytes32 merkleRoot,
        uint256 treeSize,
        uint256 timestamp
    );

    /// @notice Custom error: zero merkleRoot is not a valid checkpoint.
    error InvalidMerkleRoot();

    /// @notice Custom error: this merkleRoot has already been anchored.
    error DuplicateMerkleRoot(bytes32 merkleRoot);

    /// @notice Custom error: treeSize must strictly exceed the previous
    ///         checkpoint's treeSize (Merkle tree only grows).
    error NonMonotonicTreeSize(uint256 newTreeSize, uint256 previousTreeSize);

    /// @notice Custom error: timestamp is older than MAX_TIMESTAMP_AGE seconds
    ///         relative to block.timestamp; the signed-tree-head is stale.
    error StaleTimestamp(uint256 timestamp, uint256 minTimestamp);

    constructor(address initialOwner) Ownable(initialOwner) {
        // Ownable's constructor reverts on zero-address; no further check needed.
    }

    /// @notice Append a Tessera signed-tree-head checkpoint. Owner-only.
    /// @param merkleRoot  Merkle root of the signed audit tree (must be non-zero
    ///                    and not previously seen)
    /// @param treeSize    Total leaf count of the Merkle tree at signing time
    ///                    (must strictly exceed the previous checkpoint's treeSize)
    /// @param timestamp   Tessera signed-tree-head timestamp (must be at most
    ///                    MAX_TIMESTAMP_AGE seconds older than block.timestamp)
    function appendCheckpoint(
        bytes32 merkleRoot,
        uint256 treeSize,
        uint256 timestamp
    ) external onlyOwner {
        if (merkleRoot == bytes32(0)) {
            revert InvalidMerkleRoot();
        }
        if (_seenRoots[merkleRoot]) {
            revert DuplicateMerkleRoot(merkleRoot);
        }

        // Monotonic treeSize guard: each append's tree must be strictly larger
        // than the previous. On the first append (empty array), any positive
        // treeSize satisfies (previousTreeSize is implicitly 0).
        uint256 previousTreeSize = 0;
        if (_checkpoints.length > 0) {
            previousTreeSize = _checkpoints[_checkpoints.length - 1].treeSize;
        }
        if (treeSize <= previousTreeSize) {
            revert NonMonotonicTreeSize(treeSize, previousTreeSize);
        }

        // Freshness guard: timestamp must be within MAX_TIMESTAMP_AGE seconds
        // of block.timestamp. Future timestamps allowed (clock skew tolerance);
        // only the lower bound is enforced.
        uint256 minTimestamp = block.timestamp > MAX_TIMESTAMP_AGE
            ? block.timestamp - MAX_TIMESTAMP_AGE
            : 0;
        if (timestamp < minTimestamp) {
            revert StaleTimestamp(timestamp, minTimestamp);
        }

        _seenRoots[merkleRoot] = true;
        uint256 checkpointId = _checkpoints.length;
        _checkpoints.push(Checkpoint({
            merkleRoot: merkleRoot,
            treeSize: treeSize,
            timestamp: timestamp,
            blockNumber: block.number
        }));

        emit CheckpointAppended(checkpointId, merkleRoot, treeSize, timestamp);
    }

    /// @notice Read the most recent checkpoint.
    /// @dev Returns sentinel zero values (bytes32(0), 0, 0, 0) on empty state
    ///      rather than reverting, so initial queries succeed before P1+
    ///      activation.
    /// @return root         The merkleRoot of the latest checkpoint
    /// @return size         The treeSize of the latest checkpoint
    /// @return ts           The Tessera-signed timestamp of the latest checkpoint
    /// @return blockNumber  The on-chain block number at append time
    function getLatestCheckpoint()
        external
        view
        returns (bytes32 root, uint256 size, uint256 ts, uint256 blockNumber)
    {
        if (_checkpoints.length == 0) {
            return (bytes32(0), 0, 0, 0);
        }
        Checkpoint memory cp = _checkpoints[_checkpoints.length - 1];
        return (cp.merkleRoot, cp.treeSize, cp.timestamp, cp.blockNumber);
    }

    /// @notice Read a specific checkpoint by id (array index).
    /// @dev Reverts on out-of-bounds via Solidity's default array bounds check.
    /// @param checkpointId  Zero-indexed checkpoint id
    /// @return root         The merkleRoot
    /// @return size         The treeSize
    /// @return ts           The Tessera-signed timestamp
    /// @return blockNumber  The on-chain block number at append time
    function getCheckpoint(uint256 checkpointId)
        external
        view
        returns (bytes32 root, uint256 size, uint256 ts, uint256 blockNumber)
    {
        Checkpoint memory cp = _checkpoints[checkpointId];
        return (cp.merkleRoot, cp.treeSize, cp.timestamp, cp.blockNumber);
    }

    /// @notice Convenience: total number of checkpoints anchored.
    function totalCheckpoints() external view returns (uint256) {
        return _checkpoints.length;
    }

    /// @notice Convenience predicate: has this Merkle root been anchored?
    function isAnchored(bytes32 merkleRoot) external view returns (bool) {
        return _seenRoots[merkleRoot];
    }
}
