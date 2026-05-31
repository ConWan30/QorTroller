const { expect } = require("chai");
const { ethers } = require("hardhat");

describe("Arc 6 — VAPIReplayProofVerifier_v2 (PoSR wrapper)", function () {
    let groth16Mock, beaconMock, verifier;
    const REPLAY_PROOF_TOKEN    = ethers.toBigInt("0xa1".padEnd(66, "a1"));
    const SANITIZED_TRACE_ROOT  = ethers.toBigInt("0xb2".padEnd(66, "b2"));
    const POAC_CHAIN_ROOT       = ethers.toBigInt("0xc3".padEnd(66, "c3"));
    const CONSENT_POLICY_HASH   = ethers.toBigInt("0xd4".padEnd(66, "d4"));
    const HUMANITY_THRESHOLD    = 700n;
    const VHP_COMMITMENT        = ethers.toBigInt("0xe5".padEnd(66, "e5"));
    const OPEN_BEACON_BLOCK     = 44188800n;
    const CLOSE_BEACON_BLOCK    = 44188864n;
    const OPEN_BEACON_COMMIT    = ethers.toBigInt("0xf6".padEnd(66, "f6"));
    const CLOSE_BEACON_COMMIT   = ethers.toBigInt("0x17".padEnd(66, "17"));
    const OPEN_BEACON_HASH      = "0x" + "ab".repeat(32);
    const CLOSE_BEACON_HASH     = "0x" + "cd".repeat(32);
    const MOCK_PQ_COMMITMENT    = "0x" + "12".repeat(32);
    const PUBLIC_INPUTS = [
        REPLAY_PROOF_TOKEN, SANITIZED_TRACE_ROOT, POAC_CHAIN_ROOT,
        CONSENT_POLICY_HASH, HUMANITY_THRESHOLD, VHP_COMMITMENT,
        OPEN_BEACON_BLOCK, CLOSE_BEACON_BLOCK,
        OPEN_BEACON_COMMIT, CLOSE_BEACON_COMMIT,
    ];
    const PROOF_A = [1n, 2n], PROOF_B = [[3n, 4n], [5n, 6n]], PROOF_C = [7n, 8n];

    beforeEach(async function () {
        const Groth16 = await ethers.getContractFactory("MockVAPIReplayProofGroth16VerifierV2");
        groth16Mock = await Groth16.deploy(); await groth16Mock.waitForDeployment();
        const BR = await ethers.getContractFactory("MockVAPITemporalBeaconRegistry");
        beaconMock = await BR.deploy(); await beaconMock.waitForDeployment();
        const V = await ethers.getContractFactory("VAPIReplayProofVerifier_v2");
        verifier = await V.deploy(
            await groth16Mock.getAddress(), await beaconMock.getAddress(),
        );
        await verifier.waitForDeployment();
        // Anchor both beacon hashes in the mock so verifyBeacon returns true.
        await beaconMock.setAnchored(OPEN_BEACON_BLOCK, OPEN_BEACON_HASH);
        await beaconMock.setAnchored(CLOSE_BEACON_BLOCK, CLOSE_BEACON_HASH);
    });

    it("T-VHR-V2-1: PROOF_TYPE = keccak256('VAPI-REPLAY-PROOF-v2')", async function () {
        expect(await verifier.PROOF_TYPE()).to.equal(
            ethers.keccak256(ethers.toUtf8Bytes("VAPI-REPLAY-PROOF-v2"))
        );
    });

    it("T-VHR-V2-2: 10-element INPUT_* index constants pin snarkjs declaration order", async function () {
        expect(await verifier.INPUT_REPLAY_PROOF_TOKEN()).to.equal(0n);
        expect(await verifier.INPUT_SANITIZED_TRACE_ROOT()).to.equal(1n);
        expect(await verifier.INPUT_POAC_CHAIN_ROOT()).to.equal(2n);
        expect(await verifier.INPUT_CONSENT_POLICY_HASH()).to.equal(3n);
        expect(await verifier.INPUT_HUMANITY_THRESHOLD()).to.equal(4n);
        expect(await verifier.INPUT_VHP_COMMITMENT()).to.equal(5n);
        expect(await verifier.INPUT_OPEN_BEACON_BLOCK()).to.equal(6n);
        expect(await verifier.INPUT_CLOSE_BEACON_BLOCK()).to.equal(7n);
        expect(await verifier.INPUT_OPEN_BEACON_COMMITMENT()).to.equal(8n);
        expect(await verifier.INPUT_CLOSE_BEACON_COMMITMENT()).to.equal(9n);
    });

    it("T-VHR-V2-3: zero-address constructor reverts (groth16 OR registry)", async function () {
        const V = await ethers.getContractFactory("VAPIReplayProofVerifier_v2");
        await expect(V.deploy(ethers.ZeroAddress, await beaconMock.getAddress()))
            .to.be.revertedWithCustomError(V, "ZeroGroth16Verifier");
        await expect(V.deploy(await groth16Mock.getAddress(), ethers.ZeroAddress))
            .to.be.revertedWithCustomError(V, "ZeroBeaconRegistry");
    });

    it("T-VHR-V2-4: happy path — verify + check beacons + emit event", async function () {
        await expect(verifier.verifyWithRecency(
            PROOF_A, PROOF_B, PROOF_C, PUBLIC_INPUTS,
            OPEN_BEACON_HASH, CLOSE_BEACON_HASH, MOCK_PQ_COMMITMENT,
        )).to.emit(verifier, "ReplayProofVerifiedV2");
    });

    it("T-VHR-V2-5: revert when Groth16 returns false", async function () {
        await groth16Mock.setVerifyResult(false);
        await expect(verifier.verifyWithRecency(
            PROOF_A, PROOF_B, PROOF_C, PUBLIC_INPUTS,
            OPEN_BEACON_HASH, CLOSE_BEACON_HASH, MOCK_PQ_COMMITMENT,
        )).to.be.revertedWithCustomError(verifier, "InvalidGroth16Proof");
    });

    it("T-VHR-V2-6: revert when open beacon hash mismatches registry anchor", async function () {
        await expect(verifier.verifyWithRecency(
            PROOF_A, PROOF_B, PROOF_C, PUBLIC_INPUTS,
            "0x" + "00".repeat(32),   // wrong open hash
            CLOSE_BEACON_HASH, MOCK_PQ_COMMITMENT,
        )).to.be.revertedWithCustomError(verifier, "OpenBeaconUnverified");
    });

    it("T-VHR-V2-7: revert when close beacon hash mismatches OR close <= open", async function () {
        // Wrong close hash
        await expect(verifier.verifyWithRecency(
            PROOF_A, PROOF_B, PROOF_C, PUBLIC_INPUTS,
            OPEN_BEACON_HASH, "0x" + "00".repeat(32), MOCK_PQ_COMMITMENT,
        )).to.be.revertedWithCustomError(verifier, "CloseBeaconUnverified");
        // close == open via shuffled publicInputs
        const equalBlocks = [...PUBLIC_INPUTS];
        equalBlocks[7] = OPEN_BEACON_BLOCK;
        await expect(verifier.verifyWithRecency(
            PROOF_A, PROOF_B, PROOF_C, equalBlocks,
            OPEN_BEACON_HASH, OPEN_BEACON_HASH, MOCK_PQ_COMMITMENT,
        )).to.be.revertedWithCustomError(verifier, "CloseNotAfterOpen");
    });

    it("T-VHR-V2-8: revert when pqCommitment is zero-address / ZeroHash", async function () {
        await expect(verifier.verifyWithRecency(
            PROOF_A, PROOF_B, PROOF_C, PUBLIC_INPUTS,
            OPEN_BEACON_HASH, CLOSE_BEACON_HASH, ethers.ZeroHash,
        )).to.be.revertedWith("VAPI: Zero PQ Commitment Disallowed");
    });
});
