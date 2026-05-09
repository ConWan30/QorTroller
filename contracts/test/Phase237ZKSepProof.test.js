const { expect } = require("chai");
const { ethers } = require("hardhat");

describe("Phase237 — ZKSepProofVerifier", function () {
    let groth16Mock;
    let adjReg;
    let verifier;
    let owner;

    // Canonical AIT-shaped public inputs (FROZEN at v1)
    // Hash split: low + high 128-bit halves of an arbitrary 256-bit snapshot value.
    // (deadbeef...cafebabe is 32 bytes)
    const SNAPSHOT_HASH = "0xdeadbeefdeadbeefdeadbeefdeadbeefcafebabecafebabecafebabecafebabe";
    const SNAPSHOT_HASH_LO = ethers.toBigInt("0xcafebabecafebabecafebabecafebabe");
    const SNAPSHOT_HASH_HI = ethers.toBigInt("0xdeadbeefdeadbeefdeadbeefdeadbeef");

    const CLAIMED_PLAYER_ID = 1n;
    const FEATURE_COMMITMENT = ethers.toBigInt(
        "0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef"
    );
    const SEPARATION_THRESHOLD_MILLI = 1000n;  // ratio ≥ 1.0
    const INFERENCE_CODE = 0n;

    const PUBLIC_INPUTS = [
        SNAPSHOT_HASH_LO,
        SNAPSHOT_HASH_HI,
        CLAIMED_PLAYER_ID,
        FEATURE_COMMITMENT,
        SEPARATION_THRESHOLD_MILLI,
        INFERENCE_CODE,
    ];

    // Stub Groth16 proof elements — the mock ignores values, only verifyResult flag matters.
    const PROOF_A = [1n, 2n];
    const PROOF_B = [[3n, 4n], [5n, 6n]];
    const PROOF_C = [7n, 8n];

    beforeEach(async function () {
        [owner] = await ethers.getSigners();

        const Mock = await ethers.getContractFactory("MockZKSepProofGroth16Verifier");
        groth16Mock = await Mock.deploy();
        await groth16Mock.waitForDeployment();

        const AdjReg = await ethers.getContractFactory("AdjudicationRegistry");
        adjReg = await AdjReg.deploy();
        await adjReg.waitForDeployment();

        const Verifier = await ethers.getContractFactory("ZKSepProofVerifier");
        verifier = await Verifier.deploy(
            await groth16Mock.getAddress(),
            await adjReg.getAddress()
        );
        await verifier.waitForDeployment();
    });

    it("T-237-SEP-HH-1: deploy succeeds; addresses immutable", async function () {
        expect(await verifier.getAddress()).to.be.properAddress;
        expect(await verifier.groth16Verifier()).to.equal(await groth16Mock.getAddress());
        expect(await verifier.adjudicationRegistry()).to.equal(await adjReg.getAddress());
    });

    it("T-237-SEP-HH-2: zero-address for groth16 reverts", async function () {
        const Verifier = await ethers.getContractFactory("ZKSepProofVerifier");
        await expect(
            Verifier.deploy(ethers.ZeroAddress, await adjReg.getAddress())
        ).to.be.revertedWith("ZKSepProof: groth16 verifier zero");
    });

    it("T-237-SEP-HH-3: zero-address for adjudicationRegistry reverts", async function () {
        const Verifier = await ethers.getContractFactory("ZKSepProofVerifier");
        await expect(
            Verifier.deploy(await groth16Mock.getAddress(), ethers.ZeroAddress)
        ).to.be.revertedWith("ZKSepProof: adjudication registry zero");
    });

    it("T-237-SEP-HH-4: snapshot not anchored -> verifyAndCheckSnapshot reverts", async function () {
        await expect(
            verifier.verifyAndCheckSnapshot(PROOF_A, PROOF_B, PROOF_C, PUBLIC_INPUTS)
        ).to.be.revertedWith("ZKSepProof: snapshot not anchored");
    });

    it("T-237-SEP-HH-5: snapshot anchored + valid proof -> returns true; emits SepProofAccepted", async function () {
        // Anchor the snapshot (mirrors anchor_biometric_snapshot pathway)
        const dummyDeviceHash = ethers.keccak256(ethers.toUtf8Bytes("VAPI_BIOMETRIC_SNAPSHOT_v1"));
        await adjReg.recordAdjudication(dummyDeviceHash, SNAPSHOT_HASH, false);
        expect(await adjReg.isRecorded(SNAPSHOT_HASH)).to.equal(true);

        // Mock returns true by default
        await expect(
            verifier.verifyAndCheckSnapshot(PROOF_A, PROOF_B, PROOF_C, PUBLIC_INPUTS)
        ).to.emit(verifier, "SepProofAccepted")
         .withArgs(
             SNAPSHOT_HASH,
             CLAIMED_PLAYER_ID,
             SEPARATION_THRESHOLD_MILLI,
             INFERENCE_CODE
         );
    });

    it("T-237-SEP-HH-6: snapshot anchored + Groth16 fails -> returns false; no event", async function () {
        const dummyDeviceHash = ethers.keccak256(ethers.toUtf8Bytes("VAPI_BIOMETRIC_SNAPSHOT_v1"));
        await adjReg.recordAdjudication(dummyDeviceHash, SNAPSHOT_HASH, false);

        // Configure mock to return false
        await groth16Mock.setVerifyResult(false);

        const tx = await verifier.verifyAndCheckSnapshot(
            PROOF_A, PROOF_B, PROOF_C, PUBLIC_INPUTS
        );
        const receipt = await tx.wait();

        // Should NOT emit SepProofAccepted (only fired on verified=true)
        const acceptedEvents = receipt.logs.filter(
            log => log.topics[0] === ethers.id("SepProofAccepted(bytes32,uint256,uint256,uint256)")
        );
        expect(acceptedEvents.length).to.equal(0);
    });

    it("T-237-SEP-HH-7: verifyAndCheckSnapshotView (pure variant) returns same result without event", async function () {
        const dummyDeviceHash = ethers.keccak256(ethers.toUtf8Bytes("VAPI_BIOMETRIC_SNAPSHOT_v1"));
        await adjReg.recordAdjudication(dummyDeviceHash, SNAPSHOT_HASH, false);

        // Default mock = true
        const result = await verifier.verifyAndCheckSnapshotView(
            PROOF_A, PROOF_B, PROOF_C, PUBLIC_INPUTS
        );
        expect(result).to.equal(true);

        // verifyAndCheckSnapshotView is `view` — calling it does not emit events.
        // Regression guard: confirm the function exists with view modifier by
        // checking it can be called via callStatic without state change.
        const filter = verifier.filters.SepProofAccepted();
        const eventsBefore = await verifier.queryFilter(filter);
        // Call the view again
        await verifier.verifyAndCheckSnapshotView(PROOF_A, PROOF_B, PROOF_C, PUBLIC_INPUTS);
        const eventsAfter = await verifier.queryFilter(filter);
        expect(eventsAfter.length).to.equal(eventsBefore.length);
    });

    it("T-237-SEP-HH-8: snapshot hash reconstruction (lo, hi) → bytes32 round-trip", async function () {
        // Construct a known snapshot hash, split into lo+hi, anchor, verify
        // wrapper reconstructs the original hash for the registry check.
        const customHash = "0x1111222233334444555566667777888899990000aaaabbbbccccddddeeeeffff";
        const customLo = ethers.toBigInt("0x99990000aaaabbbbccccddddeeeeffff");
        const customHi = ethers.toBigInt("0x11112222333344445555666677778888");

        const dummyDeviceHash = ethers.keccak256(ethers.toUtf8Bytes("VAPI_BIOMETRIC_SNAPSHOT_v1_alt"));
        await adjReg.recordAdjudication(dummyDeviceHash, customHash, false);

        const customInputs = [
            customLo, customHi,
            CLAIMED_PLAYER_ID, FEATURE_COMMITMENT,
            SEPARATION_THRESHOLD_MILLI, INFERENCE_CODE,
        ];

        await expect(
            verifier.verifyAndCheckSnapshot(PROOF_A, PROOF_B, PROOF_C, customInputs)
        ).to.emit(verifier, "SepProofAccepted")
         .withArgs(customHash, CLAIMED_PLAYER_ID, SEPARATION_THRESHOLD_MILLI, INFERENCE_CODE);
    });
});
