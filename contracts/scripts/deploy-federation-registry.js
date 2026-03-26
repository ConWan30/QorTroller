/**
 * Phase 80 — Deploy FederatedThreatRegistry
 *
 * FederatedThreatRegistry stores cross-bridge BLOCK ruling threat signals on-chain.
 * isThreatSignaled(deviceId) is a pure view callable by any tournament gate contract.
 * Anti-replay: duplicate commitHash is rejected by the active-flag check.
 *
 * Prerequisites:
 *   1. Ensure wallet has sufficient IOTX (wallet: 0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692)
 *   2. Set BRIDGE_PRIVATE_KEY in contracts/.env
 *
 * Usage:
 *   cd contracts && npx hardhat run scripts/deploy-federation-registry.js --network iotex_testnet
 *
 * Outputs:
 *   bridge/.env.phase80  -- FEDERATION_REGISTRY_ADDRESS=<addr>
 *   contracts/deployed-addresses.json  -- FederatedThreatRegistry updated
 */

const { ethers } = require("hardhat");
const fs = require("fs"), path = require("path");

async function main() {
    const [deployer] = await ethers.getSigners();
    console.log("Deployer:", deployer.address);
    const balance = await ethers.provider.getBalance(deployer.address);
    console.log("Balance:", ethers.formatEther(balance), "IOTX");

    // Deploy FederatedThreatRegistry with deployer as operator
    const Factory = await ethers.getContractFactory("FederatedThreatRegistry");
    const registry = await Factory.deploy(deployer.address);
    await registry.waitForDeployment();

    const addr = await registry.getAddress();
    console.log("FederatedThreatRegistry deployed to:", addr);
    console.log("Operator:", await registry.operator());

    // Write bridge/.env.phase80
    const envPath = path.join(__dirname, "../../bridge/.env.phase80");
    fs.writeFileSync(envPath,
        `# Phase 80 — FederatedThreatRegistry\n` +
        `FEDERATION_REGISTRY_ADDRESS=${addr}\n`
    );
    console.log("Wrote", envPath);

    // Update deployed-addresses.json
    const addrPath = path.join(__dirname, "../deployed-addresses.json");
    let existing = {};
    if (fs.existsSync(addrPath)) {
        existing = JSON.parse(fs.readFileSync(addrPath, "utf8"));
    }
    existing["FederatedThreatRegistry"] = {
        address: addr,
        network: "iotex_testnet",
        deployer: deployer.address,
        phase: 80,
        note: "Phase 80 — per-ruling threat signals; isThreatSignaled() tournament gate composability"
    };
    fs.writeFileSync(addrPath, JSON.stringify(existing, null, 2));
    console.log("Updated deployed-addresses.json");

    console.log("\n=== Phase 80 FederatedThreatRegistry Deploy Complete ===");
    console.log("FEDERATION_REGISTRY_ADDRESS=" + addr);
    console.log("Add to bridge/.env.testnet:\n  FEDERATION_REGISTRY_ADDRESS=" + addr);
}

main().catch((e) => { console.error(e); process.exit(1); });
