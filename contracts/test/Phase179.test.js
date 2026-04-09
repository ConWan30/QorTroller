/**
 * Phase 179 — CeremonyAuditRegistry Hardhat Tests (8 tests)
 *
 * Tests the ZK ceremony multi-party audit gate (WIF-030 W1 closure):
 *   T179-1: Deploy + owner check
 *   T179-2: registerParticipant stores participant and emits event
 *   T179-3: Anti-replay — duplicate (ceremonyId, participantAddress, circuitName) reverts
 *   T179-4: onlyOwner — non-owner registerParticipant reverts
 *   T179-5: getParticipantCount returns correct count per circuit
 *   T179-6: Multiple circuits tracked independently
 *   T179-7: ParticipantRegistered event emitted with correct args
 *   T179-8: Zero-address participantAddress guard reverts
 */

const { expect } = require("chai");
const { ethers } = require("hardhat");

describe("CeremonyAuditRegistry (Phase 179)", function () {
  let registry, owner, nonOwner, participant1, participant2, participant3;
  let circuitA, circuitB, ceremonyId;

  beforeEach(async function () {
    [owner, nonOwner, participant1, participant2, participant3] = await ethers.getSigners();
    const Factory = await ethers.getContractFactory("CeremonyAuditRegistry");
    registry = await Factory.deploy(owner.address);
    await registry.waitForDeployment();

    circuitA  = ethers.keccak256(ethers.toUtf8Bytes("PitlSessionProof"));
    circuitB  = ethers.keccak256(ethers.toUtf8Bytes("TournamentPassport"));
    ceremonyId = ethers.keccak256(ethers.toUtf8Bytes("vapi-ceremony-2026-04-09"));
  });

  it("T179-1: deploys with correct owner and zero totalParticipants", async function () {
    expect(await registry.owner()).to.equal(owner.address);
    expect(await registry.totalParticipants()).to.equal(0n);
  });

  it("T179-2: registerParticipant stores participant and increments totalParticipants", async function () {
    const contribHash = ethers.keccak256(ethers.toUtf8Bytes("contrib-p1-circuitA"));
    await registry.registerParticipant(ceremonyId, circuitA, participant1.address, contribHash);
    expect(await registry.totalParticipants()).to.equal(1n);
    expect(await registry.getParticipantCount(circuitA)).to.equal(1n);
    const entry = await registry.getParticipant(circuitA, 0);
    expect(entry.participantAddress).to.equal(participant1.address);
    expect(entry.contributionHash).to.equal(contribHash);
  });

  it("T179-3: anti-replay — duplicate (ceremonyId, participantAddress, circuitName) reverts", async function () {
    const contribHash = ethers.keccak256(ethers.toUtf8Bytes("contrib-p1-circuitA-dup"));
    await registry.registerParticipant(ceremonyId, circuitA, participant1.address, contribHash);
    await expect(
      registry.registerParticipant(ceremonyId, circuitA, participant1.address, contribHash)
    ).to.be.revertedWith("CeremonyAuditRegistry: duplicate participant");
  });

  it("T179-4: onlyOwner — non-owner registerParticipant reverts", async function () {
    const contribHash = ethers.keccak256(ethers.toUtf8Bytes("contrib-nonowner"));
    await expect(
      registry.connect(nonOwner).registerParticipant(ceremonyId, circuitA, participant1.address, contribHash)
    ).to.be.revertedWithCustomError(registry, "OwnableUnauthorizedAccount");
  });

  it("T179-5: getParticipantCount returns correct count per circuit after 3 registrations", async function () {
    const h1 = ethers.keccak256(ethers.toUtf8Bytes("h1"));
    const h2 = ethers.keccak256(ethers.toUtf8Bytes("h2"));
    const h3 = ethers.keccak256(ethers.toUtf8Bytes("h3"));
    await registry.registerParticipant(ceremonyId, circuitA, participant1.address, h1);
    await registry.registerParticipant(ceremonyId, circuitA, participant2.address, h2);
    await registry.registerParticipant(ceremonyId, circuitA, participant3.address, h3);
    expect(await registry.getParticipantCount(circuitA)).to.equal(3n);
    // circuitB should still be 0
    expect(await registry.getParticipantCount(circuitB)).to.equal(0n);
  });

  it("T179-6: multiple circuits tracked independently", async function () {
    const hA = ethers.keccak256(ethers.toUtf8Bytes("hA"));
    const hB = ethers.keccak256(ethers.toUtf8Bytes("hB"));
    await registry.registerParticipant(ceremonyId, circuitA, participant1.address, hA);
    await registry.registerParticipant(ceremonyId, circuitB, participant1.address, hB);
    expect(await registry.getParticipantCount(circuitA)).to.equal(1n);
    expect(await registry.getParticipantCount(circuitB)).to.equal(1n);
    expect(await registry.totalParticipants()).to.equal(2n);
  });

  it("T179-7: ParticipantRegistered event emitted with correct args", async function () {
    const contribHash = ethers.keccak256(ethers.toUtf8Bytes("event-test-contrib"));
    const tx = await registry.registerParticipant(
      ceremonyId, circuitA, participant1.address, contribHash
    );
    await expect(tx)
      .to.emit(registry, "ParticipantRegistered")
      .withArgs(circuitA, participant1.address, ceremonyId, contribHash, await ethers.provider.getBlockNumber());
  });

  it("T179-8: zero-address participantAddress guard reverts", async function () {
    const contribHash = ethers.keccak256(ethers.toUtf8Bytes("zero-addr-test"));
    await expect(
      registry.registerParticipant(ceremonyId, circuitA, ethers.ZeroAddress, contribHash)
    ).to.be.revertedWith("CeremonyAuditRegistry: zero participantAddress");
  });
});
