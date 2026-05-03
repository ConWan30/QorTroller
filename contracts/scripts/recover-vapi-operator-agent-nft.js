/**
 * Phase O0 Third Sitting Recovery — VAPIOperatorAgentNFT initialize + configureMinter
 *
 * One-off recovery script for partial deployment failure during third
 * sitting External Action A. Executes initialize and configureMinter
 * against the existing deployed contract at
 *   0xa0CDD2B3E292c56030185c66a3d423278A4c467b
 * with explicit gas limit overrides to work around the IoTeX testnet
 * gas-estimation underestimation for upgradeable contract initializers.
 *
 * IoTeX OOG quirk (per CLAUDE.md WIF-059 + Phase 237.5 Path C+ precedent):
 *   IoTeX testnet returns status 0x65 (decimal 101 — action-level error)
 *   on out-of-gas conditions. Original deploy script's initialize
 *   transaction was estimated at ~127K gas by Hardhat's automatic
 *   estimation; actual execution required more, hitting the OOG ceiling.
 *   OpenZeppelin ERC721Upgradeable + OwnableUpgradeable use namespaced
 *   storage per ERC-7201 with larger storage write costs than
 *   non-upgradeable variants — Hardhat's local-network-tuned estimator
 *   underestimates these on IoTeX testnet specifically.
 *
 * Three independent verification signals confirmed failure mode is
 * exactly "gas limit too low" (per Claude Code diagnosis):
 *   eth_call simulation of initialize() returned success (0x)
 *   Initializable storage slot reads 0x0 (no persistent state changes;
 *     previous tx fully reverted including the would-be _initialized=1)
 *   gas-used pattern matches IoTeX OOG signature (status 0x65, single
 *     Initialized event emitted before revert, gasUsed = limit)
 *
 * Recovery approach: explicit gasLimit overrides on the two failing
 * calls. 500000 for initialize (3.9x prior failed estimate at 127K);
 * 200000 for configureMinter (4x typical cost). Margins eliminate any
 * plausible IoTeX-specific cost amplification from triggering OOG.
 *
 * Additional fourth action: writes VAPIOperatorAgentNFT entry into
 * contracts/deployed-addresses.json. The original deploy script placed
 * the JSON write at end of main() after smoke tests; the configureMinter
 * failure aborted the script before the JSON write executed. Recovery
 * performs this first-write as part of completing the deployment.
 *
 * Cost: ~0.05 IOTX (initialize ~150K actual + configureMinter ~50K
 * actual; both with margin from 500K and 200K limits — unused gas is
 * NOT charged).
 *
 * Usage (one-off; do not re-run after success):
 *   npx hardhat run scripts/recover-vapi-operator-agent-nft.js --network iotex_testnet
 *
 * After successful recovery:
 *   contracts/deployed-addresses.json reflects the deployed address
 *   Contract is functionally identical to a clean deploy
 *   Phase O0 third sitting can resume at step_1_deploy_device_nft()
 *   Operator commits V8.3 constant update (External Action B) before
 *   step_2_update_constant_commit()
 *
 * Cross-references:
 *   contracts/scripts/deploy-vapi-operator-agent-nft.js (original deploy
 *     script at commit db9b4b97; failure mode captured in this recovery
 *     commit message)
 *   contracts/contracts/VAPIOperatorAgentNFT.sol (verbatim canonical
 *     DeviceNFT pattern + W2 __Ownable_init(msg.sender) adaptation)
 *   Pass 2C Section 14.4 Option β (canonical deviceContract architecture)
 *   CLAUDE.md WIF-059 + Phase 237.5 Path C+ (IoTeX OOG precedent)
 *
 * This recovery script is a permanent operational artifact preserved
 * for audit trail and future operational reference. Future deployments
 * use the updated deploy script per Artifact 2 (separate commit) which
 * applies the same gas-limit-override pattern at the canonical deploy
 * level.
 */

const { ethers } = require("hardhat");
const fs = require("fs");
const path = require("path");

const DEPLOYED_ADDRESS = "0xa0CDD2B3E292c56030185c66a3d423278A4c467b";
const VAPI_OPERATOR_AGENT_NFT_NAME = "VAPI Operator Agent NFT";
const VAPI_OPERATOR_AGENT_NFT_SYMBOL = "VOA";
const MINTER_ALLOWANCE = 2;

// Explicit gas limits (per IoTeX OOG quirk diagnosis — see header NatSpec)
const INITIALIZE_GAS_LIMIT = 500000;
const CONFIGURE_MINTER_GAS_LIMIT = 200000;

async function main() {
  const [deployer] = await ethers.getSigners();
  console.log("Recovering VAPIOperatorAgentNFT with deployer:", deployer.address);
  console.log("Target contract address:", DEPLOYED_ADDRESS);

  // 0. Pre-recovery verification: confirm contract is uninitialized
  const Factory = await ethers.getContractFactory("VAPIOperatorAgentNFT");
  const contract = Factory.attach(DEPLOYED_ADDRESS);

  const ownerBefore = await contract.owner();
  if (ownerBefore !== ethers.ZeroAddress) {
    throw new Error(
      `Contract already initialized: owner=${ownerBefore} (expected zero address). ` +
      `If this is a re-run after partial recovery, inspect state manually before proceeding.`
    );
  }
  console.log("Pre-recovery owner check: 0x0 (uninitialized as expected)");

  // 1. initialize() with explicit gas limit override
  console.log("\nStep 1: initialize() with gasLimit=" + INITIALIZE_GAS_LIMIT);
  const initTx = await contract.initialize(
    VAPI_OPERATOR_AGENT_NFT_NAME,
    VAPI_OPERATOR_AGENT_NFT_SYMBOL,
    { gasLimit: INITIALIZE_GAS_LIMIT },
  );
  console.log("  initialize tx submitted:", initTx.hash);
  const initReceipt = await initTx.wait();
  if (initReceipt.status !== 1) {
    throw new Error(
      `initialize reverted: status=${initReceipt.status} ` +
      `(expected 1). tx=${initTx.hash} block=${initReceipt.blockNumber} ` +
      `gasUsed=${initReceipt.gasUsed}. Inspect on testnet explorer: ` +
      `https://testnet.iotexscan.io/tx/${initTx.hash}`
    );
  }
  console.log("  initialize confirmed: block=" + initReceipt.blockNumber +
              " gasUsed=" + initReceipt.gasUsed.toString() +
              " status=" + initReceipt.status);

  // 2. configureMinter() with explicit gas limit override
  console.log("\nStep 2: configureMinter(" + deployer.address + ", " +
              MINTER_ALLOWANCE + ") with gasLimit=" + CONFIGURE_MINTER_GAS_LIMIT);
  const configTx = await contract.configureMinter(
    deployer.address,
    MINTER_ALLOWANCE,
    { gasLimit: CONFIGURE_MINTER_GAS_LIMIT },
  );
  console.log("  configureMinter tx submitted:", configTx.hash);
  const configReceipt = await configTx.wait();
  if (configReceipt.status !== 1) {
    throw new Error(
      `configureMinter reverted: status=${configReceipt.status} ` +
      `(expected 1). tx=${configTx.hash} block=${configReceipt.blockNumber} ` +
      `gasUsed=${configReceipt.gasUsed}. Inspect on testnet explorer: ` +
      `https://testnet.iotexscan.io/tx/${configTx.hash}`
    );
  }
  console.log("  configureMinter confirmed: block=" + configReceipt.blockNumber +
              " gasUsed=" + configReceipt.gasUsed.toString() +
              " status=" + configReceipt.status);

  // 3. Smoke tests — verify state via view calls
  console.log("\nStep 3: Smoke tests");
  const owner = await contract.owner();
  if (owner !== deployer.address) {
    throw new Error(`Smoke test failed: owner=${owner} (expected ${deployer.address})`);
  }
  console.log("  Smoke test passed: owner =", owner);

  const total = await contract.total();
  if (total !== 0n) {
    throw new Error(`Smoke test failed: total=${total} (expected 0)`);
  }
  console.log("  Smoke test passed: total =", total.toString());

  const isMinter = await contract.isMinter(deployer.address);
  if (isMinter !== true) {
    throw new Error(`Smoke test failed: isMinter(deployer)=${isMinter} (expected true)`);
  }
  console.log("  Smoke test passed: isMinter(deployer) =", isMinter);

  const allowance = await contract.minterAllowance(deployer.address);
  if (allowance !== BigInt(MINTER_ALLOWANCE)) {
    throw new Error(
      `Smoke test failed: minterAllowance=${allowance} (expected ${MINTER_ALLOWANCE})`
    );
  }
  console.log("  Smoke test passed: minterAllowance =", allowance.toString());

  // 4. Write deployed address to contracts/deployed-addresses.json
  // (First-write — original deploy script's JSON write at end of main()
  //  never executed because configureMinter failure aborted the script
  //  before reaching it. Recovery completes this step as part of the
  //  partial-failure recovery flow.)
  console.log("\nStep 4: Update contracts/deployed-addresses.json");
  const addressesPath = path.join(__dirname, "..", "deployed-addresses.json");
  const addresses = JSON.parse(fs.readFileSync(addressesPath, "utf-8"));
  const previousValue = addresses["VAPIOperatorAgentNFT"];
  addresses["VAPIOperatorAgentNFT"] = DEPLOYED_ADDRESS;
  fs.writeFileSync(addressesPath, JSON.stringify(addresses, null, 2));
  console.log("  deployed-addresses.json updated:");
  console.log("    previous: " + previousValue);
  console.log("    current:  " + DEPLOYED_ADDRESS);

  // Summary
  console.log("\n=== Recovery complete ===");
  console.log("VAPIOperatorAgentNFT at " + DEPLOYED_ADDRESS + " is now functionally");
  console.log("identical to a clean deploy. Contract is canonical deviceContract");
  console.log("per Pass 2C Section 14.4 Option β.");
  console.log("");
  console.log("Recovery transactions:");
  console.log("  initialize:      " + initTx.hash);
  console.log("  configureMinter: " + configTx.hash);
  console.log("");
  console.log("Next operator action: V8.3 constant update commit (External Action B)");
  console.log("  Edit bridge/vapi_bridge/agent_registration.py:");
  console.log("    VAPI_OPERATOR_AGENT_NFT_ADDR = \"" + DEPLOYED_ADDRESS + "\"");
  console.log("  Commit + push, then resume third sitting at step_1.");
  console.log("");
}

main()
  .then(() => process.exit(0))
  .catch((error) => {
    console.error("\n=== Recovery FAILED ===");
    console.error(error);
    console.error("\nHALT — operator decision required. Do not retry without operator approval.");
    console.error("Recovery from recovery failure requires Option B (full redeploy with ");
    console.error("Artifact 2 deploy script) or operator decision.");
    process.exit(1);
  });
