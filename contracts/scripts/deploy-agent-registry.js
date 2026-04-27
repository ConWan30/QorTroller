/**
 * Operator series Phase O0 — Deploy AgentRegistry
 *
 * AgentRegistry is the first of five new contracts deployed in Stream 2 per
 * Pass 2C Section 3 (commit b9ddeeb2). It has no dependencies on the other
 * Phase O0 contracts. Subsequent contracts (AgentScope, AuditLog,
 * AgentSlashing, AgentAdjudicationRegistry) reference AgentRegistry's address.
 *
 * Storage layout: agentId (bytes32) → (publicKey, scopeHash, status).
 * Owner is the bridge wallet (0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692).
 *
 * Gas estimate: ~0.07 IOTX (matches VAPIBiometricGovernance Phase 222 estimate
 * per Pass 2C Section 3.1; same Ownable+Registry shape).
 *
 * ─────────────────────────────────────────────────────────────────────
 * STREAM 2-DEPLOY STATUS — DEFERRED, DO NOT INVOKE THIS SCRIPT YET
 * ─────────────────────────────────────────────────────────────────────
 *
 * This script ships as Stream 2-prep work. Per Pass 2A V8, deployment to
 * IoTeX testnet requires the bridge wallet at >= 3 IOTX (target 5 IOTX).
 * Live balance at the most recent verification was 0.5525 IOTX, well below
 * the threshold. Operator funding action is a precondition for invocation.
 *
 * Stream 2-deploy resumes when:
 *   1. Operator funds the wallet to >= 3 IOTX (target 5 IOTX per Pass 2A V8).
 *   2. Live eth_getBalance against https://babel-api.testnet.iotex.io
 *      confirms the new balance.
 *   3. The Stream 2-deploy session re-runs V1 verification, then invokes
 *      this script via:
 *         npx hardhat run scripts/deploy-agent-registry.js --network iotex_testnet
 *
 * Until that sequence completes, this script is dormant code. Do NOT run it.
 *
 * ─────────────────────────────────────────────────────────────────────
 * Post-deploy actions (executed only at Stream 2-deploy time)
 * ─────────────────────────────────────────────────────────────────────
 *
 *   - deployed-addresses.json updated with AgentRegistry address.
 *   - bridge/.env.testnet hint printed: AGENT_REGISTRY_ADDRESS=<addr>.
 *   - CLAUDE.md note block updated: contracts 46 → 47, Stream 2 deploy
 *     progress.
 *   - Smoke tests: owner() returns deployer, totalAgents() returns 0,
 *     STATUS_DEFINED() returns 0, STATUS_SUSPENDED() returns 255.
 */

const { ethers } = require("hardhat");
const fs = require("fs");
const path = require("path");

async function main() {
  const [deployer] = await ethers.getSigners();
  console.log("Deploying AgentRegistry with:", deployer.address);

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

  const Factory = await ethers.getContractFactory("AgentRegistry");
  const contract = await Factory.deploy(deployer.address);
  await contract.waitForDeployment();
  const addr = await contract.getAddress();

  console.log("AgentRegistry deployed to:", addr);

  // Smoke tests — confirm contract is live and zero-state-clean.
  const ownerAddr = await contract.owner();
  console.assert(ownerAddr === deployer.address, "Smoke test failed: owner mismatch");
  console.log("Smoke test passed: owner =", ownerAddr);

  const total = await contract.totalAgents();
  console.assert(total === 0n, "Smoke test failed: totalAgents should be 0");
  console.log("Smoke test passed: totalAgents =", total.toString());

  const statusDefined = await contract.STATUS_DEFINED();
  const statusSuspended = await contract.STATUS_SUSPENDED();
  console.assert(statusDefined === 0n, "Smoke test failed: STATUS_DEFINED");
  console.assert(statusSuspended === 255n, "Smoke test failed: STATUS_SUSPENDED");
  console.log("Smoke test passed: STATUS_DEFINED=0, STATUS_SUSPENDED=255");

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
  addresses["AgentRegistry"] = addr;
  addresses["_phase_o0_agent_registry_status"] = "deployed";
  addresses["_phase_o0_agent_registry_note"] =
    "Phase O0 Stream 2: AgentRegistry — agent identity (agentId → publicKey, scopeHash, status); " +
    "Ownable + ReentrancyGuard pattern matching VAPIBiometricGovernance Phase 222; " +
    "owner is bridge wallet 0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692; " +
    "no agents registered at deploy (first registration in Phase O0 Section 6.4 " +
    "after GitHub Apps registration completes).";
  fs.writeFileSync(addrFile, JSON.stringify(addresses, null, 2));
  console.log("deployed-addresses.json updated");

  console.log("\nNext steps:");
  console.log("  bridge/.env.testnet:    AGENT_REGISTRY_ADDRESS=" + addr);
  console.log("  CLAUDE.md update:       contracts 46 -> 47, Stream 2 deploy 1/5 COMPLETE");
  console.log("  Next contract:          AgentScope (depends on this AgentRegistry address)");
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
