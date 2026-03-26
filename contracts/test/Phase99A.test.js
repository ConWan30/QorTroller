/**
 * Phase 99A — VAPIToken + VAPIOperatorRegistry + VAPIHardwareCertRegistry Tests
 *
 * 12 tests total (4 per contract):
 *
 * VAPIToken (4 tests):
 *   T99A-1: mint() up to MAX_SUPPLY succeeds
 *   T99A-2: mint() after completeTGE() reverts "TGE complete"
 *   T99A-3: completeTGE() by non-owner reverts Ownable
 *   T99A-4: mint() exceeding MAX_SUPPLY reverts "exceeds max supply"
 *
 * VAPIOperatorRegistry (4 tests):
 *   T99A-5: registerOperator() locks MINIMUM_STAKE — balance decreases, isOperator=true
 *   T99A-6: slash() burns 50%, transfers 50% to caller — balances verified
 *   T99A-7: slash() by non-owner reverts Ownable
 *   T99A-8: executeDeregister() before cooldown elapses reverts
 *
 * VAPIHardwareCertRegistry (4 tests):
 *   T99A-9:  certifyHardware() with valid profileHash — isCertified returns true
 *   T99A-10: certifyHardware() duplicate profileHash reverts "already certified"
 *   T99A-11: certifyHardware() with certLevel=0 reverts "invalid certLevel"
 *   T99A-12: revokeCertification() — isCertified returns false
 *
 * W1 invariant: each describe block deploys a fresh VAPIToken via beforeEach.
 * Never call completeTGE() in shared fixtures — it is irreversible and would
 * break all subsequent mint() calls on the same deployment.
 *
 * Hardhat count: 408 → 420 (+12)
 */

const { expect } = require("chai");
const { ethers } = require("hardhat");

const ONE_BILLION = ethers.parseEther("1000000000"); // 1B VAPI
const MIN_STAKE   = ethers.parseEther("10000");       // 10,000 VAPI
const THIRTY_DAYS = 30 * 24 * 60 * 60;               // seconds

// ─────────────────────────────────────────────────────────────────────────────
// VAPIToken Tests
// ─────────────────────────────────────────────────────────────────────────────

describe("Phase 99A — VAPIToken", function () {

    let owner, alice, bob;
    let token;

    // W1 invariant: fresh token deployment per test — completeTGE is irreversible
    beforeEach(async function () {
        [owner, alice, bob] = await ethers.getSigners();
        const Factory = await ethers.getContractFactory("VAPIToken");
        token = await Factory.deploy(owner.address);
        await token.waitForDeployment();
    });

    it("T99A-1: mint() up to MAX_SUPPLY succeeds", async function () {
        // Mint the full 1B supply to alice
        await token.mint(alice.address, ONE_BILLION);
        expect(await token.totalSupply()).to.equal(ONE_BILLION);
        expect(await token.balanceOf(alice.address)).to.equal(ONE_BILLION);
        expect(await token.MAX_SUPPLY()).to.equal(ONE_BILLION);
    });

    it("T99A-2: mint() after completeTGE() reverts", async function () {
        await token.mint(alice.address, ethers.parseEther("1000")); // partial mint
        await token.completeTGE();

        // tgeComplete should now be true
        expect(await token.tgeComplete()).to.equal(true);

        // Further minting must revert
        await expect(
            token.mint(alice.address, ethers.parseEther("1"))
        ).to.be.revertedWith("VAPIToken: TGE complete, no further minting");
    });

    it("T99A-3: completeTGE() by non-owner reverts OwnableUnauthorizedAccount", async function () {
        await expect(
            token.connect(alice).completeTGE()
        ).to.be.revertedWithCustomError(token, "OwnableUnauthorizedAccount");
    });

    it("T99A-4: mint() exceeding MAX_SUPPLY reverts", async function () {
        // Mint MAX_SUPPLY first
        await token.mint(owner.address, ONE_BILLION);
        // Any additional mint should revert
        await expect(
            token.mint(alice.address, 1n)
        ).to.be.revertedWith("VAPIToken: exceeds max supply");
    });
});

// ─────────────────────────────────────────────────────────────────────────────
// VAPIOperatorRegistry Tests
// ─────────────────────────────────────────────────────────────────────────────

describe("Phase 99A — VAPIOperatorRegistry", function () {

    let owner, alice, bob;
    let token, registry;

    // W1 invariant: fresh token + registry per test
    beforeEach(async function () {
        [owner, alice, bob] = await ethers.getSigners();

        // Fresh token
        const TokenFactory = await ethers.getContractFactory("VAPIToken");
        token = await TokenFactory.deploy(owner.address);
        await token.waitForDeployment();
        const tokenAddr = await token.getAddress();

        // Fresh registry
        const RegFactory = await ethers.getContractFactory("VAPIOperatorRegistry");
        registry = await RegFactory.deploy(tokenAddr, owner.address);
        await registry.waitForDeployment();

        // Mint 50,000 VAPI to alice for staking tests
        await token.mint(alice.address, ethers.parseEther("50000"));
        // Approve registry to spend alice's stake
        await token.connect(alice).approve(
            await registry.getAddress(),
            MIN_STAKE
        );
    });

    it("T99A-5: registerOperator() locks MINIMUM_STAKE, isOperator=true", async function () {
        const balanceBefore = await token.balanceOf(alice.address);

        await registry.connect(alice).registerOperator();

        const balanceAfter = await token.balanceOf(alice.address);
        expect(balanceBefore - balanceAfter).to.equal(MIN_STAKE);
        expect(await registry.isOperator(alice.address)).to.equal(true);

        const stake = await registry.stakes(alice.address);
        expect(stake.amount).to.equal(MIN_STAKE);
        expect(stake.active).to.equal(true);
    });

    it("T99A-6: slash() burns 50% and transfers 50% to owner", async function () {
        // Alice registers
        await registry.connect(alice).registerOperator();

        const registryAddr = await registry.getAddress();
        const registryBalance = await token.balanceOf(registryAddr);
        const ownerBalanceBefore = await token.balanceOf(owner.address);
        const totalSupplyBefore = await token.totalSupply();

        // Owner slashes alice
        // Note: slash() calls vapiToken.burn(burnAmt) — which burns from registry's balance
        // The slash implementation transfers to self then burns, then transfers claimAmt to owner.
        // Let's verify net effect: 50% burned (supply drops), 50% goes to owner.
        await registry.slash(alice.address, "test_violation_t99a6");

        const totalSupplyAfter = await token.totalSupply();
        const ownerBalanceAfter = await token.balanceOf(owner.address);

        const burnAmt = MIN_STAKE / 2n;
        const claimAmt = MIN_STAKE - burnAmt;

        // Supply should drop by burn amount
        expect(totalSupplyBefore - totalSupplyAfter).to.equal(burnAmt);
        // Owner should receive claimAmt
        expect(ownerBalanceAfter - ownerBalanceBefore).to.equal(claimAmt);
        // alice should no longer be an active operator
        expect(await registry.isOperator(alice.address)).to.equal(false);
    });

    it("T99A-7: slash() by non-owner reverts OwnableUnauthorizedAccount", async function () {
        await registry.connect(alice).registerOperator();
        await expect(
            registry.connect(bob).slash(alice.address, "unauthorized")
        ).to.be.revertedWithCustomError(registry, "OwnableUnauthorizedAccount");
    });

    it("T99A-8: executeDeregister() before cooldown elapsed reverts", async function () {
        await registry.connect(alice).registerOperator();
        await registry.connect(alice).requestDeregister();

        // Attempt immediate deregister (cooldown = 30 days)
        await expect(
            registry.connect(alice).executeDeregister()
        ).to.be.revertedWith("VAPIOperatorRegistry: cooldown not elapsed");
    });
});

// ─────────────────────────────────────────────────────────────────────────────
// VAPIHardwareCertRegistry Tests
// ─────────────────────────────────────────────────────────────────────────────

describe("Phase 99A — VAPIHardwareCertRegistry", function () {

    let owner, alice, bob;
    let token, certRegistry;
    let profileHash;

    beforeEach(async function () {
        [owner, alice, bob] = await ethers.getSigners();

        // Fresh token (needed even if fee=0, constructor requires address)
        const TokenFactory = await ethers.getContractFactory("VAPIToken");
        token = await TokenFactory.deploy(owner.address);
        await token.waitForDeployment();
        const tokenAddr = await token.getAddress();

        // Fresh cert registry with zero fee (testnet mode)
        const CertFactory = await ethers.getContractFactory("VAPIHardwareCertRegistry");
        certRegistry = await CertFactory.deploy(tokenAddr, owner.address, 0n);
        await certRegistry.waitForDeployment();

        // Reference profile hash: DualShock Edge Level 1
        profileHash = ethers.keccak256(
            ethers.toUtf8Bytes("Sony:DualShock Edge CFI-ZCP1:01.04.00")
        );
    });

    it("T99A-9: certifyHardware() with valid profileHash — isCertified returns true", async function () {
        await certRegistry.connect(alice).certifyHardware(
            profileHash,
            1,
            "Sony",
            "DualShock Edge CFI-ZCP1",
            "01.04.00"
        );

        expect(await certRegistry.isCertified(profileHash)).to.equal(true);
        expect(await certRegistry.profileCount()).to.equal(1n);

        const profile = await certRegistry.profiles(profileHash);
        expect(profile.certLevel).to.equal(1);
        expect(profile.manufacturer).to.equal("Sony");
        expect(profile.active).to.equal(true);
    });

    it("T99A-10: certifyHardware() duplicate profileHash reverts", async function () {
        await certRegistry.connect(alice).certifyHardware(
            profileHash, 1, "Sony", "DualShock Edge CFI-ZCP1", "01.04.00"
        );

        await expect(
            certRegistry.connect(bob).certifyHardware(
                profileHash, 1, "Sony", "DualShock Edge CFI-ZCP1", "01.04.00"
            )
        ).to.be.revertedWith("VAPIHardwareCertRegistry: profile already certified");
    });

    it("T99A-11: certifyHardware() with certLevel=0 reverts invalid certLevel", async function () {
        await expect(
            certRegistry.certifyHardware(
                profileHash, 0, "Sony", "DualShock Edge CFI-ZCP1", "01.04.00"
            )
        ).to.be.revertedWith("VAPIHardwareCertRegistry: invalid certLevel (1 or 2)");
    });

    it("T99A-12: revokeCertification() — isCertified returns false", async function () {
        await certRegistry.connect(alice).certifyHardware(
            profileHash, 1, "Sony", "DualShock Edge CFI-ZCP1", "01.04.00"
        );
        expect(await certRegistry.isCertified(profileHash)).to.equal(true);

        await certRegistry.revokeCertification(profileHash);
        expect(await certRegistry.isCertified(profileHash)).to.equal(false);

        // Profile count still 1 (revoked != deleted)
        expect(await certRegistry.profileCount()).to.equal(1n);
        const profile = await certRegistry.profiles(profileHash);
        expect(profile.active).to.equal(false);
    });
});
