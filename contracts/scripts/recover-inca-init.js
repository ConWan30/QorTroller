/**
 * ioID Inc-A RECOVERY — initialize an already-DEPLOYED VAPIGamerControllerNFT.
 *
 * Why this exists: the Inc-A deploy tx succeeded on-chain (status=1) but the deploy
 * script's status check used ethers v6 `receipt.status !== 1n` (bigint) while ethers
 * returns status as a NUMBER, so it false-positive-threw BEFORE running initialize +
 * configureMinter + the deployed-addresses write. The contract is live but uninitialized
 * (owner == 0x0). This script salvages it (no redeploy, no wasted ~2.25 IOTX) by running
 * initialize + configureMinter against the existing address, then smoke + write.
 *
 *   # dry-run (no spend) - prints what it will do + the current owner:
 *   GCN_RECOVER_ADDR=0x.. npx hardhat run scripts/recover-inca-init.js --network iotex_testnet
 *   # broadcast (operator-fired):
 *   GCN_RECOVER_ADDR=0x.. GCN_RECOVER_CONFIRM=1 npx hardhat run scripts/recover-inca-init.js --network iotex_testnet
 *
 * Front-run safe: an uninitialized OpenZeppelin upgradeable contract's initialize() is
 * callable by anyone. This script ABORTS if owner is already a NON-bridge address
 * (someone front-ran -> redeploy instead); if the bridge's own initialize races and loses,
 * the tx reverts and the Number(status)!==1 check throws (fail-safe, no corruption).
 */
const { ethers } = require("hardhat");
const fs = require("fs");
const path = require("path");

const BRIDGE_WALLET = "0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692";
const NAME = "QorTroller Gamer Controller NFT";
const SYMBOL = "QGC";
const MINTER_ALLOWANCE = parseInt(process.env.VAPI_GCN_MINTER_ALLOWANCE || "1", 10);
const ADDR = process.env.GCN_RECOVER_ADDR || "";

async function main() {
  if (!ethers.isAddress(ADDR)) {
    console.error("ERROR: set GCN_RECOVER_ADDR to the deployed VAPIGamerControllerNFT address."); process.exit(1);
  }
  const [deployer] = await ethers.getSigners();
  console.log("Recovering VAPIGamerControllerNFT:", ADDR);
  console.log("Deployer        :", deployer.address);
  if (deployer.address.toLowerCase() !== BRIDGE_WALLET.toLowerCase()) {
    console.error(`[GATE] deployer ${deployer.address} != bridge wallet ${BRIDGE_WALLET} - ABORT.`); process.exit(1);
  }
  const code = await deployer.provider.getCode(ADDR);
  if (code === "0x") { console.error("ERROR: no contract code at that address - wrong address. ABORT."); process.exit(1); }
  console.log("code bytes      :", (code.length - 2) / 2);

  const c = await ethers.getContractAt("VAPIGamerControllerNFT", ADDR);
  let owner = await c.owner();
  console.log("owner (pre)     :", owner, owner === ethers.ZeroAddress ? "(uninitialized)" : "");
  if (owner !== ethers.ZeroAddress && owner.toLowerCase() !== deployer.address.toLowerCase()) {
    console.error(`[ABORT] already initialized to a DIFFERENT owner (${owner}) - front-run/compromised. Redeploy instead.`);
    process.exit(1);
  }

  if (process.env.GCN_RECOVER_CONFIRM !== "1") {
    console.log("\n[DRY-RUN] set GCN_RECOVER_CONFIRM=1 to broadcast initialize + configureMinter. No spend.");
    console.log("Will run:", owner === ethers.ZeroAddress ? "initialize + configureMinter" : "configureMinter (already owned by bridge)");
    return;
  }

  if (owner === ethers.ZeroAddress) {
    console.log("\n[BROADCAST] initialize...");
    const itx = await c.initialize(NAME, SYMBOL, { gasLimit: 500000 });
    const ircpt = await itx.wait();
    if (Number(ircpt.status) !== 1) {
      throw new Error(`initialize reverted: status=${ircpt.status} tx=${itx.hash} - https://testnet.iotexscan.io/tx/${itx.hash}`);
    }
    console.log("initialize      : status", ircpt.status, " gasUsed", ircpt.gasUsed.toString());
    owner = await c.owner();
  } else {
    console.log("initialize      : SKIP (already owned by bridge)");
  }

  const isMinterNow = await c.isMinter(deployer.address);
  const allowNow = await c.minterAllowance(deployer.address);
  if (!isMinterNow || allowNow < BigInt(MINTER_ALLOWANCE)) {
    console.log("[BROADCAST] configureMinter...");
    const ctx = await c.configureMinter(deployer.address, MINTER_ALLOWANCE, { gasLimit: 200000 });
    const crcpt = await ctx.wait();
    if (Number(crcpt.status) !== 1) {
      throw new Error(`configureMinter reverted: status=${crcpt.status} tx=${ctx.hash} - https://testnet.iotexscan.io/tx/${ctx.hash}`);
    }
    console.log("configureMinter : status", crcpt.status, " minter=deployer allowance=" + MINTER_ALLOWANCE);
  } else {
    console.log("configureMinter : SKIP (already minter with allowance)");
  }

  // Smoke (same asserts as the deploy script's post-deploy smoke)
  const fOwner = await c.owner();
  const total = await c.total();
  const isMinter = await c.isMinter(deployer.address);
  const allowance = await c.minterAllowance(deployer.address);
  console.log("smoke           : owner=" + fOwner + " total=" + total + " isMinter=" + isMinter + " allowance=" + allowance);
  if (fOwner.toLowerCase() !== deployer.address.toLowerCase() || total !== 0n ||
      isMinter !== true || allowance < BigInt(MINTER_ALLOWANCE)) {
    throw new Error("SMOKE FAILED: post-recovery state mismatch - inspect the txs before proceeding.");
  }

  // Write deployed-addresses.json (only on a clean smoke)
  const p = path.join(__dirname, "..", "deployed-addresses.json");
  const a = JSON.parse(fs.readFileSync(p, "utf-8"));
  a["VAPIGamerControllerNFT"] = ADDR;
  if (!a["_wiring_notes"]) a["_wiring_notes"] = {};
  a["_wiring_notes"]["VAPIGamerControllerNFT"] = (
    "ioID controller DeviceNFT (Inc-A). deviceContract for the 'QorTroller Controllers' ioID " +
    "project via ioIDStore.setDeviceContract; minted tokenId consumed by ioIDRegistry.register " +
    "(0x0A7e595C...). Owner/minter = bridge wallet; allowance " + MINTER_ALLOWANCE + ". Deploy tx " +
    "succeeded but the script's status!==1n false-positive skipped init; recovered-init " +
    new Date().toISOString().slice(0, 10) + "."
  );
  fs.writeFileSync(p, JSON.stringify(a, null, 2));
  console.log("\nWrote VAPIGamerControllerNFT =", ADDR, "to deployed-addresses.json");
  console.log("Inc-A COMPLETE. Next (Inc-C): register-project -> set-device-contract -> mint.");
}

main().then(() => process.exit(0)).catch((e) => { console.error(e); process.exit(1); });
