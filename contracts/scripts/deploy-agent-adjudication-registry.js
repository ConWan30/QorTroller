/**
 * Operator series Phase O0 — Deploy AgentAdjudicationRegistry
 *
 * AgentAdjudicationRegistry is the FIFTH AND FINAL contract deployed in
 * Stream 2 per Pass 2C Section 3.5 (commit b9ddeeb2). It depends on BOTH
 * AgentRegistry (Session 1, commit b063718e) AND AgentScope (Session 2,
 * commit d1453f84). This is the first Phase O0 contract with two upstream
 * dependencies.
 *
 * Architectural significance: this contract is the architectural climax
 * of Stream 2-prep because it brings together agent identity (AgentRegistry),
 * operational scope (AgentScope), and the on-chain attestation surface
 * where AGENT_COMMIT v1 (sixth FROZEN-v1 primitive, per Pass 2A V10) and
 * PHYSICAL_DATA_ATTESTATION v1 (seventh FROZEN-v1 primitive, per Pass 2B
 * Path 3) land at the contract layer.
 *
 * Decisions resolved in Session 5:
 *   U-Enum — actionType is a Solidity enum with four entries
 *            (AGENT_COMMIT, PHYSICAL_DATA_ATTESTATION, AUDIT_LOG_CHECKPOINT,
 *            BOUNDARY_UPDATE). Diverges from Pass 2C Section 3.5/4.3's
 *            string specification but better serves Pass 2C's underlying
 *            FROZEN-vocabulary architectural intent.
 *   V-A    — reserved actionTypes (AUDIT_LOG_CHECKPOINT=2, BOUNDARY_UPDATE=3)
 *            pass validation in Phase O0; reserved status is operator-policy
 *            documentation, not contract enforcement.
 *   UNION  — storage design combines operator's anchorId-keyed array with
 *            Pass 2C's actionHash anti-replay tracker. Anchor[] _anchors
 *            (primary) + mapping(agentId => uint256[]) _agentAnchors
 *            (per-agent index) + mapping(actionHash => anchorId+1)
 *            _anchorIdByHash (anti-replay).
 *
 * The contract's requireAgentScope modifier reads from AgentScope.scopeRoot
 * per Decision C from Session 2 (Interpretation 1 two-layer scope
 * enforcement). At Phase O0 exit, no agents have scope set, so the modifier
 * rejects all anchor calls — consistent with Pass 2C's "Phase O0 has no
 * operational authority" framing.
 *
 * Storage layout: Anchor[] indexed by anchorId (uint256). Per-agent
 * index for efficient lookup. Anti-replay tracker for actionHash uniqueness.
 *
 * Owner is the bridge wallet (0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692).
 * Both agentRegistry and agentScope references are immutable.
 *
 * Gas estimate: ~0.08 IOTX per Pass 2C Section 3.5 (larger than
 * AgentRegistry due to requireAgentScope modifier logic + actionType
 * vocabulary enforcement + UNION storage's three components).
 *
 * ─────────────────────────────────────────────────────────────────────
 * STREAM 2-DEPLOY STATUS — DEFERRED, DO NOT INVOKE THIS SCRIPT YET
 * ─────────────────────────────────────────────────────────────────────
 *
 * This script ships as Stream 2-prep Session 5 work — the FINAL
 * Stream 2-prep session. Per Pass 2A V8, deployment to IoTeX testnet
 * requires the bridge wallet at >= 3 IOTX (target 5 IOTX). Live balance
 * at the most recent verification was 0.5525 IOTX, well below the
 * threshold. Operator funding action is a precondition for invocation.
 *
 * Stream 2-deploy resumes when:
 *   1. Operator funds the wallet to >= 3 IOTX (target 5 IOTX per Pass 2A V8).
 *   2. Live eth_getBalance against https://babel-api.testnet.iotex.io
 *      confirms the new balance.
 *   3. AgentRegistry has been deployed (Session 1's deploy-agent-registry.js
 *      invoked first; AgentRegistry address present in deployed-addresses.json).
 *   4. AgentScope has been deployed (Session 2's deploy-agent-scope.js
 *      invoked; AgentScope address present in deployed-addresses.json).
 *   5. The Stream 2-deploy session re-runs V1 verification, then invokes
 *      this script via:
 *         npx hardhat run scripts/deploy-agent-adjudication-registry.js \
 *           --network iotex_testnet
 *
 * Until that sequence completes, this script is dormant code. Do NOT run it.
 *
 * ─────────────────────────────────────────────────────────────────────
 * Post-deploy actions (executed only at Stream 2-deploy time)
 * ─────────────────────────────────────────────────────────────────────
 *
 *   - deployed-addresses.json updated with AgentAdjudicationRegistry address.
 *   - bridge/.env.testnet hint printed:
 *     AGENT_ADJUDICATION_REGISTRY_ADDRESS=<addr>.
 *   - CLAUDE.md note block updated: contracts X → X+1, Stream 2 deploy 5/5
 *     COMPLETE, Phase O0 contract deployments fully landed.
 *   - Smoke tests: owner() returns deployer, agentRegistry() returns
 *     Session 1 address, agentScope() returns Session 2 address,
 *     getAnchorCount() returns 0.
 */

const { ethers } = require("hardhat");
const fs = require("fs");
const path = require("path");

async function main() {
  const [deployer] = await ethers.getSigners();
  console.log("Deploying AgentAdjudicationRegistry with:", deployer.address);

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

  // Read AgentRegistry AND AgentScope addresses from deployed-addresses.json.
  // Two-tier dependency check: registry first, then scope.
  const addrFile = path.join(__dirname, "../deployed-addresses.json");
  if (!fs.existsSync(addrFile)) {
    console.error("ABORT: contracts/deployed-addresses.json does not exist.");
    console.error("AgentRegistry and AgentScope must be deployed before AgentAdjudicationRegistry.");
    console.error("Run deploy-agent-registry.js first, then deploy-agent-scope.js.");
    process.exit(1);
  }
  const addresses = JSON.parse(fs.readFileSync(addrFile, "utf8"));

  const agentRegistryAddr = addresses["AgentRegistry"];
  if (!agentRegistryAddr) {
    console.error(
      "ABORT: AgentRegistry address not found in deployed-addresses.json."
    );
    console.error("AgentRegistry must be deployed before AgentAdjudicationRegistry.");
    console.error("Run deploy-agent-registry.js first, then re-run this script.");
    process.exit(1);
  }
  console.log("Using AgentRegistry at:", agentRegistryAddr);

  const agentScopeAddr = addresses["AgentScope"];
  if (!agentScopeAddr) {
    console.error(
      "ABORT: AgentScope address not found in deployed-addresses.json."
    );
    console.error("AgentScope must be deployed before AgentAdjudicationRegistry.");
    console.error("Run deploy-agent-scope.js first, then re-run this script.");
    process.exit(1);
  }
  console.log("Using AgentScope at:   ", agentScopeAddr);

  const Factory = await ethers.getContractFactory("AgentAdjudicationRegistry");
  const contract = await Factory.deploy(
    deployer.address,
    agentRegistryAddr,
    agentScopeAddr
  );
  await contract.waitForDeployment();
  const addr = await contract.getAddress();

  console.log("AgentAdjudicationRegistry deployed to:", addr);

  // Smoke tests.
  const ownerAddr = await contract.owner();
  console.assert(ownerAddr === deployer.address, "Smoke test failed: owner mismatch");
  console.log("Smoke test passed: owner =", ownerAddr);

  const registryRef = await contract.agentRegistry();
  console.assert(
    registryRef === agentRegistryAddr,
    "Smoke test failed: agentRegistry reference mismatch"
  );
  console.log("Smoke test passed: agentRegistry =", registryRef);

  const scopeRef = await contract.agentScope();
  console.assert(
    scopeRef === agentScopeAddr,
    "Smoke test failed: agentScope reference mismatch"
  );
  console.log("Smoke test passed: agentScope =", scopeRef);

  const total = await contract.getAnchorCount();
  console.assert(total === 0n, "Smoke test failed: getAnchorCount should be 0");
  console.log("Smoke test passed: getAnchorCount =", total.toString());

  // Post-deploy balance check.
  const balAfter = await ethers.provider.getBalance(deployer.address);
  const gasSpent = Number(ethers.formatEther(bal - balAfter));
  console.log(`Post-deploy balance: ${Number(ethers.formatEther(balAfter)).toFixed(6)} IOTX`);
  console.log(`Gas spent on deploy: ${gasSpent.toFixed(6)} IOTX`);

  // Update deployed-addresses.json.
  addresses["AgentAdjudicationRegistry"] = addr;
  addresses["_phase_o0_agent_adjudication_registry_status"] = "deployed";
  addresses["_phase_o0_agent_adjudication_registry_note"] =
    "Phase O0 Stream 2: AgentAdjudicationRegistry — agent-scoped action anchor; " +
    "hosts AGENT_COMMIT v1 (Pass 2A V10) and PHYSICAL_DATA_ATTESTATION v1 (Pass 2B Path 3) " +
    "via U-Enum FROZEN four-entry actionType vocabulary; V-A reserved-as-documentation; " +
    "UNION storage (anchorId-keyed array + per-agent index + actionHash anti-replay); " +
    "Ownable + ReentrancyGuard pattern; " +
    "owner is bridge wallet 0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692; " +
    "agentRegistry immutable at " + agentRegistryAddr + "; " +
    "agentScope immutable at " + agentScopeAddr + "; " +
    "requireAgentScope modifier reads operational truth (Decision C, Session 2).";
  fs.writeFileSync(addrFile, JSON.stringify(addresses, null, 2));
  console.log("deployed-addresses.json updated");

  console.log("\nNext steps:");
  console.log("  bridge/.env.testnet:    AGENT_ADJUDICATION_REGISTRY_ADDRESS=" + addr);
  console.log("  CLAUDE.md update:       Stream 2 deploy 5/5 COMPLETE — Phase O0 contracts fully deployed");
  console.log("");
  console.log("With this deploy, all five Phase O0 contracts (AgentRegistry,");
  console.log("AgentScope, AuditLog, AgentSlashing, AgentAdjudicationRegistry)");
  console.log("are LIVE on IoTeX testnet. Stream 2 of Phase O0 implementation");
  console.log("completes; Stream 3+ (bridge modules for AGENT_COMMIT v1 +");
  console.log("PHYSICAL_DATA_ATTESTATION v1 + agent identity infrastructure)");
  console.log("begins next.");
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
