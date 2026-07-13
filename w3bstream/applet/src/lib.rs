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

/// EvmLogPayload — mechanical W3bstream ingestion surface.
///
/// DEPIN-1 LEG 2 (W3BSTREAM-VERIFY-1): additive `node_id` + `session_root` +
/// `node_session_verify` (serde default → old payloads parse; verify OFF = byte-identical
/// handler path for legacy fields). Mechanical format/presence only — applet is NOT a
/// truth oracle (does not re-derive node_id or recompute session_root).
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
    #[serde(default)]
    pub events_root: String,
    #[serde(default)]
    pub retina_events_root_verify: bool,
    /// Leg-1 spine: 64-hex SHA-256(QORTROLLER-NODE-v0 || …). Format-checked only.
    #[serde(default)]
    pub node_id: String,
    /// Session proof root (scorecard/PoSP root). 64-hex. Format-checked only.
    #[serde(default)]
    pub session_root: String,
    /// Opt-in gate: when true, both node_id and session_root must be present + well-formed.
    /// Default false → today's behavior for payloads without these fields.
    #[serde(default)]
    pub node_session_verify: bool,
}

#[derive(Serialize, Deserialize, Debug)]
pub struct RecencyResolution {
    pub block_cadence_valid: bool,
    pub pq_proof_resolved: bool,
    pub retina_commitment_valid: bool,
    /// LEG 2: true when node_session gate passes or is unarmed (verify OFF + empty fields).
    pub node_session_gate_ok: bool,
}

/// Per-field mechanical result for the node_id / session_root spine check.
#[derive(Serialize, Deserialize, Debug)]
pub struct NodeSessionResolution {
    pub node_id_valid: bool,
    pub session_root_valid: bool,
    pub node_session_gate_ok: bool,
}

/// Mechanical format check for 32-byte sidecar pointers (PQ, Retina, node_id, session_root).
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

/// DEPIN-1 LEG 2 — mechanical node_id + session_root gate.
///
/// ASSERTS (format/presence only):
/// - each non-empty field is 64-hex non-zero (resolve_sidecar_commitment class)
/// - when `node_session_verify`: both present + well-formed
///
/// MUST NOT:
/// - re-derive node_id from device_id / first_session_id
/// - recompute session_root from scorecard/PoSP surfaces
/// - invent a node_id when ABSENT
/// - claim decentralized truth / on-chain verification of the spine
fn resolve_node_session(
    node_id: &str,
    session_root: &str,
    node_session_verify: bool,
) -> Result<NodeSessionResolution, &'static str> {
    let node_empty = node_id.is_empty();
    let root_empty = session_root.is_empty();

    if node_session_verify {
        // Fail-closed: both required when gate armed
        if node_empty {
            println!("[W3BSTREAM APPLET WARNING] node_session_verify requires node_id");
            return Err("node_session_verify requires non-empty node_id");
        }
        if root_empty {
            println!("[W3BSTREAM APPLET WARNING] node_session_verify requires session_root");
            return Err("node_session_verify requires non-empty session_root");
        }
        resolve_sidecar_commitment(node_id)?;
        resolve_sidecar_commitment(session_root)?;
        return Ok(NodeSessionResolution {
            node_id_valid: true,
            session_root_valid: true,
            node_session_gate_ok: true,
        });
    }

    // Gate OFF: empty = skip (legacy byte-identical); nonempty must still be well-formed
    // (fail-closed on garbage — mirrors events_root nonempty path).
    if !node_empty {
        resolve_sidecar_commitment(node_id)?;
    }
    if !root_empty {
        resolve_sidecar_commitment(session_root)?;
    }

    // Absent fields report valid=false (not well-formed) but gate still OK when unarmed.
    Ok(NodeSessionResolution {
        node_id_valid: !node_empty,
        session_root_valid: !root_empty,
        node_session_gate_ok: true,
    })
}

/// W3bstream message handler entrypoint.
/// Exit codes: 0=ok, 1=bad ptr, 2=utf8, 3=json, 4=cadence, 5=pq, 6=retina, 7=events_root,
/// 8=node_session (DEPIN-1 LEG 2)
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

    if payload.retina_events_root_verify || !payload.events_root.is_empty() {
        if resolve_sidecar_commitment(&payload.events_root).is_err() {
            return 7;
        }
    }

    // DEPIN-1 LEG 2 — node_id + session_root mechanical gate (exit 8)
    let node_session = match resolve_node_session(
        &payload.node_id,
        &payload.session_root,
        payload.node_session_verify,
    ) {
        Ok(res) => res,
        Err(_) => return 8,
    };

    let _resolution = RecencyResolution {
        block_cadence_valid,
        pq_proof_resolved: pq_resolved,
        retina_commitment_valid,
        node_session_gate_ok: node_session.node_session_gate_ok,
    };

    0
}
