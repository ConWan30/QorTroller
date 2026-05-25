// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;
import "@openzeppelin/contracts/access/Ownable.sol";

/// @title SeparationRatioRegistry — Phase 153 + Phase 178 + Phase 186
/// @notice Stores SHA-256 proof-of-calibration commitments on IoTeX L1.
///         Phase 153: commit_hash = SHA-256(ratio_str + N + players_sorted + ts_ns)
///         Phase 178: adds ttl_days field and renewCommit() function.
///         renewCommit() links a new commitment to a previous one, enabling
///         a renewal chain for biometric credential TTL (WIF-029 W1 closure).
///         Anti-replay: UNIQUE commitHash guard on both commitRatio and renewCommit.
///         Phase 186 (WIF-032 W2): attestation-bound renewal — the on-chain
///         counterpart of the bridge AttestationBoundRenewalAgent. An attestation
///         (HMAC hash) is registered with a TTL, then consumed exactly once by
///         attestedRenewCommit (single-use + TTL anti-replay). Autoresearch-specced
///         (commit 2b01831b); validation suite = test/Phase186.test.js.
contract SeparationRatioRegistry is Ownable {

    struct RatioCommit {
        bytes32 commitHash;     // SHA-256(ratio_str | n_sessions | n_players | ts_ns)
        uint256 ratioMillis;    // separation_ratio * 1000 (e.g. 1261 = 1.261)
        uint32  nSessions;      // number of sessions in corpus
        uint32  nPlayers;       // number of players
        uint256 committedAt;    // block.timestamp
        uint256 blockNumber;    // block.number for cross-check
        uint32  ttlDays;        // Phase 178: credential TTL in days (0 = no TTL, 90 = default)
        bytes32 prevCommitHash; // Phase 178: previous commitment in renewal chain (0x0 = initial)
    }

    mapping(bytes32 => bool) public commitRecorded;
    RatioCommit[] private _commits;
    uint256 public totalCommits;

    event RatioCommitted(
        bytes32 indexed commitHash,
        uint256 ratioMillis,
        uint32  nSessions,
        uint32  nPlayers,
        uint256 blockNumber
    );

    /// @notice Phase 178: emitted on credential renewal linking prevHash → newHash.
    event RatioRenewed(
        bytes32 indexed prevCommitHash,
        bytes32 indexed newCommitHash,
        uint32  ttlDays,
        uint256 blockNumber
    );

    constructor(address initialOwner) Ownable(initialOwner) {}

    /// @notice Record a new ratio commitment. Reverts on duplicate commitHash.
    ///         ttlDays defaults to 0 (no TTL) for backward compatibility with Phase 153.
    function commitRatio(
        bytes32 commitHash,
        uint256 ratioMillis,
        uint32  nSessions,
        uint32  nPlayers
    ) external onlyOwner {
        require(!commitRecorded[commitHash], "SeparationRatioRegistry: duplicate commit");
        commitRecorded[commitHash] = true;
        _commits.push(RatioCommit({
            commitHash:     commitHash,
            ratioMillis:    ratioMillis,
            nSessions:      nSessions,
            nPlayers:       nPlayers,
            committedAt:    block.timestamp,
            blockNumber:    block.number,
            ttlDays:        0,
            prevCommitHash: bytes32(0)
        }));
        totalCommits++;
        emit RatioCommitted(commitHash, ratioMillis, nSessions, nPlayers, block.number);
    }

    /// @notice Phase 178: Renew an expiring commitment, linking it to the previous one.
    ///         newCommitHash = SHA-256(prevHash + ratio + N_consented + players + ttlDays + ts_ns)
    ///         Anti-replay: newCommitHash must be new (not previously recorded).
    ///         prevCommitHash must have been previously recorded.
    ///         ttlDays must be > 0 (renewal without TTL is meaningless).
    function renewCommit(
        bytes32 prevCommitHash,
        bytes32 newCommitHash,
        uint32  ttlDays
    ) external onlyOwner {
        require(ttlDays > 0, "SeparationRatioRegistry: ttlDays must be > 0");
        require(commitRecorded[prevCommitHash], "SeparationRatioRegistry: prevCommitHash not found");
        require(!commitRecorded[newCommitHash], "SeparationRatioRegistry: duplicate newCommitHash");
        commitRecorded[newCommitHash] = true;
        // Inherit ratioMillis, nSessions, nPlayers from the previous commit
        RatioCommit memory prev = _findByHash(prevCommitHash);
        _commits.push(RatioCommit({
            commitHash:     newCommitHash,
            ratioMillis:    prev.ratioMillis,
            nSessions:      prev.nSessions,
            nPlayers:       prev.nPlayers,
            committedAt:    block.timestamp,
            blockNumber:    block.number,
            ttlDays:        ttlDays,
            prevCommitHash: prevCommitHash
        }));
        totalCommits++;
        emit RatioRenewed(prevCommitHash, newCommitHash, ttlDays, block.number);
    }

    /// @notice Check whether a commitment has been recorded.
    function isCommitted(bytes32 commitHash) external view returns (bool) {
        return commitRecorded[commitHash];
    }

    /// @notice Return the most recent commitment.
    function getLatestCommit() external view returns (RatioCommit memory) {
        require(totalCommits > 0, "SeparationRatioRegistry: no commits");
        return _commits[totalCommits - 1];
    }

    /// @notice Return a specific commit by index.
    function getCommit(uint256 index) external view returns (RatioCommit memory) {
        require(index < totalCommits, "SeparationRatioRegistry: out of range");
        return _commits[index];
    }

    /// @dev Internal linear scan to find a commit by hash (used by renewCommit).
    ///      Acceptable for small N (protocol-grade calibration corpus, not high-frequency).
    function _findByHash(bytes32 h) internal view returns (RatioCommit memory) {
        for (uint256 i = totalCommits; i > 0; i--) {
            if (_commits[i - 1].commitHash == h) {
                return _commits[i - 1];
            }
        }
        revert("SeparationRatioRegistry: hash not found");
    }

    // ─────────────────────────────────────────────────────────────────────────
    // Phase 186 (WIF-032 W2) — Attestation-bound renewal
    // On-chain counterpart of the bridge AttestationBoundRenewalAgent. An
    // attestation (HMAC hash) is registered with a TTL, then consumed exactly
    // once by attestedRenewCommit. Anti-replay: single-use flag + TTL window.
    // ─────────────────────────────────────────────────────────────────────────

    struct AttestationRecord {
        uint32  ttlDays;       // attestation validity window in days
        uint256 registeredAt;  // block.timestamp at registration (0 = never registered)
        bool    used;          // true once consumed by attestedRenewCommit (single-use)
    }

    mapping(bytes32 => AttestationRecord) private _attestations;

    /// @notice Emitted when an attestation is registered.
    event AttestationRegistered(
        bytes32 indexed attestationHash,
        uint32  ttlDays,
        uint256 timestamp
    );

    /// @notice Emitted when a renewal is bound to (and consumes) an attestation.
    event AttestationBoundRenewal(
        bytes32 indexed prevCommitHash,
        bytes32 indexed newCommitHash,
        bytes32 indexed attestationHash,
        uint32  ttlDays,
        uint256 blockNumber
    );

    /// @notice Register an attestation hash with a TTL (in days). Single-use:
    ///         re-registering the same hash reverts (prevents resetting a used flag).
    function registerAttestation(bytes32 attestationHash, uint32 ttlDays) external onlyOwner {
        require(attestationHash != bytes32(0), "SeparationRatioRegistry: zero attestation hash");
        require(_attestations[attestationHash].registeredAt == 0, "SeparationRatioRegistry: attestation exists");
        _attestations[attestationHash] = AttestationRecord({
            ttlDays:      ttlDays,
            registeredAt: block.timestamp,
            used:         false
        });
        emit AttestationRegistered(attestationHash, ttlDays, block.timestamp);
    }

    /// @notice Read an attestation record.
    function getAttestation(bytes32 attestationHash) external view returns (AttestationRecord memory) {
        return _attestations[attestationHash];
    }

    /// @notice Renew a commitment, consuming a registered attestation exactly once.
    ///         Reverts if the attestation is unknown, already used, or past its TTL.
    ///         The renewal itself mirrors renewCommit() semantics (prev recorded,
    ///         new unique, inherits ratio/N from the previous commit).
    function attestedRenewCommit(
        bytes32 prevCommitHash,
        bytes32 newCommitHash,
        uint32  ttlDays,
        bytes32 attestationHash
    ) external onlyOwner {
        AttestationRecord storage att = _attestations[attestationHash];
        require(att.registeredAt != 0, "SeparationRatioRegistry: attestation not found");
        require(!att.used, "SeparationRatioRegistry: attestation already used");
        require(
            block.timestamp <= att.registeredAt + uint256(att.ttlDays) * 1 days,
            "SeparationRatioRegistry: attestation expired"
        );

        // Renewal preconditions (mirror renewCommit)
        require(ttlDays > 0, "SeparationRatioRegistry: ttlDays must be > 0");
        require(commitRecorded[prevCommitHash], "SeparationRatioRegistry: prevCommitHash not found");
        require(!commitRecorded[newCommitHash], "SeparationRatioRegistry: duplicate newCommitHash");

        // Consume the attestation (single-use) before recording the renewal.
        att.used = true;

        commitRecorded[newCommitHash] = true;
        RatioCommit memory prev = _findByHash(prevCommitHash);
        _commits.push(RatioCommit({
            commitHash:     newCommitHash,
            ratioMillis:    prev.ratioMillis,
            nSessions:      prev.nSessions,
            nPlayers:       prev.nPlayers,
            committedAt:    block.timestamp,
            blockNumber:    block.number,
            ttlDays:        ttlDays,
            prevCommitHash: prevCommitHash
        }));
        totalCommits++;
        emit AttestationBoundRenewal(prevCommitHash, newCommitHash, attestationHash, ttlDays, block.number);
    }
}
