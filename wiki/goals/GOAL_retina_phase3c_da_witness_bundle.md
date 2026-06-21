# /goal — Retina Phase 3c: DA witness bundle keyed by `events_root`

**Status:** COMPLETE ([PR #45](https://github.com/ConWan30/QorTroller/pull/45), `e1cca900`)  
**Prerequisite:** Phase 3 COMPLETE ([PR #41](https://github.com/ConWan30/QorTroller/pull/41), `29ce63a9`)  
**Architecture anchor:** `bridge/vapi_bridge/retina_da_witness.py`  
**Sidecar discipline:** witness JSON lives off-chain on `da_router`; DA key is **`events_root` only** (32B); `state_commitment_hex` is metadata for auditors

---

## The goal

Ship a **prover-fetchable DA witness bundle** `{events, events_root}` keyed by **`events_root`**
after W3bstream validation passes in `persist_retina_result`. Complements Phase 2b bulk upload
(keyed by `state_commitment`) without replacing it.

**Success shape:**

- Witness schema `vapi-retina-da-witness-v1` on `da_router` keyed by `events_root` bytes
- `retina_da_witness_log` table + `GET /bridge/retina-da-status` witness block
- `RETINA_DA_WITNESS_ENABLED` default `False`; fail-closed on `w3bstream_exit_code != 0`

---

## Non-goals

| Non-goal | Reason |
|----------|--------|
| Phase 3b circom / Groth16 | Operator GO + ceremony deferred |
| PoAC 228B wire growth | Sidecar pointer only |
| Wasm DA fetch | Mechanical validation only in Rust applet |
| PV-CI `--confirm-governance` | No new invariants this phase |
| On-chain deploy | `CHAIN_SUBMISSION_PAUSED` held |

---

## Config

| Field | Default | Env |
|-------|---------|-----|
| `retina_da_witness_enabled` | `False` | `RETINA_DA_WITNESS_ENABLED` |

Uses `retina_events_root_poseidon_enabled` to select `events_root_scheme` (`poseidon_v1` vs `sha256_v1`).

---

## Witness schema `vapi-retina-da-witness-v1`

```json
{
  "schema": "vapi-retina-da-witness-v1",
  "device_id": "...",
  "record_hash_hex": "...",
  "ts_ns": 123,
  "events_root_scheme": "sha256_v1" | "poseidon_v1",
  "events_root_hex": "64-char hex",
  "state_commitment_hex": "...",
  "events": [ ... ]
}
```

`state_commitment_hex` is **metadata only** (cross-link for auditors); DA key is **`events_root` bytes**.

---

## Acceptance tests

1. **AT-1:** Witness round-trip upload/download by `events_root` key.
2. **AT-2:** Disabled flag → no DA write, no log row.
3. **AT-3:** `w3bstream_exit_code != 0` → skipped.
4. **AT-4:** `persist_retina_result` chains witness when flags on.
5. **AT-5:** SHA256 vs Poseidon scheme produces distinct roots; witness keyed by computed root.
6. **AT-6:** Bulk upload (2b) and witness upload (3c) coexist — different DA keys.

---

## Follow-on

| Phase | Deliverable |
|-------|-------------|
| **3b ZK** | `VAPIRetinaEventsRoot.circom` + Groth16 ceremony (operator GO) |
| **Live verifier** | `scripts/verify_retina_phase3c_live.py` (optional post-merge) |

---

## References

- `bridge/vapi_bridge/retina_da_upload.py` (Phase 2b bulk pattern)
- `bridge/vapi_bridge/retina_events_root.py` (Poseidon root)
- `wiki/goals/GOAL_retina_phase3_events_root_poseidon.md`
