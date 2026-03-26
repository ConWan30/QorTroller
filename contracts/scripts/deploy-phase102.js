/**
 * Phase 102 — Developer Integration Layer
 * Deploys TournamentGateDemo.sol with live testnet addresses.
 * Sets demoMode=true so developers can evaluate without a full PITL session.
 *
 * Usage: npx hardhat run scripts/deploy-phase102.js --network iotex_testnet
 * Gas estimate: ~0.04 IOTX
 */
const hre = require("hardhat");
const fs  = require("fs");
const path = require("path");

// Live testnet addresses (Phase 70 + Phase 99C)
const VAPI_PROTOCOL_LENS        = "0x1972bf756aFE0FFCfaF9842e2FbBb2B084352EAf";
const VAPI_VERIFIED_HUMAN_PROOF = "0xD3B2E259A4B69EF08e263e3A57B2507B7eac3dcF";

async function main() {
  const [deployer] = await hre.ethers.getSigners();
  console.log("Deploying with account:", deployer.address);

  const TournamentGateDemo = await hre.ethers.getContractFactory("TournamentGateDemo");
  const demo = await TournamentGateDemo.deploy(
    VAPI_PROTOCOL_LENS,
    VAPI_VERIFIED_HUMAN_PROOF
  );
  await demo.waitForDeployment();
  const demoAddr = await demo.getAddress();
  console.log("TournamentGateDemo deployed to:", demoAddr);

  // Enable demoMode for testnet developer evaluation (W1 mitigation)
  const tx = await demo.setDemoMode(true);
  await tx.wait();
  console.log("demoMode=true set for testnet developer evaluation");

  // Update deployed-addresses.json
  const addrFile = path.join(__dirname, "../deployed-addresses.json");
  const addrs = JSON.parse(fs.readFileSync(addrFile, "utf8"));
  addrs["TournamentGateDemo"] = demoAddr;
  fs.writeFileSync(addrFile, JSON.stringify(addrs, null, 2));
  console.log("deployed-addresses.json updated with TournamentGateDemo:", demoAddr);
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
