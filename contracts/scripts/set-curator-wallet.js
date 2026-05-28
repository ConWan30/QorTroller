/**
 * VAPIBuyerRegistry.setCuratorWallet — Data Economy Arc 1 post-deploy step.
 *
 * Authorizes the Curator to call issueCredential / revokeCredential. In v1 the
 * curator wallet IS the bridge wallet itself (Curator submits txs via the bridge
 * wallet, not an independent key — preserves the Operator two-key gate per the
 * curator-scope manifest). setCuratorWallet is onlyOwner; owner == bridge wallet.
 *
 * DISCIPLINE (matches deploy-vapi-buyer-registry.js):
 *   - estimate_gas + 1.25x buffer + hard-cap check BEFORE broadcast
 *   - ESTIMATE-ONLY by default. Broadcast ONLY when SET_CURATOR_WALLET_CONFIRM=1
 *   - Pre-tx sanity: caller == registry owner; balance > 2x buffered cost;
 *     reads current curatorWallet (no-op guard if already set)
 *
 * Usage:
 *   npx hardhat run scripts/set-curator-wallet.js --network iotex_testnet
 *   SET_CURATOR_WALLET_CONFIRM=1 npx hardhat run scripts/set-curator-wallet.js --network iotex_testnet
 */
const { ethers } = require("hardhat");

const REGISTRY_ADDRESS = "0x3742189eBDC09B115FA7e841C884247E9856130B";
// v1: curator wallet == bridge wallet (the deployer / owner).
const CURATOR_WALLET   = "0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692";
const EXPECTED_OWNER   = "0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692";
const HARD_CAP_IOTX    = 0.1;
const GAS_BUFFER       = 1.25;

async function main() {
  const [signer] = await ethers.getSigners();
  const provider = signer.provider;
  const bal = await provider.getBalance(signer.address);
  console.log("Signer          :", signer.address);
  console.log("Balance         :", ethers.formatEther(bal), "IOTX");

  if (signer.address.toLowerCase() !== EXPECTED_OWNER.toLowerCase()) {
    console.error(`ERROR: signer ${signer.address} != registry owner ${EXPECTED_OWNER} — setCuratorWallet is onlyOwner.`);
    process.exit(2);
  }

  const reg = await ethers.getContractAt("VAPIBuyerRegistry", REGISTRY_ADDRESS);
  const ownerOnChain = await reg.owner();
  const current = await reg.curatorWallet();
  console.log("Registry        :", REGISTRY_ADDRESS);
  console.log("owner (on-chain):", ownerOnChain, ownerOnChain.toLowerCase() === signer.address.toLowerCase() ? "(== signer OK)" : "(MISMATCH)");
  console.log("curatorWallet   :", current);
  console.log("target          :", CURATOR_WALLET);

  if (ownerOnChain.toLowerCase() !== signer.address.toLowerCase()) {
    console.error("ERROR: on-chain owner != signer — ABORT.");
    process.exit(2);
  }
  if (current.toLowerCase() === CURATOR_WALLET.toLowerCase()) {
    console.log("\n[NO-OP] curatorWallet already == target — nothing to do.");
    return;
  }

  const estGas        = await reg.setCuratorWallet.estimateGas(CURATOR_WALLET);
  const feeData       = await provider.getFeeData();
  const gasPrice      = feeData.gasPrice ?? 1000000000000n;
  const bufferedGas   = (estGas * BigInt(Math.round(GAS_BUFFER * 100))) / 100n;
  const bufferedCost  = bufferedGas * gasPrice;
  const bufferedIotx  = Number(ethers.formatEther(bufferedCost));

  console.log("\n--- GAS ESTIMATE ---");
  console.log("estimate_gas    :", estGas.toString());
  console.log("buffered (x1.25):", bufferedGas.toString());
  console.log("buffered cost   :", ethers.formatEther(bufferedCost), "IOTX");
  console.log("hard-cap        :", HARD_CAP_IOTX, "IOTX");

  if (bufferedIotx > HARD_CAP_IOTX) {
    console.error(`[HARD-CAP EXCEEDED] ${bufferedIotx} > ${HARD_CAP_IOTX} IOTX — ABORT.`);
    process.exit(2);
  }
  if (Number(ethers.formatEther(bal)) < bufferedIotx * 2) {
    console.error("[BALANCE GUARD] balance < 2x buffered cost — ABORT.");
    process.exit(2);
  }
  console.log("hard-cap check  : PASS");
  console.log("balance guard   : PASS");

  if (process.env.SET_CURATOR_WALLET_CONFIRM !== "1") {
    console.log("\n[ESTIMATE-ONLY] SET_CURATOR_WALLET_CONFIRM!=1 — NOT broadcasting.");
    return;
  }

  console.log("\n[FIRING] SET_CURATOR_WALLET_CONFIRM=1 — broadcasting...");
  const tx   = await reg.setCuratorWallet(CURATOR_WALLET, { gasLimit: bufferedGas });
  console.log("tx hash         :", tx.hash);
  const rcpt = await tx.wait();
  console.log("--- MINED ---");
  console.log("block           :", rcpt.blockNumber);
  console.log("gas used        :", rcpt.gasUsed.toString());
  console.log("status          :", rcpt.status, rcpt.status === 1 ? "(success)" : "(FAILED)");

  const after = await reg.curatorWallet();
  console.log("curatorWallet   :", after, after.toLowerCase() === CURATOR_WALLET.toLowerCase() ? "(== target OK)" : "(MISMATCH)");

  console.log("\nSET_CURATOR_RESULT_JSON " + JSON.stringify({
    contract: "VAPIBuyerRegistry", chainId: 4690, address: REGISTRY_ADDRESS,
    method: "setCuratorWallet", curatorWallet: after, txHash: tx.hash,
    block: rcpt.blockNumber, gasUsed: rcpt.gasUsed.toString(), status: rcpt.status,
  }));
}

main().catch((e) => { console.error(e); process.exit(1); });
