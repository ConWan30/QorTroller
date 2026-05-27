// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/access/Ownable.sol";
import "@openzeppelin/contracts/utils/ReentrancyGuard.sol";

/// @title VAPIManufacturerDeviceRegistry — Path A Arc 1 (Commit 2)
/// @notice VAPIManufacturerDeviceRegistry — Path A silicon-rooted device birth certificate registry.
/// @dev Trust model: MANUFACTURER-AUTHORITATIVE (onlyOwner = QorTroller Foundation or partner HSM wallet).
///      Deliberate divergence from VAPIPoEPRegistry (gamer-sovereign, msg.sender = gamer):
///      - VAPIPoEPRegistry: gamer self-registers their composite renewal key
///      - VAPIManufacturerDeviceRegistry: manufacturer registers device-as-shipped hardware identity
///      Both registries coexist. VAPIProtocolLens_v2 composes both for isFullyEligible_PathA().
///      Path A v1 scope: silicon-rooted iPACT renewal authenticity.
///      Path A v2 (future, Arc 3+): per-PoAC record silicon-root at 1000 Hz cadence.
///
///      Pattern: Ownable + ReentrancyGuard (mirrors VAPIPoEPRegistry / VAPIConsentRegistry).
///      Storage: per-device DeviceRegistration struct, keyed by bytes32 deviceId.
///      pubkeyHash is SHA-256 of the COMPRESSED ECDSA-P256 pubkey (33 bytes); manufacturer
///      attests the device shipped with this on-chip key. The hash anchors the silicon root
///      so a tournament verifier can re-compute it against the device's reported pubkey.
///
///      Anti-replay: deviceId can be registered at most once (one device = one birth event).
///      Revocation is one-way (active=false); a new device with a new pubkey must use a new
///      deviceId. This is intentional — a single hardware unit's birth identity is permanent;
///      compromised units are revoked but their record is preserved for forensic audit.
///
/// @dev FROZEN enum constants (pinned by scripts/vapi_invariant_gate.py):
///        SIGNING_PATH_A = 1  → silicon-rooted (ATECC608A or equivalent secure element)
///        SIGNING_PATH_B = 2  → host-held JSON key (current default; VAPIPoEPRegistry path)
///        PROOF_TIER_FULL     = 1  → DualSense Edge CFI-ZCP1: adaptive triggers + 1002 Hz + IMU
///        PROOF_TIER_STANDARD = 2  → DualSense CFI-ZCT1: limited adaptive triggers + ~1000 Hz
///        PROOF_TIER_BASIC    = 3  → third-party: no adaptive triggers, lower polling
///      Drift in these values silently inverts every Path A eligibility decision OR silently
///      reclassifies hardware capability — INV-MFG-001 and INV-MFG-002 pin both literals.
contract VAPIManufacturerDeviceRegistry is Ownable, ReentrancyGuard {

    // ── FROZEN enum constants (INV-MFG-001 / INV-MFG-002) ────────────────────

    uint8 public constant SIGNING_PATH_A = 1;   // silicon-rooted (ATECC608A or equivalent)
    uint8 public constant SIGNING_PATH_B = 2;   // host-held JSON key

    uint8 public constant PROOF_TIER_FULL     = 1;  // DualSense Edge CFI-ZCP1
    uint8 public constant PROOF_TIER_STANDARD = 2;  // DualSense CFI-ZCT1
    uint8 public constant PROOF_TIER_BASIC    = 3;  // third-party / generic

    // ── Storage ──────────────────────────────────────────────────────────────

    struct DeviceRegistration {
        bytes32 pubkeyHash;          // sha256(compressed_ecdsa_p256_pubkey — 33 bytes)
        bytes32 controllerModel;     // keccak256("CFI-ZCP1") | keccak256("CFI-ZCT1") | ...
        uint8   signingPath;         // SIGNING_PATH_A or SIGNING_PATH_B
        uint8   proofTier;           // PROOF_TIER_FULL | STANDARD | BASIC
        uint64  registeredAt;        // block.timestamp at registration
        bytes32 birthCertHash;       // sha256(DeviceBirthCertificate canonical bytes)
        address manufacturerWallet;  // msg.sender at registration (= contract owner in v1)
        bool    active;              // false after revoke (one-way)
    }

    /// deviceId → DeviceRegistration. Zero-init when unregistered (pubkeyHash == 0).
    mapping(bytes32 => DeviceRegistration) public devices;

    /// Anti-replay: a deviceId may be registered at most once. Decoupled from `devices`
    /// so a revoked device's pubkeyHash check + registration check are independent.
    mapping(bytes32 => bool) public registered;

    /// Lifetime registration count (not decremented on revoke — forensic-stable).
    uint256 public totalRegistrations;

    // ── Events ───────────────────────────────────────────────────────────────

    event DeviceRegistered(
        bytes32 indexed deviceId,
        bytes32         controllerModel,
        uint8           signingPath,
        uint8           proofTier
    );

    event DeviceRevoked(bytes32 indexed deviceId);

    // ── Constructor ──────────────────────────────────────────────────────────

    constructor(address initialOwner) Ownable(initialOwner) {}

    // ── Writers (onlyOwner) ──────────────────────────────────────────────────

    /// @notice Register a device's birth identity. One-shot per deviceId — to replace, revoke
    ///         then register with a NEW deviceId. msg.sender (the owner) is the attesting
    ///         manufacturer wallet for forensic record.
    /// @param deviceId         canonical device id (bytes32; matches the rest of the protocol)
    /// @param pubkeyHash       sha256(compressed_ecdsa_p256_pubkey blob, 33 bytes)
    /// @param controllerModel  keccak256("CFI-ZCP1") etc. — model identifier
    /// @param signingPath      SIGNING_PATH_A (silicon) or SIGNING_PATH_B (host JSON)
    /// @param proofTier        PROOF_TIER_FULL / STANDARD / BASIC
    /// @param birthCertHash    sha256(DeviceBirthCertificate canonical bytes); off-chain cert
    ///                         lives in the manufacturer's ceremony output + the gamer's host
    function registerDevice(
        bytes32 deviceId,
        bytes32 pubkeyHash,
        bytes32 controllerModel,
        uint8   signingPath,
        uint8   proofTier,
        bytes32 birthCertHash
    ) external onlyOwner nonReentrant {
        require(!registered[deviceId],       "VMDR: already registered");
        require(pubkeyHash != bytes32(0),    "VMDR: zero pubkeyHash");
        require(birthCertHash != bytes32(0), "VMDR: zero birthCertHash");
        require(
            signingPath == SIGNING_PATH_A || signingPath == SIGNING_PATH_B,
            "VMDR: invalid signingPath"
        );
        require(
            proofTier >= PROOF_TIER_FULL && proofTier <= PROOF_TIER_BASIC,
            "VMDR: invalid proofTier"
        );

        devices[deviceId] = DeviceRegistration({
            pubkeyHash:         pubkeyHash,
            controllerModel:    controllerModel,
            signingPath:        signingPath,
            proofTier:          proofTier,
            registeredAt:       uint64(block.timestamp),
            birthCertHash:      birthCertHash,
            manufacturerWallet: msg.sender,
            active:             true
        });
        registered[deviceId] = true;
        totalRegistrations++;

        emit DeviceRegistered(deviceId, controllerModel, signingPath, proofTier);
    }

    /// @notice Revoke a device's birth registration. One-way; preserves the record for audit.
    function revokeDevice(bytes32 deviceId) external onlyOwner nonReentrant {
        require(registered[deviceId], "VMDR: not registered");
        require(devices[deviceId].active, "VMDR: already revoked");
        devices[deviceId].active = false;
        emit DeviceRevoked(deviceId);
    }

    // ── Views ────────────────────────────────────────────────────────────────

    /// @return 0 if not registered, else the SIGNING_PATH_A/B value.
    function getSigningPath(bytes32 deviceId) external view returns (uint8) {
        return devices[deviceId].signingPath;
    }

    /// @return 0 if not registered, else the PROOF_TIER_FULL/STANDARD/BASIC value.
    function getProofTier(bytes32 deviceId) external view returns (uint8) {
        return devices[deviceId].proofTier;
    }

    /// @return true iff registered AND active AND signingPath == SIGNING_PATH_A.
    function isPathA(bytes32 deviceId) external view returns (bool) {
        return registered[deviceId]
            && devices[deviceId].active
            && devices[deviceId].signingPath == SIGNING_PATH_A;
    }

    /// @return true iff registered AND active (regardless of signingPath).
    function isActive(bytes32 deviceId) external view returns (bool) {
        return registered[deviceId] && devices[deviceId].active;
    }

    /// @notice Full registration record. Zero-init struct returned when unregistered.
    function getDevice(bytes32 deviceId) external view returns (DeviceRegistration memory) {
        return devices[deviceId];
    }
}
