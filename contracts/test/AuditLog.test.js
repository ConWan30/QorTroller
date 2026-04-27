/**
 * AuditLog — Operator series Phase O0 Hardhat Tests
 *
 * Pass 2C Section 3.4 specification + Session 3 Decision Y-A (Pass 2C
 * system-level Tessera anchor design):
 *   T-AL-1:  deployment defaults — owner correct, totalCheckpoints=0,
 *            getLatestCheckpoint returns sentinel zero values
 *   T-AL-2:  first appendCheckpoint succeeds + emits CheckpointAppended
 *            (checkpointId=0, treeSize and timestamp captured correctly)
 *   T-AL-3:  second appendCheckpoint with larger treeSize succeeds (sequence)
 *   T-AL-4:  duplicate merkleRoot reverts DuplicateMerkleRoot
 *   T-AL-5:  non-monotonic treeSize reverts NonMonotonicTreeSize (equal AND
 *            smaller-than-previous both rejected)
 *   T-AL-6:  stale timestamp (older than MAX_TIMESTAMP_AGE) reverts StaleTimestamp
 *   T-AL-7:  appendCheckpoint only-owner — non-owner reverts
 *   T-AL-8:  zero merkleRoot reverts InvalidMerkleRoot
 *   T-AL-9:  getLatestCheckpoint returns the latest tuple after multiple appends
 *   T-AL-10: getCheckpoint(id) returns historical checkpoint by id; out-of-bounds reverts
 *   T-AL-11: future timestamp (within reason) is accepted (clock skew tolerance)
 *   T-AL-12: isAnchored predicate reflects appendCheckpoint state
 *
 * Setup pattern: deploy AuditLog directly with the bridge wallet (owner) as
 * initialOwner. AuditLog has no contract dependencies under Y-A — no
 * AgentRegistry deployment needed in beforeEach. Simpler than Sessions 1+2.
 */

const { expect } = require("chai");
const { ethers } = require("hardhat");

describe("AuditLog (Operator series Phase O0)", function () {
  let auditLog, owner, nonOwner;

  // Synthetic Merkle roots representing distinct Tessera signed-tree-heads.
  const ROOT_A = ethers.keccak256(ethers.toUtf8Bytes("tessera-sth-alpha"));
  const ROOT_B = ethers.keccak256(ethers.toUtf8Bytes("tessera-sth-beta"));
  const ROOT_C = ethers.keccak256(ethers.toUtf8Bytes("tessera-sth-gamma"));

  beforeEach(async function () {
    [owner, nonOwner] = await ethers.getSigners();

    const Factory = await ethers.getContractFactory("AuditLog");
    auditLog = await Factory.deploy(owner.address);
    await auditLog.waitForDeployment();
  });

  // Helper: get current block timestamp
  async function nowTs() {
    const block = await ethers.provider.getBlock("latest");
    return BigInt(block.timestamp);
  }

  it("T-AL-1: deploys with correct owner and empty-state sentinel views", async function () {
    expect(await auditLog.owner()).to.equal(owner.address);
    expect(await auditLog.totalCheckpoints()).to.equal(0n);
    expect(await auditLog.MAX_TIMESTAMP_AGE()).to.equal(3600n);

    // Empty-state sentinel: getLatestCheckpoint returns zeros, not revert.
    const [root, size, ts, blk] = await auditLog.getLatestCheckpoint();
    expect(root).to.equal(ethers.ZeroHash);
    expect(size).to.equal(0n);
    expect(ts).to.equal(0n);
    expect(blk).to.equal(0n);

    // isAnchored returns false for any root before first append.
    expect(await auditLog.isAnchored(ROOT_A)).to.equal(false);
  });

  it("T-AL-2: first appendCheckpoint succeeds and emits CheckpointAppended with checkpointId=0", async function () {
    const ts = await nowTs();
    const tx = await auditLog.connect(owner).appendCheckpoint(ROOT_A, 100n, ts);

    await expect(tx)
      .to.emit(auditLog, "CheckpointAppended")
      .withArgs(0n, ROOT_A, 100n, ts);

    expect(await auditLog.totalCheckpoints()).to.equal(1n);
    expect(await auditLog.isAnchored(ROOT_A)).to.equal(true);

    // Latest checkpoint reflects the append, including block number captured automatically.
    const [root, size, tsLatest, blk] = await auditLog.getLatestCheckpoint();
    expect(root).to.equal(ROOT_A);
    expect(size).to.equal(100n);
    expect(tsLatest).to.equal(ts);
    expect(blk).to.be.greaterThan(0n);
  });

  it("T-AL-3: second appendCheckpoint with larger treeSize succeeds", async function () {
    const ts1 = await nowTs();
    await auditLog.connect(owner).appendCheckpoint(ROOT_A, 100n, ts1);

    const ts2 = await nowTs();
    await auditLog.connect(owner).appendCheckpoint(ROOT_B, 250n, ts2);

    expect(await auditLog.totalCheckpoints()).to.equal(2n);

    // Latest is the second checkpoint.
    const [root, size] = await auditLog.getLatestCheckpoint();
    expect(root).to.equal(ROOT_B);
    expect(size).to.equal(250n);

    // First checkpoint preserved at id=0.
    const [root0, size0] = await auditLog.getCheckpoint(0);
    expect(root0).to.equal(ROOT_A);
    expect(size0).to.equal(100n);
  });

  it("T-AL-4: duplicate merkleRoot reverts DuplicateMerkleRoot", async function () {
    const ts = await nowTs();
    await auditLog.connect(owner).appendCheckpoint(ROOT_A, 100n, ts);

    // Same root, different treeSize/timestamp — still must revert.
    await expect(
      auditLog.connect(owner).appendCheckpoint(ROOT_A, 200n, ts)
    )
      .to.be.revertedWithCustomError(auditLog, "DuplicateMerkleRoot")
      .withArgs(ROOT_A);
  });

  it("T-AL-5: non-monotonic treeSize reverts (both equal-to and smaller-than previous)", async function () {
    const ts = await nowTs();
    await auditLog.connect(owner).appendCheckpoint(ROOT_A, 100n, ts);

    // Equal treeSize must revert (must be STRICTLY greater).
    await expect(
      auditLog.connect(owner).appendCheckpoint(ROOT_B, 100n, ts)
    )
      .to.be.revertedWithCustomError(auditLog, "NonMonotonicTreeSize")
      .withArgs(100n, 100n);

    // Smaller treeSize must revert.
    await expect(
      auditLog.connect(owner).appendCheckpoint(ROOT_B, 50n, ts)
    )
      .to.be.revertedWithCustomError(auditLog, "NonMonotonicTreeSize")
      .withArgs(50n, 100n);
  });

  it("T-AL-6: stale timestamp (older than MAX_TIMESTAMP_AGE) reverts StaleTimestamp", async function () {
    const now = await nowTs();
    const stale = now - 3601n;  // 1 second past the 3600s window

    await expect(
      auditLog.connect(owner).appendCheckpoint(ROOT_A, 100n, stale)
    ).to.be.revertedWithCustomError(auditLog, "StaleTimestamp");

    // Confirm that comfortably-within-window timestamps still succeed
    // (the boundary case is sensitive to Hardhat's block.timestamp advancing
    // by 1 per tx, so we use a comfortable margin of 1000s rather than the
    // exact 3600s boundary). The freshness check correctness is asserted by
    // both the stale-revert above and the in-window-success here.
    const inWindow = now - 1000n;
    await auditLog.connect(owner).appendCheckpoint(ROOT_B, 100n, inWindow);
    expect(await auditLog.totalCheckpoints()).to.equal(1n);
  });

  it("T-AL-7: appendCheckpoint only-owner — non-owner reverts", async function () {
    const ts = await nowTs();
    await expect(
      auditLog.connect(nonOwner).appendCheckpoint(ROOT_A, 100n, ts)
    ).to.be.revertedWithCustomError(auditLog, "OwnableUnauthorizedAccount");
  });

  it("T-AL-8: zero merkleRoot reverts InvalidMerkleRoot", async function () {
    const ts = await nowTs();
    await expect(
      auditLog.connect(owner).appendCheckpoint(ethers.ZeroHash, 100n, ts)
    ).to.be.revertedWithCustomError(auditLog, "InvalidMerkleRoot");
  });

  it("T-AL-9: getLatestCheckpoint returns latest tuple after multiple appends", async function () {
    const ts1 = await nowTs();
    await auditLog.connect(owner).appendCheckpoint(ROOT_A, 100n, ts1);

    const ts2 = await nowTs();
    await auditLog.connect(owner).appendCheckpoint(ROOT_B, 200n, ts2);

    const ts3 = await nowTs();
    await auditLog.connect(owner).appendCheckpoint(ROOT_C, 350n, ts3);

    expect(await auditLog.totalCheckpoints()).to.equal(3n);

    const [root, size, ts] = await auditLog.getLatestCheckpoint();
    expect(root).to.equal(ROOT_C);
    expect(size).to.equal(350n);
    expect(ts).to.equal(ts3);
  });

  it("T-AL-10: getCheckpoint(id) returns historical checkpoint; out-of-bounds reverts", async function () {
    const ts1 = await nowTs();
    await auditLog.connect(owner).appendCheckpoint(ROOT_A, 100n, ts1);
    const ts2 = await nowTs();
    await auditLog.connect(owner).appendCheckpoint(ROOT_B, 200n, ts2);

    // id=0 returns first append.
    const [r0, s0] = await auditLog.getCheckpoint(0);
    expect(r0).to.equal(ROOT_A);
    expect(s0).to.equal(100n);

    // id=1 returns second append.
    const [r1, s1] = await auditLog.getCheckpoint(1);
    expect(r1).to.equal(ROOT_B);
    expect(s1).to.equal(200n);

    // Out-of-bounds reverts (Solidity default array index check).
    await expect(auditLog.getCheckpoint(2)).to.be.reverted;
  });

  it("T-AL-11: future timestamp (within reason) is accepted (clock skew tolerance)", async function () {
    // Tessera and on-chain clocks may have slight skew; future timestamps
    // within plausible drift should be accepted. Pass 2C only specifies
    // the lower bound.
    const future = (await nowTs()) + 60n;  // 60s in the future
    await auditLog.connect(owner).appendCheckpoint(ROOT_A, 100n, future);
    expect(await auditLog.totalCheckpoints()).to.equal(1n);

    const [, , ts] = await auditLog.getLatestCheckpoint();
    expect(ts).to.equal(future);
  });

  it("T-AL-12: isAnchored predicate reflects appendCheckpoint state", async function () {
    // Before any appends, all roots return false.
    expect(await auditLog.isAnchored(ROOT_A)).to.equal(false);
    expect(await auditLog.isAnchored(ROOT_B)).to.equal(false);

    // After anchoring ROOT_A, only ROOT_A returns true.
    const ts = await nowTs();
    await auditLog.connect(owner).appendCheckpoint(ROOT_A, 100n, ts);
    expect(await auditLog.isAnchored(ROOT_A)).to.equal(true);
    expect(await auditLog.isAnchored(ROOT_B)).to.equal(false);
  });
});
