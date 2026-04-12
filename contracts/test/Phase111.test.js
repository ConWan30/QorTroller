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

    // -------------------------------------------------------------------
    // VAPI-EXT Phase 204 — anchorAdjudication with sourceType
    // -------------------------------------------------------------------

    const podHash1 = ethers.keccak256(ethers.toUtf8Bytes("pod_bundle_vapi_001"));
    const podHash2 = ethers.keccak256(ethers.toUtf8Bytes("pod_bundle_mobile_001"));
    const podHash3 = ethers.keccak256(ethers.toUtf8Bytes("pod_bundle_pragma_001"));

    it("7. anchorAdjudication(podHash, sourceType) records sourceType; isRecorded returns true", async function () {
        await registry["anchorAdjudication(bytes32,string)"](podHash1, "VAPI");
        expect(await registry.isRecorded(podHash1)).to.equal(true);
        expect(await registry.getSourceType(podHash1)).to.equal("VAPI");
        expect(await registry.totalAdjudications()).to.equal(1n);
    });

    it("8. anchorAdjudication(podHash) overload defaults to sourceType='VAPI'", async function () {
        await registry["anchorAdjudication(bytes32)"](podHash1);
        expect(await registry.isRecorded(podHash1)).to.equal(true);
        expect(await registry.getSourceType(podHash1)).to.equal("VAPI");
    });

    it("9. anchorAdjudication stores VAPI_MOBILE sourceType correctly", async function () {
        await registry["anchorAdjudication(bytes32,string)"](podHash2, "VAPI_MOBILE");
        expect(await registry.getSourceType(podHash2)).to.equal("VAPI_MOBILE");
    });

    it("10. anchorAdjudication stores PRAGMA_JUDGE sourceType correctly", async function () {
        await registry["anchorAdjudication(bytes32,string)"](podHash3, "PRAGMA_JUDGE");
        expect(await registry.getSourceType(podHash3)).to.equal("PRAGMA_JUDGE");
    });

    it("11. anchorAdjudication anti-replay: duplicate podHash reverts", async function () {
        await registry["anchorAdjudication(bytes32,string)"](podHash1, "VAPI");
        await expect(
            registry["anchorAdjudication(bytes32,string)"](podHash1, "VAPI")
        ).to.be.revertedWith("PoAd: already recorded");
    });

    it("12. anchorAdjudication emits AdjudicationAnchoredV2 event", async function () {
        await expect(registry["anchorAdjudication(bytes32,string)"](podHash1, "VAPI"))
            .to.emit(registry, "AdjudicationAnchoredV2")
            .withArgs(podHash1, "VAPI", await ethers.provider.getBlockNumber() + 1);
    });

    it("13. anchorAdjudication non-owner reverts", async function () {
        await expect(
            registry.connect(nonOwner)["anchorAdjudication(bytes32,string)"](podHash1, "VAPI")
        ).to.be.revertedWithCustomError(registry, "OwnableUnauthorizedAccount");
    });

    it("14. recordAdjudication and anchorAdjudication share the anti-replay guard", async function () {
        // Record via legacy API
        await registry.recordAdjudication(deviceHash1, poadHash1, false);
        // Attempt to anchor the same hash via new API — must revert
        await expect(
            registry["anchorAdjudication(bytes32,string)"](poadHash1, "VAPI")
        ).to.be.revertedWith("PoAd: already recorded");
    });

    it("15. totalAdjudications increments for both APIs combined", async function () {
        await registry.recordAdjudication(deviceHash1, poadHash1, false);
        await registry["anchorAdjudication(bytes32,string)"](podHash1, "VAPI_MOBILE");
        await registry["anchorAdjudication(bytes32)"](podHash2);
        expect(await registry.totalAdjudications()).to.equal(3n);
    });

    it("16. getSourceType returns empty string for legacy recordAdjudication entries", async function () {
        await registry.recordAdjudication(deviceHash1, poadHash1, false);
        expect(await registry.getSourceType(poadHash1)).to.equal("");
    });
});
