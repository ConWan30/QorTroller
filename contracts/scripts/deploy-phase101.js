/**
 * Phase 101 Deploy — VAPIQuickSilverCollateral
 *
 * Sequence:
 *   1. Deploy MockStIOTX (testnet only — real stIOTX address on mainnet)
 *   2. Deploy VAPIQuickSilverCollateral(stIOTXAddress, owner)
 *
 * Gas estimate: ~0.06 IOTX total
 */
const hre = require("hardhat");
const fs = require("fs");

async function main() {
  const [deployer] = await hre.ethers.getSigners();
  console.log("Deploying Phase 101 from:", deployer.address);

  const stIOTXAddr = process.env.STIOTX_TOKEN_ADDRESS;
  let stIOTX;

  if (!stIOTXAddr || stIOTXAddr === "") {
    console.log("No STIOTX_TOKEN_ADDRESS set — deploying MockStIOTX for testnet");
    const MockStIOTX = await hre.ethers.getContractFactory("MockStIOTX");
    stIOTX = await MockStIOTX.deploy();
    await stIOTX.waitForDeployment();
    console.log("MockStIOTX deployed to:", await stIOTX.getAddress());
  } else {
    console.log("Using existing stIOTX at:", stIOTXAddr);
    stIOTX = { getAddress: () => stIOTXAddr };
  }

  const VAPIQuickSilverCollateral = await hre.ethers.getContractFactory("VAPIQuickSilverCollateral");
  const collateral = await VAPIQuickSilverCollateral.deploy(
    await stIOTX.getAddress(),
    deployer.address
  );
  await collateral.waitForDeployment();
  const collateralAddr = await collateral.getAddress();
  console.log("VAPIQuickSilverCollateral deployed to:", collateralAddr);

  // Write env file
  const envContent = [
    `STIOTX_TOKEN_ADDRESS=${await stIOTX.getAddress()}`,
    `QUICKSILVER_COLLATERAL_ADDRESS=${collateralAddr}`,
  ].join("\n");
  fs.writeFileSync("../bridge/.env.phase101", envContent + "\n");
  console.log("Wrote bridge/.env.phase101");

  // Update deployed-addresses.json
  const addrPath = "./deployed-addresses.json";
  const addrs = JSON.parse(fs.readFileSync(addrPath, "utf8"));
  addrs.VAPIQuickSilverCollateral = collateralAddr;
  if (!stIOTXAddr) addrs.MockStIOTX = await stIOTX.getAddress();
  fs.writeFileSync(addrPath, JSON.stringify(addrs, null, 2));
  console.log("Updated deployed-addresses.json");
}

main().catch((e) => { console.error(e); process.exit(1); });
