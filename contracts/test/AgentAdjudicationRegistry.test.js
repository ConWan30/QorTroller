/**
 * AgentAdjudicationRegistry — Operator series Phase O0 Hardhat Tests
 *
 * Pass 2C Section 3.5 + 4.3 + Session 5 decisions U-Enum (actionType as
 * Solidity enum), V-A (reserved actionTypes pass validation), and UNION
 * storage (anchorId-keyed array + per-agent index + actionHash anti-replay).
 *
 *   T-AAR-1:  deployment defaults — owner, agentRegistry, agentScope, count=0
 *   T-AAR-2:  constructor zero-address agentRegistry reverts
 *   T-AAR-3:  constructor zero-address agentScope reverts
 *   T-AAR-4:  anchorAgentAction success for AGENT_COMMIT (event with all 6 fields)
 *   T-AAR-5:  anchorAgentAction success for PHYSICAL_DATA_ATTESTATION
 *   T-AAR-6:  anchorAgentAction success for AUDIT_LOG_CHECKPOINT (V-A reserved-as-doc)
 *   T-AAR-7:  anchorAgentAction success for BOUNDARY_UPDATE (V-A reserved-as-doc)
 *   T-AAR-8:  anchorAgentAction unregistered agent reverts AgentNotRegistered
 *   T-AAR-9:  anchorAgentAction registered-but-no-scope reverts InvalidAgentScope
 *             (the requireAgentScope path; Phase O0's default-state behavior)
 *   T-AAR-10: anchorAgentAction zero actionHash reverts InvalidActionHash
 *   T-AAR-11: anchorAgentAction duplicate actionHash reverts DuplicateActionHash
 *             (anti-replay enforcement; load-bearing under UNION storage)
 *   T-AAR-12: anchorAgentAction invalid enum value (4+) reverts via Solidity bounds check
 *   T-AAR-13: anchorAgentAction only-owner — non-owner reverts
 *   T-AAR-14: getAnchor returns correct tuple; out-of-bounds reverts AnchorNotFound
 *   T-AAR-15: getAnchorCount monotonic increment across multiple anchors
 *   T-AAR-16: getAgentAnchors returns correct array for agent (multi-actionType)
 *   T-AAR-17: getAgentAnchors returns empty array for never-anchored agent
 *   T-AAR-18: isRecorded reflects anchor state (true after anchor, false otherwise)
 *   T-AAR-19: getAnchorByHash returns correct anchorId; unknown hash reverts
 *   T-AAR-20: anchorId monotonic across all agents (global sequence)
 *
 * Setup pattern: deploys AgentRegistry, registers test agents, deploys
 * AgentScope and SETS scope roots (so requireAgentScope passes), then
 * deploys AgentAdjudicationRegistry. Tests exercise the contract against
 * registered+scoped agents. AuditLog and AgentSlashing are NOT deployed
 * in the test setup (AgentAdjudicationRegistry does not depend on them).
 */

const { expect } = require("chai");
const { ethers } = require("hardhat");

describe("AgentAdjudicationRegistry (Operator series Phase O0)", function () {
  let registry, scope, adj, owner, nonOwner, agentSigner1, agentSigner2;

  const AGENT_ID_SENTRY = ethers.keccak256(ethers.toUtf8Bytes("test-agent-sentry"));
  const AGENT_ID_GUARDIAN = ethers.keccak256(ethers.toUtf8Bytes("test-agent-guardian"));
  const AGENT_ID_REGISTERED_NO_SCOPE = ethers.keccak256(
    ethers.toUtf8Bytes("test-agent-registered-no-scope")
  );
  const AGENT_ID_UNREGISTERED = ethers.keccak256(ethers.toUtf8Bytes("never-registered"));

  const SCOPE_HASH_REGISTERED = ethers.keccak256(ethers.toUtf8Bytes("scope-at-registration"));
  const SCOPE_HASH_OPERATIONAL = ethers.keccak256(ethers.toUtf8Bytes("operational-scope"));

  const ACTION_HASH_A = ethers.keccak256(ethers.toUtf8Bytes("action-alpha"));
  const ACTION_HASH_B = ethers.keccak256(ethers.toUtf8Bytes("action-beta"));
  const ACTION_HASH_C = ethers.keccak256(ethers.toUtf8Bytes("action-gamma"));
  const ACTION_HASH_D = ethers.keccak256(ethers.toUtf8Bytes("action-delta"));
  const ACTION_HASH_E = ethers.keccak256(ethers.toUtf8Bytes("action-epsilon"));
  const ACTION_HASH_F = ethers.keccak256(ethers.toUtf8Bytes("action-zeta"));

  // ActionType enum values (matching the contract's enum order).
  const AGENT_COMMIT = 0;
  const PHYSICAL_DATA_ATTESTATION = 1;
  const AUDIT_LOG_CHECKPOINT = 2;  // reserved per V-A
  const BOUNDARY_UPDATE = 3;        // reserved per V-A

  const STATUS_DEFINED = 0;

  beforeEach(async function () {
    [owner, nonOwner, agentSigner1, agentSigner2] = await ethers.getSigners();

    // Deploy AgentRegistry (Session 1 dependency).
    const RegistryFactory = await ethers.getContractFactory("AgentRegistry");
    registry = await RegistryFactory.deploy(owner.address);
    await registry.waitForDeployment();

    // Register three test agents:
    //   AGENT_ID_SENTRY     — registered + scoped (anchors should succeed)
    //   AGENT_ID_GUARDIAN   — registered + scoped (separate agent for index tests)
    //   AGENT_ID_REGISTERED_NO_SCOPE — registered but NO scope set
    //                                  (tests requireAgentScope rejection)
    await registry.connect(owner).registerAgent(
      AGENT_ID_SENTRY, agentSigner1.address, SCOPE_HASH_REGISTERED, STATUS_DEFINED
    );
    await registry.connect(owner).registerAgent(
      AGENT_ID_GUARDIAN, agentSigner2.address, SCOPE_HASH_REGISTERED, STATUS_DEFINED
    );
    await registry.connect(owner).registerAgent(
      AGENT_ID_REGISTERED_NO_SCOPE, agentSigner1.address, SCOPE_HASH_REGISTERED, STATUS_DEFINED
    );

    // Deploy AgentScope (Session 2 dependency).
    const ScopeFactory = await ethers.getContractFactory("AgentScope");
    scope = await ScopeFactory.deploy(owner.address, await registry.getAddress());
    await scope.waitForDeployment();

    // Set operational scope for SENTRY and GUARDIAN. Leave
    // REGISTERED_NO_SCOPE without scope to test requireAgentScope rejection.
    await scope.connect(owner).setAgentScopeRoot(AGENT_ID_SENTRY, SCOPE_HASH_OPERATIONAL);
    await scope.connect(owner).setAgentScopeRoot(AGENT_ID_GUARDIAN, SCOPE_HASH_OPERATIONAL);

    // Deploy AgentAdjudicationRegistry with both dependency addresses.
    const AdjFactory = await ethers.getContractFactory("AgentAdjudicationRegistry");
    adj = await AdjFactory.deploy(
      owner.address,
      await registry.getAddress(),
      await scope.getAddress()
    );
    await adj.waitForDeployment();
  });

  it("T-AAR-1: deploys with correct owner, agentRegistry, agentScope, getAnchorCount=0", async function () {
    expect(await adj.owner()).to.equal(owner.address);
    expect(await adj.agentRegistry()).to.equal(await registry.getAddress());
    expect(await adj.agentScope()).to.equal(await scope.getAddress());
    expect(await adj.getAnchorCount()).to.equal(0n);

    // Default state: no actionHash recorded.
    expect(await adj.isRecorded(ACTION_HASH_A)).to.equal(false);
    // Default state: no anchors for any agent.
    expect((await adj.getAgentAnchors(AGENT_ID_SENTRY)).length).to.equal(0);
  });

  it("T-AAR-2: constructor zero-address agentRegistry reverts InvalidAgentRegistry", async function () {
    const AdjFactory = await ethers.getContractFactory("AgentAdjudicationRegistry");
    await expect(
      AdjFactory.deploy(owner.address, ethers.ZeroAddress, await scope.getAddress())
    ).to.be.revertedWithCustomError(adj, "InvalidAgentRegistry");
  });

  it("T-AAR-3: constructor zero-address agentScope reverts InvalidAgentScopeContract", async function () {
    const AdjFactory = await ethers.getContractFactory("AgentAdjudicationRegistry");
    await expect(
      AdjFactory.deploy(owner.address, await registry.getAddress(), ethers.ZeroAddress)
    ).to.be.revertedWithCustomError(adj, "InvalidAgentScopeContract");
  });

  it("T-AAR-4: anchorAgentAction success for AGENT_COMMIT — event with all 6 fields", async function () {
    const tx = await adj
      .connect(owner)
      .anchorAgentAction(AGENT_ID_SENTRY, AGENT_COMMIT, ACTION_HASH_A);
    const receipt = await tx.wait();
    const block = await ethers.provider.getBlock(receipt.blockNumber);

    await expect(tx)
      .to.emit(adj, "AgentActionAnchored")
      .withArgs(
        0n,                         // anchorId
        AGENT_ID_SENTRY,            // agentId
        AGENT_COMMIT,               // actionType
        ACTION_HASH_A,              // actionHash
        BigInt(block.timestamp),    // timestamp
        BigInt(receipt.blockNumber) // blockNumber
      );

    expect(await adj.getAnchorCount()).to.equal(1n);
    expect(await adj.isRecorded(ACTION_HASH_A)).to.equal(true);
  });

  it("T-AAR-5: anchorAgentAction success for PHYSICAL_DATA_ATTESTATION", async function () {
    await adj
      .connect(owner)
      .anchorAgentAction(AGENT_ID_SENTRY, PHYSICAL_DATA_ATTESTATION, ACTION_HASH_A);

    const [, actionType] = await adj.getAnchor(0);
    expect(actionType).to.equal(PHYSICAL_DATA_ATTESTATION);
  });

  it("T-AAR-6: anchorAgentAction success for AUDIT_LOG_CHECKPOINT (V-A reserved-as-documentation)", async function () {
    // Decision V-A: reserved actionTypes pass validation in Phase O0;
    // the "reserved" status is operator-policy documentation, not contract
    // enforcement. The reserved value cleanly casts to ActionType and the
    // anchor proceeds.
    await adj
      .connect(owner)
      .anchorAgentAction(AGENT_ID_SENTRY, AUDIT_LOG_CHECKPOINT, ACTION_HASH_A);

    expect(await adj.getAnchorCount()).to.equal(1n);
    const [, actionType] = await adj.getAnchor(0);
    expect(actionType).to.equal(AUDIT_LOG_CHECKPOINT);
  });

  it("T-AAR-7: anchorAgentAction success for BOUNDARY_UPDATE (V-A reserved-as-documentation)", async function () {
    await adj
      .connect(owner)
      .anchorAgentAction(AGENT_ID_SENTRY, BOUNDARY_UPDATE, ACTION_HASH_A);

    const [, actionType] = await adj.getAnchor(0);
    expect(actionType).to.equal(BOUNDARY_UPDATE);
  });

  it("T-AAR-8: anchorAgentAction unregistered agent reverts AgentNotRegistered", async function () {
    await expect(
      adj.connect(owner).anchorAgentAction(AGENT_ID_UNREGISTERED, AGENT_COMMIT, ACTION_HASH_A)
    )
      .to.be.revertedWithCustomError(adj, "AgentNotRegistered")
      .withArgs(AGENT_ID_UNREGISTERED);
  });

  it("T-AAR-9: anchorAgentAction registered-but-no-scope reverts InvalidAgentScope (requireAgentScope path)", async function () {
    // AGENT_ID_REGISTERED_NO_SCOPE is registered in AgentRegistry (passes
    // requireAgentRegistered) but has no scope set in AgentScope (fails
    // requireAgentScope). This exercises the Phase O0 default-state behavior:
    // anchors are universally rejected because no agents have scope set yet.
    await expect(
      adj.connect(owner).anchorAgentAction(AGENT_ID_REGISTERED_NO_SCOPE, AGENT_COMMIT, ACTION_HASH_A)
    )
      .to.be.revertedWithCustomError(adj, "InvalidAgentScope")
      .withArgs(AGENT_ID_REGISTERED_NO_SCOPE);
  });

  it("T-AAR-10: anchorAgentAction zero actionHash reverts InvalidActionHash", async function () {
    await expect(
      adj.connect(owner).anchorAgentAction(AGENT_ID_SENTRY, AGENT_COMMIT, ethers.ZeroHash)
    ).to.be.revertedWithCustomError(adj, "InvalidActionHash");
  });

  it("T-AAR-11: anchorAgentAction duplicate actionHash reverts DuplicateActionHash (anti-replay)", async function () {
    // First anchor succeeds.
    await adj.connect(owner).anchorAgentAction(AGENT_ID_SENTRY, AGENT_COMMIT, ACTION_HASH_A);

    // Same actionHash, different agent and actionType — must still revert
    // because anti-replay is global across all anchors.
    await expect(
      adj.connect(owner).anchorAgentAction(AGENT_ID_GUARDIAN, PHYSICAL_DATA_ATTESTATION, ACTION_HASH_A)
    )
      .to.be.revertedWithCustomError(adj, "DuplicateActionHash")
      .withArgs(ACTION_HASH_A);

    // Same agent, different actionHash — should succeed (anti-replay is per-hash, not per-agent).
    await adj.connect(owner).anchorAgentAction(AGENT_ID_SENTRY, AGENT_COMMIT, ACTION_HASH_B);
    expect(await adj.getAnchorCount()).to.equal(2n);
  });

  it("T-AAR-12: anchorAgentAction invalid enum value reverts via Solidity bounds check", async function () {
    // ActionType has 4 entries (0..3). Casting uint8=4 to ActionType triggers
    // Solidity's automatic enum bounds check, reverting with Panic(0x21).
    // ethers handles the encoding; the enum decoder on the contract side
    // produces the panic.
    await expect(
      adj.connect(owner).anchorAgentAction(AGENT_ID_SENTRY, 4, ACTION_HASH_A)
    ).to.be.reverted;  // Panic(0x21) — ethers may not match a custom error here

    await expect(
      adj.connect(owner).anchorAgentAction(AGENT_ID_SENTRY, 255, ACTION_HASH_A)
    ).to.be.reverted;
  });

  it("T-AAR-13: anchorAgentAction only-owner — non-owner reverts", async function () {
    await expect(
      adj.connect(nonOwner).anchorAgentAction(AGENT_ID_SENTRY, AGENT_COMMIT, ACTION_HASH_A)
    ).to.be.revertedWithCustomError(adj, "OwnableUnauthorizedAccount");
  });

  it("T-AAR-14: getAnchor returns correct tuple; out-of-bounds reverts AnchorNotFound", async function () {
    await adj.connect(owner).anchorAgentAction(AGENT_ID_SENTRY, AGENT_COMMIT, ACTION_HASH_A);

    const [agentId, actionType, actionHash, ts, blk] = await adj.getAnchor(0);
    expect(agentId).to.equal(AGENT_ID_SENTRY);
    expect(actionType).to.equal(AGENT_COMMIT);
    expect(actionHash).to.equal(ACTION_HASH_A);
    expect(ts).to.be.greaterThan(0n);
    expect(blk).to.be.greaterThan(0n);

    await expect(adj.getAnchor(1))
      .to.be.revertedWithCustomError(adj, "AnchorNotFound")
      .withArgs(1);
  });

  it("T-AAR-15: getAnchorCount monotonic increment across multiple anchors", async function () {
    expect(await adj.getAnchorCount()).to.equal(0n);

    await adj.connect(owner).anchorAgentAction(AGENT_ID_SENTRY, AGENT_COMMIT, ACTION_HASH_A);
    expect(await adj.getAnchorCount()).to.equal(1n);

    await adj.connect(owner).anchorAgentAction(AGENT_ID_GUARDIAN, AGENT_COMMIT, ACTION_HASH_B);
    expect(await adj.getAnchorCount()).to.equal(2n);

    await adj.connect(owner).anchorAgentAction(AGENT_ID_SENTRY, PHYSICAL_DATA_ATTESTATION, ACTION_HASH_C);
    expect(await adj.getAnchorCount()).to.equal(3n);
  });

  it("T-AAR-16: getAgentAnchors returns correct array for agent across multiple actionTypes", async function () {
    // Anchor SENTRY with three different actionTypes.
    await adj.connect(owner).anchorAgentAction(AGENT_ID_SENTRY, AGENT_COMMIT, ACTION_HASH_A);
    await adj.connect(owner).anchorAgentAction(AGENT_ID_GUARDIAN, AGENT_COMMIT, ACTION_HASH_B); // separate agent
    await adj.connect(owner).anchorAgentAction(AGENT_ID_SENTRY, PHYSICAL_DATA_ATTESTATION, ACTION_HASH_C);
    await adj.connect(owner).anchorAgentAction(AGENT_ID_SENTRY, AUDIT_LOG_CHECKPOINT, ACTION_HASH_D);

    const sentryAnchors = await adj.getAgentAnchors(AGENT_ID_SENTRY);
    expect(sentryAnchors.length).to.equal(3);
    expect(sentryAnchors[0]).to.equal(0n);
    expect(sentryAnchors[1]).to.equal(2n);
    expect(sentryAnchors[2]).to.equal(3n);

    const guardianAnchors = await adj.getAgentAnchors(AGENT_ID_GUARDIAN);
    expect(guardianAnchors.length).to.equal(1);
    expect(guardianAnchors[0]).to.equal(1n);
  });

  it("T-AAR-17: getAgentAnchors returns empty array for never-anchored agent", async function () {
    const arr = await adj.getAgentAnchors(AGENT_ID_GUARDIAN);
    expect(arr.length).to.equal(0);
  });

  it("T-AAR-18: isRecorded reflects anchor state (true after anchor, false otherwise)", async function () {
    expect(await adj.isRecorded(ACTION_HASH_A)).to.equal(false);
    expect(await adj.isRecorded(ACTION_HASH_B)).to.equal(false);

    await adj.connect(owner).anchorAgentAction(AGENT_ID_SENTRY, AGENT_COMMIT, ACTION_HASH_A);

    expect(await adj.isRecorded(ACTION_HASH_A)).to.equal(true);
    expect(await adj.isRecorded(ACTION_HASH_B)).to.equal(false);
  });

  it("T-AAR-19: getAnchorByHash returns correct anchorId; unknown hash reverts", async function () {
    // Unknown hash reverts.
    await expect(adj.getAnchorByHash(ACTION_HASH_A))
      .to.be.revertedWithCustomError(adj, "ActionHashNotFound")
      .withArgs(ACTION_HASH_A);

    await adj.connect(owner).anchorAgentAction(AGENT_ID_SENTRY, AGENT_COMMIT, ACTION_HASH_A);
    expect(await adj.getAnchorByHash(ACTION_HASH_A)).to.equal(0n);

    await adj.connect(owner).anchorAgentAction(AGENT_ID_GUARDIAN, AGENT_COMMIT, ACTION_HASH_B);
    expect(await adj.getAnchorByHash(ACTION_HASH_B)).to.equal(1n);

    // Sentinel correctness: anchorId=0 (the first anchor) must be returned
    // as 0, not as 1 (the +1 sentinel internal storage). Verifies the
    // un-shift is correct.
    expect(await adj.getAnchorByHash(ACTION_HASH_A)).to.equal(0n);
  });

  it("T-AAR-20: anchorId monotonic across all agents (global sequence)", async function () {
    // anchorId increments globally regardless of which agent anchors.
    await adj.connect(owner).anchorAgentAction(AGENT_ID_SENTRY, AGENT_COMMIT, ACTION_HASH_A);
    await adj.connect(owner).anchorAgentAction(AGENT_ID_GUARDIAN, PHYSICAL_DATA_ATTESTATION, ACTION_HASH_B);
    await adj.connect(owner).anchorAgentAction(AGENT_ID_SENTRY, AUDIT_LOG_CHECKPOINT, ACTION_HASH_C);
    await adj.connect(owner).anchorAgentAction(AGENT_ID_GUARDIAN, BOUNDARY_UPDATE, ACTION_HASH_D);
    await adj.connect(owner).anchorAgentAction(AGENT_ID_SENTRY, AGENT_COMMIT, ACTION_HASH_E);
    await adj.connect(owner).anchorAgentAction(AGENT_ID_GUARDIAN, AGENT_COMMIT, ACTION_HASH_F);

    expect(await adj.getAnchorCount()).to.equal(6n);
    expect(await adj.getAnchorByHash(ACTION_HASH_A)).to.equal(0n);
    expect(await adj.getAnchorByHash(ACTION_HASH_B)).to.equal(1n);
    expect(await adj.getAnchorByHash(ACTION_HASH_C)).to.equal(2n);
    expect(await adj.getAnchorByHash(ACTION_HASH_D)).to.equal(3n);
    expect(await adj.getAnchorByHash(ACTION_HASH_E)).to.equal(4n);
    expect(await adj.getAnchorByHash(ACTION_HASH_F)).to.equal(5n);
  });
});
