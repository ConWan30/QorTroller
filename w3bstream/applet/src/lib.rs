use serde::{Deserialize, Serialize};
use std::slice;

const ANCHOR_CADENCE: u64 = 64;

#[derive(Serialize, Deserialize, Debug)]
pub struct PoACPayload {
    pub device_id: String,
    pub block_number: u64,
    pub payload_hash: String,
    pub signature: String,
}

#[derive(Serialize, Deserialize, Debug)]
pub struct EvmLogPayload {
    pub device_id: String,
    pub block_number: u64,
    pub payload_hash: String,
    pub signature: String,
    pub pq_commitment: String,
    #[serde(default)]
    pub retina_state_commitment: String,
    #[serde(default)]
    pub retina_w3bstream_enforce: bool,
}

#[derive(Serialize, Deserialize, Debug)]
pub struct RecencyResolution {
    pub block_cadence_valid: bool,
    pub pq_proof_resolved: bool,
    pub retina_commitment_valid: bool,
}

/// Mechanical format check for 32-byte sidecar pointers (PQ, Retina, etc.).
/// Fail-closed on zero-padded / empty / non-64-hex commitments.
fn resolve_sidecar_commitment(commitment_hex: &str) -> Result<(), &'static str> {
    let is_zero_padded = commitment_hex.is_empty()
        || commitment_hex
            .chars()
            .all(|c| c == '0' || c == 'x' || c == 'X');

    if is_zero_padded {
        println!(
            "[W3BSTREAM APPLET WARNING] sidecar commitment is zero-padded or empty: {}",
            commitment_hex
        );
        return Err("Zero-padded or empty sidecar commitment is forbidden");
    }

    let cleaned = if commitment_hex.starts_with("0x") || commitment_hex.starts_with("0X") {
        &commitment_hex[2..]
    } else {
        commitment_hex
    };

    if cleaned.len() != 64 || !cleaned.chars().all(|c| c.is_ascii_hexdigit()) {
        println!(
            "[W3BSTREAM APPLET WARNING] sidecar commitment format invalid: {}",
            commitment_hex
        );
        return Err("Invalid sidecar commitment format");
    }

    Ok(())
}

/// Simulates a host call to the DePIN DA storage layer for PQ payloads.
fn resolve_da_proof(pq_commitment: &str) -> Result<bool, &'static str> {
    resolve_sidecar_commitment(pq_commitment)?;

    // Mock a successful 3,309-byte payload match (ML-DSA-65 signature)
    let mock_payload = vec![0u8; 3309];
    if mock_payload.len() == 3309 {
        Ok(true)
    } else {
        Err("DA resolution payload mismatch")
    }
}

/// W3bstream message handler entrypoint.
/// Exit codes: 0=ok, 1=bad ptr, 2=utf8, 3=json, 4=cadence, 5=pq, 6=retina
///
/// Strictly mechanical input validation — no frame-grabbing, optical capture,
/// or Mahalanobis enrollment inside Wasm.
#[no_mangle]
pub extern "C" fn handle_poac_payload(ptr: *const u8, size: usize) -> i32 {
    if ptr.is_null() || size == 0 {
        return 1;
    }

    let slice = unsafe { slice::from_raw_parts(ptr, size) };
    let payload_str = match std::str::from_utf8(slice) {
        Ok(s) => s,
        Err(_) => return 2,
    };

    let payload: EvmLogPayload = match serde_json::from_str(payload_str) {
        Ok(p) => p,
        Err(_) => return 3,
    };

    // INV-W3S-001
    let block_cadence_valid = payload.block_number % ANCHOR_CADENCE == 0;
    if !block_cadence_valid {
        return 4;
    }

    // INV-W3S-005
    let pq_resolved = match resolve_da_proof(&payload.pq_commitment) {
        Ok(res) => res,
        Err(_) => return 5,
    };

    // INV-W3S-006
    let retina_nonempty = !payload.retina_state_commitment.is_empty();
    let retina_commitment_valid = if payload.retina_w3bstream_enforce || retina_nonempty {
        match resolve_sidecar_commitment(&payload.retina_state_commitment) {
            Ok(()) => true,
            Err(_) => return 6,
        }
    } else {
        true
    };

    let _resolution = RecencyResolution {
        block_cadence_valid,
        pq_proof_resolved: pq_resolved,
        retina_commitment_valid,
    };

    0
}
