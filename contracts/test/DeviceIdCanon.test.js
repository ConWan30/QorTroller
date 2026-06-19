/**
 * DEVICE_ID_CANON_v1 — EVM execution proof (F-CANON-2).
 *
 * Runs the fixture pubkey through compiled DeviceRegistry.computeDeviceId and
 * asserts the returned bytes32 matches the golden vector. This is the execution
 * check; bridge/tests/test_device_id_canon.py source-pin is supplementary only.
 */
const { expect } = require("chai");
const { ethers } = require("hardhat");
const fs = require("fs");
const path = require("path");

const FIXTURE_PATH = path.join(
  __dirname,
  "../../bridge/tests/fixtures/device_id_canon_demo.json"
);

describe("DeviceIdCanon (DEVICE_ID_CANON_v1 golden vector)", function () {
  let registry;
  let fixture;

  before(async function () {
    fixture = JSON.parse(fs.readFileSync(FIXTURE_PATH, "utf8"));
    expect(fixture.schema).to.equal("vapi-device-id-canon-demo-v1");

    const Factory = await ethers.getContractFactory("DeviceRegistry");
    registry = await Factory.deploy(ethers.parseEther("0.01"));
    await registry.waitForDeployment();
  });

  it("computeDeviceId(fixture pubkey) returns golden device_id on EVM", async function () {
    const pubkey = "0x" + fixture.pubkey_hex;
    const onChain = await registry.computeDeviceId(pubkey);
    expect(onChain).to.equal("0x" + fixture.device_id_hex);
  });

  it("ethers.keccak256(fixture pubkey) matches golden device_id", async function () {
    const pubkey = "0x" + fixture.pubkey_hex;
    expect(ethers.keccak256(pubkey)).to.equal("0x" + fixture.device_id_hex);
  });
});
