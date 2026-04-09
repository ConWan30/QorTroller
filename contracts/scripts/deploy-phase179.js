/**
 * Phase 179 — Deploy CeremonyAuditRegistry
 *
 * ZK Ceremony Multi-Party Audit Gate (WIF-030 W1 closure).
 * Tracks Groth16 MPC trusted-setup ceremony participants per ZK circuit.
 * Tournament authorization gate: getParticipantCount(circuitName) >= 3.
 *
 * Gas estimate: ~0.06 IOTX (similar to SeparationRatioRegistry Phase 153).
 * Wallet balance required: >= 0.06 IOTX.
 * Wallet: 0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692 (~0.35 IOTX as of Phase 178)
 *
 * Usage:
 *   npx hardhat run scripts/deploy-phase179.js --network iotex_testnet
 *
 * Post-deploy:
 *   Update contracts/deployed-addresses.json (automatic)
 *   Update bridge/.env.testnet: CEREMONY_AUDIT_REGISTRY_ADDRESS=<addr>
 *   Update CLAUDE.md: contracts 39→40
 */

const { ethers } = require("hardhat");
const fs = require("fs");
const path = require("path");

async function main() {
  const [deployer] = await ethers.getSigners();
  console.log("Deploying CeremonyAuditRegistry with:", deployer.address);

  const Factory = await ethers.getContractFactory("CeremonyAuditRegistry");
  const contract = await Factory.deploy(deployer.address);
  await contract.waitForDeployment();
  const addr = await contract.getAddress();

  console.log("CeremonyAuditRegistry deployed to:", addr);

  // Smoke test: getParticipantCount for unknown circuit should return 0
  const unknownCircuit = ethers.keccak256(ethers.toUtf8Bytes("unknown_circuit"));
  const count = await contract.getParticipantCount(unknownCircuit);
  console.assert(count === 0n, "Smoke test failed: unknown circuit count should be 0");
  console.log("Smoke test passed: getParticipantCount(unknown) =", count.toString());

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
  addresses["CeremonyAuditRegistry"] = addr;
  addresses["_phase179_status"] = "deployed";
  fs.writeFileSync(addrFile, JSON.stringify(addresses, null, 2));
  console.log("deployed-addresses.json updated");
  console.log("\nNext steps:");
  console.log("  bridge/.env.testnet: CEREMONY_AUDIT_REGISTRY_ADDRESS=" + addr);
  console.log("  CLAUDE.md: contracts 39->40, phase 179 COMPLETE");
}

main().catch((err) => { console.error(err); process.exit(1); });
