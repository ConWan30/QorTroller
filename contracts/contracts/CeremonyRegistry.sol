// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * @title CeremonyRegistry — Phase 67 VAPI MPC Ceremony Audit Trail
 * @notice Stores verifying key hashes, MPC contributor transcripts, and the
 *         IoTeX-block beacon for each VAPI ZK circuit. Enables any party to
 *         independently verify that a given proof uses an MPC-derived key
 *         bound to an on-chain beacon — no external trust source required.
 *
 * Novel primitive: the beacon finalizing each circuit's Phase 2 zkey is the
 * hash of a specific IoTeX testnet block. This anchors ceremony integrity to
 * the same chain where all VAPI contracts are deployed — independently verifiable
 * by querying block N on IoTeX testnet.
 *
 * circuitId = keccak256(abi.encodePacked(circuitName))
 *   e.g. keccak256("PitlSessionProof"), keccak256("TeamProof"), keccak256("TournamentPassport")
 *
 * verifyingKeyHash = keccak256(vkey_json_bytes) — deterministic, matches bridge ZKVerifier
 * contributorHashes[i] = sha256(zkey_after_contribution_i) — auditable MPC transcript
 *
 * Anti-replay: each circuitId may be registered at most once.
 * Minimum 2 contributors enforced on-chain.
 */
contract CeremonyRegistry {

    struct CircuitCeremony {
        bytes32   verifyingKeyHash;    // keccak256(vkey_json_bytes)
        bytes32   beaconBlockHash;     // IoTeX testnet block hash used as final entropy beacon
        uint64    beaconBlockNumber;   // IoTeX testnet block number (queryable by anyone)
        uint8     contributorCount;    // number of MPC Phase 2 contributors
        bytes32[] contributorHashes;  // sha256(zkey) after each MPC contribution round
        string    ptauSource;          // e.g. "hermez-hez_final_15-2021"
        uint64    timestamp;           // unix seconds ceremony completed
        address   registeredBy;        // operator wallet
    }

    /// circuitId => CircuitCeremony (one entry per circuit, immutable after registration)
    mapping(bytes32 => CircuitCeremony) private _ceremonies;

    address public operator;

    event CeremonyRegistered(
        bytes32 indexed circuitId,
        bytes32         verifyingKeyHash,
        bytes32         beaconBlockHash,
        uint64          beaconBlockNumber,
        uint8           contributorCount
    );

    event OperatorTransferred(address indexed oldOperator, address indexed newOperator);

    modifier onlyOperator() {
        require(msg.sender == operator, "CeremonyRegistry: unauthorized");
        _;
    }

    constructor(address _operator) {
        require(_operator != address(0), "CeremonyRegistry: zero operator");
        operator = _operator;
    }

    /**
     * @notice Register the MPC ceremony result for a VAPI ZK circuit.
     * @param circuitId          keccak256(circuitName) — unique per circuit
     * @param verifyingKeyHash   keccak256(vkey_json_bytes) from snarkjs export
     * @param beaconBlockHash    IoTeX testnet block hash used as final Phase 2 beacon
     * @param beaconBlockNumber  IoTeX testnet block number of the beacon
     * @param contributorHashes  sha256(zkey) after each MPC contribution (min 2)
     * @param ptauSource         Human-readable Phase 1 ptau provenance string
     */
    function registerCeremony(
        bytes32          circuitId,
        bytes32          verifyingKeyHash,
        bytes32          beaconBlockHash,
        uint64           beaconBlockNumber,
        bytes32[] calldata contributorHashes,
        string calldata  ptauSource
    ) external onlyOperator {
        require(
            contributorHashes.length >= 2,
            "CeremonyRegistry: minimum 2 contributors required"
        );
        require(
            _ceremonies[circuitId].timestamp == 0,
            "CeremonyRegistry: circuit already registered"
        );
        _ceremonies[circuitId] = CircuitCeremony({
            verifyingKeyHash:  verifyingKeyHash,
            beaconBlockHash:   beaconBlockHash,
            beaconBlockNumber: beaconBlockNumber,
            contributorCount:  uint8(contributorHashes.length),
            contributorHashes: contributorHashes,
            ptauSource:        ptauSource,
            timestamp:         uint64(block.timestamp),
            registeredBy:      msg.sender
        });
        emit CeremonyRegistered(
            circuitId,
            verifyingKeyHash,
            beaconBlockHash,
            beaconBlockNumber,
            uint8(contributorHashes.length)
        );
    }

    /**
     * @notice Verify that the claimed vkey hash matches the registered ceremony.
     * @param circuitId        keccak256(circuitName)
     * @param claimedVkeyHash  keccak256(local_vkey_json_bytes) to check against registry
     * @return True if the circuit has a registered ceremony and the key matches.
     */
    function verifyCeremony(bytes32 circuitId, bytes32 claimedVkeyHash)
        external view returns (bool)
    {
        CircuitCeremony storage c = _ceremonies[circuitId];
        return c.timestamp > 0 && c.verifyingKeyHash == claimedVkeyHash;
    }

    /**
     * @notice Return the header fields for a registered circuit ceremony.
     */
    function getCeremony(bytes32 circuitId)
        external view returns (
            bytes32 verifyingKeyHash,
            bytes32 beaconBlockHash,
            uint64  beaconBlockNumber,
            uint8   contributorCount,
            string memory ptauSource,
            uint64  timestamp,
            address registeredBy
        )
    {
        CircuitCeremony storage c = _ceremonies[circuitId];
        return (
            c.verifyingKeyHash,
            c.beaconBlockHash,
            c.beaconBlockNumber,
            c.contributorCount,
            c.ptauSource,
            c.timestamp,
            c.registeredBy
        );
    }

    /**
     * @notice Return the contributor transcript hashes for a circuit.
     */
    function getContributorHashes(bytes32 circuitId)
        external view returns (bytes32[] memory)
    {
        return _ceremonies[circuitId].contributorHashes;
    }

    /**
     * @notice Get the number of MPC contributors for a circuit.
     */
    function getContributorCount(bytes32 circuitId) external view returns (uint8) {
        return _ceremonies[circuitId].contributorCount;
    }

    /**
     * @notice Transfer the operator role.
     */
    function setOperator(address _operator) external onlyOperator {
        require(_operator != address(0), "CeremonyRegistry: zero operator");
        emit OperatorTransferred(operator, _operator);
        operator = _operator;
    }
}
