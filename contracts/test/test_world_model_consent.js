// WMP-4 Hardhat tests for VAPIWorldModelConsentRegistry.
//
// T-WMC-1  default state — every address returns false (granted=false)
// T-WMC-2  setWorldModelConsent(true) flips caller's state to true and
//          emits WorldModelConsentSet(gamer, true, block, ts)
// T-WMC-3  msg.sender == gamer is structurally enforced — bridge wallet
//          cannot grant on behalf of a gamer wallet
// T-WMC-4  toggle round-trip: false → true → false; totalToggles
//          increments on each call
// T-WMC-5  consent is per-address — granting for gamer A does not
//          grant for gamer B
const { expect } = require("chai");
const { ethers } = require("hardhat");

describe("VAPIWorldModelConsentRegistry (WMP-4)", function () {
  let reg;
  let owner, gamerA, gamerB, bridgeWallet;

  beforeEach(async function () {
    [owner, gamerA, gamerB, bridgeWallet] = await ethers.getSigners();
    const F = await ethers.getContractFactory("VAPIWorldModelConsentRegistry");
    reg = await F.deploy();
    await reg.waitForDeployment();
  });

  it("T-WMC-1: default state — every address returns false", async function () {
    expect(await reg.isWorldModelConsentGranted(gamerA.address)).to.equal(false);
    expect(await reg.isWorldModelConsentGranted(gamerB.address)).to.equal(false);
    expect(await reg.isWorldModelConsentGranted(bridgeWallet.address)).to.equal(false);
    expect(await reg.totalToggles()).to.equal(0n);
  });

  it("T-WMC-2: setWorldModelConsent(true) flips caller's state and emits event", async function () {
    const tx = await reg.connect(gamerA).setWorldModelConsent(true);
    const rcpt = await tx.wait();
    expect(await reg.isWorldModelConsentGranted(gamerA.address)).to.equal(true);
    expect(await reg.totalToggles()).to.equal(1n);
    // Event check: WorldModelConsentSet emitted with gamerA address
    const logs = rcpt.logs.filter(
      (l) => l.fragment && l.fragment.name === "WorldModelConsentSet"
    );
    expect(logs.length).to.equal(1);
    expect(logs[0].args.gamer).to.equal(gamerA.address);
    expect(logs[0].args.granted).to.equal(true);
  });

  it("T-WMC-3: msg.sender == gamer is structurally enforced (bridge cannot grant for gamer)", async function () {
    // bridgeWallet calls setWorldModelConsent — it only flips its OWN
    // mapping entry, NOT gamerA's. That's the sovereignty invariant.
    await reg.connect(bridgeWallet).setWorldModelConsent(true);
    expect(await reg.isWorldModelConsentGranted(bridgeWallet.address)).to.equal(true);
    // Critical: gamerA's consent state is UNCHANGED.
    expect(await reg.isWorldModelConsentGranted(gamerA.address)).to.equal(false);
  });

  it("T-WMC-4: round-trip false → true → false; totalToggles increments", async function () {
    expect(await reg.totalToggles()).to.equal(0n);

    await reg.connect(gamerA).setWorldModelConsent(true);
    expect(await reg.isWorldModelConsentGranted(gamerA.address)).to.equal(true);
    expect(await reg.totalToggles()).to.equal(1n);

    await reg.connect(gamerA).setWorldModelConsent(false);
    expect(await reg.isWorldModelConsentGranted(gamerA.address)).to.equal(false);
    expect(await reg.totalToggles()).to.equal(2n);

    await reg.connect(gamerA).setWorldModelConsent(true);
    expect(await reg.isWorldModelConsentGranted(gamerA.address)).to.equal(true);
    expect(await reg.totalToggles()).to.equal(3n);
  });

  it("T-WMC-5: per-address scoping — granting for A does not grant for B", async function () {
    await reg.connect(gamerA).setWorldModelConsent(true);
    expect(await reg.isWorldModelConsentGranted(gamerA.address)).to.equal(true);
    expect(await reg.isWorldModelConsentGranted(gamerB.address)).to.equal(false);

    await reg.connect(gamerB).setWorldModelConsent(true);
    expect(await reg.isWorldModelConsentGranted(gamerB.address)).to.equal(true);
    // gamerA still consenting
    expect(await reg.isWorldModelConsentGranted(gamerA.address)).to.equal(true);

    // gamerA revokes — gamerB unaffected
    await reg.connect(gamerA).setWorldModelConsent(false);
    expect(await reg.isWorldModelConsentGranted(gamerA.address)).to.equal(false);
    expect(await reg.isWorldModelConsentGranted(gamerB.address)).to.equal(true);
  });
});
