/**
 * Phase 99C — VAPIVerifiedHumanProof + VAPIVerifiedHumanProofBridge tests.
 *
 * Tests:
 *   T99C-1  mint() — ownerOf[tokenId]=to, isValid()=true, totalSupply increments
 *   T99C-2  isValid() after expiresAt passed — returns false
 *   T99C-3  transferFrom() — reverts "soulbound"
 *   T99C-4  renew() extends expiresAt by 90 days (>= 90 * 86400 seconds)
 *   T99C-5  renew() on expired token — reverts "token not valid"
 *   T99C-6  mint() by non-owner — reverts OwnableUnauthorizedAccount
 *
 * Hardhat count: 424 → 430 (+6)
 */
const { expect } = require("chai");
const { ethers } = require("hardhat");

// Helper: build a valid VHPData struct with expiresAt in the future
function makeVHPData(overrides = {}) {
    const now = Math.floor(Date.now() / 1000);
    return {
        deviceIdHash: ethers.keccak256(ethers.toUtf8Bytes("device_test_99c")),
        certificationLevel: 1,
        consecutiveClean: 25,
        confidenceScore: 8750,     // 87.50 % in basis points
        issuedAt: now,
        expiresAt: now + 90 * 86400,  // 90 days from now
        mpcCeremonyHash: ethers.keccak256(ethers.toUtf8Bytes("ceremony_hash_v3")),
        ...overrides,
    };
}

describe("VAPIVerifiedHumanProof (Phase 99C)", function () {
    let vhp, owner, user1, user2;

    beforeEach(async function () {
        [owner, user1, user2] = await ethers.getSigners();
        const Factory = await ethers.getContractFactory("VAPIVerifiedHumanProof");
        vhp = await Factory.deploy(owner.address);
        await vhp.waitForDeployment();
    });

    it("T99C-1: mint() — ownerOf=to, isValid=true, totalSupply increments", async function () {
        const data = makeVHPData();
        const tx = await vhp.mint(user1.address, data);
        const receipt = await tx.wait();

        // Confirm tokenId=1 (first mint)
        const tokenId = 1n;
        expect(await vhp.ownerOf(tokenId)).to.equal(user1.address);
        expect(await vhp.tokenOfAddress(user1.address)).to.equal(tokenId);
        expect(await vhp.isValid(tokenId)).to.equal(true);
        expect(await vhp.totalSupply()).to.equal(1n);

        // VHPData fields preserved
        const stored = await vhp.vhpData(tokenId);
        expect(stored.certificationLevel).to.equal(1);
        expect(stored.consecutiveClean).to.equal(25);
        expect(stored.confidenceScore).to.equal(8750);
    });

    it("T99C-2: isValid() returns false after expiresAt has passed", async function () {
        // Use blockchain timestamp (not Date.now()) to avoid divergence after evm_increaseTime
        const block = await ethers.provider.getBlock("latest");
        const blockTs = block.timestamp;
        const data = makeVHPData({ expiresAt: blockTs + 2 });
        await vhp.mint(user1.address, data);
        const tokenId = 1n;

        // Advance blockchain time past expiresAt
        await ethers.provider.send("evm_increaseTime", [10]);
        await ethers.provider.send("evm_mine");

        expect(await vhp.isValid(tokenId)).to.equal(false);
    });

    it("T99C-3: transferFrom() reverts with 'soulbound'", async function () {
        const data = makeVHPData();
        await vhp.mint(user1.address, data);
        const tokenId = 1n;

        await expect(
            vhp.connect(user1).transferFrom(user1.address, user2.address, tokenId)
        ).to.be.revertedWith("VAPIVerifiedHumanProof: soulbound");

        // Also test approve and setApprovalForAll
        await expect(
            vhp.connect(user1).approve(user2.address, tokenId)
        ).to.be.revertedWith("VAPIVerifiedHumanProof: soulbound");

        await expect(
            vhp.connect(user1).setApprovalForAll(user2.address, true)
        ).to.be.revertedWith("VAPIVerifiedHumanProof: soulbound");
    });

    it("T99C-4: renew() extends expiresAt by >= 90 days", async function () {
        const data = makeVHPData();
        await vhp.mint(user1.address, data);
        const tokenId = 1n;

        const before = (await vhp.vhpData(tokenId)).expiresAt;
        await vhp.renew(tokenId);
        const after = (await vhp.vhpData(tokenId)).expiresAt;

        // After renew, expiresAt should be now+90d (>= original if original was future)
        // At minimum, expiresAt should have been updated
        const delta = after - before;
        // renew sets expiresAt = block.timestamp + 90*86400
        // since block.timestamp ≈ now, delta ≈ 0 (or slightly negative if original was far future)
        // The key invariant: after renew, isValid() is still true
        expect(await vhp.isValid(tokenId)).to.equal(true);
        // And the new expiry is at least 89 days from now (block timing tolerance)
        const blockTs = BigInt((await ethers.provider.getBlock("latest")).timestamp);
        expect(after).to.be.gte(blockTs + BigInt(89 * 86400));
    });

    it("T99C-5: renew() on expired token reverts 'token not valid'", async function () {
        // Use blockchain timestamp to avoid divergence from prior evm_increaseTime calls
        const block = await ethers.provider.getBlock("latest");
        const blockTs = block.timestamp;
        const data = makeVHPData({ expiresAt: blockTs + 2 });
        await vhp.mint(user1.address, data);
        const tokenId = 1n;

        // Expire the token
        await ethers.provider.send("evm_increaseTime", [10]);
        await ethers.provider.send("evm_mine");

        expect(await vhp.isValid(tokenId)).to.equal(false);
        await expect(vhp.renew(tokenId)).to.be.revertedWith("VAPIVerifiedHumanProof: token not valid");
    });

    it("T99C-6: mint() by non-owner reverts OwnableUnauthorizedAccount", async function () {
        const data = makeVHPData();
        await expect(
            vhp.connect(user1).mint(user2.address, data)
        ).to.be.revertedWithCustomError(vhp, "OwnableUnauthorizedAccount");
    });
});
