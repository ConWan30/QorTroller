/**
 * Phase O4-VPM-ANCHOR-INT — VPMAnchorRegistry full-pipeline integration test
 *
 * Stream C.1 of the post-O4 v4 §15 wallet-free backlog closure plan.
 *
 * The existing test_t_vpm_anchor_*.js band exercises VPMAnchorRegistry
 * in isolation against MockAdjudicationRegistry_VPM. This integration
 * test exercises the FULL Phase 111 (AdjudicationRegistry) + Phase O4
 * (VPMAnchorRegistry) composition end-to-end:
 *
 *   1. Deploy real AdjudicationRegistry (Phase 111 contract)
 *   2. Deploy VPMAnchorRegistry pinned to that AdjudicationRegistry
 *   3. Anchor a synthetic ZKBA hash via AdjudicationRegistry.recordAdjudication
 *   4. Anchor a synthetic VPM that wraps it via VPMAnchorRegistry.anchorVPM
 *   5. Cross-verify: VPMAnchorRegistry.isAnchored(vpm) → true
 *      AND VPMAnchorRegistry.getVpmsForZkbaCount(zkba) → 1
 *      AND AdjudicationRegistry.isRecorded(zkba) → true
 *   6. Negative test: VPM anchoring with un-anchored ZKBA reverts with
 *      'VPM: zkba not anchored' (cross-contract integrity at write time)
 *
 * Catches deploy-time integration bugs ahead of the operator three-
 * factor deploy ceremony per wiki/runbooks/
 * vpm_anchor_registry_deploy_runbook.md.
 */
const { expect } = require("chai");
const { ethers } = require("hardhat");

describe("Phase O4-VPM-ANCHOR-INT — VPMAnchorRegistry + AdjudicationRegistry composition", function () {
    let adjReg;
    let vpmReg;
    let owner;
    let nonOwner;

    const zkbaHash1 = ethers.keccak256(ethers.toUtf8Bytes("zkba_int_001"));
    const zkbaHash2 = ethers.keccak256(ethers.toUtf8Bytes("zkba_int_002"));
    const vpmHash1  = ethers.keccak256(ethers.toUtf8Bytes("vpm_int_001"));
    const vpmHash2  = ethers.keccak256(ethers.toUtf8Bytes("vpm_int_002"));
    const deviceHash1 = ethers.keccak256(ethers.toUtf8Bytes("device_int_001"));
    const tsNs1     = 1778900000000000000n;
    const tsNs2     = 1778900100000000000n;

    beforeEach(async function () {
        [owner, nonOwner] = await ethers.getSigners();

        // 1. Deploy real Phase 111 AdjudicationRegistry
        const AdjReg = await ethers.getContractFactory("AdjudicationRegistry");
        adjReg = await AdjReg.deploy();
        await adjReg.waitForDeployment();

        // 2. Deploy VPMAnchorRegistry pinned to the real AdjudicationRegistry
        const VpmReg = await ethers.getContractFactory("VPMAnchorRegistry");
        vpmReg = await VpmReg.deploy(await adjReg.getAddress());
        await vpmReg.waitForDeployment();
    });

    it("1. integration deploy: both contracts deploy + VPMAnchorRegistry pinned to real AdjudicationRegistry", async function () {
        expect(await adjReg.getAddress()).to.be.properAddress;
        expect(await vpmReg.getAddress()).to.be.properAddress;
        expect(await vpmReg.adjudicationRegistry()).to.equal(
            await adjReg.getAddress()
        );
        expect(await adjReg.totalAdjudications()).to.equal(0n);
        expect(await vpmReg.totalAnchored()).to.equal(0n);
    });

    it("2. end-to-end happy path: anchor ZKBA via Phase 111, then VPM wrapping it via Phase O4", async function () {
        // Anchor the ZKBA via real recordAdjudication (3-arg legacy ABI)
        await adjReg.recordAdjudication(deviceHash1, zkbaHash1, false);
        expect(await adjReg.isRecorded(zkbaHash1)).to.equal(true);

        // Anchor the VPM that wraps it — cross-contract integrity check
        // should PASS because zkbaHash1 is now recorded in adjReg.
        await expect(vpmReg.anchorVPM(zkbaHash1, vpmHash1, tsNs1))
            .to.emit(vpmReg, "VPMAnchored");

        // Cross-verify all three views
        expect(await vpmReg.isAnchored(vpmHash1)).to.equal(true);
        expect(await vpmReg.getVpmsForZkbaCount(zkbaHash1)).to.equal(1n);
        expect(await vpmReg.getVpmForZkbaAt(zkbaHash1, 0)).to.equal(vpmHash1);
        expect(await adjReg.isRecorded(zkbaHash1)).to.equal(true);
        expect(await vpmReg.totalAnchored()).to.equal(1n);
    });

    it("3. cross-contract integrity ENFORCEMENT: anchoring VPM for un-recorded ZKBA reverts at write time", async function () {
        // Do NOT recordAdjudication first — zkbaHash1 has NEVER been anchored
        expect(await adjReg.isRecorded(zkbaHash1)).to.equal(false);

        // anchorVPM MUST revert with the cross-contract integrity error
        await expect(
            vpmReg.anchorVPM(zkbaHash1, vpmHash1, tsNs1)
        ).to.be.revertedWith("VPM: zkba not anchored");

        // Confirm no state was mutated on revert
        expect(await vpmReg.isAnchored(vpmHash1)).to.equal(false);
        expect(await vpmReg.totalAnchored()).to.equal(0n);
        expect(await vpmReg.getVpmsForZkbaCount(zkbaHash1)).to.equal(0n);
    });

    it("4. multiple VPMs may wrap the same anchored ZKBA — zkbaToVpms scales", async function () {
        await adjReg.recordAdjudication(deviceHash1, zkbaHash1, false);

        await vpmReg.anchorVPM(zkbaHash1, vpmHash1, tsNs1);
        await vpmReg.anchorVPM(zkbaHash1, vpmHash2, tsNs2);

        expect(await vpmReg.getVpmsForZkbaCount(zkbaHash1)).to.equal(2n);
        expect(await vpmReg.getVpmForZkbaAt(zkbaHash1, 0)).to.equal(vpmHash1);
        expect(await vpmReg.getVpmForZkbaAt(zkbaHash1, 1)).to.equal(vpmHash2);
        expect(await vpmReg.totalAnchored()).to.equal(2n);
    });

    it("5. distinct ZKBAs maintain independent VPM lists post real Phase 111 anchoring", async function () {
        await adjReg.recordAdjudication(deviceHash1, zkbaHash1, false);
        await adjReg.recordAdjudication(deviceHash1, zkbaHash2, true);

        await vpmReg.anchorVPM(zkbaHash1, vpmHash1, tsNs1);
        await vpmReg.anchorVPM(zkbaHash2, vpmHash2, tsNs2);

        expect(await vpmReg.getVpmsForZkbaCount(zkbaHash1)).to.equal(1n);
        expect(await vpmReg.getVpmsForZkbaCount(zkbaHash2)).to.equal(1n);
        expect(await vpmReg.getVpmForZkbaAt(zkbaHash1, 0)).to.equal(vpmHash1);
        expect(await vpmReg.getVpmForZkbaAt(zkbaHash2, 0)).to.equal(vpmHash2);
    });

    it("6. anti-replay survives real Phase 111 anchoring path — duplicate vpmHash reverts", async function () {
        await adjReg.recordAdjudication(deviceHash1, zkbaHash1, false);
        await vpmReg.anchorVPM(zkbaHash1, vpmHash1, tsNs1);

        await expect(
            vpmReg.anchorVPM(zkbaHash1, vpmHash1, tsNs2)
        ).to.be.revertedWith("VPM: already anchored");
    });

    it("7. ownership boundary preserved across integration — non-owner cannot anchorVPM even when ZKBA is recorded", async function () {
        await adjReg.recordAdjudication(deviceHash1, zkbaHash1, false);

        await expect(
            vpmReg.connect(nonOwner).anchorVPM(zkbaHash1, vpmHash1, tsNs1)
        ).to.be.revertedWithCustomError(vpmReg, "OwnableUnauthorizedAccount");
    });

    it("8. compose with anchorAdjudication (sourceType-tagged) — both ZKBA-anchoring paths feed VPMAnchorRegistry equally", async function () {
        // Use the SOURCE-TAGGED anchorAdjudication path (Phase 237.5 Path X)
        await adjReg["anchorAdjudication(bytes32,string)"](
            zkbaHash1,
            "INTEGRATION_TEST"
        );
        expect(await adjReg.isRecorded(zkbaHash1)).to.equal(true);
        expect(await adjReg.getSourceType(zkbaHash1)).to.equal("INTEGRATION_TEST");

        // VPMAnchorRegistry doesn't care about sourceType — only isRecorded
        await vpmReg.anchorVPM(zkbaHash1, vpmHash1, tsNs1);
        expect(await vpmReg.isAnchored(vpmHash1)).to.equal(true);
    });
});
