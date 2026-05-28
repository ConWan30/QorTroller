/**
 * VAPIBuyerRegistry deploy — Data Economy Arc 1 Commit 1.
 *
 * Constructor takes one arg: the initial owner address (bridge wallet).
 * Post-deploy steps (separate operator-fired txs, NOT in this script):
 *   1. Operator calls registry.setCuratorWallet(curatorWalletAddr) — onlyOwner.
 *      (curator wallet is the bridge wallet itself in v1 per the
 *      "Operator two-key gate for Curator executor: PRESERVED" manifest
 *      constraint — Curator submits txs via bridge wallet, not independent key)
 *
 * DISCIPLINE (triple-gate, matches every prior deploy this arc):
 *   - estimate_gas + 1.25x buffer + hard-cap check BEFORE broadcast
 *   - ESTIMATE-ONLY by default. Broadcast ONLY when VAPI_BUYER_REGISTRY_DEPLOY_CONFIRM=1
 *   - Pre-deploy sanity:
 *       * deployer balance > 2x buffered cost
 *       * deployer == bridge wallet (so Ownable's initialOwner is correct
 *         without an extra owner-transfer step)
 *
 * Usage:
 *   # estimate-only:
 *   npx hardhat run scripts/deploy-vapi-buyer-registry.js --network iotex_testnet
 *   # operator-confirmed:
 *   VAPI_BUYER_REGISTRY_DEPLOY_CONFIRM=1 npx hardhat run scripts/deploy-vapi-buyer-registry.js --network iotex_testnet
 *
 * Expected gas budget: ~700k-900k (4 events, 2 mappings, 1 address, Ownable +
 * ReentrancyGuard). Hard-cap 1.0 IOTX to leave runaway headroom.
 */
const { ethers } = require("hardhat");
const fs   = require("fs");
const path = require("path");

// Cap calibrated 2026-05-28 against the actual on-chain estimate (0.864 IOTX raw
// + 1.25x buffer = 1.080 IOTX). Cap is 10% above the buffered estimate -- still
// catches runaway estimates (~5x normal) while accepting the contract's honest
// size (4 events + 2 mappings + ~10 functions + Ownable + ReentrancyGuard).
const HARD_CAP_IOTX = 1.2;
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
    console.error("       (the registry's initialOwner is set to deployer.address;");
    console.error("        deploying with a different key would lock owner to that wrong key)");
    process.exit(2);
  }
  console.log("deployer == bridge wallet : PASS");

  const Factory  = await ethers.getContractFactory("VAPIBuyerRegistry");
  const deployTx = await Factory.getDeployTransaction(deployer.address);

  // --- estimate ---
  const estGas         = await provider.estimateGas({ ...deployTx, from: deployer.address });
  const feeData        = await provider.getFeeData();
  const gasPrice       = feeData.gasPrice ?? 1000000000000n;
  const bufferedGas    = (estGas * BigInt(Math.round(GAS_BUFFER * 100))) / 100n;
  const estCostWei     = estGas * gasPrice;
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

  if (process.env.VAPI_BUYER_REGISTRY_DEPLOY_CONFIRM !== "1") {
    console.log("\n[ESTIMATE-ONLY] VAPI_BUYER_REGISTRY_DEPLOY_CONFIRM!=1 — NOT broadcasting.");
    console.log("Re-run with VAPI_BUYER_REGISTRY_DEPLOY_CONFIRM=1 to deploy.");
    return;
  }

  // --- broadcast ---
  console.log("\n[DEPLOYING] VAPI_BUYER_REGISTRY_DEPLOY_CONFIRM=1 — broadcasting...");
  const c  = await Factory.deploy(deployer.address, { gasLimit: bufferedGas });
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

  // Sanity: post-deploy view calls
  const ownerOnChain     = await c.owner();
  const curatorWalletAt0 = await c.curatorWallet();
  const catAcademic      = await c.CATEGORY_ACADEMIC();
  const catBrand         = await c.CATEGORY_BRAND();
  console.log("owner           :", ownerOnChain, ownerOnChain.toLowerCase() === deployer.address.toLowerCase() ? "(== deployer OK)" : "(MISMATCH)");
  console.log("curatorWallet   :", curatorWalletAt0, "(expected 0x0 -- setCuratorWallet pending)");
  console.log("CATEGORY_ACADEMIC:", catAcademic.toString(), "(expected 1)");
  console.log("CATEGORY_BRAND   :", catBrand.toString(), "(expected 4)");

  // Machine-readable line
  console.log("\nDEPLOY_RESULT_JSON " + JSON.stringify({
    contract: "VAPIBuyerRegistry", chainId: 4690, address: addr,
    txHash: tx.hash, block: rcpt.blockNumber, gasUsed: rcpt.gasUsed.toString(),
    status: rcpt.status, owner: ownerOnChain,
  }));
}

main().catch((e) => { console.error(e); process.exit(1); });
