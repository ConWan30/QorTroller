/**
 * Phase 99A — Deploy VAPIToken + VAPIOperatorRegistry + VAPIHardwareCertRegistry
 *
 * AGaaS Foundation token stack. Deploys to IoTeX testnet ONLY in Phase 99.
 * No TGE in Phase 99 — token launch gated after separation ratio > 1.0 confirmed.
 *
 * Deploy order:
 *   1. VAPIToken (ERC20Pausable, 1B max supply)
 *   2. VAPIOperatorRegistry (staking + slashing, token address required)
 *   3. VAPIHardwareCertRegistry (hardware cert, token address required)
 *
 * W1 invariant: never call completeTGE() on this deploy in tests.
 * Tests must use fresh VAPIToken per describe block (beforeEach deploy).
 *
 * W2 note: VAPIHardwareCertRegistry.isCertified() is pure view — composable
 * as a hardware gate in any tournament contract via single eth_call.
 *
 * Prerequisites:
 *   contracts/.env must have BRIDGE_PRIVATE_KEY set
 *   Wallet: 0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692 (~11 IOTX available)
 *   Estimated cost: ~0.15 IOTX for 3 contracts
 *
 * Usage:
 *   cd contracts && npx hardhat run scripts/deploy-phase99a.js --network iotex_testnet
 *
 * Outputs:
 *   bridge/.env.phase99a  -- 3 new address vars
 *   contracts/deployed-addresses.json  -- VAPIToken, VAPIOperatorRegistry, VAPIHardwareCertRegistry
 */

const { ethers } = require("hardhat");
const fs = require("fs"), path = require("path");

async function main() {
    const [deployer] = await ethers.getSigners();
    console.log("Deployer:", deployer.address);
    const balance = await ethers.provider.getBalance(deployer.address);
    console.log("Balance:", ethers.formatEther(balance), "IOTX");

    if (ethers.formatEther(balance) < 0.1) {
        throw new Error("Insufficient balance — need at least 0.1 IOTX for 3 contracts");
    }

    // 1. Deploy VAPIToken
    console.log("\n[1/3] Deploying VAPIToken...");
    const TokenFactory = await ethers.getContractFactory("VAPIToken");
    const token = await TokenFactory.deploy(deployer.address);
    await token.waitForDeployment();
    const tokenAddr = await token.getAddress();
    console.log("VAPIToken deployed:", tokenAddr);

    // Sanity check
    const maxSupply = await token.MAX_SUPPLY();
    const expected = ethers.parseEther("1000000000"); // 1B
    if (maxSupply !== expected) {
        throw new Error(`MAX_SUPPLY mismatch: ${maxSupply} != ${expected}`);
    }
    const tgeComplete = await token.tgeComplete();
    if (tgeComplete) {
        throw new Error("VAPIToken: tgeComplete should be false on deploy");
    }
    console.log("MAX_SUPPLY verified: 1,000,000,000 VAPI");
    console.log("tgeComplete:", tgeComplete, "(expected false)");

    // 2. Deploy VAPIOperatorRegistry
    console.log("\n[2/3] Deploying VAPIOperatorRegistry...");
    const RegistryFactory = await ethers.getContractFactory("VAPIOperatorRegistry");
    const registry = await RegistryFactory.deploy(tokenAddr, deployer.address);
    await registry.waitForDeployment();
    const registryAddr = await registry.getAddress();
    console.log("VAPIOperatorRegistry deployed:", registryAddr);

    // Sanity check
    const minStake = await registry.MINIMUM_STAKE();
    console.log("MINIMUM_STAKE:", ethers.formatEther(minStake), "VAPI (expected 10000)");
    const cooldown = await registry.DEREGISTER_COOLDOWN();
    console.log("DEREGISTER_COOLDOWN:", Number(cooldown) / 86400, "days (expected 30)");

    // 3. Deploy VAPIHardwareCertRegistry (fee=0 for testnet)
    console.log("\n[3/3] Deploying VAPIHardwareCertRegistry...");
    const CertFactory = await ethers.getContractFactory("VAPIHardwareCertRegistry");
    const certFee = 0n; // free certification on testnet
    const certRegistry = await CertFactory.deploy(tokenAddr, deployer.address, certFee);
    await certRegistry.waitForDeployment();
    const certAddr = await certRegistry.getAddress();
    console.log("VAPIHardwareCertRegistry deployed:", certAddr);

    // Sanity check — certify DualShock Edge as Level 1 reference hardware
    const profileHash = ethers.keccak256(
        ethers.toUtf8Bytes("Sony:DualShock Edge CFI-ZCP1:01.04.00")
    );
    const certTx = await certRegistry.certifyHardware(
        profileHash,
        1,
        "Sony",
        "DualShock Edge CFI-ZCP1",
        "01.04.00"
    );
    await certTx.wait();
    const isCert = await certRegistry.isCertified(profileHash);
    if (!isCert) {
        throw new Error("VAPIHardwareCertRegistry: reference hardware certification failed");
    }
    console.log("Reference hardware (DualShock Edge) certified:", profileHash);
    console.log("isCertified() verified: true");

    // Write bridge env file
    const envContent =
        `# Phase 99A — AGaaS Foundation Token Stack (IoTeX testnet)\n` +
        `VAPI_TOKEN_ADDRESS=${tokenAddr}\n` +
        `OPERATOR_REGISTRY_ADDRESS=${registryAddr}\n` +
        `HARDWARE_CERT_REGISTRY_ADDRESS=${certAddr}\n`;

    const envPath = path.join(__dirname, "../../bridge/.env.phase99a");
    fs.writeFileSync(envPath, envContent);
    console.log("\nWritten:", envPath);

    // Update deployed-addresses.json
    const addrsPath = path.join(__dirname, "../deployed-addresses.json");
    let addrs = {};
    try { addrs = JSON.parse(fs.readFileSync(addrsPath, "utf8")); } catch {}
    addrs.VAPIToken = tokenAddr;
    addrs.VAPIOperatorRegistry = registryAddr;
    addrs.VAPIHardwareCertRegistry = certAddr;
    addrs._phase99a_note = "Phase 99A: AGaaS Foundation Token Stack — testnet ONLY, no TGE";
    addrs._phase99a_status = "LIVE (testnet)";
    fs.writeFileSync(addrsPath, JSON.stringify(addrs, null, 2));
    console.log("deployed-addresses.json updated (35 contracts).");

    const postBalance = await ethers.provider.getBalance(deployer.address);
    const spent = balance - postBalance;
    console.log("\n=== Phase 99A Deployment Summary ===");
    console.log("VAPIToken:              ", tokenAddr);
    console.log("VAPIOperatorRegistry:   ", registryAddr);
    console.log("VAPIHardwareCertRegistry:", certAddr);
    console.log("IOTX spent:             ", ethers.formatEther(spent));
    console.log("IOTX remaining:         ", ethers.formatEther(postBalance));
    console.log("\nNext: add to bridge/.env.testnet:");
    console.log("  VAPI_TOKEN_ADDRESS=" + tokenAddr);
    console.log("  OPERATOR_REGISTRY_ADDRESS=" + registryAddr);
    console.log("  HARDWARE_CERT_REGISTRY_ADDRESS=" + certAddr);
}

main().catch(e => { console.error(e); process.exit(1); });
