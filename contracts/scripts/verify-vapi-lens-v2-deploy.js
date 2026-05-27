// Path A Arc 1 Commit 4 — one-shot post-deploy verifier.
const { ethers } = require("hardhat");

async function main() {
  const ADDR   = "0x32Bf1A01a0a2629955A3Fd5ce74c0571DAd7C989";
  const WALLET = "0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692";

  const code = await ethers.provider.getCode(ADDR);
  console.log("bytecode_hex_length:", code.length - 2);

  const bal = await ethers.provider.getBalance(WALLET);
  console.log("wallet_after_deploy:", ethers.formatEther(bal), "IOTX");

  const c = await ethers.getContractAt("VAPIProtocolLensV2", ADDR);
  console.log("humanityOracle             :", await c.humanityOracle());
  console.log("rulingOracle               :", await c.rulingOracle());
  console.log("passportOracle             :", await c.passportOracle());
  console.log("rewardDistributor          :", await c.rewardDistributor());
  console.log("manufacturerDeviceRegistry :", await c.manufacturerDeviceRegistry());
  // Path A surface on the real wired oracles + real MFG (unregistered device).
  const zeroDev = "0x" + "00".repeat(32);
  console.log("isFullyEligible(0x00...00)       :", await c.isFullyEligible(zeroDev));
  console.log("isFullyEligible_PathA(0x00...00) :", await c.isFullyEligible_PathA(zeroDev));
  console.log("getDeviceTier(0x00...00)         :", (await c.getDeviceTier(zeroDev)).toString());
}

main().catch((e) => { console.error(e); process.exit(1); });
