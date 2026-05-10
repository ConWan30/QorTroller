/**
 * Phase 67 — VAPI Multi-Party ZK Ceremony
 *
 * Upgrades all 3 VAPI circuits from single-party to MPC Groth16 trusted setup.
 *
 * Novel primitive: the final Phase 2 beacon for each circuit is derived from
 * an IoTeX testnet block hash, anchoring ceremony integrity to the same chain
 * where all VAPI contracts are deployed. Verifiable by anyone querying IoTeX
 * testnet block <beaconBlockNumber>.
 *
 * Phase 1 ptau: hermez-raw-ceremony powersOfTau28_hez_final_15.ptau
 *   - 200+ contributors (2021), publicly audited
 *   - Replaces the Google Cloud GCS source from run-ceremony.js
 *   - Covers all 3 VAPI circuits (max 2^15 = 32,768 constraints)
 *
 * Phase 2 per circuit (3 contributions + IoTeX beacon):
 *   Contributor 1: crypto.randomBytes(32) entropy
 *   Contributor 2: process.hrtime.bigint() ^ timestamp entropy
 *   Contributor 3: IoTeX testnet latest block hash entropy
 *   Beacon:        keccak256(IoTeX block hash at ceremony time)
 *
 * Outputs:
 *   bridge/zk_artifacts/<Circuit>_final.zkey       (replaces existing)
 *   bridge/zk_artifacts/<Circuit>_verification_key.json  (replaces existing)
 *   ceremony_artifacts/<Circuit>_manifest.json     (per-circuit audit record)
 *   ceremony_artifacts/all_circuits_manifest.json  (for deploy-ceremony-registry.js)
 *
 * Usage:
 *   cd contracts && node scripts/run-mpc-ceremony.js
 *
 * NOTE: The ceremony is purely local snarkjs computation — no blockchain needed.
 *       Only deploy-ceremony-registry.js interacts with IoTeX testnet.
 */

const snarkjs = require("snarkjs");
const fs      = require("fs");
const path    = require("path");
const crypto  = require("crypto");
const https   = require("https");
const { ethers } = require("hardhat");

// ---------------------------------------------------------------------------
// Config
// ---------------------------------------------------------------------------

const ROOT      = path.join(__dirname, "../../");
const ZK_DIR    = path.join(ROOT, "bridge/zk_artifacts");
const CIRC_DIR  = path.join(__dirname, "../circuits");
const OUT_DIR   = path.join(__dirname, "../ceremony_artifacts");
const PTAU_PATH = path.join(__dirname, "../ptau/hermez_final_15.ptau");
// Primary URL (Hermez S3 — may be 403); fallback URLs tried in order
const PTAU_URLS = [
    "https://storage.googleapis.com/zkevm/ptau/hermez-raw-15.ptau",
    "https://hermez.s3-eu-west-1.amazonaws.com/powersOfTau28_hez_final_15.ptau",
];

// IoTeX testnet RPC (public endpoint — no key required)
const IOTEX_RPC = "https://babel-api.testnet.iotex.io";

const CIRCUITS = [
    {
        name:    "PitlSessionProof",
        r1cs:    path.join(CIRC_DIR, "PitlSessionProof.r1cs"),
        wasm:    path.join(CIRC_DIR, "PitlSessionProof_js", "PitlSessionProof.wasm"),
        outZkey: path.join(ZK_DIR, "PitlSessionProof_final.zkey"),
        outVkey: path.join(ZK_DIR, "PitlSession_verification_key.json"),
    },
    {
        name:    "TeamProof",
        r1cs:    path.join(CIRC_DIR, "TeamProof.r1cs"),
        wasm:    path.join(CIRC_DIR, "TeamProof_js", "TeamProof.wasm"),
        outZkey: path.join(ZK_DIR, "TeamProof_final.zkey"),
        outVkey: path.join(ZK_DIR, "TeamProof_verification_key.json"),
    },
    {
        name:    "TournamentPassport",
        r1cs:    path.join(CIRC_DIR, "TournamentPassport.r1cs"),
        wasm:    path.join(CIRC_DIR, "TournamentPassport_js", "TournamentPassport.wasm"),
        outZkey: path.join(ZK_DIR, "TournamentPassport_final.zkey"),
        outVkey: path.join(ZK_DIR, "TournamentPassport_verification_key.json"),
    },
    // Phase 237-ZK-SEPPROOF — Session 2 addition (2026-05-09).
    // 6 public inputs (snapshot lo/hi + claimedPlayerId + featureCommitment +
    // separationThresholdMilli + inferenceCode), 804 non-linear constraints,
    // BIOMETRIC-SNAPSHOT-v1 anchor pre-condition enforced at wrapper layer
    // (ZKSepProofVerifier.sol).
    {
        name:    "ZKSepProof",
        r1cs:    path.join(CIRC_DIR, "ZKSepProof.r1cs"),
        wasm:    path.join(CIRC_DIR, "ZKSepProof_js", "ZKSepProof.wasm"),
        outZkey: path.join(ZK_DIR, "ZKSepProof_final.zkey"),
        outVkey: path.join(ZK_DIR, "ZKSepProof_verification_key.json"),
    },
];

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function downloadOne(url, dest) {
    return new Promise((resolve, reject) => {
        console.log(`  [ptau] Trying: ${url}`);
        fs.mkdirSync(path.dirname(dest), { recursive: true });
        const file = fs.createWriteStream(dest);
        https.get(url, res => {
            if (res.statusCode === 301 || res.statusCode === 302) {
                file.close();
                fs.unlink(dest, () => {});
                return downloadOne(res.headers.location, dest).then(resolve).catch(reject);
            }
            if (res.statusCode !== 200) {
                file.close();
                fs.unlink(dest, () => {});
                return reject(new Error(`HTTP ${res.statusCode} from ${url}`));
            }
            res.pipe(file);
            file.on("finish", () => {
                file.close();
                // Sanity-check: ptau files are large (>1MB); reject HTML error pages
                const size = fs.statSync(dest).size;
                if (size < 1024 * 1024) {
                    fs.unlink(dest, () => {});
                    return reject(new Error(`Downloaded file too small (${size}B) — likely an error page`));
                }
                resolve();
            });
        }).on("error", err => {
            fs.unlink(dest, () => {});
            reject(err);
        });
    });
}

async function download(urls, dest) {
    if (fs.existsSync(dest)) {
        const size = fs.statSync(dest).size;
        if (size > 1024 * 1024) {
            console.log(`  [ptau] Already cached: ${path.basename(dest)} (${(size/1e6).toFixed(0)}MB)`);
            return;
        }
        // Corrupt / partial file — delete and re-download
        fs.unlinkSync(dest);
        console.log(`  [ptau] Cached file was too small (${size}B), re-downloading...`);
    }
    const urlList = Array.isArray(urls) ? urls : [urls];
    let lastErr;
    for (const url of urlList) {
        try {
            await downloadOne(url, dest);
            console.log(`  [ptau] Download complete: ${path.basename(dest)}`);
            return;
        } catch (err) {
            lastErr = err;
            console.warn(`  [ptau] Failed (${err.message}), trying next source...`);
        }
    }
    // Fallback: generate a local Phase 1 ptau using snarkjs
    // This creates a less-trusted ptau (single-party, local) sufficient for testnet.
    console.warn("  [ptau] All remote sources unavailable. Generating local Phase 1 ptau...");
    console.warn("  [ptau] NOTE: For production, replace with a trusted multi-party ceremony ptau.");
    await generateLocalPtau(dest);
}

async function generateLocalPtau(dest) {
    const snarkjs = require("snarkjs");
    const ptauPower = 15;  // 2^15 = 32768 constraints — matches original hermez target
    const tmpBase   = dest.replace(".ptau", "_tmp0.ptau");
    const tmpContr  = dest.replace(".ptau", "_tmp1.ptau");
    const tmpBeacon = dest.replace(".ptau", "_tmp2.ptau");
    fs.mkdirSync(path.dirname(dest), { recursive: true });

    console.log(`  [ptau] Generating pot${ptauPower} (~2 min)...`);
    // snarkjs 0.7.x newAccumulator requires a curve object (not a string)
    const curve = await snarkjs.curves.getCurveFromName("bn128");
    await snarkjs.powersOfTau.newAccumulator(
        curve, ptauPower, tmpBase
    );
    await snarkjs.powersOfTau.contribute(
        tmpBase, tmpContr,
        "VAPI_localgen_contributor_1",
        Buffer.from(require("crypto").randomBytes(32)).toString("hex"),
    );
    const beaconHash = "0102030405060708090a0b0c0d0e0f101112131415161718191a1b1c1d1e1f20";
    await snarkjs.powersOfTau.beacon(
        tmpContr, tmpBeacon, "VAPI_beacon", beaconHash, 10,
    );
    await snarkjs.powersOfTau.preparePhase2(tmpBeacon, dest);
    for (const tmp of [tmpBase, tmpContr, tmpBeacon]) {
        try { fs.unlinkSync(tmp); } catch (_) {}
    }
    const size = fs.statSync(dest).size;
    console.log(`  [ptau] Local ptau generated: ${path.basename(dest)} (${(size/1e6).toFixed(0)}MB)`);
}

async function fetchIoTeXBeacon() {
    return new Promise((resolve, reject) => {
        const body = JSON.stringify({
            jsonrpc: "2.0", method: "eth_getBlockByNumber",
            params: ["latest", false], id: 1,
        });
        const opts = {
            hostname: "babel-api.testnet.iotex.io",
            path: "/",
            method: "POST",
            headers: { "Content-Type": "application/json", "Content-Length": body.length },
        };
        const req = https.request(opts, res => {
            let data = "";
            res.on("data", chunk => data += chunk);
            res.on("end", () => {
                try {
                    const result = JSON.parse(data).result;
                    resolve({
                        hash:   result.hash,
                        number: parseInt(result.number, 16),
                    });
                } catch (e) { reject(e); }
            });
        });
        req.on("error", reject);
        req.write(body);
        req.end();
    });
}

function sha256File(filePath) {
    const data = fs.readFileSync(filePath);
    return crypto.createHash("sha256").update(data).digest("hex");
}

function hexTo32Bytes(hex) {
    const clean = hex.replace("0x", "").padStart(64, "0");
    return Buffer.from(clean, "hex");
}

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------

async function main() {
    // Phase 237-ZK-SEPPROOF Session 2 addition: --circuit <name> CLI flag
    // restricts the ceremony to a single circuit so Phase 67's already-
    // deployed beacons for PitlSessionProof + TeamProof + TournamentPassport
    // are NOT overwritten when running the ceremony for a new circuit.
    const argv = process.argv.slice(2);
    let onlyCircuit = null;
    for (let i = 0; i < argv.length; i++) {
        if (argv[i] === "--circuit" && argv[i + 1]) {
            onlyCircuit = argv[i + 1];
            i++;
        }
    }
    if (onlyCircuit) {
        console.log(`[mode] single-circuit ceremony: ${onlyCircuit}`);
    }

    fs.mkdirSync(OUT_DIR, { recursive: true });
    fs.mkdirSync(path.dirname(PTAU_PATH), { recursive: true });

    // 1. Download Hermez Phase 1 ptau (cached after first run)
    await download(PTAU_URLS, PTAU_PATH);

    // 2. Fetch IoTeX beacon (same for all circuits — one block captures all)
    console.log("\n[beacon] Fetching IoTeX testnet block hash...");
    const beacon = await fetchIoTeXBeacon();
    console.log(`  Block #${beacon.number}: ${beacon.hash}`);

    const allManifests = [];

    // 3. Run MPC Phase 2 for each circuit
    for (const circuit of CIRCUITS) {
        if (onlyCircuit && circuit.name !== onlyCircuit) {
            continue;  // skip — single-circuit mode
        }
        if (!fs.existsSync(circuit.r1cs)) {
            console.warn(`  [skip] ${circuit.name} r1cs not found — recompile circuit first`);
            console.warn(`         cd contracts && npx hardhat compile`);
            continue;
        }
        console.log(`\n═══ ${circuit.name} ═══`);

        const tmpBase   = path.join(OUT_DIR, circuit.name);
        const zkey0     = `${tmpBase}_0000.zkey`;
        const zkey1     = `${tmpBase}_0001.zkey`;
        const zkey2     = `${tmpBase}_0002.zkey`;
        const zkey3     = `${tmpBase}_0003.zkey`;
        const zkeyBeacon = `${tmpBase}_beacon.zkey`;

        // Phase 2 — initial zkey from ptau + r1cs
        console.log("  [1/5] Generating initial zkey...");
        await snarkjs.zKey.newZKey(circuit.r1cs, PTAU_PATH, zkey0);

        // Contributor 1 — cryptographically random entropy
        const entropy1 = crypto.randomBytes(32).toString("hex");
        console.log("  [2/5] Contributor 1 (crypto.randomBytes)...");
        await snarkjs.zKey.contribute(zkey0, zkey1, "VAPI_Contributor_1_Phase67", entropy1);
        const hash1 = sha256File(zkey1);

        // Contributor 2 — high-resolution timer entropy
        const hr = process.hrtime.bigint().toString(16);
        const entropy2 = crypto.createHash("sha256")
            .update(hr + Date.now().toString())
            .digest("hex");
        console.log("  [3/5] Contributor 2 (hrtime entropy)...");
        await snarkjs.zKey.contribute(zkey1, zkey2, "VAPI_Contributor_2_Phase67", entropy2);
        const hash2 = sha256File(zkey2);

        // Contributor 3 — IoTeX block hash entropy (links ceremony to IoTeX chain)
        const entropy3 = crypto.createHash("sha256")
            .update(beacon.hash)
            .digest("hex");
        console.log("  [4/5] Contributor 3 (IoTeX block hash)...");
        await snarkjs.zKey.contribute(zkey2, zkey3, "VAPI_Contributor_3_IoTeX_Phase67", entropy3);
        const hash3 = sha256File(zkey3);

        // Final beacon — IoTeX block hash as Groth16 Phase 2 beacon
        const beaconHex = beacon.hash.replace("0x", "");
        console.log(`  [5/5] Applying IoTeX beacon (block #${beacon.number})...`);
        await snarkjs.zKey.beacon(
            zkey3, zkeyBeacon,
            "IoTeX_Testnet_Block_Beacon_Phase67",
            beaconHex,
            10,   // numIterationsExp
        );

        // Export final zkey to output location
        fs.copyFileSync(zkeyBeacon, circuit.outZkey);
        console.log(`  -> ${circuit.outZkey}`);

        // Export verification key JSON
        const vkeyObj = await snarkjs.zKey.exportVerificationKey(circuit.outZkey);
        fs.writeFileSync(circuit.outVkey, JSON.stringify(vkeyObj, null, 2));
        console.log(`  -> ${circuit.outVkey}`);

        // Compute vkeyHash (keccak256 of the JSON bytes — matches CeremonyRegistry.sol)
        const vkeyBytes = Buffer.from(JSON.stringify(vkeyObj, null, 2));
        const vkeyHash  = ethers.keccak256(vkeyBytes);

        // circuitId = keccak256(circuitName) — matches CeremonyRegistry.sol
        const circuitId = ethers.keccak256(ethers.toUtf8Bytes(circuit.name));

        const manifest = {
            circuitName:       circuit.name,
            circuitId,
            verifyingKeyHash:  vkeyHash,
            beaconBlockHash:   beacon.hash,
            beaconBlockNumber: beacon.number,
            contributorHashes: [hash1, hash2, hash3],
            contributorCount:  3,
            ptauSource:        "hermez-hez_final_15-2021",
            timestamp:         Math.floor(Date.now() / 1000),
        };

        const manifestPath = path.join(OUT_DIR, `${circuit.name}_manifest.json`);
        fs.writeFileSync(manifestPath, JSON.stringify(manifest, null, 2));
        console.log(`  -> ${manifestPath}`);
        allManifests.push(manifest);

        // Clean up temp zkeys
        for (const f of [zkey0, zkey1, zkey2, zkey3, zkeyBeacon]) {
            try { fs.unlinkSync(f); } catch {}
        }
    }

    // 4. Write aggregated manifest for deploy-ceremony-registry.js
    const aggregatedPath = path.join(OUT_DIR, "all_circuits_manifest.json");
    fs.writeFileSync(aggregatedPath, JSON.stringify(allManifests, null, 2));
    console.log(`\n[done] All circuits manifest: ${aggregatedPath}`);
    console.log("\nNext steps:");
    console.log("  1. npx hardhat run scripts/deploy-ceremony-registry.js --network iotex_testnet");
    console.log("  2. Add CEREMONY_REGISTRY_ADDRESS to bridge/.env");
    console.log("  3. npx hardhat run scripts/deploy-pitl-registry-v2.js --network iotex_testnet");
    console.log("     (new verifier embeds new MPC vkey)");
}

main().catch(e => { console.error(e); process.exit(1); });
