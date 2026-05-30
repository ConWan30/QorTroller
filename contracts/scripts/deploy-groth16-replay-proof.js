/**
 * Groth16VerifierVAPIReplayProof deploy — Data Economy Arc 5 inner verifier.
 *
 * snarkjs-generated from the 2026-05-30 trusted-setup ceremony zkey
 * (transcript: docs/data-economy-arc5-ceremony-transcript.md). No constructor
 * args — pure view verifier with verifyProof as the only entrypoint. The
 * Arc 5 wrapper (VAPIReplayProofVerifier) consumes this address.
 *
 * DISCIPLINE (mirrors deploy-vapi-replay-proof-verifier.js triple-gate):
 *   - estimate_gas + 1.25x buffer + 1.5 IOTX hard-cap (this contract is
 *     heavier than the buyer-category verifier — 6-element publicInputs vs 4)
 *   - ESTIMATE-ONLY by default. Broadcast ONLY when
 *     VAPI_GROTH16_REPLAY_DEPLOY_CONFIRM=1
 *   - deployer == bridge wallet check
 *   - balance > 2x buffered cost check
 *
 * Usage:
 *   # estimate-only (default):
 *   npx hardhat run scripts/deploy-groth16-replay-proof.js --network iotex_testnet
 *   # operator-confirmed:
 *   VAPI_GROTH16_REPLAY_DEPLOY_CONFIRM=1 \
 *     npx hardhat run scripts/deploy-groth16-replay-proof.js --network iotex_testnet
 */
const { ethers } = require("hardhat");

const HARD_CAP_IOTX = 1.5;
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

  const Factory  = await ethers.getContractFactory("Groth16VerifierVAPIReplayProof");
  const deployTx = await Factory.getDeployTransaction();

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

  if (process.env.VAPI_GROTH16_REPLAY_DEPLOY_CONFIRM !== "1") {
    console.log("\n[ESTIMATE-ONLY] VAPI_GROTH16_REPLAY_DEPLOY_CONFIRM!=1 — NOT broadcasting.");
    return;
  }

  console.log("\n[DEPLOYING] VAPI_GROTH16_REPLAY_DEPLOY_CONFIRM=1 — broadcasting...");
  const c  = await Factory.deploy({ gasLimit: bufferedGas });
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

  console.log("\nDEPLOY_RESULT_JSON " + JSON.stringify({
    contract: "Groth16VerifierVAPIReplayProof", chainId: 4690, address: addr,
    txHash: tx.hash, block: rcpt.blockNumber, gasUsed: rcpt.gasUsed.toString(),
    status: rcpt.status,
  }));
}

main().catch((e) => { console.error(e); process.exit(1); });
