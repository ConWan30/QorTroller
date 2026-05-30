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
// Dimension 8 (Arc 5) fields default to a NO-VHR-OPT-IN posture: allowReplayProofs
// false, threshold at the AIT default 70 (×100), quantization at the FROZEN floor,
// require-verdict on. Existing v1 tests pass through unchanged.
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
    // Dimension 8 (Arc 5) defaults
    allowReplayProofs:          false,
    replayHumanityThreshold:    70,   // 0.70 AIT floor on ×100 scale
    replayQuantizationBits:     4,    // == REPLAY_QUANTIZATION_BITS_FLOOR
    replayRequireVerdict:       true,
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

  // ── Dimension 8 (Arc 5) ───────────────────────────────────────────────

  it("T239-CM-D8-1: REPLAY_QUANTIZATION_BITS_FLOOR constant pinned at 4", async function () {
    expect(await reg.REPLAY_QUANTIZATION_BITS_FLOOR()).to.equal(4n);
  });

  it("T239-CM-D8-2: defaults — allowReplayProofs false; replay-require-verdict true; threshold 70; bits 4", async function () {
    const m = manifest();
    expect(m.allowReplayProofs).to.equal(false);
    expect(m.replayRequireVerdict).to.equal(true);
    expect(m.replayHumanityThreshold).to.equal(70);
    expect(m.replayQuantizationBits).to.equal(4);
    // Round-trip through storage.
    await reg.connect(gamer1).setManifest(m);
    const s = await reg.getManifest(gamer1.address);
    expect(s.allowReplayProofs).to.equal(false);
    expect(s.replayRequireVerdict).to.equal(true);
    expect(s.replayHumanityThreshold).to.equal(70n);
    expect(s.replayQuantizationBits).to.equal(4n);
  });

  it("T239-CM-D8-3: setManifest reverts when replayQuantizationBits < floor (=4)", async function () {
    await expect(
      reg.connect(gamer1).setManifest(manifest({ replayQuantizationBits: 3 }))
    ).to.be.revertedWith("VCMR: replayQuantizationBits must equal floor");
  });

  it("T239-CM-D8-4: setManifest reverts when replayQuantizationBits > floor (=5)", async function () {
    await expect(
      reg.connect(gamer1).setManifest(manifest({ replayQuantizationBits: 5 }))
    ).to.be.revertedWith("VCMR: replayQuantizationBits must equal floor");
  });

  it("T239-CM-D8-5: setManifest reverts when replayHumanityThreshold > 100 (×100 scale)", async function () {
    await expect(
      reg.connect(gamer1).setManifest(manifest({ replayHumanityThreshold: 101 }))
    ).to.be.revertedWith("VCMR: replayHumanityThreshold > 1.00");
  });

  it("T239-CM-D8-6: manifestHash includes Dimension 8 — toggling allowReplayProofs changes hash", async function () {
    const m_off = manifest({ allowReplayProofs: false });
    const m_on  = manifest({ allowReplayProofs: true  });
    const h_off = await reg.computeManifestHash(m_off);
    const h_on  = await reg.computeManifestHash(m_on);
    expect(h_off).to.not.equal(h_on);
  });

  it("T239-CM-D8-7: manifestHash includes Dimension 8 — flipping replayRequireVerdict changes hash", async function () {
    const m_a = manifest({ replayRequireVerdict: true  });
    const m_b = manifest({ replayRequireVerdict: false });
    expect(await reg.computeManifestHash(m_a)).to.not.equal(await reg.computeManifestHash(m_b));
  });

  it("T239-CM-D8-8: enabling replay proofs round-trips through getManifest", async function () {
    const m = manifest({ allowReplayProofs: true, replayHumanityThreshold: 85 });
    await reg.connect(gamer1).setManifest(m);
    const s = await reg.getManifest(gamer1.address);
    expect(s.allowReplayProofs).to.equal(true);
    expect(s.replayHumanityThreshold).to.equal(85n);
  });
});

// Helper: match the blockNumber arg without pinning an exact value.
function anyValueBlock() {
  const { anyValue } = require("@nomicfoundation/hardhat-chai-matchers/withArgs");
  return anyValue;
}
