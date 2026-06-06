/**
 * VAPIWorldModelConsentRegistry — operator-fired deploy script (WMP-4).
 *
 * PHASE-2 PROMOTE — NOT broadcast in v1.
 *
 * The W1-D operator decision (2026-06-05) is: ship the WMP lane on
 * fixtures in v1; defer the cryptographic consent leg until a real
 * world-model buyer is actually paying for real-data export. This
 * script is committed for that Phase-2 moment.
 *
 * SAFETY RAILS (matching every other Arc deploy script in this repo):
 *   - Reads DEPLOYER_PRIVATE_KEY from env; refuses zero / missing.
 *   - estimate_gas + 1.25× buffer + 0.30 IOTX hard-cap (tiny contract).
 *   - Estimate-only by default. Broadcast iff VAPI_WMC_DEPLOY_CONFIRM=1.
 *   - Triple-gate: deployer address required + balance ≥ 2× cost +
 *     explicit confirm env var.
 *   - Post-deploy verification: read totalToggles() == 0n and assert
 *     isWorldModelConsentGranted(deployer) == false (default-deny
 *     state; the contract was just deployed and nobody has consented).
 *
 * Usage:
 *   # estimate-only (no on-chain spend):
 *   npx hardhat run scripts/deploy-vapi-world-model-consent-registry.js \
 *     --network iotex_testnet
 *
 *   # broadcast (operator-fired):
 *   VAPI_WMC_DEPLOY_CONFIRM=1 \
 *     npx hardhat run scripts/deploy-vapi-world-model-consent-registry.js \
 *     --network iotex_testnet
 */
const { ethers } = require("hardhat");

const HARD_CAP_IOTX = 0.30;
const GAS_BUFFER    = 1.25;

async function main() {
  const [deployer] = await ethers.getSigners();
  const provider = ethers.provider;
  const bal = await provider.getBalance(deployer.address);

  console.log("Deployer        :", deployer.address);
  console.log("Balance         :", ethers.formatEther(bal), "IOTX");

  const F = await ethers.getContractFactory("VAPIWorldModelConsentRegistry");
  // Estimate gas for the deploy transaction.
  const deployTx   = await F.getDeployTransaction();
  const estGas     = await provider.estimateGas({
    ...deployTx,
    from: deployer.address,
  });
  const feeData    = await provider.getFeeData();
  const gasPrice   = feeData.gasPrice ?? 1000000000000n;
  const bufGas     = (estGas * BigInt(Math.round(GAS_BUFFER * 100))) / 100n;
  const bufCost    = bufGas * gasPrice;
  const bufCostIotx = Number(ethers.formatEther(bufCost));

  console.log("\n--- GAS ESTIMATE ---");
  console.log("estimate_gas    :", estGas.toString());
  console.log("buffered (x1.25):", bufGas.toString());
  console.log("gasPrice (wei)  :", gasPrice.toString());
  console.log("est cost        :", ethers.formatEther(estGas * gasPrice), "IOTX");
  console.log("buffered cost   :", ethers.formatEther(bufCost), "IOTX");
  console.log("hard-cap        :", HARD_CAP_IOTX, "IOTX");

  if (bufCostIotx > HARD_CAP_IOTX) {
    console.error(`[HARD-CAP EXCEEDED] ${bufCostIotx} > ${HARD_CAP_IOTX} — ABORT.`);
    process.exit(2);
  }
  const balRatio = parseFloat(process.env.VAPI_WMC_BALANCE_RATIO || "2");
  if (Number(ethers.formatEther(bal)) < bufCostIotx * balRatio) {
    console.error(`[BALANCE GUARD] balance < ${balRatio}x buffered cost — ABORT.`);
    process.exit(2);
  }
  console.log("hard-cap check  : PASS");
  console.log("balance guard   : PASS");

  if (process.env.VAPI_WMC_DEPLOY_CONFIRM !== "1") {
    console.log("\n[ESTIMATE-ONLY] VAPI_WMC_DEPLOY_CONFIRM!=1 — NOT broadcasting.");
    console.log("Re-run with VAPI_WMC_DEPLOY_CONFIRM=1 to deploy on testnet.");
    console.log("\nW1-D POSTURE NOTE: this contract is Phase-2 of the WMP lane.");
    console.log("Deploy when a real world-model buyer needs cryptographic consent.");
    return;
  }

  // ── Broadcast ────────────────────────────────────────────────────────
  console.log("\n[DEPLOYING] VAPI_WMC_DEPLOY_CONFIRM=1 — broadcasting...");
  const reg = await F.deploy({
    gasLimit: bufGas,
    type: 0,
    gasPrice: gasPrice,
  });
  await reg.waitForDeployment();
  const address = await reg.getAddress();
  const tx = reg.deploymentTransaction();
  const rcpt = await tx.wait();

  console.log("--- DEPLOYED ---");
  console.log("address         :", address);
  console.log("tx hash         :", tx.hash);
  console.log("block           :", rcpt.blockNumber);
  console.log("gas used        :", rcpt.gasUsed.toString());
  console.log("status          :", rcpt.status, rcpt.status === 1 ? "(success)" : "(FAILED)");

  // Post-deploy verification — default-deny state.
  const totalToggles = await reg.totalToggles();
  const deployerConsent = await reg.isWorldModelConsentGranted(deployer.address);
  console.log("\n--- POST-DEPLOY VERIFY ---");
  console.log("totalToggles                       :", totalToggles.toString());
  console.log("isWorldModelConsentGranted(deployer):", deployerConsent);
  if (totalToggles !== 0n || deployerConsent !== false) {
    console.error("DRIFT: post-deploy default state is not default-deny — INVESTIGATE.");
    process.exit(3);
  }

  console.log("\nDEPLOY_RESULT_JSON " + JSON.stringify({
    contract: "VAPIWorldModelConsentRegistry",
    chainId:  4690,
    address:  address,
    txHash:   tx.hash,
    block:    rcpt.blockNumber,
    gasUsed:  rcpt.gasUsed.toString(),
    status:   rcpt.status,
  }));
}

main().catch((e) => { console.error(e); process.exit(1); });
