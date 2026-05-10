// Phase 237-ZK-SEPPROOF Session 2 — deploy Groth16VerifierZKSepProof + ZKSepProofVerifier wrapper
//
// Two-stage deploy per ZKSepProofVerifier.sol NatSpec design:
//   Stage 1: deploy Groth16VerifierZKSepProof.sol (auto-generated from
//            ceremony VK via snarkjs zkey export solidityverifier)
//   Stage 2: deploy ZKSepProofVerifier(groth16Address, adjudicationRegAddr)
//            — wraps the Groth16 verifier + adds BIOMETRIC-SNAPSHOT-v1
//            anchor pre-condition (snapshot_hash from public inputs MUST
//            be recorded on AdjudicationRegistry).
//
// Estimated cost: ~0.10-0.15 IOTX total at 2000 Gwei
//   - Groth16Verifier: ~750k gas (verifyProof contract is heavy)
//   - ZKSepProofVerifier wrapper: ~400k gas (lighter)
//
// Pre-flight: Phase 237 ceremony complete + Groth16VerifierZKSepProof.sol
//   present at contracts/contracts/Groth16VerifierZKSepProof.sol
//
// Usage:
//   cd contracts && npx hardhat run scripts/deploy-zk-sepproof.js \
//       --network iotex_testnet

const { ethers } = require("hardhat");
const fs = require("fs");

async function main() {
    const [deployer] = await ethers.getSigners();
    console.log("=".repeat(72));
    console.log("Phase 237-ZK-SEPPROOF Session 2 — verifier deploy");
    console.log("=".repeat(72));
    console.log("Deployer:", deployer.address);

    const balance = await ethers.provider.getBalance(deployer.address);
    const balanceIotx = parseFloat(ethers.formatEther(balance));
    console.log("Balance: ", balanceIotx.toFixed(4), "IOTX");
    if (balanceIotx < 0.20) {
        throw new Error(`Insufficient balance: ${balanceIotx.toFixed(4)} < 0.20 IOTX safety floor.`);
    }

    const addressesPath = "deployed-addresses.json";
    const addresses = JSON.parse(fs.readFileSync(addressesPath, "utf8"));
    const adjRegAddr = addresses.AdjudicationRegistry;
    if (!adjRegAddr) {
        throw new Error("AdjudicationRegistry address missing from deployed-addresses.json");
    }
    console.log("AdjudicationRegistry:", adjRegAddr);

    // ── Already-deployed guard ────────────────────────────────────────
    if (addresses.Groth16VerifierZKSepProof && addresses.ZKSepProofVerifier) {
        console.log("");
        console.log("ALREADY DEPLOYED:");
        console.log("  Groth16VerifierZKSepProof:", addresses.Groth16VerifierZKSepProof);
        console.log("  ZKSepProofVerifier:       ", addresses.ZKSepProofVerifier);
        console.log("Skipping (re-deploy would change verifier addresses).");
        return;
    }

    // ── Stage 1: Deploy Groth16VerifierZKSepProof ─────────────────────
    console.log("");
    console.log("Stage 1: Deploying Groth16VerifierZKSepProof...");
    const Groth16 = await ethers.getContractFactory("Groth16VerifierZKSepProof");
    const groth16 = await Groth16.deploy();
    await groth16.waitForDeployment();
    const groth16Addr = await groth16.getAddress();
    console.log("  Groth16VerifierZKSepProof:", groth16Addr);

    // ── Stage 2: Deploy ZKSepProofVerifier wrapper ────────────────────
    console.log("");
    console.log("Stage 2: Deploying ZKSepProofVerifier wrapper...");
    const Wrapper = await ethers.getContractFactory("ZKSepProofVerifier");
    const wrapper = await Wrapper.deploy(groth16Addr, adjRegAddr);
    await wrapper.waitForDeployment();
    const wrapperAddr = await wrapper.getAddress();
    console.log("  ZKSepProofVerifier:       ", wrapperAddr);

    // ── Smoke calls ──────────────────────────────────────────────────
    console.log("");
    console.log("Smoke calls:");
    const innerVerifier = await wrapper.groth16Verifier();
    const innerAdjReg   = await wrapper.adjudicationRegistry();
    console.log("  groth16Verifier()       =", innerVerifier);
    console.log("  adjudicationRegistry()  =", innerAdjReg);
    if (innerVerifier.toLowerCase() !== groth16Addr.toLowerCase()) {
        throw new Error("groth16Verifier read-back mismatch");
    }
    if (innerAdjReg.toLowerCase() !== adjRegAddr.toLowerCase()) {
        throw new Error("adjudicationRegistry read-back mismatch");
    }

    // ── Update deployed-addresses.json ────────────────────────────────
    addresses.Groth16VerifierZKSepProof = groth16Addr;
    addresses.ZKSepProofVerifier = wrapperAddr;
    addresses._phase237_zk_sepproof_status = "LIVE (testnet)";
    addresses._phase237_zk_sepproof_ceremony_beacon_block = 43451392;
    addresses._phase237_zk_sepproof_vk_hash = "0x32fda2857bdfb0612dd5cb305aa6798fabd64bb3f9362f362c6d73cdc49c4c1f";
    fs.writeFileSync(addressesPath, JSON.stringify(addresses, null, 2));
    console.log("");
    console.log("deployed-addresses.json updated");

    // ── Cost reporting ────────────────────────────────────────────────
    const balanceAfter = await ethers.provider.getBalance(deployer.address);
    const cost = balanceIotx - parseFloat(ethers.formatEther(balanceAfter));
    console.log("");
    console.log("=".repeat(72));
    console.log("Phase 237-ZK-SEPPROOF deploy COMPLETE");
    console.log("=".repeat(72));
    console.log("  Total cost:                ", cost.toFixed(4), "IOTX");
    console.log("  Wallet remaining:          ", ethers.formatEther(balanceAfter), "IOTX");
    console.log("");
    console.log("NEXT: bridge/.env additions:");
    console.log("   GROTH16_VERIFIER_ZK_SEPPROOF_ADDRESS=" + groth16Addr);
    console.log("   ZK_SEPPROOF_VERIFIER_ADDRESS=" + wrapperAddr);
    console.log("");
    console.log("THEN: Phase 237 deployment can flip the bridge prover from mock to real");
    console.log("      mode by setting ZK_SEPPROOF_REAL_MODE_ENABLED=true in bridge/.env");
}

main().catch((e) => { console.error(e); process.exit(1); });
