/**
 * Phase 227 — Upgrade ProtocolCoherenceRegistry with anchorCoherenceWithProvenance
 *
 * This is NOT a new contract deployment — the existing ProtocolCoherenceRegistry
 * at 0xfAfe4E8BEE45be22836b90D542045510dDd927Dd was deployed with Phase 221 and
 * already contains the Phase 227 changes (anchorCoherenceWithProvenance added,
 * governanceProvenanceHash struct field, getLatestGovernanceProvenance view).
 *
 * If re-deploying to testnet, the new address should be updated in:
 *   contracts/deployed-addresses.json
 *   bridge/.env: PROTOCOL_COHERENCE_REGISTRY_ADDRESS=<addr>
 *
 * Gas estimate: ~0.07 IOTX (same as Phase 221 — same contract size category)
 * Wallet: 0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692
 *
 * Usage:
 *   npx hardhat run scripts/deploy-phase227.js --network iotex_testnet
 */

const { ethers } = require("hardhat");
const fs = require("fs");
const path = require("path");

async function main() {
  const [deployer] = await ethers.getSigners();
  console.log("Deploying ProtocolCoherenceRegistry (Phase 227) with:", deployer.address);

  const Factory = await ethers.getContractFactory("ProtocolCoherenceRegistry");
  const contract = await Factory.deploy(deployer.address);
  await contract.waitForDeployment();
  const addr = await contract.getAddress();

  console.log("ProtocolCoherenceRegistry (Phase 227) deployed to:", addr);

  // Smoke test 1: totalAnchors = 0
  const total = await contract.totalAnchors();
  console.assert(total === 0n, "Smoke test failed: totalAnchors should be 0");
  console.log("Smoke test passed: totalAnchors =", total.toString());

  // Smoke test 2: getLatestCoherence returns zero root when empty
  const [root, ts, count] = await contract.getLatestCoherence();
  console.assert(root === ethers.ZeroHash, "Smoke test failed: root should be zero");
  console.log("Smoke test passed: getLatestCoherence() root =", root);

  // Smoke test 3: getLatestGovernanceProvenance returns bytes32(0) when empty
  const govProv = await contract.getLatestGovernanceProvenance();
  console.assert(govProv === ethers.ZeroHash, "Smoke test failed: govProv should be zero");
  console.log("Smoke test passed: getLatestGovernanceProvenance() =", govProv);

  // Smoke test 4: anchorCoherenceWithProvenance can be called
  const testRoot = ethers.keccak256(ethers.toUtf8Bytes("phase227-smoke-test"));
  const testProv = ethers.keccak256(ethers.toUtf8Bytes("governance-provenance-smoke"));
  const tx = await contract.anchorCoherenceWithProvenance(testRoot, testProv, 37n, 1000n);
  await tx.wait();
  const govProvAfter = await contract.getLatestGovernanceProvenance();
  console.assert(govProvAfter === testProv, "Smoke test failed: governance provenance not stored");
  console.log("Smoke test passed: anchorCoherenceWithProvenance() stored govProv =", govProvAfter);
  console.log("Smoke test passed: totalAnchors =", (await contract.totalAnchors()).toString());

  // Smoke test 5: owner check
  const owner = await contract.owner();
  console.assert(owner === deployer.address, "Smoke test failed: owner mismatch");
  console.log("Smoke test passed: owner =", owner);

  // Update deployed-addresses.json
  const addrFile = path.join(__dirname, "../deployed-addresses.json");
  let addresses = {};
  if (fs.existsSync(addrFile)) {
    addresses = JSON.parse(fs.readFileSync(addrFile, "utf8"));
  }
  addresses["ProtocolCoherenceRegistry"] = addr;
  addresses["_phase227_status"] = "deployed";
  addresses["_phase227_note"] = "Phase 227: PoPC+Provenance — anchorCoherenceWithProvenance() + GOVERNANCE_PROVENANCE_ANCHOR_DRIFT FSCA rule";
  fs.writeFileSync(addrFile, JSON.stringify(addresses, null, 2));
  console.log("deployed-addresses.json updated");
  console.log("\nNext steps:");
  console.log("  bridge/.env: PROTOCOL_COHERENCE_REGISTRY_ADDRESS=" + addr);
  console.log("  CLAUDE.md: phase 227 COMPLETE");
}

main().catch((err) => { console.error(err); process.exit(1); });
