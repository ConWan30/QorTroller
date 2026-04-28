/**
 * AgentSlashing — Operator series Phase O0 Hardhat Tests
 *
 * Pass 2C Section 3.3 + Session 4 decisions Z-A (pure burn) and W-A
 * (partial slashing):
 *   T-AS4-1:  deployment defaults — owner, registry, vetoWindow, totalProposals=0
 *   T-AS4-2:  constructor zero-address AgentRegistry reverts InvalidAgentRegistry
 *   T-AS4-3:  postBond success + BondDeposited event + getBond reflects state
 *   T-AS4-4:  postBond unregistered agent reverts AgentNotRegistered
 *   T-AS4-5:  postBond zero value reverts InvalidBondAmount
 *   T-AS4-6:  postBond accumulates across multiple deposits for same agent
 *   T-AS4-7:  proposeSlash success + SlashProposed event + getProposal returns tuple
 *   T-AS4-8:  proposeSlash unregistered agent reverts AgentNotRegistered
 *   T-AS4-9:  proposeSlash slashAmount > bond reverts InsufficientBond
 *   T-AS4-10: proposeSlash input guards (zero slashAmount, zero evidenceHash, only-owner)
 *   T-AS4-11: veto success + SlashVetoed event + only-owner reverts
 *   T-AS4-12: veto reverts on Vetoed/Executed/elapsed-window (status + window guards)
 *   T-AS4-13: executeSlash before veto window reverts VetoWindowNotElapsed
 *   T-AS4-14: executeSlash after window: bond reduces, transfer to 0xdead verified
 *             via balance, SlashExecuted event with (proposalId, burnedAmount=slashAmount,
 *             distributedAmount=0)
 *   T-AS4-15: executeSlash on Vetoed reverts + only-owner reverts
 *   T-AS4-16: multiple proposals against same agent — partial slashing tracking +
 *             double-spend guard at execute time
 */

const { expect } = require("chai");
const { ethers } = require("hardhat");

describe("AgentSlashing (Operator series Phase O0)", function () {
  let registry, slashing, owner, nonOwner, bondPoster, agentSigner1, agentSigner2;

  const AGENT_ID_SENTRY = ethers.keccak256(ethers.toUtf8Bytes("test-agent-sentry"));
  const AGENT_ID_GUARDIAN = ethers.keccak256(ethers.toUtf8Bytes("test-agent-guardian"));
  const AGENT_ID_UNREGISTERED = ethers.keccak256(ethers.toUtf8Bytes("never-registered"));
  const SCOPE_HASH = ethers.keccak256(ethers.toUtf8Bytes("test-scope"));
  const STATUS_DEFINED = 0;

  const VETO_WINDOW_SECONDS = 86400n; // 24 hours per Pass 2C Section 3.3
  const BURN_ADDRESS = "0x000000000000000000000000000000000000dEaD";

  const EVIDENCE_HASH_A = ethers.keccak256(ethers.toUtf8Bytes("evidence-alpha"));
  const EVIDENCE_HASH_B = ethers.keccak256(ethers.toUtf8Bytes("evidence-beta"));
  const REASON_A = "agent-commit signed wrong target";
  const REASON_B = "agent attested to falsified PoAC chain";

  // Snapshot the Hardhat network state before each test, revert after each
  // test. This prevents evm_increaseTime calls (used to advance past the veto
  // window) from leaking time advancement into subsequent test files. Without
  // this isolation, downstream test files that assume the network clock is
  // close to system time (Phase 69 DataSovereignty, Phase 237 VAPIConsent)
  // would see post-advance timestamps and revert with "expired timestamp" /
  // stale-state errors.
  let _snapshotId;
  beforeEach(async function () {
    _snapshotId = await ethers.provider.send("evm_snapshot", []);

    [owner, nonOwner, bondPoster, agentSigner1, agentSigner2] = await ethers.getSigners();

    // Deploy AgentRegistry first (Session 1 dependency).
    const RegistryFactory = await ethers.getContractFactory("AgentRegistry");
    registry = await RegistryFactory.deploy(owner.address);
    await registry.waitForDeployment();

    // Register two test agents.
    await registry.connect(owner).registerAgent(
      AGENT_ID_SENTRY, agentSigner1.address, SCOPE_HASH, STATUS_DEFINED
    );
    await registry.connect(owner).registerAgent(
      AGENT_ID_GUARDIAN, agentSigner2.address, SCOPE_HASH, STATUS_DEFINED
    );

    // Deploy AgentSlashing with AgentRegistry's address and 24h veto window.
    const SlashingFactory = await ethers.getContractFactory("AgentSlashing");
    slashing = await SlashingFactory.deploy(
      owner.address,
      await registry.getAddress(),
      VETO_WINDOW_SECONDS
    );
    await slashing.waitForDeployment();
  });

  afterEach(async function () {
    // Revert the snapshot taken in beforeEach. This rolls back any time
    // advancement (evm_increaseTime) and any state changes, ensuring no
    // leakage into subsequent test files.
    if (_snapshotId !== undefined) {
      await ethers.provider.send("evm_revert", [_snapshotId]);
      _snapshotId = undefined;
    }
  });

  // Helper: advance time on Hardhat network past the veto window
  async function advanceVetoWindow() {
    await ethers.provider.send("evm_increaseTime", [Number(VETO_WINDOW_SECONDS) + 1]);
    await ethers.provider.send("evm_mine", []);
  }

  // Helper: post a bond and return the amount in wei
  async function postBondHelper(agentId, ethAmount = "1.0", signer = bondPoster) {
    const wei = ethers.parseEther(ethAmount);
    await slashing.connect(signer).postBond(agentId, { value: wei });
    return wei;
  }

  it("T-AS4-1: deploys with correct owner, registry, vetoWindow, and totalProposals=0", async function () {
    expect(await slashing.owner()).to.equal(owner.address);
    expect(await slashing.agentRegistry()).to.equal(await registry.getAddress());
    expect(await slashing.vetoWindowSeconds()).to.equal(VETO_WINDOW_SECONDS);
    expect(await slashing.totalProposals()).to.equal(0n);
    expect(await slashing.BURN_ADDRESS()).to.equal(BURN_ADDRESS);

    // Default bond for any agent is 0.
    expect(await slashing.getBond(AGENT_ID_SENTRY)).to.equal(0n);
  });

  it("T-AS4-2: constructor zero-address AgentRegistry reverts InvalidAgentRegistry", async function () {
    const SlashingFactory = await ethers.getContractFactory("AgentSlashing");
    await expect(
      SlashingFactory.deploy(owner.address, ethers.ZeroAddress, VETO_WINDOW_SECONDS)
    ).to.be.revertedWithCustomError(slashing, "InvalidAgentRegistry");
  });

  it("T-AS4-3: postBond succeeds and emits BondDeposited; getBond reflects state", async function () {
    const wei = ethers.parseEther("1.0");
    const tx = await slashing.connect(bondPoster).postBond(AGENT_ID_SENTRY, { value: wei });

    await expect(tx).to.emit(slashing, "BondDeposited").withArgs(AGENT_ID_SENTRY, wei);
    expect(await slashing.getBond(AGENT_ID_SENTRY)).to.equal(wei);

    // Other agents unaffected.
    expect(await slashing.getBond(AGENT_ID_GUARDIAN)).to.equal(0n);
  });

  it("T-AS4-4: postBond for unregistered agent reverts AgentNotRegistered", async function () {
    await expect(
      slashing.connect(bondPoster).postBond(
        AGENT_ID_UNREGISTERED,
        { value: ethers.parseEther("1.0") }
      )
    )
      .to.be.revertedWithCustomError(slashing, "AgentNotRegistered")
      .withArgs(AGENT_ID_UNREGISTERED);

    expect(await slashing.getBond(AGENT_ID_UNREGISTERED)).to.equal(0n);
  });

  it("T-AS4-5: postBond with zero value reverts InvalidBondAmount", async function () {
    await expect(
      slashing.connect(bondPoster).postBond(AGENT_ID_SENTRY, { value: 0n })
    ).to.be.revertedWithCustomError(slashing, "InvalidBondAmount");
  });

  it("T-AS4-6: postBond accumulates across multiple deposits for same agent", async function () {
    await postBondHelper(AGENT_ID_SENTRY, "1.0");
    await postBondHelper(AGENT_ID_SENTRY, "2.5");
    await postBondHelper(AGENT_ID_SENTRY, "0.3", agentSigner1);  // different depositor — still permissionless

    const expected = ethers.parseEther("3.8");
    expect(await slashing.getBond(AGENT_ID_SENTRY)).to.equal(expected);
  });

  it("T-AS4-7: proposeSlash succeeds, emits SlashProposed, getProposal returns tuple", async function () {
    await postBondHelper(AGENT_ID_SENTRY, "5.0");
    const slashAmount = ethers.parseEther("1.0");

    const tx = await slashing
      .connect(owner)
      .proposeSlash(AGENT_ID_SENTRY, REASON_A, slashAmount, EVIDENCE_HASH_A);

    await expect(tx)
      .to.emit(slashing, "SlashProposed")
      .withArgs(0n, AGENT_ID_SENTRY, slashAmount, EVIDENCE_HASH_A, REASON_A);

    expect(await slashing.totalProposals()).to.equal(1n);
    expect(await slashing.isProposed(0)).to.equal(true);

    const [agentId, sa, evHash, , status, reason] = await slashing.getProposal(0);
    expect(agentId).to.equal(AGENT_ID_SENTRY);
    expect(sa).to.equal(slashAmount);
    expect(evHash).to.equal(EVIDENCE_HASH_A);
    expect(status).to.equal(0);  // Proposed
    expect(reason).to.equal(REASON_A);

    // Out-of-bounds proposal id reverts.
    await expect(slashing.getProposal(1))
      .to.be.revertedWithCustomError(slashing, "ProposalNotFound")
      .withArgs(1);
  });

  it("T-AS4-8: proposeSlash on unregistered agent reverts AgentNotRegistered", async function () {
    await expect(
      slashing
        .connect(owner)
        .proposeSlash(AGENT_ID_UNREGISTERED, REASON_A, ethers.parseEther("1.0"), EVIDENCE_HASH_A)
    )
      .to.be.revertedWithCustomError(slashing, "AgentNotRegistered")
      .withArgs(AGENT_ID_UNREGISTERED);
  });

  it("T-AS4-9: proposeSlash with slashAmount > bond reverts InsufficientBond", async function () {
    await postBondHelper(AGENT_ID_SENTRY, "1.0");
    const tooMuch = ethers.parseEther("2.0");

    await expect(
      slashing.connect(owner).proposeSlash(AGENT_ID_SENTRY, REASON_A, tooMuch, EVIDENCE_HASH_A)
    )
      .to.be.revertedWithCustomError(slashing, "InsufficientBond")
      .withArgs(tooMuch, ethers.parseEther("1.0"));
  });

  it("T-AS4-10: proposeSlash input guards — zero slashAmount, zero evidenceHash, only-owner", async function () {
    await postBondHelper(AGENT_ID_SENTRY, "1.0");
    const validAmount = ethers.parseEther("0.5");

    // Zero slashAmount.
    await expect(
      slashing.connect(owner).proposeSlash(AGENT_ID_SENTRY, REASON_A, 0n, EVIDENCE_HASH_A)
    ).to.be.revertedWithCustomError(slashing, "InvalidSlashAmount");

    // Zero evidenceHash.
    await expect(
      slashing.connect(owner).proposeSlash(AGENT_ID_SENTRY, REASON_A, validAmount, ethers.ZeroHash)
    ).to.be.revertedWithCustomError(slashing, "InvalidEvidenceHash");

    // Non-owner.
    await expect(
      slashing.connect(nonOwner).proposeSlash(AGENT_ID_SENTRY, REASON_A, validAmount, EVIDENCE_HASH_A)
    ).to.be.revertedWithCustomError(slashing, "OwnableUnauthorizedAccount");
  });

  it("T-AS4-11: veto succeeds during window, emits SlashVetoed, only-owner reverts", async function () {
    await postBondHelper(AGENT_ID_SENTRY, "5.0");
    await slashing.connect(owner).proposeSlash(
      AGENT_ID_SENTRY, REASON_A, ethers.parseEther("1.0"), EVIDENCE_HASH_A
    );

    // Non-owner cannot veto.
    await expect(slashing.connect(nonOwner).veto(0))
      .to.be.revertedWithCustomError(slashing, "OwnableUnauthorizedAccount");

    // Owner veto succeeds during window.
    const tx = await slashing.connect(owner).veto(0);
    await expect(tx).to.emit(slashing, "SlashVetoed").withArgs(0n, owner.address);

    // Status transitioned to Vetoed (1).
    const [, , , , status] = await slashing.getProposal(0);
    expect(status).to.equal(1);
    expect(await slashing.isProposed(0)).to.equal(false);
  });

  it("T-AS4-12: veto status + window guards — already-Vetoed, already-Executed, elapsed-window, not-found", async function () {
    await postBondHelper(AGENT_ID_SENTRY, "5.0");

    // Proposal 0 — vetoed, then second veto reverts.
    await slashing.connect(owner).proposeSlash(
      AGENT_ID_SENTRY, REASON_A, ethers.parseEther("1.0"), EVIDENCE_HASH_A
    );
    await slashing.connect(owner).veto(0);
    await expect(slashing.connect(owner).veto(0))
      .to.be.revertedWithCustomError(slashing, "ProposalNotProposed")
      .withArgs(0n, 1);  // status=Vetoed

    // Proposal 1 — executed via window expiry; veto reverts on Executed.
    await slashing.connect(owner).proposeSlash(
      AGENT_ID_SENTRY, REASON_B, ethers.parseEther("1.0"), EVIDENCE_HASH_B
    );
    await advanceVetoWindow();
    await slashing.connect(owner).executeSlash(1);
    await expect(slashing.connect(owner).veto(1))
      .to.be.revertedWithCustomError(slashing, "ProposalNotProposed")
      .withArgs(1n, 2);  // status=Executed

    // Proposal 2 — Proposed but window elapsed; veto reverts VetoWindowElapsed.
    const evHashC = ethers.keccak256(ethers.toUtf8Bytes("evidence-gamma"));
    await slashing.connect(owner).proposeSlash(
      AGENT_ID_SENTRY, "third reason", ethers.parseEther("0.5"), evHashC
    );
    await advanceVetoWindow();
    await expect(slashing.connect(owner).veto(2))
      .to.be.revertedWithCustomError(slashing, "VetoWindowElapsed");

    // Out-of-bounds proposalId reverts ProposalNotFound.
    await expect(slashing.connect(owner).veto(99))
      .to.be.revertedWithCustomError(slashing, "ProposalNotFound")
      .withArgs(99);
  });

  it("T-AS4-13: executeSlash before veto window reverts VetoWindowNotElapsed", async function () {
    await postBondHelper(AGENT_ID_SENTRY, "5.0");
    await slashing.connect(owner).proposeSlash(
      AGENT_ID_SENTRY, REASON_A, ethers.parseEther("1.0"), EVIDENCE_HASH_A
    );

    // Window not elapsed — execute reverts.
    await expect(slashing.connect(owner).executeSlash(0))
      .to.be.revertedWithCustomError(slashing, "VetoWindowNotElapsed");
  });

  it("T-AS4-14: executeSlash after window — bond reduces, transfer to 0xdead, SlashExecuted event", async function () {
    const initialBond = ethers.parseEther("5.0");
    await postBondHelper(AGENT_ID_SENTRY, "5.0");
    const slashAmount = ethers.parseEther("1.5");

    await slashing.connect(owner).proposeSlash(
      AGENT_ID_SENTRY, REASON_A, slashAmount, EVIDENCE_HASH_A
    );

    // Capture pre-execute burn-address balance.
    const burnBefore = await ethers.provider.getBalance(BURN_ADDRESS);

    await advanceVetoWindow();

    const tx = await slashing.connect(owner).executeSlash(0);

    // SlashExecuted event with burnedAmount=slashAmount, distributedAmount=0 (Z-A pure burn).
    await expect(tx)
      .to.emit(slashing, "SlashExecuted")
      .withArgs(0n, slashAmount, 0n);

    // Bond reduced by slashAmount.
    expect(await slashing.getBond(AGENT_ID_SENTRY)).to.equal(initialBond - slashAmount);

    // Burn address balance increased by slashAmount.
    const burnAfter = await ethers.provider.getBalance(BURN_ADDRESS);
    expect(burnAfter - burnBefore).to.equal(slashAmount);

    // Status transitioned to Executed (2).
    const [, , , , status] = await slashing.getProposal(0);
    expect(status).to.equal(2);
  });

  it("T-AS4-15: executeSlash on Vetoed reverts; only-owner reverts", async function () {
    await postBondHelper(AGENT_ID_SENTRY, "5.0");
    await slashing.connect(owner).proposeSlash(
      AGENT_ID_SENTRY, REASON_A, ethers.parseEther("1.0"), EVIDENCE_HASH_A
    );

    // Veto first.
    await slashing.connect(owner).veto(0);
    await advanceVetoWindow();

    // Execute on Vetoed reverts.
    await expect(slashing.connect(owner).executeSlash(0))
      .to.be.revertedWithCustomError(slashing, "ProposalNotProposed")
      .withArgs(0n, 1);  // status=Vetoed

    // Non-owner execute reverts (separate proposal).
    await slashing.connect(owner).proposeSlash(
      AGENT_ID_SENTRY, REASON_B, ethers.parseEther("1.0"), EVIDENCE_HASH_B
    );
    await advanceVetoWindow();
    await expect(slashing.connect(nonOwner).executeSlash(1))
      .to.be.revertedWithCustomError(slashing, "OwnableUnauthorizedAccount");
  });

  it("T-AS4-16: multiple proposals + partial slashing tracking + double-spend guard", async function () {
    // Bond 3 IOTX. Two proposals each for 2 IOTX. Both pass propose (2 <= 3).
    // After first execute, bond = 1 IOTX. Second execute must revert
    // InsufficientBond (2 > 1) per double-spend guard.
    await postBondHelper(AGENT_ID_SENTRY, "3.0");

    await slashing.connect(owner).proposeSlash(
      AGENT_ID_SENTRY, REASON_A, ethers.parseEther("2.0"), EVIDENCE_HASH_A
    );
    await slashing.connect(owner).proposeSlash(
      AGENT_ID_SENTRY, REASON_B, ethers.parseEther("2.0"), EVIDENCE_HASH_B
    );

    expect(await slashing.totalProposals()).to.equal(2n);

    await advanceVetoWindow();

    // First execute succeeds, bond reduces from 3 to 1.
    await slashing.connect(owner).executeSlash(0);
    expect(await slashing.getBond(AGENT_ID_SENTRY)).to.equal(ethers.parseEther("1.0"));

    // Second execute reverts InsufficientBond (slashAmount=2 > bond=1).
    await expect(slashing.connect(owner).executeSlash(1))
      .to.be.revertedWithCustomError(slashing, "InsufficientBond")
      .withArgs(ethers.parseEther("2.0"), ethers.parseEther("1.0"));

    // Bond unchanged after the failed execute.
    expect(await slashing.getBond(AGENT_ID_SENTRY)).to.equal(ethers.parseEther("1.0"));

    // Proposal 1 still in Proposed status (failed execute did not transition).
    expect(await slashing.isProposed(1)).to.equal(true);
  });
});
