// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/// @title MockLayerZeroEndpoint - Hardhat test mock for the LayerZero V2 EndpointV2
/// @notice Defensive Phase O4-VPM-INT-B-PREP infrastructure shipped 2026-05-14 as
///         part of the PARTIAL_REFACTOR fallback path in the post-O4 v4 section 15
///         plan. Full LayerZero V2 OApp inheritance in VAPIVerifiedHumanProofBridge
///         is BLOCKED upstream by a peer-dep conflict: lz-evm-oapp-v2 v3.0.168
///         transitively requires eth-optimism contracts v0.6.0 with peer ethers
///         v5, but Hardhat Toolbox v4.0.0 declares peer ethers v6.14. npm refuses
///         to resolve. Per approved plan Risk 3 fallback: defensive additions
///         only; full OApp refactor deferred until (a) LayerZero publishes a
///         line dropping the ethers v5 transitive dep, or (b) the project
///         migrates Hardhat Toolbox to a 5.x line supporting the older ethers
///         peer range. This mock + the bridgeMint modifier on
///         VAPIVerifiedHumanProof constitute the defensive prep.
contract MockLayerZeroEndpoint {

    struct MessagingParams {
        uint32  dstEid;
        bytes32 receiver;
        bytes   message;
        bytes   options;
        bool    payInLzToken;
    }

    struct MessagingReceipt {
        bytes32 guid;
        uint64  nonce;
        uint256 fee;
    }

    /// @notice Each send() call recorded for test inspection.
    MessagingParams[] public sentParams;

    /// @notice Each send() caller recorded for test inspection.
    address[] public sentCallers;

    event Sent(
        address indexed sender,
        uint32  indexed dstEid,
        bytes32 receiver,
        uint64  nonce
    );

    /// @notice Counter assigned as nonce per (caller, dstEid) call.
    uint64 public globalNonce;

    /**
     * @notice Mock LayerZero V2 send. Records the params + returns a synthetic receipt.
     * @dev    Production OApp v2 send() would route the message via the LZ endpoint;
     *         this mock just records the call for Hardhat-level test verification.
     */
    function send(
        MessagingParams calldata _params,
        address _refundAddress
    ) external payable returns (MessagingReceipt memory) {
        require(_params.dstEid != 0, "MockLZ: zero dstEid");
        require(_params.receiver != bytes32(0), "MockLZ: zero receiver");
        require(_refundAddress != address(0), "MockLZ: zero refund addr");

        sentParams.push(_params);
        sentCallers.push(msg.sender);
        globalNonce++;

        emit Sent(msg.sender, _params.dstEid, _params.receiver, globalNonce);

        return MessagingReceipt({
            guid: bytes32(uint256(globalNonce)),
            nonce: globalNonce,
            fee: msg.value
        });
    }

    /**
     * @notice Quote a fictional fee for a hypothetical send().
     */
    function quote(
        MessagingParams calldata,
        address
    ) external pure returns (uint256 nativeFee, uint256 lzTokenFee) {
        return (0.001 ether, 0);
    }

    /**
     * @notice Returns the count of recorded send() invocations.
     */
    function sentCount() external view returns (uint256) {
        return sentParams.length;
    }

    /**
     * @notice Test helper — dispatch a synthetic inbound message at a target
     *         contract's `_lzReceive`-like entry-point. Production EndpointV2
     *         would call lzReceive on the OApp; this mock provides the same
     *         shape so tests can exercise the receive path before the full
     *         OApp inheritance refactor lands.
     */
    function simulateInbound(
        address target,
        bytes calldata payload
    ) external returns (bool success, bytes memory returnData) {
        // Production: target.lzReceive(Origin, guid, payload, executor, extraData)
        // Mock: simple low-level call with the payload only — exercises the
        // receiver-side decode + state-mutation path during tests
        (success, returnData) = target.call(payload);
    }
}
