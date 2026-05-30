// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/access/Ownable.sol";

/**
 * @title VAPITemporalBeaconRegistry — Data Economy Arc 6 (PoSR)
 * @notice Durable on-chain anchor for IoTeX block hashes used to bind VHR
 *         session boundaries to verifiable time.
 *
 * Closes three attack surfaces left open by Arc 5 (VHR):
 *
 *   1. Stale re-listing — a real VHR proof from weeks ago re-listed as fresh
 *   2. Pre-computation drip — operator batches valid proofs from a corpus
 *      of real sessions, releases on a schedule to simulate ongoing activity
 *   3. Tournament-window backdating — session outside the eligibility window
 *      claimed to have occurred inside it
 *
 * Each session binds its open and close boundaries to a publicly verifiable
 * block hash that did not exist before the session occurred. The hash is
 * anchored here durably so verification still works after IoTeX's 256-block
 * BLOCKHASH window (~11 min empirical on testnet) lapses.
 *
 * FROZEN-v1 #14 domain tag: `VAPI-TEMPORAL-BEACON-v1` (INV-TBR-001). New
 * PATTERN-017 family — does NOT overload any Arc 5 invariant.
 *
 * Anchoring is permissionless-readable, keeper-written. No gamer data on-chain.
 *
 * @dev DEPLOYMENT — gated on:
 *   - Arc 5 fully live (Verifier wrapper + ceremony zkey + bridge wiring)
 *   - Operator GO + VAPI_TBR_DEPLOY_CONFIRM=1 via the deploy script
 *
 *   Honest cost (empirical 2.6s/block on IoTeX testnet 2026-05-30):
 *     ANCHOR_CADENCE=64 → ~167s/anchor → ~516 anchors/day → ~0.258 IOTX/day
 *     (Spec assumed 5s/block which would give ~0.135 IOTX/day; revised here.)
 */
contract VAPITemporalBeaconRegistry is Ownable {
    /// @notice FROZEN-v1 #14 domain tag, pinned by INV-TBR-001. Any change
    /// breaks the entire PoSR primitive — drift here cascades through
    /// VAPIReplayProofVerifier_v2 + every off-chain verifier reproducing
    /// the open/close beacon commitment.
    bytes32 public constant BEACON_DOMAIN =
        keccak256("VAPI-TEMPORAL-BEACON-v1");

    /// @notice Block-number multiple at which the keeper is permitted to
    /// anchor a beacon. FROZEN by INV-TBR-002 at 64 blocks. Bridge clients
    /// must align session-boundary beacon reads to this cadence so the
    /// hash is always retrievable from this registry at verification time.
    uint256 public constant ANCHOR_CADENCE = 64;

    /// @notice The 256-block BLOCKHASH retention window of the EVM. Spec
    /// (informational only — not used as a require parameter beyond
    /// `block.number - blockNumber <= BLOCKHASH_WINDOW`).
    uint256 public constant BLOCKHASH_WINDOW = 256;

    /// blockNumber → blockHash. bytes32(0) means not yet anchored.
    mapping(uint256 => bytes32) public anchoredHash;

    /// @notice Highest block number for which a beacon is anchored.
    /// Off-chain readers use this to discover the freshest available anchor.
    uint256 public latestAnchoredBlock;

    /// @notice Authorized keeper address. Set by owner via setKeeper.
    /// In v1 this is the operator cron's wallet (single-developer testnet;
    /// see docs/posr-keeper-runbook.md). Future arcs may migrate to the
    /// Curator agent under expanded O3 scope (requires governance proposal).
    address public keeper;

    event BeaconAnchored(uint256 indexed blockNumber, bytes32 blockHash);
    event KeeperSet(address indexed previousKeeper, address indexed newKeeper);

    error NotKeeper();
    error FutureBlock();
    error OutsideBlockhashWindow();
    error NotCadenceBlock();
    error BlockhashUnavailable();

    constructor(address initialOwner) Ownable(initialOwner) {}

    /// @notice Set the authorized keeper. onlyOwner.
    function setKeeper(address k) external onlyOwner {
        address prev = keeper;
        keeper = k;
        emit KeeperSet(prev, k);
    }

    /// @notice Anchor the hash of a recent cadence-aligned block.
    /// @param blockNumber must be:
    ///   - < block.number (not future)
    ///   - within BLOCKHASH_WINDOW (256 blocks) so BLOCKHASH returns non-zero
    ///   - a multiple of ANCHOR_CADENCE (64) so reads align deterministically
    /// @dev Idempotent for already-anchored cadence blocks (same hash always
    ///      written; no reorg concern because BLOCKHASH after finalization
    ///      returns the canonical hash).
    function anchorBeacon(uint256 blockNumber) external {
        if (msg.sender != keeper) revert NotKeeper();
        if (blockNumber >= block.number) revert FutureBlock();
        if (block.number - blockNumber > BLOCKHASH_WINDOW) revert OutsideBlockhashWindow();
        if (blockNumber % ANCHOR_CADENCE != 0) revert NotCadenceBlock();

        bytes32 h = blockhash(blockNumber);
        if (h == bytes32(0)) revert BlockhashUnavailable();

        anchoredHash[blockNumber] = h;
        if (blockNumber > latestAnchoredBlock) {
            latestAnchoredBlock = blockNumber;
        }
        emit BeaconAnchored(blockNumber, h);
    }

    /// @notice Pure view — confirm a claimed beacon hash matches the anchored
    /// hash for blockNumber. Used by VAPIReplayProofVerifier_v2.verifyWithRecency
    /// at proof-verification time.
    function verifyBeacon(uint256 blockNumber, bytes32 claimedHash)
        external view returns (bool)
    {
        bytes32 stored = anchoredHash[blockNumber];
        return stored != bytes32(0) && stored == claimedHash;
    }

    /// @notice Latest available beacon — used by the bridge at session-open
    /// to pick the freshest cadence block for the open-beacon commitment.
    function latestBeacon() external view returns (uint256, bytes32) {
        return (latestAnchoredBlock, anchoredHash[latestAnchoredBlock]);
    }
}
