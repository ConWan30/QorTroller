/**
 * VAPIManufacturerDeviceRegistry — Path A Arc 1 Commit 2 Hardhat tests.
 *
 *   T-MFG-1  registerDevice (Path A FULL) — stores all fields, emits DeviceRegistered,
 *            increments totalRegistrations, sets registered[deviceId] = true
 *   T-MFG-2  getSigningPath returns the stored enum value (1 = Path A, 2 = Path B)
 *   T-MFG-3  getProofTier returns the stored enum value (1 / 2 / 3)
 *   T-MFG-4  isPathA returns TRUE iff registered + active + signingPath == 1 (Path A device)
 *   T-MFG-5  isPathA returns FALSE for a Path B device (signingPath == 2) even when active
 *   T-MFG-6  registerDevice REVERTS on double-registration of the same deviceId
 *            (anti-replay: one device id, one birth event)
 *   T-MFG-7  registerDevice REVERTS when called by a non-owner (onlyOwner gate)
 *   T-MFG-8  revokeDevice flips active → false, emits DeviceRevoked, isActive returns
 *            false post-revoke (one-way revocation; record preserved for audit)
 *
 * Pattern mirrors VAPIPoEPRegistry.test.js (chai + ethers v6, fresh deploy per test).
 */

const { expect } = require("chai");
const { ethers } = require("hardhat");

describe("VAPIManufacturerDeviceRegistry (Path A Arc 1 C2)", function () {
  let reg, owner, mfgOther, attacker;

  const DEVICE_PATH_A   = ethers.keccak256(ethers.toUtf8Bytes("atecc-SERIAL-A-001"));
  const DEVICE_PATH_B   = ethers.keccak256(ethers.toUtf8Bytes("host-SERIAL-B-002"));
  const PUBKEY_HASH_A   = ethers.keccak256(ethers.toUtf8Bytes("compressed-pubkey-A"));
  const PUBKEY_HASH_B   = ethers.keccak256(ethers.toUtf8Bytes("compressed-pubkey-B"));
  const MODEL_EDGE      = ethers.keccak256(ethers.toUtf8Bytes("CFI-ZCP1"));
  const MODEL_DUALSENSE = ethers.keccak256(ethers.toUtf8Bytes("CFI-ZCT1"));
  const CERT_HASH_A     = ethers.keccak256(ethers.toUtf8Bytes("birth-cert-A"));
  const CERT_HASH_B     = ethers.keccak256(ethers.toUtf8Bytes("birth-cert-B"));

  // FROZEN enum constants — mirror INV-MFG-001 / INV-MFG-002
  const SIGNING_PATH_A   = 1;
  const SIGNING_PATH_B   = 2;
  const PROOF_TIER_FULL     = 1;
  const PROOF_TIER_STANDARD = 2;
  const PROOF_TIER_BASIC    = 3;

  beforeEach(async function () {
    [owner, mfgOther, attacker] = await ethers.getSigners();
    const F = await ethers.getContractFactory("VAPIManufacturerDeviceRegistry");
    reg = await F.deploy(owner.address);
    await reg.waitForDeployment();
  });

  it("T-MFG-1: registerDevice (Path A FULL) stores + emits + increments", async function () {
    await expect(
      reg.connect(owner).registerDevice(
        DEVICE_PATH_A, PUBKEY_HASH_A, MODEL_EDGE,
        SIGNING_PATH_A, PROOF_TIER_FULL, CERT_HASH_A,
      )
    )
      .to.emit(reg, "DeviceRegistered")
      .withArgs(DEVICE_PATH_A, MODEL_EDGE, SIGNING_PATH_A, PROOF_TIER_FULL);

    const dev = await reg.getDevice(DEVICE_PATH_A);
    expect(dev.pubkeyHash).to.equal(PUBKEY_HASH_A);
    expect(dev.controllerModel).to.equal(MODEL_EDGE);
    expect(dev.signingPath).to.equal(SIGNING_PATH_A);
    expect(dev.proofTier).to.equal(PROOF_TIER_FULL);
    expect(dev.birthCertHash).to.equal(CERT_HASH_A);
    expect(dev.manufacturerWallet).to.equal(owner.address);
    expect(dev.active).to.equal(true);

    expect(await reg.registered(DEVICE_PATH_A)).to.equal(true);
    expect(await reg.totalRegistrations()).to.equal(1n);
  });

  it("T-MFG-2: getSigningPath returns the stored enum value", async function () {
    await reg.connect(owner).registerDevice(
      DEVICE_PATH_A, PUBKEY_HASH_A, MODEL_EDGE,
      SIGNING_PATH_A, PROOF_TIER_FULL, CERT_HASH_A,
    );
    await reg.connect(owner).registerDevice(
      DEVICE_PATH_B, PUBKEY_HASH_B, MODEL_DUALSENSE,
      SIGNING_PATH_B, PROOF_TIER_STANDARD, CERT_HASH_B,
    );

    expect(await reg.getSigningPath(DEVICE_PATH_A)).to.equal(SIGNING_PATH_A);
    expect(await reg.getSigningPath(DEVICE_PATH_B)).to.equal(SIGNING_PATH_B);
    // unregistered → 0
    const NEVER = ethers.keccak256(ethers.toUtf8Bytes("never-registered"));
    expect(await reg.getSigningPath(NEVER)).to.equal(0);
  });

  it("T-MFG-3: getProofTier returns the stored enum value", async function () {
    await reg.connect(owner).registerDevice(
      DEVICE_PATH_A, PUBKEY_HASH_A, MODEL_EDGE,
      SIGNING_PATH_A, PROOF_TIER_FULL, CERT_HASH_A,
    );
    await reg.connect(owner).registerDevice(
      DEVICE_PATH_B, PUBKEY_HASH_B, MODEL_DUALSENSE,
      SIGNING_PATH_B, PROOF_TIER_BASIC, CERT_HASH_B,
    );

    expect(await reg.getProofTier(DEVICE_PATH_A)).to.equal(PROOF_TIER_FULL);
    expect(await reg.getProofTier(DEVICE_PATH_B)).to.equal(PROOF_TIER_BASIC);
    // unregistered → 0
    expect(await reg.getProofTier(ethers.keccak256(ethers.toUtf8Bytes("none")))).to.equal(0);
  });

  it("T-MFG-4: isPathA true iff registered + active + signingPath == 1", async function () {
    await reg.connect(owner).registerDevice(
      DEVICE_PATH_A, PUBKEY_HASH_A, MODEL_EDGE,
      SIGNING_PATH_A, PROOF_TIER_FULL, CERT_HASH_A,
    );
    expect(await reg.isPathA(DEVICE_PATH_A)).to.equal(true);
    expect(await reg.isActive(DEVICE_PATH_A)).to.equal(true);
  });

  it("T-MFG-5: isPathA false for Path B device even when active", async function () {
    await reg.connect(owner).registerDevice(
      DEVICE_PATH_B, PUBKEY_HASH_B, MODEL_DUALSENSE,
      SIGNING_PATH_B, PROOF_TIER_STANDARD, CERT_HASH_B,
    );
    expect(await reg.isPathA(DEVICE_PATH_B)).to.equal(false);
    expect(await reg.isActive(DEVICE_PATH_B)).to.equal(true); // still active, just not Path A
    // unregistered → false on both
    const NEVER = ethers.keccak256(ethers.toUtf8Bytes("never-registered"));
    expect(await reg.isPathA(NEVER)).to.equal(false);
    expect(await reg.isActive(NEVER)).to.equal(false);
  });

  it("T-MFG-6: double-registration of same deviceId reverts", async function () {
    await reg.connect(owner).registerDevice(
      DEVICE_PATH_A, PUBKEY_HASH_A, MODEL_EDGE,
      SIGNING_PATH_A, PROOF_TIER_FULL, CERT_HASH_A,
    );
    await expect(
      reg.connect(owner).registerDevice(
        DEVICE_PATH_A, PUBKEY_HASH_B, MODEL_EDGE,
        SIGNING_PATH_A, PROOF_TIER_FULL, CERT_HASH_B,
      )
    ).to.be.revertedWith("VMDR: already registered");
    // totalRegistrations still 1 (revert rolled back the increment)
    expect(await reg.totalRegistrations()).to.equal(1n);
  });

  it("T-MFG-7: non-owner registerDevice reverts (onlyOwner)", async function () {
    await expect(
      reg.connect(attacker).registerDevice(
        DEVICE_PATH_A, PUBKEY_HASH_A, MODEL_EDGE,
        SIGNING_PATH_A, PROOF_TIER_FULL, CERT_HASH_A,
      )
    ).to.be.revertedWithCustomError(reg, "OwnableUnauthorizedAccount");
    // Different non-owner also reverts (defense-in-depth)
    await expect(
      reg.connect(mfgOther).registerDevice(
        DEVICE_PATH_A, PUBKEY_HASH_A, MODEL_EDGE,
        SIGNING_PATH_A, PROOF_TIER_FULL, CERT_HASH_A,
      )
    ).to.be.revertedWithCustomError(reg, "OwnableUnauthorizedAccount");
    // Nothing registered, count still 0
    expect(await reg.totalRegistrations()).to.equal(0n);
    expect(await reg.registered(DEVICE_PATH_A)).to.equal(false);
  });

  it("T-MFG-8: revokeDevice flips active false, emits DeviceRevoked, record preserved", async function () {
    await reg.connect(owner).registerDevice(
      DEVICE_PATH_A, PUBKEY_HASH_A, MODEL_EDGE,
      SIGNING_PATH_A, PROOF_TIER_FULL, CERT_HASH_A,
    );
    expect(await reg.isActive(DEVICE_PATH_A)).to.equal(true);

    await expect(reg.connect(owner).revokeDevice(DEVICE_PATH_A))
      .to.emit(reg, "DeviceRevoked")
      .withArgs(DEVICE_PATH_A);

    expect(await reg.isActive(DEVICE_PATH_A)).to.equal(false);
    expect(await reg.isPathA(DEVICE_PATH_A)).to.equal(false);  // post-revoke, no longer Path A

    // record preserved for forensic audit (signingPath, proofTier, pubkeyHash still queryable)
    const dev = await reg.getDevice(DEVICE_PATH_A);
    expect(dev.pubkeyHash).to.equal(PUBKEY_HASH_A);
    expect(dev.signingPath).to.equal(SIGNING_PATH_A);
    expect(dev.active).to.equal(false);

    // double-revoke reverts
    await expect(reg.connect(owner).revokeDevice(DEVICE_PATH_A))
      .to.be.revertedWith("VMDR: already revoked");

    // non-owner revoke reverts
    await reg.connect(owner).registerDevice(
      DEVICE_PATH_B, PUBKEY_HASH_B, MODEL_DUALSENSE,
      SIGNING_PATH_B, PROOF_TIER_STANDARD, CERT_HASH_B,
    );
    await expect(reg.connect(attacker).revokeDevice(DEVICE_PATH_B))
      .to.be.revertedWithCustomError(reg, "OwnableUnauthorizedAccount");
  });
});
