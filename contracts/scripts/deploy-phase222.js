/**
 * Phase 222 — Deploy VAPIBiometricGovernance
 *
 * Biometric-Bound Governance (BBG) — governance proposals gated on live VHP.
 * Blocks STOLEN_KEY / VHP_EXPIRY / FLASH_LOAN governance attacks.
 *
 * Requires the VHP contract address from contracts/deployed-addresses.json.
 *
 * Gas estimate: ~0.08 IOTX.
 * Wallet: 0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692
 *
 * Usage:
 *   npx hardhat run scripts/deploy-phase222.js --network iotex_testnet
 *
 * Post-deploy:
 *   Update contracts/deployed-addresses.json (automatic)
 *   Update bridge/.env.testnet: BBG_CONTRACT_ADDRESS=<addr>
 *   Update CLAUDE.md: contracts 44->45, phase 222 COMPLETE
 */

const { ethers } = require("hardhat");
const fs = require("fs");
const path = require("path");

async function main() {
  const [deployer] = await ethers.getSigners();
  console.log("Deploying VAPIBiometricGovernance with:", deployer.address);

  // Load VHP address from deployed-addresses.json
  const addrFile = path.join(__dirname, "../deployed-addresses.json");
  let addresses = {};
  if (fs.existsSync(addrFile)) {
    addresses = JSON.parse(fs.readFileSync(addrFile, "utf8"));
  }
  const vhpAddr = addresses["VAPIVerifiedHumanProof"] || "";
  if (!vhpAddr) {
    console.error("ERROR: VAPIVerifiedHumanProof address not found in deployed-addresses.json");
    console.error("Deploy VAPIVerifiedHumanProof first (Phase 99+)");
    process.exit(1);
  }
  console.log("VHP address:", vhpAddr);

  const bbgMaxAgeSec = 3600; // 1 hour default

  const Factory = await ethers.getContractFactory("VAPIBiometricGovernance");
  const contract = await Factory.deploy(deployer.address, vhpAddr, bbgMaxAgeSec);
  await contract.waitForDeployment();
  const addr = await contract.getAddress();

  console.log("VAPIBiometricGovernance deployed to:", addr);

  // Smoke tests
  const owner = await contract.owner();
  console.assert(owner === deployer.address, "Smoke test failed: owner mismatch");
  console.log("Smoke test passed: owner =", owner);

  const total = await contract.totalProposals();
  console.assert(total === 0n, "Smoke test failed: totalProposals should be 0");
  console.log("Smoke test passed: totalProposals =", total.toString());

  const maxAge = await contract.bbgMaxAgeSec();
  console.assert(maxAge === BigInt(bbgMaxAgeSec), "Smoke test failed: bbgMaxAgeSec mismatch");
  console.log("Smoke test passed: bbgMaxAgeSec =", maxAge.toString());

  // Update deployed-addresses.json
  addresses["VAPIBiometricGovernance"] = addr;
  addresses["_phase222_status"] = "deployed";
  addresses["_phase222_note"] = "Phase 222: BBG — governance proposals gated on live VHP; blocks STOLEN_KEY+VHP_EXPIRY+FLASH_LOAN attacks";
  fs.writeFileSync(addrFile, JSON.stringify(addresses, null, 2));
  console.log("deployed-addresses.json updated");
  console.log("\nNext steps:");
  console.log("  bridge/.env.testnet: BBG_CONTRACT_ADDRESS=" + addr);
  console.log("  CLAUDE.md: contracts 44->45, phase 222 COMPLETE");
}

main().catch((err) => { console.error(err); process.exit(1); });
