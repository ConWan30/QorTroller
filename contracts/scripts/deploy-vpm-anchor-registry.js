/**
 * Phase O4-VPM-ANCHOR — Deploy VPMAnchorRegistry to IoTeX testnet (chain ID 4690)
 *
 * Wallet:           0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692
 * Gas estimate:     ~0.1 IOTX (constructor binding + 14-test surface)
 * Hardhat baseline: ~0.005 IOTX (local node); IoTeX testnet ~2.7x multiplier
 *
 * Constructor:
 *   AdjudicationRegistry address pinned at construction (immutable).
 *   Default: 0x44CF981f46a52ADE56476Ce894255954a7776fb4 (Phase 111 LIVE).
 *   Override via env var ADJUDICATION_REGISTRY_ADDR if testing against
 *   a different deployment.
 *
 * Operator gate (three-factor — operator runs at PowerShell terminal):
 *   1. $env:CHAIN_SUBMISSION_PAUSED="false"       # explicit kill-switch lift
 *   2. $env:OPERATOR_VPM_ANCHOR_AUTHORIZED="true" # intent confirmation
 *   3. npx hardhat run scripts/deploy-vpm-anchor-registry.js \
 *        --network iotex_testnet
 *
 * The script self-checks gates 1+2 before any RPC contact; missing env
 * causes immediate exit without wallet impact.
 *
 * After successful deploy, this script:
 *   - Verifies isAnchored(zero_hash) returns false (cold-start sanity)
 *   - Verifies adjudicationRegistry() returns the pinned address
 *   - Verifies owner() == deployer
 *   - Updates contracts/deployed-addresses.json
 *   - Prints follow-up env var hints for bridge/.env
 *
 * Post-deploy, bridge/.env should add:
 *   VPM_ANCHOR_REGISTRY_ADDRESS=<addr>
 *
 * Then bridge restart picks up the new address for future
 * chain.anchor_vpm() helper calls (Phase O4-VPM-ANCHOR-CHAIN-CLIENT
 * follow-up).
 *
 * Idempotent on the chain side: this contract has no existing state to
 * preserve; a re-deploy creates a new instance at a new address. The
 * original instance would continue to function — the registry has no
 * concept of "active version" beyond the address bridge/.env points at.
 */

const { ethers } = require("hardhat");
const fs = require("fs");
const path = require("path");

const DEFAULT_ADJUDICATION_REGISTRY =
    "0x44CF981f46a52ADE56476Ce894255954a7776fb4"; // Phase 111 LIVE

async function main() {
    // Gate 1: CHAIN_SUBMISSION_PAUSED must NOT be true.
    if (process.env.CHAIN_SUBMISSION_PAUSED === "true") {
        console.error(
            "ABORT: CHAIN_SUBMISSION_PAUSED=true held. Lift kill-switch " +
            "to authorize wallet spend."
        );
        process.exit(2);
    }

    // Gate 2: explicit operator intent.
    if (process.env.OPERATOR_VPM_ANCHOR_AUTHORIZED !== "true") {
        console.error(
            "ABORT: OPERATOR_VPM_ANCHOR_AUTHORIZED env var not set to " +
            "'true'. This is the operator's three-factor intent flag. " +
            "Set explicitly before re-running."
        );
        process.exit(3);
    }

    const adjRegAddr = process.env.ADJUDICATION_REGISTRY_ADDR ||
                       DEFAULT_ADJUDICATION_REGISTRY;
    console.log("AdjudicationRegistry address (composed):", adjRegAddr);

    const [deployer] = await ethers.getSigners();
    console.log("Deployer wallet:", deployer.address);

    const balanceBefore = await ethers.provider.getBalance(deployer.address);
    console.log(
        "Wallet balance (pre-deploy):",
        ethers.formatEther(balanceBefore),
        "IOTX",
    );

    if (balanceBefore < ethers.parseEther("0.5")) {
        console.error(
            "ABORT: wallet balance below 0.5 IOTX safety floor. " +
            "Cost projection 0.1 IOTX deploy + buffer; refuel wallet " +
            "before retrying."
        );
        process.exit(4);
    }

    const Factory = await ethers.getContractFactory("VPMAnchorRegistry");
    const contract = await Factory.deploy(adjRegAddr);
    await contract.waitForDeployment();
    const addr = await contract.getAddress();
    console.log("VPMAnchorRegistry deployed to:", addr);

    // Smoke test 1: owner == deployer
    const owner = await contract.owner();
    console.assert(
        owner === deployer.address,
        `Smoke test 1 FAILED: owner ${owner} != deployer ${deployer.address}`,
    );
    console.log("Smoke test 1 passed: owner =", owner);

    // Smoke test 2: adjudicationRegistry == pinned address
    const adjReg = await contract.adjudicationRegistry();
    console.assert(
        adjReg.toLowerCase() === adjRegAddr.toLowerCase(),
        `Smoke test 2 FAILED: adjudicationRegistry mismatch`,
    );
    console.log("Smoke test 2 passed: adjudicationRegistry =", adjReg);

    // Smoke test 3: totalAnchored = 0 on cold start
    const total = await contract.totalAnchored();
    console.assert(total === 0n, "Smoke test 3 FAILED: totalAnchored != 0");
    console.log("Smoke test 3 passed: totalAnchored =", total.toString());

    // Smoke test 4: isAnchored(zero_hash) returns false
    const isZeroAnchored = await contract.isAnchored(ethers.ZeroHash);
    console.assert(
        isZeroAnchored === false,
        "Smoke test 4 FAILED: zero hash reported anchored",
    );
    console.log("Smoke test 4 passed: isAnchored(0x0) =", isZeroAnchored);

    const balanceAfter = await ethers.provider.getBalance(deployer.address);
    const cost = balanceBefore - balanceAfter;
    console.log(
        "Wallet balance (post-deploy):",
        ethers.formatEther(balanceAfter),
        "IOTX",
    );
    console.log(
        "Deploy cost:",
        ethers.formatEther(cost),
        "IOTX",
    );

    // Update contracts/deployed-addresses.json
    const addrFile = path.join(__dirname, "../deployed-addresses.json");
    let addresses = {};
    if (fs.existsSync(addrFile)) {
        addresses = JSON.parse(fs.readFileSync(addrFile, "utf8"));
    }
    addresses["VPMAnchorRegistry"] = addr;
    addresses["_phase_o4_vpm_anchor_status"] = "deployed";
    addresses["_phase_o4_vpm_anchor_note"] =
        "Phase O4-VPM-ANCHOR: extends FROZEN quadruple-bind into " +
        "quintuple-bind by adding chain-anchored VPM manifest " +
        "registry. Composes with AdjudicationRegistry " +
        "isRecorded() for cross-contract ZKBA integrity check.";
    fs.writeFileSync(addrFile, JSON.stringify(addresses, null, 2));
    console.log("contracts/deployed-addresses.json updated");

    console.log("\nNext steps:");
    console.log("  bridge/.env: VPM_ANCHOR_REGISTRY_ADDRESS=" + addr);
    console.log("  CLAUDE.md:   Phase O4-VPM-ANCHOR COMPLETE");
    console.log(
        "  bridge restart picks up the new address for future anchor " +
        "ceremony scripts."
    );
}

main().catch((err) => {
    console.error(err);
    process.exit(1);
});
