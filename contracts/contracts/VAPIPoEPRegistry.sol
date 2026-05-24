// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;
import "@openzeppelin/contracts/access/Ownable.sol";
import "@openzeppelin/contracts/utils/ReentrancyGuard.sol";

/// @title VAPIPoEPRegistry — Phase B ② P4b: gamer-sovereign composite-key / PoEP-commitment registry
/// @notice On-chain registry of a device's COMPOSITE public key (① encode_pubkey blob) + PoEP
///         commitment, keyed by (gamer, deviceId). Gamers (msg.sender) register their own devices;
///         the bridge READS this state via view calls + event logs but NEVER writes on the gamer's
///         behalf (self-sovereignty / W1). This is the production source of the composite pubkey the
///         ③/#8 re-attestation verifier needs (resolves #8 W-1).
///
///         Naming: VAPI-prefixed per the Layer-C V.A.P.I.-category contract-identifier convention
///         (QRESCE operating mode). The PoEP commitments it stores are QorTroller-branded
///         (QORTROLLER-POEP-v0) — that QorTroller data lives in the event PAYLOAD, not the
///         VAPI-prefixed event signature.
///
///         Pattern: Ownable + ReentrancyGuard (mirrors VAPIConsentRegistry / VAPIBiometricGovernance).
///         Storage: on-chain stores ONLY bytes32 compositePubkeyHash = sha256(blob); the full
///         (152–2058 byte) ① encode_pubkey blob is emitted NON-INDEXED in DeviceRegistered event
///         data (event-sourced; cheaper than SSTORE). Off-chain readers fetch the blob from the
///         event log and MUST verify sha256(blob) == on-chain hash before trusting it.
///         Anti-replay: poepCommitment cannot be submitted twice across all gamers (Option B —
///         matches VAPIConsentRegistry's record-the-commitment pattern). NOT on the composite
///         pubkey: a composite PUBLIC key is public, so global pubkey-uniqueness would be a
///         front-running grief vector (an attacker who observes a gamer's public key could register
///         it first and lock the owner out). poepCommitment is a commitment, not public → safe.
///         Zero-hash guard: poepCommitment != bytes32(0); empty blob rejected.
///
/// @dev expiresAt — FLAG A → Property X (renewal-agnostic registry): ③'s renewal cadence is the
///      SOLE lifetime authority. v1 requires expiresAt == 0 (reserved for a v2 if a registry-level
///      expiry distinct from ③ is ever justified); isRegistrationValid checks only !revoked.
contract VAPIPoEPRegistry is Ownable, ReentrancyGuard {

    struct PoEPRecord {
        bytes32 compositePubkeyHash; // sha256(① encode_pubkey blob)
        bytes32 poepCommitment;      // QORTROLLER-POEP-v0 SHA-256 commitment
        uint64  registeredAt;        // block.timestamp at registration
        uint64  expiresAt;           // v1: ALWAYS 0 (Property X; reserved for v2)
        bool    revoked;             // set true by revokeDevice
    }

    /// gamer → deviceId → PoEPRecord
    mapping(address => mapping(bytes32 => PoEPRecord)) private _records;

    /// Anti-replay across all gamers — a poepCommitment, once submitted, cannot be reused
    /// (Option B; mirrors VAPIConsentRegistry._recordedHashes). NOT on the composite pubkey
    /// (which is public → would be a front-running grief vector).
    mapping(bytes32 => bool) private _recordedCommitments;

    /// Optional VAPIioIDRegistry reference for off-chain DID resolution (not required to operate).
    address public ioidRegistry;

    /// Lifetime registration count (not decremented on revoke).
    uint256 public totalRegistrations;

    event DeviceRegistered(
        address indexed gamer,
        bytes32 indexed deviceId,
        bytes32 indexed compositePubkeyHash,
        bytes32         poepCommitment,
        bytes           compositePubkeyBlob, // NON-INDEXED: full ① encode_pubkey blob in event DATA
        uint64          expiresAt,
        uint256         blockNumber
    );

    event DeviceRevoked(
        address indexed gamer,
        bytes32 indexed deviceId,
        bytes32         priorCompositePubkeyHash,
        uint256         blockNumber
    );

    event IoIDRegistrySet(address indexed oldRegistry, address indexed newRegistry);

    constructor(address initialOwner) Ownable(initialOwner) {
        // ioidRegistry intentionally unset; setIoIDRegistry() is optional.
    }

    /// @notice Set/update the optional VAPIioIDRegistry reference. Reverts on zero address.
    function setIoIDRegistry(address newRegistry) external onlyOwner {
        require(newRegistry != address(0), "VPR: zero ioidRegistry");
        emit IoIDRegistrySet(ioidRegistry, newRegistry);
        ioidRegistry = newRegistry;
    }

    /// @notice Register (or re-register) the caller's device composite pubkey + PoEP commitment.
    ///         msg.sender is the gamer. Reverts when:
    ///           - compositePubkeyBlob is empty
    ///           - poepCommitment is bytes32(0)
    ///           - poepCommitment already submitted (anti-replay across all senders)
    ///           - expiresAt != 0 (v1 Property X — reserved for v2)
    ///         Re-registering the same deviceId overwrites the caller's prior record (new pubkey /
    ///         new commitment); the prior poepCommitment remains in the anti-replay set.
    ///         compositePubkeyHash = sha256(compositePubkeyBlob) is computed on-chain; the full blob
    ///         is emitted in the event (event-sourced storage).
    function registerDevice(
        bytes32 deviceId,
        bytes calldata compositePubkeyBlob,
        bytes32 poepCommitment,
        uint64 expiresAt
    ) external nonReentrant {
        require(compositePubkeyBlob.length > 0, "VPR: empty pubkey blob");
        require(poepCommitment != bytes32(0), "VPR: zero poepCommitment");
        require(!_recordedCommitments[poepCommitment], "VPR: duplicate poepCommitment");
        require(expiresAt == 0, "VPR: expiresAt reserved for v2"); // Property X

        bytes32 pkHash = sha256(compositePubkeyBlob);

        // CEI: state changes before the event emit (no external calls here)
        _recordedCommitments[poepCommitment] = true;
        _records[msg.sender][deviceId] = PoEPRecord({
            compositePubkeyHash: pkHash,
            poepCommitment:      poepCommitment,
            registeredAt:        uint64(block.timestamp),
            expiresAt:           0,
            revoked:             false
        });
        totalRegistrations++;

        emit DeviceRegistered(
            msg.sender, deviceId, pkHash, poepCommitment, compositePubkeyBlob, 0, block.number
        );
    }

    /// @notice Revoke the caller's registration for a device. msg.sender is the gamer.
    function revokeDevice(bytes32 deviceId) external nonReentrant {
        PoEPRecord storage rec = _records[msg.sender][deviceId];
        require(rec.compositePubkeyHash != bytes32(0), "VPR: nothing to revoke");
        require(!rec.revoked, "VPR: already revoked");
        rec.revoked = true;
        emit DeviceRevoked(msg.sender, deviceId, rec.compositePubkeyHash, block.number);
    }

    /// @notice Full record for (gamer, deviceId). Zero-record if none.
    function getRecord(address gamer, bytes32 deviceId)
        external view returns (PoEPRecord memory)
    {
        return _records[gamer][deviceId];
    }

    /// @notice The on-chain composite-pubkey hash anchor for (gamer, deviceId) — the value the
    ///         bridge compares sha256(event-sourced blob) against (integrity check).
    function getCompositePubkeyHash(address gamer, bytes32 deviceId)
        external view returns (bytes32)
    {
        return _records[gamer][deviceId].compositePubkeyHash;
    }

    /// @notice Valid iff registered AND not revoked. Property X: NO expiry check (③ is the sole
    ///         lifetime authority via its renewal cadence).
    function isRegistrationValid(address gamer, bytes32 deviceId)
        external view returns (bool)
    {
        PoEPRecord storage rec = _records[gamer][deviceId];
        if (rec.compositePubkeyHash == bytes32(0)) return false;
        if (rec.revoked) return false;
        return true;
    }

    /// @notice True when a poepCommitment has already been submitted (anti-replay surface).
    function isRecorded(bytes32 poepCommitment) external view returns (bool) {
        return _recordedCommitments[poepCommitment];
    }
}
