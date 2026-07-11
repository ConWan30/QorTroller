/**
 * WMP Phase-2 INC-2 — gamer-signed world-model consent flip (setWorldModelConsent).
 *
 * Mirrors contracts/scripts/set-consent-manifest.js (the proven gamer-signed pattern) with a
 * one-bool payload. The GAMER's own wallet signs — msg.sender on-chain IS the gamer
 * (self-sovereignty invariant); the bridge process never holds this key.
 *
 * Gates (house triple-gate):
 *   G1 estimate-first  — estimateGas must succeed; cost printed before anything sends
 *   G2 hard cap        — buffered cost must be <= 0.10 IOTX (tiny single-bool write)
 *   G3 intent          — broadcast ONLY with VAPI_WMC_CONSENT_CONFIRM=1 (default: estimate-only)
 *   G4 readback        — post-tx isWorldModelConsentGranted(signer) must equal the requested value
 *
 * Rails:
 *   - GAMER_PRIVATE_KEY required; signer == bridge wallet REFUSED unless
 *     VAPI_ALLOW_BRIDGE_WALLET_AS_GAMER=1 (single-developer testnet reality, stated loudly —
 *     the same rail name as the Arc 4 precedent).
 *   - Registry address from WORLD_MODEL_CONSENT_REGISTRY_ADDRESS (set at INC-4 deploy).
 *   - WMC_GRANT=false revokes (the same call with granted=false).
 *
 * Run (estimate-only):
 *   npx hardhat run contracts/scripts/set-world-model-consent.js --network iotex_testnet
 * Broadcast:
 *   VAPI_WMC_CONSENT_CONFIRM=1 GAMER_PRIVATE_KEY=0x... npx hardhat run ... --network iotex_testnet
 */
const { ethers } = require("hardhat");

const BRIDGE_WALLET = "0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692";
const HARD_CAP_IOTX = 0.10;

async function main() {
  const registry = process.env.WORLD_MODEL_CONSENT_REGISTRY_ADDRESS;
  if (!registry) {
    console.error("ERROR: WORLD_MODEL_CONSENT_REGISTRY_ADDRESS not set (deploy WMP-4 first — INC-4).");
    process.exit(2);
  }
  const pk = process.env.GAMER_PRIVATE_KEY;
  if (!pk) {
    console.error("ERROR: GAMER_PRIVATE_KEY env not set.");
    console.error("       This script REQUIRES the gamer's own wallet key — NEVER the bridge");
    console.error("       process. msg.sender on-chain becomes the gamer (self-sovereignty).");
    process.exit(2);
  }
  const grant = process.env.WMC_GRANT === undefined ? true : process.env.WMC_GRANT === "true" || process.env.WMC_GRANT === "1";

  const provider = ethers.provider;
  const signer = new ethers.Wallet(pk, provider);

  if (signer.address.toLowerCase() === BRIDGE_WALLET.toLowerCase()) {
    if (process.env.VAPI_ALLOW_BRIDGE_WALLET_AS_GAMER !== "1") {
      console.error("ERROR: GAMER_PRIVATE_KEY signer == bridge wallet.");
      console.error("       The bridge MUST NOT flip world-model consent on any gamer's behalf.");
      console.error("       Use a separate gamer wallet, OR set VAPI_ALLOW_BRIDGE_WALLET_AS_GAMER=1");
      console.error("       if you are the operator intentionally consenting for yourself as gamer.");
      process.exit(2);
    }
    console.warn("WARN: VAPI_ALLOW_BRIDGE_WALLET_AS_GAMER=1 — operator and gamer are the same");
    console.warn("      person (single-developer testnet, developer_self scope). Stated honestly.");
  }

  const bal = await provider.getBalance(signer.address);
  console.log("Gamer signer     :", signer.address);
  console.log("Registry (WMP-4) :", registry);
  console.log("Balance          :", ethers.formatEther(bal), "IOTX");
  console.log("Requested state  :", grant ? "GRANT world-model export consent" : "REVOKE");

  const reg = await ethers.getContractAt("VAPIWorldModelConsentRegistry", registry, signer);

  const before = await reg.isWorldModelConsentGranted(signer.address);
  console.log("Current on-chain :", before);
  if (before === grant) {
    console.log("NO-OP: on-chain state already matches the requested value. Nothing to send.");
    return;
  }

  // G1 estimate-first (never static gas — the IoTeX OOG lesson).
  const est = await reg.setWorldModelConsent.estimateGas(grant);
  const fee = await provider.getFeeData();
  const gasPrice = fee.gasPrice ?? 1000000000000n;
  const buffered = (est * 125n) / 100n;
  const costIotx = Number(ethers.formatEther(buffered * gasPrice));
  console.log("Gas estimate     :", est.toString(), `(buffered ${buffered})`);
  console.log("Est. cost        :", costIotx.toFixed(6), "IOTX  (hard cap", HARD_CAP_IOTX, ")");

  // G2 hard cap.
  if (costIotx > HARD_CAP_IOTX) {
    console.error(`ABORT: buffered cost ${costIotx} IOTX exceeds hard cap ${HARD_CAP_IOTX}.`);
    process.exit(1);
  }

  // G3 intent gate.
  if (process.env.VAPI_WMC_CONSENT_CONFIRM !== "1") {
    console.log("ESTIMATE-ONLY: set VAPI_WMC_CONSENT_CONFIRM=1 to broadcast. Nothing sent.");
    return;
  }

  const tx = await reg.setWorldModelConsent(grant, { gasLimit: buffered });
  console.log("tx sent          :", tx.hash);
  const rcpt = await tx.wait();
  console.log("mined            : block", rcpt.blockNumber, "status", rcpt.status);

  // G4 readback — the on-chain truth must equal the requested value.
  const after = await reg.isWorldModelConsentGranted(signer.address);
  console.log("Readback         :", after);
  if (after !== grant || rcpt.status !== 1) {
    console.error("FAIL: readback does not match the requested consent state.");
    process.exit(1);
  }
  console.log("OK: world-model consent", grant ? "GRANTED" : "REVOKED", "by", signer.address);
}

main().catch((e) => { console.error(e); process.exit(1); });
