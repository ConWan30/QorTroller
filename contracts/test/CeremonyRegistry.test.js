/**
 * CeremonyRegistry Tests — Phase 67
 *
 * 8 tests covering:
 *   Group 1: Deployment (2)
 *     - deploys with correct operator
 *     - rejects non-operator registerCeremony call
 *   Group 2: registerCeremony (4)
 *     - registers ceremony and emits CeremonyRegistered event
 *     - rejects fewer than 2 contributors (minimum enforcement)
 *     - rejects duplicate circuitId (anti-replay)
 *     - stores verifyingKeyHash, beaconBlockHash, contributorCount correctly
 *   Group 3: Queries (2)
 *     - verifyCeremony returns true for matching vkeyHash
 *     - verifyCeremony returns false for wrong vkeyHash
 */

const { expect } = require("chai");
const { ethers } = require("hardhat");

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

// circuitId = keccak256(circuitName) — matches run-mpc-ceremony.js
function makeCircuitId(name) {
    return ethers.keccak256(ethers.toUtf8Bytes(name));
}

function makeBytes32(seed) {
    return ethers.zeroPadValue(ethers.toBeHex(seed), 32);
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("CeremonyRegistry", function () {

    let registry, operator, nonOperator;

    const CIRCUIT_ID    = makeCircuitId("PitlSessionProof");
    const VKEY_HASH     = makeBytes32(0xdeadbeef);
    const BEACON_HASH   = makeBytes32(0xcafe1234);
    const BEACON_NUMBER = 999888;
    const PTAU_SOURCE   = "hermez-hez_final_15-2021";
    const CONTRIB_1     = makeBytes32(0x0101);
    const CONTRIB_2     = makeBytes32(0x0202);
    const CONTRIB_3     = makeBytes32(0x0303);

    beforeEach(async function () {
        [operator, nonOperator] = await ethers.getSigners();
        const Factory = await ethers.getContractFactory("CeremonyRegistry");
        registry = await Factory.deploy(operator.address);
        await registry.waitForDeployment();
    });

    // -----------------------------------------------------------------------
    // Group 1: Deployment
    // -----------------------------------------------------------------------

    describe("Deployment", function () {

        it("deploys with correct operator address", async function () {
            const onChainOperator = await registry.operator();
            expect(onChainOperator).to.equal(operator.address);
        });

        it("rejects non-operator registerCeremony call", async function () {
            await expect(
                registry.connect(nonOperator).registerCeremony(
                    CIRCUIT_ID,
                    VKEY_HASH,
                    BEACON_HASH,
                    BEACON_NUMBER,
                    [CONTRIB_1, CONTRIB_2],
                    PTAU_SOURCE,
                )
            ).to.be.revertedWith("CeremonyRegistry: unauthorized");
        });

    });

    // -----------------------------------------------------------------------
    // Group 2: registerCeremony
    // -----------------------------------------------------------------------

    describe("registerCeremony", function () {

        it("registers ceremony and emits CeremonyRegistered event", async function () {
            await expect(
                registry.registerCeremony(
                    CIRCUIT_ID,
                    VKEY_HASH,
                    BEACON_HASH,
                    BEACON_NUMBER,
                    [CONTRIB_1, CONTRIB_2, CONTRIB_3],
                    PTAU_SOURCE,
                )
            )
            .to.emit(registry, "CeremonyRegistered")
            .withArgs(CIRCUIT_ID, VKEY_HASH, BEACON_HASH, BEACON_NUMBER, 3);
        });

        it("rejects fewer than 2 contributors (minimum MPC enforcement)", async function () {
            await expect(
                registry.registerCeremony(
                    CIRCUIT_ID,
                    VKEY_HASH,
                    BEACON_HASH,
                    BEACON_NUMBER,
                    [CONTRIB_1],   // only 1 — below minimum
                    PTAU_SOURCE,
                )
            ).to.be.revertedWith("CeremonyRegistry: minimum 2 contributors required");
        });

        it("rejects duplicate circuitId (anti-replay)", async function () {
            // First registration succeeds
            await registry.registerCeremony(
                CIRCUIT_ID, VKEY_HASH, BEACON_HASH, BEACON_NUMBER,
                [CONTRIB_1, CONTRIB_2], PTAU_SOURCE,
            );
            // Second registration with same circuitId must revert
            await expect(
                registry.registerCeremony(
                    CIRCUIT_ID, makeBytes32(0xaabbccdd), BEACON_HASH, BEACON_NUMBER,
                    [CONTRIB_1, CONTRIB_2], PTAU_SOURCE,
                )
            ).to.be.revertedWith("CeremonyRegistry: circuit already registered");
        });

        it("stores verifyingKeyHash, beaconBlockHash, and contributorCount correctly", async function () {
            await registry.registerCeremony(
                CIRCUIT_ID, VKEY_HASH, BEACON_HASH, BEACON_NUMBER,
                [CONTRIB_1, CONTRIB_2, CONTRIB_3], PTAU_SOURCE,
            );
            const [vkHash, bcHash, bcNumber, contribCount, ptau, ts, registeredBy] =
                await registry.getCeremony(CIRCUIT_ID);

            expect(vkHash).to.equal(VKEY_HASH);
            expect(bcHash).to.equal(BEACON_HASH);
            expect(Number(bcNumber)).to.equal(BEACON_NUMBER);
            expect(Number(contribCount)).to.equal(3);
            expect(ptau).to.equal(PTAU_SOURCE);
            expect(registeredBy).to.equal(operator.address);
            expect(Number(ts)).to.be.greaterThan(0);
        });

    });

    // -----------------------------------------------------------------------
    // Group 3: Queries
    // -----------------------------------------------------------------------

    describe("Queries", function () {

        beforeEach(async function () {
            await registry.registerCeremony(
                CIRCUIT_ID, VKEY_HASH, BEACON_HASH, BEACON_NUMBER,
                [CONTRIB_1, CONTRIB_2], PTAU_SOURCE,
            );
        });

        it("verifyCeremony returns true for matching vkeyHash", async function () {
            const valid = await registry.verifyCeremony(CIRCUIT_ID, VKEY_HASH);
            expect(valid).to.be.true;
        });

        it("verifyCeremony returns false for wrong vkeyHash", async function () {
            const wrongHash = makeBytes32(0xbaddcafe);
            const valid = await registry.verifyCeremony(CIRCUIT_ID, wrongHash);
            expect(valid).to.be.false;
        });

    });

});
