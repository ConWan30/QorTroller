const { expect } = require("chai");
const { ethers } = require("hardhat");

// ---------------------------------------------------------------------------
// GateAttestationAnchor Tests — Phase 84
//
// GAA-1: deploy sets operator correctly
// GAA-2: recordGateAttestation emits GateAttestationRecorded and stores correctly
// GAA-3: non-operator recordGateAttestation reverts
// GAA-4: duplicate attestationHash reverts (anti-replay)
// ---------------------------------------------------------------------------

const ATTEST_HASH_1 = ethers.zeroPadBytes("0xaa8401", 32);
const ATTEST_HASH_2 = ethers.zeroPadBytes("0xaa8402", 32);

async function deployGAA(operatorAddress) {
    const Factory = await ethers.getContractFactory("GateAttestationAnchor");
    return Factory.deploy(operatorAddress);
}

describe("GateAttestationAnchor (Phase 84)", function () {
    let gaa, operator, other;

    beforeEach(async function () {
        [operator, other] = await ethers.getSigners();
        gaa = await deployGAA(operator.address);
    });

    // -------------------------------------------------------------------------
    // GAA-1: Deployment
    // -------------------------------------------------------------------------

    it("GAA-1: deploy sets operator address correctly", async function () {
        expect(await gaa.operator()).to.equal(operator.address);
        expect(await gaa.getAttestationCount()).to.equal(0n);
    });

    // -------------------------------------------------------------------------
    // GAA-2: recordGateAttestation emits event and stores correctly
    // -------------------------------------------------------------------------

    it("GAA-2: recordGateAttestation emits GateAttestationRecorded and stores correctly", async function () {
        const consecutiveClean = 100;
        const gateN = 100;
        const divergenceRateMillis = 0;
        const timestamp = Math.floor(Date.now() / 1000);

        await expect(
            gaa.connect(operator).recordGateAttestation(
                ATTEST_HASH_1, consecutiveClean, gateN, divergenceRateMillis, timestamp
            )
        )
            .to.emit(gaa, "GateAttestationRecorded")
            .withArgs(ATTEST_HASH_1, consecutiveClean, gateN, timestamp);

        // Verify stored struct
        const stored = await gaa.getAttestation(ATTEST_HASH_1);
        expect(stored.consecutiveClean).to.equal(consecutiveClean);
        expect(stored.gateN).to.equal(gateN);
        expect(stored.divergenceRateMillis).to.equal(divergenceRateMillis);
        expect(stored.submittedBy).to.equal(operator.address);

        // Verify getLatestAttestation
        const latest = await gaa.getLatestAttestation();
        expect(latest.attestationHash).to.equal(ATTEST_HASH_1);
        expect(await gaa.getAttestationCount()).to.equal(1n);
    });

    // -------------------------------------------------------------------------
    // GAA-3: Access control
    // -------------------------------------------------------------------------

    it("GAA-3: non-operator recordGateAttestation reverts", async function () {
        await expect(
            gaa.connect(other).recordGateAttestation(
                ATTEST_HASH_1, 100, 100, 0, Math.floor(Date.now() / 1000)
            )
        ).to.be.revertedWith("GateAttestationAnchor: unauthorized");
    });

    // -------------------------------------------------------------------------
    // GAA-4: Anti-replay
    // -------------------------------------------------------------------------

    it("GAA-4: duplicate attestationHash reverts (anti-replay)", async function () {
        const ts = Math.floor(Date.now() / 1000);
        await gaa.connect(operator).recordGateAttestation(ATTEST_HASH_1, 100, 100, 0, ts);
        await expect(
            gaa.connect(operator).recordGateAttestation(ATTEST_HASH_1, 100, 100, 0, ts)
        ).to.be.revertedWith("GateAttestationAnchor: already recorded");
        // Different hash is fine
        await gaa.connect(operator).recordGateAttestation(ATTEST_HASH_2, 101, 100, 0, ts);
        expect(await gaa.getAttestationCount()).to.equal(2n);
    });
});
