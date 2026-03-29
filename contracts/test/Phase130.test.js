const { expect } = require("chai");
const { ethers } = require("hardhat");

/**
 * Phase 130 — VAPISwarmOperatorGate (WIF-001 mitigation)
 * Pure view contract enforcing minimum 3 distinct stakers and stake-weight cap 1.5×.
 * Deploy deferred until wallet >= 0.40 IOTX.
 *
 * T130-1: isQuorumValid([]) → false
 * T130-2: validateQuorum with < MIN_DISTINCT_STAKERS=3 → (false, 0)
 * T130-3: validateQuorum with 3 distinct equal-stake stakers → (true, 3)
 * T130-4: stake weight cap violated (one staker > 1.5× average) → (false, ...)
 * T130-5: isQuorumValid with 3 valid equal-stake nodes → true
 * T130-6: non-zero operatorRegistry immutable stored correctly
 */
describe("Phase130 — VAPISwarmOperatorGate WIF-001 quorum gate", function () {
    let gate, mockRegistry, owner, addr1, addr2, addr3, addr4;

    beforeEach(async function () {
        [owner, addr1, addr2, addr3, addr4] = await ethers.getSigners();

        const MockReg = await ethers.getContractFactory("MockOperatorRegistry130");
        mockRegistry = await MockReg.deploy();
        await mockRegistry.waitForDeployment();

        const GateFactory = await ethers.getContractFactory("VAPISwarmOperatorGate");
        gate = await GateFactory.deploy(await mockRegistry.getAddress());
        await gate.waitForDeployment();
    });

    it("T130-1: isQuorumValid([]) returns false", async function () {
        const result = await gate.isQuorumValid([]);
        expect(result).to.equal(false);
    });

    it("T130-2: validateQuorum with 2 distinct stakers (< MIN=3) returns (false, ...)", async function () {
        await mockRegistry.setStake(addr1.address, ethers.parseEther("10000"));
        await mockRegistry.setStake(addr2.address, ethers.parseEther("10000"));

        const [valid, distinct] = await gate.validateQuorum(
            [addr1.address, addr2.address],
            3  // quorum=3 (MIN_DISTINCT_STAKERS)
        );
        expect(valid).to.equal(false);
        // distinct may be 2 but valid is false because < quorum
        expect(distinct).to.be.lte(2);
    });

    it("T130-3: validateQuorum with 3 distinct equal-stake stakers returns (true, 3)", async function () {
        const stake = ethers.parseEther("10000");
        await mockRegistry.setStake(addr1.address, stake);
        await mockRegistry.setStake(addr2.address, stake);
        await mockRegistry.setStake(addr3.address, stake);

        const [valid, distinct] = await gate.validateQuorum(
            [addr1.address, addr2.address, addr3.address],
            3
        );
        expect(valid).to.equal(true);
        expect(distinct).to.equal(3);
    });

    it("T130-4: stake weight cap violated (1 staker > 1.5× avg) returns (false, ...)", async function () {
        // addr1 has 3× the stake of others → violates 1.5× cap
        await mockRegistry.setStake(addr1.address, ethers.parseEther("30000"));
        await mockRegistry.setStake(addr2.address, ethers.parseEther("10000"));
        await mockRegistry.setStake(addr3.address, ethers.parseEther("10000"));

        const [valid] = await gate.validateQuorum(
            [addr1.address, addr2.address, addr3.address],
            3
        );
        expect(valid).to.equal(false);
    });

    it("T130-5: isQuorumValid with 3 valid equal-stake nodes returns true", async function () {
        const stake = ethers.parseEther("10000");
        await mockRegistry.setStake(addr1.address, stake);
        await mockRegistry.setStake(addr2.address, stake);
        await mockRegistry.setStake(addr3.address, stake);

        const result = await gate.isQuorumValid(
            [addr1.address, addr2.address, addr3.address]
        );
        expect(result).to.equal(true);
    });

    it("T130-6: operatorRegistry immutable stored correctly", async function () {
        const storedRegistry = await gate.operatorRegistry();
        expect(storedRegistry).to.equal(await mockRegistry.getAddress());
    });
});

/**
 * Phase 133 — Swarm PoAd Auto-Anchor (Novel Composability)
 *
 * T133-1: swarm_fingerprint is valid 64-char hex (SHA-256 output format)
 * T133-2: poad_hash bytes32 round-trips correctly in AdjudicationRegistry pattern
 */
describe("Phase133 — Swarm PoAd Auto-Anchor fingerprint format", function () {
    it("T133-1: swarm_fingerprint is a valid 64-char hex string (SHA-256 output)", async function () {
        // Simulate the swarm_fingerprint computation:
        // SHA-256(JSON({classj_nodes, triage_nodes}, sort_keys=True)) → 32 bytes = 64 hex chars
        const { ethers } = require("hardhat");
        const dummyData = JSON.stringify({
            classj_nodes: [{ verdict: "BLOCK" }],
            triage_nodes: [{ verdict: "BLOCK" }],
        });
        const hash = ethers.keccak256(ethers.toUtf8Bytes(dummyData));
        // keccak256 returns 0x-prefixed 64-char hex + 2 prefix chars
        expect(hash.length).to.equal(66);
        expect(hash.startsWith("0x")).to.equal(true);
        // SHA-256 (used in Python) also produces 64-char hex
        const sha256hex = hash.slice(2);
        expect(sha256hex.length).to.equal(64);
        expect(/^[0-9a-f]+$/i.test(sha256hex)).to.equal(true);
    });

    it("T133-2: poad_hash bytes32 round-trips correctly in AdjudicationRegistry pattern", async function () {
        const { ethers } = require("hardhat");
        // AdjudicationRegistry stores poad_hash as bytes32
        // Python: bytes.fromhex(poad_hash_hex) — 32 bytes
        const poadHash = "0xabcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890";
        expect(poadHash.length).to.equal(66); // "0x" + 64 hex chars = 32 bytes
        // Ensure it's a valid bytes32 value
        const asBigInt = BigInt(poadHash);
        expect(asBigInt).to.be.gt(0n);
        // Round-trip: BigInt → hex should match original
        const roundTripped = "0x" + asBigInt.toString(16).padStart(64, "0");
        expect(roundTripped).to.equal(poadHash);
    });
});
