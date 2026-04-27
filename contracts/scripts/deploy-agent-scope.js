/**
 * Operator series Phase O0 — Deploy AgentScope
 *
 * AgentScope is the second of five new contracts deployed in Stream 2 per
 * Pass 2C Section 3.2 (commit b9ddeeb2). It depends on AgentRegistry
 * (Session 1, commit b063718e) — the deploy script reads AgentRegistry's
 * address from deployed-addresses.json and passes it to the AgentScope
 * constructor.
 *
 * Two-layer scope enforcement (architectural reasoning, see AgentScope.sol):
 *   AgentRegistry.scopeHash — governance commitment (registered scope).
 *   AgentScope.scopeRoot   — operational state (live enforced scope).
 *   The two are deliberately allowed to differ; auditors compare them.
 *   AgentAdjudicationRegistry's requireAgentScope modifier (Session 5)
 *   reads from AgentScope.scopeRoot — operational truth at moment of action.
 *
 * Storage layout: agentId (bytes32) → scopeRoot (bytes32 Merkle root of
 * the agent's policy bundle). Default value bytes32(0) for any unset agent
 * (Pass 2C Section 3.2 default Phase O0 state).
 *
 * Owner is the bridge wallet (0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692).
 * agentRegistry reference is immutable for the AgentScope's lifetime.
 *
 * Gas estimate: ~0.05 IOTX per Pass 2C Section 3.2 (smaller than
 * AgentRegistry; just Merkle root storage + per-agent mapping + one
 * cross-contract view call per setAgentScopeRoot).
 *
 * ─────────────────────────────────────────────────────────────────────
 * STREAM 2-DEPLOY STATUS — DEFERRED, DO NOT INVOKE THIS SCRIPT YET
 * ─────────────────────────────────────────────────────────────────────
 *
 * This script ships as Stream 2-prep Session 2 work. Per Pass 2A V8,
 * deployment to IoTeX testnet requires the bridge wallet at >= 3 IOTX
 * (target 5 IOTX). Live balance at the most recent verification was
 * 0.5525 IOTX, well below the threshold. Operator funding action is a
 * precondition for invocation.
 *
 * Stream 2-deploy resumes when:
 *   1. Operator funds the wallet to >= 3 IOTX (target 5 IOTX per Pass 2A V8).
 *   2. Live eth_getBalance against https://babel-api.testnet.iotex.io
 *      confirms the new balance.
 *   3. AgentRegistry has been deployed (Session 1's deploy-agent-registry.js
 *      invoked first; AgentRegistry address present in deployed-addresses.json).
 *   4. The Stream 2-deploy session re-runs V1 verification, then invokes
 *      this script via:
 *         npx hardhat run scripts/deploy-agent-scope.js --network iotex_testnet
 *
 * Until that sequence completes, this script is dormant code. Do NOT run it.
 *
 * ─────────────────────────────────────────────────────────────────────
 * Post-deploy actions (executed only at Stream 2-deploy time)
 * ─────────────────────────────────────────────────────────────────────
 *
 *   - deployed-addresses.json updated with AgentScope address.
 *   - bridge/.env.testnet hint printed: AGENT_SCOPE_ADDRESS=<addr>.
 *   - CLAUDE.md note block updated: contracts 47 → 48, Stream 2 deploy
 *     progress.
 *   - Smoke tests: owner() returns deployer, agentRegistry() returns the
 *     value from deployed-addresses.json, getScopeRoot returns bytes32(0)
 *     for any never-set agent.
 */

const { ethers } = require("hardhat");
const fs = require("fs");
const path = require("path");

async function main() {
  const [deployer] = await ethers.getSigners();
  console.log("Deploying AgentScope with:", deployer.address);

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

  // Read AgentRegistry address from deployed-addresses.json. AgentScope's
  // constructor requires it; deployment cannot proceed without it.
  const addrFile = path.join(__dirname, "../deployed-addresses.json");
  if (!fs.existsSync(addrFile)) {
    console.error("ABORT: contracts/deployed-addresses.json does not exist.");
    console.error("AgentRegistry must be deployed before AgentScope.");
    console.error("Run deploy-agent-registry.js first.");
    process.exit(1);
  }
  const addresses = JSON.parse(fs.readFileSync(addrFile, "utf8"));
  const agentRegistryAddr = addresses["AgentRegistry"];
  if (!agentRegistryAddr) {
    console.error(
      "ABORT: AgentRegistry address not found in deployed-addresses.json."
    );
    console.error("AgentRegistry must be deployed before AgentScope.");
    console.error("Run deploy-agent-registry.js first, then re-run this script.");
    process.exit(1);
  }
  console.log("Using AgentRegistry at:", agentRegistryAddr);

  const Factory = await ethers.getContractFactory("AgentScope");
  const contract = await Factory.deploy(deployer.address, agentRegistryAddr);
  await contract.waitForDeployment();
  const addr = await contract.getAddress();

  console.log("AgentScope deployed to:", addr);

  // Smoke tests — confirm contract is live, owner correct, and AgentRegistry
  // reference matches deployed-addresses.json.
  const ownerAddr = await contract.owner();
  console.assert(ownerAddr === deployer.address, "Smoke test failed: owner mismatch");
  console.log("Smoke test passed: owner =", ownerAddr);

  const registryRef = await contract.agentRegistry();
  console.assert(
    registryRef === agentRegistryAddr,
    "Smoke test failed: agentRegistry reference mismatch"
  );
  console.log("Smoke test passed: agentRegistry =", registryRef);

  // Default state: unset agent returns bytes32(0).
  const sentinelId = ethers.keccak256(ethers.toUtf8Bytes("smoke-test-never-set"));
  const defaultRoot = await contract.getScopeRoot(sentinelId);
  console.assert(
    defaultRoot === ethers.ZeroHash,
    "Smoke test failed: default scopeRoot should be bytes32(0)"
  );
  console.log("Smoke test passed: default getScopeRoot returns bytes32(0)");

  // Post-deploy balance check.
  const balAfter = await ethers.provider.getBalance(deployer.address);
  const gasSpent = Number(ethers.formatEther(bal - balAfter));
  console.log(`Post-deploy balance: ${Number(ethers.formatEther(balAfter)).toFixed(6)} IOTX`);
  console.log(`Gas spent on deploy: ${gasSpent.toFixed(6)} IOTX`);

  // Update deployed-addresses.json.
  addresses["AgentScope"] = addr;
  addresses["_phase_o0_agent_scope_status"] = "deployed";
  addresses["_phase_o0_agent_scope_note"] =
    "Phase O0 Stream 2: AgentScope — operational scope storage (agentId → scopeRoot); " +
    "Ownable + ReentrancyGuard pattern matching AgentRegistry; " +
    "owner is bridge wallet 0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692; " +
    "agentRegistry reference immutable at " + agentRegistryAddr + "; " +
    "two-layer scope enforcement: AgentRegistry.scopeHash = governance commitment, " +
    "AgentScope.scopeRoot = operational state, deliberately allowed to differ.";
  fs.writeFileSync(addrFile, JSON.stringify(addresses, null, 2));
  console.log("deployed-addresses.json updated");

  console.log("\nNext steps:");
  console.log("  bridge/.env.testnet:    AGENT_SCOPE_ADDRESS=" + addr);
  console.log("  CLAUDE.md update:       contracts 47 -> 48, Stream 2 deploy 2/5 COMPLETE");
  console.log("  Next contract:          AuditLog (independent of AgentRegistry/AgentScope)");
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
