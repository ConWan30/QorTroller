/**
 * Phase 99B — W3bstream AssemblyScript Applet: validate_poac_record
 * Phase 237-EXTEND — Per-category consent routing layer added (forward-compat stub)
 *
 * Validates an incoming 228-byte PoAC record and submits the proof to
 * PITLSessionRegistryV2.sol on IoTeX L1, then routes the record to
 * downstream pools (research, marketplace) based on the gamer's per-category
 * on-chain consent state in VAPIConsentRegistry.
 *
 * Wire format (FROZEN — DO NOT MODIFY):
 *   [0:164]   — Signed body (chain link hash = SHA-256 of this region only)
 *   [164:228] — ECDSA-P256 signature (r=32B, s=32B)
 *
 * Processing flow:
 *   1. Receive raw 228B packet from W3bstream message queue
 *   2. Extract device_id, inference_code, and chain_link_hash from body
 *   3. Verify ECDSA-P256 signature over raw[0:164]
 *   4. On valid signature: call PITLSessionRegistryV2.submitProof(...)
 *   5. **Phase 237-EXTEND**: query VAPIConsentRegistry.isConsentValid(gamer, category)
 *      for each downstream destination; route only on True; log denials.
 *   6. On invalid signature: reject and log (never write invalid proofs on-chain)
 *
 * Chain link hash = SHA-256(raw[0:164]) — body ONLY, never 228B.
 * This invariant is cryptographically enforced by the on-chain verifier.
 *
 * Phase 237-EXTEND consent routing matrix:
 *   ConsentCategory.TOURNAMENT_GATE     (0) — required for any PoAC submission;
 *                                              checked here as a hard gate
 *   ConsentCategory.ANONYMIZED_RESEARCH (1) — gates routing to research pool
 *   ConsentCategory.MANUFACTURER_CERT   (2) — gates routing to OEM cert pool
 *   ConsentCategory.MARKETPLACE         (3) — gates listing in VAPIDataMarketplace
 *
 * Return codes:
 *   0  — success (proof submitted; consent-gated downstream routing applied)
 *   1  — malformed packet
 *   2  — ECDSA-P256 signature invalid
 *   3  — chain_call to PITLSessionRegistryV2 failed
 *   4  — Phase 237-EXTEND: TOURNAMENT_GATE consent absent (hard refuse)
 *   5  — Phase 237-EXTEND: marketplace/research routing skipped (soft refuse;
 *        proof was still submitted to PITL — return value documents skip)
 *
 * Status: AssemblyScript stub — compiles to WASM via asc.
 * W3bstream project ID: cfg.w3bstream_project_id
 * Target contracts:
 *   PITLSessionRegistryV2  (Phase 62, LIVE on IoTeX testnet)
 *   VAPIConsentRegistry    (Phase 237, LIVE — set CONSENT_REGISTRY_ADDRESS in
 *                           W3bstream project env to enable consent routing)
 *
 * Note: @assemblyscript/wasm-crypto is required for SHA-256 and P256 verify.
 * Install: npm install --save-dev assemblyscript @assemblyscript/wasm-crypto
 *
 * PLACEHOLDER ABI WARNING:
 *   This file uses placeholder function selectors (0xDEADBEEF for submitProof,
 *   0xCAFE0237 for isConsentValid). The applet is stub-only and does NOT run
 *   in production today — no W3bstream applet pipeline is wired. Real
 *   selectors must be computed via keccak256(canonicalSignature)[:4] when the
 *   applet pipeline phase ships separately. The bridge `_check_consent_gate`
 *   (Phase 237 core, shipped) is the live enforcement point in the meantime.
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

    // ─────────────────────────────────────────────────────────────────────
    // Phase 237-EXTEND — Consent-gated downstream routing
    // ─────────────────────────────────────────────────────────────────────
    // After successful PITL submission, check the gamer's consent state for
    // each downstream destination via view calls to VAPIConsentRegistry.
    // The view calls do NOT cost gas (read-only) and never block PoAC
    // submission — they only gate WHICH downstream pools the record flows to.
    //
    // FROZEN ConsentCategory enum (matches contract + bridge):
    //   TOURNAMENT_GATE = 0  (hard refuse if absent)
    //   ANONYMIZED_RESEARCH = 1
    //   MANUFACTURER_CERT = 2
    //   MARKETPLACE = 3

    const consentCalldataPtr = rawPtr + POAC_TOTAL_LEN + calldataLen;

    // 1. TOURNAMENT_GATE — hard gate; absent consent means refuse to route
    //    proof to any downstream pool (PITL submission already happened above).
    if (!_check_consent_view(rawPtr, /*category=*/0, consentCalldataPtr)) {
        _log("validate_poac_record: TOURNAMENT_GATE consent absent — hard refuse routing");
        return 4;
    }

    // 2. ANONYMIZED_RESEARCH — soft gate; absent consent means skip routing
    //    to research pool. Marketplace pool gated separately below.
    let routingSkipped: bool = false;
    if (!_check_consent_view(rawPtr, /*category=*/1, consentCalldataPtr)) {
        _log("validate_poac_record: ANONYMIZED_RESEARCH consent absent — skipping research pool");
        routingSkipped = true;
    }
    // (research pool routing call would go here when downstream pipeline lands)

    // 3. MARKETPLACE — soft gate; absent consent means skip marketplace listing.
    if (!_check_consent_view(rawPtr, /*category=*/3, consentCalldataPtr)) {
        _log("validate_poac_record: MARKETPLACE consent absent — skipping marketplace listing");
        routingSkipped = true;
    }
    // (VAPIDataMarketplace.listSession call would go here when Phase 238 lands)

    return routingSkipped ? 5 : 0;
}

// --- Private helpers ---

/**
 * Phase 237-EXTEND — Query VAPIConsentRegistry.isConsentValid(gamer, category).
 *
 * Returns true iff the gamer (extracted from PoAC body bytes 0..32 at
 * OFF_DEVICE_ID — note: production deriving from device_id needs the real
 * deviceId-to-wallet mapping which lives in VAPIioIDRegistry; for the stub
 * we treat device_id bytes as the gamer address) has currently-valid consent
 * for the given category.
 *
 * PLACEHOLDER: function selector 0xCAFE0237 must be replaced with the real
 * keccak256("isConsentValid(address,uint8)")[:4] when the applet pipeline
 * phase ships. The contract is deployed; only this stub's ABI encoding is
 * placeholder.
 */
function _check_consent_view(rawPtr: i32, category: u8, callPtr: i32): bool {
    // ABI encode: isConsentValid(address gamer, uint8 category)
    //   selector(4) || gamer_padded(32) || category_padded(32) = 68 bytes
    store<u32>(callPtr, 0xCAFE0237);  // PLACEHOLDER selector — replace at applet-pipeline phase
    // (real ABI encoder would copy device_id → gamer slot and category → uint8 slot)

    // Consent registry address — configured via W3bstream project env
    // (CONSENT_REGISTRY_ADDRESS). When unset, this view call returns
    // non-zero and the helper returns false (fail-closed for soft gates;
    // for TOURNAMENT_GATE this means routing is refused).
    const consentAddrPtr: i32 = 0;  // address passed by W3bstream runtime configuration
    const result = chain_call(consentAddrPtr, 20, callPtr, 4 + 32 + 32);

    // chain_call returns 0 on success; the actual bool result of the view
    // would be in the return-data buffer. STUB: assume success (=allowed)
    // when chain_call returns 0; real implementation reads return-data.
    return result == 0;
}

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
