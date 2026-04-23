/**
 * Phase 222 — VAPIBiometricGovernance Hardhat Tests (8 tests)
 *
 * Tests the Biometric-Bound Governance (BBG) contract:
 *   T222-HH-1: Deploy + owner check + totalProposals=0
 *   T222-HH-2: proposeWithVHP stores proposal, emits ProposalSubmitted, increments totalProposals
 *   T222-HH-3: Anti-replay — duplicate proposalHash reverts
 *   T222-HH-4: STOLEN_KEY guard — non-owner of VHP reverts
 *   T222-HH-5: VHP_EXPIRY guard — VHP expiring too soon reverts
 *   T222-HH-6: Invalid VHP (not minted / invalidated) reverts
 *   T222-HH-7: setVHPContract updates vhpContract; zero-address reverts
 *   T222-HH-8: Zero proposalHash reverts
 */

const { expect } = require("chai");
const { ethers } = require("hardhat");

describe("VAPIBiometricGovernance (Phase 222)", function () {
  let bbg, mockVHP, owner, nonOwner, proposer1, proposer2;
  const MAX_AGE_SEC = 3600n;

  beforeEach(async function () {
    [owner, nonOwner, proposer1, proposer2] = await ethers.getSigners();

    const MockFactory = await ethers.getContractFactory("MockVHP222");
    mockVHP = await MockFactory.deploy();
    await mockVHP.waitForDeployment();

    const BBGFactory = await ethers.getContractFactory("VAPIBiometricGovernance");
    bbg = await BBGFactory.deploy(owner.address, await mockVHP.getAddress(), MAX_AGE_SEC);
    await bbg.waitForDeployment();
  });

  // Helper: mint a VHP token with expiry far in the future
  async function mintVHP(tokenId, holder) {
    const farFuture = BigInt(Math.floor(Date.now() / 1000)) + 86400n * 365n; // 1 year
    await mockVHP.mint(tokenId, holder.address, farFuture);
    return farFuture;
  }

  it("T222-HH-1: deploys with correct owner and totalProposals=0", async function () {
    expect(await bbg.owner()).to.equal(owner.address);
    expect(await bbg.totalProposals()).to.equal(0n);
    expect(await bbg.bbgMaxAgeSec()).to.equal(MAX_AGE_SEC);
  });

  it("T222-HH-2: proposeWithVHP stores proposal and emits ProposalSubmitted", async function () {
    await mintVHP(1n, proposer1);
    const proposalHash = ethers.keccak256(ethers.toUtf8Bytes("proposal-alpha"));

    const tx = await bbg.connect(proposer1).proposeWithVHP(proposalHash, 1n);
    await expect(tx)
      .to.emit(bbg, "ProposalSubmitted")
      .withArgs(proposalHash, proposer1.address, 1n, await ethers.provider.getBlockNumber());

    expect(await bbg.totalProposals()).to.equal(1n);
    expect(await bbg.isProposed(proposalHash)).to.equal(true);

    const prop = await bbg.getProposal(0);
    expect(prop.proposer).to.equal(proposer1.address);
    expect(prop.vhpTokenId).to.equal(1n);
  });

  it("T222-HH-3: anti-replay — duplicate proposalHash reverts", async function () {
    await mintVHP(2n, proposer1);
    const proposalHash = ethers.keccak256(ethers.toUtf8Bytes("proposal-dup"));
    await bbg.connect(proposer1).proposeWithVHP(proposalHash, 2n);
    await expect(
      bbg.connect(proposer1).proposeWithVHP(proposalHash, 2n)
    ).to.be.revertedWith("BBG: duplicate proposalHash");
  });

  it("T222-HH-4: STOLEN_KEY guard — non-owner of VHP reverts", async function () {
    await mintVHP(3n, proposer1);  // proposer1 owns token 3
    const proposalHash = ethers.keccak256(ethers.toUtf8Bytes("proposal-stolen-key"));
    // proposer2 tries to use token 3 (not their VHP)
    await expect(
      bbg.connect(proposer2).proposeWithVHP(proposalHash, 3n)
    ).to.be.revertedWith("BBG: not VHP owner");
  });

  it("T222-HH-5: VHP_EXPIRY guard — VHP expiring too soon reverts", async function () {
    // Mint VHP that expires only 100 seconds from now (< bbgMaxAgeSec=3600)
    const soon = BigInt(Math.floor(Date.now() / 1000)) + 100n;
    await mockVHP.mint(4n, proposer1.address, soon);
    const proposalHash = ethers.keccak256(ethers.toUtf8Bytes("proposal-expiry"));
    await expect(
      bbg.connect(proposer1).proposeWithVHP(proposalHash, 4n)
    ).to.be.revertedWith("BBG: VHP expires too soon");
  });

  it("T222-HH-6: invalid VHP reverts (invalidated token)", async function () {
    await mintVHP(5n, proposer1);
    await mockVHP.invalidate(5n);  // Mark VHP as invalid
    const proposalHash = ethers.keccak256(ethers.toUtf8Bytes("proposal-invalid-vhp"));
    await expect(
      bbg.connect(proposer1).proposeWithVHP(proposalHash, 5n)
    ).to.be.revertedWith("BBG: VHP not valid");
  });

  it("T222-HH-7: setVHPContract updates contract; zero-address reverts; emits VHPContractSet", async function () {
    const MockFactory2 = await ethers.getContractFactory("MockVHP222");
    const newMock = await MockFactory2.deploy();
    await newMock.waitForDeployment();
    const newAddr = await newMock.getAddress();
    const oldAddr = await mockVHP.getAddress();

    const tx = await bbg.connect(owner).setVHPContract(newAddr);
    await expect(tx).to.emit(bbg, "VHPContractSet").withArgs(oldAddr, newAddr);
    expect(await bbg.vhpContract()).to.equal(newAddr);

    await expect(
      bbg.connect(owner).setVHPContract(ethers.ZeroAddress)
    ).to.be.revertedWith("BBG: zero newVHP");
  });

  it("T222-HH-8: zero proposalHash reverts", async function () {
    await mintVHP(6n, proposer1);
    await expect(
      bbg.connect(proposer1).proposeWithVHP(ethers.ZeroHash, 6n)
    ).to.be.revertedWith("BBG: zero proposalHash");
  });
});
