/**
 * Phase 187 — VHPReenrollmentBadge.sol Deploy (Deferred)
 *
 * WIF-033 W2 closure: ERC-4671 soulbound credential for biometric re-enrollment events.
 * Issued when ReEnrollmentAttestationAgent HMAC token validates on-chain.
 *
 * Contract functions:
 *   - mintBadge(playerIdHash, attestationHash, ttlDays) — onlyOwner, anti-replay
 *   - isValid(tokenId) — checks valid + expiresAt
 *   - getLatestBadge(playerIdHash) — returns latest tokenId
 *   - revokeBadge(tokenId) — emergency revoke, onlyOwner
 *   - playerBadgeCount[playerIdHash] — total re-enrollments (biometric stability score)
 *
 * VAPI Exclusivity (4-layer stack):
 *   Phase 182: PersonaBreakDetectorAgent → detects LOO accuracy trend collapse
 *   Phase 185: ReEnrollmentAttestationAgent → issues HMAC-SHA256 attestation token
 *   Phase 186: AttestationBoundRenewalAgent → binds attestation on-chain via SeparationRatioRegistry
 *   Phase 187: VHPReenrollmentBadge → soulbound identity recovery credential
 *   Non-replicable: requires all 4 agents' infrastructure + 9-phase prerequisite stack.
 *
 * Gas estimate: ~0.08 IOTX (Ownable + ReentrancyGuard + Badge struct + 4 mappings)
 * Wallet balance required: >= 0.10 IOTX (buffer above estimate)
 * Wallet: 0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692 (~0.35 IOTX as of Phase 186)
 *
 * Deploy Status: DEFERRED — wallet feasible, pending token launch sequencing.
 * vhpReenrollmentBadge key in deployed-addresses.json: "PENDING_DEPLOY"
 *
 * Usage (when ready):
 *   npx hardhat run scripts/deploy-phase187.js --network iotex_testnet
 *
 * Post-deploy checklist:
 *   1. Update deployed-addresses.json: vhpReenrollmentBadge = <deployed addr>
 *   2. Update bridge/.env.testnet: VHP_REENROLLMENT_BADGE_ADDRESS=<deployed addr>
 *   3. Update CLAUDE.md: VHPReenrollmentBadge LIVE (Phase 187)
 *   4. Enable reenrollment_badge_enabled=True in bridge config
 *   5. Test first mintBadge via bridge on a validated re-enrollment event
 */

const { ethers } = require("hardhat");
const fs = require("fs");
const path = require("path");

async function main() {
  const [deployer] = await ethers.getSigners();
  console.log("Deploying VHPReenrollmentBadge (Phase 187) with:", deployer.address);

  const balance = await ethers.provider.getBalance(deployer.address);
  console.log("Wallet balance:", ethers.formatEther(balance), "IOTX");

  if (balance < ethers.parseEther("0.08")) {
    console.warn(
      "WARNING: Wallet balance may be insufficient.",
      "Estimated gas: ~0.08 IOTX. Balance:", ethers.formatEther(balance), "IOTX"
    );
  }

  const Factory = await ethers.getContractFactory("VHPReenrollmentBadge");
  console.log("Deploying...");
  const contract = await Factory.deploy(deployer.address);
  await contract.waitForDeployment();

  const addr = await contract.getAddress();
  console.log("VHPReenrollmentBadge deployed to:", addr);

  // Verify key state
  const totalBadges = await contract.totalBadges();
  console.log("totalBadges:", totalBadges.toString(), "(expect 0)");

  // Update deployed-addresses.json
  const addrPath = path.join(__dirname, "../deployed-addresses.json");
  let deployed = {};
  if (fs.existsSync(addrPath)) {
    deployed = JSON.parse(fs.readFileSync(addrPath, "utf8"));
  }
  deployed.vhpReenrollmentBadge = addr;
  fs.writeFileSync(addrPath, JSON.stringify(deployed, null, 2));
  console.log("Updated deployed-addresses.json: vhpReenrollmentBadge =", addr);

  console.log("\n=== Phase 187 Deploy Complete ===");
  console.log("vhpReenrollmentBadge:", addr);
  console.log("Functions: mintBadge() + isValid() + getLatestBadge() + revokeBadge()");
  console.log("\nNext steps:");
  console.log("  1. Set VHP_REENROLLMENT_BADGE_ADDRESS=" + addr + " in bridge/.env.testnet");
  console.log("  2. Set reenrollment_badge_enabled=True in bridge config");
  console.log("  3. Trigger first mintBadge on validated re-enrollment attestation");
  console.log("  4. Update CLAUDE.md to mark VHPReenrollmentBadge as LIVE");
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
