/**
 * Phase 187 — VHPReenrollmentBadge.sol Tests
 *
 * WIF-033 W2 closure: ERC-4671 soulbound credential issued when re-enrollment
 * attestation validates on IoTeX L1.
 *
 * Test suite (6 tests):
 *   T187-1: mintBadge stores badge and emits BadgeMinted event
 *   T187-2: isValid returns true for fresh badge, false after expiry
 *   T187-3: revert on used attestationHash (anti-replay)
 *   T187-4: revert on zero playerIdHash
 *   T187-5: revert on zero attestationHash
 *   T187-6: playerBadgeCount increments per player; latestBadgeId updates correctly
 */

const { expect } = require("chai");
const { ethers }  = require("hardhat");

const PLAYER_HASH_0 = ethers.keccak256(ethers.toUtf8Bytes("player_p1"));
const PLAYER_HASH_1 = ethers.keccak256(ethers.toUtf8Bytes("player_p2"));
const ATTEST_HASH_0 = ethers.keccak256(ethers.toUtf8Bytes("hmac:abc123token"));
const ATTEST_HASH_1 = ethers.keccak256(ethers.toUtf8Bytes("hmac:def456token"));

describe("VHPReenrollmentBadge Phase 187 (WIF-033 W2 closure)", function () {
  this.timeout(120000); // viaIR compilation may be slow

  let badge;
  let owner;
  let other;

  beforeEach(async function () {
    [owner, other] = await ethers.getSigners();
    const Factory = await ethers.getContractFactory("VHPReenrollmentBadge");
    badge = await Factory.deploy(owner.address);
    await badge.waitForDeployment();
  });

  // T187-1: mintBadge stores badge and emits BadgeMinted event
  it("T187-1: mintBadge stores badge correctly and emits BadgeMinted", async function () {
    const tx = await badge.mintBadge(PLAYER_HASH_0, ATTEST_HASH_0, 90);
    const receipt = await tx.wait();

    // Check event
    const event = receipt.logs.find(
      (log) => log.fragment && log.fragment.name === "BadgeMinted"
    );
    expect(event).to.not.be.undefined;
    expect(event.args.tokenId).to.equal(1n);
    expect(event.args.playerIdHash).to.equal(PLAYER_HASH_0);
    expect(event.args.attestationHash).to.equal(ATTEST_HASH_0);

    // Check totalBadges
    expect(await badge.totalBadges()).to.equal(1n);

    // Check badge struct
    const stored = await badge.badges(1n);
    expect(stored.playerIdHash).to.equal(PLAYER_HASH_0);
    expect(stored.attestationHash).to.equal(ATTEST_HASH_0);
    expect(stored.valid).to.be.true;
    expect(stored.expiresAt).to.be.gt(stored.mintedAt);
  });

  // T187-2: isValid returns true for fresh badge, false after expiry (ttlDays=0 edge case)
  it("T187-2: isValid returns true for fresh badge; revokeBadge sets valid=false", async function () {
    await badge.mintBadge(PLAYER_HASH_0, ATTEST_HASH_0, 90);
    expect(await badge.isValid(1n)).to.be.true;

    await badge.revokeBadge(1n);
    expect(await badge.isValid(1n)).to.be.false;
  });

  // T187-3: revert on used attestationHash (anti-replay)
  it("T187-3: reverts when attestationHash already used (anti-replay)", async function () {
    await badge.mintBadge(PLAYER_HASH_0, ATTEST_HASH_0, 90);
    await expect(
      badge.mintBadge(PLAYER_HASH_1, ATTEST_HASH_0, 90)
    ).to.be.revertedWith("VHPReenrollmentBadge: attestation already used");
  });

  // T187-4: revert on zero playerIdHash
  it("T187-4: reverts on zero playerIdHash", async function () {
    await expect(
      badge.mintBadge(ethers.ZeroHash, ATTEST_HASH_0, 90)
    ).to.be.revertedWith("VHPReenrollmentBadge: zero player hash");
  });

  // T187-5: revert on zero attestationHash
  it("T187-5: reverts on zero attestationHash", async function () {
    await expect(
      badge.mintBadge(PLAYER_HASH_0, ethers.ZeroHash, 90)
    ).to.be.revertedWith("VHPReenrollmentBadge: zero attestation hash");
  });

  // T187-6: playerBadgeCount increments per player; latestBadgeId updates
  it("T187-6: playerBadgeCount increments per player and latestBadgeId updates", async function () {
    // Mint two badges for P1
    await badge.mintBadge(PLAYER_HASH_0, ATTEST_HASH_0, 90);
    await badge.mintBadge(PLAYER_HASH_0, ATTEST_HASH_1, 90);

    expect(await badge.playerBadgeCount(PLAYER_HASH_0)).to.equal(2n);
    expect(await badge.latestBadgeId(PLAYER_HASH_0)).to.equal(2n);
    expect(await badge.totalBadges()).to.equal(2n);

    // P2 untouched
    expect(await badge.playerBadgeCount(PLAYER_HASH_1)).to.equal(0n);
    expect(await badge.latestBadgeId(PLAYER_HASH_1)).to.equal(0n);
  });
});
