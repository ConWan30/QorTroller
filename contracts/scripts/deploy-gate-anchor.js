/**
 * Phase 84 — Deploy GateAttestationAnchor
 *
 * First on-chain proof registry for autonomous AI fleet self-calibration gates.
 * attestation_hash = SHA-256(consecutive_clean || gate_n || divergence_rate || timestamp_ns)
 * Anti-replay: each attestation_hash recorded at most once.
 *
 * Prerequisites:
 *   1. Ensure wallet has sufficient IOTX (wallet: 0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692)
 *   2. Set BRIDGE_PRIVATE_KEY in contracts/.env
 *
 * Usage:
 *   cd contracts && npx hardhat run scripts/deploy-gate-anchor.js --network iotex_testnet
 *
 * Outputs:
 *   bridge/.env.phase84  -- GATE_ATTESTATION_ANCHOR_ADDRESS=<addr>
 *   contracts/deployed-addresses.json  -- GateAttestationAnchor updated
 */

const { ethers } = require("hardhat");
const fs = require("fs"), path = require("path");

async function main() {
    const [deployer] = await ethers.getSigners();
    console.log("Deployer:", deployer.address);
    const balance = await ethers.provider.getBalance(deployer.address);
    console.log("Balance:", ethers.formatEther(balance), "IOTX");

    // Deploy GateAttestationAnchor with deployer as operator
    const Factory = await ethers.getContractFactory("GateAttestationAnchor");
    const anchor = await Factory.deploy(deployer.address);
    await anchor.waitForDeployment();
    const addr = await anchor.getAddress();
    console.log("GateAttestationAnchor deployed:", addr);

    // Sanity check — operator matches deployer
    const operatorOnChain = await anchor.operator();
    if (operatorOnChain.toLowerCase() !== deployer.address.toLowerCase()) {
        throw new Error(`Operator mismatch: expected ${deployer.address}, got ${operatorOnChain}`);
    }
    console.log("Operator verified:", operatorOnChain);
    console.log("Attestation count (initial):", await anchor.getAttestationCount());

    // Write to bridge/.env.phase84
    const envPath = path.join(__dirname, "../../bridge/.env.phase84");
    fs.writeFileSync(envPath,
        `# Phase 84 — GateAttestationAnchor on IoTeX testnet\n` +
        `GATE_ATTESTATION_ANCHOR_ADDRESS=${addr}\n`
    );
    console.log("Written to:", envPath);

    // Update deployed-addresses.json
    const addrsPath = path.join(__dirname, "../deployed-addresses.json");
    let addrs = {};
    try { addrs = JSON.parse(fs.readFileSync(addrsPath, "utf8")); } catch {}
    addrs.GateAttestationAnchor = addr;
    fs.writeFileSync(addrsPath, JSON.stringify(addrs, null, 2));
    console.log("deployed-addresses.json updated.");
    console.log("\nPhase 84 deployment complete.");
    console.log("Add to bridge/.env: GATE_ATTESTATION_ANCHOR_ADDRESS=" + addr);
}

main().catch(e => { console.error(e); process.exit(1); });
