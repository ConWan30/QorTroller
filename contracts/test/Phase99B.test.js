/**
 * Phase 99B — VAPIGSRRegistry Tests
 *
 * 4 tests:
 *   T99B-1: recordSample() stores correctly — getLatestSample() returns values
 *   T99B-2: recordSample() duplicate (deviceId, timestamp) reverts "duplicate timestamp"
 *   T99B-3: recordSample() by non-owner reverts OwnableUnauthorizedAccount
 *   T99B-4: getSampleCount() increments on each recordSample() call
 *
 * GSR_ENABLED=false in bridge — code-before-hardware, advisory layer only.
 * On-chain registry is the tamper-evident anchor for W3bstream WASM applet output.
 *
 * Hardhat count: 420 → 424 (+4)
 */

const { expect } = require("chai");
const { ethers } = require("hardhat");

describe("Phase 99B — VAPIGSRRegistry", function () {

    let owner, alice;
    let registry;
    let deviceId;
    const TS1 = 1700000000n;  // fixed unix timestamp for deterministic tests
    const TS2 = 1700000030n;  // +30s sample

    beforeEach(async function () {
        [owner, alice] = await ethers.getSigners();
        const Factory = await ethers.getContractFactory("VAPIGSRRegistry");
        registry = await Factory.deploy(owner.address);
        await registry.waitForDeployment();
        // deviceId = keccak256("test_device_99b")
        deviceId = ethers.keccak256(ethers.toUtf8Bytes("test_device_99b"));
    });

    it("T99B-1: recordSample() stores correctly — getLatestSample() returns values", async function () {
        const arousal    = 450n;  // 0.450 sympathetic_arousal_index
        const correlation = 650n; // (0.30 + 1.0) * 500 = 650

        await registry.recordSample(deviceId, arousal, correlation, TS1);

        const [gotArousal, gotCorr, gotTs] = await registry.getLatestSample(deviceId);
        expect(gotArousal).to.equal(arousal);
        expect(gotCorr).to.equal(correlation);
        // recordedAt is block.timestamp — just verify it's nonzero
        expect(gotTs).to.be.greaterThan(0n);

        // latestTimestamp mapping updated
        expect(await registry.latestTimestamp(deviceId)).to.equal(TS1);
    });

    it("T99B-2: recordSample() duplicate (deviceId, timestamp) reverts", async function () {
        await registry.recordSample(deviceId, 300n, 500n, TS1);

        // Same deviceId + same timestamp → revert
        await expect(
            registry.recordSample(deviceId, 400n, 600n, TS1)
        ).to.be.revertedWith("VAPIGSRRegistry: duplicate timestamp");

        // Different timestamp → should succeed
        await registry.recordSample(deviceId, 400n, 600n, TS2);
        expect(await registry.getSampleCount(deviceId)).to.equal(2n);
    });

    it("T99B-3: recordSample() by non-owner reverts OwnableUnauthorizedAccount", async function () {
        await expect(
            registry.connect(alice).recordSample(deviceId, 300n, 500n, TS1)
        ).to.be.revertedWithCustomError(registry, "OwnableUnauthorizedAccount");
    });

    it("T99B-4: getSampleCount() increments on each recordSample()", async function () {
        expect(await registry.getSampleCount(deviceId)).to.equal(0n);

        await registry.recordSample(deviceId, 200n, 400n, TS1);
        expect(await registry.getSampleCount(deviceId)).to.equal(1n);

        await registry.recordSample(deviceId, 300n, 550n, TS2);
        expect(await registry.getSampleCount(deviceId)).to.equal(2n);

        // Second device is independent
        const deviceId2 = ethers.keccak256(ethers.toUtf8Bytes("test_device_99b_v2"));
        await registry.recordSample(deviceId2, 100n, 450n, TS1);
        expect(await registry.getSampleCount(deviceId)).to.equal(2n);  // unchanged
        expect(await registry.getSampleCount(deviceId2)).to.equal(1n);
    });
});
