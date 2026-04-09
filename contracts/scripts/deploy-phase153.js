/**
 * Phase 153 — Deploy SeparationRatioRegistry
 *
 * On-chain proof-of-calibration commitment for inter-person separation ratio.
 * commit_hash = SHA-256(ratio_str + N + players_sorted + ts_ns)
 *
 * Usage:
 *   npx hardhat run scripts/deploy-phase153.js --network iotex_testnet
 */

const { ethers } = require("hardhat");
const fs = require("fs");
const path = require("path");

async function main() {
  const [deployer] = await ethers.getSigners();
  console.log("Deploying SeparationRatioRegistry with:", deployer.address);

  const Factory = await ethers.getContractFactory("SeparationRatioRegistry");
  const contract = await Factory.deploy(deployer.address);
  await contract.waitForDeployment();
  const addr = await contract.getAddress();

  console.log("SeparationRatioRegistry deployed to:", addr);

  // Smoke test: isCommitted(zero hash) should return false
  const zeroHash = ethers.ZeroHash;
  const notCommitted = await contract.isCommitted(zeroHash);
  console.assert(!notCommitted, "Smoke test failed: zero hash should not be committed");
  console.log("Smoke test passed: isCommitted(0x0) =", notCommitted);

  // Update deployed-addresses.json
  const addrFile = path.join(__dirname, "../deployed-addresses.json");
  let addresses = {};
  if (fs.existsSync(addrFile)) {
    addresses = JSON.parse(fs.readFileSync(addrFile, "utf8"));
  }
  addresses["SeparationRatioRegistry"] = addr;
  addresses["_phase153_status"] = "deployed";
  fs.writeFileSync(addrFile, JSON.stringify(addresses, null, 2));
  console.log("deployed-addresses.json updated");
}

main().catch((err) => { console.error(err); process.exit(1); });
