/**
 * Phase O4-VPM-INT-B-PREP — Defensive additions tests
 *
 * Stream B fallback path (per approved plan Risk #3): full LayerZero V2
 * OApp inheritance is BLOCKED upstream by a peer-dep conflict between
 * @layerzerolabs/lz-evm-oapp-v2's transitive @eth-optimism/contracts
 * (requires ethers v5) and @nomicfoundation/hardhat-toolbox@4.0
 * (requires ethers v6). npm refuses to resolve both.
 *
 * This test band exercises the defensive additions shipped INSTEAD of
 * the full refactor:
 *   - MockLayerZeroEndpoint.sol (test infrastructure)
 *   - bridgeMint() + onlyBridge modifier on VAPIVerifiedHumanProof.sol
 *   - setBridgeAddress() owner-gated bridge authority configuration
 *
 * Once the upstream dep conflict resolves, the bridge contract itself
 * (VAPIVerifiedHumanProofBridge.sol) gets the full OApp refactor; this
 * test band's MockLayerZeroEndpoint + bridgeMint contracts plug
 * directly into that refactor's test pattern without changes.
 */
const { expect } = require("chai");
const { ethers } = require("hardhat");

describe("Phase O4-VPM-INT-B-PREP — Defensive bridge additions", function () {

    describe("MockLayerZeroEndpoint", function () {
        let mockLZ;
        let owner;
        let nonOwner;

        beforeEach(async function () {
            [owner, nonOwner] = await ethers.getSigners();
            const MockLZ = await ethers.getContractFactory("MockLayerZeroEndpoint");
            mockLZ = await MockLZ.deploy();
            await mockLZ.waitForDeployment();
        });

        it("1. deploys with zero sent count + zero global nonce", async function () {
            expect(await mockLZ.sentCount()).to.equal(0n);
            expect(await mockLZ.globalNonce()).to.equal(0n);
        });

        it("2. send() records MessagingParams + emits Sent event", async function () {
            const params = {
                dstEid: 30101n,
                receiver: ethers.zeroPadValue(owner.address, 32),
                message: ethers.toUtf8Bytes("test_message"),
                options: ethers.toUtf8Bytes("test_options"),
                payInLzToken: false,
            };
            await expect(
                mockLZ.send(params, owner.address, { value: ethers.parseEther("0.001") })
            ).to.emit(mockLZ, "Sent")
                .withArgs(owner.address, 30101n, params.receiver, 1n);

            expect(await mockLZ.sentCount()).to.equal(1n);
            expect(await mockLZ.globalNonce()).to.equal(1n);
        });

        it("3. send() rejects zero dstEid", async function () {
            const params = {
                dstEid: 0n,
                receiver: ethers.zeroPadValue(owner.address, 32),
                message: ethers.toUtf8Bytes("x"),
                options: ethers.toUtf8Bytes(""),
                payInLzToken: false,
            };
            await expect(
                mockLZ.send(params, owner.address)
            ).to.be.revertedWith("MockLZ: zero dstEid");
        });

        it("4. send() rejects zero receiver", async function () {
            const params = {
                dstEid: 30101n,
                receiver: ethers.ZeroHash,
                message: ethers.toUtf8Bytes("x"),
                options: ethers.toUtf8Bytes(""),
                payInLzToken: false,
            };
            await expect(
                mockLZ.send(params, owner.address)
            ).to.be.revertedWith("MockLZ: zero receiver");
        });

        it("5. send() rejects zero refund addr", async function () {
            const params = {
                dstEid: 30101n,
                receiver: ethers.zeroPadValue(owner.address, 32),
                message: ethers.toUtf8Bytes("x"),
                options: ethers.toUtf8Bytes(""),
                payInLzToken: false,
            };
            await expect(
                mockLZ.send(params, ethers.ZeroAddress)
            ).to.be.revertedWith("MockLZ: zero refund addr");
        });

        it("6. quote() returns plausible fee shape", async function () {
            const params = {
                dstEid: 30101n,
                receiver: ethers.zeroPadValue(owner.address, 32),
                message: ethers.toUtf8Bytes("x"),
                options: ethers.toUtf8Bytes(""),
                payInLzToken: false,
            };
            const [nativeFee, lzTokenFee] = await mockLZ.quote(params, owner.address);
            expect(nativeFee).to.equal(ethers.parseEther("0.001"));
            expect(lzTokenFee).to.equal(0n);
        });

        it("7. nonce increments monotonically across multiple send() calls", async function () {
            const params = {
                dstEid: 30101n,
                receiver: ethers.zeroPadValue(owner.address, 32),
                message: ethers.toUtf8Bytes("x"),
                options: ethers.toUtf8Bytes(""),
                payInLzToken: false,
            };
            await mockLZ.send(params, owner.address);
            await mockLZ.send(params, owner.address);
            await mockLZ.send(params, owner.address);
            expect(await mockLZ.globalNonce()).to.equal(3n);
            expect(await mockLZ.sentCount()).to.equal(3n);
        });
    });

    describe("VAPIVerifiedHumanProof - bridgeMint additions", function () {
        let vhp;
        let owner;
        let bridge;
        let recipient;
        let nonBridge;
        const futureTimestamp = Math.floor(Date.now() / 1000) + 90 * 86400;
        const deviceHash = ethers.keccak256(ethers.toUtf8Bytes("test_device_001"));
        const ceremonyHash = ethers.keccak256(ethers.toUtf8Bytes("test_ceremony"));

        function _vhpData() {
            return {
                deviceIdHash: deviceHash,
                certificationLevel: 1,
                consecutiveClean: 100,
                confidenceScore: 9500,
                issuedAt: Math.floor(Date.now() / 1000),
                expiresAt: futureTimestamp,
                mpcCeremonyHash: ceremonyHash,
            };
        }

        beforeEach(async function () {
            [owner, bridge, recipient, nonBridge] = await ethers.getSigners();
            const VHP = await ethers.getContractFactory("VAPIVerifiedHumanProof");
            vhp = await VHP.deploy(owner.address);
            await vhp.waitForDeployment();
        });

        it("8. bridgeAddress is zero on deploy", async function () {
            expect(await vhp.bridgeAddress()).to.equal(ethers.ZeroAddress);
        });

        it("9. bridgeMint reverts when bridge not configured", async function () {
            await expect(
                vhp.bridgeMint(recipient.address, _vhpData(), 1n)
            ).to.be.revertedWith("VAPIVerifiedHumanProof: bridge not configured");
        });

        it("10. setBridgeAddress emits BridgeAddressSet + persists state", async function () {
            await expect(vhp.setBridgeAddress(bridge.address))
                .to.emit(vhp, "BridgeAddressSet")
                .withArgs(ethers.ZeroAddress, bridge.address);
            expect(await vhp.bridgeAddress()).to.equal(bridge.address);
        });

        it("11. setBridgeAddress rejects zero address", async function () {
            await expect(
                vhp.setBridgeAddress(ethers.ZeroAddress)
            ).to.be.revertedWith("VAPIVerifiedHumanProof: zero bridge");
        });

        it("12. setBridgeAddress is onlyOwner", async function () {
            await expect(
                vhp.connect(nonBridge).setBridgeAddress(bridge.address)
            ).to.be.revertedWithCustomError(vhp, "OwnableUnauthorizedAccount");
        });

        it("13. bridgeMint rejects calls from non-bridge address even once configured", async function () {
            await vhp.setBridgeAddress(bridge.address);
            await expect(
                vhp.connect(nonBridge).bridgeMint(recipient.address, _vhpData(), 1n)
            ).to.be.revertedWith("VAPIVerifiedHumanProof: caller not bridge");
        });

        it("14. bridgeMint succeeds when called by configured bridge address", async function () {
            await vhp.setBridgeAddress(bridge.address);

            const tx = await vhp.connect(bridge).bridgeMint(
                recipient.address, _vhpData(), 42n
            );
            await expect(tx).to.emit(vhp, "VHPMinted");
            await expect(tx).to.emit(vhp, "VHPBridgeMinted")
                .withArgs(1n, recipient.address, deviceHash, 42n);

            // Mint succeeded — recipient owns the token
            expect(await vhp.ownerOf(1n)).to.equal(recipient.address);
            expect(await vhp.isValid(1n)).to.equal(true);
            expect(await vhp.totalSupply()).to.equal(1n);
        });

        it("15. bridgeMint rejects zero recipient even when bridge is caller", async function () {
            await vhp.setBridgeAddress(bridge.address);
            await expect(
                vhp.connect(bridge).bridgeMint(ethers.ZeroAddress, _vhpData(), 1n)
            ).to.be.revertedWith("VAPIVerifiedHumanProof: zero address");
        });

        it("16. bridgeMint rejects already-expired tokens (receiver-side TTL check)", async function () {
            await vhp.setBridgeAddress(bridge.address);

            const expiredData = _vhpData();
            expiredData.expiresAt = Math.floor(Date.now() / 1000) - 1;

            await expect(
                vhp.connect(bridge).bridgeMint(recipient.address, expiredData, 1n)
            ).to.be.revertedWith("VAPIVerifiedHumanProof: already expired");
        });

        it("17. bridgeMint nonce is recorded in VHPBridgeMinted event for replay-guard inspection", async function () {
            await vhp.setBridgeAddress(bridge.address);

            const tx1 = await vhp.connect(bridge).bridgeMint(recipient.address, _vhpData(), 100n);
            await expect(tx1).to.emit(vhp, "VHPBridgeMinted")
                .withArgs(1n, recipient.address, deviceHash, 100n);

            // Different recipient + different nonce
            const [, , , , recipient2] = await ethers.getSigners();
            const tx2 = await vhp.connect(bridge).bridgeMint(recipient2.address, _vhpData(), 101n);
            await expect(tx2).to.emit(vhp, "VHPBridgeMinted")
                .withArgs(2n, recipient2.address, deviceHash, 101n);
        });

        it("18. setBridgeAddress can rotate bridge authority (emits old + new)", async function () {
            const [, , , , newBridge] = await ethers.getSigners();
            await vhp.setBridgeAddress(bridge.address);

            await expect(vhp.setBridgeAddress(newBridge.address))
                .to.emit(vhp, "BridgeAddressSet")
                .withArgs(bridge.address, newBridge.address);

            expect(await vhp.bridgeAddress()).to.equal(newBridge.address);

            // Old bridge no longer authorized
            await expect(
                vhp.connect(bridge).bridgeMint(recipient.address, _vhpData(), 1n)
            ).to.be.revertedWith("VAPIVerifiedHumanProof: caller not bridge");

            // New bridge IS authorized
            await vhp.connect(newBridge).bridgeMint(recipient.address, _vhpData(), 1n);
            expect(await vhp.totalSupply()).to.equal(1n);
        });

        it("19. owner mint() path UNAFFECTED by bridge additions (regression guard)", async function () {
            // owner mint should still work without any bridge configuration
            await vhp.mint(recipient.address, _vhpData());
            expect(await vhp.totalSupply()).to.equal(1n);
            expect(await vhp.ownerOf(1n)).to.equal(recipient.address);
        });
    });

    describe("MockLayerZeroEndpoint + VHP composition", function () {
        let mockLZ;
        let vhp;
        let owner;
        let recipient;

        beforeEach(async function () {
            [owner, , recipient] = await ethers.getSigners();
            const MockLZ = await ethers.getContractFactory("MockLayerZeroEndpoint");
            mockLZ = await MockLZ.deploy();
            await mockLZ.waitForDeployment();

            const VHP = await ethers.getContractFactory("VAPIVerifiedHumanProof");
            vhp = await VHP.deploy(owner.address);
            await vhp.waitForDeployment();
        });

        it("20. simulateInbound dispatches a payload at a target contract (test infra smoke)", async function () {
            // Simple smoke that the mock's simulateInbound can low-level-call a target.
            // We dispatch a setBridgeAddress call from the mock as if it were the bridge.
            // Production: _lzReceive on the bridge OApp would unmarshal a VHPData
            // payload + call vhp.bridgeMint. This smoke just verifies the dispatch path.
            const iface = vhp.interface;
            // encode a no-arg call (totalSupply) — simplest read; should succeed
            const calldata = iface.encodeFunctionData("totalSupply");
            const [success, returnData] = await mockLZ.simulateInbound.staticCall(
                await vhp.getAddress(), calldata,
            );
            expect(success).to.equal(true);
            // returnData decodes to uint256(0) — totalSupply on a fresh contract
            expect(returnData.length).to.be.greaterThan(0);
        });
    });
});
