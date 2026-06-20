# /goal — Retina Phase 2b: DA bulk upload for `retina_event_log`

**Status:** IN PROGRESS — `feat/retina-phase2b-da-upload`  
**Prerequisite:** Phase 2 W3bstream COMPLETE ([PR #37](https://github.com/ConWan30/QorTroller/pull/37))  
**Architecture anchor:** `docs/retina-w3bstream-integration.md` (sidecar pointer pattern)  
**Arc 7 precedent:** `bridge/vapi_bridge/replay_proof_pipeline/da_layer.py`

---

## The goal

Route the **bulk** trio-retina event JSON from `retina_event_log` to the mock DePIN DA layer
(`da_router`), keyed by the existing 32-byte `retina_state_commitment`. Only the pointer crosses
ingestion/wire boundaries — same Decoupled Cryptographic Sidecar Pointer discipline as Arc 7
`pq_commitment`.

**Success shape:** After W3bstream validation passes (`exit_code=0`), `persist_retina_result`
optionally uploads canonical `vapi-retina-da-bulk-v1` JSON to DA; `GET /bridge/retina-da-status`
surfaces upload log; tests prove round-trip download by commitment hash.

---

## Non-goals

| Non-goal | Reason |
|----------|--------|
| PoAC 228B wire growth | Pointer-only on wire |
| Wasm DA fetch / events_root recompute | Phase 3+ |
| On-chain deploy | `CHAIN_SUBMISSION_PAUSED` held |
| PV-CI invariant bump | No new invariants this phase |

---

## Config

| Field | Default | Env |
|-------|---------|-----|
| `retina_da_upload_enabled` | `False` | `RETINA_DA_UPLOAD_ENABLED` |

Upload runs only when **also** `retina_w3bstream_validation_enabled` path returned `exit_code=0`.

---

## Acceptance tests

1. **AT-1:** `upload_retina_bulk_to_da` + `download_retina_bulk_from_da` round-trip by commitment.
2. **AT-2:** Disabled flag → no DA write, no log row with `uploaded=1`.
3. **AT-3:** W3bstream `exit_code!=0` → DA upload skipped (fail-closed).
4. **AT-4:** `persist_retina_result` integration writes `retina_da_upload_log` when both flags on.
5. **AT-5:** PoAC 228B unchanged; PV-CI 179/179 without ceremony.

---

## Follow-on

| Phase | Deliverable |
|-------|-------------|
| **2c PDA** | `RETINA_PERCEPTION_OBSERVATION` attestation + optional anchor |
| **3 ZK** | Poseidon `events_root` in-circuit |

---

## References

- `bridge/vapi_bridge/retina_da_upload.py`
- `bridge/tests/test_retina_da_upload.py`
- `bridge/tests/test_arc7_pq_sidecar.py`
