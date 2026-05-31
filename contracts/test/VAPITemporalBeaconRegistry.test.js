const { expect } = require("chai");
const { ethers } = require("hardhat");

describe("Arc 6 — VAPITemporalBeaconRegistry", function () {
    let reg;
    let owner, keeper, attacker;

    beforeEach(async function () {
        [owner, keeper, attacker] = await ethers.getSigners();
        const Factory = await ethers.getContractFactory("VAPITemporalBeaconRegistry");
        reg = await Factory.deploy(owner.address);
        await reg.waitForDeployment();
    });

    it("T-TBR-1: deploys with owner; initial state empty; no keeper set", async function () {
        expect(await reg.owner()).to.equal(owner.address);
        expect(await reg.keeper()).to.equal(ethers.ZeroAddress);
        expect(await reg.latestAnchoredBlock()).to.equal(0n);
    });

    it("T-TBR-2: BEACON_DOMAIN FROZEN at keccak256('VAPI-TEMPORAL-BEACON-v1') (INV-TBR-001)", async function () {
        const expected = ethers.keccak256(ethers.toUtf8Bytes("VAPI-TEMPORAL-BEACON-v1"));
        expect(await reg.BEACON_DOMAIN()).to.equal(expected);
    });

    it("T-TBR-3: ANCHOR_CADENCE FROZEN at 64 + BLOCKHASH_WINDOW = 256 (INV-TBR-002)", async function () {
        expect(await reg.ANCHOR_CADENCE()).to.equal(64n);
        expect(await reg.BLOCKHASH_WINDOW()).to.equal(256n);
    });

    it("T-TBR-4: setKeeper only by owner; emits KeeperSet(prev, new)", async function () {
        await expect(reg.connect(attacker).setKeeper(keeper.address))
            .to.be.revertedWithCustomError(reg, "OwnableUnauthorizedAccount");
        await expect(reg.connect(owner).setKeeper(keeper.address))
            .to.emit(reg, "KeeperSet")
            .withArgs(ethers.ZeroAddress, keeper.address);
        expect(await reg.keeper()).to.equal(keeper.address);
    });

    it("T-TBR-5: anchorBeacon refuses non-keeper", async function () {
        await reg.connect(owner).setKeeper(keeper.address);
        // Mine some blocks so blockhash is callable.
        for (let i = 0; i < 70; i++) await ethers.provider.send("evm_mine", []);
        const targetBlock = (await ethers.provider.getBlockNumber()) - 5;
        // Round down to a cadence multiple
        const cadenceBlock = targetBlock - (targetBlock % 64);
        await expect(reg.connect(attacker).anchorBeacon(cadenceBlock))
            .to.be.revertedWithCustomError(reg, "NotKeeper");
    });

    it("T-TBR-6: anchorBeacon refuses non-cadence block (% 64 != 0)", async function () {
        await reg.connect(owner).setKeeper(keeper.address);
        for (let i = 0; i < 70; i++) await ethers.provider.send("evm_mine", []);
        const cur = await ethers.provider.getBlockNumber();
        // Pick a block that is decidedly NOT a multiple of 64
        const nonCadence = cur - 3;  // recent + non-multiple
        // Ensure it isn't a multiple of 64 just in case
        const adjusted = (nonCadence % 64 === 0) ? nonCadence - 1 : nonCadence;
        await expect(reg.connect(keeper).anchorBeacon(adjusted))
            .to.be.revertedWithCustomError(reg, "NotCadenceBlock");
    });

    it("T-TBR-7: anchorBeacon refuses future block (regardless of cadence)", async function () {
        await reg.connect(owner).setKeeper(keeper.address);
        const cur = await ethers.provider.getBlockNumber();
        // Choose a future block that is BOTH > block.number AND a cadence
        // multiple — proves the future-block check fires regardless of
        // whether the cadence check would also reject the same input. The
        // require order in the contract is: NotKeeper -> FutureBlock ->
        // OutsideBlockhashWindow -> NotCadenceBlock, so FutureBlock must
        // surface first when applicable.
        let futureBlock = cur + 200;
        futureBlock = futureBlock - (futureBlock % 64);  // cadence-aligned
        if (futureBlock <= cur) futureBlock += 64;       // ensure strictly future
        await expect(reg.connect(keeper).anchorBeacon(futureBlock))
            .to.be.revertedWithCustomError(reg, "FutureBlock");
    });

    it("T-TBR-8: anchorBeacon refuses blocks outside the 256-block BLOCKHASH window", async function () {
        await reg.connect(owner).setKeeper(keeper.address);
        // Mine far past 256 so we have a stale cadence block
        for (let i = 0; i < 400; i++) await ethers.provider.send("evm_mine", []);
        // Pick a block strictly more than 256 in the past, on cadence
        const cur = await ethers.provider.getBlockNumber();
        // Aim for cur - 300, then round down to a multiple of 64
        let staleCandidate = cur - 300;
        staleCandidate = staleCandidate - (staleCandidate % 64);
        await expect(reg.connect(keeper).anchorBeacon(staleCandidate))
            .to.be.revertedWithCustomError(reg, "OutsideBlockhashWindow");
    });

    it("T-TBR-9: anchor succeeds + state updated + event emitted", async function () {
        await reg.connect(owner).setKeeper(keeper.address);
        for (let i = 0; i < 200; i++) await ethers.provider.send("evm_mine", []);
        const cur = await ethers.provider.getBlockNumber();
        // Pick the largest cadence-aligned block within window
        let target = cur - 10;
        target = target - (target % 64);
        // Read the chain's hash so we can assert event arg byte-perfect
        const expectedHash = (await ethers.provider.getBlock(target)).hash;
        await expect(reg.connect(keeper).anchorBeacon(target))
            .to.emit(reg, "BeaconAnchored")
            .withArgs(target, expectedHash);
        expect(await reg.anchoredHash(target)).to.equal(expectedHash);
        expect(await reg.latestAnchoredBlock()).to.equal(target);
        const [latestBlock, latestHash] = await reg.latestBeacon();
        expect(latestBlock).to.equal(target);
        expect(latestHash).to.equal(expectedHash);
    });

    it("T-TBR-10: verifyBeacon returns true for anchored hash; false otherwise", async function () {
        await reg.connect(owner).setKeeper(keeper.address);
        for (let i = 0; i < 200; i++) await ethers.provider.send("evm_mine", []);
        const cur = await ethers.provider.getBlockNumber();
        let target = cur - 10; target -= (target % 64);
        const expectedHash = (await ethers.provider.getBlock(target)).hash;
        await reg.connect(keeper).anchorBeacon(target);
        
        const mockPQ = ethers.id("mock-pq-commitment");
        
        expect(await reg.verifyBeacon(target, expectedHash, mockPQ)).to.equal(true);
        // Wrong hash → false
        expect(await reg.verifyBeacon(target, ethers.ZeroHash, mockPQ)).to.equal(false);
        // Unanchored block → false
        const otherTarget = target - 64;
        expect(await reg.verifyBeacon(otherTarget, expectedHash, mockPQ)).to.equal(false);
        
        // Zero commitment -> reverts
        await expect(reg.verifyBeacon(target, expectedHash, ethers.ZeroHash))
            .to.be.revertedWith("VAPI: Zero PQ Commitment Disallowed");
    });
});
