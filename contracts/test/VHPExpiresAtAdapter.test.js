/**
 * VHPExpiresAtAdapter — IVHP222 shim over VAPIVerifiedHumanProof.
 *
 *   T-VHPA-1  Constructor reverts on zero VHP address.
 *   T-VHPA-2  vhp() immutable getter returns the address passed at construction.
 *   T-VHPA-3  expiresAt(tokenId) returns the exact value stored in the wrapped
 *             VHP's VHPData.expiresAt (field index 5 of the 7-tuple getter).
 *   T-VHPA-4  expiresAt(unminted) returns 0 (default uint256 from zero-init
 *             struct); does NOT revert.
 *   T-VHPA-5  isValid(tokenId) pass-through matches the wrapped VHP's isValid
 *             (true for valid token, false for expired/unminted).
 *   T-VHPA-6  ownerOf(tokenId) pass-through matches the wrapped VHP's ownerOf
 *             (token holder for minted, zero address for unminted).
 *   T-VHPA-7  After wrapped VHP's renew() bumps expiresAt, adapter's
 *             expiresAt() reflects the new value (read-through, not cached).
 *   T-VHPA-8  IVHP222 surface complete — all three methods callable + return
 *             types as BBG expects (regression guard against future ABI drift).
 */

const { expect } = require("chai");
const { ethers } = require("hardhat");

describe("VHPExpiresAtAdapter (Curator governance ceremony unblock)", function () {
  let owner, gamer, attacker;
  let vhp, adapter;
  const DEVICE_ID_HASH = ethers.keccak256(ethers.toUtf8Bytes("device-cfi-zcp1-test"));
  const MPC_CEREMONY_HASH = ethers.keccak256(ethers.toUtf8Bytes("mpc-ceremony-test"));

  // VHPData struct — matches the canonical VAPIVerifiedHumanProof.sol struct order
  function _vhpData(expiresAtTs) {
    return {
      deviceIdHash:        DEVICE_ID_HASH,
      certificationLevel:  1,
      consecutiveClean:    100,
      confidenceScore:     9500,
      issuedAt:            Math.floor(Date.now() / 1000),
      expiresAt:           expiresAtTs,
      mpcCeremonyHash:     MPC_CEREMONY_HASH,
    };
  }

  beforeEach(async function () {
    [owner, gamer, attacker] = await ethers.getSigners();

    const VHP = await ethers.getContractFactory("VAPIVerifiedHumanProof");
    vhp = await VHP.deploy(owner.address);
    await vhp.waitForDeployment();

    const Adapter = await ethers.getContractFactory("VHPExpiresAtAdapter");
    adapter = await Adapter.deploy(await vhp.getAddress());
    await adapter.waitForDeployment();
  });

  // ── T-VHPA-1 ──────────────────────────────────────────────────────────────
  it("T-VHPA-1: constructor reverts on zero VHP address", async function () {
    const Adapter = await ethers.getContractFactory("VHPExpiresAtAdapter");
    await expect(Adapter.deploy(ethers.ZeroAddress))
      .to.be.revertedWith("VHPAdapter: zero vhpAddr");
  });

  // ── T-VHPA-2 ──────────────────────────────────────────────────────────────
  it("T-VHPA-2: vhp() immutable getter returns the constructor-passed address", async function () {
    expect(await adapter.vhp()).to.equal(await vhp.getAddress());
  });

  // ── T-VHPA-3 ──────────────────────────────────────────────────────────────
  it("T-VHPA-3: expiresAt(tokenId) returns the wrapped VHP's stored value", async function () {
    const blockTs = (await ethers.provider.getBlock("latest")).timestamp;
    const futureTs = blockTs + 90 * 24 * 3600; // +90d
    const data = _vhpData(futureTs);
    await vhp.mint(gamer.address, data);

    // Read via the wrapped VHP's struct getter directly
    const direct = await vhp.vhpData(1);
    expect(direct.expiresAt).to.equal(futureTs);

    // Read via the adapter — must match exactly
    expect(await adapter.expiresAt(1)).to.equal(futureTs);
  });

  // ── T-VHPA-4 ──────────────────────────────────────────────────────────────
  it("T-VHPA-4: expiresAt(unminted) returns 0 (no revert)", async function () {
    expect(await adapter.expiresAt(999)).to.equal(0);
  });

  // ── T-VHPA-5 ──────────────────────────────────────────────────────────────
  it("T-VHPA-5: isValid pass-through matches wrapped VHP", async function () {
    const blockTs = (await ethers.provider.getBlock("latest")).timestamp;
    const futureTs = blockTs + 86400; // +1d
    await vhp.mint(gamer.address, _vhpData(futureTs));

    expect(await adapter.isValid(1)).to.equal(true);
    expect(await vhp.isValid(1)).to.equal(true);

    // Unminted token: both return false
    expect(await adapter.isValid(2)).to.equal(false);
    expect(await vhp.isValid(2)).to.equal(false);
  });

  // ── T-VHPA-6 ──────────────────────────────────────────────────────────────
  it("T-VHPA-6: ownerOf pass-through matches wrapped VHP", async function () {
    const blockTs = (await ethers.provider.getBlock("latest")).timestamp;
    const futureTs = blockTs + 86400;
    await vhp.mint(gamer.address, _vhpData(futureTs));

    expect(await adapter.ownerOf(1)).to.equal(gamer.address);
    expect(await vhp.ownerOf(1)).to.equal(gamer.address);

    // Unminted: zero address
    expect(await adapter.ownerOf(99)).to.equal(ethers.ZeroAddress);
  });

  // ── T-VHPA-7 ──────────────────────────────────────────────────────────────
  it("T-VHPA-7: adapter expiresAt reflects renew() — read-through, not cached", async function () {
    const blockTs = (await ethers.provider.getBlock("latest")).timestamp;
    const initialTs = blockTs + 86400;
    await vhp.mint(gamer.address, _vhpData(initialTs));
    const beforeRenew = await adapter.expiresAt(1);
    expect(beforeRenew).to.equal(initialTs);

    // Renew the token (defaultTTLDays from now)
    await vhp.renew(1);

    // Adapter must reflect the new expiresAt (not the cached initialTs)
    const afterRenew = await adapter.expiresAt(1);
    expect(afterRenew).to.be.greaterThan(beforeRenew);

    // Also confirm via direct read on the wrapped VHP
    const directAfter = await vhp.vhpData(1);
    expect(afterRenew).to.equal(directAfter.expiresAt);
  });

  // ── T-VHPA-8 ──────────────────────────────────────────────────────────────
  it("T-VHPA-8: IVHP222 surface complete — all three methods callable + return types correct", async function () {
    const blockTs = (await ethers.provider.getBlock("latest")).timestamp;
    const futureTs = blockTs + 86400;
    await vhp.mint(gamer.address, _vhpData(futureTs));

    // ownerOf returns address
    const owner = await adapter.ownerOf(1);
    expect(typeof owner).to.equal("string");
    expect(ethers.isAddress(owner)).to.equal(true);

    // isValid returns bool
    const valid = await adapter.isValid(1);
    expect(typeof valid).to.equal("boolean");

    // expiresAt returns uint256 (ethers v6 returns bigint)
    const expires = await adapter.expiresAt(1);
    expect(typeof expires).to.equal("bigint");
    expect(expires).to.equal(BigInt(futureTs));
  });
});
