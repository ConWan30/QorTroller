/**
 * Phase 69 — Data Sovereignty Layer + DePIN Tokenomics Tests (12 tests)
 *
 * DataSovereigntyRegistry (3): pledge, license grant, license revoke
 * HumanityOracle (2):         updateVerdict, isNominal / getHumanityPct
 * RulingOracle (2):           updateRulingState, isSuspended / isEligible
 * PassportOracle (2):         updatePassportState, hasVerifiedPassport
 * VAPIRewardDistributor (2):  updateDeviceState + multiplier, claimReward blocked without token
 * VAPIDataMarketplace (1):    registerDeveloper + purchaseAccess pricing
 */

const { expect } = require("chai");
const { ethers }  = require("hardhat");

const DEVICE_ID_A = "0x" + "aa".repeat(32);
const DEVICE_ID_B = "0x" + "bb".repeat(32);

describe("Phase 69 — Data Sovereignty Layer", function () {

    let owner, alice, bob;
    let sovereignty, humanity, ruling, passport, reward, marketplace;

    beforeEach(async function () {
        [owner, alice, bob] = await ethers.getSigners();

        const DSR = await ethers.getContractFactory("DataSovereigntyRegistry");
        sovereignty = await DSR.deploy(owner.address);
        await sovereignty.waitForDeployment();

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

        const MP = await ethers.getContractFactory("VAPIDataMarketplace");
        marketplace = await MP.deploy(owner.address, owner.address);
        await marketplace.waitForDeployment();
    });

    // ─────────────────────────────────────────────────────────────────────
    // DataSovereigntyRegistry
    // ─────────────────────────────────────────────────────────────────────

    describe("DataSovereigntyRegistry", function () {

        it("test_1: pledge_ stores schemaHash and declaration immutably", async function () {
            const schemaHash = ethers.keccak256(ethers.toUtf8Bytes("VAPI schema v69"));
            await sovereignty.pledge_(schemaHash, "VAPI data sovereignty pledge v69");
            const p = await sovereignty.getPledge();
            expect(p.schemaHash).to.equal(schemaHash);
            expect(p.sovereignAddress).to.equal(owner.address);
            expect(p.pledgeBlock).to.be.gt(0n);
        });

        it("test_2: grantLicense issues license with correct tier", async function () {
            // DEVELOPER tier = 1, SESSION_DATA = 0
            const expiry = Math.floor(Date.now() / 1000) + 86400;
            const tx = await sovereignty.grantLicense(alice.address, 1, 0, expiry);
            await tx.wait();
            const hasAccess = await sovereignty.hasAccess(alice.address, 0);
            expect(hasAccess).to.be.true;
        });

        it("test_3: revokeLicense removes access", async function () {
            const expiry = Math.floor(Date.now() / 1000) + 86400;
            await (await sovereignty.grantLicense(alice.address, 1, 0, expiry)).wait();
            const licenseId = 1n;
            await (await sovereignty.revokeLicense(licenseId)).wait();
            const hasAccess = await sovereignty.hasAccess(alice.address, 0);
            expect(hasAccess).to.be.false;
        });
    });

    // ─────────────────────────────────────────────────────────────────────
    // HumanityOracle
    // ─────────────────────────────────────────────────────────────────────

    describe("HumanityOracle", function () {

        it("test_4: updateVerdict stores all fields correctly", async function () {
            await humanity.updateVerdict(DEVICE_ID_A, 0x20, 875, 4500, 80);
            const v = await humanity.getHumanityVerdict(DEVICE_ID_A);
            expect(v.inferenceCode).to.equal(0x20);
            expect(v.humanityPct).to.equal(875);
            expect(v.l4DistanceX1000).to.equal(4500);
            expect(v.l5CvX1000).to.equal(80);
            expect(await humanity.updateCount(DEVICE_ID_A)).to.equal(1n);
        });

        it("test_5: isNominal returns true for 0x20 and getHumanityPct matches", async function () {
            await humanity.updateVerdict(DEVICE_ID_A, 0x20, 920, 3000, 50);
            expect(await humanity.isNominal(DEVICE_ID_A)).to.be.true;
            expect(await humanity.getHumanityPct(DEVICE_ID_A)).to.equal(920);

            await humanity.updateVerdict(DEVICE_ID_B, 0x30, 400, 9000, 500);
            expect(await humanity.isNominal(DEVICE_ID_B)).to.be.false;
        });
    });

    // ─────────────────────────────────────────────────────────────────────
    // RulingOracle
    // ─────────────────────────────────────────────────────────────────────

    describe("RulingOracle", function () {

        it("test_6: updateRulingState stores suspension + streaks correctly", async function () {
            const lastHash = "0x" + "cc".repeat(32);
            const suspendedUntil = Math.floor(Date.now() / 1000) + 3600;
            await ruling.updateRulingState(DEVICE_ID_A, true, 3, 1, suspendedUntil, lastHash);
            const s = await ruling.getRulingState(DEVICE_ID_A);
            expect(s.suspended).to.be.true;
            expect(s.flagStreak).to.equal(3);
            expect(s.holdStreak).to.equal(1);
            expect(s.lastCommitmentHash).to.equal(lastHash);
            expect(await ruling.eventCount(DEVICE_ID_A)).to.equal(1n);
        });

        it("test_7: isSuspended and isEligible reflect ruling state", async function () {
            const future = Math.floor(Date.now() / 1000) + 3600;
            await ruling.updateRulingState(DEVICE_ID_A, true, 3, 0, future, "0x" + "00".repeat(32));
            expect(await ruling.isSuspended(DEVICE_ID_A)).to.be.true;
            expect(await ruling.isEligible(DEVICE_ID_A)).to.be.false;

            // Not suspended — clean state
            await ruling.updateRulingState(DEVICE_ID_B, false, 2, 0, 0, "0x" + "00".repeat(32));
            expect(await ruling.isSuspended(DEVICE_ID_B)).to.be.false;
            expect(await ruling.isEligible(DEVICE_ID_B)).to.be.true;
        });
    });

    // ─────────────────────────────────────────────────────────────────────
    // PassportOracle
    // ─────────────────────────────────────────────────────────────────────

    describe("PassportOracle", function () {

        it("test_8: updatePassportState persists all fields", async function () {
            const pHash = "0x" + "dd".repeat(32);
            await passport.updatePassportState(DEVICE_ID_A, true, true, pHash, 15);
            const s = await passport.getPassportState(DEVICE_ID_A);
            expect(s.issued).to.be.true;
            expect(s.onChain).to.be.true;
            expect(s.passportHash).to.equal(pHash);
            expect(s.sessionCount).to.equal(15);
            expect(await passport.updateCount(DEVICE_ID_A)).to.equal(1n);
        });

        it("test_9: hasVerifiedPassport returns correct boolean", async function () {
            const pHash = "0x" + "ee".repeat(32);
            await passport.updatePassportState(DEVICE_ID_A, true, true, pHash, 12);
            expect(await passport.hasVerifiedPassport(DEVICE_ID_A)).to.be.true;

            await passport.updatePassportState(DEVICE_ID_B, true, false, pHash, 8);
            expect(await passport.hasVerifiedPassport(DEVICE_ID_B)).to.be.false;
        });
    });

    // ─────────────────────────────────────────────────────────────────────
    // VAPIRewardDistributor
    // ─────────────────────────────────────────────────────────────────────

    describe("VAPIRewardDistributor", function () {

        it("test_10: updateDeviceState accumulates points with multiplier", async function () {
            // passport(1.5×) + enrollment(2.0×) = 3.0× → 5 sessions × 10 pts × 3.0 = 150 pts
            await reward.updateDeviceState(
                DEVICE_ID_A,
                5,      // nominalSessionsDelta
                true,   // passportHeld
                true,   // enrollmentComplete
                false,  // mpcVerified
                false,  // gatePassed
                3       // cleanStreakNow
            );
            await reward.setRewardAddress(DEVICE_ID_A, alice.address);
            const breakdown = await reward.getRewardBreakdown(DEVICE_ID_A);
            expect(breakdown.totalSessions).to.equal(5n);
            expect(breakdown.accPoints).to.be.gt(0n);
            // multiplier should be > 100 (base)
            expect(breakdown.multiplierX100).to.be.gt(100n);
        });

        it("test_11: claimReward reverts when token not set", async function () {
            await reward.updateDeviceState(DEVICE_ID_A, 100, false, false, false, false, 0);
            await reward.setRewardAddress(DEVICE_ID_A, alice.address);
            await expect(
                reward.connect(alice).claimReward(DEVICE_ID_A)
            ).to.be.revertedWith("VAPIRewardDistributor: token not set");
        });
    });

    // ─────────────────────────────────────────────────────────────────────
    // VAPIDataMarketplace
    // ─────────────────────────────────────────────────────────────────────

    describe("VAPIDataMarketplace", function () {

        it("test_12: registerDeveloper + purchaseAccess price matches table", async function () {
            await marketplace.registerDeveloper(alice.address);
            const p = await marketplace.participants(alice.address);
            expect(p.registered).to.be.true;
            expect(p.tier).to.equal(1n); // DEVELOPER

            // SESSION_DATA (0) for DEVELOPER (1) = 500 points
            const price = await marketplace.getPrice(1, 0);
            expect(price).to.equal(500n);

            // Credit points and purchase
            await marketplace.creditPoints(alice.address, 1000);
            const tx = await marketplace.connect(alice).purchaseAccess(0); // SESSION_DATA
            await tx.wait();
            const history = await marketplace.getPurchaseHistory(alice.address);
            expect(history.length).to.equal(1);
            const txRecord = await marketplace.getTransaction(history[0]);
            expect(txRecord.pricePoints).to.equal(500n);
        });
    });
});
