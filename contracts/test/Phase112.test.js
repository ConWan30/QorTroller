const { expect } = require("chai");
const { ethers } = require("hardhat");

describe("Phase112 — AdjudicationRegistry on-chain anchoring (PoAdAnchorAgent path)", function () {
    let registry;
    let owner;

    beforeEach(async function () {
        [owner] = await ethers.getSigners();
        const AdjudicationRegistry = await ethers.getContractFactory("AdjudicationRegistry");
        registry = await AdjudicationRegistry.deploy();
        await registry.waitForDeployment();
    });

    it("1. recordAdjudication with exact bytes32 inputs; isRecorded=true; blockNumber>0; dualVeto=false", async function () {
        // Replicate bridge bytes32 conversion:
        //   device_id_bytes32 = sha256("dev_001") — 32 raw bytes as hex
        //   poad_hash_bytes32 = known 64-char hex
        const deviceIdHash = ethers.keccak256(ethers.toUtf8Bytes("dev_001"));
        const poadHashHex  = ethers.keccak256(ethers.toUtf8Bytes("poad_bundle_phase112_1"));

        await registry.recordAdjudication(deviceIdHash, poadHashHex, false);

        expect(await registry.isRecorded(poadHashHex)).to.equal(true);
        expect(await registry.totalAdjudications()).to.equal(1n);

        const rec = await registry.getAdjudication(deviceIdHash, 0);
        expect(rec.blockNumber).to.be.gt(0n);
        expect(rec.dualVeto).to.equal(false);
        expect(rec.poadHash).to.equal(poadHashHex);
    });

    it("2. two records same deviceIdHash stored separately; getAdjudicationCount=2; totalAdjudications=2", async function () {
        const deviceIdHash = ethers.keccak256(ethers.toUtf8Bytes("dev_002"));
        const poadHash1    = ethers.keccak256(ethers.toUtf8Bytes("poad_bundle_phase112_2a"));
        const poadHash2    = ethers.keccak256(ethers.toUtf8Bytes("poad_bundle_phase112_2b"));

        await registry.recordAdjudication(deviceIdHash, poadHash1, false);
        await registry.recordAdjudication(deviceIdHash, poadHash2, true);

        expect(await registry.getAdjudicationCount(deviceIdHash)).to.equal(2n);
        expect(await registry.totalAdjudications()).to.equal(2n);

        const rec0 = await registry.getAdjudication(deviceIdHash, 0);
        const rec1 = await registry.getAdjudication(deviceIdHash, 1);
        expect(rec0.poadHash).to.equal(poadHash1);
        expect(rec1.poadHash).to.equal(poadHash2);
        expect(rec1.dualVeto).to.equal(true);
    });
});
