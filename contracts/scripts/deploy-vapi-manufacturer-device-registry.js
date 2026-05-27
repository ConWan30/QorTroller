/**
 * Path A Arc 1 Commit 2 — VAPIManufacturerDeviceRegistry deploy (IoTeX testnet).
 *
 * Manufacturer-authoritative device birth certificate registry (Ownable + ReentrancyGuard,
 * onlyOwner writes). Deliberate trust-model divergence from VAPIPoEPRegistry (gamer-sovereign).
 * Constructor: constructor(address initialOwner). Owner = QorTroller Foundation wallet for the
 * reference implementation (the bridge wallet here); future partner deploys would pass the
 * partner manufacturer's HSM wallet.
 *
 * DISCIPLINE (triple-gate, matches deploy-phase-p4b-poep.js precedent):
 *   - estimate_gas, apply x1.25 buffer, hard-cap check BEFORE broadcast
 *   - ESTIMATE-ONLY by default. Broadcast ONLY when MFG_DEPLOY_CONFIRM=1.
 *
 * Usage:
 *   # estimate + report (no spend):
 *   npx hardhat run scripts/deploy-vapi-manufacturer-device-registry.js --network iotex_testnet
 *   # actually deploy (operator-confirmed):
 *   MFG_DEPLOY_CONFIRM=1 npx hardhat run scripts/deploy-vapi-manufacturer-device-registry.js --network iotex_testnet
 */
const { ethers } = require("hardhat");

const HARD_CAP_IOTX = 2.0;   // runaway-guard (matches PoEP precedent: live estimate ~0.8 IOTX; ~1.6 worst-case)
const GAS_BUFFER    = 1.25;  // estimate_gas x 1.25 (matches IoTeX gotcha discipline)

async function main() {
  const [deployer] = await ethers.getSigners();
  const provider = deployer.provider;
  const bal = await provider.getBalance(deployer.address);
  console.log("Deployer        :", deployer.address);
  console.log("Balance         :", ethers.formatEther(bal), "IOTX");

  const Factory  = await ethers.getContractFactory("VAPIManufacturerDeviceRegistry");
  const deployTx = await Factory.getDeployTransaction(deployer.address); // initialOwner = deployer

  // --- estimate ---
  const estGas         = await provider.estimateGas({ ...deployTx, from: deployer.address });
  const feeData        = await provider.getFeeData();
  const gasPrice       = feeData.gasPrice ?? 1000000000000n; // IoTeX testnet 1000 Gwei fallback
  const bufferedGas    = (estGas * BigInt(Math.round(GAS_BUFFER * 100))) / 100n;
  const estCostWei     = estGas * gasPrice;
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

  if (process.env.MFG_DEPLOY_CONFIRM !== "1") {
    console.log("\n[ESTIMATE-ONLY] MFG_DEPLOY_CONFIRM!=1 — NOT broadcasting.");
    console.log("Re-run with MFG_DEPLOY_CONFIRM=1 to deploy.");
    return;
  }

  // --- broadcast (operator-confirmed) ---
  console.log("\n[DEPLOYING] MFG_DEPLOY_CONFIRM=1 — broadcasting...");
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

  // sanity: owner() callable + enum constants byte-equal to FROZEN
  const owner = await c.owner();
  console.log("owner()         :", owner,
              owner.toLowerCase() === deployer.address.toLowerCase() ? "(== deployer OK)" : "(MISMATCH)");

  const sigA = await c.SIGNING_PATH_A();
  const sigB = await c.SIGNING_PATH_B();
  const tFull = await c.PROOF_TIER_FULL();
  const tStd  = await c.PROOF_TIER_STANDARD();
  const tBas  = await c.PROOF_TIER_BASIC();
  console.log("SIGNING_PATH_A  :", sigA.toString(), sigA === 1n ? "(OK)" : "(MISMATCH — INV-MFG-001 violated)");
  console.log("SIGNING_PATH_B  :", sigB.toString(), sigB === 2n ? "(OK)" : "(MISMATCH — INV-MFG-001 violated)");
  console.log("PROOF_TIER_FULL :", tFull.toString(), tFull === 1n ? "(OK)" : "(MISMATCH — INV-MFG-002)");
  console.log("PROOF_TIER_STD  :", tStd.toString(),  tStd  === 2n ? "(OK)" : "(MISMATCH — INV-MFG-002)");
  console.log("PROOF_TIER_BAS  :", tBas.toString(),  tBas  === 3n ? "(OK)" : "(MISMATCH — INV-MFG-002)");

  // emit a machine-readable line for capture
  console.log("\nDEPLOY_RESULT_JSON " + JSON.stringify({
    contract: "VAPIManufacturerDeviceRegistry", chainId: 4690, address: addr,
    txHash: tx.hash, block: rcpt.blockNumber, gasUsed: rcpt.gasUsed.toString(),
    status: rcpt.status,
  }));
}

main().catch((e) => { console.error(e); process.exit(1); });
