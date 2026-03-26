// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

contract MockVHP102 {
    bool private _valid;

    function setValid(bool val) external { _valid = val; }
    function isValid(uint256) external view returns (bool) { return _valid; }
}
