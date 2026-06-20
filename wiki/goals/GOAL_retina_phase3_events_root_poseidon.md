# /goal — Retina Phase 3: Poseidon `events_root` (off-chain ZK-prep)

**Status:** COMPLETE ([PR #41](https://github.com/ConWan30/QorTroller/pull/41), `29ce63a9`)  
**Prerequisite:** Phase 2c PDA attestation COMPLETE ([PR #40](https://github.com/ConWan30/QorTroller/pull/40), `0ffa70f8`)  
**Architecture anchor:** `bridge/vapi_bridge/retina_events_root.py` + `retina_zk_artifacts/compute_retina_events_root.js`  
**Sidecar discipline:** `events_root` stays off-chain; only 32-byte roots cross W3bstream / `retina_state_commitment` (PoAC 228B unchanged)

---

## The goal

Ship **off-chain Poseidon-2 `events_root`** over canonical trio-retina event JSON, wired into
`VAPI-RETINA-STATE-v2` commitments and optional W3bstream mechanical recompute validation.
Full in-circuit Groth16 (`VAPIRetinaEventsRoot.circom`) remains **deferred** pending operator GO
+ ceremony (ZK-SEP / Arc 5 precedent).

**Success shape:**

- `compute_events_root_poseidon()` + circomlibjs node helper produce deterministic 32-byte roots
- `compute_retina_state_commitment_v2()` uses Poseidon root + `VAPI-RETINA-STATE-v2` domain tag
- Phase 2 v1 SHA-256 root remains default (`RETINA_EVENTS_ROOT_POSEIDON_ENABLED=false`)
- W3bstream payload optional fields: `events_root`, `retina_events`, `retina_events_root_verify`
- Wasm exit code **7** on malformed `events_root`; Python mirror recomputes when verify flag set

---

## Non-goals

| Non-goal | Reason |
|----------|--------|
| circom circuit + Groth16 ceremony | Operator GO + PV-CI ceremony deferred |
| PoAC 228B wire growth | Sidecar pointer only |
| Wasm Poseidon recompute | Mechanical format check in Rust; recompute in Python mirror |
| FROZEN-v1 / PV-CI invariant bump | No new invariants this phase |

---

## Config

| Field | Default | Env |
|-------|---------|-----|
| `retina_events_root_poseidon_enabled` | `False` | `RETINA_EVENTS_ROOT_POSEIDON_ENABLED` |
| `retina_events_root_verify_on_ingest` | `False` | `RETINA_EVENTS_ROOT_VERIFY_ON_INGEST` |

---

## Acceptance tests

1. **AT-1:** Canonical event lines order-independent → same field elements / root.
2. **AT-2:** v1 SHA-256 vs v2 Poseidon commitments differ for same events.
3. **AT-3:** `verify_events_root_recompute` pass/fail on match/mismatch.
4. **AT-4:** W3bstream validate exit **7** when `retina_events_root_verify` + bad root.
5. **AT-5:** Optional node+circomlibjs integration test (skip when deps absent).

---

## Operator decisions (full in-circuit ZK)

1. Authorize `VAPIRetinaEventsRoot.circom` + pot reuse vs new ceremony.
2. Pin PV-CI invariants for in-circuit Poseidon binding (candidate post-GO).
3. Whether tournament / marketplace surfaces require Groth16 proof vs off-chain root only.

---

## Follow-on

| Phase | Deliverable |
|-------|-------------|
| **3b ZK** | circom circuit proving Poseidon chain matches public `events_root` |
| **3c DA** | DA witness bundle `{events, events_root}` keyed by commitment |

---

## References

- `docs/retina-w3bstream-integration.md`
- `bridge/vapi_bridge/replay_proof_pipeline/zk_artifacts/compute_inputs_replay_proof.js` (Poseidon-2 chain precedent)
- `wiki/goals/GOAL_retina_phase2c_pda_attestation.md`
