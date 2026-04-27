/**
 * Operator series Phase O0 — Deploy AuditLog
 *
 * AuditLog is the third of five new contracts deployed in Stream 2 per
 * Pass 2C Section 3.4 (commit b9ddeeb2). It has NO dependencies on other
 * Phase O0 contracts — neither AgentRegistry nor AgentScope is referenced.
 * AuditLog is a system-level Tessera signed-tree-head anchor; it is a peer
 * of AgentRegistry/AgentScope under Decision Y-A's design (per Session 3
 * verification report).
 *
 * Architectural distinction (system-level vs per-agent):
 *   AuditLog                   — protocol-wide audit checkpoint anchor
 *   AgentAdjudicationRegistry  — per-agent action attestation (Session 5)
 *   The two contracts have distinct purposes and do not overlap.
 *
 * Storage layout: append-only array of (merkleRoot, treeSize, timestamp,
 * blockNumber) records, indexed by global checkpointId (uint256). NOT
 * indexed by agentId.
 *
 * Owner is the bridge wallet (0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692).
 * No constructor parameters beyond initialOwner.
 *
 * Gas estimate: ~0.05 IOTX per Pass 2C Section 3.4 (simplest contract;
 * append-only Merkle root storage with three integrity guards: anti-replay
 * unique merkleRoot, monotonic treeSize, ±3600s freshness window).
 *
 * ─────────────────────────────────────────────────────────────────────
 * STREAM 2-DEPLOY STATUS — DEFERRED, DO NOT INVOKE THIS SCRIPT YET
 * ─────────────────────────────────────────────────────────────────────
 *
 * This script ships as Stream 2-prep Session 3 work. Per Pass 2A V8,
 * deployment to IoTeX testnet requires the bridge wallet at >= 3 IOTX
 * (target 5 IOTX). Live balance at the most recent verification was
 * 0.5525 IOTX, well below the threshold. Operator funding action is a
 * precondition for invocation.
 *
 * Stream 2-deploy resumes when:
 *   1. Operator funds the wallet to >= 3 IOTX (target 5 IOTX per Pass 2A V8).
 *   2. Live eth_getBalance against https://babel-api.testnet.iotex.io
 *      confirms the new balance.
 *   3. The Stream 2-deploy session re-runs V1 verification, then invokes
 *      this script via:
 *         npx hardhat run scripts/deploy-audit-log.js --network iotex_testnet
 *
 * AuditLog has no contract dependencies, so deployment ordering relative
 * to AgentRegistry/AgentScope/AgentSlashing is flexible. AuditLog can be
 * deployed before, between, or after the other Stream 2 contracts.
 *
 * Until that sequence completes, this script is dormant code. Do NOT run it.
 *
 * ─────────────────────────────────────────────────────────────────────
 * Post-deploy actions (executed only at Stream 2-deploy time)
 * ─────────────────────────────────────────────────────────────────────
 *
 *   - deployed-addresses.json updated with AuditLog address.
 *   - bridge/.env.testnet hint printed: AUDIT_LOG_ADDRESS=<addr>.
 *   - CLAUDE.md note block updated: contracts X → X+1, Stream 2 deploy
 *     progress.
 *   - Smoke tests: owner() returns deployer, totalCheckpoints() returns 0,
 *     getLatestCheckpoint() returns sentinel zero values,
 *     MAX_TIMESTAMP_AGE() returns 3600.
 *
 * Post-deploy operational note:
 *   The Tessera upstream signed-tree-head feed is deferred to P1+. AuditLog
 *   ships empty in P0. The first appendCheckpoint occurs when the upstream
 *   Tessera log is wired to a bridge module that owns the AuditLog contract
 *   and posts checkpoints on its signing cadence. Until then, the contract
 *   is "infrastructure in place, enforcement inactive" — same pattern as
 *   Stream 1's path-scope gate awaiting GitHub Apps registration.
 */

const { ethers } = require("hardhat");
const fs = require("fs");
const path = require("path");

async function main() {
  const [deployer] = await ethers.getSigners();
  console.log("Deploying AuditLog with:", deployer.address);

  // Pre-deploy balance check — guards against accidental invocation when
  // wallet is below the Pass 2A V8 threshold.
  const bal = await ethers.provider.getBalance(deployer.address);
  const balIotx = Number(ethers.formatEther(bal));
  console.log(`Pre-deploy balance: ${balIotx.toFixed(6)} IOTX`);
  if (balIotx < 3.0) {
    console.error(
      `ABORT: balance ${balIotx.toFixed(6)} IOTX is below the Pass 2A V8 ` +
        "threshold of 3 IOTX. Fund wallet before deploying."
    );
    process.exit(1);
  }

  const Factory = await ethers.getContractFactory("AuditLog");
  const contract = await Factory.deploy(deployer.address);
  await contract.waitForDeployment();
  const addr = await contract.getAddress();

  console.log("AuditLog deployed to:", addr);

  // Smoke tests — confirm contract is live, owner correct, empty-state
  // sentinels operational.
  const ownerAddr = await contract.owner();
  console.assert(ownerAddr === deployer.address, "Smoke test failed: owner mismatch");
  console.log("Smoke test passed: owner =", ownerAddr);

  const total = await contract.totalCheckpoints();
  console.assert(total === 0n, "Smoke test failed: totalCheckpoints should be 0");
  console.log("Smoke test passed: totalCheckpoints =", total.toString());

  const maxAge = await contract.MAX_TIMESTAMP_AGE();
  console.assert(maxAge === 3600n, "Smoke test failed: MAX_TIMESTAMP_AGE should be 3600");
  console.log("Smoke test passed: MAX_TIMESTAMP_AGE =", maxAge.toString());

  // Empty-state sentinel: getLatestCheckpoint returns zeros, not revert.
  const [root, size, ts, blk] = await contract.getLatestCheckpoint();
  console.assert(root === ethers.ZeroHash, "Smoke test failed: empty root");
  console.assert(size === 0n, "Smoke test failed: empty size");
  console.assert(ts === 0n, "Smoke test failed: empty ts");
  console.assert(blk === 0n, "Smoke test failed: empty block");
  console.log("Smoke test passed: getLatestCheckpoint returns sentinel zeros on empty state");

  // Post-deploy balance check.
  const balAfter = await ethers.provider.getBalance(deployer.address);
  const gasSpent = Number(ethers.formatEther(bal - balAfter));
  console.log(`Post-deploy balance: ${Number(ethers.formatEther(balAfter)).toFixed(6)} IOTX`);
  console.log(`Gas spent on deploy: ${gasSpent.toFixed(6)} IOTX`);

  // Update deployed-addresses.json.
  const addrFile = path.join(__dirname, "../deployed-addresses.json");
  let addresses = {};
  if (fs.existsSync(addrFile)) {
    addresses = JSON.parse(fs.readFileSync(addrFile, "utf8"));
  }
  addresses["AuditLog"] = addr;
  addresses["_phase_o0_audit_log_status"] = "deployed";
  addresses["_phase_o0_audit_log_note"] =
    "Phase O0 Stream 2: AuditLog — system-level Tessera signed-tree-head anchor; " +
    "Ownable + ReentrancyGuard pattern; " +
    "owner is bridge wallet 0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692; " +
    "no contract dependencies (Y-A design, distinct from per-agent contracts); " +
    "ships empty in P0; first checkpoint occurs in P1+ when Tessera upstream feed is wired.";
  fs.writeFileSync(addrFile, JSON.stringify(addresses, null, 2));
  console.log("deployed-addresses.json updated");

  console.log("\nNext steps:");
  console.log("  bridge/.env.testnet:    AUDIT_LOG_ADDRESS=" + addr);
  console.log("  CLAUDE.md update:       Stream 2 deploy 3/5 COMPLETE");
  console.log("  Next contracts:         AgentSlashing (Session 4) and");
  console.log("                          AgentAdjudicationRegistry (Session 5)");
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
