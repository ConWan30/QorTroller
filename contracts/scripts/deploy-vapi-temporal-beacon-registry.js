/**
 * VAPITemporalBeaconRegistry deploy — Data Economy Arc 6 (PoSR) Commit 1.
 *
 * On-chain anchor for IoTeX block hashes used to bind VHR session boundaries
 * to verifiable time. FROZEN-v1 #14 domain tag: VAPI-TEMPORAL-BEACON-v1.
 *
 * Constructor takes the initial owner (bridge wallet). Post-deploy: owner
 * calls setKeeper(<keeper_address>) — for v1 the keeper IS the operator
 * cron wallet (single-developer testnet, Decision T1 → Option B).
 *
 * DISCIPLINE (mirrors Arc 5 + Arc 4 + Arc 2 triple-gate):
 *   - estimate_gas + 1.25x buffer + 1.0 IOTX hard-cap
 *   - ESTIMATE-ONLY by default. Broadcast ONLY when
 *     VAPI_TBR_DEPLOY_CONFIRM=1
 *   - deployer == bridge wallet check
 *   - balance > 2x buffered cost check
 *   - Post-deploy: reads BEACON_DOMAIN + ANCHOR_CADENCE on-chain and asserts
 *     FROZEN constants byte-equal expected
 *
 * Usage:
 *   # estimate-only:
 *   npx hardhat run scripts/deploy-vapi-temporal-beacon-registry.js --network iotex_testnet
 *   # operator-confirmed:
 *   VAPI_TBR_DEPLOY_CONFIRM=1 \
 *     npx hardhat run scripts/deploy-vapi-temporal-beacon-registry.js --network iotex_testnet
 */
const { ethers } = require("hardhat");

const HARD_CAP_IOTX = 1.0;
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

  const Factory  = await ethers.getContractFactory("VAPITemporalBeaconRegistry");
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

  if (process.env.VAPI_TBR_DEPLOY_CONFIRM !== "1") {
    console.log("\n[ESTIMATE-ONLY] VAPI_TBR_DEPLOY_CONFIRM!=1 — NOT broadcasting.");
    return;
  }

  console.log("\n[DEPLOYING] VAPI_TBR_DEPLOY_CONFIRM=1 — broadcasting...");
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

  // Post-deploy FROZEN-constant sanity (Arc 5 deploy precedent)
  const reg = await ethers.getContractAt("VAPITemporalBeaconRegistry", addr);
  const expectedDomain = ethers.keccak256(ethers.toUtf8Bytes("VAPI-TEMPORAL-BEACON-v1"));
  const onchainDomain  = await reg.BEACON_DOMAIN();
  const onchainCadence = await reg.ANCHOR_CADENCE();
  if (onchainDomain !== expectedDomain) {
    console.error(`[FROZEN DRIFT] BEACON_DOMAIN ${onchainDomain} != ${expectedDomain}`);
    process.exit(3);
  }
  if (onchainCadence !== 64n) {
    console.error(`[FROZEN DRIFT] ANCHOR_CADENCE ${onchainCadence} != 64`);
    process.exit(3);
  }
  console.log("FROZEN check    : BEACON_DOMAIN + ANCHOR_CADENCE byte-equal PASS");

  console.log("\nDEPLOY_RESULT_JSON " + JSON.stringify({
    contract: "VAPITemporalBeaconRegistry", chainId: 4690, address: addr,
    txHash: tx.hash, block: rcpt.blockNumber, gasUsed: rcpt.gasUsed.toString(),
    status: rcpt.status,
    beaconDomain: onchainDomain,
  }));
  console.log("\nNEXT STEP: owner calls reg.setKeeper(<keeper-address>) — operator-fired.");
}

main().catch((e) => { console.error(e); process.exit(1); });
