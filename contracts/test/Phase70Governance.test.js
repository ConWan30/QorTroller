/**
 * Phase 70 — VAPI Governance Timelock + Protocol Lens Tests (14 tests)
 *
 * VAPIGovernanceTimelock (9 tests):
 *   test_1:  queueTransition emits TransitionQueued with correct eta
 *   test_2:  executeTransition before eta reverts
 *   test_3:  executeTransition after 48h succeeds and calls setOperator
 *   test_4:  cancelTransition by operator succeeds
 *   test_5:  cancelTransition by coSigner succeeds
 *   test_6:  cancelTransition by unauthorized address reverts
 *   test_7:  executed transition cannot be re-executed
 *   test_8:  cancelled transition cannot be executed
 *   test_13: setCoSigner(address(0)) reverts [Phase 71 — L-1 fix]
 *
 * VAPIProtocolLens (5 tests):
 *   test_9:  getDeviceState returns composite struct with snapshotBlock
 *   test_10: isFullyEligible returns true when all conditions met
 *   test_11: isFullyEligible returns false when suspended
 *   test_12: isFullyEligible returns false when passport not on-chain
 *   test_14: isEligible defaults false when ruling oracle reverts [Phase 71 — M-1 fix]
 */

const { expect } = require("chai");
const { ethers, network } = require("hardhat");

const DEVICE_ID_A = "0x" + "aa".repeat(32);
const ZERO_HASH   = "0x" + "00".repeat(32);

// Helper: increase EVM time by `seconds`
async function increaseTime(seconds) {
    await network.provider.send("evm_increaseTime", [seconds]);
    await network.provider.send("evm_mine");
}

describe("Phase 70 — VAPIGovernanceTimelock", function () {

    let owner, alice, coSigner;
    let timelock;
    let targetOracle; // HumanityOracle used as a target for operator transitions

    beforeEach(async function () {
        [owner, alice, coSigner] = await ethers.getSigners();

        // Deploy a Phase 69 oracle contract as the transition target
        const HO = await ethers.getContractFactory("HumanityOracle");
        targetOracle = await HO.deploy(owner.address);
        await targetOracle.waitForDeployment();

        const TL = await ethers.getContractFactory("VAPIGovernanceTimelock");
        timelock = await TL.deploy(owner.address, coSigner.address);
        await timelock.waitForDeployment();
    });

    it("test_1: queueTransition emits TransitionQueued with correct eta", async function () {
        const tx = await timelock.queueTransition(await targetOracle.getAddress(), alice.address);
        const receipt = await tx.wait();
        const block = await ethers.provider.getBlock(receipt.blockNumber);

        const event = receipt.logs.find(l => {
            try { return timelock.interface.parseLog(l).name === "TransitionQueued"; }
            catch { return false; }
        });
        expect(event).to.not.be.undefined;

        const parsed = timelock.interface.parseLog(event);
        expect(parsed.args.queueId).to.equal(0n);
        expect(parsed.args.target).to.equal(await targetOracle.getAddress());
        expect(parsed.args.newOperator).to.equal(alice.address);
        // eta should be approximately block.timestamp + 48h
        const expectedEta = BigInt(block.timestamp) + BigInt(48 * 3600);
        expect(parsed.args.eta).to.be.closeTo(expectedEta, 5n);
    });

    it("test_2: executeTransition before eta reverts", async function () {
        await timelock.queueTransition(await targetOracle.getAddress(), alice.address);
        // No time advance — should revert
        await expect(timelock.executeTransition(0))
            .to.be.revertedWith("VAPIGovernanceTimelock: timelock not elapsed");
    });

    it("test_3: executeTransition after 48h succeeds and calls setOperator", async function () {
        // First transfer oracle ownership to timelock so it can call setOperator
        await targetOracle.setOperator(await timelock.getAddress());

        await timelock.queueTransition(await targetOracle.getAddress(), alice.address);

        // Advance time past 48h
        await increaseTime(48 * 3600 + 1);

        const tx = await timelock.executeTransition(0);
        const receipt = await tx.wait();

        const event = receipt.logs.find(l => {
            try { return timelock.interface.parseLog(l).name === "TransitionExecuted"; }
            catch { return false; }
        });
        expect(event).to.not.be.undefined;

        // Verify oracle's operator changed
        expect(await targetOracle.operator()).to.equal(alice.address);

        // Verify transition marked executed
        const t = await timelock.getTransition(0);
        expect(t.executed).to.be.true;
    });

    it("test_4: cancelTransition by operator succeeds", async function () {
        await timelock.queueTransition(await targetOracle.getAddress(), alice.address);
        const tx = await timelock.cancelTransition(0);
        const receipt = await tx.wait();

        const event = receipt.logs.find(l => {
            try { return timelock.interface.parseLog(l).name === "TransitionCancelled"; }
            catch { return false; }
        });
        expect(event).to.not.be.undefined;

        const t = await timelock.getTransition(0);
        expect(t.cancelled).to.be.true;
    });

    it("test_5: cancelTransition by coSigner succeeds", async function () {
        await timelock.queueTransition(await targetOracle.getAddress(), alice.address);
        // co-signer cancels
        await timelock.connect(coSigner).cancelTransition(0);
        const t = await timelock.getTransition(0);
        expect(t.cancelled).to.be.true;
    });

    it("test_6: cancelTransition by unauthorized address reverts", async function () {
        await timelock.queueTransition(await targetOracle.getAddress(), alice.address);
        await expect(
            timelock.connect(alice).cancelTransition(0)
        ).to.be.revertedWith("VAPIGovernanceTimelock: not operator or co-signer");
    });

    it("test_7: executed transition cannot be re-executed", async function () {
        await targetOracle.setOperator(await timelock.getAddress());
        await timelock.queueTransition(await targetOracle.getAddress(), alice.address);
        await increaseTime(48 * 3600 + 1);
        await timelock.executeTransition(0);

        await expect(timelock.executeTransition(0))
            .to.be.revertedWith("VAPIGovernanceTimelock: already executed");
    });

    it("test_8: cancelled transition cannot be executed", async function () {
        await timelock.queueTransition(await targetOracle.getAddress(), alice.address);
        await timelock.cancelTransition(0);
        await increaseTime(48 * 3600 + 1);

        await expect(timelock.executeTransition(0))
            .to.be.revertedWith("VAPIGovernanceTimelock: cancelled");
    });

    it("test_13: setCoSigner(address(0)) reverts [Phase 71 L-1 fix]", async function () {
        await expect(
            timelock.setCoSigner(ethers.ZeroAddress)
        ).to.be.revertedWith("VAPIGovernanceTimelock: zero co-signer");
    });
});

describe("Phase 70 — VAPIProtocolLens", function () {

    let owner, alice;
    let humanity, ruling, passport, reward, lens;

    beforeEach(async function () {
        [owner, alice] = await ethers.getSigners();

        const HO = await ethers.getContractFactory("HumanityOracle");
        humanity = await HO.deploy(owner.address);
        await humanity.waitForDeployment();

        const RO = await ethers.getContractFactory("RulingOracle");
        ruling = await RO.deploy(owner.address);
        await ruling.waitForDeployment();

        const PO = await ethers.getContractFactory("PassportOracle");
        passport = await PO.deploy(owner.address);
        await passport.waitForDeployment();

        const VRD = await ethers.getContractFactory("VAPIRewardDistributor");
        reward = await VRD.deploy(owner.address);
        await reward.waitForDeployment();

        const Lens = await ethers.getContractFactory("VAPIProtocolLens");
        lens = await Lens.deploy(
            await humanity.getAddress(),
            await ruling.getAddress(),
            await passport.getAddress(),
            await reward.getAddress()
        );
        await lens.waitForDeployment();
    });

    it("test_9: getDeviceState returns composite struct with snapshotBlock", async function () {
        const state = await lens.getDeviceState(DEVICE_ID_A);
        // Unregistered device — all zeros/defaults
        expect(state.snapshotBlock).to.be.gt(0n);
        expect(state.fullyEligible).to.be.false; // not nominal, no passport
        expect(state.isNominal).to.be.false;
        expect(state.multiplierX100).to.equal(100n); // default 1.0×
    });

    it("test_10: isFullyEligible returns true when all conditions met", async function () {
        // Set NOMINAL humanity
        await humanity.updateVerdict(DEVICE_ID_A, 0x20, 920, 3000, 50);

        // Set not suspended, clean ruling state
        await ruling.updateRulingState(DEVICE_ID_A, false, 2, 0, 0, ZERO_HASH);

        // Set passport issued and on-chain
        await passport.updatePassportState(
            DEVICE_ID_A, true, true, ethers.keccak256(ethers.toUtf8Bytes("passport")), 12
        );

        expect(await lens.isFullyEligible(DEVICE_ID_A)).to.be.true;
    });

    it("test_11: isFullyEligible returns false when suspended", async function () {
        // Set NOMINAL humanity
        await humanity.updateVerdict(DEVICE_ID_A, 0x20, 920, 3000, 50);

        // Set SUSPENDED ruling state
        const suspendedUntil = Math.floor(Date.now() / 1000) + 86400; // 24h from now
        await ruling.updateRulingState(DEVICE_ID_A, true, 5, 1, suspendedUntil, ZERO_HASH);

        // Set passport issued and on-chain
        await passport.updatePassportState(
            DEVICE_ID_A, true, true, ethers.keccak256(ethers.toUtf8Bytes("passport")), 12
        );

        expect(await lens.isFullyEligible(DEVICE_ID_A)).to.be.false;
    });

    it("test_12: isFullyEligible returns false when passport not on-chain", async function () {
        // Set NOMINAL humanity
        await humanity.updateVerdict(DEVICE_ID_A, 0x20, 920, 3000, 50);

        // Set not suspended
        await ruling.updateRulingState(DEVICE_ID_A, false, 2, 0, 0, ZERO_HASH);

        // Passport issued but NOT on-chain (onChain=false)
        await passport.updatePassportState(
            DEVICE_ID_A, true, false, ethers.keccak256(ethers.toUtf8Bytes("passport")), 8
        );

        expect(await lens.isFullyEligible(DEVICE_ID_A)).to.be.false;
    });

    it("test_14: isEligible defaults false when ruling oracle reverts [Phase 71 M-1 fix]", async function () {
        // Deploy a mock oracle that always reverts on isEligible()
        const Mock = await ethers.getContractFactory("MockRevertingRulingOracle");
        const mockRuling = await Mock.deploy();
        await mockRuling.waitForDeployment();

        // Deploy a lens pointing at the reverting ruling oracle
        const Lens = await ethers.getContractFactory("VAPIProtocolLens");
        const lensWithMock = await Lens.deploy(
            await humanity.getAddress(),
            await mockRuling.getAddress(),  // <-- always reverts on isEligible
            await passport.getAddress(),
            await reward.getAddress()
        );
        await lensWithMock.waitForDeployment();

        const state = await lensWithMock.getDeviceState(DEVICE_ID_A);

        // M-1 fix: oracle failure must produce fail-closed behaviour
        expect(state.oracleAvailable).to.be.false;
        expect(state.isEligible).to.be.false;
        // isSuspended() succeeds on the mock, so suspended stays false
        expect(state.suspended).to.be.false;
    });
});
