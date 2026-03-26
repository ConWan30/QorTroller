/**
 * Phase 70 — VAPI Synergistic Foundation: Governance Timelock + Protocol Lens
 *
 * Deploys 2 contracts:
 *   1. VAPIGovernanceTimelock.sol — 48h queued operator transitions for Phase 69 contracts
 *   2. VAPIProtocolLens.sol       — unified device state in one eth_call
 *
 * Prerequisites:
 *   Phase 69 must be deployed first (VAPIProtocolLens constructor needs oracle addresses).
 *   Run: npx hardhat run scripts/deploy-phase69.js --network iotex_testnet
 *
 * Estimated gas: ~0.13 IOTX total
 *
 * Usage:
 *   cd contracts && npx hardhat run scripts/deploy-phase70.js --network iotex_testnet
 *
 * Outputs:
 *   contracts/deployed-addresses.json  — 2 new addresses appended
 *   bridge/.env.phase70                — GOVERNANCE_TIMELOCK_ADDRESS, PROTOCOL_LENS_ADDRESS
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
    console.log("  Phase 70 — VAPI Governance Timelock + Protocol Lens");
    console.log("═══════════════════════════════════════════════════════\n");

    // Load deployed addresses to get Phase 69 oracle addresses
    const addrPath = path.join(__dirname, "..", "deployed-addresses.json");
    let existing = {};
    try {
        existing = JSON.parse(fs.readFileSync(addrPath, "utf8"));
    } catch (e) {
        console.warn("Warning: could not load deployed-addresses.json:", e.message);
    }

    // Phase 69 oracle addresses (required for VAPIProtocolLens)
    const humanityOracleAddr     = existing.HumanityOracle     || process.env.HUMANITY_ORACLE_ADDRESS     || "";
    const rulingOracleAddr       = existing.RulingOracle       || process.env.RULING_ORACLE_ADDRESS       || "";
    const passportOracleAddr     = existing.PassportOracle     || process.env.PASSPORT_ORACLE_ADDRESS     || "";
    const rewardDistributorAddr  = existing.VAPIRewardDistributor || process.env.REWARD_DISTRIBUTOR_ADDRESS || "";

    if (!humanityOracleAddr || !rulingOracleAddr || !passportOracleAddr || !rewardDistributorAddr) {
        console.error("ERROR: Phase 69 oracle addresses not found in deployed-addresses.json.");
        console.error("  Deploy Phase 69 first: npx hardhat run scripts/deploy-phase69.js --network iotex_testnet");
        console.error("  Required: HumanityOracle, RulingOracle, PassportOracle, VAPIRewardDistributor");
        process.exit(1);
    }

    console.log("Phase 69 oracle addresses:");
    console.log("  HumanityOracle:      ", humanityOracleAddr);
    console.log("  RulingOracle:        ", rulingOracleAddr);
    console.log("  PassportOracle:      ", passportOracleAddr);
    console.log("  VAPIRewardDistributor:", rewardDistributorAddr);
    console.log();

    const deployed = {};

    // ─────────────────────────────────────────────────────────────────────
    // 1. VAPIGovernanceTimelock
    // ─────────────────────────────────────────────────────────────────────
    console.log("[1/2] VAPIGovernanceTimelock...");
    {
        const Factory = await ethers.getContractFactory("VAPIGovernanceTimelock");
        // co-signer defaults to deployer address (update post-deploy with setCoSigner)
        const contract = await Factory.deploy(deployer.address, deployer.address);
        await contract.waitForDeployment();
        const addr = await contract.getAddress();
        deployed.VAPIGovernanceTimelock = addr;
        console.log("  VAPIGovernanceTimelock: ", addr);
        console.log("  operator:               ", deployer.address);
        console.log("  coSigner (initial):     ", deployer.address);
        console.log("  TIMELOCK_DELAY:          48 hours");
        console.log("  -> Verify: operator() + TIMELOCK_DELAY");
        console.log();
    }

    // ─────────────────────────────────────────────────────────────────────
    // 2. VAPIProtocolLens
    // ─────────────────────────────────────────────────────────────────────
    console.log("[2/2] VAPIProtocolLens...");
    {
        const Factory = await ethers.getContractFactory("VAPIProtocolLens");
        const contract = await Factory.deploy(
            humanityOracleAddr,
            rulingOracleAddr,
            passportOracleAddr,
            rewardDistributorAddr
        );
        await contract.waitForDeployment();
        const addr = await contract.getAddress();
        deployed.VAPIProtocolLens = addr;
        console.log("  VAPIProtocolLens:        ", addr);
        console.log("  humanityOracle:          ", humanityOracleAddr);
        console.log("  rulingOracle:            ", rulingOracleAddr);
        console.log("  passportOracle:          ", passportOracleAddr);
        console.log("  rewardDistributor:       ", rewardDistributorAddr);
        console.log("  -> Verify: isFullyEligible(bytes32(0)) -> false (no data)");
        console.log();
    }

    // ─────────────────────────────────────────────────────────────────────
    // Write outputs
    // ─────────────────────────────────────────────────────────────────────

    // Update deployed-addresses.json
    const updated = {
        ...existing,
        _note: "IoTeX Testnet — Phase 70 deployment (25 contracts LIVE)",
        _status: "COMPLETE — 25 contracts LIVE (Phase 70: VAPIGovernanceTimelock, VAPIProtocolLens)",
        ...deployed,
        _wiring_notes: {
            ...(existing._wiring_notes || {}),
            VAPIGovernanceTimelock: `Phase 70 — 48h governance timelock for Phase 69 contracts. coSigner=deployer (update via setCoSigner). operator=${deployer.address}.`,
            VAPIProtocolLens: `Phase 70 — Zero-state unified device state view. Synthesizes 4 Phase 69 oracles in one eth_call. isFullyEligible(deviceId) -> bool.`,
        },
    };
    fs.writeFileSync(addrPath, JSON.stringify(updated, null, 2));
    console.log("Updated deployed-addresses.json");

    // Write bridge/.env.phase70
    const envLines = [
        `# Phase 70 — Governance Timelock + Protocol Lens`,
        `# Generated by deploy-phase70.js`,
        ``,
        `GOVERNANCE_TIMELOCK_ADDRESS=${deployed.VAPIGovernanceTimelock}`,
        `PROTOCOL_LENS_ADDRESS=${deployed.VAPIProtocolLens}`,
    ].join("\n");
    const envPath = path.join(__dirname, "..", "..", "bridge", ".env.phase70");
    fs.writeFileSync(envPath, envLines);
    console.log("Written bridge/.env.phase70");

    console.log("\n═══════════════════════════════════════════════════════");
    console.log("  Phase 70 deployment COMPLETE");
    console.log("═══════════════════════════════════════════════════════");
    console.log("  Contracts deployed: 2");
    console.log("  VAPIGovernanceTimelock:", deployed.VAPIGovernanceTimelock);
    console.log("  VAPIProtocolLens:      ", deployed.VAPIProtocolLens);
    console.log("\nNext: Update bridge/.env.testnet with these addresses.");
    console.log("      Update CLAUDE.md + MEMORY.md (Phase 70 complete, 25 contracts).");
}

main().catch((err) => {
    console.error(err);
    process.exitCode = 1;
});
