/**
 * deploy-phase113.js — VAPIDualPrimitiveGate
 * Phase 113: Dual-Primitive Composability Gate (PoAC + PoAd)
 *
 * Prerequisites (BOTH required):
 *   1. AdjudicationRegistry deployed (run deploy-phase111.js first)
 *   2. IOTX funded wallet: 0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692
 *
 * Gas estimate: ~0.03 IOTX (view-only contract, minimal state)
 *
 * Usage:
 *   npx hardhat run scripts/deploy-phase113.js --network iotex_testnet
 *
 * Post-deploy:
 *   1. Update contracts/deployed-addresses.json VAPIDualPrimitiveGate field
 *   2. Update bridge/.env.testnet DUAL_PRIMITIVE_GATE_ADDRESS=<address>
 *   3. Set DUAL_PRIMITIVE_GATE_ENABLED=true in bridge/.env.testnet
 */

const { ethers } = require("hardhat");
const fs = require("fs");
const path = require("path");

async function main() {
    const [deployer] = await ethers.getSigners();
    console.log("Deployer:", deployer.address);
    console.log("Balance:", ethers.formatEther(await ethers.provider.getBalance(deployer.address)), "IOTX");

    // Read deployed addresses
    const addressesPath = path.join(__dirname, "..", "deployed-addresses.json");
    const addresses = JSON.parse(fs.readFileSync(addressesPath, "utf8"));

    const protocolLensAddr = addresses["VAPIProtocolLens"];
    const adjRegistryAddr  = addresses["AdjudicationRegistry"];

    if (!protocolLensAddr || protocolLensAddr === "0x0000000000000000000000000000000000000000") {
        throw new Error("VAPIProtocolLens address not found in deployed-addresses.json");
    }
    if (!adjRegistryAddr || adjRegistryAddr === "0x0000000000000000000000000000000000000000") {
        throw new Error("AdjudicationRegistry not deployed — run deploy-phase111.js first");
    }

    console.log("\n=== Phase 113: VAPIDualPrimitiveGate ===");
    console.log("VAPIProtocolLens:    ", protocolLensAddr);
    console.log("AdjudicationRegistry:", adjRegistryAddr);

    const GateFactory = await ethers.getContractFactory("VAPIDualPrimitiveGate");
    const gate = await GateFactory.deploy(protocolLensAddr, adjRegistryAddr);
    await gate.waitForDeployment();
    const gateAddr = await gate.getAddress();
    console.log("VAPIDualPrimitiveGate deployed:", gateAddr);

    // Smoke test — view call, no gas
    const testDeviceId = ethers.keccak256(ethers.toUtf8Bytes("smoke_test_device"));
    const testPoadHash = ethers.keccak256(ethers.toUtf8Bytes("smoke_test_poad"));
    const [eligible, poac, poad] = await gate.isDualEligible(testDeviceId, testPoadHash);
    console.log("Smoke isDualEligible:", { eligible, poac_valid: poac, poad_valid: poad });
    // Expected: all false (unregistered device/poad) — correct behavior

    // Verify immutables
    const storedLens = await gate.protocolLens();
    const storedReg  = await gate.adjudicationRegistry();
    if (storedLens.toLowerCase() !== protocolLensAddr.toLowerCase()) {
        throw new Error("protocolLens address mismatch");
    }
    if (storedReg.toLowerCase() !== adjRegistryAddr.toLowerCase()) {
        throw new Error("adjudicationRegistry address mismatch");
    }
    console.log("Immutables verified ✓");

    // Update deployed-addresses.json
    addresses["VAPIDualPrimitiveGate"] = gateAddr;
    addresses["_phase113_note"] = "Phase 113: VAPIDualPrimitiveGate — dual-primitive composability gate (PoAC + PoAd)";
    addresses["_phase113_status"] = "LIVE (testnet)";
    fs.writeFileSync(addressesPath, JSON.stringify(addresses, null, 2));
    console.log("deployed-addresses.json updated ✓");

    console.log("\n=== Phase 113 deployment complete ===");
    console.log("Next steps:");
    console.log("  1. Set DUAL_PRIMITIVE_GATE_ADDRESS=" + gateAddr + " in bridge/.env.testnet");
    console.log("  2. Set DUAL_PRIMITIVE_GATE_ENABLED=true to activate check-dual-eligibility endpoint");
}

main().catch((err) => {
    console.error(err);
    process.exit(1);
});
