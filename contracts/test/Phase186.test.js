/**
 * Phase 186 — SeparationRatioRegistry Phase 186 Extension Hardhat Tests (6 tests)
 *
 * Tests for registerAttestation() + attestedRenewCommit() functions (WIF-032 W2 closure).
 * SeparationRatioRegistry.sol extended with AttestationRecord struct and two new functions.
 * IMPLEMENTED 2026-05-24 (this is now the live validation suite — describe.skip removed).
 * Contract is code-complete + locally validated; testnet REDEPLOY is wallet-gated
 * (SeparationRatioRegistry is LIVE at 0xB39C…; the extension ships on the next funded deploy).
 *
 * T186-1: registerAttestation stores record correctly; getAttestation returns it
 * T186-2: attestedRenewCommit succeeds with valid attestation; emits AttestationBoundRenewal
 * T186-3: attestedRenewCommit reverts when attestation already used (anti-replay)
 * T186-4: attestedRenewCommit reverts when attestation expired
 * T186-5: registerAttestation reverts on zero attestationHash
 * T186-6: AttestationRegistered event emitted correctly on registerAttestation
 */

const { expect } = require("chai");
const { ethers } = require("hardhat");
const { time } = require("@nomicfoundation/hardhat-network-helpers");

describe("SeparationRatioRegistry Phase 186 (Attestation-Bound Renewal)", function () {
  // IMPLEMENTED 2026-05-24 — describe.skip removed (was: autoresearch-specced
  // 2b01831b / WIF-032 W2, tests-ahead-of-implementation per the
  // autoresearch-test-landing-gate process rule). The contract methods
  // registerAttestation, attestedRenewCommit, getAttestation + the
  // AttestationRecord struct + AttestationRegistered/AttestationBoundRenewal
  // events now EXIST on SeparationRatioRegistry.sol (the on-chain counterpart of
  // the bridge's Phase 186 AttestationBoundRenewalAgent). These preserved tests
  // are now the live validation suite for that implementation.
  //
  // Implemented under the standard discipline (V-check -> code -> P-check ->
  // commit). Testnet REDEPLOY remains wallet-gated: SeparationRatioRegistry is
  // LIVE at 0xB39C…; the source extension ships on the next funded deploy. Until
  // then the live on-chain bytecode lacks these methods (documented divergence).
  this.timeout(120000); // 2 minutes — viaIR compilation + ReentrancyGuard may be slow

  let registry, owner, nonOwner;

  // Fixture commit hashes
  const COMMIT_HASH_0 = ethers.encodeBytes32String("commit_initial_0001");
  const COMMIT_HASH_1 = ethers.encodeBytes32String("commit_renewed_0002");
  const COMMIT_HASH_2 = ethers.encodeBytes32String("commit_renewed_0003");
  const ATTEST_HASH_A = ethers.encodeBytes32String("hmac_attestation_A");
  const ATTEST_HASH_B = ethers.encodeBytes32String("hmac_attestation_B");
  const ZERO_BYTES32  = "0x" + "0".repeat(64);

  beforeEach(async function () {
    [owner, nonOwner] = await ethers.getSigners();
    const Factory = await ethers.getContractFactory("SeparationRatioRegistry");
    registry = await Factory.deploy(owner.address);
    await registry.waitForDeployment();

    // Seed an initial commitment so renewals have a prevCommitHash
    await registry.connect(owner).commitRatio(COMMIT_HASH_0, 1261n, 11n, 3n);
  });

  // -------------------------------------------------------------------------
  // T186-1: registerAttestation stores and is readable via getAttestation
  // -------------------------------------------------------------------------

  it("T186-1: registerAttestation stores AttestationRecord; getAttestation returns it", async function () {
    await registry.connect(owner).registerAttestation(ATTEST_HASH_A, 7n);

    const rec = await registry.getAttestation(ATTEST_HASH_A);
    expect(rec.ttlDays).to.equal(7n);
    expect(rec.registeredAt).to.be.gt(0n);
    expect(rec.used).to.be.false;
  });

  // -------------------------------------------------------------------------
  // T186-2: attestedRenewCommit succeeds and marks attestation as used
  // -------------------------------------------------------------------------

  it("T186-2: attestedRenewCommit succeeds with valid attestation; emits AttestationBoundRenewal", async function () {
    await registry.connect(owner).registerAttestation(ATTEST_HASH_A, 7n);

    const tx = await registry.connect(owner).attestedRenewCommit(
      COMMIT_HASH_0, COMMIT_HASH_1, 30n, ATTEST_HASH_A
    );
    const receipt = await tx.wait();

    // Event emitted
    const event = receipt.logs.find(l => {
      try { return registry.interface.parseLog(l)?.name === "AttestationBoundRenewal"; }
      catch { return false; }
    });
    expect(event).to.not.be.undefined;

    // Attestation marked as used
    const rec = await registry.getAttestation(ATTEST_HASH_A);
    expect(rec.used).to.be.true;

    // New commit is recorded
    expect(await registry.isCommitted(COMMIT_HASH_1)).to.be.true;
    expect(await registry.totalCommits()).to.equal(2n);
  });

  // -------------------------------------------------------------------------
  // T186-3: attestedRenewCommit reverts when attestation already used (anti-replay)
  // -------------------------------------------------------------------------

  it("T186-3: attestedRenewCommit reverts on already-used attestation (anti-replay)", async function () {
    await registry.connect(owner).registerAttestation(ATTEST_HASH_A, 7n);

    // First use succeeds
    await registry.connect(owner).attestedRenewCommit(
      COMMIT_HASH_0, COMMIT_HASH_1, 30n, ATTEST_HASH_A
    );

    // Second use must revert (anti-replay)
    await expect(
      registry.connect(owner).attestedRenewCommit(
        COMMIT_HASH_1, COMMIT_HASH_2, 30n, ATTEST_HASH_A
      )
    ).to.be.revertedWith("SeparationRatioRegistry: attestation already used");
  });

  // -------------------------------------------------------------------------
  // T186-4: attestedRenewCommit reverts when attestation expired
  // -------------------------------------------------------------------------

  it("T186-4: attestedRenewCommit reverts when attestation TTL has elapsed", async function () {
    // Register attestation with 1-day TTL
    await registry.connect(owner).registerAttestation(ATTEST_HASH_B, 1n);

    // Advance block time by 2 days
    await time.increase(2 * 24 * 60 * 60);

    await expect(
      registry.connect(owner).attestedRenewCommit(
        COMMIT_HASH_0, COMMIT_HASH_1, 30n, ATTEST_HASH_B
      )
    ).to.be.revertedWith("SeparationRatioRegistry: attestation expired");
  });

  // -------------------------------------------------------------------------
  // T186-5: registerAttestation reverts on zero attestationHash
  // -------------------------------------------------------------------------

  it("T186-5: registerAttestation reverts on zero attestationHash (zero-address guard pattern)", async function () {
    await expect(
      registry.connect(owner).registerAttestation(ZERO_BYTES32, 7n)
    ).to.be.revertedWith("SeparationRatioRegistry: zero attestation hash");
  });

  // -------------------------------------------------------------------------
  // T186-6: AttestationRegistered event emitted correctly
  // -------------------------------------------------------------------------

  it("T186-6: registerAttestation emits AttestationRegistered with correct args", async function () {
    const tx = await registry.connect(owner).registerAttestation(ATTEST_HASH_A, 14n);
    const receipt = await tx.wait();

    const parsed = receipt.logs
      .map(l => { try { return registry.interface.parseLog(l); } catch { return null; } })
      .find(l => l?.name === "AttestationRegistered");

    expect(parsed).to.not.be.null;
    expect(parsed.args.attestationHash).to.equal(ATTEST_HASH_A);
    expect(parsed.args.ttlDays).to.equal(14n);
    expect(parsed.args.timestamp).to.be.gt(0n);
  });
});
