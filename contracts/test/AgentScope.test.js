/**
 * AgentScope — Operator series Phase O0 Hardhat Tests
 *
 * Pass 2C Section 3.2 specification + Session 2 architectural decisions:
 *   T-AS-1:  deployment defaults — owner correct, agentRegistry stored
 *   T-AS-2:  setAgentScopeRoot for registered agent (success + event,
 *            oldRoot=bytes32(0) on first call)
 *   T-AS-3:  setAgentScopeRoot for unregistered agent reverts AgentNotRegistered
 *   T-AS-4:  subsequent setAgentScopeRoot transitions oldRoot→newRoot in event
 *   T-AS-5:  setAgentScopeRoot only-owner — non-owner reverts
 *   T-AS-6:  getScopeRoot returns set value (or bytes32(0) for unset)
 *   T-AS-7:  zero-bytes32 agentId guard reverts InvalidAgentId
 *   T-AS-8:  DELIBERATE NON-CONSISTENCY — AgentRegistry.scopeHash and
 *            AgentScope.scopeRoot may differ (architectural property)
 *   T-AS-9:  setAgentScopeRoot to bytes32(0) is allowed (default state may be
 *            set explicitly, e.g. to revoke operational scope)
 *   T-AS-10: zero-address AgentRegistry constructor reverts
 *
 * Setup pattern: deploys AgentRegistry first, registers test agents in it,
 * then deploys AgentScope passing the AgentRegistry address. This mirrors
 * the Stream 2-deploy sequence (Session 1 deploys AgentRegistry before
 * Session 2 can deploy AgentScope).
 */

const { expect } = require("chai");
const { ethers } = require("hardhat");

describe("AgentScope (Operator series Phase O0)", function () {
  let registry, scope, owner, nonOwner, agentSigner1, agentSigner2;

  // Synthetic agentIds for test scenarios. Real agentIds in production are
  // keccak256(abi.encode(ioID_DID_address, ERC6551_TBA_address)) per Pass 2C Q9.
  const AGENT_ID_SENTRY = ethers.keccak256(ethers.toUtf8Bytes("test-agent-sentry"));
  const AGENT_ID_GUARDIAN = ethers.keccak256(ethers.toUtf8Bytes("test-agent-guardian"));
  const AGENT_ID_UNREGISTERED = ethers.keccak256(ethers.toUtf8Bytes("never-registered"));

  // Distinct scope roots for testing transitions and non-consistency.
  const SCOPE_HASH_REGISTERED = ethers.keccak256(ethers.toUtf8Bytes("scope-at-registration"));
  const SCOPE_HASH_OPERATIONAL_A = ethers.keccak256(ethers.toUtf8Bytes("operational-scope-a"));
  const SCOPE_HASH_OPERATIONAL_B = ethers.keccak256(ethers.toUtf8Bytes("operational-scope-b"));

  const STATUS_DEFINED = 0;

  beforeEach(async function () {
    [owner, nonOwner, agentSigner1, agentSigner2] = await ethers.getSigners();

    // Deploy AgentRegistry first (Session 1 dependency).
    const RegistryFactory = await ethers.getContractFactory("AgentRegistry");
    registry = await RegistryFactory.deploy(owner.address);
    await registry.waitForDeployment();

    // Register two agents so AgentScope tests can exercise the cross-validation.
    await registry.connect(owner).registerAgent(
      AGENT_ID_SENTRY,
      agentSigner1.address,
      SCOPE_HASH_REGISTERED,
      STATUS_DEFINED
    );
    await registry.connect(owner).registerAgent(
      AGENT_ID_GUARDIAN,
      agentSigner2.address,
      SCOPE_HASH_REGISTERED,
      STATUS_DEFINED
    );

    // Deploy AgentScope with AgentRegistry's address.
    const ScopeFactory = await ethers.getContractFactory("AgentScope");
    scope = await ScopeFactory.deploy(owner.address, await registry.getAddress());
    await scope.waitForDeployment();
  });

  it("T-AS-1: deploys with correct owner and stores AgentRegistry address", async function () {
    expect(await scope.owner()).to.equal(owner.address);
    expect(await scope.agentRegistry()).to.equal(await registry.getAddress());

    // Default scope for any agent is bytes32(0).
    expect(await scope.getScopeRoot(AGENT_ID_SENTRY)).to.equal(ethers.ZeroHash);
    expect(await scope.getScopeRoot(AGENT_ID_GUARDIAN)).to.equal(ethers.ZeroHash);
  });

  it("T-AS-2: setAgentScopeRoot for registered agent succeeds and emits event with oldRoot=bytes32(0)", async function () {
    const tx = await scope
      .connect(owner)
      .setAgentScopeRoot(AGENT_ID_SENTRY, SCOPE_HASH_OPERATIONAL_A);

    // Event carries oldRoot=bytes32(0) on first call (Pass 2C default state).
    const receipt = await tx.wait();
    const evt = receipt.logs.find((l) => {
      try { return scope.interface.parseLog(l).name === "AgentScopeRootSet"; }
      catch (_) { return false; }
    });
    expect(evt).to.not.be.undefined;
    const parsed = scope.interface.parseLog(evt);
    expect(parsed.args.agentId).to.equal(AGENT_ID_SENTRY);
    expect(parsed.args.oldRoot).to.equal(ethers.ZeroHash);
    expect(parsed.args.newRoot).to.equal(SCOPE_HASH_OPERATIONAL_A);
    expect(parsed.args.timestamp).to.be.a("bigint");

    // State updated.
    expect(await scope.getScopeRoot(AGENT_ID_SENTRY)).to.equal(SCOPE_HASH_OPERATIONAL_A);
  });

  it("T-AS-3: setAgentScopeRoot for unregistered agent reverts AgentNotRegistered", async function () {
    await expect(
      scope.connect(owner).setAgentScopeRoot(AGENT_ID_UNREGISTERED, SCOPE_HASH_OPERATIONAL_A)
    )
      .to.be.revertedWithCustomError(scope, "AgentNotRegistered")
      .withArgs(AGENT_ID_UNREGISTERED);

    // State unchanged.
    expect(await scope.getScopeRoot(AGENT_ID_UNREGISTERED)).to.equal(ethers.ZeroHash);
  });

  it("T-AS-4: subsequent setAgentScopeRoot transitions oldRoot→newRoot in event", async function () {
    // First call.
    await scope.connect(owner).setAgentScopeRoot(AGENT_ID_SENTRY, SCOPE_HASH_OPERATIONAL_A);

    // Second call — oldRoot should now be the previous value, not bytes32(0).
    const tx = await scope
      .connect(owner)
      .setAgentScopeRoot(AGENT_ID_SENTRY, SCOPE_HASH_OPERATIONAL_B);
    const receipt = await tx.wait();
    const parsed = scope.interface.parseLog(
      receipt.logs.find((l) => {
        try { return scope.interface.parseLog(l).name === "AgentScopeRootSet"; }
        catch (_) { return false; }
      })
    );
    expect(parsed.args.agentId).to.equal(AGENT_ID_SENTRY);
    expect(parsed.args.oldRoot).to.equal(SCOPE_HASH_OPERATIONAL_A);
    expect(parsed.args.newRoot).to.equal(SCOPE_HASH_OPERATIONAL_B);

    // State reflects latest value.
    expect(await scope.getScopeRoot(AGENT_ID_SENTRY)).to.equal(SCOPE_HASH_OPERATIONAL_B);
  });

  it("T-AS-5: setAgentScopeRoot only-owner — non-owner reverts", async function () {
    await expect(
      scope.connect(nonOwner).setAgentScopeRoot(AGENT_ID_SENTRY, SCOPE_HASH_OPERATIONAL_A)
    ).to.be.revertedWithCustomError(scope, "OwnableUnauthorizedAccount");
  });

  it("T-AS-6: getScopeRoot returns set value (and bytes32(0) for unset)", async function () {
    // Unset agent returns bytes32(0).
    expect(await scope.getScopeRoot(AGENT_ID_GUARDIAN)).to.equal(ethers.ZeroHash);

    // After set, returns the stored value.
    await scope.connect(owner).setAgentScopeRoot(AGENT_ID_GUARDIAN, SCOPE_HASH_OPERATIONAL_B);
    expect(await scope.getScopeRoot(AGENT_ID_GUARDIAN)).to.equal(SCOPE_HASH_OPERATIONAL_B);

    // Other agents are independent.
    expect(await scope.getScopeRoot(AGENT_ID_SENTRY)).to.equal(ethers.ZeroHash);
  });

  it("T-AS-7: zero-bytes32 agentId guard reverts InvalidAgentId", async function () {
    await expect(
      scope.connect(owner).setAgentScopeRoot(ethers.ZeroHash, SCOPE_HASH_OPERATIONAL_A)
    ).to.be.revertedWithCustomError(scope, "InvalidAgentId");
  });

  it("T-AS-8: deliberate non-consistency — AgentRegistry.scopeHash and AgentScope.scopeRoot may differ", async function () {
    // Pre-condition: AgentRegistry has SCOPE_HASH_REGISTERED for this agent
    // (set in beforeEach).
    const [, registeredScopeHash] = await registry.getAgent(AGENT_ID_SENTRY);
    expect(registeredScopeHash).to.equal(SCOPE_HASH_REGISTERED);

    // Operational scope set to a different value — must not revert.
    await scope.connect(owner).setAgentScopeRoot(AGENT_ID_SENTRY, SCOPE_HASH_OPERATIONAL_A);

    // Both contracts hold their respective values; neither matches the other.
    const [, registeredScopeAfter] = await registry.getAgent(AGENT_ID_SENTRY);
    const operationalScope = await scope.getScopeRoot(AGENT_ID_SENTRY);

    expect(registeredScopeAfter).to.equal(SCOPE_HASH_REGISTERED);
    expect(operationalScope).to.equal(SCOPE_HASH_OPERATIONAL_A);
    expect(operationalScope).to.not.equal(registeredScopeAfter);

    // This is the architectural property: AgentRegistry.scopeHash captures
    // the governance commitment; AgentScope.scopeRoot captures the
    // operational state. The two are deliberately allowed to differ.
    // Auditors compare them off-chain; the contracts do not enforce
    // consistency.
  });

  it("T-AS-9: setAgentScopeRoot to bytes32(0) is allowed (explicit revocation of operational scope)", async function () {
    // Set to a non-zero value first.
    await scope.connect(owner).setAgentScopeRoot(AGENT_ID_SENTRY, SCOPE_HASH_OPERATIONAL_A);
    expect(await scope.getScopeRoot(AGENT_ID_SENTRY)).to.equal(SCOPE_HASH_OPERATIONAL_A);

    // Setting to bytes32(0) explicitly must succeed (Pass 2C default-state value).
    const tx = await scope.connect(owner).setAgentScopeRoot(AGENT_ID_SENTRY, ethers.ZeroHash);
    await expect(tx)
      .to.emit(scope, "AgentScopeRootSet")
      .withArgs(AGENT_ID_SENTRY, SCOPE_HASH_OPERATIONAL_A, ethers.ZeroHash, await getLatestBlockTimestamp());

    expect(await scope.getScopeRoot(AGENT_ID_SENTRY)).to.equal(ethers.ZeroHash);
  });

  it("T-AS-10: zero-address AgentRegistry constructor reverts InvalidAgentRegistry", async function () {
    const ScopeFactory = await ethers.getContractFactory("AgentScope");
    await expect(
      ScopeFactory.deploy(owner.address, ethers.ZeroAddress)
    ).to.be.revertedWithCustomError(scope, "InvalidAgentRegistry");
  });

  // Helper: read latest block timestamp for tx event matching.
  async function getLatestBlockTimestamp() {
    const block = await ethers.provider.getBlock("latest");
    return BigInt(block.timestamp);
  }
});
