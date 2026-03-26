// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/access/Ownable.sol";

interface IVAPIProtocolLens {
    function isFullyEligible(bytes32 deviceId) external view returns (bool);
}

interface IVAPIVerifiedHumanProof {
    function isValid(uint256 tokenId) external view returns (bool);
}

/**
 * @title TournamentGateDemo
 * @notice Developer-facing composability demo for VAPI-gated tournaments (Phase 102).
 * @dev Shows "single composable call" AGaaS pattern: isFullyEligible() + VHP validity check.
 *      W1 mitigation: demoMode flag (owner-settable) bypasses gate calls for developer testing.
 *      demoMode=false enforces full PITL stack. Set demoMode=true on testnet for evaluation.
 */
contract TournamentGateDemo is Ownable {
    IVAPIProtocolLens       public immutable protocolLens;
    IVAPIVerifiedHumanProof public immutable vhp;

    /// @notice W1 mitigation: when true, bypasses PITL gate for developer testing.
    ///         Set to false for production enforcement of full VAPI stack.
    bool public demoMode;

    struct Participant {
        address player;
        bytes32 deviceId;
        uint256 vhpTokenId;
        uint256 enteredAt;
    }

    Participant[] private _participants;

    event PlayerEntered(
        address indexed player,
        bytes32 indexed deviceId,
        uint256 vhpTokenId,
        uint256 timestamp
    );
    event DemoModeSet(bool enabled);

    constructor(address _lens, address _vhp) Ownable(msg.sender) {
        require(_lens != address(0), "TournamentGateDemo: zero lens");
        require(_vhp  != address(0), "TournamentGateDemo: zero vhp");
        protocolLens = IVAPIProtocolLens(_lens);
        vhp          = IVAPIVerifiedHumanProof(_vhp);
    }

    /**
     * @notice Enter a VAPI-gated tournament.
     * @param deviceId  The player's ioID device identifier (bytes32).
     * @param vhpTokenId The player's VHP soulbound token ID.
     * @dev   When demoMode=false: requires isFullyEligible(deviceId) AND isValid(vhpTokenId).
     *        When demoMode=true: skips both checks (for developer evaluation on testnet).
     */
    function enterTournament(bytes32 deviceId, uint256 vhpTokenId) external {
        if (!demoMode) {
            require(
                protocolLens.isFullyEligible(deviceId),
                "TournamentGateDemo: PITL gate not passed"
            );
            require(
                vhp.isValid(vhpTokenId),
                "TournamentGateDemo: VHP token expired or invalid"
            );
        }
        _participants.push(Participant(msg.sender, deviceId, vhpTokenId, block.timestamp));
        emit PlayerEntered(msg.sender, deviceId, vhpTokenId, block.timestamp);
    }

    /// @notice Toggle demo mode (W1 mitigation). Only callable by owner.
    function setDemoMode(bool _demo) external onlyOwner {
        demoMode = _demo;
        emit DemoModeSet(_demo);
    }

    /// @notice Returns number of registered tournament participants.
    function getParticipantCount() external view returns (uint256) {
        return _participants.length;
    }

    /// @notice Returns participant at index.
    function getParticipant(uint256 idx) external view returns (Participant memory) {
        require(idx < _participants.length, "TournamentGateDemo: index out of range");
        return _participants[idx];
    }
}
