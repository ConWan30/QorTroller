// One-shot post-deploy verification — read bytecode + owner + balance.
const { ethers } = require("hardhat");

async function main() {
  const ADDR = "0x2e5B5FB110890f498e289E3045d0f54Cfb0F91b0";
  const WALLET = "0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692";

  const code = await ethers.provider.getCode(ADDR);
  console.log("bytecode_hex_length:", code.length - 2); // strip 0x

  const bal = await ethers.provider.getBalance(WALLET);
  console.log("wallet_after_deploy:", ethers.formatEther(bal), "IOTX");

  const c = await ethers.getContractAt("VAPIManufacturerDeviceRegistry", ADDR);
  console.log("on_chain_owner:", await c.owner());
  console.log("totalRegistrations:", (await c.totalRegistrations()).toString());
  console.log("SIGNING_PATH_A:", (await c.SIGNING_PATH_A()).toString());
  console.log("SIGNING_PATH_B:", (await c.SIGNING_PATH_B()).toString());
  console.log("PROOF_TIER_FULL:", (await c.PROOF_TIER_FULL()).toString());

  // smoke test the 4 bridge-consumed view methods against an unregistered device
  // (no registrations yet — should all return dormant)
  const noDev = ethers.keccak256(ethers.toUtf8Bytes("unregistered-smoke-test"));
  console.log("--- live view smoke (unregistered device) ---");
  console.log("getSigningPath:", (await c.getSigningPath(noDev)).toString(), "(expect 0)");
  console.log("getProofTier  :", (await c.getProofTier(noDev)).toString(), "(expect 0)");
  console.log("isPathA       :", await c.isPathA(noDev),         "(expect false)");
  console.log("isActive      :", await c.isActive(noDev),        "(expect false)");
}

main().catch((e) => { console.error(e); process.exit(1); });
