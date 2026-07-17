/**
 * ioID Ceremony Inc-A — deploy VAPIGamerControllerNFT (the controller DeviceNFT).
 *
 * The DeviceNFT for the "QorTroller Controllers" ioID project: the deviceContract that
 * ioIDStore.setDeviceContract maps to the project, and whose minted tokenId ioIDRegistry.register
 * consumes. Mirrors deploy-vapi-operator-agent-nft.js (proven agent precedent) for the
 * initialize/configureMinter/gasLimit/receipt-status discipline, PLUS an estimate-first + triple-gate
 * spend posture (Path A deploy-script convention). Default = ESTIMATE-ONLY, no spend.
 *
 *   # estimate-only (no spend):
 *   npx hardhat run scripts/deploy-vapi-gamer-controller-nft.js --network iotex_testnet
 *
 *   # broadcast (operator-fired):
 *   VAPI_GCN_DEPLOY_CONFIRM=1 npx hardhat run scripts/deploy-vapi-gamer-controller-nft.js --network iotex_testnet
 *
 * Empirical IoTeX baselines (agent NFT, commit fef267e9 — Hardhat under-estimates upgradeable ~3-4x):
 *   deploy ~2.17 IOTX / initialize ~0.13 / configureMinter ~0.07  (total ~2.37; budget ~3.0).
 *   Explicit gasLimit overrides: initialize 500000, configureMinter 200000.
 *   Check receipt.status === 1n after EVERY tx (a mined-but-reverted tx still returns a receipt).
 *
 * Post-deploy (operator ceremony, Inc-C): ProjectRegistry.register("QorTroller Controllers", 0) ->
 *   ioIDStore.setDeviceContract(projectTokenId, thisAddress) -> NFT.mint(gamer).
 */
const { ethers } = require("hardhat");
const fs = require("fs");
const path = require("path");

const BRIDGE_WALLET = "0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692";
const NAME = "QorTroller Gamer Controller NFT";
const SYMBOL = "QGC";
const MINTER_ALLOWANCE = parseInt(process.env.VAPI_GCN_MINTER_ALLOWANCE || "1", 10); // 1 = single Edge
const HARD_CAP_IOTX = 3.5;   // deploy ~2.8 buffered + init/configureMinter ~0.2 + gas-spike headroom (grok r02 F2)
const GAS_BUFFER = 125n;     // /100

async function main() {
  const [deployer] = await ethers.getSigners();
  const provider = deployer.provider;
  const bal = await provider.getBalance(deployer.address);
  console.log("Deployer        :", deployer.address);
  console.log("Balance         :", ethers.formatEther(bal), "IOTX");
  console.log("NFT             :", NAME, `(${SYMBOL})  minterAllowance=${MINTER_ALLOWANCE}`);

  if (deployer.address.toLowerCase() !== BRIDGE_WALLET.toLowerCase()) {
    console.error(`[GATE] deployer ${deployer.address} != bridge wallet ${BRIDGE_WALLET} — ABORT.`);
    process.exit(1);
  }

  // Re-deploy guard (grok r02 F3): refuse to overwrite an existing deployed address.
  const _apath = path.join(__dirname, "..", "deployed-addresses.json");
  const _existing = JSON.parse(fs.readFileSync(_apath, "utf-8"))["VAPIGamerControllerNFT"];
  if (_existing) {
    console.error(`[GUARD] VAPIGamerControllerNFT already deployed at ${_existing} — refusing to re-deploy `
      + `(would orphan the mapped project). Clear the key deliberately to redeploy. ABORT.`);
    process.exit(1);
  }

  // ── Estimate-first (no spend) ──────────────────────────────────────────────
  const Factory = await ethers.getContractFactory("VAPIGamerControllerNFT");
  const deployTx = await Factory.getDeployTransaction();
  const estGas = await provider.estimateGas({ ...deployTx, from: deployer.address });
  const bufGas = (estGas * GAS_BUFFER) / 100n;
  const gasPrice = (await provider.getFeeData()).gasPrice ?? 0n;
  const bufCost = bufGas * gasPrice;
  const bufCostIotx = parseFloat(ethers.formatEther(bufCost));

  console.log("\n--- DEPLOY GAS ESTIMATE (Hardhat under-estimates upgradeable ~3-4x on IoTeX) ---");
  console.log("estimate_gas    :", estGas.toString(), " buffered:", bufGas.toString());
  console.log("buffered cost   :", ethers.formatEther(bufCost), "IOTX  (cap", HARD_CAP_IOTX + ")");
  console.log("plus init ~0.13 + configureMinter ~0.07 IOTX (separate txs)");

  if (bufCostIotx > HARD_CAP_IOTX) {
    console.error(`[HARD-CAP EXCEEDED] ${bufCostIotx} > ${HARD_CAP_IOTX} — ABORT.`);
    process.exit(1);
  }
  const ratio = parseFloat(process.env.VAPI_GCN_BALANCE_RATIO || "2");
  if (bal < BigInt(Math.ceil(ratio)) * bufCost) {
    console.error(`[BALANCE GUARD] balance < ${ratio}x buffered cost — ABORT.`);
    process.exit(1);
  }

  if (process.env.VAPI_GCN_DEPLOY_CONFIRM !== "1") {
    console.log("\n[ESTIMATE-ONLY] set VAPI_GCN_DEPLOY_CONFIRM=1 to broadcast (deploy + initialize + configureMinter). No spend.");
    return;
  }

  // ── Broadcast: deploy -> initialize -> configureMinter (agent precedent) ───
  console.log("\n[BROADCAST] deploying...");
  const contract = await Factory.deploy();
  await contract.waitForDeployment();
  const addr = await contract.getAddress();
  const dtx = contract.deploymentTransaction();
  const drcpt = await dtx.wait();
  if (drcpt.status !== 1n) {
    throw new Error(`Deploy reverted: status=${drcpt.status} tx=${dtx.hash} — https://testnet.iotexscan.io/tx/${dtx.hash}`);
  }
  console.log("DEPLOYED        :", addr, " block:", drcpt.blockNumber, " gasUsed:", drcpt.gasUsed.toString());

  const itx = await contract.initialize(NAME, SYMBOL, { gasLimit: 500000 });
  const ircpt = await itx.wait();
  if (ircpt.status !== 1n) {
    throw new Error(`initialize reverted: status=${ircpt.status} tx=${itx.hash} (0x65 = IoTeX OOG, raise gasLimit) — https://testnet.iotexscan.io/tx/${itx.hash}`);
  }
  console.log("initialize      : status", ircpt.status, " gasUsed", ircpt.gasUsed.toString());

  const ctx = await contract.configureMinter(deployer.address, MINTER_ALLOWANCE, { gasLimit: 200000 });
  const crcpt = await ctx.wait();
  if (crcpt.status !== 1n) {
    throw new Error(`configureMinter reverted: status=${crcpt.status} tx=${ctx.hash} (owner 0x0 => initialize failed) — https://testnet.iotexscan.io/tx/${ctx.hash}`);
  }
  console.log("configureMinter : status", crcpt.status, " minter=deployer allowance=" + MINTER_ALLOWANCE);

  // ── Smoke views ────────────────────────────────────────────────────────────
  const owner = await contract.owner();
  const total = await contract.total();
  const isMinter = await contract.isMinter(deployer.address);
  const allowance = await contract.minterAllowance(deployer.address);
  console.log("smoke           : owner=" + owner + " total=" + total + " isMinter=" + isMinter + " allowance=" + allowance);
  if (owner.toLowerCase() !== deployer.address.toLowerCase() || total !== 0n ||
      isMinter !== true || allowance !== BigInt(MINTER_ALLOWANCE)) {
    throw new Error("SMOKE FAILED: post-deploy state mismatch — inspect the txs before proceeding.");
  }

  // ── Write deployed-addresses.json (only on success) ────────────────────────
  const addressesPath = path.join(__dirname, "..", "deployed-addresses.json");
  const addresses = JSON.parse(fs.readFileSync(addressesPath, "utf-8"));
  addresses["VAPIGamerControllerNFT"] = addr;
  if (!addresses["_wiring_notes"]) addresses["_wiring_notes"] = {};
  addresses["_wiring_notes"]["VAPIGamerControllerNFT"] = (
    "ioID controller DeviceNFT (Inc-A). The deviceContract for the 'QorTroller Controllers' ioID " +
    "project via ioIDStore.setDeviceContract; minted tokenId consumed by ioIDRegistry.register " +
    "(0x0A7e595C...). Owner/minter = bridge wallet; allowance " + MINTER_ALLOWANCE + ". Deployed " +
    new Date().toISOString().slice(0, 10) + "."
  );
  fs.writeFileSync(addressesPath, JSON.stringify(addresses, null, 2));
  console.log("\nWrote VAPIGamerControllerNFT =", addr, "to deployed-addresses.json");
  console.log("Next (Inc-C): ProjectRegistry.register('QorTroller Controllers',0) -> ioIDStore.setDeviceContract(projectTokenId, " + addr + ") -> mint(gamer).");
}

main().then(() => process.exit(0)).catch((e) => { console.error(e); process.exit(1); });
