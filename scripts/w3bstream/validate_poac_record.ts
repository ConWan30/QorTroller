/**
 * Phase 99B — W3bstream AssemblyScript Applet: validate_poac_record
 *
 * Validates an incoming 228-byte PoAC record and submits the proof to
 * PITLSessionRegistryV2.sol on IoTeX L1.
 *
 * Wire format (FROZEN — DO NOT MODIFY):
 *   [0:164]  — Signed body (chain link hash = SHA-256 of this region only)
 *   [164:228] — ECDSA-P256 signature (r=32B, s=32B)
 *
 * Processing flow:
 *   1. Receive raw 228B packet from W3bstream message queue
 *   2. Extract device_id, inference_code, and chain_link_hash from body
 *   3. Verify ECDSA-P256 signature over raw[0:164]
 *   4. On valid signature: call PITLSessionRegistryV2.submitProof(chainLinkHash, deviceId, inferenceCode)
 *   5. On invalid signature: reject and log (never write invalid proofs on-chain)
 *
 * Chain link hash = SHA-256(raw[0:164]) — body ONLY, never 228B.
 * This invariant is cryptographically enforced by the on-chain verifier.
 *
 * Status: AssemblyScript stub — compiles to WASM via asc.
 * W3bstream project ID: cfg.w3bstream_project_id
 * Target contract: PITLSessionRegistryV2 (Phase 62, LIVE on IoTeX testnet)
 *
 * Note: @assemblyscript/wasm-crypto is required for SHA-256 and P256 verify.
 * Install: npm install --save-dev assemblyscript @assemblyscript/wasm-crypto
 */

// AssemblyScript type declarations
declare function env_get_message(ptr: i32, maxLen: i32): i32;
declare function chain_call(contractAddr: i32, addrLen: i32, calldata: i32, calldataLen: i32): i32;
declare function log_info(msg: i32, msgLen: i32): void;
declare function abort(msg: i32, file: i32, line: i32, col: i32): void;

const POAC_TOTAL_LEN: i32 = 228;
const BODY_LEN: i32 = 164;
const SIG_LEN: i32 = 64;

// Byte offsets within 164-byte body (see PoAC wire format specification)
const OFF_DEVICE_ID: i32 = 0;    // 32 bytes
const OFF_INF_CODE: i32 = 104;   // 1 byte
const OFF_CHAIN_HASH: i32 = 32;  // 32 bytes (SHA-256 of prior body segment)

/**
 * Entry point — called by W3bstream runtime for each PoAC message.
 * Returns 0 on success, non-zero on failure.
 */
export function handle_poac_message(): i32 {
    // Allocate buffer for incoming 228B packet
    const buf = memory.grow(1);  // grow by 1 page (64KB) — sufficient for single packet
    const rawPtr: i32 = buf << 16;

    // Read message from W3bstream queue
    const msgLen = env_get_message(rawPtr, POAC_TOTAL_LEN);
    if (msgLen != POAC_TOTAL_LEN) {
        _log("validate_poac_record: invalid length — expected 228, got " + msgLen.toString());
        return 1;  // reject: malformed packet
    }

    // Extract inference code from body (byte at OFF_INF_CODE)
    const inferenceCode: i32 = load<u8>(rawPtr + OFF_INF_CODE);

    // In production: verify ECDSA-P256 signature over raw[0:164]
    // P256 verify is available via @assemblyscript/wasm-crypto
    // For stub: signature verification returns true (replace with real impl)
    if (!_verify_p256_stub(rawPtr, BODY_LEN)) {
        _log("validate_poac_record: ECDSA-P256 signature invalid — rejected");
        return 2;  // reject: invalid signature
    }

    // Submit proof to PITLSessionRegistryV2
    // Calldata: ABI encode submitProof(bytes32 chainLinkHash, bytes32 deviceId, uint8 inferenceCode)
    const calldataPtr = rawPtr + POAC_TOTAL_LEN;  // use space after packet for calldata
    const calldataLen = _encode_submit_proof(rawPtr, inferenceCode, calldataPtr);

    // PITLSessionRegistryV2 address — configured via W3bstream project env
    const addrPtr: i32 = 0;  // address passed by W3bstream runtime configuration
    const result = chain_call(addrPtr, 20, calldataPtr, calldataLen);
    if (result != 0) {
        _log("validate_poac_record: chain_call failed — code " + result.toString());
        return 3;
    }

    _log("validate_poac_record: proof submitted — inference_code=" + inferenceCode.toString());
    return 0;
}

// --- Private helpers ---

function _verify_p256_stub(bodyPtr: i32, bodyLen: i32): bool {
    // Stub: always returns true in development
    // Production: use @assemblyscript/wasm-crypto ecdsa.verify(body, sig, pubkey)
    // where sig = raw[BODY_LEN:BODY_LEN+SIG_LEN] and pubkey from device registry
    return true;
}

function _encode_submit_proof(rawPtr: i32, inferenceCode: i32, outPtr: i32): i32 {
    // ABI encode: submitProof(bytes32 chainLinkHash, bytes32 deviceId, uint8 inferenceCode)
    // Function selector = keccak256("submitProof(bytes32,bytes32,uint8)")[0:4]
    // Full ABI encoding stub — replace with proper ABI encoder in production
    store<u32>(outPtr, 0xDEADBEEF);  // function selector placeholder
    return 4 + 32 + 32 + 32;  // selector + chainLinkHash + deviceId + padded uint8
}

function _log(msg: string): void {
    const encoded = String.UTF8.encode(msg);
    log_info(changetype<i32>(encoded), encoded.byteLength);
}
