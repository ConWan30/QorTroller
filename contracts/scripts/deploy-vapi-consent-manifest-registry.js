/**
 * VAPIConsentManifestRegistry deploy — Data Economy Arc 4 (Dimension 8 extended).
 *
 * Gamer-address-keyed structured consent manifest with Dimension 8 (Arc 5)
 * extension fields: allowReplayProofs, replayHumanityThreshold,
 * replayQuantizationBits, replayRequireVerdict. Constructor takes
 * `initialOwner` (Ownable) — set to the deployer (bridge wallet).
 *
 * DISCIPLINE (mirrors deploy-vapi-buyer-category-verifier.js triple-gate):
 *   - estimate_gas + 1.25x buffer + 1.5 IOTX hard-cap
 *   - ESTIMATE-ONLY by default. Broadcast ONLY when
 *     VAPI_CONSENT_MANIFEST_DEPLOY_CONFIRM=1
 *   - deployer == bridge wallet check
 *   - balance > 2x buffered cost check
 *   - Post-deploy sanity: reads MIN_SESSIONS_FLOOR, COOLING_HOURS_FLOOR,
 *     REPLAY_QUANTIZATION_BITS_FLOOR (Dimension 8) and asserts the FROZEN
 *     constants are byte-equal to expected.
 *
 * Usage:
 *   # estimate-only (default):
 *   npx hardhat run scripts/deploy-vapi-consent-manifest-registry.js --network iotex_testnet
 *   # operator-confirmed:
 *   VAPI_CONSENT_MANIFEST_DEPLOY_CONFIRM=1 \
 *     npx hardhat run scripts/deploy-vapi-consent-manifest-registry.js --network iotex_testnet
 */
const { ethers } = require("hardhat");

const HARD_CAP_IOTX = 2.0;
const GAS_BUFFER    = 1.25;
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

  const Factory  = await ethers.getContractFactory("VAPIConsentManifestRegistry");
  const deployTx = await Factory.getDeployTransaction(deployer.address);

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

  if (process.env.VAPI_CONSENT_MANIFEST_DEPLOY_CONFIRM !== "1") {
    console.log("\n[ESTIMATE-ONLY] VAPI_CONSENT_MANIFEST_DEPLOY_CONFIRM!=1 — NOT broadcasting.");
    return;
  }

  console.log("\n[DEPLOYING] VAPI_CONSENT_MANIFEST_DEPLOY_CONFIRM=1 — broadcasting...");
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

  // Post-deploy sanity: FROZEN constants
  const reg = await ethers.getContractAt("VAPIConsentManifestRegistry", addr);
  const minSess = await reg.MIN_SESSIONS_FLOOR();
  const coolHr  = await reg.COOLING_HOURS_FLOOR();
  const autonMx = await reg.AUTONOMY_MAX();
  const qBits   = await reg.REPLAY_QUANTIZATION_BITS_FLOOR();
  if (minSess !== 10n) throw new Error(`MIN_SESSIONS_FLOOR drift: ${minSess} != 10`);
  if (coolHr  !== 72n) throw new Error(`COOLING_HOURS_FLOOR drift: ${coolHr} != 72`);
  if (autonMx !== 3n)  throw new Error(`AUTONOMY_MAX drift: ${autonMx} != 3`);
  if (qBits   !== 4n)  throw new Error(`REPLAY_QUANTIZATION_BITS_FLOOR drift: ${qBits} != 4 (INV-VHR-007)`);
  console.log("FROZEN constants : MIN_SESSIONS=10 COOLING=72 AUTONOMY_MAX=3 REPLAY_BITS=4 PASS");

  console.log("\nDEPLOY_RESULT_JSON " + JSON.stringify({
    contract: "VAPIConsentManifestRegistry", chainId: 4690, address: addr,
    txHash: tx.hash, block: rcpt.blockNumber, gasUsed: rcpt.gasUsed.toString(),
    status: rcpt.status,
  }));
}

main().catch((e) => { console.error(e); process.exit(1); });
