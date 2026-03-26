// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * @title VAPIProtocolLens — Phase 70 Unified Protocol State View
 * @notice Zero-state pure-view contract that synthesizes HumanityOracle,
 *         RulingOracle, PassportOracle, and VAPIRewardDistributor into a
 *         single eth_call returning DeviceProtocolState.
 *
 * Use case: tournament integrations and third-party contracts that need to
 * gate on VAPI device status without making 5 separate eth_calls and
 * handling 5 independent failure modes.
 *
 * isFullyEligible(deviceId) — single gate function:
 *   True iff: isNominal && isEligible (not suspended) && passportOnChain
 *
 * Security:
 *   - Zero storage — no state can be corrupted.
 *   - All oracle calls wrapped in try/catch — oracle failure returns safe
 *     defaults (false/0) rather than reverting the whole call.
 *   - Oracle addresses are immutable after construction.
 *   - Does NOT expose raw biometric feature vectors — only scalars and booleans.
 *
 * PHGCredential is not referenced here (immutable bridge address, Phase 68).
 * Separation ratio 0.362 caveat: device-gated only (§8.6).
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

contract VAPIProtocolLens {

    // -----------------------------------------------------------------------
    // Types
    // -----------------------------------------------------------------------

    struct DeviceProtocolState {
        // Humanity (HumanityOracle)
        uint8   inferenceCode;         // PITL inference code (0x20 = NOMINAL)
        uint16  humanityPct;           // 0–1000 scaled ×10
        bool    isNominal;             // inferenceCode == 0x20

        // Ruling (RulingOracle)
        bool    suspended;
        uint32  flagStreak;
        bool    isEligible;            // not suspended AND streak clean

        // Passport (PassportOracle)
        bool    passportIssued;
        bool    passportOnChain;       // ZK proof verified on-chain
        uint32  passportSessionCount;

        // Reward (VAPIRewardDistributor)
        uint256 totalSessions;
        uint256 accPoints;
        uint32  multiplierX100;        // combined multiplier ×100 (100 = 1.0×)

        // Composite gate
        bool    fullyEligible;         // isNominal && isEligible && passportOnChain
        bool    oracleAvailable;       // false when RulingOracle call fails (fail-closed flag)
        uint256 snapshotBlock;
    }

    // -----------------------------------------------------------------------
    // Immutable oracle addresses (set in constructor, never changed)
    // -----------------------------------------------------------------------

    IHumanityOracle       public immutable humanityOracle;
    IRulingOracle         public immutable rulingOracle;
    IPassportOracle       public immutable passportOracle;
    IVAPIRewardDistributor public immutable rewardDistributor;

    // -----------------------------------------------------------------------
    // Constructor
    // -----------------------------------------------------------------------

    constructor(
        address _humanityOracle,
        address _rulingOracle,
        address _passportOracle,
        address _rewardDistributor
    ) {
        require(_humanityOracle    != address(0), "VAPIProtocolLens: zero humanityOracle");
        require(_rulingOracle      != address(0), "VAPIProtocolLens: zero rulingOracle");
        require(_passportOracle    != address(0), "VAPIProtocolLens: zero passportOracle");
        require(_rewardDistributor != address(0), "VAPIProtocolLens: zero rewardDistributor");

        humanityOracle    = IHumanityOracle(_humanityOracle);
        rulingOracle      = IRulingOracle(_rulingOracle);
        passportOracle    = IPassportOracle(_passportOracle);
        rewardDistributor = IVAPIRewardDistributor(_rewardDistributor);
    }

    // -----------------------------------------------------------------------
    // Primary view — synthesises all four oracles in one call
    // -----------------------------------------------------------------------

    /**
     * @notice Get the complete protocol state for a device in one eth_call.
     *
     * All oracle calls are wrapped in try/catch. If an oracle is unreachable or
     * not yet initialized for this device, the corresponding fields return
     * safe zero-values (false, 0) rather than reverting.
     *
     * @param  deviceId  keccak256(pubkey) padded to bytes32
     * @return state     DeviceProtocolState struct with all protocol dimensions
     */
    function getDeviceState(bytes32 deviceId)
        external
        view
        returns (DeviceProtocolState memory state)
    {
        state.snapshotBlock = block.number;

        // --- HumanityOracle ---
        try humanityOracle.isNominal(deviceId) returns (bool nom) {
            state.isNominal = nom;
        } catch { state.isNominal = false; }

        try humanityOracle.getHumanityPct(deviceId) returns (uint16 pct) {
            state.humanityPct = pct;
        } catch { state.humanityPct = 0; }

        // inferenceCode from verdict struct
        try humanityOracle.getHumanityVerdict(deviceId) returns (
            uint8 ic, uint16, uint32, uint32, uint32, uint64
        ) {
            state.inferenceCode = ic;
        } catch { state.inferenceCode = 0; }

        // --- RulingOracle ---
        try rulingOracle.isSuspended(deviceId) returns (bool susp) {
            state.suspended = susp;
        } catch { state.suspended = false; }

        try rulingOracle.isEligible(deviceId) returns (bool elig) {
            state.oracleAvailable = true;
            state.isEligible = elig;
        } catch {
            // M-1 fix: fail-closed — a suspended device must not pass eligibility gate
            // during oracle downtime. oracleAvailable=false lets callers distinguish
            // "not eligible" from "oracle unavailable".
            state.isEligible = false;
            state.oracleAvailable = false;
        }

        try rulingOracle.getRulingState(deviceId) returns (
            bool, uint32 flagStr, uint32, uint32, uint64, bytes32
        ) {
            state.flagStreak = flagStr;
        } catch { state.flagStreak = 0; }

        // --- PassportOracle ---
        try passportOracle.hasVerifiedPassport(deviceId) returns (bool vp) {
            state.passportOnChain = vp;
        } catch { state.passportOnChain = false; }

        try passportOracle.getPassportState(deviceId) returns (
            bool issued, bool, bytes32, uint32 sessionCount, uint32, uint64
        ) {
            state.passportIssued        = issued;
            state.passportSessionCount  = sessionCount;
        } catch {
            state.passportIssued       = false;
            state.passportSessionCount = 0;
        }

        // --- VAPIRewardDistributor ---
        try rewardDistributor.getRewardBreakdown(deviceId) returns (
            uint256 totalSess, uint256 accPts, uint256, uint256 multX100, uint32
        ) {
            state.totalSessions  = totalSess;
            state.accPoints      = accPts;
            state.multiplierX100 = uint32(multX100 > type(uint32).max ? type(uint32).max : multX100);
        } catch {
            state.totalSessions  = 0;
            state.accPoints      = 0;
            state.multiplierX100 = 100; // 1.0× default
        }

        // --- Composite gate ---
        state.fullyEligible = state.isNominal && state.isEligible && state.passportOnChain;
    }

    // -----------------------------------------------------------------------
    // Convenience gate — single boolean for tournament contracts
    // -----------------------------------------------------------------------

    /**
     * @notice Single-boolean tournament gate.
     *         Returns true iff: isNominal AND isEligible AND passportOnChain.
     *
     * Tournament integrations should call this instead of getDeviceState()
     * when only a pass/fail decision is needed (lower gas).
     *
     * @param  deviceId  keccak256(pubkey) padded to bytes32
     * @return eligible  True if device passes all VAPI protocol gates
     */
    function isFullyEligible(bytes32 deviceId) external view returns (bool eligible) {
        bool nom  = false;
        bool elig = false; // M-1 fix: fail-closed default — oracle down → ineligible
        bool vp   = false;

        try humanityOracle.isNominal(deviceId) returns (bool n) { nom  = n; } catch {}
        try rulingOracle.isEligible(deviceId)  returns (bool e) { elig = e; } catch {}
        try passportOracle.hasVerifiedPassport(deviceId) returns (bool p) { vp = p; } catch {}

        return nom && elig && vp;
    }
}
