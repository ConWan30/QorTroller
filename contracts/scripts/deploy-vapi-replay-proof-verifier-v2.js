/**
 * VAPIReplayProofVerifier_v2 deploy — Data Economy Arc 6 (PoSR) Commit 4.
 *
 * Wraps the snarkjs-generated Groth16VerifierVAPIReplayProof_v2 (lands
 * after the v2 ceremony fires) + VAPITemporalBeaconRegistry (deployed in
 * Commit 1). Coexists with Arc 5 v1 verifier — recency is opt-in.
 *
 * Constructor: (groth16VerifierV2, beaconRegistry). Both required, both
 * non-zero, both checked at deploy time.
 *
 * DISCIPLINE (mirrors Arc 5 v1 wrapper triple-gate):
 *   - VAPI_VHR_V2_GROTH16_ADDR + VAPI_TBR_ADDRESS required
 *   - VAPI_VHR_V2_DEPLOY_CONFIRM=1 to broadcast
 *   - 1.0 IOTX hard-cap + 2x balance guard + deployer-bridge-wallet check
 */
const { ethers } = require("hardhat");
const HARD_CAP_IOTX = 1.0, GAS_BUFFER = 1.25;
const EXPECTED_DEPLOYER = "0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692";

async function main() {
  const groth = process.env.VAPI_VHR_V2_GROTH16_ADDR;
  const bReg  = process.env.VAPI_TBR_ADDRESS;
  if (!groth || !ethers.isAddress(groth) || groth === ethers.ZeroAddress) {
    console.error("ERROR: VAPI_VHR_V2_GROTH16_ADDR required (post-ceremony Groth16VerifierVAPIReplayProof_v2 address).");
    process.exit(2);
  }
  if (!bReg || !ethers.isAddress(bReg) || bReg === ethers.ZeroAddress) {
    console.error("ERROR: VAPI_TBR_ADDRESS required (Arc 6 Commit 1 VAPITemporalBeaconRegistry address).");
    process.exit(2);
  }
  const [deployer] = await ethers.getSigners();
  const provider = deployer.provider;
  const bal = await provider.getBalance(deployer.address);
  console.log("Deployer        :", deployer.address);
  console.log("Balance         :", ethers.formatEther(bal), "IOTX");
  console.log("Groth16 v2      :", groth);
  console.log("BeaconRegistry  :", bReg);
  if (deployer.address.toLowerCase() !== EXPECTED_DEPLOYER.toLowerCase()) {
    console.error(`ERROR: deployer != ${EXPECTED_DEPLOYER}`); process.exit(2);
  }
  console.log("deployer check  : PASS");
  const Factory = await ethers.getContractFactory("VAPIReplayProofVerifier_v2");
  const tx = await Factory.getDeployTransaction(groth, bReg);
  const est = await provider.estimateGas({ ...tx, from: deployer.address });
  const gp = (await provider.getFeeData()).gasPrice ?? 1000000000000n;
  const buf = (est * BigInt(Math.round(GAS_BUFFER * 100))) / 100n;
  const cost = Number(ethers.formatEther(buf * gp));
  console.log("\n--- GAS ESTIMATE ---");
  console.log("estimate_gas    :", est.toString());
  console.log("buffered cost   :", cost.toFixed(6), "IOTX");
  if (cost > HARD_CAP_IOTX) { console.error("HARD-CAP EXCEEDED"); process.exit(2); }
  if (Number(ethers.formatEther(bal)) < cost * 2) { console.error("BALANCE GUARD"); process.exit(2); }
  console.log("hard-cap + balance guards : PASS");
  if (process.env.VAPI_VHR_V2_DEPLOY_CONFIRM !== "1") {
    console.log("\n[ESTIMATE-ONLY] VAPI_VHR_V2_DEPLOY_CONFIRM!=1 — NOT broadcasting.");
    return;
  }
  console.log("\n[DEPLOYING] broadcasting...");
  const c = await Factory.deploy(groth, bReg, { gasLimit: buf });
  await c.waitForDeployment();
  const addr = await c.getAddress();
  const rcpt = await provider.getTransactionReceipt(c.deploymentTransaction().hash);
  console.log("address         :", addr);
  console.log("status          :", rcpt.status === 1 ? "success" : "FAILED");
  const v = await ethers.getContractAt("VAPIReplayProofVerifier_v2", addr);
  const expected = ethers.keccak256(ethers.toUtf8Bytes("VAPI-REPLAY-PROOF-v2"));
  if (await v.PROOF_TYPE() !== expected) { console.error("PROOF_TYPE DRIFT"); process.exit(3); }
  console.log("PROOF_TYPE      :", expected, "PASS");
  console.log("\nDEPLOY_RESULT_JSON " + JSON.stringify({
    contract: "VAPIReplayProofVerifier_v2", chainId: 4690, address: addr,
    txHash: c.deploymentTransaction().hash, block: rcpt.blockNumber,
    gasUsed: rcpt.gasUsed.toString(), groth16Verifier: groth, beaconRegistry: bReg,
  }));
}
main().catch((e) => { console.error(e); process.exit(1); });
