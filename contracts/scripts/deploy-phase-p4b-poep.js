/**
 * Phase B ② P4b — VAPIPoEPRegistry deploy (IoTeX testnet).
 *
 * Gamer-sovereign composite-key registry (Property X contract-enforced,
 * Option B anti-replay). Constructor: constructor(address initialOwner).
 *
 * DISCIPLINE (triple-gate, matches Guardian Tier-2 anchor):
 *   - estimate_gas, apply x1.25 buffer, hard-cap check BEFORE broadcast.
 *   - ESTIMATE-ONLY by default. Broadcast ONLY when POEP_DEPLOY_CONFIRM=1.
 *
 * Usage:
 *   # estimate + report (no spend):
 *   npx hardhat run scripts/deploy-phase-p4b-poep.js --network iotex_testnet
 *   # actually deploy (operator-confirmed):
 *   POEP_DEPLOY_CONFIRM=1 npx hardhat run scripts/deploy-phase-p4b-poep.js --network iotex_testnet
 */
const { ethers } = require("hardhat");
const fs = require("fs");
const path = require("path");

const HARD_CAP_IOTX = 2.0;      // runaway-guard (raised 1.0->2.0 2026-05-24: live estimate 788k gas x 1000 Gwei = ~0.79 IOTX realistic, ~1.58 worst-case at Guardian-observed 2000 Gwei ceiling; 1.0 was an underestimate of IoTeX gas for Ownable+ReentrancyGuard contracts)
const GAS_BUFFER = 1.25;        // estimate_gas x1.25

async function main() {
  const [deployer] = await ethers.getSigners();
  const provider = deployer.provider;
  const bal = await provider.getBalance(deployer.address);
  console.log("Deployer        :", deployer.address);
  console.log("Balance         :", ethers.formatEther(bal), "IOTX");

  const Factory = await ethers.getContractFactory("VAPIPoEPRegistry");
  const deployTx = await Factory.getDeployTransaction(deployer.address); // initialOwner = deployer

  // --- estimate ---
  const estGas = await provider.estimateGas({ ...deployTx, from: deployer.address });
  const feeData = await provider.getFeeData();
  const gasPrice = feeData.gasPrice ?? 1000000000000n; // IoTeX testnet 1000 Gwei fallback
  const bufferedGas = (estGas * BigInt(Math.round(GAS_BUFFER * 100))) / 100n;
  const estCostWei = estGas * gasPrice;
  const bufferedCostWei = bufferedGas * gasPrice;

  console.log("--- GAS ESTIMATE ---");
  console.log("estimate_gas    :", estGas.toString());
  console.log("buffered (x1.25):", bufferedGas.toString());
  console.log("gasPrice (wei)  :", gasPrice.toString());
  console.log("est cost        :", ethers.formatEther(estCostWei), "IOTX");
  console.log("buffered cost   :", ethers.formatEther(bufferedCostWei), "IOTX");
  console.log("hard-cap        :", HARD_CAP_IOTX, "IOTX");

  const bufferedCostIotx = Number(ethers.formatEther(bufferedCostWei));
  if (bufferedCostIotx > HARD_CAP_IOTX) {
    console.error(`[HARD-CAP EXCEEDED] buffered cost ${bufferedCostIotx} > ${HARD_CAP_IOTX} IOTX — ABORT.`);
    process.exit(2);
  }
  console.log("hard-cap check  : PASS (buffered cost within cap)");

  if (process.env.POEP_DEPLOY_CONFIRM !== "1") {
    console.log("\n[ESTIMATE-ONLY] POEP_DEPLOY_CONFIRM!=1 — NOT broadcasting. Re-run with POEP_DEPLOY_CONFIRM=1 to deploy.");
    return;
  }

  // --- broadcast (operator-confirmed) ---
  console.log("\n[DEPLOYING] POEP_DEPLOY_CONFIRM=1 — broadcasting...");
  const c = await Factory.deploy(deployer.address, { gasLimit: bufferedGas });
  const tx = c.deploymentTransaction();
  console.log("deploy tx hash  :", tx.hash);
  await c.waitForDeployment();
  const addr = await c.getAddress();
  const rcpt = await provider.getTransactionReceipt(tx.hash);
  console.log("--- DEPLOYED ---");
  console.log("address         :", addr);
  console.log("block           :", rcpt.blockNumber);
  console.log("gas used        :", rcpt.gasUsed.toString());
  console.log("status          :", rcpt.status, rcpt.status === 1 ? "(success)" : "(FAILED)");

  // sanity: owner() callable
  const owner = await c.owner();
  console.log("owner()         :", owner, owner.toLowerCase() === deployer.address.toLowerCase() ? "(== deployer OK)" : "(MISMATCH)");

  // emit a machine-readable line for capture
  console.log("\nDEPLOY_RESULT_JSON " + JSON.stringify({
    contract: "VAPIPoEPRegistry", chainId: 4690, address: addr,
    txHash: tx.hash, block: rcpt.blockNumber, gasUsed: rcpt.gasUsed.toString(),
    status: rcpt.status,
  }));
}

main().catch((e) => { console.error(e); process.exit(1); });
