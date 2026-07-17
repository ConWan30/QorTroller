// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/access/Ownable.sol";

/// @dev Minimal view surface of VAPIManufacturerDeviceRegistry (0x2e5B5FB1...). We read `isActive`
///      and the `birthCertHash` field (index 5) of the public `devices` tuple getter. No struct import.
interface IVMDR {
    function isActive(bytes32 deviceId) external view returns (bool);
    function devices(bytes32 deviceId) external view returns (
        bytes32 pubkeyHash,
        bytes32 controllerModel,
        uint8   signingPath,
        uint8   proofTier,
        uint64  registeredAt,
        bytes32 birthCertHash,
        address manufacturerWallet,
        bool    active
    );
}

/// @title  VAPIDeviceBirthCertUpdateRegistry
/// @notice Path A companion OVERRIDE for the Manufacturer Root CA HSM migration (grok round-24). The
///         deployed VMDR is one-shot + immutable, so a device already registered under a software-signed
///         `birthCertHash` cannot be re-anchored to an HSM-re-signed cert in place. This contract records
///         an owner-vouched updated hash per device, and exposes `currentBirthCertHash` = OVERRIDE-then-VMDR
///         as the single effective-hash view verifiers must read.
///
///         Trust model: identity / eligibility stays on VMDR (pubkey, path, tier, active); only the
///         birth-cert INTEGRITY hash is overridable here. Writes are `onlyOwner` — the SAME Foundation
///         trust as `VMDR.registerDevice` — and require the device be active on VMDR. This adds a second
///         hash write path, NOT a new trust principal, NOT any gamer-side authority. The contract only ever
///         sees a bytes32; it cannot (and does not pretend to) verify the new hash corresponds to an
///         HSM-issued cert — that is the off-chain preflight + `verify_device_cert` ceremony's job.
contract VAPIDeviceBirthCertUpdateRegistry is Ownable {
    IVMDR public immutable vmdr;

    /// deviceId → owner-vouched updated birthCertHash (bytes32(0) = no override, fall back to VMDR).
    mapping(bytes32 => bytes32) public updatedBirthCertHash;
    /// deviceId → block.timestamp of the last override write.
    mapping(bytes32 => uint64) public updatedAt;

    event BirthCertHashUpdated(bytes32 indexed deviceId, bytes32 newHash, bytes32 previousEffectiveHash);
    event BirthCertHashCleared(bytes32 indexed deviceId, bytes32 previousHash);

    constructor(address vmdrAddress) Ownable(msg.sender) {
        require(vmdrAddress != address(0), "DBC-UPD: zero vmdr");
        vmdr = IVMDR(vmdrAddress);
    }

    /// @notice Re-anchor a device's birthCertHash to an HSM-re-signed cert. onlyOwner; device must be
    ///         active on VMDR; non-zero; no-op rejected.
    function setUpdatedBirthCertHash(bytes32 deviceId, bytes32 newHash) external onlyOwner {
        require(vmdr.isActive(deviceId), "DBC-UPD: not active on VMDR");
        require(newHash != bytes32(0), "DBC-UPD: zero hash");
        bytes32 prev = currentBirthCertHash(deviceId);
        require(newHash != prev, "DBC-UPD: noop");
        updatedBirthCertHash[deviceId] = newHash;
        updatedAt[deviceId] = uint64(block.timestamp);
        emit BirthCertHashUpdated(deviceId, newHash, prev);
    }

    /// @notice Roll back to VMDR's original hash. `clear` (not "set back to software hash") is the honest
    ///         rollback — it leaves no override residue falsely claiming an HSM-era hash.
    function clearOverride(bytes32 deviceId) external onlyOwner {
        bytes32 prev = updatedBirthCertHash[deviceId];
        require(prev != bytes32(0), "DBC-UPD: no override");
        delete updatedBirthCertHash[deviceId];
        delete updatedAt[deviceId];
        emit BirthCertHashCleared(deviceId, prev);
    }

    function hasOverride(bytes32 deviceId) external view returns (bool) {
        return updatedBirthCertHash[deviceId] != bytes32(0);
    }

    /// @notice THE effective-hash view — override if set, else VMDR's stored birthCertHash. Verifiers MUST
    ///         read this, never VMDR's raw hash alone, once this registry is wired.
    function currentBirthCertHash(bytes32 deviceId) public view returns (bytes32) {
        bytes32 o = updatedBirthCertHash[deviceId];
        if (o != bytes32(0)) {
            return o;
        }
        (, , , , , bytes32 h, , ) = vmdr.devices(deviceId);
        return h;
    }
}
