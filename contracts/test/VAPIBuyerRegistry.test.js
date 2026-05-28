/**
 * VAPIBuyerRegistry — Curator-attested buyer credential registry.
 * Data Economy Arc 1 Commit 1 (post Curator scope-expansion 2026-05-28).
 *
 *   T-VBR-1   Constructor reverts on zero owner (inherited Ownable behavior).
 *   T-VBR-2   FROZEN category constants pinned: ACADEMIC=1, GAME_DEV=2,
 *             ESPORTS=3, BRAND=4 (regression guard against enum reorder).
 *   T-VBR-3   setCuratorWallet: owner can set; non-owner reverts; event emits
 *             oldWallet + newWallet.
 *   T-VBR-4   issueCredential fails when curatorWallet is address(0) ("Curator
 *             wallet not set").
 *   T-VBR-5   issueCredential fails when called by non-Curator ("only Curator").
 *   T-VBR-6   issueCredential fails on zero buyerDID ("zero buyerDID").
 *   T-VBR-7   issueCredential fails on category < 1 or > 4 ("invalid category").
 *   T-VBR-8   issueCredential happy-path: writes struct, registers, emits
 *             CredentialIssued, expiresAt = issuedAt + 365 days.
 *   T-VBR-9   Double-registration reverts ("already registered") — slot
 *             stays consumed.
 *   T-VBR-10  isValidCredential: true for active+unexpired+matching-category;
 *             false for unregistered; false for wrong category.
 *   T-VBR-11  Credential expires after 365 days — isValidCredential returns
 *             false (uses hardhat time-travel).
 *   T-VBR-12  revokeCredential: Curator can revoke; owner can also revoke;
 *             non-Curator/non-owner reverts ("unauthorized").
 *   T-VBR-13  revokeCredential fails on unregistered buyer ("not registered").
 *   T-VBR-14  Post-revoke: isValidCredential returns false; credential.active
 *             = false; getCategory still returns original category (slot
 *             consumed per v1).
 *   T-VBR-15  Re-attestation under same buyerDID NOT permitted (post-revoke
 *             issueCredential reverts "already registered").
 *   T-VBR-16  setCuratorWallet(address(0)) effectively pauses issuance.
 *   T-VBR-17  getCredential returns full 7-tuple matching credentials mapping.
 */

const { expect } = require("chai");
const { ethers } = require("hardhat");
const { time } = require("@nomicfoundation/hardhat-network-helpers");

describe("VAPIBuyerRegistry (Data Economy Arc 1)", function () {
  let owner, curator, attacker, buyer1, buyer2;
  let registry;

  const BUYER_DID_1 = ethers.keccak256(ethers.toUtf8Bytes("buyer-academic-mit"));
  const BUYER_DID_2 = ethers.keccak256(ethers.toUtf8Bytes("buyer-brand-redbull"));
  const EVIDENCE_HASH_1 = ethers.keccak256(ethers.toUtf8Bytes("mit-irb-approval-2026"));
  const EVIDENCE_HASH_2 = ethers.keccak256(ethers.toUtf8Bytes("redbull-marketing-doc"));

  const CATEGORY_ACADEMIC = 1;
  const CATEGORY_GAME_DEV = 2;
  const CATEGORY_ESPORTS  = 3;
  const CATEGORY_BRAND    = 4;

  const ONE_YEAR_SECONDS = 365 * 24 * 60 * 60;

  beforeEach(async function () {
    [owner, curator, attacker, buyer1, buyer2] = await ethers.getSigners();
    const Factory = await ethers.getContractFactory("VAPIBuyerRegistry");
    registry = await Factory.deploy(owner.address);
    await registry.waitForDeployment();
  });

  it("T-VBR-1: deploy with valid owner sets ownership", async function () {
    expect(await registry.owner()).to.equal(owner.address);
    expect(await registry.curatorWallet()).to.equal(ethers.ZeroAddress);
  });

  it("T-VBR-2: FROZEN category constants pinned at canonical values", async function () {
    expect(await registry.CATEGORY_ACADEMIC()).to.equal(1);
    expect(await registry.CATEGORY_GAME_DEV()).to.equal(2);
    expect(await registry.CATEGORY_ESPORTS()).to.equal(3);
    expect(await registry.CATEGORY_BRAND()).to.equal(4);
  });

  it("T-VBR-3: setCuratorWallet -- owner only, emits oldWallet + newWallet", async function () {
    await expect(
      registry.connect(attacker).setCuratorWallet(curator.address)
    ).to.be.revertedWithCustomError(registry, "OwnableUnauthorizedAccount");

    await expect(registry.connect(owner).setCuratorWallet(curator.address))
      .to.emit(registry, "CuratorWalletSet")
      .withArgs(ethers.ZeroAddress, curator.address);
    expect(await registry.curatorWallet()).to.equal(curator.address);

    // Rotate to a new wallet emits old + new
    await expect(registry.connect(owner).setCuratorWallet(buyer1.address))
      .to.emit(registry, "CuratorWalletSet")
      .withArgs(curator.address, buyer1.address);
  });

  it("T-VBR-4: issueCredential reverts before curatorWallet is set", async function () {
    await expect(
      registry.connect(curator).issueCredential(
        BUYER_DID_1, CATEGORY_ACADEMIC, EVIDENCE_HASH_1
      )
    ).to.be.revertedWith("Curator wallet not set");
  });

  it("T-VBR-5: non-Curator issueCredential reverts", async function () {
    await registry.connect(owner).setCuratorWallet(curator.address);
    await expect(
      registry.connect(attacker).issueCredential(
        BUYER_DID_1, CATEGORY_ACADEMIC, EVIDENCE_HASH_1
      )
    ).to.be.revertedWith("only Curator");
  });

  it("T-VBR-6: zero buyerDID reverts", async function () {
    await registry.connect(owner).setCuratorWallet(curator.address);
    await expect(
      registry.connect(curator).issueCredential(
        ethers.ZeroHash, CATEGORY_ACADEMIC, EVIDENCE_HASH_1
      )
    ).to.be.revertedWith("zero buyerDID");
  });

  it("T-VBR-7: invalid category (0 or 5+) reverts", async function () {
    await registry.connect(owner).setCuratorWallet(curator.address);
    await expect(
      registry.connect(curator).issueCredential(BUYER_DID_1, 0, EVIDENCE_HASH_1)
    ).to.be.revertedWith("invalid category");
    await expect(
      registry.connect(curator).issueCredential(BUYER_DID_1, 5, EVIDENCE_HASH_1)
    ).to.be.revertedWith("invalid category");
    await expect(
      registry.connect(curator).issueCredential(BUYER_DID_1, 255, EVIDENCE_HASH_1)
    ).to.be.revertedWith("invalid category");
  });

  it("T-VBR-8: issueCredential happy-path -- struct + event + 365d expiry", async function () {
    await registry.connect(owner).setCuratorWallet(curator.address);
    const tx = await registry.connect(curator).issueCredential(
      BUYER_DID_1, CATEGORY_ACADEMIC, EVIDENCE_HASH_1
    );
    const rcpt = await tx.wait();
    const block = await ethers.provider.getBlock(rcpt.blockNumber);
    const expectedExpiresAt = BigInt(block.timestamp) + BigInt(ONE_YEAR_SECONDS);

    await expect(tx)
      .to.emit(registry, "CredentialIssued")
      .withArgs(
        BUYER_DID_1, CATEGORY_ACADEMIC, curator.address,
        EVIDENCE_HASH_1, expectedExpiresAt
      );

    expect(await registry.registered(BUYER_DID_1)).to.equal(true);
    const cred = await registry.credentials(BUYER_DID_1);
    expect(cred.buyerDID).to.equal(BUYER_DID_1);
    expect(cred.categoryId).to.equal(CATEGORY_ACADEMIC);
    expect(cred.evidenceHash).to.equal(EVIDENCE_HASH_1);
    expect(cred.attestedBy).to.equal(curator.address);
    expect(cred.issuedAt).to.equal(BigInt(block.timestamp));
    expect(cred.expiresAt).to.equal(expectedExpiresAt);
    expect(cred.active).to.equal(true);
  });

  it("T-VBR-9: double-registration of same buyerDID reverts", async function () {
    await registry.connect(owner).setCuratorWallet(curator.address);
    await registry.connect(curator).issueCredential(
      BUYER_DID_1, CATEGORY_ACADEMIC, EVIDENCE_HASH_1
    );
    await expect(
      registry.connect(curator).issueCredential(
        BUYER_DID_1, CATEGORY_BRAND, EVIDENCE_HASH_2
      )
    ).to.be.revertedWith("already registered");
  });

  it("T-VBR-10: isValidCredential gates correctly", async function () {
    await registry.connect(owner).setCuratorWallet(curator.address);
    // Unregistered -> false
    expect(await registry.isValidCredential(BUYER_DID_1, CATEGORY_ACADEMIC))
      .to.equal(false);

    await registry.connect(curator).issueCredential(
      BUYER_DID_1, CATEGORY_ACADEMIC, EVIDENCE_HASH_1
    );
    expect(await registry.isValidCredential(BUYER_DID_1, CATEGORY_ACADEMIC))
      .to.equal(true);
    // Wrong category -> false
    expect(await registry.isValidCredential(BUYER_DID_1, CATEGORY_BRAND))
      .to.equal(false);
  });

  it("T-VBR-11: credential expires after 365 days", async function () {
    await registry.connect(owner).setCuratorWallet(curator.address);
    await registry.connect(curator).issueCredential(
      BUYER_DID_1, CATEGORY_ACADEMIC, EVIDENCE_HASH_1
    );
    expect(await registry.isValidCredential(BUYER_DID_1, CATEGORY_ACADEMIC))
      .to.equal(true);

    // Advance time past 365 days
    await time.increase(ONE_YEAR_SECONDS + 1);

    expect(await registry.isValidCredential(BUYER_DID_1, CATEGORY_ACADEMIC))
      .to.equal(false);
    // active flag still true (only expiresAt gate hits)
    const cred = await registry.credentials(BUYER_DID_1);
    expect(cred.active).to.equal(true);
  });

  it("T-VBR-12: revokeCredential -- Curator OR owner may revoke", async function () {
    await registry.connect(owner).setCuratorWallet(curator.address);
    await registry.connect(curator).issueCredential(
      BUYER_DID_1, CATEGORY_ACADEMIC, EVIDENCE_HASH_1
    );
    await registry.connect(curator).issueCredential(
      BUYER_DID_2, CATEGORY_BRAND, EVIDENCE_HASH_2
    );

    // Non-authorized reverts
    await expect(
      registry.connect(attacker).revokeCredential(BUYER_DID_1)
    ).to.be.revertedWith("unauthorized");

    // Curator can revoke
    await expect(registry.connect(curator).revokeCredential(BUYER_DID_1))
      .to.emit(registry, "CredentialRevoked")
      .withArgs(BUYER_DID_1, curator.address);

    // Owner can also revoke (separate buyer)
    await expect(registry.connect(owner).revokeCredential(BUYER_DID_2))
      .to.emit(registry, "CredentialRevoked")
      .withArgs(BUYER_DID_2, owner.address);
  });

  it("T-VBR-13: revokeCredential reverts on unregistered buyer", async function () {
    await registry.connect(owner).setCuratorWallet(curator.address);
    await expect(
      registry.connect(curator).revokeCredential(BUYER_DID_1)
    ).to.be.revertedWith("not registered");
  });

  it("T-VBR-14: post-revoke -- isValid=false, active=false, category preserved", async function () {
    await registry.connect(owner).setCuratorWallet(curator.address);
    await registry.connect(curator).issueCredential(
      BUYER_DID_1, CATEGORY_ESPORTS, EVIDENCE_HASH_1
    );
    await registry.connect(curator).revokeCredential(BUYER_DID_1);

    expect(await registry.isValidCredential(BUYER_DID_1, CATEGORY_ESPORTS))
      .to.equal(false);
    const cred = await registry.credentials(BUYER_DID_1);
    expect(cred.active).to.equal(false);
    expect(await registry.getCategory(BUYER_DID_1)).to.equal(CATEGORY_ESPORTS);
  });

  it("T-VBR-15: re-attestation under same buyerDID NOT permitted (v1)", async function () {
    await registry.connect(owner).setCuratorWallet(curator.address);
    await registry.connect(curator).issueCredential(
      BUYER_DID_1, CATEGORY_ACADEMIC, EVIDENCE_HASH_1
    );
    await registry.connect(curator).revokeCredential(BUYER_DID_1);
    // Slot consumed; cannot re-issue
    await expect(
      registry.connect(curator).issueCredential(
        BUYER_DID_1, CATEGORY_ACADEMIC, EVIDENCE_HASH_1
      )
    ).to.be.revertedWith("already registered");
  });

  it("T-VBR-16: setCuratorWallet(0) pauses issuance", async function () {
    await registry.connect(owner).setCuratorWallet(curator.address);
    await registry.connect(curator).issueCredential(
      BUYER_DID_1, CATEGORY_ACADEMIC, EVIDENCE_HASH_1
    );
    // Operator pauses
    await registry.connect(owner).setCuratorWallet(ethers.ZeroAddress);
    // New issuance reverts
    await expect(
      registry.connect(curator).issueCredential(
        BUYER_DID_2, CATEGORY_BRAND, EVIDENCE_HASH_2
      )
    ).to.be.revertedWith("Curator wallet not set");
    // Existing credential still valid (pause doesn't retroactively invalidate)
    expect(await registry.isValidCredential(BUYER_DID_1, CATEGORY_ACADEMIC))
      .to.equal(true);
  });

  it("T-VBR-17: getCredential returns full 7-tuple matching credentials map", async function () {
    await registry.connect(owner).setCuratorWallet(curator.address);
    await registry.connect(curator).issueCredential(
      BUYER_DID_1, CATEGORY_GAME_DEV, EVIDENCE_HASH_1
    );
    const direct = await registry.credentials(BUYER_DID_1);
    const named  = await registry.getCredential(BUYER_DID_1);
    expect(named[0]).to.equal(direct.buyerDID);
    expect(named[1]).to.equal(direct.categoryId);
    expect(named[2]).to.equal(direct.evidenceHash);
    expect(named[3]).to.equal(direct.attestedBy);
    expect(named[4]).to.equal(direct.issuedAt);
    expect(named[5]).to.equal(direct.expiresAt);
    expect(named[6]).to.equal(direct.active);
  });
});
