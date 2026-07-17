/**
 * Deploy VAPIDeviceBirthCertUpdateRegistry (Path A birth-cert override) — estimate-first, triple-gated.
 *
 * The companion override that re-anchors a device's birthCertHash to an HSM-re-signed cert without
 * redeploying the immutable one-shot VMDR. constructor(vmdrAddress).
 *
 *   # estimate-only (no on-chain spend):
 *   npx hardhat run scripts/deploy-device-birthcert-update-registry.js --network iotex_testnet
 *
 *   # broadcast (operator-fired):
 *   VAPI_DBC_DEPLOY_CONFIRM=1 npx hardhat run scripts/deploy-device-birthcert-update-registry.js --network iotex_testnet
 *
 * Gates: deployer must equal the bridge wallet; buffered cost <= hard-cap; balance >= ratio * cost;
 * broadcast only when VAPI_DBC_DEPLOY_CONFIRM=1.
 */
const { ethers } = require("hardhat");

const BRIDGE_WALLET = "0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692";
const VMDR_ADDRESS  = process.env.VMDR_ADDRESS || "0x2e5B5FB110890f498e289E3045d0f54Cfb0F91b0";
// Measured 2026-07-16: estimate_gas 604254 -> 0.755 IOTX buffered at testnet gas price.
// 1.0 matches the repo's contract-deploy cap convention (Arc 1 VMDR/Lens, Arc 5/6 deploys);
// the 0.5 cap in set-updated-birth-cert-hash.js stays (small call, not a deploy).
const HARD_CAP_IOTX = 1.0;

async function main() {
  const [deployer] = await ethers.getSigners();
  const provider = deployer.provider;
  const bal = await provider.getBalance(deployer.address);
  console.log("Deployer        :", deployer.address);
  console.log("Balance         :", ethers.formatEther(bal), "IOTX");
  console.log("VMDR (immutable):", VMDR_ADDRESS);

  if (deployer.address.toLowerCase() !== BRIDGE_WALLET.toLowerCase()) {
    console.error(`[GATE] deployer ${deployer.address} != bridge wallet ${BRIDGE_WALLET} — ABORT.`);
    process.exit(1);
  }
  if (!ethers.isAddress(VMDR_ADDRESS) || VMDR_ADDRESS === ethers.ZeroAddress) {
    console.error("[GATE] VMDR_ADDRESS invalid — ABORT.");
    process.exit(1);
  }

  const Factory = await ethers.getContractFactory("VAPIDeviceBirthCertUpdateRegistry");
  const deployTx = await Factory.getDeployTransaction(VMDR_ADDRESS);
  const estGas = await provider.estimateGas({ ...deployTx, from: deployer.address });
  const bufGas = (estGas * 125n) / 100n;
  const feeData = await provider.getFeeData();
  const gasPrice = feeData.gasPrice ?? 0n;
  const bufCost = bufGas * gasPrice;
  const bufCostIotx = parseFloat(ethers.formatEther(bufCost));

  console.log("\n--- GAS ESTIMATE ---");
  console.log("estimate_gas    :", estGas.toString());
  console.log("buffered (x1.25):", bufGas.toString());
  console.log("gasPrice (wei)  :", gasPrice.toString());
  console.log("buffered cost   :", ethers.formatEther(bufCost), "IOTX");
  console.log("hard-cap        :", HARD_CAP_IOTX, "IOTX");

  if (bufCostIotx > HARD_CAP_IOTX) {
    console.error(`[HARD-CAP EXCEEDED] ${bufCostIotx} > ${HARD_CAP_IOTX} — ABORT.`);
    process.exit(1);
  }
  const ratio = parseFloat(process.env.VAPI_DBC_BALANCE_RATIO || "2");
  if (bal < BigInt(Math.ceil(ratio)) * bufCost) {
    console.error(`[BALANCE GUARD] balance < ${ratio}x buffered cost — ABORT.`);
    process.exit(1);
  }

  if (process.env.VAPI_DBC_DEPLOY_CONFIRM !== "1") {
    console.log("\n[ESTIMATE-ONLY] set VAPI_DBC_DEPLOY_CONFIRM=1 to broadcast. No spend.");
    return;
  }

  console.log("\n[BROADCAST] deploying...");
  const c = await Factory.deploy(VMDR_ADDRESS);
  await c.waitForDeployment();
  const addr = await c.getAddress();
  console.log("DEPLOYED        :", addr);
  console.log("wired VMDR      :", await c.vmdr());
  console.log("owner           :", await c.owner());
  console.log("\nNext: set BIRTH_CERT_UPDATE_REGISTRY_ADDRESS=" + addr + " in bridge/.env,");
  console.log("add the deployed-addresses.json entry, then re-anchor via set-updated-birth-cert-hash.js");
}

main().catch((e) => { console.error(e); process.exit(1); });
