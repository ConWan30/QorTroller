const { expect } = require("chai");
const { ethers } = require("hardhat");

describe("Arc 5 — VAPIReplayProofVerifier", function () {
    let groth16Mock;
    let verifier;

    // 6-element snarkjs publicInputs array (output first, then publics
    // in circuit declaration order — pinned by INV-VHR-005).
    const REPLAY_PROOF_TOKEN     = ethers.toBigInt("0xa1a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1");
    const SANITIZED_TRACE_ROOT   = ethers.toBigInt("0xb2b2b2b2b2b2b2b2b2b2b2b2b2b2b2b2b2b2b2b2b2b2b2b2b2b2b2b2b2b2b2b2");
    const POAC_CHAIN_ROOT        = ethers.toBigInt("0xc3c3c3c3c3c3c3c3c3c3c3c3c3c3c3c3c3c3c3c3c3c3c3c3c3c3c3c3c3c3c3c3");
    const CONSENT_POLICY_HASH    = ethers.toBigInt("0xd4d4d4d4d4d4d4d4d4d4d4d4d4d4d4d4d4d4d4d4d4d4d4d4d4d4d4d4d4d4d4d4");
    const HUMANITY_THRESHOLD     = 700n;   // AIT default floor scaled ×1000
    const VHP_COMMITMENT         = ethers.toBigInt("0xe5e5e5e5e5e5e5e5e5e5e5e5e5e5e5e5e5e5e5e5e5e5e5e5e5e5e5e5e5e5e5e5");

    const PUBLIC_INPUTS = [
        REPLAY_PROOF_TOKEN,
        SANITIZED_TRACE_ROOT,
        POAC_CHAIN_ROOT,
        CONSENT_POLICY_HASH,
        HUMANITY_THRESHOLD,
        VHP_COMMITMENT,
    ];

    // Stub Groth16 proof elements — the mock ignores values, only the
    // verifyResult flag matters.
    const PROOF_A = [1n, 2n];
    const PROOF_B = [[3n, 4n], [5n, 6n]];
    const PROOF_C = [7n, 8n];

    beforeEach(async function () {
        const Mock = await ethers.getContractFactory("MockVAPIReplayProofGroth16Verifier");
        groth16Mock = await Mock.deploy();
        await groth16Mock.waitForDeployment();

        const Verifier = await ethers.getContractFactory("VAPIReplayProofVerifier");
        verifier = await Verifier.deploy(await groth16Mock.getAddress());
        await verifier.waitForDeployment();
    });

    it("T-VHR-1: deploy succeeds; groth16Verifier immutable", async function () {
        expect(await verifier.getAddress()).to.be.properAddress;
        expect(await verifier.groth16Verifier()).to.equal(await groth16Mock.getAddress());
    });

    it("T-VHR-2: zero-address for groth16Verifier reverts", async function () {
        const Verifier = await ethers.getContractFactory("VAPIReplayProofVerifier");
        await expect(
            Verifier.deploy(ethers.ZeroAddress)
        ).to.be.revertedWith("VHR: groth16 verifier zero");
    });

    it("T-VHR-3: PROOF_TYPE FROZEN at keccak256('VAPI-REPLAY-PROOF-v1') (INV-VHR-003)", async function () {
        const expected = ethers.keccak256(ethers.toUtf8Bytes("VAPI-REPLAY-PROOF-v1"));
        expect(await verifier.PROOF_TYPE()).to.equal(expected);
    });

    it("T-VHR-4: public-input index constants pin snarkjs order (INV-VHR-005)", async function () {
        // Output first, then 5 publics in circuit declaration order.
        expect(await verifier.INPUT_REPLAY_PROOF_TOKEN()).to.equal(0n);
        expect(await verifier.INPUT_SANITIZED_TRACE_ROOT()).to.equal(1n);
        expect(await verifier.INPUT_POAC_CHAIN_ROOT()).to.equal(2n);
        expect(await verifier.INPUT_CONSENT_POLICY_HASH()).to.equal(3n);
        expect(await verifier.INPUT_HUMANITY_THRESHOLD()).to.equal(4n);
        expect(await verifier.INPUT_VHP_COMMITMENT()).to.equal(5n);
    });

    it("T-VHR-5: valid proof returns true and emits ReplayProofVerified with tuple", async function () {
        // Mock returns true by default
        await expect(
            verifier.verify(PROOF_A, PROOF_B, PROOF_C, PUBLIC_INPUTS)
        ).to.emit(verifier, "ReplayProofVerified")
         .withArgs(
             ethers.toBeHex(REPLAY_PROOF_TOKEN, 32),
             ethers.toBeHex(POAC_CHAIN_ROOT, 32),
             ethers.toBeHex(CONSENT_POLICY_HASH, 32),
             HUMANITY_THRESHOLD,
             ethers.toBeHex(SANITIZED_TRACE_ROOT, 32),
             ethers.toBeHex(VHP_COMMITMENT, 32),
         );
    });

    it("T-VHR-6: rejected proof returns false and emits NO event (matches snarkjs convention)", async function () {
        await groth16Mock.setVerifyResult(false);
        // verify() forwards Groth16's false rather than reverting (mirrors
        // snarkjs-generated verifier convention). No event on rejection.
        const tx = await verifier.verify(PROOF_A, PROOF_B, PROOF_C, PUBLIC_INPUTS);
        const rcpt = await tx.wait();
        // event topic[0] for ReplayProofVerified
        const eventTopic = verifier.interface.getEvent("ReplayProofVerified").topicHash;
        const emitted = rcpt.logs.some(l => l.topics[0] === eventTopic);
        expect(emitted).to.equal(false);
    });

    it("T-VHR-7: verifyView returns true on valid proof; no state-write semantics", async function () {
        // staticCall path — confirms the view variant doesn't require a tx
        const ok = await verifier.verifyView.staticCall(PROOF_A, PROOF_B, PROOF_C, PUBLIC_INPUTS);
        expect(ok).to.equal(true);
    });

    it("T-VHR-8: verifyView returns false when Groth16 rejects; no event possible (view)", async function () {
        await groth16Mock.setVerifyResult(false);
        const ok = await verifier.verifyView.staticCall(PROOF_A, PROOF_B, PROOF_C, PUBLIC_INPUTS);
        expect(ok).to.equal(false);
    });

    it("T-VHR-9: verify() forwards the EXACT publicInputs tuple to Groth16 (no reorder)", async function () {
        // If the wrapper accidentally reordered the array between snarkjs
        // convention and the Groth16 interface, the tuple emitted in the
        // event would mismatch the input. T-VHR-5 already covers the happy
        // path; this test pins the rejection-path inputs to be the same
        // reference Groth16 sees, so a future refactor that introduces a
        // reorder would surface here as a tuple-mismatch.
        const shuffled = [...PUBLIC_INPUTS];
        // Swap two adjacent entries to make a distinguishably-wrong tuple.
        [shuffled[2], shuffled[3]] = [shuffled[3], shuffled[2]];
        await expect(
            verifier.verify(PROOF_A, PROOF_B, PROOF_C, shuffled)
        ).to.emit(verifier, "ReplayProofVerified")
         .withArgs(
             ethers.toBeHex(REPLAY_PROOF_TOKEN, 32),
             ethers.toBeHex(CONSENT_POLICY_HASH, 32),   // shuffled into [2]
             ethers.toBeHex(POAC_CHAIN_ROOT, 32),       // shuffled into [3]
             HUMANITY_THRESHOLD,
             ethers.toBeHex(SANITIZED_TRACE_ROOT, 32),
             ethers.toBeHex(VHP_COMMITMENT, 32),
         );
    });
});
