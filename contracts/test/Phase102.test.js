/**
 * Phase 102 — TournamentGateDemo.sol Tests (4 tests: T102-1..4)
 * Tests demoMode bypass, PITL gate enforcement, VHP validity, and access control.
 * Hardhat count: 430 → 434 (+4)
 */
const { expect } = require("chai");
const { ethers }  = require("hardhat");

describe("TournamentGateDemo (Phase 102)", function () {
  let demo, owner, player, nonOwner;
  let mockLens, mockVhp;

  const DEVICE_ID   = ethers.encodeBytes32String("dev-abc123");
  const VHP_TOKEN   = 42n;

  beforeEach(async function () {
    [owner, player, nonOwner] = await ethers.getSigners();

    // Deploy mock ProtocolLens (returns false by default)
    const MockLens = await ethers.getContractFactory("MockProtocolLens102");
    mockLens = await MockLens.deploy();

    // Deploy mock VHP (returns false by default)
    const MockVHP = await ethers.getContractFactory("MockVHP102");
    mockVhp = await MockVHP.deploy();

    const TournamentGateDemo = await ethers.getContractFactory("TournamentGateDemo");
    demo = await TournamentGateDemo.deploy(
      await mockLens.getAddress(),
      await mockVhp.getAddress()
    );
  });

  it("T102-1: demoMode=true allows entry without gate checks", async function () {
    await demo.setDemoMode(true);

    const tx = await demo.connect(player).enterTournament(DEVICE_ID, VHP_TOKEN);
    await expect(tx)
      .to.emit(demo, "PlayerEntered")
      .withArgs(player.address, DEVICE_ID, VHP_TOKEN, await ethers.provider.getBlock("latest").then(b => b.timestamp));

    expect(await demo.getParticipantCount()).to.equal(1n);
    const p = await demo.getParticipant(0);
    expect(p.player).to.equal(player.address);
    expect(p.deviceId).to.equal(DEVICE_ID);
    expect(p.vhpTokenId).to.equal(VHP_TOKEN);
  });

  it("T102-2: demoMode=false + isFullyEligible=false → revert PITL gate not passed", async function () {
    await demo.setDemoMode(false);
    await mockLens.setEligible(false);

    await expect(
      demo.connect(player).enterTournament(DEVICE_ID, VHP_TOKEN)
    ).to.be.revertedWith("TournamentGateDemo: PITL gate not passed");
  });

  it("T102-3: demoMode=false + PITL passes + isValid=false → revert VHP token expired or invalid", async function () {
    await demo.setDemoMode(false);
    await mockLens.setEligible(true);
    await mockVhp.setValid(false);

    await expect(
      demo.connect(player).enterTournament(DEVICE_ID, VHP_TOKEN)
    ).to.be.revertedWith("TournamentGateDemo: VHP token expired or invalid");
  });

  it("T102-4: setDemoMode from non-owner reverts OwnableUnauthorizedAccount", async function () {
    await expect(
      demo.connect(nonOwner).setDemoMode(true)
    ).to.be.revertedWithCustomError(demo, "OwnableUnauthorizedAccount");
  });
});
