// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * @title VAPIDualPrimitiveGate — Phase 113
 * @notice Composable dual-primitive tournament eligibility gate.
 *
 *         Requires BOTH on-chain primitives for a player to be eligible:
 *           1. PoAC (Proof of Autonomous Cognition) — isFullyEligible() via VAPIProtocolLens
 *           2. PoAd (Proof of Adjudication)         — isRecorded() via AdjudicationRegistry
 *
 *         First on-chain dual-proof composability gate in any gaming protocol.
 *         Presupposes quorum-adjudicated physiological proof chain — exclusive to VAPI.
 *
 *         Phase 113 — VAPI Verified Autonomous Physical Intelligence (AGaaS/DePIN on IoTeX).
 *         Inter-person separation ratio: 0.362 — TOURNAMENT BLOCKER (§8.6, non-negotiable).
 */

interface IVAPIProtocolLens {
    function isFullyEligible(bytes32 deviceIdHash) external view returns (bool);
}

interface IAdjudicationRegistry {
    function isRecorded(bytes32 poadHash) external view returns (bool);
}

contract VAPIDualPrimitiveGate {

    IVAPIProtocolLens    public immutable protocolLens;
    IAdjudicationRegistry public immutable adjudicationRegistry;

    constructor(address _protocolLens, address _adjudicationRegistry) {
        require(
            _protocolLens != address(0),
            "VAPIDualPrimitiveGate: zero protocolLens"
        );
        require(
            _adjudicationRegistry != address(0),
            "VAPIDualPrimitiveGate: zero adjudicationRegistry"
        );
        protocolLens         = IVAPIProtocolLens(_protocolLens);
        adjudicationRegistry = IAdjudicationRegistry(_adjudicationRegistry);
    }

    /**
     * @notice Check dual-primitive tournament eligibility for a device+adjudication pair.
     *
     * @param deviceIdHash  bytes32 — sha256(device_id.encode()) matching bridge convention
     *                      (Phase 112 record_adjudication uses same derivation)
     * @param poadHash      bytes32 — SHA-256(sorted verdict bundle, sort_keys=True) from Phase 111
     *                      stored in poad_registry_log.poad_hash
     *
     * @return eligible     true ONLY when both poac_valid AND poad_valid
     * @return poac_valid   true when VAPIProtocolLens.isFullyEligible(deviceIdHash) returns true
     * @return poad_valid   true when AdjudicationRegistry.isRecorded(poadHash) returns true
     *
     * @dev Pure view — no state changes. Game developer entry point:
     *      (eligible,,) = gate.isDualEligible(deviceIdHash, poadHash);
     */
    function isDualEligible(
        bytes32 deviceIdHash,
        bytes32 poadHash
    ) external view returns (bool eligible, bool poac_valid, bool poad_valid) {
        poac_valid = protocolLens.isFullyEligible(deviceIdHash);
        poad_valid = adjudicationRegistry.isRecorded(poadHash);
        eligible   = poac_valid && poad_valid;
    }
}
