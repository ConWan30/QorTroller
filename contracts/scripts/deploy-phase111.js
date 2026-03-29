// Deploy AdjudicationRegistry (Phase 111 — PoAd Registry)
// Append deployed address to deployed-addresses.json
// Gas estimate: ~0.04 IOTX on IoTeX testnet
const { ethers } = require("hardhat");
const fs = require("fs");

async function main() {
    const [deployer] = await ethers.getSigners();
    console.log("Deploying AdjudicationRegistry with:", deployer.address);
    const balance = await ethers.provider.getBalance(deployer.address);
    console.log("Deployer balance:", ethers.formatEther(balance), "IOTX");

    const AdjudicationRegistry = await ethers.getContractFactory("AdjudicationRegistry");
    const registry = await AdjudicationRegistry.deploy();
    await registry.waitForDeployment();

    const addr = await registry.getAddress();
    console.log("AdjudicationRegistry deployed to:", addr);

    // Append to deployed-addresses.json
    const addressesPath = "deployed-addresses.json";
    const addresses = JSON.parse(fs.readFileSync(addressesPath, "utf8"));
    addresses.AdjudicationRegistry = addr;
    addresses._phase111_status = "LIVE (testnet)";
    fs.writeFileSync(addressesPath, JSON.stringify(addresses, null, 2));
    console.log("deployed-addresses.json updated (39 contracts)");

    // Smoke test: isRecorded on zero hash should return false
    const zeroHash = ethers.ZeroHash;
    const recorded = await registry.isRecorded(zeroHash);
    console.log("Smoke test isRecorded(0x0):", recorded, "(expected: false)");
    if (recorded !== false) throw new Error("Smoke test failed");
    console.log("Phase 111 deployment complete.");
}

main().catch((e) => { console.error(e); process.exit(1); });
