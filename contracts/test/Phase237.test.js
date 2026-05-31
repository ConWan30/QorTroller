/**
 * Phase 237 — VAPIConsentRegistry Hardhat Tests (6 tests)
 *
 *   T237-HH-1: Deploy + owner check + totalGrants=0
 *   T237-HH-2: grantConsent stores record, emits ConsentGranted, increments totalGrants
 *   T237-HH-3: Anti-replay — duplicate consentHash reverts (across all senders)
 *   T237-HH-4: revokeConsent flips revoked=true; isConsentValid → false; expired
 *              consent (block.timestamp >= expiresAt) → isConsentValid false
 *   T237-HH-5: setIoIDRegistry — owner-only; zero-address reverts
 *   T237-HH-6: Bad inputs revert (zero consentHash, out-of-range category,
 *              double-revoke, no-consent-to-revoke)
 */

const { expect } = require("chai");
const { ethers } = require("hardhat");

const TOURNAMENT_GATE     = 0;
const ANONYMIZED_RESEARCH = 1;
const MANUFACTURER_CERT   = 2;
const MARKETPLACE         = 3;

describe("VAPIConsentRegistry (Phase 237)", function () {
  let vcr, owner, gamer1, gamer2, otherAddr;

  beforeEach(async function () {
    [owner, gamer1, gamer2, otherAddr] = await ethers.getSigners();
    const Factory = await ethers.getContractFactory("VAPIConsentRegistry");
    vcr = await Factory.deploy(owner.address);
    await vcr.waitForDeployment();
  });

  it("T237-HH-1: deploys with correct owner and totalGrants=0", async function () {
    expect(await vcr.owner()).to.equal(owner.address);
    expect(await vcr.totalGrants()).to.equal(0n);
    expect(await vcr.ioidRegistry()).to.equal(ethers.ZeroAddress);
  });

  it("T237-HH-2: grantConsent stores record and emits ConsentGranted", async function () {
    const consentHash = ethers.keccak256(ethers.toUtf8Bytes("consent-1"));
    const blockTs = (await ethers.provider.getBlock("latest")).timestamp;
    const expiresAt   = BigInt(blockTs) + 86400n;

    const tx = await vcr.connect(gamer1).grantConsent(
      TOURNAMENT_GATE, expiresAt, consentHash
    );
    await expect(tx)
      .to.emit(vcr, "ConsentGranted")
      .withArgs(
        gamer1.address,
        TOURNAMENT_GATE,
        consentHash,
        expiresAt,
        await ethers.provider.getBlockNumber()
      );

    expect(await vcr.totalGrants()).to.equal(1n);
    expect(await vcr.isRecorded(consentHash)).to.equal(true);
    expect(await vcr.isConsentValid(gamer1.address, TOURNAMENT_GATE)).to.equal(true);

    const rec = await vcr.getConsentRecord(gamer1.address, TOURNAMENT_GATE);
    expect(rec.consentHash).to.equal(consentHash);
    expect(rec.expiresAt).to.equal(expiresAt);
    expect(rec.revoked).to.equal(false);

    // Other category for same gamer NOT granted
    expect(await vcr.isConsentValid(gamer1.address, MARKETPLACE)).to.equal(false);
  });

  it("T237-HH-3: anti-replay — duplicate consentHash reverts (across senders)", async function () {
    const consentHash = ethers.keccak256(ethers.toUtf8Bytes("consent-shared"));
    const blockTs = (await ethers.provider.getBlock("latest")).timestamp;
    const expiresAt   = BigInt(blockTs) + 3600n;

    await vcr.connect(gamer1).grantConsent(TOURNAMENT_GATE, expiresAt, consentHash);

    // Same gamer / category — duplicate hash blocked
    await expect(
      vcr.connect(gamer1).grantConsent(TOURNAMENT_GATE, expiresAt, consentHash)
    ).to.be.revertedWith("VCR: duplicate consentHash");

    // Different gamer / category — duplicate hash STILL blocked (cross-sender)
    await expect(
      vcr.connect(gamer2).grantConsent(MARKETPLACE, expiresAt, consentHash)
    ).to.be.revertedWith("VCR: duplicate consentHash");
  });

  it("T237-HH-4: revokeConsent + expired consent → isConsentValid false", async function () {
    const consentHash = ethers.keccak256(ethers.toUtf8Bytes("consent-rev"));
    const blockTs = (await ethers.provider.getBlock("latest")).timestamp;
    const farFuture   = BigInt(blockTs) + 365n * 86400n;

    await vcr.connect(gamer1).grantConsent(MARKETPLACE, farFuture, consentHash);
    expect(await vcr.isConsentValid(gamer1.address, MARKETPLACE)).to.equal(true);

    const tx = await vcr.connect(gamer1).revokeConsent(MARKETPLACE);
    await expect(tx).to.emit(vcr, "ConsentRevoked")
      .withArgs(gamer1.address, MARKETPLACE, consentHash, await ethers.provider.getBlockNumber());

    expect(await vcr.isConsentValid(gamer1.address, MARKETPLACE)).to.equal(false);
    const rec = await vcr.getConsentRecord(gamer1.address, MARKETPLACE);
    expect(rec.revoked).to.equal(true);

    // Expiry test: grant ANONYMIZED_RESEARCH expiring in 1s, advance time, verify invalid
    const consentHash2 = ethers.keccak256(ethers.toUtf8Bytes("consent-soon"));
    const block = await ethers.provider.getBlock("latest");
    const soonExpiry = BigInt(block.timestamp) + 2n;
    await vcr.connect(gamer2).grantConsent(ANONYMIZED_RESEARCH, soonExpiry, consentHash2);
    expect(await vcr.isConsentValid(gamer2.address, ANONYMIZED_RESEARCH)).to.equal(true);

    // Mine forward past the expiry
    await ethers.provider.send("evm_increaseTime", [10]);
    await ethers.provider.send("evm_mine", []);
    expect(await vcr.isConsentValid(gamer2.address, ANONYMIZED_RESEARCH)).to.equal(false);
  });

  it("T237-HH-5: setIoIDRegistry — owner-only and zero-address guard", async function () {
    // Non-owner cannot set
    await expect(
      vcr.connect(gamer1).setIoIDRegistry(otherAddr.address)
    ).to.be.revertedWithCustomError(vcr, "OwnableUnauthorizedAccount");

    // Zero-address reverts even from owner
    await expect(
      vcr.connect(owner).setIoIDRegistry(ethers.ZeroAddress)
    ).to.be.revertedWith("VCR: zero ioidRegistry");

    // Owner can set valid address
    const tx = await vcr.connect(owner).setIoIDRegistry(otherAddr.address);
    await expect(tx).to.emit(vcr, "IoIDRegistrySet")
      .withArgs(ethers.ZeroAddress, otherAddr.address);
    expect(await vcr.ioidRegistry()).to.equal(otherAddr.address);
  });

  it("T237-HH-6: bad inputs revert (zero hash / bad category / double-revoke)", async function () {
    const validHash = ethers.keccak256(ethers.toUtf8Bytes("v"));
    const blockTs = (await ethers.provider.getBlock("latest")).timestamp;
    const expiresAt = BigInt(blockTs) + 3600n;

    // Zero consentHash
    await expect(
      vcr.connect(gamer1).grantConsent(TOURNAMENT_GATE, expiresAt, ethers.ZeroHash)
    ).to.be.revertedWith("VCR: zero consentHash");

    // Out-of-range category
    await expect(
      vcr.connect(gamer1).grantConsent(99, expiresAt, validHash)
    ).to.be.revertedWith("VCR: bad category");

    // Revoke without prior consent
    await expect(
      vcr.connect(gamer1).revokeConsent(MANUFACTURER_CERT)
    ).to.be.revertedWith("VCR: no consent to revoke");

    // Grant + double-revoke
    await vcr.connect(gamer1).grantConsent(TOURNAMENT_GATE, expiresAt, validHash);
    await vcr.connect(gamer1).revokeConsent(TOURNAMENT_GATE);
    await expect(
      vcr.connect(gamer1).revokeConsent(TOURNAMENT_GATE)
    ).to.be.revertedWith("VCR: already revoked");

    // Out-of-range category in views returns safe defaults (no revert)
    expect(await vcr.isConsentValid(gamer1.address, 99)).to.equal(false);
    const rec = await vcr.getConsentRecord(gamer1.address, 99);
    expect(rec.consentHash).to.equal(ethers.ZeroHash);
  });
});
