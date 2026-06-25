/**
 * VAPITemporalBeaconRegistry.setKeeper — Data Economy Arc 6 (PoSR) activation.
 *
 * The registry is deployed but its keeper is unset, so scripts/anchor_beacon.py
 * refuses to anchor ("registry keeper != our wallet — operator must call
 * setKeeper"). This owner-only tx authorizes the keeper wallet to call
 * anchorBeacon(). For v1 the keeper IS the operator/bridge wallet (single-dev
 * testnet, Decision T1 → Option B).
 *
 * DISCIPLINE (mirrors the Arc 6 deploy script):
 *   - estimate_gas + 1.25x buffer + 0.1 IOTX hard-cap (a setKeeper is cheap)
 *   - ESTIMATE-ONLY by default; broadcast ONLY when VAPI_TBR_SETKEEPER_CONFIRM=1
 *   - deployer == bridge wallet check (owner)
 *   - balance > 2x buffered cost guard
 *   - IDEMPOTENT: if keeper already == target, no-op (no tx)
 *
 * Usage:
 *   # estimate-only (default):
 *   npx hardhat run scripts/set-temporal-beacon-keeper.js --network iotex_testnet
 *   # operator-confirmed:
 *   VAPI_TBR_SETKEEPER_CONFIRM=1 \
 *     npx hardhat run scripts/set-temporal-beacon-keeper.js --network iotex_testnet
 *
 * Env:
 *   VAPI_TBR_ADDRESS   registry address (default: the 2026-06-05 deploy below)
 *   VAPI_TBR_KEEPER    keeper to set    (default: the bridge wallet)
 */
const { ethers } = require("hardhat");

const HARD_CAP_IOTX = 0.1;
const GAS_BUFFER = 1.25;
const EXPECTED_DEPLOYER = "0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692";
const DEFAULT_TBR = "0x962440312a995b21d4E203bE6d93021CC22bA051";

async function main() {
  const regAddr = process.env.VAPI_TBR_ADDRESS || DEFAULT_TBR;
  const [signer] = await ethers.getSigners();
  const provider = signer.provider;
  const keeper = process.env.VAPI_TBR_KEEPER || signer.address;

  if (!ethers.isAddress(regAddr) || regAddr === ethers.ZeroAddress) {
    console.error("ERROR: VAPI_TBR_ADDRESS invalid."); process.exit(2);
  }
  if (!ethers.isAddress(keeper) || keeper === ethers.ZeroAddress) {
    console.error("ERROR: VAPI_TBR_KEEPER invalid (zero address)."); process.exit(2);
  }

  const bal = await provider.getBalance(signer.address);
  console.log("Owner/signer    :", signer.address);
  console.log("Balance         :", ethers.formatEther(bal), "IOTX");
  console.log("Registry        :", regAddr);
  console.log("Keeper target   :", keeper);

  if (signer.address.toLowerCase() !== EXPECTED_DEPLOYER.toLowerCase()) {
    console.error(`ERROR: signer != owner/bridge wallet ${EXPECTED_DEPLOYER}`); process.exit(2);
  }
  console.log("owner check     : PASS");

  const reg = await ethers.getContractAt("VAPITemporalBeaconRegistry", regAddr);

  // Idempotency: read current keeper.
  let current;
  try {
    current = await reg.keeper();
    console.log("current keeper  :", current);
  } catch (e) {
    console.error("ERROR: reg.keeper() read failed — wrong address or ABI?", e.message);
    process.exit(2);
  }
  if (current.toLowerCase() === keeper.toLowerCase()) {
    console.log("\n[NO-OP] keeper already == target. Nothing to do.");
    console.log("\nNEXT STEP: run scripts/anchor_beacon.py (ANCHOR_BEACON_CONFIRM=1) to fire the first beacon.");
    return;
  }

  const txReq = await reg.setKeeper.populateTransaction(keeper);
  const estGas = await provider.estimateGas({ ...txReq, from: signer.address });
  const feeData = await provider.getFeeData();
  const gasPrice = feeData.gasPrice ?? 1000000000000n;
  const bufferedGas = (estGas * BigInt(Math.round(GAS_BUFFER * 100))) / 100n;
  const bufferedCostIotx = Number(ethers.formatEther(bufferedGas * gasPrice));

  console.log("\n--- GAS ESTIMATE ---");
  console.log("estimate_gas    :", estGas.toString());
  console.log("buffered (x1.25):", bufferedGas.toString());
  console.log("buffered cost   :", bufferedCostIotx.toFixed(6), "IOTX");
  if (bufferedCostIotx > HARD_CAP_IOTX) {
    console.error(`[HARD-CAP EXCEEDED] ${bufferedCostIotx} > ${HARD_CAP_IOTX} IOTX — ABORT.`); process.exit(2);
  }
  if (Number(ethers.formatEther(bal)) < bufferedCostIotx * 2) {
    console.error("[BALANCE GUARD] balance < 2x buffered cost — ABORT."); process.exit(2);
  }
  console.log("hard-cap + balance guards : PASS");

  if (process.env.VAPI_TBR_SETKEEPER_CONFIRM !== "1") {
    console.log("\n[ESTIMATE-ONLY] VAPI_TBR_SETKEEPER_CONFIRM!=1 — NOT broadcasting.");
    return;
  }

  console.log("\n[BROADCASTING] setKeeper...");
  const tx = await reg.setKeeper(keeper, { gasLimit: bufferedGas });
  console.log("tx hash         :", tx.hash);
  const rcpt = await tx.wait();
  console.log("block           :", rcpt.blockNumber);
  console.log("gas used        :", rcpt.gasUsed.toString());
  console.log("status          :", rcpt.status, rcpt.status === 1 ? "(success)" : "(FAILED)");

  const after = await reg.keeper();
  if (after.toLowerCase() !== keeper.toLowerCase()) {
    console.error(`[POST-CHECK DRIFT] keeper ${after} != target ${keeper}`); process.exit(3);
  }
  console.log("post-check      : keeper == target PASS");
  console.log("\nSETKEEPER_RESULT_JSON " + JSON.stringify({
    registry: regAddr, keeper, txHash: tx.hash, block: rcpt.blockNumber,
    gasUsed: rcpt.gasUsed.toString(), status: rcpt.status,
  }));
  console.log("\nNEXT STEP: run scripts/anchor_beacon.py (ANCHOR_BEACON_CONFIRM=1) to fire the first beacon.");
}
main().catch((e) => { console.error(e); process.exit(1); });
