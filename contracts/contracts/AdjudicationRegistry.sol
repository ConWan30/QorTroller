// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;
import "@openzeppelin/contracts/access/Ownable.sol";

/// @title AdjudicationRegistry — Phase 111 PoAd Anchor
/// @notice Stores cryptographic proofs of ioSwarm adjudication verdicts on-chain.
///         On-chain anchoring (bridge → chain.record_adjudication()) is deferred to Phase 112.
///         Phase 111 deploys infrastructure only; poad_registry_enabled=False in bridge.
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

    uint256 public totalAdjudications;

    event AdjudicationAnchored(
        bytes32 indexed deviceIdHash,
        bytes32 indexed poadHash,
        bool dualVeto,
        uint256 blockNumber
    );

    constructor() Ownable(msg.sender) {}

    /// @notice Record a PoAd hash on-chain.
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

    /// @notice Returns true if a PoAd hash has been anchored. Used by Phase 113 tournament gate.
    function isRecorded(bytes32 poadHash) external view returns (bool) {
        return poadRecorded[poadHash];
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
