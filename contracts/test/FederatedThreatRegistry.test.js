const { expect } = require("chai");
const { ethers } = require("hardhat");

// ---------------------------------------------------------------------------
// FederatedThreatRegistry Tests — Phase 80
//
// 14 tests replacing Phase 34 cluster-hash design with Phase 80 per-ruling
// threat signal design (addThreatSignal / isThreatSignaled / revokeThreatSignal).
//
// FTR-1:  deploy sets operator correctly
// FTR-2:  addThreatSignal emits ThreatSignalAdded event
// FTR-3:  isThreatSignaled returns true after addThreatSignal
// FTR-4:  revokeThreatSignal sets active=false and emits ThreatSignalRevoked
// FTR-5:  isThreatSignaled returns false after revoke
// FTR-6:  non-operator addThreatSignal reverts
// FTR-7:  duplicate commitHash reverts (anti-replay)
// FTR-8:  getThreatSignal returns full struct with correct fields
// FTR-9:  addThreatSignal with zero deviceId reverts
// FTR-10: addThreatSignal with zero commitHash reverts
// FTR-11: deviceSignalCount increments on add, decrements on revoke
// FTR-12: revokeThreatSignal on inactive signal reverts
// FTR-13: non-operator revokeThreatSignal reverts
// FTR-14: transferOperator changes operator and emits OperatorTransferred
// ---------------------------------------------------------------------------

const COMMIT_HASH_1 = ethers.zeroPadBytes("0xaabb01", 32);
const COMMIT_HASH_2 = ethers.zeroPadBytes("0xaabb02", 32);
const CIRCUIT_ID_1 = ethers.zeroPadBytes("0xccdd01", 32);
const ZERO_BYTES32  = ethers.zeroPadBytes("0x00",    32);

async function deployFTR(operatorAddress) {
    const Factory = await ethers.getContractFactory("FederatedThreatRegistry");
    return Factory.deploy(operatorAddress);
}

describe("FederatedThreatRegistry (Phase 80)", function () {
    let ftr, operator, other, deviceAddr;

    beforeEach(async function () {
        [operator, other, deviceAddr] = await ethers.getSigners();
        ftr = await deployFTR(operator.address);
    });

    // -------------------------------------------------------------------------
    // FTR-1: Deployment
    // -------------------------------------------------------------------------

    it("FTR-1: deploy sets operator address correctly", async function () {
        expect(await ftr.operator()).to.equal(operator.address);
    });

    // -------------------------------------------------------------------------
    // FTR-2: addThreatSignal emits ThreatSignalAdded
    // -------------------------------------------------------------------------

    it("FTR-2: addThreatSignal emits ThreatSignalAdded event", async function () {
        await expect(
            ftr.connect(operator).addThreatSignal(
                deviceAddr.address, COMMIT_HASH_1, CIRCUIT_ID_1
            )
        )
            .to.emit(ftr, "ThreatSignalAdded")
            .withArgs(
                deviceAddr.address,
                COMMIT_HASH_1,
                CIRCUIT_ID_1,
                // timestamp is block.timestamp — any positive value is acceptable
                (ts) => ts > 0n
            );
    });

    // -------------------------------------------------------------------------
    // FTR-3: isThreatSignaled returns true after addThreatSignal
    // -------------------------------------------------------------------------

    it("FTR-3: isThreatSignaled returns true after addThreatSignal", async function () {
        expect(await ftr.isThreatSignaled(deviceAddr.address)).to.equal(false);
        await ftr.connect(operator).addThreatSignal(
            deviceAddr.address, COMMIT_HASH_1, CIRCUIT_ID_1
        );
        expect(await ftr.isThreatSignaled(deviceAddr.address)).to.equal(true);
    });

    // -------------------------------------------------------------------------
    // FTR-4: revokeThreatSignal sets active=false and emits event
    // -------------------------------------------------------------------------

    it("FTR-4: revokeThreatSignal sets active=false and emits ThreatSignalRevoked", async function () {
        await ftr.connect(operator).addThreatSignal(
            deviceAddr.address, COMMIT_HASH_1, CIRCUIT_ID_1
        );
        const tx = ftr.connect(operator).revokeThreatSignal(COMMIT_HASH_1);
        await expect(tx)
            .to.emit(ftr, "ThreatSignalRevoked")
            .withArgs(COMMIT_HASH_1, deviceAddr.address);

        const sig = await ftr.getThreatSignal(COMMIT_HASH_1);
        expect(sig.active).to.equal(false);
    });

    // -------------------------------------------------------------------------
    // FTR-5: isThreatSignaled returns false after revoke
    // -------------------------------------------------------------------------

    it("FTR-5: isThreatSignaled returns false after all signals revoked", async function () {
        await ftr.connect(operator).addThreatSignal(
            deviceAddr.address, COMMIT_HASH_1, CIRCUIT_ID_1
        );
        expect(await ftr.isThreatSignaled(deviceAddr.address)).to.equal(true);
        await ftr.connect(operator).revokeThreatSignal(COMMIT_HASH_1);
        expect(await ftr.isThreatSignaled(deviceAddr.address)).to.equal(false);
    });

    // -------------------------------------------------------------------------
    // FTR-6: Access control — non-operator reverts
    // -------------------------------------------------------------------------

    it("FTR-6: non-operator addThreatSignal reverts", async function () {
        await expect(
            ftr.connect(other).addThreatSignal(deviceAddr.address, COMMIT_HASH_1, CIRCUIT_ID_1)
        ).to.be.revertedWith("FederatedThreatRegistry: caller is not operator");
    });

    // -------------------------------------------------------------------------
    // FTR-7: Anti-replay — duplicate commitHash reverts
    // -------------------------------------------------------------------------

    it("FTR-7: duplicate commitHash in addThreatSignal reverts", async function () {
        await ftr.connect(operator).addThreatSignal(
            deviceAddr.address, COMMIT_HASH_1, CIRCUIT_ID_1
        );
        await expect(
            ftr.connect(operator).addThreatSignal(deviceAddr.address, COMMIT_HASH_1, CIRCUIT_ID_1)
        ).to.be.revertedWith("FederatedThreatRegistry: commitHash already registered");
    });

    // -------------------------------------------------------------------------
    // FTR-8: getThreatSignal returns full struct
    // -------------------------------------------------------------------------

    it("FTR-8: getThreatSignal returns full struct with correct fields", async function () {
        await ftr.connect(operator).addThreatSignal(
            deviceAddr.address, COMMIT_HASH_1, CIRCUIT_ID_1
        );
        const sig = await ftr.getThreatSignal(COMMIT_HASH_1);
        expect(sig.deviceId).to.equal(deviceAddr.address);
        expect(sig.commitHash).to.equal(COMMIT_HASH_1);
        expect(sig.circuitId).to.equal(CIRCUIT_ID_1);
        expect(sig.active).to.equal(true);
        expect(sig.timestamp).to.be.gt(0n);
    });

    // -------------------------------------------------------------------------
    // FTR-9: zero deviceId reverts
    // -------------------------------------------------------------------------

    it("FTR-9: addThreatSignal with zero deviceId reverts", async function () {
        await expect(
            ftr.connect(operator).addThreatSignal(
                ethers.ZeroAddress, COMMIT_HASH_1, CIRCUIT_ID_1
            )
        ).to.be.revertedWith("FederatedThreatRegistry: zero deviceId");
    });

    // -------------------------------------------------------------------------
    // FTR-10: zero commitHash reverts
    // -------------------------------------------------------------------------

    it("FTR-10: addThreatSignal with zero commitHash reverts", async function () {
        await expect(
            ftr.connect(operator).addThreatSignal(
                deviceAddr.address, ZERO_BYTES32, CIRCUIT_ID_1
            )
        ).to.be.revertedWith("FederatedThreatRegistry: zero commitHash");
    });

    // -------------------------------------------------------------------------
    // FTR-11: deviceSignalCount tracking
    // -------------------------------------------------------------------------

    it("FTR-11: deviceSignalCount increments on add and decrements on revoke", async function () {
        expect(await ftr.deviceSignalCount(deviceAddr.address)).to.equal(0n);

        await ftr.connect(operator).addThreatSignal(
            deviceAddr.address, COMMIT_HASH_1, CIRCUIT_ID_1
        );
        expect(await ftr.deviceSignalCount(deviceAddr.address)).to.equal(1n);

        await ftr.connect(operator).addThreatSignal(
            deviceAddr.address, COMMIT_HASH_2, CIRCUIT_ID_1
        );
        expect(await ftr.deviceSignalCount(deviceAddr.address)).to.equal(2n);

        await ftr.connect(operator).revokeThreatSignal(COMMIT_HASH_1);
        expect(await ftr.deviceSignalCount(deviceAddr.address)).to.equal(1n);

        await ftr.connect(operator).revokeThreatSignal(COMMIT_HASH_2);
        expect(await ftr.deviceSignalCount(deviceAddr.address)).to.equal(0n);
    });

    // -------------------------------------------------------------------------
    // FTR-12: revoke inactive signal reverts
    // -------------------------------------------------------------------------

    it("FTR-12: revokeThreatSignal on already-inactive signal reverts", async function () {
        await ftr.connect(operator).addThreatSignal(
            deviceAddr.address, COMMIT_HASH_1, CIRCUIT_ID_1
        );
        await ftr.connect(operator).revokeThreatSignal(COMMIT_HASH_1);

        // Second revoke should revert
        await expect(
            ftr.connect(operator).revokeThreatSignal(COMMIT_HASH_1)
        ).to.be.revertedWith("FederatedThreatRegistry: signal not active");
    });

    // -------------------------------------------------------------------------
    // FTR-13: non-operator revoke reverts
    // -------------------------------------------------------------------------

    it("FTR-13: non-operator revokeThreatSignal reverts", async function () {
        await ftr.connect(operator).addThreatSignal(
            deviceAddr.address, COMMIT_HASH_1, CIRCUIT_ID_1
        );
        await expect(
            ftr.connect(other).revokeThreatSignal(COMMIT_HASH_1)
        ).to.be.revertedWith("FederatedThreatRegistry: caller is not operator");
    });

    // -------------------------------------------------------------------------
    // FTR-14: transferOperator
    // -------------------------------------------------------------------------

    it("FTR-14: transferOperator changes operator and emits OperatorTransferred", async function () {
        await expect(ftr.connect(operator).transferOperator(other.address))
            .to.emit(ftr, "OperatorTransferred")
            .withArgs(operator.address, other.address);

        expect(await ftr.operator()).to.equal(other.address);

        // Old operator no longer has access
        await expect(
            ftr.connect(operator).addThreatSignal(deviceAddr.address, COMMIT_HASH_1, CIRCUIT_ID_1)
        ).to.be.revertedWith("FederatedThreatRegistry: caller is not operator");
    });
});

// ---------------------------------------------------------------------------
// Helper: get latest block timestamp (tolerant of ±1s EVM clock)
// ---------------------------------------------------------------------------
async function latestTimestamp() {
    const block = await ethers.provider.getBlock("latest");
    return BigInt(block.timestamp);
}
