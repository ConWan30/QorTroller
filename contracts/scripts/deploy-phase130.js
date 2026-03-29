// Deploy VAPISwarmOperatorGate (Phase 130A — WIF-001 mitigation)
// DEFERRED: Requires wallet >= 0.40 IOTX (current: ~0.35 IOTX after Phase 113 deploy)
// Run after IOTX top-up: npx hardhat run contracts/scripts/deploy-phase130.js --network iotex_testnet
// Gas estimate: ~0.04 IOTX on IoTeX testnet (pure view contract, minimal storage)
// Post-deploy: set SWARM_OPERATOR_GATE_ADDRESS in bridge/.env.testnet
const { ethers } = require("hardhat");
const fs = require("fs");

async function main() {
    const [deployer] = await ethers.getSigners();
    console.log("Deploying VAPISwarmOperatorGate with:", deployer.address);
    const balance = await ethers.provider.getBalance(deployer.address);
    console.log("Deployer balance:", ethers.formatEther(balance), "IOTX");

    if (ethers.formatEther(balance) < 0.04) {
        console.error("WARNING: Low balance. Recommend >= 0.04 IOTX for deployment.");
    }

    // Read VAPIOperatorRegistry address from deployed-addresses.json
    const addressesPath = "deployed-addresses.json";
    const addresses = JSON.parse(fs.readFileSync(addressesPath, "utf8"));
    const operatorRegistryAddr = addresses.VAPIOperatorRegistry;
    if (!operatorRegistryAddr) {
        throw new Error("VAPIOperatorRegistry not found in deployed-addresses.json. Deploy Phase 99A first.");
    }
    console.log("Using VAPIOperatorRegistry:", operatorRegistryAddr);

    const VAPISwarmOperatorGate = await ethers.getContractFactory("VAPISwarmOperatorGate");
    const gate = await VAPISwarmOperatorGate.deploy(operatorRegistryAddr);
    await gate.waitForDeployment();

    const addr = await gate.getAddress();
    console.log("VAPISwarmOperatorGate deployed to:", addr);

    // Smoke test: isQuorumValid([]) -> false
    const emptyValid = await gate.isQuorumValid([]);
    console.log("Smoke test isQuorumValid([]):", emptyValid, "(expected false)");
    if (emptyValid !== false) {
        throw new Error("Smoke test FAILED: isQuorumValid([]) should return false");
    }

    // Verify immutable
    const regAddr = await gate.operatorRegistry();
    console.log("operatorRegistry immutable:", regAddr);
    if (regAddr.toLowerCase() !== operatorRegistryAddr.toLowerCase()) {
        throw new Error("Immutable operatorRegistry mismatch");
    }

    // Append to deployed-addresses.json
    addresses.VAPISwarmOperatorGate = addr;
    addresses._phase130_status = "LIVE (testnet)";
    fs.writeFileSync(addressesPath, JSON.stringify(addresses, null, 2));
    console.log("deployed-addresses.json updated (40 contracts)");

    console.log("\n=== Phase 130A Deploy Complete ===");
    console.log("Set SWARM_OPERATOR_GATE_ADDRESS=" + addr + " in bridge/.env.testnet");
    console.log("Phase 130B (activate gate): set swarm_operator_gate_address in bridge config");
}

main().catch((err) => {
    console.error(err);
    process.exit(1);
});
