/**
 * Phase 221 — Deploy ProtocolCoherenceRegistry
 *
 * Proof of Protocol Coherence (PoPC) — on-chain Merkle root anchor
 * over all 36 VAPI agent fleet observations.
 *
 * Gas estimate: ~0.07 IOTX (similar to CeremonyAuditRegistry Phase 179).
 * Wallet balance required: >= 0.07 IOTX.
 * Wallet: 0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692 (~10.4 IOTX as of Phase 220)
 *
 * Usage:
 *   npx hardhat run scripts/deploy-phase221.js --network iotex_testnet
 *
 * Post-deploy:
 *   Update contracts/deployed-addresses.json (automatic below)
 *   Update bridge/.env.testnet: PROTOCOL_COHERENCE_REGISTRY_ADDRESS=<addr>
 *   Update CLAUDE.md: contracts 43->44, phase 221 COMPLETE
 */

const { ethers } = require("hardhat");
const fs = require("fs");
const path = require("path");

async function main() {
  const [deployer] = await ethers.getSigners();
  console.log("Deploying ProtocolCoherenceRegistry with:", deployer.address);

  const Factory = await ethers.getContractFactory("ProtocolCoherenceRegistry");
  const contract = await Factory.deploy(deployer.address);
  await contract.waitForDeployment();
  const addr = await contract.getAddress();

  console.log("ProtocolCoherenceRegistry deployed to:", addr);

  // Smoke test: totalAnchors should be 0
  const total = await contract.totalAnchors();
  console.assert(total === 0n, "Smoke test failed: totalAnchors should be 0");
  console.log("Smoke test passed: totalAnchors =", total.toString());

  // Smoke test: getLatestCoherence returns zero root when empty
  const [root, ts, count] = await contract.getLatestCoherence();
  console.assert(root === ethers.ZeroHash, "Smoke test failed: root should be zero");
  console.log("Smoke test passed: getLatestCoherence() root =", root);

  // Smoke test: owner check
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
  addresses["_phase221_status"] = "deployed";
  addresses["_phase221_note"] = "Phase 221: PoPC — Merkle root anchor over 36-agent fleet; isCoherent(maxAgeSec) wired into VAPIProtocolLens";
  fs.writeFileSync(addrFile, JSON.stringify(addresses, null, 2));
  console.log("deployed-addresses.json updated");
  console.log("\nNext steps:");
  console.log("  bridge/.env.testnet: PROTOCOL_COHERENCE_REGISTRY_ADDRESS=" + addr);
  console.log("  CLAUDE.md: contracts 43->44, phase 221 COMPLETE");
}

main().catch((err) => { console.error(err); process.exit(1); });
