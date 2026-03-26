/**
 * Phase 66 — Deploy RulingRegistry
 *
 * RulingRegistry stores autonomous agent ruling commitment_hashes on-chain.
 * commitment_hash = SHA-256(verdict + sorted(evidence_hashes) + attestation_hash + ts_ns)
 * Anti-replay: each commitment_hash may only be recorded once.
 *
 * Prerequisites:
 *   1. Ensure wallet has sufficient IOTX (wallet: 0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692)
 *   2. Set BRIDGE_PRIVATE_KEY in contracts/.env
 *
 * Usage:
 *   cd contracts && npx hardhat run scripts/deploy-ruling-registry.js --network iotex_testnet
 *
 * Outputs:
 *   bridge/.env.phase66  -- RULING_REGISTRY_ADDRESS=<addr>
 *   contracts/deployed-addresses.json  -- RulingRegistry updated
 */

const { ethers } = require("hardhat");
const fs = require("fs"), path = require("path");

async function main() {
    const [deployer] = await ethers.getSigners();
    console.log("Deployer:", deployer.address);
    const balance = await ethers.provider.getBalance(deployer.address);
    console.log("Balance:", ethers.formatEther(balance), "IOTX");

    // Deploy RulingRegistry with deployer as operator
    const Factory = await ethers.getContractFactory("RulingRegistry");
    const registry = await Factory.deploy(deployer.address);
    await registry.waitForDeployment();
    const addr = await registry.getAddress();
    console.log("RulingRegistry deployed:", addr);

    // Sanity check — operator matches deployer
    const operatorOnChain = await registry.operator();
    if (operatorOnChain.toLowerCase() !== deployer.address.toLowerCase()) {
        throw new Error(`Operator mismatch: expected ${deployer.address}, got ${operatorOnChain}`);
    }
    console.log("Operator verified:", operatorOnChain);

    // Write to bridge/.env.phase66
    const envPath = path.join(__dirname, "../../bridge/.env.phase66");
    fs.writeFileSync(envPath,
        `# Phase 66 — RulingRegistry on IoTeX testnet\n` +
        `RULING_REGISTRY_ADDRESS=${addr}\n`
    );
    console.log("Written to:", envPath);

    // Update deployed-addresses.json
    const addrsPath = path.join(__dirname, "../deployed-addresses.json");
    let addrs = {};
    try { addrs = JSON.parse(fs.readFileSync(addrsPath, "utf8")); } catch {}
    addrs.RulingRegistry = addr;
    fs.writeFileSync(addrsPath, JSON.stringify(addrs, null, 2));
    console.log("deployed-addresses.json updated.");
    console.log("\nPhase 66 deployment complete.");
    console.log("Add to bridge/.env: RULING_REGISTRY_ADDRESS=" + addr);
}

main().catch(e => { console.error(e); process.exit(1); });
