const { expect } = require("chai");
const { ethers } = require("hardhat");

/**
 * Phase 113 — VAPIDualPrimitiveGate
 * Dual-primitive composability gate: PoAC (isFullyEligible) + PoAd (isRecorded).
 * Uses MockProtocolLens102 (setEligible/isFullyEligible) + AdjudicationRegistry (Phase 111).
 */
describe("Phase113 — VAPIDualPrimitiveGate dual-primitive composability gate", function () {
    let gate, mockLens, registry, owner;

    const deviceIdHash = ethers.keccak256(ethers.toUtf8Bytes("device_phase113_1"));
    const poadHash     = ethers.keccak256(ethers.toUtf8Bytes("poad_bundle_phase113_1"));

    beforeEach(async function () {
        [owner] = await ethers.getSigners();

        const MockLens = await ethers.getContractFactory("MockProtocolLens102");
        mockLens = await MockLens.deploy();
        await mockLens.waitForDeployment();

        const Registry = await ethers.getContractFactory("AdjudicationRegistry");
        registry = await Registry.deploy();
        await registry.waitForDeployment();

        const GateFactory = await ethers.getContractFactory("VAPIDualPrimitiveGate");
        gate = await GateFactory.deploy(
            await mockLens.getAddress(),
            await registry.getAddress()
        );
        await gate.waitForDeployment();
    });

    it("1. isDualEligible returns (true, true, true) when both PoAC and PoAd valid", async function () {
        await mockLens.setEligible(true);
        await registry.recordAdjudication(deviceIdHash, poadHash, false);

        const [eligible, poac_valid, poad_valid] = await gate.isDualEligible(deviceIdHash, poadHash);
        expect(eligible).to.equal(true);
        expect(poac_valid).to.equal(true);
        expect(poad_valid).to.equal(true);
    });

    it("2. isDualEligible returns (false, false, true) when only poad_valid (PoAC fails)", async function () {
        await mockLens.setEligible(false);
        await registry.recordAdjudication(deviceIdHash, poadHash, false);

        const [eligible, poac_valid, poad_valid] = await gate.isDualEligible(deviceIdHash, poadHash);
        expect(eligible).to.equal(false);
        expect(poac_valid).to.equal(false);
        expect(poad_valid).to.equal(true);
    });

    it("3. isDualEligible returns (false, true, false) when only poac_valid (PoAd not recorded)", async function () {
        await mockLens.setEligible(true);
        // poadHash not recorded in registry

        const [eligible, poac_valid, poad_valid] = await gate.isDualEligible(deviceIdHash, poadHash);
        expect(eligible).to.equal(false);
        expect(poac_valid).to.equal(true);
        expect(poad_valid).to.equal(false);
    });

    it("4. isDualEligible returns (false, false, false) when neither primitive valid", async function () {
        await mockLens.setEligible(false);
        // poadHash not recorded

        const [eligible, poac_valid, poad_valid] = await gate.isDualEligible(deviceIdHash, poadHash);
        expect(eligible).to.equal(false);
        expect(poac_valid).to.equal(false);
        expect(poad_valid).to.equal(false);
    });

    it("5. constructor reverts on zero protocolLens address", async function () {
        const GateFactory = await ethers.getContractFactory("VAPIDualPrimitiveGate");
        await expect(
            GateFactory.deploy(ethers.ZeroAddress, await registry.getAddress())
        ).to.be.revertedWith("VAPIDualPrimitiveGate: zero protocolLens");
    });

    it("6. constructor stores protocolLens and adjudicationRegistry as immutables", async function () {
        const storedLens = await gate.protocolLens();
        const storedReg  = await gate.adjudicationRegistry();
        expect(storedLens).to.equal(await mockLens.getAddress());
        expect(storedReg).to.equal(await registry.getAddress());
    });
});
