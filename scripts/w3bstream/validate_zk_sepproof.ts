/**
 * Phase 237-ZK-SEPPROOF Step H — W3bstream AssemblyScript Applet: validate_zk_sepproof
 *
 * First DePIN W3bstream applet hosting a Groth16 verifier in production.
 * Three-zone privacy compartmentalization:
 *   ZONE 1 (bridge):       sees raw biometrics (witness vector, centroids)
 *   ZONE 2 (W3bstream):    sees only the ZK proof (zero-knowledge — reveals nothing)
 *   ZONE 3 (IoTeX chain):  sees only the verification anchor (32 bytes)
 *
 * Each zone has strictly less information than the previous one.  A bridge
 * compromise reveals biometric data; a W3bstream compromise reveals only
 * the proof bytes (which leak nothing about the witness); a chain compromise
 * reveals only the anchor (which is just a record that "some proof was
 * verified at this time for this snapshot/player").  Three independent
 * compromises required to leak biometric identity.
 *
 * Wire format (FROZEN at Step H v1):
 *   [0:256]      Groth16 proof bytes (BN254 uncompressed)
 *                  - [0:32]    pi_a[0]
 *                  - [32:64]   pi_a[1]
 *                  - [64:96]   pi_b[0][0]
 *                  - [96:128]  pi_b[0][1]
 *                  - [128:160] pi_b[1][0]
 *                  - [160:192] pi_b[1][1]
 *                  - [192:224] pi_c[0]
 *                  - [224:256] pi_c[1]
 *   [256:288]    biometricSnapshotHashLo  (uint256 BE; low 128 bits in low half)
 *   [288:320]    biometricSnapshotHashHi  (uint256 BE; high 128 bits in low half)
 *   [320:352]    claimedPlayerId          (uint256 BE; uint8 value in low byte)
 *   [352:384]    featureCommitment        (uint256 BE; Poseidon output)
 *   [384:416]    separationThresholdMilli (uint256 BE; uint16 value in low 2 bytes)
 *   [416:448]    inferenceCode            (uint256 BE; uint8 value in low byte)
 *
 *   TOTAL: 448 bytes (256 proof + 6 × 32 public inputs)
 *
 * Processing flow:
 *   1. Receive 448-byte submission from W3bstream message queue
 *   2. Reconstruct biometricSnapshotHash from (lo, hi) split:
 *        snapshot = hi << 128 | lo  (matches ZKSepProofVerifier.sol)
 *   3. Pre-condition: AdjudicationRegistry.isRecorded(snapshotHash) must be true
 *   4. Verify Groth16 proof (stub — production swaps in compiled snarkjs WASM
 *      verifier from ZKSepProof_verification_key.json)
 *   5. On verified=true: anchor the verification record via
 *      AdjudicationRegistry.recordAdjudication(VERIFICATION_DEVICE_ID,
 *      verification_poad_hash, false) where verification_poad_hash binds
 *      (snapshot, claimed_id, feature_commitment, ts) for replay-evidence.
 *   6. On verified=false: log + return without anchor (proof rejected).
 *
 * Return codes:
 *   0  — success: proof verified and verification anchored on AdjudicationRegistry
 *   1  — malformed packet (wrong length)
 *   2  — biometricSnapshotHash not anchored on AdjudicationRegistry
 *        (mirrors Solidity verifier's revert path)
 *   3  — Groth16 verification failed (proof invalid)
 *   4  — chain_call to record verification anchor failed
 *
 * Status: AssemblyScript stub — compiles to WASM via `asc`. Compatible with
 * the same applet pipeline phase as validate_poac_record.ts (Phase 99B/237-EXTEND).
 *
 * PLACEHOLDER ABI WARNING:
 *   This file uses placeholder function selectors:
 *     - 0xC0FFEE07 for AdjudicationRegistry.isRecorded
 *     - 0x5FA83F4B for AdjudicationRegistry.recordAdjudication (legacy 3-arg)
 *   The recordAdjudication selector matches what's actually deployed (Phase
 *   237.5 Path X discovery: anchorAdjudication 2-arg is NOT in deployed
 *   bytecode; only legacy 3-arg recordAdjudication is live). The isRecorded
 *   selector is a placeholder and must be computed via
 *   keccak256("isRecorded(bytes32)")[:4] when applet pipeline ships.
 *
 * Verification stub: _verify_groth16_zksep_stub() returns true unconditionally
 * in development. Production swaps this for the snarkjs-compiled WASM verifier
 * (or a hand-rolled BN254 pairing implementation embedded in the applet) once
 * the trusted setup ceremony produces ZKSepProof_verification_key.json
 * (deferred until wallet refill — see Phase 237-ZK-SEPPROOF Step E).
 *
 * Dependencies (when wired into production):
 *   @assemblyscript/wasm-crypto   — SHA-256 for verification record hashing
 *   snarkjs (precompiled WASM)    — Groth16 verifier for ZKSepProof
 *
 * Anchor design — verification record (anchored via AdjudicationRegistry):
 *   verification_poad_hash = SHA-256(
 *       b"VAPI-SEPPROOF-VERIFIED-v1" (25 bytes)
 *       || snapshot_hash[:32]
 *       || claimed_player_id[:1]
 *       || feature_commitment[:32]
 *       || ts_ns_be[:8]
 *   )
 *
 *   This produces a unique 32-byte hash per verification event. When
 *   anchored on AdjudicationRegistry, the resulting on-chain record proves
 *   "this exact (snapshot, player, commitment) tuple was verified at the
 *   block embedded in the AdjudicationAnchoredV2 event." Third-party
 *   verifiers can re-derive this hash from public inputs + ts and check
 *   AdjudicationRegistry.isRecorded(verification_poad_hash) to audit.
 */

// AssemblyScript runtime declarations
declare function env_get_message(ptr: i32, maxLen: i32): i32;
declare function env_get_block_timestamp_ns(): i64;
declare function chain_call(contractAddr: i32, addrLen: i32, calldata: i32, calldataLen: i32): i32;
declare function chain_call_view(contractAddr: i32, addrLen: i32, calldata: i32, calldataLen: i32, retBuf: i32, retMaxLen: i32): i32;
declare function sha256(inputPtr: i32, inputLen: i32, outputPtr: i32): void;
declare function log_info(msg: i32, msgLen: i32): void;

// Wire-format constants (FROZEN — must match bridge encoder at
// bridge/vapi_bridge/zk_sepproof_w3bstream.py)
const SUBMISSION_TOTAL_LEN: i32 = 448;
const PROOF_LEN: i32           = 256;
const N_PUBLIC_INPUTS: i32     = 6;
const PUBLIC_INPUT_LEN: i32    = 32;  // each is uint256 BE

const OFF_PROOF: i32                   = 0;
const OFF_SNAP_HASH_LO: i32            = 256;
const OFF_SNAP_HASH_HI: i32            = 288;
const OFF_CLAIMED_PLAYER_ID: i32       = 320;
const OFF_FEATURE_COMMITMENT: i32      = 352;
const OFF_SEPARATION_THRESHOLD_MILLI: i32 = 384;
const OFF_INFERENCE_CODE: i32          = 416;

// Verification anchor domain tag (FROZEN at Step H v1)
// "VAPI-SEPPROOF-VERIFIED-v1" — 25 bytes
// Used in verification_poad_hash composition; anchored via AdjudicationRegistry.

/**
 * Entry point — called by W3bstream runtime for each ZK-SEPPROOF submission.
 * Returns 0 on success, non-zero on failure (see file docstring for codes).
 */
export function handle_zk_sepproof_message(): i32 {
    // Allocate buffer for incoming 448B packet + scratch space
    const buf = memory.grow(2);  // grow by 2 pages (128KB) — packet + scratch
    const rawPtr: i32 = buf << 16;

    // Read message from W3bstream queue
    const msgLen = env_get_message(rawPtr, SUBMISSION_TOTAL_LEN);
    if (msgLen != SUBMISSION_TOTAL_LEN) {
        _log("validate_zk_sepproof: invalid length — expected 448, got " + msgLen.toString());
        return 1;  // reject: malformed packet
    }

    // Reconstruct 32-byte snapshot hash from (lo, hi) public input split.
    // Layout in memory: [256:288] = lo (uint256 BE), [288:320] = hi (uint256 BE).
    // Each uint256 holds a 128-bit value in the low half (high 16 bytes are zero).
    // Combined snapshot_hash[i] = hi[i+16] for i<16, lo[i-16+16] for i>=16.
    // (Concretely: high 16 bytes of hi-uint256 contain the high 128 bits of the
    // 32-byte snapshot hash; high 16 bytes of lo-uint256 contain the low 128.)
    const snapshotHashPtr = rawPtr + SUBMISSION_TOTAL_LEN;  // scratch space
    _reconstruct_snapshot_hash(rawPtr + OFF_SNAP_HASH_LO,
                                rawPtr + OFF_SNAP_HASH_HI,
                                snapshotHashPtr);

    // ZONE 3 pre-condition: snapshot must be anchored on AdjudicationRegistry.
    // This is the load-bearing check that closes the W1 attack: without it,
    // a malicious bridge could fabricate centroids that satisfy the
    // separation inequality but represent no real corpus state.
    if (!_check_snapshot_anchored(snapshotHashPtr)) {
        _log("validate_zk_sepproof: biometricSnapshotHash not anchored on AdjudicationRegistry");
        return 2;
    }

    // ZONE 2 verification: Groth16 proof check.
    // Stub: always returns true in development.
    // Production: snarkjs WASM verifier loaded with
    // ZKSepProof_verification_key.json from the trusted setup ceremony.
    // Public inputs read directly from packet at OFF_SNAP_HASH_LO..OFF_INFERENCE_CODE.
    if (!_verify_groth16_zksep_stub(rawPtr + OFF_PROOF,
                                     rawPtr + OFF_SNAP_HASH_LO,
                                     N_PUBLIC_INPUTS)) {
        _log("validate_zk_sepproof: Groth16 verification failed — proof invalid");
        return 3;
    }

    // Compose verification record hash.
    // verification_poad_hash binds (snapshot, claimed_id, feature_commitment, ts)
    // for unique-per-verification anchor. AdjudicationRegistry's UNIQUE
    // constraint on poadHash provides anti-replay automatically.
    const verPoadHashPtr = snapshotHashPtr + 32;  // next scratch slot
    _compose_verification_poad_hash(snapshotHashPtr, rawPtr, verPoadHashPtr);

    // ZONE 3 anchor: AdjudicationRegistry.recordAdjudication(
    //   VERIFICATION_DEVICE_ID, verification_poad_hash, false
    // )
    const anchorCalldataPtr = verPoadHashPtr + 32;
    const anchorCalldataLen = _encode_record_adjudication(
        verPoadHashPtr, anchorCalldataPtr
    );
    const anchorAddrPtr: i32 = 0;  // AdjudicationRegistry address from W3bstream env
    const anchorResult = chain_call(anchorAddrPtr, 20, anchorCalldataPtr, anchorCalldataLen);
    if (anchorResult != 0) {
        _log("validate_zk_sepproof: chain_call to record verification anchor failed — code " +
             anchorResult.toString());
        return 4;
    }

    _log("validate_zk_sepproof: verification anchored — proof accepted");
    return 0;
}

// --- Private helpers ---

/**
 * Reconstruct 32-byte snapshot hash from the (lo, hi) public-input split.
 *
 * In the public-input layout, lo and hi are each 32-byte uint256 BE values
 * containing a 128-bit value in their low 16 bytes (high 16 zero).  The
 * full 32-byte hash is formed as:
 *
 *   hash[0:16]  = hi-uint256[16:32]   (high 128 bits of original hash)
 *   hash[16:32] = lo-uint256[16:32]   (low 128 bits of original hash)
 *
 * This matches the Solidity verifier's `bytes32((hi << 128) | lo)` pattern.
 */
function _reconstruct_snapshot_hash(loPtr: i32, hiPtr: i32, outPtr: i32): void {
    // Copy high 16 bytes of hi-uint256 → output[0:16]
    for (let i: i32 = 0; i < 16; i++) {
        store<u8>(outPtr + i, load<u8>(hiPtr + 16 + i));
    }
    // Copy high 16 bytes of lo-uint256 → output[16:32]
    for (let i: i32 = 0; i < 16; i++) {
        store<u8>(outPtr + 16 + i, load<u8>(loPtr + 16 + i));
    }
}

/**
 * Query AdjudicationRegistry.isRecorded(bytes32 poadHash) → bool.
 *
 * View call (no gas). Returns true iff the snapshot is anchored.
 *
 * PLACEHOLDER selector 0xC0FFEE07 — replace with
 * keccak256("isRecorded(bytes32)")[:4] at applet-pipeline phase.
 */
function _check_snapshot_anchored(snapshotHashPtr: i32): bool {
    // Calldata: selector(4) || snapshotHash(32) = 36 bytes
    const callPtr: i32 = snapshotHashPtr + 64;  // scratch after hash + spare
    store<u32>(callPtr, 0xC0FFEE07);  // PLACEHOLDER selector
    for (let i: i32 = 0; i < 32; i++) {
        store<u8>(callPtr + 4 + i, load<u8>(snapshotHashPtr + i));
    }

    // View call to AdjudicationRegistry — runtime configures address
    const adjAddrPtr: i32 = 0;
    const retBuf: i32 = callPtr + 64;
    const retLen = chain_call_view(adjAddrPtr, 20, callPtr, 36, retBuf, 32);

    // Return-data is uint256 BE (1 = true, 0 = false). Check low byte.
    if (retLen <= 0) return false;
    return load<u8>(retBuf + 31) != 0;
}

/**
 * Compose verification_poad_hash for AdjudicationRegistry anchor.
 *
 * Body layout (FROZEN at Step H v1):
 *   25-byte tag "VAPI-SEPPROOF-VERIFIED-v1"
 *   || 32-byte snapshot_hash
 *   || 1-byte claimed_player_id
 *   || 32-byte feature_commitment
 *   || 8-byte ts_ns BE
 *
 * Total body = 25 + 32 + 1 + 32 + 8 = 98 bytes → SHA-256 → 32 bytes
 */
function _compose_verification_poad_hash(
    snapshotHashPtr: i32,
    rawPtr: i32,
    outPtr: i32,
): void {
    // Build body in scratch space
    const bodyPtr: i32 = outPtr + 64;  // scratch after output
    let bodyLen: i32 = 0;

    // Tag bytes "VAPI-SEPPROOF-VERIFIED-v1" (25 bytes)
    const tag = "VAPI-SEPPROOF-VERIFIED-v1";
    for (let i: i32 = 0; i < tag.length; i++) {
        store<u8>(bodyPtr + bodyLen + i, tag.charCodeAt(i) as u8);
    }
    bodyLen += tag.length;  // 25

    // Snapshot hash (32 bytes)
    for (let i: i32 = 0; i < 32; i++) {
        store<u8>(bodyPtr + bodyLen + i, load<u8>(snapshotHashPtr + i));
    }
    bodyLen += 32;

    // Claimed player ID (1 byte) — taken from low byte of uint256 at OFF_CLAIMED_PLAYER_ID
    store<u8>(bodyPtr + bodyLen, load<u8>(rawPtr + OFF_CLAIMED_PLAYER_ID + 31));
    bodyLen += 1;

    // Feature commitment (32 bytes)
    for (let i: i32 = 0; i < 32; i++) {
        store<u8>(bodyPtr + bodyLen + i, load<u8>(rawPtr + OFF_FEATURE_COMMITMENT + i));
    }
    bodyLen += 32;

    // Timestamp ns (8 bytes BE)
    const tsNs: i64 = env_get_block_timestamp_ns();
    for (let i: i32 = 0; i < 8; i++) {
        const shift: i64 = ((7 - i) * 8) as i64;
        const byteVal: u8 = ((tsNs >> shift) & 0xff) as u8;
        store<u8>(bodyPtr + bodyLen + i, byteVal);
    }
    bodyLen += 8;

    // SHA-256(body) → outPtr
    sha256(bodyPtr, bodyLen, outPtr);
}

/**
 * Encode AdjudicationRegistry.recordAdjudication(deviceId, poadHash, dualVeto).
 *
 * Selector 0x5FA83F4B matches the deployed legacy 3-arg ABI per Phase 237.5
 * Path X discovery (anchorAdjudication 2-arg not in deployed bytecode).
 *
 * Calldata layout: selector(4) || deviceId(32) || poadHash(32) || dualVeto(32) = 100 bytes
 *
 * deviceId is the constant SHA-256("VAPI_SEPPROOF_VERIFIED_v1") which W3bstream
 * runtime configures as VERIFICATION_DEVICE_ID env var (32-byte hex). Stub
 * uses zero-bytes; production reads from runtime config.
 */
function _encode_record_adjudication(poadHashPtr: i32, outPtr: i32): i32 {
    // Selector 0x5FA83F4B (legacy recordAdjudication, 3-arg)
    store<u32>(outPtr, 0x5FA83F4B);
    let off: i32 = 4;

    // deviceId (32 bytes) — W3bstream runtime sets these from env at deploy.
    // Stub: zeros. Production: VERIFICATION_DEVICE_ID = SHA-256("VAPI_SEPPROOF_VERIFIED_v1").
    for (let i: i32 = 0; i < 32; i++) {
        store<u8>(outPtr + off + i, 0);
    }
    off += 32;

    // poadHash (32 bytes)
    for (let i: i32 = 0; i < 32; i++) {
        store<u8>(outPtr + off + i, load<u8>(poadHashPtr + i));
    }
    off += 32;

    // dualVeto (uint256 BE, false → 32 zeros)
    for (let i: i32 = 0; i < 32; i++) {
        store<u8>(outPtr + off + i, 0);
    }
    off += 32;

    return off;  // 100 bytes
}

/**
 * Stub Groth16 verifier — always returns true in development.
 *
 * Production replacement:
 *   Compile snarkjs to WASM via `npm run build:wasm-verifier` and import
 *   verify(vkey, proof, public_inputs) — must use ZKSepProof_verification_key.json
 *   from the Phase 237-ZK-SEPPROOF Step E ceremony.
 *
 * Inputs match the snarkjs JS verifier signature:
 *   proof:          256-byte BN254 uncompressed (pi_a + pi_b + pi_c)
 *   publicInputs:   N × 32-byte uint256 BE (BN254 scalar field elements)
 */
function _verify_groth16_zksep_stub(
    proofPtr: i32,
    publicInputsPtr: i32,
    nPublic: i32,
): bool {
    // Stub: bypass cryptographic check
    return true;
}

function _log(msg: string): void {
    const encoded = String.UTF8.encode(msg);
    log_info(changetype<i32>(encoded), encoded.byteLength);
}
