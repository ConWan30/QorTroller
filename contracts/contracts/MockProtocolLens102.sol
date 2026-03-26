// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

contract MockProtocolLens102 {
    bool private _eligible;

    function setEligible(bool val) external { _eligible = val; }
    function isFullyEligible(bytes32) external view returns (bool) { return _eligible; }
}
