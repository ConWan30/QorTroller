// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;
import "@openzeppelin/contracts/access/Ownable.sol";

/// @title AdjudicationRegistry — Phase 111 PoAd Anchor / VAPI-EXT Phase 204+
/// @notice Stores cryptographic proofs of ioSwarm adjudication verdicts on-chain.
///         Phase 111: recordAdjudication (VAPI_CORE legacy API).
///         VAPI-EXT: anchorAdjudication with sourceType for sub-protocol attribution.
contract AdjudicationRegistry is Ownable {
    struct PoAdRecord {
        bytes32 poadHash;
        uint256 blockNumber;
        uint256 recordedAt;
        bool dualVeto;
    }

    /// @notice deviceIdHash (keccak256(pubkey)) → ordered array of PoAd records
    mapping(bytes32 => PoAdRecord[]) public records;

    /// @notice poadHash → recorded flag — UNIQUE anti-replay guard
    mapping(bytes32 => bool) public poadRecorded;

    /// @notice poadHash → source sub-protocol ("VAPI", "VAPI_MOBILE", "PRAGMA_JUDGE", ...)
    /// @dev    Set by anchorAdjudication; empty string for recordAdjudication legacy entries.
    mapping(bytes32 => string) public poadSourceType;

    uint256 public totalAdjudications;

    event AdjudicationAnchored(
        bytes32 indexed deviceIdHash,
        bytes32 indexed poadHash,
        bool dualVeto,
        uint256 blockNumber
    );

    /// @notice Emitted by anchorAdjudication with sub-protocol source attribution.
    event AdjudicationAnchoredV2(
        bytes32 indexed podHash,
        string sourceType,
        uint256 blockNumber
    );

    constructor() Ownable(msg.sender) {}

    // -----------------------------------------------------------------------
    // Phase 111 — VAPI_CORE legacy API (backward-compatible, chain.py unchanged)
    // -----------------------------------------------------------------------

    /// @notice Record a PoAd hash on-chain (VAPI_CORE legacy call — chain.py unchanged).
    /// @param deviceIdHash keccak256(pubkey) of the adjudicated device
    /// @param poadHash     SHA-256 of sorted verdict bundle (operator-computed off-chain)
    /// @param dualVeto     true if both ClassJ and Triage quorums returned BLOCK
    function recordAdjudication(
        bytes32 deviceIdHash,
        bytes32 poadHash,
        bool dualVeto
    ) external onlyOwner {
        require(!poadRecorded[poadHash], "PoAd: already recorded");
        // CEI pattern: state before external interactions
        poadRecorded[poadHash] = true;
        records[deviceIdHash].push(PoAdRecord({
            poadHash: poadHash,
            blockNumber: block.number,
            recordedAt: block.timestamp,
            dualVeto: dualVeto
        }));
        totalAdjudications++;
        emit AdjudicationAnchored(deviceIdHash, poadHash, dualVeto, block.number);
    }

    // -----------------------------------------------------------------------
    // VAPI-EXT — Sub-protocol source-attributed anchoring API
    // -----------------------------------------------------------------------

    /// @notice Anchors an adjudication or verdict hash on-chain with source attribution.
    /// @param podHash    The SHA-256 hash of the adjudication or verdict record body.
    /// @param sourceType The sub-protocol that produced this record.
    ///        Valid values: "VAPI", "VAPI_MOBILE", "PRAGMA_JUDGE"
    function anchorAdjudication(
        bytes32 podHash,
        string memory sourceType
    ) external onlyOwner {
        _anchorAdjudication(podHash, sourceType);
    }

    /// @notice Overload for backward compatibility — existing VAPI call sites unchanged.
    function anchorAdjudication(bytes32 podHash) external onlyOwner {
        _anchorAdjudication(podHash, "VAPI");
    }

    /// @dev Internal implementation shared by both anchorAdjudication overloads.
    function _anchorAdjudication(bytes32 podHash, string memory sourceType) internal {
        require(!poadRecorded[podHash], "PoAd: already recorded");
        // CEI pattern: state before external interactions
        poadRecorded[podHash] = true;
        poadSourceType[podHash] = sourceType;
        totalAdjudications++;
        emit AdjudicationAnchoredV2(podHash, sourceType, block.number);
    }

    // -----------------------------------------------------------------------
    // View helpers
    // -----------------------------------------------------------------------

    /// @notice Returns true if a PoAd hash has been anchored. Used by Phase 113 tournament gate.
    function isRecorded(bytes32 poadHash) external view returns (bool) {
        return poadRecorded[poadHash];
    }

    /// @notice Returns the source type for a recorded pod hash ("" if recorded via legacy API).
    function getSourceType(bytes32 podHash) external view returns (string memory) {
        return poadSourceType[podHash];
    }

    /// @notice Returns the number of adjudication records for a device.
    function getAdjudicationCount(bytes32 deviceIdHash) external view returns (uint256) {
        return records[deviceIdHash].length;
    }

    /// @notice Returns a specific PoAd record by index.
    function getAdjudication(bytes32 deviceIdHash, uint256 index)
        external view returns (PoAdRecord memory)
    {
        require(index < records[deviceIdHash].length, "PoAd: index out of bounds");
        return records[deviceIdHash][index];
    }
}
