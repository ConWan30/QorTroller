/**
 * VAPIBuyerCategoryVerifier deploy — Data Economy Arc 2 Phase 3.
 *
 * Groth16 verifier (snarkjs-generated). Constructor takes NO args — it is a
 * pure view verifier (verifyProof is the only entrypoint). No post-deploy
 * wiring needed: the bridge calls verifyProof directly via staticcall (Phase 4),
 * so there is no registry to setVerifier on (unlike the PitlSession verifier).
 *
 * DISCIPLINE (triple-gate, matches deploy-vapi-buyer-registry.js):
 *   - estimate_gas + 1.25x buffer + hard-cap check BEFORE broadcast
 *   - ESTIMATE-ONLY by default. Broadcast ONLY when VAPI_BUYER_VERIFIER_DEPLOY_CONFIRM=1
 *   - Pre-deploy sanity:
 *       * deployer balance > 2x buffered cost
 *       * deployer == bridge wallet
 *
 * Usage:
 *   # estimate-only (read-only RPC, no broadcast):
 *   npx hardhat run scripts/deploy-vapi-buyer-category-verifier.js --network iotex_testnet
 *   # operator-confirmed:
 *   VAPI_BUYER_VERIFIER_DEPLOY_CONFIRM=1 npx hardhat run scripts/deploy-vapi-buyer-category-verifier.js --network iotex_testnet
 *
 * Expected gas budget: ~0.5-0.8 IOTX (pure verifier, no storage). Hard-cap
 * 1.0 IOTX for runaway headroom.
 */
const { ethers } = require("hardhat");

const HARD_CAP_IOTX = 1.0;
const GAS_BUFFER    = 1.25;

// Bridge wallet -- the only deployer authorized for this arc
const EXPECTED_DEPLOYER = "0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692";

async function main() {
  const [deployer] = await ethers.getSigners();
  const provider = deployer.provider;
  const bal = await provider.getBalance(deployer.address);
  console.log("Deployer        :", deployer.address);
  console.log("Balance         :", ethers.formatEther(bal), "IOTX");

  if (deployer.address.toLowerCase() !== EXPECTED_DEPLOYER.toLowerCase()) {
    console.error(`ERROR: deployer ${deployer.address} != expected bridge wallet ${EXPECTED_DEPLOYER}`);
    process.exit(2);
  }
  console.log("deployer == bridge wallet : PASS");

  const Factory  = await ethers.getContractFactory("VAPIBuyerCategoryVerifier");
  const deployTx = await Factory.getDeployTransaction();

  // --- estimate ---
  const estGas          = await provider.estimateGas({ ...deployTx, from: deployer.address });
  const feeData         = await provider.getFeeData();
  const gasPrice        = feeData.gasPrice ?? 1000000000000n;
  const bufferedGas     = (estGas * BigInt(Math.round(GAS_BUFFER * 100))) / 100n;
  const estCostWei      = estGas * gasPrice;
  const bufferedCostWei = bufferedGas * gasPrice;

  console.log("\n--- GAS ESTIMATE ---");
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
  if (Number(ethers.formatEther(bal)) < bufferedCostIotx * 2) {
    console.error(`[BALANCE GUARD] balance < 2x buffered cost — ABORT.`);
    process.exit(2);
  }
  console.log("hard-cap check  : PASS");
  console.log("balance guard   : PASS");

  if (process.env.VAPI_BUYER_VERIFIER_DEPLOY_CONFIRM !== "1") {
    console.log("\n[ESTIMATE-ONLY] VAPI_BUYER_VERIFIER_DEPLOY_CONFIRM!=1 — NOT broadcasting.");
    console.log("Re-run with VAPI_BUYER_VERIFIER_DEPLOY_CONFIRM=1 to deploy.");
    return;
  }

  // --- broadcast ---
  console.log("\n[DEPLOYING] VAPI_BUYER_VERIFIER_DEPLOY_CONFIRM=1 — broadcasting...");
  const c  = await Factory.deploy({ gasLimit: bufferedGas });
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

  // Machine-readable line
  console.log("\nDEPLOY_RESULT_JSON " + JSON.stringify({
    contract: "VAPIBuyerCategoryVerifier", chainId: 4690, address: addr,
    txHash: tx.hash, block: rcpt.blockNumber, gasUsed: rcpt.gasUsed.toString(),
    status: rcpt.status,
  }));
}

main().catch((e) => { console.error(e); process.exit(1); });
