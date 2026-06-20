# Retina State Commitment — W3bstream Integration Architecture (Phase D)

**Status:** Architecture note only. **No PV-CI invariant edits** until operator GO.

## Purpose

Document how QorTroller's trio-retina advisory layer could extend the existing
W3bstream Wasm applet (`w3bstream/applet/`) without modifying the FROZEN
228-byte PoAC wire format or deploying new contracts during grant-pause.

## Current W3bstream surface (Arc 6/7)

`EvmLogPayload` today carries:

- Block cadence alignment (`block_number % 64 == 0`, INV-W3S-001)
- Clean-environment isolation (INV-W3S-002)
- `pq_commitment` — 32-byte ML-DSA sidecar pointer (INV-W3S-005, Arc 7)

The applet validates **transport and cryptographic commitments**, not full
perception dynamics or HID replay.

## Proposed field: `retina_state_commitment`

Add an optional `bytes32` (or 64-char hex string in JSON) alongside
`pq_commitment`:

```
retina_state_commitment = SHA-256(
    b"VAPI-RETINA-STATE-v1"
    || device_id(32)
    || ts_ns_be(8)
    || events_root(32)
)
```

Where `events_root` is a Merkle or sorted-hash over the canonical JSON of
trio-retina `Event` objects emitted in the cognition window that produced the
PoAC record. The bulk event list and `WorldState.vec` remain **off-chain**
(in `retina_event_log` / DePIN DA), mirroring the Arc 7 PQ sidecar pattern.

### Namespace discipline

| Field | Commits to |
|-------|------------|
| PoAC `world_model_hash` | EWC continual-learning TinyML world model (on-device) |
| `pq_commitment` | ML-DSA-65 signature blob on DA |
| `retina_state_commitment` | trio-retina `WorldState` event slice for the cycle |

These three MUST NOT be overloaded or aliased in docs or code.

## Applet validation rules (future, post-GO)

When `retina_state_commitment` is present and non-zero:

1. Reject zero-padded / malformed hex (same fail-closed posture as INV-W3S-005).
2. Optionally verify `events_root` recomputes from an attached off-chain payload
   fetched via mock DA router (development) or operator-supplied witness.
3. Do **not** run dynamics training or Mahalanobis enrollment inside Wasm —
   mechanical hash + schema version check only.

## Bridge ingestion path (today vs future)

| Layer | Today (Phase A–C) | Future (post-GO) |
|-------|-------------------|------------------|
| HID | `dualshock_integration` → `retina_perception` | unchanged |
| Storage | `retina_event_log` + `agent_events` | + DA upload optional |
| PoAC | Advisory `pitl_meta` only; wire frozen | `sensor_commitment` v2 discussion only |
| W3bstream | Not wired | `retina_state_commitment` in payload JSON |
| On-chain | None (CHAIN_SUBMISSION_PAUSED) | Optional registry view, separate ceremony |

## New invariants (deferred)

Do **not** add to `scripts/vapi_invariant_gate.py` until operator authorizes a
PV-CI ceremony. Candidate IDs (placeholder names only):

- `INV-W3S-006` — Wasm rejects null `retina_state_commitment` when feature flag on
- `INV-RETINA-001` — PoAC wire frame remains 228 bytes when retina enabled
- `INV-RETINA-002` — `retina_perception_enabled` default False in config

## Operator decisions required before implementation

1. Whether `sensor_commitment` (PoAC body) may hash retina slice in v2 schema.
2. Whether W3bstream applet version bumps require new genesis / deployment.
3. Whether Retina events become tournament gates (default: **no** — AIT/L4 remain authoritative).

## References

- `bridge/vapi_bridge/retina_controller_embedder.py` — Phase A encoder
- `bridge/vapi_bridge/retina_perception.py` — Phase B bridge hook
- `w3bstream/applet/src/lib.rs` — existing PQ + cadence validation
- Plan: Trio-Retina × QorTroller — "Retina encoder, PoAC anchor"
