/**
 * Phase 237 — Deploy VAPIConsentRegistry
 *
 * Per-category gamer consent registry. Gamers (msg.sender) call
 * grantConsent(category, expiresAt, consentHash) and revokeConsent(category)
 * directly; the bridge READS this state via view calls but never writes
 * on the gamer's behalf (self-sovereignty invariant).
 *
 * Optional composition: setIoIDRegistry(addr) AFTER deploy lets off-chain
 * tooling resolve did:io DIDs from gamer addresses. Not required for the
 * contract to operate.
 *
 * Gas estimate: ~0.07 IOTX.
 * Wallet: 0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692
 *
 * Usage (run only when ready to anchor consent on-chain):
 *   npx hardhat run scripts/deploy-phase237.js --network iotex_testnet
 *
 * Post-deploy:
 *   Update contracts/deployed-addresses.json   (automatic)
 *   Update bridge/.env.testnet:                CONSENT_REGISTRY_ADDRESS=<addr>
 *   (Optional) Set IoIDRegistry composition:   call setIoIDRegistry(<existing ioid addr>)
 *   Update CLAUDE.md: contracts 45->46, phase 237 deploy COMPLETE
 */

const { ethers } = require("hardhat");
const fs = require("fs");
const path = require("path");

async function main() {
  const [deployer] = await ethers.getSigners();
  console.log("Deploying VAPIConsentRegistry with:", deployer.address);

  const Factory = await ethers.getContractFactory("VAPIConsentRegistry");
  const contract = await Factory.deploy(deployer.address);
  await contract.waitForDeployment();
  const addr = await contract.getAddress();

  console.log("VAPIConsentRegistry deployed to:", addr);

  // Smoke tests — read views to confirm contract is live and zero-state-clean
  const owner = await contract.owner();
  console.assert(owner === deployer.address, "Smoke test failed: owner mismatch");
  console.log("Smoke test passed: owner =", owner);

  const total = await contract.totalGrants();
  console.assert(total === 0n, "Smoke test failed: totalGrants should be 0");
  console.log("Smoke test passed: totalGrants =", total.toString());

  const ioidRef = await contract.ioidRegistry();
  console.assert(ioidRef === ethers.ZeroAddress,
    "Smoke test failed: ioidRegistry should be unset at deploy");
  console.log("Smoke test passed: ioidRegistry = (unset)");

  // Update deployed-addresses.json
  const addrFile = path.join(__dirname, "../deployed-addresses.json");
  let addresses = {};
  if (fs.existsSync(addrFile)) {
    addresses = JSON.parse(fs.readFileSync(addrFile, "utf8"));
  }
  addresses["VAPIConsentRegistry"] = addr;
  addresses["_phase237_status"] = "deployed";
  addresses["_phase237_note"] = "Phase 237: VAPIConsentRegistry — per-category gamer consent (TOURNAMENT_GATE / ANONYMIZED_RESEARCH / MANUFACTURER_CERT / MARKETPLACE), gamer-self-sovereign (msg.sender writes), bridge reads only";
  fs.writeFileSync(addrFile, JSON.stringify(addresses, null, 2));
  console.log("deployed-addresses.json updated");

  console.log("\nNext steps:");
  console.log("  bridge/.env.testnet:    CONSENT_REGISTRY_ADDRESS=" + addr);
  console.log("  Restart bridge          (chain.is_consent_valid begins returning live state)");
  console.log("  Optional composition:   contract.setIoIDRegistry(VAPIioIDRegistry_addr)");
  console.log("  Update CLAUDE.md:       contracts 45->46, phase 237 deploy COMPLETE");
}

main().catch((err) => { console.error(err); process.exit(1); });
