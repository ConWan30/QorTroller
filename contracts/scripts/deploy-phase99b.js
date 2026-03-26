/**
 * Phase 99B — Deploy VAPIGSRRegistry
 *
 * On-chain anchor for GSR biometric samples from the W3bstream pipeline.
 * GSR_ENABLED=false in bridge until N≥30 real calibration sessions per player.
 * process_gsr_packet.ts WASM applet calls recordSample() on each GSR packet.
 *
 * Prerequisites:
 *   Phase 99A contracts already deployed (VAPIToken, VAPIOperatorRegistry, VAPIHardwareCertRegistry)
 *   contracts/.env must have BRIDGE_PRIVATE_KEY set
 *   Wallet: 0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692
 *   Estimated cost: ~0.05 IOTX
 *
 * Usage:
 *   cd contracts && npx hardhat run scripts/deploy-phase99b.js --network iotex_testnet
 *
 * Outputs:
 *   bridge/.env.phase99b  -- GSR_REGISTRY_ADDRESS var
 *   contracts/deployed-addresses.json  -- VAPIGSRRegistry updated
 */

const { ethers } = require("hardhat");
const fs = require("fs"), path = require("path");

async function main() {
    const [deployer] = await ethers.getSigners();
    console.log("Deployer:", deployer.address);
    const balance = await ethers.provider.getBalance(deployer.address);
    console.log("Balance:", ethers.formatEther(balance), "IOTX");

    // Deploy VAPIGSRRegistry
    console.log("\nDeploying VAPIGSRRegistry...");
    const Factory = await ethers.getContractFactory("VAPIGSRRegistry");
    const registry = await Factory.deploy(deployer.address);
    await registry.waitForDeployment();
    const addr = await registry.getAddress();
    console.log("VAPIGSRRegistry deployed:", addr);

    // Sanity check: record a test sample
    const testDeviceId = ethers.keccak256(ethers.toUtf8Bytes("deploy_sanity_check"));
    const testTs = Math.floor(Date.now() / 1000);
    const tx = await registry.recordSample(testDeviceId, 450n, 650n, BigInt(testTs));
    await tx.wait();
    const count = await registry.getSampleCount(testDeviceId);
    if (count !== 1n) {
        throw new Error(`GSRRegistry sanity check failed: expected count=1, got ${count}`);
    }
    console.log("Sanity check: recordSample + getSampleCount=1 verified");

    // Write env file
    const envPath = path.join(__dirname, "../../bridge/.env.phase99b");
    fs.writeFileSync(envPath,
        `# Phase 99B — VAPIGSRRegistry on IoTeX testnet\n` +
        `GSR_REGISTRY_ADDRESS=${addr}\n` +
        `# GSR_ENABLED=false (default) until N>=30 real calibration sessions per player\n`
    );
    console.log("Written:", envPath);

    // Update deployed-addresses.json
    const addrsPath = path.join(__dirname, "../deployed-addresses.json");
    let addrs = {};
    try { addrs = JSON.parse(fs.readFileSync(addrsPath, "utf8")); } catch {}
    addrs.VAPIGSRRegistry = addr;
    addrs._phase99b_note = "Phase 99B: VAPIGSRRegistry — GSR_ENABLED=false default, advisory layer";
    addrs._phase99b_status = "LIVE (testnet)";
    fs.writeFileSync(addrsPath, JSON.stringify(addrs, null, 2));
    console.log("deployed-addresses.json updated (36 contracts).");

    const postBalance = await ethers.provider.getBalance(deployer.address);
    const spent = balance - postBalance;
    console.log("\n=== Phase 99B Deployment Summary ===");
    console.log("VAPIGSRRegistry:", addr);
    console.log("IOTX spent:     ", ethers.formatEther(spent));
    console.log("IOTX remaining: ", ethers.formatEther(postBalance));
    console.log("\nAdd to bridge/.env.testnet:");
    console.log("  GSR_REGISTRY_ADDRESS=" + addr);
    console.log("  # GSR_ENABLED=false (default)");
}

main().catch(e => { console.error(e); process.exit(1); });
