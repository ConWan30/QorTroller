/**
 * Phase 99B — W3bstream AssemblyScript Applet: process_gsr_packet
 *
 * Receives a GSR packet from the physiological grip peripheral, parses
 * arousal and correlation fields, and calls VAPIGSRRegistry.sol.recordSample().
 *
 * GSR packet format (custom, 48 bytes):
 *   [0:4]   — magic bytes: 0x47 0x53 0x52 0x01 ("GSR\x01")
 *   [4:12]  — device_id_hash (first 8 bytes of keccak256 of device_id)
 *   [12:16] — timestamp (uint32 Unix seconds, big-endian)
 *   [16:20] — arousal_millis (uint32, sympathetic_arousal_index * 1000)
 *   [20:24] — correlation_millis (uint32, (r + 1.0) * 500, range 0–1000)
 *   [24:28] — conductance_raw_millis (uint32, μS * 1000)
 *   [28:48] — device_id_bytes32 full (first 20 bytes of 32-byte identifier)
 *
 * Target contract: VAPIGSRRegistry.sol (Phase 99B, pending deploy)
 * GSR is ADVISORY ONLY — inference code 0x33 GSR_CORRELATION_ABSENT never hard gates.
 * GSR_ENABLED=false until N≥30 real calibration sessions per player.
 *
 * Status: AssemblyScript stub — compiles to WASM via asc.
 * W3bstream project ID: cfg.w3bstream_project_id
 */

// AssemblyScript runtime declarations (injected by W3bstream executor)
declare function env_get_message(ptr: i32, maxLen: i32): i32;
declare function chain_call(contractAddr: i32, addrLen: i32, calldata: i32, calldataLen: i32): i32;
declare function log_info(msg: i32, msgLen: i32): void;

const GSR_PACKET_LEN: i32 = 48;
const GSR_MAGIC: u32 = 0x47535201;  // "GSR\x01"

// Offsets within GSR packet
const OFF_MAGIC: i32 = 0;
const OFF_DEVICE_SHORT: i32 = 4;   // 8-byte short hash
const OFF_TIMESTAMP: i32 = 12;
const OFF_AROUSAL: i32 = 16;
const OFF_CORRELATION: i32 = 20;
const OFF_CONDUCTANCE: i32 = 24;
const OFF_DEVICE_FULL: i32 = 28;   // 20 bytes of the 32-byte device_id

/**
 * Entry point — called by W3bstream runtime for each GSR message.
 * Returns 0 on success, non-zero on failure.
 */
export function handle_gsr_packet(): i32 {
    const buf = memory.grow(1);
    const rawPtr: i32 = buf << 16;

    // Read packet
    const msgLen = env_get_message(rawPtr, GSR_PACKET_LEN);
    if (msgLen < GSR_PACKET_LEN) {
        _log("process_gsr_packet: invalid length " + msgLen.toString());
        return 1;
    }

    // Validate magic bytes
    const magic = bswap<u32>(load<u32>(rawPtr + OFF_MAGIC));
    if (magic != GSR_MAGIC) {
        _log("process_gsr_packet: bad magic — not a GSR packet");
        return 2;
    }

    // Parse fields
    const timestamp = bswap<u32>(load<u32>(rawPtr + OFF_TIMESTAMP));
    const arousalMillis = bswap<u32>(load<u32>(rawPtr + OFF_AROUSAL));
    const correlationMillis = bswap<u32>(load<u32>(rawPtr + OFF_CORRELATION));

    // Validate ranges
    if (arousalMillis > 1000) {
        _log("process_gsr_packet: arousal_millis out of range: " + arousalMillis.toString());
        return 3;
    }
    if (correlationMillis > 1000) {
        _log("process_gsr_packet: correlation_millis out of range: " + correlationMillis.toString());
        return 4;
    }

    // Build 32-byte deviceId: pad 20 bytes from packet + 12 zero bytes
    const deviceIdPtr = rawPtr + GSR_PACKET_LEN;  // scratch space after packet
    memory.copy(deviceIdPtr, rawPtr + OFF_DEVICE_FULL, 20);
    memory.fill(deviceIdPtr + 20, 0, 12);  // zero-pad to 32 bytes

    // ABI encode VAPIGSRRegistry.recordSample(bytes32,uint256,uint256,uint256)
    const calldataPtr = deviceIdPtr + 32;
    const calldataLen = _encode_record_sample(deviceIdPtr, arousalMillis, correlationMillis, timestamp, calldataPtr);

    // Call VAPIGSRRegistry (address configured by W3bstream project environment)
    const addrPtr: i32 = 0;  // runtime-injected registry address
    const result = chain_call(addrPtr, 20, calldataPtr, calldataLen);
    if (result != 0) {
        _log("process_gsr_packet: chain_call failed — code " + result.toString());
        return 5;
    }

    _log(
        "process_gsr_packet: recorded — arousal=" + arousalMillis.toString() +
        " corr=" + correlationMillis.toString() +
        " ts=" + timestamp.toString()
    );
    return 0;
}

// --- Private helpers ---

function _encode_record_sample(
    deviceIdPtr: i32,
    arousalMillis: u32,
    correlationMillis: u32,
    timestamp: u32,
    outPtr: i32
): i32 {
    // ABI encode: recordSample(bytes32 deviceId, uint256 arousal, uint256 corr, uint256 ts)
    // Function selector placeholder — replace with keccak256("recordSample(bytes32,uint256,uint256,uint256)")[0:4]
    store<u32>(outPtr, 0xCAFEBABE);  // selector placeholder
    memory.copy(outPtr + 4, deviceIdPtr, 32);                        // deviceId (bytes32)
    store<u64>(outPtr + 4 + 32 + 24, bswap<u64>(arousalMillis));     // uint256 arousal (last 8B of 32)
    store<u64>(outPtr + 4 + 64 + 24, bswap<u64>(correlationMillis)); // uint256 corr
    store<u64>(outPtr + 4 + 96 + 24, bswap<u64>(timestamp));         // uint256 ts
    return 4 + 32 + 32 + 32 + 32;  // selector + 4 ABI-encoded params
}

function _log(msg: string): void {
    const encoded = String.UTF8.encode(msg);
    log_info(changetype<i32>(encoded), encoded.byteLength);
}
