const { expect } = require("chai");
const { ethers } = require("hardhat");

describe("Phase111 — AdjudicationRegistry", function () {
    let registry;
    let owner;
    let nonOwner;

    const deviceHash1 = ethers.keccak256(ethers.toUtf8Bytes("device_001"));
    const poadHash1   = ethers.keccak256(ethers.toUtf8Bytes("poad_bundle_001"));
    const poadHash2   = ethers.keccak256(ethers.toUtf8Bytes("poad_bundle_002"));
    const poadHash3   = ethers.keccak256(ethers.toUtf8Bytes("poad_bundle_003"));

    beforeEach(async function () {
        [owner, nonOwner] = await ethers.getSigners();
        const AdjudicationRegistry = await ethers.getContractFactory("AdjudicationRegistry");
        registry = await AdjudicationRegistry.deploy();
        await registry.waitForDeployment();
    });

    it("1. deploy succeeds; owner == deployer", async function () {
        expect(await registry.getAddress()).to.be.properAddress;
        expect(await registry.owner()).to.equal(owner.address);
        expect(await registry.totalAdjudications()).to.equal(0n);
    });

    it("2. recordAdjudication stores PoAd record; isRecorded returns true; blockNumber > 0", async function () {
        await registry.recordAdjudication(deviceHash1, poadHash1, false);
        expect(await registry.isRecorded(poadHash1)).to.equal(true);
        expect(await registry.getAdjudicationCount(deviceHash1)).to.equal(1n);
        const rec = await registry.getAdjudication(deviceHash1, 0);
        expect(rec.poadHash).to.equal(poadHash1);
        expect(rec.blockNumber).to.be.gt(0n);
        expect(rec.dualVeto).to.equal(false);
        expect(await registry.totalAdjudications()).to.equal(1n);
    });

    it("3. anti-replay: duplicate poadHash reverts with 'PoAd: already recorded'", async function () {
        await registry.recordAdjudication(deviceHash1, poadHash1, false);
        await expect(
            registry.recordAdjudication(deviceHash1, poadHash1, false)
        ).to.be.revertedWith("PoAd: already recorded");
    });

    it("4. dualVeto=true stored correctly", async function () {
        await registry.recordAdjudication(deviceHash1, poadHash1, true);
        const rec = await registry.getAdjudication(deviceHash1, 0);
        expect(rec.dualVeto).to.equal(true);
    });

    it("5. totalAdjudications increments across multiple records", async function () {
        await registry.recordAdjudication(deviceHash1, poadHash1, false);
        await registry.recordAdjudication(deviceHash1, poadHash2, true);
        await registry.recordAdjudication(deviceHash1, poadHash3, false);
        expect(await registry.totalAdjudications()).to.equal(3n);
        expect(await registry.getAdjudicationCount(deviceHash1)).to.equal(3n);
    });

    it("6. non-owner reverts with OwnableUnauthorizedAccount", async function () {
        await expect(
            registry.connect(nonOwner).recordAdjudication(deviceHash1, poadHash1, false)
        ).to.be.revertedWithCustomError(registry, "OwnableUnauthorizedAccount");
    });
});
