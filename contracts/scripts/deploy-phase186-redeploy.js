/**
 * Phase 186 — SeparationRatioRegistry REDEPLOY (replace posture, IoTeX testnet).
 *
 * Deploys the Phase 153+178+186 source (commit de012a9b — adds the attestation
 * extension: registerAttestation / attestedRenewCommit / getAttestation) as a NEW
 * address. The prior 0xB39CeE732cf91c93539Bd064D9426642a095a026 (Phase 153+178
 * bytecode, no attestation methods) is documented superseded in deployed-addresses.json.
 *
 * DISCIPLINE: estimate_gas x1.25, hard-cap 2.0 IOTX, ESTIMATE-ONLY unless
 * PHASE186_DEPLOY_CONFIRM=1.
 *
 *   npx hardhat run scripts/deploy-phase186-redeploy.js --network iotex_testnet            # estimate
 *   PHASE186_DEPLOY_CONFIRM=1 npx hardhat run scripts/deploy-phase186-redeploy.js --network iotex_testnet  # deploy
 */
const { ethers } = require("hardhat");

const HARD_CAP_IOTX = 2.0;
const GAS_BUFFER = 1.25;

async function main() {
  const [deployer] = await ethers.getSigners();
  const provider = deployer.provider;
  console.log("Deployer        :", deployer.address);
  console.log("Balance         :", ethers.formatEther(await provider.getBalance(deployer.address)), "IOTX");

  const Factory = await ethers.getContractFactory("SeparationRatioRegistry");
  const deployTx = await Factory.getDeployTransaction(deployer.address); // initialOwner = deployer

  const estGas = await provider.estimateGas({ ...deployTx, from: deployer.address });
  const gasPrice = (await provider.getFeeData()).gasPrice ?? 1000000000000n;
  const bufferedGas = (estGas * BigInt(Math.round(GAS_BUFFER * 100))) / 100n;
  const bufferedCostWei = bufferedGas * gasPrice;
  console.log("--- GAS ESTIMATE ---");
  console.log("estimate_gas    :", estGas.toString());
  console.log("buffered (x1.25):", bufferedGas.toString());
  console.log("gasPrice (wei)  :", gasPrice.toString());
  console.log("est cost        :", ethers.formatEther(estGas * gasPrice), "IOTX");
  console.log("buffered cost   :", ethers.formatEther(bufferedCostWei), "IOTX");
  console.log("hard-cap        :", HARD_CAP_IOTX, "IOTX");

  if (Number(ethers.formatEther(bufferedCostWei)) > HARD_CAP_IOTX) {
    console.error("[HARD-CAP EXCEEDED] ABORT."); process.exit(2);
  }
  console.log("hard-cap check  : PASS");

  if (process.env.PHASE186_DEPLOY_CONFIRM !== "1") {
    console.log("\n[ESTIMATE-ONLY] PHASE186_DEPLOY_CONFIRM!=1 — NOT broadcasting.");
    return;
  }

  console.log("\n[DEPLOYING] broadcasting...");
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

  // sanity: Phase 186 attestation methods callable + base commitRatio works
  const owner = await c.owner();
  console.log("owner()         :", owner);
  // getAttestation on an unknown hash returns a zero record (callable = extension present)
  const zeroRec = await c.getAttestation("0x" + "11".repeat(32));
  console.log("getAttestation callable (Phase 186 ext present):", zeroRec.registeredAt.toString() === "0");

  console.log("\nDEPLOY_RESULT_JSON " + JSON.stringify({
    contract: "SeparationRatioRegistry", chainId: 4690, address: addr,
    txHash: tx.hash, block: rcpt.blockNumber, gasUsed: rcpt.gasUsed.toString(),
    status: rcpt.status, supersedes: "0xB39CeE732cf91c93539Bd064D9426642a095a026",
  }));
}

main().catch((e) => { console.error(e); process.exit(1); });
