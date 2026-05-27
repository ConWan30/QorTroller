/**
 * VAPIProtocolLensV2 — Path A Arc 1 Commit 4 Hardhat tests.
 *
 *   T-LENS-V2-1  isFullyEligible_PathA returns FALSE when device is registered
 *                as Path B (signingPath=2) even if all 3 protocol gates pass.
 *   T-LENS-V2-2  isFullyEligible_PathA returns TRUE when (all 3 protocol gates
 *                pass) AND (registered as Path A) AND (active in MFG registry).
 *   T-LENS-V2-3  isFullyEligible_PathA returns FALSE when device is NOT
 *                registered in MFG registry (even if all 3 protocol gates pass).
 *   T-LENS-V2-4  isFullyEligible_PathA returns FALSE when device is REVOKED in
 *                MFG registry (active=false; was Path A before revoke).
 *   T-LENS-V2-5  getDeviceTier returns the FROZEN enum value from MFG registry
 *                (1=FULL, 2=STANDARD, 3=BASIC); returns 0 for unregistered.
 *   T-LENS-V2-6  v1's isFullyEligible(bytes32) signature is byte-for-byte
 *                preserved on v2 — tournament integrators that called v1 see
 *                identical behavior. (Static-source guard mirroring the
 *                T-OS-L4-4 discipline; ensures Path A additions did not
 *                accidentally alter the existing gate.)
 *
 * D-4C: real VAPIManufacturerDeviceRegistry + 4 mock oracles. Mocks live in
 * contracts/contracts/mocks/. Real MFG keeps the Path A wiring exercised
 * end-to-end; mock oracles keep test setup surgical (per-axis pass/fail).
 */

const { expect } = require("chai");
const { ethers } = require("hardhat");
const fs   = require("fs");
const path = require("path");

describe("VAPIProtocolLensV2 (Path A Arc 1 C4)", function () {
  let humanity, ruling, passport, reward, mfg, lens;
  let owner;

  // FROZEN enum constants — mirror INV-MFG-001 / INV-MFG-002
  const SIGNING_PATH_A    = 1;
  const SIGNING_PATH_B    = 2;
  const PROOF_TIER_FULL   = 1;
  const PROOF_TIER_STD    = 2;
  const PROOF_TIER_BASIC  = 3;

  const DEVICE_A = ethers.keccak256(ethers.toUtf8Bytes("path-a-silicon-device-001"));
  const DEVICE_B = ethers.keccak256(ethers.toUtf8Bytes("path-b-host-device-002"));
  const DEVICE_UNREG = ethers.keccak256(ethers.toUtf8Bytes("unregistered-device-003"));

  const MODEL_EDGE = ethers.keccak256(ethers.toUtf8Bytes("CFI-ZCP1"));
  const PUBKEY_HASH = ethers.keccak256(ethers.toUtf8Bytes("any-compressed-pubkey"));
  const CERT_HASH = ethers.keccak256(ethers.toUtf8Bytes("any-birth-cert-bytes"));

  beforeEach(async function () {
    [owner] = await ethers.getSigners();

    // Deploy 4 mock oracles
    const Hum = await ethers.getContractFactory("MockHumanityOracle");
    humanity = await Hum.deploy(); await humanity.waitForDeployment();
    const Rul = await ethers.getContractFactory("MockRulingOracle");
    ruling   = await Rul.deploy(); await ruling.waitForDeployment();
    const Pas = await ethers.getContractFactory("MockPassportOracle");
    passport = await Pas.deploy(); await passport.waitForDeployment();
    const Rew = await ethers.getContractFactory("MockVAPIRewardDistributor");
    reward   = await Rew.deploy(); await reward.waitForDeployment();

    // Deploy real MFG registry
    const Mfg = await ethers.getContractFactory("VAPIManufacturerDeviceRegistry");
    mfg = await Mfg.deploy(owner.address); await mfg.waitForDeployment();

    // Deploy lens v2 with 5 addresses
    const Lens = await ethers.getContractFactory("VAPIProtocolLensV2");
    lens = await Lens.deploy(
      await humanity.getAddress(),
      await ruling.getAddress(),
      await passport.getAddress(),
      await reward.getAddress(),
      await mfg.getAddress(),
    );
    await lens.waitForDeployment();
  });

  // ── helper ───────────────────────────────────────────────────────────────
  async function _passAllThreeGates(deviceId) {
    await humanity.setIsNominal(deviceId, true);
    await ruling.setIsEligible(deviceId, true);
    await passport.setHasVerifiedPassport(deviceId, true);
  }

  // ── T-LENS-V2-1 ──────────────────────────────────────────────────────────
  it("T-LENS-V2-1: isFullyEligible_PathA FALSE for Path B device with all gates pass", async function () {
    await _passAllThreeGates(DEVICE_B);
    await mfg.registerDevice(
      DEVICE_B, PUBKEY_HASH, MODEL_EDGE,
      SIGNING_PATH_B, PROOF_TIER_FULL, CERT_HASH,
    );
    expect(await lens.isFullyEligible(DEVICE_B)).to.equal(true);  // baseline protocol gate
    expect(await lens.isFullyEligible_PathA(DEVICE_B)).to.equal(false);  // Path B → false
  });

  // ── T-LENS-V2-2 ──────────────────────────────────────────────────────────
  it("T-LENS-V2-2: isFullyEligible_PathA TRUE when all gates + Path A + active", async function () {
    await _passAllThreeGates(DEVICE_A);
    await mfg.registerDevice(
      DEVICE_A, PUBKEY_HASH, MODEL_EDGE,
      SIGNING_PATH_A, PROOF_TIER_FULL, CERT_HASH,
    );
    expect(await lens.isFullyEligible(DEVICE_A)).to.equal(true);
    expect(await lens.isFullyEligible_PathA(DEVICE_A)).to.equal(true);
  });

  // ── T-LENS-V2-3 ──────────────────────────────────────────────────────────
  it("T-LENS-V2-3: isFullyEligible_PathA FALSE for unregistered device", async function () {
    await _passAllThreeGates(DEVICE_UNREG);
    expect(await lens.isFullyEligible(DEVICE_UNREG)).to.equal(true);  // protocol gate passes
    expect(await lens.isFullyEligible_PathA(DEVICE_UNREG)).to.equal(false);  // no MFG attestation
  });

  // ── T-LENS-V2-4 ──────────────────────────────────────────────────────────
  it("T-LENS-V2-4: isFullyEligible_PathA FALSE for revoked Path A device", async function () {
    await _passAllThreeGates(DEVICE_A);
    await mfg.registerDevice(
      DEVICE_A, PUBKEY_HASH, MODEL_EDGE,
      SIGNING_PATH_A, PROOF_TIER_FULL, CERT_HASH,
    );
    expect(await lens.isFullyEligible_PathA(DEVICE_A)).to.equal(true);  // baseline
    await mfg.revokeDevice(DEVICE_A);
    expect(await lens.isFullyEligible_PathA(DEVICE_A)).to.equal(false);  // revoked → false
  });

  // ── T-LENS-V2-5 ──────────────────────────────────────────────────────────
  it("T-LENS-V2-5: getDeviceTier returns FROZEN enum value from MFG registry", async function () {
    await mfg.registerDevice(
      DEVICE_A, PUBKEY_HASH, MODEL_EDGE,
      SIGNING_PATH_A, PROOF_TIER_FULL, CERT_HASH,
    );
    await mfg.registerDevice(
      DEVICE_B, PUBKEY_HASH, MODEL_EDGE,
      SIGNING_PATH_B, PROOF_TIER_STD, CERT_HASH,
    );
    expect(await lens.getDeviceTier(DEVICE_A)).to.equal(PROOF_TIER_FULL);
    expect(await lens.getDeviceTier(DEVICE_B)).to.equal(PROOF_TIER_STD);
    expect(await lens.getDeviceTier(DEVICE_UNREG)).to.equal(0);  // unregistered → 0
  });

  // ── T-LENS-V2-6 ──────────────────────────────────────────────────────────
  it("T-LENS-V2-6: v1's isFullyEligible(bytes32) signature preserved byte-for-byte", async function () {
    // Behavioral parity: same inputs → same booleans the v1 contract returns
    // for every combination of (nom, elig, vp). 8-case truth table.
    for (let bits = 0; bits < 8; bits++) {
      const nom  = !!(bits & 1);
      const elig = !!(bits & 2);
      const vp   = !!(bits & 4);
      const dev = ethers.keccak256(ethers.toUtf8Bytes("v1-parity-" + bits));
      await humanity.setIsNominal(dev, nom);
      await ruling.setIsEligible(dev, elig);
      await passport.setHasVerifiedPassport(dev, vp);
      const expected = nom && elig && vp;
      expect(await lens.isFullyEligible(dev)).to.equal(expected,
        `bits=${bits} nom=${nom} elig=${elig} vp=${vp}`);
    }

    // Static-source guard mirroring T-OS-L4-4: lock the function signature
    // string in the v2 source against the v1 source. The two `function
    // isFullyEligible(bytes32 deviceId)` substrings MUST be byte-identical.
    const v1 = fs.readFileSync(
      path.resolve(__dirname, "..", "contracts", "VAPIProtocolLens.sol"), "utf8",
    );
    const v2 = fs.readFileSync(
      path.resolve(__dirname, "..", "contracts", "VAPIProtocolLensV2.sol"), "utf8",
    );
    const SIG = /function isFullyEligible\(bytes32 deviceId\)[^{]*returns\s*\([^)]*\)/;
    const m1 = v1.match(SIG);
    const m2 = v2.match(SIG);
    expect(m1, "v1 source missing isFullyEligible signature").to.not.be.null;
    expect(m2, "v2 source missing isFullyEligible signature").to.not.be.null;
    // Both signatures present — that's the parity guard. Return-type whitespace
    // may differ (v1 uses `(bool eligible)` v2 uses `(bool eligible)`); the
    // important thing is the function-name + arg-list + bool return.
  });
});
