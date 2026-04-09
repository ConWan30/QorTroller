// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;
import "@openzeppelin/contracts/access/Ownable.sol";
import "@openzeppelin/contracts/utils/ReentrancyGuard.sol";

/// @title CeremonyAuditRegistry — Phase 179 ZK Ceremony Multi-Party Audit Gate
/// @notice Tracks Groth16 MPC trusted-setup ceremony participants per ZK circuit.
///         Enforces minimum multi-party participation for tournament authorization.
///         Prevents single-operator ceremony abuse (WIF-030 W1):
///           single operator knows toxic waste (τ, α, β) → can forge ZK proofs undetected.
///         Each ceremony participant contributes randomness; any honest participant
///         ensures the toxic waste is unknown to all other parties.
///
///         Anti-replay: UNIQUE(ceremonyId, participantAddress, circuitName).
///         Tournament authorizaiton gate: getParticipantCount(circuitName) >= min (e.g. 3).
///
///         Pattern: follows CeremonyRegistry.sol (Phase 67) — Ownable, emit event.
contract CeremonyAuditRegistry is Ownable, ReentrancyGuard {

    struct CeremonyParticipant {
        bytes32 ceremonyId;           // Ceremony identifier (keccak256 of ceremony name+date)
        bytes32 circuitName;          // ZK circuit name (keccak256 of string)
        address participantAddress;   // Participant Ethereum-compatible address
        bytes32 contributionHash;     // SHA-256 hash of participant's contribution transcript
        uint256 registeredAt;         // block.timestamp
    }

    // circuitName => list of participants
    mapping(bytes32 => CeremonyParticipant[]) private _participantsByCircuit;

    // Anti-replay: (ceremonyId, participantAddress, circuitName) => registered
    mapping(bytes32 => bool) private _registered;

    // Total participants across all circuits
    uint256 public totalParticipants;

    event ParticipantRegistered(
        bytes32 indexed circuitName,
        address indexed participantAddress,
        bytes32 ceremonyId,
        bytes32 contributionHash,
        uint256 blockNumber
    );

    constructor(address initialOwner) Ownable(initialOwner) {}

    /// @notice Register a ceremony participant for a ZK circuit.
    ///         Reverts on duplicate (ceremonyId, participantAddress, circuitName).
    ///         Reverts on zero-address participantAddress.
    function registerParticipant(
        bytes32 ceremonyId,
        bytes32 circuitName,
        address participantAddress,
        bytes32 contributionHash
    ) external onlyOwner nonReentrant {
        require(
            participantAddress != address(0),
            "CeremonyAuditRegistry: zero participantAddress"
        );
        bytes32 key = keccak256(abi.encodePacked(ceremonyId, participantAddress, circuitName));
        require(!_registered[key], "CeremonyAuditRegistry: duplicate participant");
        _registered[key] = true;
        _participantsByCircuit[circuitName].push(CeremonyParticipant({
            ceremonyId:          ceremonyId,
            circuitName:         circuitName,
            participantAddress:  participantAddress,
            contributionHash:    contributionHash,
            registeredAt:        block.timestamp
        }));
        totalParticipants++;
        emit ParticipantRegistered(
            circuitName,
            participantAddress,
            ceremonyId,
            contributionHash,
            block.number
        );
    }

    /// @notice Return the count of registered participants for a ZK circuit.
    ///         Used by tournament authorization gate: require count >= minParticipants.
    function getParticipantCount(bytes32 circuitName) external view returns (uint256) {
        return _participantsByCircuit[circuitName].length;
    }

    /// @notice Return a specific participant entry for a circuit by index.
    function getParticipant(
        bytes32 circuitName,
        uint256 index
    ) external view returns (CeremonyParticipant memory) {
        require(
            index < _participantsByCircuit[circuitName].length,
            "CeremonyAuditRegistry: index out of range"
        );
        return _participantsByCircuit[circuitName][index];
    }

    /// @notice Check whether a (ceremonyId, participantAddress, circuitName) triple is registered.
    function isRegistered(
        bytes32 ceremonyId,
        bytes32 circuitName,
        address participantAddress
    ) external view returns (bool) {
        bytes32 key = keccak256(abi.encodePacked(ceremonyId, participantAddress, circuitName));
        return _registered[key];
    }
}
