const { expect } = require("chai");
const { ethers } = require("hardhat");

describe("Phase238 — VAPIDataMarketplaceListings (PALL)", function () {
    let pall;
    let phase69;
    let adjReg;
    let operator;
    let curator;
    let gamer;
    let stranger;

    // Canonical anchor hashes (32-byte each)
    const SEPPROOF_HASH  = "0x" + "aa".repeat(32);
    const BIOMETRIC_HASH = "0x" + "bb".repeat(32);
    const CORPUS_HASH    = "0x" + "cc".repeat(32);
    const GIC_HASH       = "0x" + "dd".repeat(32);
    const IPFS_CID_HASH  = "0x" + "ee".repeat(32);
    const ZERO_HASH      = "0x" + "00".repeat(32);

    // CONSENT bitmask (Phase 237 enum: bit 0 TOURNAMENT, bit 1 RESEARCH, bit 2 MFR_CERT, bit 3 MARKETPLACE)
    const CONSENT_MARKETPLACE_ONLY = 1 << 3;        // bit 3 only — minimal valid
    const CONSENT_FULL = (1 << 3) | (1 << 1);        // MARKETPLACE + RESEARCH
    const CONSENT_NO_MARKETPLACE = (1 << 0) | (1 << 1);  // missing bit 3

    const DATA_CLASS_SESSION   = 0;
    const DATA_CLASS_BIOMETRIC = 4;
    const PHASE69_TIER_GAMER   = 2;

    const PRICE_5_IOTX_MICRO = 5_000_000n;  // 5 IOTX in micro-IOTX

    // Helper: compute a canonical 32-byte listing commitment for tests.
    // (We don't recompute the full LISTING-v1 SHA-256 in JS — we just use a
    //  unique 32-byte placeholder; the contract doesn't validate the
    //  commitment shape, only stores it as a key.)
    function makeListingCommitment(seed) {
        return ethers.keccak256(ethers.toUtf8Bytes(`listing_${seed}`));
    }

    beforeEach(async function () {
        [operator, curator, gamer, stranger] = await ethers.getSigners();

        // Deploy real AdjudicationRegistry (Phase 111 LIVE pattern)
        const AdjReg = await ethers.getContractFactory("AdjudicationRegistry");
        adjReg = await AdjReg.deploy();
        await adjReg.waitForDeployment();

        // Deploy real Phase 69 VAPIDataMarketplace (constructor takes operator + treasury)
        const Phase69 = await ethers.getContractFactory("VAPIDataMarketplace");
        phase69 = await Phase69.deploy(operator.address, operator.address);
        await phase69.waitForDeployment();

        // Register gamer in Phase 69 (self-service)
        await phase69.connect(gamer).registerAsGamer();

        // Deploy PALL extension
        const PALL = await ethers.getContractFactory("VAPIDataMarketplaceListings");
        pall = await PALL.deploy(
            await phase69.getAddress(),
            await adjReg.getAddress()
        );
        await pall.waitForDeployment();
    });

    // ─────────────────────────────────────────────────────────────────────
    // Basic deploy + admin
    // ─────────────────────────────────────────────────────────────────────

    it("T-238-MKT-HH-1: deploy succeeds; addresses immutable; operator = deployer", async function () {
        expect(await pall.getAddress()).to.be.properAddress;
        expect(await pall.phase69Marketplace()).to.equal(await phase69.getAddress());
        expect(await pall.adjudicationRegistry()).to.equal(await adjReg.getAddress());
        expect(await pall.operator()).to.equal(operator.address);
        expect(await pall.curator()).to.equal(ethers.ZeroAddress);  // curator unset by default
    });

    it("T-238-MKT-HH-2: zero-address constructor args revert", async function () {
        const PALL = await ethers.getContractFactory("VAPIDataMarketplaceListings");
        await expect(
            PALL.deploy(ethers.ZeroAddress, await adjReg.getAddress())
        ).to.be.revertedWith("PALL: phase69 zero");
        await expect(
            PALL.deploy(await phase69.getAddress(), ethers.ZeroAddress)
        ).to.be.revertedWith("PALL: adjReg zero");
    });

    // ─────────────────────────────────────────────────────────────────────
    // createListing — guards
    // ─────────────────────────────────────────────────────────────────────

    it("T-238-MKT-HH-3: createListing requires non-zero commitment", async function () {
        await expect(
            pall.connect(gamer).createListing(
                ZERO_HASH, ZERO_HASH, ZERO_HASH, ZERO_HASH, ZERO_HASH,
                CONSENT_MARKETPLACE_ONLY, DATA_CLASS_SESSION,
                PRICE_5_IOTX_MICRO, IPFS_CID_HASH, 1_778_000_000_000_000_000n,
            )
        ).to.be.revertedWith("PALL: zero commitment");
    });

    it("T-238-MKT-HH-4: createListing requires MARKETPLACE consent bit", async function () {
        const commit = makeListingCommitment("no_marketplace");
        await expect(
            pall.connect(gamer).createListing(
                commit, ZERO_HASH, ZERO_HASH, ZERO_HASH, ZERO_HASH,
                CONSENT_NO_MARKETPLACE,   // missing bit 3
                DATA_CLASS_SESSION, PRICE_5_IOTX_MICRO, IPFS_CID_HASH,
                1_778_000_000_000_000_000n,
            )
        ).to.be.revertedWith("PALL: MARKETPLACE consent bit required");
    });

    it("T-238-MKT-HH-5: createListing requires Phase 69 GAMER tier", async function () {
        const commit = makeListingCommitment("not_gamer");
        // stranger has not registered in Phase 69
        await expect(
            pall.connect(stranger).createListing(
                commit, ZERO_HASH, ZERO_HASH, ZERO_HASH, ZERO_HASH,
                CONSENT_MARKETPLACE_ONLY, DATA_CLASS_SESSION,
                PRICE_5_IOTX_MICRO, IPFS_CID_HASH, 1_778_000_000_000_000_000n,
            )
        ).to.be.revertedWith("PALL: not registered in Phase 69");
    });

    it("T-238-MKT-HH-6: createListing requires data_class in [0, 6]", async function () {
        const commit = makeListingCommitment("bad_class");
        await expect(
            pall.connect(gamer).createListing(
                commit, ZERO_HASH, ZERO_HASH, ZERO_HASH, ZERO_HASH,
                CONSENT_MARKETPLACE_ONLY, 7,   // out of range
                PRICE_5_IOTX_MICRO, IPFS_CID_HASH, 1_778_000_000_000_000_000n,
            )
        ).to.be.revertedWith("PALL: data_class out of range");
    });

    // ─────────────────────────────────────────────────────────────────────
    // Tier computation — anchor-count based
    // ─────────────────────────────────────────────────────────────────────

    it("T-238-MKT-HH-7: zero anchors -> Tier.Basic (multiplier 1.0x)", async function () {
        const commit = makeListingCommitment("basic");
        await pall.connect(gamer).createListing(
            commit, ZERO_HASH, ZERO_HASH, ZERO_HASH, ZERO_HASH,
            CONSENT_MARKETPLACE_ONLY, DATA_CLASS_SESSION,
            PRICE_5_IOTX_MICRO, IPFS_CID_HASH, 1_778_000_000_000_000_000n,
        );
        expect(await pall.getListingTier(commit)).to.equal(0n);  // Basic
        expect(await pall.getListingMultiplierBps(commit)).to.equal(10000n);  // 1.0x
    });

    it("T-238-MKT-HH-8: 1 anchor recorded -> Tier.Verified (1.5x)", async function () {
        // Anchor only the corpus snapshot
        const dummyDevice = ethers.keccak256(ethers.toUtf8Bytes("VAPI_TEST"));
        await adjReg.recordAdjudication(dummyDevice, CORPUS_HASH, false);

        const commit = makeListingCommitment("verified");
        await pall.connect(gamer).createListing(
            commit, ZERO_HASH, ZERO_HASH, CORPUS_HASH, ZERO_HASH,
            CONSENT_MARKETPLACE_ONLY, DATA_CLASS_SESSION,
            PRICE_5_IOTX_MICRO, IPFS_CID_HASH, 1_778_000_000_000_000_000n,
        );
        expect(await pall.getListingTier(commit)).to.equal(1n);  // Verified
        expect(await pall.getListingMultiplierBps(commit)).to.equal(15000n);  // 1.5x
    });

    it("T-238-MKT-HH-9: 3 anchors recorded -> Tier.Attested (2.0x)", async function () {
        const dummyDevice = ethers.keccak256(ethers.toUtf8Bytes("VAPI_TEST"));
        await adjReg.recordAdjudication(dummyDevice, SEPPROOF_HASH, false);
        await adjReg.recordAdjudication(dummyDevice, BIOMETRIC_HASH, false);
        await adjReg.recordAdjudication(dummyDevice, CORPUS_HASH, false);
        // GIC NOT anchored

        const commit = makeListingCommitment("attested");
        await pall.connect(gamer).createListing(
            commit, SEPPROOF_HASH, BIOMETRIC_HASH, CORPUS_HASH, ZERO_HASH,
            CONSENT_FULL, DATA_CLASS_BIOMETRIC,
            PRICE_5_IOTX_MICRO, IPFS_CID_HASH, 1_778_000_000_000_000_000n,
        );
        expect(await pall.getListingTier(commit)).to.equal(2n);  // Attested
        expect(await pall.getListingMultiplierBps(commit)).to.equal(20000n);  // 2.0x
    });

    it("T-238-MKT-HH-10: 4 anchors recorded -> Tier.Premium (3.0x)", async function () {
        const dummyDevice = ethers.keccak256(ethers.toUtf8Bytes("VAPI_TEST"));
        await adjReg.recordAdjudication(dummyDevice, SEPPROOF_HASH, false);
        await adjReg.recordAdjudication(dummyDevice, BIOMETRIC_HASH, false);
        await adjReg.recordAdjudication(dummyDevice, CORPUS_HASH, false);
        await adjReg.recordAdjudication(dummyDevice, GIC_HASH, false);

        const commit = makeListingCommitment("premium");
        await pall.connect(gamer).createListing(
            commit, SEPPROOF_HASH, BIOMETRIC_HASH, CORPUS_HASH, GIC_HASH,
            CONSENT_FULL, DATA_CLASS_BIOMETRIC,
            PRICE_5_IOTX_MICRO * 2n, IPFS_CID_HASH, 1_778_000_000_000_000_000n,
        );
        expect(await pall.getListingTier(commit)).to.equal(3n);  // Premium
        expect(await pall.getListingMultiplierBps(commit)).to.equal(30000n);  // 3.0x
    });

    it("T-238-MKT-HH-11: anchor referenced but not recorded -> NOT counted", async function () {
        // Pass non-zero hashes that are NOT anchored on adjReg
        const commit = makeListingCommitment("ghost_anchors");
        await pall.connect(gamer).createListing(
            commit, SEPPROOF_HASH, BIOMETRIC_HASH, CORPUS_HASH, GIC_HASH,
            CONSENT_FULL, DATA_CLASS_BIOMETRIC,
            PRICE_5_IOTX_MICRO, IPFS_CID_HASH, 1_778_000_000_000_000_000n,
        );
        // None of those hashes were anchored -> tier should be Basic
        expect(await pall.getListingTier(commit)).to.equal(0n);
    });

    // ─────────────────────────────────────────────────────────────────────
    // Storage + indices
    // ─────────────────────────────────────────────────────────────────────

    it("T-238-MKT-HH-12: createListing emits ListingCreated with correct args", async function () {
        const commit = makeListingCommitment("event_check");
        const ts = 1_778_500_000_000_000_000n;
        await expect(
            pall.connect(gamer).createListing(
                commit, ZERO_HASH, ZERO_HASH, ZERO_HASH, ZERO_HASH,
                CONSENT_MARKETPLACE_ONLY, DATA_CLASS_SESSION,
                PRICE_5_IOTX_MICRO, IPFS_CID_HASH, ts,
            )
        ).to.emit(pall, "ListingCreated")
         .withArgs(commit, gamer.address, 0, DATA_CLASS_SESSION, PRICE_5_IOTX_MICRO, IPFS_CID_HASH);

        // Storage + indices
        expect(await pall.listingExists(commit)).to.equal(true);
        expect(await pall.getListingCount()).to.equal(1n);
        expect(await pall.getSellerListingCount(gamer.address)).to.equal(1n);
        const stored = await pall.listings(commit);
        expect(stored.seller).to.equal(gamer.address);
        expect(stored.priceMicroIotx).to.equal(PRICE_5_IOTX_MICRO);
        expect(stored.suspended).to.equal(false);
    });

    it("T-238-MKT-HH-13: duplicate listing commitment reverts", async function () {
        const commit = makeListingCommitment("dup");
        await pall.connect(gamer).createListing(
            commit, ZERO_HASH, ZERO_HASH, ZERO_HASH, ZERO_HASH,
            CONSENT_MARKETPLACE_ONLY, DATA_CLASS_SESSION,
            PRICE_5_IOTX_MICRO, IPFS_CID_HASH, 1_778_000_000_000_000_000n,
        );
        await expect(
            pall.connect(gamer).createListing(
                commit, ZERO_HASH, ZERO_HASH, ZERO_HASH, ZERO_HASH,
                CONSENT_MARKETPLACE_ONLY, DATA_CLASS_SESSION,
                PRICE_5_IOTX_MICRO, IPFS_CID_HASH, 1_778_000_000_000_000_000n,
            )
        ).to.be.revertedWith("PALL: listing exists");
    });

    // ─────────────────────────────────────────────────────────────────────
    // Suspension (operator + curator forward-compat)
    // ─────────────────────────────────────────────────────────────────────

    it("T-238-MKT-HH-14: operator can suspend listing; emits ListingSuspended", async function () {
        const commit = makeListingCommitment("to_suspend");
        await pall.connect(gamer).createListing(
            commit, ZERO_HASH, ZERO_HASH, ZERO_HASH, ZERO_HASH,
            CONSENT_MARKETPLACE_ONLY, DATA_CLASS_SESSION,
            PRICE_5_IOTX_MICRO, IPFS_CID_HASH, 1_778_000_000_000_000_000n,
        );
        await expect(
            pall.connect(operator).suspendListing(commit, "fraud_detected")
        ).to.emit(pall, "ListingSuspended")
         .withArgs(commit, operator.address, "fraud_detected");

        const stored = await pall.listings(commit);
        expect(stored.suspended).to.equal(true);
    });

    it("T-238-MKT-HH-15: stranger cannot suspend (only operator/curator)", async function () {
        const commit = makeListingCommitment("protected");
        await pall.connect(gamer).createListing(
            commit, ZERO_HASH, ZERO_HASH, ZERO_HASH, ZERO_HASH,
            CONSENT_MARKETPLACE_ONLY, DATA_CLASS_SESSION,
            PRICE_5_IOTX_MICRO, IPFS_CID_HASH, 1_778_000_000_000_000_000n,
        );
        await expect(
            pall.connect(stranger).suspendListing(commit, "should_revert")
        ).to.be.revertedWith("PALL: not operator or curator");
    });

    it("T-238-MKT-HH-16: setCurator + curator can suspend (Step I forward-compat)", async function () {
        // operator sets curator address — Phase 238 Step I will use this
        await expect(pall.connect(operator).setCurator(curator.address))
            .to.emit(pall, "CuratorTransferred")
            .withArgs(ethers.ZeroAddress, curator.address);
        expect(await pall.curator()).to.equal(curator.address);

        // Curator can now suspend listings
        const commit = makeListingCommitment("curator_suspend");
        await pall.connect(gamer).createListing(
            commit, ZERO_HASH, ZERO_HASH, ZERO_HASH, ZERO_HASH,
            CONSENT_MARKETPLACE_ONLY, DATA_CLASS_SESSION,
            PRICE_5_IOTX_MICRO, IPFS_CID_HASH, 1_778_000_000_000_000_000n,
        );
        await expect(
            pall.connect(curator).suspendListing(commit, "curator_flag")
        ).to.emit(pall, "ListingSuspended");

        // But curator CANNOT setOperator (operator-only)
        await expect(
            pall.connect(curator).setOperator(stranger.address)
        ).to.be.revertedWith("PALL: not operator");
    });

    it("T-238-MKT-HH-17: getListingTier reverts for non-existent listing", async function () {
        const ghostCommit = makeListingCommitment("ghost");
        await expect(
            pall.getListingTier(ghostCommit)
        ).to.be.revertedWith("PALL: listing not found");
    });

    it("T-238-MKT-HH-18: cannot suspend twice", async function () {
        const commit = makeListingCommitment("double_suspend");
        await pall.connect(gamer).createListing(
            commit, ZERO_HASH, ZERO_HASH, ZERO_HASH, ZERO_HASH,
            CONSENT_MARKETPLACE_ONLY, DATA_CLASS_SESSION,
            PRICE_5_IOTX_MICRO, IPFS_CID_HASH, 1_778_000_000_000_000_000n,
        );
        await pall.connect(operator).suspendListing(commit, "first");
        await expect(
            pall.connect(operator).suspendListing(commit, "second")
        ).to.be.revertedWith("PALL: already suspended");
    });
});
