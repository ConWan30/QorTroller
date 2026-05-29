const { expect } = require("chai");
const { ethers } = require("hardhat");

// ─────────────────────────────────────────────────────────────────────────────
// VAPIBuyerCategoryVerifier — Data Economy Arc 2
// Real Groth16 proof fixture (NOT a mock). Generated against the committed
// circuit VAPIBuyerCategoryVerifier.circom with:
//   buyerDID=12345678901234567890  categoryId=3 (ESPORTS)  claimedCategory=3
//   issuedAt=1700000000  expiresAt=1800000000  currentTimestamp=1750000000
//   credentialNonce=98765432109876543210
//   credentialCommitment = Poseidon(5)(buyerDID,categoryId,issuedAt,expiresAt,nonce)
//   nullifierHash        = Poseidon(2)(buyerDID,nonce)
// snarkjs groth16 verify reports OK against this fixture; the on-chain verifier
// must agree. Tampering ANY proof point or public signal must flip it to false.
//
// _pubSignals layout (circuit declares outputs first, then public inputs):
//   [0] valid (output, always 1)   [1] claimedCategory   [2] currentTimestamp
//   [3] credentialCommitment        [4] nullifierHash
// ─────────────────────────────────────────────────────────────────────────────
describe("VAPIBuyerCategoryVerifier — Arc 2 Groth16 (real proof)", function () {
    let verifier;

    const pA = [
        "0x1b28a05d2e24204767e3c55ac8da40b41f591bd52c16667bf24e1ae3915fe9d1",
        "0x1e8f4a10c51efff2d7beec2b5b9cf999cf0376f36dce9dbe142e4cfe9a96ed0a",
    ];
    const pB = [
        [
            "0x302b1599b3d8bdc669119aa5399a268be4fc49f2bb98899e83aa58c5a8799d4b",
            "0x23ced951255c684bb335051030ac8aa7b0665d1c84681264694ea1693b0cf078",
        ],
        [
            "0x048239ca136f269861af23e3b58d04c6ef2aef8241324fb32fe371d4bcc00301",
            "0x105276b4840911f09a63c1f55a0a051b0eb633c361bff6976f3ab994b5b808b0",
        ],
    ];
    const pC = [
        "0x0506015b8eedd7418b5b9b1caa942a1c37d6c3ba39a6aa7ae4bde1f5008ac20e",
        "0x14c1ad66bebd916bfc6842b072095a5ab46fad5f91c4fc7dd110f8689f5c25c7",
    ];
    const pubSignals = [
        "0x0000000000000000000000000000000000000000000000000000000000000001",
        "0x0000000000000000000000000000000000000000000000000000000000000003",
        "0x00000000000000000000000000000000000000000000000000000000684ee180",
        "0x2d22e513a5efb4ea6308c21458da2e569fc3e4928699a479623e389cef484e8f",
        "0x0fd56a897af5cb70f165c3f9a18b32e97c81dc5bc6c351dbef8fdfe43333922e",
    ];

    before(async function () {
        const Factory = await ethers.getContractFactory("VAPIBuyerCategoryVerifier");
        verifier = await Factory.deploy();
        await verifier.waitForDeployment();
    });

    it("T-BCV-1: verifies a valid Groth16 proof", async function () {
        expect(await verifier.verifyProof(pA, pB, pC, pubSignals)).to.equal(true);
    });

    it("T-BCV-2: rejects a tampered claimedCategory public signal", async function () {
        const bad = [...pubSignals];
        bad[1] = "0x0000000000000000000000000000000000000000000000000000000000000004";
        expect(await verifier.verifyProof(pA, pB, pC, bad)).to.equal(false);
    });

    it("T-BCV-3: rejects a tampered credentialCommitment public signal", async function () {
        const bad = [...pubSignals];
        bad[3] = "0x2d22e513a5efb4ea6308c21458da2e569fc3e4928699a479623e389cef484e90";
        expect(await verifier.verifyProof(pA, pB, pC, bad)).to.equal(false);
    });

    it("T-BCV-4: rejects a tampered nullifierHash public signal", async function () {
        const bad = [...pubSignals];
        bad[4] = "0x0fd56a897af5cb70f165c3f9a18b32e97c81dc5bc6c351dbef8fdfe43333922f";
        expect(await verifier.verifyProof(pA, pB, pC, bad)).to.equal(false);
    });

    it("T-BCV-5: rejects a tampered currentTimestamp public signal", async function () {
        const bad = [...pubSignals];
        bad[2] = "0x00000000000000000000000000000000000000000000000000000000684ee181";
        expect(await verifier.verifyProof(pA, pB, pC, bad)).to.equal(false);
    });

    it("T-BCV-6: rejects a tampered proof point (pA)", async function () {
        const badA = [
            "0x1b28a05d2e24204767e3c55ac8da40b41f591bd52c16667bf24e1ae3915fe9d2",
            pA[1],
        ];
        expect(await verifier.verifyProof(badA, pB, pC, pubSignals)).to.equal(false);
    });
});
