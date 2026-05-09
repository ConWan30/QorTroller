// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * @title MockZKSepProofGroth16Verifier — Phase 237-ZK-SEPPROOF test mock
 * @notice Configurable mock of the snarkjs-generated Groth16 verifier.
 *
 * Used by Phase 237-ZK-SEPPROOF Hardhat tests to exercise
 * ZKSepProofVerifier wrapper logic before the trusted setup ceremony
 * runs.  Production deploy swaps this for the auto-generated
 * Groth16VerifierZKSepProof.sol from snarkjs.
 *
 * The mock returns whatever value was set via setVerifyResult().
 * Default behaviour is `true` so happy-path tests don't have to
 * configure the mock first.
 */

contract MockZKSepProofGroth16Verifier {
    bool public verifyResult = true;

    /// @notice Set the boolean that verifyProof will return on every call.
    function setVerifyResult(bool _result) external {
        verifyResult = _result;
    }

    /// @notice Mock implementation matching IZKSepProofGroth16Verifier shape.
    function verifyProof(
        uint256[2] memory /* a */,
        uint256[2][2] memory /* b */,
        uint256[2] memory /* c */,
        uint256[6] memory /* input */
    ) external view returns (bool) {
        return verifyResult;
    }
}
