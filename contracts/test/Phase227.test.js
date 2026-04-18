/**
 * Phase 227 — ProtocolCoherenceRegistry Phase 227 extension (6 Hardhat tests)
 *
 * Tests anchorCoherenceWithProvenance() and getLatestGovernanceProvenance():
 *   T227-HH-1: anchorCoherenceWithProvenance stores governanceProvenanceHash, emits event
 *   T227-HH-2: getLatestGovernanceProvenance returns correct value after anchoring
 *   T227-HH-3: anti-replay — same merkleRoot reverts even with different govProvHash
 *   T227-HH-4: anchorCoherence backward compat — governanceProvenanceHash stored as bytes32(0)
 *   T227-HH-5: getLatestGovernanceProvenance returns bytes32(0) when no anchors
 *   T227-HH-6: getAnchorAt returns full CoherenceAnchor with governanceProvenanceHash
 */

const { expect } = require("chai");
const { ethers } = require("hardhat");

describe("ProtocolCoherenceRegistry Phase 227 extension", function () {
  let registry, owner, nonOwner;

  beforeEach(async function () {
    [owner, nonOwner] = await ethers.getSigners();
    const Factory = await ethers.getContractFactory("ProtocolCoherenceRegistry");
    registry = await Factory.deploy(owner.address);
    await registry.waitForDeployment();
  });

  it("T227-HH-1: anchorCoherenceWithProvenance stores anchor and emits CoherenceAnchoredWithProvenance", async function () {
    const merkleRoot = ethers.keccak256(ethers.toUtf8Bytes("phase227-fleet-root-1"));
    const govProv    = ethers.keccak256(ethers.toUtf8Bytes("governance-provenance-hash-1"));
    const agentCount = 37n;
    const tsNs       = BigInt(Date.now()) * 1_000_000n;

    const tx = await registry.anchorCoherenceWithProvenance(merkleRoot, govProv, agentCount, tsNs);
    const receipt = await tx.wait();
    const blockNumber = receipt.blockNumber;

    await expect(tx)
      .to.emit(registry, "CoherenceAnchoredWithProvenance")
      .withArgs(merkleRoot, govProv, agentCount, tsNs, blockNumber);

    expect(await registry.totalAnchors()).to.equal(1n);

    const [root, ts, count] = await registry.getLatestCoherence();
    expect(root).to.equal(merkleRoot);
    expect(count).to.equal(agentCount);
    expect(ts).to.be.gt(0n);
  });

  it("T227-HH-2: getLatestGovernanceProvenance returns correct value after anchoring", async function () {
    // No anchors → bytes32(0)
    expect(await registry.getLatestGovernanceProvenance()).to.equal(ethers.ZeroHash);

    const merkleRoot1 = ethers.keccak256(ethers.toUtf8Bytes("root-1"));
    const govProv1    = ethers.keccak256(ethers.toUtf8Bytes("prov-1"));
    await registry.anchorCoherenceWithProvenance(merkleRoot1, govProv1, 37n, 1000n);
    expect(await registry.getLatestGovernanceProvenance()).to.equal(govProv1);

    // Second anchor: getLatestGovernanceProvenance should return the newer one
    const merkleRoot2 = ethers.keccak256(ethers.toUtf8Bytes("root-2"));
    const govProv2    = ethers.keccak256(ethers.toUtf8Bytes("prov-2"));
    await registry.anchorCoherenceWithProvenance(merkleRoot2, govProv2, 37n, 2000n);
    expect(await registry.getLatestGovernanceProvenance()).to.equal(govProv2);
    expect(await registry.totalAnchors()).to.equal(2n);
  });

  it("T227-HH-3: anti-replay — same merkleRoot reverts even with different govProvHash", async function () {
    const merkleRoot = ethers.keccak256(ethers.toUtf8Bytes("replay-root-227"));
    const govProv1   = ethers.keccak256(ethers.toUtf8Bytes("prov-first"));
    const govProv2   = ethers.keccak256(ethers.toUtf8Bytes("prov-second"));

    await registry.anchorCoherenceWithProvenance(merkleRoot, govProv1, 37n, 1000n);
    await expect(
      registry.anchorCoherenceWithProvenance(merkleRoot, govProv2, 37n, 2000n)
    ).to.be.revertedWith("ProtocolCoherenceRegistry: duplicate merkleRoot");

    // Also cross-function: same root via anchorCoherence reverts
    await expect(
      registry.anchorCoherence(merkleRoot, 37n, 3000n)
    ).to.be.revertedWith("ProtocolCoherenceRegistry: duplicate merkleRoot");
  });

  it("T227-HH-4: anchorCoherence backward compat — governanceProvenanceHash stored as bytes32(0)", async function () {
    const merkleRoot = ethers.keccak256(ethers.toUtf8Bytes("legacy-anchor-root"));
    await registry.anchorCoherence(merkleRoot, 36n, 1000n);

    // getLatestGovernanceProvenance should return bytes32(0) for legacy anchors
    expect(await registry.getLatestGovernanceProvenance()).to.equal(ethers.ZeroHash);

    // getAnchorAt should show bytes32(0) for governanceProvenanceHash
    const anchor = await registry.getAnchorAt(0);
    expect(anchor.merkleRoot).to.equal(merkleRoot);
    expect(anchor.governanceProvenanceHash).to.equal(ethers.ZeroHash);
  });

  it("T227-HH-5: getLatestGovernanceProvenance returns bytes32(0) when no anchors exist", async function () {
    expect(await registry.totalAnchors()).to.equal(0n);
    expect(await registry.getLatestGovernanceProvenance()).to.equal(ethers.ZeroHash);
  });

  it("T227-HH-6: getAnchorAt returns full CoherenceAnchor with governanceProvenanceHash", async function () {
    const merkleRoot = ethers.keccak256(ethers.toUtf8Bytes("getAnchorAt-root"));
    const govProv    = ethers.keccak256(ethers.toUtf8Bytes("getAnchorAt-prov"));
    const agentCount = 37n;
    const tsNs       = 9_999_999_000_000_000n;

    await registry.anchorCoherenceWithProvenance(merkleRoot, govProv, agentCount, tsNs);

    const anchor = await registry.getAnchorAt(0);
    expect(anchor.merkleRoot).to.equal(merkleRoot);
    expect(anchor.governanceProvenanceHash).to.equal(govProv);
    expect(anchor.agentCount).to.equal(agentCount);
    expect(anchor.tsNs).to.equal(tsNs);
    expect(anchor.anchoredAt).to.be.gt(0n);

    // Out-of-range reverts
    await expect(registry.getAnchorAt(1)).to.be.revertedWith(
      "ProtocolCoherenceRegistry: index out of range"
    );
  });
});
