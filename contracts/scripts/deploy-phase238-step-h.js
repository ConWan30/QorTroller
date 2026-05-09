// Phase 238 Step H — Deploy VAPIDataMarketplaceListings.sol on IoTeX testnet
//
// Provenance-Anchored Listing Layer (PALL) extension contract.  Reads
// IAdjudicationRegistry.isRecorded() per anchor to compute tier multiplier
// (1.0× / 1.5× / 2.0× / 3.0×) — sellers cannot self-attest tier.
//
// Constructor args:
//   _phase69Marketplace    : VAPIDataMarketplace address (Phase 69 LIVE)
//   _adjudicationRegistry  : AdjudicationRegistry address (Phase 111 LIVE
//                            0x44CF981f46a52ADE56476Ce894255954a7776fb4)
//
// Estimated gas: ~0.10 IOTX on IoTeX testnet (Phase 99-PREP empirical baseline
// 2.7× Hardhat multiplier).  Pre-deploy wallet check requires ≥0.5 IOTX
// to leave headroom for Phase 237 ceremony+verifier deploy queue ahead.
//
// Usage:
//   cd contracts && npx hardhat run scripts/deploy-phase238-step-h.js \
//       --network iotex_testnet
//
// Pre-flight: run `python scripts/curator_preflight_runbook.py` first.

const { ethers } = require("hardhat");
const fs = require("fs");

async function main() {
    const [deployer] = await ethers.getSigners();
    console.log("=".repeat(72));
    console.log("Phase 238 Step H — VAPIDataMarketplaceListings deploy");
    console.log("=".repeat(72));
    console.log("Deployer:", deployer.address);

    const balance = await ethers.provider.getBalance(deployer.address);
    const balanceIotx = parseFloat(ethers.formatEther(balance));
    console.log("Balance: ", balanceIotx.toFixed(4), "IOTX");

    if (balanceIotx < 0.15) {
        throw new Error(
            `Insufficient balance: ${balanceIotx.toFixed(4)} IOTX.  ` +
            `Need >=0.15 IOTX for safety margin (estimated cost ~0.10 IOTX).`
        );
    }

    // ── Read existing deployed contract addresses ────────────────────
    const addressesPath = "deployed-addresses.json";
    if (!fs.existsSync(addressesPath)) {
        throw new Error("deployed-addresses.json not found");
    }
    const addresses = JSON.parse(fs.readFileSync(addressesPath, "utf8"));

    // Phase 69 marketplace + Phase 111 AdjudicationRegistry must be live
    const phase69Addr = addresses.VAPIDataMarketplace;
    const adjRegAddr  = addresses.AdjudicationRegistry;

    if (!phase69Addr) {
        throw new Error(
            "VAPIDataMarketplace (Phase 69) not in deployed-addresses.json — " +
            "PALL extension cannot deploy without its parent contract."
        );
    }
    if (!adjRegAddr) {
        throw new Error(
            "AdjudicationRegistry (Phase 111) not in deployed-addresses.json — " +
            "PALL extension cannot deploy without anchor verification source."
        );
    }
    console.log("Phase 69 VAPIDataMarketplace:    ", phase69Addr);
    console.log("Phase 111 AdjudicationRegistry:  ", adjRegAddr);

    // Already deployed check
    if (addresses.VAPIDataMarketplaceListings) {
        console.log("");
        console.log("ALREADY DEPLOYED at", addresses.VAPIDataMarketplaceListings);
        console.log("Skipping — re-deploy would change tier compute address; " +
                    "operators relying on the existing deployment would break.");
        return;
    }

    // ── Deploy extension contract ────────────────────────────────────
    console.log("");
    console.log("Deploying VAPIDataMarketplaceListings...");
    const Listings = await ethers.getContractFactory("VAPIDataMarketplaceListings");
    const listings = await Listings.deploy(phase69Addr, adjRegAddr);
    await listings.waitForDeployment();
    const addr = await listings.getAddress();
    console.log("VAPIDataMarketplaceListings deployed to:", addr);

    // ── Sanity calls ──────────────────────────────────────────────────
    console.log("");
    console.log("Smoke calls:");
    const phase69ReadBack = await listings.phase69Marketplace();
    const adjRegReadBack  = await listings.adjudicationRegistry();
    console.log("  phase69Marketplace()    =", phase69ReadBack);
    console.log("  adjudicationRegistry()  =", adjRegReadBack);
    if (phase69ReadBack.toLowerCase() !== phase69Addr.toLowerCase()) {
        throw new Error("phase69 read-back mismatch");
    }
    if (adjRegReadBack.toLowerCase() !== adjRegAddr.toLowerCase()) {
        throw new Error("adjudicationRegistry read-back mismatch");
    }

    // ── Update deployed-addresses.json ────────────────────────────────
    addresses.VAPIDataMarketplaceListings = addr;
    addresses._phase238_step_h_status = "LIVE (testnet)";
    fs.writeFileSync(addressesPath, JSON.stringify(addresses, null, 2));
    console.log("");
    console.log("deployed-addresses.json updated (added VAPIDataMarketplaceListings)");

    // ── Operator next steps ───────────────────────────────────────────
    const balanceAfter = await ethers.provider.getBalance(deployer.address);
    const cost = balanceIotx - parseFloat(ethers.formatEther(balanceAfter));
    console.log("");
    console.log("=".repeat(72));
    console.log("Phase 238 Step H deploy COMPLETE");
    console.log("=".repeat(72));
    console.log("  Cost:                     ", cost.toFixed(4), "IOTX");
    console.log("  Wallet remaining:         ", ethers.formatEther(balanceAfter), "IOTX");
    console.log("");
    console.log("NEXT STEP: bridge/.env add:");
    console.log("   LISTING_REGISTRY_ADDRESS=" + addr);
    console.log("");
    console.log("THEN: Phase 238 Step I-FINAL — Curator NFT mint + dual-anchor:");
    console.log("   npx hardhat run scripts/mint-curator-agent.js --network iotex_testnet");
    console.log("");
}

main().catch((e) => {
    console.error(e);
    process.exit(1);
});
