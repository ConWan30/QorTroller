/**
 * Path A Arc 1 Commit 4 — VAPIProtocolLensV2 deploy (IoTeX testnet).
 *
 * Constructor: (humanityOracle, rulingOracle, passportOracle, rewardDistributor,
 *               manufacturerDeviceRegistry). All 5 addresses are read from
 * deployed-addresses.json (no manual entry).
 *
 * Replace-posture: the v1 lens at 0x1972bf75... stays callable post-deploy
 * (EVM bytecode is immutable; tournament integrators that hard-coded v1
 * continue to work). The new v2 address becomes the canonical
 * deployed-addresses.json:"VAPIProtocolLens_v2" entry; v1 is preserved as
 * VAPIProtocolLens_v1_superseded with the supersede rationale in its _note.
 * Bridge env points at the NEW v2 address.
 *
 * DISCIPLINE (triple-gate, matches VMDR deploy script precedent):
 *   - estimate_gas, apply x1.25 buffer, hard-cap check BEFORE broadcast
 *   - ESTIMATE-ONLY by default. Broadcast ONLY when LENS_V2_DEPLOY_CONFIRM=1.
 *
 * Usage:
 *   # estimate + report (no spend):
 *   npx hardhat run scripts/deploy-vapi-protocol-lens-v2.js --network iotex_testnet
 *   # actually deploy (operator-confirmed):
 *   LENS_V2_DEPLOY_CONFIRM=1 npx hardhat run scripts/deploy-vapi-protocol-lens-v2.js --network iotex_testnet
 */
const { ethers } = require("hardhat");
const fs   = require("fs");
const path = require("path");

const HARD_CAP_IOTX = 2.0;   // runaway-guard (matches VMDR precedent)
const GAS_BUFFER    = 1.25;  // estimate_gas x 1.25 (IoTeX gotcha discipline)

async function main() {
  const [deployer] = await ethers.getSigners();
  const provider = deployer.provider;
  const bal = await provider.getBalance(deployer.address);
  console.log("Deployer        :", deployer.address);
  console.log("Balance         :", ethers.formatEther(bal), "IOTX");

  // Load the 5 constructor addresses from deployed-addresses.json
  const addrPath = path.join(__dirname, "..", "deployed-addresses.json");
  let existing = {};
  try {
    existing = JSON.parse(fs.readFileSync(addrPath, "utf8"));
  } catch (e) {
    console.error("ERROR: could not load deployed-addresses.json:", e.message);
    process.exit(2);
  }
  const humanity = existing.HumanityOracle             || "";
  const ruling   = existing.RulingOracle               || "";
  const passport = existing.PassportOracle             || "";
  const reward   = existing.VAPIRewardDistributor      || "";
  const mfg      = existing.VAPIManufacturerDeviceRegistry || "";

  for (const [name, addr] of [
    ["HumanityOracle", humanity], ["RulingOracle", ruling],
    ["PassportOracle", passport], ["VAPIRewardDistributor", reward],
    ["VAPIManufacturerDeviceRegistry", mfg],
  ]) {
    if (!addr) {
      console.error(`ERROR: ${name} address missing from deployed-addresses.json`);
      process.exit(2);
    }
  }

  console.log("--- CONSTRUCTOR ADDRESSES ---");
  console.log("  HumanityOracle             :", humanity);
  console.log("  RulingOracle               :", ruling);
  console.log("  PassportOracle             :", passport);
  console.log("  VAPIRewardDistributor      :", reward);
  console.log("  VAPIManufacturerDeviceRegistry :", mfg);

  const Factory  = await ethers.getContractFactory("VAPIProtocolLensV2");
  const deployTx = await Factory.getDeployTransaction(humanity, ruling, passport, reward, mfg);

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
    console.error(`[HARD-CAP EXCEEDED] buffered cost ${bufferedCostIotx} > ${HARD_CAP_IOTX} — ABORT.`);
    process.exit(2);
  }
  console.log("hard-cap check  : PASS (buffered cost within cap)");

  if (process.env.LENS_V2_DEPLOY_CONFIRM !== "1") {
    console.log("\n[ESTIMATE-ONLY] LENS_V2_DEPLOY_CONFIRM!=1 — NOT broadcasting.");
    console.log("Re-run with LENS_V2_DEPLOY_CONFIRM=1 to deploy.");
    return;
  }

  // --- broadcast (operator-confirmed) ---
  console.log("\n[DEPLOYING] LENS_V2_DEPLOY_CONFIRM=1 — broadcasting...");
  const c  = await Factory.deploy(humanity, ruling, passport, reward, mfg, { gasLimit: bufferedGas });
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

  // sanity: 5 oracle addresses byte-identical post-deploy
  const ho = await c.humanityOracle();
  const ro = await c.rulingOracle();
  const po = await c.passportOracle();
  const rd = await c.rewardDistributor();
  const md = await c.manufacturerDeviceRegistry();
  console.log("on-chain humanityOracle         :", ho, ho.toLowerCase() === humanity.toLowerCase() ? "(OK)" : "(MISMATCH)");
  console.log("on-chain rulingOracle           :", ro, ro.toLowerCase() === ruling.toLowerCase() ? "(OK)" : "(MISMATCH)");
  console.log("on-chain passportOracle         :", po, po.toLowerCase() === passport.toLowerCase() ? "(OK)" : "(MISMATCH)");
  console.log("on-chain rewardDistributor      :", rd, rd.toLowerCase() === reward.toLowerCase() ? "(OK)" : "(MISMATCH)");
  console.log("on-chain manufacturerDeviceReg  :", md, md.toLowerCase() === mfg.toLowerCase() ? "(OK)" : "(MISMATCH)");

  // smoke: isFullyEligible_PathA(0x00...00) on the zero deviceId — expect false
  // (oracles say no for zero; even if they did, MFG isPathA returns false).
  const zeroDev = "0x" + "00".repeat(32);
  const smokeA = await c.isFullyEligible_PathA(zeroDev);
  console.log("smoke isFullyEligible_PathA(0x00...00):", smokeA, smokeA === false ? "(OK)" : "(UNEXPECTED true!)");
  const smokeTier = await c.getDeviceTier(zeroDev);
  console.log("smoke getDeviceTier(0x00...00)       :", smokeTier.toString(), smokeTier === 0n ? "(OK)" : "(UNEXPECTED)");

  console.log("\nDEPLOY_RESULT_JSON " + JSON.stringify({
    contract: "VAPIProtocolLensV2", chainId: 4690, address: addr,
    txHash: tx.hash, block: rcpt.blockNumber, gasUsed: rcpt.gasUsed.toString(),
    status: rcpt.status,
  }));
}

main().catch((e) => { console.error(e); process.exit(1); });
