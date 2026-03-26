/**
 * RulingRegistry Tests — Phase 66
 *
 * 10 tests covering:
 *   Group 1: Deployment (2)
 *     - deploys with correct operator
 *     - rejects non-operator recordRuling call
 *   Group 2: recordRuling (5)
 *     - records a ruling and emits RulingRecorded event
 *     - rejects duplicate commitment_hash (anti-replay)
 *     - stores all 5 verdict enum values correctly
 *     - stores confidence1000 and timestamp correctly
 *     - allows multiple rulings for same device
 *   Group 3: Queries (3)
 *     - getLatestRuling returns most recent ruling for device
 *     - getRulingCount returns correct count after multiple rulings
 *     - getLatestRuling reverts when device has no rulings
 */

const { expect } = require("chai");
const { ethers } = require("hardhat");

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const DEVICE_A = ethers.zeroPadBytes("0xaa", 32);
const DEVICE_B = ethers.zeroPadBytes("0xbb", 32);

function makeCommitmentHash(n) {
    return ethers.zeroPadValue(ethers.toBeHex(n), 32);
}

// Verdict enum values (matches RulingRegistry.sol order)
const Verdict = { FLAG: 0, HOLD: 1, BLOCK: 2, CERTIFY: 3, CLEAR: 4 };

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("RulingRegistry", function () {

    let registry, operator, nonOperator;

    beforeEach(async function () {
        [operator, nonOperator] = await ethers.getSigners();
        const Factory = await ethers.getContractFactory("RulingRegistry");
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

        it("rejects non-operator recordRuling call with unauthorized error", async function () {
            const commitHash = makeCommitmentHash(1);
            await expect(
                registry.connect(nonOperator).recordRuling(
                    commitHash, DEVICE_A, Verdict.FLAG, 50, 1700000000
                )
            ).to.be.revertedWith("RulingRegistry: unauthorized");
        });
    });

    // -----------------------------------------------------------------------
    // Group 2: recordRuling
    // -----------------------------------------------------------------------

    describe("recordRuling", function () {

        it("records a ruling and emits RulingRecorded event", async function () {
            const commitHash = makeCommitmentHash(10);
            const ts = 1700000100n;
            await expect(
                registry.recordRuling(commitHash, DEVICE_A, Verdict.FLAG, 50, ts)
            )
                .to.emit(registry, "RulingRecorded")
                .withArgs(commitHash, DEVICE_A, Verdict.FLAG, 50, ts);
        });

        it("rejects duplicate commitment_hash (anti-replay)", async function () {
            const commitHash = makeCommitmentHash(20);
            await registry.recordRuling(commitHash, DEVICE_A, Verdict.FLAG, 50, 1700000200n);
            // Second call with same commitHash should revert
            await expect(
                registry.recordRuling(commitHash, DEVICE_A, Verdict.FLAG, 50, 1700000300n)
            ).to.be.revertedWith("RulingRegistry: already recorded");
        });

        it("stores all 5 verdict enum values without error", async function () {
            const verdicts = [Verdict.FLAG, Verdict.HOLD, Verdict.BLOCK, Verdict.CERTIFY, Verdict.CLEAR];
            for (let i = 0; i < verdicts.length; i++) {
                const commitHash = makeCommitmentHash(100 + i);
                // Use different device per verdict to keep counts clean
                const device = ethers.zeroPadValue(ethers.toBeHex(0xAA + i), 32);
                await expect(
                    registry.recordRuling(commitHash, device, verdicts[i], 500, BigInt(1700000400 + i))
                ).to.not.be.reverted;
            }
        });

        it("stores confidence1000 and timestamp correctly in Ruling struct", async function () {
            const commitHash = makeCommitmentHash(200);
            const confidence1000 = 950;
            const ts = 1700000500n;
            await registry.recordRuling(commitHash, DEVICE_A, Verdict.BLOCK, confidence1000, ts);
            const ruling = await registry.rulings(commitHash);
            expect(ruling.confidence1000).to.equal(confidence1000);
            expect(ruling.timestamp).to.equal(ts);
            expect(ruling.verdict).to.equal(Verdict.BLOCK);
        });

        it("allows multiple rulings for the same device", async function () {
            const commit1 = makeCommitmentHash(300);
            const commit2 = makeCommitmentHash(301);
            await registry.recordRuling(commit1, DEVICE_B, Verdict.FLAG, 50, 1700000600n);
            await registry.recordRuling(commit2, DEVICE_B, Verdict.HOLD, 700, 1700000700n);
            const count = await registry.getRulingCount(DEVICE_B);
            expect(count).to.equal(2n);
        });
    });

    // -----------------------------------------------------------------------
    // Group 3: Queries
    // -----------------------------------------------------------------------

    describe("Queries", function () {

        it("getLatestRuling returns most recent ruling for device", async function () {
            const commit1 = makeCommitmentHash(400);
            const commit2 = makeCommitmentHash(401);
            await registry.recordRuling(commit1, DEVICE_A, Verdict.FLAG, 50, 1700000800n);
            await registry.recordRuling(commit2, DEVICE_A, Verdict.BLOCK, 950, 1700000900n);
            const latest = await registry.getLatestRuling(DEVICE_A);
            expect(latest.commitmentHash).to.equal(commit2);
            expect(latest.verdict).to.equal(Verdict.BLOCK);
            expect(latest.confidence1000).to.equal(950);
        });

        it("getRulingCount returns correct count after multiple rulings", async function () {
            expect(await registry.getRulingCount(DEVICE_B)).to.equal(0n);
            const commit1 = makeCommitmentHash(500);
            const commit2 = makeCommitmentHash(501);
            const commit3 = makeCommitmentHash(502);
            await registry.recordRuling(commit1, DEVICE_B, Verdict.FLAG, 50,  1700001000n);
            await registry.recordRuling(commit2, DEVICE_B, Verdict.HOLD, 700, 1700001100n);
            await registry.recordRuling(commit3, DEVICE_B, Verdict.BLOCK, 950, 1700001200n);
            expect(await registry.getRulingCount(DEVICE_B)).to.equal(3n);
        });

        it("getLatestRuling reverts when device has no rulings", async function () {
            const unknownDevice = ethers.zeroPadBytes("0xff", 32);
            await expect(
                registry.getLatestRuling(unknownDevice)
            ).to.be.revertedWith("RulingRegistry: no rulings for device");
        });
    });
});
