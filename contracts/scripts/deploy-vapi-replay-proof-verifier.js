/**
 * VAPIReplayProofVerifier deploy — Data Economy Arc 5 Commit 3.
 *
 * Wrapper around the snarkjs-generated Groth16VerifierVAPIReplayProof.sol.
 * Constructor takes the Groth16 verifier address (set after the trusted
 * setup ceremony lands the .zkey). No post-deploy wiring required: the
 * Curator orchestrator calls verify() directly via staticcall (Arc 5
 * Commit 4), so there is no registry to setVerifier on.
 *
 * DEPLOY-HOLD POSTURE (load-bearing — read before running with CONFIRM=1):
 *   Per docs/data-economy-deploy-hold-and-arc5-readiness.md, all REMAINING
 *   Data Economy on-chain deploys (Arc 2, Arc 4, Arc 5) are HELD until Arc 5
 *   is built end-to-end and the full ladder is verified under explicit
 *   operator GO. This script being present in source DOES NOT lift the hold;
 *   it ships ready so the operator-fired ceremony+deploy sequence is one
 *   command when the gate opens.
 *
 * DISCIPLINE (triple-gate, matches deploy-vapi-buyer-category-verifier.js):
 *   - estimate_gas + 1.25x buffer + hard-cap check BEFORE broadcast
 *   - ESTIMATE-ONLY by default. Broadcast ONLY when
 *     VAPI_REPLAY_PROOF_DEPLOY_CONFIRM=1
 *   - Groth16 verifier address must be supplied via
 *     VAPI_REPLAY_PROOF_GROTH16_ADDR — no zero-address default, no fallback
 *   - Pre-deploy sanity:
 *       * deployer balance > 2x buffered cost
 *       * deployer == bridge wallet
 *       * Groth16 address is a properAddress (lightweight format check)
 *
 * Usage:
 *   # estimate-only (read-only RPC, no broadcast):
 *   VAPI_REPLAY_PROOF_GROTH16_ADDR=0x... \
 *     npx hardhat run scripts/deploy-vapi-replay-proof-verifier.js \
 *       --network iotex_testnet
 *
 *   # operator-confirmed (hold-lift gate must already be open):
 *   VAPI_REPLAY_PROOF_GROTH16_ADDR=0x... \
 *   VAPI_REPLAY_PROOF_DEPLOY_CONFIRM=1 \
 *     npx hardhat run scripts/deploy-vapi-replay-proof-verifier.js \
 *       --network iotex_testnet
 *
 * Expected gas budget: ~0.3-0.5 IOTX (single immutable address, one constant,
 * one event sig — smaller than VAPIBuyerCategoryVerifier). Hard-cap 1.0 IOTX
 * for runaway headroom matching the Arc 2 precedent.
 */
const { ethers } = require("hardhat");

const HARD_CAP_IOTX = 1.0;
const GAS_BUFFER    = 1.25;

// Bridge wallet — the only deployer authorized for this arc (matches the
// Arc 2 precedent and the CLAUDE.md "Active wallet" pin).
const EXPECTED_DEPLOYER = "0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692";

async function main() {
  // ── Groth16 verifier address gate ───────────────────────────────────────
  // The wrapper's constructor rejects address(0); we surface the missing-env
  // case before estimateGas so the operator gets a clear actionable error
  // rather than a confusing revert.
  const groth16Addr = process.env.VAPI_REPLAY_PROOF_GROTH16_ADDR;
  if (!groth16Addr) {
    console.error("ERROR: VAPI_REPLAY_PROOF_GROTH16_ADDR is required.");
    console.error("  Set it to the address of the snarkjs-deployed");
    console.error("  Groth16VerifierVAPIReplayProof.sol contract (Stage 1).");
    process.exit(2);
  }
  if (!ethers.isAddress(groth16Addr)) {
    console.error(`ERROR: ${groth16Addr} is not a valid address.`);
    process.exit(2);
  }
  if (groth16Addr === ethers.ZeroAddress) {
    console.error("ERROR: VAPI_REPLAY_PROOF_GROTH16_ADDR is the zero address.");
    process.exit(2);
  }

  // ── Deployer + balance gate ─────────────────────────────────────────────
  const [deployer] = await ethers.getSigners();
  const provider = deployer.provider;
  const bal = await provider.getBalance(deployer.address);
  console.log("Deployer         :", deployer.address);
  console.log("Balance          :", ethers.formatEther(bal), "IOTX");
  console.log("Groth16 verifier :", groth16Addr);

  if (deployer.address.toLowerCase() !== EXPECTED_DEPLOYER.toLowerCase()) {
    console.error(`ERROR: deployer ${deployer.address} != expected bridge wallet ${EXPECTED_DEPLOYER}`);
    process.exit(2);
  }
  console.log("deployer == bridge wallet : PASS");

  // ── Estimate ────────────────────────────────────────────────────────────
  const Factory  = await ethers.getContractFactory("VAPIReplayProofVerifier");
  const deployTx = await Factory.getDeployTransaction(groth16Addr);

  const estGas          = await provider.estimateGas({ ...deployTx, from: deployer.address });
  const feeData         = await provider.getFeeData();
  const gasPrice        = feeData.gasPrice ?? 1000000000000n;
  const bufferedGas     = (estGas * BigInt(Math.round(GAS_BUFFER * 100))) / 100n;
  const estCostWei      = estGas * gasPrice;
  const bufferedCostWei = bufferedGas * gasPrice;

  console.log("\n--- GAS ESTIMATE ---");
  console.log("estimate_gas     :", estGas.toString());
  console.log("buffered (x1.25) :", bufferedGas.toString());
  console.log("gasPrice (wei)   :", gasPrice.toString());
  console.log("est cost         :", ethers.formatEther(estCostWei), "IOTX");
  console.log("buffered cost    :", ethers.formatEther(bufferedCostWei), "IOTX");
  console.log("hard-cap         :", HARD_CAP_IOTX, "IOTX");

  const bufferedCostIotx = Number(ethers.formatEther(bufferedCostWei));
  if (bufferedCostIotx > HARD_CAP_IOTX) {
    console.error(`[HARD-CAP EXCEEDED] buffered cost ${bufferedCostIotx} > ${HARD_CAP_IOTX} IOTX — ABORT.`);
    process.exit(2);
  }
  if (Number(ethers.formatEther(bal)) < bufferedCostIotx * 2) {
    console.error(`[BALANCE GUARD] balance < 2x buffered cost — ABORT.`);
    process.exit(2);
  }
  console.log("hard-cap check   : PASS");
  console.log("balance guard    : PASS");

  // ── Estimate-only short-circuit ─────────────────────────────────────────
  if (process.env.VAPI_REPLAY_PROOF_DEPLOY_CONFIRM !== "1") {
    console.log("\n[ESTIMATE-ONLY] VAPI_REPLAY_PROOF_DEPLOY_CONFIRM!=1 — NOT broadcasting.");
    console.log("Re-run with VAPI_REPLAY_PROOF_DEPLOY_CONFIRM=1 to deploy.");
    console.log("Per docs/data-economy-deploy-hold-and-arc5-readiness.md the");
    console.log("Arc 5 on-chain deploy is HELD pending explicit operator GO.");
    return;
  }

  // ── Broadcast ───────────────────────────────────────────────────────────
  console.log("\n[DEPLOYING] VAPI_REPLAY_PROOF_DEPLOY_CONFIRM=1 — broadcasting...");
  const c  = await Factory.deploy(groth16Addr, { gasLimit: bufferedGas });
  const tx = c.deploymentTransaction();
  console.log("deploy tx hash   :", tx.hash);
  await c.waitForDeployment();
  const addr = await c.getAddress();
  const rcpt = await provider.getTransactionReceipt(tx.hash);
  console.log("--- DEPLOYED ---");
  console.log("address          :", addr);
  console.log("block            :", rcpt.blockNumber);
  console.log("gas used         :", rcpt.gasUsed.toString());
  console.log("status           :", rcpt.status, rcpt.status === 1 ? "(success)" : "(FAILED)");

  // Post-deploy sanity: PROOF_TYPE constant should equal the FROZEN hash.
  const verifier = await ethers.getContractAt("VAPIReplayProofVerifier", addr);
  const expectedProofType = ethers.keccak256(ethers.toUtf8Bytes("VAPI-REPLAY-PROOF-v1"));
  const onchainProofType = await verifier.PROOF_TYPE();
  if (onchainProofType !== expectedProofType) {
    console.error(`[FROZEN DRIFT] PROOF_TYPE ${onchainProofType} != expected ${expectedProofType}`);
    process.exit(3);
  }
  console.log("PROOF_TYPE check :", onchainProofType, "(matches keccak256('VAPI-REPLAY-PROOF-v1'))");

  // Machine-readable line
  console.log("\nDEPLOY_RESULT_JSON " + JSON.stringify({
    contract: "VAPIReplayProofVerifier", chainId: 4690, address: addr,
    groth16Verifier: groth16Addr,
    txHash: tx.hash, block: rcpt.blockNumber, gasUsed: rcpt.gasUsed.toString(),
    status: rcpt.status,
    proofType: onchainProofType,
  }));
}

main().catch((e) => { console.error(e); process.exit(1); });
