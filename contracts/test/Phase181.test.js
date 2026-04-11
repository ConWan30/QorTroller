/**
 * Phase 181 — CeremonyAuditRegistry Hardhat Tests (4 tests)
 *
 * T181-1: Deploy smoke — deploys with correct owner, totalParticipants=0
 * T181-2: registerParticipant stores and getParticipantCount increments
 * T181-3: getParticipantCount correct per circuit
 * T181-4: zero-address participantAddress guard reverts
 *
 * CeremonyAuditRegistry.sol is code-complete since Phase 179.
 * Phase 181 WIF-030 W2: on-chain deploy + ceremony_audit_registry_address config field.
 */

const { expect } = require("chai");
const { ethers } = require("hardhat");

describe("CeremonyAuditRegistry (Phase 181)", function () {
  let registry, owner, nonOwner, addr1;

  const CIRCUIT_NAME = ethers.encodeBytes32String("pitl_feature_extraction");
  const CEREMONY_ID  = ethers.encodeBytes32String("ceremony_2026_phase181");
  const CONTRIB_HASH = ethers.encodeBytes32String("sha256:abc123contribution");

  beforeEach(async function () {
    [owner, nonOwner, addr1] = await ethers.getSigners();
    const Factory = await ethers.getContractFactory("CeremonyAuditRegistry");
    registry = await Factory.deploy(owner.address);
    await registry.waitForDeployment();
  });

  it("T181-1: deploys with correct owner and totalParticipants=0", async function () {
    expect(await registry.owner()).to.equal(owner.address);
    expect(await registry.totalParticipants()).to.equal(0n);
    // getParticipantCount for any circuit should be 0
    expect(await registry.getParticipantCount(CIRCUIT_NAME)).to.equal(0n);
  });

  it("T181-2: registerParticipant stores entry and increments totalParticipants", async function () {
    await registry.connect(owner).registerParticipant(
      CEREMONY_ID,
      CIRCUIT_NAME,
      addr1.address,
      CONTRIB_HASH,
    );
    expect(await registry.totalParticipants()).to.equal(1n);
    expect(await registry.getParticipantCount(CIRCUIT_NAME)).to.equal(1n);
  });

  it("T181-3: getParticipantCount correct per circuit (two circuits independent)", async function () {
    const CIRCUIT_B = ethers.encodeBytes32String("ceremony_circuit_b");

    await registry.connect(owner).registerParticipant(
      CEREMONY_ID, CIRCUIT_NAME, addr1.address, CONTRIB_HASH
    );
    await registry.connect(owner).registerParticipant(
      CEREMONY_ID, CIRCUIT_B, owner.address, CONTRIB_HASH
    );

    expect(await registry.getParticipantCount(CIRCUIT_NAME)).to.equal(1n);
    expect(await registry.getParticipantCount(CIRCUIT_B)).to.equal(1n);
    expect(await registry.totalParticipants()).to.equal(2n);
  });

  it("T181-4: zero-address participantAddress reverts", async function () {
    await expect(
      registry.connect(owner).registerParticipant(
        CEREMONY_ID,
        CIRCUIT_NAME,
        ethers.ZeroAddress,
        CONTRIB_HASH,
      )
    ).to.be.revertedWith("CeremonyAuditRegistry: zero participantAddress");
  });
});
