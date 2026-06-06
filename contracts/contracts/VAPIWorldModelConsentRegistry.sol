// SPDX-License-Identifier: UNLICENSED
pragma solidity ^0.8.20;

/// @title VAPIWorldModelConsentRegistry
/// @author QorTroller (V.A.P.I. reference implementation)
/// @notice Minimal greenfield registry for per-gamer world-model export
///         consent. The W1-D operator decision (2026-06-05) ships this
///         as a flagged Phase-2 promote — Solidity + hardhat test live in
///         the repo, but the contract is NOT deployed on testnet in v1.
///         Deploy is gated on `VAPI_WMC_DEPLOY_CONFIRM=1` plus
///         operator-fired hardhat broadcast.
///
/// @dev    Greenfield design rationale (vs. extending Arc 4 Dimension 9):
///         the Arc 4 `VAPIConsentManifestRegistry` is already deployed
///         and its struct layout is frozen by Solidity storage rules.
///         Inserting a Dimension 9 field would require an Arc 4 v2
///         redeploy plus a per-gamer migration write. This contract
///         sidesteps both problems by being a separate, single-purpose
///         `(gamer => bool)` mapping.
///
///         Sovereignty invariant (load-bearing): `setWorldModelConsent`
///         is gated by `msg.sender == gamer` — only the gamer can grant
///         or revoke their own world-model export consent. The bridge
///         is structurally incapable of writing on a gamer's behalf.
///         Mirrors the same `msg.sender == gamer` pattern used by
///         `VAPIConsentRegistry.grantConsent` (Phase 237) and
///         `VAPIConsentManifestRegistry.setManifest` (Arc 4).
///
///         Distinct from replay consent. A gamer can grant replay-proof
///         export consent (Arc 4 Dimension 8 `allowReplayProofs=true`)
///         while withholding world-model export consent here — granular
///         sovereignty across distinct buyer / use-case classes.
///
/// @dev    Honesty rails preserved:
///         • No new FROZEN-v1 commitment family. This is consent
///           infrastructure, not commitment infrastructure.
///         • Domain tag absent by design. No PATTERN-017 entry.
///         • No PV-CI invariant change. The contract is dormant until
///           operator-fired deploy.
///         • Does NOT touch the FROZEN VAPI-CONSENT-v1 preimage
///           (`bridge/vapi_bridge/consent_categories.py:47`). That
///           preimage belongs to the per-category VAPIConsentRegistry;
///           this is a separate contract with no commitment domain.
contract VAPIWorldModelConsentRegistry {

    /// @dev   gamer address → world-model export consent flag.
    ///        Default false. Set by the gamer's own wallet only.
    mapping(address => bool) private _worldModelConsent;

    /// @dev   Lifetime count of consent toggles (grants + revokes).
    ///        Operational counter; not a commitment input.
    uint256 public totalToggles;

    /// @notice Emitted on every consent toggle by the gamer.
    event WorldModelConsentSet(
        address indexed gamer,
        bool            granted,
        uint64          updatedAtBlock,
        uint64          updatedAtTimestamp
    );

    /// @notice Toggle the caller's world-model export consent.
    /// @dev    Caller IS the gamer — the contract enforces no
    ///         delegation, no operator override, no bridge write path.
    ///         The bridge can READ but cannot WRITE.
    /// @param  granted true to grant; false to revoke.
    function setWorldModelConsent(bool granted) external {
        _worldModelConsent[msg.sender] = granted;
        totalToggles++;
        emit WorldModelConsentSet(
            msg.sender,
            granted,
            uint64(block.number),
            uint64(block.timestamp)
        );
    }

    /// @notice Returns whether `gamer` has granted world-model export
    ///         consent. Returns false for any address that has never
    ///         called `setWorldModelConsent`.
    /// @dev    View-call entry for the WMP consumer verifier and for
    ///         the bridge-side export-script gate (WMP-2's
    ///         `world_model_consent_present`).
    function isWorldModelConsentGranted(address gamer)
        external
        view
        returns (bool)
    {
        return _worldModelConsent[gamer];
    }
}
