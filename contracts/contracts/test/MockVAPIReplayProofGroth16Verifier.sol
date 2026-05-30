// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * @title MockVAPIReplayProofGroth16Verifier — Arc 5 Commit 3 test mock
 * @notice Configurable mock of the snarkjs-generated Groth16 verifier.
 *
 * Used by VAPIReplayProofVerifier Hardhat tests to exercise the wrapper's
 * verify / verifyView paths and event emission before the trusted setup
 * ceremony runs. Production deploy swaps this for the auto-generated
 * Groth16VerifierVAPIReplayProof.sol from snarkjs.
 *
 * Default behaviour is `true` so happy-path tests don't have to configure
 * the mock first; setVerifyResult(false) is used to exercise the rejection
 * path.
 */
contract MockVAPIReplayProofGroth16Verifier {
    bool public verifyResult = true;

    function setVerifyResult(bool _result) external {
        verifyResult = _result;
    }

    function verifyProof(
        uint256[2] memory /* a */,
        uint256[2][2] memory /* b */,
        uint256[2] memory /* c */,
        uint256[6] memory /* input */
    ) external view returns (bool) {
        return verifyResult;
    }
}
