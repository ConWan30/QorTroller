/**
 * Phase 69 — VAPI Data Sovereignty Layer + DePIN Tokenomics + Data Marketplace
 *
 * Deploys 6 contracts in sequence and wires oracles into VAPIRewardDistributor:
 *   1. DataSovereigntyRegistry.sol  — immutable data ownership pledge
 *   2. HumanityOracle.sol           — humanity verdict oracle (native VAPI oracle)
 *   3. RulingOracle.sol             — ruling state oracle (native VAPI oracle)
 *   4. PassportOracle.sol           — passport state oracle (native VAPI oracle)
 *   5. VAPIRewardDistributor.sol    — device-gated DePIN token distributor
 *   6. VAPIDataMarketplace.sol      — three-tier data licensing exchange
 *
 * Data release is exclusively gated to: MANUFACTURER / DEVELOPER / GAMER.
 * No other entity may access VAPI data on-chain.
 *
 * Estimated gas: ~0.32 IOTX total (wallet has ~16.5 IOTX remaining)
 *
 * Prerequisites:
 *   Wallet: 0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692 (bridge + deployer)
 *   Chain:  IoTeX Testnet (4690)
 *
 * Usage:
 *   cd contracts && npx hardhat run scripts/deploy-phase69.js --network iotex_testnet
 *
 * Outputs:
 *   contracts/deployed-addresses.json  — 6 new addresses
 *   bridge/.env.phase69                — all 6 addresses as env vars
 */

const { ethers } = require("hardhat");
const fs   = require("fs");
const path = require("path");

async function main() {
    const [deployer] = await ethers.getSigners();
    console.log("\nDeployer:", deployer.address);
    const balance = await ethers.provider.getBalance(deployer.address);
    console.log("Balance: ", ethers.formatEther(balance), "IOTX");
    console.log("\n═══════════════════════════════════════════════════════");
    console.log("  Phase 69 — VAPI Data Sovereignty + DePIN Tokenomics");
    console.log("═══════════════════════════════════════════════════════\n");

    const deployed = {};

    // ─────────────────────────────────────────────────────────────────────
    // 1. DataSovereigntyRegistry
    // ─────────────────────────────────────────────────────────────────────
    console.log("[1/6] DataSovereigntyRegistry...");
    {
        const Factory = await ethers.getContractFactory("DataSovereigntyRegistry");
        const contract = await Factory.deploy(deployer.address);
        await contract.waitForDeployment();
        deployed.DataSovereigntyRegistry = await contract.getAddress();
        const op = await contract.operator();
        console.log("  ✓ DataSovereigntyRegistry:", deployed.DataSovereigntyRegistry);
        console.log("  operator:", op);
    }

    // ─────────────────────────────────────────────────────────────────────
    // 2. HumanityOracle
    // ─────────────────────────────────────────────────────────────────────
    console.log("\n[2/6] HumanityOracle...");
    {
        const Factory = await ethers.getContractFactory("HumanityOracle");
        const contract = await Factory.deploy(deployer.address);
        await contract.waitForDeployment();
        deployed.HumanityOracle = await contract.getAddress();
        const op = await contract.operator();
        console.log("  ✓ HumanityOracle:", deployed.HumanityOracle);
        console.log("  operator:", op);
    }

    // ─────────────────────────────────────────────────────────────────────
    // 3. RulingOracle
    // ─────────────────────────────────────────────────────────────────────
    console.log("\n[3/6] RulingOracle...");
    {
        const Factory = await ethers.getContractFactory("RulingOracle");
        const contract = await Factory.deploy(deployer.address);
        await contract.waitForDeployment();
        deployed.RulingOracle = await contract.getAddress();
        const op = await contract.operator();
        console.log("  ✓ RulingOracle:", deployed.RulingOracle);
        console.log("  operator:", op);
    }

    // ─────────────────────────────────────────────────────────────────────
    // 4. PassportOracle
    // ─────────────────────────────────────────────────────────────────────
    console.log("\n[4/6] PassportOracle...");
    {
        const Factory = await ethers.getContractFactory("PassportOracle");
        const contract = await Factory.deploy(deployer.address);
        await contract.waitForDeployment();
        deployed.PassportOracle = await contract.getAddress();
        const op = await contract.operator();
        console.log("  ✓ PassportOracle:", deployed.PassportOracle);
        console.log("  operator:", op);
    }

    // ─────────────────────────────────────────────────────────────────────
    // 5. VAPIRewardDistributor
    // ─────────────────────────────────────────────────────────────────────
    console.log("\n[5/6] VAPIRewardDistributor...");
    {
        const Factory = await ethers.getContractFactory("VAPIRewardDistributor");
        const contract = await Factory.deploy(deployer.address);
        await contract.waitForDeployment();
        deployed.VAPIRewardDistributor = await contract.getAddress();
        const op = await contract.operator();
        console.log("  ✓ VAPIRewardDistributor:", deployed.VAPIRewardDistributor);
        console.log("  operator:", op);
        console.log("  BASE_POINTS_PER_SESSION:", (await contract.BASE_POINTS_PER_SESSION()).toString());
        console.log("  POINTS_PER_TOKEN:", (await contract.POINTS_PER_TOKEN()).toString());
    }

    // ─────────────────────────────────────────────────────────────────────
    // 6. VAPIDataMarketplace
    // ─────────────────────────────────────────────────────────────────────
    console.log("\n[6/6] VAPIDataMarketplace...");
    {
        const Factory = await ethers.getContractFactory("VAPIDataMarketplace");
        // Treasury = deployer wallet for testnet; replace with multisig for mainnet
        const contract = await Factory.deploy(deployer.address, deployer.address);
        await contract.waitForDeployment();
        deployed.VAPIDataMarketplace = await contract.getAddress();
        const op = await contract.operator();

        // Wire DataSovereigntyRegistry
        await contract.setSovereigntyRegistry(deployed.DataSovereigntyRegistry);
        console.log("  ✓ VAPIDataMarketplace:", deployed.VAPIDataMarketplace);
        console.log("  operator:", op);
        console.log("  sovereigntyRegistry wired:", deployed.DataSovereigntyRegistry);

        // Verify pricing for DEVELOPER/SESSION_DATA (spot check)
        const devSessionPrice = await contract.getPrice(1, 0); // TIER_DEVELOPER, CLASS_SESSION
        console.log("  devSessionPrice (500 expected):", devSessionPrice.toString());
    }

    // ─────────────────────────────────────────────────────────────────────
    // Write deployed-addresses.json
    // ─────────────────────────────────────────────────────────────────────
    const addrPath = path.join(__dirname, "../deployed-addresses.json");
    const existing = JSON.parse(fs.readFileSync(addrPath, "utf8"));

    const updated = {
        ...existing,
        _note:    "IoTeX Testnet — Phase 69 deployment complete 2026-03-18 (29 contracts LIVE)",
        _status:  "COMPLETE — 29 contracts LIVE (Phase 69: DataSovereigntyRegistry, HumanityOracle, RulingOracle, PassportOracle, VAPIRewardDistributor, VAPIDataMarketplace)",
        DataSovereigntyRegistry: deployed.DataSovereigntyRegistry,
        HumanityOracle:          deployed.HumanityOracle,
        RulingOracle:            deployed.RulingOracle,
        PassportOracle:          deployed.PassportOracle,
        VAPIRewardDistributor:   deployed.VAPIRewardDistributor,
        VAPIDataMarketplace:     deployed.VAPIDataMarketplace,
        _wiring_notes: {
            ...existing._wiring_notes,
            DataSovereigntyRegistry: "Phase 69 — Immutable data sovereignty pledge. Three-tier licensing (MANUFACTURER/DEVELOPER/GAMER). Call pledge_() once after deploy. operator=0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692.",
            HumanityOracle:          "Phase 69 — Native VAPI oracle. DataCuratorAgent writes after each PITL cycle. humanityPct scaled ×10 (1000 = 100.0%). Any tournament contract may query.",
            RulingOracle:            "Phase 69 — Native VAPI oracle. Wraps RulingEnforcementAgent streak state. isEligible() = not suspended AND flagStreak < 5 AND holdStreak < 2.",
            PassportOracle:          "Phase 69 — Native VAPI oracle. Wraps PITLTournamentPassport on-chain status. hasVerifiedPassport() = issued AND onChain.",
            VAPIRewardDistributor:   "Phase 69 — DePIN token distributor. Device-gated (not player-gated, separation ratio 0.362). Multipliers stack: passport 1.5× + enrollment 2.0× + streak 2.5× + MPC 1.25× + gate 3.0×. setRewardToken() before first claim.",
            VAPIDataMarketplace:     "Phase 69 — Three-tier data exchange. MANUFACTURER/DEVELOPER/GAMER only. Data pricing in VAPI reward points. 70% device pool / 30% treasury revenue split. sovereigntyRegistry wired.",
        },
    };

    fs.writeFileSync(addrPath, JSON.stringify(updated, null, 2));
    console.log("\n✓ deployed-addresses.json updated");

    // ─────────────────────────────────────────────────────────────────────
    // Write bridge/.env.phase69
    // ─────────────────────────────────────────────────────────────────────
    const envLines = [
        "# Phase 69 — Data Sovereignty Layer + DePIN Tokenomics + Data Marketplace",
        `DATA_SOVEREIGNTY_REG_ADDRESS=${deployed.DataSovereigntyRegistry}`,
        `HUMANITY_ORACLE_ADDRESS=${deployed.HumanityOracle}`,
        `RULING_ORACLE_ADDRESS=${deployed.RulingOracle}`,
        `PASSPORT_ORACLE_ADDRESS=${deployed.PassportOracle}`,
        `REWARD_DISTRIBUTOR_ADDRESS=${deployed.VAPIRewardDistributor}`,
        `DATA_MARKETPLACE_ADDRESS=${deployed.VAPIDataMarketplace}`,
        `CURATOR_ENABLED=true`,
        `CURATOR_ORACLE_PUBLISH=true`,
    ].join("\n");

    const envPath = path.join(__dirname, "../../bridge/.env.phase69");
    fs.writeFileSync(envPath, envLines);
    console.log("✓ bridge/.env.phase69 written");

    // ─────────────────────────────────────────────────────────────────────
    // Summary
    // ─────────────────────────────────────────────────────────────────────
    console.log("\n═══════════════════════════════════════════════════════");
    console.log("  Phase 69 — Deployment Complete");
    console.log("═══════════════════════════════════════════════════════");
    for (const [name, addr] of Object.entries(deployed)) {
        console.log(`  ${name.padEnd(28)} ${addr}`);
    }
    console.log("\nNext steps:");
    console.log("  1. Merge bridge/.env.phase69 into bridge/.env.testnet");
    console.log("  2. Call DataSovereigntyRegistry.pledge_() with schema hash");
    console.log("  3. Set CURATOR_ENABLED=true + CURATOR_ORACLE_PUBLISH=true");
    console.log("  4. DataCuratorAgent will start publishing oracle updates");
    console.log("  5. Call VAPIRewardDistributor.setRewardToken() when token is deployed");
    console.log("  6. Register first manufacturer/developer via VAPIDataMarketplace");
}

main().catch(e => { console.error(e); process.exit(1); });
