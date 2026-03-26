// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/access/Ownable.sol";

/// @dev Minimal token interface for certification fee payment
interface IVAPIHardwareToken {
    function transferFrom(address from, address to, uint256 amount) external returns (bool);
}

/**
 * @title VAPIHardwareCertRegistry — Phase 99A Hardware Certification Registry
 * @notice Trustless on-chain certification of physical gaming peripherals.
 *
 * Hardware profiles are keyed by a bytes32 profileHash, typically:
 *   profileHash = keccak256(abi.encodePacked(manufacturer, model, firmwareVersion))
 *
 * Certification levels:
 *   1 = Controller only (DualShock Edge class)
 *   2 = Controller + GSR grip (biometric peripheral)
 *
 * DePIN composability:
 *   isCertified(profileHash) is a pure view call — no gas cost to integrators.
 *   Tournament contracts can gate hardware with a single require():
 *     require(certRegistry.isCertified(grip.profileHash), "hardware not certified")
 *   This is the first hardware-level DePIN composability primitive in competitive gaming.
 *
 * Fee model:
 *   certificationFee in VAPI tokens, sent to owner() (VAPI treasury).
 *   Set to 0 for free certification during testnet phase.
 *   Adjusted via setCertificationFee() by owner.
 */
contract VAPIHardwareCertRegistry is Ownable {

    struct HardwareProfile {
        uint8 certLevel;          // 1=controller, 2=controller+GSR
        string manufacturer;
        string model;
        string firmwareVersion;
        address certifiedBy;      // address that called certifyHardware()
        uint256 certifiedAt;      // block.timestamp of certification
        bool active;              // false after revocation
    }

    IVAPIHardwareToken public immutable vapiToken;
    uint256 public certificationFee;             // in VAPI tokens (18 decimals)

    mapping(bytes32 => HardwareProfile) public profiles;
    bytes32[] public profileHashes;              // enumeration support

    event HardwareCertified(
        bytes32 indexed profileHash,
        uint8 certLevel,
        string manufacturer,
        string model,
        uint256 timestamp
    );
    event CertificationRevoked(bytes32 indexed profileHash);
    event CertificationFeeUpdated(uint256 oldFee, uint256 newFee);

    constructor(address tokenAddress, address initialOwner, uint256 _certificationFee)
        Ownable(initialOwner)
    {
        require(tokenAddress != address(0), "VAPIHardwareCertRegistry: zero token address");
        vapiToken = IVAPIHardwareToken(tokenAddress);
        certificationFee = _certificationFee;
    }

    /**
     * @notice Certify a hardware profile on-chain.
     * @param profileHash  keccak256(manufacturer ++ model ++ firmwareVersion)
     * @param certLevel    1=controller, 2=controller+GSR
     * @param manufacturer e.g. "Sony"
     * @param model        e.g. "DualShock Edge CFI-ZCP1"
     * @param firmwareVersion e.g. "01.04.00"
     */
    function certifyHardware(
        bytes32 profileHash,
        uint8 certLevel,
        string calldata manufacturer,
        string calldata model,
        string calldata firmwareVersion
    ) external {
        require(
            certLevel >= 1 && certLevel <= 2,
            "VAPIHardwareCertRegistry: invalid certLevel (1 or 2)"
        );
        require(profileHash != bytes32(0), "VAPIHardwareCertRegistry: zero profileHash");
        require(
            !profiles[profileHash].active,
            "VAPIHardwareCertRegistry: profile already certified"
        );

        // Collect certification fee if non-zero
        if (certificationFee > 0) {
            vapiToken.transferFrom(msg.sender, owner(), certificationFee);
        }

        profiles[profileHash] = HardwareProfile({
            certLevel: certLevel,
            manufacturer: manufacturer,
            model: model,
            firmwareVersion: firmwareVersion,
            certifiedBy: msg.sender,
            certifiedAt: block.timestamp,
            active: true
        });
        profileHashes.push(profileHash);

        emit HardwareCertified(
            profileHash,
            certLevel,
            manufacturer,
            model,
            block.timestamp
        );
    }

    /**
     * @notice Returns true if the profile is currently certified (not revoked).
     * @dev Pure view — zero gas cost to integrators. Composable as tournament gate.
     */
    function isCertified(bytes32 profileHash) external view returns (bool) {
        return profiles[profileHash].active;
    }

    /**
     * @notice Revoke a hardware certification (e.g. firmware vulnerability discovered).
     */
    function revokeCertification(bytes32 profileHash) external onlyOwner {
        require(
            profiles[profileHash].active,
            "VAPIHardwareCertRegistry: profile not active"
        );
        profiles[profileHash].active = false;
        emit CertificationRevoked(profileHash);
    }

    /**
     * @notice Update the VAPI token fee for new certifications.
     */
    function setCertificationFee(uint256 newFee) external onlyOwner {
        emit CertificationFeeUpdated(certificationFee, newFee);
        certificationFee = newFee;
    }

    /**
     * @notice Total number of profiles ever registered (including revoked).
     */
    function profileCount() external view returns (uint256) {
        return profileHashes.length;
    }
}
