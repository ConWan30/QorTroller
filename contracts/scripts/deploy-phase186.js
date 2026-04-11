/**
 * Phase 186 — SeparationRatioRegistry.sol Extension Deploy (Deferred)
 *
 * WIF-032 W2 closure: extends SeparationRatioRegistry with:
 *   - registerAttestation(bytes32 attestationHash, uint256 ttlDays) — stores HMAC attestation
 *   - attestedRenewCommit(prevHash, newHash, ttlDays, attestationHash) — renewal gated by HMAC
 *   - AttestationRecord struct + attestations mapping (anti-replay, single-use)
 *   - Events: AttestationRegistered + AttestationBoundRenewal
 *   - ReentrancyGuard on attestedRenewCommit (CEI pattern enforced)
 *
 * NOTE: SeparationRatioRegistry.sol is NOT yet deployed on IoTeX testnet.
 * It has been code-complete since Phase 153 (deploy deferred — wallet ~0.35 IOTX).
 * Phase 178 added renewCommit(); Phase 186 adds registerAttestation() + attestedRenewCommit().
 * All three phases' functionality is included in this single deploy.
 *
 * VAPI Exclusivity:
 *   After Phase 186, VAPI is the ONLY protocol where:
 *   1. PersonaBreakDetectorAgent detects biometric identity drift (Phase 182)
 *   2. ReEnrollmentAttestationAgent issues HMAC-gated re-enrollment authorization (Phase 185)
 *   3. That authorization is bound on-chain via attestedRenewCommit() — immutable audit trail
 *   4. Entire chain is composable via isFullyEligible() tournament gate
 *   Prerequisite stack: Phases 153+163+164+173+178+180+182+185+186 — non-replicable.
 *
 * Gas estimate: ~0.12 IOTX (Ownable + ReentrancyGuard + attestation mapping + 2 new functions)
 * Wallet balance required: >= 0.15 IOTX (buffer above estimate)
 * Wallet: 0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692 (~0.35 IOTX as of Phase 185)
 *
 * Deploy Status: DEFERRED — wallet feasible but pending token launch sequencing.
 * separationRatioRegistry key in deployed-addresses.json: "PENDING_DEPLOY"
 *
 * Usage (when ready):
 *   npx hardhat run scripts/deploy-phase186.js --network iotex_testnet
 *
 * Post-deploy checklist:
 *   1. Update deployed-addresses.json: separationRatioRegistry = <deployed addr>
 *   2. Update bridge/.env.testnet: SEPARATION_RATIO_REGISTRY_ADDRESS=<deployed addr>
 *   3. Update CLAUDE.md: contracts note (SeparationRatioRegistry now LIVE with Phase 186)
 *   4. Enable separation_ratio_on_chain_enabled=True in bridge config
 *   5. Register first HMAC attestation via registerAttestation() for testing
 */

const { ethers } = require("hardhat");
const fs = require("fs");
const path = require("path");

async function main() {
  const [deployer] = await ethers.getSigners();
  console.log("Deploying SeparationRatioRegistry (Phase 153+178+186) with:", deployer.address);

  const balance = await ethers.provider.getBalance(deployer.address);
  console.log("Wallet balance:", ethers.formatEther(balance), "IOTX");

  if (balance < ethers.parseEther("0.12")) {
    console.warn(
      "WARNING: Wallet balance may be insufficient.",
      "Estimated gas: ~0.12 IOTX. Balance:", ethers.formatEther(balance), "IOTX"
    );
  }

  const Factory = await ethers.getContractFactory("SeparationRatioRegistry");
  console.log("Deploying...");
  const contract = await Factory.deploy(deployer.address);
  await contract.waitForDeployment();

  const addr = await contract.getAddress();
  console.log("SeparationRatioRegistry deployed to:", addr);

  // --- Verify key functions are callable ---
  const totalCommits = await contract.totalCommits();
  console.log("totalCommits:", totalCommits.toString(), "(expect 0)");

  // --- Update deployed-addresses.json ---
  const addrPath = path.join(__dirname, "../deployed-addresses.json");
  let deployed = {};
  if (fs.existsSync(addrPath)) {
    deployed = JSON.parse(fs.readFileSync(addrPath, "utf8"));
  }
  deployed.separationRatioRegistry = addr;
  fs.writeFileSync(addrPath, JSON.stringify(deployed, null, 2));
  console.log("Updated deployed-addresses.json: separationRatioRegistry =", addr);

  console.log("\n=== Phase 186 Deploy Complete ===");
  console.log("separationRatioRegistry:", addr);
  console.log("Phase 153+178+186 functions: commitRatio() + renewCommit() + registerAttestation() + attestedRenewCommit()");
  console.log("\nNext steps:");
  console.log("  1. Set SEPARATION_RATIO_REGISTRY_ADDRESS=" + addr + " in bridge/.env.testnet");
  console.log("  2. Set separation_ratio_on_chain_enabled=True in bridge config");
  console.log("  3. Register first HMAC attestation: registerAttestation(hash, ttlDays=7)");
  console.log("  4. Update CLAUDE.md to mark SeparationRatioRegistry as LIVE");
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
