# /goal — Retina Phase 2: W3bstream mechanical validation + ingestion wire-up

**Status:** COMPLETE — [PR #37](https://github.com/ConWan30/QorTroller/pull/37) merged 2026-06-20 (PV-CI 179/179; operator GO for invariant_change ceremony)  
**Prerequisite shipped:** PR #35 — Retina DePIN Policy Governor (`feat/retina-depin-policy-governor`, merged 2026-06-20)  
**Architecture anchor:** `docs/retina-w3bstream-integration.md` (Phase D note)  
**Policy anchor:** `docs/retina-depin-policy-governor-v1.md` (Phase 1 complete)

---

## The goal

Extend the existing W3bstream Wasm sandbox (`w3bstream/applet/`) and Python ingestion path so
**`retina_state_commitment`** (32-byte `VAPI-RETINA-STATE-v1`) is validated mechanically on the
same rail as Arc 7 **`pq_commitment`** — without growing the FROZEN 228-byte PoAC wire frame,
without Mahalanobis or dynamics training inside Wasm, and without making Retina a tournament P0
gate (AIT/L4 remain authoritative).

**Success shape:** A cognition-cycle ingestion payload may carry both sidecar pointers; the applet
fail-closes on null/malformed `retina_state_commitment` when the feature flag is on; bridge tests
prove byte-identical commitment recomputation from `retina_event_log`; PV-CI gains `INV-W3S-006` +
`INV-RETINA-001/002` only after explicit `--confirm-governance` ceremony.

---

## Non-goals (honesty rails — do not scope-creep)

| Non-goal | Reason |
|----------|--------|
| PoAC body `sensor_commitment` v2 | Operator decision deferred; wire stays 228B |
| On-chain registry deploy | `CHAIN_SUBMISSION_PAUSED` held; code-side only |
| Tournament / humanity formula weight | Retina stays advisory; FSCA MEDIUM only |
| DA bulk upload (Phase 2b) | Separate goal after W3bstream field lands |
| PDA `RETINA_PERCEPTION_OBSERVATION` (Phase 2c) | Separate goal; depends on commitment rail |
| ZK proof of HID window | Phase 3+; Poseidon ceremony is its own arc |

---

## Namespace discipline (load-bearing)

| Field | Commits to |
|-------|------------|
| PoAC `world_model_hash` | On-device EWC/TinyML world model |
| `pq_commitment` | ML-DSA-65 blob on DePIN DA (Arc 7) |
| `retina_state_commitment` | trio-retina event slice for the cycle |

Never alias or overload these in docs, JSON payloads, or store columns.

---

## Execution plan (Verification-First Discipline)

### Step 0 — V-check (pre-implementation, hold for operator)

- [ ] **V1** Read live `w3bstream/applet/src/lib.rs` — confirm `EvmLogPayload` has only `pq_commitment` today.
- [ ] **V2** Grep bridge ingestion for where `EvmLogPayload` JSON is assembled (if any); document gap vs `dualshock_integration` → `retina_perception` path.
- [ ] **V3** Confirm `compute_retina_state_commitment()` in `retina_state_commitment.py` is the single canonical hasher (no duplicate hash logic).
- [ ] **V4** Run baseline: `python scripts/vapi_invariant_gate.py` (174/174), `cargo build --release --target wasm32-unknown-unknown` in `w3bstream/applet/`, existing W3S tests green.
- [ ] **V5** Operator GO recorded for PV-CI expansion (+3 invariants). Without GO: ship code behind `retina_w3bstream_validation_enabled=False` default only.

### Step 1 — Wasm applet (`w3bstream/applet/`)

**Files:** `src/lib.rs`, optional `Cargo.toml` if serde field rename needed.

1. Add `retina_state_commitment: String` to `EvmLogPayload` (optional empty = skip when flag off).
2. Extract shared `resolve_sidecar_commitment(label, hex)` from `resolve_da_proof` (DRY with PQ).
3. When `retina_w3bstream_enforce` config is true in payload meta OR non-empty field present:
   - Reject zero-padded / empty / non-64-hex (same posture as INV-W3S-005).
   - **Do not** fetch DA or recompute `events_root` in v2.0 — mechanical format check only.
4. Return distinct exit codes: cadence (4), PQ (5), retina (6) — document in applet header comment.
5. `RecencyResolution` gains `retina_commitment_valid: bool`.

**Tests (Rust or bridge integration):** mirror `bridge/tests/test_arc7_pq_sidecar.py` pattern for retina hex cases.

### Step 2 — Python ingestion bridge

**Files (candidate):** new `bridge/vapi_bridge/retina_w3bstream.py` OR extend existing w3bstream helper module.

1. `build_evm_log_payload(record, *, pq_commitment, retina_state_commitment)` — JSON serializer aligned with applet.
2. Wire from `persist_retina_result()` or a thin post-persist hook: when `retina_w3bstream_validation_enabled` and row has `state_commitment_hex`, enqueue validation (sync in tests, async optional in prod).
3. Extend `scripts/test_w3bstream_ingestion.py`:
   - Import/commitment fixture from `retina_state_commitment.py`.
   - Cases: valid 64-hex, empty reject when enforce on, cadence 64/65, env isolation (INV-W3S-002).
4. Optional: `scripts/validate_retina_w3bstream_payload.py` CLI for operator replay from `retina_event_log` row id.

### Step 3 — Config + feature flags

**File:** `bridge/vapi_bridge/config.py`

| Field | Default | Env |
|-------|---------|-----|
| `retina_w3bstream_validation_enabled` | `False` | `RETINA_W3BSTREAM_VALIDATION_ENABLED` |
| `retina_w3bstream_enforce_on_ingest` | `False` | `RETINA_W3BSTREAM_ENFORCE_ON_INGEST` |

Fail-closed: disabled = applet skips retina field validation (backward compat with Arc 6/7 payloads).

### Step 4 — PV-CI ceremony (operator-fired)

**File:** `scripts/vapi_invariant_gate.py`, `.github/INVARIANTS_ALLOWLIST.json`

| ID | Pin |
|----|-----|
| `INV-W3S-006` | Wasm rejects null/malformed `retina_state_commitment` when enforce flag on |
| `INV-RETINA-001` | PoAC wire frame remains 228 bytes with retina+w3bstream enabled (grep `HardForkDisallowedError` / packet size) |
| `INV-RETINA-002` | `retina_perception_enabled` default False in config (already true; pin digest) |

Ceremony requires `--reason invariant_change: ...` + `--confirm-governance`. Baseline **174 → 177**.

### Step 5 — Observability (minimal)

- `GET /bridge/retina-w3bstream-status` — last validation result, enforce flags, last error code (mirror `/bridge/retina-policy-status` shape).
- OpenAPI + SDK slot (`VAPIRetinaW3bstream`) — +4 SDK tests convention.
- **No** new FSCA rules this phase (mechanical validation only).

### Step 6 — P-check + ship

- [ ] **P1** `pytest bridge/tests/test_retina_w3bstream*.py` + extended ingestion script.
- [ ] **P2** `python scripts/vapi_invariant_gate.py` (post-ceremony 177/177).
- [ ] **P3** CI matrix: wasm32 build + `test_w3bstream_ingestion.py`.
- [ ] **P4** Replay one `hw_*` row: commitment in DB == recomputed from events JSON.
- [ ] **P5** Atomic commit → push → PR → merge (autonomous ship discipline per `.cursor/rules/retina-integration-autonomous-ship.mdc`).

---

## Acceptance tests (definition of done)

1. **AT-1:** Applet returns 0 for payload with valid cadence + valid PQ + valid retina hex; returns 6 for zero retina when enforce on.
2. **AT-2:** Ingestion script passes with `OPERATOR_PRIVATE_KEY` popped (INV-W3S-002 preserved).
3. **AT-3:** Enabling all retina+w3bstream flags does not change PoAC encode size (228) in existing packet tests.
4. **AT-4:** `retina_event_log.state_commitment_hex` round-trips through `build_evm_log_payload` without mutation.
5. **AT-5:** PV-CI 177/177 after ceremony; no Solidity/firmware/FROZEN-v1 primitive edits.

---

## Follow-on goals (Phase 2b / 2c — not this /goal)

| Phase | Deliverable | Depends on |
|-------|-------------|------------|
| **2b DA upload** | Route event bulk to `replay_proof_pipeline/da_layer.py`; pointer-only on wire | Phase 2 W3bstream field |
| **2c PDA** | `RETINA_PERCEPTION_OBSERVATION` attestation type + optional anchor | 2b |
| **3 ZK** | Poseidon events_root in-circuit (ZK-SEP precedent) | Stage A measurements + operator GO |

---

## Autonomous ship contract (this arc and future Retina sessions)

When executing this /goal or any subsequent Retina integration phase in chat:

1. Feature branch from `origin/main` (`feat/retina-<phase>-<slug>`).
2. Scope commit to Retina/W3bstream touch surfaces only (no unrelated untracked repo noise).
3. Run targeted pytest + PV-CI gate before push.
4. `git push` → `gh pr create` → `gh pr merge --merge --delete-branch` without waiting for user prompt.
5. Update this /goal file status section + link merged PR in commit body.

**Exception:** PV-CI `invariant_change` ceremony and any mainnet deploy remain operator-explicit GO.

---

## References

- `bridge/vapi_bridge/retina_state_commitment.py` — commitment formula
- `bridge/vapi_bridge/retina_perception.py` — persist + evidence slice
- `bridge/vapi_bridge/retina_depin_policy.py` — HID bind gate (Phase 1)
- `w3bstream/applet/src/lib.rs` — Wasm handler (INV-W3S-001/002/005)
- `bridge/tests/test_arc7_pq_sidecar.py` — sidecar pointer test precedent
- `audits/retina_cross_oracle_latest.json` — clean-corpus cross-oracle baseline
