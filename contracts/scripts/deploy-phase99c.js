/**
 * Phase 99C — Deploy VAPIVerifiedHumanProof + VAPIVerifiedHumanProofBridge
 *
 * Deploys:
 *   1. VAPIVerifiedHumanProof.sol — ERC-4671 soulbound VHP token (~0.08 IOTX)
 *   2. VAPIVerifiedHumanProofBridge.sol — LayerZero V2 OApp stub (~0.05 IOTX)
 *
 * Prerequisites:
 *   Phase 99A + 99B contracts already deployed
 *   contracts/.env must have BRIDGE_PRIVATE_KEY set
 *   Wallet: 0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692
 *   Estimated cost: ~0.13 IOTX total
 *
 * LayerZero V2 endpoint on IoTeX testnet:
 *   Use LZ_ENDPOINT env var or fallback to IoTeX testnet OApp endpoint.
 *   If not set, a zero-address stub is used (bridge send() emits events only).
 *
 * Usage:
 *   cd contracts && npx hardhat run scripts/deploy-phase99c.js --network iotex_testnet
 *
 * Outputs:
 *   bridge/.env.phase99c  — VHP_CONTRACT_ADDRESS + LAYERZERO_ENDPOINT_ADDRESS
 *   contracts/deployed-addresses.json — VAPIVerifiedHumanProof + VAPIVerifiedHumanProofBridge updated
 */

const { ethers } = require("hardhat");
const fs = require("fs"), path = require("path");

async function main() {
    const [deployer] = await ethers.getSigners();
    console.log("Deployer:", deployer.address);
    const balance = await ethers.provider.getBalance(deployer.address);
    console.log("Balance:", ethers.formatEther(balance), "IOTX");

    // LayerZero endpoint — use env var or stub (zero address for testnet stub mode)
    const lzEndpoint = process.env.LZ_ENDPOINT || "0x0000000000000000000000000000000000000001";
    console.log("\nLayerZero endpoint:", lzEndpoint);

    // ----------------------------------------------------------------
    // 1. Deploy VAPIVerifiedHumanProof
    // ----------------------------------------------------------------
    console.log("\nDeploying VAPIVerifiedHumanProof...");
    const VHPFactory = await ethers.getContractFactory("VAPIVerifiedHumanProof");
    const vhp = await VHPFactory.deploy(deployer.address);
    await vhp.waitForDeployment();
    const vhpAddr = await vhp.getAddress();
    console.log("VAPIVerifiedHumanProof deployed:", vhpAddr);

    // Sanity check: mint a test token
    const testData = {
        deviceIdHash: ethers.keccak256(ethers.toUtf8Bytes("deploy_sanity_check")),
        certificationLevel: 1,
        consecutiveClean: 1,
        confidenceScore: 9000,
        issuedAt: Math.floor(Date.now() / 1000),
        expiresAt: Math.floor(Date.now() / 1000) + 90 * 86400,
        mpcCeremonyHash: ethers.keccak256(ethers.toUtf8Bytes("ceremony_sanity")),
    };
    const mintTx = await vhp.mint(deployer.address, testData);
    await mintTx.wait();
    const isValid = await vhp.isValid(1n);
    const supply = await vhp.totalSupply();
    if (!isValid || supply !== 1n) {
        throw new Error(`VHP sanity check failed: isValid=${isValid}, totalSupply=${supply}`);
    }
    console.log("Sanity check: mint+isValid+totalSupply=1 verified");

    // ----------------------------------------------------------------
    // 2. Deploy VAPIVerifiedHumanProofBridge
    // ----------------------------------------------------------------
    console.log("\nDeploying VAPIVerifiedHumanProofBridge...");
    const BridgeFactory = await ethers.getContractFactory("VAPIVerifiedHumanProofBridge");
    const bridge = await BridgeFactory.deploy(lzEndpoint, deployer.address);
    await bridge.waitForDeployment();
    const bridgeAddr = await bridge.getAddress();
    console.log("VAPIVerifiedHumanProofBridge deployed:", bridgeAddr);

    // Sanity check: setPeer for a test dstEid
    const testDstEid = 30101;  // Ethereum mainnet LZ EID
    const testPeer = ethers.keccak256(ethers.toUtf8Bytes("deploy_sanity_peer"));
    const peerTx = await bridge.setPeer(testDstEid, testPeer);
    await peerTx.wait();
    const storedPeer = await bridge.peers(testDstEid);
    if (storedPeer !== testPeer) {
        throw new Error(`Bridge sanity check failed: peers(${testDstEid}) = ${storedPeer}`);
    }
    console.log("Sanity check: setPeer verified");

    // ----------------------------------------------------------------
    // Write env file
    // ----------------------------------------------------------------
    const envPath = path.join(__dirname, "../../bridge/.env.phase99c");
    fs.writeFileSync(envPath,
        `# Phase 99C — VAPIVerifiedHumanProof + VAPIVerifiedHumanProofBridge on IoTeX testnet\n` +
        `VHP_CONTRACT_ADDRESS=${vhpAddr}\n` +
        `LAYERZERO_ENDPOINT_ADDRESS=${lzEndpoint}\n` +
        `LAYERZERO_BRIDGE_ADDRESS=${bridgeAddr}\n` +
        `# POST /agent/mint-vhp requires: audit_valid=True AND gate_passed=True AND AGENT_DRY_RUN=false\n`
    );
    console.log("\nWritten:", envPath);

    // ----------------------------------------------------------------
    // Update deployed-addresses.json
    // ----------------------------------------------------------------
    const addrsPath = path.join(__dirname, "../deployed-addresses.json");
    let addrs = {};
    try { addrs = JSON.parse(fs.readFileSync(addrsPath, "utf8")); } catch {}
    addrs.VAPIVerifiedHumanProof = vhpAddr;
    addrs.VAPIVerifiedHumanProofBridge = bridgeAddr;
    addrs._phase99c_note = "Phase 99C: VHP ERC-4671 soulbound + LayerZero V2 OApp — first cross-chain physiological humanity credential";
    addrs._phase99c_status = "LIVE (testnet)";
    fs.writeFileSync(addrsPath, JSON.stringify(addrs, null, 2));
    console.log("deployed-addresses.json updated (38 contracts).");

    const postBalance = await ethers.provider.getBalance(deployer.address);
    const spent = balance - postBalance;
    console.log("\n=== Phase 99C Deployment Summary ===");
    console.log("VAPIVerifiedHumanProof:       ", vhpAddr);
    console.log("VAPIVerifiedHumanProofBridge: ", bridgeAddr);
    console.log("LayerZero endpoint:           ", lzEndpoint);
    console.log("IOTX spent:                  ", ethers.formatEther(spent));
    console.log("IOTX remaining:              ", ethers.formatEther(postBalance));
    console.log("\nAdd to bridge/.env.testnet:");
    console.log("  VHP_CONTRACT_ADDRESS=" + vhpAddr);
    console.log("  LAYERZERO_BRIDGE_ADDRESS=" + bridgeAddr);
}

main().catch(e => { console.error(e); process.exit(1); });
