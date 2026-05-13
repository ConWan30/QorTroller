const { expect } = require("chai");
const { ethers } = require("hardhat");

describe("VPMAnchorRegistry — Phase O4-VPM-ANCHOR", function () {
    let mockAdj;
    let registry;
    let owner;
    let nonOwner;

    const zkbaHash1 = ethers.keccak256(ethers.toUtf8Bytes("zkba_manifest_001"));
    const zkbaHash2 = ethers.keccak256(ethers.toUtf8Bytes("zkba_manifest_002"));
    const vpmHash1  = ethers.keccak256(ethers.toUtf8Bytes("vpm_manifest_001"));
    const vpmHash2  = ethers.keccak256(ethers.toUtf8Bytes("vpm_manifest_002"));
    const vpmHash3  = ethers.keccak256(ethers.toUtf8Bytes("vpm_manifest_003"));
    const tsNs1     = 1778900000000000000n;
    const tsNs2     = 1778900100000000000n;

    beforeEach(async function () {
        [owner, nonOwner] = await ethers.getSigners();

        const Mock = await ethers.getContractFactory(
            "MockAdjudicationRegistry_VPM"
        );
        mockAdj = await Mock.deploy();
        await mockAdj.waitForDeployment();

        const Registry = await ethers.getContractFactory("VPMAnchorRegistry");
        registry = await Registry.deploy(await mockAdj.getAddress());
        await registry.waitForDeployment();
    });

    it("1. deploy succeeds; owner == deployer; adjudicationRegistry pinned", async function () {
        expect(await registry.getAddress()).to.be.properAddress;
        expect(await registry.owner()).to.equal(owner.address);
        expect(await registry.adjudicationRegistry()).to.equal(
            await mockAdj.getAddress()
        );
        expect(await registry.totalAnchored()).to.equal(0n);
    });

    it("2. zero-address adjudication registry reverts at construction", async function () {
        const Registry = await ethers.getContractFactory("VPMAnchorRegistry");
        await expect(
            Registry.deploy(ethers.ZeroAddress)
        ).to.be.revertedWith("VPM: zero adjudication registry");
    });

    it("3. anchorVPM stores record + emits VPMAnchored when ZKBA is recorded", async function () {
        await mockAdj.setRecorded(zkbaHash1, true);

        await expect(registry.anchorVPM(zkbaHash1, vpmHash1, tsNs1))
            .to.emit(registry, "VPMAnchored")
            .withArgs(zkbaHash1, vpmHash1, anyValue => true, tsNs1);

        expect(await registry.isAnchored(vpmHash1)).to.equal(true);
        expect(await registry.totalAnchored()).to.equal(1n);

        const rec = await registry.getRecord(vpmHash1);
        expect(rec.zkbaManifestHash).to.equal(zkbaHash1);
        expect(rec.vpmManifestHash).to.equal(vpmHash1);
        expect(rec.tsNs).to.equal(tsNs1);
        expect(rec.blockNumber).to.be.gt(0n);
    });

    it("4. zero zkba hash reverts with 'VPM: zero zkba hash'", async function () {
        await expect(
            registry.anchorVPM(ethers.ZeroHash, vpmHash1, tsNs1)
        ).to.be.revertedWith("VPM: zero zkba hash");
    });

    it("5. zero vpm hash reverts with 'VPM: zero vpm hash'", async function () {
        await expect(
            registry.anchorVPM(zkbaHash1, ethers.ZeroHash, tsNs1)
        ).to.be.revertedWith("VPM: zero vpm hash");
    });

    it("6. anchor without ZKBA recorded reverts with 'VPM: zkba not anchored' (cross-contract integrity)", async function () {
        // mockAdj.setRecorded NOT called — zkbaHash1 returns false from isRecorded.
        await expect(
            registry.anchorVPM(zkbaHash1, vpmHash1, tsNs1)
        ).to.be.revertedWith("VPM: zkba not anchored");
    });

    it("7. anti-replay: duplicate vpmManifestHash reverts with 'VPM: already anchored'", async function () {
        await mockAdj.setRecorded(zkbaHash1, true);
        await registry.anchorVPM(zkbaHash1, vpmHash1, tsNs1);

        await expect(
            registry.anchorVPM(zkbaHash1, vpmHash1, tsNs2)
        ).to.be.revertedWith("VPM: already anchored");
    });

    it("8. multiple VPMs may wrap the same ZKBA; zkbaToVpms populated correctly", async function () {
        await mockAdj.setRecorded(zkbaHash1, true);
        await registry.anchorVPM(zkbaHash1, vpmHash1, tsNs1);
        await registry.anchorVPM(zkbaHash1, vpmHash2, tsNs2);
        await registry.anchorVPM(zkbaHash1, vpmHash3, tsNs2 + 1n);

        expect(await registry.getVpmsForZkbaCount(zkbaHash1)).to.equal(3n);
        expect(await registry.getVpmForZkbaAt(zkbaHash1, 0)).to.equal(vpmHash1);
        expect(await registry.getVpmForZkbaAt(zkbaHash1, 1)).to.equal(vpmHash2);
        expect(await registry.getVpmForZkbaAt(zkbaHash1, 2)).to.equal(vpmHash3);
    });

    it("9. distinct ZKBAs maintain independent VPM lists", async function () {
        await mockAdj.setRecorded(zkbaHash1, true);
        await mockAdj.setRecorded(zkbaHash2, true);
        await registry.anchorVPM(zkbaHash1, vpmHash1, tsNs1);
        await registry.anchorVPM(zkbaHash2, vpmHash2, tsNs1);

        expect(await registry.getVpmsForZkbaCount(zkbaHash1)).to.equal(1n);
        expect(await registry.getVpmsForZkbaCount(zkbaHash2)).to.equal(1n);
        expect(await registry.getVpmForZkbaAt(zkbaHash1, 0)).to.equal(vpmHash1);
        expect(await registry.getVpmForZkbaAt(zkbaHash2, 0)).to.equal(vpmHash2);
    });

    it("10. getVpmForZkbaAt out-of-bounds reverts with 'VPM: index OOB'", async function () {
        await mockAdj.setRecorded(zkbaHash1, true);
        await registry.anchorVPM(zkbaHash1, vpmHash1, tsNs1);
        await expect(
            registry.getVpmForZkbaAt(zkbaHash1, 5)
        ).to.be.revertedWith("VPM: index OOB");
    });

    it("11. non-owner anchorVPM reverts with OwnableUnauthorizedAccount", async function () {
        await mockAdj.setRecorded(zkbaHash1, true);
        await expect(
            registry.connect(nonOwner).anchorVPM(zkbaHash1, vpmHash1, tsNs1)
        ).to.be.revertedWithCustomError(registry, "OwnableUnauthorizedAccount");
    });

    it("12. isAnchored returns false for never-anchored VPM", async function () {
        const fakeVpm = ethers.keccak256(ethers.toUtf8Bytes("fake_vpm"));
        expect(await registry.isAnchored(fakeVpm)).to.equal(false);
    });

    it("13. getRecord returns zero-initialized struct for never-anchored VPM", async function () {
        const fakeVpm = ethers.keccak256(ethers.toUtf8Bytes("fake_vpm"));
        const rec = await registry.getRecord(fakeVpm);
        expect(rec.zkbaManifestHash).to.equal(ethers.ZeroHash);
        expect(rec.vpmManifestHash).to.equal(ethers.ZeroHash);
        expect(rec.tsNs).to.equal(0n);
        expect(rec.blockNumber).to.equal(0n);
    });

    it("14. adjudicationRegistry address is immutable post-deploy (no setter)", async function () {
        // Confirm there's no public mutator. Address-only property check.
        expect(registry.adjudicationRegistry).to.be.a("function");
        // Attempt to call non-existent setter must fail at the ABI layer.
        expect(registry.setAdjudicationRegistry).to.equal(undefined);
    });
});
