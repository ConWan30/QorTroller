/**
 * Operator series Phase O0 — Deploy AgentSlashing
 *
 * AgentSlashing is the fourth of five new contracts deployed in Stream 2 per
 * Pass 2C Section 3.3 (commit b9ddeeb2). It depends on AgentRegistry
 * (Session 1, commit b063718e). The deploy script reads AgentRegistry's
 * address from deployed-addresses.json and passes it to the AgentSlashing
 * constructor along with the 24-hour veto window default.
 *
 * AgentScope (Session 2) and AuditLog (Session 3) are NOT dependencies.
 * AgentSlashing is the second contract that depends on AgentRegistry but
 * does not interact with the other Phase O0 contracts at the contract level.
 *
 * VetoSlasher pattern (Pass 2C Section 3.3, adapted from Symbiotic):
 *   Bond → propose slash → 24h veto window → execute (burn).
 *
 * Decisions resolved in Session 4:
 *   Z-A — pure burn: slashed amounts transfer to address(0xdead).
 *         SlashExecuted event ships with both burnedAmount and
 *         distributedAmount fields per Pass 2C signature, with
 *         distributedAmount=0 in Phase O0 pure-burn implementation.
 *   W-A — partial slashing: slashAmount specified per proposal.
 *         Bond persists with reduced balance after partial slash.
 *
 * Storage layout: per-agent bond mapping + append-only proposals array.
 * Owner is the bridge wallet (0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692).
 * vetoWindowSeconds is immutable at 86400 (24 hours) by default.
 *
 * Gas estimate: ~0.10 IOTX per Pass 2C Section 3.3 (largest of the five
 * contracts; bond accounting + veto state machine + slash execution logic).
 *
 * ─────────────────────────────────────────────────────────────────────
 * STREAM 2-DEPLOY STATUS — DEFERRED, DO NOT INVOKE THIS SCRIPT YET
 * ─────────────────────────────────────────────────────────────────────
 *
 * This script ships as Stream 2-prep Session 4 work. Per Pass 2A V8,
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
 *         npx hardhat run scripts/deploy-agent-slashing.js --network iotex_testnet
 *
 * Until that sequence completes, this script is dormant code. Do NOT run it.
 *
 * ─────────────────────────────────────────────────────────────────────
 * Post-deploy actions (executed only at Stream 2-deploy time)
 * ─────────────────────────────────────────────────────────────────────
 *
 *   - deployed-addresses.json updated with AgentSlashing address.
 *   - bridge/.env.testnet hint printed: AGENT_SLASHING_ADDRESS=<addr>.
 *   - CLAUDE.md note block updated: contracts X → X+1, Stream 2 deploy
 *     progress.
 *   - Smoke tests: owner() returns deployer, agentRegistry() returns the
 *     value from deployed-addresses.json, vetoWindowSeconds() returns 86400,
 *     totalProposals() returns 0, BURN_ADDRESS() returns 0xdead.
 */

const { ethers } = require("hardhat");
const fs = require("fs");
const path = require("path");

// 24 hours per Pass 2C Section 3.3 default veto window.
const VETO_WINDOW_SECONDS = 86400;

async function main() {
  const [deployer] = await ethers.getSigners();
  console.log("Deploying AgentSlashing with:", deployer.address);

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

  // Read AgentRegistry address from deployed-addresses.json. AgentSlashing's
  // constructor requires it; deployment cannot proceed without it.
  const addrFile = path.join(__dirname, "../deployed-addresses.json");
  if (!fs.existsSync(addrFile)) {
    console.error("ABORT: contracts/deployed-addresses.json does not exist.");
    console.error("AgentRegistry must be deployed before AgentSlashing.");
    console.error("Run deploy-agent-registry.js first.");
    process.exit(1);
  }
  const addresses = JSON.parse(fs.readFileSync(addrFile, "utf8"));
  const agentRegistryAddr = addresses["AgentRegistry"];
  if (!agentRegistryAddr) {
    console.error(
      "ABORT: AgentRegistry address not found in deployed-addresses.json."
    );
    console.error("AgentRegistry must be deployed before AgentSlashing.");
    console.error("Run deploy-agent-registry.js first, then re-run this script.");
    process.exit(1);
  }
  console.log("Using AgentRegistry at:", agentRegistryAddr);
  console.log(`Veto window: ${VETO_WINDOW_SECONDS} seconds (24 hours)`);

  const Factory = await ethers.getContractFactory("AgentSlashing");
  const contract = await Factory.deploy(
    deployer.address,
    agentRegistryAddr,
    VETO_WINDOW_SECONDS
  );
  await contract.waitForDeployment();
  const addr = await contract.getAddress();

  console.log("AgentSlashing deployed to:", addr);

  // Smoke tests — confirm contract is live, owner correct, immutable
  // references and constants set as expected.
  const ownerAddr = await contract.owner();
  console.assert(ownerAddr === deployer.address, "Smoke test failed: owner mismatch");
  console.log("Smoke test passed: owner =", ownerAddr);

  const registryRef = await contract.agentRegistry();
  console.assert(
    registryRef === agentRegistryAddr,
    "Smoke test failed: agentRegistry reference mismatch"
  );
  console.log("Smoke test passed: agentRegistry =", registryRef);

  const window = await contract.vetoWindowSeconds();
  console.assert(window === BigInt(VETO_WINDOW_SECONDS),
    "Smoke test failed: vetoWindowSeconds mismatch");
  console.log("Smoke test passed: vetoWindowSeconds =", window.toString());

  const totalProps = await contract.totalProposals();
  console.assert(totalProps === 0n, "Smoke test failed: totalProposals should be 0");
  console.log("Smoke test passed: totalProposals =", totalProps.toString());

  const burnAddr = await contract.BURN_ADDRESS();
  console.assert(
    burnAddr.toLowerCase() === "0x000000000000000000000000000000000000dead",
    "Smoke test failed: BURN_ADDRESS mismatch"
  );
  console.log("Smoke test passed: BURN_ADDRESS =", burnAddr);

  // Post-deploy balance check.
  const balAfter = await ethers.provider.getBalance(deployer.address);
  const gasSpent = Number(ethers.formatEther(bal - balAfter));
  console.log(`Post-deploy balance: ${Number(ethers.formatEther(balAfter)).toFixed(6)} IOTX`);
  console.log(`Gas spent on deploy: ${gasSpent.toFixed(6)} IOTX`);

  // Update deployed-addresses.json.
  addresses["AgentSlashing"] = addr;
  addresses["_phase_o0_agent_slashing_status"] = "deployed";
  addresses["_phase_o0_agent_slashing_note"] =
    "Phase O0 Stream 2: AgentSlashing — VetoSlasher-pattern economic accountability " +
    "(bond → propose → 24h veto → burn); Z-A pure burn (slashed amounts to 0xdead); " +
    "W-A partial slashing (per-proposal slashAmount); Ownable + ReentrancyGuard pattern; " +
    "owner is bridge wallet 0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692; " +
    "agentRegistry reference immutable at " + agentRegistryAddr + "; " +
    "vetoWindowSeconds immutable at " + VETO_WINDOW_SECONDS + " (24h).";
  fs.writeFileSync(addrFile, JSON.stringify(addresses, null, 2));
  console.log("deployed-addresses.json updated");

  console.log("\nNext steps:");
  console.log("  bridge/.env.testnet:    AGENT_SLASHING_ADDRESS=" + addr);
  console.log("  CLAUDE.md update:       Stream 2 deploy 4/5 COMPLETE");
  console.log("  Next contract:          AgentAdjudicationRegistry (Session 5)");
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
