/**
 * Data Economy Arc 4 — VAPIConsentManifestRegistry Hardhat Tests (10 tests)
 *
 * Structured 7-dimension consent manifest, ADDITIVE to the deployed
 * VAPIConsentRegistry bitmask surface (Phase 237). The FROZEN VAPI-CONSENT-v1
 * formula + ConsentCategory enum are untouched — this is a SEPARATE contract
 * (SeparationRatioRegistry redeploy precedent), so the bitmask surface stays
 * callable and is not exercised here.
 *
 *   T239-CM-1 : deploy + owner + totalManifests=0 + floor constants
 *   T239-CM-2 : setManifest stores, stamps updatedAt + manifestHash, emits event
 *   T239-CM-3 : aggregation floor — minSessionsPerPackage < 10 reverts
 *   T239-CM-4 : cooling floor — coolingPeriodHours < 72 reverts
 *   T239-CM-5 : autonomyLevel > 3 reverts; listingType > 1 reverts
 *   T239-CM-6 : getManifest round-trips all 7 dimensions; hasManifest toggles
 *   T239-CM-7 : computeManifestHash deterministic + ignores caller versioning fields
 *   T239-CM-8 : manifestHash changes when a policy field changes
 *   T239-CM-9 : self-sovereignty — each gamer writes only their own manifest
 *   T239-CM-10: re-setManifest overwrites in place (totalManifests increments)
 */

const { expect } = require("chai");
const { ethers } = require("hardhat");

// Manifest struct field order MUST match ConsentManifest in the contract.
function manifest(overrides = {}) {
  return {
    allowAggregateStats:        true,
    allowSkillRankingProof:     true,
    allowTrajectoryProof:       true,
    allowContextPerformanceProof: false,
    allowFullSessionProof:      false,
    allowAcademic:              true,
    allowGameDev:               true,
    allowEsports:               false,
    allowBrand:                 false,
    allowAnonymous:             false,
    minSessionsPerPackage:      10,
    coolingPeriodHours:         72,
    minPriceVapi:               1000n,
    listingType:                0,
    autonomyLevel:              1,
    updatedAt:                  0,
    manifestHash:               ethers.ZeroHash,
    ...overrides,
  };
}

describe("VAPIConsentManifestRegistry (Data Economy Arc 4)", function () {
  let reg, owner, gamer1, gamer2;

  beforeEach(async function () {
    [owner, gamer1, gamer2] = await ethers.getSigners();
    const Factory = await ethers.getContractFactory("VAPIConsentManifestRegistry");
    reg = await Factory.deploy(owner.address);
    await reg.waitForDeployment();
  });

  it("T239-CM-1: deploys with owner, totalManifests=0, floor constants pinned", async function () {
    expect(await reg.owner()).to.equal(owner.address);
    expect(await reg.totalManifests()).to.equal(0n);
    expect(await reg.MIN_SESSIONS_FLOOR()).to.equal(10n);
    expect(await reg.COOLING_HOURS_FLOOR()).to.equal(72n);
    expect(await reg.AUTONOMY_MAX()).to.equal(3n);
  });

  it("T239-CM-2: setManifest stores, stamps manifestHash, emits ManifestUpdated", async function () {
    const m = manifest();
    const expectedHash = await reg.computeManifestHash(m);

    const tx = await reg.connect(gamer1).setManifest(m);
    await expect(tx)
      .to.emit(reg, "ManifestUpdated")
      .withArgs(gamer1.address, expectedHash, 1, 10, 72, anyValueBlock());

    expect(await reg.totalManifests()).to.equal(1n);
    expect(await reg.hasManifest(gamer1.address)).to.equal(true);

    const stored = await reg.getManifest(gamer1.address);
    expect(stored.manifestHash).to.equal(expectedHash);
    expect(stored.updatedAt).to.be.greaterThan(0n);
  });

  it("T239-CM-3: aggregation floor — minSessionsPerPackage < 10 reverts", async function () {
    const m = manifest({ minSessionsPerPackage: 9 });
    await expect(reg.connect(gamer1).setManifest(m))
      .to.be.revertedWith("VCMR: aggregation floor (min 10 sessions)");
  });

  it("T239-CM-4: cooling floor — coolingPeriodHours < 72 reverts", async function () {
    const m = manifest({ coolingPeriodHours: 71 });
    await expect(reg.connect(gamer1).setManifest(m))
      .to.be.revertedWith("VCMR: cooling floor (min 72 hours)");
  });

  it("T239-CM-5: autonomyLevel > 3 reverts; listingType > 1 reverts", async function () {
    await expect(reg.connect(gamer1).setManifest(manifest({ autonomyLevel: 4 })))
      .to.be.revertedWith("VCMR: bad autonomyLevel");
    await expect(reg.connect(gamer1).setManifest(manifest({ listingType: 2 })))
      .to.be.revertedWith("VCMR: bad listingType");
  });

  it("T239-CM-6: getManifest round-trips all 7 dimensions; hasManifest toggles", async function () {
    expect(await reg.hasManifest(gamer1.address)).to.equal(false);

    const m = manifest({
      allowContextPerformanceProof: true,
      allowFullSessionProof:        true,
      allowEsports:                 true,
      allowBrand:                   true,
      allowAnonymous:               true,
      minSessionsPerPackage:        25,
      coolingPeriodHours:           120,
      minPriceVapi:                 5000n,
      listingType:                  1,
      autonomyLevel:                3,
    });
    await reg.connect(gamer1).setManifest(m);
    const s = await reg.getManifest(gamer1.address);

    expect(s.allowAggregateStats).to.equal(true);
    expect(s.allowContextPerformanceProof).to.equal(true);
    expect(s.allowFullSessionProof).to.equal(true);
    expect(s.allowEsports).to.equal(true);
    expect(s.allowBrand).to.equal(true);
    expect(s.allowAnonymous).to.equal(true);
    expect(s.minSessionsPerPackage).to.equal(25n);
    expect(s.coolingPeriodHours).to.equal(120n);
    expect(s.minPriceVapi).to.equal(5000n);
    expect(s.listingType).to.equal(1n);
    expect(s.autonomyLevel).to.equal(3n);
    expect(await reg.hasManifest(gamer1.address)).to.equal(true);
  });

  it("T239-CM-7: computeManifestHash deterministic + ignores updatedAt/manifestHash", async function () {
    const a = manifest({ updatedAt: 0, manifestHash: ethers.ZeroHash });
    const b = manifest({
      updatedAt:    999999,
      manifestHash: ethers.keccak256(ethers.toUtf8Bytes("garbage")),
    });
    // Same policy fields, different (ignored) versioning fields → identical hash.
    expect(await reg.computeManifestHash(a)).to.equal(await reg.computeManifestHash(b));
  });

  it("T239-CM-8: manifestHash changes when a policy field changes", async function () {
    const h1 = await reg.computeManifestHash(manifest({ minPriceVapi: 1000n }));
    const h2 = await reg.computeManifestHash(manifest({ minPriceVapi: 2000n }));
    expect(h1).to.not.equal(h2);
  });

  it("T239-CM-9: self-sovereignty — each gamer writes only their own manifest", async function () {
    await reg.connect(gamer1).setManifest(manifest({ minPriceVapi: 111n }));
    await reg.connect(gamer2).setManifest(manifest({ minPriceVapi: 222n }));

    expect((await reg.getManifest(gamer1.address)).minPriceVapi).to.equal(111n);
    expect((await reg.getManifest(gamer2.address)).minPriceVapi).to.equal(222n);
    // No setter takes a target address — a gamer cannot write another's manifest.
  });

  it("T239-CM-10: re-setManifest overwrites in place + increments totalManifests", async function () {
    await reg.connect(gamer1).setManifest(manifest({ autonomyLevel: 1 }));
    await reg.connect(gamer1).setManifest(manifest({ autonomyLevel: 2 }));

    expect(await reg.totalManifests()).to.equal(2n);
    expect((await reg.getManifest(gamer1.address)).autonomyLevel).to.equal(2n);
  });
});

// Helper: match the blockNumber arg without pinning an exact value.
function anyValueBlock() {
  const { anyValue } = require("@nomicfoundation/hardhat-chai-matchers/withArgs");
  return anyValue;
}
