/**
 * Phase O0 Section 6.4 Block B — Deploy VAPIOperatorAgentNFT
 *
 * Deploys the custom DeviceNFT contract for the VAPI Operator Agents
 * project per Pass 2C Section 14.4 Option β canonical resolution.
 * After deployment, calls initialize() and configureMinter() to grant
 * the bridge wallet allowance to mint two device NFTs (one per operator
 * agent: anchor-sentry → tokenId 1; guardian → tokenId 2).
 *
 * Empirical gas baselines from third sitting External Action A + recovery
 * (commit fef267e9). Future operators reference these baselines for cost
 * estimation rather than Hardhat estimates which underestimate actual
 * IoTeX testnet consumption by approximately 3-4x for upgradeable
 * contract operations:
 *   Deploy upgradeable contract:    ~2.17 IOTX (~2,165,909 gas at 1000 gwei)
 *   Initialize upgradeable contract: ~0.13 IOTX (~126,053 gas at 1000 gwei)
 *   configureMinter:                 ~0.07 IOTX (~65,216 gas at 1000 gwei)
 *   Total deployment cost:          ~2.37 IOTX
 *   Plus margin for any IoTeX-specific cost amplification:  ~3.0 IOTX
 *
 * Empirical findings preserved as permanent corrections in this script:
 *
 *   Finding 1 (gas estimation underestimation): Hardhat automatic gas
 *   estimation for upgradeable contract initializer underestimated
 *   actual gas need on IoTeX testnet — Hardhat estimated ~127K gas;
 *   actual need was 126K with overhead pushing past the chosen limit.
 *   OpenZeppelin ERC721Upgradeable + OwnableUpgradeable use namespaced
 *   storage per ERC-7201 with larger storage write costs than
 *   non-upgradeable variants. Fix: explicit gasLimit overrides on
 *   initialize (500000) and configureMinter (200000). See WIF-059
 *   and Phase 237.5 Path C+ for IoTeX OOG (status 0x65) precedent.
 *
 *   Finding 2 (receipt status checking): Original script called
 *   tx.wait() and proceeded without checking receipt.status. When
 *   initialize reverted in External Action A, tx.wait() returned a
 *   receipt (the tx was mined; just reverted) and the script proceeded
 *   to configureMinter where pre-flight estimateGas aborted on
 *   owner=0x0 condition. The script crashed with ProviderError but
 *   the actual cause (initialize revert) was opaque without diagnostic
 *   work. Fix: explicit receipt.status !== 1n checks after each
 *   tx.wait() call (deploy + initialize + configureMinter). On failure:
 *   throw with tx hash + explorer link + diagnostic context.
 *
 *   Finding 3 (cost estimation reliance on empirical observations):
 *   Initial recovery cost framing of 0.05 IOTX was approximately 4x
 *   lower than actual 0.19 IOTX because the framing relied on Hardhat
 *   estimation patterns. Future cost estimation references the
 *   empirical baselines documented in the NatSpec block above rather
 *   than Hardhat estimates.
 *
 * Wallet: 0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692 (third sitting
 *         start was 16.97 IOTX; ~3.0 IOTX safe budget per finding 3)
 *
 * Usage (run only when ready to deploy on testnet):
 *   npx hardhat run scripts/deploy-vapi-operator-agent-nft.js --network iotex_testnet
 *
 * Post-deploy:
 *   contracts/deployed-addresses.json updated automatically (VAPIOperatorAgentNFT key)
 *   bridge/vapi_bridge/agent_registration.py: update VAPI_OPERATOR_AGENT_NFT_ADDR
 *     constant from "0x0000...0000" placeholder to the deployed address per V8.3.
 *     Commit message documents the deployment transaction hash and address.
 *
 * Then operator-driven session executes the prerequisite chain (Section 14.5):
 *   ProjectRegistry.register("VAPI Operator Agents", 0)
 *   ioIDStore.setDeviceContract(projectTokenId, deployedDeviceNFTAddress)
 *   (optional) ioIDStore.applyIoIDs(projectTokenId, 2) {value: 0.2 IOTX}
 *
 * Cross-references:
 *   Pass 2C Section 14.4 (Option β canonical resolution)
 *   Pass 2C Section 14.5 (ioIDStore prerequisite chain)
 *   contracts/contracts/VAPIOperatorAgentNFT.sol (this contract source)
 */

const { ethers } = require("hardhat");
const fs = require("fs");
const path = require("path");

const VAPI_OPERATOR_AGENT_NFT_NAME = "VAPI Operator Agent NFT";
const VAPI_OPERATOR_AGENT_NFT_SYMBOL = "VOA";
const MINTER_ALLOWANCE = 2;  // Sentry + Guardian — one device tokenId per agent

async function main() {
  const [deployer] = await ethers.getSigners();
  console.log("Deploying VAPIOperatorAgentNFT with:", deployer.address);

  // 1. Deploy the contract (no constructor args; uses initialize pattern)
  const Factory = await ethers.getContractFactory("VAPIOperatorAgentNFT");
  const contract = await Factory.deploy();
  await contract.waitForDeployment();
  const addr = await contract.getAddress();
  console.log("VAPIOperatorAgentNFT deployed to:", addr);
  const deployTx = contract.deploymentTransaction();
  console.log("  deploy tx:", deployTx ? deployTx.hash : "<unknown>");

  // Finding 2: explicit receipt status check after deployment.
  // Halts on first failure with diagnostic info rather than cascading
  // to subsequent operations. See header NatSpec for failure-mode context.
  if (deployTx) {
    const deployReceipt = await deployTx.wait();
    if (deployReceipt.status !== 1n) {
      throw new Error(
        `Deploy reverted: status=${deployReceipt.status} (expected 1n). ` +
        `tx=${deployTx.hash} block=${deployReceipt.blockNumber} ` +
        `gasUsed=${deployReceipt.gasUsed}. Explorer: ` +
        `https://testnet.iotexscan.io/tx/${deployTx.hash}`
      );
    }
    console.log(
      "  deploy confirmed: block=" + deployReceipt.blockNumber +
      " gasUsed=" + deployReceipt.gasUsed.toString() +
      " status=" + deployReceipt.status,
    );
  }

  // 2. Initialize the contract (sets name, symbol, Ownable owner = deployer)
  // Finding 1: explicit gasLimit override per IoTeX OOG quirk.
  // Hardhat's automatic gas estimation underestimates upgradeable contract
  // initializer gas need on IoTeX testnet (estimated ~127K vs actual 126K
  // with overhead pushing past the chosen limit during execution).
  // 500000 gives 3.9x margin. See WIF-059 + Phase 237.5 Path C+ for
  // IoTeX OOG (status 0x65) precedent. Also see recovery commit fef267e9
  // for the empirical finding that motivated this fix.
  const initTx = await contract.initialize(
    VAPI_OPERATOR_AGENT_NFT_NAME,
    VAPI_OPERATOR_AGENT_NFT_SYMBOL,
    { gasLimit: 500000 },
  );
  console.log("initialize tx submitted:", initTx.hash);
  // Finding 2: explicit receipt status check.
  const initReceipt = await initTx.wait();
  if (initReceipt.status !== 1n) {
    throw new Error(
      `initialize reverted: status=${initReceipt.status} (expected 1n). ` +
      `tx=${initTx.hash} block=${initReceipt.blockNumber} ` +
      `gasUsed=${initReceipt.gasUsed}. Explorer: ` +
      `https://testnet.iotexscan.io/tx/${initTx.hash}. ` +
      `If status=0x65 (IoTeX OOG), increase gasLimit beyond 500000.`
    );
  }
  console.log(
    "  initialize confirmed: block=" + initReceipt.blockNumber +
    " gasUsed=" + initReceipt.gasUsed.toString() +
    " status=" + initReceipt.status,
  );

  // 3. Configure bridge wallet (deployer) as minter with allowance for 2 NFTs
  // Finding 1: explicit gasLimit override per IoTeX OOG quirk (same
  // rationale as initialize call above). 200000 gives 4x margin against
  // typical configureMinter cost (~50-65K). See header NatSpec.
  const configTx = await contract.configureMinter(
    deployer.address,
    MINTER_ALLOWANCE,
    { gasLimit: 200000 },
  );
  console.log("configureMinter tx submitted:", configTx.hash);
  // Finding 2: explicit receipt status check.
  const configReceipt = await configTx.wait();
  if (configReceipt.status !== 1n) {
    throw new Error(
      `configureMinter reverted: status=${configReceipt.status} (expected 1n). ` +
      `tx=${configTx.hash} block=${configReceipt.blockNumber} ` +
      `gasUsed=${configReceipt.gasUsed}. Explorer: ` +
      `https://testnet.iotexscan.io/tx/${configTx.hash}. ` +
      `If owner is 0x0, the prior initialize call did not complete; ` +
      `inspect that tx receipt for the actual failure cause.`
    );
  }
  console.log(
    "  configureMinter confirmed: block=" + configReceipt.blockNumber +
    " gasUsed=" + configReceipt.gasUsed.toString() +
    " status=" + configReceipt.status,
  );
  console.log("  minter:", deployer.address, "allowance:", MINTER_ALLOWANCE);

  // 4. Smoke tests — verify state via view calls
  const owner = await contract.owner();
  console.assert(owner === deployer.address, "Smoke test failed: owner mismatch");
  console.log("Smoke test passed: owner =", owner);

  const total = await contract.total();
  console.assert(total === 0n, "Smoke test failed: total should be 0 pre-mint");
  console.log("Smoke test passed: total =", total.toString());

  const isMinter = await contract.isMinter(deployer.address);
  console.assert(isMinter === true, "Smoke test failed: deployer not configured as minter");
  console.log("Smoke test passed: isMinter(deployer) =", isMinter);

  const allowance = await contract.minterAllowance(deployer.address);
  console.assert(allowance === BigInt(MINTER_ALLOWANCE), "Smoke test failed: minterAllowance mismatch");
  console.log("Smoke test passed: minterAllowance =", allowance.toString());

  // 5. Update deployed-addresses.json
  const addressesPath = path.join(__dirname, "..", "deployed-addresses.json");
  let addresses = {};
  if (fs.existsSync(addressesPath)) {
    addresses = JSON.parse(fs.readFileSync(addressesPath, "utf-8"));
  }
  addresses["VAPIOperatorAgentNFT"] = addr;
  if (!addresses["_descriptions"]) addresses["_descriptions"] = {};
  addresses["_descriptions"]["VAPIOperatorAgentNFT"] = (
    "Phase O0 Section 6.4 Block B — Custom DeviceNFT contract for VAPI Operator Agents project. " +
    "Verbatim copy of canonical examples/DeviceNFT.sol from ioID-contracts at commit b94ad092. " +
    "Per N2 β: registered with ioIDStore.setDeviceContract as the deviceContract for the " +
    "VAPI Operator Agents project (one IProject tokenId). Per-agent device tokenIds " +
    "(anchor-sentry → 1, guardian → 2) are consumed by ioIDRegistry.register."
  );
  fs.writeFileSync(addressesPath, JSON.stringify(addresses, null, 2));
  console.log("Wrote deployed address to:", addressesPath);

  console.log("");
  console.log("Next steps (per Pass 2C Section 14.5 prerequisite chain):");
  console.log("  1. Update bridge/vapi_bridge/agent_registration.py per V8.3:");
  console.log("       VAPI_OPERATOR_AGENT_NFT_ADDR = \"" + addr + "\"");
  console.log("  2. Operator-driven session: ProjectRegistry.register(\"VAPI Operator Agents\", 0)");
  console.log("  3. Operator-driven session: ioIDStore.setDeviceContract(projectTokenId, " + addr + ")");
  console.log("  4. (Optional) ioIDStore.applyIoIDs(projectTokenId, 2) {value: 0.2 IOTX} pre-pay");
  console.log("");
}

main()
  .then(() => process.exit(0))
  .catch((error) => {
    console.error(error);
    process.exit(1);
  });
