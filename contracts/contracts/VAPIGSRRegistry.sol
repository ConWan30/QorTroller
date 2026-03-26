// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/access/Ownable.sol";

/**
 * @title VAPIGSRRegistry — Phase 99B Galvanic Skin Response On-Chain Registry
 * @notice Tamper-evident on-chain record of physiological biometric samples
 *         from GSR-equipped gaming peripherals.
 *
 * Anti-replay: each (deviceId, timestamp) pair may be recorded at most once.
 * Only the bridge operator (onlyOwner) may write samples.
 *
 * Encoding convention (avoids float storage):
 *   arousalMillis     = sympathetic_arousal_index * 1000   (0–1000, uint)
 *   correlationMillis = (gsr_game_event_correlation + 1.0) * 500
 *                       so: -1.0 → 0, 0.0 → 500, +1.0 → 1000 (uint)
 *
 * Status: GSR_ENABLED=false in bridge — advisory layer only, never hard gate.
 * Code-before-hardware pattern: precedent from L6b (Phase 63), ClassJDetector (Phase 81).
 *
 * W3bstream integration: process_gsr_packet.ts WASM applet calls recordSample()
 * after parsing and validating the GSR packet from the physical grip.
 *
 * Inference code: 0x33 GSR_CORRELATION_ABSENT — ADVISORY ONLY.
 * Hardware required for live L7 calibration: N≥30 sessions per player.
 */
contract VAPIGSRRegistry is Ownable {

    struct GSRSample {
        uint256 arousalMillis;     // sympathetic_arousal_index * 1000
        uint256 correlationMillis; // (correlation + 1.0) * 500, range 0–1000
        uint256 recordedAt;        // block.timestamp at recording
        bool exists;               // anti-replay guard
    }

    // deviceId (bytes32) → timestamp (uint256) → sample
    mapping(bytes32 => mapping(uint256 => GSRSample)) public samples;
    mapping(bytes32 => uint256) public sampleCounts;
    mapping(bytes32 => uint256) public latestTimestamp;

    event GSRSampleRecorded(
        bytes32 indexed deviceId,
        uint256 arousalMillis,
        uint256 correlationMillis,
        uint256 timestamp
    );

    constructor(address initialOwner) Ownable(initialOwner) {}

    /**
     * @notice Record a GSR sample for a device. Reverts on duplicate timestamp.
     * @param deviceId         keccak256(device_id string) from bridge
     * @param arousalMillis    sympathetic_arousal_index * 1000
     * @param correlationMillis (correlation + 1.0) * 500
     * @param timestamp        Unix seconds from gsr_sample.timestamp
     */
    function recordSample(
        bytes32 deviceId,
        uint256 arousalMillis,
        uint256 correlationMillis,
        uint256 timestamp
    ) external onlyOwner {
        require(deviceId != bytes32(0), "VAPIGSRRegistry: zero deviceId");
        require(
            !samples[deviceId][timestamp].exists,
            "VAPIGSRRegistry: duplicate timestamp"
        );

        samples[deviceId][timestamp] = GSRSample({
            arousalMillis: arousalMillis,
            correlationMillis: correlationMillis,
            recordedAt: block.timestamp,
            exists: true
        });
        sampleCounts[deviceId]++;
        latestTimestamp[deviceId] = timestamp;

        emit GSRSampleRecorded(deviceId, arousalMillis, correlationMillis, timestamp);
    }

    /**
     * @notice Retrieve the most recent sample for a device.
     * @dev Reverts if no samples recorded for this deviceId.
     */
    function getLatestSample(bytes32 deviceId)
        external
        view
        returns (uint256 arousal, uint256 correlation, uint256 ts)
    {
        uint256 lt = latestTimestamp[deviceId];
        require(lt > 0, "VAPIGSRRegistry: no samples for device");
        GSRSample memory s = samples[deviceId][lt];
        return (s.arousalMillis, s.correlationMillis, s.recordedAt);
    }

    /**
     * @notice Total samples recorded for a device.
     */
    function getSampleCount(bytes32 deviceId) external view returns (uint256) {
        return sampleCounts[deviceId];
    }
}
