// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;
import "@openzeppelin/contracts/access/Ownable.sol";
import "@openzeppelin/contracts/utils/ReentrancyGuard.sol";

/// @title ProtocolCoherenceRegistry — Phase 221/227 Proof of Protocol Coherence (PoPC)
/// @notice On-chain anchor for the Merkle root computed over all VAPI agent fleet
///         observations at a point in time.  Proves the full agent fleet was observed
///         and coherent at anchor time.
///
///         Phase 227: anchorCoherenceWithProvenance() additionally anchors the
///         governance_provenance_hash (SHA-256 chain over all --generate events).
///         The GOVERNANCE_PROVENANCE_ANCHOR_DRIFT FSCA rule cross-checks the live SQLite
///         chain against this on-chain anchor, reducing the silent-tamper window to
///         one anchor cycle (default 1h).
///
///         Root construction (off-chain, Python bridge):
///           leaf_i = sha256(agent_id_bytes || ts_ns.to_bytes(8,'big'))
///           root   = Merkle(sorted(leaf_i for i in range(N_AGENTS)))
///
///         isCoherent(maxAgeSec) sub-check is wired into VAPIProtocolLens.isFullyEligible()
///         once PROTOCOL_COHERENCE_ENABLED=true and the registry address is configured.
///
///         Anti-replay: same merkleRoot cannot be anchored twice.
///         Zero-root guard: bytes32(0) always reverts.
///         Pattern: Ownable + ReentrancyGuard (CeremonyAuditRegistry Phase 179).
contract ProtocolCoherenceRegistry is Ownable, ReentrancyGuard {

    struct CoherenceAnchor {
        bytes32 merkleRoot;              // Merkle root over N agent observations
        uint256 agentCount;              // Number of agents included in the Merkle tree
        uint256 tsNs;                    // Off-chain observation timestamp (nanoseconds)
        uint256 anchoredAt;              // block.timestamp at anchor time
        bytes32 governanceProvenanceHash;// Phase 227: latest governance provenance hash (0 if unavailable)
    }

    CoherenceAnchor[] private _anchors;

    // Anti-replay: merkleRoot => already anchored
    mapping(bytes32 => bool) private _anchored;

    uint256 public totalAnchors;

    event CoherenceAnchored(
        bytes32 indexed merkleRoot,
        uint256 agentCount,
        uint256 tsNs,
        uint256 blockNumber
    );

    event CoherenceAnchoredWithProvenance(
        bytes32 indexed merkleRoot,
        bytes32 indexed governanceProvenanceHash,
        uint256 agentCount,
        uint256 tsNs,
        uint256 blockNumber
    );

    constructor(address initialOwner) Ownable(initialOwner) {}

    /// @notice Anchor a Merkle root over the current agent fleet observation.
    ///         Reverts on zero root, duplicate root, or zero agent count.
    ///         Backward-compatible: governanceProvenanceHash stored as bytes32(0).
    function anchorCoherence(
        bytes32 merkleRoot,
        uint256 agentCount,
        uint256 tsNs
    ) external onlyOwner nonReentrant {
        require(merkleRoot != bytes32(0), "ProtocolCoherenceRegistry: zero merkleRoot");
        require(!_anchored[merkleRoot], "ProtocolCoherenceRegistry: duplicate merkleRoot");
        require(agentCount > 0, "ProtocolCoherenceRegistry: zero agentCount");

        _anchored[merkleRoot] = true;
        _anchors.push(CoherenceAnchor({
            merkleRoot:               merkleRoot,
            agentCount:               agentCount,
            tsNs:                     tsNs,
            anchoredAt:               block.timestamp,
            governanceProvenanceHash: bytes32(0)
        }));
        totalAnchors++;

        emit CoherenceAnchored(merkleRoot, agentCount, tsNs, block.number);
    }

    /// @notice Anchor a Merkle root alongside the latest governance provenance hash.
    ///         Phase 227: enables GOVERNANCE_PROVENANCE_ANCHOR_DRIFT cross-check in FSCA.
    ///         Anti-replay on merkleRoot (same merkleRoot cannot be anchored twice,
    ///         regardless of which anchor function was used).
    function anchorCoherenceWithProvenance(
        bytes32 merkleRoot,
        bytes32 governanceProvenanceHash,
        uint256 agentCount,
        uint256 tsNs
    ) external onlyOwner nonReentrant {
        require(merkleRoot != bytes32(0), "ProtocolCoherenceRegistry: zero merkleRoot");
        require(!_anchored[merkleRoot], "ProtocolCoherenceRegistry: duplicate merkleRoot");
        require(agentCount > 0, "ProtocolCoherenceRegistry: zero agentCount");

        _anchored[merkleRoot] = true;
        _anchors.push(CoherenceAnchor({
            merkleRoot:               merkleRoot,
            agentCount:               agentCount,
            tsNs:                     tsNs,
            anchoredAt:               block.timestamp,
            governanceProvenanceHash: governanceProvenanceHash
        }));
        totalAnchors++;

        emit CoherenceAnchoredWithProvenance(
            merkleRoot, governanceProvenanceHash, agentCount, tsNs, block.number
        );
    }

    /// @notice Return the latest anchored (merkleRoot, anchoredAt, agentCount).
    ///         Returns (bytes32(0), 0, 0) when no anchors exist.
    function getLatestCoherence()
        external view
        returns (bytes32 root, uint256 ts, uint256 count)
    {
        if (_anchors.length == 0) return (bytes32(0), 0, 0);
        CoherenceAnchor storage a = _anchors[_anchors.length - 1];
        return (a.merkleRoot, a.anchoredAt, a.agentCount);
    }

    /// @notice Return the most recent governance provenance hash anchored on-chain.
    ///         Returns bytes32(0) when no anchors exist or all used anchorCoherence().
    function getLatestGovernanceProvenance() external view returns (bytes32) {
        if (_anchors.length == 0) return bytes32(0);
        return _anchors[_anchors.length - 1].governanceProvenanceHash;
    }

    /// @notice Return the anchor at a specific index.
    ///         Reverts when index >= totalAnchors.
    function getAnchorAt(uint256 index) external view returns (CoherenceAnchor memory) {
        require(index < _anchors.length, "ProtocolCoherenceRegistry: index out of range");
        return _anchors[index];
    }

    /// @notice Returns true when the most recent anchor is within maxAgeSec seconds.
    ///         Used by VAPIProtocolLens.isFullyEligible() as an optional sub-check.
    ///         Returns false when no anchors exist.
    function isCoherent(uint256 maxAgeSec) external view returns (bool) {
        if (_anchors.length == 0) return false;
        CoherenceAnchor storage a = _anchors[_anchors.length - 1];
        return (block.timestamp - a.anchoredAt) <= maxAgeSec;
    }
}
