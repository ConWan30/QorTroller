/**
 * Phase 99B — W3bstream AssemblyScript Applet: validate_poac_record
 * Phase 237-EXTEND — Per-category consent routing layer added (forward-compat stub)
 * Phase O4-VPM-INT-A.PARTIAL (2026-05-14) — 3 of 5 crypto-integration deltas CLOSED:
 *   ABI_ENCODER + CONSENT_RETURN_DATA + DEVICE_ID_TO_GAMER. P256_VERIFY and
 *   POSEIDON_HASH remain explicitly deferred (see deferral block below).
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
 *   3. Verify ECDSA-P256 signature over raw[0:164]  [STUB — see deferral]
 *   4. On valid signature: call PITLSessionRegistryV2.submitPITLProof(...)
 *   5. **Phase 237-EXTEND**: resolve device_id → gamer address via
 *      VAPIioIDRegistry.getDeviceWallet, then query
 *      VAPIConsentRegistry.isConsentValid(gamer, category) for each
 *      downstream destination; route only on True; log denials.
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
 *   6  — Phase O4-VPM-INT-A.PARTIAL: device_id → gamer resolution failed
 *        (VAPIioIDRegistry.getDeviceWallet returned non-zero result code or
 *        zero-address gamer; consent routing cannot proceed without gamer)
 *
 * Status: AssemblyScript stub — compiles to WASM via asc.
 * W3bstream project ID: cfg.w3bstream_project_id
 * Target contracts:
 *   PITLSessionRegistryV2  (Phase 62, LIVE on IoTeX testnet)
 *   VAPIConsentRegistry    (Phase 237, LIVE — set CONSENT_REGISTRY_ADDRESS in
 *                           W3bstream project env to enable consent routing)
 *   VAPIioIDRegistry       (Phase 55, LIVE — set IOID_REGISTRY_ADDRESS in
 *                           W3bstream project env to enable gamer resolution)
 *
 * Note: @assemblyscript/wasm-crypto is required for SHA-256 and P256 verify.
 *   2026-05-14 status: 404 on npm — P256_VERIFY remains stubbed (see
 *   deferral block above _verify_p256_stub).
 *
 * STUB STATUS (Phase O4-VPM-INT-A.PARTIAL, 2026-05-14):
 *   - ABI_ENCODER:        CLOSED — full 7-arg submitPITLProof ABI v2 encoder
 *                         with real selector 0x7c4847ed
 *   - CONSENT_RETURN_DATA: CLOSED — chain_call return-data buffer parsed,
 *                         rightmost byte read as bool
 *   - DEVICE_ID_TO_GAMER: CLOSED — VAPIioIDRegistry.getDeviceWallet resolves
 *                         device_id → gamer address before consent check
 *   - P256_VERIFY:        STUB (dep-blocked; @assemblyscript/wasm-crypto 404)
 *   - POSEIDON_HASH:      STUB (no AS Poseidon reference available; the
 *                         applet stub still does not compute featureCommitment
 *                         or nullifierHash — both passed as zero placeholders
 *                         to preserve ABI shape until Poseidon lands)
 *
 *   The W3bstream applet pipeline is NOT wired to production at this commit;
 *   the bridge `_check_consent_gate` (Phase 237 core, shipped) remains the
 *   live enforcement point.
 */

// AssemblyScript type declarations
declare function env_get_message(ptr: i32, maxLen: i32): i32;
declare function chain_call(contractAddr: i32, addrLen: i32, calldata: i32, calldataLen: i32): i32;
declare function chain_call_returndata(retPtr: i32, retLen: i32): i32;
declare function log_info(msg: i32, msgLen: i32): void;
declare function abort(msg: i32, file: i32, line: i32, col: i32): void;

const POAC_TOTAL_LEN: i32 = 228;
const BODY_LEN: i32 = 164;
const SIG_LEN: i32 = 64;

// Byte offsets within 164-byte body (see PoAC wire format specification)
const OFF_DEVICE_ID: i32 = 0;    // 32 bytes
const OFF_INF_CODE: i32 = 104;   // 1 byte
const OFF_CHAIN_HASH: i32 = 32;  // 32 bytes (SHA-256 of prior body segment)

// FROZEN ABI selectors (real, computed via keccak256; audited by
// scripts/w3bstream_applet_audit.py).
const SEL_SUBMIT_PITL_PROOF: u32 = 0x7c4847ed;
const SEL_IS_CONSENT_VALID:  u32 = 0xbabcf9f5;
const SEL_GET_DEVICE_WALLET: u32 = 0x0ff0779b;

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

    // ECDSA-P256 signature verification — STUB (see deferral block below).
    if (!_verify_p256_stub(rawPtr, BODY_LEN)) {
        _log("validate_poac_record: ECDSA-P256 signature invalid — rejected");
        return 2;  // reject: invalid signature
    }

    // Submit proof to PITLSessionRegistryV2
    // Real ABI v2 encoder for the 7-arg submitPITLProof signature.
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
    // Phase O4-VPM-INT-A.PARTIAL — Real ABI encoding + return-data parsing
    // ─────────────────────────────────────────────────────────────────────
    // After successful PITL submission:
    //   (1) Resolve device_id_hash → gamer address via VAPIioIDRegistry
    //   (2) Check the gamer's consent state for each downstream destination
    //       via view calls to VAPIConsentRegistry.
    // View calls are read-only (no gas) and never block PoAC submission —
    // they only gate WHICH downstream pools the record flows to.
    //
    // FROZEN ConsentCategory enum (matches contract + bridge):
    //   TOURNAMENT_GATE = 0  (hard refuse if absent)
    //   ANONYMIZED_RESEARCH = 1
    //   MANUFACTURER_CERT = 2
    //   MARKETPLACE = 3

    const downstreamCalldataPtr = rawPtr + POAC_TOTAL_LEN + calldataLen;

    // (1) device_id_hash → gamer address via VAPIioIDRegistry.getDeviceWallet
    const gamerAddrPtr = downstreamCalldataPtr + 256;  // reserve 256B for gamer address output
    if (!_resolve_device_to_gamer(rawPtr, downstreamCalldataPtr, gamerAddrPtr)) {
        _log("validate_poac_record: device_id → gamer resolution failed");
        return 6;
    }

    // (2) Run the three consent checks using the resolved gamer address.
    const consentCalldataPtr = downstreamCalldataPtr + 320;  // 256B output + slack

    // TOURNAMENT_GATE — hard gate; absent consent means refuse to route
    //    proof to any downstream pool (PITL submission already happened above).
    if (!_check_consent_view(gamerAddrPtr, /*category=*/0, consentCalldataPtr)) {
        _log("validate_poac_record: TOURNAMENT_GATE consent absent — hard refuse routing");
        return 4;
    }

    // ANONYMIZED_RESEARCH — soft gate; absent consent means skip routing
    //    to research pool. Marketplace pool gated separately below.
    let routingSkipped: bool = false;
    if (!_check_consent_view(gamerAddrPtr, /*category=*/1, consentCalldataPtr)) {
        _log("validate_poac_record: ANONYMIZED_RESEARCH consent absent — skipping research pool");
        routingSkipped = true;
    }
    // (research pool routing call would go here when downstream pipeline lands)

    // MARKETPLACE — soft gate; absent consent means skip marketplace listing.
    if (!_check_consent_view(gamerAddrPtr, /*category=*/3, consentCalldataPtr)) {
        _log("validate_poac_record: MARKETPLACE consent absent — skipping marketplace listing");
        routingSkipped = true;
    }
    // (VAPIDataMarketplace.listSession call would go here when Phase 238 lands)

    return routingSkipped ? 5 : 0;
}

// --- Private helpers ---

/**
 * Phase O4-VPM-INT-A.PARTIAL — device_id_hash → gamer address resolution.
 *
 * Calls VAPIioIDRegistry.getDeviceWallet(bytes32 deviceIdHash) and writes
 * the 20-byte gamer address (left-padded to 32B in return-data; we extract
 * the rightmost 20 bytes) into outAddrPtr.
 *
 * ABI:
 *   selector(4) || deviceIdHash(32) = 36 bytes calldata
 *   return-data: 32 bytes, address in rightmost 20 bytes (bytes 12..31)
 *
 * Returns false if:
 *   - chain_call returns non-zero (RPC-level failure)
 *   - returned address is the zero address (device not registered)
 *
 * Selector 0x0ff0779b = keccak256("getDeviceWallet(bytes32)")[:4]
 * (computed 2026-05-14 via eth_utils.keccak; audited by
 * scripts/w3bstream_applet_audit.py — see AUTHORITATIVE_SIGNATURES).
 */
function _resolve_device_to_gamer(rawPtr: i32, callPtr: i32, outAddrPtr: i32): bool {
    // ABI v2 encode: getDeviceWallet(bytes32 deviceIdHash)
    //   selector(4) || deviceIdHash(32) = 36 bytes
    // Selector stored big-endian; AS store<u32> is little-endian on
    // wasm32, so write byte-by-byte to preserve big-endian ABI layout.
    _store_u32_be(callPtr, SEL_GET_DEVICE_WALLET);
    // Copy device_id_hash (32 bytes) from PoAC body [OFF_DEVICE_ID:OFF_DEVICE_ID+32]
    memory.copy(callPtr + 4, rawPtr + OFF_DEVICE_ID, 32);

    const ioidAddrPtr: i32 = 0;  // address passed by W3bstream runtime configuration
    const result = chain_call(ioidAddrPtr, 20, callPtr, 36);
    if (result != 0) {
        return false;
    }

    // Read 32-byte return-data; address is in rightmost 20 bytes
    // (Ethereum left-pads address to 32B in return-data).
    const retBufPtr = outAddrPtr;  // reuse caller's output buffer for read
    const retLen = chain_call_returndata(retBufPtr, 32);
    if (retLen != 32) {
        return false;
    }

    // Zero-address check: bytes 12..31 must not all be zero.
    let nonZero: bool = false;
    for (let i: i32 = 12; i < 32; i++) {
        if (load<u8>(retBufPtr + i) != 0) {
            nonZero = true;
            break;
        }
    }
    if (!nonZero) {
        return false;
    }

    // outAddrPtr now holds the 32-byte left-padded address — the consent
    // ABI encoder reads it as-is (address slot is already 32B-padded).
    return true;
}

/**
 * Phase 237-EXTEND — Query VAPIConsentRegistry.isConsentValid(gamer, category).
 * Phase O4-VPM-INT-A.PARTIAL — Real ABI v2 encoder + return-data parsing.
 *
 * Returns true iff the gamer (resolved via _resolve_device_to_gamer above)
 * has currently-valid consent for the given category.
 *
 * ABI:
 *   selector(4) || gamer_padded(32) || category_padded(32) = 68 bytes calldata
 *   return-data: 32 bytes, bool in rightmost byte (offset 31)
 *
 * Selector 0xbabcf9f5 = keccak256("isConsentValid(address,uint8)")[:4]
 */
function _check_consent_view(gamerAddrPtr: i32, category: u8, callPtr: i32): bool {
    // ABI v2 encode: isConsentValid(address gamer, uint8 category)
    //   selector(4) || gamer_padded(32) || category_padded(32) = 68 bytes
    _store_u32_be(callPtr, SEL_IS_CONSENT_VALID);
    // gamerAddrPtr is already 32B left-padded from _resolve_device_to_gamer
    memory.copy(callPtr + 4, gamerAddrPtr, 32);
    // category is uint8; ABI encodes as 32 bytes, value in rightmost byte
    memory.fill(callPtr + 4 + 32, 0, 32);
    store<u8>(callPtr + 4 + 32 + 31, category);

    // Consent registry address — configured via W3bstream project env
    // (CONSENT_REGISTRY_ADDRESS). When unset, chain_call returns non-zero
    // and the helper returns false (fail-closed for soft gates;
    // for TOURNAMENT_GATE this means routing is refused).
    const consentAddrPtr: i32 = 0;  // address passed by W3bstream runtime configuration
    const result = chain_call(consentAddrPtr, 20, callPtr, 68);
    if (result != 0) {
        return false;
    }

    // Read 32-byte return-data; bool is in rightmost byte (offset 31).
    // Solidity ABI encodes bool as uint256 with 0=false, 1=true; only the
    // last byte carries the value.
    const retBufPtr = callPtr + 68;  // scratch slot after calldata
    const retLen = chain_call_returndata(retBufPtr, 32);
    if (retLen != 32) {
        return false;
    }
    return _read_bool_from_returndata(retBufPtr);
}

/**
 * Read the rightmost byte of a 32-byte ABI-encoded bool return-data buffer
 * and return true iff non-zero. Solidity ABI encodes bool as uint256 with
 * the value byte at the rightmost (offset 31) position.
 */
function _read_bool_from_returndata(retPtr: i32): bool {
    return load<u8>(retPtr + 31) != 0;
}

/**
 * STUB — ECDSA-P256 signature verification.
 *
 * ─────────────────────────────────────────────────────────────────────
 * DEFERRAL DOCUMENTATION (Phase O4-VPM-INT-A.PARTIAL, 2026-05-14)
 * ─────────────────────────────────────────────────────────────────────
 *
 * This function REMAINS A STUB returning `true` unconditionally. Per
 * VAPI's "verifiable claims with visible limits" posture and the explicit
 * Stream A Hard Rule ("at NO point in A.1–A.4 do we ship code that
 * COMPILES TO WASM but produces incorrect cryptographic output"):
 *
 * WHY STILL A STUB:
 *   - @assemblyscript/wasm-crypto is 404 on npm registry (probed
 *     2026-05-14; see scripts/w3bstream_applet_audit.py DEPENDENCY_BLOCKERS).
 *   - No W3bstream runtime test harness available to verify a
 *     hand-written ECDSA-P256 AS implementation against known test
 *     vectors at the WASM execution layer.
 *   - Shipping a hand-rolled ECDSA-P256 implementation without runtime
 *     verification risks producing incorrect cryptographic output that
 *     would silently accept forged signatures — strictly forbidden.
 *
 * OPERATOR AUDIT SURFACE:
 *   - scripts/w3bstream_applet_audit.py reports this delta as
 *     P256_VERIFY (still open) in CRYPTO_INTEGRATION_DELTAS.
 *   - The applet's overall verdict remains STUB until P256_VERIFY closes.
 *   - The bridge `_check_consent_gate` (Phase 237 core, shipped) is the
 *     live enforcement point at this commit; the applet pipeline is NOT
 *     wired to production.
 *
 * PATH FORWARD (in priority order):
 *   1. When @assemblyscript/wasm-crypto becomes available on npm,
 *      replace this stub with:
 *          ecdsa.verify(rawBody, rawSig, pubkey)
 *      where rawSig = raw[BODY_LEN:BODY_LEN+SIG_LEN] and pubkey resolves
 *      via VAPIioIDRegistry getDeviceWallet (already wired via
 *      _resolve_device_to_gamer above) + a separate getDevicePubkey view.
 *   2. Alternative: when W3bstream provides a runtime test harness that
 *      can verify a hand-written AS ECDSA-P256 implementation against
 *      NIST CAVP test vectors at WASM execution layer, vendor the
 *      implementation under runtime-verified semantics.
 *   3. DO NOT WRITE a hand-rolled P256 implementation without one of
 *      the above. The safety rule blocks this path.
 *
 * ─────────────────────────────────────────────────────────────────────
 */
function _verify_p256_stub(bodyPtr: i32, bodyLen: i32): bool {
    return true;
}

/**
 * Phase O4-VPM-INT-A.PARTIAL — Full ABI v2 encoder for submitPITLProof.
 *
 * Real PITLSessionRegistry.submitPITLProof signature (7 args):
 *   submitPITLProof(
 *     bytes32 deviceId,
 *     bytes proof,
 *     uint256 featureCommitment,
 *     uint256 humanityProbInt,
 *     uint256 inferenceCode,
 *     uint256 nullifierHash,
 *     uint256 epoch
 *   )
 *
 * Selector 0x7c4847ed = keccak256(canonical_sig)[:4] (computed 2026-05-14
 * via eth_utils.keccak; audited by scripts/w3bstream_applet_audit.py).
 *
 * ABI v2 layout (Solidity dynamic-type spec):
 *   [0:4]      selector
 *   [4:36]     deviceId (bytes32, head)
 *   [36:68]    offset to `proof` bytes (uint256 = 0xE0 = 224)
 *              = 7 head-words × 32B = 224B from start of args region
 *   [68:100]   featureCommitment (uint256, head)        [STUB ZERO]
 *   [100:132]  humanityProbInt   (uint256, head)        [STUB ZERO]
 *   [132:164]  inferenceCode     (uint256, head)
 *   [164:196]  nullifierHash     (uint256, head)        [STUB ZERO]
 *   [196:228]  epoch             (uint256, head)        [STUB ZERO]
 *   [228:260]  proof length (uint256, tail)
 *   [260:260+proof_len_padded]  proof data, zero-padded to 32B boundary
 *
 * STUB DEPENDENCIES (Phase O4-VPM-INT-A.PARTIAL):
 *   - featureCommitment requires Poseidon(8-input) over feature vector;
 *     no AS Poseidon reference available (POSEIDON_HASH delta still open);
 *     emitted as zero placeholder for now.
 *   - nullifierHash requires Poseidon(deviceIdHash, epoch); same blocker.
 *   - humanityProbInt requires deriving probability from feature vector;
 *     emitted as zero placeholder.
 *   - epoch requires block.number / EPOCH_BLOCKS; needs W3bstream chain
 *     introspection API not modeled in this stub.
 *   - `bytes proof` requires a real Groth16 proof; emitted as empty bytes
 *     (length=0) for now. ABI shape is correct; payload is empty.
 *
 * The selector + ABI v2 layout shape ARE correct. The cryptographic
 * payload contents are placeholders. When Poseidon + P256 deps land,
 * only the zero-placeholder fills change — the encoder shape is final.
 */
function _encode_submit_proof(rawPtr: i32, inferenceCode: i32, outPtr: i32): i32 {
    // Selector (4 bytes, big-endian)
    _store_u32_be(outPtr, SEL_SUBMIT_PITL_PROOF);

    // Head region (7 × 32B = 224B starting at outPtr + 4):
    //   word 0: deviceId           (bytes32 from PoAC body[0:32])
    //   word 1: offset to proof    (uint256 = 224)
    //   word 2: featureCommitment  (STUB ZERO)
    //   word 3: humanityProbInt    (STUB ZERO)
    //   word 4: inferenceCode      (uint256 from PoAC body byte OFF_INF_CODE)
    //   word 5: nullifierHash      (STUB ZERO)
    //   word 6: epoch              (STUB ZERO)
    const headStart: i32 = outPtr + 4;

    // word 0: deviceId — copy 32B from PoAC body OFF_DEVICE_ID
    memory.copy(headStart, rawPtr + OFF_DEVICE_ID, 32);

    // word 1: offset to proof — 224 (= 7 × 32), encoded as uint256 big-endian
    memory.fill(headStart + 32, 0, 32);
    // 224 fits in one byte; encode at offset 31 (rightmost)
    store<u8>(headStart + 32 + 31, 224);

    // word 2: featureCommitment — STUB ZERO
    memory.fill(headStart + 64, 0, 32);

    // word 3: humanityProbInt — STUB ZERO
    memory.fill(headStart + 96, 0, 32);

    // word 4: inferenceCode — uint256 from inferenceCode byte
    memory.fill(headStart + 128, 0, 32);
    store<u8>(headStart + 128 + 31, <u8>(inferenceCode & 0xFF));

    // word 5: nullifierHash — STUB ZERO
    memory.fill(headStart + 160, 0, 32);

    // word 6: epoch — STUB ZERO
    memory.fill(headStart + 192, 0, 32);

    // Tail region (dynamic `bytes proof`):
    //   word 0: length (uint256) — STUB = 0
    //   word 1+: data padded to 32B boundary — STUB = empty
    const tailStart: i32 = headStart + 224;
    memory.fill(tailStart, 0, 32);  // length = 0 (no data follows)

    // Total calldata length = selector(4) + head(224) + tail_length(32) = 260
    return 4 + 224 + 32;
}

/**
 * Store a u32 in big-endian byte order at the given pointer.
 *
 * AS's native store<u32> is little-endian on wasm32; ABI selectors are
 * big-endian byte sequences ("selector hex" reads MSB-first), so we write
 * byte-by-byte to preserve big-endian layout.
 */
function _store_u32_be(ptr: i32, value: u32): void {
    store<u8>(ptr,     <u8>((value >> 24) & 0xFF));
    store<u8>(ptr + 1, <u8>((value >> 16) & 0xFF));
    store<u8>(ptr + 2, <u8>((value >> 8)  & 0xFF));
    store<u8>(ptr + 3, <u8>(value         & 0xFF));
}

function _log(msg: string): void {
    const encoded = String.UTF8.encode(msg);
    log_info(changetype<i32>(encoded), encoded.byteLength);
}
