/**
 * VHPExpiresAtAdapter deploy — Curator governance ceremony unblock.
 *
 * Constructor takes one arg: the address of the canonical VAPIVerifiedHumanProof
 * (Phase 99C, read from contracts/deployed-addresses.json:VAPIVerifiedHumanProof).
 *
 * Why this deploy exists: 2026-05-28 V-check found that BBG.proposeWithVHP()
 * at line 97 calls `vhpContract.expiresAt(vhpTokenId)` which reverts against
 * the deployed VAPIVerifiedHumanProof (Phase 99C's auto-generated `vhpData`
 * struct getter exposes `expiresAt` as field 5 of a 7-tuple, not as a
 * standalone method). This adapter shims the IVHP222 interface BBG expects.
 *
 * Post-deploy steps (separate operator-fired txs, NOT in this script):
 *   1. Operator calls BBG.setVHPContract(adapter) — onlyOwner.
 *   2. Operator re-runs scripts/fire_curator_governance_proposal.py.
 *
 * DISCIPLINE (triple-gate, matches every prior deploy this arc):
 *   - Reads VAPIVerifiedHumanProof address from deployed-addresses.json.
 *   - estimate_gas + 1.25x buffer + hard-cap check BEFORE broadcast.
 *   - ESTIMATE-ONLY by default. Broadcast ONLY when VHP_ADAPTER_DEPLOY_CONFIRM=1.
 *
 * Usage:
 *   # estimate + report (no spend):
 *   npx hardhat run scripts/deploy-vhp-expires-at-adapter.js --network iotex_testnet
 *   # actually deploy (operator-confirmed):
 *   VHP_ADAPTER_DEPLOY_CONFIRM=1 npx hardhat run scripts/deploy-vhp-expires-at-adapter.js --network iotex_testnet
 */
const { ethers } = require("hardhat");
const fs   = require("fs");
const path = require("path");

const HARD_CAP_IOTX = 1.0;   // runaway-guard (adapter is small; ~0.3-0.4 expected)
const GAS_BUFFER    = 1.25;  // estimate_gas x 1.25

async function main() {
  const [deployer] = await ethers.getSigners();
  const provider = deployer.provider;
  const bal = await provider.getBalance(deployer.address);
  console.log("Deployer        :", deployer.address);
  console.log("Balance         :", ethers.formatEther(bal), "IOTX");

  // Load VHP address from deployed-addresses.json
  const addrPath = path.join(__dirname, "..", "deployed-addresses.json");
  let existing = {};
  try {
    existing = JSON.parse(fs.readFileSync(addrPath, "utf8"));
  } catch (e) {
    console.error("ERROR: could not load deployed-addresses.json:", e.message);
    process.exit(2);
  }
  const vhpAddr = existing.VAPIVerifiedHumanProof || "";
  if (!vhpAddr) {
    console.error("ERROR: VAPIVerifiedHumanProof address missing from deployed-addresses.json");
    process.exit(2);
  }
  console.log("VAPIVerifiedHumanProof:", vhpAddr);

  const Factory  = await ethers.getContractFactory("VHPExpiresAtAdapter");
  const deployTx = await Factory.getDeployTransaction(vhpAddr);

  // --- estimate ---
  const estGas         = await provider.estimateGas({ ...deployTx, from: deployer.address });
  const feeData        = await provider.getFeeData();
  const gasPrice       = feeData.gasPrice ?? 1000000000000n;
  const bufferedGas    = (estGas * BigInt(Math.round(GAS_BUFFER * 100))) / 100n;
  const estCostWei     = estGas * gasPrice;
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
  console.log("hard-cap check  : PASS (buffered cost within cap)");

  if (process.env.VHP_ADAPTER_DEPLOY_CONFIRM !== "1") {
    console.log("\n[ESTIMATE-ONLY] VHP_ADAPTER_DEPLOY_CONFIRM!=1 — NOT broadcasting.");
    console.log("Re-run with VHP_ADAPTER_DEPLOY_CONFIRM=1 to deploy.");
    return;
  }

  // --- broadcast (operator-confirmed) ---
  console.log("\n[DEPLOYING] VHP_ADAPTER_DEPLOY_CONFIRM=1 — broadcasting...");
  const c  = await Factory.deploy(vhpAddr, { gasLimit: bufferedGas });
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

  // sanity: vhp() returns the constructor-passed address + 3 IVHP222 methods
  // callable against tokenId=2 (the bridge wallet's Phase 99 VHP)
  const wrappedVhp = await c.vhp();
  console.log("vhp() (immutable):", wrappedVhp, wrappedVhp.toLowerCase() === vhpAddr.toLowerCase() ? "(== constructor arg OK)" : "(MISMATCH)");

  const smokeOwner = await c.ownerOf(2);
  const smokeValid = await c.isValid(2);
  const smokeExpires = await c.expiresAt(2);
  console.log("smoke ownerOf(2) :", smokeOwner);
  console.log("smoke isValid(2) :", smokeValid);
  console.log("smoke expiresAt(2):", smokeExpires.toString(), "(epoch s)");

  // machine-readable line
  console.log("\nDEPLOY_RESULT_JSON " + JSON.stringify({
    contract: "VHPExpiresAtAdapter", chainId: 4690, address: addr,
    txHash: tx.hash, block: rcpt.blockNumber, gasUsed: rcpt.gasUsed.toString(),
    status: rcpt.status, wrappedVhp: wrappedVhp,
  }));
}

main().catch((e) => { console.error(e); process.exit(1); });
