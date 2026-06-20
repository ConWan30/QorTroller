# /goal — Retina Phase 2c: `RETINA_PERCEPTION_OBSERVATION` PDA attestation

**Status:** COMPLETE ([PR #40](https://github.com/ConWan30/QorTroller/pull/40), `0ffa70f8`)  
**Prerequisite:** Phase 2b DA upload COMPLETE ([PR #38](https://github.com/ConWan30/QorTroller/pull/38))  
**Architecture anchor:** `bridge/vapi_bridge/physical_data_attestation.py` (FROZEN PDA v1)  
**Sidecar discipline:** `retina_state_commitment` is the 32-byte hardware_data_hash input to PDA

---

## The goal

After W3bstream validation (`exit_code=0`) and optional DA bulk upload, record a
**PHYSICAL_DATA_ATTESTATION v1** row with canonical type
`RETINA_PERCEPTION_OBSERVATION`, binding the bridge agent to the off-chain
`retina_state_commitment` pointer. Local log only — no on-chain anchor unless
operator lifts `CHAIN_SUBMISSION_PAUSED` and enables anchor flag.

**Success shape:** `persist_retina_result` chains PDA insert when
`retina_pda_attestation_enabled=true`; `GET /bridge/retina-pda-status` surfaces
latest attestation; tests prove deterministic `pda_commitment` + idempotent insert.

---

## Non-goals

| Non-goal | Reason |
|----------|--------|
| PoAC 228B wire growth | Off-chain PDA log only |
| FROZEN PDA formula change | v1 frozen; new type string only |
| PV-CI invariant bump | No new invariants |
| On-chain anchor (default) | `CHAIN_SUBMISSION_PAUSED` held |

---

## Config

| Field | Default | Env |
|-------|---------|-----|
| `retina_pda_attestation_enabled` | `False` | `RETINA_PDA_ATTESTATION_ENABLED` |
| `retina_pda_attestation_agent_id` | `bridge_agent` | `RETINA_PDA_ATTESTATION_AGENT_ID` |

---

## Acceptance tests

1. **AT-1:** `compute_pda_hash` with `RETINA_PERCEPTION_OBSERVATION` + commitment bytes.
2. **AT-2:** Disabled flag → no `physical_data_attestation_log` row.
3. **AT-3:** W3bstream `exit_code!=0` → PDA skipped.
4. **AT-4:** `persist_retina_result` integration writes PDA when flags on.
5. **AT-5:** Duplicate persist → idempotent PDA row (UNIQUE on commitment).

---

## Follow-on

| Phase | Deliverable |
|-------|-------------|
| **3 ZK** | Poseidon `events_root` in-circuit |

---

## References

- `bridge/vapi_bridge/retina_pda_attestation.py`
- `bridge/tests/test_retina_pda_attestation.py`
