/**
 * Phase 178 — SeparationRatioRegistry (renewCommit + ttlDays) Hardhat Tests (6 tests)
 *
 * Tests the Phase 178 additions to SeparationRatioRegistry.sol:
 *   - ttlDays field on RatioCommit struct
 *   - renewCommit() function with anti-replay UNIQUE(newCommitHash) guard
 *   - prevCommitHash linkage
 *   - onlyOwner access control on renewCommit
 *   - RatioRenewed event emitted
 *   - zero-ttlDays guard (must be > 0 on renewal)
 *
 * T178-1: commitRatio stores ttlDays=0 and prevCommitHash=0x0 (backward compat)
 * T178-2: renewCommit succeeds and emits RatioRenewed event
 * T178-3: renewCommit anti-replay — duplicate newCommitHash reverts
 * T178-4: renewCommit onlyOwner — non-owner reverts OwnableUnauthorizedAccount
 * T178-5: renewCommit stores ttlDays and prevCommitHash correctly
 * T178-6: renewCommit reverts when ttlDays = 0 (zero-TTL guard)
 */

const { expect } = require("chai");
const { ethers } = require("hardhat");

describe("SeparationRatioRegistry Phase 178 (renewCommit + ttlDays)", function () {
  let registry, owner, nonOwner;
  let initialHash;

  beforeEach(async function () {
    [owner, nonOwner] = await ethers.getSigners();
    const Factory = await ethers.getContractFactory("SeparationRatioRegistry");
    registry = await Factory.deploy(owner.address);
    await registry.waitForDeployment();

    // Establish an initial commitment as the "prev" for renewal tests
    initialHash = ethers.keccak256(ethers.toUtf8Bytes("ratio=0.569:N=20:P1P2P3:ts=1000"));
    await registry.commitRatio(initialHash, 569n, 20, 3);
  });

  it("T178-1: commitRatio stores ttlDays=0 and prevCommitHash=bytes32(0) for backward compat", async function () {
    const latest = await registry.getLatestCommit();
    expect(latest.commitHash).to.equal(initialHash);
    expect(latest.ttlDays).to.equal(0n);
    expect(latest.prevCommitHash).to.equal(ethers.ZeroHash);
    expect(latest.ratioMillis).to.equal(569n);
  });

  it("T178-2: renewCommit succeeds and emits RatioRenewed event", async function () {
    const newHash = ethers.keccak256(ethers.toUtf8Bytes("renewal:prevhash=initialHash:ttl=90"));
    const tx = await registry.renewCommit(initialHash, newHash, 90);
    await expect(tx)
      .to.emit(registry, "RatioRenewed")
      .withArgs(initialHash, newHash, 90n, await ethers.provider.getBlockNumber());
    expect(await registry.totalCommits()).to.equal(2n);
    expect(await registry.isCommitted(newHash)).to.be.true;
  });

  it("T178-3: renewCommit anti-replay — duplicate newCommitHash reverts", async function () {
    const newHash = ethers.keccak256(ethers.toUtf8Bytes("renewal-unique"));
    await registry.renewCommit(initialHash, newHash, 90);
    // Attempt to use the same newCommitHash again
    await expect(
      registry.renewCommit(initialHash, newHash, 90)
    ).to.be.revertedWith("SeparationRatioRegistry: duplicate newCommitHash");
  });

  it("T178-4: renewCommit onlyOwner — non-owner reverts", async function () {
    const newHash = ethers.keccak256(ethers.toUtf8Bytes("non-owner-renewal"));
    await expect(
      registry.connect(nonOwner).renewCommit(initialHash, newHash, 90)
    ).to.be.revertedWithCustomError(registry, "OwnableUnauthorizedAccount");
  });

  it("T178-5: renewCommit stores ttlDays and prevCommitHash in new commit", async function () {
    const newHash = ethers.keccak256(ethers.toUtf8Bytes("renewal-with-fields"));
    await registry.renewCommit(initialHash, newHash, 90);
    const latest = await registry.getLatestCommit();
    expect(latest.commitHash).to.equal(newHash);
    expect(latest.ttlDays).to.equal(90n);
    expect(latest.prevCommitHash).to.equal(initialHash);
    // Inherits ratioMillis from prev commit
    expect(latest.ratioMillis).to.equal(569n);
  });

  it("T178-6: renewCommit reverts when ttlDays = 0 (zero-TTL guard)", async function () {
    const newHash = ethers.keccak256(ethers.toUtf8Bytes("renewal-zero-ttl"));
    await expect(
      registry.renewCommit(initialHash, newHash, 0)
    ).to.be.revertedWith("SeparationRatioRegistry: ttlDays must be > 0");
  });
});
