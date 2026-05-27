// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * @title VAPIProtocolLensV2 — Path A Arc 1 Commit 4
 * @notice Zero-state pure-view contract that composes 4 Phase 69 oracles +
 *         VAPIManufacturerDeviceRegistry (Path A Arc 1 Commit 2) into single
 *         eth_calls for tournament integrations.
 *
 * v2 vs v1 — strictly additive:
 *   • Constructor takes a 5th arg: VAPIManufacturerDeviceRegistry address.
 *   • Adds isFullyEligible_PathA(bytes32) — single boolean: protocol-fully-
 *     eligible AND manufacturer-attested-as-Path-A AND active in MFG registry.
 *   • Adds getDeviceTier(bytes32) — uint8 from MFG registry (1=FULL,
 *     2=STANDARD, 3=BASIC, 0=not registered).
 *   • isFullyEligible(bytes32) unchanged byte-for-byte from v1 — tournament
 *     integrators that called v1 see identical behavior here.
 *
 * Path A v1 scope: silicon-rooted iPACT renewal authenticity. Per-PoAC record
 * silicon-root is reserved for Path A v2 (Arc 3+).
 *
 * v1 contract (0x1972bf756aFE0FFCfaF9842e2FbBb2B084352EAf, Phase 70) stays
 * callable post-v2 deploy — EVM bytecode is immutable. Replace-posture
 * matches the SeparationRatioRegistry redeploy precedent (2026-05-24).
 *
 * Security:
 *   - Zero storage — no state can be corrupted.
 *   - All oracle / registry calls wrapped in try/catch — failure returns safe
 *     defaults rather than reverting the whole call.
 *   - Oracle + registry addresses are immutable after construction.
 */

interface IHumanityOracle {
    function isNominal(bytes32 deviceId) external view returns (bool);
    function getHumanityPct(bytes32 deviceId) external view returns (uint16);
    function getHumanityVerdict(bytes32 deviceId) external view returns (
        uint8  inferenceCode,
        uint16 humanityPct,
        uint32 l4DistanceX1000,
        uint32 l5CvX1000,
        uint32 lastUpdateBlock,
        uint64 lastUpdateTime
    );
}

interface IRulingOracle {
    function isSuspended(bytes32 deviceId) external view returns (bool);
    function isEligible(bytes32 deviceId) external view returns (bool);
    function getRulingState(bytes32 deviceId) external view returns (
        bool    suspended,
        uint32  flagStreak,
        uint32  holdStreak,
        uint32  lastUpdateBlock,
        uint64  suspendedUntil,
        bytes32 lastCommitmentHash
    );
}

interface IPassportOracle {
    function hasVerifiedPassport(bytes32 deviceId) external view returns (bool);
    function getPassportState(bytes32 deviceId) external view returns (
        bool    issued,
        bool    onChain,
        bytes32 passportHash,
        uint32  sessionCount,
        uint32  lastUpdateBlock,
        uint64  issuedAt
    );
}

interface IVAPIRewardDistributor {
    function getRewardBreakdown(bytes32 deviceId) external view returns (
        uint256 totalSessions,
        uint256 accPoints,
        uint256 claimableTokens,
        uint256 multiplierX100,
        uint32  cleanStreak
    );
}

/// @notice Read surface that VAPIProtocolLensV2 needs from VAPIManufacturerDeviceRegistry.
///         Minimum surface — register/revoke remain owner-only on the registry itself.
interface IVAPIManufacturerDeviceRegistry {
    function isPathA(bytes32 deviceId) external view returns (bool);
    function isActive(bytes32 deviceId) external view returns (bool);
    function getProofTier(bytes32 deviceId) external view returns (uint8);
}

contract VAPIProtocolLensV2 {

    // -----------------------------------------------------------------------
    // Immutable addresses (set in constructor, never changed)
    // -----------------------------------------------------------------------

    IHumanityOracle                   public immutable humanityOracle;
    IRulingOracle                     public immutable rulingOracle;
    IPassportOracle                   public immutable passportOracle;
    IVAPIRewardDistributor            public immutable rewardDistributor;
    IVAPIManufacturerDeviceRegistry   public immutable manufacturerDeviceRegistry;

    constructor(
        address _humanityOracle,
        address _rulingOracle,
        address _passportOracle,
        address _rewardDistributor,
        address _manufacturerDeviceRegistry
    ) {
        require(_humanityOracle             != address(0), "VPLv2: zero humanityOracle");
        require(_rulingOracle               != address(0), "VPLv2: zero rulingOracle");
        require(_passportOracle             != address(0), "VPLv2: zero passportOracle");
        require(_rewardDistributor          != address(0), "VPLv2: zero rewardDistributor");
        require(_manufacturerDeviceRegistry != address(0), "VPLv2: zero manufacturerDeviceRegistry");

        humanityOracle             = IHumanityOracle(_humanityOracle);
        rulingOracle               = IRulingOracle(_rulingOracle);
        passportOracle             = IPassportOracle(_passportOracle);
        rewardDistributor          = IVAPIRewardDistributor(_rewardDistributor);
        manufacturerDeviceRegistry = IVAPIManufacturerDeviceRegistry(_manufacturerDeviceRegistry);
    }

    // -----------------------------------------------------------------------
    // Convenience gates (single-boolean — for tournament integrations)
    // -----------------------------------------------------------------------

    /**
     * @notice Single-boolean tournament gate.
     *         Returns true iff: isNominal AND isEligible AND passportOnChain.
     *         Byte-for-byte equivalent to v1's isFullyEligible.
     */
    function isFullyEligible(bytes32 deviceId) public view returns (bool eligible) {
        bool nom  = false;
        bool elig = false; // M-1 fix: fail-closed default
        bool vp   = false;

        try humanityOracle.isNominal(deviceId)            returns (bool n) { nom  = n; } catch {}
        try rulingOracle.isEligible(deviceId)             returns (bool e) { elig = e; } catch {}
        try passportOracle.hasVerifiedPassport(deviceId)  returns (bool p) { vp   = p; } catch {}

        return nom && elig && vp;
    }

    /**
     * @notice Path A composable gate. Returns true iff:
     *           isFullyEligible(deviceId)
     *           AND manufacturerDeviceRegistry.isPathA(deviceId)
     *           AND manufacturerDeviceRegistry.isActive(deviceId)
     *
     *         All three conditions are gated through try/catch so a registry
     *         outage degrades gracefully (returns false, never reverts).
     *
     *         Path A v1 scope: this proves the device's iPACT renewal authority
     *         is silicon-rooted via VAPIManufacturerDeviceRegistry's attestation.
     *         It does NOT yet prove per-PoAC record silicon-rooting (Path A v2,
     *         Arc 3+).
     */
    function isFullyEligible_PathA(bytes32 deviceId) external view returns (bool) {
        if (!isFullyEligible(deviceId)) return false;
        bool isA = false;
        bool act = false;
        try manufacturerDeviceRegistry.isPathA(deviceId)  returns (bool a) { isA = a; } catch {}
        try manufacturerDeviceRegistry.isActive(deviceId) returns (bool b) { act = b; } catch {}
        return isA && act;
    }

    /**
     * @notice Pass-through to manufacturerDeviceRegistry.getProofTier(deviceId).
     *         Returns 0 if device not registered OR registry outage. 1/2/3 per
     *         the FROZEN PROOF_TIER_FULL/STANDARD/BASIC enum (pinned by
     *         INV-MFG-002 in scripts/vapi_invariant_gate.py).
     */
    function getDeviceTier(bytes32 deviceId) external view returns (uint8) {
        try manufacturerDeviceRegistry.getProofTier(deviceId) returns (uint8 t) { return t; } catch {}
        return 0;
    }
}
