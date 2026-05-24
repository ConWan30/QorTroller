/**
 * VAPIPoEPRegistry — Phase B ② P4b Hardhat tests (§5(a) of the scope doc).
 *
 *   T-PR-1: deployment — owner correct, totalRegistrations=0, ioidRegistry unset
 *   T-PR-2: registerDevice stores record, emits DeviceRegistered (full blob in event data),
 *           computes sha256(blob) on-chain, increments totalRegistrations
 *   T-PR-3: gamer-sovereign — a non-owner gamer registers their OWN device; the record is keyed
 *           by msg.sender; gamer A's registration does not touch gamer B's slot
 *   T-PR-4: anti-replay — duplicate poepCommitment reverts (Option B; even across gamers)
 *   T-PR-5: zero/empty guards — empty pubkey blob reverts; zero poepCommitment reverts
 *   T-PR-6: Property X — expiresAt != 0 reverts ("reserved for v2"); stored expiresAt is 0
 *   T-PR-7: revokeDevice flips revoked, emits DeviceRevoked, only the owner-gamer can revoke
 *           their own; isRegistrationValid false after revoke
 *   T-PR-8: views — getRecord / getCompositePubkeyHash / isRegistrationValid / isRecorded
 *   T-PR-9: re-registration overwrites the caller's own record (new pubkey); prior commitment
 *           stays in the anti-replay set
 *
 * Pattern mirrors AgentRegistry.test.js (chai + ethers v6, fresh deploy per test).
 */

const { expect } = require("chai");
const { ethers } = require("hardhat");

describe("VAPIPoEPRegistry (Phase B ② P4b)", function () {
  let reg, owner, gamerA, gamerB;

  const DEVICE_1 = ethers.keccak256(ethers.toUtf8Bytes("Sony_DualShock_Edge_CFI-ZCP1"));
  const DEVICE_2 = ethers.keccak256(ethers.toUtf8Bytes("sony_dualshock_edge_v1"));
  // simulated ① encode_pubkey blobs (content opaque to the contract; it only sha256's them)
  const BLOB_A = "0x" + "01".repeat(152);   // SLH-DSA-128s-sized
  const BLOB_B = "0x" + "ab".repeat(200);
  const COMMIT_1 = ethers.keccak256(ethers.toUtf8Bytes("poep-commit-1"));
  const COMMIT_2 = ethers.keccak256(ethers.toUtf8Bytes("poep-commit-2"));
  const COMMIT_3 = ethers.keccak256(ethers.toUtf8Bytes("poep-commit-3"));

  beforeEach(async function () {
    [owner, gamerA, gamerB] = await ethers.getSigners();
    const F = await ethers.getContractFactory("VAPIPoEPRegistry");
    reg = await F.deploy(owner.address);
    await reg.waitForDeployment();
  });

  it("T-PR-1: deployment defaults", async function () {
    expect(await reg.owner()).to.equal(owner.address);
    expect(await reg.totalRegistrations()).to.equal(0n);
    expect(await reg.ioidRegistry()).to.equal(ethers.ZeroAddress);
  });

  it("T-PR-2: registerDevice stores + emits + on-chain sha256 + increments", async function () {
    await expect(reg.connect(gamerA).registerDevice(DEVICE_1, BLOB_A, COMMIT_1, 0))
      .to.emit(reg, "DeviceRegistered");
    const expectedHash = ethers.sha256(BLOB_A);
    expect(await reg.getCompositePubkeyHash(gamerA.address, DEVICE_1)).to.equal(expectedHash);
    const rec = await reg.getRecord(gamerA.address, DEVICE_1);
    expect(rec.compositePubkeyHash).to.equal(expectedHash);
    expect(rec.poepCommitment).to.equal(COMMIT_1);
    expect(rec.expiresAt).to.equal(0n);
    expect(rec.revoked).to.equal(false);
    expect(await reg.totalRegistrations()).to.equal(1n);
    // the full blob is carried in the event data (event-sourced storage)
    const ev = (await reg.queryFilter(reg.filters.DeviceRegistered()))[0];
    expect(ev.args.compositePubkeyBlob).to.equal(BLOB_A);
    expect(ev.args.compositePubkeyHash).to.equal(expectedHash);
  });

  it("T-PR-3: gamer-sovereign — keyed by msg.sender; A's record independent of B", async function () {
    await reg.connect(gamerA).registerDevice(DEVICE_1, BLOB_A, COMMIT_1, 0);
    await reg.connect(gamerB).registerDevice(DEVICE_1, BLOB_B, COMMIT_2, 0); // same deviceId, diff gamer
    expect(await reg.getCompositePubkeyHash(gamerA.address, DEVICE_1)).to.equal(ethers.sha256(BLOB_A));
    expect(await reg.getCompositePubkeyHash(gamerB.address, DEVICE_1)).to.equal(ethers.sha256(BLOB_B));
    // gamer B has no record under gamer A's address-keyed slot for a device B never registered
    expect(await reg.isRegistrationValid(gamerB.address, DEVICE_2)).to.equal(false);
  });

  it("T-PR-4: anti-replay — duplicate poepCommitment reverts (even cross-gamer)", async function () {
    await reg.connect(gamerA).registerDevice(DEVICE_1, BLOB_A, COMMIT_1, 0);
    await expect(
      reg.connect(gamerB).registerDevice(DEVICE_2, BLOB_B, COMMIT_1, 0)
    ).to.be.revertedWith("VPR: duplicate poepCommitment");
    expect(await reg.isRecorded(COMMIT_1)).to.equal(true);
    expect(await reg.isRecorded(COMMIT_2)).to.equal(false);
  });

  it("T-PR-5: zero/empty guards", async function () {
    await expect(
      reg.connect(gamerA).registerDevice(DEVICE_1, "0x", COMMIT_1, 0)
    ).to.be.revertedWith("VPR: empty pubkey blob");
    await expect(
      reg.connect(gamerA).registerDevice(DEVICE_1, BLOB_A, ethers.ZeroHash, 0)
    ).to.be.revertedWith("VPR: zero poepCommitment");
  });

  it("T-PR-6: Property X — expiresAt != 0 reverts; stored expiresAt is 0", async function () {
    await expect(
      reg.connect(gamerA).registerDevice(DEVICE_1, BLOB_A, COMMIT_1, 9999999999)
    ).to.be.revertedWith("VPR: expiresAt reserved for v2");
    await reg.connect(gamerA).registerDevice(DEVICE_1, BLOB_A, COMMIT_1, 0);
    expect((await reg.getRecord(gamerA.address, DEVICE_1)).expiresAt).to.equal(0n);
  });

  it("T-PR-7: revoke — flips revoked, emits, only own record, invalidates", async function () {
    await reg.connect(gamerA).registerDevice(DEVICE_1, BLOB_A, COMMIT_1, 0);
    expect(await reg.isRegistrationValid(gamerA.address, DEVICE_1)).to.equal(true);
    // gamer B cannot revoke gamer A's device (B has no record at its own slot)
    await expect(reg.connect(gamerB).revokeDevice(DEVICE_1)).to.be.revertedWith("VPR: nothing to revoke");
    await expect(reg.connect(gamerA).revokeDevice(DEVICE_1)).to.emit(reg, "DeviceRevoked");
    expect(await reg.isRegistrationValid(gamerA.address, DEVICE_1)).to.equal(false);
    await expect(reg.connect(gamerA).revokeDevice(DEVICE_1)).to.be.revertedWith("VPR: already revoked");
  });

  it("T-PR-8: views default to zero/false for unregistered", async function () {
    expect(await reg.getCompositePubkeyHash(gamerA.address, DEVICE_1)).to.equal(ethers.ZeroHash);
    expect(await reg.isRegistrationValid(gamerA.address, DEVICE_1)).to.equal(false);
    expect(await reg.isRecorded(COMMIT_1)).to.equal(false);
    const rec = await reg.getRecord(gamerA.address, DEVICE_1);
    expect(rec.compositePubkeyHash).to.equal(ethers.ZeroHash);
  });

  it("T-PR-9: re-registration overwrites caller's own record; prior commitment stays recorded", async function () {
    await reg.connect(gamerA).registerDevice(DEVICE_1, BLOB_A, COMMIT_1, 0);
    await reg.connect(gamerA).registerDevice(DEVICE_1, BLOB_B, COMMIT_3, 0); // new pubkey + new commitment
    expect(await reg.getCompositePubkeyHash(gamerA.address, DEVICE_1)).to.equal(ethers.sha256(BLOB_B));
    expect(await reg.isRecorded(COMMIT_1)).to.equal(true);  // prior commitment still in anti-replay set
    expect(await reg.isRecorded(COMMIT_3)).to.equal(true);
  });

  it("T-PR-10: setIoIDRegistry only-owner", async function () {
    await expect(reg.connect(gamerA).setIoIDRegistry(gamerB.address)).to.be.reverted; // Ownable
    await expect(reg.connect(owner).setIoIDRegistry(gamerB.address)).to.emit(reg, "IoIDRegistrySet");
    expect(await reg.ioidRegistry()).to.equal(gamerB.address);
    await expect(reg.connect(owner).setIoIDRegistry(ethers.ZeroAddress)).to.be.revertedWith("VPR: zero ioidRegistry");
  });
});
