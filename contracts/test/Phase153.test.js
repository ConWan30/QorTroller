/**
 * Phase 153 — SeparationRatioRegistry Hardhat Tests (6 tests)
 *
 * T153-1: Deploy + owner
 * T153-2: commitRatio stores data correctly
 * T153-3: isCommitted returns true after commit
 * T153-4: Duplicate commitHash reverts
 * T153-5: getLatestCommit returns most recent
 * T153-6: Non-owner commitRatio reverts
 */

const { expect } = require("chai");
const { ethers } = require("hardhat");

describe("SeparationRatioRegistry (Phase 153)", function () {
  let registry, owner, nonOwner;

  beforeEach(async function () {
    [owner, nonOwner] = await ethers.getSigners();
    const Factory = await ethers.getContractFactory("SeparationRatioRegistry");
    registry = await Factory.deploy(owner.address);
    await registry.waitForDeployment();
  });

  it("T153-1: deploys with correct owner", async function () {
    expect(await registry.owner()).to.equal(owner.address);
    expect(await registry.totalCommits()).to.equal(0n);
  });

  it("T153-2: commitRatio stores data and increments totalCommits", async function () {
    const commitHash = ethers.keccak256(ethers.toUtf8Bytes("ratio=1.261:N=11:P1P2P3"));
    await registry.commitRatio(commitHash, 1261n, 11, 3);
    expect(await registry.totalCommits()).to.equal(1n);
    expect(await registry.isCommitted(commitHash)).to.be.true;
  });

  it("T153-3: isCommitted returns false for unknown hash", async function () {
    const unknownHash = ethers.keccak256(ethers.toUtf8Bytes("unknown"));
    expect(await registry.isCommitted(unknownHash)).to.be.false;
  });

  it("T153-4: duplicate commitHash reverts", async function () {
    const commitHash = ethers.keccak256(ethers.toUtf8Bytes("same-hash"));
    await registry.commitRatio(commitHash, 1261n, 11, 3);
    await expect(
      registry.commitRatio(commitHash, 1500n, 15, 3)
    ).to.be.revertedWith("SeparationRatioRegistry: duplicate commit");
  });

  it("T153-5: getLatestCommit returns most recent entry", async function () {
    const hash1 = ethers.keccak256(ethers.toUtf8Bytes("commit-1"));
    const hash2 = ethers.keccak256(ethers.toUtf8Bytes("commit-2"));
    await registry.commitRatio(hash1, 1261n, 11, 3);
    await registry.commitRatio(hash2, 1552n, 15, 3);
    const latest = await registry.getLatestCommit();
    expect(latest.commitHash).to.equal(hash2);
    expect(latest.ratioMillis).to.equal(1552n);
  });

  it("T153-6: non-owner commitRatio reverts OwnableUnauthorizedAccount", async function () {
    const hash = ethers.keccak256(ethers.toUtf8Bytes("non-owner-hash"));
    await expect(
      registry.connect(nonOwner).commitRatio(hash, 1261n, 11, 3)
    ).to.be.revertedWithCustomError(registry, "OwnableUnauthorizedAccount");
  });
});
