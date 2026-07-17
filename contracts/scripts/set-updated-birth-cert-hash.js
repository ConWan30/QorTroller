/**
 * Re-anchor a device's birthCertHash to its HSM-re-signed cert — estimate-first, operator-fired.
 * Calls VAPIDeviceBirthCertUpdateRegistry.setUpdatedBirthCertHash(deviceId, newHash).
 *
 *   # estimate-only (no spend):
 *   DBC_REGISTRY=0x... DEVICE_ID=0x581a836c... NEW_HASH=0x... \
 *     npx hardhat run scripts/set-updated-birth-cert-hash.js --network iotex_testnet
 *
 *   # broadcast (operator-fired):
 *   VAPI_DBC_SET_CONFIRM=1 DBC_REGISTRY=0x... DEVICE_ID=0x... NEW_HASH=0x... \
 *     npx hardhat run scripts/set-updated-birth-cert-hash.js --network iotex_testnet
 *
 * NEW_HASH must be SHA-256 of the KMS-re-signed cert's canonical bytes (produce it with
 * `provision_device_mfg.py --dry-run` under MFG_CA_BACKEND=kms; it prints birthCertHash). After the tx,
 * run verify_device_cert on THAT cert file -> expect VALID.
 */
const { ethers } = require("hardhat");

const BRIDGE_WALLET = "0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692";
const HARD_CAP_IOTX = 0.50;

async function main() {
  const registry = process.env.DBC_REGISTRY;
  const deviceId = process.env.DEVICE_ID;
  const newHash  = process.env.NEW_HASH;
  for (const [k, v] of [["DBC_REGISTRY", registry], ["DEVICE_ID", deviceId], ["NEW_HASH", newHash]]) {
    if (!v) { console.error(`[GATE] ${k} env required — ABORT.`); process.exit(1); }
  }
  if (!ethers.isAddress(registry)) { console.error("[GATE] DBC_REGISTRY not an address — ABORT."); process.exit(1); }
  if (!/^0x[0-9a-fA-F]{64}$/.test(deviceId)) { console.error("[GATE] DEVICE_ID must be 32-byte hex — ABORT."); process.exit(1); }
  if (!/^0x[0-9a-fA-F]{64}$/.test(newHash) || newHash === ethers.ZeroHash) {
    console.error("[GATE] NEW_HASH must be a non-zero 32-byte hex — ABORT."); process.exit(1);
  }

  const [signer] = await ethers.getSigners();
  console.log("Signer          :", signer.address);
  console.log("Registry        :", registry);
  console.log("deviceId        :", deviceId);
  console.log("newHash         :", newHash);
  if (signer.address.toLowerCase() !== BRIDGE_WALLET.toLowerCase()) {
    console.error(`[GATE] signer ${signer.address} != bridge wallet ${BRIDGE_WALLET} — ABORT.`);
    process.exit(1);
  }

  const c = await ethers.getContractAt("VAPIDeviceBirthCertUpdateRegistry", registry);
  console.log("current effective hash:", await c.currentBirthCertHash(deviceId));

  // pre-send revert guard + estimate
  let estGas;
  try {
    estGas = await c.setUpdatedBirthCertHash.estimateGas(deviceId, newHash);
  } catch (e) {
    console.error("[PRE-SEND REVERT] setUpdatedBirthCertHash would revert:", e.shortMessage || e.message);
    process.exit(1);
  }
  const bufGas = (estGas * 125n) / 100n;
  const gasPrice = (await signer.provider.getFeeData()).gasPrice ?? 0n;
  const bufCost = bufGas * gasPrice;
  const bufCostIotx = parseFloat(ethers.formatEther(bufCost));
  console.log("\n--- GAS ESTIMATE ---");
  console.log("estimate_gas    :", estGas.toString(), " buffered:", bufGas.toString());
  console.log("buffered cost   :", ethers.formatEther(bufCost), "IOTX  (cap", HARD_CAP_IOTX + ")");
  if (bufCostIotx > HARD_CAP_IOTX) { console.error("[HARD-CAP EXCEEDED] — ABORT."); process.exit(1); }

  // balance guard (parity with the deploy script, grok round-25 F2)
  const bal = await signer.provider.getBalance(signer.address);
  const ratio = parseFloat(process.env.VAPI_DBC_BALANCE_RATIO || "2");
  if (bal < BigInt(Math.ceil(ratio)) * bufCost) {
    console.error(`[BALANCE GUARD] balance ${ethers.formatEther(bal)} < ${ratio}x buffered cost — ABORT.`);
    process.exit(1);
  }

  if (process.env.VAPI_DBC_SET_CONFIRM !== "1") {
    console.log("\n[ESTIMATE-ONLY] set VAPI_DBC_SET_CONFIRM=1 to broadcast the re-anchor. No spend.");
    return;
  }

  console.log("\n[BROADCAST] setUpdatedBirthCertHash...");
  const tx = await c.setUpdatedBirthCertHash(deviceId, newHash, { gasLimit: bufGas });
  console.log("tx sent         :", tx.hash);
  const rcpt = await tx.wait();
  console.log("status          :", rcpt.status, " block:", rcpt.blockNumber);
  console.log("new effective hash:", await c.currentBirthCertHash(deviceId));
  console.log("\nNext: run verify_device_cert on the KMS cert file -> expect VALID.");
}

main().catch((e) => { console.error(e); process.exit(1); });
