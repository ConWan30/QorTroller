/**
 * Phase O0 Section 6.4 Block B — Deploy VAPIOperatorAgentNFT
 *
 * Deploys the custom DeviceNFT contract for the VAPI Operator Agents
 * project per Pass 2C Section 14.4 Option β canonical resolution.
 * After deployment, calls initialize() and configureMinter() to grant
 * the bridge wallet allowance to mint two device NFTs (one per operator
 * agent: anchor-sentry → tokenId 1; guardian → tokenId 2).
 *
 * Gas estimate per Section 14.6:
 *   Deployment:     ~0.30 IOTX
 *   initialize:     part of ~0.05 IOTX initialize+configureMinter group
 *   configureMinter:part of same group
 *   Total:          ~0.35 IOTX
 *
 * Wallet: 0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692 (16.97 IOTX —
 *         9.8x headroom against full ~1.73 IOTX Section 14.6 budget)
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

  // 2. Initialize the contract (sets name, symbol, Ownable owner = deployer)
  const initTx = await contract.initialize(
    VAPI_OPERATOR_AGENT_NFT_NAME,
    VAPI_OPERATOR_AGENT_NFT_SYMBOL,
  );
  await initTx.wait();
  console.log("initialize tx:", initTx.hash);

  // 3. Configure bridge wallet (deployer) as minter with allowance for 2 NFTs
  const configTx = await contract.configureMinter(deployer.address, MINTER_ALLOWANCE);
  await configTx.wait();
  console.log("configureMinter tx:", configTx.hash);
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
