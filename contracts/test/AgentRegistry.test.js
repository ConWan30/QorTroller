/**
 * AgentRegistry — Operator series Phase O0 Hardhat Tests (8 tests)
 *
 * Pass 2C Section 3.1 specification (commit b9ddeeb2):
 *   T-AR-1: deployment defaults — owner correct, totalAgents=0
 *   T-AR-2: registerAgent stores agent, emits AgentRegistered, increments totalAgents
 *   T-AR-3: registerAgent only-owner — non-owner reverts
 *   T-AR-4: anti-replay — duplicate agentId reverts
 *   T-AR-5: updateAgentStatus transitions status, emits AgentStatusUpdated, only-owner reverts
 *   T-AR-6: updateAgentScope changes scopeHash, emits AgentScopeUpdated, only-owner reverts
 *   T-AR-7: getAgent view returns the registered tuple
 *   T-AR-8: zero-bytes32 agentId guard reverts on registerAgent
 *
 * Pattern: matches Phase222.test.js shape (BBG tests). Deploy fixture in
 * beforeEach with a fresh signer set per test for isolation.
 */

const { expect } = require("chai");
const { ethers } = require("hardhat");

describe("AgentRegistry (Operator series Phase O0)", function () {
  let registry, owner, nonOwner, agentSigner1, agentSigner2;

  // Synthetic agentIds for test scenarios. Real agentIds in production are
  // keccak256(abi.encode(ioID_DID_address, ERC6551_TBA_address)) per Pass 2C Q9.
  const AGENT_ID_SENTRY = ethers.keccak256(ethers.toUtf8Bytes("test-agent-sentry"));
  const AGENT_ID_GUARDIAN = ethers.keccak256(ethers.toUtf8Bytes("test-agent-guardian"));
  const SCOPE_HASH_EMPTY = ethers.ZeroHash;
  const SCOPE_HASH_ALPHA = ethers.keccak256(ethers.toUtf8Bytes("scope-alpha"));
  const SCOPE_HASH_BETA = ethers.keccak256(ethers.toUtf8Bytes("scope-beta"));

  // Status values (mirroring AgentRegistry.sol constants for test clarity).
  const STATUS_DEFINED = 0;
  const STATUS_SHADOW = 1;
  const STATUS_SUGGESTING = 2;
  const STATUS_SUSPENDED = 255;

  beforeEach(async function () {
    [owner, nonOwner, agentSigner1, agentSigner2] = await ethers.getSigners();

    const Factory = await ethers.getContractFactory("AgentRegistry");
    registry = await Factory.deploy(owner.address);
    await registry.waitForDeployment();
  });

  it("T-AR-1: deploys with correct owner and totalAgents=0", async function () {
    expect(await registry.owner()).to.equal(owner.address);
    expect(await registry.totalAgents()).to.equal(0n);

    // Status constants exposed correctly.
    expect(await registry.STATUS_DEFINED()).to.equal(0);
    expect(await registry.STATUS_FULL_OPERATOR()).to.equal(6);
    expect(await registry.STATUS_SUSPENDED()).to.equal(255);
  });

  it("T-AR-2: registerAgent stores agent, emits AgentRegistered, increments totalAgents", async function () {
    const tx = await registry
      .connect(owner)
      .registerAgent(AGENT_ID_SENTRY, agentSigner1.address, SCOPE_HASH_EMPTY, STATUS_DEFINED);

    await expect(tx)
      .to.emit(registry, "AgentRegistered")
      .withArgs(AGENT_ID_SENTRY, agentSigner1.address, SCOPE_HASH_EMPTY, STATUS_DEFINED);

    expect(await registry.totalAgents()).to.equal(1n);
    expect(await registry.isRegistered(AGENT_ID_SENTRY)).to.equal(true);

    const [pk, scope, status] = await registry.getAgent(AGENT_ID_SENTRY);
    expect(pk).to.equal(agentSigner1.address);
    expect(scope).to.equal(SCOPE_HASH_EMPTY);
    expect(status).to.equal(STATUS_DEFINED);
  });

  it("T-AR-3: registerAgent only-owner — non-owner reverts", async function () {
    await expect(
      registry
        .connect(nonOwner)
        .registerAgent(AGENT_ID_SENTRY, agentSigner1.address, SCOPE_HASH_EMPTY, STATUS_DEFINED)
    ).to.be.revertedWithCustomError(registry, "OwnableUnauthorizedAccount");
  });

  it("T-AR-4: anti-replay — duplicate agentId reverts", async function () {
    await registry
      .connect(owner)
      .registerAgent(AGENT_ID_SENTRY, agentSigner1.address, SCOPE_HASH_EMPTY, STATUS_DEFINED);

    // Same agentId, different publicKey/scope/status — still must revert.
    await expect(
      registry
        .connect(owner)
        .registerAgent(AGENT_ID_SENTRY, agentSigner2.address, SCOPE_HASH_ALPHA, STATUS_SHADOW)
    ).to.be.revertedWith("AgentRegistry: agent already registered");

    // State unchanged: original registration intact.
    expect(await registry.totalAgents()).to.equal(1n);
    const [pk, scope, status] = await registry.getAgent(AGENT_ID_SENTRY);
    expect(pk).to.equal(agentSigner1.address);
    expect(scope).to.equal(SCOPE_HASH_EMPTY);
    expect(status).to.equal(STATUS_DEFINED);
  });

  it("T-AR-5: updateAgentStatus transitions status, emits AgentStatusUpdated, only-owner reverts", async function () {
    await registry
      .connect(owner)
      .registerAgent(AGENT_ID_SENTRY, agentSigner1.address, SCOPE_HASH_EMPTY, STATUS_DEFINED);

    // Owner can transition status.
    const tx = await registry.connect(owner).updateAgentStatus(AGENT_ID_SENTRY, STATUS_SHADOW);
    await expect(tx)
      .to.emit(registry, "AgentStatusUpdated")
      .withArgs(AGENT_ID_SENTRY, STATUS_DEFINED, STATUS_SHADOW);

    const [, , status] = await registry.getAgent(AGENT_ID_SENTRY);
    expect(status).to.equal(STATUS_SHADOW);

    // Non-owner cannot transition status.
    await expect(
      registry.connect(nonOwner).updateAgentStatus(AGENT_ID_SENTRY, STATUS_SUGGESTING)
    ).to.be.revertedWithCustomError(registry, "OwnableUnauthorizedAccount");

    // Update on unregistered agent reverts.
    await expect(
      registry.connect(owner).updateAgentStatus(AGENT_ID_GUARDIAN, STATUS_SHADOW)
    ).to.be.revertedWith("AgentRegistry: agent not registered");

    // Suspended sentinel works.
    await registry.connect(owner).updateAgentStatus(AGENT_ID_SENTRY, STATUS_SUSPENDED);
    const [, , statusAfter] = await registry.getAgent(AGENT_ID_SENTRY);
    expect(statusAfter).to.equal(STATUS_SUSPENDED);
  });

  it("T-AR-6: updateAgentScope changes scopeHash, emits AgentScopeUpdated, only-owner reverts", async function () {
    await registry
      .connect(owner)
      .registerAgent(AGENT_ID_SENTRY, agentSigner1.address, SCOPE_HASH_EMPTY, STATUS_DEFINED);

    // Owner can update scope.
    const tx = await registry.connect(owner).updateAgentScope(AGENT_ID_SENTRY, SCOPE_HASH_ALPHA);
    await expect(tx)
      .to.emit(registry, "AgentScopeUpdated")
      .withArgs(AGENT_ID_SENTRY, SCOPE_HASH_EMPTY, SCOPE_HASH_ALPHA);

    const [, scope] = await registry.getAgent(AGENT_ID_SENTRY);
    expect(scope).to.equal(SCOPE_HASH_ALPHA);

    // Subsequent update emits old → new correctly.
    const tx2 = await registry.connect(owner).updateAgentScope(AGENT_ID_SENTRY, SCOPE_HASH_BETA);
    await expect(tx2)
      .to.emit(registry, "AgentScopeUpdated")
      .withArgs(AGENT_ID_SENTRY, SCOPE_HASH_ALPHA, SCOPE_HASH_BETA);

    // Non-owner cannot update scope.
    await expect(
      registry.connect(nonOwner).updateAgentScope(AGENT_ID_SENTRY, SCOPE_HASH_EMPTY)
    ).to.be.revertedWithCustomError(registry, "OwnableUnauthorizedAccount");

    // Update on unregistered agent reverts.
    await expect(
      registry.connect(owner).updateAgentScope(AGENT_ID_GUARDIAN, SCOPE_HASH_ALPHA)
    ).to.be.revertedWith("AgentRegistry: agent not registered");
  });

  it("T-AR-7: getAgent view returns the registered tuple (and zero-tuple for unregistered)", async function () {
    // Unregistered agent returns zero-tuple sentinel.
    const [pk0, scope0, status0] = await registry.getAgent(AGENT_ID_SENTRY);
    expect(pk0).to.equal(ethers.ZeroAddress);
    expect(scope0).to.equal(ethers.ZeroHash);
    expect(status0).to.equal(0);
    expect(await registry.isRegistered(AGENT_ID_SENTRY)).to.equal(false);

    // After registration, getAgent returns the stored tuple.
    await registry
      .connect(owner)
      .registerAgent(AGENT_ID_GUARDIAN, agentSigner2.address, SCOPE_HASH_BETA, STATUS_SHADOW);

    const [pk, scope, status] = await registry.getAgent(AGENT_ID_GUARDIAN);
    expect(pk).to.equal(agentSigner2.address);
    expect(scope).to.equal(SCOPE_HASH_BETA);
    expect(status).to.equal(STATUS_SHADOW);
    expect(await registry.isRegistered(AGENT_ID_GUARDIAN)).to.equal(true);
  });

  it("T-AR-8: zero-bytes32 agentId guard reverts on registerAgent (plus zero-publicKey + invalid-status guards)", async function () {
    // Zero agentId reverts.
    await expect(
      registry
        .connect(owner)
        .registerAgent(ethers.ZeroHash, agentSigner1.address, SCOPE_HASH_EMPTY, STATUS_DEFINED)
    ).to.be.revertedWith("AgentRegistry: zero agentId");

    // Zero publicKey reverts.
    await expect(
      registry
        .connect(owner)
        .registerAgent(AGENT_ID_SENTRY, ethers.ZeroAddress, SCOPE_HASH_EMPTY, STATUS_DEFINED)
    ).to.be.revertedWith("AgentRegistry: zero publicKey");

    // Invalid status (7..254) reverts. Status space is 0..6 plus 255.
    await expect(
      registry.connect(owner).registerAgent(AGENT_ID_SENTRY, agentSigner1.address, SCOPE_HASH_EMPTY, 7)
    ).to.be.revertedWith("AgentRegistry: invalid status");
    await expect(
      registry.connect(owner).registerAgent(AGENT_ID_SENTRY, agentSigner1.address, SCOPE_HASH_EMPTY, 254)
    ).to.be.revertedWith("AgentRegistry: invalid status");

    // Boundary values 6 and 255 are accepted.
    await registry
      .connect(owner)
      .registerAgent(AGENT_ID_SENTRY, agentSigner1.address, SCOPE_HASH_EMPTY, 6);
    await registry
      .connect(owner)
      .registerAgent(AGENT_ID_GUARDIAN, agentSigner2.address, SCOPE_HASH_EMPTY, 255);
    expect(await registry.totalAgents()).to.equal(2n);
  });
});
