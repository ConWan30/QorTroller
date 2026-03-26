/**
 * Phase 67 — Deploy CeremonyRegistry + Register All 3 VAPI Circuits
 *
 * Reads ceremony_artifacts/all_circuits_manifest.json produced by run-mpc-ceremony.js.
 * Deploys CeremonyRegistry.sol and calls registerCeremony() for each circuit.
 * Sanity-checks each registration via verifyCeremony().
 *
 * Prerequisites:
 *   1. Run: node scripts/run-mpc-ceremony.js   (produces ceremony_artifacts/)
 *   2. Ensure wallet has sufficient IOTX (~0.15 IOTX for deploy + 3 registerCeremony txs)
 *
 * Usage:
 *   cd contracts && npx hardhat run scripts/deploy-ceremony-registry.js --network iotex_testnet
 *
 * Outputs:
 *   bridge/.env.phase67   -- CEREMONY_REGISTRY_ADDRESS=<addr>
 *   contracts/deployed-addresses.json -- CeremonyRegistry updated
 */

const { ethers } = require("hardhat");
const fs   = require("fs");
const path = require("path");

async function main() {
    const [deployer] = await ethers.getSigners();
    console.log("Deployer:", deployer.address);
    const balance = await ethers.provider.getBalance(deployer.address);
    console.log("Balance:", ethers.formatEther(balance), "IOTX");

    // Load ceremony manifest
    const manifestPath = path.join(__dirname, "../ceremony_artifacts/all_circuits_manifest.json");
    if (!fs.existsSync(manifestPath)) {
        throw new Error(
            "ceremony_artifacts/all_circuits_manifest.json not found.\n" +
            "Run: node scripts/run-mpc-ceremony.js first."
        );
    }
    const manifests = JSON.parse(fs.readFileSync(manifestPath, "utf8"));
    console.log(`\nLoaded manifests for ${manifests.length} circuit(s):`,
        manifests.map(m => m.circuitName).join(", "));

    // Deploy CeremonyRegistry
    console.log("\nDeploying CeremonyRegistry...");
    const Factory  = await ethers.getContractFactory("CeremonyRegistry");
    const registry = await Factory.deploy(deployer.address);
    await registry.waitForDeployment();
    const addr = await registry.getAddress();
    console.log("CeremonyRegistry deployed:", addr);

    // Sanity check: operator matches deployer
    const operatorOnChain = await registry.operator();
    if (operatorOnChain.toLowerCase() !== deployer.address.toLowerCase()) {
        throw new Error(`Operator mismatch: expected ${deployer.address}, got ${operatorOnChain}`);
    }
    console.log("Operator verified:", operatorOnChain);

    // Register each circuit
    for (const m of manifests) {
        console.log(`\nRegistering ${m.circuitName}...`);
        console.log("  circuitId:        ", m.circuitId);
        console.log("  verifyingKeyHash: ", m.verifyingKeyHash);
        console.log("  beaconBlock:      ", m.beaconBlockNumber, "->", m.beaconBlockHash);
        console.log("  contributors:     ", m.contributorCount);

        const contributorHashesBytes32 = m.contributorHashes.map(h => {
            const clean = h.replace("0x", "").padStart(64, "0");
            return "0x" + clean;
        });

        const tx = await registry.registerCeremony(
            m.circuitId,
            m.verifyingKeyHash,
            m.beaconBlockHash.startsWith("0x") ? m.beaconBlockHash : "0x" + m.beaconBlockHash,
            m.beaconBlockNumber,
            contributorHashesBytes32,
            m.ptauSource,
        );
        const receipt = await tx.wait();
        console.log("  tx:", receipt.hash);

        // Sanity check via verifyCeremony()
        const valid = await registry.verifyCeremony(m.circuitId, m.verifyingKeyHash);
        if (!valid) {
            throw new Error(`verifyCeremony failed for ${m.circuitName}`);
        }
        console.log("  verifyCeremony(): OK");
    }

    // Write CEREMONY_REGISTRY_ADDRESS to bridge/.env.phase67
    const envPath = path.join(__dirname, "../../bridge/.env.phase67");
    const existing = fs.existsSync(envPath) ? fs.readFileSync(envPath, "utf8") : "";
    fs.writeFileSync(
        envPath,
        existing +
        `# Phase 67 — CeremonyRegistry on IoTeX testnet\n` +
        `CEREMONY_REGISTRY_ADDRESS=${addr}\n`,
    );
    console.log("\nWritten to:", envPath);

    // Update deployed-addresses.json
    const addrsPath = path.join(__dirname, "../deployed-addresses.json");
    let addrs = {};
    try { addrs = JSON.parse(fs.readFileSync(addrsPath, "utf8")); } catch {}
    addrs.CeremonyRegistry = addr;
    fs.writeFileSync(addrsPath, JSON.stringify(addrs, null, 2));
    console.log("deployed-addresses.json updated.");

    console.log("\n═══════════════════════════════════════════");
    console.log("Phase 67 CeremonyRegistry deployment complete.");
    console.log("Add to bridge/.env:");
    console.log("  CEREMONY_REGISTRY_ADDRESS=" + addr);
    console.log("\nNext: redeploy PitlSessionProofVerifierV2 with new MPC vkey:");
    console.log("  npx hardhat run scripts/deploy-pitl-registry-v2.js --network iotex_testnet");
}

main().catch(e => { console.error(e); process.exit(1); });
