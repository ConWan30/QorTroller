// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;
import "@openzeppelin/contracts/access/Ownable.sol";

/// @notice Interface for the Phase 111 AdjudicationRegistry composition check.
/// @dev    Live IoTeX testnet address 0x44CF981f46a52ADE56476Ce894255954a7776fb4.
///         Address bound at VPMAnchorRegistry construction; immutable after deploy.
interface IAdjudicationRegistry {
    function isRecorded(bytes32 poadHash) external view returns (bool);
}

/// @title VPMAnchorRegistry — Phase O4-VPM-ANCHOR / Verified Projection Media on-chain anchor
/// @notice Anchors VPM (Verified Projection Media) artifact manifests on IoTeX testnet,
///         extending the FROZEN quadruple-bind (primitive ↔ compiler ↔ visual grammar ↔
///         iframe sandbox) into a quintuple-bind by adding a frozen on-chain anchor.
///
///         The cryptographic composition link enforced by this registry:
///
///             VPM manifest hash  ──anchored along with──>  underlying ZKBA manifest hash
///
///         A VPM artifact may only be anchored if its declared zkba_manifest_hash_hex
///         references a real on-chain-anchored ZKBA via AdjudicationRegistry.isRecorded()
///         (cross-contract referential integrity check at anchor time).
///
///         FROZEN guards:
///           - Anti-replay: each vpm_manifest_hash UNIQUE (cannot re-anchor the same VPM)
///           - Cross-contract integrity: zkba_manifest_hash MUST be already anchored
///             in AdjudicationRegistry (no orphan VPM anchors)
///           - Owner-only writes (operator three-factor authorization upstream)
///           - CEI (Checks-Effects-Interactions) on every state change
///           - Zero-hash + zero-address guards
///
/// @dev   Phase O4-VPM-ANCHOR. Deployment to IoTeX testnet (chain ID 4690) ~0.1 IOTX
///        estimated. Wallet-free until operator fires deploy ceremony. Deploy via
///        scripts/deploy-vpm-anchor-registry.js with operator three-factor pattern.
contract VPMAnchorRegistry is Ownable {

    /// @notice The AdjudicationRegistry whose isRecorded() this registry composes.
    IAdjudicationRegistry public immutable adjudicationRegistry;

    struct VPMRecord {
        bytes32 zkbaManifestHash;
        bytes32 vpmManifestHash;
        uint256 blockNumber;
        uint256 recordedAt;
        uint64  tsNs;
    }

    /// @notice vpm_manifest_hash → record (each VPM hash uniquely anchored)
    mapping(bytes32 => VPMRecord) public records;

    /// @notice vpm_manifest_hash → recorded flag (UNIQUE anti-replay guard)
    mapping(bytes32 => bool) public vpmRecorded;

    /// @notice zkba_manifest_hash → array of VPM manifest hashes that wrap it
    /// @dev    Enables forward composition lookup: "what VPMs were generated
    ///         from this ZKBA artifact?"
    mapping(bytes32 => bytes32[]) public zkbaToVpms;

    uint256 public totalAnchored;

    event VPMAnchored(
        bytes32 indexed zkbaManifestHash,
        bytes32 indexed vpmManifestHash,
        uint256 blockNumber,
        uint64  tsNs
    );

    /// @param adjudicationRegistryAddr The AdjudicationRegistry contract this anchor
    ///        composes with. Zero address rejected. Address is immutable post-deploy.
    constructor(address adjudicationRegistryAddr) Ownable(msg.sender) {
        require(adjudicationRegistryAddr != address(0), "VPM: zero adjudication registry");
        adjudicationRegistry = IAdjudicationRegistry(adjudicationRegistryAddr);
    }

    // -----------------------------------------------------------------------
    // Anchoring API (operator-gated upstream via CHAIN_SUBMISSION_PAUSED kill-switch)
    // -----------------------------------------------------------------------

    /// @notice Anchor a VPM manifest hash, cryptographically bound to its underlying
    ///         ZKBA manifest. Reverts if either hash is zero, if the VPM hash is
    ///         already anchored (anti-replay), or if the ZKBA manifest is not yet
    ///         anchored in AdjudicationRegistry (cross-contract integrity).
    /// @param zkbaManifestHash The SHA-256 of the underlying ZKBA manifest's
    ///        canonical bytes (FROZEN per INV-VPM-WRAPPER-001 composition link).
    /// @param vpmManifestHash  The SHA-256 of the VPM artifact manifest's
    ///        canonical bytes.
    /// @param tsNs             Caller-supplied uint64 timestamp (off-chain ns
    ///        precision; chain stores block.timestamp separately).
    function anchorVPM(
        bytes32 zkbaManifestHash,
        bytes32 vpmManifestHash,
        uint64  tsNs
    ) external onlyOwner {
        require(zkbaManifestHash != bytes32(0), "VPM: zero zkba hash");
        require(vpmManifestHash != bytes32(0),  "VPM: zero vpm hash");
        require(!vpmRecorded[vpmManifestHash],  "VPM: already anchored");
        require(
            adjudicationRegistry.isRecorded(zkbaManifestHash),
            "VPM: zkba not anchored"
        );

        // CEI: state before external interactions / events
        vpmRecorded[vpmManifestHash] = true;
        records[vpmManifestHash] = VPMRecord({
            zkbaManifestHash: zkbaManifestHash,
            vpmManifestHash:  vpmManifestHash,
            blockNumber:      block.number,
            recordedAt:       block.timestamp,
            tsNs:             tsNs
        });
        zkbaToVpms[zkbaManifestHash].push(vpmManifestHash);
        totalAnchored++;

        emit VPMAnchored(zkbaManifestHash, vpmManifestHash, block.number, tsNs);
    }

    // -----------------------------------------------------------------------
    // View helpers
    // -----------------------------------------------------------------------

    /// @notice Returns true if a VPM manifest hash has been anchored.
    function isAnchored(bytes32 vpmManifestHash) external view returns (bool) {
        return vpmRecorded[vpmManifestHash];
    }

    /// @notice Returns the full VPM record for a manifest hash. Returns
    ///         zero-initialized struct if not anchored.
    function getRecord(bytes32 vpmManifestHash) external view returns (VPMRecord memory) {
        return records[vpmManifestHash];
    }

    /// @notice Returns the count of VPM artifacts that wrap a given ZKBA manifest.
    function getVpmsForZkbaCount(bytes32 zkbaManifestHash)
        external
        view
        returns (uint256)
    {
        return zkbaToVpms[zkbaManifestHash].length;
    }

    /// @notice Returns the VPM manifest hash at index i for a given ZKBA wrap.
    function getVpmForZkbaAt(bytes32 zkbaManifestHash, uint256 index)
        external
        view
        returns (bytes32)
    {
        require(index < zkbaToVpms[zkbaManifestHash].length, "VPM: index OOB");
        return zkbaToVpms[zkbaManifestHash][index];
    }
}
