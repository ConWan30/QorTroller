/**
 * Path A — VAPIDeviceBirthCertUpdateRegistry (birth-cert override for the MFG-CA HSM migration).
 *
 * grok round-24 test packs: (1) active-gate + precedence + guards + events; (2) revoke-after-override
 * (stale override is inert for VALID because VMDR.isActive is the eligibility gate elsewhere).
 * Uses the REAL VMDR (deploy + register) so the isActive / devices interface is exercised for real.
 */
const { expect } = require("chai");
const { ethers } = require("hardhat");

describe("VAPIDeviceBirthCertUpdateRegistry (Path A override)", function () {
  const DEVICE     = ethers.keccak256(ethers.toUtf8Bytes("host-SERIAL-581a836c"));
  const UNREG      = ethers.keccak256(ethers.toUtf8Bytes("never-registered"));
  const PUBKEY     = ethers.keccak256(ethers.toUtf8Bytes("compressed-pubkey"));
  const MODEL_EDGE = ethers.keccak256(ethers.toUtf8Bytes("CFI-ZCP1"));
  const OLD_HASH   = ethers.keccak256(ethers.toUtf8Bytes("software-signed-birth-cert"));
  const NEW_HASH   = ethers.keccak256(ethers.toUtf8Bytes("kms-signed-birth-cert"));
  const ZERO       = ethers.ZeroHash;

  let vmdr, ovr, owner, attacker;

  beforeEach(async function () {
    [owner, attacker] = await ethers.getSigners();
    const V = await ethers.getContractFactory("VAPIManufacturerDeviceRegistry");
    vmdr = await V.deploy(owner.address);
    await vmdr.waitForDeployment();
    // register the device with the OLD (software) hash, Path B FULL
    await vmdr.registerDevice(DEVICE, PUBKEY, MODEL_EDGE, 2, 1, OLD_HASH);

    const O = await ethers.getContractFactory("VAPIDeviceBirthCertUpdateRegistry");
    ovr = await O.deploy(await vmdr.getAddress());
    await ovr.waitForDeployment();
  });

  // --- pack 1: active-gate + precedence + guards -------------------------------------------------

  it("T-DBC-1: constructor rejects zero VMDR", async function () {
    const O = await ethers.getContractFactory("VAPIDeviceBirthCertUpdateRegistry");
    await expect(O.deploy(ethers.ZeroAddress)).to.be.revertedWith("DBC-UPD: zero vmdr");
  });

  it("T-DBC-2: currentBirthCertHash defaults to the VMDR hash with no override", async function () {
    expect(await ovr.hasOverride(DEVICE)).to.equal(false);
    expect(await ovr.currentBirthCertHash(DEVICE)).to.equal(OLD_HASH);
  });

  it("T-DBC-3: setUpdated on an active device overrides + emits + precedence wins", async function () {
    await expect(ovr.setUpdatedBirthCertHash(DEVICE, NEW_HASH))
      .to.emit(ovr, "BirthCertHashUpdated").withArgs(DEVICE, NEW_HASH, OLD_HASH);
    expect(await ovr.hasOverride(DEVICE)).to.equal(true);
    expect(await ovr.currentBirthCertHash(DEVICE)).to.equal(NEW_HASH);   // override wins over VMDR raw
  });

  it("T-DBC-4: setUpdated reverts for an unregistered device (not active on VMDR)", async function () {
    await expect(ovr.setUpdatedBirthCertHash(UNREG, NEW_HASH))
      .to.be.revertedWith("DBC-UPD: not active on VMDR");
  });

  it("T-DBC-5: setUpdated reverts on zero hash and on a no-op", async function () {
    await expect(ovr.setUpdatedBirthCertHash(DEVICE, ZERO)).to.be.revertedWith("DBC-UPD: zero hash");
    await expect(ovr.setUpdatedBirthCertHash(DEVICE, OLD_HASH)).to.be.revertedWith("DBC-UPD: noop");
  });

  it("T-DBC-6: only the owner can set or clear", async function () {
    await expect(ovr.connect(attacker).setUpdatedBirthCertHash(DEVICE, NEW_HASH))
      .to.be.revertedWithCustomError(ovr, "OwnableUnauthorizedAccount");
    await ovr.setUpdatedBirthCertHash(DEVICE, NEW_HASH);
    await expect(ovr.connect(attacker).clearOverride(DEVICE))
      .to.be.revertedWithCustomError(ovr, "OwnableUnauthorizedAccount");
  });

  it("T-DBC-7: clearOverride falls back to the VMDR hash + emits", async function () {
    await ovr.setUpdatedBirthCertHash(DEVICE, NEW_HASH);
    await expect(ovr.clearOverride(DEVICE))
      .to.emit(ovr, "BirthCertHashCleared").withArgs(DEVICE, NEW_HASH);
    expect(await ovr.hasOverride(DEVICE)).to.equal(false);
    expect(await ovr.currentBirthCertHash(DEVICE)).to.equal(OLD_HASH);   // back to VMDR
  });

  it("T-DBC-8: clearOverride reverts when there is no override", async function () {
    await expect(ovr.clearOverride(DEVICE)).to.be.revertedWith("DBC-UPD: no override");
  });

  // --- pack 2: revoke after override ------------------------------------------------------------

  it("T-DBC-9: a revoked device's stale override is inert for VALID (isActive is the eligibility gate)", async function () {
    await ovr.setUpdatedBirthCertHash(DEVICE, NEW_HASH);
    await vmdr.revokeDevice(DEVICE);
    // the override mapping still holds (this contract can't be called by VMDR on revoke)...
    expect(await ovr.hasOverride(DEVICE)).to.equal(true);
    expect(await ovr.currentBirthCertHash(DEVICE)).to.equal(NEW_HASH);
    // ...but the device is no longer active, so verify's isActive check (elsewhere) fails -> not VALID
    expect(await vmdr.isActive(DEVICE)).to.equal(false);
  });

  it("T-DBC-10: cannot set an override on a revoked device", async function () {
    await vmdr.revokeDevice(DEVICE);
    await expect(ovr.setUpdatedBirthCertHash(DEVICE, NEW_HASH))
      .to.be.revertedWith("DBC-UPD: not active on VMDR");
  });
});
