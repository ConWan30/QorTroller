/**
 * Phase 181 — Deploy CeremonyAuditRegistry to IoTeX Testnet
 *
 * WIF-030 W2 closure: CeremonyAuditRegistry.sol was code-complete in Phase 179
 * (deploy deferred — wallet had ~0.35 IOTX, needed ~0.06 IOTX). Phase 181 executes
 * the on-chain deploy, storing `ceremonyAuditRegistry` in deployed-addresses.json
 * and enabling `ceremony_audit_registry_address` config field.
 *
 * Gas estimate: ~0.06 IOTX (ReentrancyGuard + Ownable + 2 mappings + 1 event).
 * Wallet balance required: >= 0.06 IOTX.
 * Wallet: 0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692 (~0.35 IOTX as of Phase 180)
 *
 * Usage:
 *   npx hardhat run scripts/deploy-phase181.js --network iotex_testnet
 *
 * Post-deploy:
 *   deployed-addresses.json: ceremonyAuditRegistry key added (automatic below)
 *   bridge/.env.testnet: CEREMONY_AUDIT_REGISTRY_ADDRESS=<deployed addr>
 *   CLAUDE.md: contracts 40→41 LIVE
 */

const { ethers } = require("hardhat");
const fs = require("fs");
const path = require("path");

async function main() {
  const [deployer] = await ethers.getSigners();
  console.log("Deploying CeremonyAuditRegistry with:", deployer.address);

  const balance = await ethers.provider.getBalance(deployer.address);
  console.log("Wallet balance:", ethers.formatEther(balance), "IOTX");

  // CeremonyAuditRegistry was code-complete in Phase 179 — reuse existing artifact
  const Factory = await ethers.getContractFactory("CeremonyAuditRegistry");
  const contract = await Factory.deploy(deployer.address);
  await contract.waitForDeployment();

  const addr = await contract.getAddress();
  console.log("CeremonyAuditRegistry deployed to:", addr);

  // --- Update deployed-addresses.json ---
  const addrPath = path.join(__dirname, "../deployed-addresses.json");
  let deployed = {};
  if (fs.existsSync(addrPath)) {
    deployed = JSON.parse(fs.readFileSync(addrPath, "utf8"));
  }
  deployed.ceremonyAuditRegistry = addr;
  fs.writeFileSync(addrPath, JSON.stringify(deployed, null, 2));
  console.log("Updated deployed-addresses.json: ceremonyAuditRegistry =", addr);

  // --- Verify contract works ---
  // getParticipantCount takes bytes32 — encode the circuit name string
  const circuitNameBytes32 = ethers.encodeBytes32String("pitl_feature_extraction");
  const count = await contract.getParticipantCount(circuitNameBytes32);
  console.log("getParticipantCount(pitl_feature_extraction):", count.toString(), "(expect 0)");

  console.log("\n=== Phase 181 Deploy Complete ===");
  console.log("ceremonyAuditRegistry:", addr);
  console.log("Next: set CEREMONY_AUDIT_REGISTRY_ADDRESS=" + addr + " in bridge/.env.testnet");
  console.log("Next: update CLAUDE.md contracts 40->41 LIVE");
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
